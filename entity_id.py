"""בניית ומיגרציה של entity_id.

פורמט: מק\"ט-סוג זכאי-סוג סכום-רמת בסיס-רמת חריגה (מפריד `-`).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Mapping

import pandas as pd

from config import ENTITY_ID_PARTS

ENTITY_ID_SEPARATOR = "-"

LEGACY_ENTITY_ID_PARTS = [
    'מק"ט',
    "רמת בסיס",
    "רמת חריגה",
    "אחוז לחריגה",
    "סוג זכאי",
    "סוג סכום",
]


def normalize_part(value: Any) -> str:
    if value is None:
        return "0"
    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "<na>"):
        return "0"
    try:
        f = float(s)
        if f == int(f):
            return str(int(f))
    except ValueError:
        pass
    return s


def build_entity_id_from_parts(parts: Mapping[str, Any]) -> str:
    return ENTITY_ID_SEPARATOR.join(
        normalize_part(parts.get(col)) for col in ENTITY_ID_PARTS
    )


def build_entity_id_from_row(row: Mapping[str, Any]) -> str:
    return build_entity_id_from_parts(row)


def build_entity_id_series(df: pd.DataFrame) -> pd.Series:
    series = df[ENTITY_ID_PARTS[0]].map(normalize_part)
    for col in ENTITY_ID_PARTS[1:]:
        series = series + ENTITY_ID_SEPARATOR + df[col].map(normalize_part)
    return series


def parse_legacy_entity_id(entity_id: str) -> dict[str, str] | None:
    parts = entity_id.split("_")
    if len(parts) != len(LEGACY_ENTITY_ID_PARTS):
        return None
    return dict(zip(LEGACY_ENTITY_ID_PARTS, parts, strict=True))


def legacy_entity_id_to_new(entity_id: str) -> str | None:
    parsed = parse_legacy_entity_id(entity_id)
    if parsed is None:
        return None
    return build_entity_id_from_parts(parsed)


def needs_entity_id_migration(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM items WHERE instr(entity_id, '_') > 0 LIMIT 1"
    ).fetchone()
    return row is not None


def migrate_entity_ids(conn: sqlite3.Connection) -> dict[str, int]:
    """מעדכן entity_id ישנים (מפריד `_`) לפורמט החדש."""
    if not needs_entity_id_migration(conn):
        return {"updated": 0, "total": 0}

    cursor = conn.execute(
        f'SELECT entity_id, {", ".join(f"[{c}]" for c in ENTITY_ID_PARTS)} FROM items'
    )
    col_names = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    total = len(rows)
    updated = 0

    for row in rows:
        row_dict = dict(zip(col_names, row, strict=True))
        old_id = row_dict["entity_id"]
        new_id = build_entity_id_from_row(row_dict)
        if old_id == new_id:
            continue
        conn.execute(
            "UPDATE items SET entity_id = ? WHERE entity_id = ?",
            (new_id, old_id),
        )
        updated += 1

    conn.commit()
    return {"updated": updated, "total": total}
