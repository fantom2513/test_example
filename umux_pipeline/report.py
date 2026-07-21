"""Самодостаточный HTML-отчёт: общая статистика, разбивка отбраковки и
графики UMUX по продукту/версии/времени — всё встроено (без внешних
ресурсов), чтобы один файл .html можно было сразу показать заказчику.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["figure.dpi"] = 110

REASON_LABELS_RU = {
    "missing_response_id": "нет response_id",
    "invalid_submitted_at": "нераспознанная дата",
    "submitted_at_out_of_range": "дата вне разумного диапазона",
    "unrecognized_product": "нераспознанный продукт",
    "missing_product_version": "нет версии продукта",
    "missing_or_invalid_score1": "score1 отсутствует/некорректен",
    "missing_or_invalid_score2": "score2 отсутствует/некорректен",
    "score1_out_of_range": "score1 вне диапазона 1-5",
    "score2_out_of_range": "score2 вне диапазона 1-5",
    "exact_duplicate_row": "точный дубликат строки",
    "conflicting_duplicate_response_id": "конфликтующий дубликат response_id",
}

COLUMN_LABELS_RU = {
    "reason": "причина",
    "count": "кол-во",
    "share_of_total": "доля от всех строк",
    "product": "продукт",
    "product_version": "версия",
    "mean_umux": "средний UMUX",
    "median_umux": "медиана UMUX",
    "n": "n",
    "month": "месяц",
    "segment": "сегмент",
}


def _fig_to_base64() -> str:
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _chart_by_product(prod_df: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(7, max(2, 0.5 * len(prod_df))))
    ax.barh(prod_df["product"], prod_df["mean_umux"], color="#4C78A8")
    ax.set_xlabel("Средний UMUX-скор")
    ax.set_xlim(0, 100)
    ax.set_title("Средний UMUX по продуктам")
    for y, (v, n) in enumerate(zip(prod_df["mean_umux"], prod_df["n"])):
        ax.text(v + 1, y, f"{v:.1f} (n={n})", va="center", fontsize=8)
    return _fig_to_base64()


def _chart_trend(month_prod_df: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for product, sub in month_prod_df.groupby("product"):
        sub = sub.sort_values("month")
        ax.plot(sub["month"], sub["mean_umux"], marker="o", label=product)
    ax.set_ylabel("Средний UMUX-скор")
    ax.set_ylim(0, 100)
    ax.set_title("Динамика UMUX по месяцам и продуктам")
    ax.legend(fontsize=8)
    ax.tick_params(axis="x", rotation=45)
    return _fig_to_base64()


def _chart_rejections(reasons_df: pd.DataFrame) -> str:
    if reasons_df.empty:
        fig, ax = plt.subplots(figsize=(6, 1.5))
        ax.text(0.5, 0.5, "Отбракованных строк нет", ha="center", va="center")
        ax.axis("off")
        return _fig_to_base64()
    labels = reasons_df["reason"].map(lambda r: REASON_LABELS_RU.get(r, r))
    fig, ax = plt.subplots(figsize=(7, max(2, 0.4 * len(reasons_df))))
    ax.barh(labels, reasons_df["count"], color="#E45756")
    ax.set_xlabel("Отбракованных строк")
    ax.set_title("Причины отбраковки")
    return _fig_to_base64()


def _localize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "reason" in out.columns:
        out["reason"] = out["reason"].map(lambda r: REASON_LABELS_RU.get(r, r))
    out = out.rename(columns=COLUMN_LABELS_RU)
    return out


def _df_to_html(df: pd.DataFrame, float_cols: list[str] | None = None) -> str:
    localized = _localize(df)
    ru_float_cols = [COLUMN_LABELS_RU.get(c, c) for c in (float_cols or [])]
    fmt = {c: "{:.1f}".format for c in ru_float_cols}
    return localized.to_html(index=False, classes="tbl", border=0, formatters=fmt)


def build_report(
    outdir: Path,
    overview_stats: dict,
    reasons_df: pd.DataFrame,
    prod_df: pd.DataFrame,
    prod_version_df: pd.DataFrame,
    month_prod_df: pd.DataFrame,
    segment_df: pd.DataFrame,
) -> Path:
    chart_product = _chart_by_product(prod_df) if len(prod_df) else None
    chart_trend = _chart_trend(month_prod_df) if len(month_prod_df) else None
    chart_rejections = _chart_rejections(reasons_df)
    overall_mean_str = (
        f"{overview_stats['overall_mean_umux']:.1f}"
        if overview_stats["overall_mean_umux"] is not None
        else "н/д"
    )

    html = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Отчёт пайплайна UMUX-Lite</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 2rem auto; max-width: 960px; color: #1a1a1a; }}
  h1 {{ margin-bottom: 0.2rem; }}
  h2 {{ margin-top: 2.5rem; border-bottom: 1px solid #ddd; padding-bottom: 0.3rem; }}
  .stats {{ display: flex; gap: 1.5rem; flex-wrap: wrap; margin: 1rem 0 2rem; }}
  .stat {{ background: #f5f6f8; border-radius: 8px; padding: 0.8rem 1.2rem; min-width: 140px; }}
  .stat .n {{ font-size: 1.6rem; font-weight: 700; }}
  .stat .l {{ font-size: 0.8rem; color: #666; }}
  table.tbl {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0 1.5rem; font-size: 0.9rem; }}
  table.tbl th, table.tbl td {{ border-bottom: 1px solid #eee; padding: 0.4rem 0.6rem; text-align: left; }}
  table.tbl th {{ background: #fafafa; }}
  img {{ max-width: 100%; }}
</style>
</head>
<body>
<h1>Отчёт пайплайна UMUX-Lite</h1>
<p style="color:#666">Сформировано umux_pipeline. UMUX = ((score1-1)+(score2-1))/8*100.</p>

<div class="stats">
  <div class="stat"><div class="n">{overview_stats['total_rows']}</div><div class="l">всего строк</div></div>
  <div class="stat"><div class="n">{overview_stats['valid_rows']}</div><div class="l">валидных строк</div></div>
  <div class="stat"><div class="n">{overview_stats['rejected_rows']}</div><div class="l">отбраковано строк</div></div>
  <div class="stat"><div class="n">{overview_stats['rejection_rate']*100:.1f}%</div><div class="l">доля отбраковки</div></div>
  <div class="stat"><div class="n">{overall_mean_str}</div><div class="l">средний UMUX (общий)</div></div>
</div>

<h2>Качество данных: отбракованные строки</h2>
<img src="data:image/png;base64,{chart_rejections}">
{_df_to_html(reasons_df, ['share_of_total']) if len(reasons_df) else '<p>Отбракованных строк нет.</p>'}

<h2>UMUX по продуктам</h2>
{f'<img src="data:image/png;base64,{chart_product}">' if chart_product else '<p>Нет валидных данных.</p>'}
{_df_to_html(prod_df, ['mean_umux', 'median_umux'])}

<h2>UMUX по продукту и версии</h2>
{_df_to_html(prod_version_df, ['mean_umux', 'median_umux'])}

<h2>Динамика по месяцам и продуктам</h2>
{f'<img src="data:image/png;base64,{chart_trend}">' if chart_trend else '<p>Нет валидных данных.</p>'}

<h2>UMUX по сегменту пользователей</h2>
{_df_to_html(segment_df, ['mean_umux'])}

</body>
</html>
"""
    out_path = outdir / "report.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
