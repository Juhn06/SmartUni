"""
End-to-end pipeline demo: student personas (see e2e_personas.py) through
admissions → interview → fee → official → class → courses → grades →
exams → thesis → graduation, with hoc_vien portal accounts + timeline.
"""
from __future__ import annotations

from datetime import date, timedelta

from e2e_personas import PERSONAS, admission_fields, apply_plan, apply_tuition, plan_signature
from seed_org import TEMP_PASSWORD

E2E_MARKER = "E2E-PIPELINE"
E2E_PASSWORD = TEMP_PASSWORD  # 123!

E2E_CANDIDATES = PERSONAS


def ensure_e2e_columns(cur) -> None:
    """Link portal user ↔ application / class_student."""
    for table, col, decl in (
        ("applications", "portal_user_id", "INTEGER"),
        ("class_students", "portal_user_id", "INTEGER"),
        ("applications", "e2e_marker", "TEXT"),
    ):
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        except Exception:
            pass


def _ensure_round(cur) -> int:
    row = cur.execute(
        "SELECT id FROM admission_rounds WHERE code = 'TS2026-1' LIMIT 1"
    ).fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO admission_rounds (code, name, programs, year, status, opened_at, intake) "
        "VALUES ('TS2026-1', 'Tuyển sinh 2026 đợt 1', 'MBA,MMS,MSCM', 2026, 'open', ?, 'May/Aug')",
        (date.today().isoformat(),),
    )
    return cur.lastrowid


def _ensure_program_version(cur, program_code: str) -> int:
    vcode = f"{program_code}_E2E_2026"
    row = cur.execute(
        "SELECT id FROM program_versions WHERE version_code = ?", (vcode,)
    ).fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO program_versions (program_code, version_code, name, description, is_active) "
        "VALUES (?, ?, ?, ?, 1)",
        (program_code, vcode, f"{program_code} E2E 2026", "E2E pipeline demo version"),
    )
    pvid = cur.lastrowid
    courses = {
        "MBA": [
            ("MBA101", "Leadership", 1),
            ("MBA102", "Corporate Finance", 1),
            ("MBA103", "Business Game", 2),
        ],
        "MMS": [
            ("MMS101", "Marketing Strategy", 1),
            ("MMS102", "Consumer Behaviour", 1),
            ("MMS103", "Brand Management", 2),
        ],
        "MSCM": [
            ("MSCM101", "Supply Chain Fundamentals", 1),
            ("MSCM102", "Operations Management", 1),
            ("MSCM103", "Logistics & Distribution", 2),
        ],
    }
    for i, (code, name, sem) in enumerate(courses.get(program_code, [])):
        cur.execute(
            "INSERT INTO courses (program_version_id, code, name, semester, sort_order, "
            "theory_sessions, practice_sessions) VALUES (?,?,?,?,?,7,2)",
            (pvid, code, name, sem, i),
        )
    return pvid


def _ensure_class(cur, program_code: str, class_name: str, pvid: int) -> int:
    row = cur.execute(
        "SELECT id FROM class_groups WHERE name = ? AND program_code = ?",
        (class_name, program_code),
    ).fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO class_groups (program_code, name, program_version_id, cohort_year, status) "
        "VALUES (?, ?, ?, 2026, 'active')",
        (program_code, class_name, pvid),
    )
    return cur.lastrowid


def _dept_id(cur, code: str) -> int | None:
    row = cur.execute("SELECT id FROM departments WHERE code = ?", (code,)).fetchone()
    return row[0] if row else None


