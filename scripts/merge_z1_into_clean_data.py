#!/usr/bin/env python3
"""
Merge BO-derived Z1 aggregates into clean HSN-level and chapter-level CSVs.

Usage:
  python scripts/merge_z1_into_clean_data.py --repo_root "/path/to/repo" [--drop_chapter_00]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Optional

import pandas as pd

HSN_COL_CANDIDATES = ["HSN Code", "HSN", "hsn", "HSN_CODE"]
CHAPTER_COL_CANDIDATES = ["Chapter", "chapter", "Chapter Code", "chapter_code"]

HSN_DIGIT_REGEX = re.compile(r"(\d{2,})")
CHAPTER_DIGIT_REGEX = re.compile(r"(\d{2})")


def find_col_case_insensitive(columns: List[str], candidates: List[str]) -> Optional[str]:
    for cand in candidates:
        for col in columns:
            if cand.lower() == col.lower():
                return col
    for col in columns:
        col_l = col.lower()
        for cand in candidates:
            if cand.lower() in col_l:
                return col
    return None


def hsn4_key_from_series(series: pd.Series) -> pd.Series:
    def extract_key(val: object) -> Optional[int]:
        if pd.isna(val):
            return None
        s = str(val).strip()
        m = HSN_DIGIT_REGEX.search(s)
        if not m:
            return None
        digits = m.group(1)
        if len(digits) < 4:
            return None
        first4 = digits[:4]
        try:
            return int(first4)
        except Exception:
            return None
    return series.apply(extract_key).astype("Int64")


def chapter_key_from_series(series: pd.Series) -> pd.Series:
    def extract_key(val: object) -> Optional[int]:
        if pd.isna(val):
            return None
        s = str(val).strip()
        m = CHAPTER_DIGIT_REGEX.search(s)
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None
    return series.apply(extract_key).astype("Int64")


def warn(msg: str):
    print(f"WARNING: {msg}")


def load_z1_hsn(bo_dir: Path, division: str) -> pd.DataFrame:
    path = bo_dir / f"hsn_z1_{division}.csv"
    df = pd.read_csv(path)
    if "hsn4" not in df.columns:
        raise ValueError(f"Missing hsn4 in {path}")
    df["hsn4_key"] = pd.to_numeric(df["hsn4"], errors="coerce").astype("Int64")
    return df


def load_z1_chapter(bo_dir: Path, division: str) -> pd.DataFrame:
    path = bo_dir / f"chapter_z1_{division}.csv"
    df = pd.read_csv(path)
    if "chapter" not in df.columns:
        raise ValueError(f"Missing chapter in {path}")
    df["chapter_key"] = pd.to_numeric(df["chapter"], errors="coerce").astype("Int64")
    return df


def report_hsn_stats(df: pd.DataFrame, division: str, hsn_col: str):
    total = len(df)
    valid_key = df["hsn4_key"].notna().sum()
    filled = df["No. of GSTNs_z1"].notna().sum()
    hsn_str = df[hsn_col].astype(str)
    starts_00 = hsn_str.str.match(r"^\s*00").sum()
    matched_00 = df.loc[hsn_str.str.match(r"^\s*00"), "No. of GSTNs_z1"].notna().sum()

    print(f"\nHSN merge stats ({division}):")
    print(f"  total rows: {total}")
    print(f"  rows with valid hsn4_key: {valid_key}")
    print(f"  rows filled with z1: {filled}")
    print(f"  rows with HSN starting '00': {starts_00} (matched: {matched_00})")

    top10 = (
        df.dropna(subset=["No. of GSTNs_z1", "hsn4_key"])
        .sort_values("No. of GSTNs_z1", ascending=False)
        .head(10)[["hsn4_key", "No. of GSTNs_z1"]]
    )
    print("  top 10 HSN4 by z1:")
    for _, row in top10.iterrows():
        print(f"    {int(row['hsn4_key'])}: {int(row['No. of GSTNs_z1'])}")

    if valid_key > 0:
        fail_rate = 1 - (filled / valid_key)
        if fail_rate > 0.10:
            warn(f"{division}: >10% HSN rows failed to parse or match. Check HSN column.")
        fill_rate = filled / valid_key
        if fill_rate < 0.60:
            warn(f"{division}: low HSN fill rate ({fill_rate:.0%}). Showing unmatched HSN4 examples.")
            unmatched = df.loc[df["hsn4_key"].notna() & df["No. of GSTNs_z1"].isna(), "hsn4_key"]
            print("  unmatched HSN4 examples:")
            print("   ", ", ".join(map(str, unmatched.dropna().astype(int).head(20).tolist())))


def report_chapter_stats(df: pd.DataFrame, division: str):
    distinct_chapter = df["chapter_key"].nunique(dropna=True)
    filled = df["No. of GSTNs_z1"].notna().sum()
    chapter_zero = (df["chapter_key"] == 0).sum()

    print(f"\nChapter merge stats ({division}):")
    print(f"  distinct chapter_key: {distinct_chapter}")
    print(f"  chapters filled with z1: {filled}")
    print(f"  chapter_key == 0 count: {chapter_zero}")

    top10 = (
        df.dropna(subset=["No. of GSTNs_z1", "chapter_key"])
        .sort_values("No. of GSTNs_z1", ascending=False)
        .head(10)[["chapter_key", "No. of GSTNs_z1"]]
    )
    print("  top 10 chapters by z1:")
    for _, row in top10.iterrows():
        print(f"    {int(row['chapter_key'])}: {int(row['No. of GSTNs_z1'])}")

    if chapter_zero > 0:
        warn(f"{division}: chapter_key == 0 present. Use --drop_chapter_00 to drop.")


def merge_hsn_clean(repo_root: Path, bo_dir: Path, division: str):
    clean_path = repo_root / "Data" / "Cleaned data" / f"{division.capitalize()}.csv"
    if not clean_path.exists():
        raise FileNotFoundError(f"Missing clean HSN file: {clean_path}")

    df = pd.read_csv(clean_path)
    hsn_col = find_col_case_insensitive(df.columns.tolist(), HSN_COL_CANDIDATES)
    if not hsn_col:
        raise ValueError(f"No HSN column found in {clean_path}. Columns: {df.columns.tolist()}")

    df["hsn4_key"] = hsn4_key_from_series(df[hsn_col])

    z1 = load_z1_hsn(bo_dir, division.lower())
    merged = df.merge(z1[["hsn4_key", "z1_hsn_unique"]], on="hsn4_key", how="left")

    if "No. of GSTNs_z1" not in merged.columns:
        merged["No. of GSTNs_z1"] = pd.NA
    merged["No. of GSTNs_z1"] = merged["z1_hsn_unique"].combine_first(merged["No. of GSTNs_z1"])
    merged = merged.drop(columns=["z1_hsn_unique"])

    backup_path = clean_path.with_suffix(".with_z1.csv")
    merged.to_csv(backup_path, index=False)
    merged.to_csv(clean_path, index=False)

    report_hsn_stats(merged, division, hsn_col)


def discover_chapter_files(repo_root: Path, division: str) -> List[Path]:
    division_l = division.lower()
    chapter_root = repo_root / "Data" / "Cleaned data" / "Chapter data"
    if not chapter_root.exists():
        return []

    candidates: List[Path] = []
    for path in chapter_root.glob("*.csv"):
        name_l = path.name.lower()
        if "with_z1" in name_l:
            continue
        if division_l not in name_l:
            continue
        try:
            df = pd.read_csv(path, nrows=1)
        except Exception:
            continue
        cols = [c.lower() for c in df.columns]
        if any("chapter" in c for c in cols):
            candidates.append(path)
    return candidates


def merge_chapter_files(repo_root: Path, bo_dir: Path, division: str, drop_chapter_00: bool):
    z1 = load_z1_chapter(bo_dir, division.lower())
    candidates = discover_chapter_files(repo_root, division)
    if not candidates:
        warn(f"No chapter-level CSV candidates found for {division}.")
        return

    print("\nChapter file candidates:")
    for c in candidates:
        print(f"  {c}")

    for path in candidates:
        df = pd.read_csv(path)
        chapter_col = find_col_case_insensitive(df.columns.tolist(), CHAPTER_COL_CANDIDATES)
        if chapter_col:
            df["chapter_key"] = chapter_key_from_series(df[chapter_col])
        else:
            hsn_col = find_col_case_insensitive(df.columns.tolist(), HSN_COL_CANDIDATES)
            if not hsn_col:
                continue
            df["hsn4_key"] = hsn4_key_from_series(df[hsn_col])
            df["chapter_key"] = (df["hsn4_key"] // 100).astype("Int64")

        if drop_chapter_00:
            df = df[df["chapter_key"] != 0]

        merged = df.merge(z1[["chapter_key", "z1_chapter_unique"]], on="chapter_key", how="left")
        if "No. of GSTNs_z1" not in merged.columns:
            merged["No. of GSTNs_z1"] = pd.NA
        merged["No. of GSTNs_z1"] = merged["z1_chapter_unique"].combine_first(merged["No. of GSTNs_z1"])
        merged = merged.drop(columns=["z1_chapter_unique"])

        backup_path = path.with_suffix(".with_z1.csv")
        merged.to_csv(backup_path, index=False)
        merged.to_csv(path, index=False)

        report_chapter_stats(merged, division)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo_root",
        default="/Users/ankurkumar/Downloads/Arthadrishti",
        help="Repo root path",
    )
    parser.add_argument(
        "--drop_chapter_00",
        action="store_true",
        help="Drop chapter_key == 0 rows",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    if not repo_root.exists():
        repo_root = Path.cwd()

    bo_dir = repo_root / "outputs" / "bo_aggregates"
    if not bo_dir.exists():
        bo_dir = Path("outputs/bo_aggregates")
    if not bo_dir.exists():
        raise FileNotFoundError("BO aggregates directory not found.")

    for division in ["Mandoli", "Gandhinagar"]:
        merge_hsn_clean(repo_root, bo_dir, division)
        merge_chapter_files(repo_root, bo_dir, division, args.drop_chapter_00)


if __name__ == "__main__":
    main()
