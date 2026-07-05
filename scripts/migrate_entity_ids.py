"""מיגרציה חד-פעמית של entity_id לפורמט החדש."""

from __future__ import annotations

import sqlite3
import sys

from config import DB_PATH
from entity_id import migrate_entity_ids, needs_entity_id_migration


def main() -> int:
    if not DB_PATH.exists():
        print(f"DB not found: {DB_PATH}", file=sys.stderr)
        return 1
    conn = sqlite3.connect(DB_PATH)
    try:
        if not needs_entity_id_migration(conn):
            print("No migration needed — entity_id already in new format.")
            return 0
        stats = migrate_entity_ids(conn)
        print(f"Migrated {stats['updated']} / {stats['total']} items.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
