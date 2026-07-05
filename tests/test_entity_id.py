"""Tests for entity_id format and migration."""

from __future__ import annotations

from entity_id import (
    build_entity_id_from_parts,
    build_entity_id_from_row,
    legacy_entity_id_to_new,
    migrate_entity_ids,
    needs_entity_id_migration,
    normalize_part,
    parse_legacy_entity_id,
)


def test_normalize_part_strips_float_zeros() -> None:
    assert normalize_part("1.0") == "1"
    assert normalize_part("0.0") == "0"
    assert normalize_part("7") == "7"
    assert normalize_part("נכים") == "נכים"


def test_build_entity_id_from_parts() -> None:
    parts = {
        'מק"ט': "642",
        "סוג זכאי": "נכים",
        "סוג סכום": "הלוואה",
        "רמת בסיס": "7",
        "רמת חריגה": "1.0",
    }
    assert build_entity_id_from_parts(parts) == "642-נכים-הלוואה-7-1"


def test_legacy_entity_id_conversion() -> None:
    old = "642_7_1.0_0.0_נכים_הלוואה"
    assert legacy_entity_id_to_new(old) == "642-נכים-הלוואה-7-1"
    parsed = parse_legacy_entity_id(old)
    assert parsed is not None
    assert parsed['מק"ט'] == "642"


def test_build_entity_id_from_row() -> None:
    row = {
        'מק"ט': "645",
        "סוג זכאי": "נכים",
        "סוג סכום": "הלוואה",
        "רמת בסיס": "7",
        "רמת חריגה": "2.0",
    }
    assert build_entity_id_from_row(row) == "645-נכים-הלוואה-7-2"


def test_migration_on_real_db(require_db) -> None:
    import sqlite3

    from config import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    try:
        if needs_entity_id_migration(conn):
            stats = migrate_entity_ids(conn)
            assert stats["updated"] > 0
        assert not needs_entity_id_migration(conn)
        sample = conn.execute(
            "SELECT entity_id FROM items WHERE CAST([מק\"ט] AS TEXT) = '642' LIMIT 1"
        ).fetchone()
        assert sample is not None
        assert "-" in sample[0]
        assert "_" not in sample[0]
    finally:
        conn.close()
