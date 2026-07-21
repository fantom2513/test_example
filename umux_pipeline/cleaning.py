"""Loading, normalization and row-level validation.

Design: every row is normalized first (whitespace/case/typo-tolerant
matching against reference values), then validated. A row is REJECTED
(excluded from scoring/aggregation) only when a field that is actually
required for scoring or product-level aggregation is missing or
unrecoverable. Fields that are descriptive-only (platform, country,
segment) fall back to "unknown" instead of rejecting the row, so a
pipeline running on real, messy exports doesn't throw away a fifth of the
data over a blank "country" cell.
"""
from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import PipelineConfig, REQUIRED_COLUMNS, UNKNOWN

logger = logging.getLogger("umux_pipeline.cleaning")


@dataclass
class LoadResult:
    raw: pd.DataFrame


def load_inputs(paths: list[str]) -> pd.DataFrame:
    """Load one or more CSV files of the same target schema and concatenate them.

    Every value is read as a string so normalization has full control over
    type coercion later -- letting pandas guess dtypes on dirty input is how
    silent corruption (e.g. "1.20" -> 1.2 float) creeps in.
    """
    frames = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {p}")
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"{p}: missing required columns {missing}")
        df = df[REQUIRED_COLUMNS].copy()
        df["source_file"] = path.name
        frames.append(df)
        logger.info("загружено %s строк из %s", len(df), path.name)
    combined = pd.concat(frames, ignore_index=True)
    combined["source_row"] = combined.index
    return combined


def _clean_str(v: str) -> str:
    return " ".join(str(v).strip().split())


def _fuzzy_match(value: str, choices: list[str], cutoff: float) -> str | None:
    if not value:
        return None
    norm = value.strip().lower().replace(" ", "").replace("-", "").replace("_", "")
    for choice in choices:
        if choice.lower().replace(" ", "") == norm:
            return choice
    match = difflib.get_close_matches(
        norm, [c.lower().replace(" ", "") for c in choices], n=1, cutoff=cutoff
    )
    if not match:
        return None
    idx = [c.lower().replace(" ", "") for c in choices].index(match[0])
    return choices[idx]


def normalize(df: pd.DataFrame, config: PipelineConfig) -> pd.DataFrame:
    out = df.copy()

    out["response_id"] = out["response_id"].map(_clean_str)
    out["product_version"] = out["product_version"].map(_clean_str)
    out["submitted_at"] = out["submitted_at"].map(_clean_str)

    out["product_norm"] = out["product"].map(
        lambda v: _fuzzy_match(v, config.known_products, config.product_match_cutoff)
    )

    out["platform_norm"] = out["platform"].map(
        lambda v: _fuzzy_match(v, config.known_platforms, config.platform_match_cutoff) or UNKNOWN
    )

    out["country_norm"] = out["country"].map(
        lambda v: _clean_str(v).upper() if _clean_str(v) else UNKNOWN
    )

    out["segment_norm"] = out["user_segment"].map(
        lambda v: _fuzzy_match(v, config.known_segments, config.segment_match_cutoff) or UNKNOWN
    )

    out["submitted_at_dt"] = pd.to_datetime(out["submitted_at"], errors="coerce")

    def _to_score(v: str):
        v = _clean_str(v)
        if not v:
            return None
        try:
            f = float(v)
        except ValueError:
            return None
        if f != int(f):
            return None
        return int(f)

    out["score1_norm"] = out["score1"].map(_to_score)
    out["score2_norm"] = out["score2"].map(_to_score)

    return out


def validate(df: pd.DataFrame, config: PipelineConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split normalized rows into (valid, rejected). ``rejected`` carries a
    ``reject_reason`` column; a row can only have one reason (first failing
    check wins) to keep the rejection log easy to read.
    """
    reasons = pd.Series([None] * len(df), index=df.index, dtype=object)

    def mark(mask, reason):
        nonlocal reasons
        unset = reasons.isna()
        hit = mask & unset
        reasons.loc[hit] = reason

    mark(df["response_id"] == "", "missing_response_id")
    mark(df["submitted_at_dt"].isna(), "invalid_submitted_at")
    mark(
        df["submitted_at_dt"].dt.year.lt(config.min_year)
        | df["submitted_at_dt"].dt.year.gt(config.max_year),
        "submitted_at_out_of_range",
    )
    mark(df["product_norm"].isna(), "unrecognized_product")
    mark(df["product_version"] == "", "missing_product_version")
    mark(df["score1_norm"].isna(), "missing_or_invalid_score1")
    mark(df["score2_norm"].isna(), "missing_or_invalid_score2")
    mark(
        df["score1_norm"].notna()
        & ~df["score1_norm"].between(config.score_min, config.score_max),
        "score1_out_of_range",
    )
    mark(
        df["score2_norm"].notna()
        & ~df["score2_norm"].between(config.score_min, config.score_max),
        "score2_out_of_range",
    )
    # exact full-row duplicates (identical response_id + payload): keep the
    # first occurrence, reject the rest before we even get to conflict
    # resolution below.
    dup_cols = [
        "response_id",
        "submitted_at",
        "product_norm",
        "product_version",
        "score1_norm",
        "score2_norm",
    ]
    exact_dup = df.duplicated(subset=dup_cols, keep="first")
    mark(exact_dup, "exact_duplicate_row")

    rejected_mask = reasons.notna()
    rejected = df[rejected_mask].copy()
    rejected["reject_reason"] = reasons[rejected_mask]

    survivors = df[~rejected_mask].copy()

    # Same response_id, different payload (conflicting duplicate): keep the
    # first surviving row (deterministic given stable input order), reject
    # the rest as conflicting duplicates.
    conflict_dup = survivors.duplicated(subset=["response_id"], keep="first")
    conflict_rejected = survivors[conflict_dup].copy()
    conflict_rejected["reject_reason"] = "conflicting_duplicate_response_id"

    valid = survivors[~conflict_dup].copy()
    rejected = pd.concat([rejected, conflict_rejected], ignore_index=True)

    logger.info(
        "валидация: %s валидных, %s отбраковано",
        len(valid),
        len(rejected),
    )
    for reason, count in rejected["reject_reason"].value_counts().items():
        logger.info(
            "  отбраковано[%s] = %s",
            reason,
            count,
        )

    return valid.reset_index(drop=True), rejected.reset_index(drop=True)
