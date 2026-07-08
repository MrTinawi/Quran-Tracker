import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
import database

matplotlib.use("Agg")
plt.rcParams["figure.figsize"] = (10, 5)

database.init_db()

if not database.get_teachers_count():
    import os
    default_pw = os.environ.get("ADMIN_PASSWORD", "admin123")
    database.create_user("admin", default_pw, "teacher")

LANG = "ar"

CLASS_LABELS = {
    "new_vision": "نيو فيجن",
    "choueifat": "الشويفات",
}

TEXTS = {
    "title": "📖 نظام تتبع حفظ القرآن",
    "class_label": "اختر الصف",
    "session_mgmt": "إدارة الجلسات",
    "date": "التاريخ",
    "label": "عنوان الجلسة",
    "add_session": "إضافة جلسة جديدة",
    "select_session": "اختر الجلسة",
    "data_entry": "إدخال البيانات",
    "select_team": "اختر الفريق",
    "select_student": "اختر الطالب",
    "hifdh": "حفظ (صفحات)",
    "tilawah": "تلاوة (صفحات)",
    "surah_anam": "سورة الأنعام (صفحات)",
    "attendance": "الحضور",
    "attended": "حاضر",
    "not_attended": "غائب",
    "misbehaviour_penalty": "خصم سوء السلوك (نقاط)",
    "inactive_penalty": "خصم الحضور بدون عمل (نقاط)",
    "rabt": "ربط (صفحات)",
    "points": "النقاط (💲)",
    "notes": "ملاحظات",
    "save": "💾 حفظ",
    "saved": "✅ تم الحفظ!",
    "team_totals": "إحصائيات الفريق",
    "total_hifdh": "مجموع الحفظ",
    "total_tilawah": "مجموع التلاوة",
    "total_rabt": "مجموع الربط",
    "total_points": "مجموع النقاط",
    "team": "الفريق",
    "student": "الطالب",
    "no_data": "لا توجد بيانات لهذه الجلسة",
    "analysis": "التحليلات",
    "export": "تصدير البيانات",
    "export_csv": "📥 تصدير CSV",
    "history": "سجل الطالب",
    "session_report": "تقرير الجلسة",
    "all_data": "جميع البيانات",
    "student_progress": "تقدم الطالب",
    "no_history": "لا يوجد سجل لهذا الطالب بعد",
    "new_session": "جلسة جديدة",
    "best_memorizers": "أفضل الحفظ",
    "cumulative": "المجموع التراكمي",
    "session_totals": "إحصائيات هذه الجلسة",
    "rank": "الرتبة",
    "student_hifdh": "حفظ (صفحات)",
    "hifdh_leader": "بطل الحفظ",
    "weekly_winner": "بطل هذا الأسبوع",
    "no_memorizers": "لا يوجد حفظ في هذه الجلسة",
    "weekly_winners": "أبطال الأسبوع",
    "best_rabt": "أفضل الربط",
    "rabt_leader": "بطل الربط",
    "weekly_period": "آخر 7 أيام",
    "team_mgmt": "إدارة الفرق والطلاب",
    "create_team": "إنشاء فريق جديد",
    "team_name": "اسم الفريق",
    "team_created": "✅ تم إنشاء الفريق",
    "add_student_to_team": "إضافة طالب إلى فريق",
    "student_added": "✅ تم إضافة الطالب",
}

def _(key):
    return TEXTS.get(key, key)

