import re
import os
import database

DATA_FILE = os.path.join(os.path.dirname(__file__), "Data")

KNOWN_STUDENTS = {
    "A": [
        "تيم تسابحجي", "عمر حورية", "كرم عكاشة", "عماد بيروتي",
        "أديب قدة", "جاد محروس", "كريم شخاشيرو", "علي جركس"
    ],
    "B": [
        "راتب تسابحجي", "حمزة الجاجة", "عبد الرحمن مهايني", "ليث",
        "سمير ستوت", "احمد قدة", "عمر حفار", "وليد بزرة", "نبيل نحاس"
    ],
    "C": [
        "ساريا", "عبد الكريم طالب اغا", "جاد الزين", "انس الخطيب",
        "عبد الكريم السقا", "عمر دركشلي", "جود جاويش", "عبد الغني جاويش",
        "موفق النجار", "خالد الخيمي"
    ]
}

CONTENT_KW = ["سمع", "سورة", "تلاوة", "حفظ", "ربط", "ربطها", "من اية", "صفحة",
              "اعادة", "للاستاذ", "خلصت", "بدها", "نص", "ربع", "نصف"]

def clean_name(name):
    name = re.sub(r'[:\s✅❌]+$', '', name)
    name = re.sub(r'^\s+', '', name)
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'[✅❌]', '', name).strip()
    return name

def extract_pages(text):
    if not text:
        return 0.0
    total = 0.0
    if re.search(r'صفحة\s*و\s*ربع', text):
        total = max(total, 1.25)
    elif re.search(r'صفحة\s*و\s*نصف', text):
        total = max(total, 1.5)
    if re.search(r'نص\s*صفحة', text):
        total = max(total, 0.5)
    if re.search(r'نصف\s*صفحة', text):
        total = max(total, 0.5)
    if re.search(r'ربع\s*صفحة', text):
        total = max(total, 0.25)
    m = re.search(r'(\d+\.?\d*)\s*صفحة', text)
    if m:
        total = max(total, float(m.group(1)))
    m = re.search(r'(\d+\.?\d*)\s*صفحات', text)
    if m:
        total = max(total, float(m.group(1)))
    if total == 0.0 and re.search(r'صفحة', text):
        total = 1.0
    m = re.search(r'اربع\s*اسطر\s*و\s*نصف', text)
    if m:
        total = max(total, 4.5 / 16.0)
    m = re.search(r'اربع\s*اسطر', text)
    if m:
        total = max(total, 4.0 / 16.0)
    m = re.search(r'ثمانية\s*اسطر', text)
    if m:
        total = max(total, 8.0 / 16.0)
    m = re.search(r'(\d+)\s*اسطر', text)
    if m:
        total = max(total, float(m.group(1)) / 16.0)
    m = re.search(r'(\d+)\s*سطر', text)
    if m:
        total = max(total, float(m.group(1)) / 16.0)
    return total

def extract_points(text):
    if not text:
        return 0
    m = re.search(r'(\d+)\s*\$\$?', text)
    if m:
        return int(m.group(1))
    m = re.search(r'\$\$?\s*(\d+)', text)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)\s*💲', text)
    if m:
        return int(m.group(1))
    return 0

def classify_text(text):
    if not text:
        return None
    if re.search(r'(حفظ|تسميع)', text):
        return "hifdh"
    if re.search(r'(تلاوة)', text):
        return "tilawah"
    if re.search(r'(ربط|ربطها)', text):
        return "rabt"
    if re.search(r'(سمع)', text):
        return "tilawah"
    return None

def is_content_line(text):
    for kw in CONTENT_KW:
        if kw in text:
            return True
    if re.match(r'[➡️⬅️]', text):
        return True
    return False

