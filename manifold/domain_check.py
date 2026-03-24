import sqlite3, json
with open("domain_check.txt", "w", encoding="utf-8") as out:
    with sqlite3.connect("manifold_activity.sqlite") as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM activity_log WHERE component='vector_observer' ORDER BY id DESC LIMIT 5").fetchall()
        for r in reversed(rows):
            out.write(f"[{r['timestamp']}] {r['type'].upper()} ({r['component']}): {r['message']}\n    Data: {r['data']}\n")
