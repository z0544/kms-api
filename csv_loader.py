"""טעינת קובץ CSV של פריטים עם נרמול עמודות כמו Excel."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from excel_loader import _canonical_rename, normalize_column_name

HEADER_MARKERS = ['מק"ט']


def _find_header_row(raw: pd.DataFrame) -> int:
    normalized_markers = {normalize_column_name(m) for m in HEADER_MARKERS}
    for idx in range(min(len(raw), 20)):
        row_values = {normalize_column_name(v) for v in raw.iloc[idx] if pd.notna(v)}
        if normalized_markers & row_values:
            return idx
    return 0


def read_kms_csv(source: bytes | Path | str) -> pd.DataFrame:
    """קורא CSV (bytes או נתיב) ומחזיר DataFrame מנורמל."""
    if isinstance(source, (bytes, bytearray)):
        raw = pd.read_csv(io.BytesIO(source), header=None, encoding="utf-8-sig")
    else:
        raw = pd.read_csv(source, header=None, encoding="utf-8-sig")

    header_row = _find_header_row(raw)
    if isinstance(source, (bytes, bytearray)):
        df = pd.read_csv(io.BytesIO(source), header=header_row, encoding="utf-8-sig")
    else:
        df = pd.read_csv(source, header=header_row, encoding="utf-8-sig")

    df = df.rename(columns=_canonical_rename(list(df.columns)))

    drop_cols = [c for c in df.columns if str(c).startswith("Unnamed")]
    if drop_cols:
        df = df.drop(columns=drop_cols, errors="ignore")

    if 'מק"ט' not in df.columns:
        raise ValueError('עמודת מק"ט חסרה בקובץ CSV')

    df = df[df['מק"ט'].notna()]
    df['מק"ט'] = df['מק"ט'].astype(str).str.strip()
    df = df[df['מק"ט'] != ""]
    return df.reset_index(drop=True)


def read_kms_csv_with_fallback(source: bytes) -> pd.DataFrame:
    """מנסה utf-8-sig ואז cp1255 לקבצים מ-Excel."""
    try:
        return read_kms_csv(source)
    except UnicodeDecodeError:
        raw = pd.read_csv(io.BytesIO(source), header=None, encoding="cp1255")
        header_row = _find_header_row(raw)
        df = pd.read_csv(io.BytesIO(source), header=header_row, encoding="cp1255")
        df = df.rename(columns=_canonical_rename(list(df.columns)))
        drop_cols = [c for c in df.columns if str(c).startswith("Unnamed")]
        if drop_cols:
            df = df.drop(columns=drop_cols, errors="ignore")
        if 'מק"ט' not in df.columns:
            raise ValueError('עמודת מק"ט חסרה בקובץ CSV') from None
        df = df[df['מק"ט'].notna()]
        df['מק"ט'] = df['מק"ט'].astype(str).str.strip()
        df = df[df['מק"ט'] != ""]
        return df.reset_index(drop=True)
