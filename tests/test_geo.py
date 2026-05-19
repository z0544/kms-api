from __future__ import annotations

from geo_service import distance_km, find_city_in_text, normalize_city, rank_suppliers


def test_distance_sderot_closer_than_rishon() -> None:
    d_sderot = distance_km("שדרות", "שדרות")
    d_ashkelon = distance_km("שדרות", "אשקלון")
    d_rishon = distance_km("שדרות", "ראשון לציון")
    assert d_sderot == 0.0
    assert d_ashkelon < d_rishon
    assert d_ashkelon < 50


def test_rank_suppliers_orders_by_distance() -> None:
    suppliers = [
        {"שם ספק": "מרכז", "יישוב קליניקה": "ראשון לציון", "אזור": None},
        {"שם ספק": "דרום", "יישוב קליניקה": "אשקלון", "אזור": None},
        {"שם ספק": "מקומי", "יישוב קליניקה": "שדרות", "אזור": None},
    ]
    ranked = rank_suppliers("שדרות", suppliers)
    assert ranked[0]["יישוב קליניקה"] == "שדרות"
    assert ranked[0]["is_nearest"] is True
    assert ranked[1]["יישוב קליניקה"] == "אשקלון"
    assert (ranked[0].get("distance_km") or 0) <= (ranked[1].get("distance_km") or 999)


def test_find_city_sderot_alias() -> None:
    assert normalize_city("ספרסופה") == "שדרות"
    assert find_city_in_text("גר בשדרות") == "שדרות"
