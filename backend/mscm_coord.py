"""MSCM coordination extras: result/welcome mail, alumni portal accounts."""
from __future__ import annotations

from typing import Any

MAIL_DEFAULTS = {
    "pass": (
        "[X] Kết quả tuyển sinh {program}",
        "Kính gửi {name},\n\n"
        "Chúc mừng bạn đã trúng tuyển chương trình {program}.\n\n"
        "Bộ phận Kế toán sẽ theo dõi phí ghi danh. "
        "Bạn nộp tiền theo thông báo và gửi minh chứng trên hệ thống.\n\nX",
    ),
    "fail": (
        "[X] Kết quả tuyển sinh {program}",
        "Kính gửi {name},\n\n"
        "Thông báo kết quả: bạn chưa trúng tuyển chương trình {program}.\n\nX",
    ),
    "interview": (
        "[X] Thư mời phỏng vấn {program}",
        "Kính gửi {name},\n\n"
        "Bạn được mời tham dự phỏng vấn chương trình {program}.\n"
        "Thời gian và phòng thi theo lịch đã công bố.\n\nX",
    ),
    "missing_docs": (
        "[X] Nhắc bổ sung hồ sơ {program}",
        "Kính gửi {name},\n\n"
        "Hồ sơ chương trình {program} còn giấy tờ cần bổ sung trước khai giảng.\n\nX",
    ),
    "welcome": (
        "[X] Chào mừng lớp {class_name}",
        "Kính gửi {name},\n\n"
        "Chào mừng bạn vào lớp {class_name}, chương trình {program}.\n\n"
        "Hướng dẫn Canvas:\n"
        "1. Bộ phận quản lý phần mềm sẽ tạo email và tài khoản Canvas cho bạn.\n"
        "2. Đăng nhập Canvas bằng email được cấp.\n"
        "3. Vào đúng khóa học của lớp {class_name} để xem tài liệu và thông báo.\n\nX",
    ),
}


def ensure_mail_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS email_templates ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "program_code TEXT NOT NULL, "
        "kind TEXT NOT NULL, "
        "subject TEXT NOT NULL, "
        "body TEXT NOT NULL, "
        "UNIQUE(program_code, kind))"
    )
    for prog in ("*", "MBA", "MMS", "MSCM"):
        for kind, (subject, body) in MAIL_DEFAULTS.items():
            cur.execute(
                "INSERT OR IGNORE INTO email_templates (program_code, kind, subject, body) "
                "VALUES (?,?,?,?)",
                (prog, kind, subject, body),
            )


def _fill(text: str, values: dict[str, str]) -> str:
    out = text or ""
    for key, val in values.items():
        out = out.replace("{" + key + "}", val or "")
    return out


def list_mail_templates(conn) -> list[dict]:
    cur = conn.cursor()
    ensure_mail_tables(cur)
    rows = cur.execute(
        "SELECT id, program_code, kind, subject, body FROM email_templates "
        "WHERE program_code != '*' ORDER BY program_code, kind"
    ).fetchall()
    labels = {
        "pass": "Thư trúng tuyển",
        "fail": "Thư chưa trúng tuyển",
        "interview": "Thư mời phỏng vấn",
        "missing_docs": "Nhắc bổ sung hồ sơ",
        "welcome": "Thư chào mừng lớp",
    }
    return [
        {
            "id": r[0],
            "program_code": r[1],
            "kind": r[2],
            "kind_label": labels.get(r[2], r[2]),
            "subject": r[3],
            "body": r[4],
        }
        for r in rows
    ]


def get_mail_template(conn, program_code: str, kind: str) -> dict:
    cur = conn.cursor()
    ensure_mail_tables(cur)
    prog = (program_code or "*").strip().upper() or "*"
    row = cur.execute(
        "SELECT subject, body FROM email_templates WHERE program_code = ? AND kind = ?",
        (prog, kind),
    ).fetchone()
    if not row:
        row = cur.execute(
            "SELECT subject, body FROM email_templates WHERE program_code = '*' AND kind = ?",
            (kind,),
        ).fetchone()
    if not row:
        subject, body = MAIL_DEFAULTS.get(kind, ("[X]", ""))
    else:
        subject, body = row[0], row[1]
    conn.commit()
    return {"program_code": prog, "kind": kind, "subject": subject, "body": body}


