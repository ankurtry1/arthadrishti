#!/usr/bin/env python3
"""Build chapter-level aggregated CSVs from cleaned division CSVs."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

INPUTS = {
    "mandoli": Path("Data/Cleaned data/Mandoli.csv"),
    "gandhinagar": Path("Data/Cleaned data/Gandhinagar.csv"),
    "delhieast": Path("Data/Cleaned data/Delhi East.csv"),
}

OUTPUT_NAMES = {
    "mandoli": "chapter_mandoli.csv",
    "gandhinagar": "chapter_gandhinagar.csv",
    "delhieast": "chapter_delhieast.csv",
}

OUT_DIR = Path("Data/Cleaned data/Chapter data")

OUT_COLS = [
    "S.No.",
    "Chapter",
    "HSN Chapter",
    "No. of GSTNs_z1",
    "Taxable value 24_25_z2",
    "YoY growth_z3",
]


def norm_header(name: str) -> str:
    return str(name or "").replace("\ufeff", "").strip().lower()


def find_column(columns, exact_name: str) -> str:
    lookup = {norm_header(c): c for c in columns}
    key = norm_header(exact_name)
    if key not in lookup:
        raise ValueError(f"Missing required column '{exact_name}'")
    return lookup[key]


def parse_number_series(s: pd.Series) -> pd.Series:
    cleaned = s.astype(str).str.strip().replace({"": pd.NA, "-": pd.NA, "nan": pd.NA, "None": pd.NA})
    cleaned = cleaned.str.replace(",", "", regex=False)
    return pd.to_numeric(cleaned, errors="coerce")


def normalize_hsn_to_chapter(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""

    if pd.Series([s]).str.match(r"^\d+\.0+$").iloc[0]:
        s = s.split(".", 1)[0]

    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        return ""

    try:
        no_leading = str(int(digits, 10))
    except ValueError:
        return ""

    if len(no_leading) >= 2:
        return no_leading[:2]
    return no_leading


def ensure_chapter(df: pd.DataFrame, hsn_col: str) -> pd.Series:
    chapter_col = next((c for c in df.columns if norm_header(c) == "chapter"), None)
    if chapter_col:
        chap = df[chapter_col].astype(str).str.strip().replace({"nan": "", "None": ""})
        missing = chap.eq("")
        if missing.any():
            chap.loc[missing] = df.loc[missing, hsn_col].apply(normalize_hsn_to_chapter)
        return chap
    return df[hsn_col].apply(normalize_hsn_to_chapter)


def aggregate_file(in_path: Path, out_path: Path) -> Tuple[pd.DataFrame, Dict[str, str]]:
    df = pd.read_csv(in_path, dtype=str, encoding="utf-8")

    hsn_col = find_column(df.columns, "HSN Code")
    z1_col = find_column(df.columns, "No. of GSTNs_z1")
    z2_col = find_column(df.columns, "Taxable value 24_25_z2")
    z3_col = find_column(df.columns, "YoY growth_z3")
    hsn_ch_col = next((c for c in df.columns if norm_header(c) == "hsn chapter"), None)

    df = df.copy()
    df["Chapter"] = ensure_chapter(df, hsn_col)
    df["Chapter"] = df["Chapter"].astype(str).str.strip()
    df = df[df["Chapter"] != ""].copy()

    df["z1_num"] = parse_number_series(df[z1_col]).fillna(0)
    df["z2_num"] = parse_number_series(df[z2_col]).fillna(0)
    df["z3_num"] = parse_number_series(df[z3_col])
    if hsn_ch_col:
        df["hsn_chapter_txt"] = df[hsn_ch_col].astype(str).str.strip().replace({"nan": "", "None": ""})
    else:
        df["hsn_chapter_txt"] = ""

    grouped = df.groupby("Chapter", dropna=False)

    out = grouped.agg(
        **{
            "No. of GSTNs_z1": ("z1_num", "sum"),
            "Taxable value 24_25_z2": ("z2_num", "sum"),
        }
    ).reset_index()

    # Representative HSN Chapter label per chapter:
    # use most frequent valid non-empty label, else fallback to \"Chapter {code}\".
    def sanitize_hsn_chapter_label(text: str) -> str:
        s = str(text or "").strip()
        if not s:
            return ""
        # Ignore placeholder-like numeric strings such as 0 or 0.0.
        if s.replace(".", "", 1).isdigit():
            return ""
        return s

    label_rows = []
    for chapter_code, g in df.groupby("Chapter", dropna=False):
        vals = g["hsn_chapter_txt"].astype(str).str.strip().replace({"nan": "", "None": ""})
        vals = vals.map(sanitize_hsn_chapter_label)
        vals = vals[vals != ""]
        if len(vals):
            label = vals.value_counts().index[0]
        else:
            label = f"Chapter {chapter_code}"
        label_rows.append({"Chapter": chapter_code, "HSN Chapter": label})

    hsn_ch = pd.DataFrame(label_rows)
    out = out.merge(hsn_ch, on="Chapter", how="left")

    # Weighted YoY: sum(z3*z2)/sum(z2), only where z3 is present.
    yoy_num = grouped.apply(lambda g: (g.loc[g["z3_num"].notna(), "z3_num"] * g.loc[g["z3_num"].notna(), "z2_num"]).sum())
    yoy_den = grouped.apply(lambda g: g.loc[g["z3_num"].notna(), "z2_num"].sum())
    yoy = (yoy_num / yoy_den).replace([pd.NA, pd.NaT], pd.NA)
    yoy = yoy.where(yoy_den != 0, pd.NA)

    out = out.merge(yoy.rename("YoY growth_z3").reset_index(), on="Chapter", how="left")

    out["chapter_num"] = pd.to_numeric(out["Chapter"], errors="coerce")
    out = out.sort_values(["chapter_num", "Chapter"], kind="stable").drop(columns=["chapter_num"])

    out.insert(0, "S.No.", range(1, len(out) + 1))

    out = out[OUT_COLS]

    # Keep blank when YoY is unavailable
    out["YoY growth_z3"] = out["YoY growth_z3"].apply(lambda x: "" if pd.isna(x) else x)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False, encoding="utf-8")

    info = {
        "chapters": str(len(out)),
        "min_chapter": str(out["Chapter"].iloc[0]) if len(out) else "",
        "max_chapter": str(out["Chapter"].iloc[-1]) if len(out) else "",
    }
    return out, info


def main() -> None:
    parser = argparse.ArgumentParser(description="Build chapter-level CSVs from cleaned division CSVs.")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="Output folder for chapter CSVs")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)

    print("Chapter aggregation summary")
    for key, in_path in INPUTS.items():
        out_path = out_dir / OUTPUT_NAMES[key]
        out_df, info = aggregate_file(in_path, out_path)
        sample = out_df.head(3).to_dict(orient="records")
        print(
            f"- {in_path} -> {out_path} | chapters={info['chapters']} min={info['min_chapter']} max={info['max_chapter']}"
        )
        print(f"  sample={sample}")


if __name__ == "__main__":
    main()
