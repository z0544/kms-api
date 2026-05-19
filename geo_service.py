"""מיפוי יישובים, מחוזות ודירוג קרבה גיאוגרפית לספקים."""

from __future__ import annotations

import csv
import math
import re
import unicodedata
from difflib import get_close_matches
from functools import lru_cache
from typing import Any

from config import GEO_MAPPING_PATH

# קואורדינטות משוערות (lat, lon) — בסיס לחישוב מרחק בק"מ
_CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "תל אביב - יפו": (32.0853, 34.7818),
    "תל אביב": (32.0853, 34.7818),
    "רמת גן": (32.0684, 34.8248),
    "גבעתיים": (32.0722, 34.8080),
    "בני ברק": (32.0849, 34.8332),
    "חולון": (32.0158, 34.7874),
    "בת ים": (32.0171, 34.7450),
    "אור יהודה": (32.0297, 34.8480),
    "קריית אונו": (32.0617, 34.8553),
    "אזור": (32.0246, 34.8066),
    "ירושלים": (31.7683, 35.2137),
    "בית שמש": (31.7470, 34.9881),
    "מעלה אדומים": (31.7774, 35.2980),
    "ביתר עילית": (31.6900, 35.1060),
    "מודיעין עילית": (31.9322, 35.0422),
    "אבו גוש": (31.8059, 35.1064),
    "מבשרת ציון": (31.8017, 35.1522),
    "חיפה": (32.7940, 34.9896),
    "קריית אתא": (32.8044, 35.1066),
    "קריית ביאליק": (32.8276, 35.0850),
    "קריית מוצקין": (32.8360, 35.0770),
    "קריית ים": (32.8500, 35.0700),
    "נשר": (32.7620, 35.0500),
    "טירת כרמל": (32.7620, 34.9720),
    "נתניה": (32.3215, 34.8532),
    "חדרה": (32.4340, 34.9190),
    "אור עקיבא": (32.5060, 34.9200),
    "זכרון יעקב": (32.5700, 34.9530),
    "פרדס חנה-כרכור": (32.4740, 34.9770),
    "באר שבע": (31.2520, 34.7915),
    "שדרות": (31.5250, 34.5960),
    "אשקלון": (31.6690, 34.5715),
    "אשדוד": (31.8040, 34.6550),
    "נתיבות": (31.4180, 34.5950),
    "אופקים": (31.2770, 34.6230),
    "קריית גת": (31.6100, 34.7640),
    "קרית גת": (31.6100, 34.7640),
    "דימונה": (31.0690, 35.0330),
    "ערד": (31.2580, 35.2130),
    "אילת": (29.5581, 34.9482),
    "ירוחם": (30.9880, 34.9310),
    "מצפה רמון": (30.6100, 34.8000),
    "להבים": (31.3730, 34.8970),
    "עומר": (31.3060, 34.8530),
    "מיתר": (31.3270, 34.9460),
    "קצרין": (32.9900, 35.6900),
    "פתח תקווה": (32.0870, 34.8870),
    "ראשון לציון": (31.9730, 34.7925),
    "רחובות": (31.8940, 34.8120),
    "נס ציונה": (31.9320, 34.7980),
    "רמלה": (31.9290, 34.8670),
    "לוד": (31.9510, 34.8880),
    "מודיעין-מכבים-רעות": (31.8960, 35.0100),
    "מודיעין": (31.8960, 35.0100),
    "כפר סבא": (32.1750, 34.9070),
    "הרצליה": (32.1660, 34.8430),
    "רעננה": (32.1840, 34.8710),
    "הוד השרון": (32.1590, 34.8930),
    "כפר יונה": (32.3170, 34.9350),
    "טייבה": (32.2660, 35.0080),
    "טירה": (32.2340, 34.9500),
    "קלנסווה": (32.2850, 34.9850),
    "יהוד-מונוסון": (32.0330, 34.8880),
    "גני תקווה": (32.0610, 34.8730),
    "אלעד": (32.0490, 34.9520),
    "שוהם": (32.0000, 34.9500),
    "יבנה": (31.8780, 34.7400),
    "גדרה": (31.8150, 34.7780),
    "מזכרת בתיה": (31.8530, 34.8420),
    "ראש העין": (32.0950, 34.9580),
    "נהריה": (33.0080, 35.0980),
    "עכו": (32.9260, 35.0820),
    "נצרת": (32.7010, 35.2970),
    "נצרת עילית": (32.7080, 35.3250),
    "טבריה": (32.7950, 35.5310),
    "צפת": (32.9650, 35.4980),
    "עפולה": (32.6100, 35.2900),
    "יקנעם עילית": (32.6600, 35.1100),
    "מגדל העמק": (32.6770, 35.2400),
    "נוף הגליל": (32.7100, 35.3300),
    "מעלות-תרשיחא": (33.0170, 35.2780),
    "כרמיאל": (32.9190, 35.3030),
    "מצפה אבייב": (32.9800, 35.4000),
    "קריית שמונה": (33.2070, 35.5700),
    "מגאר": (32.8880, 35.4070),
    "סחנין": (32.8640, 35.2970),
    "שפרעם": (32.8060, 35.1690),
    "טמרה": (32.8530, 35.2000),
    "בוקעאתא": (33.2030, 35.7750),
    "מעיליה": (33.0280, 35.2570),
    "בית שאן": (32.4970, 35.4960),
}

