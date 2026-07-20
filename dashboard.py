import os
import sys
import secrets
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database

database.init_db()
database.seed_choueifat()

app = Flask(__name__, static_folder=None)
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

def _get_class():
    return request.args.get("class", request.headers.get("X-Class", "new_vision"))

@app.route("/")
def index():
    return render_template("dashboard.html")

@app.route("/api/leaderboard")
def leaderboard():
    class_name = _get_class()
    rows = database.get_cumulative_team_totals(class_name=class_name)
    return jsonify([dict(r) for r in rows])

@app.route("/api/pages-history")
def pages_history():
    class_name = _get_class()
    rows = database.get_cumulative_points_by_session(class_name=class_name)
    return jsonify([dict(r) for r in rows])

@app.route("/api/sessions")
def sessions():
    rows = database.get_sessions()
    return jsonify([dict(r) for r in rows])

@app.route("/api/teams", methods=["GET", "POST"])
def api_teams():
    class_name = _get_class()
    if request.method == "POST":
        user_info = require_teacher()
        if not user_info:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.get_json()
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "name required"}), 400
        team_id = database.add_team(name, class_name=class_name)
        return jsonify({"success": True, "id": team_id}), 201
    rows = database.get_teams(class_name=class_name)
    return jsonify([dict(r) for r in rows])

@app.route("/api/weekly-hifdh")
def api_weekly_hifdh():
    class_name = _get_class()
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = database.get_weekly_top_hifdh(since, class_name=class_name)
    return jsonify([dict(r) for r in rows])

@app.route("/api/weekly-rabt")
def api_weekly_rabt():
    class_name = _get_class()
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = database.get_weekly_top_rabt(since, class_name=class_name)
    return jsonify([dict(r) for r in rows])

@app.route("/api/anam/overall")
def api_anam_overall():
    class_name = _get_class()
    rows = database.get_student_anam_all(class_name=class_name)
    return jsonify([dict(r) for r in rows])

@app.route("/api/anam/weekly")
def api_anam_weekly():
    class_name = _get_class()
    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = database.get_student_anam_weekly(since, class_name=class_name)
    return jsonify([dict(r) for r in rows])

@app.route("/api/anam/daily")
def api_anam_daily():
    class_name = _get_class()
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    rows = database.get_student_anam_daily(date, class_name=class_name)
    return jsonify([dict(r) for r in rows])

@app.route("/api/teams/<int:team_id>/students")
def api_team_students(team_id):
    rows = database.get_students(team_id)
    return jsonify([dict(r) for r in rows])

@app.route("/api/students/<int:student_id>/history")
def api_student_history(student_id):
    rows = database.get_student_history(student_id)
    return jsonify([dict(r) for r in rows])

@app.route("/api/surahs")
def api_surahs():
    rows = database.get_surahs()
    return jsonify([dict(r) for r in rows])

@app.route("/api/students/<int:student_id>/current-surah")
def api_student_current_surah(student_id):
    row = database.get_student_current_surah(student_id)
    return jsonify(dict(row) if row else {})

# ─── Full data export (data.json shape) ───

@app.route("/api/data")
def api_data():
    class_name = _get_class()
    teams = database.get_teams(class_name=class_name)
    students = database.get_all_students(class_name=class_name)
    sessions = database.get_sessions()
    entries = database.get_all_entries_raw(class_name=class_name)
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
            surah_id=int(data["surah_id"]) if data.get("surah_id") else None,
            start_ayah=int(data["start_ayah"]) if data.get("start_ayah") else None,
            end_ayah=int(data["end_ayah"]) if data.get("end_ayah") else None,
        )
        if data.get("surah_id"):
            database.set_student_current_surah(int(data["student_id"]), int(data["surah_id"]))
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

# ─── Game Board (Monopoly) ───

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory(BASE_DIR, filename)

@app.route("/board-image")
def serve_board_image():
    return send_from_directory(BASE_DIR, "Monopoly.jpg")

@app.route("/game")
def game_board():
    return render_template("game.html")

@app.route("/api/game/state", methods=["GET"])
def api_game_state():
    class_name = request.args.get("class", "new_vision")
    rows = database.get_game_state(class_name)
    return jsonify(rows)

@app.route("/api/game/state", methods=["POST"])
def api_game_save():
    class_name = request.args.get("class", "new_vision")
    data = request.get_json()
    if not data or "characters" not in data:
        return jsonify({"success": False, "error": "no characters"}), 400
    for ch in data["characters"]:
        database.save_game_state(
            class_name=class_name,
            character_name=ch["character_name"],
            character_emoji=ch["character_emoji"],
            team_name=ch.get("team_name", ""),
            pos_x=ch.get("pos_x", 640),
            pos_y=ch.get("pos_y", 638),
        )
    return jsonify({"success": True})

@app.route("/api/game/reset", methods=["POST"])
def api_game_reset():
    class_name = request.args.get("class", "new_vision")
    database.reset_game_state(class_name)
    return jsonify({"success": True})

@app.route("/api/game/seed", methods=["POST"])
def api_game_seed():
    class_name = request.args.get("class", "new_vision")
    database.seed_default_characters(class_name)
    return jsonify({"success": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