def provision_student_account(
    conn,
    *,
    login: str,
    display_name: str,
    email: str,
    program_code: str,
    application_id: int | None = None,
    class_student_id: int | None = None,
    password: str | None = None,
    force_change: bool = False,
    reset_password: bool = True,
) -> dict:
    """Create/update hoc_vien portal user; link to application & class_student.

    Demo accounts reset to the shared demo password. Real enrollments pass a temporary password,
    force a change at first login and never overwrite a password the student already set.
    """
    from student_accounts import ensure_account_columns

    cur = conn.cursor()
    ensure_e2e_columns(cur)
    ensure_account_columns(cur)
    login = (login or "").strip()
    if not login:
        raise ValueError("login required")
    initial = password or E2E_PASSWORD
    cur.execute("SELECT id FROM user WHERE lower(email) = lower(?)", (login,))
    row = cur.fetchone()
    if row:
        user_id = row[0]
        if reset_password:
            cur.execute(
                "UPDATE user SET name = ?, password = ?, is_locked = 0, is_admin = 0, must_change_password = ? WHERE id = ?",
                (display_name, initial, 1 if force_change else 0, user_id),
            )
        else:
            cur.execute("UPDATE user SET name = ?, is_admin = 0 WHERE id = ?", (display_name, user_id))
        created = False
    else:
        cur.execute(
            "INSERT INTO user (name, email, password, is_admin, is_locked, must_change_password) VALUES (?,?,?,0,0,?)",
            (display_name, login, initial, 1 if force_change else 0),
        )
        user_id = cur.lastrowid
        created = True

    hv = _dept_id(cur, "hoc_vien")
    if hv:
        cur.execute(
            "INSERT OR IGNORE INTO user_departments (user_id, department_id) VALUES (?, ?)",
            (user_id, hv),
        )
    # Scope = program only
    cur.execute("DELETE FROM user_program_scopes WHERE user_id = ?", (user_id,))
    cur.execute(
        "INSERT OR IGNORE INTO user_program_scopes (user_id, program_code) VALUES (?, ?)",
        (user_id, program_code),
    )

    if application_id:
        try:
            cur.execute(
                "UPDATE applications SET portal_user_id = ?, e2e_marker = ? WHERE id = ?",
                (user_id, E2E_MARKER, application_id),
            )
        except Exception:
            cur.execute(
                "UPDATE applications SET portal_user_id = ? WHERE id = ?",
                (user_id, application_id),
            )
    if class_student_id:
        cur.execute(
            "UPDATE class_students SET portal_user_id = ? WHERE id = ?",
            (user_id, class_student_id),
        )
    conn.commit()
    return {
        "user_id": user_id,
        "login": login,
        "password": initial if (created or reset_password) else None,
        "email": email,
        "program_code": program_code,
        "created": created,
    }


def _upsert_application(cur, round_id: int, c: dict) -> int:
    ensure_e2e_columns(cur)
    existing = cur.execute(
        "SELECT id FROM applications WHERE cfvg_app_no = ? OR email = ?",
        (c["cfvg_app_no"], c["email"]),
    ).fetchone()
    fields = dict(
        round_id=round_id,
        program_code=c["program_code"],
        full_name=c["full_name"],
        cccd=c["cccd"],
        email=c["email"],
        phone=c["phone"],
        status=c.get("app_status", "official"),
        notes=f"{E2E_MARKER} full lifecycle demo",
        cfvg_app_no=c["cfvg_app_no"],
        company=c.get("company") or "",
        job_title=c.get("job_title") or "",
        intake_session=c.get("intake_session") or "",
        student_code_mba=c["student_code"],
        final_result="Admitted",
        confirmation_status="Confirmed",
        board_decision="Admitted",
        written_score=c["admission"]["written"],
        interview_score=c["admission"]["interview"],
        avg_score=round((c["admission"]["written"] + c["admission"]["interview"]) / 2, 2),
        written_exam_no=f"SBD-{c['program_code']}-E2E",
        written_exam_date=(date.today() - timedelta(days=40)).isoformat(),
        written_exam_room="P.E2E",
        written_exam_session="Ca 1",
        interview_date=(date.today() - timedelta(days=30)).isoformat(),
        checklist_status="complete",
        degree_verified="yes",
        english_verified="yes",
        neu_packet_ready="yes",
        transferred_at=(date.today() - timedelta(days=45)).isoformat(),
        transferred_by="E2E:NhungLH",
        e2e_marker=E2E_MARKER,
        **admission_fields(c),
    )
    if existing:
        app_id = existing[0]
        sets = ", ".join(f"{k}=?" for k in fields)
        cur.execute(
            f"UPDATE applications SET {sets} WHERE id = ?",
            (*fields.values(), app_id),
        )
        return app_id
    cols = ", ".join(fields.keys())
    qs = ", ".join("?" * len(fields))
    cur.execute(f"INSERT INTO applications ({cols}) VALUES ({qs})", tuple(fields.values()))
    return cur.lastrowid


