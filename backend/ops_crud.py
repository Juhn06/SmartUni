"""
CRUD + export helpers for ops modules (replacing alert placeholders).
"""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any


def ensure_extra_ops_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS study_groups ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "class_id INTEGER NOT NULL, "
        "course_id INTEGER, "
        "name TEXT NOT NULL, "
        "member_names TEXT, "
        "status TEXT DEFAULT 'active', "
        "FOREIGN KEY (class_id) REFERENCES class_groups(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS exam_schedules ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "class_id INTEGER NOT NULL, "
        "course_id INTEGER, "
        "title TEXT NOT NULL, "
        "exam_date TEXT, "
        "exam_type TEXT DEFAULT 'final', "
        "room TEXT, "
        "status TEXT DEFAULT 'planned', "
        "notes TEXT, "
        "FOREIGN KEY (class_id) REFERENCES class_groups(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS course_evaluations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "class_id INTEGER NOT NULL, "
        "course_id INTEGER, "
        "title TEXT NOT NULL, "
        "response_pct REAL DEFAULT 0, "
        "status TEXT DEFAULT 'draft', "
        "summary TEXT, "
        "FOREIGN KEY (class_id) REFERENCES class_groups(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS assignment_submissions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "class_id INTEGER NOT NULL, "
        "course_code TEXT, "
        "student_name TEXT NOT NULL, "
        "title TEXT, "
        "score REAL, "
        "submitted_at TEXT, "
        "status TEXT DEFAULT 'submitted')"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS email_outbox ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "kind TEXT, "
        "recipient TEXT, "
        "subject TEXT, "
        "body TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "status TEXT DEFAULT 'queued')"
    )


def create_admission_round(conn, data: dict) -> dict:
    from admission_ops import create_admission_round as _create

    return _create(conn, data)


def enroll_official_into_class(conn, class_id: int, *, program_code: str | None = None) -> dict:
    """Đưa hồ sơ official vào lớp. Cùng một người, không tạo hồ sơ cá nhân mới."""
    from mba_ops import ensure_mba_tables
    from person_profile import ensure_person_tables

    cur = conn.cursor()
    ensure_mba_tables(cur)
    ensure_person_tables(cur)
    meta = cur.execute(
        "SELECT id, program_code, cohort_year, name FROM class_groups WHERE id = ?",
        (class_id,),
    ).fetchone()
    if not meta:
        raise ValueError("Class not found")
    prog = (program_code or meta[1] or "").strip().upper()
    year = meta[2] or date.today().year
    y2 = str(year)[-2:]
    apps = cur.execute(
        "SELECT a.id, a.full_name, a.email, "
        "COALESCE(NULLIF(pe.learner_code,''), NULLIF(a.student_code_mba,''), ''), "
        "a.cccd, a.phone, a.person_id FROM applications a "
        "LEFT JOIN program_enrollments pe ON pe.application_id = a.id "
        "WHERE a.program_code = ? AND a.status = 'official' "
        "AND IFNULL(a.decision_status,'effective') = 'effective' "
        "AND IFNULL(a.selection_status,'') != 'conditional' "
        "AND UPPER(IFNULL(NULLIF(a.admitted_program,''), a.program_code)) = ? "
        "AND NOT EXISTS ("
        "  SELECT 1 FROM class_students cs WHERE cs.application_id = a.id"
        ") ORDER BY a.id",
        (prog, prog),
    ).fetchall()
    enrolled = accounts = notices = 0
    account_errors: list[str] = []
    cs_cols = {r[1] for r in cur.execute("PRAGMA table_info(class_students)").fetchall()}
    for app_id, full_name, email, mba_code, cccd, phone, person_id in apps:
        seq = cur.execute(
            "SELECT COUNT(*) + 1 FROM class_students WHERE class_id = ?", (class_id,)
        ).fetchone()[0]
        student_code = (mba_code or "").strip() or f"{prog}{y2}{seq:03d}"
        today = date.today().isoformat()
        ins_cols = [
            "class_id", "application_id", "full_name", "email",
            "student_code", "lifecycle_status", "enrolled_at",
        ]
        ins_vals = [class_id, app_id, full_name, email or "", student_code, "active", today]
        if "cccd" in cs_cols:
            ins_cols.append("cccd")
            ins_vals.append(cccd or "")
        if "phone" in cs_cols:
            ins_cols.append("phone")
            ins_vals.append(phone or "")
        if "person_id" in cs_cols and person_id:
            ins_cols.append("person_id")
            ins_vals.append(int(person_id))
        cur.execute(
            f"INSERT INTO class_students ({', '.join(ins_cols)}) "
            f"VALUES ({', '.join('?' * len(ins_cols))})",
            ins_vals,
        )
        sid = cur.lastrowid
        enrolled += 1
        try:
            from learner_spine import upsert_learner_for_application

            upsert_learner_for_application(conn, app_id)
        except Exception:
            pass
        try:
            from treasury_ops import (
                ensure_inscription_charge,
                link_charges_to_student,
                open_tuition_plan_after_official,
            )

            ensure_inscription_charge(conn, app_id)
            open_tuition_plan_after_official(conn, app_id)
            link_charges_to_student(conn, app_id, sid)
        except Exception:
            pass
        # Portal account for the student (login from email local-part or student_code)
        try:
            from e2e_pipeline import provision_student_account
            from student_accounts import queue_credentials, temp_password

            login = (student_code or "").strip() or (
                (email or "").split("@")[0] if email else f"hv{sid}"
            )
            account = provision_student_account(
                conn,
                login=login,
                display_name=f"{full_name} — Học viên {prog}",
                email=email or "",
                program_code=prog,
                application_id=app_id,
                class_student_id=sid,
                password=temp_password(),
                force_change=True,
                reset_password=False,
            )
            if account["created"]:
                accounts += 1
                if queue_credentials(
                    conn, email=email or "", full_name=full_name, login=login,
                    password=account["password"], program_code=prog,
                ):
                    notices += 1
        except Exception as e:
            account_errors.append(f"{student_code or full_name}: {e}")
            print(f"[ENROLL] không tạo được tài khoản học viên {student_code or full_name}: {e}")
    conn.commit()
    try:
        from admission_ops import sync_candidate_link_tables

        sync_candidate_link_tables(conn)
    except Exception:
        pass
    return {
        "class_id": class_id,
        "class_name": meta[3],
        "program_code": prog,
        "enrolled": enrolled,
        "accounts_created": accounts,
        "credential_emails_queued": notices,
        "account_errors": account_errors,
        "handoff": "Hồ sơ official vào lớp trên cùng một người. Mã học viên giữ theo chương trình. Có sổ thu và tài khoản học viên (mật khẩu tạm, bắt đổi ở lần đăng nhập đầu, email báo tài khoản đã xếp hàng gửi).",
    }


def convert_all_official(conn, scopes: list[str] | None = None) -> dict:
    """Đưa các hồ sơ official còn lại vào lớp. Không tạo thêm hồ sơ cá nhân."""
    from ops_data import _scopes_sql

    cur = conn.cursor()
    from mba_ops import ensure_mba_tables

    ensure_mba_tables(cur)
    frag, params = _scopes_sql(scopes, "a.program_code")
    apps = cur.execute(
        "SELECT a.id, a.program_code FROM applications a "
        "WHERE a.status = 'official' "
        "AND IFNULL(a.decision_status,'effective') = 'effective' "
        "AND IFNULL(a.selection_status,'') != 'conditional' "
        f"AND {frag} AND NOT EXISTS ("
        "  SELECT 1 FROM class_students cs WHERE cs.application_id = a.id"
        ") ORDER BY a.program_code, a.id",
        params,
    ).fetchall()
    if not apps:
        return {"converted": 0, "classes": [], "handoff": "Không còn hồ sơ official chưa vào lớp"}
    by_prog: dict[str, int] = {}
    details = []
    for _aid, prog in apps:
        prog = (prog or "").strip().upper()
        if not prog:
            continue
        if prog not in by_prog:
            row = cur.execute(
                "SELECT id FROM class_groups WHERE upper(program_code)=? "
                "ORDER BY id DESC LIMIT 1",
                (prog,),
            ).fetchone()
            if row:
                by_prog[prog] = row[0]
            else:
                created = create_class_group(
                    conn,
                    {
                        "name": f"{prog} {date.today().year}",
                        "program_code": prog,
                        "enroll_official": False,
                    },
                )
                by_prog[prog] = created["id"]
    converted = 0
    for prog, cid in by_prog.items():
        result = enroll_official_into_class(conn, cid, program_code=prog)
        n = int(result.get("enrolled") or 0)
        converted += n
        details.append(
            {
                "class_id": cid,
                "class_name": result.get("class_name"),
                "program_code": prog,
                "enrolled": n,
            }
        )
    return {
        "converted": converted,
        "classes": details,
        "handoff": f"Đã xếp {converted} học viên chính thức vào lớp. Trạng thái theo học hết Chờ xếp lớp.",
    }


