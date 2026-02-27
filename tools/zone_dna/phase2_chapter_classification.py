#!/usr/bin/env python3
"""Phase 2: Chapter classification and aggregation."""

from __future__ import annotations

import argparse
import json
import os
import warnings
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yaml


def load_config(config_path: str) -> Dict:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_range_key(key: str) -> Optional[List[str]]:
    if "-" in key:
        start, end = key.split("-", 1)
        if not (start.isdigit() and end.isdigit()):
            return None
        start_i = int(start)
        end_i = int(end)
        return [f"{i:02d}" for i in range(start_i, end_i + 1)]
    if key.isdigit():
        return [f"{int(key):02d}"]
    return None


def classify_chapter(chapter2: str, mapping: Dict[str, str], default_label: str) -> str:
    if not isinstance(chapter2, str) or not chapter2.strip():
        return default_label
    ch = chapter2.zfill(2)
    for key, label in mapping.items():
        if key == "default":
            continue
        expanded = parse_range_key(key)
        if expanded and ch in expanded:
            return label
    return default_label


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0 or pd.isna(denominator):
        return np.nan
    return numerator / denominator


def _ensure_hsn_chapter(df: pd.DataFrame) -> pd.DataFrame:
    if "hsn4" in df.columns:
        df["hsn4"] = df["hsn4"].astype("string")
    if "chapter2" in df.columns:
        df["chapter2"] = df["chapter2"].astype("string")
    if "chapter2" not in df.columns or df["chapter2"].isna().any():
        if "hsn4" not in df.columns:
            raise ValueError("chapter2 missing and hsn4 unavailable to recompute.")
        df["chapter2"] = df["hsn4"].str.extract(r"(\d{2})")[0].astype("string")

    df["chapter2"] = df["chapter2"].str.strip().str.zfill(2)
    # If chapter2 is still "00", derive from last two digits of hsn4 (e.g., 0080 -> 80)
    if "hsn4" in df.columns:
        mask_zero = df["chapter2"] == "00"
        if mask_zero.any():
            df.loc[mask_zero, "chapter2"] = df.loc[mask_zero, "hsn4"].str[-2:].str.zfill(2)
    malformed = df["chapter2"].str.len().ne(2) | ~df["chapter2"].str.match(r"^\d{2}$")
    if malformed.any():
        warnings.warn(f"Found {malformed.sum()} malformed chapter2 values; recomputing from hsn4.")
        if "hsn4" not in df.columns:
            raise ValueError("Malformed chapter2 and hsn4 unavailable to recompute.")
        df.loc[malformed, "chapter2"] = df.loc[malformed, "hsn4"].str.extract(r"(\d{2})")[0]
        df["chapter2"] = df["chapter2"].astype("string").str.zfill(2)
    if df["chapter2"].isna().any():
        raise ValueError("chapter2 contains nulls after normalization.")
    return df


