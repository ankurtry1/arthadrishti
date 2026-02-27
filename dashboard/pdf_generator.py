from __future__ import annotations

import io
from datetime import date
from typing import Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from metrics_engine import CutMetrics

ACCENT_BLUE = colors.HexColor("#2563EB")
TEXT_PRIMARY = colors.HexColor("#111827")
TEXT_SECONDARY = colors.HexColor("#6B7280")


def _section_title(text: str):
    return Paragraph(text, ParagraphStyle(name="section", fontSize=14, textColor=ACCENT_BLUE, spaceAfter=8))


def _small_title(text: str):
    return Paragraph(text, ParagraphStyle(name="small", fontSize=11, textColor=TEXT_PRIMARY, spaceAfter=4))


def _paragraph(text: str):
    return Paragraph(text, ParagraphStyle(name="body", fontSize=9, textColor=TEXT_SECONDARY, leading=12))


def _table(data, col_widths):
    table = Table(data, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_PRIMARY),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("TEXTCOLOR", (0, 1), (-1, -1), TEXT_SECONDARY),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.lightgrey),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.lightgrey),
                ("ALIGN", (1, 0), (-1, -1), "LEFT"),
            ]
        )
    )
    return table


def generate_commissioner_report(
    df,
    metrics_by_cut: Dict[str, CutMetrics],
    summaries: Dict[str, str],
    divergence_labels,
    divergence_series,
    momentum_tables,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm)
    styles = getSampleStyleSheet()

    story = []
    story.append(Paragraph("Industrial Identity Intelligence", styles["Title"]))
    story.append(Paragraph("Commissioner Report", styles["Heading2"]))
    story.append(Spacer(1, 12))

    story.append(_section_title("Executive Summary"))
    for cut in ["total", "mandoli", "gandhinagar"]:
        story.append(_small_title(cut.title()))
        story.append(_paragraph(summaries.get(cut, "")))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 12))
    story.append(_section_title("Identity Snapshot Tables"))
    for cut in ["total", "mandoli", "gandhinagar"]:
        cdf = df[df["cut"] == cut].sort_values("chapter_share_y3", ascending=False).head(5)
        data = [["Chapter", "Share %"]]
        for _, row in cdf.iterrows():
            data.append([row["chapter_name"], f"{row['chapter_share_y3']*100:.2f}%"])
        story.append(_small_title(cut.title()))
        story.append(_table(data, [9 * cm, 3 * cm]))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 12))
    story.append(_section_title("Structural Momentum Summary"))
    sections = [
        ("Fastest Growing", momentum_tables["fastest"]),
        ("Declining Anchors", momentum_tables["declining"]),
        ("High Volatility Large Chapters", momentum_tables["volatile"]),
    ]
    for title, table in sections:
        data = [["Chapter", "Share", "CAGR", "CV"]]
        for _, row in table.iterrows():
            data.append(
                [
                    row["chapter_name"],
                    f"{row['chapter_share_y3']*100:.2f}%",
                    f"{row['chapter_cagr_3yr']*100:.2f}%",
                    f"{row['chapter_cv_volatility']:.2f}",
                ]
            )
        story.append(_small_title(title))
        story.append(_table(data, [7 * cm, 2 * cm, 2 * cm, 2 * cm]))
        story.append(Spacer(1, 8))

    story.append(Spacer(1, 12))
    story.append(_section_title("Key Observations"))
    for cut in ["total", "mandoli", "gandhinagar"]:
        metrics = metrics_by_cut[cut]
        obs = (
            f"{cut.title()}: {metrics.structure_type}, "
            f"Top-3 share {metrics.top_3_share_sum:.1f}%, "
            f"Weighted CAGR {metrics.weighted_cagr*100:.1f}%."
        )
        story.append(_paragraph(obs))

    story.append(Spacer(1, 12))
    story.append(_paragraph(f"Generated on {date.today().isoformat()}"))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
