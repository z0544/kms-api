from __future__ import annotations

from db_service import (
    deduplicate_suppliers,
    get_supplier_counts_for_makts,
    get_suppliers_for_makt,
)


def test_deduplicate_suppliers_by_id() -> None:
    rows = [
        {"מספר ספק": "1", "שם ספק": "א", "יישוב קליניקה": "חיפה", "האם בתוקף": "לא"},
        {"מספר ספק": "1", "שם ספק": "א", "יישוב קליניקה": "חיפה", "האם בתוקף": "כן", "מחיר הסכם": "100"},
    ]
    out = deduplicate_suppliers(rows)
    assert len(out) == 1
    assert out[0]["האם בתוקף"] == "כן"


def test_get_suppliers_for_makt_no_duplicate_ids() -> None:
    suppliers = get_suppliers_for_makt("26449")
    ids = [str(s.get("מספר ספק", "")).strip() for s in suppliers if s.get("מספר ספק")]
    assert len(ids) == len(set(ids))


def test_supplier_count_matches_listed_suppliers() -> None:
    """ספירה בטבלת תוצאות = מספר ספקים שמוחזרים בפועל (JOIN ל-suppliers)."""
    makt = "52995"
    counts = get_supplier_counts_for_makts([makt])
    listed = get_suppliers_for_makt(makt)
    assert counts.get(makt) == len(listed)
