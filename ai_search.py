"""חיפוש חכם בשפה חופשית — מקומי וחינמי, ללא OpenAI."""

from __future__ import annotations

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
from geo_service import find_city_in_text, normalize_city, rank_suppliers

# מילות עזר בעברית — לא משמשות לחיפוש במאגר
STOPWORDS = frozenset(
    """
    אני אתה את אתם אנחנו הוא היא הם הן של על עם ב בב בבית גר גרה גרים
    מחפש מחפשת מחפשים רוצה רוצים צריך צריכה צריכים למצוא תן תני שיש
    איפה הכי קרוב אליי לי אלי אלינו עבור כדי שאני אשמח בבקשה גם כן
    לא כל מאוד יותר מאוד ואני שזה זה יש לי אצלי אצלנו איזה איזהו
    מה שמי שיכול אפשר אפשרות דבר דברים מוצר מוצרים פריט פריטים
    """.split()
)

_HE_PREFIXES = ("ול", "ל", "ב", "מ", "ה", "ו", "כ", "ש")


@dataclass
class ParsedQuery:
    product_terms: list[str] = field(default_factory=list)
    search_phrase: str = ""
    location: str | None = None
    location_normalized: str | None = None
    explanation: str = ""
    parser: str = "local"


def _strip_hebrew_prefix(word: str) -> str:
    w = word.strip()
    for _ in range(2):
        changed = False
        for p in _HE_PREFIXES:
            if w.startswith(p) and len(w) > len(p) + 1:
                w = w[len(p) :]
                changed = True
                break
        if not changed:
            break
    return w


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[א-ת0-9][א-ת0-9\-]{1,}", text)
    tokens: list[str] = []
    for w in words:
        if w in STOPWORDS or len(w) < 2:
            continue
        root = _strip_hebrew_prefix(w)
        if root and root not in STOPWORDS and len(root) >= 2:
            tokens.append(root)
    return tokens


def _remove_city_from_text(text: str, city: str | None) -> str:
    if not city:
        return text
    out = text
    for variant in {city, normalize_city(city)}:
        if variant:
            out = re.sub(re.escape(variant), " ", out, flags=re.IGNORECASE)
    return out


def parse_smart_query(query: str) -> ParsedQuery:
    text = query.strip()
    if not text:
        return ParsedQuery(explanation="שאילתה ריקה")

    location_raw = find_city_in_text(text)
    loc_norm = normalize_city(location_raw) if location_raw else None

    without_loc = _remove_city_from_text(text, location_raw)
    for pat in (
        r"גר(?:ים|ה)?\s+ב[\-–]?\s*",
        r"מתגורר(?:ת)?\s+ב[\-–]?\s*",
        r"מגורים\s+ב[\-–]?\s*",
        r"באזור\s+",
    ):
        without_loc = re.sub(pat, " ", without_loc)

    without_loc = re.sub(r"[^\w\s\"'-]+", " ", without_loc, flags=re.UNICODE)
    without_loc = re.sub(r"\s+", " ", without_loc).strip()

    terms = _tokenize(without_loc)
    if not terms and without_loc:
        terms = _tokenize(text)

    # ביטוי שלם לחיפוש (למשל "עדשות מולטיפוקל" / "כיסא גלגלים")
    phrase = without_loc if len(without_loc) >= 3 else ""
    if not phrase and terms:
        phrase = " ".join(terms[:6])

    expl_parts = ["חיפוש חכם מקומי (חינמי)"]
    if phrase:
        expl_parts.append(f"ביטוי: {phrase[:60]}")
    if terms:
        expl_parts.append(f"מילים: {', '.join(terms[:8])}")
    if loc_norm:
        expl_parts.append(f"מיקום: {loc_norm}")

    return ParsedQuery(
        product_terms=terms,
        search_phrase=phrase,
        location=location_raw,
        location_normalized=loc_norm,
        explanation=" · ".join(expl_parts),
        parser="local",
    )


def parse_ai_query(query: str) -> ParsedQuery:
    return parse_smart_query(query)


def _item_relevance_score(
    desc: str,
    terms: list[str],
    phrase: str,
) -> int:
    d = desc.lower()
    score = 0
    if phrase and len(phrase) >= 3 and phrase.lower() in d:
        score += 12
    if not terms:
        return score
    matched = 0
    for t in terms:
        tl = t.lower()
        if tl in d:
            matched += 1
            score += 4 if len(tl) >= 5 else 3 if len(tl) >= 4 else 2
    if terms and matched == len(terms):
        score += 6
    elif matched and matched >= max(1, len(terms) // 2):
        score += 3
    return score


def _min_relevance_score(terms: list[str], phrase: str) -> int:
    if phrase and len(phrase) >= 4:
        return 2
    if len(terms) <= 1:
        return 2
    if len(terms) == 2:
        return 3
    return 4


def search_items_smart(
    terms: list[str],
    phrase: str,
    limit: int = 80,
) -> list[dict[str, Any]]:
    select_cols = _select_items_sql()
    clauses: list[str] = []
    params: list[Any] = []

    if phrase and len(phrase) >= 3:
        clauses.append('[תיאור פריט] LIKE ?')
        params.append(f"%{phrase}%")

    for t in terms:
        clauses.append('[תיאור פריט] LIKE ?')
        params.append(f"%{t}%")

    if not clauses:
        return []

    sql = f"""
        SELECT {select_cols} FROM items
        WHERE ({' OR '.join(clauses)})
        LIMIT ?
    """
    params.append(limit * 5)

    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()

    items = [_pick_columns(r, ITEM_LIST_COLUMNS) for r in rows]
    min_score = _min_relevance_score(terms, phrase)
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in items:
        desc = str(item.get("תיאור פריט") or "")
        sc = _item_relevance_score(desc, terms, phrase)
        if sc >= min_score:
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
    phrase = parsed.search_phrase

    if not terms and not phrase:
        return {
            "query": query,
            "parsed": parsed.__dict__,
            "engine": "local",
            "count": 0,
            "results": [],
            "message": "לא זוהו מילות חיפוש. נסה לתאר את המוצר או השירות (למשל: עדשות, כיסא גלגלים, בדיקת שינה).",
        }

    items = search_items_smart(terms, phrase, limit=item_limit)
    if not items:
        return {
            "query": query,
            "parsed": parsed.__dict__,
            "engine": "local",
            "count": 0,
            "results": [],
            "message": "לא נמצאו מקטים התואמים לתיאור. נסה ניסוח אחר או מילים נרדפות.",
        }

    groups = enrich_groups_with_supplier_counts(group_items_by_makt(items))

    def group_rank(g: dict[str, Any]) -> tuple[int, int, int]:
        variants = g.get("variants") or []
        desc = str(
            g.get("תיאור פריט")
            or (variants[0].get("תיאור פריט") if variants else "")
        )
        rel = _item_relevance_score(desc, terms, phrase)
        return (rel, g.get("supplier_count") or 0, g.get("variant_count") or 0)

    groups.sort(key=group_rank, reverse=True)
    groups = groups[:limit_makts]

    user_city = parsed.location_normalized

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
        "engine": "local",
        "count": len(results),
        "user_location": user_city,
        "results": results,
        "message": None,
    }
