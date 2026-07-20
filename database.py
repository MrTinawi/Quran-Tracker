import os
import sqlite3
from functools import partial

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_SQLITE = DATABASE_URL is None

if not USE_SQLITE:
    import bcrypt
    import psycopg2
    from psycopg2.extras import RealDictCursor

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")

def _get_conn():
    global USE_SQLITE
    if USE_SQLITE:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    try:
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    except psycopg2.OperationalError as e:
        print(f"PostgreSQL connection failed ({e}). Falling back to SQLite.")
        USE_SQLITE = True
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

def _q():
    return "?" if USE_SQLITE else "%s"

def _sql(sql):
    return sql.replace("?", _q())

def _exec(conn, sql, params=None):
    if USE_SQLITE:
        return conn.execute(sql, params or ())
    cur = conn.cursor()
    cur.execute(sql, params or ())
    return cur

def get_connection():
    return _get_conn()

def _commit(conn):
    conn.commit()

def _close(conn):
    conn.close()

# ─── Init ───

def init_db():
    conn = _get_conn()
    if USE_SQLITE:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
                class_name TEXT NOT NULL DEFAULT 'new_vision'
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                team_id INTEGER NOT NULL REFERENCES teams(id)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, label TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'student'
            );
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id),
                session_id INTEGER NOT NULL REFERENCES sessions(id),
                hifdh_pages REAL DEFAULT 0, tilawah_pages REAL DEFAULT 0,
                rabt_pages REAL DEFAULT 0, points INTEGER DEFAULT 0, notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id),
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                UNIQUE(student_id, session_id)
            );
        """)
    else:
        cur = conn.cursor()
        for t in [
            "CREATE TABLE IF NOT EXISTS teams (id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, class_name TEXT NOT NULL DEFAULT 'new_vision')",
            "CREATE TABLE IF NOT EXISTS students (id SERIAL PRIMARY KEY, name TEXT NOT NULL, team_id INTEGER NOT NULL REFERENCES teams(id))",
            "CREATE TABLE IF NOT EXISTS sessions (id SERIAL PRIMARY KEY, date TEXT NOT NULL, label TEXT)",
            "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'student')",
            "CREATE TABLE IF NOT EXISTS entries (id SERIAL PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id), session_id INTEGER NOT NULL REFERENCES sessions(id), hifdh_pages REAL DEFAULT 0, tilawah_pages REAL DEFAULT 0, rabt_pages REAL DEFAULT 0, points INTEGER DEFAULT 0, notes TEXT, UNIQUE(student_id, session_id))",
        ]:
            cur.execute(t)
    _commit(conn)
    _close(conn)

    # Migration: add new columns if missing
    conn2 = _get_conn()
    for col, typ in [("surah_anam_pages", "REAL DEFAULT 0"),
                     ("attended", "INTEGER DEFAULT 1"),
                     ("misbehaviour_penalty", "INTEGER DEFAULT 0"),
                     ("inactive_penalty", "INTEGER DEFAULT 0")]:
        try:
            if USE_SQLITE:
                _exec(conn2, f"ALTER TABLE entries ADD COLUMN {col} {typ}")
            else:
                _exec(conn2, f"ALTER TABLE entries ADD COLUMN IF NOT EXISTS {col} {typ}")
            _commit(conn2)
        except Exception:
            _commit(conn2)

    # Migration: add class_name to teams if missing
    try:
        if USE_SQLITE:
            _exec(conn2, "ALTER TABLE teams ADD COLUMN class_name TEXT DEFAULT 'new_vision'")
        else:
            _exec(conn2, "ALTER TABLE teams ADD COLUMN IF NOT EXISTS class_name TEXT DEFAULT 'new_vision'")
        _commit(conn2)
    except Exception:
        _commit(conn2)

    # Migration: add surah/ayah columns to entries
    for col, typ in [("surah_id", "INTEGER DEFAULT NULL"),
                     ("start_ayah", "INTEGER DEFAULT NULL"),
                     ("end_ayah", "INTEGER DEFAULT NULL")]:
        try:
            if USE_SQLITE:
                _exec(conn2, f"ALTER TABLE entries ADD COLUMN {col} {typ}")
            else:
                _exec(conn2, f"ALTER TABLE entries ADD COLUMN IF NOT EXISTS {col} {typ}")
            _commit(conn2)
        except Exception:
            _commit(conn2)

    # Migration: add current_surah_id to students
    try:
        if USE_SQLITE:
            _exec(conn2, "ALTER TABLE students ADD COLUMN current_surah_id INTEGER DEFAULT NULL")
        else:
            _exec(conn2, "ALTER TABLE students ADD COLUMN IF NOT EXISTS current_surah_id INTEGER DEFAULT NULL")
        _commit(conn2)
    except Exception:
        _commit(conn2)

    # Create surahs table
    if USE_SQLITE:
        _exec(conn2, """
            CREATE TABLE IF NOT EXISTS surahs (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                ayah_count INTEGER NOT NULL
            )
        """)
    else:
        _exec(conn2, """
            CREATE TABLE IF NOT EXISTS surahs (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                ayah_count INTEGER NOT NULL
            )
        """)
    _commit(conn2)

    # Seed surahs if empty
    cur = _exec(conn2, "SELECT COUNT(*) as cnt FROM surahs")
    row = cur.fetchone()
    if row["cnt"] == 0:
        surahs = [
            (1, "الفاتحة", 7), (2, "البقرة", 286), (3, "آل عمران", 200),
            (4, "النساء", 176), (5, "المائدة", 120), (6, "الأنعام", 165),
            (7, "الأعراف", 206), (8, "الأنفال", 75), (9, "التوبة", 129),
            (10, "يونس", 109), (11, "هود", 123), (12, "يوسف", 111),
            (13, "الرعد", 43), (14, "إبراهيم", 52), (15, "الحجر", 99),
            (16, "النحل", 128), (17, "الإسراء", 111), (18, "الكهف", 110),
            (19, "مريم", 98), (20, "طه", 135), (21, "الأنبياء", 112),
            (22, "الحج", 78), (23, "المؤمنون", 118), (24, "النور", 64),
            (25, "الفرقان", 77), (26, "الشعراء", 227), (27, "النمل", 93),
            (28, "القصص", 88), (29, "العنكبوت", 69), (30, "الروم", 60),
            (31, "لقمان", 34), (32, "السجدة", 30), (33, "الأحزاب", 73),
            (34, "سبأ", 54), (35, "فاطر", 45), (36, "يس", 83),
            (37, "الصافات", 182), (38, "ص", 88), (39, "الزمر", 75),
            (40, "غافر", 85), (41, "فصلت", 54), (42, "الشورى", 53),
            (43, "الزخرف", 89), (44, "الدخان", 59), (45, "الجاثية", 37),
            (46, "الأحقاف", 35), (47, "محمد", 38), (48, "الفتح", 29),
            (49, "الحجرات", 18), (50, "ق", 45), (51, "الذاريات", 60),
            (52, "الطور", 49), (53, "النجم", 62), (54, "القمر", 55),
            (55, "الرحمن", 78), (56, "الواقعة", 96), (57, "الحديد", 29),
            (58, "المجادلة", 22), (59, "الحشر", 24), (60, "الممتحنة", 13),
            (61, "الصف", 14), (62, "الجمعة", 11), (63, "المنافقون", 11),
            (64, "التغابن", 18), (65, "الطلاق", 12), (66, "التحريم", 12),
            (67, "الملك", 30), (68, "القلم", 52), (69, "الحاقة", 52),
            (70, "المعارج", 44), (71, "نوح", 28), (72, "الجن", 28),
            (73, "المزمل", 20), (74, "المدثر", 56), (75, "القيامة", 40),
            (76, "الإنسان", 31), (77, "المرسلات", 50), (78, "النبأ", 40),
            (79, "النازعات", 46), (80, "عبس", 42), (81, "التكوير", 29),
            (82, "الإنفطار", 19), (83, "المطففين", 36), (84, "الانشقاق", 25),
            (85, "البروج", 22), (86, "الطارق", 17), (87, "الأعلى", 19),
            (88, "الغاشية", 26), (89, "الفجر", 30), (90, "البلد", 20),
            (91, "الشمس", 15), (92, "الليل", 21), (93, "الضحى", 11),
            (94, "الشرح", 8), (95, "التين", 8), (96, "العلق", 19),
            (97, "القدر", 5), (98, "البينة", 8), (99, "الزلزلة", 8),
            (100, "العاديات", 11), (101, "القارعة", 11), (102, "التكاثر", 8),
            (103, "العصر", 3), (104, "الهمزة", 9), (105, "الفيل", 5),
            (106, "قريش", 4), (107, "الماعون", 7), (108, "الكوثر", 3),
            (109, "الكافرون", 6), (110, "النصر", 3), (111, "المسد", 5),
            (112, "الإخلاص", 4), (113, "الفلق", 5), (114, "الناس", 6),
        ]
        for s_id, s_name, s_ayahs in surahs:
            _exec(conn2, _sql("INSERT OR IGNORE INTO surahs (id, name, ayah_count) VALUES (?, ?, ?)"),
                  (s_id, s_name, s_ayahs))
        _commit(conn2)

    _close(conn2)

# ─── Auth ───

def create_user(username, password, role="student"):
    hasher = __import__("bcrypt")
    password_hash = hasher.hashpw(password.encode(), hasher.gensalt()).decode()
    conn = _get_conn()
    _exec(conn, _sql("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)"),
          (username, password_hash, role))
    _commit(conn)
    _close(conn)

def get_user(username):
    conn = _get_conn()
    cur = _exec(conn, _sql("SELECT * FROM users WHERE username = ?"), (username,))
    user = cur.fetchone()
    _close(conn)
    return user

def authenticate_user(username, password):
    user = get_user(username)
    if not user:
        return None
    hasher = __import__("bcrypt")
    if hasher.checkpw(password.encode(), user["password_hash"].encode()):
        return user
    return None

def get_users_count():
    conn = _get_conn()
    cur = _exec(conn, "SELECT COUNT(*) as cnt FROM users")
    row = cur.fetchone()
    _close(conn)
    return row["cnt"]

def get_teachers_count():
    conn = _get_conn()
    cur = _exec(conn, "SELECT COUNT(*) as cnt FROM users WHERE role = 'teacher'")
    row = cur.fetchone()
    _close(conn)
    return row["cnt"]

# ─── Game State (Monopoly Board) ───

def init_game_table():
    conn = _get_conn()
    if USE_SQLITE:
        _exec(conn, """
            CREATE TABLE IF NOT EXISTS game_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL DEFAULT 'new_vision',
                character_name TEXT NOT NULL,
                character_emoji TEXT NOT NULL,
                team_name TEXT DEFAULT '',
                position_index INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(class_name, character_name)
            )
        """)
    else:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS game_state (
                id SERIAL PRIMARY KEY,
                class_name TEXT NOT NULL DEFAULT 'new_vision',
                character_name TEXT NOT NULL,
                character_emoji TEXT NOT NULL,
                team_name TEXT DEFAULT '',
                position_index INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(class_name, character_name)
            )
        """)
    _commit(conn)
    _close(conn)

