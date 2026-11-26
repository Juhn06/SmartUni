"""
Operational business data: schema, draft seed, and scoped queries.
Aligned with nghiepvu (tuyển sinh → lớp → giảng dạy → alumni).
"""
from __future__ import annotations

from datetime import date, timedelta


def ensure_ops_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS admission_rounds ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "code TEXT NOT NULL UNIQUE, "
        "name TEXT NOT NULL, "
        "programs TEXT NOT NULL, "  # comma-separated MBA,MMS,MSCM
        "year INTEGER NOT NULL, "
        "status TEXT NOT NULL DEFAULT 'open', "
        "opened_at TEXT, "
        "closed_at TEXT, "
        "intake TEXT, "  # e.g. May / August (MBA)
        "exam_timeline TEXT, "
        "interview_timeline TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS applications ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "round_id INTEGER NOT NULL, "
        "program_code TEXT NOT NULL, "
        "full_name TEXT NOT NULL, "
        "cccd TEXT, "
        "email TEXT, "
        "phone TEXT, "
        "status TEXT NOT NULL DEFAULT 'submitted', "
        # submitted | approved_ts | interview | passed | failed | paid | official | withdrawn
        "notes TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (round_id) REFERENCES admission_rounds(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS interview_sessions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "round_id INTEGER NOT NULL, "
        "program_code TEXT NOT NULL, "
        "title TEXT NOT NULL, "
        "room TEXT, "
        "starts_at TEXT NOT NULL, "
        "slot_minutes INTEGER DEFAULT 20, "
        "owner TEXT, "
        "FOREIGN KEY (round_id) REFERENCES admission_rounds(id))"
    )
    try:
        cur.execute("ALTER TABLE interview_sessions ADD COLUMN owner TEXT")
    except Exception:
        pass
    cur.execute(
        "CREATE TABLE IF NOT EXISTS interview_slots ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "session_id INTEGER NOT NULL, "
        "application_id INTEGER NOT NULL, "
        "slot_order INTEGER NOT NULL, "
        "scheduled_at TEXT, "
        "score_conclusion TEXT, "
        "result TEXT, "  # pass | fail | pending
        "notes TEXT, "
        "FOREIGN KEY (session_id) REFERENCES interview_sessions(id), "
        "FOREIGN KEY (application_id) REFERENCES applications(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS enrollment_fees ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "application_id INTEGER NOT NULL UNIQUE, "
        "amount REAL DEFAULT 0, "
        "status TEXT NOT NULL DEFAULT 'pending', "  # pending | paid | waived
        "paid_at TEXT, "
        "proof_note TEXT, "
        "FOREIGN KEY (application_id) REFERENCES applications(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS program_versions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "program_code TEXT NOT NULL, "
        "version_code TEXT NOT NULL UNIQUE, "
        "name TEXT NOT NULL, "
        "description TEXT, "
        "is_active INTEGER DEFAULT 1)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS courses ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "program_version_id INTEGER NOT NULL, "
        "code TEXT NOT NULL, "
        "name TEXT NOT NULL, "
        "semester INTEGER DEFAULT 1, "
        "sort_order INTEGER DEFAULT 0, "
        "theory_sessions INTEGER DEFAULT 7, "
        "practice_sessions INTEGER DEFAULT 2, "
        "syllabus_note TEXT, "
        "FOREIGN KEY (program_version_id) REFERENCES program_versions(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS class_groups ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "program_code TEXT NOT NULL, "
        "name TEXT NOT NULL, "
        "program_version_id INTEGER, "
        "cohort_year INTEGER, "
        "status TEXT DEFAULT 'active', "
        "FOREIGN KEY (program_version_id) REFERENCES program_versions(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS class_students ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "class_id INTEGER NOT NULL, "
        "application_id INTEGER, "
        "full_name TEXT NOT NULL, "
        "email TEXT, "
        "FOREIGN KEY (class_id) REFERENCES class_groups(id), "
        "FOREIGN KEY (application_id) REFERENCES applications(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS faculty ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "full_name TEXT NOT NULL, "
        "role_type TEXT NOT NULL, "  # lecturer | expert
        "degree TEXT, "
        "title TEXT, "
        "organization TEXT, "
        "specialty TEXT, "
        "teachable_courses TEXT, "
        "email TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS teaching_assignments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "class_id INTEGER NOT NULL, "
        "course_id INTEGER NOT NULL, "
        "lecturer_id INTEGER, "
        "expert_id INTEGER, "
        "status TEXT DEFAULT 'planned', "
        "FOREIGN KEY (class_id) REFERENCES class_groups(id), "
        "FOREIGN KEY (course_id) REFERENCES courses(id), "
        "FOREIGN KEY (lecturer_id) REFERENCES faculty(id), "
        "FOREIGN KEY (expert_id) REFERENCES faculty(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS attendance_sessions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "assignment_id INTEGER NOT NULL, "
        "session_no INTEGER NOT NULL, "
        "session_label TEXT, "
        "session_date TEXT, "
        "present_count INTEGER DEFAULT 0, "
        "absent_count INTEGER DEFAULT 0, "
        "FOREIGN KEY (assignment_id) REFERENCES teaching_assignments(id))"
    )
    for _tbl, _cols in (
        ("program_versions", (("cohort_no", "TEXT"), ("year_start", "INTEGER"), ("year_end", "INTEGER"))),
        ("class_groups", (("cohort_no", "TEXT"), ("year_start", "INTEGER"), ("year_end", "INTEGER"))),
        ("attendance_sessions", (("room", "TEXT"), ("chapter", "TEXT"))),
    ):
        for _name, _typ in _cols:
            try:
                cur.execute(f"ALTER TABLE {_tbl} ADD COLUMN {_name} {_typ}")
            except Exception:
                pass
    cur.execute(
        "CREATE TABLE IF NOT EXISTS alumni_members ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "full_name TEXT NOT NULL, "
        "program_code TEXT NOT NULL, "
        "cohort TEXT, "
        "class_name TEXT, "
        "email TEXT, "
        "phone TEXT, "
        "company TEXT, "
        "activity_keywords TEXT)"
    )
    try:
        cur.execute("ALTER TABLE alumni_members ADD COLUMN activity_keywords TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE alumni_members ADD COLUMN cccd TEXT")
    except Exception:
        pass
    for _alumni_col, _alumni_spec in (
        ("person_id", "INTEGER"),
        ("learner_id", "INTEGER"),
        ("class_student_id", "INTEGER"),
        ("user_id", "INTEGER"),
        ("portal_login", "TEXT"),
    ):
        try:
            cur.execute(f"ALTER TABLE alumni_members ADD COLUMN {_alumni_col} {_alumni_spec}")
        except Exception:
            pass
    cur.execute(
        "CREATE TABLE IF NOT EXISTS alumni_events ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "event_date TEXT, "
        "location TEXT, "
        "program_filter TEXT, "
        "status TEXT DEFAULT 'planned', "
        "description TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS alumni_event_invitees ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "event_id INTEGER NOT NULL, "
        "alumni_id INTEGER NOT NULL, "
        "invited_at TEXT, "
        "email_status TEXT DEFAULT 'pending', "
        "UNIQUE(event_id, alumni_id), "
        "FOREIGN KEY (event_id) REFERENCES alumni_events(id), "
        "FOREIGN KEY (alumni_id) REFERENCES alumni_members(id))"
    )
    try:
        from practice_homework import ensure_practice_tables

        ensure_practice_tables(cur)
    except Exception:
        pass
    try:
        from mc_quiz import ensure_mc_tables

        ensure_mc_tables(cur)
    except Exception:
        pass


