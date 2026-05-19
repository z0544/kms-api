from __future__ import annotations


def test_ai_status(client) -> None:
    r = client.get("/api/ai/status")
    assert r.status_code == 200
    assert r.json()["engine"] == "local"


def test_ai_search_short_query(client) -> None:
    r = client.post("/api/ai/search", json={"query": "ab"})
    assert r.status_code == 422


def test_ai_search_valid(client) -> None:
    r = client.post("/api/ai/search", json={"query": "כיסא גלגלים"})
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert data["engine"] == "local"