def migrate():
    database.init_db()

    use_sqlite = database.USE_SQLITE
    ph = "?" if use_sqlite else "%s"
    on_conflict = "INSERT INTO teams (name) VALUES ({ph}) ON CONFLICT DO NOTHING"
    on_conflict_s = "INSERT INTO students (name, team_id) VALUES ({ph}, {ph}) ON CONFLICT DO NOTHING"

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    session_date = "14/6/2026"
    session_label = "الموعد 1"
    for line in lines:
        if 'الموعد' in line and 'حفظ' in line:
            m = re.search(r'(\d+/\d+/\d+)', line)
            if m:
                session_date = m.group(1)
            m = re.search(r'الموعد\s*\((\d+)\)', line)
            if m:
                session_label = f"الموعد {m.group(1)}"

    session_id = database.get_or_create_session(session_date, session_label)

    conn = database.get_connection()
    cur = conn.cursor() if not use_sqlite else conn
    for t in ["A", "B", "C"]:
        cur.execute(on_conflict.format(ph=ph), (t,))
    conn.commit()

    for team_letter, student_names in KNOWN_STUDENTS.items():
        cur.execute(f"SELECT id FROM teams WHERE name = {ph}", (team_letter,))
        tr = cur.fetchone()
        team_id = tr["id"]
        for sname in student_names:
            cur.execute(on_conflict_s.format(ph=ph), (sname, team_id))
    conn.commit()
    conn.close()

    conn = database.get_connection()
    cur = conn.cursor() if not use_sqlite else conn
    cur.execute(f"SELECT id, name FROM teams")
    team_rows = cur.fetchall()
    team_map = {r["name"]: r["id"] for r in team_rows}
    cur.execute(f"SELECT id, name, team_id FROM students")
    all_students = cur.fetchall()
    conn.close()

    student_map = {}
    for s in all_students:
        student_map[(s["name"], s["team_id"])] = s["id"]

    current_team = None
    current_student_raw = None
    current_lines = []
    found_entries = {}

    def save_current():
        nonlocal current_student_raw, current_lines
        if current_team and current_student_raw and current_lines:
            clean = clean_name(current_student_raw)
            if clean:
                key = (clean, current_team)
                if key not in found_entries:
                    found_entries[key] = []
                found_entries[key].extend(current_lines)
        current_student_raw = None
        current_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        tm = re.match(r'الفريق\s*\(([ABC])\)', stripped)
        if tm:
            save_current()
            current_team = tm.group(1)
            continue

        if not current_team:
            continue

        if re.search(r'(مجموع|💲\s*مجموع|الموعد|صفحات?\s*(الحفظ|التلاوة|الربط)|🔴)', stripped):
            continue
        if re.match(r'^💲', stripped):
            continue

        sm = re.match(r'(\d+)\.\s*(.+)', stripped)
        if sm:
            save_current()
            current_student_raw = sm.group(2).strip()
            continue

        if (not current_student_raw
            and re.match(r'^[أ-ي\s]+[:\s]*$', stripped)
            and not is_content_line(stripped)
            and len(clean_name(stripped)) <= 20):
            save_current()
            current_student_raw = stripped
            continue

        if current_student_raw:
            current_lines.append(stripped)

    save_current()

    processed = 0
    for (student_name, team_letter), content_lines in found_entries.items():
        team_id = team_map.get(team_letter)
        if not team_id:
            continue

        student_id = student_map.get((student_name, team_id))
        if not student_id:
            for (db_name, db_tid), db_id in student_map.items():
                if db_tid == team_id and (db_name == student_name or clean_name(db_name) == student_name):
                    student_id = db_id
                    break

        if not student_id:
            print(f"  SKIP: {student_name} (فريق {team_letter})")
            continue

        full_text = "\n".join(content_lines)
        hifdh = 0.0
        tilawah = 0.0
        rabt = 0.0
        points = 0

        for cl in content_lines:
            pts = extract_points(cl)
            if pts > 0:
                points = max(points, pts)

            pages = extract_pages(cl)
            if pages == 0:
                continue

            cat = classify_text(cl)
            if cat == "hifdh":
                hifdh = max(hifdh, pages)
            elif cat == "tilawah":
                tilawah = max(tilawah, pages)
            elif cat == "rabt":
                rabt = max(rabt, pages)
            else:
                if "تلاوة" in cl:
                    tilawah = max(tilawah, pages)
                elif "ربط" in cl:
                    rabt = max(rabt, pages)
                else:
                    hifdh = max(hifdh, pages)

        database.save_entry(student_id, session_id, hifdh, tilawah, rabt, points, full_text)
        print(f"  ✓ {student_name} (فريق {team_letter}): حفظ={hifdh:.2f} تلاوة={tilawah:.2f} ربط={rabt:.2f} نقاط={points}")
        processed += 1

    all_students = database.get_all_students()
    empty_count = 0
    for s in all_students:
        existing = database.get_entry(s["id"], session_id)
        if not existing:
            database.save_entry(s["id"], session_id, 0, 0, 0, 0, "")
            empty_count += 1

    print(f"\n✓ Migration complete! Session '{session_label}' ({session_date})")
    print(f"  Students with data: {processed}, Empty: {empty_count}, Total: {processed + empty_count}")

    conn = database.get_connection()
    cur = conn.cursor() if not use_sqlite else conn
    cur.execute(f"SELECT COALESCE(SUM(points),0) as s FROM entries WHERE session_id = {ph}", (session_id,))
    tot = cur.fetchone()["s"]
    conn.close()
    print(f"  Total points: {tot} 💲")

if __name__ == "__main__":
    migrate()
