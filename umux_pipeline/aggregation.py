"""Aggregation of scored responses into product/version/time summaries."""
from __future__ import annotations

import pandas as pd


def add_month(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["month"] = out["submitted_at_dt"].dt.to_period("M").astype(str)
    return out


def by_product(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby("product_norm")["umux_score"]
        .agg(mean_umux="mean", median_umux="median", n="count")
        .reset_index()
        .rename(columns={"product_norm": "product"})
        .sort_values("mean_umux")
    )
    return g


def by_product_version(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby(["product_norm", "product_version"])["umux_score"]
        .agg(mean_umux="mean", median_umux="median", n="count")
        .reset_index()
        .rename(columns={"product_norm": "product"})
        .sort_values(["product", "product_version"])
    )
    return g


def by_month_product(df: pd.DataFrame) -> pd.DataFrame:
    dfm = add_month(df)
    g = (
        dfm.groupby(["month", "product_norm"])["umux_score"]
        .agg(mean_umux="mean", n="count")
        .reset_index()
        .rename(columns={"product_norm": "product"})
        .sort_values(["product", "month"])
    )
    return g


def by_segment(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby("segment_norm")["umux_score"]
        .agg(mean_umux="mean", n="count")
        .reset_index()
        .rename(columns={"segment_norm": "segment"})
        .sort_values("mean_umux")
    )
    return g


def rejection_summary(valid: pd.DataFrame, rejected: pd.DataFrame) -> pd.DataFrame:
    total = len(valid) + len(rejected)
    reason_counts = (
        rejected["reject_reason"].value_counts().rename_axis("reason").reset_index(name="count")
        if len(rejected)
        else pd.DataFrame(columns=["reason", "count"])
    )
    reason_counts["share_of_total"] = reason_counts["count"] / total if total else 0.0
    return reason_counts


def overview(valid: pd.DataFrame, rejected: pd.DataFrame) -> dict:
    total = len(valid) + len(rejected)
    return {
        "total_rows": total,
        "valid_rows": len(valid),
        "rejected_rows": len(rejected),
        "rejection_rate": (len(rejected) / total) if total else 0.0,
        "overall_mean_umux": float(valid["umux_score"].mean()) if len(valid) else None,
    }
