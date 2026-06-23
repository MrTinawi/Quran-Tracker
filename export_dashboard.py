import sqlite3
import json
import re
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "data.db")
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "templates", "dashboard.html")
OUTPUT_PATH = os.path.join(SCRIPT_DIR, "index.html")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

lb = [dict(r) for r in conn.execute("""
    SELECT t.name as team_name,
           COALESCE(SUM(e.points),0) as total_points,
           COALESCE(SUM(e.hifdh_pages),0) as total_hifdh,
           COALESCE(SUM(e.tilawah_pages),0) as total_tilawah,
           COALESCE(SUM(e.rabt_pages),0) as total_rabt
    FROM teams t
    LEFT JOIN students s ON s.team_id = t.id
    LEFT JOIN entries e ON e.student_id = s.id
    GROUP BY t.id ORDER BY total_points DESC
""").fetchall()]

hi = [dict(r) for r in conn.execute("""
    WITH ts AS (
        SELECT sess.id, sess.date, sess.label, t.name as tn,
               COALESCE(SUM(e.points),0) as sp,
               COALESCE(SUM(e.hifdh_pages),0) as sh
        FROM sessions sess
        CROSS JOIN teams t
        LEFT JOIN students s ON s.team_id = t.id
        LEFT JOIN entries e ON e.student_id = s.id AND e.session_id = sess.id
        GROUP BY sess.id, t.id
    )
    SELECT id as session_id, date, label, tn as team_name,
           sp as session_points, sh as session_hifdh,
           SUM(sh) OVER(PARTITION BY tn ORDER BY id) as cumulative_hifdh,
           SUM(sp) OVER(PARTITION BY tn ORDER BY id) as cumulative_points
    FROM ts ORDER BY id, tn
""").fetchall()]
conn.close()

data_json = json.dumps({"leaderboard": lb, "history": hi}, ensure_ascii=False)

with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
    html = f.read()

html = re.sub(
    r'const EMBEDDED_DATA = \{.*?\};',
    f'const EMBEDDED_DATA = {data_json};',
    html,
    flags=re.DOTALL
)

with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Dashboard exported to {OUTPUT_PATH}")
