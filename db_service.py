"""שכבת גישה לבסיס הנתונים – חיפוש, פריטים וספקים."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from enum import Enum
from typing import Any, Generator

from config import DB_PATH, REFUND_NOTE
from utils import clean_record

SEARCH_FIELDS: dict[str, list[str]] = {
    "entity_id": ["entity_id"],
    "מקט": ['מק"ט'],
    "makt": ['מק"ט'],
    "sku": ['מק"ט'],
    "תיאור": ["תיאור פריט"],
    "description": ["תיאור פריט"],
    "זכאי": ["סוג זכאי"],
    "ספק": ["supplier"],
    "supplier": ["supplier"],
    "all": ["entity_id", 'מק"ט', "תיאור פריט", "סוג זכאי"],
}

VARIANT_LABELS = [
    ("רמת בסיס", "בסיס"),
    ("רמת חריגה", "חריגה"),
    ("אחוז לחריגה", "אחוז"),
    ("סוג זכאי", "זכאי"),
    ("סוג סכום", "סוג סכום"),
    ("סכום", "סכום"),
]


class MatchMode(str, Enum):
    exact = "exact"
    contains = "contains"
    startswith = "startswith"
    endswith = "endswith"


MATCH_ALIASES: dict[str, MatchMode] = {
    "exact": MatchMode.exact,
    "שווה": MatchMode.exact,
    "=": MatchMode.exact,
    "contains": MatchMode.contains,
    "מכיל": MatchMode.contains,
    "startswith": MatchMode.startswith,
    "מתחיל": MatchMode.startswith,
    "endswith": MatchMode.endswith,
    "מסתיים": MatchMode.endswith,
}

ITEM_LIST_COLUMNS = [
    "entity_id",
    'מק"ט',
    "תיאור פריט",
    "סוג זכאי",
    "סוג סכום",
    "רמת בסיס",
    "רמת חריגה",
    "אחוז לחריגה",
    "סכום",
]


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_db_dep() -> Generator[sqlite3.Connection, None, None]:
    """תלות FastAPI — חיבור SQLite אחד לכל בקשה HTTP."""
    with get_db() as conn:
        yield conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def parse_match_mode(match: str) -> MatchMode:
    key = match.strip().lower()
    if key in MATCH_ALIASES:
        return MATCH_ALIASES[key]
    return MatchMode(key)


def parse_field(field: str) -> list[str]:
    key = field.strip().lower()
    if key not in SEARCH_FIELDS:
        raise ValueError(f"field לא תקין: {field}")
    return SEARCH_FIELDS[key]


def _sql_value(value: str, mode: MatchMode) -> str:
    if mode == MatchMode.exact:
        return value
    if mode == MatchMode.contains:
        return f"%{value}%"
    if mode == MatchMode.startswith:
        return f"{value}%"
    return f"%{value}"


def _build_where(field: str, value: str, mode: MatchMode) -> tuple[str, tuple[str, ...]]:
    columns = parse_field(field)
    parts: list[str] = []
    params: list[str] = []
    for column in columns:
        sql_value = _sql_value(value, mode)
        col_sql = "entity_id" if column == "entity_id" else f"[{column}]"
        if mode == MatchMode.exact:
            parts.append(f"{col_sql} = ?")
            params.append(value)
        else:
            parts.append(f"{col_sql} LIKE ?")
            params.append(sql_value)
    return " OR ".join(parts), tuple(params)


def _pick_columns(row: sqlite3.Row, columns: list[str]) -> dict[str, Any]:
    data = _row_to_dict(row)
    return clean_record({c: data.get(c) for c in columns if c in data}, hide_undefined=True)


def _select_items_sql() -> str:
    return ", ".join(
        f"[{c}]" if c != "entity_id" else "entity_id" for c in ITEM_LIST_COLUMNS
    )


def _makt_join_sql() -> str:
    return (
        "(CAST(a.[מק\"ט] AS TEXT) = CAST(i.[מק\"ט] AS TEXT) "
        "OR CAST(a.[מק\"ט] AS INTEGER) = CAST(i.[מק\"ט] AS INTEGER))"
    )


def search_items_by_supplier(
    value: str,
    mode: MatchMode,
    limit: int,
) -> list[dict[str, Any]]:
    sql_value = _sql_value(value, mode)
    supplier_cond = "s.[שם ספק] LIKE ?"
    params: list[str] = [sql_value]
    if mode == MatchMode.exact:
        supplier_cond = "s.[שם ספק] = ?"
        params = [value]

    select_cols = ", ".join(f"i.[{c}]" if c != "entity_id" else "i.entity_id" for c in ITEM_LIST_COLUMNS)
    sql = f"""
        SELECT DISTINCT {select_cols}
        FROM items i
        INNER JOIN agreements a ON {_makt_join_sql()}
        INNER JOIN suppliers s ON a.[מספר ספק] = s.[מספר ספק]
        WHERE {supplier_cond}
        LIMIT ?
    """
    with get_db() as conn:
        rows = conn.execute(sql, (*params, limit)).fetchall()
    return [_pick_columns(r, ITEM_LIST_COLUMNS) for r in rows]


def search_items(
    value: str,
    mode: MatchMode,
    field: str,
    limit: int,
) -> list[dict[str, Any]]:
    if field in ("ספק", "supplier"):
        return search_items_by_supplier(value, mode, limit)

    where_sql, params = _build_where(field, value, mode)
    select_cols = _select_items_sql()
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT {select_cols} FROM items WHERE {where_sql} LIMIT ?",
            (*params, limit),
        ).fetchall()
    return [_pick_columns(r, ITEM_LIST_COLUMNS) for r in rows]


def group_items_by_makt(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for item in items:
        makt = str(item.get('מק"ט', "") or "")
        if makt not in groups:
            groups[makt] = {
                'מק"ט': makt,
                "תיאור פריט": item.get("תיאור פריט"),
                "variant_count": 0,
                "variants": [],
            }
            order.append(makt)
        groups[makt]["variants"].append(item)
        groups[makt]["variant_count"] += 1
    return enrich_groups_with_supplier_counts([groups[m] for m in order])


def _makt_count_lookup_keys(makt: str) -> list[str]:
    m = str(makt).strip()
    if not m:
        return []
    keys = [m]
    if m.isdigit():
        keys.append(str(int(m)))
    return keys


def get_supplier_counts_for_makts(makts: list[str]) -> dict[str, int]:
    """מפת מק\"ט → מספר ספקים ייחודיים (הסכמים).

    אופטימיזציה (v0.8.1):
    - אופציה 1 — שאילתה ממוקדת עם WHERE IN (?, ...) במקום סריקה גורפת של agreements.
    - שילוב גם של מפתחות "כמספר" וגם "כמחרוזת" כדי להתאים למצבי DB שונים.
    """
    unique = list({str(m).strip() for m in makts if str(m).strip()})
    if not unique:
        return {}

    # מכינים את כל הוריאנטים האפשריים (string + int) כדי להתאים לכל הטיפוסים ב-DB
    lookup_set: set[str] = set()
    variants_per_makt: dict[str, list[str]] = {}
    for makt in unique:
        keys = _makt_count_lookup_keys(makt)
        variants_per_makt[makt] = keys
        lookup_set.update(keys)

    if not lookup_set:
        return {m: 0 for m in unique}

    placeholders = ", ".join(["?"] * len(lookup_set))
    params = list(lookup_set)

    sql = f"""
        SELECT TRIM(CAST(a.[מק"ט] AS TEXT)) AS makt_key,
               COUNT(DISTINCT a.[מספר ספק]) AS cnt
        FROM agreements a
        WHERE TRIM(CAST(a.[מק"ט] AS TEXT)) IN ({placeholders})
        GROUP BY makt_key
    """

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    by_key: dict[str, int] = {}
    for row in rows:
        key = str(row["makt_key"]).strip()
        cnt = int(row["cnt"])
        by_key[key] = cnt
        # ניסיון גם בלי zero-padding
        if key.isdigit():
            by_key[str(int(key))] = cnt

    result: dict[str, int] = {}
    for makt in unique:
        cnt = 0
        for key in variants_per_makt[makt]:
            if key in by_key:
                cnt = by_key[key]
                break
        result[makt] = cnt
    return result


def enrich_groups_with_supplier_counts(
    groups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    makts = [str(g.get('מק"ט', "")).strip() for g in groups if g.get('מק"ט')]
    counts = get_supplier_counts_for_makts(makts)
    for group in groups:
        makt = str(group.get('מק"ט', "")).strip()
        cnt = counts.get(makt, 0)
        group["supplier_count"] = cnt
        for variant in group.get("variants", []):
            variant["supplier_count"] = cnt
    return groups


def variant_summary(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, label in VARIANT_LABELS:
        val = item.get(key)
        if val is not None and str(val) not in ("", "לא מוגדר", "0", "0.0"):
            parts.append(f"{label}: {val}")
    return " · ".join(parts) if parts else "ברירת מחדל"


def get_item_by_entity_id(entity_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM items WHERE entity_id = ?",
            (entity_id,),
        ).fetchone()
        if not row:
            return None
        item = clean_record(_row_to_dict(row))
        makt = item.get('מק"ט')
        if makt:
            item["authorized_suppliers"] = get_suppliers_for_makt(str(makt), conn=conn)
        else:
            item["authorized_suppliers"] = []
        if "החזר" in str(item.get("סוג סכום", "")):
            item["special_note"] = REFUND_NOTE
        return item


def get_suppliers_for_makt(
    makt: str,
    *,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    def _run(connection: sqlite3.Connection) -> list[dict[str, Any]]:
        agreement_cols = {r[1] for r in connection.execute("PRAGMA table_info(agreements)")}
        supplier_cols = {r[1] for r in connection.execute("PRAGMA table_info(suppliers)")}
        select_parts = [
            "s.[מספר ספק]",
            "s.[שם ספק]",
            "s.[יישוב קליניקה]",
        ]
        if "אזור" in supplier_cols:
            select_parts.append("s.[אזור]")
        for phone_col in ("נייד ספק", "טלפון עבודה ספק", "נייח ספק"):
            if phone_col in supplier_cols:
                select_parts.append(f"s.[{phone_col}]")
        if "מחיר הסכם" in agreement_cols:
            select_parts.append("a.[מחיר הסכם]")
        if "האם בתוקף" in agreement_cols:
            select_parts.append("a.[האם בתוקף]")
        makt_str = str(makt).strip()
        if makt_str.isdigit():
            where_makt = (
                "(CAST(a.[מק\"ט] AS TEXT) = ? "
                "OR CAST(a.[מק\"ט] AS INTEGER) = CAST(? AS INTEGER))"
            )
            makt_params: tuple[str, ...] = (makt_str, makt_str)
        else:
            where_makt = "CAST(a.[מק\"ט] AS TEXT) = ?"
            makt_params = (makt_str,)

        sql = f"""
            SELECT {", ".join(select_parts)}
            FROM agreements a
            JOIN suppliers s ON a.[מספר ספק] = s.[מספר ספק]
            WHERE {where_makt}
            ORDER BY s.[שם ספק]
        """
        rows = connection.execute(sql, makt_params).fetchall()
        return [clean_record(_row_to_dict(r), hide_undefined=True) for r in rows]

    if conn is not None:
        return _run(conn)
    with get_db() as connection:
        return _run(connection)


def get_items_for_makt(makt: str) -> list[dict[str, Any]]:
    """כל הוריאנטים של מק״ט."""
    makt_str = str(makt).strip()
    select_cols = _select_items_sql()
    with get_db() as conn:
        if makt_str.isdigit():
            rows = conn.execute(
                f"""
                SELECT {select_cols} FROM items
                WHERE CAST([מק"ט] AS TEXT) = ?
                   OR CAST([מק"ט] AS INTEGER) = CAST(? AS INTEGER)
                ORDER BY entity_id
                """,
                (makt_str, makt_str),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT {select_cols} FROM items
                WHERE CAST([מק"ט] AS TEXT) = ?
                ORDER BY entity_id
                """,
                (makt_str,),
            ).fetchall()
    return [_pick_columns(r, ITEM_LIST_COLUMNS) for r in rows]
