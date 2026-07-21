"""Optional HTTP interface (bonus requirement).

Run with:
    uvicorn umux_pipeline.api:app --reload

POST /pipeline/run with one or more CSV files (multipart/form-data, field
name "files") runs the same pipeline as the CLI against a temporary
directory and returns the aggregation summary as JSON, plus the rendered
HTML report inline.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse

from .config import PipelineConfig
from .pipeline import run_pipeline

app = FastAPI(title="UMUX-Lite Pipeline", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/pipeline/run")
async def run(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(400, "No files uploaded")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_paths = []
        for f in files:
            if not f.filename.lower().endswith(".csv"):
                raise HTTPException(400, f"Only .csv files are accepted, got {f.filename}")
            dest = tmp_path / f.filename
            dest.write_bytes(await f.read())
            input_paths.append(str(dest))

        outdir = tmp_path / "output"
        result = run_pipeline(
            inputs=input_paths, outdir=outdir, config=PipelineConfig(), write_report=True
        )

        return {
            "overview": result.overview,
            "rejection_reasons": result.reasons.to_dict(orient="records"),
            "by_product": result.by_product.to_dict(orient="records"),
            "by_product_version": result.by_product_version.to_dict(orient="records"),
            "by_month_product": result.by_month_product.to_dict(orient="records"),
            "by_segment": result.by_segment.to_dict(orient="records"),
            "report_html": result.report_path.read_text(encoding="utf-8"),
        }


@app.post("/pipeline/run/report", response_class=HTMLResponse)
async def run_report(files: list[UploadFile] = File(...)):
    """Same as /pipeline/run but returns the HTML report directly for viewing in a browser."""
    if not files:
        raise HTTPException(400, "No files uploaded")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_paths = []
        for f in files:
            dest = tmp_path / f.filename
            dest.write_bytes(await f.read())
            input_paths.append(str(dest))

        outdir = tmp_path / "output"
        result = run_pipeline(
            inputs=input_paths, outdir=outdir, config=PipelineConfig(), write_report=True
        )
        return result.report_path.read_text(encoding="utf-8")
