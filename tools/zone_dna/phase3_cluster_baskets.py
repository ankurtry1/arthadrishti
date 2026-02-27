#!/usr/bin/env python3
"""Phase 3: Cluster basket aggregation."""

from __future__ import annotations

import argparse
import os
import json
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



def phase3_cluster_baskets(input_csv: str, output_dir: str, config_path: str, tag: Optional[str] = None) -> str:
    df = pd.read_csv(input_csv, dtype={"chapter2": "string"})
    if "chapter2" not in df.columns:
        raise ValueError("chapter2 column not found in chapter_summary.csv")
    df["chapter2"] = df["chapter2"].astype("string").str.strip().str.zfill(2)

    config = load_config(config_path)
    clusters = config.get("clusters", {})
    if not clusters:
        raise ValueError("No clusters found in config.yaml")

    total_y3 = df["chapter_value_y3"].sum(skipna=True)
    if total_y3 == 0 or pd.isna(total_y3):
        warnings.warn("Total chapter_value_y3 is zero or NaN; cluster_share_y3 set to NaN.")

    rows = []
    for cluster_name, cluster_def in clusters.items():
        chapters = [str(c).zfill(2) for c in cluster_def.get("chapters", [])]
        subset = df[df["chapter2"].isin(chapters)].copy()

        # Ensure all configured chapters are represented (even if missing)
        missing_chapters = [c for c in chapters if c not in set(subset["chapter2"])]
        if missing_chapters:
            warnings.warn(f"Cluster '{cluster_name}' missing chapters in data: {missing_chapters}")
            for ch in missing_chapters:
                subset = pd.concat(
                    [
                        subset,
                        pd.DataFrame(
                            [
                                {
                                    "chapter2": ch,
                                    "chapter_value_y1": 0.0,
                                    "chapter_value_y2": 0.0,
                                    "chapter_value_y3": 0.0,
                                    "chapter_share_y3": 0.0,
                                    "chapter_cagr_3yr": np.nan,
                                    "chapter_cv_volatility": np.nan,
                                    "hsn_count": 0,
                                }
                            ]
                        ),
                    ],
                    ignore_index=True,
                )

        cluster_value_y3 = subset["chapter_value_y3"].sum(skipna=True)
        cluster_value_y2 = subset["chapter_value_y2"].sum(skipna=True)
        cluster_value_y1 = subset["chapter_value_y1"].sum(skipna=True)

        if total_y3 == 0 or pd.isna(total_y3):
            cluster_share_y3 = np.nan
        else:
            cluster_share_y3 = cluster_value_y3 / total_y3

        with np.errstate(divide="ignore", invalid="ignore"):
            cluster_cagr_3yr = (cluster_value_y3 / cluster_value_y1) ** (1 / 2) - 1 if cluster_value_y1 and cluster_value_y1 > 0 else np.nan
        with np.errstate(divide="ignore", invalid="ignore"):
            cluster_yoy_change = (cluster_value_y3 - cluster_value_y2) / cluster_value_y2 if cluster_value_y2 and cluster_value_y2 > 0 else np.nan

        # Cluster CV volatility based on aggregated y1,y2,y3
        mean_3yr = np.mean([cluster_value_y1, cluster_value_y2, cluster_value_y3])
        sd_3yr = np.std([cluster_value_y1, cluster_value_y2, cluster_value_y3], ddof=0)
        if mean_3yr == 0 or pd.isna(mean_3yr):
            cluster_cv_volatility = np.nan
        else:
            cluster_cv_volatility = sd_3yr / mean_3yr

        # Balance score
        if len(subset) <= 1:
            balance_score = 1.0 if len(subset) == 1 else np.nan
        else:
            min_val = subset["chapter_value_y3"].min(skipna=True)
            max_val = subset["chapter_value_y3"].max(skipna=True)
            balance_score = min_val / max_val if max_val and not pd.isna(max_val) else np.nan

        component_y3 = {row["chapter2"]: float(row["chapter_value_y3"]) for _, row in subset.iterrows()}
        component_y2 = {row["chapter2"]: float(row["chapter_value_y2"]) for _, row in subset.iterrows()}
        component_y1 = {row["chapter2"]: float(row["chapter_value_y1"]) for _, row in subset.iterrows()}
        component_hsn = {row["chapter2"]: int(row.get("hsn_count", 0)) for _, row in subset.iterrows()}
        component_share = {row["chapter2"]: float(row["chapter_share_y3"]) for _, row in subset.iterrows()}

        rows.append(
            {
                "cluster_name": cluster_name,
                "included_chapters": ",".join(chapters),
                "rule_source": "config.yaml",
                "cluster_value_y3": cluster_value_y3,
                "cluster_value_y2": cluster_value_y2,
                "cluster_value_y1": cluster_value_y1,
                "cluster_share_y3": cluster_share_y3,
                "cluster_yoy_change": cluster_yoy_change,
                "cluster_cagr_3yr": cluster_cagr_3yr,
                "cluster_cv_volatility": cluster_cv_volatility,
                "cluster_balance_score_y3": balance_score,
                "component_values_y3_json": json.dumps(component_y3),
                "component_values_y2_json": json.dumps(component_y2),
                "component_values_y1_json": json.dumps(component_y1),
                "component_hsn_counts_json": json.dumps(component_hsn),
                "component_shares_y3_json": json.dumps(component_share),
            }
        )

    output_base = output_dir
    if tag:
        output_base = os.path.join(output_dir, tag)
    os.makedirs(output_base, exist_ok=True)

    output_path = os.path.join(output_base, "cluster_summary.csv")
    out_df = pd.DataFrame(rows)
    out_df.to_csv(output_path, index=False)

    print(f"Total clusters: {len(out_df)}")
    print(f"Wrote: {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3: Cluster basket aggregation.")
    parser.add_argument("--input", default=os.path.join(os.path.dirname(__file__), "output", "chapter_summary.csv"), help="Path to chapter_summary.csv")
    parser.add_argument("--output-dir", default=os.path.join(os.path.dirname(__file__), "output"), help="Output directory")
    parser.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "config.yaml"), help="Path to config.yaml")
    parser.add_argument("--tag", default=None, help="Optional tag to create a subfolder under output")
    args = parser.parse_args()

    phase3_cluster_baskets(args.input, args.output_dir, args.config, tag=args.tag)


if __name__ == "__main__":
    main()
