"""End-to-end orchestration: load -> normalize -> validate -> score -> aggregate -> report.

Idempotent by construction: every run reads only its inputs and writes a
fresh, fully-overwritten set of output files (no append-to-log, no
incremental state), so running twice on the same input yields the same
output rather than doubled counts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import aggregation, cleaning, scoring
from .config import PipelineConfig

logger = logging.getLogger("umux_pipeline")


@dataclass
class PipelineResult:
    valid: pd.DataFrame
    rejected: pd.DataFrame
    overview: dict
    reasons: pd.DataFrame
    by_product: pd.DataFrame
    by_product_version: pd.DataFrame
    by_month_product: pd.DataFrame
    by_segment: pd.DataFrame
    report_path: Path | None = None


def _setup_logging(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    log_path = outdir / "pipeline.log"
    root = logging.getLogger("umux_pipeline")
    root.setLevel(logging.INFO)
    root.handlers.clear()
    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(fh)
    root.addHandler(sh)


def run_pipeline(
    inputs: list[str],
    outdir: str | Path,
    config: PipelineConfig | None = None,
    write_report: bool = True,
) -> PipelineResult:
    outdir = Path(outdir)
    _setup_logging(outdir)
    config = config or PipelineConfig()

    logger.info("запуск пайплайна: %s входных файл(ов)", len(inputs))
    raw = cleaning.load_inputs(inputs)
    normalized = cleaning.normalize(raw, config)
    valid, rejected = cleaning.validate(normalized, config)
    valid = scoring.compute_umux(valid)

    ov = aggregation.overview(valid, rejected)
    reasons = aggregation.rejection_summary(valid, rejected)
    prod_df = aggregation.by_product(valid)
    prod_version_df = aggregation.by_product_version(valid)
    month_prod_df = aggregation.by_month_product(valid)
    segment_df = aggregation.by_segment(valid)

    outdir.mkdir(parents=True, exist_ok=True)
    valid.to_csv(outdir / "clean_scored.csv", index=False)
    rejected.to_csv(outdir / "rejected_rows.csv", index=False)
    reasons.to_csv(outdir / "rejection_reasons.csv", index=False)
    prod_df.to_csv(outdir / "agg_by_product.csv", index=False)
    prod_version_df.to_csv(outdir / "agg_by_product_version.csv", index=False)
    month_prod_df.to_csv(outdir / "agg_by_month_product.csv", index=False)
    segment_df.to_csv(outdir / "agg_by_segment.csv", index=False)
    pd.Series(ov).to_json(outdir / "overview.json", indent=2)

    report_path = None
    if write_report:
        from . import report as report_mod

        report_path = report_mod.build_report(
            outdir, ov, reasons, prod_df, prod_version_df, month_prod_df, segment_df
        )
        logger.info("отчёт записан в %s", report_path)

    logger.info("пайплайн завершён: %s", ov)
    return PipelineResult(
        valid=valid,
        rejected=rejected,
        overview=ov,
        reasons=reasons,
        by_product=prod_df,
        by_product_version=prod_version_df,
        by_month_product=month_prod_df,
        by_segment=segment_df,
        report_path=report_path,
    )
