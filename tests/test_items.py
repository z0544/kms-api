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


def test_search_items_include_history_count(client) -> None:
    r = client.get(
        "/api/items",
        params={"q": "641", "match": "exact", "field": "מקט", "limit": 50},
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert all("history_count" in i for i in items)
    changed = [i for i in items if i.get("history_count", 0) > 0]
    assert len(changed) >= 1


def test_item_detail_includes_change_history(client) -> None:
    r = client.get(
        "/api/items",
        params={"q": "641", "match": "exact", "field": "מקט", "limit": 50},
    )
    eid = next(i["entity_id"] for i in r.json()["items"] if i.get("history_count"))
    detail = client.get(f"/api/item/{eid}")
    assert detail.status_code == 200
    data = detail.json()
    assert "change_history" in data
    assert data["history_count"] >= 1
    assert len(data["change_history"]) >= 1
