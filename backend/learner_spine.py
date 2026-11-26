"""
Một người, một hồ sơ cá nhân (person_profiles).

Ứng viên → người dự thi chính thức → học viên → cựu học viên.

Không có giai đoạn Sinh viên. `learners` giữ liên kết theo từng hồ sơ tuyển sinh
để không trộn điểm giữa các chương trình. Mã học viên nằm trên program_enrollments.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


STAGE_LABELS = {
    "candidate": "Ứng viên",
    "examinee": "Người dự thi chính thức",
    "learner": "Học viên",
    "alumni": "Cựu học viên",
}


def stage_label(stage: str | None, *, enrolled: bool = False) -> str:
    st = (stage or "candidate").strip() or "candidate"
    if st == "student":
        st = "learner" if enrolled else "examinee"
    return STAGE_LABELS.get(st, st)

PROGRESS_LABELS = {
    "completed": "Đã học xong",
    "recognized": "Miễn / công nhận",
    "studying": "Đang học",
    "failed": "Chưa đạt",
    "scheduled": "Sắp học",
    "not_started": "Chưa học",
    "done": "Đã học xong",
    "current": "Đang học",
    "upcoming": "Chưa học",
}

SPECIAL_TOKENS = (
    "thesis",
    "capstone",
    "chuyên đề",
    "chuyen de",
    "đề án",
    "de an",
    "business game",
    "mémoire",
    "memoire",
    "dissertation",
)


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _cols(cur, table: str) -> set[str]:
    try:
        return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def _add_col(cur, table: str, name: str, spec: str) -> None:
    if name not in _cols(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")


def _table_exists(cur, table: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def ensure_learner_spine(cur) -> None:
    from nv2026_ops import ensure_nv2026_tables

    ensure_nv2026_tables(cur)
    cur.execute(
        "CREATE TABLE IF NOT EXISTS exam_registrations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "learner_id INTEGER NOT NULL, "
        "application_id INTEGER NOT NULL UNIQUE, "
        "round_id INTEGER, "
        "program_code TEXT, "
        "exam_board TEXT, "
        "registered_at TEXT, "
        "registered_by TEXT, "
        "fee_status TEXT NOT NULL DEFAULT 'pending', "
        "fee_amount REAL DEFAULT 0, "
        "charge_id INTEGER, "
        "paid_at TEXT, "
        "roster_status TEXT NOT NULL DEFAULT 'registered', "
        "written_score TEXT, "
        "board_decision TEXT, "
        "FOREIGN KEY (learner_id) REFERENCES learners(id), "
        "FOREIGN KEY (application_id) REFERENCES applications(id))"
    )
    for table, cols in (
        ("learners", [
            ("stage", "TEXT DEFAULT 'candidate'"),
            ("candidate_code", "TEXT"),
            ("class_student_id", "INTEGER"),
            ("portal_user_id", "INTEGER"),
            ("round_id", "INTEGER"),
            ("crm_profile_id", "INTEGER"),
            ("updated_at", "TEXT"),
            ("person_id", "INTEGER"),
        ]),
        ("applications", [("learner_id", "INTEGER")]),
        ("class_students", [("learner_id", "INTEGER")]),
        ("course_grades", [("learner_id", "INTEGER")]),
        ("thesis_records", [("learner_id", "INTEGER")]),
        ("student_charges", [("learner_id", "INTEGER")]),
    ):
        if _table_exists(cur, table):
            for name, spec in cols:
                _add_col(cur, table, name, spec)
    if _table_exists(cur, "crm_source_profiles"):
        _add_col(cur, "crm_source_profiles", "learner_id", "INTEGER")
    from person_profile import ensure_person_tables

    ensure_person_tables(cur)


def derive_stage(
    status: str | None,
    *,
    has_exam_reg: bool = False,
    examinee_confirmed: bool = False,
    has_program_enrollment: bool = False,
    lifecycle: str | None = None,
    enrolled: bool = False,
) -> str:
    """Tư cách dự thi chỉ tính khi đã xác nhận. Đăng ký nháp không đủ."""
    del has_exam_reg
    life = (lifecycle or "").strip().lower()
    if life in ("graduated", "alumni"):
        return "alumni"
    if has_program_enrollment or (enrolled and life not in ("withdrawn",)):
        return "learner"
    st = (status or "").strip().lower()
    if st == "withdrawn":
        return "candidate"
    if examinee_confirmed:
        return "examinee"
    return "candidate"


def _candidate_code(app_id: int, cfvg: str | None) -> str:
    code = (cfvg or "").strip()
    return code or f"UV{int(app_id):05d}"


def upsert_learner_for_application(conn, application_id: int) -> dict:
    """Tạo hoặc cập nhật học viên gốc từ hồ sơ ứng viên. Không commit."""
    cur = conn.cursor()
    ensure_learner_spine(cur)
    app_cols = _cols(cur, "applications")
    want = [
        "id", "round_id", "program_code", "full_name", "cccd", "email", "phone", "status",
    ]
    for optional in (
        "cfvg_app_no", "student_code_mba", "board_decision",
        "portal_user_id", "examinee_confirmed_at", "dob", "person_id",
    ):
        if optional in app_cols:
            want.append(optional)
    row = cur.execute(
        f"SELECT {', '.join(want)} FROM applications WHERE id = ?",
        (int(application_id),),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy hồ sơ ứng viên")
    app = dict(zip(want, row))
    cs = None
    if _table_exists(cur, "class_students"):
        cs_cols = _cols(cur, "class_students")
        cs_want = [c for c in ("id", "student_code", "lifecycle_status") if c in cs_cols or c == "id"]
        if "portal_user_id" in cs_cols:
            cs_want.append("portal_user_id")
        cs_row = cur.execute(
            f"SELECT {', '.join(cs_want)} FROM class_students "
            "WHERE application_id = ? ORDER BY id DESC LIMIT 1",
            (int(application_id),),
        ).fetchone()
        if cs_row:
            cs = dict(zip(cs_want, cs_row))
    from person_profile import attach_person, ensure_program_enrollment

    person_id = int(app.get("person_id") or 0) or attach_person(
        cur,
        int(application_id),
        full_name=app.get("full_name"),
        cccd=app.get("cccd"),
        email=app.get("email"),
        phone=app.get("phone"),
        dob=app.get("dob"),
        portal_user_id=app.get("portal_user_id"),
    )
    enrolled_at = ""
    prior = cur.execute(
        "SELECT enrolled_at FROM learners WHERE application_id = ?",
        (int(application_id),),
    ).fetchone()
    if prior and prior[0]:
        enrolled_at = prior[0]
    life = (cs or {}).get("lifecycle_status")
    confirmed = bool((app.get("examinee_confirmed_at") or "").strip())
    stage = derive_stage(
        app.get("status"),
        examinee_confirmed=confirmed,
        has_program_enrollment=False,
        lifecycle=life,
        enrolled=bool(cs),
    )
    code = _candidate_code(app["id"], app.get("cfvg_app_no"))
    student_code = ((cs or {}).get("student_code") or app.get("student_code_mba") or "").strip()
    portal = app.get("portal_user_id") or (cs or {}).get("portal_user_id")
    crm_id = None
    if _table_exists(cur, "crm_source_profiles") and "application_id" in _cols(cur, "crm_source_profiles"):
        crm = cur.execute(
            "SELECT id FROM crm_source_profiles WHERE application_id = ? ORDER BY id DESC LIMIT 1",
            (int(application_id),),
        ).fetchone()
        if crm:
            crm_id = crm[0]
    existing = cur.execute(
        "SELECT id FROM learners WHERE application_id = ?",
        (int(application_id),),
    ).fetchone()
    payload = (
        stage, code, student_code or None, app.get("full_name"), app.get("program_code"),
        app.get("cccd"), app.get("email"), app.get("phone"),
        cs["id"] if cs else None, portal, app.get("round_id"), crm_id, _now(),
    )
    if existing:
        lid = int(existing[0])
        cur.execute(
            "UPDATE learners SET stage=?, candidate_code=?, "
            "student_code=COALESCE(NULLIF(?, ''), student_code), "
            "full_name=?, program_code=?, cccd=?, email=?, phone=?, "
            "class_student_id=?, portal_user_id=COALESCE(?, portal_user_id), "
            "round_id=?, crm_profile_id=COALESCE(?, crm_profile_id), updated_at=? "
            "WHERE id=?",
            (*payload, lid),
        )
    else:
        cur.execute(
            "INSERT INTO learners ("
            "application_id, stage, candidate_code, student_code, full_name, program_code, "
            "cccd, email, phone, class_student_id, portal_user_id, round_id, crm_profile_id, "
            "updated_at, created_at"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (int(application_id), *payload, _now()),
        )
        lid = int(cur.lastrowid)
    if "learner_id" in _cols(cur, "applications"):
        cur.execute("UPDATE applications SET learner_id = ? WHERE id = ?", (lid, int(application_id)))
    if cs and "learner_id" in _cols(cur, "class_students"):
        cur.execute("UPDATE class_students SET learner_id = ? WHERE id = ?", (lid, cs["id"]))
        if _table_exists(cur, "course_grades") and "learner_id" in _cols(cur, "course_grades"):
            cur.execute(
                "UPDATE course_grades SET learner_id = ? WHERE student_id = ?",
                (lid, cs["id"]),
            )
        if _table_exists(cur, "thesis_records") and "learner_id" in _cols(cur, "thesis_records"):
            cur.execute(
                "UPDATE thesis_records SET learner_id = ? WHERE student_id = ?",
                (lid, cs["id"]),
            )
    if crm_id and "learner_id" in _cols(cur, "crm_source_profiles"):
        cur.execute(
            "UPDATE crm_source_profiles SET learner_id = ? WHERE id = ?",
            (lid, crm_id),
        )
    if person_id and "person_id" in _cols(cur, "learners"):
        cur.execute(
            "UPDATE learners SET person_id = ? WHERE id = ? AND IFNULL(person_id, 0) = 0",
            (person_id, lid),
        )
    enrollment_id = ensure_program_enrollment(
        cur,
        int(application_id),
        person_id=int(person_id or 0),
        program_code=app.get("program_code") or "",
        learner_code=student_code or "",
        decision_ref=app.get("board_decision") or "",
        status=app.get("status") or "",
        lifecycle=life or "",
        has_class=bool(cs),
        learner_id=lid,
        enrolled_at=enrolled_at,
    )
    final_stage = derive_stage(
        app.get("status"),
        examinee_confirmed=confirmed,
        has_program_enrollment=bool(enrollment_id),
        lifecycle=life,
        enrolled=bool(cs),
    )
    if final_stage != stage:
        cur.execute("UPDATE learners SET stage = ? WHERE id = ?", (final_stage, lid))
        stage = final_stage
    return {
        "learner_id": lid,
        "application_id": int(application_id),
        "person_id": int(person_id or 0),
        "stage": stage,
        "stage_label": stage_label(stage, enrolled=bool(cs) or bool(enrollment_id)),
        "candidate_code": code,
        "student_code": student_code,
        "class_student_id": cs["id"] if cs else None,
    }


def backfill_missing_learners(conn) -> int:
    cur = conn.cursor()
    ensure_learner_spine(cur)
    ids = [
        r[0]
        for r in cur.execute(
            "SELECT a.id FROM applications a "
            "WHERE NOT EXISTS (SELECT 1 FROM learners l WHERE l.application_id = a.id)"
        ).fetchall()
    ]
    for aid in ids:
        upsert_learner_for_application(conn, int(aid))
    if ids:
        conn.commit()
    return len(ids)


def refresh_from_class_students(conn, student_ids: list[int]) -> int:
    cur = conn.cursor()
    ensure_learner_spine(cur)
    ids = [int(x) for x in student_ids if str(x).strip()]
    if not ids:
        return 0
    ph = ",".join("?" * len(ids))
    aids = [
        int(r[0])
        for r in cur.execute(
            f"SELECT application_id FROM class_students "
            f"WHERE id IN ({ph}) AND application_id IS NOT NULL",
            ids,
        ).fetchall()
    ]
    return refresh_learner_stages(conn, aids)


def refresh_learner_stages(conn, application_ids: list[int] | None = None) -> int:
    cur = conn.cursor()
    ensure_learner_spine(cur)
    if application_ids is None:
        ids = [r[0] for r in cur.execute("SELECT id FROM applications").fetchall()]
    else:
        ids = [int(x) for x in application_ids]
    for aid in ids:
        upsert_learner_for_application(conn, aid)
    conn.commit()
    return len(ids)


def _fee_amount(cur, round_id: int | None, requested: float | None) -> tuple[str, float]:
    if requested is not None:
        label = "Lệ phí thi đầu vào"
        try:
            from treasury_ops import _catalog_fee

            label, _default = _catalog_fee(cur, "entrance_exam", 0)
        except Exception:
            pass
        return label, float(requested)
    if round_id and _table_exists(cur, "round_fee_settings"):
        row = cur.execute(
            "SELECT unit_price FROM round_fee_settings WHERE round_id = ? AND fee_type = 'entrance_exam'",
            (round_id,),
        ).fetchone()
        if row and row[0] is not None:
            return "Lệ phí thi đầu vào", float(row[0])
    try:
        from treasury_ops import _catalog_fee

        return _catalog_fee(cur, "entrance_exam", 0)
    except Exception:
        return "Lệ phí thi đầu vào", 0.0


def _ensure_exam_charge(conn, application_id: int, learner_id: int, amount: float, title: str) -> int:
    from treasury_ops import ensure_treasury_tables

    cur = conn.cursor()
    ensure_treasury_tables(cur)
    ensure_learner_spine(cur)
    row = cur.execute(
        "SELECT id FROM student_charges WHERE application_id = ? AND fee_type = 'entrance_exam' "
        "ORDER BY id DESC LIMIT 1",
        (application_id,),
    ).fetchone()
    if row:
        cid = int(row[0])
        sets = ["amount_due = CASE WHEN amount_paid > 0 THEN amount_due ELSE ? END", "title = ?"]
        params: list[Any] = [amount, title]
        if "learner_id" in _cols(cur, "student_charges"):
            sets.append("learner_id = ?")
            params.append(learner_id)
        params.append(cid)
        cur.execute(f"UPDATE student_charges SET {', '.join(sets)} WHERE id = ?", params)
        return cid
    prog = cur.execute(
        "SELECT program_code FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    program_code = prog[0] if prog else ""
    cur.execute(
        "INSERT INTO student_charges ("
        "application_id, program_code, fee_type, title, amount_due, amount_paid, "
        "amount_adjust, status, notes, created_at, learner_id"
        ") VALUES (?, ?, 'entrance_exam', ?, ?, 0, 0, 'pending', ?, ?, ?)",
        (
            application_id, program_code, title, amount,
            "Lệ phí thi đầu vào — không phải phí ghi danh",
            _now(), learner_id,
        ),
    )
    return int(cur.lastrowid)


def register_examinee(conn, application_id: int, *, actor: str = "", amount: float | None = None, exam_board: str = "") -> dict:
    """Ứng viên đăng ký thành thí sinh của đợt thi chương trình và mở lệ phí thi."""
    cur = conn.cursor()
    ensure_learner_spine(cur)
    cols = _cols(cur, "applications")

    def _present(name: str) -> str:
        return name if name in cols else "NULL"

    app = cur.execute(
        "SELECT id, status, round_id, program_code, "
        f"{_present('exam_board')}, {_present('written_score')}, {_present('board_decision')} "
        "FROM applications WHERE id = ?",
        (int(application_id),),
    ).fetchone()
    if not app:
        raise ValueError("Không tìm thấy hồ sơ ứng viên")
    if (app[1] or "") == "withdrawn":
        raise ValueError("Hồ sơ đã rút — không đăng ký nội dung thi")
    confirmed = cur.execute(
        "SELECT IFNULL(examinee_confirmed_at, '') FROM applications WHERE id = ?",
        (int(application_id),),
    ).fetchone()
    if not confirmed or not (confirmed[0] or "").strip():
        raise ValueError(
            "Chưa xác nhận người dự thi chính thức. Tạo đăng ký nháp không suy ra tư cách dự thi."
        )
    spine = upsert_learner_for_application(conn, int(application_id))
    label, fee_amt = _fee_amount(cur, app[2], amount)
    charge_id = _ensure_exam_charge(conn, int(application_id), spine["learner_id"], fee_amt, label)
    board = (exam_board or app[4] or "").strip()
    existing = cur.execute(
        "SELECT id, fee_status, roster_status FROM exam_registrations WHERE application_id = ?",
        (int(application_id),),
    ).fetchone()
    if existing:
        cur.execute(
            "UPDATE exam_registrations SET learner_id=?, round_id=?, program_code=?, "
            "exam_board=COALESCE(NULLIF(?, ''), exam_board), fee_amount=?, charge_id=?, "
            "written_score=COALESCE(written_score, ?), board_decision=COALESCE(board_decision, ?) "
            "WHERE id=?",
            (spine["learner_id"], app[2], app[3], board, fee_amt, charge_id, app[5], app[6], existing[0]),
        )
        reg_id = int(existing[0])
        fee_status = existing[1]
        roster = existing[2]
    else:
        cur.execute(
            "INSERT INTO exam_registrations ("
            "learner_id, application_id, round_id, program_code, exam_board, registered_at, "
            "registered_by, fee_status, fee_amount, charge_id, roster_status, written_score, board_decision"
            ") VALUES (?,?,?,?,?,?,?,'pending',?,?,'registered',?,?)",
            (
                spine["learner_id"], int(application_id), app[2], app[3], board, _now(), actor,
                fee_amt, charge_id, app[5], app[6],
            ),
        )
        reg_id = int(cur.lastrowid)
        fee_status = "pending"
        roster = "registered"
    from person_profile import fee_required_before_roster

    if (
        "exam_eligible_flag" in _cols(cur, "applications")
        and not fee_required_before_roster(cur, app[2])
    ):
        cur.execute(
            "UPDATE applications SET exam_eligible_flag = 'yes' "
            "WHERE id = ? AND IFNULL(exam_eligible_flag,'') NOT IN ('yes','1','true')",
            (int(application_id),),
        )
    spine = upsert_learner_for_application(conn, int(application_id))
    conn.commit()
    return {
        "ok": True,
        "registration_id": reg_id,
        "learner_id": spine["learner_id"],
        "stage": spine["stage"],
        "stage_label": spine["stage_label"],
        "candidate_code": spine["candidate_code"],
        "fee_status": fee_status,
        "fee_amount": fee_amt,
        "charge_id": charge_id,
        "roster_status": roster,
        "handoff": "Đã đăng ký nội dung thi trên hồ sơ đã xác nhận. Lệ phí theo quy chế của đợt.",
    }


def mark_exam_fee_paid(conn, application_id: int, *, actor: str = "", amount: float | None = None) -> dict:
    """Xác nhận thí sinh đã nộp lệ phí thi. Không đổi phí ghi danh / trạng thái đỗ."""
    cur = conn.cursor()
    ensure_learner_spine(cur)
    reg = cur.execute(
        "SELECT id, learner_id, charge_id, fee_amount, fee_status FROM exam_registrations WHERE application_id = ?",
        (int(application_id),),
    ).fetchone()
    if not reg:
        raise ValueError("Thí sinh chưa đăng ký đợt thi")
    if reg[4] == "paid":
        return {"ok": True, "already": True, "registration_id": reg[0], "fee_status": "paid"}
    pay_amt = float(amount if amount is not None else (reg[3] or 0))
    charge_id = reg[2]
    today = date.today().isoformat()
    if charge_id:
        from treasury_ops import _recompute_charge, ensure_treasury_tables

        ensure_treasury_tables(cur)
        cur.execute(
            "INSERT INTO fee_payments (charge_id, amount, paid_at, method, proof_note, created_by) "
            "VALUES (?, ?, ?, 'bank_transfer', ?, ?)",
            (charge_id, pay_amt, today, "Lệ phí thi đầu vào", actor),
        )
        _recompute_charge(cur, int(charge_id))
    cur.execute(
        "UPDATE exam_registrations SET fee_status='paid', paid_at=?, fee_amount=COALESCE(NULLIF(fee_amount,0), ?) "
        "WHERE id=?",
        (today, pay_amt, reg[0]),
    )
    if "exam_eligible_flag" in _cols(cur, "applications"):
        cur.execute(
            "UPDATE applications SET exam_eligible_flag = 'yes' WHERE id = ?",
            (int(application_id),),
        )
    conn.commit()
    return {
        "ok": True,
        "registration_id": reg[0],
        "learner_id": reg[1],
        "fee_status": "paid",
        "amount": pay_amt,
        "handoff": "Lệ phí thi đã thu. Thí sinh đủ điều kiện vào danh sách hội đồng.",
    }


_LEGACY_EXAM_STATUSES = {"interview", "passed", "failed", "paid", "official"}


def entrance_sitting_ready(cur, application_id: int) -> tuple[bool, str]:
    """Cấp SBD và lập hội đồng: đã xác nhận dự thi; đợt yêu cầu thì đã thu lệ phí thi.

    Hồ sơ đã ở bước phỏng vấn hoặc sau đó, và chưa có dòng đăng ký thi mới,
    giữ lối cũ để không chặn đợt đang chạy.
    """
    from person_profile import ensure_person_tables, fee_required_before_roster

    ensure_person_tables(cur)
    if "examinee_confirmed_at" not in _cols(cur, "applications"):
        return True, ""
    row = cur.execute(
        "SELECT IFNULL(examinee_confirmed_at, ''), round_id, IFNULL(status, '') "
        "FROM applications WHERE id = ?",
        (int(application_id),),
    ).fetchone()
    if not row:
        return False, "Không tìm thấy hồ sơ ứng viên"
    confirmed, round_id, status = row
    if status == "withdrawn":
        return False, "Hồ sơ đã rút"
    if not (confirmed or "").strip():
        return False, "Chưa xác nhận người dự thi chính thức"
    if not fee_required_before_roster(cur, round_id):
        return True, ""
    reg = None
    if _table_exists(cur, "exam_registrations"):
        reg = cur.execute(
            "SELECT IFNULL(fee_status, '') FROM exam_registrations WHERE application_id = ?",
            (int(application_id),),
        ).fetchone()
    if reg and reg[0] not in ("paid", "waived"):
        return False, "Theo quy chế của đợt, cần xác nhận lệ phí thi trước khi cấp số báo danh hoặc xếp hội đồng."
    if not reg and status not in _LEGACY_EXAM_STATUSES:
        return False, "Chưa đăng ký nội dung thi và chưa xác nhận lệ phí thi."
    return True, ""


def bind_application_spine(conn, application_id: int) -> dict:
    """Gắn học viên gốc và người vào hồ sơ vừa tạo từ Marcom hoặc CRM. Không commit."""
    spine = upsert_learner_for_application(conn, int(application_id))
    cur = conn.cursor()
    if not _table_exists(cur, "crm_source_profiles"):
        return spine
    cols = _cols(cur, "crm_source_profiles")
    sets, params = [], []
    person_id = int(spine.get("person_id") or 0)
    learner_id = int(spine.get("learner_id") or 0)
    if person_id and "person_id" in cols:
        sets.append("person_id = COALESCE(NULLIF(person_id, 0), ?)")
        params.append(person_id)
    if learner_id and "learner_id" in cols:
        sets.append("learner_id = COALESCE(learner_id, ?)")
        params.append(learner_id)
    if sets:
        params.append(int(application_id))
        cur.execute(
            f"UPDATE crm_source_profiles SET {', '.join(sets)} WHERE application_id = ?",
            params,
        )
    return spine


def list_on_exam_board(conn, application_id: int, *, exam_board: str, actor: str = "") -> dict:
    cur = conn.cursor()
    ensure_learner_spine(cur)
    board = (exam_board or "").strip()
    if not board:
        raise ValueError("Cần tên hội đồng thi")
    reg = cur.execute(
        "SELECT id, fee_status, round_id FROM exam_registrations WHERE application_id = ?",
        (int(application_id),),
    ).fetchone()
    if not reg:
        raise ValueError("Chưa đăng ký nội dung thi")
    from person_profile import fee_required_before_roster

    if fee_required_before_roster(cur, reg[2]) and reg[1] not in ("paid", "waived"):
        raise ValueError("Theo quy chế của đợt này, cần xác nhận lệ phí thi trước khi xếp hội đồng.")
    cur.execute(
        "UPDATE exam_registrations SET roster_status='listed', exam_board=? WHERE id=?",
        (board, reg[0]),
    )
    if "exam_eligible_flag" in _cols(cur, "applications"):
        cur.execute(
            "UPDATE applications SET exam_board = ?, exam_eligible_flag = 'yes' WHERE id = ?",
            (board, int(application_id)),
        )
    else:
        cur.execute(
            "UPDATE applications SET exam_board = ? WHERE id = ?",
            (board, int(application_id)),
        )
    conn.commit()
    return {
        "ok": True,
        "registration_id": reg[0],
        "exam_board": board,
        "roster_status": "listed",
        "actor": actor,
        "handoff": "Thí sinh nằm trong danh sách thi của hội đồng.",
    }


def annotate_applications(conn, rows: list[dict]) -> list[dict]:
    if not rows:
        return rows
    cur = conn.cursor()
    ensure_learner_spine(cur)
    ids = []
    for row in rows:
        raw = row.get("application_id") or row.get("id")
        try:
            ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    if not ids:
        return rows
    ph = ",".join("?" * len(ids))
    found: dict[int, dict] = {}
    for r in cur.execute(
        f"SELECT l.application_id, l.id, l.stage, l.candidate_code, l.student_code, "
        f"IFNULL(er.fee_status,''), IFNULL(er.roster_status,''), IFNULL(er.exam_board,''), "
        f"IFNULL(er.fee_amount,0), IFNULL(l.person_id,0) "
        f"FROM learners l LEFT JOIN exam_registrations er ON er.application_id = l.application_id "
        f"WHERE l.application_id IN ({ph})",
        ids,
    ):
        found[int(r[0])] = {
            "learner_id": r[1],
            "person_stage": "examinee" if (r[2] or "") == "student" else (r[2] or "candidate"),
            "person_stage_label": stage_label(r[2] or "candidate"),
            "candidate_code": r[3] or "",
            "spine_student_code": r[4] or "",
            "exam_fee_status": r[5] or "",
            "exam_roster_status": r[6] or "",
            "exam_board_listed": r[7] or "",
            "exam_fee_amount": r[8] or 0,
            "person_id": r[9] or None,
        }
    for row in rows:
        try:
            aid = int(row.get("application_id") or row.get("id"))
        except (TypeError, ValueError):
            continue
        extra = found.get(aid)
        if not extra:
            continue
        row.update(extra)
        if not row.get("student_code"):
            row["student_code"] = extra.get("spine_student_code") or row.get("student_code")
    return rows


def annotate_class_students(conn, rows: list[dict]) -> list[dict]:
    if not rows:
        return rows
    cur = conn.cursor()
    ensure_learner_spine(cur)
    ids = []
    for row in rows:
        try:
            ids.append(int(row.get("id")))
        except (TypeError, ValueError):
            continue
    if not ids:
        return rows
    ph = ",".join("?" * len(ids))
    found: dict[int, dict] = {}
    for r in cur.execute(
        f"SELECT class_student_id, id, stage, candidate_code, application_id, student_code, "
        f"IFNULL(person_id,0) "
        f"FROM learners WHERE class_student_id IN ({ph})",
        ids,
    ):
        if r[0] is None:
            continue
        found[int(r[0])] = {
            "learner_id": r[1],
            "person_stage": "learner" if (r[2] or "") == "student" else (r[2] or "learner"),
            "person_stage_label": stage_label(r[2] or "learner", enrolled=True),
            "candidate_code": r[3] or "",
            "application_id": r[4],
            "spine_student_code": r[5] or "",
            "person_id": r[6] or None,
        }
    for row in rows:
        try:
            sid = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        extra = found.get(sid)
        if extra:
            row.update(extra)
    return rows


def _program_version_id(cur, program_code: str, class_version_id: int | None) -> int | None:
    if class_version_id:
        return int(class_version_id)
    if not program_code or not _table_exists(cur, "program_versions"):
        return None
    row = cur.execute(
        "SELECT id FROM program_versions WHERE program_code = ? AND IFNULL(is_active,1) = 1 "
        "ORDER BY id DESC LIMIT 1",
        (program_code,),
    ).fetchone()
    return int(row[0]) if row else None


def _is_special_course(code: str, name: str) -> bool:
    blob = f"{code} {name}".lower()
    return any(tok in blob for tok in SPECIAL_TOKENS)


def _attendance_for_course(cur, student_id: int, class_id: int, course_id: int) -> dict:
    if not _table_exists(cur, "attendance_marks"):
        return {"sessions": 0, "present": 0, "rate": ""}
    row = cur.execute(
        "SELECT COUNT(*), "
        "SUM(CASE WHEN IFNULL(am.present,1) != 0 THEN 1 ELSE 0 END) "
        "FROM attendance_marks am "
        "JOIN attendance_sessions s ON s.id = am.attendance_session_id "
        "JOIN teaching_assignments ta ON ta.id = s.assignment_id "
        "WHERE am.student_id = ? AND ta.class_id = ? AND ta.course_id = ?",
        (student_id, class_id, course_id),
    ).fetchone()
    total = int(row[0] or 0) if row else 0
    present = int(row[1] or 0) if row else 0
    rate = f"{round(100 * present / total)}%" if total else ""
    return {"sessions": total, "present": present, "rate": rate}


def _lesson_trace(cur, class_id: int, course_id: int, email: str, user_id: int | None) -> dict:
    if not _table_exists(cur, "lesson_view_sessions"):
        return {"lessons_viewed": 0, "minutes": 0}
    clauses = []
    params: list[Any] = [class_id, course_id]
    if email:
        clauses.append("LOWER(IFNULL(lvs.student_email,'')) = ?")
        params.append(email.strip().lower())
    if user_id:
        clauses.append("lvs.user_id = ?")
        params.append(int(user_id))
    if not clauses:
        return {"lessons_viewed": 0, "minutes": 0}
    row = cur.execute(
        "SELECT COUNT(DISTINCT lvs.lesson_id), COALESCE(SUM(lvs.duration_sec),0) "
        "FROM lesson_view_sessions lvs "
        "JOIN class_lessons cl ON cl.id = lvs.lesson_id "
        "JOIN teaching_assignments ta ON ta.id = cl.assignment_id "
        f"WHERE ta.class_id = ? AND ta.course_id = ? AND ({' OR '.join(clauses)})",
        params,
    ).fetchone()
    viewed = int(row[0] or 0) if row else 0
    minutes = int((row[1] or 0) / 60) if row else 0
    return {"lessons_viewed": viewed, "minutes": minutes}


def _pass_line(score) -> float:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return 10.0
    return 10.0 if value <= 20 else 50.0


def _is_recognized(*parts: str | None) -> bool:
    blob = " ".join(str(p or "") for p in parts).lower()
    return any(tok in blob for tok in ("công nhận", "cong nhan", "miễn", "mien", "recognized", "waiver"))


def academic_record(conn, learner_id: int, *, edition: str = "tracking", mask_unpublished: bool = False) -> dict:
    cur = conn.cursor()
    ensure_learner_spine(cur)
    learner = cur.execute(
        "SELECT id, application_id, student_code, full_name, program_code, cccd, email, phone, "
        "stage, candidate_code, class_student_id, enrolled_at, portal_user_id "
        "FROM learners WHERE id = ?",
        (int(learner_id),),
    ).fetchone()
    if not learner:
        raise ValueError("Không tìm thấy học viên")
    keys = [
        "id", "application_id", "student_code", "full_name", "program_code", "cccd", "email",
        "phone", "stage", "candidate_code", "class_student_id", "enrolled_at", "portal_user_id",
    ]
    person = dict(zip(keys, learner))
    person["stage_label"] = stage_label(
        person.get("stage"),
        enrolled=bool(person.get("class_student_id") or person.get("enrolled_at")),
    )
    app = {}
    if person.get("application_id"):
        arow = cur.execute(
            "SELECT status, cfvg_app_no, board_decision, final_result, round_id, admitted_program "
            "FROM applications WHERE id = ?",
            (person["application_id"],),
        ).fetchone()
        if arow:
            app = {
                "status": arow[0], "cfvg_app_no": arow[1], "board_decision": arow[2],
                "final_result": arow[3], "round_id": arow[4], "admitted_program": arow[5],
            }
    reg = None
    if person.get("application_id"):
        rrow = cur.execute(
            "SELECT exam_board, fee_status, fee_amount, roster_status, written_score, board_decision "
            "FROM exam_registrations WHERE application_id = ?",
            (person["application_id"],),
        ).fetchone()
        if rrow:
            reg = {
                "exam_board": rrow[0], "fee_status": rrow[1], "fee_amount": rrow[2],
                "roster_status": rrow[3], "written_score": rrow[4], "board_decision": rrow[5],
            }
    class_name = ""
    class_id = None
    version_id = None
    if person.get("class_student_id") and _table_exists(cur, "class_students"):
        crow = cur.execute(
            "SELECT cs.class_id, cg.name, cg.program_version_id, cg.program_code "
            "FROM class_students cs JOIN class_groups cg ON cg.id = cs.class_id WHERE cs.id = ?",
            (person["class_student_id"],),
        ).fetchone()
        if crow:
            class_id = crow[0]
            class_name = crow[1] or ""
            version_id = crow[2]
            if not person.get("program_code"):
                person["program_code"] = crow[3]
    version_id = _program_version_id(cur, person.get("program_code") or "", version_id)
    thesis = None
    if person.get("class_student_id") and _table_exists(cur, "thesis_records"):
        trow = cur.execute(
            "SELECT title, tutor, status, total_grade FROM thesis_records WHERE student_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (person["class_student_id"],),
        ).fetchone()
        if trow:
            thesis = {
                "title": trow[0] or "",
                "advisor": trow[1] or "",
                "status": trow[2] or "",
                "grade": trow[3],
            }
    courses: list[dict] = []
    if version_id and _table_exists(cur, "courses"):
        course_rows = cur.execute(
            "SELECT id, code, name, semester, sort_order FROM courses "
            "WHERE program_version_id = ? ORDER BY semester, sort_order, id",
            (version_id,),
        ).fetchall()
        special_seen = False
        for c in course_rows:
            cid, code, name, semester, sort_order = c
            special = _is_special_course(code or "", name or "")
            if special:
                special_seen = True
            grade = None
            locked = 0
            study_score = None
            exam_score = None
            if class_id and person.get("class_student_id") and _table_exists(cur, "course_grades"):
                grow = cur.execute(
                    "SELECT score, locked, group_assignment, final_exam FROM course_grades "
                    "WHERE class_id = ? AND student_id = ? AND course_id = ?",
                    (class_id, person["class_student_id"], cid),
                ).fetchone()
                if grow:
                    grade, locked, study_score, exam_score = grow
            assigned = False
            if class_id and _table_exists(cur, "teaching_assignments"):
                assigned = bool(cur.execute(
                    "SELECT 1 FROM teaching_assignments WHERE class_id = ? AND course_id = ?",
                    (class_id, cid),
                ).fetchone())
            remarks = ""
            if class_id and person.get("class_student_id") and _table_exists(cur, "course_grades"):
                extra = cur.execute(
                    "SELECT IFNULL(remarks,''), IFNULL(observations,'') FROM course_grades "
                    "WHERE class_id = ? AND student_id = ? AND course_id = ?",
                    (class_id, person["class_student_id"], cid),
                ).fetchone()
                if extra:
                    remarks = f"{extra[0]} {extra[1]}"
            future = False
            if assigned and class_id and _table_exists(cur, "attendance_sessions"):
                future = bool(cur.execute(
                    "SELECT 1 FROM attendance_sessions s "
                    "JOIN teaching_assignments ta ON ta.id = s.assignment_id "
                    "WHERE ta.class_id = ? AND ta.course_id = ? "
                    "AND IFNULL(s.session_date,'') > date('now') LIMIT 1",
                    (class_id, cid),
                ).fetchone())
            published = bool(locked)
            if _is_recognized(remarks):
                progress = "recognized"
            elif published and grade is not None:
                progress = "failed" if float(grade) < _pass_line(grade) else "completed"
            elif grade is not None or study_score is not None or exam_score is not None or assigned:
                progress = "scheduled" if future and grade is None and study_score is None else (
                    "studying" if assigned or grade is not None else "not_started"
                )
            else:
                progress = "not_started"
            if edition == "official" and progress not in ("completed", "recognized", "failed"):
                continue
            if edition == "official" and not published and progress != "recognized":
                continue
            att = (
                _attendance_for_course(cur, int(person["class_student_id"]), int(class_id), int(cid))
                if class_id and person.get("class_student_id")
                else {"sessions": 0, "present": 0, "rate": ""}
            )
            trace = (
                _lesson_trace(
                    cur, int(class_id), int(cid),
                    person.get("email") or "", person.get("portal_user_id"),
                )
                if class_id else {"lessons_viewed": 0, "minutes": 0}
            )
            advisor = ""
            if special:
                advisor = (thesis or {}).get("advisor") or "Chưa phân công hướng dẫn"
            courses.append({
                "course_id": cid,
                "course_code": code,
                "course_name": name,
                "semester": semester,
                "sort_order": sort_order,
                "progress": progress,
                "progress_label": PROGRESS_LABELS.get(progress, progress),
                "published": published,
                "study_score": None if (edition == "official" or mask_unpublished) and not published else study_score,
                "exam_score": None if (edition == "official" or mask_unpublished) and not published else exam_score,
                "final_score": None if (edition == "official" or mask_unpublished) and not published else grade,
                "attendance": att["rate"],
                "attendance_sessions": att["sessions"],
                "lessons_viewed": trace["lessons_viewed"],
                "study_minutes": trace["minutes"],
                "special": special,
                "advisor": advisor,
            })
        if thesis and not special_seen and (edition != "official" or thesis.get("grade") not in (None, "")):
            courses.append({
                "course_id": 0,
                "course_code": "CDTN",
                "course_name": thesis.get("title") or "Chuyên đề / đề án",
                "semester": "",
                "sort_order": 999,
                "progress": "completed" if thesis.get("grade") not in (None, "") else "studying",
                "progress_label": PROGRESS_LABELS[
                    "completed" if thesis.get("grade") not in (None, "") else "studying"
                ],
                "published": thesis.get("grade") not in (None, ""),
                "study_score": None,
                "exam_score": None,
                "final_score": thesis.get("grade"),
                "attendance": "",
                "attendance_sessions": 0,
                "lessons_viewed": 0,
                "study_minutes": 0,
                "special": True,
                "advisor": thesis.get("advisor") or "Chưa phân công hướng dẫn",
            })
    done = [c for c in courses if c["progress"] in ("completed", "recognized", "done")]
    current = [c for c in courses if c["progress"] in ("studying", "current")]
    upcoming = [c for c in courses if c["progress"] in ("not_started", "scheduled", "upcoming")]
    failed = [c for c in courses if c["progress"] == "failed"]
    scored = [c["final_score"] for c in done if isinstance(c.get("final_score"), (int, float))]
    gpa = round(sum(scored) / len(scored), 2) if scored else None
    class_gpa = None
    if class_id:
        try:
            class_gpa_row = cur.execute(
                "SELECT ROUND(AVG(student_gpa), 2) FROM ("
                " SELECT AVG(score) AS student_gpa FROM course_grades "
                " WHERE class_id = ? AND score IS NOT NULL GROUP BY student_id"
                ")",
                (int(class_id),),
            ).fetchone()
            if class_gpa_row and class_gpa_row[0] is not None:
                class_gpa = class_gpa_row[0]
        except Exception:
            class_gpa = None
    return {
        "learner": person,
        "application": app,
        "exam": reg,
        "class_name": class_name,
        "program_version_id": version_id,
        "thesis": thesis,
        "edition": edition,
        "courses": courses,
        "summary": {
            "done": len(done),
            "current": len(current),
            "upcoming": len(upcoming),
            "failed": len(failed),
            "total": len(courses),
            "gpa": gpa,
            "class_gpa": class_gpa,
            "done_names": ", ".join(c["course_code"] for c in done),
            "upcoming_names": ", ".join(c["course_code"] for c in upcoming),
            "current_names": ", ".join(c["course_code"] for c in current),
            "failed_names": ", ".join(c["course_code"] for c in failed),
        },
    }


def list_academic_records(conn, scopes: list[str] | None, *, q: str = "", semester: str = "") -> list[dict]:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_learner_spine(cur)
    refresh_learner_stages(conn)
    frag, params = _scopes_sql(scopes, "l.program_code")
    sql = (
        "SELECT l.id, l.candidate_code, l.student_code, l.full_name, l.stage, l.program_code, "
        "l.email, l.application_id, l.class_student_id, "
        "IFNULL(a.cfvg_app_no,''), IFNULL(a.status,''), IFNULL(a.board_decision,''), "
        "IFNULL(cg.name,''), IFNULL(er.fee_status,''), IFNULL(er.roster_status,''), IFNULL(er.exam_board,''), "
        "IFNULL(l.person_id,0) "
        "FROM learners l "
        "LEFT JOIN applications a ON a.id = l.application_id "
        "LEFT JOIN class_students cs ON cs.id = l.class_student_id "
        "LEFT JOIN class_groups cg ON cg.id = cs.class_id "
        "LEFT JOIN exam_registrations er ON er.application_id = l.application_id "
        f"WHERE {frag}"
    )
    if q:
        sql += (
            " AND (l.full_name LIKE ? OR IFNULL(l.candidate_code,'') LIKE ? "
            "OR IFNULL(l.student_code,'') LIKE ? OR IFNULL(l.email,'') LIKE ? "
            "OR IFNULL(a.cfvg_app_no,'') LIKE ?)"
        )
        like = f"%{q}%"
        params.extend([like, like, like, like, like])
    sql += " ORDER BY l.id DESC"
    rows = []
    for r in cur.execute(sql, params).fetchall():
        stage = r[4] or "candidate"
        item = {
            "id": r[0],
            "learner_id": r[0],
            "candidate_code": r[1] or r[9],
            "student_code": r[2] or "",
            "full_name": r[3] or "",
            "person_stage": "learner" if stage == "student" else stage,
            "person_stage_label": stage_label(stage, enrolled=bool(r[8])),
            "person_id": r[16] or None,
            "program_code": r[5] or "",
            "email": r[6] or "",
            "application_id": r[7],
            "class_student_id": r[8],
            "application_status": r[10],
            "board_decision": r[11],
            "class_name": r[12],
            "exam_fee_status": r[13],
            "exam_roster_status": r[14],
            "exam_board": r[15],
        }
        try:
            rec = academic_record(conn, int(r[0]))
            summary = rec["summary"]
            item["courses_done"] = summary["done"]
            item["courses_current"] = summary["current"]
            item["courses_upcoming"] = summary["upcoming"]
            item["gpa_to_date"] = "" if summary["gpa"] is None else summary["gpa"]
            item["class_gpa"] = "" if summary.get("class_gpa") is None else summary.get("class_gpa")
            item["progress_note"] = (
                f"Xong {summary['done']}/{summary['total']}"
                + (f" · GPA {summary['gpa']}" if summary["gpa"] is not None else "")
            )
        except Exception:
            item["courses_done"] = ""
            item["courses_current"] = ""
            item["courses_upcoming"] = ""
            item["gpa_to_date"] = ""
            item["class_gpa"] = ""
            item["progress_note"] = ""
        rows.append(item)
    if (semester or "").strip() in ("1", "2"):
        _apply_semester_scores(conn, rows, int(semester))
    _attach_class_rank(conn, rows)
    return rows


def _apply_semester_scores(conn, rows: list[dict], semester: int) -> None:
    """Điểm TB cá nhân và điểm TB lớp theo đúng một học kỳ."""
    cur = conn.cursor()
    try:
        scored = cur.execute(
            "SELECT student_id, class_id, ROUND(AVG(score), 2) "
            "FROM course_grades g JOIN courses c ON c.id = g.course_id "
            "WHERE c.semester = ? AND g.score IS NOT NULL "
            "GROUP BY student_id, class_id",
            (semester,),
        ).fetchall()
    except Exception:
        return
    by_student = {int(sid): avg for sid, _cid, avg in scored if sid is not None}
    class_avgs: dict[int, list[float]] = {}
    for _sid, cid, avg in scored:
        if cid is None or avg is None:
            continue
        class_avgs.setdefault(int(cid), []).append(float(avg))
    class_gpa = {
        cid: round(sum(vals) / len(vals), 2) for cid, vals in class_avgs.items() if vals
    }
    class_of_student = {}
    try:
        for sid, cid in cur.execute("SELECT id, class_id FROM class_students").fetchall():
            class_of_student[int(sid)] = int(cid) if cid is not None else None
    except Exception:
        class_of_student = {}
    for item in rows:
        sid = item.get("class_student_id")
        gpa = by_student.get(int(sid)) if sid else None
        item["gpa_to_date"] = "" if gpa is None else gpa
        cid = class_of_student.get(int(sid)) if sid else None
        cg = class_gpa.get(cid) if cid else None
        item["class_gpa"] = "" if cg is None else cg
        item["progress_note"] = f"Kỳ {semester}" + (f" · GPA {gpa}" if gpa is not None else "")


def _attach_class_rank(conn, rows: list[dict]) -> None:
    """Xếp hạng trong lớp. Nếu đã chọn tối đa 5 môn kỳ 1 thì dùng điểm các môn đó."""
    cur = conn.cursor()
    basis = {}
    try:
        for prog, cid in cur.execute(
            "SELECT program_code, course_id FROM scholarship_basis"
        ).fetchall():
            basis.setdefault(prog, []).append(int(cid))
    except Exception:
        basis = {}
    scholarship_gpa = {}
    if any(basis.values()):
        for prog, ids in basis.items():
            if not ids:
                continue
            ph = ",".join("?" * len(ids))
            for sid, avg in cur.execute(
                f"SELECT student_id, ROUND(AVG(score), 2) FROM course_grades "
                f"WHERE course_id IN ({ph}) AND score IS NOT NULL GROUP BY student_id",
                ids,
            ).fetchall():
                scholarship_gpa[int(sid)] = avg
    groups: dict[str, list[dict]] = {}
    for item in rows:
        sid = item.get("class_student_id")
        if sid and int(sid) in scholarship_gpa:
            item["scholarship_gpa"] = scholarship_gpa[int(sid)]
        else:
            item["scholarship_gpa"] = item.get("gpa_to_date") or ""
        groups.setdefault(item.get("class_name") or "", []).append(item)
    for group in groups.values():
        ranked = sorted(
            group,
            key=lambda it: float(it["scholarship_gpa"]) if isinstance(it.get("scholarship_gpa"), (int, float)) else -1,
            reverse=True,
        )
        place = 0
        last = None
        for idx, it in enumerate(ranked, start=1):
            score = it.get("scholarship_gpa")
            if not isinstance(score, (int, float)):
                it["class_rank"] = ""
                continue
            if score != last:
                place = idx
                last = score
            it["class_rank"] = place


def learner_id_for_user(conn, user_id: int) -> int | None:
    cur = conn.cursor()
    ensure_learner_spine(cur)
    if "portal_user_id" in _cols(cur, "learners"):
        row = cur.execute(
            "SELECT id FROM learners WHERE portal_user_id = ? ORDER BY id DESC LIMIT 1",
            (int(user_id),),
        ).fetchone()
        if row:
            return int(row[0])
    try:
        from e2e_pipeline import resolve_student_identity

        ident = resolve_student_identity(conn, user_id=int(user_id))
    except Exception:
        ident = None
    app = (ident or {}).get("application") or {}
    app_id = app.get("id")
    if not app_id:
        return None
    spine = upsert_learner_for_application(conn, int(app_id))
    if "portal_user_id" in _cols(cur, "learners"):
        cur.execute(
            "UPDATE learners SET portal_user_id = COALESCE(portal_user_id, ?) WHERE id = ?",
            (int(user_id), spine["learner_id"]),
        )
        conn.commit()
    return spine.get("learner_id")


def align_flow_records(conn) -> dict:
    """Đưa hồ sơ hiện có về cùng một người: học viên gốc, cựu học viên, cờ dự thi."""
    cur = conn.cursor()
    ensure_learner_spine(cur)
    created = backfill_missing_learners(conn)
    refreshed = refresh_learner_stages(conn, None)
    promoted = 0
    if _table_exists(cur, "class_students") and "lifecycle_status" in _cols(cur, "class_students"):
        from mba_ops import promote_graduated_to_alumni

        ids = [
            int(r[0])
            for r in cur.execute(
                "SELECT id FROM class_students WHERE lifecycle_status = 'graduated'"
            ).fetchall()
        ]
        for sid in ids:
            promote_graduated_to_alumni(conn, sid)
            promoted += 1
    flags = 0
    if "exam_eligible_flag" in _cols(cur, "applications"):
        for aid, flag in cur.execute(
            "SELECT id, IFNULL(exam_eligible_flag, '') FROM applications"
        ).fetchall():
            ready, _why = entrance_sitting_ready(cur, int(aid))
            want = "yes" if ready else "no"
            current = "yes" if (flag or "").strip().lower() in ("yes", "1", "true") else "no"
            if current != want:
                cur.execute(
                    "UPDATE applications SET exam_eligible_flag = ? WHERE id = ?",
                    (want, int(aid)),
                )
                flags += 1
        conn.commit()
    return {
        "learners_created": created,
        "learners_refreshed": refreshed,
        "alumni_linked": promoted,
        "exam_flags_updated": flags,
    }
    conn.commit()
    return int(spine["learner_id"])
