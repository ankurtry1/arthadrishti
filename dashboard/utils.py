from __future__ import annotations

from typing import Dict, List

import plotly.graph_objects as go

ACCENT_BLUE = "#2563EB"
NEUTRAL_DARK = "#374151"
NEUTRAL_LIGHT = "#9CA3AF"
GRID_LIGHT = "#E5E7EB"
TEXT_SECONDARY = "#6B7280"

EXPLAINERS = {
    "chart_share": {
        "title": "Top Chapters (Share)",
        "lines": [
            "What it shows: which HSN chapters contribute the most to outward supplies.",
            "How it's calculated: chapter value (latest year) ÷ total value (latest year) × 100.",
            "How to read: bigger bar = bigger contribution; top bars define industrial identity.",
        ],
    },
    "growth": {
        "title": "Growth",
        "lines": [
            "Meaning: the overall growth rate of the division across chapters.",
            "Calculation: weighted average of chapter CAGR using each chapter’s share.",
            "Interpretation: higher = faster expansion; negative = shrinking.",
        ],
    },
    "concentration": {
        "title": "Concentration (Top 3)",
        "lines": [
            "Meaning: how dependent the division is on a few industries.",
            "Calculation: adds the share % of the top 3 chapters (largest contributors).",
            "Interpretation: high = focused identity but higher risk; low = diversified.",
        ],
    },
    "volatility": {
        "title": "Volatility",
        "lines": [
            "Meaning: how stable or shaky the industrial pattern is across years.",
            "Calculation: weighted average of chapter volatility (CV), using chapter share as weights.",
            "Interpretation: low = stable base; high = large swings (seasonality/commodities/instability).",
        ],
    },
    "structure": {
        "title": "Structure",
        "lines": [
            "Meaning: whether the mix leans more manufacturing/value-added or primary/raw.",
            "Calculation: compares total share of manufacturing chapters vs primary chapters.",
            "Interpretation: manufacturing-heavy = more value addition; primary-heavy = more raw output.",
        ],
    },
    "compare_toggle": {
        "title": "Compare View",
        "lines": [
            "What it changes: switches the comparison between Share, Growth, and Volatility.",
            "How it's calculated: same chapters, different metric per selection.",
            "How to read: compare Total vs Mandoli vs Gandhinagar on the chosen metric.",
        ],
    },
}


def short_label(text: str, max_len: int = 42) -> str:
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def format_percent(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}%"


def safe_update_axes(fig: go.Figure, axis: str = "x", **kwargs):
    titlefont = kwargs.pop("titlefont", None)
    if titlefont:
        title = kwargs.get("title", {}) or {}
        if isinstance(title, str):
            title = {"text": title}
        title["font"] = titlefont
        kwargs["title"] = title
    if axis == "x":
        fig.update_xaxes(**kwargs)
    else:
        fig.update_yaxes(**kwargs)


def plotly_snapshot_chart(
    labels: List[str],
    values: List[float],
    theme: str = "light",
    hover_labels: List[str] | None = None,
    highlight_index: int = 0,
) -> go.Figure:
    theme = theme if theme in {"light", "dark"} else "light"
    text_primary = "#111827" if theme == "light" else "#F9FAFB"
    text_secondary = "#6B7280" if theme == "light" else "#9CA3AF"
    grid = "#E5E7EB" if theme == "light" else "#1F2937"
    accent = "#2563EB" if theme == "light" else "#60A5FA"
    neutral = "#9CA3AF" if theme == "light" else "#475569"
    tpl = "plotly_white" if theme == "light" else "plotly_dark"
    hover_labels = hover_labels or labels
    colors = [neutral for _ in values]
    if values and 0 <= highlight_index < len(values):
        colors[highlight_index] = accent

    fig = go.Figure(
        data=[
            go.Bar(
                x=values,
                y=labels,
                orientation="h",
                marker=dict(color=colors),
                customdata=hover_labels,
                hovertemplate="%{customdata}<br>Share: %{x:.2f}%<extra></extra>",
            )
        ]
    )

    try:
        fig.update_layout(
            template=tpl,
            height=260,
            margin=dict(l=160, r=16, t=8, b=24),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            font=dict(color=text_primary, size=12),
        )
    except Exception:
        fig.update_layout(template="plotly_white", height=260, margin=dict(l=160, r=16, t=8, b=24))

    fig.update_xaxes(
        title=dict(text="Share %", font=dict(color=text_secondary)),
        gridcolor=grid,
        zeroline=False,
        tickfont=dict(color=text_secondary),
    )
    fig.update_yaxes(
        tickfont=dict(color=text_primary),
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
            title=dict(text=xaxis_title, font=dict(color=theme["text_secondary"], size=11)),
            gridcolor=theme["grid"],
            tickfont=dict(color=theme["text_secondary"], size=11),
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
            title=dict(text="Share %", font=dict(color=theme["text_secondary"], size=11)),
            gridcolor=theme["grid"],
            tickfont=dict(color=theme["text_secondary"], size=11),
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
