"""Schema and reference-data configuration for the pipeline.

Everything that is specific to *observed* values (canonical product names,
known platforms, etc.) lives here as data, not scattered through the cleaning
logic. Callers can override any of it (see ``PipelineConfig.load``) so a
different source file with a different product catalogue does not require
touching the code.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# Columns required to be present in the input file(s). This is the contract
# of the "target schema" the task describes; the pipeline refuses files that
# don't have these columns rather than guessing.
REQUIRED_COLUMNS = [
    "response_id",
    "submitted_at",
    "product",
    "product_version",
    "platform",
    "country",
    "user_segment",
    "score1",
    "score2",
]

SCORE_MIN = 1
SCORE_MAX = 5

UNKNOWN = "unknown"


@dataclass
class PipelineConfig:
    # Canonical product names. Incoming values are normalized (trim, case,
    # spacing) and fuzzy-matched against this list; unmatched values reject
    # the row because aggregation "by product" can't put them anywhere sane.
    known_products: list[str] = field(
        default_factory=lambda: [
            "Checkout",
            "Payments",
            "Search",
            "Onboarding",
            "Profile",
        ]
    )
    # Minimum fuzzy-match similarity (difflib ratio) to accept a product
    # value as a known product after normalization.
    product_match_cutoff: float = 0.75

    # Canonical platform names. Unlike product, an unrecognized/missing
    # platform does NOT reject the row (it isn't needed for the score and
    # aggregation just buckets it as "unknown") -- only used to normalize.
    known_platforms: list[str] = field(default_factory=lambda: ["Web", "Android", "iOS"])
    platform_match_cutoff: float = 0.6

    known_segments: list[str] = field(default_factory=lambda: ["new", "returning", "power"])
    segment_match_cutoff: float = 0.6

    # Sanity bounds for submitted_at; rows outside this are rejected as
    # invalid dates (catches things like typo'd years, epoch defaults, etc).
    min_year: int = 2015
    max_year: int = 2100

    score_min: int = SCORE_MIN
    score_max: int = SCORE_MAX

    @classmethod
    def load(cls, path: str | None) -> "PipelineConfig":
        if not path:
            return cls()
        data: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
