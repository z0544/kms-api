"""מיפוי יישובים, מחוזות ודירוג קרבה גיאוגרפית לספקים."""

from __future__ import annotations

import csv
import re
import unicodedata
from difflib import get_close_matches
from functools import lru_cache
from typing import Any

from config import GEO_MAPPING_PATH

# יישובים עיקריים (מחוז) — משלים את geo_mapping.csv
_BUILTIN_SETTLEMENTS: dict[str, str] = {
    "תל אביב - יפו": "מחוז תל אביב",
    "תל אביב": "מחוז תל אביב",
    "ירושלים": "מחוז ירושלים",
    "חיפה": "מחוז חיפה",
    "באר שבע": "מחוז הדרום",
    "שדרות": "מחוז הדרום",
    "אשקלון": "מחוז הדרום",
    "נתיבות": "מחוז הדרום",
    "אופקים": "מחוז הדרום",
    "קריית גת": "מחוז הדרום",
    "קרית גת": "מחוז הדרום",
    "דימונה": "מחוז הדרום",
    "ערד": "מחוז הדרום",
    "אילת": "מחוז הדרום",
    "פתח תקווה": "מחוז המרכז",
    "ראשון לציון": "מחוז המרכז",
    "רחובות": "מחוז המרכז",
    "נתניה": "מחוז המרכז",
    "הרצליה": "מחוז המרכז",
    "חולון": "מחוז המרכז",
    "בת ים": "מחוז המרכז",
    "רמת גן": "מחוז המרכז",
    "כפר סבא": "מחוז המרכז",
    "רעננה": "מחוז המרכז",
    "מודיעין": "מחוז המרכז",
    "לוד": "מחוז המרכז",
    "רמלה": "מחוז המרכז",
    "בני ברק": "מחוז המרכז",
    "חדרה": "מחוז חיפה",
    "קריית אתא": "מחוז חיפה",
    "נצרת": "מחוז הצפון",
    "טבריה": "מחוז הצפון",
    "צפת": "מחוז הצפון",
    "עפולה": "מחוז הצפון",
    "נהריה": "מחוז הצפון",
    "כרמיאל": "מחוז הצפון",
    "בית שמש": "מחוז ירושלים",
    "מעלה אדומים": "מחוז ירושלים",
}

CITY_ALIASES: dict[str, str] = {
    "ספרסופה": "שדרות",
    "סדרות": "שדרות",
    "שדרות": "שדרות",
    "תל אביב יפו": "תל אביב - יפו",
    "ת\"א": "תל אביב - יפו",
    "באר-שבע": "באר שבע",
    "באר שבע": "באר שבע",
    "פתח תקוה": "פתח תקווה",
    "קרית גת": "קריית גת",
}

# סדר עדיפות יישובים באותו מחוז (אינדקס נמוך = קרוב יותר לעוגן)
_DISTRICT_NEARBY: dict[str, list[str]] = {
    "מחוז הדרום": [
        "שדרות",
        "אשקלון",
        "נתיבות",
        "אופקים",
        "קריית גת",
        "באר שבע",
        "דימונה",
        "ערד",
        "אילת",
    ],
    "מחוז המרכז": [
        "רחובות",
        "לוד",
        "רמלה",
        "פתח תקווה",
        "ראשון לציון",
        "חולון",
        "בת ים",
        "תל אביב - יפו",
        "רמת גן",
        "הרצליה",
        "נתניה",
        "כפר סבא",
        "רעננה",
    ],
    "מחוז תל אביב": [
        "תל אביב - יפו",
        "רמת גן",
        "חולון",
        "בת ים",
        "הרצליה",
    ],
    "מחוז ירושלים": ["ירושלים", "בית שמש", "מעלה אדומים"],
    "מחוז חיפה": ["חיפה", "חדרה", "קריית אתא"],
    "מחוז הצפון": ["נהריה", "עפולה", "טבריה", "נצרת", "צפת", "כרמיאל"],
}

