from __future__ import annotations

import io
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np

ACCENT_BLUE = "#2563EB"
NEUTRAL_DARK = "#374151"
NEUTRAL_LIGHT = "#9CA3AF"
GRID_LIGHT = "#E5E7EB"
TEXT_SECONDARY = "#6B7280"


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

    x = np.arange(len(labels))
    width = 0.25

    colors = {
        "total": ACCENT_BLUE,
        "mandoli": NEUTRAL_DARK,
        "gandhinagar": NEUTRAL_LIGHT,
    }

    for i, key in enumerate(["total", "mandoli", "gandhinagar"]):
        ax.bar(x + (i - 1) * width, series[key], width, label=key.title(), color=colors[key])

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=0, fontsize=8, color=TEXT_SECONDARY)
    ax.tick_params(axis="y", labelsize=9, colors=TEXT_SECONDARY)
    ax.grid(axis="y", color=GRID_LIGHT, linewidth=1)
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_ylabel("Share %", color=TEXT_SECONDARY, fontsize=9)

    return fig_to_png_bytes(fig)


def bar_chart(labels: List[str], values: List[float], color: str = ACCENT_BLUE) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 2.4))
    ax.bar(labels, values, color=color)
    ax.grid(axis="y", color=GRID_LIGHT, linewidth=1)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=9, colors=TEXT_SECONDARY)
    ax.tick_params(axis="y", labelsize=9, colors=TEXT_SECONDARY)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return fig_to_png_bytes(fig)


def line_chart(labels: List[str], values: List[float]) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 2.4))
    ax.plot(labels, values, color=ACCENT_BLUE, linewidth=2)
    ax.grid(axis="y", color=GRID_LIGHT, linewidth=1)
    ax.tick_params(axis="x", labelsize=9, colors=TEXT_SECONDARY)
    ax.tick_params(axis="y", labelsize=9, colors=TEXT_SECONDARY)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return fig_to_png_bytes(fig)
