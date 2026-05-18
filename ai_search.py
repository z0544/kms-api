"""חיפוש חכם בשפה טבעית — מקטים + ספקים לפי קרבה."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from db_service import (
    ITEM_LIST_COLUMNS,
    _pick_columns,
    _select_items_sql,
    enrich_groups_with_supplier_counts,
    get_db,
    get_suppliers_for_makt,
    group_items_by_makt,
)
from geo_service import normalize_city, rank_suppliers

TERM_SYNONYMS: dict[str, list[str]] = {
    "טייטול": ["טייטול", "טיטול", "חיתול", "כוסית", "שימום"],
    "טיטול": ["טייטול", "חיתול", "כוסית"],
    "חיתול": ["חיתול", "חיתולים", "טייטול", "האגיס", "פמפרס", "כוסית"],
    "חיתולים": ["חיתול", "חיתולים", "טייטול", "כוסית"],
    "כוסית": ["כוסית", "חיתול", "טייטול"],
    "מבוגר": ["מבוגר", "מבוגרים"],
    "מבוגרים": ["מבוגר", "מבוגרים"],
    "תינוק": ["תינוק", "תינוקות", "ינק"],
    "עדשות": ["עדשות", "מולטיפוקל", "מגע"],
    "משקפיים": ["משקפיים", "משקפי"],
}

STOPWORDS = frozenset(
    """
    אני אתה את אתם אנחנו הוא היא הם הן של על עם ב בב בבית גר גרה גרים
    מחפש מחפשת רוצה צריך צריכה למצוא תן תני שיש איפה הכי קרוב אליי לי
    עבור כדי שאני אשמח בבקשה גם כן לא כל מאוד יותר מאוד ואני שזה זה
    """.split()
)

_HE_PREFIXES = ("ול", "ל", "ב", "מ", "ה", "ו", "כ", "ש")

LOCATION_PATTERNS = [
    re.compile(r"גר(?:ים|ה)?\s+ב[\-–]?\s*([א-ת\"'\s\-]{2,30})"),
    re.compile(r"מתגורר(?:ת)?\s+ב[\-–]?\s*([א-ת\"'\s\-]{2,30})"),
    re.compile(r"מגורים\s+ב[\-–]?\s*([א-ת\"'\s\-]{2,30})"),
    re.compile(r"באזור\s+([א-ת\"'\s\-]{2,30})"),
    re.compile(r"\bב([א-ת]{2,20}(?:\s+[א-ת]{2,15})?)\s*$"),
]


@dataclass
class ParsedQuery:
    product_terms: list[str] = field(default_factory=list)
    location: str | None = None
    location_normalized: str | None = None
    explanation: str = ""
    parser: str = "heuristic"


def _expand_terms(terms: list[str]) -> list[str]:
    expanded: list[str] = []
    seen: set[str] = set()
    for t in terms:
        t = t.strip()
        if len(t) < 2:
            continue
        keys = [t, t.lower()]
        for key in keys:
            for word in TERM_SYNONYMS.get(key, [t]):
                w = word.strip()
                if w and w not in seen:
                    seen.add(w)
                    expanded.append(w)
    return expanded[:12]


def _extract_location_heuristic(text: str) -> str | None:
    for pat in LOCATION_PATTERNS:
        m = pat.search(text)
        if m:
            loc = m.group(1).strip(" .,;\"'")
            loc = re.split(r"\s+(?:ו|ש|עם|ל)\s+", loc)[0].strip()
            if len(loc) >= 2:
                return loc
    return None


def _strip_hebrew_prefix(word: str) -> str:
    w = word.strip()
    for _ in range(2):
        for p in _HE_PREFIXES:
            if w.startswith(p) and len(w) > len(p) + 1:
                w = w[len(p) :]
                break
        else:
            break
    return w


def _extract_terms_heuristic(text: str) -> list[str]:
    cleaned = text
    for pat in LOCATION_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    cleaned = re.sub(r"[^\w\s\"'-]+", " ", cleaned, flags=re.UNICODE)
    words = re.findall(r"[א-ת]{2,}|\d+", cleaned)
    terms: list[str] = []
    for w in words:
        if w in STOPWORDS:
            continue
        root = _strip_hebrew_prefix(w)
        if root and root not in STOPWORDS and len(root) >= 2:
            terms.append(root)
    if not terms:
        terms = [
            _strip_hebrew_prefix(w)
            for w in re.findall(r"[א-ת]{2,}", text)
            if _strip_hebrew_prefix(w) not in STOPWORDS
        ][:5]
    return _expand_terms(terms)


def parse_query_heuristic(query: str) -> ParsedQuery:
    text = query.strip()
    location = _extract_location_heuristic(text)
    terms = _extract_terms_heuristic(text)
    loc_norm = normalize_city(location) if location else None
    expl = "חיפוש לפי מילות מפתח"
    if terms:
        expl += f": {', '.join(terms[:5])}"
    if loc_norm:
        expl += f" · מיקום: {loc_norm}"
    return ParsedQuery(
        product_terms=terms,
        location=location,
        location_normalized=loc_norm,
        explanation=expl,
        parser="heuristic",
    )


def parse_query_openai(query: str) -> ParsedQuery | None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import httpx
    except ImportError:
        return None

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    system = (
        "אתה מנתח שאילתות חיפוש בעברית למערכת מקטים רפואיים וספקים. "
        "החזר JSON בלבד עם המפתחות: product_terms (מערך מילים לחיפוש בתיאור מוצר), "
        "location (יישוב מגורים של המשתמש או null), explanation (משפט קצר בעברית)."
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": query},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }
    try:
        with httpx.Client(timeout=30.0) as client:
            res = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
    except Exception:
        return None

    terms = [str(t).strip() for t in data.get("product_terms", []) if str(t).strip()]
    location = data.get("location")
    loc_str = str(location).strip() if location else None
    loc_norm = normalize_city(loc_str) if loc_str else None
    return ParsedQuery(
        product_terms=_expand_terms(terms) if terms else _extract_terms_heuristic(query),
        location=loc_str,
        location_normalized=loc_norm,
        explanation=str(data.get("explanation") or "ניתוח AI"),
        parser="openai",
    )


def parse_ai_query(query: str) -> ParsedQuery:
    text = query.strip()
    if not text:
        return ParsedQuery(explanation="שאילתה ריקה")
    parsed = parse_query_openai(text)
    if parsed and parsed.product_terms:
        return parsed
    return parse_query_heuristic(text)


def _item_relevance_score(desc: str, terms: list[str]) -> int:
    d = desc.lower()
    score = 0
    for t in terms:
        tl = t.lower()
        if tl in d:
            score += 3 if len(tl) >= 5 else 2 if len(tl) >= 4 else 1
    return score


def search_items_by_description_terms(
    terms: list[str],
    limit: int = 80,
) -> list[dict[str, Any]]:
    if not terms:
        return []
    select_cols = _select_items_sql()
    clauses = " OR ".join(['[תיאור פריט] LIKE ?' for _ in terms])
    params: list[Any] = [f"%{t}%" for t in terms]
    sql = f"""
        SELECT {select_cols} FROM items
        WHERE ({clauses})
        LIMIT ?
    """
    params.append(limit * 4)
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    items = [_pick_columns(r, ITEM_LIST_COLUMNS) for r in rows]

    scored: list[tuple[int, dict[str, Any]]] = []
    for item in items:
        desc = str(item.get("תיאור פריט") or "")
        sc = _item_relevance_score(desc, terms)
        if sc >= 2:
            scored.append((sc, item))
    scored.sort(key=lambda x: (-x[0], str(x[1].get('מק"ט', ""))))
    return [item for _, item in scored[:limit]]


def run_ai_search(
    query: str,
    *,
    limit_makts: int = 15,
    item_limit: int = 80,
) -> dict[str, Any]:
    parsed = parse_ai_query(query)
    terms = parsed.product_terms
    if not terms:
        return {
            "query": query,
            "parsed": parsed.__dict__,
            "ai_available": bool(os.getenv("OPENAI_API_KEY")),
            "count": 0,
            "results": [],
            "message": "לא זוהו מילות חיפוש למוצר. נסה לפרט (למשל: חיתולים למבוגרים).",
        }

    items = search_items_by_description_terms(terms, limit=item_limit)
    if not items:
        return {
            "query": query,
            "parsed": parsed.__dict__,
            "ai_available": bool(os.getenv("OPENAI_API_KEY")),
            "count": 0,
            "results": [],
            "message": "לא נמצאו מקטים התואמים לתיאור.",
        }

    groups = enrich_groups_with_supplier_counts(group_items_by_makt(items))
    def group_rank(g: dict[str, Any]) -> tuple[int, int, int]:
        variants = g.get("variants") or []
        desc = str(
            g.get("תיאור פריט")
            or (variants[0].get("תיאור פריט") if variants else "")
        )
        rel = _item_relevance_score(desc, terms)
        return (rel, g.get("supplier_count") or 0, g.get("variant_count") or 0)

    groups.sort(key=group_rank, reverse=True)
    groups = groups[:limit_makts]

    user_city = parsed.location_normalized or (
        normalize_city(parsed.location) if parsed.location else None
    )

    results: list[dict[str, Any]] = []
    for g in groups:
        makt = str(g.get('מק"ט', ""))
        suppliers = get_suppliers_for_makt(makt)
        ranked = rank_suppliers(user_city, suppliers)
        nearest = next((s for s in ranked if s.get("is_nearest")), None)
        results.append(
            {
                'מק"ט': makt,
                "תיאור פריט": g.get("תיאור פריט")
                or (g.get("variants") or [{}])[0].get("תיאור פריט"),
                "variant_count": g.get("variant_count", 0),
                "supplier_count": len(ranked),
                "variants": g.get("variants", [])[:5],
                "suppliers": ranked,
                "nearest_supplier": nearest,
                "supplier_note": (
                    "ספקים מורשים למק״ט — זהים לכל הוריאנטים"
                    if (g.get("variant_count") or 0) > 1
                    else None
                ),
            }
        )

    return {
        "query": query,
        "parsed": parsed.__dict__,
        "ai_available": bool(os.getenv("OPENAI_API_KEY")),
        "count": len(results),
        "user_location": user_city,
        "results": results,
        "message": None,
    }
