"""Fixtures משותפים לטסטי API."""

from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from config import DB_PATH
from db_schema import ensure_schema
from main import app


@pytest.fixture(scope="session")
def require_db() -> None:
    if not DB_PATH.exists():
        pytest.skip(f"בסיס נתונים חסר: {DB_PATH} — הרץ python process_data.py")
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_schema(conn)
    finally:
        conn.close()


@pytest.fixture
def client(require_db) -> TestClient:
    return TestClient(app)
