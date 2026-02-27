from __future__ import annotations

import base64
import sys
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Industrial Identity Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from data_loader import load_chapter_data
from interpretation_engine import generate_all_summaries
from metrics_engine import (
    compute_identity_metrics,
    compute_over_specialized,
    compute_structural_momentum_tables,
    top10_by_total_share,
    top_chapters_by_cut,
)
from pdf_generator import generate_commissioner_report
from utils import (
    bar_chart,
    grouped_bar_chart,
    horizontal_bar_chart,
    line_chart,
)

with open(BASE_DIR / "style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown("<h1>Industrial Identity Intelligence Dashboard</h1>", unsafe_allow_html=True)

# Health check for data files
required_files = [
    BASE_DIR.parent / "tools" / "zone_dna" / "output" / "mandoli" / "chapter_summary.csv",
    BASE_DIR.parent / "tools" / "zone_dna" / "output" / "gandhinagar" / "chapter_summary.csv",
    BASE_DIR.parent / "tools" / "zone_dna" / "output" / "delhi_east" / "chapter_summary.csv",
]
if not all(p.exists() for p in required_files):
    st.error("Data files not found. Check deployment configuration.")
    st.stop()

# Data + precompute
unified_df = load_chapter_data(BASE_DIR.parent / "tools" / "zone_dna" / "output")
metrics_by_cut = compute_identity_metrics(unified_df)
summaries = generate_all_summaries(metrics_by_cut)
top5_by_cut = top_chapters_by_cut(unified_df, top_n=5)
top10_total = top10_by_total_share(unified_df)
over_specialized = compute_over_specialized(unified_df, top_n=5)
structural_tables = compute_structural_momentum_tables(unified_df, share_threshold=0.005)


def _img_html(png_bytes: bytes, width: str = "100%") -> str:
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    return f"<img src='data:image/png;base64,{b64}' style='width:{width};' />"


def render_snapshot_card(cut: str):
    cdf = top5_by_cut[cut]
    labels = cdf["chapter_name"].tolist()
    values = (cdf["chapter_share_y3"] * 100).tolist()
    chart_bytes = horizontal_bar_chart(labels, values, highlight_index=0)
    top_chapter = cdf.iloc[0]["chapter_name"]

    metrics = metrics_by_cut[cut]

    growth = metrics.weighted_cagr * 100
    concentration = metrics.top_3_share_sum
    volatility = metrics.weighted_cv * 100

    summary = summaries[cut]

    card_html = f"""
    <div class='card'>
      <h2>{cut.title()}</h2>
      {_img_html(chart_bytes)}
      <div class='metric-row'>
        <div class='metric'><strong>{growth:.1f}%</strong>Growth</div>
        <div class='metric'><strong>{concentration:.1f}%</strong>Concentration</div>
        <div class='metric'><strong>{volatility:.1f}%</strong>Volatility</div>
        <div class='metric'><strong>{metrics.structure_type}</strong>Structure</div>
      </div>
      <div class='body-secondary' style='margin-bottom:8px;'>Top chapter <span class='chip'>#1</span> {top_chapter}</div>
      <div class='body-secondary' style='white-space:pre-line;'>{summary}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


st.markdown("<div class='section-title'>Industrial Identity Snapshot</div>", unsafe_allow_html=True)
render_snapshot_card("total")
render_snapshot_card("mandoli")
render_snapshot_card("gandhinagar")

# Section 2
st.markdown("<div class='section-title'>Divergence & Specialization</div>", unsafe_allow_html=True)
metric_choice = st.radio("", ["Share", "Growth", "Volatility"], horizontal=True, index=0)

metric_col = {
    "Share": "chapter_share_y3",
    "Growth": "chapter_cagr_3yr",
    "Volatility": "chapter_cv_volatility",
}[metric_choice]

labels = top10_total["chapter_name"].tolist()
series = {"total": [], "mandoli": [], "gandhinagar": []}
for _, row in top10_total.iterrows():
    chapter2 = row["chapter2"]
    for cut in series:
        cdf = unified_df[(unified_df["cut"] == cut) & (unified_df["chapter2"] == chapter2)]
        if cdf.empty:
            value = 0.0
        else:
            value = float(cdf.iloc[0][metric_col])
        series[cut].append(value * 100)

grouped_chart = grouped_bar_chart(labels, series)
st.markdown(_img_html(grouped_chart), unsafe_allow_html=True)

st.markdown("<h3>Over-specialized Chapters</h3>", unsafe_allow_html=True)
cols = st.columns(2)
for i, cut in enumerate(["mandoli", "gandhinagar"]):
    table = over_specialized[cut]
    rows = "".join(
        [
            f"<tr><td>{r['chapter_name']}</td><td class='subtle-highlight'>{r['rs']:.2f}</td></tr>"
            for _, r in table.iterrows()
        ]
    )
    html = (
        f"<div class='card' style='margin-bottom:16px;'>"
        f"<h3>{cut.title()}</h3>"
        f"<table class='table'><thead><tr><th>Chapter</th><th>RS</th></tr></thead><tbody>{rows}</tbody></table>"
        f"</div>"
    )
    cols[i].markdown(html, unsafe_allow_html=True)

# Section 3
st.markdown("<div class='section-title'>Structural Momentum</div>", unsafe_allow_html=True)
cols = st.columns(3)
section_titles = [
    ("Fastest Growing", "fastest"),
    ("Declining Anchors", "declining"),
    ("High Volatility Large Chapters", "volatile"),
]
for col, (title, key) in zip(cols, section_titles):
    table = structural_tables[key]
    rows = "".join(
        [
            "<tr>"
            f"<td>{r['chapter_name']}</td>"
            f"<td>{r['chapter_share_y3']*100:.2f}%</td>"
            f"<td>{r['chapter_cagr_3yr']*100:.2f}%</td>"
            f"<td>{r['chapter_cv_volatility']:.2f}</td>"
            "</tr>"
            for _, r in table.iterrows()
        ]
    )
    html = (
        f"<div class='card' style='margin-bottom:16px;'>"
        f"<h3>{title}</h3>"
        f"<table class='table'><thead><tr><th>Chapter</th><th>Share</th><th>CAGR</th><th>CV</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
    )
    col.markdown(html, unsafe_allow_html=True)

# Section 4
st.markdown("<div class='section-title'>Drilldown</div>", unsafe_allow_html=True)

total_df = unified_df[unified_df["cut"] == "total"].copy()
options = [f"{r['chapter2']} — {r['chapter_name']}" for _, r in total_df.iterrows()]
selection = st.selectbox("Select chapter", options)
selected_code = selection.split(" — ")[0]

chapter_rows = unified_df[unified_df["chapter2"] == selected_code]

share_values = []
share_labels = []
for cut in ["total", "mandoli", "gandhinagar"]:
    row = chapter_rows[chapter_rows["cut"] == cut]
    share_labels.append(cut.title())
    share_values.append(float(row.iloc[0]["chapter_share_y3"]) * 100 if not row.empty else 0.0)

share_chart = bar_chart(share_labels, share_values)

trend_row = chapter_rows[chapter_rows["cut"] == "total"]
if trend_row.empty:
    trend_values = [0.0, 0.0, 0.0]
else:
    trend_values = [
        float(trend_row.iloc[0]["chapter_value_y1"]),
        float(trend_row.iloc[0]["chapter_value_y2"]),
        float(trend_row.iloc[0]["chapter_value_y3"]),
    ]

trend_chart = line_chart(["Y1", "Y2", "Y3"], trend_values)

contrib_rows = chapter_rows[chapter_rows["cut"].isin(["mandoli", "gandhinagar"])].copy()
contrib_total = contrib_rows["chapter_value_y3"].sum()
contrib_rows["contribution"] = (
    contrib_rows["chapter_value_y3"] / contrib_total * 100 if contrib_total > 0 else 0
)

contrib_html_rows = "".join(
    [
        f"<tr><td>{r['cut'].title()}</td><td>{r['contribution']:.1f}%</td></tr>"
        for _, r in contrib_rows.iterrows()
    ]
)

chapter_type = trend_row.iloc[0]["type"] if not trend_row.empty else "-"

col1, col2 = st.columns(2)
col1.markdown(_img_html(share_chart), unsafe_allow_html=True)
col2.markdown(_img_html(trend_chart), unsafe_allow_html=True)

st.markdown(
    f"""
    <div class='card'>
      <h3>Contribution by Division %</h3>
      <table class='table'>
        <thead><tr><th>Division</th><th>Contribution</th></tr></thead>
        <tbody>{contrib_html_rows}</tbody>
      </table>
      <div class='body-secondary' style='margin-top:12px;'>Type classification: <strong>{chapter_type}</strong></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# PDF Export
st.markdown("<div class='section-title'>Commissioner Report</div>", unsafe_allow_html=True)
if st.button("Download Commissioner Report"):
    labels = top10_total["chapter_name"].tolist()
    series_pdf = {"total": [], "mandoli": [], "gandhinagar": []}
    for _, row in top10_total.iterrows():
        chapter2 = row["chapter2"]
        for cut in series_pdf:
            cdf = unified_df[(unified_df["cut"] == cut) & (unified_df["chapter2"] == chapter2)]
            value = float(cdf.iloc[0]["chapter_share_y3"]) * 100 if not cdf.empty else 0.0
            series_pdf[cut].append(value)

    pdf_bytes = generate_commissioner_report(
        unified_df,
        metrics_by_cut,
        summaries,
        labels,
        series_pdf,
        structural_tables,
    )
    st.download_button(
        label="Download Commissioner Report",
        data=pdf_bytes,
        file_name="industrial_identity_report.pdf",
        mime="application/pdf",
    )
