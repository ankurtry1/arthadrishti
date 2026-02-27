from __future__ import annotations

import io
from datetime import date
from typing import Dict

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from metrics_engine import CutMetrics
from utils import grouped_bar_chart, horizontal_bar_chart

ACCENT_BLUE = "#2563EB"
TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#6B7280"
GRID_LIGHT = "#E5E7EB"


def _img_from_bytes(png_bytes: bytes):
    return plt.imread(io.BytesIO(png_bytes))


def _add_footer(fig, generated_date: str):
    fig.text(0.5, 0.02, f"Generated on {generated_date}", ha="center", fontsize=9, color=TEXT_SECONDARY)


def _table_text(rows, col_labels, x, y, row_height=0.03, col_widths=None, font_size=9):
    if col_widths is None:
        col_widths = [0.2] * len(col_labels)
    for i, label in enumerate(col_labels):
        plt.gcf().text(x + sum(col_widths[:i]), y, label, fontsize=font_size, color=TEXT_PRIMARY, weight="bold")
    y -= row_height
    for row in rows:
        for i, cell in enumerate(row):
            plt.gcf().text(x + sum(col_widths[:i]), y, str(cell), fontsize=font_size, color=TEXT_SECONDARY)
        y -= row_height


def generate_commissioner_report(
    df,
    metrics_by_cut: Dict[str, CutMetrics],
    summaries: Dict[str, str],
    divergence_labels,
    divergence_series,
    momentum_tables,
) -> bytes:
    generated_date = date.today().isoformat()
    buffer = io.BytesIO()

    with PdfPages(buffer) as pdf:
        # Title Page
        fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
        fig.text(0.1, 0.85, "Industrial Identity Intelligence", fontsize=24, color=TEXT_PRIMARY, weight="bold")
        fig.text(0.1, 0.80, "Commissioner Report", fontsize=14, color=TEXT_SECONDARY)
        _add_footer(fig, generated_date)
        pdf.savefig(fig)
        plt.close(fig)

        # Executive Summary
        fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
        fig.text(0.1, 0.92, "Executive Summary", fontsize=16, color=ACCENT_BLUE, weight="bold")
        y = 0.86
        for cut in ["total", "mandoli", "gandhinagar"]:
            summary = summaries.get(cut, "")
            fig.text(0.1, y, cut.title(), fontsize=12, color=TEXT_PRIMARY, weight="bold")
            fig.text(0.1, y - 0.03, summary, fontsize=10, color=TEXT_SECONDARY)
            y -= 0.12
        _add_footer(fig, generated_date)
        pdf.savefig(fig)
        plt.close(fig)

        # Identity Snapshot Tables + charts
        fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
        fig.text(0.1, 0.92, "Identity Snapshot", fontsize=16, color=ACCENT_BLUE, weight="bold")
        y = 0.84
        for cut in ["total", "mandoli", "gandhinagar"]:
            cdf = df[df["cut"] == cut].sort_values("chapter_share_y3", ascending=False).head(5)
            labels = cdf["chapter_name"].tolist()
            values = (cdf["chapter_share_y3"] * 100).tolist()
            chart = _img_from_bytes(horizontal_bar_chart(labels, values, highlight_index=0))
            ax = fig.add_axes([0.1, y - 0.08, 0.8, 0.12])
            ax.imshow(chart)
            ax.axis("off")
            fig.text(0.1, y + 0.05, cut.title(), fontsize=12, color=TEXT_PRIMARY, weight="bold")
            y -= 0.22
        _add_footer(fig, generated_date)
        pdf.savefig(fig)
        plt.close(fig)

        # Divergence Table
        fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
        fig.text(0.1, 0.92, "Divergence & Specialization", fontsize=16, color=ACCENT_BLUE, weight="bold")
        chart = _img_from_bytes(grouped_bar_chart(divergence_labels, divergence_series))
        ax = fig.add_axes([0.1, 0.55, 0.8, 0.25])
        ax.imshow(chart)
        ax.axis("off")
        _add_footer(fig, generated_date)
        pdf.savefig(fig)
        plt.close(fig)

        # Structural Momentum Summary
        fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
        fig.text(0.1, 0.92, "Structural Momentum", fontsize=16, color=ACCENT_BLUE, weight="bold")
        sections = [
            ("Fastest Growing", momentum_tables["fastest"]),
            ("Declining Anchors", momentum_tables["declining"]),
            ("High Volatility Large Chapters", momentum_tables["volatile"]),
        ]
        y = 0.84
        for title, table in sections:
            fig.text(0.1, y, title, fontsize=12, color=TEXT_PRIMARY, weight="bold")
            rows = []
            for _, row in table.iterrows():
                rows.append(
                    [
                        row["chapter_name"],
                        f"{row['chapter_share_y3']*100:.2f}%",
                        f"{row['chapter_cagr_3yr']*100:.2f}%",
                        f"{row['chapter_cv_volatility']:.2f}",
                    ]
                )
            _table_text(
                rows,
                ["Chapter", "Share", "CAGR", "CV"],
                x=0.1,
                y=y - 0.04,
                row_height=0.028,
                col_widths=[0.45, 0.15, 0.15, 0.1],
            )
            y -= 0.23
        _add_footer(fig, generated_date)
        pdf.savefig(fig)
        plt.close(fig)

        # Key Observations
        fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
        fig.text(0.1, 0.92, "Key Observations", fontsize=16, color=ACCENT_BLUE, weight="bold")
        y = 0.86
        for cut in ["total", "mandoli", "gandhinagar"]:
            metrics = metrics_by_cut[cut]
            obs = (
                f"{cut.title()}: {metrics.structure_type}, "
                f"Top-3 share {metrics.top_3_share_sum:.1f}%, "
                f"Weighted CAGR {metrics.weighted_cagr*100:.1f}%."
            )
            fig.text(0.1, y, obs, fontsize=11, color=TEXT_SECONDARY)
            y -= 0.06
        _add_footer(fig, generated_date)
        pdf.savefig(fig)
        plt.close(fig)

    buffer.seek(0)
    return buffer.read()
