from __future__ import annotations


def test_admin_reload_disabled_without_token_config(client) -> None:
    r = client.post("/api/admin/reload-data", headers={"X-Admin-Token": "any"})
    assert r.status_code == 403