def get_game_state(class_name="new_vision"):
    init_game_table()
    conn = _get_conn()
    cur = _exec(conn, _sql("SELECT * FROM game_state WHERE class_name = ? ORDER BY id"), (class_name,))
    rows = cur.fetchall()
    _close(conn)
    return [dict(r) for r in rows]

def save_game_state(class_name, character_name, character_emoji, team_name, position_index):
    init_game_table()
    conn = _get_conn()
    _exec(conn, _sql("""
        INSERT INTO game_state (class_name, character_name, character_emoji, team_name, position_index, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(class_name, character_name) DO UPDATE SET
            team_name = excluded.team_name,
            position_index = excluded.position_index,
            updated_at = datetime('now')
    """), (class_name, character_name, character_emoji, team_name, position_index))
    _commit(conn)
    _close(conn)

def reset_game_state(class_name="new_vision"):
    init_game_table()
    conn = _get_conn()
    _exec(conn, _sql("DELETE FROM game_state WHERE class_name = ?"), (class_name,))
    _commit(conn)
    _close(conn)

def seed_default_characters(class_name="new_vision"):
    init_game_table()
    defaults = [
        ("crown",       "👑",  "الفريق الأول",   0),
        ("padel",       "🏓",  "الفريق الثاني",  1),
        ("gold_coin",   "🪙",  "الفريق الثالث",  2),
        ("car",         "🚗",  "الفريق الرابع",  3),
        ("book",        "📖",  "الفريق الخامس",  4),
        ("star",         "⭐",  "الفريق السادس",  5),
    ]
    for name, emoji, team, pos in defaults:
        conn = _get_conn()
        try:
            _exec(conn, _sql("""
                INSERT INTO game_state (class_name, character_name, character_emoji, team_name, position_index)
                VALUES (?, ?, ?, ?, ?)
            """), (class_name, name, emoji, team, pos))
            _commit(conn)
        except Exception:
            _commit(conn)
        finally:
            _close(conn)

