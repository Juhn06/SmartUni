"""
Coordinator program ops — fields aligned with nghiepvu sample Excels:
1) Candidate profile (danh sách thí sinh)
2) Interview jury scores
3) Course grade matrix
4) Thesis / CP defense tracking
"""
from __future__ import annotations

from datetime import date
from typing import Any


APP_PROFILE_COLUMNS = [
    ("campus", "TEXT"),
    ("cfvg_app_no", "TEXT"),
    ("gender", "TEXT"),
    ("dob", "TEXT"),
    ("university", "TEXT"),
    ("degree_major", "TEXT"),
    ("study_duration", "TEXT"),
    ("degree_grade", "TEXT"),
    ("experience_years", "REAL"),
    ("credit_hours", "REAL"),
    ("english_cert", "TEXT"),
    ("company", "TEXT"),
    ("job_title", "TEXT"),
    ("interview_date", "TEXT"),
    ("final_result", "TEXT"),
    # Checklist / đảm bảo chất lượng đầu vào (Admission Process — TS)
    ("lead_source", "TEXT"),  # facebook | zalo | call | event | marcom | other
    ("checklist_status", "TEXT"),  # pending | issued | confirmed | incomplete
    ("degree_verified", "TEXT"),  # pending | yes | no
    ("english_verified", "TEXT"),  # pending | yes | no
    ("neu_packet_ready", "TEXT"),  # pending | yes | no — sẵn sàng nộp TT/Khảo thí NEU
    ("no_show", "TEXT"),  # '' | yes — Admin cập nhật không đến PV → TS biết
    ("no_response", "TEXT"),  # '' | yes — Admin: không phản hồi sau deadline thi/PV
    ("checklist_received_by", "TEXT"),  # người TS ký checklist gửi ứng viên (Nhung / Giao)
    ("chk_degree", "TEXT"),  # x | incompleted | exempted | not_required
    ("chk_transcript", "TEXT"),
    ("chk_cv", "TEXT"),
    ("chk_motivation", "TEXT"),
    ("chk_reference", "TEXT"),
    ("chk_id", "TEXT"),
    ("chk_web", "TEXT"),
    ("chk_english", "TEXT"),
    ("chk_fee", "TEXT"),
    ("chk_naric", "TEXT"),
    ("chk_other", "TEXT"),
    ("thanh_tra_status", "TEXT"),  # not_sent | sent | received — Thanh tra Pháp chế
    ("khao_thi_status", "TEXT"),  # not_sent | sent | received — Khảo thí (minh chứng TA)
    ("htqt_status", "TEXT"),  # not_sent | sent | received — phòng HTQT
    ("neu_doc_status", "TEXT"),  # not_sent | sent | received — văn bản NEU đã cấp
    ("english_cert_type", "TEXT"),
    ("english_cert_no", "TEXT"),
    ("english_cert_date", "TEXT"),
    ("english_cert_score", "TEXT"),
    ("degree_issuer", "TEXT"),
    ("degree_country", "TEXT"),
    ("degree_year", "TEXT"),
    ("degree_years_studied", "TEXT"),
    ("degree_mode", "TEXT"),
    ("degree_foreign_confirmed", "TEXT"),
    ("needs_verification", "TEXT"),
    ("inspect_khao_thi", "TEXT"),
    ("inspect_thanh_tra", "TEXT"),
    ("inspect_partner", "TEXT"),
    ("eligible_for_admit", "TEXT"),
    ("admit_decided_by", "TEXT"),
    ("admit_decided_at", "TEXT"),
    ("passport", "TEXT"),
    ("withdraw_reason", "TEXT"),
]

STUDENT_EXTRA_COLUMNS = [
    ("student_code", "TEXT"),
    ("dob", "TEXT"),
    ("gender", "TEXT"),
    ("graduated_at", "TEXT"),
    ("observations", "TEXT"),
]

PROFILE_EDITABLE = {c[0] for c in APP_PROFILE_COLUMNS} | {
    "full_name", "email", "phone", "cccd", "notes", "program_code", "status",
    "written_score", "written_exam_no", "written_exam_date",
    "written_exam_room", "written_exam_session",
    # MBA34 roster / exam fields (Điều phối)
    "intake_session", "student_code_mba", "eco_background", "master_level",
    "bachelor_start_year", "bachelor_grad_year", "job_title", "management_years",
    "english_note", "naric_status", "naric_note", "exam_eligible_flag",
    "other_achievements", "interview_score", "interview_jury1", "interview_jury2",
    "interview_jury3", "written_gk", "written_mle", "avg_score",
    "confirmation_status", "board_decision",
    "exam_format", "exam_board", "admitted_program",
    "english_cert_type", "english_cert_no", "english_cert_date", "english_cert_score",
    "degree_issuer", "degree_country", "degree_year", "degree_years_studied",
    "degree_mode", "degree_foreign_confirmed",
    "needs_verification", "inspect_khao_thi", "inspect_thanh_tra", "inspect_partner",
    "eligible_for_admit", "admit_decided_by", "admit_decided_at", "passport",
}

WITHDRAW_REASONS = {
    "degree_unconfirmed": "Hồ sơ không phù hợp (không xác nhận văn bằng)",
    "other_plan": "Có kế hoạch khác",
}

GRADE_SCHEMES = {
    "40_60": (("Đầu điểm 1", 40), ("Đầu điểm 2", 60)),
    "50_50": (("Đầu điểm 1", 50), ("Đầu điểm 2", 50)),
}

CHECKLIST_STATUS_VALUES = {"pending", "issued", "confirmed", "incomplete"}
VERIFY_VALUES = {"pending", "yes", "no"}

APP_STATUS_VALUES = {
    "submitted",
    "approved_ts",
    "interview",
    "passed",
    "failed",
    "paid",
    "official",
    "withdrawn",
}

FINAL_RESULT_BY_STATUS = {
    "passed": "Admitted",
    "paid": "Admitted",
    "official": "Admitted",
    "failed": "Non-Admitted",
}


def _table_cols(cur, table: str) -> set[str]:
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_missing_columns(cur, table: str, columns: list[tuple[str, str]]) -> None:
    existing = _table_cols(cur, table)
    for name, typ in columns:
        if name not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")


def ensure_coord_tables(cur) -> None:
    from ops_data import ensure_ops_tables
    from mba_ops import ensure_mba_tables

    ensure_ops_tables(cur)
    _add_missing_columns(cur, "applications", APP_PROFILE_COLUMNS)
    _add_missing_columns(cur, "class_students", STUDENT_EXTRA_COLUMNS)

    cur.execute(
        "CREATE TABLE IF NOT EXISTS interview_scores ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "slot_id INTEGER NOT NULL, "
        "jury_name TEXT NOT NULL, "
        "score TEXT, "
        "sort_order INTEGER DEFAULT 0, "
        "note TEXT, "
        "FOREIGN KEY (slot_id) REFERENCES interview_slots(id))"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_interview_scores_slot "
        "ON interview_scores(slot_id)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS scholarship_basis ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "program_code TEXT NOT NULL, "
        "course_id INTEGER NOT NULL, "
        "UNIQUE(program_code, course_id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS course_grades ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "class_id INTEGER NOT NULL, "
        "student_id INTEGER NOT NULL, "
        "course_id INTEGER NOT NULL, "
        "score REAL, "
        "locked INTEGER DEFAULT 0, "
        "observations TEXT, "
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "UNIQUE(class_id, student_id, course_id), "
        "FOREIGN KEY (class_id) REFERENCES class_groups(id), "
        "FOREIGN KEY (student_id) REFERENCES class_students(id), "
        "FOREIGN KEY (course_id) REFERENCES courses(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS grade_components ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "class_id INTEGER NOT NULL, "
        "course_id INTEGER NOT NULL, "
        "name TEXT NOT NULL, "
        "weight_pct REAL NOT NULL, "
        "sort_order INTEGER NOT NULL, "
        "UNIQUE(class_id, course_id, sort_order), "
        "FOREIGN KEY (class_id) REFERENCES class_groups(id), "
        "FOREIGN KEY (course_id) REFERENCES courses(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS grade_component_scores ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "component_id INTEGER NOT NULL, "
        "student_id INTEGER NOT NULL, "
        "score REAL, "
        "UNIQUE(component_id, student_id), "
        "FOREIGN KEY (component_id) REFERENCES grade_components(id), "
        "FOREIGN KEY (student_id) REFERENCES class_students(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS course_grade_attempts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "grade_id INTEGER, "
        "class_id INTEGER NOT NULL, "
        "student_id INTEGER NOT NULL, "
        "course_id INTEGER NOT NULL, "
        "attempt_no INTEGER NOT NULL, "
        "group_assignment REAL, "
        "final_exam REAL, "
        "score REAL, "
        "published INTEGER DEFAULT 0, "
        "created_at TEXT, "
        "created_by TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS thesis_records ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "class_id INTEGER, "
        "student_id INTEGER, "
        "program_code TEXT NOT NULL, "
        "full_name TEXT NOT NULL, "
        "email TEXT, "
        "gender TEXT, "
        "cp_number TEXT, "
        "title TEXT, "
        "tutor TEXT, "
        "payment_status TEXT, "
        "turnitin_pct REAL, "
        "ai_pct REAL, "
        "jury_host TEXT, "
        "jury_member_1 TEXT, "
        "jury_member_2 TEXT, "
        "defense_date TEXT, "
        "defense_time TEXT, "
        "room TEXT, "
        "total_grade REAL, "
        "status TEXT DEFAULT 'draft', "
        "notes TEXT, "
        "FOREIGN KEY (class_id) REFERENCES class_groups(id), "
        "FOREIGN KEY (student_id) REFERENCES class_students(id))"
    )
    # MBA columns / attendance_marks after base tables exist
    ensure_mba_tables(cur)
    _backfill_grade_attempts(cur)


