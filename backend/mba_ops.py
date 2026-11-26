"""
MBA coordinator ops — written exam, score import, interview boards,
student lifecycle helpers, attendance eligibility, program version copy.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


MBA_APP_COLUMNS = [
    ("written_score", "REAL"),
    ("written_exam_no", "TEXT"),
    ("written_exam_date", "TEXT"),
    ("written_exam_room", "TEXT"),
    ("written_exam_session", "TEXT"),  # ca thi
    ("transferred_at", "TEXT"),  # TS → Điều phối
    ("transferred_by", "TEXT"),
    # MBA34 Student list (1.2.2 / CĐS-1.3.2)
    ("intake_session", "TEXT"),  # May | August
    ("student_code_mba", "TEXT"),  # HN34MBA001
    ("eco_background", "TEXT"),  # Yes | No
    ("master_level", "TEXT"),
    ("bachelor_start_year", "TEXT"),
    ("bachelor_grad_year", "TEXT"),
    ("job_title", "TEXT"),
    ("management_years", "REAL"),
    ("english_note", "TEXT"),
    ("naric_status", "TEXT"),
    ("naric_note", "TEXT"),
    ("exam_eligible_flag", "TEXT"),
    ("other_achievements", "TEXT"),
    ("interview_score", "REAL"),  # /20 avg
    ("interview_jury1", "REAL"),
    ("interview_jury2", "REAL"),
    ("interview_jury3", "REAL"),
    ("written_gk", "REAL"),  # General Knowledge & Economic /20
    ("written_mle", "REAL"),  # Maths+Logic+English /20
    ("avg_score", "REAL"),  # Điểm trung bình /20
    ("confirmation_status", "TEXT"),  # Study | Postpone | Defer | Drop
    ("board_decision", "TEXT"),  # Trúng tuyển …
    ("exam_format", "TEXT"),  # written | interview | written_interview
    ("exam_board", "TEXT"),
    ("admitted_program", "TEXT"),
    # Trục trạng thái tách riêng. Workflow `status` vẫn phục vụ bàn giao bộ phận.
    ("dossier_status", "TEXT"),  # incomplete | under_review | eligible
    ("sitting_status", "TEXT"),  # scheduled | sat | absent | cancelled
    ("selection_status", "TEXT"),  # pending | conditional | admitted | rejected | not_considered
    ("decision_status", "TEXT"),  # draft | approved | effective
    ("response_status", "TEXT"),  # study | defer | withdraw | postpone
    ("result_reserve_status", "TEXT"),  # bảo lưu kết quả tuyển sinh, khác bảo lưu học tập
    ("scores_locked", "INTEGER DEFAULT 0"),
    ("written_gk_raw", "REAL"),
    ("written_gk_max", "REAL"),
    ("written_mle_raw", "REAL"),
    ("written_mle_max", "REAL"),
]

COURSE_RULE_COLUMNS = [
    ("component_weight_ga", "REAL"),
    ("component_weight_fe", "REAL"),
    ("score_rule_status", "TEXT"),  # draft | published
    ("contact_minutes", "INTEGER"),
]

ROUND_EXTRA_COLUMNS = [
    ("intake", "TEXT"),
    ("exam_timeline", "TEXT"),
    ("interview_timeline", "TEXT"),
    ("cohort", "TEXT"),
    ("apply_due_date", "TEXT"),
    ("exam_date", "TEXT"),
    ("result_date", "TEXT"),
]

STUDENT_LIFECYCLE_COLUMNS = [
    ("lifecycle_status", "TEXT"),
    ("scholarship_type", "TEXT"),
    ("partner_enrollment", "TEXT"),
    ("reserve_note", "TEXT"),
    # Roster / attendance / grade file identity (MBA34)
    ("place_of_birth", "TEXT"),
    ("phone", "TEXT"),
    ("job_title", "TEXT"),
    ("management_years", "REAL"),
    ("company", "TEXT"),
    ("intake_session", "TEXT"),
    ("exchange_flag", "TEXT"),
    ("enrolled_at", "TEXT"),
    ("cccd", "TEXT"),
]

# Corporate Finance style: Group assignment 30% + Final exam 70%
COURSE_GRADE_EXTRA_COLUMNS = [
    ("group_assignment", "REAL"),
    ("final_exam", "REAL"),
    ("anonymous_no", "TEXT"),
    ("remarks", "TEXT"),
]

# Fractional check-in / check-out (0 | 0.5 | 1) — Excel attendance matrix
ATTENDANCE_MARK_EXTRA_COLUMNS = [
    ("check_in", "REAL"),
    ("check_out", "REAL"),
    ("excused", "INTEGER DEFAULT 0"),
    ("exception_kind", "TEXT"),  # late | left_early | excused
]

FACULTY_EXTRA_COLUMNS = [
    ("phone", "TEXT"),
    ("nationality", "TEXT"),
    ("passport_no", "TEXT"),
    ("bank_account", "TEXT"),
    ("cv_note", "TEXT"),
    ("teaching_history_note", "TEXT"),  # CT / năm / môn đã dạy tại CFVG
    ("contract_status", "TEXT"),  # draft | signed | paid | closed
    ("contract_no", "TEXT"),
    ("grade_return_date", "TEXT"),
    ("cfvg_payment_status", "TEXT"),  # unpaid | processing | paid
    ("insurance_note", "TEXT"),
]

SCHOLARSHIP_TYPES = (
    "",
    "none",
    "cfvg",
    "partner",
    "french_gov",
    "partial",
    "other",
)

INTL_STUDENT_EXTRA_COLUMNS = [
    ("direction", "TEXT"),  # incoming | outgoing
    ("semester", "TEXT"),  # S1 | S2 | S3 | year
    ("exchange_kind", "TEXT"),  # double_degree | one_semester | other
    ("partner_university", "TEXT"),
    ("handoff_visa_by", "TEXT"),
    ("handoff_iae_by", "TEXT"),
    ("handoff_courses_by", "TEXT"),
    ("accounting_note", "TEXT"),
]

LIFECYCLE_STATUSES = {
    "active",
    "reserved",
    "on_leave",
    "withdrawn_program",
    "graduated",
}

JURY_ROLES = ("CFVG", "IAE", "Alumni")
MASTER_JURY_ROLES = ("Giám đốc", "Alumni")


def interview_board_defaults(program_code: str) -> dict:
    """MBA keeps ~10 candidates and three jury seats. MSCM/MMS: 6 and Director + alumni."""
    prog = (program_code or "MBA").strip().upper() or "MBA"
    if prog == "MBA":
        return {"max_per_board": 10, "board_count": 4, "jury": list(JURY_ROLES)}
    return {"max_per_board": 6, "board_count": 4, "jury": list(MASTER_JURY_ROLES)}


def _table_exists(cur, table: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    return bool(row)


def _table_cols(cur, table: str) -> set[str]:
    if not _table_exists(cur, table):
        return set()
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_missing_columns(cur, table: str, columns: list[tuple[str, str]]) -> None:
    if not _table_exists(cur, table):
        return
    existing = _table_cols(cur, table)
    for name, typ in columns:
        if name not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")


def ensure_mba_tables(cur) -> None:
    from ops_data import ensure_ops_tables
    from asst_ops import ensure_asst_tables

    ensure_ops_tables(cur)
    ensure_asst_tables(cur)
    _add_missing_columns(cur, "applications", MBA_APP_COLUMNS)
    _add_missing_columns(cur, "admission_rounds", ROUND_EXTRA_COLUMNS)
    try:
        from admission_ops import ensure_admission_tables

        ensure_admission_tables(cur)
    except Exception:
        pass
    _add_missing_columns(cur, "class_students", STUDENT_LIFECYCLE_COLUMNS)
    _add_missing_columns(cur, "faculty", FACULTY_EXTRA_COLUMNS)
    _add_missing_columns(cur, "asst_intl_students", INTL_STUDENT_EXTRA_COLUMNS)
    _add_missing_columns(
        cur,
        "attendance_marks",
        [("present_after_break", "INTEGER DEFAULT 1")] + ATTENDANCE_MARK_EXTRA_COLUMNS,
    )
    if _table_exists(cur, "course_grades"):
        _add_missing_columns(cur, "course_grades", COURSE_GRADE_EXTRA_COLUMNS)
    _add_missing_columns(
        cur,
        "course_evaluations",
        [
            ("report_status", "TEXT"),
            ("sent_mgmt_at", "TEXT"),
            ("sent_faculty_at", "TEXT"),
        ],
    )
    _add_missing_columns(cur, "interview_scores", [("jury_role", "TEXT")])
    if _table_exists(cur, "attendance_sessions"):
        cur.execute(
            "CREATE TABLE IF NOT EXISTS attendance_marks ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "attendance_session_id INTEGER NOT NULL, "
            "student_id INTEGER NOT NULL, "
            "present INTEGER DEFAULT 1, "
            "present_after_break INTEGER DEFAULT 1, "
            "note TEXT, "
            "UNIQUE(attendance_session_id, student_id), "
            "FOREIGN KEY (attendance_session_id) REFERENCES attendance_sessions(id), "
            "FOREIGN KEY (student_id) REFERENCES class_students(id))"
        )
        _add_missing_columns(cur, "attendance_marks", ATTENDANCE_MARK_EXTRA_COLUMNS)
        _add_missing_columns(cur, "attendance_sessions", [("planned_minutes", "INTEGER")])
    if _table_exists(cur, "courses"):
        _add_missing_columns(cur, "courses", COURSE_RULE_COLUMNS)
    if _table_exists(cur, "program_versions"):
        _add_missing_columns(cur, "program_versions", [("version_status", "TEXT")])
    cur.execute(
        "CREATE TABLE IF NOT EXISTS admission_score_rules ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "round_id INTEGER NOT NULL, "
        "version_label TEXT, "
        "formula_json TEXT, "
        "status TEXT NOT NULL DEFAULT 'draft', "
        "note TEXT, "
        "UNIQUE(round_id, version_label))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS application_exam_sittings ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "application_id INTEGER NOT NULL, "
        "round_id INTEGER, "
        "session_label TEXT NOT NULL, "
        "convocation_no TEXT, "
        "UNIQUE(application_id, session_label))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS academic_policies ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "program_code TEXT NOT NULL, "
        "policy_key TEXT NOT NULL, "
        "absent_limit_pct REAL NOT NULL DEFAULT 30, "
        "absent_operator TEXT NOT NULL DEFAULT 'gt', "
        "excused_counts INTEGER NOT NULL DEFAULT 0, "
        "status TEXT NOT NULL DEFAULT 'draft', "
        "note TEXT, "
        "UNIQUE(program_code, policy_key))"
    )
    cur.execute(
        "SELECT 1 FROM academic_policies WHERE program_code = 'MBA' AND policy_key = 'absence'"
    )
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO academic_policies ("
            "program_code, policy_key, absent_limit_pct, absent_operator, excused_counts, status, note"
            ") VALUES ('MBA', 'absence', 30, 'gt', 0, 'published', ?)",
            (
                "Không nghỉ quá 30% tổng giờ môn: vắng mặt chỉ khi tỷ lệ > 30%. "
                "Vắng có phép không tính vào tỷ lệ cho đến khi quy chế nói khác. "
                "Chưa có giờ học thì chưa kết luận điều kiện dự thi.",
            ),
        )
    _backfill_admission_axes(cur)
    _backfill_exam_sittings(cur)


def _blank(value) -> bool:
    return value is None or str(value).strip() == ""


def _backfill_admission_axes(cur) -> None:
    """Điền trục trạng thái còn trống từ hồ sơ hiện có. Không ghi đè giá trị đã chốt."""
    if "dossier_status" not in _table_cols(cur, "applications"):
        return
    rows = cur.execute(
        "SELECT id, IFNULL(status,''), IFNULL(exam_eligible_flag,''), IFNULL(board_decision,''), "
        "IFNULL(confirmation_status,''), written_score, IFNULL(written_exam_no,''), "
        "IFNULL(dossier_status,''), IFNULL(selection_status,''), IFNULL(decision_status,''), "
        "IFNULL(response_status,''), IFNULL(sitting_status,''), IFNULL(result_reserve_status,'') "
        "FROM applications"
    ).fetchall()
    for (
        app_id, status, eligible, board, confirm, written, exam_no,
        dossier, selection, decision, response, sitting, reserve,
    ) in rows:
        st = status.strip().lower()
        board_l = board.lower()
        confirm_l = confirm.lower()
        sets = []
        params = []
        if _blank(dossier):
            if eligible.strip().lower() in ("yes", "1", "true") or st in (
                "approved_ts", "interview", "passed", "paid", "official", "failed",
            ):
                sets.append("dossier_status = ?")
                params.append("eligible")
            elif st == "submitted":
                sets.append("dossier_status = ?")
                params.append("under_review")
            else:
                sets.append("dossier_status = ?")
                params.append("incomplete")
        if _blank(sitting):
            if written not in (None, ""):
                sets.append("sitting_status = ?")
                params.append("sat")
            elif exam_no:
                sets.append("sitting_status = ?")
                params.append("scheduled")
            elif st == "withdrawn":
                sets.append("sitting_status = ?")
                params.append("cancelled")
        if _blank(selection):
            if "điều kiện" in board_l or "conditional" in board_l:
                sets.append("selection_status = ?")
                params.append("conditional")
            elif "không xét" in board_l:
                sets.append("selection_status = ?")
                params.append("not_considered")
            elif "trúng" in board_l or board_l == "admitted" or st in ("passed", "paid", "official"):
                sets.append("selection_status = ?")
                params.append("admitted")
            elif st == "failed" or "không đ" in board_l:
                sets.append("selection_status = ?")
                params.append("rejected")
            elif st in ("submitted", "approved_ts", "interview"):
                sets.append("selection_status = ?")
                params.append("pending")
        if _blank(decision):
            if st == "official":
                sets.append("decision_status = ?")
                params.append("effective")
            elif st in ("passed", "paid"):
                sets.append("decision_status = ?")
                params.append("approved")
            elif board:
                sets.append("decision_status = ?")
                params.append("draft")
        if _blank(response):
            if any(k in confirm_l for k in ("study", "confirmed", "theo học")):
                sets.append("response_status = ?")
                params.append("study")
            elif "postpone" in confirm_l or "bảo lưu" in confirm_l:
                sets.append("response_status = ?")
                params.append("postpone")
            elif "defer" in confirm_l or "hoãn" in confirm_l:
                sets.append("response_status = ?")
                params.append("defer")
            elif "drop" in confirm_l or "rút" in confirm_l or st == "withdrawn":
                sets.append("response_status = ?")
                params.append("withdraw")
        if _blank(reserve) and ("postpone" in confirm_l or "bảo lưu kết quả" in confirm_l):
            sets.append("result_reserve_status = ?")
            params.append("requested")
        if sets:
            params.append(app_id)
            cur.execute(
                f"UPDATE applications SET {', '.join(sets)} WHERE id = ?",
                params,
            )


def _backfill_exam_sittings(cur) -> None:
    if not _table_exists(cur, "application_exam_sittings"):
        return
    rows = cur.execute(
        "SELECT id, round_id, IFNULL(intake_session,''), IFNULL(written_exam_no,'') "
        "FROM applications WHERE IFNULL(intake_session,'') != ''"
    ).fetchall()
    for app_id, round_id, session, convocation in rows:
        for label in [p.strip() for p in session.replace("+", ",").split(",") if p.strip()]:
            cur.execute(
                "INSERT OR IGNORE INTO application_exam_sittings "
                "(application_id, round_id, session_label, convocation_no) VALUES (?,?,?,?)",
                (app_id, round_id, label, convocation or None),
            )


def exam_session_labels(raw: dict) -> list[str]:
    """Một hồ sơ có thể thi cả hai đợt. Không lưu hai cột cờ May/August."""
    labels: list[str] = []
    session = str(raw.get("intake_session") or raw.get("Session") or "").strip()
    if session:
        for part in session.replace("+", ",").split(","):
            part = part.strip()
            if part and part not in labels:
                labels.append(part)
    for label, key in (("May", "May Session"), ("August", "August Session")):
        val = raw.get(key)
        if val in (None, "", 0, "0", "0.0", False):
            continue
        if label not in labels:
            labels.append(label)
    return labels


def remember_exam_sittings(cur, application_id: int, labels: list[str], round_id: int | None) -> None:
    for label in labels:
        cur.execute(
            "INSERT OR IGNORE INTO application_exam_sittings "
            "(application_id, round_id, session_label) VALUES (?,?,?)",
            (int(application_id), round_id, label),
        )


def _recalc_exam_scores(cur, app_id: int) -> None:
    """Không tự lấy trung bình giám khảo hay trung bình viết/phỏng vấn.

    Điểm tổng hợp chỉ được ghi khi đợt có quy chế điểm status=published và hồ sơ chưa khóa.
    Chưa có quy chế đã ban hành thì giữ nguyên điểm gốc đã nhập.
    """
    if not _table_exists(cur, "admission_score_rules"):
        return
    cols = _table_cols(cur, "applications")
    if "scores_locked" in cols:
        locked = cur.execute(
            "SELECT IFNULL(scores_locked, 0) FROM applications WHERE id = ?",
            (app_id,),
        ).fetchone()
        if locked and int(locked[0] or 0):
            return
    rule = cur.execute(
        "SELECT formula_json FROM admission_score_rules r "
        "JOIN applications a ON a.round_id = r.round_id "
        "WHERE a.id = ? AND r.status = 'published' "
        "AND IFNULL(r.formula_json, '') != '' "
        "ORDER BY r.id DESC LIMIT 1",
        (app_id,),
    ).fetchone()
    if not rule:
        return
    # Công thức lưu trong quy chế. Không áp trung bình mặc định khi JSON chưa khai báo phép tính.
    return


def assign_written_exam_numbers(
    conn,
    *,
    round_id: int | None = None,
    program_code: str = "MBA",
    prefix: str | None = None,
    start: int = 1,
    preview: bool = False,
    eligible_only: bool = True,
) -> dict:
    """Assign SBD with prefix + start; preview; unique per round; roster = đủ ĐK dự thi."""
    cur = conn.cursor()
    ensure_mba_tables(cur)
    prefix = (prefix or f"{program_code}-{datetime.now().year}-").strip()
    start = int(start or 1)
    sql = (
        "SELECT id, IFNULL(written_exam_no,''), IFNULL(exam_eligible_flag,''), status "
        "FROM applications WHERE program_code = ? "
        "AND status IN ('approved_ts','interview','passed','failed','paid','official') "
        "AND (written_exam_no IS NULL OR written_exam_no = '') "
    )
    params: list[Any] = [program_code]
    if round_id:
        sql += "AND round_id = ? "
        params.append(round_id)
    sql += "ORDER BY id"
    rows = cur.execute(sql, params).fetchall()
    used = {
        r[0]
        for r in cur.execute(
            "SELECT written_exam_no FROM applications WHERE IFNULL(written_exam_no,'') != ''"
            + (" AND round_id = ?" if round_id else ""),
            ([round_id] if round_id else []),
        ).fetchall()
        if r[0]
    }
    preview_rows = []
    assigned = 0
    skipped = 0
    from learner_spine import entrance_sitting_ready

    n = start
    for aid, existing, flag, status in rows:
        del existing, flag
        if eligible_only:
            ready, _why = entrance_sitting_ready(cur, aid)
            if not ready and status not in ("paid", "official"):
                skipped += 1
                continue
        while True:
            sbd = f"{prefix}{n:03d}" if not prefix.endswith("-") else f"{prefix}{n:03d}"
            n += 1
            if sbd not in used:
                break
        used.add(sbd)
        preview_rows.append({"application_id": aid, "written_exam_no": sbd})
        if preview:
            continue
        cur.execute("UPDATE applications SET written_exam_no = ? WHERE id = ?", (sbd, aid))
        assigned += 1
    if not preview:
        conn.commit()
    return {
        "assigned": assigned,
        "skipped": skipped,
        "preview": preview,
        "rows": preview_rows,
        "program_code": program_code,
        "round_id": round_id,
        "prefix": prefix,
        "start": start,
    }


def import_round_scores(conn, rows: list[dict], *, program_code: str = "MBA") -> dict:
    """Import written / interview conclusion scores for a round."""
    cur = conn.cursor()
    ensure_mba_tables(cur)
    updated = 0
    not_found = 0
    for raw in rows:
        app_id = None
        for key, col in (
            ("cfvg_app_no", "cfvg_app_no"),
            ("written_exam_no", "written_exam_no"),
            ("student_code_mba", "student_code_mba"),
            ("Student code", "student_code_mba"),
            ("email", "email"),
        ):
            val = (raw.get(key) or "").strip()
            if not val:
                continue
            cur.execute(
                f"SELECT id FROM applications WHERE {col} = ? AND program_code = ?",
                (val, program_code),
            )
            hit = cur.fetchone()
            if hit:
                app_id = hit[0]
                break
        if not app_id and (raw.get("full_name") or "").strip():
            cur.execute(
                "SELECT id FROM applications WHERE full_name = ? AND program_code = ? "
                "ORDER BY id DESC LIMIT 1",
                (raw["full_name"].strip(), program_code),
            )
            hit = cur.fetchone()
            if hit:
                app_id = hit[0]
        if not app_id:
            not_found += 1
            continue
        if "scores_locked" in _table_cols(cur, "applications"):
            locked = cur.execute(
                "SELECT IFNULL(scores_locked, 0) FROM applications WHERE id = ?",
                (app_id,),
            ).fetchone()
            if locked and int(locked[0] or 0):
                continue

        fields: list[str] = []
        params: list[Any] = []
        set_cols: set[str] = set()

        def _set_num(col: str, val: Any) -> None:
            if col in set_cols or val in (None, ""):
                return
            try:
                fields.append(f"{col} = ?")
                params.append(float(val))
                set_cols.add(col)
            except (TypeError, ValueError):
                pass

        def _set_text(col: str, val: Any, *, maxlen: int = 200) -> None:
            if col in set_cols or val in (None, ""):
                return
            fields.append(f"{col} = ?")
            params.append(str(val).strip()[:maxlen])
            set_cols.add(col)

        _set_num("written_score", raw.get("written_score") or raw.get("Điểm viết | /20"))
        for src, col in (
            ("written_gk", "written_gk"),
            ("written_mle", "written_mle"),
            ("avg_score", "avg_score"),
            ("interview_score", "interview_score"),
            ("interview_jury1", "interview_jury1"),
            ("interview_jury2", "interview_jury2"),
            ("interview_jury3", "interview_jury3"),
            ("General Knowledge & Economic/20", "written_gk"),
            ("(Maths+Logic+English)/20", "written_mle"),
            ("General Knowledge & Economic/45", "written_gk_raw"),
            ("(Maths+Logic+English)/22", "written_mle_raw"),
            ("Điểm trung bình | /20", "avg_score"),
            ("Điểm phỏng vấn | /20", "interview_score"),
        ):
            _set_num(col, raw.get(src))
        for src, col in (
            ("intake_session", "intake_session"),
            ("Session", "intake_session"),
            ("student_code_mba", "student_code_mba"),
            ("Student code", "student_code_mba"),
            ("confirmation_status", "confirmation_status"),
            ("Confirmation to Study/Postpone/Defer/Drop", "confirmation_status"),
            ("board_decision", "board_decision"),
            ("Quyết định HĐ TS CFVG HN", "board_decision"),
            ("eco_background", "eco_background"),
            ("Eco/Non-eco", "eco_background"),
            ("job_title", "job_title"),
            ("Vị trí", "job_title"),
            ("Vị trí", "job_title"),
        ):
            _set_text(col, raw.get(src))
        _set_text("written_exam_no", raw.get("written_exam_no"), maxlen=64)
        _set_text("written_exam_date", raw.get("written_exam_date"), maxlen=32)
        _set_text("written_exam_room", raw.get("written_exam_room"), maxlen=64)
        _set_text(
            "written_exam_session",
            raw.get("written_exam_session") or raw.get("exam_session"),
            maxlen=64,
        )

        result = (
            raw.get("interview_result")
            or raw.get("final_result")
            or raw.get("board_decision")
            or ""
        ).strip()
        low = result.lower()
        conditional = ("điều kiện" in low) or ("conditional" in low)
        if conditional:
            _set_text("selection_status", "conditional")
            _set_text("decision_status", "draft")
        elif low in ("passed", "admitted") or "trúng tuyển" in low:
            _set_text("selection_status", "admitted")
            _set_text("final_result", "Admitted")
        elif low in ("failed", "non-admitted", "non_admitted") or "không xét" in low:
            _set_text("selection_status", "not_considered" if "không xét" in low else "rejected")
            _set_text("final_result", "Non-Admitted")
        if "written_gk_raw" in set_cols:
            _set_num("written_gk_max", 45)
        if "written_mle_raw" in set_cols:
            _set_num("written_mle_max", 22)

        if fields:
            params.append(app_id)
            cur.execute(f"UPDATE applications SET {', '.join(fields)} WHERE id = ?", params)
            _recalc_exam_scores(cur, app_id)
            updated += 1
    conn.commit()
    return {"updated": updated, "not_found": not_found, "program_code": program_code}


def create_interview_boards(
    conn,
    *,
    round_id: int,
    program_code: str = "MBA",
    board_count: int = 4,
    room_prefix: str = "Room",
    starts_at: str | None = None,
    slot_minutes: int = 20,
    max_per_board: int = 10,
    queue_confirm_emails: bool = True,
    application_ids: list[int] | None = None,
) -> dict:
    """Create N interview sessions and fill slots from approved applicants.

    MBA practice: ~4–5 boards, ~9–10 candidates/board, 20 minutes/slot.
    Optionally queue confirmation emails to applicant inboxes.

    When ``application_ids`` is provided, only those candidates (within the
    round/program and eligible status) are scheduled — this powers the
    coordinator flow of hand-picking candidates from the list.
    """
    cur = conn.cursor()
    ensure_mba_tables(cur)
    from coord_ops import ensure_coord_tables
    from ops_data import ensure_ops_tables

    ensure_coord_tables(cur)
    ensure_ops_tables(cur)

    selected = [int(x) for x in (application_ids or []) if str(x).strip()]
    if selected:
        placeholders = ",".join("?" * len(selected))
        cur.execute(
            "SELECT id, full_name, email FROM applications "
            "WHERE round_id = ? AND program_code = ? "
            "AND status IN ('approved_ts','interview') "
            f"AND id IN ({placeholders}) "
            "ORDER BY id",
            (round_id, program_code, *selected),
        )
    else:
        cur.execute(
            "SELECT id, full_name, email FROM applications "
            "WHERE round_id = ? AND program_code = ? "
            "AND status IN ('approved_ts','interview') "
            "ORDER BY id",
            (round_id, program_code),
        )
    apps = cur.fetchall()
    if not apps:
        raise ValueError(
            "Không có thí sinh đủ điều kiện (đã duyệt TS) trong đợt/lựa chọn này."
            if selected
            else "No applicants ready for interview boards"
        )
    from learner_spine import entrance_sitting_ready

    ready_apps = []
    blocked = []
    for app_row in apps:
        ok_ready, why = entrance_sitting_ready(cur, app_row[0])
        if ok_ready:
            ready_apps.append(app_row)
        else:
            blocked.append(why)
    if not ready_apps:
        sample = blocked[0] if blocked else "Chưa đủ bước xác nhận dự thi."
        raise ValueError(
            "Không lập được hội đồng. Hồ sơ cần được Tuyển sinh xác nhận dự thi, "
            "đăng ký nội dung thi, và Kế toán xác nhận lệ phí nếu đợt yêu cầu. "
            + sample
        )
    apps = ready_apps

    max_per_board = max(1, min(int(max_per_board or 10), 20))
    board_count = max(1, min(int(board_count or 4), 12))
    # Auto-expand boards if applicants exceed capacity
    needed = (len(apps) + max_per_board - 1) // max_per_board
    if needed > board_count:
        board_count = needed
    start = datetime.fromisoformat(starts_at) if starts_at else datetime.now() + timedelta(days=3)
    created_sessions = 0
    created_slots = 0
    emails_queued = 0
    idx = 0
    for b in range(board_count):
        chunk = apps[idx : idx + max_per_board]
        idx += max_per_board
        if not chunk:
            break
        title = f"{program_code} Interview Board {b + 1}"
        room = f"{room_prefix} {b + 1}"
        sess_start = start + timedelta(hours=b)
        cur.execute(
            "INSERT INTO interview_sessions "
            "(round_id, program_code, title, room, starts_at, slot_minutes, owner) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                round_id,
                program_code,
                title,
                room,
                sess_start.isoformat(sep=" ", timespec="minutes"),
                slot_minutes,
                "Điều phối CT",
            ),
        )
        sid = cur.lastrowid
        created_sessions += 1
        for order, app_row in enumerate(chunk, start=1):
            aid = app_row[0]
            aname = app_row[1]
            aemail = (app_row[2] or "").strip() if len(app_row) > 2 else ""
            slot_at = sess_start + timedelta(minutes=(order - 1) * slot_minutes)
            slot_label = slot_at.isoformat(sep=" ", timespec="minutes")
            cur.execute(
                "INSERT INTO interview_slots "
                "(session_id, application_id, slot_order, scheduled_at, result) "
                "VALUES (?,?,?,?, 'pending')",
                (sid, aid, order, slot_label),
            )
            slot_id = cur.lastrowid
            created_slots += 1
            jury_roles = interview_board_defaults(program_code)["jury"]
            for j, role in enumerate(jury_roles):
                jury_name = f"{role} Jury" if (program_code or "").upper() == "MBA" else role
                cur.execute(
                    "INSERT INTO interview_scores "
                    "(slot_id, jury_name, score, sort_order, jury_role) "
                    "VALUES (?,?, '', ?, ?)",
                    (slot_id, jury_name, j, role),
                )
            cur.execute(
                "UPDATE applications SET status = 'interview' "
                "WHERE id = ? AND status = 'approved_ts'",
                (aid,),
            )
            if queue_confirm_emails and aemail:
                from ops_crud import queue_email

                queue_email(
                    conn,
                    kind="interview_confirm",
                    recipient=aemail,
                    subject=f"[{program_code}] Interview schedule confirmation",
                    body=(
                        f"Dear {aname},\n\n"
                        f"Your interview is scheduled as follows:\n"
                        f"- Board: {title}\n"
                        f"- Room: {room}\n"
                        f"- Time: {slot_label}\n"
                        f"- Duration: {slot_minutes} minutes\n\n"
                        f"Please arrive 10 minutes early.\n\n"
                        f"SmartUni / CFVG"
                    ),
                )
                emails_queued += 1
    scheduled_ids = [int(app_row[0]) for app_row in apps]
    try:
        from learner_spine import refresh_learner_stages

        refresh_learner_stages(conn, scheduled_ids)
    except Exception:
        conn.commit()
    return {
        "sessions": created_sessions,
        "slots": created_slots,
        "applicants": len(apps),
        "board_count": created_sessions,
        "max_per_board": max_per_board,
        "emails_queued": emails_queued,
        "skipped_not_ready": len(blocked),
    }


def notify_ineligible_students(
    conn, scopes: list[str] | None, *, max_absent_pct: float = 30.0
) -> dict:
    """Queue emails to students exceeding absence threshold."""
    from ops_crud import queue_email

    rows = attendance_eligibility(conn, scopes, max_absent_pct=max_absent_pct)
    queued = 0
    skipped = 0
    for r in rows:
        if r.get("exam_eligible") is not False:
            continue
        email = (r.get("email") or "").strip()
        if not email:
            skipped += 1
            continue
        queue_email(
            conn,
            kind="attendance_ineligible",
            recipient=email,
            subject=f"[{r.get('program_code') or 'X'}] Exam eligibility warning",
            body=(
                f"Dear {r.get('full_name') or 'Student'},\n\n"
                f"Your absence rate for {r.get('course_code') or ''} — {r.get('course_name') or ''} "
                f"({r.get('class_name') or ''}) is {r.get('absent_pct')}% "
                f"(limit {max_absent_pct}%).\n"
                f"You may be ineligible for the final exam. Please contact the program office.\n\n"
                f"SmartUni / CFVG"
            ),
        )
        queued += 1
    conn.commit()
    return {"queued": queued, "skipped_no_email": skipped, "max_absent_pct": max_absent_pct}


def list_written_exam_roster(
    conn, scopes: list[str] | None, *, round_id: int | None = None, q: str = ""
) -> list[dict]:
    from coord_ops import ensure_coord_tables
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_coord_tables(cur)
    ensure_mba_tables(cur)
    try:
        from learner_spine import ensure_learner_spine

        ensure_learner_spine(cur)
    except Exception:
        pass
    frag, params = _scopes_sql(scopes, "a.program_code")
    sql = (
        "SELECT a.id, a.written_exam_no, a.full_name, a.program_code, a.email, a.phone, "
        "a.written_score, a.written_gk, a.written_mle, a.interview_score, a.avg_score, "
        "a.written_exam_date, a.written_exam_room, a.written_exam_session, "
        "a.status, a.cfvg_app_no, r.code AS round_code, IFNULL(a.exam_eligible_flag,''), "
        "IFNULL(a.dob,''), IFNULL(a.degree_grade,''), IFNULL(a.no_response,''), IFNULL(a.no_show,'') "
        "FROM applications a JOIN admission_rounds r ON r.id = a.round_id "
        f"WHERE {frag} AND ("
        "a.status IN ('submitted','approved_ts','interview','passed','failed','paid','official') "
        ") AND ("
        "IFNULL(a.exam_eligible_flag,'') IN ('yes','1','true') "
        "OR a.status IN ('paid','official') "
        "OR EXISTS (SELECT 1 FROM exam_registrations er WHERE er.application_id = a.id)"
        ") "
    )
    if round_id:
        sql += "AND a.round_id = ? "
        params.append(round_id)
    if q:
        like = f"%{q}%"
        sql += (
            "AND (a.full_name LIKE ? OR a.email LIKE ? OR IFNULL(a.written_exam_no,'') LIKE ? "
            "OR IFNULL(a.cfvg_app_no,'') LIKE ? OR a.program_code LIKE ? OR r.code LIKE ?) "
        )
        params.extend([like] * 6)
    sql += "ORDER BY a.written_exam_no, a.id"
    rows = cur.execute(sql, params).fetchall()
    keys = [
        "id",
        "written_exam_no",
        "full_name",
        "program_code",
        "email",
        "phone",
        "written_score",
        "written_gk",
        "written_mle",
        "interview_score",
        "avg_score",
        "written_exam_date",
        "written_exam_room",
        "written_exam_session",
        "status",
        "cfvg_app_no",
        "round_code",
        "exam_eligible_flag",
        "dob",
        "degree_grade",
        "no_response",
        "no_show",
    ]
    return [dict(zip(keys, r)) for r in rows]


def promote_graduated_to_alumni(conn, student_id: int) -> dict | None:
    """When lifecycle = graduated, upsert alumni_members for handoff Thesis/Graduation → Alumni."""
    cur = conn.cursor()
    ensure_mba_tables(cur)
    from ops_data import ensure_ops_tables

    ensure_ops_tables(cur)
    for col, spec in (
        ("person_id", "INTEGER"),
        ("learner_id", "INTEGER"),
        ("class_student_id", "INTEGER"),
    ):
        try:
            cur.execute(f"ALTER TABLE alumni_members ADD COLUMN {col} {spec}")
        except Exception:
            pass
    cs_cols = {r[1] for r in cur.execute("PRAGMA table_info(class_students)").fetchall()}
    app_expr = "cs.application_id" if "application_id" in cs_cols else "NULL"
    row = cur.execute(
        "SELECT cs.full_name, cs.email, cg.program_code, cg.cohort_year, cg.name, "
        f"{app_expr} "
        "FROM class_students cs JOIN class_groups cg ON cg.id = cs.class_id "
        "WHERE cs.id = ?",
        (student_id,),
    ).fetchone()
    if not row:
        return None
    full_name, email, prog, year, class_name, application_id = row
    person_id = learner_id = None
    if application_id:
        app_cols = {r[1] for r in cur.execute("PRAGMA table_info(applications)").fetchall()}
        want = [c for c in ("person_id", "learner_id") if c in app_cols]
        if want:
            link = cur.execute(
                f"SELECT {', '.join(want)} FROM applications WHERE id = ?",
                (int(application_id),),
            ).fetchone()
            if link:
                got = dict(zip(want, link))
                person_id = got.get("person_id")
                learner_id = got.get("learner_id")
    existing = cur.execute(
        "SELECT id FROM alumni_members WHERE class_student_id = ? LIMIT 1",
        (int(student_id),),
    ).fetchone()
    if not existing and person_id:
        existing = cur.execute(
            "SELECT id FROM alumni_members WHERE person_id = ? AND program_code = ? LIMIT 1",
            (int(person_id), prog),
        ).fetchone()
    if not existing:
        existing = cur.execute(
            "SELECT id FROM alumni_members WHERE full_name = ? AND program_code = ? "
            "AND IFNULL(email,'') = IFNULL(?, '') LIMIT 1",
            (full_name, prog, email or ""),
        ).fetchone()
    if existing:
        cur.execute(
            "UPDATE alumni_members SET class_student_id = COALESCE(class_student_id, ?), "
            "person_id = COALESCE(person_id, ?), learner_id = COALESCE(learner_id, ?) "
            "WHERE id = ?",
            (int(student_id), person_id, learner_id, existing[0]),
        )
        conn.commit()
        return {
            "alumni_id": existing[0],
            "created": False,
            "person_id": person_id,
            "learner_id": learner_id,
            "handoff": "Graduated → Alumni (cùng người)",
        }
    cur.execute(
        "INSERT INTO alumni_members "
        "(full_name, program_code, cohort, class_name, email, phone, company, "
        "person_id, learner_id, class_student_id) "
        "VALUES (?, ?, ?, ?, ?, '', '', ?, ?, ?)",
        (
            full_name, prog, str(year or ""), class_name or "", email or "",
            person_id, learner_id, int(student_id),
        ),
    )
    conn.commit()
    return {
        "alumni_id": cur.lastrowid,
        "created": True,
        "person_id": person_id,
        "learner_id": learner_id,
        "handoff": "Graduated → Alumni",
    }


def update_student_lifecycle(conn, student_id: int, data: dict) -> dict:
    cur = conn.cursor()
    ensure_mba_tables(cur)
    field_allowed = {
        "lifecycle_status",
        "scholarship_type",
        "partner_enrollment",
        "reserve_note",
        "full_name",
        "email",
        "student_code",
        "observations",
    }
    fields, params = [], []
    for k, v in data.items():
        if k not in field_allowed:
            continue
        if k == "lifecycle_status" and v:
            try:
                from status_catalog import allowed_codes

                life_codes = allowed_codes(conn, "lifecycle_status")
            except Exception:
                life_codes = set()
            if not life_codes:
                life_codes = LIFECYCLE_STATUSES
            if v not in life_codes:
                raise ValueError(f"Invalid lifecycle_status: {v}")
        if k == "scholarship_type" and v is not None and str(v) not in SCHOLARSHIP_TYPES:
            raise ValueError(f"Invalid scholarship_type: {v}")
        fields.append(f"{k} = ?")
        params.append(v)
    if not fields:
        raise ValueError("No fields")
    params.append(student_id)
    cur.execute(f"UPDATE class_students SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    row = cur.execute(
        "SELECT id, class_id, full_name, email, student_code, lifecycle_status, "
        "scholarship_type, partner_enrollment, reserve_note, observations "
        "FROM class_students WHERE id = ?",
        (student_id,),
    ).fetchone()
    if not row:
        raise ValueError("Student not found")
    keys = [
        "id",
        "class_id",
        "full_name",
        "email",
        "student_code",
        "lifecycle_status",
        "scholarship_type",
        "partner_enrollment",
        "reserve_note",
        "observations",
    ]
    return dict(zip(keys, row))


def attendance_eligibility(
    conn, scopes: list[str] | None, *, max_absent_pct: float = 30.0
) -> list[dict]:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_mba_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    has_marks = cur.execute("SELECT COUNT(*) FROM attendance_marks").fetchone()[0] > 0
    out: list[dict] = []
    if has_marks:
        sql = (
            "SELECT cs.id, cs.full_name, cs.email, cg.name AS class_name, cg.program_code, "
            "c.code AS course_code, c.name AS course_name, ta.id AS assignment_id, "
            "COUNT(am.id) AS sessions_marked, "
            "SUM(CASE WHEN IFNULL(am.excused,0)=0 AND ("
            "    COALESCE(am.check_in, CAST(am.present AS REAL), 1.0)"
            "    + COALESCE(am.check_out, CAST(COALESCE(am.present_after_break, 1) AS REAL), 1.0)"
            "  ) / 2.0 < 0.5 THEN 1 ELSE 0 END) AS absent_sessions, "
            "SUM(CASE WHEN IFNULL(am.excused,0)=1 THEN 0 ELSE "
            "  (1.0 - ("
            "    COALESCE(am.check_in, CAST(am.present AS REAL), 1.0)"
            "    + COALESCE(am.check_out, CAST(COALESCE(am.present_after_break, 1) AS REAL), 1.0)"
            "  ) / 2.0) * IFNULL(ats.planned_minutes, 0) END) AS absent_minutes, "
            "SUM(IFNULL(ats.planned_minutes, 0)) AS planned_minutes, "
            "SUM(CASE WHEN IFNULL(ats.planned_minutes,0)=0 THEN 1 ELSE 0 END) AS sessions_without_hours "
            "FROM attendance_marks am "
            "JOIN attendance_sessions ats ON ats.id = am.attendance_session_id "
            "JOIN teaching_assignments ta ON ta.id = ats.assignment_id "
            "JOIN class_groups cg ON cg.id = ta.class_id "
            "JOIN class_students cs ON cs.id = am.student_id "
            "JOIN courses c ON c.id = ta.course_id "
            f"WHERE {frag} "
            "GROUP BY cs.id, ta.id "
            "ORDER BY cg.name, c.code, cs.full_name"
        )
        policies = {
            row[0]: {"limit": row[1], "operator": row[2] or "gt", "excused_counts": int(row[3] or 0)}
            for row in cur.execute(
                "SELECT program_code, absent_limit_pct, absent_operator, excused_counts "
                "FROM academic_policies WHERE status = 'published' AND policy_key = 'absence'"
            ).fetchall()
        }
        for r in cur.execute(sql, params).fetchall():
            total = r[8] or 0
            absent_sessions = r[9] or 0
            absent_minutes = r[10] or 0
            planned_minutes = r[11] or 0
            missing_hours = r[12] or 0
            policy = policies.get(r[4])
            limit = policy["limit"] if policy else max_absent_pct
            operator = policy["operator"] if policy else "gt"
            if missing_hours or not planned_minutes or not policy:
                basis = "pending_hours"
                pct = None
                eligible = None
            else:
                basis = "hours"
                pct = round((absent_minutes / planned_minutes) * 100, 1)
                exceeded = pct >= limit if operator == "ge" else pct > limit
                eligible = not exceeded
            out.append(
                {
                    "student_id": r[0],
                    "full_name": r[1],
                    "email": r[2],
                    "class_name": r[3],
                    "program_code": r[4],
                    "course_code": r[5],
                    "course_name": r[6],
                    "assignment_id": r[7],
                    "sessions_marked": total,
                    "absent_count": absent_sessions,
                    "absent_minutes": absent_minutes,
                    "planned_minutes": planned_minutes,
                    "absent_pct": pct,
                    "basis": basis,
                    "absent_operator": operator,
                    "exam_eligible": eligible,
                    "near_threshold": bool(
                        pct is not None and limit and pct > (limit * 0.8) and eligible
                    ),
                    "max_absent_pct": limit,
                }
            )
    else:
        sql = (
            "SELECT ta.id, cg.name, cg.program_code, c.code, c.name, "
            "SUM(ats.absent_count), SUM(ats.present_count + ats.absent_count), "
            "(SELECT COUNT(*) FROM class_students cs WHERE cs.class_id = cg.id) "
            "FROM attendance_sessions ats "
            "JOIN teaching_assignments ta ON ta.id = ats.assignment_id "
            "JOIN class_groups cg ON cg.id = ta.class_id "
            "JOIN courses c ON c.id = ta.course_id "
            f"WHERE {frag} "
            "GROUP BY ta.id"
        )
        for r in cur.execute(sql, params).fetchall():
            absent_sum, headcount_sum, class_size = r[5] or 0, r[6] or 0, r[7] or 0
            sessions = cur.execute(
                "SELECT COUNT(*) FROM attendance_sessions WHERE assignment_id = ?",
                (r[0],),
            ).fetchone()[0]
            pct = round((absent_sum / headcount_sum) * 100, 1) if headcount_sum else 0.0
            out.append(
                {
                    "student_id": None,
                    "full_name": f"(Class aggregate — {class_size} students)",
                    "email": "",
                    "class_name": r[1],
                    "program_code": r[2],
                    "course_code": r[3],
                    "course_name": r[4],
                    "assignment_id": r[0],
                    "sessions_marked": sessions,
                    "absent_count": absent_sum,
                    "absent_pct": pct,
                    "exam_eligible": None,
                    "basis": "pending_hours",
                    "max_absent_pct": max_absent_pct,
                    "aggregate": True,
                }
            )
    return out


def version_has_active_study(conn, version_id: int) -> dict:
    """Detect classes / students still studying on a program version."""
    cur = conn.cursor()
    active_classes = cur.execute(
        "SELECT cg.id, cg.name, COALESCE(cg.status,'active') "
        "FROM class_groups cg "
        "WHERE cg.program_version_id = ? "
        "AND LOWER(COALESCE(cg.status,'')) NOT IN "
        "('closed','archived','completed','cancelled','done') "
        "ORDER BY cg.name",
        (version_id,),
    ).fetchall()
    studying = cur.execute(
        "SELECT COUNT(*) FROM class_students cs "
        "JOIN class_groups cg ON cg.id = cs.class_id "
        "WHERE cg.program_version_id = ? "
        "AND COALESCE(NULLIF(cs.lifecycle_status,''), 'active') "
        "IN ('active','on_leave','reserved')",
        (version_id,),
    ).fetchone()
    studying_n = int((studying[0] if studying else 0) or 0)
    classes = [
        {"id": r[0], "name": r[1], "status": r[2]} for r in active_classes
    ]
    return {
        "blocked": bool(classes) or studying_n > 0,
        "active_class_count": len(classes),
        "studying_student_count": studying_n,
        "classes": classes[:10],
    }


def assert_version_courses_editable(conn, version_id: int) -> None:
    info = version_has_active_study(conn, version_id)
    if not info["blocked"]:
        return
    parts = []
    if info["active_class_count"]:
        names = ", ".join(c["name"] for c in info["classes"][:5])
        more = info["active_class_count"] - min(5, len(info["classes"]))
        label = names + (f" (+{more})" if more > 0 else "")
        parts.append(f"{info['active_class_count']} lớp đang hoạt động ({label})")
    if info["studying_student_count"]:
        parts.append(f"{info['studying_student_count']} HV đang học/bảo lưu/nghỉ")
    raise ValueError(
        "Không thể thay học phần trên phiên bản này vì còn "
        + "; ".join(parts)
        + ". Chỉ chuyển/ghi đè khi không còn lớp đang theo học."
    )


def _course_columns(cur) -> set[str]:
    return {r[1] for r in cur.execute("PRAGMA table_info(courses)").fetchall()}


def _delete_courses_of_version(cur, version_id: int) -> int:
    ids = [
        r[0]
        for r in cur.execute(
            "SELECT id FROM courses WHERE program_version_id = ?", (version_id,)
        ).fetchall()
    ]
    if not ids:
        return 0
    ph = ",".join("?" * len(ids))
    cur.execute(f"DELETE FROM course_materials WHERE course_id IN ({ph})", ids)
    cur.execute(f"DELETE FROM course_sessions WHERE course_id IN ({ph})", ids)
    try:
        cur.execute(f"DELETE FROM teaching_assignments WHERE course_id IN ({ph})", ids)
    except Exception:
        pass
    try:
        cur.execute(
            f"DELETE FROM canvas_course_links WHERE course_id IN ({ph})", ids
        )
    except Exception:
        pass
    cur.execute(f"DELETE FROM courses WHERE id IN ({ph})", ids)
    return len(ids)


def _copy_courses_to_version(
    cur,
    source_version_id: int,
    target_version_id: int,
    program_code: str,
    keep_course_ids: list[int] | None = None,
    drop_course_ids: list[int] | None = None,
) -> int:
    """Copy courses + session sequence from source version into target. Returns count."""
    from course_content import ensure_sessions_for_course

    cols = _course_columns(cur)
    extra = [
        c
        for c in (
            "learning_outcomes",
            "assessment_note",
            "reading_list",
            "syllabus_status",
        )
        if c in cols
    ]
    select_extra = (", " + ", ".join(extra)) if extra else ""
    courses = cur.execute(
        "SELECT id, code, name, semester, sort_order, theory_sessions, practice_sessions, "
        f"syllabus_note{select_extra} FROM courses WHERE program_version_id = ? "
        "ORDER BY sort_order, id",
        (source_version_id,),
    ).fetchall()
    if keep_course_ids:
        keep = {int(x) for x in keep_course_ids}
        courses = [c for c in courses if int(c[0]) in keep]
    if drop_course_ids:
        drop = {int(x) for x in drop_course_ids}
        courses = [c for c in courses if int(c[0]) not in drop]
    copied = 0
    for c in courses:
        theory, practice = c[5], c[6]
        if program_code in ("MBA", "MMS"):
            if (theory or 0) + (practice or 0) != 8:
                theory, practice = 8, 0
        base_vals = [
            target_version_id,
            c[1],
            c[2],
            c[3],
            c[4],
            theory,
            practice,
            c[7],
        ]
        insert_cols = (
            "program_version_id, code, name, semester, sort_order, theory_sessions, "
            "practice_sessions, syllabus_note"
        )
        if extra:
            insert_cols += ", " + ", ".join(extra)
            base_vals.extend(c[8 : 8 + len(extra)])
        placeholders = ",".join("?" * len(base_vals))
        cur.execute(
            f"INSERT INTO courses ({insert_cols}) VALUES ({placeholders})",
            base_vals,
        )
        new_cid = cur.lastrowid
        copied += 1
        sess_cols = {r[1] for r in cur.execute("PRAGMA table_info(course_sessions)").fetchall()}
        req_sql = ", requirements" if "requirements" in sess_cols else ""
        sess = cur.execute(
            "SELECT session_no, session_type, title, content_outline, objectives, "
            f"duration_hours, sort_order, status{req_sql} FROM course_sessions WHERE course_id = ? "
            "ORDER BY sort_order, session_no",
            (c[0],),
        ).fetchall()
        if program_code in ("MBA", "MMS") and (theory, practice) == (8, 0) and len(sess) != 8:
            ensure_sessions_for_course(cur, new_cid)
        elif sess:
            for s in sess:
                if "requirements" in sess_cols:
                    cur.execute(
                        "INSERT INTO course_sessions "
                        "(course_id, session_no, session_type, title, content_outline, "
                        "objectives, duration_hours, sort_order, status, requirements) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (
                            new_cid,
                            s[0],
                            s[1],
                            s[2],
                            s[3],
                            s[4],
                            s[5],
                            s[6],
                            s[7] or "planned",
                            s[8],
                        ),
                    )
                else:
                    cur.execute(
                        "INSERT INTO course_sessions "
                        "(course_id, session_no, session_type, title, content_outline, "
                        "objectives, duration_hours, sort_order, status) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            new_cid,
                            s[0],
                            s[1],
                            s[2],
                            s[3],
                            s[4],
                            s[5],
                            s[6],
                            s[7] or "planned",
                        ),
                    )
        else:
            ensure_sessions_for_course(cur, new_cid)
    return copied


def copy_program_version(
    conn,
    source_version_id: int,
    *,
    new_version_code: str,
    new_name: str | None = None,
    copy_courses: bool = True,
    keep_course_ids: list[int] | None = None,
    drop_course_ids: list[int] | None = None,
) -> dict:
    cur = conn.cursor()
    ensure_mba_tables(cur)
    from course_content import ensure_course_content_tables

    ensure_course_content_tables(cur)
    src = cur.execute(
        "SELECT id, program_code, version_code, name, description "
        "FROM program_versions WHERE id = ?",
        (source_version_id,),
    ).fetchone()
    if not src:
        raise ValueError("Source program version not found")
    prog, old_code, old_name, desc = src[1], src[2], src[3], src[4]
    code = (new_version_code or "").strip()
    if not code:
        raise ValueError("new_version_code required")
    exists = cur.execute(
        "SELECT id FROM program_versions WHERE version_code = ?", (code,)
    ).fetchone()
    if exists:
        raise ValueError(f"Mã phiên bản đã tồn tại: {code}")
    name = (new_name or f"{old_name} (copy of {old_code})").strip()
    cur.execute(
        "INSERT INTO program_versions "
        "(program_code, version_code, name, description, is_active, version_status) "
        "VALUES (?,?,?,?,0,'draft')",
        (prog, code, name, desc or f"Copied from {old_code}. Draft — approve before use."),
    )
    new_vid = cur.lastrowid
    # New version has no classes yet — still verify before attaching courses.
    assert_version_courses_editable(conn, new_vid)
    copied_courses = 0
    if copy_courses:
        copied_courses = _copy_courses_to_version(
            cur,
            source_version_id,
            new_vid,
            prog,
            keep_course_ids=keep_course_ids,
            drop_course_ids=drop_course_ids,
        )
    conn.commit()
    return {
        "id": new_vid,
        "program_code": prog,
        "version_code": code,
        "name": name,
        "courses_copied": copied_courses,
        "copy_courses": bool(copy_courses),
        "source_version_id": source_version_id,
        "mode": "create_version",
    }


def transfer_program_version_courses(
    conn,
    source_version_id: int,
    target_version_id: int,
    *,
    replace: bool = True,
) -> dict:
    """Copy course set + sequence into an existing version (no new version created)."""
    cur = conn.cursor()
    from course_content import ensure_course_content_tables

    ensure_course_content_tables(cur)
    if int(source_version_id) == int(target_version_id):
        raise ValueError("Nguồn và đích phải khác nhau")
    src = cur.execute(
        "SELECT id, program_code, version_code, name FROM program_versions WHERE id = ?",
        (source_version_id,),
    ).fetchone()
    if not src:
        raise ValueError("Phiên bản nguồn không tồn tại")
    tgt = cur.execute(
        "SELECT id, program_code, version_code, name FROM program_versions WHERE id = ?",
        (target_version_id,),
    ).fetchone()
    if not tgt:
        raise ValueError("Phiên bản đích không tồn tại")
    if (src[1] or "").upper() != (tgt[1] or "").upper():
        raise ValueError(
            f"Chỉ chuyển học phần trong cùng chương trình ({src[1]} → {tgt[1]} khác CT)."
        )
    assert_version_courses_editable(conn, target_version_id)
    removed = 0
    if replace:
        removed = _delete_courses_of_version(cur, target_version_id)
    else:
        # Append mode still blocked if target already has courses that collide? Keep replace default.
        existing = cur.execute(
            "SELECT COUNT(*) FROM courses WHERE program_version_id = ?",
            (target_version_id,),
        ).fetchone()
        if existing and existing[0]:
            raise ValueError(
                "Phiên bản đích đã có học phần. Bật replace để ghi đè toàn bộ trình tự."
            )
    copied = _copy_courses_to_version(cur, source_version_id, target_version_id, src[1])
    conn.commit()
    return {
        "ok": True,
        "mode": "transfer_courses",
        "source_version_id": source_version_id,
        "source_version_code": src[2],
        "target_version_id": target_version_id,
        "target_version_code": tgt[2],
        "program_code": src[1],
        "courses_removed": removed,
        "courses_copied": copied,
    }


def list_students_lifecycle(
    conn, scopes: list[str] | None, *, q: str = "", campuses: list[str] | None = None,
    cohort: str = "", mobility: str = "",
) -> list[dict]:
    """Admin student roster: Financial + Academic lifecycle fields."""
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_mba_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    sql = (
        "SELECT cs.id, cs.student_code, cs.full_name, cs.email, cg.name AS class_name, "
        "cg.program_code, cg.cohort_year, IFNULL(cg.cohort_no,''), "
        "IFNULL(cg.year_start,''), IFNULL(cg.year_end,''), "
        "COALESCE(NULLIF(cs.lifecycle_status,''), 'active') AS lifecycle_status, "
        "cs.scholarship_type, cs.partner_enrollment, cs.reserve_note, cs.observations, "
        "cs.gender, cs.dob, cs.place_of_birth, cs.phone, cs.company, cs.job_title, "
        "cs.management_years, cs.intake_session, cs.exchange_flag "
        "FROM class_students cs "
        "JOIN class_groups cg ON cg.id = cs.class_id "
        f"WHERE {frag}"
    )
    if q:
        sql += (
            " AND (cs.full_name LIKE ? OR IFNULL(cs.email,'') LIKE ? "
            "OR IFNULL(cs.student_code,'') LIKE ? OR IFNULL(cs.company,'') LIKE ?)"
        )
        params.extend([f"%{q}%"] * 4)
    if (cohort or "").strip():
        sql += (
            " AND (CAST(IFNULL(cg.cohort_year,'') AS TEXT) = ? "
            "OR IFNULL(cg.cohort_no,'') = ?)"
        )
        params.extend([(cohort or "").strip(), (cohort or "").strip()])
    mobility_key = (mobility or "").strip().lower()
    if mobility_key in ("incoming", "outgoing"):
        sql += " AND lower(IFNULL(cs.exchange_flag,'')) = ?"
        params.append(mobility_key)
    if campuses and "*" not in campuses:
        ph = ",".join("?" * len(campuses))
        sql += (
            " AND (cs.application_id IS NULL OR EXISTS ("
            "SELECT 1 FROM applications a WHERE a.id = cs.application_id "
            f"AND UPPER(IFNULL(a.campus,'')) IN ({ph})))"
        )
        params.extend([c.strip().upper() for c in campuses])
    sql += " ORDER BY cg.program_code, cg.name, cs.full_name"
    rows = cur.execute(sql, params).fetchall()
    keys = [
        "id", "student_code", "full_name", "email", "class_name", "program_code",
        "cohort_year", "cohort_no", "year_start", "year_end",
        "lifecycle_status", "scholarship_type", "partner_enrollment",
        "reserve_note", "observations",
        "gender", "dob", "place_of_birth", "phone", "company", "job_title",
        "management_years", "intake_session", "exchange_flag",
    ]
    out = []
    for r in rows:
        item = dict(zip(keys, r))
        from ops_data import format_cohort_label

        item["cohort_label"] = format_cohort_label(
            item.get("cohort_no"), item.get("year_start"), item.get("year_end"), item.get("cohort_year"),
        )
        flag = (item.get("exchange_flag") or "").strip().lower()
        item["mobility_group"] = "Incoming" if flag == "incoming" else ("Outgoing" if flag == "outgoing" else "")
        # dual track labels for UI
        item["financial_track"] = item.get("scholarship_type") or "—"
        item["academic_track"] = item.get("lifecycle_status") or "active"
        out.append(item)
    return out


def list_teaching_schedule(
    conn,
    scopes: list[str] | None,
    *,
    session_date: str = "",
    course_code: str = "",
    chapter: str = "",
) -> list[dict]:
    """Coordinator semester schedule view (offerings + attendance sessions as dates)."""
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_mba_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    # Prefer concrete attendance session dates; fall back to assignment rows
    sql = (
        "SELECT ats.id, cg.name, cg.program_code, c.code, c.name, "
        "fl.full_name, fe.full_name, ats.session_no, ats.session_label, "
        "ats.session_date, ta.status, ta.id, IFNULL(ats.room,''), IFNULL(ats.chapter,'') "
        "FROM attendance_sessions ats "
        "JOIN teaching_assignments ta ON ta.id = ats.assignment_id "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        "LEFT JOIN faculty fl ON fl.id = ta.lecturer_id "
        "LEFT JOIN faculty fe ON fe.id = ta.expert_id "
        f"WHERE {frag} "
    )
    if (session_date or "").strip():
        sql += " AND IFNULL(ats.session_date,'') = ?"
        params.append(session_date.strip()[:10])
    if (course_code or "").strip():
        sql += " AND c.code LIKE ?"
        params.append(f"%{course_code.strip()}%")
    if (chapter or "").strip():
        sql += " AND (IFNULL(ats.chapter,'') LIKE ? OR IFNULL(ats.session_label,'') LIKE ?)"
        like = f"%{chapter.strip()}%"
        params.extend([like, like])
    sql += " ORDER BY ats.session_date DESC, cg.name, c.code LIMIT 400"
    rows = cur.execute(sql, params).fetchall()
    if rows:
        return [
            {
                "id": r[0],
                "class_name": r[1],
                "program_code": r[2],
                "course_code": r[3],
                "course_name": r[4],
                "lecturer": r[5] or "—",
                "expert": r[6] or "—",
                "session_no": r[7],
                "session_label": r[8],
                "session_date": r[9],
                "room": r[12] if len(r) > 12 else "",
                "chapter": r[13] if len(r) > 13 else (r[8] or ""),
                "status": r[10],
                "assignment_id": r[11],
            }
            for r in rows
        ]
    sql2 = (
        "SELECT ta.id, cg.name, cg.program_code, c.code, c.name, "
        "fl.full_name, fe.full_name, ta.status "
        "FROM teaching_assignments ta "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        "LEFT JOIN faculty fl ON fl.id = ta.lecturer_id "
        "LEFT JOIN faculty fe ON fe.id = ta.expert_id "
        f"WHERE {frag} ORDER BY cg.program_code, cg.name, c.code"
    )
    return [
        {
            "id": r[0],
            "class_name": r[1],
            "program_code": r[2],
            "course_code": r[3],
            "course_name": r[4],
            "lecturer": r[5] or "—",
            "expert": r[6] or "—",
            "session_no": "",
            "session_label": "Offering (schedule TBD)",
            "session_date": "",
            "room": "",
            "status": r[7],
            "assignment_id": r[0],
        }
        for r in cur.execute(sql2, params).fetchall()
    ]


def assign_students_to_class(conn, student_ids: list, class_id: int) -> dict:
    """Đưa nhiều học viên đang có hồ sơ lớp vào một lớp cùng chương trình."""
    cur = conn.cursor()
    ensure_mba_tables(cur)
    meta = cur.execute(
        "SELECT id, program_code, name FROM class_groups WHERE id = ?",
        (int(class_id),),
    ).fetchone()
    if not meta:
        raise ValueError("Không tìm thấy lớp")
    moved = 0
    skipped = 0
    for raw in student_ids or []:
        try:
            sid = int(raw)
        except (TypeError, ValueError):
            skipped += 1
            continue
        row = cur.execute(
            "SELECT cs.id, cg.program_code FROM class_students cs "
            "JOIN class_groups cg ON cg.id = cs.class_id WHERE cs.id = ?",
            (sid,),
        ).fetchone()
        if not row or (row[1] or "").upper() != (meta[1] or "").upper():
            skipped += 1
            continue
        cur.execute("UPDATE class_students SET class_id = ? WHERE id = ?", (int(class_id), sid))
        moved += 1
    conn.commit()
    return {"moved": moved, "skipped": skipped, "class_id": int(class_id), "class_name": meta[2]}


def import_schedule_rooms(conn, rows: list[dict]) -> dict:
    """Cập nhật phòng học và chương từ Excel. Khóa dòng là mã buổi."""
    cur = conn.cursor()
    ensure_mba_tables(cur)
    from ops_data import ensure_ops_tables

    ensure_ops_tables(cur)
    updated = 0
    skipped = 0
    for raw in rows or []:
        try:
            sid = int(raw.get("id") or raw.get("session_id") or raw.get("Mã buổi") or 0)
        except (TypeError, ValueError):
            sid = 0
        if not sid:
            class_name = str(raw.get("class_name") or raw.get("Lớp") or raw.get("lop") or "").strip()
            course_code = str(raw.get("course_code") or raw.get("Mã môn") or raw.get("Mã HP") or "").strip()
            session_no = str(raw.get("session_no") or raw.get("Số buổi") or "").strip()
            session_date_key = str(raw.get("session_date") or raw.get("Ngày học") or "").strip()[:10]
            if class_name and course_code:
                found = cur.execute(
                    "SELECT ats.id FROM attendance_sessions ats "
                    "JOIN teaching_assignments ta ON ta.id = ats.assignment_id "
                    "JOIN class_groups cg ON cg.id = ta.class_id "
                    "JOIN courses c ON c.id = ta.course_id "
                    "WHERE lower(trim(cg.name)) = lower(trim(?)) AND lower(trim(c.code)) = lower(trim(?)) "
                    "AND (? = '' OR IFNULL(ats.session_date,'') = ? OR CAST(ats.session_no AS TEXT) = ?) "
                    "ORDER BY ats.id LIMIT 1",
                    (class_name, course_code, session_date_key or session_no, session_date_key, session_no),
                ).fetchone()
                sid = int(found[0]) if found else 0
        if not sid:
            skipped += 1
            continue
        room = str(raw.get("room") or raw.get("Phòng") or raw.get("phong") or "").strip()
        chapter = str(raw.get("chapter") or raw.get("Chương") or raw.get("chuong") or "").strip()
        session_date = str(raw.get("session_date") or raw.get("Ngày học") or "").strip()[:10]
        fields, params = [], []
        if room:
            fields.append("room = ?")
            params.append(room)
        if chapter:
            fields.append("chapter = ?")
            params.append(chapter)
        if session_date:
            fields.append("session_date = ?")
            params.append(session_date)
        if not fields:
            skipped += 1
            continue
        params.append(sid)
        cur.execute(f"UPDATE attendance_sessions SET {', '.join(fields)} WHERE id = ?", params)
        if cur.rowcount:
            updated += 1
        else:
            skipped += 1
    conn.commit()
    return {"updated": updated, "skipped": skipped}


def mark_evaluation_sent(conn, eval_id: int, target: str) -> dict:
    cur = conn.cursor()
    ensure_mba_tables(cur)
    row = cur.execute(
        "SELECT id, response_pct, report_status, sent_mgmt_at, sent_faculty_at, status "
        "FROM course_evaluations WHERE id = ?",
        (eval_id,),
    ).fetchone()
    if not row:
        raise ValueError("Evaluation not found")
    pct = float(row[1] or 0)
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    if target == "mgmt":
        if pct < 60:
            raise ValueError("Need at least 60% responses before sending to management")
        cur.execute(
            "UPDATE course_evaluations SET report_status = 'ready_mgmt', "
            "sent_mgmt_at = ?, status = 'sent_mgmt' WHERE id = ?",
            (now, eval_id),
        )
    elif target == "faculty":
        if pct < 80:
            raise ValueError("Need at least 80% responses before sending to faculty")
        cur.execute(
            "UPDATE course_evaluations SET report_status = 'ready_faculty', "
            "sent_faculty_at = ?, status = 'sent_faculty' WHERE id = ?",
            (now, eval_id),
        )
    else:
        raise ValueError("target must be mgmt or faculty")
    conn.commit()
    return {
        "id": eval_id,
        "target": target,
        "response_pct": pct,
        "sent_at": now,
        "ready_mgmt": pct >= 60,
        "ready_faculty": pct >= 80,
    }


def mark_evaluation_closed(conn, eval_id: int) -> dict:
    cur = conn.cursor()
    ensure_mba_tables(cur)
    row = cur.execute(
        "SELECT id, status FROM course_evaluations WHERE id = ?",
        (eval_id,),
    ).fetchone()
    if not row:
        raise ValueError("Evaluation not found")
    cur.execute(
        "UPDATE course_evaluations SET status = 'closed', report_status = CASE "
        "WHEN IFNULL(report_status,'') = '' THEN 'closed' ELSE report_status END "
        "WHERE id = ?",
        (eval_id,),
    )
    conn.commit()
    return {"id": eval_id, "status": "closed"}


# Sample MBA34 roster (subset of 1.2.2 / CĐS-1.3.2 Student list MBA34)
_MBA34_SEED = [
    {
        "intake_session": "August",
        "student_code_mba": "HN34MBA001",
        "full_name": "Bùi Diệp Anh",
        "gender": "F",
        "dob": "2001-12-18",
        "email": "diepanhh.dvn@gmail.com",
        "university": "Đại học Kinh tế Quốc dân",
        "degree_major": "Quản trị Marketing",
        "eco_background": "Yes",
        "bachelor_grad_year": "2023",
        "study_duration": "4",
        "credit_hours": 136,
        "degree_grade": "Giỏi",
        "company": "Techcombank",
        "job_title": "Nhân viên Công nghệ Marketing Số",
        "experience_years": 3,
        "management_years": 0,
        "english_cert": "IELTS 6.5",
        "avg_score": 14.43,
        "interview_score": 15.33,
        "interview_jury1": 15,
        "interview_jury2": 17,
        "interview_jury3": 14,
        "written_score": 13.53,
        "written_gk": 12,
        "written_mle": 14.55,
        "confirmation_status": "",
        "board_decision": "Trúng tuyển",
        "place_of_birth": "Hanoi",
        "phone": "705111520",
    },
    {
        "intake_session": "May",
        "student_code_mba": "HN34MBA002",
        "full_name": "Bùi Nguyễn Tố Hạnh",
        "gender": "F",
        "dob": "1994-06-18",
        "email": "tohanh@hotmail.com",
        "university": "University of California, Berkeley",
        "degree_major": "English Literature",
        "eco_background": "No",
        "bachelor_grad_year": "2016",
        "study_duration": "4",
        "credit_hours": 140,
        "company": "American Study",
        "job_title": "Phó Giám Đốc Tuyển Sinh",
        "experience_years": 9,
        "management_years": 6,
        "english_cert": "Miễn",
        "english_note": "Công dân Mỹ, Tốt nghiệp Cử nhân tại Mỹ",
        "naric_status": "Đạt yêu cầu",
        "avg_score": 18.36,
        "interview_score": 19.17,
        "written_score": 17.56,
        "confirmation_status": "Confirmation to Study",
        "board_decision": "Trúng tuyển",
        "place_of_birth": "Hanoi",
    },
    {
        "intake_session": "August",
        "student_code_mba": "HN34MBA004",
        "full_name": "Bùi Phương Thảo",
        "gender": "F",
        "dob": "1997-07-08",
        "email": "thaobui8797@gmail.com",
        "university": "Đại học Kinh tế Quốc dân",
        "degree_major": "Tài chính Ngân hàng",
        "eco_background": "Yes",
        "bachelor_grad_year": "2019",
        "study_duration": "4",
        "credit_hours": 128,
        "degree_grade": "Xuất sắc",
        "company": "TAL VIETNAM.,JSC",
        "job_title": "Giám Đốc Quản lý Kinh Doanh",
        "experience_years": 6,
        "management_years": 4,
        "english_cert": "Aptis Esol B2",
        "avg_score": 14.69,
        "interview_score": 15.83,
        "written_score": 13.54,
        "board_decision": "Trúng tuyển",
        "place_of_birth": "Hanoi",
    },
    {
        "intake_session": "May",
        "student_code_mba": "HN34MBA005",
        "full_name": "Cao Hồng Nam",
        "gender": "M",
        "dob": "1990-10-22",
        "email": "nam.caohong@gmail.com",
        "university": "Học viện Ngân hàng",
        "degree_major": "Kế toán",
        "eco_background": "Yes",
        "bachelor_grad_year": "2012",
        "company": "Bao Viet Life",
        "job_title": "Nhân viên cấp cao phụ trách Đãi Ngộ",
        "experience_years": 13,
        "management_years": 0,
        "english_cert": "IELTS 7.0",
        "avg_score": 15.18,
        "interview_score": 13.33,
        "written_score": 17.02,
        "confirmation_status": "Confirmation to Study",
        "board_decision": "Trúng tuyển",
    },
    {
        "intake_session": "May",
        "student_code_mba": "HN34MBA006",
        "full_name": "Đàm Quang Huy",
        "gender": "M",
        "dob": "1991-09-20",
        "email": "dqhuy.fet.bk@gmail.com",
        "university": "ĐH Bách Khoa",
        "degree_major": "Điện tử và Viễn thông",
        "eco_background": "No",
        "master_level": "2018/Master/Electronic and telecommunication/HUST",
        "bachelor_grad_year": "2015",
        "company": "Qualcomm",
        "job_title": "Kỹ sư",
        "experience_years": 10,
        "management_years": 3,
        "english_cert": "Vstep bậc 4",
        "avg_score": 14.95,
        "interview_score": 16.17,
        "written_score": 13.73,
        "confirmation_status": "Confirmation to Study",
        "board_decision": "Trúng tuyển",
    },
    {
        "intake_session": "August",
        "student_code_mba": "HN34MBA010",
        "full_name": "Đinh Thị Ánh Minh",
        "gender": "F",
        "dob": "1999-12-25",
        "email": "dinhanhminh2512@gmail.com",
        "university": "Học viện Ngân hàng",
        "degree_major": "Tài chính Ngân hàng",
        "eco_background": "Yes",
        "bachelor_grad_year": "2021",
        "company": "PwC (Vietnam) Limited",
        "job_title": "Trợ lý Cấp cao",
        "experience_years": 4,
        "management_years": 0,
        "english_cert": "Aptis ESOL C1",
        "avg_score": 14.78,
        "interview_score": 14.67,
        "written_score": 14.89,
        "board_decision": "Trúng tuyển",
    },
    {
        "intake_session": "May",
        "student_code_mba": "HN34MBA033",
        "full_name": "Nguyễn Công Tùng",
        "gender": "M",
        "dob": "1998-01-07",
        "email": "nctung017@gmail.com",
        "university": "Trường ĐH Ngoại thương",
        "degree_major": "Accounting-Auditing",
        "eco_background": "Yes",
        "bachelor_grad_year": "2020",
        "company": "TNB Aura",
        "job_title": "Trưởng Phòng Đầu Tư",
        "experience_years": 3,
        "management_years": 2,
        "english_cert": "Vstep bậc 4",
        "avg_score": 17.18,
        "interview_score": 17.33,
        "written_score": 17.02,
        "confirmation_status": "Confirmation to Study",
        "board_decision": "Trúng tuyển",
    },
    {
        "intake_session": "August",
        "student_code_mba": "HN34MBA031",
        "full_name": "Nguyễn Anh Tuấn",
        "gender": "M",
        "dob": "1981-09-26",
        "email": "tuannguyenrhm@gmail.com",
        "university": "Trường ĐH Y Hà Nội",
        "degree_major": "Phẫu thuật Nha khoa",
        "eco_background": "No",
        "company": "Neosmile Orthodontic Clinic",
        "job_title": "Giám Đốc Điều Hành",
        "experience_years": 19,
        "management_years": 8,
        "english_cert": "Miễn",
        "avg_score": 15.35,
        "interview_score": 17.17,
        "written_score": 13.53,
        "board_decision": "Trúng tuyển",
        "other_achievements": "Tiến sĩ Y Khoa",
    },
]


def seed_mba34_demo(conn) -> dict:
    """Idempotent MBA34 sample: official apps → MBA 2026 class + sample grades/attendance."""
    cur = conn.cursor()
    ensure_mba_tables(cur)
    out = {"apps": 0, "enrolled": 0, "grades": 0, "attendance": 0}

    round_id = cur.execute(
        "SELECT id FROM admission_rounds WHERE programs LIKE '%MBA%' "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not round_id:
        round_id = cur.execute("SELECT id FROM admission_rounds ORDER BY id DESC LIMIT 1").fetchone()
    if not round_id:
        return out
    round_id = round_id[0]

    class_row = cur.execute(
        "SELECT id, program_version_id FROM class_groups "
        "WHERE program_code = 'MBA' AND (name LIKE '%2026%' OR name LIKE '%MBA34%' OR name LIKE '%K34%') "
        "ORDER BY id LIMIT 1"
    ).fetchone()
    if not class_row:
        class_row = cur.execute(
            "SELECT id, program_version_id FROM class_groups WHERE program_code = 'MBA' ORDER BY id LIMIT 1"
        ).fetchone()
    if not class_row:
        return out
    class_id, pvid = class_row[0], class_row[1]

    student_ids: list[int] = []
    for row in _MBA34_SEED:
        code = row["student_code_mba"]
        existing = cur.execute(
            "SELECT id FROM applications WHERE student_code_mba = ? OR email = ?",
            (code, row["email"]),
        ).fetchone()
        if existing:
            app_id = existing[0]
            cur.execute(
                "UPDATE applications SET status='official', final_result='Admitted', "
                "program_code='MBA', intake_session=?, student_code_mba=?, eco_background=?, "
                "master_level=?, bachelor_grad_year=?, job_title=?, management_years=?, "
                "english_note=?, naric_status=?, other_achievements=?, "
                "interview_score=?, interview_jury1=?, interview_jury2=?, interview_jury3=?, "
                "written_score=?, written_gk=?, written_mle=?, avg_score=?, "
                "confirmation_status=?, board_decision=?, company=?, "
                "university=?, degree_major=?, gender=?, dob=?, english_cert=?, "
                "experience_years=?, credit_hours=?, study_duration=?, degree_grade=? "
                "WHERE id=?",
                (
                    row.get("intake_session"), code, row.get("eco_background"),
                    row.get("master_level"), row.get("bachelor_grad_year"),
                    row.get("job_title"), row.get("management_years"),
                    row.get("english_note"), row.get("naric_status"),
                    row.get("other_achievements"),
                    row.get("interview_score"), row.get("interview_jury1"),
                    row.get("interview_jury2"), row.get("interview_jury3"),
                    row.get("written_score"), row.get("written_gk"), row.get("written_mle"),
                    row.get("avg_score"), row.get("confirmation_status"),
                    row.get("board_decision"), row.get("company"),
                    row.get("university"), row.get("degree_major"),
                    row.get("gender"), row.get("dob"), row.get("english_cert"),
                    row.get("experience_years"), row.get("credit_hours"),
                    row.get("study_duration"), row.get("degree_grade"),
                    app_id,
                ),
            )
        else:
            cur.execute(
                "INSERT INTO applications "
                "(round_id, program_code, full_name, email, phone, status, notes, "
                "campus, gender, dob, university, degree_major, study_duration, degree_grade, "
                "experience_years, credit_hours, english_cert, company, final_result, "
                "intake_session, student_code_mba, eco_background, master_level, "
                "bachelor_grad_year, job_title, management_years, english_note, naric_status, "
                "other_achievements, interview_score, interview_jury1, interview_jury2, "
                "interview_jury3, written_score, written_gk, written_mle, avg_score, "
                "confirmation_status, board_decision) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    round_id, "MBA", row["full_name"], row["email"], row.get("phone") or "",
                    "official", "", "HN", row.get("gender"), row.get("dob"),
                    row.get("university"), row.get("degree_major"),
                    row.get("study_duration"), row.get("degree_grade"),
                    row.get("experience_years"), row.get("credit_hours"),
                    row.get("english_cert"), row.get("company"), "Admitted",
                    row.get("intake_session"), code, row.get("eco_background"),
                    row.get("master_level"), row.get("bachelor_grad_year"),
                    row.get("job_title"), row.get("management_years"),
                    row.get("english_note"), row.get("naric_status"),
                    row.get("other_achievements"),
                    row.get("interview_score"), row.get("interview_jury1"),
                    row.get("interview_jury2"), row.get("interview_jury3"),
                    row.get("written_score"), row.get("written_gk"), row.get("written_mle"),
                    row.get("avg_score"), row.get("confirmation_status"),
                    row.get("board_decision"),
                ),
            )
            app_id = cur.lastrowid
            out["apps"] += 1

        st = cur.execute(
            "SELECT id FROM class_students WHERE application_id = ? OR "
            "(class_id = ? AND student_code = ?)",
            (app_id, class_id, code),
        ).fetchone()
        if st:
            sid = st[0]
            cur.execute(
                "UPDATE class_students SET student_code=?, full_name=?, email=?, gender=?, dob=?, "
                "place_of_birth=?, phone=?, company=?, job_title=?, management_years=?, "
                "intake_session=?, lifecycle_status='active' WHERE id=?",
                (
                    code, row["full_name"], row["email"], row.get("gender"), row.get("dob"),
                    row.get("place_of_birth"), row.get("phone"), row.get("company"),
                    row.get("job_title"), row.get("management_years"),
                    row.get("intake_session"), sid,
                ),
            )
        else:
            cur.execute(
                "INSERT INTO class_students "
                "(class_id, application_id, full_name, email, student_code, lifecycle_status, "
                "gender, dob, place_of_birth, phone, company, job_title, management_years, "
                "intake_session) "
                "VALUES (?,?,?,?,?,'active',?,?,?,?,?,?,?,?)",
                (
                    class_id, app_id, row["full_name"], row["email"], code,
                    row.get("gender"), row.get("dob"), row.get("place_of_birth"),
                    row.get("phone"), row.get("company"), row.get("job_title"),
                    row.get("management_years"), row.get("intake_session"),
                ),
            )
            sid = cur.lastrowid
            out["enrolled"] += 1
        student_ids.append(sid)

    # Sample course grades (Corporate Finance style components) for first MBA course
    if pvid and student_ids:
        course = cur.execute(
            "SELECT id, IFNULL(component_weight_ga, -1), IFNULL(component_weight_fe, -1), "
            "IFNULL(score_rule_status,'') FROM courses WHERE program_version_id = ? "
            "AND (LOWER(name) LIKE '%corporate finance%' OR LOWER(name) LIKE '%finance%') "
            "ORDER BY sort_order LIMIT 1",
            (pvid,),
        ).fetchone()
        if course:
            cid = course[0]
            if course[3] != "published":
                cur.execute(
                    "UPDATE courses SET component_weight_ga = 0.3, component_weight_fe = 0.7, "
                    "score_rule_status = 'published' WHERE id = ?",
                    (cid,),
                )
                ga_w, fe_w = 0.3, 0.7
            else:
                ga_w, fe_w = course[1], course[2]
            for i, sid in enumerate(student_ids):
                ga = round(12 + (i % 5) * 0.8, 1)
                fe = round(11 + (i % 6) * 0.7, 1)
                final = round(ga_w * ga + fe_w * fe, 2) if ga_w >= 0 and fe_w >= 0 else None
                exists = cur.execute(
                    "SELECT id FROM course_grades WHERE class_id=? AND student_id=? AND course_id=?",
                    (class_id, sid, cid),
                ).fetchone()
                if exists:
                    cur.execute(
                        "UPDATE course_grades SET group_assignment=?, final_exam=?, score=?, "
                        "anonymous_no=?, remarks=? WHERE id=?",
                        (ga, fe, final, str(80 + i), "", exists[0]),
                    )
                else:
                    cur.execute(
                        "INSERT INTO course_grades "
                        "(class_id, student_id, course_id, score, locked, "
                        "group_assignment, final_exam, anonymous_no) "
                        "VALUES (?,?,?,?,0,?,?,?)",
                        (class_id, sid, cid, final, ga, fe, str(80 + i)),
                    )
                    out["grades"] += 1

    # Dual check-in/out attendance sample on first MBA teaching assignment
    ta = cur.execute(
        "SELECT id FROM teaching_assignments WHERE class_id = ? LIMIT 1", (class_id,)
    ).fetchone()
    if ta and student_ids:
        ta_id = ta[0]
        for day_i, d in enumerate(("2026-06-15", "2026-06-17", "2026-06-18", "2026-06-19")):
            sess = cur.execute(
                "SELECT id FROM attendance_sessions WHERE assignment_id=? AND session_date=?",
                (ta_id, d),
            ).fetchone()
            if not sess:
                cur.execute(
                    "INSERT INTO attendance_sessions "
                    "(assignment_id, session_no, session_label, session_date, present_count, absent_count) "
                    "VALUES (?,?,?,?,0,0)",
                    (ta_id, day_i + 1, f"Session {day_i + 1}", d),
                )
                sess_id = cur.lastrowid
            else:
                sess_id = sess[0]
            for j, sid in enumerate(student_ids):
                # Sample fractional marks like Business game Excel
                if j in (1, 12) and day_i == 2:
                    cin, cout = 0.5, 0.5
                elif j == 7 and day_i == 0:
                    cin, cout = 0.5, 0.5
                else:
                    cin, cout = 1.0, 1.0
                present_i = 1 if cin >= 0.5 else 0
                after_i = 1 if cout >= 0.5 else 0
                hit = cur.execute(
                    "SELECT id FROM attendance_marks WHERE attendance_session_id=? AND student_id=?",
                    (sess_id, sid),
                ).fetchone()
                if hit:
                    cur.execute(
                        "UPDATE attendance_marks SET present=?, present_after_break=?, "
                        "check_in=?, check_out=? WHERE id=?",
                        (present_i, after_i, cin, cout, hit[0]),
                    )
                else:
                    cur.execute(
                        "INSERT INTO attendance_marks "
                        "(attendance_session_id, student_id, present, present_after_break, "
                        "check_in, check_out) VALUES (?,?,?,?,?,?)",
                        (sess_id, sid, present_i, after_i, cin, cout),
                    )
                    out["attendance"] += 1

    conn.commit()
    return out


def attendance_matrix_rows(conn, scopes: list[str] | None, *, class_id: int | None = None) -> list[dict]:
    """Flat export similar to CĐS-Attendance: student × session check-in/out."""
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_mba_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    sql = (
        "SELECT cs.student_code, cs.full_name, cs.gender, cs.dob, cs.place_of_birth, "
        "cs.email, cs.phone, cs.company, cs.job_title, "
        "cg.name, cg.program_code, c.code, c.name, "
        "ats.session_date, "
        "COALESCE(am.check_in, CAST(am.present AS REAL)), "
        "COALESCE(am.check_out, CAST(COALESCE(am.present_after_break,1) AS REAL)) "
        "FROM attendance_marks am "
        "JOIN attendance_sessions ats ON ats.id = am.attendance_session_id "
        "JOIN teaching_assignments ta ON ta.id = ats.assignment_id "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN class_students cs ON cs.id = am.student_id "
        "JOIN courses c ON c.id = ta.course_id "
        f"WHERE {frag}"
    )
    if class_id:
        sql += " AND cg.id = ?"
        params.append(class_id)
    sql += " ORDER BY c.code, cs.full_name, ats.session_date"
    rows = []
    for r in cur.execute(sql, params).fetchall():
        rows.append(
            {
                "student_code": r[0],
                "full_name": r[1],
                "gender": r[2],
                "dob": r[3],
                "place_of_birth": r[4],
                "email": r[5],
                "phone": r[6],
                "company": r[7],
                "job_title": r[8],
                "class_name": r[9],
                "program_code": r[10],
                "course_code": r[11],
                "course_name": r[12],
                "session_date": r[13],
                "check_in": r[14],
                "check_out": r[15],
                "day_total": (float(r[14] or 0) + float(r[15] or 0)),
            }
        )
    return rows


def grade_synthesis_rows(conn, scopes: list[str] | None, *, class_id: int | None = None) -> list[dict]:
    """Per-student course scores for Grade Synthesis style export."""
    from ops_data import _scopes_sql
    from coord_ops import get_class_gradebook

    cur = conn.cursor()
    ensure_mba_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    sql = f"SELECT cg.id FROM class_groups cg WHERE {frag}"
    if class_id:
        sql += " AND cg.id = ?"
        params.append(class_id)
    sql += " ORDER BY cg.program_code, cg.name"
    out: list[dict] = []
    for (cid,) in cur.execute(sql, params).fetchall():
        book = get_class_gradebook(conn, cid)
        if not book:
            continue
        for st in book["students"]:
            base = {
                "class_name": book["meta"]["name"],
                "program_code": book["meta"]["program_code"],
                "student_code": st.get("student_code"),
                "full_name": st.get("full_name"),
                "gender": st.get("gender"),
                "dob": st.get("dob"),
                "total": st.get("total"),
            }
            for c in book["courses"]:
                g = st["grades"].get(str(c["id"]), {})
                label = c.get("code") or c.get("module_no") or str(c["id"])
                base[f"score_{label}"] = g.get("score")
                if g.get("group_assignment") is not None:
                    base[f"ga_{label}"] = g.get("group_assignment")
                if g.get("final_exam") is not None:
                    base[f"fe_{label}"] = g.get("final_exam")
            out.append(base)
    return out