# ─── Authentication ───
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.markdown("## 🔐 تسجيل الدخول")
    with st.form("login"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        submitted = st.form_submit_button("دخول", use_container_width=True)
    if submitted:
        user = database.authenticate_user(username, password)
        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.error("❌ اسم المستخدم أو كلمة المرور غير صحيحة")
    st.stop()

user = st.session_state.user
is_teacher = user["role"] == "teacher"

# ─── Class Selection ───
if "class_name" not in st.session_state:
    st.session_state.class_name = "new_vision"

class_name = st.session_state.class_name

st.title(f"📖 {CLASS_LABELS.get(class_name, class_name)} — نظام تتبع حفظ القرآن")

# ─── Sidebar ───
with st.sidebar:
    st.markdown(f"**المستخدم:** {user['username']}  \n**الدور:** {'مشرف' if is_teacher else 'طالب'}")

    selected_class = st.selectbox(
        _("class_label"),
        options=database.get_classes(),
        format_func=lambda c: CLASS_LABELS.get(c, c),
        index=database.get_classes().index(class_name),
        key="class_selector"
    )

    if selected_class != st.session_state.class_name:
        st.session_state.class_name = selected_class
        st.session_state.current_team = None
        st.session_state.current_student = None
        if selected_class == "choueifat":
            database.seed_choueifat()
        st.rerun()

    class_name = st.session_state.class_name

    if st.button("🚪 تسجيل الخروج"):
        st.session_state.user = None
        st.rerun()
    st.divider()

    st.header(_("session_mgmt"))

    sessions = database.get_sessions()
    session_options = {f"{s['label']} - {s['date']}": s["id"] for s in sessions}
    session_keys = list(session_options.keys())

    if session_keys:
        selected_session_key = st.selectbox(
            _("select_session"), session_keys,
            index=0 if session_keys else None
        )
        session_id = session_options[selected_session_key]
    else:
        st.warning("لا توجد جلسات. أضف جلسة أولاً.")
        session_id = None

    with st.expander(_("new_session")):
        if not is_teacher:
            st.info("فقط المشرفون يمكنهم إضافة جلسات جديدة")
        else:
            new_date = st.date_input(_("date"))
            new_label = st.text_input(_("label"), value="")
            if st.button(_("add_session")):
                if new_label.strip():
                    database.add_session(str(new_date), new_label.strip())
                    st.success(f"✅ تمت إضافة الجلسة: {new_label}")
                    st.rerun()
                else:
                    st.error("الرجاء إدخال عنوان الجلسة")

    if is_teacher:
        st.divider()
        with st.expander("👥 إدارة المستخدمين"):
            with st.form("create_user"):
                new_user = st.text_input("اسم المستخدم")
                new_pass = st.text_input("كلمة المرور", type="password")
                new_role = st.selectbox("الدور", ["student", "teacher"],
                                        format_func=lambda r: "مشرف" if r == "teacher" else "طالب")
                submitted = st.form_submit_button("إنشاء حساب", type="primary", use_container_width=True)

            if submitted:
                if not new_user or not new_pass:
                    st.error("الرجاء ملء جميع الحقول")
                elif database.get_user(new_user):
                    st.error("اسم المستخدم موجود مسبقاً")
                else:
                    database.create_user(new_user, new_pass, new_role)
                    st.success(f"✅ تم إنشاء حساب {new_user}")
                    st.rerun()

        with st.expander("👥 " + _("team_mgmt")):
            with st.form("create_team"):
                new_team_name = st.text_input(_("team_name"))
                if st.form_submit_button(_("create_team"), type="primary", use_container_width=True):
                    if new_team_name.strip():
                        database.add_team(new_team_name.strip(), class_name=class_name)
                        st.success(_("team_created"))
                        st.rerun()
                    else:
                        st.error("الرجاء إدخال اسم الفريق")

            st.markdown("---")

            all_teams = database.get_teams(class_name=class_name)
            team_opts = {t["name"]: t["id"] for t in all_teams}
            with st.form("add_student"):
                sel_team = st.selectbox(_("select_team"), list(team_opts.keys()))
                new_student = st.text_input(_("select_student"))
                if st.form_submit_button(_("add_student_to_team"), type="primary", use_container_width=True):
                    if new_student.strip():
                        database.add_student(new_student.strip(), team_opts[sel_team])
                        st.success(_("student_added"))
                        st.rerun()
                    else:
                        st.error("الرجاء إدخال اسم الطالب")

# ─── Main Content ───
if session_id is None:
    st.info("الرجاء إضافة جلسة أولاً من القائمة الجانبية")
    st.stop()

# Initialize session state
if "current_team" not in st.session_state:
    st.session_state.current_team = None
if "current_student" not in st.session_state:
    st.session_state.current_student = None

tabs = st.tabs([_("data_entry"), _("team_totals"), _("session_report"), _("analysis"), _("export"), _("best_memorizers"), _("weekly_winners")])

# ═══════════════════════════════════════════
# TAB 1: DATA ENTRY
# ═══════════════════════════════════════════
with tabs[0]:
    col1, col2 = st.columns([1, 2])

    with col1:
        teams = database.get_teams(class_name=class_name)
        team_names = {t["name"]: t["id"] for t in teams}
        selected_team_name = st.selectbox(
            _("select_team"), list(team_names.keys()),
            key="team_selector"
        )
        team_id = team_names[selected_team_name]

        students = database.get_students(team_id)
        student_names = {s["name"]: s["id"] for s in students}
        selected_student_name = st.selectbox(
            _("select_student"), list(student_names.keys()),
            key="student_selector"
        )
        student_id = student_names[selected_student_name]

        st.session_state.current_team = selected_team_name
        st.session_state.current_student = selected_student_name

    with col2:
        st.subheader(f"{selected_student_name} - {selected_team_name}")

        existing = database.get_entry(student_id, session_id)

        hifdh = st.number_input(
            _("hifdh"), min_value=0.0, step=0.25,
            value=float(existing["hifdh_pages"]) if existing else 0.0,
            key=f"hifdh_{student_id}_{session_id}"
        )
        tilawah = st.number_input(
            _("tilawah"), min_value=0.0, step=0.25,
            value=float(existing["tilawah_pages"]) if existing else 0.0,
            key=f"tilawah_{student_id}_{session_id}"
        )
        surah_anam = st.number_input(
            _("surah_anam"), min_value=0.0, step=0.25,
            value=float(existing["surah_anam_pages"]) if existing and "surah_anam_pages" in existing else 0.0,
            key=f"anam_{student_id}_{session_id}"
        )
        rabt = st.number_input(
            _("rabt"), min_value=0.0, step=0.25,
            value=float(existing["rabt_pages"]) if existing else 0.0,
            key=f"rabt_{student_id}_{session_id}"
        )
        points = st.number_input(
            _("points"), min_value=0, step=5,
            value=int(existing["points"]) if existing else 0,
            key=f"points_{student_id}_{session_id}"
        )

        col_a1, col_a2 = st.columns(2)
        with col_a1:
            attended = st.checkbox(
                _("attended"),
                value=bool(existing["attended"]) if existing and "attended" in existing else True,
                key=f"attended_{student_id}_{session_id}"
            )
        with col_a2:
            if not attended:
                st.caption(_("not_attended"))

        misbehaviour_penalty = st.number_input(
            _("misbehaviour_penalty"), min_value=-100, step=1,
            value=int(existing["misbehaviour_penalty"]) if existing and "misbehaviour_penalty" in existing else 0,
            key=f"misbehave_{student_id}_{session_id}"
        )
        inactive_penalty = st.number_input(
            _("inactive_penalty"), min_value=-100, step=1,
            value=int(existing["inactive_penalty"]) if existing and "inactive_penalty" in existing else 0,
            key=f"inactive_{student_id}_{session_id}"
        )

        notes = st.text_area(
            _("notes"),
            value=existing["notes"] if existing and existing["notes"] else "",
            height=120,
            key=f"notes_{student_id}_{session_id}"
        )

        if st.button(_("save"), type="primary", use_container_width=True):
            if not is_teacher:
                st.error("غير مسموح بالتعديل. فقط المشرفون يمكنهم حفظ البيانات.")
            else:
                database.save_entry(student_id, session_id, hifdh, tilawah, rabt, points, notes, surah_anam,
                                    int(attended), misbehaviour_penalty, inactive_penalty)
                st.success(_("saved"))

    # Student history below
    history = database.get_student_history(student_id)
    if history:
        st.subheader(_("history"))
        hist_df = pd.DataFrame([{
            "التاريخ": h["date"],
            "الجلسة": h["label"],
            "حفظ": h["hifdh_pages"],
            "تلاوة": h["tilawah_pages"],
            "الأنعام": h["surah_anam_pages"],
            "ربط": h["rabt_pages"],
            "نقاط": h["points"],
            "حضور": "✅" if h["attended"] else "❌",
            "خصم سلوك": h["misbehaviour_penalty"],
            "خصم خمول": h["inactive_penalty"],
        } for h in history])
        st.dataframe(hist_df, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════
# TAB 2: TEAM TOTALS
# ═══════════════════════════════════════════
with tabs[1]:
    st.subheader(_("team_totals"))

    totals = database.get_session_totals(session_id, class_name=class_name)
    if totals:
        total_data = []
        for t in totals:
            total_data.append({
                _("team"): t["team_name"],
                _("total_hifdh"): t["total_hifdh"],
                _("total_tilawah"): t["total_tilawah"],
                _("total_rabt"): t["total_rabt"],
                _("total_points"): t["total_points"],
            })
        totals_df = pd.DataFrame(total_data)
        totals_df["المجموع الكلي (صفحات)"] = (
            totals_df[_("total_hifdh")] +
            totals_df[_("total_tilawah")] +
            totals_df[_("total_rabt")]
        )
        st.dataframe(totals_df, use_container_width=True, hide_index=True)

        # Bar chart
        fig, ax = plt.subplots()
        x = [t["team_name"] for t in totals]
        w = 0.2
        x_pos = range(len(x))
        ax.bar([p - w for p in x_pos], [t["total_hifdh"] for t in totals], w, label="حفظ")
        ax.bar(x_pos, [t["total_tilawah"] for t in totals], w, label="تلاوة")
        ax.bar([p + w for p in x_pos], [t["total_rabt"] for t in totals], w, label="ربط")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(x)
        ax.set_ylabel("صفحات")
        ax.legend()
        st.pyplot(fig)

        # Points chart
        fig2, ax2 = plt.subplots()
        ax2.bar(x, [t["total_points"] for t in totals], color="gold", edgecolor="orange")
        ax2.set_ylabel("💲 نقاط")
        ax2.set_xlabel("الفريق")
        for i, t in enumerate(totals):
            ax2.text(i, t["total_points"] + 5, str(t["total_points"]), ha="center")
        st.pyplot(fig2)
    else:
        st.info(_("no_data"))

    # ── Cumulative section ──
    st.markdown("---")
    st.subheader(_("cumulative"))

    cum_data = database.get_cumulative_team_totals(class_name=class_name)
    if cum_data:
        cum_df = pd.DataFrame([{
            _("team"): c["team_name"],
            _("total_hifdh"): c["total_hifdh"],
            _("total_tilawah"): c["total_tilawah"],
            _("total_rabt"): c["total_rabt"],
            _("total_points"): c["total_points"],
        } for c in cum_data])
        cum_df["المجموع الكلي (صفحات)"] = (
            cum_df[_("total_hifdh")] + cum_df[_("total_tilawah")] + cum_df[_("total_rabt")]
        )
        st.dataframe(cum_df, use_container_width=True, hide_index=True)

        # Running cumulative line chart
        cum_by_session = database.get_cumulative_points_by_session(class_name=class_name)
        if cum_by_session:
            cum_pts_df = pd.DataFrame([{
                "session_label": c["label"],
                "team": c["team_name"],
                "cumulative_points": c["cumulative_points"],
            } for c in cum_by_session])

            st.subheader("النقاط التراكمية لكل فريق عبر الجلسات")
            fig3, ax3 = plt.subplots()
            for team in cum_pts_df["team"].unique():
                td = cum_pts_df[cum_pts_df["team"] == team]
                ax3.plot(td["session_label"], td["cumulative_points"], "o-", label=f"الفريق {team}", linewidth=2.5)
            ax3.set_ylabel("💲 نقاط")
            ax3.legend()
            plt.xticks(rotation=45)
            st.pyplot(fig3)
    else:
        st.info(_("no_data"))

# ═══════════════════════════════════════════
# TAB 3: SESSION REPORT
# ═══════════════════════════════════════════
with tabs[2]:
    st.subheader(_("session_report"))

    entries = database.get_all_entries_for_session(session_id, class_name=class_name)
    if entries:
        report_df = pd.DataFrame([{
            _("team"): e["team_name"],
            _("student"): e["student_name"],
            _("hifdh"): e["hifdh_pages"],
            _("tilawah"): e["tilawah_pages"],
            "الأنعام": e["surah_anam_pages"],
            _("rabt"): e["rabt_pages"],
            _("points"): e["points"],
            "حضور": "✅" if e["attended"] else "❌",
            "خصم سلوك": e["misbehaviour_penalty"],
            "خصم خمول": e["inactive_penalty"],
        } for e in entries])
        st.dataframe(report_df, use_container_width=True, hide_index=True)
    else:
        st.info(_("no_data"))

# ═══════════════════════════════════════════
# TAB 4: ANALYSIS
# ═══════════════════════════════════════════
with tabs[3]:
    st.subheader(_("analysis"))

    teams = database.get_teams(class_name=class_name)
    all_entries = database.get_all_data_for_export(class_name=class_name)

    if not all_entries:
        st.info(_("no_data"))
        st.stop()

    df = pd.DataFrame([{
        "session_date": e["session_date"],
        "session_label": e["session_label"],
        "team": e["team"],
        "student": e["student"],
        "hifdh_pages": e["hifdh_pages"],
        "tilawah_pages": e["tilawah_pages"],
        "surah_anam_pages": e["surah_anam_pages"],
        "rabt_pages": e["rabt_pages"],
        "points": e["points"],
    } for e in all_entries])

    # Filter controls
    selected_team_filter = st.selectbox(
        _("select_team"), ["الكل"] + list(df["team"].unique()),
        key="analysis_team"
    )
    if selected_team_filter != "الكل":
        df_filtered = df[df["team"] == selected_team_filter]
    else:
        df_filtered = df

    selected_student_filter = st.selectbox(
        _("select_student"), ["الكل"] + list(df_filtered["student"].unique()),
        key="analysis_student"
    )
    if selected_student_filter != "الكل":
        df_filtered = df_filtered[df_filtered["student"] == selected_student_filter]

    if df_filtered.empty:
        st.info(_("no_data"))
        st.stop()

    # Group by session for trend
    if selected_student_filter != "الكل":
        trend = df_filtered.groupby("session_date").agg(
            {"hifdh_pages": "sum", "tilawah_pages": "sum", "surah_anam_pages": "sum", "rabt_pages": "sum", "points": "sum"}
        ).reset_index()

        st.subheader(_("student_progress"))
        fig, ax = plt.subplots()
        ax.plot(trend["session_date"], trend["hifdh_pages"], "o-", label="حفظ")
        ax.plot(trend["session_date"], trend["tilawah_pages"], "s-", label="تلاوة")
        ax.plot(trend["session_date"], trend["surah_anam_pages"], "^-", label="الأنعام")
        ax.plot(trend["session_date"], trend["rabt_pages"], "D-", label="ربط")
        ax.plot(trend["session_date"], trend["points"], "D-", label="نقاط")
        ax.set_xlabel("التاريخ")
        ax.legend()
        plt.xticks(rotation=45)
        st.pyplot(fig)
    else:
        # Team comparison over time
        trend = df_filtered.groupby(["session_date", "team"]).agg(
            {"points": "sum"}
        ).reset_index()

        st.subheader("مقارنة النقاط بين الفرق")
        fig, ax = plt.subplots()
        for team in trend["team"].unique():
            team_data = trend[trend["team"] == team]
            ax.plot(team_data["session_date"], team_data["points"], "o-", label=f"الفريق {team}")
        ax.set_xlabel("التاريخ")
        ax.set_ylabel("💲 نقاط")
        ax.legend()
        plt.xticks(rotation=45)
        st.pyplot(fig)

# ═══════════════════════════════════════════
# TAB 5: EXPORT
# ═══════════════════════════════════════════
with tabs[4]:
    st.subheader(_("export"))

    all_data = database.get_all_data_for_export(class_name=class_name)
    if all_data:
        export_df = pd.DataFrame([{
            "التاريخ": e["session_date"],
            "الجلسة": e["session_label"],
            "الفريق": e["team"],
            "الطالب": e["student"],
            "حفظ (صفحات)": e["hifdh_pages"],
            "تلاوة (صفحات)": e["tilawah_pages"],
            "الأنعام (صفحات)": e["surah_anam_pages"],
            "ربط (صفحات)": e["rabt_pages"],
            "النقاط": e["points"],
            "حضور": "نعم" if e["attended"] else "لا",
            "خصم سلوك": e["misbehaviour_penalty"],
            "خصم خمول": e["inactive_penalty"],
            "ملاحظات": e["notes"],
        } for e in all_data])

        st.dataframe(export_df, use_container_width=True, hide_index=True)

        csv = export_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label=_("export_csv"),
            data=csv,
            file_name="quran_tracking_data.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True
        )
    else:
        st.info(_("no_data"))

# ═══════════════════════════════════════════
# TAB 6: BEST MEMORIZERS (WEEKLY)
# ═══════════════════════════════════════════
with tabs[5]:
    st.subheader(_("best_memorizers"))

    sess_for_hifdh = st.selectbox(
        _("select_session"), session_keys,
        key="hifdh_session"
    )
    hifdh_session_id = session_options[sess_for_hifdh]

    top_mems = database.get_top_memorizers(hifdh_session_id, class_name=class_name)
    if top_mems:
        winner = top_mems[0]
        st.success(f"🏆 {_('hifdh_leader')}: **{winner['student_name']}** (فريق {winner['team_name']}) — {winner['hifdh_pages']} صفحة حفظ")

        mem_df = pd.DataFrame([{
            _("rank"): i + 1,
            _("team"): m["team_name"],
            _("student"): m["student_name"],
            "حفظ": m["hifdh_pages"],
            "تلاوة": m["tilawah_pages"],
            "ربط": m["rabt_pages"],
            _("points"): m["points"],
        } for i, m in enumerate(top_mems)])
        st.dataframe(mem_df, use_container_width=True, hide_index=True)

        fig_h, ax_h = plt.subplots()
        names = [m["student_name"] for m in top_mems[:10]]
        pages = [m["hifdh_pages"] for m in top_mems[:10]]
        colors = ["#2ecc71" if i == 0 else "#3498db" for i in range(len(names))]
        ax_h.barh(names[::-1], pages[::-1], color=colors[::-1])
        ax_h.set_xlabel("صفحات حفظ")
        st.pyplot(fig_h)
    else:
        st.info(_("no_memorizers"))

    st.markdown("---")
    st.subheader("أبطال الحفظ عبر الجلسات")

    leaders = database.get_hifdh_leaders_all_sessions(class_name=class_name)
    if leaders:
        leaders_df = pd.DataFrame([{
            "الجلسة": l["label"],
            "التاريخ": l["date"],
            "الطالب": l["student_name"],
            "الفريق": l["team_name"],
            "صفحات حفظ": l["hifdh_pages"],
        } for l in leaders])
        st.dataframe(leaders_df, use_container_width=True, hide_index=True)

        fig_l, ax_l = plt.subplots()
        lbls = [l["label"] for l in leaders]
        pgs = [l["hifdh_pages"] for l in leaders]
        ax_l.plot(lbls, pgs, "o-", color="#2ecc71", linewidth=2.5, markersize=8)
        ax_l.fill_between(range(len(lbls)), pgs, alpha=0.2, color="#2ecc71")
        ax_l.set_ylabel("صفحات حفظ")
        ax_l.set_xlabel("الجلسة")
        for i, l in enumerate(leaders):
            ax_l.annotate(f"{l['student_name']}", (i, l["hifdh_pages"]),
                         textcoords="offset points", xytext=(0, 10), ha="center", fontsize=8)
        plt.xticks(rotation=45)
        st.pyplot(fig_l)
    else:
        st.info(_("no_data"))

# ═══════════════════════════════════════════
# TAB 7: WEEKLY WINNERS
# ═══════════════════════════════════════════
with tabs[6]:
    st.subheader(_("weekly_winners"))
    st.caption(_("weekly_period"))

    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    col_h, col_r = st.columns(2)

    with col_h:
        st.markdown(f"### 🏆 {_('hifdh_leader')}")
        top_hifdh = database.get_weekly_top_hifdh(week_ago, class_name=class_name)
        if top_hifdh:
            winner_h = top_hifdh[0]
            st.success(f"**{winner_h['student_name']}** (فريق {winner_h['team_name']}) — {winner_h['total_hifdh']} صفحة حفظ")

            hifdh_df = pd.DataFrame([{
                _("rank"): i + 1,
                _("student"): r["student_name"],
                _("team"): r["team_name"],
                "حفظ": r["total_hifdh"],
                "ربط": r["total_rabt"],
                _("points"): r["total_points"],
            } for i, r in enumerate(top_hifdh)])
            st.dataframe(hifdh_df, use_container_width=True, hide_index=True)

            fig_h, ax_h = plt.subplots()
            names_h = [r["student_name"] for r in top_hifdh[:10]]
            pages_h = [r["total_hifdh"] for r in top_hifdh[:10]]
            colors_h = ["#2ecc71" if i == 0 else "#3498db" for i in range(len(names_h))]
            ax_h.barh(names_h[::-1], pages_h[::-1], color=colors_h[::-1])
            ax_h.set_xlabel("صفحات حفظ")
            st.pyplot(fig_h)
        else:
            st.info(_("no_memorizers"))

    with col_r:
        st.markdown(f"### 🏆 {_('rabt_leader')}")
        top_rabt = database.get_weekly_top_rabt(week_ago, class_name=class_name)
        if top_rabt:
            winner_r = top_rabt[0]
            st.success(f"**{winner_r['student_name']}** (فريق {winner_r['team_name']}) — {winner_r['total_rabt']} صفحة ربط")

            rabt_df = pd.DataFrame([{
                _("rank"): i + 1,
                _("student"): r["student_name"],
                _("team"): r["team_name"],
                "حفظ": r["total_hifdh"],
                "ربط": r["total_rabt"],
                _("points"): r["total_points"],
            } for i, r in enumerate(top_rabt)])
            st.dataframe(rabt_df, use_container_width=True, hide_index=True)

            fig_r, ax_r = plt.subplots()
            names_r = [r["student_name"] for r in top_rabt[:10]]
            pages_r = [r["total_rabt"] for r in top_rabt[:10]]
            colors_r = ["#e74c3c" if i == 0 else "#9b59b6" for i in range(len(names_r))]
            ax_r.barh(names_r[::-1], pages_r[::-1], color=colors_r[::-1])
            ax_r.set_xlabel("صفحات ربط")
            st.pyplot(fig_r)
        else:
            st.info(_("no_data"))