def seed_coord_enrichment(conn) -> dict:
    """Backfill profile / scores / grades / thesis for demos (idempotent)."""
    cur = conn.cursor()
    ensure_coord_tables(cur)
    out = {"profiles": 0, "interview_scores": 0, "grades": 0, "thesis": 0}

    # Backfill candidate profile sample fields
    cur.execute(
        "SELECT id, program_code, full_name FROM applications "
        "WHERE campus IS NULL OR campus = '' LIMIT 50"
    )
    samples = {
        "MSCM": ("HN", "CAN36001", "NEU", "Supply Chain", "4 Years", "Good", 5, "IELTS"),
        "MMS": ("HN", "CAN36757", "UEH", "Marketing", "4 Years", "Passable", 8, "IELTS"),
        "MBA": ("HCM", "CAN36100", "FTU", "Business Admin", "4 Years", "Good", 10, "TOEIC"),
    }
    for i, (aid, prog, name) in enumerate(cur.fetchall()):
        camp, pref, uni, major, dur, grade, exp, eng = samples.get(
            prog, ("HN", "CAN36000", "NEU", "Management", "4 Years", "Good", 3, "IELTS")
        )
        gender = "F" if i % 2 else "M"
        cur.execute(
            "UPDATE applications SET campus=?, cfvg_app_no=?, gender=?, dob=?, "
            "university=?, degree_major=?, study_duration=?, degree_grade=?, "
            "experience_years=?, english_cert=?, company=?, "
            "interview_date=COALESCE(NULLIF(interview_date,''), ?), "
            "final_result=CASE WHEN status IN ('passed','paid','official') THEN 'Admitted' "
            "WHEN status='failed' THEN 'Non-Admitted' ELSE final_result END "
            "WHERE id=?",
            (
                camp,
                f"{pref}{aid:02d}",
                gender,
                f"199{i % 10}-0{(i % 9)+1}-15",
                uni,
                major,
                dur,
                grade,
                float(exp),
                eng,
                f"Company {aid}",
                date.today().isoformat(),
                aid,
            ),
        )
        out["profiles"] += 1

    # Interview jury scores
    cur.execute("SELECT COUNT(*) FROM interview_scores")
    if cur.fetchone()[0] == 0:
        juries = [
            "Prof. Jean Pierre Helfer",
            "Dr. Hoang Thi Thu Phuong",
            "Ms. Nguyen Thi Lan Phuong",
        ]
        cur.execute("SELECT id FROM interview_slots")
        for slot_id in [r[0] for r in cur.fetchall()]:
            for j, jury in enumerate(juries):
                score = ["A", "B", "A"][j % 3]
                cur.execute(
                    "INSERT INTO interview_scores (slot_id, jury_name, score, sort_order) "
                    "VALUES (?, ?, ?, ?)",
                    (slot_id, jury, score, j),
                )
                out["interview_scores"] += 1
            cur.execute(
                "UPDATE interview_slots SET score_conclusion = 'A', result = 'pass' "
                "WHERE id = ? AND (result IS NULL OR result = 'pending')",
                (slot_id,),
            )

    # Student codes on class_students
    cur.execute(
        "SELECT cs.id, cg.program_code, cg.cohort_year FROM class_students cs "
        "JOIN class_groups cg ON cg.id = cs.class_id "
        "WHERE cs.student_code IS NULL OR cs.student_code = ''"
    )
    for sid, prog, year in cur.fetchall():
        y = str(year or 2026)[-2:]
        cur.execute(
            "UPDATE class_students SET student_code=?, gender=COALESCE(gender,'F'), "
            "dob=COALESCE(dob,'1995-06-01') WHERE id=?",
            (f"{prog}{y}HN{sid:03d}", sid),
        )

    # Course grades matrix sample
    cur.execute("SELECT COUNT(*) FROM course_grades")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id, program_version_id FROM class_groups")
        for class_id, pvid in cur.fetchall():
            if not pvid:
                continue
            cur.execute(
                "SELECT id FROM courses WHERE program_version_id = ? ORDER BY sort_order",
                (pvid,),
            )
            course_ids = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT id FROM class_students WHERE class_id = ?", (class_id,))
            for student_id in [r[0] for r in cur.fetchall()]:
                for i, cid in enumerate(course_ids):
                    score = round(10 + (student_id + i) % 8 + (i % 3) * 0.25, 2)
                    cur.execute(
                        "INSERT OR IGNORE INTO course_grades "
                        "(class_id, student_id, course_id, score, locked) "
                        "VALUES (?, ?, ?, ?, 0)",
                        (class_id, student_id, cid, score),
                    )
                    out["grades"] += 1

    # Thesis / CP tracking
    cur.execute("SELECT COUNT(*) FROM thesis_records")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "SELECT cs.id, cs.class_id, cs.full_name, cs.email, cs.gender, cs.student_code, "
            "cg.program_code FROM class_students cs "
            "JOIN class_groups cg ON cg.id = cs.class_id LIMIT 12"
        )
        for i, (sid, cid, name, email, gender, scode, prog) in enumerate(cur.fetchall()):
            cur.execute(
                "INSERT INTO thesis_records "
                "(class_id, student_id, program_code, full_name, email, gender, cp_number, "
                "title, tutor, payment_status, turnitin_pct, ai_pct, jury_host, "
                "jury_member_1, jury_member_2, defense_date, defense_time, room, "
                "total_grade, status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    cid,
                    sid,
                    prog,
                    name,
                    email,
                    gender or "F",
                    scode or f"{prog}CP{i+1:03d}",
                    f"Case study: strategic development — {name}",
                    "Jean-Pierre Helfer" if i % 2 == 0 else "Prof. Jean Dupont",
                    "Da thanh toan" if i % 3 else "Cho thanh toan",
                    round(0.05 + (i % 5) * 0.02, 2),
                    float(i % 3),
                    "Prof. Dr. Jean Pierre Helfer",
                    "GS.TS. Nguyễn Thị Tuyết Mai",
                    "Ms. Vu Mai Anh",
                    (date.today().replace(month=3, day=10 + (i % 10))).isoformat()
                    if hasattr(date.today(), "replace")
                    else date.today().isoformat(),
                    f"{13 + (i % 3)}:30-{14 + (i % 3)}:15",
                    str(1210 + i),
                    round(14 + (i % 5) * 0.5, 1) if i % 4 else None,
                    "scheduled" if i % 4 else "draft",
                ),
            )
            out["thesis"] += 1

    try:
        from mba_ops import seed_mba34_demo

        out["mba34"] = seed_mba34_demo(conn)
    except Exception as e:
        out["mba34_error"] = str(e)
    try:
        from mms_program import seed_mms_program

        out["mms"] = seed_mms_program(conn)
    except Exception as e:
        out["mms_error"] = str(e)
    try:
        from e2e_pipeline import seed_e2e_pipeline

        out["e2e"] = seed_e2e_pipeline(conn)
    except Exception as e:
        out["e2e_error"] = str(e)

    conn.commit()
    return out


# ── Applications profile ─────────────────────────────────────────────

def application_dict(row, cols: list[str]) -> dict:
    return {cols[i]: row[i] for i in range(len(cols))}


