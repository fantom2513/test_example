from pathlib import Path

from umux_pipeline.pipeline import run_pipeline

SAMPLE = Path(__file__).parent.parent / "sample_data" / "raw_responses_sample.csv"


def test_pipeline_runs_on_sample(tmp_path):
    result = run_pipeline([str(SAMPLE)], outdir=tmp_path, write_report=True)
    assert result.overview["total_rows"] > 0
    assert result.overview["valid_rows"] > 0
    assert result.overview["rejected_rows"] > 0
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "clean_scored.csv").exists()
    assert (tmp_path / "rejected_rows.csv").exists()


def test_pipeline_idempotent(tmp_path):
    r1 = run_pipeline([str(SAMPLE)], outdir=tmp_path, write_report=False)
    r2 = run_pipeline([str(SAMPLE)], outdir=tmp_path, write_report=False)
    assert r1.overview == r2.overview