def get_classes():
    return ["new_vision", "choueifat"]

# ─── Teams & Students ───

def get_teams(class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("SELECT * FROM teams WHERE class_name = ? ORDER BY name"), (class_name,))
    else:
        cur = _exec(conn, "SELECT * FROM teams ORDER BY name")
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_team_by_id(team_id):
    conn = _get_conn()
    cur = _exec(conn, _sql("SELECT * FROM teams WHERE id = ?"), (team_id,))
    row = cur.fetchone()
    _close(conn)
    return row

def get_students(team_id):
    conn = _get_conn()
    cur = _exec(conn, _sql("SELECT * FROM students WHERE team_id = ? ORDER BY name"), (team_id,))
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_student_by_id(student_id):
    conn = _get_conn()
    cur = _exec(conn, _sql("SELECT s.*, t.name as team_name FROM students s JOIN teams t ON s.team_id = t.id WHERE s.id = ?"), (student_id,))
    row = cur.fetchone()
    _close(conn)
    return row

def add_student(name, team_id):
    conn = _get_conn()
    ret = "" if USE_SQLITE else " RETURNING id"
    cur = _exec(conn, _sql(f"INSERT INTO students (name, team_id) VALUES (?, ?){ret}"), (name, team_id))
    student_id = cur.lastrowid if USE_SQLITE else cur.fetchone()["id"]
    _commit(conn)
    _close(conn)
    return student_id

def remove_student(student_id):
    conn = _get_conn()
    _exec(conn, _sql("DELETE FROM entries WHERE student_id = ?"), (student_id,))
    _exec(conn, _sql("DELETE FROM students WHERE id = ?"), (student_id,))
    _commit(conn)
    _close(conn)

