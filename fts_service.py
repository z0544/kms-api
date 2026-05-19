"""שירות חיפוש FTS5 — אופציונלי, עם fallback ל-LIKE."""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from logging_setup import get_logger

logger = get_logger("kms.fts")

FTS_TABLE = "items_fts"
_FTS_SUPPORTED: bool | None = None
_FTS_BUILT = False


def fts5_supported(conn: sqlite3.Connection) -> bool:
    global _FTS_SUPPORTED
    if _FTS_SUPPORTED is not None:
        return _FTS_SUPPORTED
    try:
        opts = [r[0] for r in conn.execute("PRAGMA compile_options")]
        _FTS_SUPPORTED = any("FTS5" in o for o in opts)
    except sqlite3.Error:
        _FTS_SUPPORTED = False
    return _FTS_SUPPORTED


def _fts_table_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (FTS_TABLE,),
    ).fetchone()
    return row is not None


def ensure_fts_index(conn: sqlite3.Connection) -> bool:
    """בונה טבלת FTS5 אם חסרה. מחזיר True אם זמינה לחיפוש."""
    global _FTS_BUILT
    if not fts5_supported(conn):
        return False
    if _FTS_BUILT and _fts_table_exists(conn):
        return True

    try:
        conn.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE}
            USING fts5(desc, tokenize='unicode61 remove_diacritics 2')
            """
        )
        conn.execute(
            f"""
            INSERT INTO {FTS_TABLE}(rowid, desc)
            SELECT rowid, COALESCE([תיאור פריט], '')
            FROM items
            WHERE rowid NOT IN (SELECT rowid FROM {FTS_TABLE})
            """
        )
        conn.commit()
        _FTS_BUILT = True
        cnt = conn.execute(f"SELECT COUNT(*) FROM {FTS_TABLE}").fetchone()[0]
        logger.info("FTS5 index ready (%d rows)", cnt)
        return True
    except sqlite3.Error as exc:
        logger.warning("FTS5 build failed: %s", exc)
        return False


def rebuild_fts_index(conn: sqlite3.Connection) -> int:
    """מחדש אינדקס אחרי ETL. מחזיר מספר שורות."""
    global _FTS_BUILT
    _FTS_BUILT = False
    if not fts5_supported(conn):
        return 0
    try:
        conn.execute(f"DROP TABLE IF EXISTS {FTS_TABLE}")
        conn.commit()
    except sqlite3.Error as exc:
        logger.warning("FTS drop failed: %s", exc)
    if not ensure_fts_index(conn):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {FTS_TABLE}").fetchone()[0])


def _token_expr(token: str) -> str:
    cleaned = re.sub(r"[^\wא-ת]", " ", token, flags=re.UNICODE).strip()
    if len(cleaned) < 2:
        return ""
    return f'"{cleaned}"*'


def build_match_expression(terms: list[str], phrase: str) -> str:
    parts: list[str] = []
    if phrase and len(phrase) >= 3:
        p = re.sub(r"[^\wא-ת\s]", " ", phrase, flags=re.UNICODE).strip()
        if len(p) >= 3:
            parts.append(f'"{p}"')
    for t in terms:
        expr = _token_expr(t)
        if expr and expr not in parts:
            parts.append(expr)
    return " OR ".join(parts)


def search_rowids_by_fts(
    conn: sqlite3.Connection,
    terms: list[str],
    phrase: str,
    limit: int,
) -> list[int] | None:
    """rowids ממוינים לפי bm25. None = fallback ל-LIKE."""
    if not ensure_fts_index(conn):
        return None
    match_expr = build_match_expression(terms, phrase)
    if not match_expr:
        return []
    try:
        rows = conn.execute(
            f"""
            SELECT rowid FROM {FTS_TABLE}
            WHERE {FTS_TABLE} MATCH ?
            ORDER BY bm25({FTS_TABLE})
            LIMIT ?
            """,
            (match_expr, limit),
        ).fetchall()
        return [int(r[0]) for r in rows]
    except sqlite3.Error as exc:
        logger.warning("FTS search failed (%r): %s", match_expr, exc)
        return None


def fts_status(conn: sqlite3.Connection) -> dict[str, Any]:
    """סטטוס בלבד — לא בונה אינדקס."""
    supported = fts5_supported(conn)
    exists = supported and _fts_table_exists(conn)
    row_count = 0
    if exists:
        try:
            row_count = int(conn.execute(f"SELECT COUNT(*) FROM {FTS_TABLE}").fetchone()[0])
        except sqlite3.Error:
            exists = False
    return {"supported": supported, "table_built": exists, "row_count": row_count}
