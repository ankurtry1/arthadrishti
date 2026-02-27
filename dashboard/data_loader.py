from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from chapter_lookup import get_chapter_name

CUT_FILE_MAP = {
    "total": "delhi_east",
    "mandoli": "mandoli",
    "gandhinagar": "gandhinagar",
}

REQUIRED_COLUMNS = [
    "chapter2",
    "chapter_value_y1",
    "chapter_value_y2",
    "chapter_value_y3",
    "chapter_share_y3",
    "chapter_cagr_3yr",
    "chapter_cv_volatility",
    "type",
]


@st.cache_data(show_spinner=False)
def load_chapter_data(base_path: Path) -> pd.DataFrame:
    frames = []
    for cut, folder in CUT_FILE_MAP.items():
        path = Path(base_path) / folder / "chapter_summary.csv"
        df = pd.read_csv(path)
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"Missing columns in {path}: {missing}")

        df = df.copy()
        df["chapter2"] = df["chapter2"].astype(str).str.zfill(2)
        df["chapter_name"] = df["chapter2"].map(get_chapter_name)
        df["cut"] = cut
        df = df[
            [
                "cut",
                "chapter2",
                "chapter_name",
                "chapter_value_y1",
                "chapter_value_y2",
                "chapter_value_y3",
                "chapter_share_y3",
                "chapter_cagr_3yr",
                "chapter_cv_volatility",
                "type",
            ]
        ]
        frames.append(df)

    unified = pd.concat(frames, ignore_index=True)
    return unified
