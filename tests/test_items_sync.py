"""Tests for CSV sync — new / updated / deleted + history."""

from __future__ import annotations

import io
import sqlite3

import pandas as pd
import pytest

from config import UNIQUE_ID_COLUMNS
from db_schema import ensure_schema
from entity_id import build_entity_id_from_parts
from items_sync import apply_sync_plan, compute_sync_plan, get_item_history, list_sync_runs


def _make_csv(rows: list[dict]) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    return buf.getvalue().encode("utf-8-sig")


def _seed_db(db_path, rows: list[dict]) -> None:
    for r in rows:
        r.setdefault("is_deleted", 0)
        r.setdefault("created_at", "2026-01-01 00:00:00")
        r.setdefault("updated_at", "2026-01-01 00:00:00")
    df = pd.DataFrame(rows)
    conn = sqlite3.connect(db_path)
    ensure_schema(conn)
    df.to_sql("items", conn, if_exists="replace", index=False)
    conn.close()


@pytest.fixture
def sync_env(tmp_path, monkeypatch):
    db_path = tmp_path / "sync_test.db"
    monkeypatch.setattr("config.settings.db_path", db_path)
    monkeypatch.setattr("config.DB_PATH", db_path)
    monkeypatch.setattr("items_sync.DB_PATH", db_path, raising=False)
    import items_sync as mod

    monkeypatch.setattr(mod, "DB_PATH", db_path, raising=False)
    return db_path


def _base_row(**overrides) -> dict:
    row = {
        'מק"ט': "100",
        "תיאור פריט": "פריט בדיקה",
        "סוג זכאי": "נכים",
        "סוג סכום": "הלוואה",
        "רמת בסיס": "1",
        "רמת חריגה": "0",
        "אחוז לחריגה": "0",
        "סכום": "1000",
    }
    row.update(overrides)
    row["entity_id"] = build_entity_id_from_parts(row)
    return row


def test_sync_detects_new_updated_deleted(sync_env) -> None:
    existing = _base_row()
    updated = _base_row(סכום="2000")
    removed = _base_row(
        **{
            'מק"ט': "200",
            "תיאור פריט": "יוסר",
            "רמת בסיס": "2",
        }
    )
    _seed_db(sync_env, [existing, removed])

    csv_rows = [
        {k: updated[k] for k in UNIQUE_ID_COLUMNS + ["תיאור פריט", "סכום"]},
        {
            'מק"ט': "300",
            "תיאור פריט": "חדש",
            "סוג זכאי": "נכים",
            "סוג סכום": "הלוואה",
            "רמת בסיס": "1",
            "רמת חריגה": "0",
            "אחוז לחריגה": "0",
            "סכום": "500",
        },
    ]
    content = _make_csv(csv_rows)
    plan = compute_sync_plan(content, "test.csv")

    assert plan.summary["new"] == 1
    assert plan.summary["updated"] == 1
    assert plan.summary["deleted"] == 1
    assert plan.summary["unchanged"] == 0


def test_sync_apply_and_history(sync_env) -> None:
    row = _base_row()
    _seed_db(sync_env, [row])

    csv_rows = [{k: row[k] for k in UNIQUE_ID_COLUMNS + ["תיאור פריט", "סכום"]}]
    csv_rows[0]["סכום"] = "9999"
    content = _make_csv(csv_rows)

    result = apply_sync_plan(content, "apply.csv")
    assert result["summary"]["updated"] == 1

    conn = sqlite3.connect(sync_env)
    val = conn.execute("SELECT [סכום] FROM items WHERE entity_id = ?", (row["entity_id"],)).fetchone()
    conn.close()
    assert str(val[0]) == "9999"

    history = get_item_history(row["entity_id"])
    assert any(h["action"] == "updated" and h["field_name"] == "סכום" for h in history)

    runs = list_sync_runs()
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"


def test_sync_soft_delete(sync_env) -> None:
    row = _base_row()
    _seed_db(sync_env, [row])

    empty_other = _base_row(**{'מק"ט': "999", "רמת בסיס": "9"})
    content = _make_csv(
        [{k: empty_other[k] for k in UNIQUE_ID_COLUMNS + ["תיאור פריט", "סכום"]}]
    )
    apply_sync_plan(content, "del.csv")

    conn = sqlite3.connect(sync_env)
    deleted = conn.execute(
        "SELECT is_deleted FROM items WHERE entity_id = ?", (row["entity_id"],)
    ).fetchone()
    conn.close()
    assert deleted[0] == 1

    history = get_item_history(row["entity_id"])
    assert any(h["action"] == "deleted" for h in history)
