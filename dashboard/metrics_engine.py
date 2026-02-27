from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd


@dataclass(frozen=True)
class CutMetrics:
    cut: str
    total_value_y3: float
    top_3_chapters: List[Tuple[str, float]]
    top_3_share_sum: float
    concentration_level: str
    weighted_cagr: float
    weighted_cv: float
    structure_type: str
    transformation_index: float


def _concentration_level(top_3_share_sum: float) -> str:
    if top_3_share_sum > 50:
        return "High Concentration"
    if 35 <= top_3_share_sum <= 50:
        return "Moderate Concentration"
    return "Diversified"


def _structure_type(primary_share: float, manufacturing_share: float) -> str:
    if manufacturing_share > primary_share:
        return "Manufacturing-heavy"
    if primary_share > manufacturing_share:
        return "Primary-heavy"
    return "Balanced"


def compute_identity_metrics(df: pd.DataFrame) -> Dict[str, CutMetrics]:
    metrics: Dict[str, CutMetrics] = {}

    for cut, cdf in df.groupby("cut"):
        total_value_y3 = cdf["chapter_value_y3"].sum()
        top3 = (
            cdf.sort_values("chapter_share_y3", ascending=False)
            .head(3)[["chapter_name", "chapter_share_y3"]]
            .values.tolist()
        )
        top3_pairs = [(name, share * 100) for name, share in top3]
        top_3_share_sum = sum(share for _, share in top3_pairs)
        concentration = _concentration_level(top_3_share_sum)

        share_sum = cdf["chapter_share_y3"].sum()
        if share_sum == 0:
            weighted_cagr = 0.0
            weighted_cv = 0.0
        else:
            weighted_cagr = (cdf["chapter_cagr_3yr"] * cdf["chapter_share_y3"]).sum() / share_sum
            weighted_cv = (cdf["chapter_cv_volatility"] * cdf["chapter_share_y3"]).sum() / share_sum

        primary_share = cdf.loc[cdf["type"] == "primary", "chapter_share_y3"].sum()
        manufacturing_share = cdf.loc[cdf["type"] == "manufacturing", "chapter_share_y3"].sum()
        structure = _structure_type(primary_share, manufacturing_share)
        transformation_index = manufacturing_share / primary_share if primary_share > 0 else 0.0

        metrics[cut] = CutMetrics(
            cut=cut,
            total_value_y3=total_value_y3,
            top_3_chapters=top3_pairs,
            top_3_share_sum=top_3_share_sum,
            concentration_level=concentration,
            weighted_cagr=weighted_cagr,
            weighted_cv=weighted_cv,
            structure_type=structure,
            transformation_index=transformation_index,
        )

    return metrics


def top_chapters_by_cut(df: pd.DataFrame, top_n: int = 5) -> Dict[str, pd.DataFrame]:
    results = {}
    for cut, cdf in df.groupby("cut"):
        results[cut] = cdf.sort_values("chapter_share_y3", ascending=False).head(top_n).copy()
    return results


def top10_by_total_share(df: pd.DataFrame) -> pd.DataFrame:
    total_df = df[df["cut"] == "total"].copy()
    return total_df.sort_values("chapter_share_y3", ascending=False).head(10)


def compute_over_specialized(df: pd.DataFrame, top_n: int = 5) -> Dict[str, pd.DataFrame]:
    total = df[df["cut"] == "total"][
        ["chapter2", "chapter_share_y3"]
    ].rename(columns={"chapter_share_y3": "total_share"})

    results = {}
    for cut in ["mandoli", "gandhinagar"]:
        cdf = df[df["cut"] == cut].merge(total, on="chapter2", how="left")
        cdf["rs"] = cdf["chapter_share_y3"] / cdf["total_share"].replace(0, pd.NA)
        cdf = cdf.dropna(subset=["rs"]).sort_values("rs", ascending=False).head(top_n)
        results[cut] = cdf
    return results


def compute_structural_momentum_tables(df: pd.DataFrame, share_threshold: float = 0.005) -> Dict[str, pd.DataFrame]:
    total = df[df["cut"] == "total"].copy()
    filtered = total[total["chapter_share_y3"] >= share_threshold].copy()

    fastest = filtered.sort_values("chapter_cagr_3yr", ascending=False).head(5)
    declining = filtered.sort_values("chapter_cagr_3yr", ascending=True).head(5)
    volatile = filtered.sort_values("chapter_cv_volatility", ascending=False).head(5)

    return {
        "fastest": fastest,
        "declining": declining,
        "volatile": volatile,
    }
