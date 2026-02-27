# Zone Industrial DNA Pipeline (Phase 1–3)

This folder implements a three-phase pipeline to extract, classify, and cluster HSN-based GST data.
Only three outputs are produced per tag: `hsn_cleaned.csv`, `chapter_summary.csv`, and `cluster_summary.csv`.

## Phase 1 — Clean Data Extraction
Reads the input Excel report, detects the header row dynamically (searches for `HSN Code`), normalizes HSN codes to 4 digits, and produces a cleaned CSV with derived metrics (mean, CV, CAGR, and computed shares).

Output:
- `output/hsn_cleaned.csv`

Notes:
- `hsn4` is always a 4-digit string (zero-padded if needed).
- `chapter2` is always a 2-digit string derived as `hsn4[:2]`. This preserves leading zeros (e.g., `01`).

**HSN Normalization Rules**
- Some source rows contain chapter-only HSNs with 2 digits (e.g., `44`, `62`).
- These are mapped to a 4-digit proxy by appending `00` (e.g., `44` → `4400`), so `chapter2` remains `44`.
- Single-digit HSNs are left-padded to 2 digits, then mapped to `CC00` (e.g., `4` → `0400`).
- For 3-digit HSNs, we right-pad to 4 digits (e.g., `123` → `1230`).
- For 4+ digits, we take the first 4 digits.
- `chapter2` is always a two-character string and never derived via integer division.

## Phase 2 — Chapter Classification
Aggregates `hsn_cleaned.csv` to chapter level, applies chapter-to-sector classification from `config.yaml`, computes chapter shares, CAGR, and CV, and writes the Transformation Index (manufacturing vs primary).

Outputs:
- `output/chapter_summary.csv`

Auditability additions:
- `chapter_summary.csv` includes `hsn_count`, `hsn_list_sample`, and `top_hsn4_by_value_y3_json` to show what HSNs rolled up.
- `transformation_index_y3` is embedded as a repeated column on every row.

## Phase 3 — Cluster Baskets
Aggregates chapter-level results into clusters defined in `config.yaml`, computes cluster shares, weighted CAGR, CV, and balance score.

Output:
- `output/cluster_summary.csv`

Auditability additions:
- `cluster_summary.csv` now lists `included_chapters`, `rule_source`, and JSON breakdown columns for component values and HSN counts.

## How To Run
Run the scripts in order. Use `--tag` to keep outputs for each Excel file separate.

Example:

```bash
python phase1_clean_extract.py --input "/path/to/HSN wise value of goods supplied from a Gandhinagar (GST_RPTPDR_111).xlsx" --tag gandhinagar
python phase2_chapter_classification.py --input output/gandhinagar/hsn_cleaned.csv --tag gandhinagar
python phase3_cluster_baskets.py --input output/gandhinagar/chapter_summary.csv --tag gandhinagar
```

Repeat for each Excel file in the ADVAIT folder by changing the `--input` and `--tag` values.
