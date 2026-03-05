#!/usr/bin/env python3
"""Insert Chapter column after HSN Code for cleaned CSV files."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_FILES = [
    "Data/Cleaned data/Mandoli.csv",
    "Data/Cleaned data/Gandhinagar.csv",
    "Data/Cleaned data/Delhi East.csv",
]


def normalize_header(name: str) -> str:
    return str(name or "").replace("\ufeff", "").strip().lower()


def normalize_hsn(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""

    # Convert forms like "7404.0" to "7404" first.
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".", 1)[0]

    digits = re.sub(r"\D", "", s)
    if not digits:
        return ""

    try:
        return str(int(digits, 10))
    except ValueError:
        return ""


def compute_chapter(raw_hsn: str) -> str:
    hsn = normalize_hsn(raw_hsn)
    if not hsn:
        return ""
    if len(hsn) >= 2:
        return hsn[:2]
    return hsn


def find_hsn_key(fieldnames: List[str]) -> str:
    by_norm = {normalize_header(k): k for k in fieldnames}
    key = by_norm.get("hsn code")
    if not key:
        raise ValueError("Could not find 'HSN Code' column.")
    return key


def insert_chapter_fieldnames(fieldnames: List[str], hsn_key: str) -> List[str]:
    cleaned = [f for f in fieldnames if normalize_header(f) != "chapter"]
    idx = cleaned.index(hsn_key)
    return cleaned[: idx + 1] + ["Chapter"] + cleaned[idx + 1 :]


def process_file(path: Path) -> Tuple[int, int, int]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        if not fieldnames:
            raise ValueError(f"No header found in {path}")

        hsn_key = find_hsn_key(fieldnames)
        out_fieldnames = insert_chapter_fieldnames(fieldnames, hsn_key)

        rows: List[Dict[str, str]] = []
        non_empty = 0
        chapters = set()

        for row in reader:
            chapter = compute_chapter(row.get(hsn_key, ""))
            row["Chapter"] = chapter
            rows.append(row)
            if chapter:
                non_empty += 1
                chapters.add(chapter)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=out_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return len(rows), non_empty, len(chapters)


def main() -> None:
    parser = argparse.ArgumentParser(description="Add Chapter column after HSN Code in cleaned CSVs.")
    parser.add_argument("files", nargs="*", default=DEFAULT_FILES, help="CSV file paths to process")
    args = parser.parse_args()

    print("Chapter column update summary")
    for file_path in args.files:
        p = Path(file_path)
        rows, non_empty, uniq = process_file(p)
        print(f"- {p}: rows={rows}, non_empty_chapter={non_empty}, unique_chapters={uniq}")


if __name__ == "__main__":
    main()
