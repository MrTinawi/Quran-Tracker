import os
import sqlite3
from flask import Flask, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/leaderboard")
def leaderboard():
    conn = get_db()
    cur = conn.execute("""
        SELECT t.name as team_name,
               COALESCE(SUM(e.points), 0) as total_points,
               COALESCE(SUM(e.hifdh_pages), 0) as total_hifdh,
               COALESCE(SUM(e.tilawah_pages), 0) as total_tilawah,
               COALESCE(SUM(e.rabt_pages), 0) as total_rabt
        FROM teams t
        LEFT JOIN students s ON s.team_id = t.id
        LEFT JOIN entries e ON e.student_id = s.id
        GROUP BY t.id
        ORDER BY total_points DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/pages-history")
def pages_history():
    conn = get_db()
    cur = conn.execute("""
        WITH team_sessions AS (
            SELECT sess.id as session_id, sess.date, sess.label, t.name as team_name,
                   COALESCE(SUM(e.points), 0) as session_points,
                   COALESCE(SUM(e.hifdh_pages), 0) as session_hifdh
            FROM sessions sess
            CROSS JOIN teams t
            LEFT JOIN students s ON s.team_id = t.id
            LEFT JOIN entries e ON e.student_id = s.id AND e.session_id = sess.id
            GROUP BY sess.id, t.id
        )
        SELECT session_id, date, label, team_name, session_points, session_hifdh,
               SUM(session_hifdh) OVER (PARTITION BY team_name ORDER BY session_id) as cumulative_hifdh,
               SUM(session_points) OVER (PARTITION BY team_name ORDER BY session_id) as cumulative_points
        FROM team_sessions
        ORDER BY session_id, team_name
    """)
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/sessions")
def sessions():
    conn = get_db()
    cur = conn.execute("SELECT * FROM sessions ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
