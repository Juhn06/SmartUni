"""
Một hồ sơ cá nhân xuyên suốt ba giai đoạn nghiệp vụ:

Ứng viên → Người dự thi chính thức → Học viên

Không có thực thể Sinh viên. Thông tin cá nhân sống trên person_profiles.
Đăng ký tuyển sinh, đăng ký thi và hồ sơ theo học chỉ bổ sung nghiệp vụ,
không nhân bản một bộ hồ sơ cá nhân mới.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any


ACADEMIC_LABELS = {
    "awaiting_class": "Chờ xếp lớp",
    "studying": "Đang học",
    "deferred": "Bảo lưu",
    "completed": "Hoàn thành",
    "withdrawn": "Thôi học",
}

SECTION_TITLES = {
    "overview": "Tổng quan",
    "care": "Chăm sóc",
    "admissions": "Tuyển sinh",
    "exam": "Thi tuyển",
    "finance": "Tài chính",
    "programs": "Chương trình theo học",
    "learning": "Quá trình học",
    "results": "Kết quả",
    "documents": "Tài liệu",
    "history": "Lịch sử",
}

_SECTION_PERMS = {
    "care": {
        "admissions.crm_source",
        "admissions.crm_activities",
        "admissions.crm_reminders",
        "admissions.applications",
        "marcom.leads",
    },
    "admissions": {
        "admissions.applications",
        "admissions.pre_enroll",
        "admissions.results",
        "admissions.verification_queue",
        "admissions.rounds",
    },
    "exam": {
        "admissions.written_exams",
        "admissions.interviews",
        "admissions.results",
    },
    "finance": {
        "accounting.fees",
        "accounting.charges",
        "accounting.official_list",
        "accounting.candidate_files",
    },
    "programs": {
        "students.manage",
        "students.academic",
        "admissions.enrolled_files",
        "admissions.student_numbering",
        "classes.manage",
    },
    "learning": {
        "students.manage",
        "students.academic",
        "teaching.attendance",
        "teaching.lessons",
        "teaching.grades",
        "classes.manage",
    },
    "results": {
        "students.academic",
        "teaching.grades",
        "admissions.results",
    },
    "documents": {
        "admissions.applications",
        "admissions.results",
        "accounting.candidate_files",
        "accounting.official_list",
    },
    "history": {
        "admissions.applications",
        "admissions.results",
        "students.manage",
        "admin.audit_logs",
    },
}

_PORTAL_SECTIONS = {
    "overview",
    "admissions",
    "exam",
    "finance",
    "programs",
    "learning",
    "results",
    "documents",
}


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _cols(cur, table: str) -> set[str]:
    try:
        return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def _table_exists(cur, table: str) -> bool:
    row = cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def _add_col(cur, table: str, name: str, spec: str) -> None:
    if _table_exists(cur, table) and name not in _cols(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")


def _norm_cccd(value: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", (value or "")).upper()


def _norm_email(value: str | None) -> str:
    return (value or "").strip().lower()


def _norm_phone(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def ensure_person_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS person_profiles ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "profile_code TEXT UNIQUE, "
        "full_name TEXT NOT NULL, "
        "date_of_birth TEXT, "
        "email TEXT, "
        "phone TEXT, "
        "identity_number TEXT, "
        "gender TEXT, "
        "portal_user_id INTEGER, "
        "created_at TEXT, "
        "updated_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS program_enrollments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "person_id INTEGER NOT NULL, "
        "application_id INTEGER NOT NULL UNIQUE, "
        "learner_id INTEGER, "
        "program_code TEXT, "
        "program_version_id INTEGER, "
        "cohort TEXT, "
        "learner_code TEXT, "
        "academic_status TEXT NOT NULL DEFAULT 'awaiting_class', "
        "decision_ref TEXT, "
        "created_at TEXT, "
        "created_by TEXT)"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_program_enroll_app "
        "ON program_enrollments(application_id)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS application_status_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "application_id INTEGER NOT NULL, "
        "person_id INTEGER, "
        "from_status TEXT, "
        "to_status TEXT, "
        "action TEXT NOT NULL, "
        "basis TEXT, "
        "actor TEXT, "
        "created_at TEXT NOT NULL)"
    )
    for table, cols in (
        ("applications", [
            ("person_id", "INTEGER"),
            ("examinee_confirmed_at", "TEXT"),
            ("examinee_confirmed_by", "TEXT"),
            ("examinee_confirm_basis", "TEXT"),
        ]),
        ("learners", [("person_id", "INTEGER")]),
        ("class_students", [("person_id", "INTEGER")]),
        ("crm_source_profiles", [("person_id", "INTEGER")]),
        ("admission_rounds", [("exam_fee_before_roster", "INTEGER DEFAULT 1")]),
    ):
        for name, spec in cols:
            _add_col(cur, table, name, spec)
    if _table_exists(cur, "person_profiles"):
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_person_identity ON person_profiles(identity_number)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_person_email ON person_profiles(email)"
        )
    retire_projection_tables(cur)
    reconcile_profiles(cur)


def retire_projection_tables(cur) -> None:
    """Bảng sao hồ sơ cá nhân. Đổi tên để còn đường quay lui, không dùng làm nguồn."""
    for old, retired in (
        ("candidate_pre_enroll", "_retired_candidate_pre_enroll"),
        ("candidate_enrolled", "_retired_candidate_enrolled"),
    ):
        if _table_exists(cur, old) and not _table_exists(cur, retired):
            cur.execute(f"ALTER TABLE {old} RENAME TO {retired}")


def reconcile_profiles(cur) -> None:
    if not _table_exists(cur, "applications") or not _table_exists(cur, "person_profiles"):
        return
    missing = cur.execute(
        "SELECT COUNT(*) FROM applications WHERE IFNULL(person_id, 0) = 0"
    ).fetchone()
    if missing and int(missing[0] or 0):
        rows = cur.execute(
            "SELECT id, full_name, cccd, email, phone, "
            + ("dob, " if "dob" in _cols(cur, "applications") else "NULL, ")
            + ("portal_user_id " if "portal_user_id" in _cols(cur, "applications") else "NULL ")
            + "FROM applications WHERE IFNULL(person_id, 0) = 0"
        ).fetchall()
        for row in rows:
            attach_person(
                cur,
                int(row[0]),
                full_name=row[1],
                cccd=row[2],
                email=row[3],
                phone=row[4],
                dob=row[5],
                portal_user_id=row[6],
            )
    _backfill_examinee_confirmation(cur)
    _backfill_program_enrollments(cur)
    if _table_exists(cur, "learners") and "stage" in _cols(cur, "learners"):
        cur.execute(
            "UPDATE learners SET stage = 'learner' "
            "WHERE stage = 'student' AND ("
            "class_student_id IS NOT NULL OR IFNULL(enrolled_at, '') != '' "
            "OR application_id IN (SELECT application_id FROM program_enrollments))"
        )
        cur.execute("UPDATE learners SET stage = 'examinee' WHERE stage = 'student'")
    if _table_exists(cur, "crm_source_profiles") and "person_status" in _cols(cur, "crm_source_profiles"):
        cur.execute(
            "UPDATE crm_source_profiles SET person_status = 'learner' "
            "WHERE lower(IFNULL(person_status, '')) IN ('student', 'students', 'sinh viên')"
        )
    _copy_learner_codes(cur)


def _backfill_examinee_confirmation(cur) -> None:
    if "examinee_confirmed_at" not in _cols(cur, "applications"):
        return
    exam_sql = ""
    if _table_exists(cur, "exam_registrations"):
        exam_sql = " OR id IN (SELECT application_id FROM exam_registrations)"
    cur.execute(
        "UPDATE applications SET "
        "examinee_confirmed_at = COALESCE(NULLIF(created_at, ''), ?), "
        "examinee_confirmed_by = 'backfill', "
        "examinee_confirm_basis = ? "
        "WHERE IFNULL(examinee_confirmed_at, '') = '' AND ("
        "status IN ('interview', 'failed', 'passed', 'paid', 'official')"
        f"{exam_sql})",
        (
            _now(),
            "Đối soát: hồ sơ đã ở bước thi hoặc sau thi trước khi tách bước xác nhận.",
        ),
    )


def _academic_status(lifecycle: str | None, has_class: bool) -> str:
    life = (lifecycle or "").strip().lower()
    if life in ("graduated", "completed", "alumni"):
        return "completed"
    if life in ("deferred", "reserved", "bao_luu"):
        return "deferred"
    if life in ("withdrawn",):
        return "withdrawn"
    if has_class:
        return "studying"
    return "awaiting_class"


def _backfill_program_enrollments(cur) -> None:
    if not _table_exists(cur, "program_enrollments"):
        return
    if "person_id" not in _cols(cur, "applications"):
        return
    app_cols = _cols(cur, "applications")
    code_expr = "IFNULL(a.student_code_mba, '')" if "student_code_mba" in app_cols else "''"
    decision_expr = "IFNULL(a.board_decision, '')" if "board_decision" in app_cols else "''"
    rows = cur.execute(
        "SELECT a.id, a.person_id, a.program_code, "
        + code_expr + ", "
        + decision_expr + ", IFNULL(a.status, '') "
        "FROM applications a "
        "WHERE IFNULL(a.person_id, 0) != 0 AND a.status = 'official' "
        "AND NOT EXISTS (SELECT 1 FROM program_enrollments pe WHERE pe.application_id = a.id)"
    ).fetchall()
    for app_id, person_id, program, code, decision, status in rows:
        ensure_program_enrollment(
            cur,
            int(app_id),
            person_id=int(person_id),
            program_code=program or "",
            learner_code=code or "",
            decision_ref=decision or "",
            status=status or "",
            actor="backfill",
        )
    if _table_exists(cur, "class_students"):
        cs_cols = _cols(cur, "class_students")
        cs_code = "IFNULL(cs.student_code, '')" if "student_code" in cs_cols else "''"
        class_rows = cur.execute(
            "SELECT cs.application_id, a.person_id, a.program_code, "
            + cs_code + ", "
            + code_expr + ", "
            + decision_expr + ", IFNULL(a.status, ''), "
            + (
                "IFNULL(cs.lifecycle_status, '') "
                if "lifecycle_status" in cs_cols
                else "'' "
            )
            + "FROM class_students cs JOIN applications a ON a.id = cs.application_id "
            "WHERE IFNULL(a.person_id, 0) != 0 AND cs.application_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM program_enrollments pe WHERE pe.application_id = cs.application_id)"
        ).fetchall()
        for app_id, person_id, program, cs_code, app_code, decision, status, life in class_rows:
            ensure_program_enrollment(
                cur,
                int(app_id),
                person_id=int(person_id),
                program_code=program or "",
                learner_code=(cs_code or app_code or ""),
                decision_ref=decision or "",
                status=status or "",
                lifecycle=life or "",
                has_class=True,
                actor="backfill",
            )


def _copy_learner_codes(cur) -> None:
    """Mã đã cấp trên cột cũ chuyển sang hồ sơ theo học. Không cấp mã mới."""
    if not _table_exists(cur, "program_enrollments"):
        return
    rows = cur.execute(
        "SELECT id, application_id FROM program_enrollments WHERE IFNULL(learner_code, '') = ''"
    ).fetchall()
    app_cols = _cols(cur, "applications") if _table_exists(cur, "applications") else set()
    cs_cols = _cols(cur, "class_students") if _table_exists(cur, "class_students") else set()
    for pe_id, app_id in rows:
        code = ""
        if "student_code" in cs_cols:
            found = cur.execute(
                "SELECT student_code FROM class_students "
                "WHERE application_id = ? AND IFNULL(student_code, '') != '' "
                "ORDER BY id DESC LIMIT 1",
                (app_id,),
            ).fetchone()
            if found:
                code = found[0]
        if not code and "student_code_mba" in app_cols:
            found = cur.execute(
                "SELECT student_code_mba FROM applications "
                "WHERE id = ? AND IFNULL(student_code_mba, '') != ''",
                (app_id,),
            ).fetchone()
            if found:
                code = found[0]
        if not code:
            continue
        cur.execute(
            "UPDATE program_enrollments SET learner_code = ? "
            "WHERE id = ? AND IFNULL(learner_code, '') = ''",
            (code, pe_id),
        )
        if _table_exists(cur, "learners") and "student_code" in _cols(cur, "learners"):
            cur.execute(
                "UPDATE learners SET student_code = ? "
                "WHERE application_id = ? AND IFNULL(student_code, '') = ''",
                (code, app_id),
            )


def attach_person(
    cur,
    application_id: int,
    *,
    full_name: str | None,
    cccd: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    dob: str | None = None,
    portal_user_id: int | None = None,
) -> int:
    """Ghép hồ sơ cá nhân. Chỉ điền chỗ trống, không ghi đè hồ sơ đã có."""
    ensure_person_tables_light(cur)
    identity = _norm_cccd(cccd)
    email_n = _norm_email(email)
    phone_n = _norm_phone(phone)
    name = (full_name or "").strip() or "Chưa có tên"
    found = None
    if identity:
        found = cur.execute(
            "SELECT id FROM person_profiles WHERE identity_number = ? ORDER BY id LIMIT 1",
            (identity,),
        ).fetchone()
    if not found and email_n:
        found = cur.execute(
            "SELECT id FROM person_profiles WHERE lower(IFNULL(email,'')) = ? ORDER BY id LIMIT 1",
            (email_n,),
        ).fetchone()
    if not found and phone_n and name:
        found = cur.execute(
            "SELECT id FROM person_profiles WHERE phone = ? AND lower(full_name) = ? ORDER BY id LIMIT 1",
            (phone_n, name.lower()),
        ).fetchone()
    now = _now()
    if found:
        pid = int(found[0])
        current = cur.execute(
            "SELECT full_name, date_of_birth, email, phone, identity_number, portal_user_id "
            "FROM person_profiles WHERE id = ?",
            (pid,),
        ).fetchone()
        sets, params = [], []
        if current and not (current[0] or "").strip() and name:
            sets.append("full_name = ?")
            params.append(name)
        if current and not (current[1] or "").strip() and (dob or "").strip():
            sets.append("date_of_birth = ?")
            params.append((dob or "").strip())
        if current and not (current[2] or "").strip() and email_n:
            sets.append("email = ?")
            params.append(email_n)
        if current and not (current[3] or "").strip() and phone_n:
            sets.append("phone = ?")
            params.append(phone_n)
        if current and not (current[4] or "").strip() and identity:
            sets.append("identity_number = ?")
            params.append(identity)
        if current and not current[5] and portal_user_id:
            sets.append("portal_user_id = ?")
            params.append(int(portal_user_id))
        if sets:
            sets.append("updated_at = ?")
            params.append(now)
            params.append(pid)
            cur.execute(
                f"UPDATE person_profiles SET {', '.join(sets)} WHERE id = ?",
                params,
            )
    else:
        cur.execute(
            "INSERT INTO person_profiles ("
            "full_name, date_of_birth, email, phone, identity_number, portal_user_id, created_at, updated_at"
            ") VALUES (?,?,?,?,?,?,?,?)",
            (name, (dob or "").strip() or None, email_n or None, phone_n or None, identity or None, portal_user_id, now, now),
        )
        pid = int(cur.lastrowid)
        cur.execute(
            "UPDATE person_profiles SET profile_code = ? WHERE id = ?",
            (f"HS{pid:05d}", pid),
        )
    if "person_id" in _cols(cur, "applications"):
        cur.execute(
            "UPDATE applications SET person_id = ? WHERE id = ? AND IFNULL(person_id, 0) = 0",
            (pid, int(application_id)),
        )
    if _table_exists(cur, "learners") and "person_id" in _cols(cur, "learners"):
        cur.execute(
            "UPDATE learners SET person_id = ? WHERE application_id = ? AND IFNULL(person_id, 0) = 0",
            (pid, int(application_id)),
        )
    if _table_exists(cur, "class_students") and "person_id" in _cols(cur, "class_students"):
        cur.execute(
            "UPDATE class_students SET person_id = ? WHERE application_id = ? AND IFNULL(person_id, 0) = 0",
            (pid, int(application_id)),
        )
    if _table_exists(cur, "crm_source_profiles") and "person_id" in _cols(cur, "crm_source_profiles"):
        cur.execute(
            "UPDATE crm_source_profiles SET person_id = ? WHERE application_id = ? AND IFNULL(person_id, 0) = 0",
            (pid, int(application_id)),
        )
        if identity and "cccd" in _cols(cur, "crm_source_profiles"):
            cur.execute(
                "UPDATE crm_source_profiles SET person_id = ? "
                "WHERE IFNULL(person_id, 0) = 0 AND upper(replace(IFNULL(cccd,''), ' ', '')) = ?",
                (pid, identity),
            )
        if email_n:
            cur.execute(
                "UPDATE crm_source_profiles SET person_id = ? "
                "WHERE IFNULL(person_id, 0) = 0 AND lower(IFNULL(email,'')) = ?",
                (pid, email_n),
            )
    return pid


def ensure_person_tables_light(cur) -> None:
    """Tạo bảng nếu chưa có, không chạy đối soát lặp."""
    if _table_exists(cur, "person_profiles") and _table_exists(cur, "program_enrollments"):
        return
    cur.execute(
        "CREATE TABLE IF NOT EXISTS person_profiles ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "profile_code TEXT UNIQUE, "
        "full_name TEXT NOT NULL, "
        "date_of_birth TEXT, "
        "email TEXT, "
        "phone TEXT, "
        "identity_number TEXT, "
        "gender TEXT, "
        "portal_user_id INTEGER, "
        "created_at TEXT, "
        "updated_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS program_enrollments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "person_id INTEGER NOT NULL, "
        "application_id INTEGER NOT NULL UNIQUE, "
        "learner_id INTEGER, "
        "program_code TEXT, "
        "program_version_id INTEGER, "
        "cohort TEXT, "
        "learner_code TEXT, "
        "academic_status TEXT NOT NULL DEFAULT 'awaiting_class', "
        "decision_ref TEXT, "
        "created_at TEXT, "
        "created_by TEXT)"
    )


def apply_person_edit(cur, application_id: int, data: dict) -> None:
    """Sửa có chủ đích từ màn hồ sơ: cập nhật hồ sơ sống, không mở hồ sơ thứ hai."""
    if "person_id" not in _cols(cur, "applications"):
        return
    row = cur.execute(
        "SELECT person_id FROM applications WHERE id = ?",
        (int(application_id),),
    ).fetchone()
    if not row or not row[0]:
        return
    sets, params = [], []
    if (data.get("full_name") or "").strip():
        sets.append("full_name = ?")
        params.append(data["full_name"].strip())
    if (data.get("email") or "").strip():
        sets.append("email = ?")
        params.append(_norm_email(data["email"]))
    if (data.get("phone") or "").strip():
        sets.append("phone = ?")
        params.append(_norm_phone(data["phone"]))
    if not sets:
        return
    sets.append("updated_at = ?")
    params.append(_now())
    params.append(int(row[0]))
    cur.execute(f"UPDATE person_profiles SET {', '.join(sets)} WHERE id = ?", params)


def confirm_official_examinee(
    conn,
    application_id: int,
    *,
    actor: str,
    basis: str,
) -> dict:
    """Xác nhận tư cách người dự thi. Không tạo hồ sơ cá nhân mới và không mở lệ phí."""
    cur = conn.cursor()
    ensure_person_tables(cur)
    basis_s = (basis or "").strip()
    if len(basis_s) < 3:
        raise ValueError("Cần ghi căn cứ xác nhận người dự thi chính thức.")
    row = cur.execute(
        "SELECT id, status, person_id, full_name, cccd, email, phone, "
        "IFNULL(examinee_confirmed_at, '') "
        "FROM applications WHERE id = ?",
        (int(application_id),),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy hồ sơ ứng viên")
    if (row[1] or "") == "withdrawn":
        raise ValueError("Hồ sơ đã rút — không xác nhận dự thi.")
    already = (row[7] or "").strip()
    person_id = row[2]
    if not person_id:
        person_id = attach_person(
            cur,
            int(application_id),
            full_name=row[3],
            cccd=row[4],
            email=row[5],
            phone=row[6],
        )
    now = _now()
    if not already:
        cur.execute(
            "UPDATE applications SET examinee_confirmed_at = ?, examinee_confirmed_by = ?, "
            "examinee_confirm_basis = ? WHERE id = ?",
            (now, actor, basis_s, int(application_id)),
        )
        cur.execute(
            "INSERT INTO application_status_log ("
            "application_id, person_id, from_status, to_status, action, basis, actor, created_at"
            ") VALUES (?,?,?,?,?,?,?,?)",
            (int(application_id), person_id, row[1], row[1], "confirm_examinee", basis_s, actor, now),
        )
        if _table_exists(cur, "ops_audit_log"):
            cur.execute(
                "INSERT INTO ops_audit_log (created_at, actor, action, entity, entity_id, detail) "
                "VALUES (?,?,?,?,?,?)",
                (now, actor, "examinee.confirm", "applications", str(application_id), basis_s[:500]),
            )
    conn.commit()
    return {
        "ok": True,
        "already": bool(already),
        "application_id": int(application_id),
        "person_id": int(person_id),
        "examinee_confirmed_at": already or now,
        "handoff": "Đã xác nhận người dự thi chính thức trên cùng hồ sơ ứng viên. Chưa mở lệ phí.",
    }


def fee_required_before_roster(cur, round_id: int | None) -> bool:
    """Thứ tự thu phí theo quy chế đợt. Mặc định giữ quy tắc hiện tại của đợt."""
    if not round_id or not _table_exists(cur, "admission_rounds"):
        return True
    if "exam_fee_before_roster" not in _cols(cur, "admission_rounds"):
        return True
    row = cur.execute(
        "SELECT exam_fee_before_roster FROM admission_rounds WHERE id = ?",
        (int(round_id),),
    ).fetchone()
    if not row or row[0] is None:
        return True
    return int(row[0]) != 0


def ensure_program_enrollment(
    cur,
    application_id: int,
    *,
    person_id: int,
    program_code: str = "",
    learner_code: str = "",
    decision_ref: str = "",
    status: str = "",
    lifecycle: str = "",
    has_class: bool = False,
    learner_id: int | None = None,
    actor: str = "",
    enrolled_at: str = "",
) -> int | None:
    """Tạo một hồ sơ theo học cho một quyết định. Gọi lại không tạo thêm dòng."""
    if not person_id:
        return None
    decision = ""
    selection = ""
    if "decision_status" in _cols(cur, "applications"):
        axis = cur.execute(
            "SELECT IFNULL(decision_status,''), IFNULL(selection_status,'') "
            "FROM applications WHERE id = ?",
            (int(application_id),),
        ).fetchone()
        if axis:
            decision, selection = axis[0], axis[1]
    # Hồ sơ theo học chỉ khi quyết định trúng tuyển đã có hiệu lực, không phải nhãn có điều kiện.
    become = decision == "effective" and selection != "conditional"
    if "decision_status" not in _cols(cur, "applications"):
        become = (status or "") == "official" or has_class or bool((enrolled_at or "").strip())
    existing = cur.execute(
        "SELECT id, academic_status, learner_code FROM program_enrollments WHERE application_id = ?",
        (int(application_id),),
    ).fetchone()
    if not become and not existing:
        return None
    target = _academic_status(lifecycle, has_class)
    code = (learner_code or "").strip()
    if existing:
        sets, params = [], []
        if existing[1] == "awaiting_class" and target == "studying":
            sets.append("academic_status = ?")
            params.append("studying")
        elif target == "completed" and existing[1] not in ("withdrawn",):
            sets.append("academic_status = ?")
            params.append("completed")
        elif target == "deferred" and existing[1] == "studying":
            sets.append("academic_status = ?")
            params.append("deferred")
        if code and not (existing[2] or "").strip():
            sets.append("learner_code = ?")
            params.append(code)
        if learner_id:
            sets.append("learner_id = ?")
            params.append(int(learner_id))
        if sets:
            params.append(int(existing[0]))
            cur.execute(
                f"UPDATE program_enrollments SET {', '.join(sets)} WHERE id = ?",
                params,
            )
        return int(existing[0])
    if not become:
        return None
    now = _now()
    cur.execute(
        "INSERT INTO program_enrollments ("
        "person_id, application_id, learner_id, program_code, learner_code, "
        "academic_status, decision_ref, created_at, created_by"
        ") VALUES (?,?,?,?,?,?,?,?,?)",
        (
            int(person_id),
            int(application_id),
            int(learner_id) if learner_id else None,
            (program_code or "").strip().upper(),
            code or None,
            target,
            (decision_ref or "").strip() or None,
            now,
            actor or None,
        ),
    )
    eid = int(cur.lastrowid)
    if _table_exists(cur, "ops_audit_log"):
        cur.execute(
            "INSERT INTO ops_audit_log (created_at, actor, action, entity, entity_id, detail) "
            "VALUES (?,?,?,?,?,?)",
            (
                now,
                actor or "",
                "learner.promote",
                "program_enrollments",
                str(eid),
                f"app={application_id} program={program_code} status={target}",
            ),
        )
    if _table_exists(cur, "application_status_log"):
        cur.execute(
            "INSERT INTO application_status_log ("
            "application_id, person_id, from_status, to_status, action, basis, actor, created_at"
            ") VALUES (?,?,?,?,?,?,?,?)",
            (
                int(application_id),
                int(person_id),
                status or "",
                "learner",
                "promote_learner",
                "Quyết định trúng tuyển có hiệu lực — mở hồ sơ theo học, không tạo người mới.",
                actor or "",
                now,
            ),
        )
    return eid


def _person_application_ids(cur, person_id: int) -> list[int]:
    if not _table_exists(cur, "applications"):
        return []
    return [
        int(r[0])
        for r in cur.execute(
            "SELECT id FROM applications WHERE person_id = ?",
            (int(person_id),),
        ).fetchall()
    ]


def _in_scope(cur, person_id: int, scopes: list[str] | None) -> bool:
    if not scopes or "*" in scopes:
        return True
    ids = _person_application_ids(cur, person_id)
    if not ids:
        return False
    ph = ",".join("?" * len(ids))
    row = cur.execute(
        f"SELECT 1 FROM applications WHERE id IN ({ph}) AND program_code IN ({','.join('?' * len(scopes))}) LIMIT 1",
        [*ids, *list(scopes)],
    ).fetchone()
    return bool(row)


def allowed_sections(actor: dict) -> list[str]:
    if actor.get("is_admin"):
        return list(SECTION_TITLES)
    codes = set(actor.get("permission_codes") or [])
    depts = set(actor.get("dept_codes") or [])
    staff = codes - {"student.profile", "student.lessons", "student.library", "student.practice"}
    if not staff and ("hoc_vien" in depts or "student.profile" in codes):
        return [key for key in SECTION_TITLES if key in _PORTAL_SECTIONS]
    allowed = ["overview"]
    for key, need in _SECTION_PERMS.items():
        if codes.intersection(need):
            allowed.append(key)
    return allowed


def _owns_person(cur, person_id: int, actor: dict) -> bool:
    row = cur.execute(
        "SELECT portal_user_id, email FROM person_profiles WHERE id = ?",
        (int(person_id),),
    ).fetchone()
    if not row:
        return False
    if row[0] and int(row[0]) == int(actor.get("user_id") or 0):
        return True
    email = _norm_email(actor.get("email"))
    return bool(email and _norm_email(row[1]) == email)


def build_dossier(conn, person_id: int, actor: dict) -> dict:
    cur = conn.cursor()
    ensure_person_tables(cur)
    actor = dict(actor)
    if not actor.get("email") and actor.get("user_id") and _table_exists(cur, "user"):
        urow = cur.execute(
            "SELECT email FROM user WHERE id = ?",
            (int(actor["user_id"]),),
        ).fetchone()
        if urow:
            actor["email"] = urow[0] or ""
    person = cur.execute(
        "SELECT id, profile_code, full_name, date_of_birth, email, phone, identity_number, "
        "gender, portal_user_id FROM person_profiles WHERE id = ?",
        (int(person_id),),
    ).fetchone()
    if not person:
        raise ValueError("Không tìm thấy hồ sơ cá nhân")
    depts = set(actor.get("dept_codes") or [])
    codes = set(actor.get("permission_codes") or [])
    portal = (not actor.get("is_admin")) and ("hoc_vien" in depts) and not (
        codes - {"student.profile", "student.lessons", "student.library", "student.practice"}
    )
    if portal and not _owns_person(cur, int(person_id), actor):
        raise ValueError("Chỉ xem hồ sơ của bản thân.")
    if not portal and not _in_scope(cur, int(person_id), actor.get("program_scopes")):
        raise ValueError("Hồ sơ ngoài phạm vi chương trình được giao.")
    sections = allowed_sections(actor)
    app_ids = _person_application_ids(cur, int(person_id))
    journey = _mba_customer_journey(actor)
    payload = {
        "person": {
            "id": person[0],
            "profile_code": person[1] or "",
            "full_name": person[2] or "",
            "date_of_birth": person[3] or "",
            "email": person[4] or "",
            "phone": person[5] or "",
            "identity_number": person[6] or "" if _can_see_identity(actor) else "",
            "gender": person[7] or "",
        },
        "sections": [],
        "journey": journey,
    }
    if journey:
        payload["sections"] = _mba_journey_sections(cur, int(person_id), app_ids, payload["person"])
        return payload
    builders = {
        "overview": _section_overview,
        "care": _section_care,
        "admissions": _section_admissions,
        "exam": _section_exam,
        "finance": _section_finance,
        "programs": _section_programs,
        "learning": _section_learning,
        "results": _section_results,
        "documents": _section_documents,
        "history": _section_history,
    }
    for key in sections:
        fn = builders.get(key)
        if not fn:
            continue
        block = fn(cur, int(person_id), app_ids)
        block["id"] = key
        block["title"] = SECTION_TITLES[key]
        payload["sections"].append(block)
    return payload


def dossier_for_application(conn, application_id: int, actor: dict) -> dict:
    cur = conn.cursor()
    ensure_person_tables(cur)
    row = cur.execute(
        "SELECT person_id, full_name, cccd, email, phone FROM applications WHERE id = ?",
        (int(application_id),),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy hồ sơ ứng viên")
    person_id = row[0]
    if not person_id:
        person_id = attach_person(
            cur, int(application_id), full_name=row[1], cccd=row[2], email=row[3], phone=row[4]
        )
        conn.commit()
    return build_dossier(conn, int(person_id), actor)


def _empty(note: str) -> dict:
    return {"columns": [], "rows": [], "note": note}


def _section_overview(cur, person_id: int, app_ids: list[int]) -> dict:
    programs = []
    if app_ids and _table_exists(cur, "program_enrollments"):
        ph = ",".join("?" * len(app_ids))
        programs = [
            f"{r[0]} · {ACADEMIC_LABELS.get(r[1] or '', r[1] or '')}"
            for r in cur.execute(
                f"SELECT program_code, academic_status FROM program_enrollments WHERE application_id IN ({ph})",
                app_ids,
            ).fetchall()
        ]
    stage = "Ứng viên"
    if programs:
        stage = "Học viên"
    elif app_ids:
        ph = ",".join("?" * len(app_ids))
        hit = cur.execute(
            f"SELECT 1 FROM applications WHERE id IN ({ph}) AND IFNULL(examinee_confirmed_at,'') != '' LIMIT 1",
            app_ids,
        ).fetchone()
        if hit:
            stage = "Người dự thi chính thức"
    return {
        "columns": ["Mục", "Nội dung"],
        "rows": [
            ["Giai đoạn hiện tại", stage],
            ["Số hồ sơ tuyển sinh", str(len(app_ids))],
            ["Chương trình đã là học viên", "; ".join(programs) or "Chưa có"],
        ],
        "note": "Cùng một mã hồ sơ cá nhân cho mọi giai đoạn. Mã học viên nằm trên từng chương trình.",
    }


def _can_see_identity(actor: dict) -> bool:
    if actor.get("is_admin"):
        return True
    codes = set(actor.get("permission_codes") or [])
    return bool(codes & {
        "admissions.applications",
        "admissions.results",
        "admissions.pre_enroll",
        "admissions.enrolled_files",
        "admissions.round_docs",
        "admissions.round_docs.view",
        "accounting.candidate_files",
        "students.manage",
        "students.academic",
    })


def _section_care(cur, person_id: int, app_ids: list[int]) -> dict:
    if not _table_exists(cur, "crm_source_profiles"):
        return _empty("Chưa có dữ liệu chăm sóc.")
    rows = cur.execute(
        "SELECT IFNULL(program_interest,''), IFNULL(care_status,''), IFNULL(pic,''), "
        "IFNULL(source,''), IFNULL(interest_level,'') "
        "FROM crm_source_profiles WHERE person_id = ? ORDER BY id DESC LIMIT 30",
        (person_id,),
    ).fetchall()
    interest_rows = []
    if _table_exists(cur, "candidate_interests"):
        interest_rows = [
            [r[0] or "", r[1] or "", r[2] or "", r[3] or "", ""]
            for r in cur.execute(
                "SELECT program_code, care_status, owner, 'Marcom' "
                "FROM candidate_interests WHERE person_id = ? ORDER BY id DESC LIMIT 20",
                (person_id,),
            ).fetchall()
        ]
    touch_note = ""
    if _table_exists(cur, "source_touchpoints"):
        n = cur.execute(
            "SELECT COUNT(*) FROM source_touchpoints WHERE person_id = ?",
            (person_id,),
        ).fetchone()
        if n and int(n[0] or 0):
            touch_note = f"Có {int(n[0])} lần ghi nhận nguồn. Nguồn không bị ghi đè."
    merged = [list(r) for r in rows] + interest_rows
    return {
        "columns": ["Chương trình quan tâm", "Trạng thái chăm sóc", "Phụ trách", "Nguồn", "Mức quan tâm"],
        "rows": merged,
        "note": touch_note or ("" if merged else "Chưa có nhu cầu tư vấn gắn với hồ sơ này."),
    }


def _section_admissions(cur, person_id: int, app_ids: list[int]) -> dict:
    if not app_ids:
        return _empty("Chưa có đăng ký tuyển sinh.")
    ph = ",".join("?" * len(app_ids))
    rows = cur.execute(
        f"SELECT id, IFNULL(program_code,''), IFNULL(status,''), "
        f"CASE WHEN IFNULL(examinee_confirmed_at,'') = '' THEN 'Chưa xác nhận' ELSE 'Đã xác nhận' END, "
        f"IFNULL(cfvg_app_no,''), IFNULL(board_decision,'') "
        f"FROM applications WHERE id IN ({ph}) ORDER BY id DESC",
        app_ids,
    ).fetchall()
    return {
        "columns": ["Hồ sơ", "CT", "Trạng thái", "Dự thi chính thức", "Mã UV", "Quyết định"],
        "rows": [list(r) for r in rows],
        "note": "Đăng ký nháp không làm người đó thành người dự thi chính thức.",
    }


def _section_exam(cur, person_id: int, app_ids: list[int]) -> dict:
    if not app_ids or not _table_exists(cur, "exam_registrations"):
        return _empty("Chưa có đăng ký thi.")
    ph = ",".join("?" * len(app_ids))
    rows = cur.execute(
        f"SELECT application_id, IFNULL(program_code,''), IFNULL(exam_board,''), "
        f"IFNULL(fee_status,''), IFNULL(roster_status,''), IFNULL(written_score,'') "
        f"FROM exam_registrations WHERE application_id IN ({ph}) ORDER BY id",
        app_ids,
    ).fetchall()
    return {
        "columns": ["Hồ sơ", "CT", "Hội đồng", "Lệ phí", "Danh sách", "Điểm viết"],
        "rows": [list(r) for r in rows],
        "note": "" if rows else "Chưa đăng ký nội dung thi.",
    }


def _section_finance(cur, person_id: int, app_ids: list[int]) -> dict:
    if not app_ids or not _table_exists(cur, "student_charges"):
        return _empty("Chưa có khoản phải thu.")
    ph = ",".join("?" * len(app_ids))
    rows = cur.execute(
        f"SELECT IFNULL(title,''), IFNULL(fee_type,''), IFNULL(amount_due,0), "
        f"IFNULL(amount_paid,0), IFNULL(status,''), application_id "
        f"FROM student_charges WHERE application_id IN ({ph}) ORDER BY id DESC LIMIT 40",
        app_ids,
    ).fetchall()
    return {
        "columns": ["Khoản", "Loại", "Phải thu", "Đã thu", "TT", "Hồ sơ"],
        "rows": [list(r) for r in rows],
        "note": "Khoản phải thu và giao dịch thu là hai việc khác nhau.",
    }


def _section_programs(cur, person_id: int, app_ids: list[int]) -> dict:
    if not _table_exists(cur, "program_enrollments"):
        return _empty("Chưa có hồ sơ theo học.")
    rows = cur.execute(
        "SELECT IFNULL(program_code,''), IFNULL(learner_code,''), academic_status, "
        "application_id, IFNULL(decision_ref,'') "
        "FROM program_enrollments WHERE person_id = ? ORDER BY id",
        (person_id,),
    ).fetchall()
    out = []
    for program, code, status, app_id, decision in rows:
        out.append([
            program,
            code or "—",
            ACADEMIC_LABELS.get(status or "", status or ""),
            app_id,
            decision,
        ])
    return {
        "columns": ["Chương trình", "Mã học viên", "TT theo học", "Hồ sơ TS", "Quyết định"],
        "rows": out,
        "note": "" if out else "Chưa có quyết định trúng tuyển có hiệu lực.",
    }


def _section_learning(cur, person_id: int, app_ids: list[int]) -> dict:
    if not app_ids or not _table_exists(cur, "class_students"):
        return _empty("Chưa xếp lớp.")
    ph = ",".join("?" * len(app_ids))
    life = "IFNULL(cs.lifecycle_status,'')" if "lifecycle_status" in _cols(cur, "class_students") else "''"
    rows = cur.execute(
        f"SELECT IFNULL(cg.program_code,''), IFNULL(cg.name,''), IFNULL(cs.student_code,''), {life} "
        f"FROM class_students cs JOIN class_groups cg ON cg.id = cs.class_id "
        f"WHERE cs.application_id IN ({ph}) ORDER BY cs.id DESC",
        app_ids,
    ).fetchall()
    return {
        "columns": ["CT", "Lớp", "Mã học viên", "Biến động"],
        "rows": [list(r) for r in rows],
        "note": "" if rows else "Chưa xếp lớp.",
    }


def _section_results(cur, person_id: int, app_ids: list[int]) -> dict:
    rows: list[list] = []
    app_cols = _cols(cur, "applications") if app_ids else set()
    if app_ids and {"written_score", "program_code"}.issubset(app_cols):
        ph = ",".join("?" * len(app_ids))
        interview = "IFNULL(interview_score,'')" if "interview_score" in app_cols else "''"
        final = "IFNULL(final_result,'')" if "final_result" in app_cols else "''"
        for r in cur.execute(
            f"SELECT id, IFNULL(program_code,''), IFNULL(written_score,''), {interview}, {final} "
            f"FROM applications WHERE id IN ({ph})",
            app_ids,
        ):
            rows.append(["Tuyển sinh", r[0], r[1], f"Viết {r[2] or '—'} · PV {r[3] or '—'}", r[4] or ""])
    if app_ids and _table_exists(cur, "course_grades") and _table_exists(cur, "class_students"):
        ph = ",".join("?" * len(app_ids))
        for r in cur.execute(
            f"SELECT cg.program_code, COUNT(g.id) "
            f"FROM course_grades g JOIN class_students cs ON cs.id = g.student_id "
            f"JOIN class_groups cg ON cg.id = cs.class_id "
            f"WHERE cs.application_id IN ({ph}) GROUP BY cg.program_code",
            app_ids,
        ):
            rows.append(["Môn học", "", r[0] or "", f"{r[1]} điểm thành phần/môn", ""])
    return {
        "columns": ["Nhóm", "Hồ sơ", "CT", "Kết quả", "Quyết định"],
        "rows": rows,
        "note": "" if rows else "Chưa có kết quả.",
    }


def _section_documents(cur, person_id: int, app_ids: list[int]) -> dict:
    if not app_ids or not _table_exists(cur, "application_docs"):
        return _empty("Chưa có giấy tờ.")
    ph = ",".join("?" * len(app_ids))
    rows = cur.execute(
        f"SELECT application_id, IFNULL(doc_type,''), IFNULL(title,''), IFNULL(uploaded_at,'') "
        f"FROM application_docs WHERE application_id IN ({ph}) ORDER BY id DESC LIMIT 40",
        app_ids,
    ).fetchall()
    return {
        "columns": ["Hồ sơ", "Loại", "Tiêu đề", "Lúc tải"],
        "rows": [list(r) for r in rows],
        "note": "" if rows else "Chưa có giấy tờ trên hồ sơ tuyển sinh.",
    }


def _section_history(cur, person_id: int, app_ids: list[int]) -> dict:
    if not _table_exists(cur, "application_status_log"):
        return _empty("Chưa có nhật ký chuyển giai đoạn.")
    rows = cur.execute(
        "SELECT created_at, IFNULL(action,''), IFNULL(from_status,''), IFNULL(to_status,''), "
        "IFNULL(actor,''), IFNULL(basis,'') "
        "FROM application_status_log WHERE person_id = ? ORDER BY id DESC LIMIT 40",
        (person_id,),
    ).fetchall()
    return {
        "columns": ["Lúc", "Việc", "Từ", "Đến", "Người", "Căn cứ"],
        "rows": [list(r) for r in rows],
        "note": "" if rows else "Chưa ghi nhận chuyển giai đoạn trên hồ sơ này.",
    }


def _mba_customer_journey(actor: dict) -> bool:
    """Điều phối MBA theo một tên khách hàng, không theo phase Tư vấn / Thi / Xét duyệt."""
    if actor.get("is_admin"):
        return False
    return set(actor.get("dept_codes") or []) == {"mba"}


def _sql_col(cols: set[str], name: str) -> str:
    return f"IFNULL({name},'')" if name in cols else "''"


def _mba_journey_sections(cur, person_id: int, app_ids: list[int], person: dict) -> list[dict]:
    specs = [
        ("customer", "Dữ liệu khách hàng", _journey_customer(cur, person_id, app_ids, person)),
        ("application", "Quản lý hồ sơ ứng tuyển", _journey_application(cur, app_ids)),
        ("enrollment", "Quản lý nhập học", _journey_enrollment(cur, person_id, app_ids)),
        ("events", "Sự kiện tuyển sinh", _journey_events(cur, person_id, person)),
        ("benefits", "Chương trình ưu đãi", _journey_benefits(cur, person_id, person)),
        ("report", "Báo cáo", _journey_report(cur, person_id, app_ids, person)),
    ]
    out = []
    for key, title, block in specs:
        block["id"] = key
        block["title"] = title
        out.append(block)
    return out


def _journey_customer(cur, person_id: int, app_ids: list[int], person: dict) -> dict:
    rows = [[
        person.get("full_name") or "",
        person.get("email") or "",
        person.get("phone") or "",
        person.get("profile_code") or "",
        "Hồ sơ cá nhân",
    ]]
    if not _table_exists(cur, "crm_source_profiles"):
        return {
            "columns": ["Họ tên", "Email", "Điện thoại", "Mã", "Nguồn"],
            "rows": rows,
            "note": "Chưa có bảng dữ liệu khách hàng.",
        }
    cols = _cols(cur, "crm_source_profiles")
    where: list[str] = []
    params: list[Any] = []
    if "person_id" in cols:
        where.append("person_id = ?")
        params.append(person_id)
    if app_ids and "application_id" in cols:
        where.append(f"application_id IN ({','.join('?' * len(app_ids))})")
        params.extend(app_ids)
    name = (person.get("full_name") or "").strip()
    email = (person.get("email") or "").strip().lower()
    if name and "full_name" in cols:
        where.append("lower(full_name) = lower(?)")
        params.append(name)
    if email and "email" in cols:
        where.append("lower(IFNULL(email,'')) = ?")
        params.append(email)
    if where:
        picked = cur.execute(
            "SELECT "
            + ", ".join([
                _sql_col(cols, "enquiry_date"),
                _sql_col(cols, "pic"),
                _sql_col(cols, "full_name"),
                _sql_col(cols, "care_status"),
                _sql_col(cols, "program_interest"),
                _sql_col(cols, "source"),
            ])
            + f" FROM crm_source_profiles WHERE {' OR '.join(where)} ORDER BY id DESC LIMIT 30",
            params,
        ).fetchall()
        for r in picked:
            rows.append([r[2], r[4], r[1], r[0], f"{r[5]} · {r[3]}".strip(" ·")])
    return {
        "columns": ["Họ tên", "Email / CT", "Điện thoại / phụ trách", "Mã / ngày", "Nguồn"],
        "rows": rows,
        "note": "Cùng một tên từ lần tiếp nhận đầu. Không tách thành phase chăm sóc riêng.",
    }


def _journey_application(cur, app_ids: list[int]) -> dict:
    if not app_ids:
        return _empty("Chưa có hồ sơ ứng tuyển.")
    cols = _cols(cur, "applications")
    ph = ",".join("?" * len(app_ids))
    rows = cur.execute(
        "SELECT id, "
        + ", ".join([
            _sql_col(cols, "program_code"),
            _sql_col(cols, "dossier_status"),
            _sql_col(cols, "sitting_status"),
            _sql_col(cols, "selection_status"),
            _sql_col(cols, "decision_status"),
            _sql_col(cols, "response_status"),
            _sql_col(cols, "written_score"),
            _sql_col(cols, "interview_score"),
            _sql_col(cols, "status"),
        ])
        + f" FROM applications WHERE id IN ({ph}) ORDER BY id DESC",
        app_ids,
    ).fetchall()
    return {
        "columns": [
            "Hồ sơ", "CT", "Hồ sơ", "Dự thi", "Xét", "Quyết định", "Phản hồi",
            "Điểm viết", "Phỏng vấn", "Trạng thái",
        ],
        "rows": [list(r) for r in rows],
        "note": "Thi viết, phỏng vấn và xét duyệt nằm trên cùng hồ sơ ứng tuyển, không phải danh sách riêng.",
    }


def _journey_enrollment(cur, person_id: int, app_ids: list[int]) -> dict:
    rows: list[list] = []
    if _table_exists(cur, "program_enrollments"):
        for program, code, status, app_id, decision in cur.execute(
            "SELECT IFNULL(program_code,''), IFNULL(learner_code,''), academic_status, "
            "application_id, IFNULL(decision_ref,'') "
            "FROM program_enrollments WHERE person_id = ? ORDER BY id",
            (person_id,),
        ):
            rows.append([
                program,
                code or "—",
                ACADEMIC_LABELS.get(status or "", status or ""),
                app_id or "",
                decision,
                "Đã có hồ sơ theo học",
            ])
    if app_ids and _table_exists(cur, "class_students"):
        ph = ",".join("?" * len(app_ids))
        for r in cur.execute(
            f"SELECT IFNULL(cg.name,''), IFNULL(cs.student_code,''), IFNULL(a.status,'') "
            f"FROM class_students cs JOIN class_groups cg ON cg.id = cs.class_id "
            f"LEFT JOIN applications a ON a.id = cs.application_id "
            f"WHERE cs.application_id IN ({ph})",
            app_ids,
        ):
            rows.append(["Lớp", r[1] or "—", r[0] or "", "", r[2] or "", "Đã xếp lớp"])
    if app_ids and _table_exists(cur, "student_charges"):
        ph = ",".join("?" * len(app_ids))
        for r in cur.execute(
            f"SELECT IFNULL(title,''), IFNULL(amount_due,0), IFNULL(amount_paid,0), IFNULL(status,'') "
            f"FROM student_charges WHERE application_id IN ({ph}) ORDER BY id DESC LIMIT 12",
            app_ids,
        ):
            rows.append(["Phí", r[0], f"Phải thu {r[1]}", f"Đã thu {r[2]}", r[3], "Chỉ xem"])
    return {
        "columns": ["Nhóm", "Mã / khoản", "Trạng thái", "Hồ sơ", "Căn cứ", "Ghi chú"],
        "rows": rows,
        "note": "Theo dõi đến khi nhập học xong. Xác nhận thu và chuyển chính thức thuộc Kế toán.",
    }


def _journey_events(cur, person_id: int, person: dict) -> dict:
    if not _table_exists(cur, "marcom_event_registrants"):
        return _empty("Chưa có sự kiện tuyển sinh.")
    rcols = _cols(cur, "marcom_event_registrants")
    where: list[str] = []
    params: list[Any] = []
    if "person_id" in rcols:
        where.append("r.person_id = ?")
        params.append(person_id)
    name = (person.get("full_name") or "").strip()
    email = (person.get("email") or "").strip().lower()
    if name and "full_name" in rcols:
        where.append("lower(r.full_name) = lower(?)")
        params.append(name)
    if email and "email" in rcols:
        where.append("lower(IFNULL(r.email,'')) = ?")
        params.append(email)
    if not where:
        return _empty("Chưa gắn khách hàng với sự kiện.")
    title = "IFNULL(e.title,'')" if _table_exists(cur, "marcom_events") else "''"
    when = "IFNULL(e.event_date,'')" if _table_exists(cur, "marcom_events") else "''"
    join = "LEFT JOIN marcom_events e ON e.id = r.event_id" if _table_exists(cur, "marcom_events") else ""
    attend = f"IFNULL(r.attendance_status,'')" if "attendance_status" in rcols else "''"
    interest = f"IFNULL(r.program_interest,'')" if "program_interest" in rcols else "''"
    rows = cur.execute(
        f"SELECT {title}, {when}, {attend}, {interest} "
        f"FROM marcom_event_registrants r {join} WHERE {' OR '.join(where)} "
        "ORDER BY r.id DESC LIMIT 30",
        params,
    ).fetchall()
    return {
        "columns": ["Sự kiện", "Ngày", "Tham dự", "Chương trình"],
        "rows": [list(r) for r in rows],
        "note": "" if rows else "Chưa thấy khách hàng này trong danh sách sự kiện.",
    }


def _journey_benefits(cur, person_id: int, person: dict) -> dict:
    rows: list[list] = []
    name = (person.get("full_name") or "").strip()
    codes: list[str] = []
    if _table_exists(cur, "program_enrollments"):
        codes = [
            r[0] for r in cur.execute(
                "SELECT learner_code FROM program_enrollments "
                "WHERE person_id = ? AND IFNULL(learner_code,'') != ''",
                (person_id,),
            ) if r[0]
        ]
    if _table_exists(cur, "financial_benefits") and (name or codes):
        where = []
        params: list[Any] = []
        if name:
            where.append("lower(full_name) = lower(?)")
            params.append(name)
        if codes:
            where.append(f"student_code IN ({','.join('?' * len(codes))})")
            params.extend(codes)
        for r in cur.execute(
            "SELECT IFNULL(benefit_type,''), IFNULL(program_code,''), IFNULL(amount,0), "
            "IFNULL(status,''), IFNULL(student_code,'') "
            f"FROM financial_benefits WHERE {' OR '.join(where)} ORDER BY id DESC LIMIT 20",
            params,
        ):
            rows.append([r[0], r[1], r[4], r[2], r[3]])
    return {
        "columns": ["Loại", "CT", "Mã HV", "Số tiền", "Trạng thái"],
        "rows": rows,
        "note": "Chỉ xem. Duyệt và chi thuộc Kế toán. Không hiện số tài khoản.",
    }


def _journey_report(cur, person_id: int, app_ids: list[int], person: dict) -> dict:
    overview = _section_overview(cur, person_id, app_ids)
    stage = overview["rows"][0][1] if overview.get("rows") else ""
    latest = ["", "", "", ""]
    if app_ids:
        cols = _cols(cur, "applications")
        ph = ",".join("?" * len(app_ids))
        row = cur.execute(
            "SELECT "
            + ", ".join([
                _sql_col(cols, "program_code"),
                _sql_col(cols, "dossier_status"),
                _sql_col(cols, "selection_status"),
                _sql_col(cols, "decision_status"),
                _sql_col(cols, "status"),
            ])
            + f" FROM applications WHERE id IN ({ph}) ORDER BY id DESC LIMIT 1",
            app_ids,
        ).fetchone()
        if row:
            latest = [row[0], row[1] or row[4], row[2], row[3]]
    enrolled = "Chưa"
    if _table_exists(cur, "program_enrollments"):
        hit = cur.execute(
            "SELECT 1 FROM program_enrollments WHERE person_id = ? LIMIT 1",
            (person_id,),
        ).fetchone()
        if hit:
            enrolled = "Rồi"
    return {
        "columns": ["Khách hàng", "Giai đoạn", "Chương trình", "Hồ sơ", "Xét", "Quyết định", "Đã nhập học"],
        "rows": [[
            person.get("full_name") or "",
            stage,
            latest[0],
            latest[1],
            latest[2],
            latest[3],
            enrolled,
        ]],
        "note": "Một dòng trạng thái của đúng khách hàng này.",
    }
