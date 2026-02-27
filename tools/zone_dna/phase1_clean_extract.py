#!/usr/bin/env python3
"""Phase 1: Clean data extraction from GST HSN Excel reports."""

from __future__ import annotations

import argparse
import os
import re
import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


HSN_HEADER = "HSN Code"


def _normalize_col_name(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def find_header_row(excel_path: str, sheet_name: Optional[str] = None) -> int:
    """Find the header row containing the HSN header cell."""
    df_raw = pd.read_excel(excel_path, sheet_name=sheet_name, header=None, dtype=object, engine="openpyxl")
    if isinstance(df_raw, dict):
        # If multiple sheets returned, take the first one
        first_key = next(iter(df_raw.keys()))
        df_raw = df_raw[first_key]
    for row_idx in range(df_raw.shape[0]):
        row = df_raw.iloc[row_idx]
        for val in row:
            if isinstance(val, str) and val.strip() == HSN_HEADER:
                return row_idx
    raise ValueError(f"Header row with '{HSN_HEADER}' not found in {excel_path}")


def _find_column(columns: List[str], targets: List[str]) -> Optional[str]:
    norm_cols = {_normalize_col_name(c): c for c in columns}
    for t in targets:
        t_norm = _normalize_col_name(t)
        if t_norm in norm_cols:
            return norm_cols[t_norm]
    return None


def _find_column_contains(columns: List[str], pattern: str) -> Optional[str]:
    pattern_norm = _normalize_col_name(pattern)
    for c in columns:
        if pattern_norm in _normalize_col_name(c):
            return c
    return None


def normalize_hsn(raw) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (hsn4, chapter2).
    Rules:
    - Accept float like 7404.0, int, str with spaces.
    - Convert to string, strip spaces, drop trailing '.0'.
    - Keep digits only.
    - If empty -> (None, None)
    - If len==1 -> pad to 2 digits then hsn4 = digits.zfill(2) + "00"
    - If len==2 -> hsn4 = digits + "00"
    - If len==3 -> hsn4 = digits.ljust(4, "0")
    - If len>=4 -> hsn4 = digits[:4]
    - chapter2 = hsn4[:2]
    """
    if pd.isna(raw):
        return None, None
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    s = str(raw).strip()
    if s.endswith(".0"):
        s = s[:-2]
    digits = re.findall(r"\d+", s)
    if not digits:
        return None, None
    combined = "".join(digits)
    if not combined:
        return None, None
    if combined.strip("0") == "":
        return None, None
    if len(combined) == 1:
        hsn4 = combined.zfill(2) + "00"
    elif len(combined) == 2:
        hsn4 = combined + "00"
    elif len(combined) == 3:
        hsn4 = combined.ljust(4, "0")
    else:
        hsn4 = combined[:4]
    chapter2 = hsn4[:2]
    if chapter2 == "00":
        chapter2 = hsn4[2:4]
    return hsn4, chapter2


def to_numeric_safe(series: pd.Series, col_name: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.isna().all():
        warnings.warn(f"Column '{col_name}' could not be converted to numeric; values are all NaN.")
    return numeric


def compute_yoy_change(y3: pd.Series, y2: pd.Series) -> pd.Series:
    with np.errstate(divide="ignore", invalid="ignore"):
        return (y3 - y2) / y2


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    with np.errstate(divide="ignore", invalid="ignore"):
        result = numerator / denominator
    result = result.replace([np.inf, -np.inf], np.nan)
    return result


def phase1_clean_extract(input_path: str, output_dir: str, tag: Optional[str] = None, sheet_name: Optional[str] = None) -> str:
    if sheet_name is None:
        sheet_name = 0
    header_row = find_header_row(input_path, sheet_name=sheet_name)
    print(f"Detected header row at index: {header_row}")

    df = pd.read_excel(
        input_path,
        sheet_name=sheet_name,
        header=header_row,
        dtype=object,
        engine="openpyxl",
    )

    df.columns = [str(c).strip() for c in df.columns]

    # Identify columns
    hsn_col = _find_column(df.columns.tolist(), ["HSN Code"])
    if not hsn_col:
        raise ValueError("HSN Code column not found after header detection.")

    zone_col = _find_column(df.columns.tolist(), ["Zone"])
    comm_col = _find_column(df.columns.tolist(), ["Commissionerate"])
    division_col = _find_column(df.columns.tolist(), ["Division"])
    range_col = _find_column(df.columns.tolist(), ["Range"])

    tax_y3_col = _find_column(df.columns.tolist(), ["Taxable Value"])
    tax_y2_col = _find_column(df.columns.tolist(), ["Taxable Value.1"])
    tax_y1_col = _find_column(df.columns.tolist(), ["Taxable Value.2"])

    if not tax_y3_col:
        tax_y3_col = _find_column_contains(df.columns.tolist(), "Taxable Value")

    if not tax_y3_col:
        raise ValueError("Taxable Value (current year) column not found.")

    yoy_col = _find_column_contains(df.columns.tolist(), "% Change in taxable value")
    share_col = _find_column_contains(df.columns.tolist(), "% of HSN to total taxable value")

    # Filter rows where HSN is present
    df = df[df[hsn_col].notna()].copy()

    norm = df[hsn_col].apply(normalize_hsn)
    df["hsn4"] = norm.apply(lambda x: x[0]).astype("string")
    df["chapter2"] = norm.apply(lambda x: x[1]).astype("string")
    df = df[df["hsn4"].notna()].copy()

    df["hsn4"] = df["hsn4"].astype(str).str.zfill(4)
    df["chapter2"] = df["chapter2"].astype(str).str.zfill(2)

    # Validation warnings
    bad_hsn4 = df["hsn4"].str.len().ne(4) | ~df["hsn4"].str.match(r"^\d{4}$")
    if bad_hsn4.any():
        warnings.warn(f"Found {bad_hsn4.sum()} hsn4 values not 4-digit numeric.")
    bad_ch2 = df["chapter2"].str.len().ne(2) | ~df["chapter2"].str.match(r"^\d{2}$")
    if bad_ch2.any():
        warnings.warn(f"Found {bad_ch2.sum()} chapter2 values not 2-digit numeric.")
    bad_zero = df["chapter2"].isin(["0", "00"])
    if bad_zero.any():
        warnings.warn(f"Found {bad_zero.sum()} chapter2 values equal to '0' or '00' after normalization.")

    df["taxable_y3"] = to_numeric_safe(df[tax_y3_col], "taxable_y3")
    df["taxable_y2"] = to_numeric_safe(df[tax_y2_col], "taxable_y2") if tax_y2_col else np.nan
    df["taxable_y1"] = to_numeric_safe(df[tax_y1_col], "taxable_y1") if tax_y1_col else np.nan

    if tax_y2_col is None:
        warnings.warn("Taxable Value.1 column missing; taxable_y2 set to NaN.")
    if tax_y1_col is None:
        warnings.warn("Taxable Value.2 column missing; taxable_y1 set to NaN.")

    if yoy_col:
        df["yoy_change"] = to_numeric_safe(df[yoy_col], "yoy_change")
    else:
        if tax_y2_col:
            df["yoy_change"] = compute_yoy_change(df["taxable_y3"], df["taxable_y2"])
            warnings.warn("yoy_change column missing; computed using taxable_y3 and taxable_y2.")
        else:
            df["yoy_change"] = np.nan
            warnings.warn("yoy_change column missing and taxable_y2 unavailable; set to NaN.")

    if share_col:
        df["share_original"] = to_numeric_safe(df[share_col], "share_original")
    else:
        df["share_original"] = np.nan
        warnings.warn("share_original column missing; set to NaN.")

    # Mean, SD, CV, CAGR
    df["mean_3yr"] = df[["taxable_y1", "taxable_y2", "taxable_y3"]].mean(axis=1, skipna=True)
    df["sd_3yr"] = df[["taxable_y1", "taxable_y2", "taxable_y3"]].std(axis=1, ddof=0, skipna=True)
    df["cv_volatility"] = safe_divide(df["sd_3yr"], df["mean_3yr"])

    with np.errstate(divide="ignore", invalid="ignore"):
        df["cagr_3yr"] = np.where(
            df["taxable_y1"] > 0,
            (df["taxable_y3"] / df["taxable_y1"]) ** (1 / 2) - 1,
            np.nan,
        )

    total_y3 = df["taxable_y3"].sum(skipna=True)
    if total_y3 == 0 or pd.isna(total_y3):
        warnings.warn("Total taxable_y3 is zero or NaN; share_y3_computed set to NaN.")
        df["share_y3_computed"] = np.nan
    else:
        df["share_y3_computed"] = df["taxable_y3"] / total_y3

    # Add location columns (if missing, fill with NaN)
    df["zone"] = df[zone_col] if zone_col else np.nan
    df["commissionerate"] = df[comm_col] if comm_col else np.nan
    df["division"] = df[division_col] if division_col else np.nan
    df["range"] = df[range_col] if range_col else np.nan

    if zone_col is None:
        warnings.warn("Zone column missing; filled with NaN.")
    if comm_col is None:
        warnings.warn("Commissionerate column missing; filled with NaN.")
    if division_col is None:
        warnings.warn("Division column missing; filled with NaN.")
    if range_col is None:
        warnings.warn("Range column missing; filled with NaN.")

    out_cols = [
        "zone",
        "commissionerate",
        "division",
        "range",
        "hsn4",
        "chapter2",
        "taxable_y1",
        "taxable_y2",
        "taxable_y3",
        "share_original",
        "yoy_change",
        "mean_3yr",
        "sd_3yr",
        "cv_volatility",
        "cagr_3yr",
        "share_y3_computed",
    ]

    output_base = output_dir
    if tag:
        output_base = os.path.join(output_dir, tag)
    os.makedirs(output_base, exist_ok=True)

    output_path = os.path.join(output_base, "hsn_cleaned.csv")
    df[out_cols].astype({"hsn4": "string", "chapter2": "string"}).to_csv(output_path, index=False)

    print(f"Total HSN rows processed: {len(df)}")
    raw_digits = df[hsn_col].astype(str).str.replace(r"\\D", "", regex=True)
    len1 = (raw_digits.str.len() == 1).sum()
    len2 = (raw_digits.str.len() == 2).sum()
    len3 = (raw_digits.str.len() == 3).sum()
    len4plus = (raw_digits.str.len() >= 4).sum()
    empty_dropped = norm.apply(lambda x: x[0] is None).sum()
    print(f"HSN length counts: len1={len1}, len2={len2}, len3={len3}, len4plus={len4plus}, empty_dropped={empty_dropped}")
    print(f"Wrote: {output_path}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1: Clean data extraction from HSN Excel report.")
    parser.add_argument("--input", required=True, help="Path to input Excel file")
    parser.add_argument("--output-dir", default=os.path.join(os.path.dirname(__file__), "output"), help="Output directory")
    parser.add_argument("--tag", default=None, help="Optional tag to create a subfolder under output")
    parser.add_argument("--sheet", default=None, help="Optional sheet name or index")
    args = parser.parse_args()

    sheet_name = args.sheet
    if isinstance(sheet_name, str) and sheet_name.isdigit():
        sheet_name = int(sheet_name)

    phase1_clean_extract(args.input, args.output_dir, tag=args.tag, sheet_name=sheet_name)


if __name__ == "__main__":
    main()