def create_class_group(conn, data: dict) -> dict:
    cur = conn.cursor()
    name = (data.get("name") or "").strip()
    prog = (data.get("program_code") or "").strip().upper()
    if not name or not prog:
        raise ValueError("Cần tên lớp và mã CT")
    dup = cur.execute(
        "SELECT id FROM class_groups WHERE lower(trim(name)) = lower(trim(?)) "
        "AND upper(program_code) = ?",
        (name, prog),
    ).fetchone()
    if dup:
        raise ValueError("Trùng mã lớp — vui lòng nhập mã/tên lớp mới")
    year = int(data.get("cohort_year") or date.today().year)
    vcode = (data.get("version_code") or "").strip()
    pvid = None
    if vcode:
        row = cur.execute(
            "SELECT id FROM program_versions WHERE version_code = ?", (vcode,)
        ).fetchone()
        pvid = row[0] if row else None
    if not pvid:
        row = cur.execute(
            "SELECT id FROM program_versions WHERE program_code = ? ORDER BY id DESC LIMIT 1",
            (prog,),
        ).fetchone()
        pvid = row[0] if row else None
    from ops_data import ensure_ops_tables

    ensure_ops_tables(cur)
    cohort_no = str(data.get("cohort_no") or "").strip()

    def _year(key):
        raw = data.get(key)
        try:
            return int(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            return None

    year_start = _year("year_start")
    year_end = _year("year_end")
    if pvid:
        ver = cur.execute(
            "SELECT IFNULL(cohort_no,''), year_start, year_end FROM program_versions WHERE id = ?",
            (pvid,),
        ).fetchone()
        if ver:
            cohort_no = cohort_no or (ver[0] or "")
            if year_start is None:
                year_start = ver[1]
            if year_end is None:
                year_end = ver[2]
    cur.execute(
        "INSERT INTO class_groups (program_code, name, program_version_id, cohort_year, status, "
        "cohort_no, year_start, year_end) "
        "VALUES (?, ?, ?, ?, 'active', ?, ?, ?)",
        (prog, name, pvid, year, cohort_no, year_start, year_end),
    )
    class_id = cur.lastrowid
    conn.commit()
    enrolled = 0
    enroll = data.get("enroll_official")
    if enroll is None or enroll in (True, 1, "1", "true", "yes"):
        result = enroll_official_into_class(conn, class_id, program_code=prog)
        enrolled = result.get("enrolled") or 0
    return {
        "id": class_id,
        "name": name,
        "program_code": prog,
        "cohort_year": year,
        "enrolled_official": enrolled,
        "handoff": f"Tạo lớp + enroll {enrolled} HV official" if enrolled else "Tạo lớp (chưa có HV official)",
    }


def list_class_students(conn, class_id: int) -> dict:
    from mba_ops import ensure_mba_tables

    cur = conn.cursor()
    ensure_mba_tables(cur)
    meta = cur.execute(
        "SELECT id, name, program_code FROM class_groups WHERE id = ?", (class_id,)
    ).fetchone()
    if not meta:
        raise ValueError("Class not found")
    students = [
        {
            "id": r[0],
            "full_name": r[1],
            "email": r[2],
            "student_code": r[3],
            "application_id": r[4],
            "lifecycle_status": r[5] or "active",
            "scholarship_type": r[6] or "",
            "partner_enrollment": r[7] or "",
            "reserve_note": r[8] or "",
            "observations": r[9] or "",
        }
        for r in cur.execute(
            "SELECT id, full_name, email, student_code, application_id, "
            "lifecycle_status, scholarship_type, partner_enrollment, reserve_note, observations "
            "FROM class_students WHERE class_id = ? ORDER BY full_name",
            (class_id,),
        ).fetchall()
    ]
    return {
        "class": {"id": meta[0], "name": meta[1], "program_code": meta[2]},
        "students": students,
    }


def create_faculty(conn, data: dict) -> dict:
    from mba_ops import ensure_mba_tables

    cur = conn.cursor()
    ensure_mba_tables(cur)
    name = (data.get("full_name") or "").strip()
    if not name:
        raise ValueError("Cần họ tên")
    role = (data.get("role_type") or "lecturer").strip()
    cur.execute(
        "INSERT INTO faculty "
        "(full_name, role_type, degree, title, organization, specialty, teachable_courses, email, "
        "phone, nationality, passport_no, bank_account, cv_note, "
        "teaching_history_note, contract_status, contract_no, grade_return_date, "
        "cfvg_payment_status, insurance_note) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            name,
            role,
            data.get("degree") or "",
            data.get("title") or "",
            data.get("organization") or "",
            data.get("specialty") or "",
            data.get("teachable_courses") or "",
            data.get("email") or "",
            data.get("phone") or "",
            data.get("nationality") or "",
            data.get("passport_no") or "",
            data.get("bank_account") or "",
            data.get("cv_note") or "",
            data.get("teaching_history_note") or "",
            data.get("contract_status") or "",
            data.get("contract_no") or "",
            data.get("grade_return_date") or "",
            data.get("cfvg_payment_status") or "",
            data.get("insurance_note") or "",
        ),
    )
    conn.commit()
    return {"id": cur.lastrowid, "full_name": name, "role_type": role}


def update_faculty(conn, faculty_id: int, data: dict) -> dict:
    from mba_ops import ensure_mba_tables

    cur = conn.cursor()
    ensure_mba_tables(cur)
    allowed = {
        "full_name", "role_type", "degree", "title", "organization",
        "specialty", "teachable_courses", "email",
        "phone", "nationality", "passport_no", "bank_account", "cv_note",
        "teaching_history_note", "contract_status", "contract_no",
        "grade_return_date", "cfvg_payment_status", "insurance_note",
    }
    fields, params = [], []
    for k, v in data.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            params.append(v)
    if not fields:
        raise ValueError("No fields")
    params.append(faculty_id)
    cur.execute(f"UPDATE faculty SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    row = cur.execute(
        "SELECT id, full_name, role_type, degree, title, organization, specialty, teachable_courses, email, "
        "phone, nationality, passport_no, bank_account, cv_note, "
        "teaching_history_note, contract_status, contract_no, grade_return_date, "
        "cfvg_payment_status, insurance_note "
        "FROM faculty WHERE id = ?",
        (faculty_id,),
    ).fetchone()
    if not row:
        raise ValueError("Not found")
    keys = [
        "id", "full_name", "role_type", "degree", "title", "organization",
        "specialty", "teachable_courses", "email",
        "phone", "nationality", "passport_no", "bank_account", "cv_note",
        "teaching_history_note", "contract_status", "contract_no",
        "grade_return_date", "cfvg_payment_status", "insurance_note",
    ]
    return dict(zip(keys, row))