def list_applications_enriched(
    conn,
    scopes: list[str] | None,
    *,
    q: str = "",
    status: str = "",
    role_mode: str = "all",
    decision: bool = False,
    round_id: int | None = None,
    intake_session: str = "",
    neu_prep: bool = False,
    campuses: list[str] | None = None,
    dossier_status: str = "",
    selection_status: str = "",
) -> list[dict]:
    from ops_data import _scopes_sql
    from status_catalog import drop_watch_or_qa_status
    from workflow_links import ACCOUNTING_FOCUS_STATUSES, COORDINATOR_VISIBLE_STATUSES

    status = drop_watch_or_qa_status(status)

    cur = conn.cursor()
    ensure_coord_tables(cur)
    frag, params = _scopes_sql(scopes, "a.program_code")
    sql = (
        "SELECT a.id, a.round_id, a.program_code, a.full_name, a.cccd, a.email, a.phone, a.status, a.notes, "
        "r.code AS round_code, r.name AS round_name, "
        "a.campus, a.cfvg_app_no, a.gender, a.dob, a.university, a.degree_major, "
        "a.study_duration, a.degree_grade, a.experience_years, a.credit_hours, "
        "a.english_cert, a.company, a.interview_date, a.final_result, "
        "a.written_score, a.written_exam_no, a.written_exam_date, "
        "a.written_exam_room, a.written_exam_session, "
        "a.transferred_at, a.transferred_by, "
        "a.lead_source, a.checklist_status, a.degree_verified, a.english_verified, "
        "a.neu_packet_ready, a.no_show, "
        "a.intake_session, a.student_code_mba, a.eco_background, a.master_level, "
        "a.bachelor_start_year, a.bachelor_grad_year, a.job_title, a.management_years, "
        "a.english_note, a.naric_status, a.naric_note, a.exam_eligible_flag, "
        "a.other_achievements, a.interview_score, a.interview_jury1, a.interview_jury2, "
        "a.interview_jury3, a.written_gk, a.written_mle, a.avg_score, "
        "a.confirmation_status, a.board_decision, "
        "a.exam_format, a.exam_board, a.admitted_program, "
        "IFNULL(a.no_response,''), IFNULL(a.checklist_received_by,''), "
        "IFNULL(a.chk_degree,''), IFNULL(a.chk_transcript,''), IFNULL(a.chk_cv,''), "
        "IFNULL(a.chk_motivation,''), IFNULL(a.chk_reference,''), IFNULL(a.chk_id,''), "
        "IFNULL(a.chk_web,''), IFNULL(a.chk_english,''), IFNULL(a.chk_fee,''), "
        "IFNULL(a.chk_naric,''), IFNULL(a.chk_other,''), "
        "IFNULL(a.thanh_tra_status,''), IFNULL(a.khao_thi_status,''), "
        "IFNULL(a.htqt_status,''), IFNULL(a.neu_doc_status,''), "
        "IFNULL(a.withdraw_reason,''), IFNULL(a.english_cert_score,'') "
        "FROM applications a JOIN admission_rounds r ON r.id = a.round_id "
        f"WHERE {frag}"
    )
    if role_mode == "coordinator":
        placeholders = ",".join("?" * len(COORDINATOR_VISIBLE_STATUSES))
        sql += f" AND a.status IN ({placeholders})"
        params.extend(sorted(COORDINATOR_VISIBLE_STATUSES))
    elif role_mode == "accounting":
        placeholders = ",".join("?" * len(ACCOUNTING_FOCUS_STATUSES))
        sql += f" AND a.status IN ({placeholders})"
        params.extend(sorted(ACCOUNTING_FOCUS_STATUSES))
    if decision and not status:
        # Kết quả TS: đỗ / trượt / đã nộp phí / official (sau quyết định hội đồng)
        sql += " AND a.status IN ('passed','failed','paid','official')"
    if status:
        sql += " AND a.status = ?"
        params.append(status)
    if round_id:
        sql += " AND a.round_id = ?"
        params.append(round_id)
    if intake_session:
        sql += " AND a.intake_session = ?"
        params.append(intake_session)
    if neu_prep:
        sql += " AND a.status IN ('passed','paid','official')"
    if q:
        sql += (
            " AND (a.full_name LIKE ? OR a.email LIKE ? OR a.cccd LIKE ? "
            "OR IFNULL(a.cfvg_app_no,'') LIKE ? OR IFNULL(a.company,'') LIKE ? "
            "OR IFNULL(a.student_code_mba,'') LIKE ? OR IFNULL(a.job_title,'') LIKE ? "
            "OR a.program_code LIKE ? OR r.code LIKE ? OR a.status LIKE ? "
            "OR IFNULL(a.final_result,'') LIKE ?)"
        )
        params.extend([f"%{q}%"] * 11)
    sql += " ORDER BY a.id DESC"
    rows = cur.execute(sql, params).fetchall()
    keys = [
        "id", "round_id", "program_code", "full_name", "cccd", "email", "phone", "status", "notes",
        "round_code", "round_name", "campus", "cfvg_app_no", "gender", "dob",
        "university", "degree_major", "study_duration", "degree_grade",
        "experience_years", "credit_hours", "english_cert", "company",
        "interview_date", "final_result",
        "written_score", "written_exam_no", "written_exam_date",
        "written_exam_room", "written_exam_session",
        "transferred_at", "transferred_by",
        "lead_source", "checklist_status", "degree_verified", "english_verified",
        "neu_packet_ready", "no_show",
        "intake_session", "student_code_mba", "eco_background", "master_level",
        "bachelor_start_year", "bachelor_grad_year", "job_title", "management_years",
        "english_note", "naric_status", "naric_note", "exam_eligible_flag",
        "other_achievements", "interview_score", "interview_jury1", "interview_jury2",
        "interview_jury3", "written_gk", "written_mle", "avg_score",
        "confirmation_status", "board_decision",
        "exam_format", "exam_board", "admitted_program",
        "no_response", "checklist_received_by",
        "chk_degree", "chk_transcript", "chk_cv", "chk_motivation", "chk_reference",
        "chk_id", "chk_web", "chk_english", "chk_fee", "chk_naric", "chk_other",
        "thanh_tra_status", "khao_thi_status", "htqt_status", "neu_doc_status",
        "withdraw_reason", "english_cert_score",
    ]
    from admission_ops import attach_application_doc_summary, enrich_sibling_programs

    packed = []
    for r in rows:
        item = dict(zip(keys, r))
        status = (item.get("status") or "").strip()
        cccd = str(item.get("cccd") or "").strip()
        student_code = str(item.get("student_code_mba") or "").strip()
        item["identifier"] = student_code if status == "official" and student_code else (cccd or item.get("cfvg_app_no") or "")
        packed.append(item)
    out = attach_application_doc_summary(conn, enrich_sibling_programs(packed))
    axis_cols = {
        r[1] for r in cur.execute("PRAGMA table_info(applications)").fetchall()
    }
    if out and {"dossier_status", "selection_status", "decision_status", "response_status", "sitting_status"} <= axis_cols:
        ids = [int(r["id"]) for r in out if r.get("id")]
        ph = ",".join("?" * len(ids))
        extra = {
            int(r[0]): {
                "dossier_status": r[1] or "",
                "sitting_status": r[2] or "",
                "selection_status": r[3] or "",
                "decision_status": r[4] or "",
                "response_status": r[5] or "",
                "result_reserve_status": r[6] or "",
            }
            for r in cur.execute(
                "SELECT id, IFNULL(dossier_status,''), IFNULL(sitting_status,''), "
                "IFNULL(selection_status,''), IFNULL(decision_status,''), "
                "IFNULL(response_status,''), IFNULL(result_reserve_status,'') "
                f"FROM applications WHERE id IN ({ph})",
                ids,
            ).fetchall()
        }
        for row in out:
            row.update(extra.get(int(row["id"]), {}))
    if campuses and "*" not in campuses:
        allow = {c.strip().upper() for c in campuses if str(c).strip()}
        out = [
            r for r in out
            if not (r.get("campus") or "").strip()
            or (r.get("campus") or "").strip().upper() in allow
        ]
    if dossier_status:
        out = [r for r in out if (r.get("dossier_status") or "") == dossier_status]
    if selection_status:
        out = [r for r in out if (r.get("selection_status") or "") == selection_status]
    return out