def get_all_students(class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT s.*, t.name as team_name FROM students s
            JOIN teams t ON s.team_id = t.id
            WHERE t.class_name = ? ORDER BY t.name, s.name
        """), (class_name,))
    else:
        cur = _exec(conn, """
            SELECT s.*, t.name as team_name FROM students s
            JOIN teams t ON s.team_id = t.id ORDER BY t.name, s.name
        """)
    rows = cur.fetchall()
    _close(conn)
    return rows

# ─── Sessions ───

def get_sessions():
    conn = _get_conn()
    cur = _exec(conn, "SELECT * FROM sessions ORDER BY id ASC")
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_sessions_desc():
    conn = _get_conn()
    cur = _exec(conn, "SELECT * FROM sessions ORDER BY id DESC")
    rows = cur.fetchall()
    _close(conn)
    return rows

def add_session(date, label):
    conn = _get_conn()
    ret = "" if USE_SQLITE else " RETURNING id"
    cur = _exec(conn, _sql(f"INSERT INTO sessions (date, label) VALUES (?, ?){ret}"), (date, label))
    session_id = cur.lastrowid if USE_SQLITE else cur.fetchone()["id"]
    _commit(conn)
    _close(conn)
    return session_id

def get_session_by_id(session_id):
    conn = _get_conn()
    cur = _exec(conn, _sql("SELECT * FROM sessions WHERE id = ?"), (session_id,))
    row = cur.fetchone()
    _close(conn)
    return row

def get_or_create_session(date, label):
    conn = _get_conn()
    cur = _exec(conn, _sql("SELECT id FROM sessions WHERE date = ? AND label = ?"), (date, label))
    row = cur.fetchone()
    if row:
        _close(conn)
        return row["id"]
    ret = "" if USE_SQLITE else " RETURNING id"
    cur = _exec(conn, _sql(f"INSERT INTO sessions (date, label) VALUES (?, ?){ret}"), (date, label))
    session_id = cur.lastrowid if USE_SQLITE else cur.fetchone()["id"]
    _commit(conn)
    _close(conn)
    return session_id

# ─── Entries ───

def get_entry(student_id, session_id):
    conn = _get_conn()
    cur = _exec(conn, _sql("SELECT * FROM entries WHERE student_id = ? AND session_id = ?"),
                (student_id, session_id))
    row = cur.fetchone()
    _close(conn)
    return row

def save_entry(student_id, session_id, hifdh_pages, tilawah_pages, rabt_pages, points, notes, surah_anam_pages=0,
               attended=1, misbehaviour_penalty=0, inactive_penalty=0,
               surah_id=None, start_ayah=None, end_ayah=None):
    conn = _get_conn()
    upsert = """
        INSERT INTO entries (student_id, session_id, hifdh_pages, tilawah_pages, rabt_pages, points, notes, surah_anam_pages, attended, misbehaviour_penalty, inactive_penalty, surah_id, start_ayah, end_ayah)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id, session_id) DO UPDATE SET
            hifdh_pages = {ex}.hifdh_pages,
            tilawah_pages = {ex}.tilawah_pages,
            rabt_pages = {ex}.rabt_pages,
            points = {ex}.points,
            notes = {ex}.notes,
            surah_anam_pages = {ex}.surah_anam_pages,
            attended = {ex}.attended,
            misbehaviour_penalty = {ex}.misbehaviour_penalty,
            inactive_penalty = {ex}.inactive_penalty,
            surah_id = {ex}.surah_id,
            start_ayah = {ex}.start_ayah,
            end_ayah = {ex}.end_ayah
    """.format(ex="excluded" if USE_SQLITE else "EXCLUDED")
    params = (student_id, session_id, hifdh_pages, tilawah_pages, rabt_pages, points, notes, surah_anam_pages, attended, misbehaviour_penalty, inactive_penalty, surah_id, start_ayah, end_ayah)
    _exec(conn, _sql(upsert), params)
    _commit(conn)
    _close(conn)

def get_session_totals(session_id, class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT t.name as team_name,
                   COALESCE(SUM(e.hifdh_pages), 0) as total_hifdh,
                   COALESCE(SUM(e.tilawah_pages), 0) as total_tilawah,
                   COALESCE(SUM(e.rabt_pages), 0) as total_rabt,
                   COALESCE(SUM(e.points + COALESCE(e.misbehaviour_penalty, 0) + COALESCE(e.inactive_penalty, 0)), 0) as total_points
            FROM entries e JOIN students s ON e.student_id = s.id JOIN teams t ON s.team_id = t.id
            WHERE e.session_id = ? AND t.class_name = ? GROUP BY t.id ORDER BY t.name
        """), (session_id, class_name))
    else:
        cur = _exec(conn, _sql("""
            SELECT t.name as team_name,
                   COALESCE(SUM(e.hifdh_pages), 0) as total_hifdh,
                   COALESCE(SUM(e.tilawah_pages), 0) as total_tilawah,
                   COALESCE(SUM(e.rabt_pages), 0) as total_rabt,
                   COALESCE(SUM(e.points + COALESCE(e.misbehaviour_penalty, 0) + COALESCE(e.inactive_penalty, 0)), 0) as total_points
            FROM entries e JOIN students s ON e.student_id = s.id JOIN teams t ON s.team_id = t.id
            WHERE e.session_id = ? GROUP BY t.id ORDER BY t.name
        """), (session_id,))
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_student_history(student_id):
    conn = _get_conn()
    cur = _exec(conn, _sql("""
        SELECT s.date, s.label, e.hifdh_pages, e.tilawah_pages, e.rabt_pages, e.points, e.surah_anam_pages,
               e.attended, e.misbehaviour_penalty, e.inactive_penalty,
               e.surah_id, e.start_ayah, e.end_ayah, su.name as surah_name
        FROM entries e
        JOIN sessions s ON e.session_id = s.id
        LEFT JOIN surahs su ON e.surah_id = su.id
        WHERE e.student_id = ? ORDER BY s.id
    """), (student_id,))
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_all_entries_for_session(session_id, class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT t.name as team_name, s.name as student_name,
                   e.hifdh_pages, e.tilawah_pages, e.rabt_pages, e.points, e.notes, e.surah_anam_pages,
                   e.attended, e.misbehaviour_penalty, e.inactive_penalty,
                   e.surah_id, e.start_ayah, e.end_ayah, su.name as surah_name
            FROM entries e
            JOIN students s ON e.student_id = s.id
            JOIN teams t ON s.team_id = t.id
            LEFT JOIN surahs su ON e.surah_id = su.id
            WHERE e.session_id = ? AND t.class_name = ? ORDER BY t.name, s.name
        """), (session_id, class_name))
    else:
        cur = _exec(conn, _sql("""
            SELECT t.name as team_name, s.name as student_name,
                   e.hifdh_pages, e.tilawah_pages, e.rabt_pages, e.points, e.notes, e.surah_anam_pages,
                   e.attended, e.misbehaviour_penalty, e.inactive_penalty,
                   e.surah_id, e.start_ayah, e.end_ayah, su.name as surah_name
            FROM entries e
            JOIN students s ON e.student_id = s.id
            JOIN teams t ON s.team_id = t.id
            LEFT JOIN surahs su ON e.surah_id = su.id
            WHERE e.session_id = ? ORDER BY t.name, s.name
        """), (session_id,))
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_all_data_for_export(class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT sess.date as session_date, sess.label as session_label,
                   t.name as team, s.name as student,
                   e.hifdh_pages, e.tilawah_pages, e.rabt_pages, e.points, e.notes, e.surah_anam_pages,
                   e.attended, e.misbehaviour_penalty, e.inactive_penalty,
                   e.surah_id, e.start_ayah, e.end_ayah, su.name as surah_name
            FROM entries e
            JOIN students s ON e.student_id = s.id
            JOIN teams t ON s.team_id = t.id
            JOIN sessions sess ON e.session_id = sess.id
            LEFT JOIN surahs su ON e.surah_id = su.id
            WHERE t.class_name = ?
            ORDER BY sess.id, t.name, s.name
        """), (class_name,))
    else:
        cur = _exec(conn, """
            SELECT sess.date as session_date, sess.label as session_label,
                   t.name as team, s.name as student,
                   e.hifdh_pages, e.tilawah_pages, e.rabt_pages, e.points, e.notes, e.surah_anam_pages,
                   e.attended, e.misbehaviour_penalty, e.inactive_penalty,
                   e.surah_id, e.start_ayah, e.end_ayah, su.name as surah_name
            FROM entries e
            JOIN students s ON e.student_id = s.id
            JOIN teams t ON s.team_id = t.id
            JOIN sessions sess ON e.session_id = sess.id
            LEFT JOIN surahs su ON e.surah_id = su.id
            ORDER BY sess.id, t.name, s.name
        """)
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_cumulative_points_by_session(class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            WITH team_sessions AS (
                SELECT sess.id as session_id, sess.date, sess.label, t.name as team_name,
                       COALESCE(SUM(e.points + COALESCE(e.misbehaviour_penalty, 0) + COALESCE(e.inactive_penalty, 0)), 0) as session_points,
                       COALESCE(SUM(e.hifdh_pages), 0) as session_hifdh,
                       COALESCE(SUM(e.tilawah_pages), 0) as session_tilawah,
                       COALESCE(SUM(e.rabt_pages), 0) as session_rabt
                FROM sessions sess CROSS JOIN teams t
                LEFT JOIN students s ON s.team_id = t.id
                LEFT JOIN entries e ON e.student_id = s.id AND e.session_id = sess.id
                WHERE t.class_name = ?
                GROUP BY sess.id, t.id
            )
            SELECT session_id, date, label, team_name,
                   session_points, session_hifdh, session_tilawah, session_rabt,
                   SUM(session_points) OVER (PARTITION BY team_name ORDER BY session_id) as cumulative_points,
                   SUM(session_hifdh) OVER (PARTITION BY team_name ORDER BY session_id) as cumulative_hifdh,
                   SUM(session_tilawah) OVER (PARTITION BY team_name ORDER BY session_id) as cumulative_tilawah,
                   SUM(session_rabt) OVER (PARTITION BY team_name ORDER BY session_id) as cumulative_rabt
            FROM team_sessions ORDER BY session_id, team_name
        """), (class_name,))
    else:
        cur = _exec(conn, """
            WITH team_sessions AS (
                SELECT sess.id as session_id, sess.date, sess.label, t.name as team_name,
                       COALESCE(SUM(e.points + COALESCE(e.misbehaviour_penalty, 0) + COALESCE(e.inactive_penalty, 0)), 0) as session_points,
                       COALESCE(SUM(e.hifdh_pages), 0) as session_hifdh,
                       COALESCE(SUM(e.tilawah_pages), 0) as session_tilawah,
                       COALESCE(SUM(e.rabt_pages), 0) as session_rabt
                FROM sessions sess CROSS JOIN teams t
                LEFT JOIN students s ON s.team_id = t.id
                LEFT JOIN entries e ON e.student_id = s.id AND e.session_id = sess.id
                GROUP BY sess.id, t.id
            )
            SELECT session_id, date, label, team_name,
                   session_points, session_hifdh, session_tilawah, session_rabt,
                   SUM(session_points) OVER (PARTITION BY team_name ORDER BY session_id) as cumulative_points,
                   SUM(session_hifdh) OVER (PARTITION BY team_name ORDER BY session_id) as cumulative_hifdh,
                   SUM(session_tilawah) OVER (PARTITION BY team_name ORDER BY session_id) as cumulative_tilawah,
                   SUM(session_rabt) OVER (PARTITION BY team_name ORDER BY session_id) as cumulative_rabt
            FROM team_sessions ORDER BY session_id, team_name
        """)
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_cumulative_team_totals(class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT t.name as team_name,
                   COALESCE(SUM(e.hifdh_pages), 0) as total_hifdh,
                   COALESCE(SUM(e.tilawah_pages), 0) as total_tilawah,
                   COALESCE(SUM(e.rabt_pages), 0) as total_rabt,
                   COALESCE(SUM(e.points + COALESCE(e.misbehaviour_penalty, 0) + COALESCE(e.inactive_penalty, 0)), 0) as total_points
            FROM teams t LEFT JOIN students s ON s.team_id = t.id LEFT JOIN entries e ON e.student_id = s.id
            WHERE t.class_name = ?
            GROUP BY t.id ORDER BY total_points DESC
        """), (class_name,))
    else:
        cur = _exec(conn, """
            SELECT t.name as team_name,
                   COALESCE(SUM(e.hifdh_pages), 0) as total_hifdh,
                   COALESCE(SUM(e.tilawah_pages), 0) as total_tilawah,
                   COALESCE(SUM(e.rabt_pages), 0) as total_rabt,
                   COALESCE(SUM(e.points + COALESCE(e.misbehaviour_penalty, 0) + COALESCE(e.inactive_penalty, 0)), 0) as total_points
            FROM teams t LEFT JOIN students s ON s.team_id = t.id LEFT JOIN entries e ON e.student_id = s.id
            GROUP BY t.id ORDER BY total_points DESC
        """)
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_top_memorizers(session_id, class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   e.hifdh_pages, e.tilawah_pages, e.rabt_pages, e.points, e.surah_anam_pages,
                   e.surah_id, e.start_ayah, e.end_ayah, su.name as surah_name
            FROM entries e
            JOIN students s ON e.student_id = s.id
            JOIN teams t ON s.team_id = t.id
            LEFT JOIN surahs su ON e.surah_id = su.id
            WHERE e.session_id = ? AND e.hifdh_pages > 0 AND t.class_name = ? ORDER BY e.hifdh_pages DESC
        """), (session_id, class_name))
    else:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   e.hifdh_pages, e.tilawah_pages, e.rabt_pages, e.points, e.surah_anam_pages,
                   e.surah_id, e.start_ayah, e.end_ayah, su.name as surah_name
            FROM entries e
            JOIN students s ON e.student_id = s.id
            JOIN teams t ON s.team_id = t.id
            LEFT JOIN surahs su ON e.surah_id = su.id
            WHERE e.session_id = ? AND e.hifdh_pages > 0 ORDER BY e.hifdh_pages DESC
        """), (session_id,))
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_all_entries_raw(class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT e.id, e.student_id, e.session_id, e.hifdh_pages, e.tilawah_pages, e.rabt_pages, e.points, e.notes, e.surah_anam_pages, e.attended, e.misbehaviour_penalty, e.inactive_penalty, e.surah_id, e.start_ayah, e.end_ayah
            FROM entries e JOIN students s ON e.student_id = s.id JOIN teams t ON s.team_id = t.id
            WHERE t.class_name = ? ORDER BY e.id
        """), (class_name,))
    else:
        cur = _exec(conn, "SELECT id, student_id, session_id, hifdh_pages, tilawah_pages, rabt_pages, points, notes, surah_anam_pages, attended, misbehaviour_penalty, inactive_penalty, surah_id, start_ayah, end_ayah FROM entries ORDER BY id")
    rows = cur.fetchall()
    _close(conn)
    return rows

def add_team(name, class_name='new_vision'):
    conn = _get_conn()
    ret = "" if USE_SQLITE else " RETURNING id"
    cur = _exec(conn, _sql(f"INSERT INTO teams (name, class_name) VALUES (?, ?){ret}"), (name, class_name))
    team_id = cur.lastrowid if USE_SQLITE else cur.fetchone()["id"]
    _commit(conn)
    _close(conn)
    return team_id

def get_weekly_top_hifdh(since_date, class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   COALESCE(SUM(e.hifdh_pages), 0) as total_hifdh,
                   COALESCE(SUM(e.rabt_pages), 0) as total_rabt,
                   COALESCE(SUM(e.points + COALESCE(e.misbehaviour_penalty, 0) + COALESCE(e.inactive_penalty, 0)), 0) as total_points,
                   su.name as surah_name
            FROM entries e
            JOIN students s ON e.student_id = s.id
            JOIN teams t ON s.team_id = t.id
            JOIN sessions sess ON e.session_id = sess.id
            LEFT JOIN surahs su ON e.surah_id = su.id
            WHERE sess.date >= ? AND e.hifdh_pages > 0 AND t.class_name = ?
            GROUP BY e.student_id
            ORDER BY total_hifdh DESC
        """), (since_date, class_name))
    else:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   COALESCE(SUM(e.hifdh_pages), 0) as total_hifdh,
                   COALESCE(SUM(e.rabt_pages), 0) as total_rabt,
                   COALESCE(SUM(e.points + COALESCE(e.misbehaviour_penalty, 0) + COALESCE(e.inactive_penalty, 0)), 0) as total_points,
                   su.name as surah_name
            FROM entries e
            JOIN students s ON e.student_id = s.id
            JOIN teams t ON s.team_id = t.id
            JOIN sessions sess ON e.session_id = sess.id
            LEFT JOIN surahs su ON e.surah_id = su.id
            WHERE sess.date >= ? AND e.hifdh_pages > 0
            GROUP BY e.student_id
            ORDER BY total_hifdh DESC
        """), (since_date,))
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_weekly_top_rabt(since_date, class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   COALESCE(SUM(e.hifdh_pages), 0) as total_hifdh,
                   COALESCE(SUM(e.rabt_pages), 0) as total_rabt,
                   COALESCE(SUM(e.points + COALESCE(e.misbehaviour_penalty, 0) + COALESCE(e.inactive_penalty, 0)), 0) as total_points,
                   su.name as surah_name
            FROM entries e
            JOIN students s ON e.student_id = s.id
            JOIN teams t ON s.team_id = t.id
            JOIN sessions sess ON e.session_id = sess.id
            LEFT JOIN surahs su ON e.surah_id = su.id
            WHERE sess.date >= ? AND e.rabt_pages > 0 AND t.class_name = ?
            GROUP BY e.student_id
            ORDER BY total_rabt DESC
        """), (since_date, class_name))
    else:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   COALESCE(SUM(e.hifdh_pages), 0) as total_hifdh,
                   COALESCE(SUM(e.rabt_pages), 0) as total_rabt,
                   COALESCE(SUM(e.points + COALESCE(e.misbehaviour_penalty, 0) + COALESCE(e.inactive_penalty, 0)), 0) as total_points,
                   su.name as surah_name
            FROM entries e
            JOIN students s ON e.student_id = s.id
            JOIN teams t ON s.team_id = t.id
            JOIN sessions sess ON e.session_id = sess.id
            LEFT JOIN surahs su ON e.surah_id = su.id
            WHERE sess.date >= ? AND e.rabt_pages > 0
            GROUP BY e.student_id
            ORDER BY total_rabt DESC
        """), (since_date,))
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_student_anam_all(class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   COALESCE(SUM(e.surah_anam_pages), 0) as total_anam,
                   COUNT(DISTINCT e.session_id) as session_count
            FROM students s
            JOIN teams t ON s.team_id = t.id
            LEFT JOIN entries e ON e.student_id = s.id
            WHERE t.class_name = ?
            GROUP BY s.id
            ORDER BY total_anam DESC
        """), (class_name,))
    else:
        cur = _exec(conn, """
            SELECT s.name as student_name, t.name as team_name,
                   COALESCE(SUM(e.surah_anam_pages), 0) as total_anam,
                   COUNT(DISTINCT e.session_id) as session_count
            FROM students s
            JOIN teams t ON s.team_id = t.id
            LEFT JOIN entries e ON e.student_id = s.id
            GROUP BY s.id
            ORDER BY total_anam DESC
        """)
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_student_anam_weekly(since_date, class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   COALESCE(sub.total, 0) as total_anam,
                   COALESCE(sub.cnt, 0) as session_count
            FROM students s
            JOIN teams t ON s.team_id = t.id
            LEFT JOIN (
                SELECT e.student_id,
                       SUM(e.surah_anam_pages) as total,
                       COUNT(DISTINCT e.session_id) as cnt
                FROM entries e
                JOIN sessions sess ON e.session_id = sess.id
                WHERE sess.date >= ?
                GROUP BY e.student_id
            ) sub ON sub.student_id = s.id
            WHERE t.class_name = ?
            ORDER BY total_anam DESC
        """), (since_date, class_name))
    else:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   COALESCE(sub.total, 0) as total_anam,
                   COALESCE(sub.cnt, 0) as session_count
            FROM students s
            JOIN teams t ON s.team_id = t.id
            LEFT JOIN (
                SELECT e.student_id,
                       SUM(e.surah_anam_pages) as total,
                       COUNT(DISTINCT e.session_id) as cnt
                FROM entries e
                JOIN sessions sess ON e.session_id = sess.id
                WHERE sess.date >= ?
                GROUP BY e.student_id
            ) sub ON sub.student_id = s.id
            ORDER BY total_anam DESC
        """), (since_date,))
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_student_anam_daily(date, class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   COALESCE(sub.total, 0) as total_anam,
                   sub.session_label, sub.session_date
            FROM students s
            JOIN teams t ON s.team_id = t.id
            LEFT JOIN (
                SELECT e.student_id,
                       SUM(e.surah_anam_pages) as total,
                       sess.label as session_label,
                       sess.date as session_date
                FROM entries e
                JOIN sessions sess ON e.session_id = sess.id
                WHERE sess.date = ?
                GROUP BY e.student_id
            ) sub ON sub.student_id = s.id
            WHERE t.class_name = ?
            ORDER BY total_anam DESC
        """), (date, class_name))
    else:
        cur = _exec(conn, _sql("""
            SELECT s.name as student_name, t.name as team_name,
                   COALESCE(sub.total, 0) as total_anam,
                   sub.session_label, sub.session_date
            FROM students s
            JOIN teams t ON s.team_id = t.id
            LEFT JOIN (
                SELECT e.student_id,
                       SUM(e.surah_anam_pages) as total,
                       sess.label as session_label,
                       sess.date as session_date
                FROM entries e
                JOIN sessions sess ON e.session_id = sess.id
                WHERE sess.date = ?
                GROUP BY e.student_id
            ) sub ON sub.student_id = s.id
            ORDER BY total_anam DESC
        """), (date,))
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_hifdh_leaders_all_sessions(class_name=None):
    conn = _get_conn()
    if class_name:
        cur = _exec(conn, _sql("""
            WITH ranked AS (
                SELECT sess.id as session_id, sess.date, sess.label,
                       s.name as student_name, t.name as team_name, e.hifdh_pages,
                       su.name as surah_name, e.start_ayah, e.end_ayah,
                       ROW_NUMBER() OVER (PARTITION BY sess.id ORDER BY e.hifdh_pages DESC) as rn
                FROM entries e JOIN students s ON e.student_id = s.id
                JOIN teams t ON s.team_id = t.id JOIN sessions sess ON e.session_id = sess.id
                LEFT JOIN surahs su ON e.surah_id = su.id
                WHERE e.hifdh_pages > 0 AND t.class_name = ?
            )
            SELECT session_id, date, label, student_name, team_name, hifdh_pages,
                   surah_name, start_ayah, end_ayah
            FROM ranked WHERE rn = 1 ORDER BY session_id
        """), (class_name,))
    else:
        cur = _exec(conn, """
            WITH ranked AS (
                SELECT sess.id as session_id, sess.date, sess.label,
                       s.name as student_name, t.name as team_name, e.hifdh_pages,
                       su.name as surah_name, e.start_ayah, e.end_ayah,
                       ROW_NUMBER() OVER (PARTITION BY sess.id ORDER BY e.hifdh_pages DESC) as rn
                FROM entries e JOIN students s ON e.student_id = s.id
                JOIN teams t ON s.team_id = t.id JOIN sessions sess ON e.session_id = sess.id
                LEFT JOIN surahs su ON e.surah_id = su.id
                WHERE e.hifdh_pages > 0
            )
            SELECT session_id, date, label, student_name, team_name, hifdh_pages,
                   surah_name, start_ayah, end_ayah
            FROM ranked WHERE rn = 1 ORDER BY session_id
        """)
    rows = cur.fetchall()
    _close(conn)
    return rows

# ─── Surahs ───

def get_surahs():
    conn = _get_conn()
    cur = _exec(conn, "SELECT * FROM surahs ORDER BY id")
    rows = cur.fetchall()
    _close(conn)
    return rows

def get_surah_by_id(surah_id):
    conn = _get_conn()
    cur = _exec(conn, _sql("SELECT * FROM surahs WHERE id = ?"), (surah_id,))
    row = cur.fetchone()
    _close(conn)
    return row

def get_student_current_surah(student_id):
    conn = _get_conn()
    cur = _exec(conn, _sql("""
        SELECT s.current_surah_id, su.name as surah_name, su.ayah_count
        FROM students s
        LEFT JOIN surahs su ON s.current_surah_id = su.id
        WHERE s.id = ?
    """), (student_id,))
    row = cur.fetchone()
    _close(conn)
    return row

def set_student_current_surah(student_id, surah_id):
    conn = _get_conn()
    _exec(conn, _sql("UPDATE students SET current_surah_id = ? WHERE id = ?"), (surah_id, student_id))
    _commit(conn)
    _close(conn)

def get_team_export_data(team_id):
    conn = _get_conn()
    cur = _exec(conn, _sql("""
        SELECT sess.date as session_date, sess.label as session_label,
               s.name as student,
               e.hifdh_pages, e.tilawah_pages, e.rabt_pages, e.points, e.notes, e.surah_anam_pages,
               e.attended, e.misbehaviour_penalty, e.inactive_penalty,
               e.surah_id, e.start_ayah, e.end_ayah, su.name as surah_name
        FROM entries e
        JOIN students s ON e.student_id = s.id
        JOIN sessions sess ON e.session_id = sess.id
        LEFT JOIN surahs su ON e.surah_id = su.id
        WHERE s.team_id = ?
        ORDER BY sess.id, s.name
    """), (team_id,))
    rows = cur.fetchall()
    _close(conn)
    return rows

# ─── Seeding ───

def seed_choueifat():
    choueifat_teams = get_teams(class_name="choueifat")
    if choueifat_teams:
        return

    teams_data = {
        "فريق A": ["حمزة صباغ", "فارس بقاعي", "محمد محفوظ", "سامي العظمة", "وليد عودة", "فدى بارودي"],
        "فريق B": ["محمد قواص", "موفق الجابي", "نزار موصلي", "سامي سكر", "أحمد عمري", "جواد سلامة", "سمير محايري"],
        "فريق C": ["علي ايتوني", "ممتاز الخطيب", "عمر سيروان", "كريم الطير", "كنان اسطواني", "كريم غبرة"],
    }

    for team_name, students in teams_data.items():
        team_id = add_team(team_name, class_name="choueifat")
        for student_name in students:
            add_student(student_name, team_id)

if __name__ == "__main__":
    init_db()
    print(f"Database initialized! Mode: {'SQLite' if USE_SQLITE else 'PostgreSQL'}")
