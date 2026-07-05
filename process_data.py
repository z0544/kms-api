"""ETL: טעינת קבצי XLSX, יצירת Unique ID, ושמירה ל-SQLite."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

from db_schema import ensure_schema
from entity_id import build_entity_id_series
from excel_loader import read_kms_excel
from config import (
    AGREEMENTS_FILE,
    DATA_DIR,
    DB_PATH,
    GEO_MAPPING_PATH,
    ITEMS_FILE,
    SUPPLIERS_FILE,
    UNIQUE_ID_COLUMNS,
    USE_FTS,
)


def _resolve_data_file(filename: str) -> Path:
    path = DATA_DIR / filename
    if path.exists():
        return path
    matches = list(DATA_DIR.glob(f"*{Path(filename).stem[:20]}*"))
    if matches:
        return matches[0]
    raise FileNotFoundError(
        f"לא נמצא קובץ: {filename}\n"
        f"הנח את קבצי ה-XLSX בתיקייה: {DATA_DIR}"
    )


def _normalize_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col not in df.columns:
            raise ValueError(f"עמודה חסרה בקובץ פריטים: {col}")
        df[col] = df[col].fillna(0).astype(str).str.strip()
    return df


def _build_entity_id(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_columns(df, UNIQUE_ID_COLUMNS)
    df["entity_id"] = build_entity_id_series(df)
    return df


def _deduplicate_items(df: pd.DataFrame) -> pd.DataFrame:
    if "סכום" not in df.columns:
        return df.drop_duplicates(subset=["entity_id"], keep="first")
    numeric_sum = pd.to_numeric(df["סכום"], errors="coerce")
    df = df.assign(_sort_amount=numeric_sum.fillna(float("-inf")))
    df = df.sort_values(by="_sort_amount", ascending=False).drop(columns="_sort_amount")
    return df.drop_duplicates(subset=["entity_id"], keep="first")


def _apply_geo_mapping(df_suppliers: pd.DataFrame) -> pd.DataFrame:
    if not GEO_MAPPING_PATH.exists():
        return df_suppliers
    geo = pd.read_csv(GEO_MAPPING_PATH, encoding="utf-8-sig")
    settlement_col = next(
        (c for c in ("יישוב", "יישוב קליניקה", "settlement") if c in geo.columns),
        geo.columns[0],
    )
    region_col = next(
        (c for c in ("מחוז", "אזור", "district", "region") if c in geo.columns),
        geo.columns[-1],
    )
    supplier_settlement = "יישוב קליניקה"
    if supplier_settlement not in df_suppliers.columns:
        return df_suppliers
    geo = geo.rename(columns={settlement_col: supplier_settlement, region_col: "אזור"})
    return df_suppliers.merge(
        geo[[supplier_settlement, "אזור"]].drop_duplicates(),
        on=supplier_settlement,
        how="left",
    )


def prepare_items_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """מכין DataFrame פריטים: נרמול, entity_id ו-dedup."""
    df = _build_entity_id(df.copy())
    return _deduplicate_items(df)


def process_data() -> dict[str, int]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    items_path = _resolve_data_file(ITEMS_FILE)
    suppliers_path = _resolve_data_file(SUPPLIERS_FILE)
    agreements_path = _resolve_data_file(AGREEMENTS_FILE)

    df_items = read_kms_excel(items_path, "items")
    df_suppliers = read_kms_excel(suppliers_path, "suppliers")
    df_agreements = read_kms_excel(agreements_path, "agreements")

    df_items = prepare_items_dataframe(df_items)
    df_suppliers = _apply_geo_mapping(df_suppliers)

    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        df_items["is_deleted"] = 0
        df_items["created_at"] = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        df_items["updated_at"] = df_items["created_at"]
        df_items.to_sql("items", conn, if_exists="replace", index=False)
        df_suppliers.to_sql("suppliers", conn, if_exists="replace", index=False)
        df_agreements.to_sql("agreements", conn, if_exists="replace", index=False)
        if USE_FTS:
            from fts_service import rebuild_fts_index

            fts_rows = rebuild_fts_index(conn)
            print(f"  FTS5 index: {fts_rows} rows")
    finally:
        conn.close()

    stats = {
        "items": len(df_items),
        "suppliers": len(df_suppliers),
        "agreements": len(df_agreements),
    }
    print(f"Database created: {DB_PATH}")
    print(f"  items: {stats['items']} rows")
    print(f"  suppliers: {stats['suppliers']} rows")
    print(f"  agreements: {stats['agreements']} rows")
    return stats


if __name__ == "__main__":
    try:
        process_data()
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