def update_application_profile(conn, app_id: int, data: dict) -> dict | None:
    cur = conn.cursor()
    ensure_coord_tables(cur)
    cur.execute(
        "SELECT id, status, program_code, exam_eligible_flag, exam_format, "
        "written_score, interview_score, board_decision, admitted_program, final_result "
        "FROM applications WHERE id = ?",
        (app_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    current = {
        "id": row[0],
        "status": row[1],
        "program_code": row[2],
        "exam_eligible_flag": row[3],
        "exam_format": row[4],
        "written_score": row[5],
        "interview_score": row[6],
        "board_decision": row[7],
        "admitted_program": row[8],
        "final_result": row[9],
    }
    current_status = current["status"]
    from admission_ops import apply_board_decision_fields

    data = apply_board_decision_fields(current, dict(data))

    fields: list[str] = []
    params: list[Any] = []
    new_status = None
    if (data.get("status") or "").strip() == "withdrawn":
        reason = (data.get("withdraw_reason") or "").strip()
        if reason not in WITHDRAW_REASONS:
            raise ValueError(
                "Chọn lý do rút hồ sơ: không xác nhận văn bằng, hoặc có kế hoạch khác."
            )
        if not (data.get("notes") or "").strip():
            raise ValueError("Rút hồ sơ cần ghi chú kèm lý do.")
    for key, val in data.items():
        if key not in PROFILE_EDITABLE:
            continue
        if key == "status":
            status_val = (val or "").strip()
            try:
                from status_catalog import allowed_codes

                allowed = allowed_codes(conn, "application_status")
            except Exception:
                allowed = set()
            if not allowed:
                allowed = APP_STATUS_VALUES
            from status_catalog import WATCH_OR_QA_CODES

            if status_val in WATCH_OR_QA_CODES or status_val not in allowed:
                raise ValueError(f"Trạng thái không hợp lệ: {status_val}")
            new_status = status_val
            fields.append("status = ?")
            params.append(status_val)
            continue
        if key == "final_result":
            fr = (val or "").strip()
            if fr:
                try:
                    from status_catalog import allowed_codes

                    fr_allowed = allowed_codes(conn, "final_result")
                except Exception:
                    fr_allowed = set()
                if fr_allowed and fr not in fr_allowed:
                    raise ValueError(f"Kết quả cuối không hợp lệ: {fr}")
            fields.append("final_result = ?")
            params.append(fr)
            continue
        fields.append(f"{key} = ?")
        params.append(val)

    # Keep final_result aligned when status changes (unless caller set it explicitly)
    if new_status and new_status != current_status:
        if "final_result" not in data and new_status in FINAL_RESULT_BY_STATUS:
            fields.append("final_result = ?")
            params.append(FINAL_RESULT_BY_STATUS[new_status])
        # TS → Điều phối: bàn giao hồ sơ (đồng bộ với POST /status)
        if new_status == "approved_ts":
            from datetime import datetime

            actor_label = (data.get("_actor_label") or data.get("transferred_by") or "system").strip()
            if "transferred_at" not in data:
                fields.append("transferred_at = ?")
                params.append(datetime.now().isoformat(sep=" ", timespec="seconds"))
            if "transferred_by" not in data:
                fields.append("transferred_by = ?")
                params.append(actor_label)
        if new_status == "paid":
            raise ValueError(
                "Xác nhận đã thu phí ghi danh trên màn Phí ghi danh (Kế toán). "
                "Không đổi trạng thái paid trực tiếp trên hồ sơ."
            )
        if new_status == "passed":
            from treasury_ops import ensure_inscription_charge

            ensure_inscription_charge(conn, app_id)
        if new_status == "official":
            from treasury_ops import inscription_is_paid, open_tuition_plan_after_official

            if not inscription_is_paid(cur, app_id):
                raise ValueError(
                    "Cần Kế toán xác nhận đã thu phí ghi danh trước khi chốt nhập học."
                )
            open_tuition_plan_after_official(conn, app_id)

    if fields:
        params.append(app_id)
        cur.execute(f"UPDATE applications SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
    try:
        from learner_spine import upsert_learner_for_application

        upsert_learner_for_application(conn, app_id)
        conn.commit()
    except Exception:
        pass
    try:
        from admission_ops import propagate_row_by_id

        propagate_row_by_id(conn, "applications", app_id, data)
    except Exception:
        pass
    rows = list_applications_enriched(conn, ["*"])
    return next((r for r in rows if r["id"] == app_id), None)


def import_candidates(conn, rows: list[dict], *, round_id: int | None = None) -> dict:
    """Import candidate list rows (from Excel template mapping)."""
    cur = conn.cursor()
    ensure_coord_tables(cur)
    if not round_id:
        cur.execute("SELECT id FROM admission_rounds ORDER BY id DESC LIMIT 1")
        r = cur.fetchone()
        if not r:
            raise ValueError("No admission round")
        round_id = r[0]
    created = updated = 0
    skipped_no_cccd = 0
    touched: list[int] = []
    from admission_ops import find_application_by_cccd_program, normalize_cccd

    for raw in rows:
        name = (raw.get("full_name") or raw.get("Fullname") or raw.get("Họ Tên") or "").strip()
        if not name:
            continue
        prog = (raw.get("program_code") or "").strip().upper()
        scode = (raw.get("student_code_mba") or raw.get("Student code") or "").strip()
        if not prog:
            prog = "MBA" if scode.upper().startswith("HN") and "MBA" in scode.upper() else "MMS"
        cccd_raw = str(
            raw.get("cccd") or raw.get("CCCD") or raw.get("Căn cước công dân")
            or raw.get("Can cuoc cong dan") or ""
        ).strip()
        if not normalize_cccd(cccd_raw):
            skipped_no_cccd += 1
            continue
        cfvg = (raw.get("cfvg_app_no") or raw.get("CFVG application nb") or "").strip()
        existing = find_application_by_cccd_program(cur, cccd_raw, prog)
        if not existing and cfvg:
            cur.execute(
                "SELECT id FROM applications WHERE cfvg_app_no = ? AND program_code = ?",
                (cfvg, prog),
            )
            existing = cur.fetchone()
        if not existing and scode:
            cur.execute(
                "SELECT id FROM applications WHERE student_code_mba = ? AND program_code = ?",
                (scode, prog),
            )
            existing = cur.fetchone()
        if not existing and (raw.get("email") or "").strip():
            cur.execute(
                "SELECT id FROM applications WHERE email = ? AND program_code = ?",
                ((raw.get("email") or "").strip(), prog),
            )
            existing = cur.fetchone()
        payload = {
            "campus": raw.get("campus") or raw.get("Campus") or "",
            "cfvg_app_no": cfvg,
            "gender": raw.get("gender") or raw.get("Gd") or raw.get("Giới tính") or "",
            "dob": str(raw.get("dob") or raw.get("DOB") or raw.get("Ngày sinh") or "")[:32],
            "university": raw.get("university") or raw.get("University") or raw.get("Trường Đại học") or "",
            "degree_major": raw.get("degree_major") or raw.get("Degree major") or raw.get("Chuyên ngành") or "",
            "study_duration": raw.get("study_duration") or raw.get("Duration") or raw.get("Số năm học ĐH") or "",
            "degree_grade": raw.get("degree_grade") or raw.get("Grade") or raw.get("Xếp loại") or "",
            "experience_years": _to_float(
                raw.get("experience_years") or raw.get("Experience Years") or raw.get("Số năm KN")
            ),
            "credit_hours": _to_float(raw.get("credit_hours") or raw.get("Credit") or raw.get("Số TC")),
            "english_cert": raw.get("english_cert") or raw.get("English certificate") or raw.get("Chứng Chỉ Tiếng Anh") or "",
            "english_cert_score": raw.get("english_cert_score") or raw.get("English score") or raw.get("Điểm chứng chỉ TA") or raw.get("Điểm TA") or "",
            "company": raw.get("company") or raw.get("Company") or raw.get("Đơn vị công tác") or "",
            "interview_date": str(raw.get("interview_date") or raw.get("Interview date") or raw.get("Jury date") or "")[:32],
            "final_result": raw.get("final_result") or raw.get("Final Results") or "",
            "notes": raw.get("notes") or raw.get("Comments") or raw.get("Ghi chú") or "",
            "email": raw.get("email") or raw.get("Email") or "",
            "phone": raw.get("phone") or "",
            "lead_source": raw.get("lead_source") or raw.get("Source") or "",
            "checklist_status": raw.get("checklist_status") or "pending",
            "degree_verified": raw.get("degree_verified") or "pending",
            "english_verified": raw.get("english_verified") or "pending",
            "neu_packet_ready": raw.get("neu_packet_ready") or "pending",
            "intake_session": "",
            "student_code_mba": raw.get("student_code_mba") or raw.get("Student code") or "",
            "eco_background": raw.get("eco_background") or raw.get("Eco/Non-eco") or "",
            "master_level": raw.get("master_level") or raw.get("Bậc Thạc sĩ") or "",
            "bachelor_start_year": raw.get("bachelor_start_year") or raw.get("Year of starting Bachelor") or "",
            "bachelor_grad_year": raw.get("bachelor_grad_year") or raw.get("Year of graduation (Bachelor)") or "",
            "job_title": raw.get("job_title") or raw.get("Vị trí") or raw.get("Vị trí") or "",
            "management_years": _to_float(
                raw.get("management_years") or raw.get("Số năm quản lý") or raw.get("Số năm quản lý")
            ),
            "english_note": raw.get("english_note") or raw.get("Ghi chú về điều kiện Tiếng Anh") or "",
            "naric_status": raw.get("naric_status") or raw.get("Naric accredited") or "",
            "naric_note": raw.get("naric_note") or raw.get("Situation of NARIC accreditation") or "",
            "exam_eligible_flag": raw.get("exam_eligible_flag") or raw.get("Đủ điều kiện dự thi") or "",
            "other_achievements": raw.get("other_achievements") or raw.get("Other academic achievements") or "",
            "interview_score": _to_float(
                raw.get("interview_score") or raw.get("Điểm phỏng vấn | /20")
            ),
            "interview_jury1": _to_float(raw.get("interview_jury1") or raw.get("Jury member 1")),
            "interview_jury2": _to_float(raw.get("interview_jury2") or raw.get("Jury member 2")),
            "interview_jury3": _to_float(raw.get("interview_jury3") or raw.get("Jury member 3")),
            "written_score": _to_float(raw.get("written_score") or raw.get("Điểm viết | /20")),
            "written_gk": _to_float(raw.get("written_gk") or raw.get("General Knowledge & Economic/20")),
            "written_mle": _to_float(raw.get("written_mle") or raw.get("(Maths+Logic+English)/20")),
            "avg_score": _to_float(raw.get("avg_score") or raw.get("Điểm trung bình | /20")),
            "confirmation_status": raw.get("confirmation_status")
            or raw.get("Confirmation to Study/Postpone/Defer/Drop")
            or "",
            "board_decision": raw.get("board_decision") or raw.get("Quyết định HĐ TS CFVG HN") or "",
            "cccd": cccd_raw,
            "exam_format": raw.get("exam_format") or raw.get("Hình thức thi") or "",
            "exam_board": raw.get("exam_board") or raw.get("Hội đồng thi") or "",
        }
        from mba_ops import exam_session_labels, remember_exam_sittings

        labels = exam_session_labels(raw)
        if labels:
            payload["intake_session"] = ", ".join(labels)
        if existing:
            update_application_profile(conn, existing[0], payload)
            updated += 1
            touched.append(int(existing[0]))
        else:
            cur.execute(
                "INSERT INTO applications "
                "(round_id, program_code, full_name, cccd, email, phone, status, notes, "
                "campus, cfvg_app_no, gender, dob, university, degree_major, "
                "study_duration, degree_grade, experience_years, credit_hours, "
                "english_cert, company, interview_date, final_result, "
                "intake_session, student_code_mba, eco_background, master_level, "
                "bachelor_start_year, bachelor_grad_year, job_title, management_years, "
                "english_note, naric_status, naric_note, exam_eligible_flag, "
                "other_achievements, interview_score, interview_jury1, interview_jury2, "
                "interview_jury3, written_score, written_gk, written_mle, avg_score, "
                "confirmation_status, board_decision, exam_format, exam_board) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    round_id, prog, name, cccd_raw, payload["email"], payload["phone"],
                    "submitted", payload["notes"], payload["campus"], payload["cfvg_app_no"],
                    payload["gender"], payload["dob"], payload["university"],
                    payload["degree_major"], payload["study_duration"], payload["degree_grade"],
                    payload["experience_years"], payload["credit_hours"],
                    payload["english_cert"], payload["company"], payload["interview_date"],
                    payload["final_result"],
                    payload["intake_session"], payload["student_code_mba"],
                    payload["eco_background"], payload["master_level"],
                    payload["bachelor_start_year"], payload["bachelor_grad_year"],
                    payload["job_title"], payload["management_years"],
                    payload["english_note"], payload["naric_status"], payload["naric_note"],
                    payload["exam_eligible_flag"], payload["other_achievements"],
                    payload["interview_score"], payload["interview_jury1"],
                    payload["interview_jury2"], payload["interview_jury3"],
                    payload["written_score"], payload["written_gk"], payload["written_mle"],
                    payload["avg_score"], payload["confirmation_status"],
                    payload["board_decision"], payload["exam_format"], payload["exam_board"],
                ),
            )
            created += 1
            touched.append(int(cur.lastrowid))
            if payload.get("english_cert_score"):
                update_application_profile(conn, cur.lastrowid, {
                    "english_cert_score": payload["english_cert_score"],
                })
            if payload.get("board_decision"):
                try:
                    update_application_profile(conn, cur.lastrowid, {
                        "board_decision": payload["board_decision"],
                    })
                except ValueError:
                    pass
        app_row_id = existing[0] if existing else cur.lastrowid
        if labels and app_row_id:
            remember_exam_sittings(cur, int(app_row_id), labels, round_id)
    conn.commit()
    if touched:
        try:
            from learner_spine import refresh_learner_stages

            refresh_learner_stages(conn, touched)
        except Exception:
            pass
    return {"created": created, "updated": updated, "skipped_no_cccd": skipped_no_cccd}


def _jury_average(scores: dict) -> str:
    nums: list[float] = []
    for value in list(scores.values())[:3]:
        parsed = _to_float(value)
        if parsed is not None:
            nums.append(parsed)
    if not nums:
        return ""
    return f"{(sum(nums) / len(nums)):.2f}".rstrip("0").rstrip(".")


def _to_float(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── Interview scores ─────────────────────────────────────────────────

def get_interview_session_detail(conn, session_id: int) -> dict | None:
    cur = conn.cursor()
    ensure_coord_tables(cur)
    s = cur.execute(
        "SELECT s.id, s.program_code, s.title, s.room, s.starts_at, s.slot_minutes, "
        "r.code, r.name FROM interview_sessions s "
        "JOIN admission_rounds r ON r.id = s.round_id WHERE s.id = ?",
        (session_id,),
    ).fetchone()
    if not s:
        return None
    # Distinct jury names for this session (from scores or defaults)
    juries = [
        r[0]
        for r in cur.execute(
            "SELECT DISTINCT sc.jury_name FROM interview_scores sc "
            "JOIN interview_slots sl ON sl.id = sc.slot_id "
            "WHERE sl.session_id = ? ORDER BY sc.sort_order, sc.jury_name",
            (session_id,),
        ).fetchall()
    ]
    if not juries:
        juries = ["Giảng viên 1", "Giảng viên 2", "Giảng viên 3"]
    while len(juries) < 3:
        juries.append(f"Giảng viên {len(juries) + 1}")
    juries = juries[:3]
    slots = []
    for sl in cur.execute(
        "SELECT sl.id, sl.slot_order, sl.scheduled_at, sl.score_conclusion, sl.result, sl.notes, "
        "a.id, a.full_name, a.gender, a.dob, a.company, a.cfvg_app_no "
        "FROM interview_slots sl "
        "JOIN applications a ON a.id = sl.application_id "
        "WHERE sl.session_id = ? ORDER BY sl.slot_order",
        (session_id,),
    ).fetchall():
        scores = {
            r[0]: r[1]
            for r in cur.execute(
                "SELECT jury_name, score FROM interview_scores WHERE slot_id = ?",
                (sl[0],),
            ).fetchall()
        }
        slots.append(
            {
                "id": sl[0],
                "slot_order": sl[1],
                "scheduled_at": sl[2],
                "score_conclusion": sl[3],
                "result": sl[4] or "pending",
                "notes": sl[5],
                "application_id": sl[6],
                "full_name": sl[7],
                "gender": sl[8],
                "dob": sl[9],
                "company": sl[10],
                "cfvg_app_no": sl[11],
                "scores": {j: scores.get(j, "") for j in juries},
                "score_avg": _jury_average({j: scores.get(j, "") for j in juries}),
            }
        )
    return {
        "id": s[0],
        "program_code": s[1],
        "title": s[2],
        "room": s[3],
        "starts_at": s[4],
        "slot_minutes": s[5],
        "round_code": s[6],
        "round_name": s[7],
        "jury_names": juries,
        "slots": slots,
        "stats": {
            "candidates": len(slots),
            "scored": sum(1 for x in slots if any(x["scores"].values())),
            "admitted": sum(1 for x in slots if x["result"] == "pass"),
        },
    }


def save_interview_slot_scores(
    conn,
    slot_id: int,
    *,
    scores: dict[str, str],
    result: str | None = None,
    score_conclusion: str | None = None,
    notes: str | None = None,
) -> dict | None:
    cur = conn.cursor()
    ensure_coord_tables(cur)
    row = cur.execute(
        "SELECT session_id FROM interview_slots WHERE id = ?", (slot_id,)
    ).fetchone()
    if not row:
        return None
    session_id = row[0]
    for i, (jury, score) in enumerate(scores.items()):
        jury = (jury or "").strip()
        if not jury:
            continue
        existing = cur.execute(
            "SELECT id FROM interview_scores WHERE slot_id = ? AND jury_name = ?",
            (slot_id, jury),
        ).fetchone()
        if existing:
            cur.execute(
                "UPDATE interview_scores SET score = ? WHERE id = ?",
                (str(score).strip() if score is not None else "", existing[0]),
            )
        else:
            cur.execute(
                "INSERT INTO interview_scores (slot_id, jury_name, score, sort_order) "
                "VALUES (?, ?, ?, ?)",
                (slot_id, jury, str(score).strip() if score is not None else "", i),
            )
    saved = {
        r[0]: r[1]
        for r in cur.execute(
            "SELECT jury_name, score FROM interview_scores WHERE slot_id = ? ORDER BY sort_order, id LIMIT 3",
            (slot_id,),
        ).fetchall()
    }
    average = _jury_average(saved)
    ordered = list(saved.items())
    while len(ordered) < 3:
        ordered.append(("", ""))
    app = cur.execute(
        "SELECT application_id FROM interview_slots WHERE id = ?", (slot_id,)
    ).fetchone()
    if app:
        cur.execute(
            "UPDATE applications SET interview_jury1 = ?, interview_jury2 = ?, "
            "interview_jury3 = ?, interview_score = ? WHERE id = ?",
            (
                ordered[0][1],
                ordered[1][1],
                ordered[2][1],
                _to_float(average),
                app[0],
            ),
        )
    fields = []
    params: list[Any] = []
    if result is not None:
        fields.append("result = ?")
        params.append(result)
    if score_conclusion is not None:
        fields.append("score_conclusion = ?")
        params.append(score_conclusion)
    if notes is not None:
        fields.append("notes = ?")
        params.append(notes)
    if fields:
        params.append(slot_id)
        cur.execute(
            f"UPDATE interview_slots SET {', '.join(fields)} WHERE id = ?", params
        )
    # Sync application final_result / status lightly
    if result in ("pass", "fail"):
        app = cur.execute(
            "SELECT application_id FROM interview_slots WHERE id = ?", (slot_id,)
        ).fetchone()
        if app:
            if result == "pass":
                cur.execute(
                    "UPDATE applications SET status = CASE WHEN status IN ('failed','withdrawn') "
                    "THEN status ELSE 'passed' END, final_result = 'Admitted' WHERE id = ?",
                    (app[0],),
                )
            else:
                cur.execute(
                    "UPDATE applications SET status = 'failed', final_result = 'Non-Admitted' "
                    "WHERE id = ?",
                    (app[0],),
                )
    conn.commit()
    return get_interview_session_detail(conn, session_id)


# ── Course grades ────────────────────────────────────────────────────

def _weighted_final(cur, class_id: int, student_id: int, course_id: int) -> float | None:
    rows = cur.execute(
        "SELECT c.id, c.weight_pct, s.score "
        "FROM grade_components c "
        "LEFT JOIN grade_component_scores s "
        "ON s.component_id = c.id AND s.student_id = ? "
        "WHERE c.class_id = ? AND c.course_id = ? "
        "ORDER BY c.sort_order",
        (student_id, class_id, course_id),
    ).fetchall()
    if not rows:
        return None
    total_w = 0.0
    acc = 0.0
    for _cid, weight, score in rows:
        if score is None:
            return None
        total_w += float(weight)
        acc += float(score) * float(weight)
    if total_w <= 0:
        return None
    return round(acc / total_w, 2)


def ensure_default_grade_components(cur, class_id: int, course_id: int, scheme: str = "40_60") -> None:
    """MSCM/MMS: two heads. MBA keeps GA 30 / FE 70 and does not call this."""
    cur.execute(
        "SELECT COUNT(*) FROM grade_components WHERE class_id = ? AND course_id = ?",
        (class_id, course_id),
    )
    if cur.fetchone()[0]:
        return
    parts = GRADE_SCHEMES.get(scheme) or GRADE_SCHEMES["40_60"]
    for i, (name, weight) in enumerate(parts, start=1):
        cur.execute(
            "INSERT INTO grade_components (class_id, course_id, name, weight_pct, sort_order) "
            "VALUES (?,?,?,?,?)",
            (class_id, course_id, name, weight, i),
        )


def set_grade_scheme(conn, class_id: int, course_id: int, scheme: str) -> dict:
    parts = GRADE_SCHEMES.get(scheme)
    if not parts:
        raise ValueError("Tỷ trọng chỉ nhận 40/60 hoặc 50/50.")
    cur = conn.cursor()
    ensure_coord_tables(cur)
    locked = cur.execute(
        "SELECT COUNT(*) FROM course_grades WHERE class_id = ? AND course_id = ? AND locked = 1",
        (class_id, course_id),
    ).fetchone()[0]
    if locked:
        raise ValueError("Môn đã khóa điểm — mở khóa trước khi đổi tỷ trọng.")
    rows = cur.execute(
        "SELECT id FROM grade_components WHERE class_id = ? AND course_id = ? ORDER BY sort_order",
        (class_id, course_id),
    ).fetchall()
    if len(rows) == len(parts):
        for (cid,), (name, weight) in zip(rows, parts):
            cur.execute(
                "UPDATE grade_components SET name = ?, weight_pct = ? WHERE id = ?",
                (name, weight, cid),
            )
    else:
        cur.execute(
            "DELETE FROM grade_component_scores WHERE component_id IN "
            "(SELECT id FROM grade_components WHERE class_id = ? AND course_id = ?)",
            (class_id, course_id),
        )
        cur.execute(
            "DELETE FROM grade_components WHERE class_id = ? AND course_id = ?",
            (class_id, course_id),
        )
        for i, (name, weight) in enumerate(parts, start=1):
            cur.execute(
                "INSERT INTO grade_components (class_id, course_id, name, weight_pct, sort_order) "
                "VALUES (?,?,?,?,?)",
                (class_id, course_id, name, weight, i),
            )
    conn.commit()
    return {"class_id": class_id, "course_id": course_id, "scheme": scheme}


def get_class_gradebook(conn, class_id: int) -> dict | None:
    cur = conn.cursor()
    ensure_coord_tables(cur)
    meta = cur.execute(
        "SELECT cg.id, cg.name, cg.program_code, cg.cohort_year, cg.status, "
        "pv.version_code, pv.id "
        "FROM class_groups cg "
        "LEFT JOIN program_versions pv ON pv.id = cg.program_version_id "
        "WHERE cg.id = ?",
        (class_id,),
    ).fetchone()
    if not meta:
        return None
    pvid = meta[6]
    courses = [
        {
            "id": r[0],
            "code": r[1],
            "name": r[2],
            "module_no": f"M{r[3]}",
            "ects": 3,
            "lecturer": r[4] or "",
            "institution": r[5] or "",
        }
        for r in cur.execute(
            "SELECT c.id, c.code, c.name, c.sort_order, "
            "(SELECT f.full_name FROM teaching_assignments ta "
            " JOIN faculty f ON f.id = ta.lecturer_id "
            " WHERE ta.course_id = c.id AND ta.class_id = ? LIMIT 1), "
            "(SELECT f.organization FROM teaching_assignments ta "
            " JOIN faculty f ON f.id = ta.lecturer_id "
            " WHERE ta.course_id = c.id AND ta.class_id = ? LIMIT 1) "
            "FROM courses c "
            "WHERE c.program_version_id = ? ORDER BY c.sort_order",
            (class_id, class_id, pvid),
        ).fetchall()
    ] if pvid else []
    program_code = meta[2] or ""
    grade_mode = "mba_30_70" if program_code == "MBA" else "weighted"
    if grade_mode == "weighted":
        for c in courses:
            ensure_default_grade_components(cur, class_id, c["id"])
        conn.commit()
    comp_by_course: dict[int, list[dict]] = {}
    for r in cur.execute(
        "SELECT id, course_id, name, weight_pct, sort_order FROM grade_components "
        "WHERE class_id = ? ORDER BY course_id, sort_order",
        (class_id,),
    ).fetchall():
        comp_by_course.setdefault(r[1], []).append(
            {"id": r[0], "name": r[2], "weight_pct": r[3], "sort_order": r[4]}
        )
    for c in courses:
        c["components"] = comp_by_course.get(c["id"], []) if grade_mode == "weighted" else []
    score_map: dict[tuple[int, int], float | None] = {}
    for sid, cid, sc in cur.execute(
        "SELECT s.student_id, s.component_id, s.score "
        "FROM grade_component_scores s "
        "JOIN grade_components c ON c.id = s.component_id "
        "WHERE c.class_id = ?",
        (class_id,),
    ).fetchall():
        score_map[(sid, cid)] = sc
    students = []
    for st in cur.execute(
        "SELECT id, full_name, email, student_code, dob, gender, graduated_at, observations "
        "FROM class_students WHERE class_id = ? ORDER BY full_name",
        (class_id,),
    ).fetchall():
        grades = {}
        for r in cur.execute(
            "SELECT course_id, score, locked, id, group_assignment, final_exam, "
            "anonymous_no, remarks FROM course_grades "
            "WHERE class_id = ? AND student_id = ?",
            (class_id, st[0]),
        ).fetchall():
            grades[r[0]] = {
                "score": r[1],
                "locked": bool(r[2]),
                "id": r[3],
                "group_assignment": r[4],
                "final_exam": r[5],
                "anonymous_no": r[6],
                "remarks": r[7],
            }
        score_vals = [grades[c["id"]]["score"] for c in courses if c["id"] in grades and grades[c["id"]]["score"] is not None]
        students.append(
            {
                "id": st[0],
                "full_name": st[1],
                "email": st[2],
                "student_code": st[3],
                "dob": st[4],
                "gender": st[5],
                "graduated_at": st[6],
                "observations": st[7],
                "grades": {
                    str(c["id"]): {
                        **grades.get(
                            c["id"],
                            {
                                "score": None,
                                "locked": False,
                                "id": None,
                                "group_assignment": None,
                                "final_exam": None,
                                "anonymous_no": None,
                                "remarks": None,
                            },
                        ),
                        "component_scores": {
                            str(comp["id"]): score_map.get((st[0], comp["id"]))
                            for comp in c.get("components") or []
                        },
                    }
                    for c in courses
                },
                "total": round(sum(score_vals) / len(score_vals), 2) if score_vals else None,
            }
        )
    locked_count = cur.execute(
        "SELECT COUNT(*) FROM course_grades WHERE class_id = ? AND locked = 1",
        (class_id,),
    ).fetchone()[0]
    return {
        "meta": {
            "id": meta[0],
            "name": meta[1],
            "program_code": meta[2],
            "cohort_year": meta[3],
            "status": meta[4],
            "version_code": meta[5],
            "grade_mode": grade_mode,
        },
        "courses": courses,
        "students": students,
        "stats": {
            "students": len(students),
            "courses": len(courses),
            "locked_cells": locked_count,
        },
    }


def _backfill_grade_attempts(cur) -> None:
    rows = cur.execute(
        "SELECT g.id, g.class_id, g.student_id, g.course_id, "
        "g.group_assignment, g.final_exam, g.score, IFNULL(g.locked,0) "
        "FROM course_grades g "
        "LEFT JOIN course_grade_attempts a ON a.grade_id = g.id "
        "WHERE a.id IS NULL"
    ).fetchall()
    for row in rows:
        _record_grade_attempt(
            cur,
            grade_id=row[0],
            class_id=row[1],
            student_id=row[2],
            course_id=row[3],
            group_assignment=row[4],
            final_exam=row[5],
            score=row[6],
            published=bool(row[7]),
            actor="backfill",
        )


def _record_grade_attempt(
    cur,
    *,
    grade_id: int,
    class_id: int,
    student_id: int,
    course_id: int,
    group_assignment,
    final_exam,
    score,
    published: bool,
    actor: str = "",
) -> None:
    last = cur.execute(
        "SELECT attempt_no, group_assignment, final_exam, score, published "
        "FROM course_grade_attempts WHERE grade_id = ? ORDER BY attempt_no DESC LIMIT 1",
        (grade_id,),
    ).fetchone()
    if last and (last[1], last[2], last[3], int(last[4] or 0)) == (
        group_assignment, final_exam, score, 1 if published else 0,
    ):
        return
    nxt = int(last[0] or 0) + 1 if last else 1
    from datetime import datetime

    cur.execute(
        "INSERT INTO course_grade_attempts ("
        "grade_id, class_id, student_id, course_id, attempt_no, "
        "group_assignment, final_exam, score, published, created_at, created_by"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            grade_id, class_id, student_id, course_id, nxt,
            group_assignment, final_exam, score, 1 if published else 0,
            datetime.now().isoformat(sep=" ", timespec="seconds"), actor,
        ),
    )


def upsert_grade(
    conn,
    class_id: int,
    student_id: int,
    course_id: int,
    *,
    score: float | None = None,
    locked: bool | None = None,
    observations: str | None = None,
    group_assignment: float | None = None,
    final_exam: float | None = None,
    anonymous_no: str | None = None,
    remarks: str | None = None,
    retake: bool = False,
    actor: str = "",
    component_id: int | None = None,
    component_score: float | None = None,
    allow_unlock: bool = False,
) -> dict:
    cur = conn.cursor()
    ensure_coord_tables(cur)
    existing = cur.execute(
        "SELECT id, score, locked, group_assignment, final_exam FROM course_grades "
        "WHERE class_id = ? AND student_id = ? AND course_id = ?",
        (class_id, student_id, course_id),
    ).fetchone()
    weighted_mode = bool(
        cur.execute(
            "SELECT 1 FROM grade_components WHERE class_id = ? AND course_id = ? LIMIT 1",
            (class_id, course_id),
        ).fetchone()
    )
    clear_score = False
    if component_id is not None:
        if existing and existing[2] and locked is not False:
            raise ValueError("Ô điểm đã khóa")
        own = cur.execute(
            "SELECT id FROM grade_components WHERE id = ? AND class_id = ? AND course_id = ?",
            (component_id, class_id, course_id),
        ).fetchone()
        if not own:
            raise ValueError("Đầu điểm không thuộc lớp–môn này.")
        if component_score is None:
            cur.execute(
                "DELETE FROM grade_component_scores WHERE component_id = ? AND student_id = ?",
                (component_id, student_id),
            )
        else:
            cur.execute(
                "INSERT INTO grade_component_scores (component_id, student_id, score) "
                "VALUES (?,?,?) "
                "ON CONFLICT(component_id, student_id) DO UPDATE SET score = excluded.score",
                (component_id, student_id, component_score),
            )
        score = _weighted_final(cur, class_id, student_id, course_id)
        clear_score = score is None
    # MBA: quy tắc đã công bố trên môn, nếu không thì 30% GA + 70% FE.
    # MSCM/MMS: grade_components (40/60 hoặc 50/50), không đi nhánh này.
    ga = group_assignment if group_assignment is not None else (existing[3] if existing else None)
    fe = final_exam if final_exam is not None else (existing[4] if existing else None)
    components_touched = group_assignment is not None or final_exam is not None
    if (
        not weighted_mode
        and component_id is None
        and components_touched
        and ga is not None
        and fe is not None
    ):
        course_cols = {r[1] for r in cur.execute("PRAGMA table_info(courses)").fetchall()}
        if {"component_weight_ga", "component_weight_fe", "score_rule_status"} <= course_cols:
            rule = cur.execute(
                "SELECT component_weight_ga, component_weight_fe, IFNULL(score_rule_status,'') "
                "FROM courses WHERE id = ?",
                (course_id,),
            ).fetchone()
            if rule and rule[2] == "published" and rule[0] is not None and rule[1] is not None:
                try:
                    score = round(float(rule[0]) * float(ga) + float(rule[1]) * float(fe), 2)
                    applied_rule = True
                except (TypeError, ValueError):
                    applied_rule = False
            else:
                applied_rule = False
        else:
            applied_rule = False
        if not applied_rule:
            try:
                score = round(0.3 * float(ga) + 0.7 * float(fe), 2)
            except (TypeError, ValueError):
                pass
    if existing and existing[2] and locked is False and not allow_unlock:
        raise ValueError("Locked grades cannot be changed.")
    if existing and existing[2] and locked is not False:
        if retake and (score is not None or group_assignment is not None or final_exam is not None):
            _record_grade_attempt(
                cur,
                grade_id=existing[0],
                class_id=class_id,
                student_id=student_id,
                course_id=course_id,
                group_assignment=ga,
                final_exam=fe,
                score=score if score is not None else existing[1],
                published=False,
                actor=actor,
            )
            conn.commit()
            return get_class_gradebook(conn, class_id)  # type: ignore
        if score is not None and score != existing[1]:
            raise ValueError("Ô điểm đã khóa")
        if group_assignment is not None or final_exam is not None or component_id is not None:
            raise ValueError("Ô điểm đã khóa")
    if existing:
        fields, params = [], []
        if score is not None or clear_score:
            fields.append("score = ?")
            params.append(score)
        if locked is not None:
            fields.append("locked = ?")
            params.append(1 if locked else 0)
        if observations is not None:
            fields.append("observations = ?")
            params.append(observations)
        if group_assignment is not None:
            fields.append("group_assignment = ?")
            params.append(group_assignment)
        if final_exam is not None:
            fields.append("final_exam = ?")
            params.append(final_exam)
        if anonymous_no is not None:
            fields.append("anonymous_no = ?")
            params.append(anonymous_no)
        if remarks is not None:
            fields.append("remarks = ?")
            params.append(remarks)
        fields.append("updated_at = CURRENT_TIMESTAMP")
        if fields:
            params.append(existing[0])
            cur.execute(
                f"UPDATE course_grades SET {', '.join(fields)} WHERE id = ?", params
            )
        grade_id = existing[0]
    else:
        cur.execute(
            "INSERT INTO course_grades "
            "(class_id, student_id, course_id, score, locked, observations, "
            "group_assignment, final_exam, anonymous_no, remarks) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                class_id,
                student_id,
                course_id,
                score,
                1 if locked else 0,
                observations,
                group_assignment,
                final_exam,
                anonymous_no,
                remarks,
            ),
        )
        grade_id = cur.lastrowid
    stored_score = score if score is not None else (existing[1] if existing else None)
    _record_grade_attempt(
        cur,
        grade_id=int(grade_id),
        class_id=class_id,
        student_id=student_id,
        course_id=course_id,
        group_assignment=ga,
        final_exam=fe,
        score=stored_score,
        published=bool(locked) or bool(existing and existing[2]),
        actor=actor,
    )
    conn.commit()
    return get_class_gradebook(conn, class_id)  # type: ignore


def lock_class_grades(conn, class_id: int, locked: bool = True, *, actor: str = "") -> dict | None:
    cur = conn.cursor()
    ensure_coord_tables(cur)
    cur.execute(
        "UPDATE course_grades SET locked = ? WHERE class_id = ?",
        (1 if locked else 0, class_id),
    )
    if locked:
        rows = cur.execute(
            "SELECT id, student_id, course_id, group_assignment, final_exam, score "
            "FROM course_grades WHERE class_id = ?",
            (class_id,),
        ).fetchall()
        for row in rows:
            _record_grade_attempt(
                cur,
                grade_id=row[0],
                class_id=class_id,
                student_id=row[1],
                course_id=row[2],
                group_assignment=row[3],
                final_exam=row[4],
                score=row[5],
                published=True,
                actor=actor,
            )
            cur.execute(
                "UPDATE course_grade_attempts SET published = 1 "
                "WHERE grade_id = ? AND attempt_no = ("
                "SELECT MAX(attempt_no) FROM course_grade_attempts WHERE grade_id = ?)",
                (row[0], row[0]),
            )
    conn.commit()
    return get_class_gradebook(conn, class_id)


def update_student_grade_meta(conn, student_id: int, data: dict) -> None:
    from mba_ops import LIFECYCLE_STATUSES, ensure_mba_tables

    cur = conn.cursor()
    ensure_coord_tables(cur)
    ensure_mba_tables(cur)
    allowed = {
        "student_code", "dob", "gender", "graduated_at", "observations",
        "full_name", "email", "lifecycle_status", "scholarship_type",
        "partner_enrollment", "reserve_note",
        "place_of_birth", "phone", "job_title", "management_years",
        "company", "intake_session", "exchange_flag",
    }
    fields, params = [], []
    for k, v in data.items():
        if k not in allowed:
            continue
        if k == "lifecycle_status" and v and v not in LIFECYCLE_STATUSES:
            raise ValueError(f"Invalid lifecycle_status: {v}")
        fields.append(f"{k} = ?")
        params.append(v)
    if fields:
        params.append(student_id)
        cur.execute(
            f"UPDATE class_students SET {', '.join(fields)} WHERE id = ?", params
        )
        conn.commit()
        if data.get("lifecycle_status") == "graduated":
            from mba_ops import promote_graduated_to_alumni

            promote_graduated_to_alumni(conn, student_id)


# ── Thesis tracking ──────────────────────────────────────────────────

def list_thesis_records(conn, scopes: list[str] | None, *, q: str = "") -> list[dict]:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_coord_tables(cur)
    frag, params = _scopes_sql(scopes, "t.program_code")
    sql = (
        "SELECT t.id, t.program_code, t.full_name, t.email, t.gender, t.cp_number, t.title, "
        "t.tutor, t.payment_status, t.turnitin_pct, t.ai_pct, t.jury_host, "
        "t.jury_member_1, t.jury_member_2, t.defense_date, t.defense_time, t.room, "
        "t.total_grade, t.status, t.class_id, cg.name "
        f"FROM thesis_records t LEFT JOIN class_groups cg ON cg.id = t.class_id "
        f"WHERE {frag}"
    )
    if q:
        sql += " AND (t.full_name LIKE ? OR IFNULL(t.cp_number,'') LIKE ? OR IFNULL(t.title,'') LIKE ?)"
        params.extend([f"%{q}%"] * 3)
    sql += " ORDER BY t.defense_date, t.full_name"
    return [
        {
            "id": r[0],
            "program_code": r[1],
            "full_name": r[2],
            "email": r[3],
            "gender": r[4],
            "cp_number": r[5],
            "title": r[6],
            "tutor": r[7],
            "payment_status": r[8],
            "turnitin_pct": r[9],
            "ai_pct": r[10],
            "jury_host": r[11],
            "jury_member_1": r[12],
            "jury_member_2": r[13],
            "defense_date": r[14],
            "defense_time": r[15],
            "room": r[16],
            "total_grade": r[17],
            "status": r[18],
            "class_id": r[19],
            "class_name": r[20],
        }
        for r in cur.execute(sql, params).fetchall()
    ]


def get_thesis_record(conn, thesis_id: int) -> dict | None:
    rows = list_thesis_records(conn, ["*"])
    return next((r for r in rows if r["id"] == thesis_id), None)


THESIS_EDITABLE = {
    "full_name", "email", "gender", "cp_number", "title", "tutor", "payment_status",
    "turnitin_pct", "ai_pct", "jury_host", "jury_member_1", "jury_member_2",
    "defense_date", "defense_time", "room", "total_grade", "status", "notes",
    "program_code", "class_id", "student_id",
}


def upsert_thesis_record(conn, data: dict, thesis_id: int | None = None) -> dict:
    cur = conn.cursor()
    ensure_coord_tables(cur)
    if thesis_id:
        fields, params = [], []
        for k, v in data.items():
            if k in THESIS_EDITABLE:
                fields.append(f"{k} = ?")
                params.append(v)
        if not fields:
            raise ValueError("No fields")
        params.append(thesis_id)
        cur.execute(f"UPDATE thesis_records SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        return get_thesis_record(conn, thesis_id)  # type: ignore
    prog = (data.get("program_code") or "MMS").strip()
    name = (data.get("full_name") or "").strip()
    if not name:
        raise ValueError("full_name required")
    cols = [c for c in THESIS_EDITABLE if c in data or c in ("program_code", "full_name")]
    # ensure required
    payload = {k: data.get(k) for k in THESIS_EDITABLE if k in data}
    payload["program_code"] = prog
    payload["full_name"] = name
    keys = list(payload.keys())
    cur.execute(
        f"INSERT INTO thesis_records ({', '.join(keys)}) VALUES ({', '.join('?'*len(keys))})",
        [payload[k] for k in keys],
    )
    conn.commit()
    return get_thesis_record(conn, cur.lastrowid)  # type: ignore
