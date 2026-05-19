from __future__ import annotations


def test_health_ok(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["database_exists"] is True
    assert "version" in data
    assert "fts" in data
