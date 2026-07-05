"""סנכרון פריטים מ-CSV — זיהוי חדש / עודכן / נמחק + היסטוריה."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from config import UNIQUE_ID_COLUMNS
from csv_loader import read_kms_csv_with_fallback
from db_schema import ITEMS_META_COLUMNS, ensure_schema, get_data_columns
from entity_id import build_entity_id_series, normalize_part
from process_data import prepare_items_dataframe

COMPARE_SKIP = frozenset({"entity_id", *ITEMS_META_COLUMNS})


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _normalize_compare(value: Any) -> str:
    if value is None:
        return ""
    return normalize_part(value)


def _field_diff(
    old: dict[str, Any],
    new: dict[str, Any],
    columns: list[str],
) -> list[dict[str, str | None]]:
    changes: list[dict[str, str | None]] = []
    for col in columns:
        if col in COMPARE_SKIP:
            continue
        old_v = _normalize_compare(old.get(col))
        new_v = _normalize_compare(new.get(col))
        if old_v != new_v:
            changes.append(
                {
                    "field": col,
                    "old": None if old_v == "" else old_v,
                    "new": None if new_v == "" else new_v,
                }
            )
    return changes


@dataclass
class SyncPlan:
    filename: str
    new_items: list[dict[str, Any]] = field(default_factory=list)
    updated_items: list[dict[str, Any]] = field(default_factory=list)
    deleted_items: list[dict[str, Any]] = field(default_factory=list)
    unchanged_count: int = 0

    @property
    def summary(self) -> dict[str, int]:
        return {
            "new": len(self.new_items),
            "updated": len(self.updated_items),
            "deleted": len(self.deleted_items),
            "unchanged": self.unchanged_count,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "summary": self.summary,
            "new": self.new_items,
            "updated": self.updated_items,
            "deleted": self.deleted_items,
            "unchanged_count": self.unchanged_count,
        }


def _load_existing_items(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM items").fetchall()
    return {_row_to_dict(r)["entity_id"]: _row_to_dict(r) for r in rows}


def _dataframe_to_records(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        rec = {k: (None if pd.isna(v) else v) for k, v in row.items()}
        eid = str(rec["entity_id"])
        records[eid] = rec
    return records


def _prepare_csv_records(content: bytes, filename: str) -> dict[str, dict[str, Any]]:
    raw = read_kms_csv_with_fallback(content)
    missing = [c for c in UNIQUE_ID_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError(f"עמודות חסרות ב-CSV: {', '.join(missing)}")
    df = prepare_items_dataframe(raw)
    return _dataframe_to_records(df)


def compute_sync_plan(content: bytes, filename: str = "upload.csv") -> SyncPlan:
    new_records = _prepare_csv_records(content, filename)

    from config import DB_PATH

    if not DB_PATH.exists():
        plan = SyncPlan(filename=filename)
        for rec in new_records.values():
            plan.new_items.append(_public_item(rec))
        return plan

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='items'"
        ).fetchone():
            plan = SyncPlan(filename=filename)
            for rec in new_records.values():
                plan.new_items.append(_public_item(rec))
            return plan
        existing = _load_existing_items(conn)
        data_cols = get_data_columns(conn)
    finally:
        conn.close()

    plan = SyncPlan(filename=filename)
    seen_new: set[str] = set()

    for eid, new_rec in new_records.items():
        seen_new.add(eid)
        old_rec = existing.get(eid)
        if old_rec is None:
            plan.new_items.append(_public_item(new_rec))
            continue

        was_deleted = bool(old_rec.get("is_deleted"))
        changes = _field_diff(old_rec, new_rec, data_cols)
        if was_deleted or changes:
            entry: dict[str, Any] = {
                "entity_id": eid,
                'מק"ט': new_rec.get('מק"ט'),
                "תיאור פריט": new_rec.get("תיאור פריט"),
                "changes": changes,
            }
            if was_deleted:
                entry["restored"] = True
            plan.updated_items.append(entry)
        else:
            plan.unchanged_count += 1

    for eid, old_rec in existing.items():
        if eid in seen_new:
            continue
        if old_rec.get("is_deleted"):
            continue
        plan.deleted_items.append(
            {
                "entity_id": eid,
                'מק"ט': old_rec.get('מק"ט'),
                "תיאור פריט": old_rec.get("תיאור פריט"),
            }
        )

    return plan


def _public_item(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_id": rec.get("entity_id"),
        'מק"ט': rec.get('מק"ט'),
        "תיאור פריט": rec.get("תיאור פריט"),
        "סוג זכאי": rec.get("סוג זכאי"),
        "סוג סכום": rec.get("סוג סכום"),
        "רמת בסיס": rec.get("רמת בסיס"),
        "רמת חריגה": rec.get("רמת חריגה"),
        "סכום": rec.get("סכום"),
    }


def _ensure_item_columns(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(items)")}
    for col in record:
        if col in ITEMS_META_COLUMNS or col in existing:
            continue
        conn.execute(f'ALTER TABLE items ADD COLUMN [{col}] TEXT')


def _insert_history(
    conn: sqlite3.Connection,
    *,
    entity_id: str,
    sync_run_id: int,
    action: str,
    field_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO item_history
            (entity_id, sync_run_id, action, field_name, old_value, new_value, changed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_id, sync_run_id, action, field_name, old_value, new_value, _utc_now()),
    )


def apply_sync_plan(content: bytes, filename: str = "upload.csv") -> dict[str, Any]:
    from config import DB_PATH, USE_FTS

    new_records = _prepare_csv_records(content, filename)
    plan = compute_sync_plan(content, filename)
    now = _utc_now()
    sync_run_id: int | None = None

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)

        cur = conn.execute(
            """
            INSERT INTO sync_runs (filename, started_at, status)
            VALUES (?, ?, 'running')
            """,
            (filename, now),
        )
        sync_run_id = cur.lastrowid

        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='items'"
        ).fetchone()

        if not table_exists:
            df = pd.DataFrame(list(new_records.values()))
            df["is_deleted"] = 0
            df["created_at"] = now
            df["updated_at"] = now
            df.to_sql("items", conn, if_exists="replace", index=False)
            added = len(new_records)
            for eid in new_records:
                _insert_history(
                    conn, entity_id=eid, sync_run_id=sync_run_id, action="created"
                )
            conn.execute(
                """
                UPDATE sync_runs SET
                    finished_at = ?, status = 'completed',
                    added_count = ?, updated_count = 0,
                    deleted_count = 0, unchanged_count = 0
                WHERE id = ?
                """,
                (now, added, sync_run_id),
            )
            conn.commit()
            return {
                "status": "ok",
                "sync_run_id": sync_run_id,
                "summary": {"new": added, "updated": 0, "deleted": 0, "unchanged": 0},
                "plan": plan.summary,
            }

        existing = _load_existing_items(conn)
        data_cols = get_data_columns(conn)

        added = updated = deleted = unchanged = 0

        for eid, new_rec in new_records.items():
            old_rec = existing.get(eid)
            if old_rec is None:
                _ensure_item_columns(conn, new_rec)
                cols = [c for c in new_rec if c not in ITEMS_META_COLUMNS]
                col_names = ", ".join(f"[{c}]" for c in cols)
                placeholders = ", ".join("?" * len(cols))
                values = [new_rec[c] for c in cols]
                conn.execute(
                    f"INSERT INTO items ({col_names}, is_deleted, created_at, updated_at) "
                    f"VALUES ({placeholders}, 0, ?, ?)",
                    (*values, now, now),
                )
                _insert_history(conn, entity_id=eid, sync_run_id=sync_run_id, action="created")
                added += 1
                continue

            was_deleted = bool(old_rec.get("is_deleted"))
            changes = _field_diff(old_rec, new_rec, data_cols)

            if not was_deleted and not changes:
                unchanged += 1
                continue

            if was_deleted:
                conn.execute(
                    "UPDATE items SET is_deleted = 0, updated_at = ? WHERE entity_id = ?",
                    (now, eid),
                )
                _insert_history(
                    conn,
                    entity_id=eid,
                    sync_run_id=sync_run_id,
                    action="restored",
                    field_name="is_deleted",
                    old_value="1",
                    new_value="0",
                )

            for change in changes:
                col = change["field"]
                conn.execute(
                    f"UPDATE items SET [{col}] = ?, updated_at = ? WHERE entity_id = ?",
                    (new_rec.get(col), now, eid),
                )
                _insert_history(
                    conn,
                    entity_id=eid,
                    sync_run_id=sync_run_id,
                    action="updated",
                    field_name=col,
                    old_value=change["old"],
                    new_value=change["new"],
                )
            updated += 1

        for eid, old_rec in existing.items():
            if eid in new_records or old_rec.get("is_deleted"):
                continue
            conn.execute(
                "UPDATE items SET is_deleted = 1, updated_at = ? WHERE entity_id = ?",
                (now, eid),
            )
            _insert_history(
                conn,
                entity_id=eid,
                sync_run_id=sync_run_id,
                action="deleted",
                field_name="is_deleted",
                old_value="0",
                new_value="1",
            )
            deleted += 1

        conn.execute(
            """
            UPDATE sync_runs SET
                finished_at = ?,
                status = 'completed',
                added_count = ?,
                updated_count = ?,
                deleted_count = ?,
                unchanged_count = ?
            WHERE id = ?
            """,
            (now, added, updated, deleted, unchanged, sync_run_id),
        )
        conn.commit()

        if USE_FTS:
            from fts_service import rebuild_fts_index

            rebuild_fts_index(conn)

        return {
            "status": "ok",
            "sync_run_id": sync_run_id,
            "summary": {
                "new": added,
                "updated": updated,
                "deleted": deleted,
                "unchanged": unchanged,
            },
            "plan": plan.summary,
        }
    except Exception as exc:
        conn.rollback()
        if sync_run_id is not None:
            conn.execute(
                """
                UPDATE sync_runs SET status = 'failed', error_message = ?, finished_at = ?
                WHERE id = ?
                """,
                (str(exc), _utc_now(), sync_run_id),
            )
            conn.commit()
        raise
    finally:
        conn.close()


def list_sync_runs(limit: int = 50) -> list[dict[str, Any]]:
    from config import DB_PATH

    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT id, filename, started_at, finished_at, status,
                   added_count, updated_count, deleted_count, unchanged_count, error_message
            FROM sync_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_item_history(entity_id: str, limit: int = 100) -> list[dict[str, Any]]:
    from config import DB_PATH

    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT h.id, h.entity_id, h.sync_run_id, h.action, h.field_name,
                   h.old_value, h.new_value, h.changed_at,
                   s.filename AS sync_filename
            FROM item_history h
            LEFT JOIN sync_runs s ON s.id = h.sync_run_id
            WHERE h.entity_id = ?
            ORDER BY h.id DESC
            LIMIT ?
            """,
            (entity_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_history_counts(entity_ids: list[str]) -> dict[str, int]:
    """מספר רשומות היסטוריה לכל entity_id."""
    from config import DB_PATH

    unique = list({eid for eid in entity_ids if eid})
    if not unique or not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
        placeholders = ", ".join("?" * len(unique))
        rows = conn.execute(
            f"""
            SELECT entity_id, COUNT(*) AS cnt
            FROM item_history
            WHERE entity_id IN ({placeholders})
            GROUP BY entity_id
            """,
            unique,
        ).fetchall()
        return {str(r[0]): int(r[1]) for r in rows}
    finally:
        conn.close()


def enrich_items_with_history_counts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = get_history_counts(
        [str(i["entity_id"]) for i in items if i.get("entity_id")]
    )
    for item in items:
        eid = str(item.get("entity_id", ""))
        item["history_count"] = counts.get(eid, 0)
    return items