def phase2_chapter_classification(input_csv: str, output_dir: str, config_path: str, tag: Optional[str] = None) -> str:
    df = pd.read_csv(input_csv, dtype={"chapter2": "string", "hsn4": "string"})
    df = _ensure_hsn_chapter(df)

    if "chapter2" not in df.columns:
        raise ValueError("chapter2 column not found in input CSV")

    # Aggregate to chapter level
    agg = df.groupby("chapter2", dropna=True).agg(
        chapter_value_y3=("taxable_y3", "sum"),
        chapter_value_y2=("taxable_y2", "sum"),
        chapter_value_y1=("taxable_y1", "sum"),
        hsn_count=("hsn4", pd.Series.nunique),
    ).reset_index()

    total_y3 = agg["chapter_value_y3"].sum(skipna=True)
    if total_y3 == 0 or pd.isna(total_y3):
        warnings.warn("Total chapter_value_y3 is zero or NaN; chapter_share_y3 set to NaN.")
        agg["chapter_share_y3"] = np.nan
    else:
        agg["chapter_share_y3"] = agg["chapter_value_y3"] / total_y3

    # Chapter CAGR and CV (based on aggregated values)
    with np.errstate(divide="ignore", invalid="ignore"):
        agg["chapter_cagr_3yr"] = np.where(
            agg["chapter_value_y1"] > 0,
            (agg["chapter_value_y3"] / agg["chapter_value_y1"]) ** (1 / 2) - 1,
            np.nan,
        )

    agg["chapter_mean_3yr"] = agg[["chapter_value_y1", "chapter_value_y2", "chapter_value_y3"]].mean(axis=1, skipna=True)
    agg["chapter_sd_3yr"] = agg[["chapter_value_y1", "chapter_value_y2", "chapter_value_y3"]].std(axis=1, ddof=0, skipna=True)
    agg["chapter_cv_volatility"] = agg["chapter_sd_3yr"] / agg["chapter_mean_3yr"]

    # YOY change
    with np.errstate(divide="ignore", invalid="ignore"):
        agg["chapter_yoy_change"] = np.where(
            agg["chapter_value_y2"] > 0,
            (agg["chapter_value_y3"] - agg["chapter_value_y2"]) / agg["chapter_value_y2"],
            np.nan,
        )

    # Traceability fields
    hsn_sample = (
        df.groupby("chapter2")["hsn4"]
        .apply(lambda s: ",".join(sorted(s.dropna().unique())[:15]))
        .reset_index(name="hsn_list_sample")
    )
    agg = agg.merge(hsn_sample, on="chapter2", how="left")

    top_hsn = (
        df.groupby(["chapter2", "hsn4"])["taxable_y3"]
        .sum()
        .reset_index()
        .sort_values(["chapter2", "taxable_y3"], ascending=[True, False])
    )
    top_hsn_json = (
        top_hsn.groupby("chapter2")
        .apply(
            lambda g: json.dumps(
                {str(k): float(v) for k, v in g.head(5)[["hsn4", "taxable_y3"]].to_numpy()}
            )
        )
        .reset_index(name="top_hsn4_by_value_y3_json")
    )
    agg = agg.merge(top_hsn_json, on="chapter2", how="left")

    # Classification
    config = load_config(config_path)
    mapping = config.get("chapter_classification", {})
    default_label = mapping.get("default", "other")
    sector_types = config.get("sector_types", {})

    agg["chapter2"] = agg["chapter2"].astype("string").str.zfill(2)
    # After normalization, "00" should only appear if hsn4 is "0000"; keep as warning
    if (agg["chapter2"] == "00").any():
        warnings.warn("chapter_summary contains chapter2 '00' after normalization.")
    agg["sector_bucket"] = agg["chapter2"].apply(lambda x: classify_chapter(str(x).zfill(2), mapping, default_label))
    agg["type"] = agg["sector_bucket"].apply(lambda x: sector_types.get(x, "other"))

    output_base = output_dir
    if tag:
        output_base = os.path.join(output_dir, tag)
    os.makedirs(output_base, exist_ok=True)

    # Transformation Index (embedded)
    manuf_sum = agg.loc[agg["type"] == "manufacturing", "chapter_value_y3"].sum(skipna=True)
    primary_sum = agg.loc[agg["type"] == "primary", "chapter_value_y3"].sum(skipna=True)
    transformation_index = safe_divide(manuf_sum, primary_sum)
    agg["transformation_index_y3"] = transformation_index

    output_path = os.path.join(output_base, "chapter_summary.csv")

    agg[
        [
            "chapter2",
            "chapter_value_y3",
            "chapter_value_y2",
            "chapter_value_y1",
            "chapter_share_y3",
            "chapter_yoy_change",
            "chapter_cagr_3yr",
            "chapter_cv_volatility",
            "hsn_count",
            "hsn_list_sample",
            "top_hsn4_by_value_y3_json",
            "sector_bucket",
            "type",
            "transformation_index_y3",
        ]
    ].to_csv(output_path, index=False)

    print(f"Total chapters: {len(agg)}")
    print(f"Wrote: {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2: Chapter classification and aggregation.")
    parser.add_argument("--input", default=os.path.join(os.path.dirname(__file__), "output", "hsn_cleaned.csv"), help="Path to hsn_cleaned.csv")
    parser.add_argument("--output-dir", default=os.path.join(os.path.dirname(__file__), "output"), help="Output directory")
    parser.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "config.yaml"), help="Path to config.yaml")
    parser.add_argument("--tag", default=None, help="Optional tag to create a subfolder under output")
    args = parser.parse_args()

    phase2_chapter_classification(args.input, args.output_dir, args.config, tag=args.tag)


if __name__ == "__main__":
    main()