def save_mail_template(conn, program_code: str, kind: str, subject: str, body: str) -> dict:
    if kind not in MAIL_DEFAULTS:
        raise ValueError("Loại thư không hợp lệ.")
    prog = (program_code or "").strip().upper()
    if prog not in ("MBA", "MMS", "MSCM"):
        raise ValueError("Chọn chương trình MBA, MMS hoặc MSCM.")
    sub = (subject or "").strip()
    text = (body or "").strip()
    if not sub or not text:
        raise ValueError("Cần tiêu đề và nội dung.")
    cur = conn.cursor()
    ensure_mail_tables(cur)
    cur.execute(
        "INSERT INTO email_templates (program_code, kind, subject, body) VALUES (?,?,?,?) "
        "ON CONFLICT(program_code, kind) DO UPDATE SET subject = excluded.subject, body = excluded.body",
        (prog, kind, sub, text),
    )
    conn.commit()
    return get_mail_template(conn, prog, kind)


def render_mail(conn, program_code: str, kind: str, **values: str) -> tuple[str, str]:
    tpl = get_mail_template(conn, program_code, kind)
    data = {"program": program_code or "", "name": "", "class_name": ""}
    data.update({k: str(v or "") for k, v in values.items()})
    return _fill(tpl["subject"], data), _fill(tpl["body"], data)