def _scopes_sql(scopes: list[str] | None, column: str = "program_code") -> tuple[str, list]:
    """Return SQL fragment and params for program scope filter."""
    if not scopes or "*" in scopes:
        return "1=1", []
    placeholders = ",".join("?" * len(scopes))
    return f"{column} IN ({placeholders})", list(scopes)


def seed_ops_draft_data(conn) -> dict:
    """Idempotent draft data for demos / UAT."""
    cur = conn.cursor()
    ensure_ops_tables(cur)
    created = {"rounds": 0, "applications": 0, "versions": 0}

    cur.execute("SELECT COUNT(*) FROM admission_rounds")
    if cur.fetchone()[0] == 0:
        rounds = [
            ("TS2026-1", "Tuyển sinh 2026 đợt 1", "MBA,MMS,MSCM", 2026, "open"),
            ("TS2025-2", "Tuyển sinh 2025 đợt 2", "MMS,MSCM", 2025, "closed"),
        ]
        for code, name, programs, year, status in rounds:
            cur.execute(
                "INSERT INTO admission_rounds (code, name, programs, year, status, opened_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (code, name, programs, year, status, date.today().isoformat()),
            )
            created["rounds"] += 1

    cur.execute("SELECT id FROM admission_rounds WHERE code = 'TS2026-1'")
    round_row = cur.fetchone()
    round_id = round_row[0] if round_row else None

    cur.execute("SELECT COUNT(*) FROM applications")
    if cur.fetchone()[0] == 0 and round_id:
        apps = [
            ("MSCM", "Nguyễn Văn An", "001234567890", "an.nv@email.com", "0901000001", "approved_ts", "Đủ hồ sơ"),
            ("MSCM", "Trần Thị Bình", "001234567891", "binh.tt@email.com", "0901000002", "interview", ""),
            ("MSCM", "Lê Minh Châu", "001234567892", "chau.lm@email.com", "0901000003", "passed", "Đỗ PV"),
            ("MSCM", "Phạm Quốc Dũng", "001234567893", "dung.pq@email.com", "0901000004", "paid", "Đã nộp phí"),
            ("MMS", "Hoàng Thu Hà", "001234567894", "ha.ht@email.com", "0901000005", "approved_ts", ""),
            ("MMS", "Vũ Đức Khoa", "001234567895", "khoa.vd@email.com", "0901000006", "passed", ""),
            ("MMS", "Đặng Mỹ Linh", "001234567896", "linh.dm@email.com", "0901000007", "official", "Trúng tuyển chính thức"),
            ("MBA", "Ngô Thanh Mai", "001234567897", "mai.nt@email.com", "0901000008", "submitted", ""),
            ("MBA", "Bùi Hải Nam", "001234567898", "nam.bh@email.com", "0901000009", "passed", ""),
            ("MBA", "Đỗ Lan Phương", "001234567899", "phuong.dl@email.com", "0901000010", "withdrawn", "Có kế hoạch khác"),
        ]
        for prog, name, cccd, email, phone, status, notes in apps:
            cur.execute(
                "INSERT INTO applications "
                "(round_id, program_code, full_name, cccd, email, phone, status, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (round_id, prog, name, cccd, email, phone, status, notes),
            )
            created["applications"] += 1
            app_id = cur.lastrowid
            if status in ("passed", "paid", "official"):
                fee_status = "paid" if status in ("paid", "official") else "pending"
                cur.execute(
                    "INSERT INTO enrollment_fees (application_id, amount, status, paid_at, proof_note) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        app_id,
                        15000000,
                        fee_status,
                        date.today().isoformat() if fee_status == "paid" else None,
                        "Chuyển khoản VCB" if fee_status == "paid" else None,
                    ),
                )

    cur.execute("SELECT COUNT(*) FROM interview_sessions")
    if cur.fetchone()[0] == 0 and round_id:
        start = (date.today() + timedelta(days=7)).isoformat() + " 09:00"
        for prog, title, room in (
            ("MSCM", "PV MSCM buổi 1", "P.201"),
            ("MMS", "PV MMS buổi 1", "P.202"),
            ("MBA", "PV MBA buổi 1", "P.301"),
        ):
            cur.execute(
                "INSERT INTO interview_sessions "
                "(round_id, program_code, title, room, starts_at, slot_minutes, owner) "
                "VALUES (?, ?, ?, ?, ?, 20, ?)",
                (round_id, prog, title, room, start, "Điều phối CT"),
            )
            session_id = cur.lastrowid
            cur.execute(
                "SELECT id, full_name FROM applications "
                "WHERE round_id = ? AND program_code = ? AND status IN ('approved_ts','interview','passed') "
                "LIMIT 4",
                (round_id, prog),
            )
            for i, (app_id, _) in enumerate(cur.fetchall(), start=1):
                cur.execute(
                    "INSERT INTO interview_slots "
                    "(session_id, application_id, slot_order, scheduled_at, result) "
                    "VALUES (?, ?, ?, ?, 'pending')",
                    (session_id, app_id, i, start),
                )

    cur.execute("SELECT COUNT(*) FROM program_versions")
    if cur.fetchone()[0] == 0:
        versions = [
            ("MSCM", "MSCM_2026", "MSCM Khóa 2026", "Phiên bản khung chương trình MSCM 2026"),
            ("MSCM", "MSCM_Khoa_10", "MSCM Khóa 10", "Bản sao từ khóa trước"),
            ("MMS", "MMS_Khoa_21", "MMS Cohort 21", "Copy of Cohort 20 — class 2026"),
            ("MMS", "MMS_Khoa_20", "MMS Cohort 20", "15 modules, 60 ECTS, 4 semesters"),
            ("MBA", "MBA_K34", "MBA Khóa 34", "MBA cohort K34 — 4 semesters, ~8 sessions/course"),
        ]
        for prog, vcode, name, desc in versions:
            cur.execute(
                "INSERT INTO program_versions (program_code, version_code, name, description) "
                "VALUES (?, ?, ?, ?)",
                (prog, vcode, name, desc),
            )
            created["versions"] += 1
            vid = cur.lastrowid
            if prog == "MSCM":
                course_list = [
                    (1, "MSCM101", "Supply Chain Strategy", 1),
                    (2, "MSCM102", "Logistics Management", 1),
                    (3, "MSCM201", "Procurement", 2),
                    (4, "MSCM202", "Inventory Analytics", 2),
                    (5, "MSCM301", "Capstone / Thesis", 3),
                ]
                theory_n, practice_n = 7, 2
            elif prog == "MMS":
                course_list = [
                    (1, "MMS101", "Marketing Strategy", 1),
                    (2, "MMS102", "Sales Management", 1),
                    (3, "MMS201", "Digital Marketing", 2),
                    (4, "MMS202", "Brand Management", 2),
                    (5, "MMS301", "Thesis", 4),
                ]
                theory_n, practice_n = 7, 2
            else:
                # MBA: richer 4-semester structure; 8 sessions per course
                course_list = [
                    (1, "MBA101", "Leadership & Organizational Behavior", 1),
                    (2, "MBA102", "Finance for Managers", 1),
                    (3, "MBA103", "Marketing Management", 1),
                    (4, "MBA201", "Corporate Strategy", 2),
                    (5, "MBA202", "Operations Management", 2),
                    (6, "MBA203", "Managerial Accounting", 2),
                    (7, "MBA301", "Digital Transformation", 3),
                    (8, "MBA302", "International Business", 3),
                    (9, "MBA303", "HR & Talent Management", 3),
                    (10, "MBA401", "Capstone / Consulting Project", 4),
                ]
                theory_n, practice_n = 8, 0
            for sort, code, cname, sem in course_list:
                cur.execute(
                    "INSERT INTO courses "
                    "(program_version_id, code, name, semester, sort_order, theory_sessions, practice_sessions) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (vid, code, cname, sem, sort, theory_n, practice_n),
                )

    cur.execute("SELECT COUNT(*) FROM class_groups")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id, program_code, version_code FROM program_versions")
        by_prog: dict[str, int] = {}
        by_code: dict[str, int] = {}
        for vid, prog, vcode in cur.fetchall():
            by_code[vcode] = vid
            by_prog.setdefault(prog, vid)
        preferred = {"MMS": "MMS_Khoa_21", "MBA": "MBA_K34", "MSCM": "MSCM_2026"}
        for prog, cname, year in (
            ("MSCM", "MSCM 2026", 2026),
            ("MMS", "MMS K21", 2026),
            ("MBA", "MBA 2026", 2026),
        ):
            vid = by_code.get(preferred.get(prog, "")) or by_prog.get(prog)
            cur.execute(
                "INSERT INTO class_groups (program_code, name, program_version_id, cohort_year, status) "
                "VALUES (?, ?, ?, ?, 'active')",
                (prog, cname, vid, year),
            )
            class_id = cur.lastrowid
            cur.execute(
                "SELECT id, full_name, email FROM applications "
                "WHERE program_code = ? AND status IN ('official','paid')",
                (prog,),
            )
            for app_id, full_name, email in cur.fetchall():
                cur.execute(
                    "INSERT INTO class_students (class_id, application_id, full_name, email) "
                    "VALUES (?, ?, ?, ?)",
                    (class_id, app_id, full_name, email),
                )

    cur.execute("SELECT COUNT(*) FROM faculty")
    if cur.fetchone()[0] == 0:
        faculty_rows = [
            ("Prof. Jean Dupont", "lecturer", "PhD", "GS", "ESCP", "Supply Chain", "MSCM101,MSCM102", "j.dupont@escp.eu"),
            ("Dr. Marie Curie", "lecturer", "PhD", "PGS", "X", "Marketing", "MMS101,MMS201", "m.curie@x.edu"),
            ("Nguyễn Văn Chuyên", "expert", "ThS", "", "ABC Corp", "Logistics", "MSCM102", "chuyen@abc.vn"),
            ("Trần Thị Sales", "expert", "ThS", "", "XYZ Retail", "Sales", "MMS102", "sales@xyz.vn"),
            ("Prof. Alan Smith", "lecturer", "PhD", "GS", "ESCP", "Strategy", "MBA201", "a.smith@escp.eu"),
        ]
        for row in faculty_rows:
            cur.execute(
                "INSERT INTO faculty "
                "(full_name, role_type, degree, title, organization, specialty, teachable_courses, email) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )

    cur.execute("SELECT COUNT(*) FROM teaching_assignments")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id, program_code FROM class_groups")
        classes = list(cur.fetchall())
        for class_id, prog in classes:
            cur.execute(
                "SELECT c.id FROM courses c "
                "JOIN program_versions v ON v.id = c.program_version_id "
                "WHERE v.program_code = ? ORDER BY c.sort_order LIMIT 3",
                (prog,),
            )
            course_ids = [r[0] for r in cur.fetchall()]
            cur.execute(
                "SELECT id FROM faculty WHERE role_type = 'lecturer' LIMIT 1"
            )
            lec = cur.fetchone()
            cur.execute("SELECT id FROM faculty WHERE role_type = 'expert' LIMIT 1")
            exp = cur.fetchone()
            for cid in course_ids:
                cur.execute(
                    "INSERT INTO teaching_assignments "
                    "(class_id, course_id, lecturer_id, expert_id, status) "
                    "VALUES (?, ?, ?, ?, 'assigned')",
                    (class_id, cid, lec[0] if lec else None, exp[0] if exp else None),
                )
                aid = cur.lastrowid
                for sn in range(1, 4):
                    cur.execute(
                        "INSERT INTO attendance_sessions "
                        "(assignment_id, session_no, session_label, session_date, present_count, absent_count) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            aid,
                            sn,
                            f"Buổi {sn}",
                            (date.today() + timedelta(days=sn * 7)).isoformat(),
                            12,
                            2,
                        ),
                    )

    cur.execute("SELECT COUNT(*) FROM alumni_members")
    if cur.fetchone()[0] == 0:
        alumni = [
            ("Lê Quốc Việt", "MSCM", "K9", "MSCM K9", "viet.lq@alumni.x", "0912000001", "Vinamilk"),
            ("Phạm Thu Trang", "MMS", "K19", "MMS K19", "trang.pt@alumni.x", "0912000002", "Unilever"),
            ("Hoàng Minh Tuấn", "MBA", "2023", "MBA 2023", "tuan.hm@alumni.x", "0912000003", "Viettel"),
        ]
        for row in alumni:
            cur.execute(
                "INSERT INTO alumni_members "
                "(full_name, program_code, cohort, class_name, email, phone, company) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                row,
            )
        cur.execute(
            "INSERT INTO alumni_events (title, event_date, location, program_filter, status, description) "
            "VALUES (?, ?, ?, ?, 'planned', ?)",
            (
                "X Alumni Networking 2026",
                (date.today() + timedelta(days=45)).isoformat(),
                "Hà Nội",
                "*",
                "Gặp mặt cựu học viên toàn chương trình",
            ),
        )
        cur.execute(
            "INSERT INTO alumni_events (title, event_date, location, program_filter, status, description) "
            "VALUES (?, ?, ?, ?, 'planned', ?)",
            (
                "MSCM Industry Talk",
                (date.today() + timedelta(days=30)).isoformat(),
                "X HN",
                "MSCM",
                "Chia sẻ thực tiễn chuỗi cung ứng",
            ),
        )

    conn.commit()
    return created


def format_cohort_label(cohort_no=None, year_start=None, year_end=None, cohort_year=None) -> str:
    """Khóa 21 – 2026–2028. Năm 4 chữ số không bị hiểu nhầm thành số khóa."""
    no = str(cohort_no or "").strip()
    ys = str(year_start or "").strip()
    ye = str(year_end or "").strip()
    raw_year = str(cohort_year or "").strip()
    if raw_year.isdigit() and len(raw_year) == 4:
        ys = ys or raw_year
    elif raw_year and not no:
        no = raw_year
    if no and ys and ye:
        return f"Khóa {no} – {ys}–{ye}"
    if no and ys:
        return f"Khóa {no} – {ys}"
    if ys and ye:
        return f"{ys}–{ye}"
    if no:
        return f"Khóa {no}"
    return ys


def list_with_scope(cur, sql: str, scopes: list[str] | None, scope_column: str, params: list | None = None):
    frag, sp = _scopes_sql(scopes, scope_column)
    params = list(params or []) + sp
    # Inject scope into WHERE: sql must contain {scope}
    return cur.execute(sql.replace("{scope}", frag), params).fetchall()
