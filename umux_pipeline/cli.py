"""Точка входа для консольного запуска.

    python -m umux_pipeline.cli --input raw_responses.csv --outdir output
    python -m umux_pipeline.cli --input a.csv b.csv --outdir output --config my_config.json
"""
from __future__ import annotations

import argparse
import sys

from .config import PipelineConfig
from .pipeline import run_pipeline


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="umux_pipeline",
        description="Очистка, скоринг и агрегация выгрузок опросника UMUX-Lite.",
    )
    p.add_argument(
        "--input",
        "-i",
        nargs="+",
        required=True,
        help="Один или несколько входных CSV-файлов целевой схемы.",
    )
    p.add_argument(
        "--outdir",
        "-o",
        default="output",
        help="Папка для очищенных данных, лога отбраковки и отчёта (по умолчанию: output).",
    )
    p.add_argument(
        "--config",
        default=None,
        help="Опциональный JSON-файл с переопределением эталонных значений "
        "(известные продукты/платформы/сегменты).",
    )
    p.add_argument(
        "--no-report",
        action="store_true",
        help="Не формировать HTML-отчёт (CSV/JSON всё равно записываются).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = PipelineConfig.load(args.config)
    result = run_pipeline(
        inputs=args.input,
        outdir=args.outdir,
        config=config,
        write_report=not args.no_report,
    )
    print(f"Валидных строк: {result.overview['valid_rows']}")
    print(
        f"Отбраковано строк: {result.overview['rejected_rows']} "
        f"({result.overview['rejection_rate']*100:.1f}%)"
    )
    if result.report_path:
        print(f"Отчёт: {result.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