_DISTRICT_CENTROIDS: dict[str, tuple[float, float]] = {
    "מחוז תל אביב": (32.08, 34.78),
    "מחוז המרכז": (32.02, 34.90),
    "מחוז ירושלים": (31.77, 35.21),
    "מחוז חיפה": (32.70, 35.00),
    "מחוז הצפון": (32.95, 35.25),
    "מחוז הדרום": (31.35, 34.75),
    "רמת הגולן": (33.05, 35.75),
}

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
    "אשדוד": "מחוז הדרום",
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
    "נהריה": "מחוז הצפון",
    "עפולה": "מחוז הצפון",
    "טבריה": "מחוז הצפון",
    "נצרת": "מחוז הצפון",
    "צפת": "מחוז הצפון",
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
    "באר שבעה": "באר שבע",
    "פתח תקוה": "פתח תקווה",
    "פתח תקווה": "פתח תקווה",
    "קרית גת": "קריית גת",
    "ראשון": "ראשון לציון",
    "ראשון לציון": "ראשון לציון",
    "ב\"ש": "באר שבע",
    "חיפה": "חיפה",
    "ירושלים": "ירושלים",
    "אשדוד": "אשדוד",
    "אשקלון": "אשקלון",
}

_DISTRICT_ALIASES: dict[str, str] = {
    "דרום": "מחוז הדרום",
    "הדרום": "מחוז הדרום",
    "מחוז דרום": "מחוז הדרום",
    "מרכז": "מחוז המרכז",
    "המרכז": "מחוז המרכז",
    "מחוז מרכז": "מחוז המרכז",
    "צפון": "מחוז הצפון",
    "הצפון": "מחוז הצפון",
    "חיפה והצפון": "מחוז חיפה",
    "תל אביב": "מחוז תל אביב",
    "ירושלים והסביבה": "מחוז ירושלים",
}

_UNKNOWN_DISTANCE_KM = 9999.0


def _normalize_text(text: str) -> str:
    t = unicodedata.normalize("NFKC", str(text or "").strip().lower())
    t = re.sub(r"\s+", " ", t)
    return t


def normalize_district(name: str | None) -> str | None:
    if not name:
        return None
    raw = str(name).strip()
    if not raw:
        return None
    key = _normalize_text(raw)
    for alias, canonical in _DISTRICT_ALIASES.items():
        if _normalize_text(alias) == key:
            return canonical
    if raw.startswith("מחוז"):
        return raw
    if raw in ("רמת הגולן",):
        return raw
    return f"מחוז {raw}" if not raw.startswith("ה") else f"מחוז {raw.lstrip('ה')}"


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
    if raw in _BUILTIN_SETTLEMENTS or raw in _CITY_COORDINATES:
        return raw
    all_names = list(_CITY_COORDINATES.keys()) + list(_BUILTIN_SETTLEMENTS.keys())
    match = get_close_matches(raw, all_names, n=1, cutoff=0.82)
    if match:
        return match[0]
    return raw


