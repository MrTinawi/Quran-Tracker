import os
import sys
import secrets
from datetime import datetime
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
CORS(app, supports_credentials=True)

# Simple token-based auth (not session-based for API)
TOKENS = {}

# ─── Auth ───

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")
    user = database.authenticate_user(username, password)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    token = secrets.token_hex(32)
    TOKENS[token] = {"user_id": user["id"], "username": user["username"], "role": user["role"]}
    return jsonify({
        "token": token,
        "user": {"id": user["id"], "username": user["username"], "role": user["role"]}
    })

def require_auth():
    auth = request.headers.get("Authorization", "")
    token = auth.replace("Bearer ", "")
    if token not in TOKENS:
        return None
    return TOKENS[token]

def require_teacher():
    user_info = require_auth()
    if not user_info or user_info["role"] != "teacher":
        return None
    return user_info

# ─── Public read endpoints (no auth needed) ───

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/leaderboard")
def leaderboard():
    rows = database.get_cumulative_team_totals()
    return jsonify([dict(r) for r in rows])

@app.route("/api/pages-history")
def pages_history():
    rows = database.get_cumulative_points_by_session()
    return jsonify([dict(r) for r in rows])

@app.route("/api/sessions")
def sessions():
    rows = database.get_sessions()
    return jsonify([dict(r) for r in rows])

@app.route("/api/teams")
def api_teams():
    rows = database.get_teams()
    return jsonify([dict(r) for r in rows])

@app.route("/api/teams/<int:team_id>/students")
def api_team_students(team_id):
    rows = database.get_students(team_id)
    return jsonify([dict(r) for r in rows])

@app.route("/api/students/<int:student_id>/history")
def api_student_history(student_id):
    rows = database.get_student_history(student_id)
    return jsonify([dict(r) for r in rows])

# ─── Full data export (data.json shape) ───

@app.route("/api/data")
def api_data():
    teams = database.get_teams()
    students = database.get_all_students()
    sessions = database.get_sessions()
    entries = database.get_all_entries_raw()
    return jsonify({
        "teams": [dict(t) for t in teams],
        "students": [dict(s) for s in students],
        "sessions": [dict(s) for s in sessions],
        "entries": [dict(e) for e in entries],
    })

# ─── Auth-protected write endpoints ───

@app.route("/api/entries", methods=["POST"])
def api_save_entry():
    user_info = require_teacher()
    if not user_info:
        return jsonify({"error": "Unauthorized — teacher access required"}), 401
    data = request.get_json()
    try:
        database.save_entry(
            int(data["student_id"]),
            int(data["session_id"]),
            float(data.get("hifdh_pages", 0)),
            float(data.get("tilawah_pages", 0)),
            float(data.get("rabt_pages", 0)),
            int(data.get("points", 0)),
            data.get("notes", ""),
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/students", methods=["POST"])
def api_add_student():
    user_info = require_teacher()
    if not user_info:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    name = data.get("name", "").strip()
    team_id = data.get("team_id")
    if not name or not team_id:
        return jsonify({"error": "name and team_id required"}), 400
    student_id = database.add_student(name, int(team_id))
    return jsonify({"success": True, "id": student_id}), 201

@app.route("/api/students/<int:student_id>", methods=["DELETE"])
def api_remove_student(student_id):
    user_info = require_teacher()
    if not user_info:
        return jsonify({"error": "Unauthorized"}), 401
    database.remove_student(student_id)
    return jsonify({"success": True})

@app.route("/api/sessions", methods=["POST"])
def api_add_session():
    user_info = require_teacher()
    if not user_info:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    label = data.get("label", "").strip()
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    if not label:
        return jsonify({"error": "label required"}), 400
    session_id = database.add_session(date, label)
    return jsonify({"success": True, "id": session_id}), 201

# ─── Serve admin panel ───

QURAN_TRACKER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Quran-Tracker-Dashboard")

@app.route("/admin")
def admin_panel():
    return send_from_directory(QURAN_TRACKER_DIR, "entry.html")

@app.route("/db.js")
def admin_db_js():
    return send_from_directory(QURAN_TRACKER_DIR, "db.js")

if __name__ == "__main__":
    database.init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
