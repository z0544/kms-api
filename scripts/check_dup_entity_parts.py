import sqlite3
from collections import Counter
from config import DB_PATH

conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    """
    SELECT [מק"ט], [סוג זכאי], [סוג סכום], [רמת בסיס], [רמת חריגה], COUNT(*) c
    FROM items
    GROUP BY 1,2,3,4,5
    HAVING c > 1
    LIMIT 10
    """
).fetchall()
print("dup groups without achuz:", len(rows), rows[:5])
