from __future__ import annotations


def test_search_items_contains(client) -> None:
    r = client.get("/api/items", params={"q": "כיסא", "limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 1
    assert "items" in data
    assert "groups" in data


def test_search_items_not_found(client) -> None:
    r = client.get(
        "/api/items",
        params={"q": "xyznonexistent99999", "match": "exact", "field": "מקט"},
    )
    assert r.status_code == 404


def test_invalid_match_mode(client) -> None:
    r = client.get("/api/items", params={"q": "x", "match": "INVALID"})
    assert r.status_code == 422
