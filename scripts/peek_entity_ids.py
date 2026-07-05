import sqlite3
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cols = ['entity_id', 'מק"ט', 'סוג זכאי', 'סוג סכום', 'רמת בסיס', 'רמת חריגה', 'אחוז לחריגה']
select = ", ".join(f'[{c}]' if c != "entity_id" else "entity_id" for c in cols)
for r in conn.execute(f"SELECT {select} FROM items WHERE CAST([מק\"ט] AS TEXT) = '642' LIMIT 3"):
    print(dict(r))
for r in conn.execute(f"SELECT {select} FROM items LIMIT 3"):
    print(dict(r))
print("total", conn.execute("SELECT COUNT(*) FROM items").fetchone()[0])