# סדר גס מצפון לדרום — לפירוק תיקו בין מחוזות שונים
_NORTH_SOUTH_ORDER: tuple[str, ...] = (
    "נהריה",
    "עכו",
    "כרמיאל",
    "צפת",
    "טבריה",
    "נצרת",
    "עפולה",
    "חיפה",
    "קריית אתא",
    "קריית ביאליק",
    "קריית מוצקין",
    "קריית ים",
    "נשר",
    "טירת כרמל",
    "חדרה",
    "אור עקיבא",
    "זכרון יעקב",
    "נתניה",
    "הרצליה",
    "כפר סבא",
    "רעננה",
    "פתח תקווה",
    "ראשון לציון",
    "רחובות",
    "חולון",
    "בת ים",
    "תל אביב - יפו",
    "רמת גן",
    "בני ברק",
    "גבעתיים",
    "ירושלים",
    "מעלה אדומים",
    "בית שמש",
    "מודיעין",
    "אשקלון",
    "אשדוד",
    "קריית גת",
    "באר שבע",
    "אילת",
)


def _normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", str(text or "").strip().lower())
    t = re.sub(r"\s+", " ", t)
    return t


def normalize_city(name: str | None) -> str:
    if not name:
        return ""
    raw = str(name).strip()
    if not raw:
        return ""
    key = _normalize_text(raw)
    for alias, canonical in CITY_ALIASES.items():
        if _normalize_text(alias) == key:
            return canonical
    if raw in _BUILTIN_SETTLEMENTS:
        return raw
    match = get_close_matches(raw, list(_BUILTIN_SETTLEMENTS.keys()), n=1, cutoff=0.82)
    if match:
        return match[0]
    return raw


@lru_cache(maxsize=1)
def load_settlement_district_map() -> dict[str, str]:
    """נטען מ-geo_mapping.csv + רשימת גיבוי מובנית."""
    mapping = dict(_BUILTIN_SETTLEMENTS)
    if GEO_MAPPING_PATH.exists():
        with GEO_MAPPING_PATH.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                city = (row.get("יישוב") or row.get("יישוב קליניקה") or "").strip()
                district = (row.get("מחוז") or row.get("אזור") or "").strip()
                if city and district:
                    mapping[city] = district
    return mapping


def get_district(city: str | None) -> str | None:
    if not city:
        return None
    norm = normalize_city(city)
    return load_settlement_district_map().get(norm)


@lru_cache(maxsize=1)
def all_settlement_names_longest_first() -> tuple[str, ...]:
    names: set[str] = set(load_settlement_district_map().keys())
    names.update(CITY_ALIASES.keys())
    names.update(CITY_ALIASES.values())
    return tuple(sorted(names, key=lambda x: len(x), reverse=True))


