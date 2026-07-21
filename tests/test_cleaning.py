import pandas as pd

from umux_pipeline.cleaning import normalize, validate
from umux_pipeline.config import PipelineConfig

COLS = [
    "response_id",
    "submitted_at",
    "product",
    "product_version",
    "platform",
    "country",
    "user_segment",
    "score1",
    "score2",
    "source_file",
    "source_row",
]


def make_df(rows):
    return pd.DataFrame(rows, columns=COLS)


def test_product_typo_and_case_normalized():
    df = make_df(
        [
            ["R1", "2024-01-01 00:00:00", "Serch", "1.2", "Web", "RU", "new", "3", "4", "f", 0],
            ["R2", "2024-01-01 00:00:00", "CHECK OUT", "1.2", "Web", "RU", "new", "3", "4", "f", 1],
        ]
    )
    norm = normalize(df, PipelineConfig())
    assert norm.loc[0, "product_norm"] == "Search"
    assert norm.loc[1, "product_norm"] == "Checkout"


def test_unrecognized_product_rejected():
    df = make_df(
        [["R1", "2024-01-01 00:00:00", "Nonsense123", "1.2", "Web", "RU", "new", "3", "4", "f", 0]]
    )
    norm = normalize(df, PipelineConfig())
    valid, rejected = validate(norm, PipelineConfig())
    assert len(valid) == 0
    assert rejected.loc[0, "reject_reason"] == "unrecognized_product"


def test_missing_platform_country_segment_kept_as_unknown():
    df = make_df(
        [["R1", "2024-01-01 00:00:00", "Profile", "1.2", "", "", "", "3", "4", "f", 0]]
    )
    norm = normalize(df, PipelineConfig())
    valid, rejected = validate(norm, PipelineConfig())
    assert len(valid) == 1
    assert valid.loc[0, "platform_norm"] == "unknown"
    assert valid.loc[0, "country_norm"] == "unknown"
    assert valid.loc[0, "segment_norm"] == "unknown"


def test_out_of_range_score_rejected():
    df = make_df(
        [["R1", "2024-01-01 00:00:00", "Profile", "1.2", "Web", "RU", "new", "0", "4", "f", 0]]
    )
    norm = normalize(df, PipelineConfig())
    valid, rejected = validate(norm, PipelineConfig())
    assert len(valid) == 0
    assert rejected.loc[0, "reject_reason"] == "score1_out_of_range"


def test_exact_duplicate_rejected():
    row = ["R1", "2024-01-01 00:00:00", "Profile", "1.2", "Web", "RU", "new", "3", "4", "f", 0]
    df = make_df([row, row])
    norm = normalize(df, PipelineConfig())
    valid, rejected = validate(norm, PipelineConfig())
    assert len(valid) == 1
    assert len(rejected) == 1
    assert rejected.loc[0, "reject_reason"] == "exact_duplicate_row"


def test_conflicting_duplicate_keeps_first():
    df = make_df(
        [
            ["R1", "2024-01-01 00:00:00", "Profile", "1.2", "Web", "RU", "new", "3", "4", "f", 0],
            ["R1", "2024-01-01 00:00:00", "Profile", "1.2", "Web", "RU", "new", "3", "5", "f", 1],
        ]
    )
    norm = normalize(df, PipelineConfig())
    valid, rejected = validate(norm, PipelineConfig())
    assert len(valid) == 1
    assert valid.loc[0, "score2_norm"] == 4
    assert rejected.loc[0, "reject_reason"] == "conflicting_duplicate_response_id"


def test_invalid_date_rejected():
    df = make_df(
        [["R1", "not_a_date", "Profile", "1.2", "Web", "RU", "new", "3", "4", "f", 0]]
    )
    norm = normalize(df, PipelineConfig())
    valid, rejected = validate(norm, PipelineConfig())
    assert len(valid) == 0
    assert rejected.loc[0, "reject_reason"] == "invalid_submitted_at"
