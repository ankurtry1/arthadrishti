from __future__ import annotations

import io
from typing import Dict, List

import matplotlib.pyplot as plt
import plotly.graph_objects as go

ACCENT_BLUE = "#2563EB"
NEUTRAL_DARK = "#374151"
NEUTRAL_LIGHT = "#9CA3AF"
GRID_LIGHT = "#E5E7EB"
TEXT_SECONDARY = "#6B7280"


def short_label(text: str, max_len: int = 42) -> str:
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def format_percent(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def fig_to_png_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def horizontal_bar_chart(labels: List[str], values: List[float], highlight_index: int = 0) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 2.2))
    colors = [NEUTRAL_LIGHT for _ in values]
    if values:
        colors[highlight_index] = ACCENT_BLUE

    ax.barh(labels, values, color=colors)
    ax.invert_yaxis()
    ax.grid(axis="x", color=GRID_LIGHT, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=9, colors=TEXT_SECONDARY)
    ax.tick_params(axis="y", labelsize=9, colors=TEXT_SECONDARY)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlabel("Share %", color=TEXT_SECONDARY, fontsize=9)

    return fig_to_png_bytes(fig)


def grouped_bar_chart(labels: List[str], series: Dict[str, List[float]]) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 3.2))

    x = list(range(len(labels)))
    width = 0.25

    colors = {
        "total": ACCENT_BLUE,
        "mandoli": NEUTRAL_DARK,
        "gandhinagar": NEUTRAL_LIGHT,
    }

    for i, key in enumerate(["total", "mandoli", "gandhinagar"]):
        ax.bar([v + (i - 1) * width for v in x], series[key], width, label=key.title(), color=colors[key])

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=0, fontsize=8, color=TEXT_SECONDARY)
    ax.tick_params(axis="y", labelsize=9, colors=TEXT_SECONDARY)
    ax.grid(axis="y", color=GRID_LIGHT, linewidth=1)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_ylabel("Share %", color=TEXT_SECONDARY, fontsize=9)

    return fig_to_png_bytes(fig)


def plotly_snapshot_chart(labels: List[str], values: List[float], theme: Dict[str, str]) -> go.Figure:
    y_labels = [short_label(s) for s in labels]
    fig = go.Figure(
        data=[
            go.Bar(
                x=values,
                y=y_labels,
                orientation="h",
                marker_color=theme["accent"],
                hovertemplate="%{customdata}<br>Share: %{x:.2f}%<extra></extra>",
                customdata=labels,
            )
        ]
    )
    fig.update_layout(
        height=260,
        margin=dict(l=140, r=16, t=8, b=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Share %",
            gridcolor=theme["grid"],
            tickfont=dict(color=theme["text_secondary"], size=11),
            titlefont=dict(color=theme["text_secondary"], size=11),
        ),
        yaxis=dict(
            tickfont=dict(color=theme["text_primary"], size=11),
        ),
        showlegend=False,
    )
    return fig


def plotly_compare_chart(
    labels: List[str], series: Dict[str, List[float]], theme: Dict[str, str], xaxis_title: str
) -> go.Figure:
    y_labels = [short_label(s) for s in labels]
    fig = go.Figure()
    colors = {
        "total": theme["accent"],
        "mandoli": theme["text_primary"],
        "gandhinagar": theme["text_secondary"],
    }
    for key in ["total", "mandoli", "gandhinagar"]:
        fig.add_trace(
            go.Bar(
                x=series[key],
                y=y_labels,
                name=key.title(),
                orientation="h",
                marker_color=colors[key],
                hovertemplate="%{customdata}<br>%{x:.2f}<extra></extra>",
                customdata=labels,
            )
        )
    fig.update_layout(
        barmode="group",
        height=360,
        margin=dict(l=160, r=16, t=24, b=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title=xaxis_title,
            gridcolor=theme["grid"],
            tickfont=dict(color=theme["text_secondary"], size=11),
            titlefont=dict(color=theme["text_secondary"], size=11),
        ),
        yaxis=dict(
            tickfont=dict(color=theme["text_primary"], size=11),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    return fig


def plotly_share_chart(labels: List[str], values: List[float], theme: Dict[str, str]) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Bar(
                x=values,
                y=labels,
                orientation="h",
                marker_color=theme["accent"],
                hovertemplate="%{y}<br>%{x:.2f}%<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        height=260,
        margin=dict(l=80, r=16, t=8, b=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="Share %",
            gridcolor=theme["grid"],
            tickfont=dict(color=theme["text_secondary"], size=11),
            titlefont=dict(color=theme["text_secondary"], size=11),
        ),
        yaxis=dict(
            tickfont=dict(color=theme["text_primary"], size=11),
        ),
        showlegend=False,
    )
    return fig


def plotly_trend_chart(labels: List[str], values: List[float], theme: Dict[str, str]) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Scatter(
                x=labels,
                y=values,
                mode="lines+markers",
                line=dict(color=theme["accent"], width=2),
                marker=dict(size=6),
                hovertemplate="Value: %{y:.2f}<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        height=260,
        margin=dict(l=60, r=16, t=8, b=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            tickfont=dict(color=theme["text_secondary"], size=11),
        ),
        yaxis=dict(
            gridcolor=theme["grid"],
            tickfont=dict(color=theme["text_secondary"], size=11),
        ),
        showlegend=False,
    )
    return fig
