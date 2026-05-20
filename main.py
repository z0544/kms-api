"""KMS API POC + ממשק GUI."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles

from config import CORS_ORIGINS, DB_PATH, USE_FTS, settings
from db_service import (
    MatchMode,
    get_db_dep,
    get_item_by_entity_id,
    get_items_for_makt,
    get_suppliers_for_makt,
    group_items_by_makt,
    parse_field,
    parse_match_mode,
    search_items,
)
from ai_search import run_ai_search
from excel_export import build_ai_search_export, build_makt_export, build_search_export
from fts_service import fts_status
from logging_setup import get_logger, setup_logging
from process_data import process_data

setup_logging()
logger = get_logger("kms.api")

API_VERSION = "0.8.16"

DbConn = Annotated[sqlite3.Connection, Depends(get_db_dep)]
EXPORT_LIMIT = 500
STATIC_DIR = Path(__file__).resolve().parent / "static"

TAGS_METADATA = [
    {"name": "ui", "description": "ממשק GUI סטטי"},
    {"name": "system", "description": "בריאות ומידע מערכת"},
    {"name": "items", "description": "חיפוש פריטים ושליפת פרטי וריאנט"},
    {"name": "suppliers", "description": "ספקים מורשים לפי מק״ט"},
    {"name": "ai", "description": "חיפוש חכם מקומי בשפה חופשית"},
    {"name": "export", "description": "ייצוא תוצאות לקבצי Excel (XLSX)"},
    {"name": "legacy", "description": "Endpoints ישנים לתאימות לאחור"},
    {"name": "admin", "description": "פעולות ניהול (דורש אסימון)"},
]

app = FastAPI(
    title="KMS API",
    description=(
        "API וממשק לשליפת מקטים, וריאנטים וספקים מורשים.\n\n"
        "כולל חיפוש חכם מקומי בעברית (ללא LLM), ייצוא Excel ודירוג קרבה גיאוגרפית."
    ),
    version=API_VERSION,
    openapi_tags=TAGS_METADATA,
    contact={"name": "KMS Team"},
)

# CORS: ברירת מחדל "*" שומרת על תאימות לאחור (כפי שהתנהג עד היום ללא middleware).
# שים לב: כש-origin הוא "*" אסור לאפשר credentials=True.
_allow_all = CORS_ORIGINS == ["*"] or "*" in CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=not _allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        status = response.status_code if response is not None else 500
        # לוג רק לבקשות API (לא static), כדי לא להציף
        path = request.url.path
        if not path.startswith("/static/"):
            log_fn = logger.info if status < 400 else logger.warning
            log_fn(
                "%s %s -> %s (%.1fms)",
                request.method,
                path,
                status,
                elapsed_ms,
            )


@app.exception_handler(sqlite3.Error)
async def _sqlite_error_handler(request: Request, exc: sqlite3.Error) -> JSONResponse:
    logger.error("SQLite error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=503,
        content={"detail": "שגיאה בגישה לבסיס הנתונים"},
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # נופל לכאן רק כשאף handler/HTTPException לא תפס.
    logger.exception(
        "Unhandled exception on %s %s: %s",
        request.method, request.url.path, exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "שגיאה פנימית בשרת"},
    )


def _ensure_db() -> None:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="בסיס הנתונים לא קיים. הרץ: python process_data.py",
        )


@app.get("/", tags=["ui"], include_in_schema=False)
def gui_home() -> FileResponse:
    index = STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="ממשק GUI לא נמצא")
    return FileResponse(index)


@app.get(
    "/health",
    tags=["system"],
    summary="בריאות שרת",
    description="מחזיר סטטוס, גרסה וקיום של בסיס הנתונים. שימושי ל-load balancer.",
)
def health(conn: DbConn) -> dict[str, Any]:
    fts_info: dict[str, Any] = {"enabled": USE_FTS}
    if DB_PATH.exists():
        try:
            fts_info.update(fts_status(conn))
        except sqlite3.Error as exc:
            fts_info["error"] = str(exc)
    return {
        "status": "ok",
        "version": API_VERSION,
        "database": str(DB_PATH),
        "database_exists": bool(DB_PATH.exists()),
        "smart_search": "local",
        "fts": fts_info,
    }


class AiSearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="שאילתה חופשית בעברית. ניתן לכלול תיאור מוצר ו/או מיקום.",
        examples=["כיסא גלגלים, גר בבאר שבע", "עדשות מולטיפוקל בחיפה"],
    )


@app.get(
    "/api/ai/status",
    tags=["ai"],
    summary="סטטוס מנוע חיפוש חכם",
)
def api_ai_status() -> dict[str, Any]:
    return {
        "engine": "local",
        "cost": "free",
        "hint": "חיפוש חכם מקומי בעברית — ללא OpenAI וללא עלות",
    }


@app.post(
    "/api/ai/search",
    tags=["ai"],
    summary="חיפוש חכם בשפה חופשית",
    description=(
        "מקבל שאילתה חופשית בעברית, מחלץ מילות מפתח ומיקום, "
        "ומחזיר רשימת מקטים מדורגים עם ספקים מורשים — כולל סימון ספק קרוב."
    ),
    responses={
        200: {"description": "תוצאות מדורגות + ספק קרוב לפי מיקום"},
        422: {"description": "שאילתה לא תקינה"},
        503: {"description": "בסיס הנתונים לא זמין"},
    },
)
def api_ai_search(body: AiSearchRequest) -> dict[str, Any]:
    _ensure_db()
    try:
        return run_ai_search(body.query.strip())
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        logger.error("שגיאת DB בחיפוש חכם: %s", exc, exc_info=True)
        raise HTTPException(status_code=503, detail="שגיאה בגישה לבסיס הנתונים") from exc


@app.get(
    "/api/items",
    tags=["items"],
    summary="חיפוש פריטים (עם קיבוץ אופציונלי לפי מק״ט)",
    description=(
        "חיפוש פריטים לפי שדה ומצב התאמה.\n"
        "**field** תומך ב: `all`, `מקט`, `תיאור`, `זכאי`, `ספק`, `entity_id`.\n"
        "**match** תומך ב: `contains` (ברירת מחדל), `exact`, `startswith`, `endswith`.\n"
        "כאשר `grouped=true` (ברירת מחדל) — מקבץ וריאנטים לפי מק״ט עם supplier_count."
    ),
)
def api_list_items(
    q: str = Query(
        ...,
        min_length=1,
        description="ערך לחיפוש (טקסט/מק״ט)",
        examples=["כיסא"],
    ),
    match: str = Query(
        default="contains",
        description="מצב התאמה: contains/exact/startswith/endswith (כולל aliases בעברית)",
    ),
    field: str = Query(
        default="all",
        description="שדה לחיפוש: all/מקט/תיאור/זכאי/ספק/entity_id",
    ),
    limit: int = Query(default=100, ge=1, le=500, description="מגבלת תוצאות"),
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


@app.get(
    "/api/item/{entity_id}",
    tags=["items"],
    summary="פרטי וריאנט מלאים לפי entity_id",
    responses={404: {"description": "פריט לא נמצא"}},
)
def api_get_item(entity_id: str) -> dict[str, Any]:
    _ensure_db()
    item = get_item_by_entity_id(entity_id)
    if not item:
        raise HTTPException(status_code=404, detail="פריט לא נמצא")
    return item


@app.get(
    "/api/makt/{makt}/suppliers",
    tags=["suppliers"],
    summary="ספקים מורשים למק״ט",
    description="מחזיר את כל הספקים בהסכם פעיל עבור מק״ט נתון.",
)
def api_suppliers_by_makt(makt: str) -> dict[str, Any]:
    _ensure_db()
    suppliers = get_suppliers_for_makt(makt)
    return {"מקט": makt, "count": len(suppliers), "suppliers": suppliers}


def _xlsx_response(content: bytes, filename: str) -> Response:
    safe_name = quote(filename)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}",
        },
    )


@app.get(
    "/api/export/search",
    tags=["export"],
    summary="ייצוא תוצאות חיפוש ל-Excel",
    response_class=Response,
    responses={
        200: {
            "description": "קובץ XLSX להורדה",
            "content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}},
        },
        404: {"description": "לא נמצאו תוצאות לייצוא"},
    },
)
def api_export_search(
    q: str = Query(..., min_length=1),
    match: str = Query(default="contains"),
    field: str = Query(default="all"),
    limit: int = Query(default=EXPORT_LIMIT, ge=1, le=EXPORT_LIMIT),
) -> Response:
    _ensure_db()
    try:
        mode = parse_match_mode(match)
        parse_field(field)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    items = search_items(q, mode, field, limit)
    if not items:
        raise HTTPException(status_code=404, detail="לא נמצאו תוצאות לייצוא")
    groups = group_items_by_makt(items)
    data = build_search_export(
        query=q,
        match=mode.value,
        field=field,
        groups=groups,
        items=items,
    )
    stamp = q.replace(" ", "_")[:30]
    return _xlsx_response(data, f"kms_search_{stamp}.xlsx")


@app.get(
    "/api/export/makt/{makt}",
    tags=["export"],
    summary="ייצוא מק״ט + ספקים מורשים ל-Excel",
    response_class=Response,
)
def api_export_makt(
    makt: str,
    entity_id: str | None = Query(default=None, description="וריאנט נבחר (אופציונלי)"),
) -> Response:
    _ensure_db()
    variants = get_items_for_makt(makt)
    if not variants:
        raise HTTPException(status_code=404, detail="מק״ט לא נמצא")
    suppliers = get_suppliers_for_makt(makt)
    selected: dict[str, Any] | None = None
    if entity_id:
        selected = get_item_by_entity_id(entity_id)
        if not selected:
            raise HTTPException(status_code=404, detail="וריאנט לא נמצא")
    data = build_makt_export(
        makt=makt,
        variants=variants,
        suppliers=suppliers,
        selected_entity_id=entity_id,
        selected_variant=selected,
    )
    return _xlsx_response(data, f"kms_makt_{makt}.xlsx")


@app.get(
    "/api/export/ai/search",
    tags=["export"],
    summary="ייצוא תוצאות חיפוש חכם ל-Excel",
    response_class=Response,
)
def api_export_ai_search(
    query: str = Query(..., min_length=3, max_length=500),
    limit_makts: int = Query(default=15, ge=1, le=50),
) -> Response:
    _ensure_db()
    result = run_ai_search(query.strip(), limit_makts=limit_makts)
    if not result.get("results"):
        detail = result.get("message") or "לא נמצאו תוצאות לייצוא"
        raise HTTPException(status_code=404, detail=detail)
    for row in result["results"]:
        makt = str(row.get('מק"ט', "")).strip()
        if makt:
            row["variants"] = get_items_for_makt(makt)
    data = build_ai_search_export(result)
    stamp = query.strip().replace(" ", "_")[:24]
    return _xlsx_response(data, f"kms_ai_{stamp}.xlsx")


def _verify_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    if not settings.admin_token:
        raise HTTPException(status_code=403, detail="endpoint ניהול מושבת (הגדר KMS_ADMIN_TOKEN)")
    if not x_admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="אסימון ניהול לא תקין")


@app.post(
    "/api/admin/reload-data",
    tags=["admin"],
    summary="טעינה מחדש של בסיס הנתונים מ-Excel",
    description="מריץ את process_data.py. דורש header X-Admin-Token תואם ל-KMS_ADMIN_TOKEN.",
    responses={
        200: {"description": "ETL הושלם בהצלחה"},
        401: {"description": "אסימון שגוי"},
        403: {"description": "endpoint מושבת"},
        500: {"description": "שגיאה בטעינת קבצים"},
    },
)
def api_admin_reload_data(_: None = Depends(_verify_admin_token)) -> dict[str, Any]:
    try:
        stats = process_data()
        logger.info("admin reload-data: %s", stats)
        return {
            "status": "ok",
            "database": str(DB_PATH),
            "rows": stats,
            "fts_enabled": USE_FTS,
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("admin reload-data failed: %s", exc)
        raise HTTPException(status_code=500, detail="שגיאה בטעינת הנתונים") from exc


# תאימות לאחור
@app.get(
    "/items",
    tags=["legacy"],
    summary="(legacy) חיפוש פריטים - השתמש ב-/api/items",
    deprecated=True,
)
def list_items_legacy(
    q: str = Query(..., min_length=1),
    match: str = Query(default="contains"),
    field: str = Query(default="all"),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    return api_list_items(q=q, match=match, field=field, limit=limit)


@app.get(
    "/item/{entity_id}",
    tags=["legacy"],
    summary="(legacy) פרטי פריט - השתמש ב-/api/item/{entity_id}",
    deprecated=True,
)
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