def find_city_in_text(text: str) -> str | None:
    """מזהה יישוב בשאילתה — דפוסי שפה + רשימת יישובים."""
    if not text:
        return None
    patterns = [
        re.compile(r"גר(?:ים|ה)?\s+ב[\-–]?\s*([א-ת\"'\-\s]{2,35})"),
        re.compile(r"מתגורר(?:ת)?\s+ב[\-–]?\s*([א-ת\"'\-\s]{2,35})"),
        re.compile(r"מגורים\s+ב[\-–]?\s*([א-ת\"'\-\s]{2,35})"),
        re.compile(r"באזור\s+([א-ת\"'\-\s]{2,35})"),
        re.compile(r"(?:קרוב|ליד|ב)\s*([א-ת\"'\-\s]{2,25})\s*$"),
    ]
    for pat in patterns:
        m = pat.search(text)
        if m:
            chunk = m.group(1).strip(" .,;\"'")
            chunk = re.split(r"\s+(?:ו|ש|עם|ל|שאני)\s+", chunk)[0].strip()
            if len(chunk) >= 2:
                return normalize_city(chunk)

    norm_text = _normalize_text(text)
    for alias, canonical in sorted(CITY_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if _normalize_text(alias) in norm_text:
            return canonical

    for city in all_settlement_names_longest_first():
        if _normalize_text(city) in norm_text:
            return normalize_city(city)

    return None


def _nearby_rank(district: str | None, settlement: str) -> int:
    if not district:
        return 999
    nearby = _DISTRICT_NEARBY.get(district, [])
    norm = normalize_city(settlement)
    try:
        return nearby.index(norm)
    except ValueError:
        return 500


def _geo_rank(city: str | None) -> int:
    """אינדקס בערך מצפון לדרום; גבוה יותר = דרומה יותר."""
    norm = normalize_city(city)
    if not norm:
        return 500
    try:
        return _NORTH_SOUTH_ORDER.index(norm)
    except ValueError:
        match = get_close_matches(norm, list(_NORTH_SOUTH_ORDER), n=1, cutoff=0.85)
        if match:
            return _NORTH_SOUTH_ORDER.index(match[0])
        return 500


def _geo_distance(user_city: str | None, supplier_city: str | None) -> int:
    return abs(_geo_rank(supplier_city) - _geo_rank(user_city))


def _fine_proximity_score(user_city: str | None, supplier: dict[str, Any]) -> int:
    """ציון משני לפירוק תיקו — גבוה יותר = קרוב יותר."""
    if not user_city:
        return 0
    user_norm = normalize_city(user_city)
    sup_city = normalize_city(supplier.get("יישוב קליניקה"))
    user_district = get_district(user_norm)
    sup_district = supplier.get("אזור") or get_district(sup_city)

    if user_norm and sup_city and user_norm == sup_city:
        return 10_000

    if user_district and sup_district and user_district == sup_district:
        dist = abs(_nearby_rank(user_district, user_norm) - _nearby_rank(user_district, sup_city))
        return max(0, 5000 - dist * 400)

    geo_dist = _geo_distance(user_norm, sup_city)
    return max(0, 3000 - geo_dist * 120)


def proximity_score(
    user_city: str | None,
    supplier: dict[str, Any],
) -> tuple[int, str]:
    """ציון גבוה יותר = ספק קרוב יותר למשתמש."""
    if not user_city:
        return 0, ""

    user_norm = normalize_city(user_city)
    sup_city = normalize_city(supplier.get("יישוב קליניקה"))
    user_district = get_district(user_norm)
    sup_district = supplier.get("אזור") or get_district(sup_city)

    if user_norm and sup_city and user_norm == sup_city:
        return 1000, "אותו יישוב"

    if user_district and sup_district and user_district == sup_district:
        user_rank = _nearby_rank(user_district, user_norm)
        sup_rank = _nearby_rank(user_district, sup_city)
        dist = abs(sup_rank - user_rank)
        if dist <= 1:
            return 850, "קרוב מאוד (אותו מחוז)"
        if dist <= 3:
            return 750, "קרוב (אותו מחוז)"
        return 650, "אותו מחוז"

    if user_district and sup_district:
        geo_dist = _geo_distance(user_norm, sup_city)
        if geo_dist <= 4:
            return 380, "סמוך גיאוגרפית"
        if geo_dist <= 10:
            return 320, "במרחק בינוני"
        if geo_dist <= 18:
            return 260, "רחוק יחסית"
        return 200, "מחוז אחר"

    if sup_city and get_close_matches(user_norm, [sup_city], n=1, cutoff=0.9):
        return 900, "יישוב דומה"

    return 100, ""


def rank_suppliers(
    user_city: str | None,
    suppliers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for s in suppliers:
        score, label = proximity_score(user_city, s)
        row = dict(s)
        row["proximity_score"] = score
        row["proximity_label"] = label
        row["_fine_proximity"] = _fine_proximity_score(user_city, s)
        enriched.append(row)
    enriched.sort(
        key=lambda x: (
            -int(x.get("proximity_score") or 0),
            -int(x.get("_fine_proximity") or 0),
            str(x.get("שם ספק") or ""),
        ),
    )
    for row in enriched:
        row["is_nearest"] = False
    if enriched and user_city and int(enriched[0].get("proximity_score") or 0) > 0:
        enriched[0]["is_nearest"] = True
    for row in enriched:
        row.pop("_fine_proximity", None)
    return enriched