def _ensure_fee(cur, app_id: int) -> int:
    row = cur.execute(
        "SELECT id FROM enrollment_fees WHERE application_id = ?", (app_id,)
    ).fetchone()
    paid_at = (date.today() - timedelta(days=25)).isoformat()
    if row:
        cur.execute(
            "UPDATE enrollment_fees SET amount=15000000, status='paid', paid_at=?, "
            "proof_note='E2E VCB transfer' WHERE id=?",
            (paid_at, row[0]),
        )
        return row[0]
    cur.execute(
        "INSERT INTO enrollment_fees (application_id, amount, status, paid_at, proof_note) "
        "VALUES (?, 15000000, 'paid', ?, 'E2E VCB transfer')",
        (app_id, paid_at),
    )
    return cur.lastrowid


def _ensure_interview(cur, round_id: int, app_id: int, c: dict) -> int:
    title = f"E2E PV {c['program_code']}"
    row = cur.execute(
        "SELECT id FROM interview_sessions WHERE title = ? AND program_code = ?",
        (title, c["program_code"]),
    ).fetchone()
    starts = (date.today() - timedelta(days=30)).isoformat() + " 09:00"
    if row:
        sid = row[0]
    else:
        cur.execute(
            "INSERT INTO interview_sessions "
            "(round_id, program_code, title, room, starts_at, slot_minutes) "
            "VALUES (?,?,?,?,?,20)",
            (round_id, c["program_code"], title, f"Room E2E-{c['program_code']}", starts),
        )
        sid = cur.lastrowid
    slot = cur.execute(
        "SELECT id FROM interview_slots WHERE session_id = ? AND application_id = ?",
        (sid, app_id),
    ).fetchone()
    if slot:
        slot_id = slot[0]
        cur.execute(
            "UPDATE interview_slots SET result='pass', score_conclusion='A', "
            "scheduled_at=?, notes='E2E pass' WHERE id=?",
            (starts, slot_id),
        )
    else:
        cur.execute(
            "INSERT INTO interview_slots "
            "(session_id, application_id, slot_order, scheduled_at, score_conclusion, result, notes) "
            "VALUES (?,?,1,?,'A','pass','E2E pass')",
            (sid, app_id, starts),
        )
        slot_id = cur.lastrowid
    # Jury scores
    try:
        from mba_ops import JURY_ROLES
    except Exception:
        JURY_ROLES = ("CFVG", "IAE", "Alumni")
    for j, role in enumerate(JURY_ROLES):
        exists = cur.execute(
            "SELECT id FROM interview_scores WHERE slot_id = ? AND jury_role = ?",
            (slot_id, role),
        ).fetchone()
        if exists:
            cur.execute(
                "UPDATE interview_scores SET score='16', jury_name=? WHERE id=?",
                (f"{role} Jury", exists[0]),
            )
        else:
            try:
                cur.execute(
                    "INSERT INTO interview_scores "
                    "(slot_id, jury_name, score, sort_order, jury_role) VALUES (?,?,?,?,?)",
                    (slot_id, f"{role} Jury", "16", j, role),
                )
            except Exception:
                cur.execute(
                    "INSERT INTO interview_scores (slot_id, jury_name, score, sort_order) "
                    "VALUES (?,?,?,?)",
                    (slot_id, f"{role} Jury", "16", j),
                )
    return sid


def _ensure_student(cur, class_id: int, app_id: int, c: dict) -> int:
    ensure_e2e_columns(cur)
    row = cur.execute(
        "SELECT id FROM class_students WHERE application_id = ?", (app_id,)
    ).fetchone()
    if row:
        sid = row[0]
        cur.execute(
            "UPDATE class_students SET class_id=?, full_name=?, email=?, student_code=?, "
            "lifecycle_status=?, reserve_note=?, scholarship_type=?, company=?, job_title=?, intake_session=? WHERE id=?",
            (
                class_id,
                c["full_name"],
                c["email"],
                c["student_code"],
                c.get("lifecycle") or "active",
                c.get("reserve_note") or "",
                c.get("scholarship") or "",
                c.get("company") or "",
                c.get("job_title") or "",
                c.get("intake_session") or "",
                sid,
            ),
        )
        return sid
    cur.execute(
        "INSERT INTO class_students "
        "(class_id, application_id, full_name, email, student_code, lifecycle_status, reserve_note, scholarship_type, "
        "company, job_title, intake_session) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            class_id,
            app_id,
            c["full_name"],
            c["email"],
            c["student_code"],
            c.get("lifecycle") or "active",
            c.get("reserve_note") or "",
            c.get("scholarship") or "",
            c.get("company") or "",
            c.get("job_title") or "",
            c.get("intake_session") or "",
        ),
    )
    return cur.lastrowid


