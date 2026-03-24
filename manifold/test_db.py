import sqlite3
import json
conn = sqlite3.connect('manifold_activity.sqlite')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
print("Tables:", [t['name'] for t in tables])
for t in tables:
    name = t['name']
    rows = cursor.execute(f"SELECT * FROM {name} ORDER BY id DESC LIMIT 5").fetchall()
    print(f"\n--- {name} ---")
    for r in reversed(rows):
        print(dict(r))