def queue_class_welcome(conn, class_id: int) -> dict:
    from ops_crud import queue_email

    cur = conn.cursor()
    row = cur.execute(
        "SELECT name, program_code FROM class_groups WHERE id = ?",
        (class_id,),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy lớp.")
    class_name, program = row[0] or "", row[1] or ""
    students = cur.execute(
        "SELECT full_name, email FROM class_students "
        "WHERE class_id = ? AND IFNULL(email,'') != ''",
        (class_id,),
    ).fetchall()
    sent = 0
    for name, email in students:
        subject, body = render_mail(
            conn, program, "welcome", name=name or "", class_name=class_name, program=program
        )
        queue_email(
            conn,
            kind="class_welcome",
            recipient=email,
            subject=subject,
            body=body,
        )
        sent += 1
    return {"sent": sent, "class_id": class_id, "class_name": class_name}


def _ensure_alumni_dept(cur) -> int:
    from rbac import MENU_ITEMS

    item = next(m for m in MENU_ITEMS if m["code"] == "alumni.portal")
    cur.execute(
        "INSERT OR IGNORE INTO permissions (code, label, group_name, route, sort_order) "
        "VALUES (?,?,?,?,?)",
        (item["code"], item["label"], item["group"], item["route"], int(item["sort"])),
    )
    cur.execute("SELECT id FROM departments WHERE code = 'cuu_hoc_vien'")
    row = cur.fetchone()
    if row:
        dept_id = row[0]
    else:
        cur.execute(
            "INSERT INTO departments (code, name, sort_order) VALUES ('cuu_hoc_vien', 'Cựu học viên', 15)"
        )
        dept_id = cur.lastrowid
    cur.execute(
        "INSERT OR IGNORE INTO department_permissions (department_id, permission_code) "
        "VALUES (?, 'alumni.portal')",
        (dept_id,),
    )
    return int(dept_id)


def provision_alumni_portal(conn, alumni_id: int) -> dict:
    from ops_data import ensure_ops_tables
    from seed_org import TEMP_PASSWORD, make_username

    cur = conn.cursor()
    ensure_ops_tables(cur)
    member = cur.execute(
        "SELECT id, full_name, program_code, email, COALESCE(user_id,0), COALESCE(portal_login,'') "
        "FROM alumni_members WHERE id = ?",
        (alumni_id,),
    ).fetchone()
    if not member:
        raise ValueError("Không có cựu học viên này.")
    _id, full_name, program, email, user_id, portal_login = member
    if user_id:
        cur.execute("SELECT email FROM user WHERE id = ?", (user_id,))
        u = cur.fetchone()
        return {
            "alumni_id": alumni_id,
            "login": (u[0] if u else portal_login) or portal_login,
            "created": False,
            "password": None,
        }
    dept_id = _ensure_alumni_dept(cur)
    base = make_username(full_name or "") or "Alumni"
    login = base
    n = 2
    while cur.execute("SELECT 1 FROM user WHERE lower(email) = lower(?)", (login,)).fetchone():
        login = f"{base}{n}"
        n += 1
    cur.execute(
        "INSERT INTO user (name, email, password, is_admin, is_locked) VALUES (?,?,?,0,0)",
        (full_name, login, TEMP_PASSWORD),
    )
    uid = cur.lastrowid
    cur.execute(
        "INSERT OR IGNORE INTO user_departments (user_id, department_id) VALUES (?,?)",
        (uid, dept_id),
    )
    cur.execute(
        "INSERT OR IGNORE INTO user_permissions (user_id, permission_code) VALUES (?, 'alumni.portal')",
        (uid,),
    )
    if program:
        cur.execute(
            "INSERT OR IGNORE INTO user_program_scopes (user_id, program_code) VALUES (?,?)",
            (uid, program),
        )
    cur.execute(
        "UPDATE alumni_members SET user_id = ?, portal_login = ? WHERE id = ?",
        (uid, login, alumni_id),
    )
    conn.commit()
    return {
        "alumni_id": alumni_id,
        "login": login,
        "password": TEMP_PASSWORD,
        "email": email or "",
        "created": True,
    }


def alumni_portal_for_user(conn, user_id: int) -> dict | None:
    from ops_data import ensure_ops_tables

    cur = conn.cursor()
    ensure_ops_tables(cur)
    row = cur.execute(
        "SELECT id, full_name, program_code, cohort, class_name, email, phone, company, "
        "COALESCE(activity_keywords,''), COALESCE(portal_login,'') "
        "FROM alumni_members WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    member = {
        "id": row[0],
        "full_name": row[1],
        "program_code": row[2],
        "cohort": row[3],
        "class_name": row[4],
        "email": row[5],
        "phone": row[6],
        "company": row[7],
        "activity_keywords": row[8],
        "portal_login": row[9],
    }
    events = cur.execute(
        "SELECT e.id, e.title, e.event_date, e.location, e.program_filter, e.status, "
        "e.description, "
        "CASE WHEN i.id IS NULL THEN 0 ELSE 1 END "
        "FROM alumni_events e "
        "LEFT JOIN alumni_event_invitees i ON i.event_id = e.id AND i.alumni_id = ? "
        "WHERE IFNULL(e.program_filter,'') = '' "
        "OR e.program_filter = ? "
        "OR i.id IS NOT NULL "
        "ORDER BY e.event_date DESC, e.id DESC",
        (member["id"], member["program_code"]),
    ).fetchall()
    member["events"] = [
        {
            "id": e[0],
            "title": e[1],
            "event_date": e[2],
            "location": e[3],
            "program_filter": e[4],
            "status": e[5],
            "description": e[6],
            "invited": bool(e[7]),
        }
        for e in events
    ]
    return member


def update_alumni_self(conn, user_id: int, data: dict) -> dict:
    current = alumni_portal_for_user(conn, user_id)
    if not current:
        raise ValueError("Tài khoản này chưa gắn hồ sơ cựu học viên.")
    fields = []
    params: list[Any] = []
    for key in ("phone", "email", "company", "activity_keywords"):
        if key not in data:
            continue
        fields.append(f"{key} = ?")
        params.append((data.get(key) or "").strip())
    if not fields:
        return current
    params.append(current["id"])
    cur = conn.cursor()
    cur.execute(
        f"UPDATE alumni_members SET {', '.join(fields)} WHERE id = ?",
        params,
    )
    conn.commit()
    updated = alumni_portal_for_user(conn, user_id)
    return updated or current
