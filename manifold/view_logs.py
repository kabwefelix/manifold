import sqlite3, json
with open("log_output.txt", "w", encoding="utf-8") as out:
    with sqlite3.connect("manifold_activity.sqlite") as c:
        c.row_factory = sqlite3.Row
        rows = c.execute("SELECT * FROM activity_log ORDER BY id DESC LIMIT 40").fetchall()
        for r in reversed(rows):
            d = r['data']
            try: d = json.loads(d) if d else {}
            except: pass
            out.write(f"[{r['timestamp']}] {r['type'].upper()} ({r['component']}): {r['message']}\n    Data: {str(d)[:600]}\n")