def create_alumni(conn, data: dict) -> dict:
    cur = conn.cursor()
    from ops_data import ensure_ops_tables

    ensure_ops_tables(cur)
    from admission_ops import normalize_cccd, propagate_row_by_id

    name = (data.get("full_name") or "").strip()
    prog = (data.get("program_code") or "MMS").strip()
    if not name:
        raise ValueError("Cần họ tên")
    keywords = (data.get("activity_keywords") or data.get("keywords") or "").strip()
    cccd = (data.get("cccd") or "").strip()
    if not normalize_cccd(cccd):
        raise ValueError("Cần Căn cước công dân (cccd)")
    cols = {r[1] for r in cur.execute("PRAGMA table_info(alumni_members)").fetchall()}
    if "cccd" in cols:
        hit = cur.execute(
            "SELECT id FROM alumni_members WHERE "
            "REPLACE(REPLACE(REPLACE(UPPER(IFNULL(cccd,'')),' ',''),'-',''),'.','') = ?",
            (normalize_cccd(cccd),),
        ).fetchone()
        if hit:
            rid = int(hit[0])
            allowed = {
                "full_name", "program_code", "cohort", "class_name",
                "email", "phone", "company", "activity_keywords", "cccd",
            }
            payload = {
                k: (data.get(k) if k != "activity_keywords" else keywords)
                for k in allowed
                if k in cols and str(data.get(k) if k != "activity_keywords" else keywords or "").strip() != ""
            }
            payload["full_name"] = name
            payload["program_code"] = prog
            payload["cccd"] = cccd
            sets = ", ".join(f"{k} = ?" for k in payload)
            cur.execute(
                f"UPDATE alumni_members SET {sets} WHERE id = ?",
                [*payload.values(), rid],
            )
            conn.commit()
            propagate_row_by_id(conn, "alumni_members", rid, payload)
            return {"id": rid, "full_name": name, "program_code": prog, "activity_keywords": keywords, "cccd": cccd}
    cur.execute(
        "INSERT INTO alumni_members "
        "(full_name, program_code, cohort, class_name, email, phone, company, activity_keywords, cccd) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            name, prog,
            data.get("cohort") or "",
            data.get("class_name") or "",
            data.get("email") or "",
            data.get("phone") or "",
            data.get("company") or "",
            keywords,
            cccd,
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    try:
        propagate_row_by_id(conn, "alumni_members", new_id, {"cccd": cccd, "full_name": name})
    except Exception:
        pass
    return {
        "id": new_id,
        "full_name": name,
        "program_code": prog,
        "activity_keywords": keywords,
        "cccd": cccd,
    }


def create_alumni_event(conn, data: dict) -> dict:
    cur = conn.cursor()
    from ops_data import ensure_ops_tables

    ensure_ops_tables(cur)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Cần tiêu đề sự kiện")
    cur.execute(
        "INSERT INTO alumni_events (title, event_date, location, program_filter, status, description) "
        "VALUES (?, ?, ?, ?, 'planned', ?)",
        (
            title,
            data.get("event_date") or "",
            data.get("location") or "",
            data.get("program_filter") or "*",
            data.get("description") or "",
        ),
    )
    conn.commit()
    return {"id": cur.lastrowid, "title": title}


def set_alumni_event_invitees(conn, event_id: int, alumni_ids: list[int]) -> dict:
    from datetime import date

    cur = conn.cursor()
    from ops_data import ensure_ops_tables

    ensure_ops_tables(cur)
    if not cur.execute("SELECT id FROM alumni_events WHERE id = ?", (event_id,)).fetchone():
        raise ValueError("Sự kiện không tồn tại")
    today = date.today().isoformat()
    ids = []
    for raw in alumni_ids or []:
        try:
            aid = int(raw)
        except (TypeError, ValueError):
            continue
        if aid and aid not in ids:
            ids.append(aid)
    cur.execute("DELETE FROM alumni_event_invitees WHERE event_id = ?", (event_id,))
    for aid in ids:
        cur.execute(
            "INSERT OR IGNORE INTO alumni_event_invitees "
            "(event_id, alumni_id, invited_at, email_status) VALUES (?, ?, ?, 'pending')",
            (event_id, aid, today),
        )
    conn.commit()
    return {"event_id": event_id, "invitee_count": len(ids), "alumni_ids": ids}


def queue_alumni_event_emails(conn, event_id: int) -> dict:
    cur = conn.cursor()
    from ops_data import ensure_ops_tables

    ensure_ops_tables(cur)
    ev = cur.execute(
        "SELECT id, title, event_date, location FROM alumni_events WHERE id = ?",
        (event_id,),
    ).fetchone()
    if not ev:
        raise ValueError("Sự kiện không tồn tại")
    rows = cur.execute(
        "SELECT i.id, m.full_name, m.email "
        "FROM alumni_event_invitees i "
        "JOIN alumni_members m ON m.id = i.alumni_id "
        "WHERE i.event_id = ?",
        (event_id,),
    ).fetchall()
    queued = 0
    skipped = 0
    for inv_id, name, email in rows:
        if not (email or "").strip():
            skipped += 1
            cur.execute(
                "UPDATE alumni_event_invitees SET email_status = 'no_email' WHERE id = ?",
                (inv_id,),
            )
            continue
        cur.execute(
            "UPDATE alumni_event_invitees SET email_status = 'queued' WHERE id = ?",
            (inv_id,),
        )
        queued += 1
    cur.execute(
        "UPDATE alumni_events SET status = 'inviting' WHERE id = ? AND status = 'planned'",
        (event_id,),
    )
    conn.commit()
    return {
        "event_id": event_id,
        "title": ev[1],
        "queued": queued,
        "skipped_no_email": skipped,
        "message": f"Đã xếp hàng gửi email lời mời tới {queued} alumni"
        + (f" (bỏ qua {skipped} không có email)" if skipped else ""),
    }


def create_study_group(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    name = (data.get("name") or "").strip()
    class_id = int(data.get("class_id") or 0)
    if not name or not class_id:
        raise ValueError("Cần tên nhóm và lớp")
    dup = cur.execute(
        "SELECT id FROM study_groups WHERE class_id = ? AND lower(trim(name)) = lower(trim(?))",
        (class_id, name),
    ).fetchone()
    if dup:
        raise ValueError("Trùng nhóm trên lớp này — không tạo thêm")
    members = (data.get("member_names") or "").strip()
    if members:
        same = cur.execute(
            "SELECT id FROM study_groups WHERE class_id = ? AND lower(trim(IFNULL(member_names,''))) = lower(?)",
            (class_id, members),
        ).fetchone()
        if same:
            raise ValueError("Trùng thành viên nhóm trên lớp này — không tạo thêm")
    cur.execute(
        "INSERT INTO study_groups (class_id, course_id, name, member_names, status) "
        "VALUES (?, ?, ?, ?, 'active')",
        (class_id, data.get("course_id"), name, data.get("member_names") or ""),
    )
    conn.commit()
    return {"id": cur.lastrowid, "name": name, "class_id": class_id}


def list_study_groups(conn, scopes: list[str] | None = None) -> list[dict]:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    rows = cur.execute(
        "SELECT g.id, g.name, g.member_names, g.status, cg.name, cg.program_code, g.class_id "
        f"FROM study_groups g JOIN class_groups cg ON cg.id = g.class_id WHERE {frag} "
        "ORDER BY g.id DESC",
        params,
    ).fetchall()
    return [
        {
            "id": r[0], "name": r[1], "member_names": r[2], "status": r[3],
            "class_name": r[4], "program_code": r[5], "class_id": r[6],
        }
        for r in rows
    ]


def create_exam(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    title = (data.get("title") or "").strip()
    class_id = int(data.get("class_id") or 0)
    if not title or not class_id:
        raise ValueError("Cần tiêu đề và lớp")
    cur.execute(
        "INSERT INTO exam_schedules "
        "(class_id, course_id, title, exam_date, exam_type, room, status, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, 'planned', ?)",
        (
            class_id, data.get("course_id"), title,
            data.get("exam_date") or "", data.get("exam_type") or "final",
            data.get("room") or "", data.get("notes") or "",
        ),
    )
    conn.commit()
    return {"id": cur.lastrowid, "title": title, "class_id": class_id}


def list_exams(conn, scopes: list[str] | None = None) -> list[dict]:
    from mba_ops import attendance_eligibility
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    rows = cur.execute(
        "SELECT e.id, e.title, e.exam_date, e.exam_type, e.room, e.status, "
        "cg.name, cg.program_code, e.class_id, "
        "(SELECT COUNT(*) FROM class_students cs WHERE cs.class_id = e.class_id) "
        f"FROM exam_schedules e JOIN class_groups cg ON cg.id = e.class_id WHERE {frag} "
        "ORDER BY e.exam_date DESC, e.id DESC",
        params,
    ).fetchall()
    # Precompute ineligible students by class (attendance >30%)
    elig_rows = attendance_eligibility(conn, scopes, max_absent_pct=30.0)
    ineligible_by_class: dict[int, int] = {}
    # Map via assignment → class when student-level; for aggregate use program+course
    class_ids = {r[8] for r in rows}
    for cid in class_ids:
        size = cur.execute(
            "SELECT COUNT(*) FROM class_students WHERE class_id = ?", (cid,)
        ).fetchone()[0]
        # Count student-level ineligible linked to this class's courses
        course_codes = {
            x[0]
            for x in cur.execute(
                "SELECT c.code FROM teaching_assignments ta "
                "JOIN courses c ON c.id = ta.course_id WHERE ta.class_id = ?",
                (cid,),
            ).fetchall()
        }
        bad = sum(
            1
            for e in elig_rows
            if not e.get("exam_eligible")
            and e.get("course_code") in course_codes
            and e.get("student_id")
        )
        if bad == 0 and any(
            not e.get("exam_eligible") and e.get("course_code") in course_codes
            for e in elig_rows
        ):
            # aggregate fallback — mark warning without exact count
            bad = -1
        ineligible_by_class[cid] = bad if size else 0

    out = []
    for r in rows:
        cid = r[8]
        bad = ineligible_by_class.get(cid, 0)
        out.append(
            {
                "id": r[0],
                "title": r[1],
                "exam_date": r[2],
                "exam_type": r[3],
                "room": r[4],
                "status": r[5],
                "class_name": r[6],
                "program_code": r[7],
                "class_id": cid,
                "name": r[6],
                "student_count": r[9] or 0,
                "ineligible_count": bad if bad >= 0 else "?",
                "exam_eligibility_note": (
                    "OK"
                    if bad == 0
                    else (f"{bad} HV không đủ ĐK thi (>30% vắng)" if bad > 0 else "Cảnh báo chuyên cần (aggregate)")
                ),
            }
        )
    return out


def create_evaluation(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    title = (data.get("title") or "Đánh giá khóa học").strip()
    class_id = int(data.get("class_id") or 0)
    if not class_id:
        raise ValueError("Cần lớp")
    cur.execute(
        "INSERT INTO course_evaluations (class_id, course_id, title, response_pct, status, summary) "
        "VALUES (?, ?, ?, ?, 'open', ?)",
        (class_id, data.get("course_id"), title, float(data.get("response_pct") or 0), data.get("summary") or ""),
    )
    conn.commit()
    return {"id": cur.lastrowid, "title": title, "class_id": class_id, "status": "open"}


def list_evaluations(conn, scopes: list[str] | None = None) -> list[dict]:
    from mba_ops import ensure_mba_tables
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    ensure_mba_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    rows = cur.execute(
        "SELECT e.id, e.title, e.response_pct, e.status, cg.name, cg.program_code, "
        "e.report_status, e.sent_mgmt_at, e.sent_faculty_at "
        f"FROM course_evaluations e JOIN class_groups cg ON cg.id = e.class_id WHERE {frag} "
        "ORDER BY e.id DESC",
        params,
    ).fetchall()
    out = []
    for r in rows:
        pct = float(r[2] or 0)
        out.append(
            {
                "id": r[0],
                "title": r[1],
                "response_pct": pct,
                "status": r[3],
                "name": r[4],
                "program_code": r[5],
                "report_status": r[6] or "",
                "sent_mgmt_at": r[7] or "",
                "sent_faculty_at": r[8] or "",
                "ready_mgmt": pct >= 60,
                "ready_faculty": pct >= 80,
            }
        )
    return out


def queue_email(conn, *, kind: str, recipient: str, subject: str, body: str = "") -> dict:
    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    cur.execute(
        "INSERT INTO email_outbox (kind, recipient, subject, body, status) "
        "VALUES (?, ?, ?, ?, 'queued')",
        (kind, recipient, subject, body),
    )
    conn.commit()
    return {"id": cur.lastrowid, "status": "queued", "recipient": recipient, "subject": subject}


def notify_passed_applicants(conn, scopes: list[str] | None = None) -> dict:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    frag, params = _scopes_sql(scopes, "a.program_code")
    rows = cur.execute(
        "SELECT a.id, a.full_name, a.email, a.program_code, a.status, "
        "IFNULL(a.final_result,''), IFNULL(a.board_decision,'') "
        "FROM applications a "
        f"WHERE IFNULL(a.email,'') != '' AND {frag}",
        params,
    ).fetchall()
    n_pass = 0
    n_fail = 0
    seen = set()
    for aid, name, email, prog, status, final, board in rows:
        key = (aid, (email or "").lower())
        if key in seen:
            continue
        st = (status or "").lower()
        fr = (final or "").lower()
        bd = (board or "").lower()
        passed = (
            st in ("passed", "paid", "official")
            or fr in ("admitted", "passed", "đỗ", "trúng tuyển")
            or "trúng" in bd
            or "đỗ" in bd
        )
        failed = (
            st in ("failed", "rejected")
            or fr in ("failed", "rejected", "trượt", "không đỗ")
            or "trượt" in bd
        )
        if passed and not failed:
            seen.add(key)
            from mscm_coord import render_mail

            subject, body = render_mail(conn, prog, "pass", name=name or "", program=prog or "")
            queue_email(
                conn,
                kind="admission_result",
                recipient=email,
                subject=subject,
                body=body,
            )
            n_pass += 1
        elif failed:
            seen.add(key)
            from mscm_coord import render_mail

            subject, body = render_mail(conn, prog, "fail", name=name or "", program=prog or "")
            queue_email(
                conn,
                kind="admission_result",
                recipient=email,
                subject=subject,
                body=body,
            )
            n_fail += 1
    return {"sent": n_pass + n_fail, "passed": n_pass, "failed": n_fail}


def notify_missing_docs(conn, scopes: list[str] | None = None) -> dict:
    """Nhắc thí sinh đã đỗ bổ sung giấy tờ (TA / văn bằng) trước khai giảng."""
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    frag, params = _scopes_sql(scopes, "a.program_code")
    rows = cur.execute(
        "SELECT a.id, a.full_name, a.email, a.program_code, "
        "IFNULL(a.degree_verified,''), IFNULL(a.english_verified,''), "
        "IFNULL(a.neu_packet_ready,''), IFNULL(a.status,''), "
        "IFNULL(a.final_result,''), IFNULL(a.board_decision,'') "
        "FROM applications a "
        f"WHERE IFNULL(a.email,'') != '' AND {frag}",
        params,
    ).fetchall()
    n = 0
    for aid, name, email, prog, deg, eng, packet, status, final, board in rows:
        st = (status or "").lower()
        fr = (final or "").lower()
        bd = (board or "").lower()
        admitted = (
            st in ("passed", "paid", "official")
            or fr in ("admitted", "passed", "đỗ", "trúng tuyển")
            or "trúng" in bd
        )
        if not admitted:
            continue
        missing = []
        if (deg or "").lower() not in ("yes", "1", "ok", "verified"):
            missing.append("văn bằng / công nhận bằng")
        if (eng or "").lower() not in ("yes", "1", "ok", "verified"):
            missing.append("chứng chỉ tiếng Anh")
        if (packet or "").lower() not in ("yes", "1", "ok", "ready"):
            missing.append("hồ sơ khảo thí NEU")
        if not missing:
            continue
        queue_email(
            conn,
            kind="missing_docs",
            recipient=email,
            subject=f"[X] Nhắc bổ sung giấy tờ trước khai giảng — {prog}",
            body=(
                f"Kính gửi {name},\n\n"
                f"Vui lòng bổ sung giấy tờ trước khai giảng chương trình {prog}:\n"
                + "\n".join(f"- {m}" for m in missing)
                + "\n\nX"
            ),
        )
        n += 1
    return {"sent": n}


def export_rows_csv(rows: list[dict], fieldnames: list[str] | None = None) -> str:
    if not rows:
        # Still emit header row when fields known
        if fieldnames:
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            return buf.getvalue()
        return ""
    fieldnames = fieldnames or list(rows[0].keys())
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in fieldnames})
    return buf.getvalue()


def export_rows_xlsx(
    rows: list[dict],
    fieldnames: list[str] | None = None,
    *,
    sheet_name: str = "Data",
) -> bytes:
    """Build a real Excel .xlsx workbook (openpyxl) for ops exports."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else []
    wb = Workbook()
    ws = wb.active
    safe = (sheet_name or "Data").strip()[:31] or "Data"
    ws.title = safe
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2563EB")
    for col, h in enumerate(fieldnames, 1):
        cell = ws.cell(1, col, h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for r_i, row in enumerate(rows, 2):
        for c_i, key in enumerate(fieldnames, 1):
            val = row.get(key, "")
            if isinstance(val, (list, dict)):
                val = str(val)
            ws.cell(r_i, c_i, val if val is not None else "")
    # Reasonable column widths
    for col, h in enumerate(fieldnames, 1):
        sample = [str(h)]
        for row in rows[:80]:
            sample.append(str(row.get(h, "") or ""))
        width = min(42, max(10, max((len(s) for s in sample), default=10) + 2))
        ws.column_dimensions[get_column_letter(col)].width = width
    if fieldnames:
        last_col = get_column_letter(len(fieldnames))
        last_row = max(1, len(rows) + 1)
        ws.auto_filter.ref = f"A1:{last_col}{last_row}"
        ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


APPLICATION_IMPORT_HEADERS = [
    "full_name",
    "program_code",
    "cfvg_app_no",
    "campus",
    "gender",
    "dob",
    "email",
    "phone",
    "university",
    "degree_major",
    "study_duration",
    "degree_grade",
    "experience_years",
    "credit_hours",
    "english_cert",
    "company",
    "interview_date",
    "final_result",
    "notes",
]


def build_applications_import_template() -> bytes:
    """XLSX template for candidate import."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Candidates"
    for col, h in enumerate(APPLICATION_IMPORT_HEADERS, 1):
        ws.cell(1, col, h)
    # Sample row
    sample = {
        "full_name": "Nguyen Van A",
        "program_code": "MMS",
        "cfvg_app_no": "CAN-2026-001",
        "campus": "Hanoi",
        "gender": "M",
        "dob": "1995-01-15",
        "email": "a@example.com",
        "phone": "0901234567",
        "university": "NEU",
        "degree_major": "Business",
        "english_cert": "IELTS 6.5",
        "company": "ABC Corp",
    }
    for col, h in enumerate(APPLICATION_IMPORT_HEADERS, 1):
        ws.cell(2, col, sample.get(h, ""))
    ws2 = wb.create_sheet("Huong_dan")
    ws2["A1"] = "Giữ nguyên dòng tiêu đề (row 1). Điền dữ liệu từ row 2."
    ws2["A2"] = "program_code: MBA | MMS | MSCM"
    ws2["A3"] = "cfvg_app_no trùng sẽ cập nhật hồ sơ hiện có."
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def parse_applications_xlsx(file_bytes: bytes) -> list[dict]:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = next(rows_iter)
    except StopIteration:
        wb.close()
        return []
    keys = [str(h or "").strip() for h in header]
    out: list[dict] = []
    for raw in rows_iter:
        if not raw or all(c is None or str(c).strip() == "" for c in raw):
            continue
        item = {}
        for i, key in enumerate(keys):
            if not key:
                continue
            val = raw[i] if i < len(raw) else None
            if val is None:
                item[key] = ""
            else:
                item[key] = str(val).strip() if not isinstance(val, (int, float)) else val
        out.append(item)
    wb.close()
    return out


# Later-stage children that block delete: (sql, label_vi, label_en)
_DELETE_CHILDREN = {
    "admission_rounds": [
        ("SELECT COUNT(*) FROM applications WHERE round_id = ?", "hồ sơ tuyển sinh", "admission applications"),
        ("SELECT COUNT(*) FROM interview_sessions WHERE round_id = ?", "lịch phỏng vấn", "interview sessions"),
        ("SELECT COUNT(*) FROM admission_round_docs WHERE round_id = ?", "tài liệu đợt tuyển sinh", "round documents"),
        (
            "SELECT COUNT(*) FROM enrollment_fees ef "
            "JOIN applications a ON a.id = ef.application_id WHERE a.round_id = ?",
            "phí ghi danh",
            "enrollment fees",
        ),
    ],
    "applications": [
        ("SELECT COUNT(*) FROM enrollment_fees WHERE application_id = ?", "phí ghi danh", "enrollment fees"),
        ("SELECT COUNT(*) FROM student_charges WHERE application_id = ?", "khoản thu / công nợ", "student charges"),
        ("SELECT COUNT(*) FROM interview_slots WHERE application_id = ?", "slot phỏng vấn", "interview slots"),
        ("SELECT COUNT(*) FROM class_students WHERE application_id = ?", "học viên trên lớp", "class enrollments"),
    ],
    "class_groups": [
        ("SELECT COUNT(*) FROM class_students WHERE class_id = ?", "học viên lớp", "class students"),
        ("SELECT COUNT(*) FROM teaching_assignments WHERE class_id = ?", "phân công giảng dạy", "teaching assignments"),
        ("SELECT COUNT(*) FROM study_groups WHERE class_id = ?", "nhóm học tập", "study groups"),
        ("SELECT COUNT(*) FROM exam_schedules WHERE class_id = ?", "lịch thi", "exam schedules"),
        ("SELECT COUNT(*) FROM course_evaluations WHERE class_id = ?", "đánh giá môn", "course evaluations"),
        ("SELECT COUNT(*) FROM thesis_records WHERE class_id = ?", "đề án / CĐTN", "thesis records"),
        ("SELECT COUNT(*) FROM course_grades WHERE class_id = ?", "bảng điểm", "gradebook"),
    ],
    "faculty": [
        (
            "SELECT COUNT(*) FROM teaching_assignments WHERE lecturer_id = ? OR expert_id = ?",
            "phân công giảng dạy",
            "teaching assignments",
        ),
    ],
    "alumni_members": [
        ("SELECT COUNT(*) FROM alumni_event_invitees WHERE alumni_id = ?", "lời mời sự kiện", "event invitations"),
    ],
    "alumni_events": [
        ("SELECT COUNT(*) FROM alumni_event_invitees WHERE event_id = ?", "danh sách mời", "invitees"),
    ],
    "marcom_events": [
        ("SELECT COUNT(*) FROM marcom_event_registrants WHERE event_id = ?", "đăng ký sự kiện", "event registrants"),
    ],
    "crm_source_profiles": [
        ("SELECT COUNT(*) FROM crm_activity_participants WHERE profile_id = ?", "tham gia đợt chăm sóc", "care activity participants"),
        ("SELECT COUNT(*) FROM crm_reminders WHERE profile_id = ?", "nhắc nhở CRM", "CRM reminders"),
    ],
    "crm_activities": [
        ("SELECT COUNT(*) FROM crm_activity_participants WHERE activity_id = ?", "hồ sơ tham gia đợt", "activity participants"),
        ("SELECT COUNT(*) FROM crm_reminders WHERE activity_id = ?", "nhắc nhở đợt", "activity reminders"),
    ],
    "program_versions": [
        ("SELECT COUNT(*) FROM courses WHERE program_version_id = ?", "học phần", "courses"),
        ("SELECT COUNT(*) FROM class_groups WHERE program_version_id = ?", "lớp học", "classes"),
    ],
    "courses": [
        ("SELECT COUNT(*) FROM teaching_assignments WHERE course_id = ?", "phân công giảng dạy", "teaching assignments"),
        ("SELECT COUNT(*) FROM course_sessions WHERE course_id = ?", "buổi học / syllabus", "course sessions"),
        ("SELECT COUNT(*) FROM course_materials WHERE course_id = ?", "tài liệu môn", "course materials"),
    ],
    "teaching_assignments": [
        ("SELECT COUNT(*) FROM attendance_sessions WHERE assignment_id = ?", "điểm danh", "attendance sessions"),
        ("SELECT COUNT(*) FROM class_lessons WHERE assignment_id = ?", "bài giảng lớp–môn", "class lessons"),
        ("SELECT COUNT(*) FROM practice_homeworks WHERE teaching_assignment_id = ?", "bài tập thực hành", "practice homework"),
        ("SELECT COUNT(*) FROM mc_quizzes WHERE teaching_assignment_id = ?", "trắc nghiệm", "MC quizzes"),
    ],
    "interview_sessions": [
        ("SELECT COUNT(*) FROM interview_slots WHERE session_id = ?", "thí sinh đã xếp slot", "interview slots"),
    ],
    "admission_doc_types": [
        ("SELECT COUNT(*) FROM admission_round_docs WHERE doc_type_id = ?", "tài liệu đợt tuyển sinh", "round documents"),
    ],
}

_APP_LATER_STATUSES = {
    "approved_ts",
    "interview",
    "passed",
    "paid",
    "official",
    "deposit_pending",
    "deposit_verified",
    "officially_enrolled",
    "admitted",
}

_ASST_LATER_STATUS = {
    "asst_leave": {"approved", "rejected"},
    "asst_weekly_reports": {"sent", "approved"},
    "asst_procurement": {"purchased", "invoiced", "paid"},
}


def _safe_count(cur, sql: str, params) -> int:
    try:
        cur.execute(sql, params)
        row = cur.fetchone()
        return int((row[0] if row else 0) or 0)
    except Exception:
        return 0


def _blocked_delete_message(hits: list[tuple[int, str, str]]) -> str:
    vi_bits = [f"{n} {vi}" for n, vi, _en in hits]
    en_bits = [f"{n} {_en}" for n, _vi, _en in hits]
    return (
        "Không xóa được vì khâu sau đã có dữ liệu: "
        + ", ".join(vi_bits)
        + ". Hãy xử lý / xóa dữ liệu khâu sau trước."
        + " / Cannot delete — later stage already has data: "
        + ", ".join(en_bits)
        + ". Remove or resolve the later-stage records first."
    )


def assert_can_delete_ops_row(conn, table: str, row_id: int) -> None:
    """Raise ValueError if a later workflow stage already has data."""
    cur = conn.cursor()
    exists = _safe_count(cur, f"SELECT COUNT(*) FROM {table} WHERE id = ?", (row_id,))
    if exists == 0:
        return

    if table == "applications":
        st = None
        try:
            row = cur.execute("SELECT status FROM applications WHERE id = ?", (row_id,)).fetchone()
            st = (row[0] or "").strip() if row else ""
        except Exception:
            st = ""
        if st in _APP_LATER_STATUSES:
            raise ValueError(
                "Không xóa được vì khâu sau đã xử lý hồ sơ (trạng thái: "
                + st
                + "). / Cannot delete — later stage already processed this application (status: "
                + st
                + ")."
            )

    if table == "marcom_leads":
        try:
            row = cur.execute(
                "SELECT application_id, status FROM marcom_leads WHERE id = ?",
                (row_id,),
            ).fetchone()
        except Exception:
            row = None
        if row:
            app_id, st = row[0], (row[1] or "").strip()
            if app_id:
                raise ValueError(
                    "Không xóa được vì khâu sau đã có hồ sơ tuyển sinh #"
                    + str(app_id)
                    + ". / Cannot delete — later stage already has application #"
                    + str(app_id)
                    + "."
                )
            if st in ("handed_ts", "converted"):
                raise ValueError(
                    "Không xóa được vì lead đã bàn giao Tuyển sinh. "
                    "/ Cannot delete — lead already handed to Admissions."
                )

    if table == "crm_source_profiles":
        try:
            row = cur.execute(
                "SELECT application_id, care_status FROM crm_source_profiles WHERE id = ?",
                (row_id,),
            ).fetchone()
        except Exception:
            row = None
        if row:
            app_id, st = row[0], (row[1] or "").strip()
            if app_id:
                raise ValueError(
                    "Không xóa được vì đã tạo hồ sơ tuyển sinh #"
                    + str(app_id)
                    + ". / Cannot delete — later stage already has application #"
                    + str(app_id)
                    + "."
                )
            if st not in ("", "potential", "interested"):
                raise ValueError(
                    "Không xóa được vì hồ sơ đã vào khâu chăm sóc / ứng viên (trạng thái: "
                    + st
                    + "). / Cannot delete — profile already progressed (status: "
                    + st
                    + ")."
                )

    if table == "marcom_events":
        try:
            row = cur.execute(
                "SELECT alumni_event_id FROM marcom_events WHERE id = ?", (row_id,)
            ).fetchone()
        except Exception:
            row = None
        if row and row[0]:
            raise ValueError(
                "Không xóa được vì sự kiện đã đồng bộ Alumni (khâu sau). "
                "/ Cannot delete — event already synced to Alumni (later stage)."
            )

    if table == "asst_payments":
        try:
            row = cur.execute(
                "SELECT IFNULL(payment_status, status) FROM asst_payments WHERE id = ?",
                (row_id,),
            ).fetchone()
            st = (row[0] or "").strip() if row else ""
        except Exception:
            st = ""
        if st in ("paid", "settled"):
            raise ValueError(
                "Không xóa được vì khâu sau đã thanh toán (trạng thái: "
                + st
                + "). / Cannot delete — payment already settled (status: "
                + st
                + ")."
            )

    later = _ASST_LATER_STATUS.get(table)
    if later:
        try:
            row = cur.execute(f"SELECT status FROM {table} WHERE id = ?", (row_id,)).fetchone()
            st = (row[0] or "").strip() if row else ""
        except Exception:
            st = ""
        if st in later:
            raise ValueError(
                "Không xóa được vì khâu sau đã xử lý (trạng thái: "
                + st
                + "). / Cannot delete — later stage already processed (status: "
                + st
                + ")."
            )

    if table == "course_evaluations":
        try:
            row = cur.execute(
                "SELECT status, response_pct FROM course_evaluations WHERE id = ?",
                (row_id,),
            ).fetchone()
        except Exception:
            row = None
        if row:
            st = (row[0] or "").strip()
            pct = float(row[1] or 0)
            if pct > 0 or st in ("open", "sent", "sent_mgmt", "sent_faculty", "closed"):
                raise ValueError(
                    "Không xóa được vì đã có phản hồi / đã gửi đánh giá (khâu sau). "
                    "/ Cannot delete — evaluation already has responses or was sent (later stage)."
                )

    if table == "exam_schedules":
        try:
            row = cur.execute(
                "SELECT status FROM exam_schedules WHERE id = ?", (row_id,)
            ).fetchone()
            st = (row[0] or "").strip() if row else ""
        except Exception:
            st = ""
        if st in ("completed", "locked", "published", "done"):
            raise ValueError(
                "Không xóa được vì kỳ thi đã diễn ra / đã chốt (khâu sau). "
                "/ Cannot delete — exam already ran or was locked (later stage)."
            )

    hits: list[tuple[int, str, str]] = []
    for spec in _DELETE_CHILDREN.get(table) or []:
        sql, vi, en = spec
        nparam = sql.count("?")
        params = tuple([row_id] * nparam)
        n = _safe_count(cur, sql, params)
        if n > 0:
            hits.append((n, vi, en))
    if hits:
        raise ValueError(_blocked_delete_message(hits))


def delete_ops_row(conn, table: str, row_id: int) -> bool:
    import sqlite3

    cur = conn.cursor()
    allowed = {
        "asst_tasks",
        "asst_calendar",
        "asst_intl_faculty",
        "asst_intl_students",
        "asst_director_fr",
        "asst_documents",
        "asst_procurement",
        "asst_payments",
        "asst_weekly_reports",
        "asst_leave",
        "marcom_leads",
        "marcom_campaigns",
        "marcom_events",
        "marcom_assets",
        "faculty_experts",
        "faculty",
        "alumni_members",
        "alumni_events",
        "study_groups",
        "exam_schedules",
        "course_evaluations",
        "class_groups",
        "admission_rounds",
        "applications",
        "program_versions",
        "courses",
        "teaching_assignments",
        "interview_sessions",
        "thesis_records",
        "crm_source_profiles",
        "crm_activities",
        "crm_reminders",
        "admission_doc_types",
        "class_lessons",
        "elearn_objectives",
        "elearn_objective_recs",
        "elearn_study_plans",
        "elearn_plan_items",
        "elearn_agenda",
        "elearn_exam_sittings",
        "elearn_return_meetings",
    }
    if table not in allowed:
        raise ValueError("Table not allowed")
    assert_can_delete_ops_row(conn, table, row_id)
    try:
        if table == "crm_source_profiles":
            try:
                cur.execute("DELETE FROM crm_care_log WHERE profile_id = ?", (row_id,))
            except Exception:
                pass
        cur.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ValueError(
            "Không xóa được vì khâu sau còn ràng buộc dữ liệu. "
            "/ Cannot delete — later stage still references this record. "
            f"({exc})"
        ) from exc
    return cur.rowcount > 0


def seed_extra_ops(conn) -> dict:
    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    out = {"groups": 0, "exams": 0, "evals": 0, "subs": 0}
    cur.execute("SELECT COUNT(*) FROM study_groups")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id FROM class_groups LIMIT 3")
        for (cid,) in cur.fetchall():
            cur.execute(
                "INSERT INTO study_groups (class_id, name, member_names, status) VALUES (?, ?, ?, 'active')",
                (cid, f"Nhóm A lớp #{cid}", "HV 1, HV 2, HV 3"),
            )
            out["groups"] += 1
    cur.execute("SELECT COUNT(*) FROM exam_schedules")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id, name FROM class_groups LIMIT 3")
        for cid, cname in cur.fetchall():
            cur.execute(
                "INSERT INTO exam_schedules (class_id, title, exam_date, exam_type, room, status) "
                "VALUES (?, ?, ?, 'final', 'P.201', 'planned')",
                (cid, f"Thi cuối kỳ — {cname}", date.today().isoformat()),
            )
            out["exams"] += 1
    cur.execute("SELECT COUNT(*) FROM course_evaluations")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id, name FROM class_groups LIMIT 2")
        for cid, cname in cur.fetchall():
            cur.execute(
                "INSERT INTO course_evaluations (class_id, title, response_pct, status, summary) "
                "VALUES (?, ?, 82, 'open', ?)",
                (cid, f"Đánh giá — {cname}", "Phản hồi tốt về nội dung."),
            )
            out["evals"] += 1
    cur.execute("SELECT COUNT(*) FROM assignment_submissions")
    if cur.fetchone()[0] == 0:
        cur.execute("SELECT id FROM class_groups LIMIT 1")
        row = cur.fetchone()
        if row:
            for i, name in enumerate(("Nguyễn Văn An", "Trần Thị Bình", "Lê Minh Châu"), 1):
                cur.execute(
                    "INSERT INTO assignment_submissions "
                    "(class_id, course_code, student_name, title, score, submitted_at, status) "
                    "VALUES (?, 'MSCM101', ?, ?, ?, ?, 'submitted')",
                    (row[0], name, f"Bài tập {i}", 12 + i * 0.5, date.today().isoformat()),
                )
                out["subs"] += 1
    conn.commit()
    return out


# —— Asst creates ——

def asst_insert(conn, table: str, data: dict, required: list[str]) -> dict:
    cur = conn.cursor()
    from asst_ops import ensure_asst_tables
    from marcom_ops import ensure_marcom_tables

    ensure_asst_tables(cur)
    ensure_marcom_tables(cur)
    try:
        from crm_ops import ensure_crm_tables

        ensure_crm_tables(cur)
    except Exception:
        pass
    defaults = {
        "asst_documents": {"doc_direction": "in", "status": "received"},
        "asst_procurement": {"category": "other", "status": "requested"},
        "asst_payments": {"cost_type": "other", "payment_status": "unpaid"},
        "asst_leave": {"status": "pending", "leave_type": "annual"},
        "asst_tasks": {"status": "open"},
        "asst_calendar": {"cal_type": "meeting", "status": "confirmed"},
        "asst_weekly_reports": {"status": "draft"},
        "marcom_leads": {"status": "new", "source": "other"},
        "marcom_campaigns": {"channel": "online", "status": "planned"},
        "marcom_events": {"event_type": "workshop", "status": "planned", "budget_status": "planned"},
        "marcom_assets": {"asset_type": "image", "content_status": "requested", "outsource": "no", "budget_status": "planned"},
    }
    payload = dict(defaults.get(table, {}))
    payload.update({k: v for k, v in data.items() if v is not None and k != "id"})
    for k in required:
        val = payload.get(k)
        if val is None or (isinstance(val, str) and not str(val).strip()):
            raise ValueError(f"Thiếu {k}")
    if not payload:
        raise ValueError("No data")
    person_tables = {"asst_intl_students"}
    if table in person_tables:
        from admission_ops import normalize_cccd, propagate_row_by_id

        cccd = str(payload.get("cccd") or "").strip()
        if not normalize_cccd(cccd):
            raise ValueError("Thiếu Căn cước công dân (cccd)")
        payload["cccd"] = cccd
        hit = cur.execute(
            f"SELECT id FROM {table} WHERE "
            "REPLACE(REPLACE(REPLACE(UPPER(IFNULL(cccd,'')),' ',''),'-',''),'.','') = ?",
            (normalize_cccd(cccd),),
        ).fetchone()
        if hit:
            rid = int(hit[0])
            sets = ", ".join(f"{k} = ?" for k in payload)
            cur.execute(f"UPDATE {table} SET {sets} WHERE id = ?", [*payload.values(), rid])
            conn.commit()
            try:
                propagate_row_by_id(conn, table, rid, payload)
            except Exception:
                pass
            return {"id": rid, **payload}
    cols = list(payload.keys())
    cur.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [payload[c] for c in cols],
    )
    new_id = cur.lastrowid
    # Mua sắm → sổ thanh toán (đồng bộ đề xuất sang Chi phí)
    if table == "asst_procurement":
        cat = (payload.get("category") or "other").strip() or "other"
        cost_map = {
            "stationery": "stationery",
            "water": "water",
            "taxi": "taxi",
            "flight": "flight",
        }
        month_key = (payload.get("request_date") or date.today().isoformat())[:7]
        cur.execute(
            "INSERT INTO asst_payments "
            "(cost_type, beneficiary, supplier, amount, invoice_no, payment_status, month_key, notes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                cost_map.get(cat, "other"),
                payload.get("requester") or "",
                payload.get("supplier") or "",
                payload.get("amount"),
                payload.get("invoice_no") or "",
                "unpaid",
                month_key,
                f"Từ đề xuất mua sắm #{new_id}: {payload.get('item_name') or ''}",
            ),
        )
    conn.commit()
    if table == "asst_intl_students":
        try:
            from admission_ops import propagate_row_by_id

            propagate_row_by_id(conn, table, new_id, payload)
        except Exception:
            pass
    return {"id": new_id, **payload}


