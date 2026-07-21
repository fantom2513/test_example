"""UMUX-Lite scoring."""
from __future__ import annotations

import pandas as pd


def compute_umux(df: pd.DataFrame) -> pd.DataFrame:
    """Add a ``umux_score`` column: ((score1-1)+(score2-1)) / 8 * 100, range 0-100."""
    out = df.copy()
    out["umux_score"] = ((out["score1_norm"] - 1) + (out["score2_norm"] - 1)) / 8 * 100
    return out