@lru_cache(maxsize=1)
def load_settlement_district_map() -> dict[str, str]:
    mapping = dict(_BUILTIN_SETTLEMENTS)
    if GEO_MAPPING_PATH.exists():
        with GEO_MAPPING_PATH.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                city = (row.get("יישוב") or row.get("יישוב קליניקה") or "").strip()
                district = (row.get("מחוז") or row.get("אזור") or "").strip()
                if city and district:
                    mapping[city] = normalize_district(district) or district
    return mapping


def get_district(city: str | None) -> str | None:
    if not city:
        return None
    norm = normalize_city(city)
    d = load_settlement_district_map().get(norm)
    return normalize_district(d) if d else None


def get_supplier_district(supplier: dict[str, Any]) -> str | None:
    raw = supplier.get("אזור")
    if raw:
        d = normalize_district(str(raw))
        if d:
            return d
    return get_district(normalize_city(supplier.get("יישוב קליניקה")))


@lru_cache(maxsize=1)
def all_settlement_names_longest_first() -> tuple[str, ...]:
    names: set[str] = set(load_settlement_district_map().keys())
    names.update(CITY_ALIASES.keys())
    names.update(CITY_ALIASES.values())
    names.update(_CITY_COORDINATES.keys())
    return tuple(sorted(names, key=lambda x: len(x), reverse=True))


def _city_from_pattern_chunk(chunk: str) -> str | None:
    """מאמת שם יישוב מתוך דפוס שפה — לא מחזיר שברי מילים."""
    chunk = chunk.strip(" .,;\"'")
    chunk = re.split(r"\s+(?:ו|ש|עם|ל|שאני)\s+", chunk)[0].strip()
    if len(chunk) < 3:
        return None
    city = normalize_city(chunk)
    if get_coordinates(city) or get_district(city):
        return city
    match = get_close_matches(
        chunk,
        list(_CITY_COORDINATES.keys()),
        n=1,
        cutoff=0.85,
    )
    return match[0] if match else None


def find_city_in_text(text: str) -> str | None:
    if not text:
        return None

    norm_text = _normalize_text(text)

    # 1. ערים מוכרות קודם — מונע זיהוי שגוי של האות ב' בתוך מילים כמו "רחובות"
    for city in all_settlement_names_longest_first():
        cn = _normalize_text(city)
        if len(cn) >= 3 and cn in norm_text:
            return normalize_city(city)

    for alias, canonical in sorted(
        CITY_ALIASES.items(), key=lambda x: len(x[0]), reverse=True,
    ):
        if len(alias) >= 3 and _normalize_text(alias) in norm_text:
            return canonical

    # 2. דפוסי שפה — 'ב' רק כמילת יחס (אחרי רווח/תחילת מחרוזת), לא בתוך מילה
    patterns = [
        re.compile(r"גר(?:ים|ה)?\s+ב[\-–]?\s*([א-ת\"'\-\s]{2,35})"),
        re.compile(r"מתגורר(?:ת)?\s+ב[\-–]?\s*([א-ת\"'\-\s]{2,35})"),
        re.compile(r"מגורים\s+ב[\-–]?\s*([א-ת\"'\-\s]{2,35})"),
        re.compile(r"באזור\s+([א-ת\"'\-\s]{2,35})"),
        re.compile(r"(?:^|\s)(?:קרוב|ליד)\s+([א-ת\"'\-\s]{2,25})\s*$"),
        re.compile(r"(?:^|\s)ב[\-–]?\s+([א-ת\"'\-\s]{2,25})\s*$"),
    ]
    for pat in patterns:
        m = pat.search(text)
        if m:
            found = _city_from_pattern_chunk(m.group(1))
            if found:
                return found

    return None


