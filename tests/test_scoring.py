import pandas as pd

from umux_pipeline.scoring import compute_umux


def test_umux_formula():
    df = pd.DataFrame({"score1_norm": [1, 5, 3], "score2_norm": [1, 5, 4]})
    out = compute_umux(df)
    assert out["umux_score"].tolist() == [0.0, 100.0, 62.5]
