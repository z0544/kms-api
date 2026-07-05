"""סכמת DB — מיגרציות וטבלאות היסטוריה."""

from __future__ import annotations

import sqlite3

ITEMS_META_COLUMNS = frozenset({"is_deleted", "created_at", "updated_at"})


def _items_columns(conn: sqlite3.Connection) -> set[str]:
    return {row[1] for row in conn.execute("PRAGMA table_info(items)")}


def ensure_schema(conn: sqlite3.Connection) -> None:
    """מוסיף עמודות מטא-דאטה וטבלאות היסטוריה אם חסרות."""
    if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='items'"
    ).fetchone():
        cols = _items_columns(conn)
        if "is_deleted" not in cols:
            conn.execute(
                "ALTER TABLE items ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"
            )
        if "created_at" not in cols:
            conn.execute("ALTER TABLE items ADD COLUMN created_at TEXT")
        if "updated_at" not in cols:
            conn.execute("ALTER TABLE items ADD COLUMN updated_at TEXT")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            added_count INTEGER NOT NULL DEFAULT 0,
            updated_count INTEGER NOT NULL DEFAULT 0,
            deleted_count INTEGER NOT NULL DEFAULT 0,
            unchanged_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS item_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_id TEXT NOT NULL,
            sync_run_id INTEGER,
            action TEXT NOT NULL,
            field_name TEXT,
            old_value TEXT,
            new_value TEXT,
            changed_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (sync_run_id) REFERENCES sync_runs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_item_history_entity
            ON item_history(entity_id);
        CREATE INDEX IF NOT EXISTS idx_item_history_sync_run
            ON item_history(sync_run_id);
        """
    )
    conn.commit()


def get_data_columns(conn: sqlite3.Connection) -> list[str]:
    """עמודות נתונים ב-items (ללא מטא-דאטה)."""
    return [
        c
        for c in (row[1] for row in conn.execute("PRAGMA table_info(items)"))
        if c not in ITEMS_META_COLUMNS
    ]
