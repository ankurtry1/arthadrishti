from __future__ import annotations

from typing import Dict

from metrics_engine import CutMetrics


def _volatility_descriptor(cv: float) -> str:
    if cv > 0.3:
        return "high"
    if 0.15 <= cv <= 0.3:
        return "moderate"
    return "low"


def generate_summary(metrics: CutMetrics) -> str:
    growth = metrics.weighted_cagr * 100
    volatility_descriptor = _volatility_descriptor(metrics.weighted_cv)

    line1 = (
        f"{metrics.cut.title()} is {metrics.structure_type} with "
        f"{metrics.concentration_level} (Top 3 = {metrics.top_3_share_sum:.1f}%)."
    )
    line2 = (
        f"Growth stands at {growth:.1f}% with {volatility_descriptor} structural volatility."
    )
    return f"{line1}\n{line2}"


def generate_all_summaries(metrics_by_cut: Dict[str, CutMetrics]) -> Dict[str, str]:
    return {cut: generate_summary(metrics) for cut, metrics in metrics_by_cut.items()}