def seed_e2e_pipeline(conn) -> dict:
    """Idempotent: demo student personas in different situations + portal accounts."""
    from mba_ops import ensure_mba_tables, promote_graduated_to_alumni
    from coord_ops import ensure_coord_tables
    from ops_data import ensure_ops_tables
    from ops_crud import ensure_extra_ops_tables

    cur = conn.cursor()
    ensure_ops_tables(cur)
    ensure_mba_tables(cur)
    ensure_coord_tables(cur)
    ensure_extra_ops_tables(cur)
    ensure_e2e_columns(cur)

    round_id = _ensure_round(cur)
    summary = {"candidates": [], "accounts": []}
    from app_settings import ensure_app_settings, get_setting, set_setting

    ensure_app_settings(cur)
    signature = plan_signature()
    rebuild = get_setting(conn, "e2e.plan_signature", "") != signature

    for c in E2E_CANDIDATES:
        pvid = _ensure_program_version(cur, c["program_code"])
        app_id = _upsert_application(cur, round_id, c)
        fee_id = _ensure_fee(cur, app_id)
        interview_id = _ensure_interview(cur, round_id, app_id, c)
        class_id = student_id = None
        academic: dict = {}
        if c.get("enrolled", True):
            class_id = _ensure_class(cur, c["program_code"], c["class_name"], pvid)
            student_id = _ensure_student(cur, class_id, app_id, c)
            if rebuild:
                academic = apply_plan(cur, class_id, student_id, pvid, c)
        conn.commit()

        try:
            from treasury_ops import (
                ensure_inscription_charge,
                link_charges_to_student,
                open_tuition_plan_after_official,
            )

            ensure_inscription_charge(conn, app_id)
            open_tuition_plan_after_official(conn, app_id)
            if student_id:
                link_charges_to_student(conn, app_id, student_id)
            if rebuild:
                apply_tuition(conn, app_id, c)
        except Exception:
            pass

        if student_id and c.get("lifecycle") == "graduated":
            promote_graduated_to_alumni(conn, student_id)
        elif student_id:
            cur.execute("DELETE FROM alumni_members WHERE class_student_id = ? OR lower(IFNULL(email, '')) = lower(?)", (student_id, c["email"]))
            conn.commit()

        acct = provision_student_account(
            conn,
            login=c["login"],
            display_name=f"{c['full_name']} — Học viên {c['program_code']}",
            email=c["email"],
            program_code=c["program_code"],
            application_id=app_id,
            class_student_id=student_id,
        )
        summary["accounts"].append(acct)
        summary["candidates"].append(
            {
                "program_code": c["program_code"],
                "full_name": c["full_name"],
                "application_id": app_id,
                "fee_id": fee_id,
                "interview_session_id": interview_id,
                "class_id": class_id,
                "student_id": student_id,
                "login": c["login"],
                "password": E2E_PASSWORD,
                "stages": [
                    "submitted",
                    "approved_ts",
                    "interview",
                    "passed",
                    "paid",
                    "official",
                    "enrolled",
                    "courses_graded",
                    "exams_done",
                    "thesis_defended",
                    "graduated",
                    "alumni",
                ],
                **academic,
            }
        )
    set_setting(conn, "e2e.plan_signature", signature)
    conn.commit()
    return summary


