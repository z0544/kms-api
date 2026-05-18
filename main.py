"""KMS API POC + ממשק GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import DB_PATH
from db_service import (
    MatchMode,
    get_item_by_entity_id,
    get_suppliers_for_makt,
    group_items_by_makt,
    parse_field,
    parse_match_mode,
    search_items,
)

API_VERSION = "0.4.4"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="KMS API POC",
    description="API וממשק לשליפת מקטים וספקים מורשים",
    version=API_VERSION,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _ensure_db() -> None:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="בסיס הנתונים לא קיים. הרץ: python process_data.py",
        )


@app.get("/")
def gui_home() -> FileResponse:
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="ממשק GUI לא נמצא")
    return FileResponse(index)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": API_VERSION,
        "database": str(DB_PATH),
        "database_exists": bool(DB_PATH.exists()),
    }


@app.get("/api/items")
def api_list_items(
    q: str = Query(..., min_length=1),
    match: str = Query(default="contains"),
    field: str = Query(default="all"),
    limit: int = Query(default=100, ge=1, le=500),
    grouped: bool = Query(default=True, description="קיבוץ וריאנטים לפי מק\"ט"),
) -> dict[str, Any]:
    _ensure_db()
    try:
        mode = parse_match_mode(match)
        parse_field(field)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    items = search_items(q, mode, field, limit)
    if not items:
        raise HTTPException(status_code=404, detail="לא נמצאו תוצאות")
    payload: dict[str, Any] = {
        "query": q,
        "match": mode.value,
        "field": field,
        "count": len(items),
        "items": items,
    }
    if grouped:
        groups = group_items_by_makt(items)
        payload["group_count"] = len(groups)
        payload["groups"] = groups
    return payload


@app.get("/api/item/{entity_id}")
def api_get_item(entity_id: str) -> dict[str, Any]:
    _ensure_db()
    item = get_item_by_entity_id(entity_id)
    if not item:
        raise HTTPException(status_code=404, detail="פריט לא נמצא")
    return item


@app.get("/api/makt/{makt}/suppliers")
def api_suppliers_by_makt(makt: str) -> dict[str, Any]:
    _ensure_db()
    suppliers = get_suppliers_for_makt(makt)
    return {"מקט": makt, "count": len(suppliers), "suppliers": suppliers}


# תאימות לאחור
@app.get("/items")
def list_items_legacy(
    q: str = Query(..., min_length=1),
    match: str = Query(default="contains"),
    field: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    return api_list_items(q=q, match=match, field=field, limit=limit)


@app.get("/item/{entity_id}")
def get_item_legacy(
    entity_id: str,
    match: str = Query(default="exact"),
    field: str = Query(default="entity_id"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ensure_db()
    if match == "exact" and field == "entity_id":
        item = get_item_by_entity_id(entity_id)
        if item:
            return item
    try:
        mode = parse_match_mode(match)
        parse_field(field)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    items = search_items(entity_id, mode, field, limit)
    if not items:
        raise HTTPException(status_code=404, detail="Item not found")
    if len(items) == 1:
        full = get_item_by_entity_id(items[0]["entity_id"])
        return full or items[0]
    return {
        "match": mode.value,
        "field": field,
        "query": entity_id,
        "count": len(items),
        "items": items,
    }