def generic_row_update(conn, table: str, row_id: int, data: dict) -> dict:
    """Patch allowlisted columns on an ops table (view → Chỉnh sửa)."""
    cur = conn.cursor()
    cols = [
        r[1]
        for r in cur.execute(f"PRAGMA table_info({table})").fetchall()
        if r[1] not in ("id",)
    ]
    skip = {"id", "created_at", "password"}
    fields, params = [], []
    for k, v in (data or {}).items():
        if k in skip or k not in cols:
            continue
        fields.append(f"{k} = ?")
        params.append(v)
    if not fields:
        raise ValueError("Không có trường để cập nhật")
    params.append(row_id)
    cur.execute(f"UPDATE {table} SET {', '.join(fields)} WHERE id = ?", params)
    if cur.rowcount < 1:
        raise ValueError("Không tìm thấy bản ghi")
    conn.commit()
    if table in {
        "applications",
        "alumni_members",
        "crm_source_profiles",
        "asst_intl_students",
        "class_students",
    }:
        try:
            from admission_ops import propagate_row_by_id

            propagate_row_by_id(conn, table, row_id, data or {})
        except Exception:
            pass
    return {"id": row_id, **data}


def create_program_version_row(conn, data: dict) -> dict:
    from ops_data import ensure_ops_tables

    cur = conn.cursor()
    ensure_ops_tables(cur)
    prog = (data.get("program_code") or "").strip().upper()
    code = (data.get("version_code") or "").strip()
    name = (data.get("name") or "").strip()
    if not prog or not code or not name:
        raise ValueError("Cần mã CT, mã phiên bản và tên.")
    exists = cur.execute(
        "SELECT id FROM program_versions WHERE version_code = ?", (code,)
    ).fetchone()
    if exists:
        raise ValueError(f"Mã phiên bản đã tồn tại: {code}")
    from ops_data import ensure_ops_tables as _ensure

    _ensure(cur)
    cohort_no = str(data.get("cohort_no") or "").strip()
    def _year(key):
        raw = data.get(key)
        try:
            return int(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            return None
    cur.execute(
        "INSERT INTO program_versions (program_code, version_code, name, description, is_active, "
        "cohort_no, year_start, year_end) "
        "VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
        (
            prog, code, name, (data.get("description") or "").strip(),
            cohort_no, _year("year_start"), _year("year_end"),
        ),
    )
    conn.commit()
    return {"id": cur.lastrowid, "program_code": prog, "version_code": code, "name": name}


def create_course_row(conn, data: dict) -> dict:
    from ops_data import ensure_ops_tables

    cur = conn.cursor()
    ensure_ops_tables(cur)
    pvid = data.get("program_version_id")
    try:
        pvid = int(pvid) if pvid not in (None, "") else None
    except (TypeError, ValueError):
        pvid = None
    if not pvid:
        vcode = (data.get("version_code") or "").strip()
        prog = (data.get("program_code") or "").strip().upper()
        row = None
        if vcode:
            row = cur.execute(
                "SELECT id FROM program_versions WHERE version_code = ?", (vcode,)
            ).fetchone()
        if not row and prog:
            row = cur.execute(
                "SELECT id FROM program_versions WHERE program_code = ? ORDER BY id DESC LIMIT 1",
                (prog,),
            ).fetchone()
        if not row:
            raise ValueError("Không tìm thấy phiên bản chương trình.")
        pvid = row[0]
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    if not code or not name:
        raise ValueError("Cần mã HP và tên học phần.")
    try:
        semester = int(data.get("semester") or 1)
    except (TypeError, ValueError):
        semester = 1
    cur.execute(
        "INSERT INTO courses (program_version_id, code, name, semester) VALUES (?, ?, ?, ?)",
        (pvid, code, name, semester),
    )
    conn.commit()
    return {
        "id": cur.lastrowid,
        "code": code,
        "name": name,
        "program_version_id": pvid,
        "semester": semester,
    }


def create_teaching_assignment_row(conn, data: dict) -> dict:
    from ops_data import ensure_ops_tables

    cur = conn.cursor()
    ensure_ops_tables(cur)
    try:
        class_id = int(data.get("class_id") or 0)
    except (TypeError, ValueError):
        class_id = 0
    if not class_id:
        raise ValueError("Cần lớp.")
    try:
        course_id = int(data.get("course_id") or 0) if data.get("course_id") not in (None, "") else 0
    except (TypeError, ValueError):
        course_id = 0
    if not course_id:
        ccode = (data.get("course_code") or "").strip()
        if not ccode:
            raise ValueError("Cần mã học phần.")
        row = cur.execute(
            "SELECT c.id FROM courses c "
            "JOIN class_groups cg ON cg.program_version_id = c.program_version_id "
            "WHERE cg.id = ? AND upper(c.code) = upper(?) LIMIT 1",
            (class_id, ccode),
        ).fetchone()
        if not row:
            row = cur.execute(
                "SELECT id FROM courses WHERE upper(code) = upper(?) ORDER BY id DESC LIMIT 1",
                (ccode,),
            ).fetchone()
        if not row:
            raise ValueError(f"Không tìm thấy học phần {ccode}.")
        course_id = row[0]
    lecturer_id = None
    if data.get("lecturer_id") not in (None, ""):
        try:
            lecturer_id = int(data["lecturer_id"])
        except (TypeError, ValueError):
            lecturer_id = None
    elif (data.get("lecturer_name") or "").strip():
        row = cur.execute(
            "SELECT id FROM faculty WHERE lower(full_name) = lower(?) LIMIT 1",
            ((data.get("lecturer_name") or "").strip(),),
        ).fetchone()
        lecturer_id = row[0] if row else None
    expert_id = None
    if data.get("expert_id") not in (None, ""):
        try:
            expert_id = int(data["expert_id"])
        except (TypeError, ValueError):
            expert_id = None
    elif (data.get("expert_name") or "").strip():
        row = cur.execute(
            "SELECT id FROM faculty WHERE lower(full_name) = lower(?) LIMIT 1",
            ((data.get("expert_name") or "").strip(),),
        ).fetchone()
        expert_id = row[0] if row else None
    status = (data.get("status") or "planned").strip() or "planned"
    cur.execute(
        "INSERT INTO teaching_assignments (class_id, course_id, lecturer_id, expert_id, status) "
        "VALUES (?, ?, ?, ?, ?)",
        (class_id, course_id, lecturer_id, expert_id, status),
    )
    assignment_id = cur.lastrowid
    conn.commit()
    stamped: dict = {}
    try:
        from class_lessons import stamp_faculty_sessions

        stamped = stamp_faculty_sessions(conn, assignment_id)
    except Exception:
        stamped = {}
    return {
        "id": assignment_id,
        "class_id": class_id,
        "course_id": course_id,
        "status": status,
        "sessions_named": stamped.get("updated", 0),
    }


def create_attendance_session_row(conn, data: dict) -> dict:
    from ops_data import ensure_ops_tables

    cur = conn.cursor()
    ensure_ops_tables(cur)
    try:
        assignment_id = int(data.get("assignment_id") or 0)
    except (TypeError, ValueError):
        assignment_id = 0
    if not assignment_id:
        raise ValueError("Cần ID phân giảng.")
    exists = cur.execute(
        "SELECT id FROM teaching_assignments WHERE id = ?", (assignment_id,)
    ).fetchone()
    if not exists:
        raise ValueError("Không tìm thấy phân giảng.")
    try:
        session_no = int(data.get("session_no") or 1)
    except (TypeError, ValueError):
        session_no = 1
    label = (data.get("session_label") or f"Buổi {session_no}").strip()
    sdate = (data.get("session_date") or "").strip()
    cur.execute(
        "INSERT INTO attendance_sessions (assignment_id, session_no, session_label, session_date) "
        "VALUES (?, ?, ?, ?)",
        (assignment_id, session_no, label, sdate),
    )
    conn.commit()
    return {
        "id": cur.lastrowid,
        "assignment_id": assignment_id,
        "session_no": session_no,
        "session_label": label,
        "session_date": sdate,
    }

