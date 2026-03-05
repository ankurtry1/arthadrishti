#!/usr/bin/env python3
"""Merge HSN Section and HSN Chapter from .numbers files into cleaned CSVs."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from numbers_parser import Document


def norm_hsn(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    s = re.sub(r"\.0+$", "", s)
    digits = re.sub(r"\D", "", s)
    if not digits:
        return ""
    try:
        return str(int(digits, 10))
    except ValueError:
        return ""


def read_numbers_map(path: Path) -> dict[str, tuple[str, str]]:
    doc = Document(str(path))
    table = doc.sheets[0].tables[0]
    rows = list(table.rows(values_only=True))
    headers = [str(x).strip() for x in rows[0]]

    try:
        hsn_i = headers.index("HSN Code")
        sec_i = headers.index("HSN Section")
        ch_i = headers.index("HSN Chapter")
    except ValueError as exc:
        raise ValueError(f"Expected columns missing in {path}: {headers}") from exc

    mapping: dict[str, tuple[str, str]] = {}
    for r in rows[1:]:
        if len(r) <= max(hsn_i, sec_i, ch_i):
            continue
        h = norm_hsn(r[hsn_i])
        if not h:
            continue
        sec = "" if r[sec_i] is None else str(r[sec_i]).strip()
        chap = "" if r[ch_i] is None else str(r[ch_i]).strip()
        mapping[h] = (sec, chap)
    return mapping


def merge_csv(csv_path: Path, mapping: dict[str, tuple[str, str]]) -> tuple[int, int]:
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    # remove existing columns if present so reruns are stable
    clean_fieldnames = [f for f in fieldnames if f not in ("HSN Section", "HSN Chapter")]

    if "HSN Code" not in clean_fieldnames:
        raise ValueError(f"HSN Code column not found in {csv_path}")

    idx = clean_fieldnames.index("HSN Code")
    out_fieldnames = clean_fieldnames[: idx + 1] + ["HSN Section", "HSN Chapter"] + clean_fieldnames[idx + 1 :]

    matched = 0
    for row in rows:
        h = norm_hsn(row.get("HSN Code", ""))
        sec, chap = mapping.get(h, ("", ""))
        if sec or chap:
            matched += 1
        row["HSN Section"] = sec
        row["HSN Chapter"] = chap

    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return len(rows), matched


def main() -> None:
    parser = argparse.ArgumentParser(description="Add HSN Section/HSN Chapter from .numbers to cleaned CSVs.")
    parser.add_argument("--repo", default=".", help="Repo root path")
    args = parser.parse_args()

    root = Path(args.repo).resolve()
    pairs = [
        (
            root / "Data/Cleaned data/Gandhinagar.csv",
            Path("/Users/ankurkumar/Downloads/gandhinagar_name.numbers"),
        ),
        (
            root / "Data/Cleaned data/Mandoli.csv",
            Path("/Users/ankurkumar/Downloads/Mandoli_name.numbers"),
        ),
    ]

    print("Merge summary")
    for csv_path, numbers_path in pairs:
        mapping = read_numbers_map(numbers_path)
        rows, matched = merge_csv(csv_path, mapping)
        print(f"- {csv_path.name}: rows={rows}, matched={matched}, unmatched={rows - matched}")


if __name__ == "__main__":
    main()
