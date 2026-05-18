"""טעינת קבצי KMS Excel עם זיהוי שורת כותרת ונרמול שמות עמודות."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# שם קנוני -> וריאציות אפשריות בקובץ (אחרי נרמול בסיסי)
COLUMN_ALIASES: dict[str, list[str]] = {
    'מק"ט': ['מק"ט', 'מק"ט פריט', "מק'ט פריט"],
    "מספר ספק": ["מספר ספק משהב\"ט", "מס' ספק משהב\"ט", "מספר ספק"],
    "מס' ספק שיקום": ["מס' ספק שיקום", "מספר ספק שיקום"],
    "שם ספק": ["שם ספק"],
    "יישוב קליניקה": [
        "ישוב קליניקה/סאפ/דואר/מגורים ספק",
        "יישוב קליניקה",
        "ישוב קליניקה",
    ],
    "מחיר הסכם": ["מחיר הסכם", "מחיר", "סכום הסכם"],
    "תיאור פריט": ["תיאור פריט", "תיאור פריט."],
    "סוג זכאי": ["סוג זכאי", ".סוג זכאי"],
    "סוג סכום": ["סוג סכום", "סוג סכום."],
    "רמת בסיס": ["רמת בסיס", "רמת בסיס."],
    "רמת חריגה": ["רמת חריגה", "רמת חריגה."],
    "אחוז לחריגה": ["אחוז לחריגה", "אחוז לחריגה."],
    "סכום": ["סכום", "סכום."],
}

HEADER_MARKERS: dict[str, list[str]] = {
    "items": ['מק"ט'],
    "suppliers": ["מספר ספק משהב\"ט", "שם ספק"],
    "agreements": ['מק"ט פריט', "מספר ספק משהב\"ט"],
}


def normalize_column_name(name: object) -> str:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ""
    text = str(name).strip()
    text = text.strip(".")
    text = re.sub(r"\s+", " ", text)
    return text


def _find_header_row(raw: pd.DataFrame, markers: list[str]) -> int:
    normalized_markers = {normalize_column_name(m) for m in markers}
    for idx in range(len(raw)):
        row_values = {normalize_column_name(v) for v in raw.iloc[idx] if pd.notna(v)}
        if normalized_markers & row_values:
            return idx
    return 0


def _canonical_rename(columns: list[object]) -> dict[str, str]:
    normalized = {str(c): normalize_column_name(c) for c in columns}
    rename: dict[str, str] = {}

    for canonical, aliases in COLUMN_ALIASES.items():
        alias_norm = {normalize_column_name(a) for a in aliases}
        for original, norm in normalized.items():
            if norm in alias_norm and original not in rename:
                rename[original] = canonical
    return rename


def read_kms_excel(path: Path, sheet_kind: str) -> pd.DataFrame:
    raw = pd.read_excel(path, header=None)
    markers = HEADER_MARKERS.get(sheet_kind, [])
    header_row = _find_header_row(raw, markers) if markers else 0

    df = pd.read_excel(path, header=header_row)
    df = df.rename(columns=_canonical_rename(list(df.columns)))

    # הסרת עמודות ריקות (לרוב Unnamed: 0)
    drop_cols = [c for c in df.columns if str(c).startswith("Unnamed")]
    if drop_cols:
        df = df.drop(columns=drop_cols, errors="ignore")

    # הסרת שורות ללא מק"ט בקובץ פריטים
    if sheet_kind == "items" and 'מק"ט' in df.columns:
        df = df[df['מק"ט'].notna()]
        df['מק"ט'] = df['מק"ט'].astype(str).str.strip()
        df = df[df['מק"ט'] != ""]

    return df.reset_index(drop=True)