def get_coordinates(city: str | None) -> tuple[float, float] | None:
    norm = normalize_city(city or "")
    if not norm:
        return None
    if norm in _CITY_COORDINATES:
        return _CITY_COORDINATES[norm]
    match = get_close_matches(norm, list(_CITY_COORDINATES.keys()), n=1, cutoff=0.85)
    if match:
        return _CITY_COORDINATES[match[0]]
    district = get_district(norm)
    if district and district in _DISTRICT_CENTROIDS:
        return _DISTRICT_CENTROIDS[district]
    return None


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float,
) -> float:
    r = 6371.0
    p = math.pi / 180.0
    a = (
        0.5
        - math.cos((lat2 - lat1) * p) / 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    )
    return 2 * r * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def distance_km(user_city: str | None, supplier_city: str | None) -> float:
    """מרחק בק״מ. ערך גבוה מאוד אם לא ניתן לחשב."""
    user_norm = normalize_city(user_city or "")
    sup_norm = normalize_city(supplier_city or "")
    if user_norm and sup_norm and user_norm == sup_norm:
        return 0.0

    u = get_coordinates(user_norm)
    s = get_coordinates(sup_norm)
    if u and s:
        return haversine_km(u[0], u[1], s[0], s[1])

    user_d = get_district(user_norm)
    sup_d = get_district(sup_norm)
    if user_d and sup_d and user_d == sup_d:
        return 35.0

    if u and sup_d and sup_d in _DISTRICT_CENTROIDS:
        c = _DISTRICT_CENTROIDS[sup_d]
        return haversine_km(u[0], u[1], c[0], c[1])
    if s and user_d and user_d in _DISTRICT_CENTROIDS:
        c = _DISTRICT_CENTROIDS[user_d]
        return haversine_km(c[0], c[1], s[0], s[1])

    return _UNKNOWN_DISTANCE_KM


def _label_for_distance(
    km: float,
    *,
    same_city: bool,
    same_district: bool,
) -> str:
    if same_city or km < 0.5:
        return "אותו יישוב"
    km_round = max(1, int(round(km)))
    if km <= 15:
        return f"כ-{km_round} ק\"מ · קרוב מאוד"
    if km <= 40:
        if same_district:
            return f"כ-{km_round} ק\"מ · אותו מחוז"
        return f"כ-{km_round} ק\"מ"
    if km <= 90:
        if same_district:
            return f"כ-{km_round} ק\"מ · אותו מחוז"
        return f"כ-{km_round} ק\"מ · מרחק בינוני"
    if km < 500:
        return f"כ-{km_round} ק\"מ"
    return "מרחק לא ידוע"


def proximity_score(
    user_city: str | None,
    supplier: dict[str, Any],
    *,
    distance: float | None = None,
) -> tuple[int, str]:
    if not user_city:
        return 0, ""

    user_norm = normalize_city(user_city)
    sup_city = normalize_city(supplier.get("יישוב קליניקה"))
    km = distance if distance is not None else distance_km(user_norm, sup_city)
    user_d = get_district(user_norm)
    sup_d = get_supplier_district(supplier)
    same_city = bool(user_norm and sup_city and user_norm == sup_city)
    same_district = bool(user_d and sup_d and user_d == sup_d)

    label = _label_for_distance(km, same_city=same_city, same_district=same_district)
    if km >= _UNKNOWN_DISTANCE_KM:
        return 50, label
    score = max(0, min(1000, int(1000 - km * 8)))
    return score, label


def rank_suppliers(
    user_city: str | None,
    suppliers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    user_norm = normalize_city(user_city or "") if user_city else ""
    enriched: list[dict[str, Any]] = []

    for s in suppliers:
        sup_city = s.get("יישוב קליניקה")
        km = distance_km(user_norm, sup_city) if user_norm else _UNKNOWN_DISTANCE_KM
        score, label = proximity_score(user_norm, s, distance=km)
        row = dict(s)
        row["distance_km"] = None if km >= _UNKNOWN_DISTANCE_KM else round(km, 1)
        row["proximity_score"] = score
        row["proximity_label"] = label
        enriched.append(row)

    enriched.sort(
        key=lambda x: (
            x.get("distance_km") if x.get("distance_km") is not None else 9999,
            str(x.get("שם ספק") or ""),
        ),
    )

    for row in enriched:
        row["is_nearest"] = False
    if enriched and user_norm:
        enriched[0]["is_nearest"] = True

    return enriched