def resolve_student_identity(conn, *, user_id: int | None = None, email: str = "") -> dict | None:
    """Map portal user → application + class_student."""
    cur = conn.cursor()
    ensure_e2e_columns(cur)
    app = None
    student = None
    login = ""
    if user_id:
        u = cur.execute("SELECT id, email, name FROM user WHERE id = ?", (user_id,)).fetchone()
        if not u:
            return None
        login = u[1] or ""
        app = cur.execute(
            "SELECT id, program_code, full_name, email, status, cfvg_app_no, final_result, "
            "written_score, interview_score, avg_score, student_code_mba "
            "FROM applications WHERE portal_user_id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
        if not app:
            # match by application email == user login OR stored candidate email
            for candidate_email in (email, login):
                if not candidate_email:
                    continue
                app = cur.execute(
                    "SELECT id, program_code, full_name, email, status, cfvg_app_no, final_result, "
                    "written_score, interview_score, avg_score, student_code_mba "
                    "FROM applications WHERE lower(email) = lower(?) LIMIT 1",
                    (candidate_email,),
                ).fetchone()
                if app:
                    break
            # E2E login → cfvg / known emails
            if not app and login:
                for c in E2E_CANDIDATES:
                    if c["login"].lower() == login.lower():
                        app = cur.execute(
                            "SELECT id, program_code, full_name, email, status, cfvg_app_no, final_result, "
                            "written_score, interview_score, avg_score, student_code_mba "
                            "FROM applications WHERE cfvg_app_no = ? OR lower(email)=lower(?) LIMIT 1",
                            (c["cfvg_app_no"], c["email"]),
                        ).fetchone()
                        break
        student = cur.execute(
            "SELECT cs.id, cs.class_id, cs.student_code, cs.lifecycle_status, cs.full_name, cs.email, "
            "cg.name, cg.program_code "
            "FROM class_students cs JOIN class_groups cg ON cg.id = cs.class_id "
            "WHERE cs.portal_user_id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
        if not student and app:
            student = cur.execute(
                "SELECT cs.id, cs.class_id, cs.student_code, cs.lifecycle_status, cs.full_name, cs.email, "
                "cg.name, cg.program_code "
                "FROM class_students cs JOIN class_groups cg ON cg.id = cs.class_id "
                "WHERE cs.application_id = ? LIMIT 1",
                (app[0],),
            ).fetchone()
    elif email:
        app = cur.execute(
            "SELECT id, program_code, full_name, email, status, cfvg_app_no, final_result, "
            "written_score, interview_score, avg_score, student_code_mba "
            "FROM applications WHERE lower(email) = lower(?) LIMIT 1",
            (email,),
        ).fetchone()
        if app:
            student = cur.execute(
                "SELECT cs.id, cs.class_id, cs.student_code, cs.lifecycle_status, cs.full_name, cs.email, "
                "cg.name, cg.program_code "
                "FROM class_students cs JOIN class_groups cg ON cg.id = cs.class_id "
                "WHERE cs.application_id = ? LIMIT 1",
                (app[0],),
            ).fetchone()

    if not app and not student:
        return None

    return {
        "user_id": user_id,
        "login": login,
        "application": (
            {
                "id": app[0],
                "program_code": app[1],
                "full_name": app[2],
                "email": app[3],
                "status": app[4],
                "cfvg_app_no": app[5],
                "final_result": app[6],
                "written_score": app[7],
                "interview_score": app[8],
                "avg_score": app[9],
                "student_code": app[10],
            }
            if app
            else None
        ),
        "student": (
            {
                "id": student[0],
                "class_id": student[1],
                "student_code": student[2],
                "lifecycle_status": student[3],
                "full_name": student[4],
                "email": student[5],
                "class_name": student[6],
                "program_code": student[7],
            }
            if student
            else None
        ),
    }


def get_student_timeline(conn, *, user_id: int | None = None, email: str = "") -> dict:
    """Sequential stages for the logged-in candidate/student."""
    ident = resolve_student_identity(conn, user_id=user_id, email=email)
    if not ident:
        return {"ok": False, "error": "Không tìm thấy hồ sơ HV/thí sinh gắn với tài khoản.", "stages": []}

    cur = conn.cursor()
    app = ident.get("application") or {}
    st = ident.get("student") or {}
    app_id = app.get("id")
    student_id = st.get("id")
    class_id = st.get("class_id")
    stages = []

    def add(code, title, status, detail="", print_entity=""):
        stages.append(
            {
                "id": len(stages) + 1,
                "code": code,
                "title": title,
                "status": status,  # done | pending | n/a
                "detail": detail,
                "print_entity": print_entity,
            }
        )

    # 1. Application
    if app:
        add(
            "application",
            "Nộp / tiếp nhận hồ sơ tuyển sinh",
            "done",
            f"{app.get('cfvg_app_no')} · {app.get('program_code')} · TT: {app.get('status')}",
            "applications",
        )
        add(
            "approved_ts",
            "TS phê duyệt → chuyển Điều phối",
            "done" if app.get("status") in (
                "approved_ts", "interview", "passed", "failed", "paid", "official"
            ) else "pending",
            "Checklist / văn bằng / TA",
            "coord-handoff",
        )
        add(
            "written",
            "Thi viết",
            "done" if app.get("written_score") not in (None, "") else "pending",
            f"Điểm viết: {app.get('written_score')}",
            "written-exam",
        )
        # Interview
        slot = None
        if app_id:
            slot = cur.execute(
                "SELECT sl.result, sl.score_conclusion, sl.scheduled_at, s.title, s.room "
                "FROM interview_slots sl JOIN interview_sessions s ON s.id = sl.session_id "
                "WHERE sl.application_id = ? ORDER BY sl.id DESC LIMIT 1",
                (app_id,),
            ).fetchone()
        if slot:
            add(
                "interview",
                "Lịch & kết quả phỏng vấn",
                "done" if slot[0] in ("pass", "fail") else "pending",
                f"{slot[3]} · {slot[4]} · {slot[2]} · KQ: {slot[0]} ({slot[1]})",
                "interview-slot",
            )
        else:
            add("interview", "Lịch & kết quả phỏng vấn", "pending", "", "interview-slot")

        add(
            "admission_result",
            "Kết quả trúng tuyển",
            "done" if app.get("status") in ("passed", "paid", "official") else (
                "done" if app.get("status") == "failed" else "pending"
            ),
            f"KQ: {app.get('final_result') or app.get('status')} · TB: {app.get('avg_score')}",
            "applications",
        )

        fee = None
        if app_id:
            fee = cur.execute(
                "SELECT status, amount, paid_at, proof_note FROM enrollment_fees WHERE application_id=?",
                (app_id,),
            ).fetchone()
        if fee:
            add(
                "fee",
                "Thanh toán phí ghi danh",
                "done" if fee[0] == "paid" else "pending",
                f"{fee[1]:,.0f} VND · {fee[0]} · {fee[2] or ''} · {fee[3] or ''}",
                "fees",
            )
        else:
            add("fee", "Thanh toán phí ghi danh", "pending", "", "fees")

        add(
            "official",
            "Nhập học chính thức (Official)",
            "done" if app.get("status") == "official" or student_id else "pending",
            f"Mã HV: {st.get('student_code') or app.get('student_code') or '—'}",
            "official",
        )
    else:
        add("application", "Hồ sơ tuyển sinh", "n/a", "Chưa liên kết hồ sơ")

    # Academic
    if student_id and class_id:
        add(
            "enrolled",
            "Xếp lớp / danh sách học viên",
            "done",
            f"Lớp: {st.get('class_name')} · {st.get('program_code')}",
            "students",
        )
        grades = cur.execute(
            "SELECT c.code, c.name, g.score, g.group_assignment, g.final_exam "
            "FROM course_grades g JOIN courses c ON c.id = g.course_id "
            "WHERE g.student_id = ? ORDER BY c.sort_order, c.code",
            (student_id,),
        ).fetchall()
        if grades:
            detail = "; ".join(
                f"{r[0]}={r[2]}" + (f" (GA{r[3]}/FE{r[4]})" if r[3] is not None else "")
                for r in grades
            )
            add("grades", "Điểm từng môn học", "done", detail, "grade-synthesis")
        else:
            add("grades", "Điểm từng môn học", "pending", "", "grade-synthesis")

        att = cur.execute(
            "SELECT COUNT(*) FROM attendance_marks WHERE student_id = ?",
            (student_id,),
        ).fetchone()[0]
        add(
            "attendance",
            "Điểm danh các buổi học",
            "done" if att else "pending",
            f"{att} buổi đã điểm danh",
            "attendance-matrix",
        )

        exams = cur.execute(
            "SELECT c.code, e.exam_type, e.exam_date, e.status "
            "FROM exam_schedules e JOIN courses c ON c.id = e.course_id "
            "WHERE e.class_id = ? ORDER BY e.exam_date",
            (class_id,),
        ).fetchall()
        if exams:
            add(
                "exams",
                "Lịch / hoàn thành bài thi",
                "done",
                "; ".join(f"{r[0]} {r[1]} ({r[3]})" for r in exams),
                "exams",
            )
        else:
            add("exams", "Lịch / hoàn thành bài thi", "pending", "", "exams")

        thesis = cur.execute(
            "SELECT title, status, total_grade, defense_date FROM thesis_records WHERE student_id=?",
            (student_id,),
        ).fetchone()
        if thesis:
            add(
                "thesis",
                "Chuyên đề / luận văn tốt nghiệp",
                "done" if thesis[1] == "defended" else "pending",
                f"{thesis[0]} · {thesis[1]} · điểm {thesis[2]} · BV {thesis[3] or ''}",
                "thesis",
            )
        else:
            add("thesis", "Chuyên đề / luận văn tốt nghiệp", "pending", "", "thesis")

        life = st.get("lifecycle_status") or ""
        add(
            "graduation",
            "Xét tốt nghiệp",
            "done" if life == "graduated" else "pending",
            f"Lifecycle: {life}",
            "students",
        )
        alum = cur.execute(
            "SELECT id FROM alumni_members WHERE lower(IFNULL(email,'')) = lower(?) "
            "AND program_code = ? LIMIT 1",
            (st.get("email") or app.get("email") or "", st.get("program_code") or app.get("program_code") or ""),
        ).fetchone()
        add(
            "alumni",
            "Chuyển Alumni",
            "done" if alum else "pending",
            f"Alumni id={alum[0]}" if alum else "",
            "alumni",
        )
    else:
        add("enrolled", "Xếp lớp", "pending", "Chưa có bản ghi class_students")

    done = sum(1 for s in stages if s["status"] == "done")
    return {
        "ok": True,
        "profile": {
            "full_name": (st or app).get("full_name"),
            "program_code": (st or app).get("program_code"),
            "email": (st or app).get("email") or app.get("email"),
            "student_code": st.get("student_code") or app.get("student_code"),
            "class_name": st.get("class_name"),
            "lifecycle_status": st.get("lifecycle_status"),
            "application_status": app.get("status"),
            "login": ident.get("login"),
            "degree_grade": app.get("degree_grade") or app.get("gpa") or "",
            "avg_score": app.get("avg_score") or "",
            "written_score": app.get("written_score") or "",
            "interview_score": app.get("interview_score") or "",
            "dob": app.get("dob") or st.get("dob") or "",
        },
        "stages": stages,
        "progress": {"done": done, "total": len(stages)},
        "print_hint": "In toàn bộ lộ trình hoặc xuất CSV từng khâu (print_entity).",
    }


def student_timeline_rows(conn, *, user_id: int | None = None, email: str = "") -> list[dict]:
    data = get_student_timeline(conn, user_id=user_id, email=email)
    if not data.get("ok"):
        return []
    profile = data.get("profile") or {}
    rows = []
    for s in data.get("stages") or []:
        rows.append(
            {
                "id": s["id"],
                "stage_no": s["id"],
                "code": s["code"],
                "title": s["title"],
                "status": s["status"],
                "detail": s["detail"],
                "print_entity": s.get("print_entity") or "",
                "full_name": profile.get("full_name"),
                "program_code": profile.get("program_code"),
                "student_code": profile.get("student_code"),
                "degree_grade": profile.get("degree_grade"),
                "avg_score": profile.get("avg_score"),
                "written_score": profile.get("written_score"),
                "interview_score": profile.get("interview_score"),
            }
        )
    return rows


def student_schedule_rows(conn, *, user_id: int | None = None, email: str = "") -> list[dict]:
    ident = resolve_student_identity(conn, user_id=user_id, email=email)
    if not ident:
        return []
    cur = conn.cursor()
    rows = []
    app = ident.get("application") or {}
    st = ident.get("student") or {}
    if app.get("id"):
        for r in cur.execute(
            "SELECT s.title, s.program_code, s.room, sl.scheduled_at, sl.result "
            "FROM interview_slots sl JOIN interview_sessions s ON s.id = sl.session_id "
            "WHERE sl.application_id = ?",
            (app["id"],),
        ).fetchall():
            rows.append(
                {
                    "id": f"pv-{r[0]}",
                    "kind": "interview",
                    "title": r[0],
                    "program_code": r[1],
                    "room": r[2],
                    "starts_at": r[3],
                    "result": r[4],
                }
            )
    if st.get("class_id"):
        for r in cur.execute(
            "SELECT c.code, c.name, e.exam_type, e.exam_date, e.room, e.status, e.title "
            "FROM exam_schedules e JOIN courses c ON c.id = e.course_id "
            "WHERE e.class_id = ? ORDER BY e.exam_date",
            (st["class_id"],),
        ).fetchall():
            rows.append(
                {
                    "id": f"ex-{r[0]}-{r[2]}",
                    "kind": "exam",
                    "title": r[6] or f"Thi {r[2]}: {r[0]} — {r[1]}",
                    "program_code": st.get("program_code"),
                    "room": r[4] or "",
                    "starts_at": r[3],
                    "result": r[5],
                }
            )
    return rows
