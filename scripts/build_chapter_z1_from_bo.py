#!/usr/bin/env python3
"""
Build chapter-level Z1 (unique GSTIN counts per chapter) from BO taxpayer Excel files.

Outputs:
- outputs/bo_normalized/gstin_hsn_exploded_<division>.csv
- outputs/bo_normalized/gstin_chapter_<division>.csv
- outputs/bo_aggregates/hsn_z1_<division>.csv
- outputs/bo_aggregates/chapter_z1_<division>.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable, List, Tuple

import pandas as pd

GSTIN_CANDIDATES = [
    "gstin",
    "gstin uin",
    "gstin/uin",
    "gstin/uin of taxpayer",
]

HSN_CANDIDATES = [
    "hsn",
    "hsn code",
    "hsn codes",
    "hsn/sac",
    "hsn/sac code",
    "hsn/sac codes",
]

SEPARATORS_REGEX = re.compile(r"[;,/|\n\r\t ]+")
DIGIT_REGEX = re.compile(r"\d{2,}")
GSTIN_REGEX = re.compile(r"^[A-Z0-9]{15}$")


def find_header_row(df: pd.DataFrame) -> int:
    for i, row in df.iterrows():
        values = row.astype(str).str.lower().tolist()
        if any(
            any(cand in str(v) for cand in GSTIN_CANDIDATES + HSN_CANDIDATES)
            for v in values
        ):
            return i
    raise ValueError("Could not locate header row containing GSTIN/HSN columns.")


def normalize_headers(headers: Iterable) -> List[str]:
    return [str(h).strip() for h in headers]


def pick_column(columns: List[str], candidates: List[str]) -> str:
    normalized = {c.lower().strip(): c for c in columns}
    matches: List[Tuple[str, str]] = []
    for col in columns:
        col_l = col.lower().strip()
        for cand in candidates:
            if cand in col_l:
                matches.append((cand, col))
    if not matches:
        raise ValueError(f"No matching column found. Available columns: {columns}")
    # Prefer the shortest candidate match
    matches.sort(key=lambda x: (len(x[0]), len(x[1])))
    return matches[0][1]


def parse_hsn_list(raw: str) -> List[str]:
    if raw is None:
        return []
    raw_str = str(raw)
    if raw_str.strip() == "" or raw_str.strip() == "-":
        return []
    parts = SEPARATORS_REGEX.split(raw_str)
    codes: List[str] = []
    for part in parts:
        for m in DIGIT_REGEX.findall(part):
            codes.append(m)
    return codes


def to_hsn4(code: str) -> str | None:
    if not code:
        return None
    code = str(code).strip()
    if len(code) < 4:
        return None
    return code[:4]


def clean_gstin(value: str) -> str | None:
    if value is None:
        return None
    gstin = str(value).strip().upper()
    if not GSTIN_REGEX.match(gstin):
        return None
    return gstin


def process_file(path: Path, division: str) -> tuple[pd.DataFrame, int]:
    raw = pd.read_excel(path, header=None)
    header_row = find_header_row(raw)
    headers = normalize_headers(raw.iloc[header_row].tolist())
    df = raw.iloc[header_row + 1 :].copy()
    df.columns = headers
    total_rows = len(df)

    gstin_col = pick_column(headers, GSTIN_CANDIDATES)
    hsn_col = pick_column(headers, HSN_CANDIDATES)

    df = df[[gstin_col, hsn_col]].copy()
    df.columns = ["gstin_raw", "hsn_raw"]
    df["gstin"] = df["gstin_raw"].apply(clean_gstin)
    df = df.dropna(subset=["gstin"])

    exploded_rows = []
    for _, row in df.iterrows():
        gstin = row["gstin"]
        raw_hsn = row["hsn_raw"]
        codes = parse_hsn_list(raw_hsn)
        hsn4_set = set()
        for code in codes:
            hsn4 = to_hsn4(code)
            if hsn4:
                hsn4_set.add(hsn4)
        for hsn4 in hsn4_set:
            exploded_rows.append(
                {
                    "division": division,
                    "gstin": gstin,
                    "hsn_raw": raw_hsn,
                    "hsn4": hsn4,
                    "chapter": hsn4[:2],
                }
            )

    return pd.DataFrame(exploded_rows), total_rows


def summarize_division(df: pd.DataFrame, division: str, total_bo_rows: int):
    if df.empty:
        print(f"{division}: no rows after processing.")
        return
    total_rows = len(df)
    distinct_gstin = df["gstin"].nunique()
    distinct_hsn4 = df["hsn4"].nunique()
    distinct_chapter = df["chapter"].nunique()
    print(f"\n{division} summary:")
    print(f"  total BO rows read: {total_bo_rows}")
    print(f"  exploded rows: {total_rows}")
    print(f"  distinct GSTINs: {distinct_gstin}")
    print(f"  distinct HSN4: {distinct_hsn4}")
    print(f"  distinct chapters: {distinct_chapter}")

    top10 = (
        df.drop_duplicates(subset=["gstin", "chapter"])
        .groupby("chapter")["gstin"]
        .nunique()
        .sort_values(ascending=False)
        .head(10)
    )
    print("  top 10 chapters by z1:")
    for chapter, count in top10.items():
        print(f"    {chapter}: {count}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bo_dir",
        default="/Users/ankurkumar/Downloads/Arthadrishti/Data/Raw data/BO data",
        help="Directory containing BO taxpayer Excel files",
    )
    parser.add_argument(
        "--out_dir",
        default="outputs",
        help="Output directory",
    )
    args = parser.parse_args()

    bo_dir = Path(args.bo_dir)
    if not bo_dir.exists():
        fallback = Path("/mnt/data")
        if fallback.exists():
            bo_dir = fallback
        else:
            raise FileNotFoundError(f"BO directory not found: {args.bo_dir}")

    out_dir = Path(args.out_dir)
    norm_dir = out_dir / "bo_normalized"
    agg_dir = out_dir / "bo_aggregates"
    norm_dir.mkdir(parents=True, exist_ok=True)
    agg_dir.mkdir(parents=True, exist_ok=True)

    files = list(bo_dir.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"No .xlsx files found in {bo_dir}")

    for division in ["Mandoli", "Gandhinagar"]:
        division_files = [f for f in files if division.lower() in f.name.lower()]
        if not division_files:
            print(f"No files found for {division}")
            continue

        all_rows = []
        bo_rows_total = 0
        for f in division_files:
            df_exploded, bo_rows = process_file(f, division)
            bo_rows_total += bo_rows
            if not df_exploded.empty:
                all_rows.append(df_exploded)

        if not all_rows:
            print(f"No usable rows for {division}")
            continue

        exploded = pd.concat(all_rows, ignore_index=True)
        exploded = exploded.dropna(subset=["hsn4", "chapter"])

        # GSTIN-HSN exploded table
        exploded_path = norm_dir / f"gstin_hsn_exploded_{division.lower()}.csv"
        exploded.to_csv(exploded_path, index=False)

        # GSTIN-CHAPTER table
        gstin_chapter = exploded[["division", "gstin", "chapter"]].drop_duplicates()
        gstin_chapter_path = norm_dir / f"gstin_chapter_{division.lower()}.csv"
        gstin_chapter.to_csv(gstin_chapter_path, index=False)

        # HSN-level unique GSTIN counts
        hsn_z1 = (
            exploded.drop_duplicates(subset=["gstin", "hsn4"])
            .groupby(["division", "hsn4"])["gstin"]
            .nunique()
            .reset_index()
            .rename(columns={"gstin": "z1_hsn_unique"})
        )
        hsn_z1_path = agg_dir / f"hsn_z1_{division.lower()}.csv"
        hsn_z1.to_csv(hsn_z1_path, index=False)

        # Chapter-level unique GSTIN counts
        chapter_z1 = (
            gstin_chapter.groupby(["division", "chapter"])["gstin"]
            .nunique()
            .reset_index()
            .rename(columns={"gstin": "z1_chapter_unique"})
        )
        chapter_z1_path = agg_dir / f"chapter_z1_{division.lower()}.csv"
        chapter_z1.to_csv(chapter_z1_path, index=False)

        summarize_division(exploded, division, bo_rows_total)


if __name__ == "__main__":
    main()
