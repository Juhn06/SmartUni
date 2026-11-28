"""Student portal account lifecycle: temporary password, first-login change, credential notice, lock or alumni on status change."""

from __future__ import annotations

import secrets
import string

LOCK_WITHDRAWN = "lifecycle_withdrawn"
TEMP_ALPHABET = string.ascii_letters + string.digits


def ensure_account_columns(cur) -> None:
    for column in ("must_change_password INTEGER DEFAULT 0", "lock_reason TEXT"):
        try:
            cur.execute(f"ALTER TABLE user ADD COLUMN {column}")
        except Exception:
            pass


def temp_password(length: int = 10) -> str:
    while True:
        value = "".join(secrets.choice(TEMP_ALPHABET) for _ in range(length))
        if any(c.isdigit() for c in value) and any(c.isalpha() for c in value):
            return value


def must_change(conn, user_id: int) -> bool:
    cur = conn.cursor()
    ensure_account_columns(cur)
    row = cur.execute("SELECT COALESCE(must_change_password, 0) FROM user WHERE id = ?", (user_id,)).fetchone()
    return bool(row and row[0])


def set_must_change(conn, user_id: int, value: bool) -> None:
    cur = conn.cursor()
    ensure_account_columns(cur)
    cur.execute("UPDATE user SET must_change_password = ? WHERE id = ?", (1 if value else 0, user_id))
    conn.commit()


def queue_credentials(conn, *, email: str, full_name: str, login: str, password: str, program_code: str) -> dict | None:
    if not email or "@" not in email:
        return None
    from ops_crud import queue_email

    body = (
        f"Chào {full_name},\n\n"
        f"Trung tâm đã tạo tài khoản cổng học viên chương trình {program_code} cho bạn.\n"
        f"Tên đăng nhập: {login}\n"
        f"Mật khẩu tạm: {password}\n\n"
        "Lần đăng nhập đầu tiên, hệ thống sẽ yêu cầu bạn đổi mật khẩu. "
        "Trong cổng học viên có trợ lý UniBot trả lời về điểm, học phí, lịch học và thủ tục học vụ của chính bạn.\n"
    )
    return queue_email(conn, kind="student_account", recipient=email, subject="Tài khoản cổng học viên", body=body)


def _portal_user(cur, student_id: int) -> int | None:
    row = cur.execute("SELECT portal_user_id, application_id FROM class_students WHERE id = ?", (student_id,)).fetchone()
    if not row:
        return None
    if row[0]:
        return int(row[0])
    if row[1]:
        app = cur.execute("SELECT portal_user_id FROM applications WHERE id = ?", (row[1],)).fetchone()
        if app and app[0]:
            return int(app[0])
    return None


def _dept_id(cur, code: str) -> int | None:
    row = cur.execute("SELECT id FROM departments WHERE code = ?", (code,)).fetchone()
    return row[0] if row else None


def sync_with_lifecycle(conn, student_id: int) -> dict:
    cur = conn.cursor()
    ensure_account_columns(cur)
    row = cur.execute("SELECT lifecycle_status FROM class_students WHERE id = ?", (student_id,)).fetchone()
    if not row:
        return {"changed": False}
    life = (row[0] or "active").strip()
    user_id = _portal_user(cur, student_id)
    if not user_id:
        return {"changed": False, "lifecycle": life, "account": None}
    action = "none"
    if life == "withdrawn_program":
        cur.execute("UPDATE user SET is_locked = 1, lock_reason = ? WHERE id = ?", (LOCK_WITHDRAWN, user_id))
        action = "locked"
    else:
        cur.execute(
            "UPDATE user SET is_locked = 0, lock_reason = NULL WHERE id = ? AND lock_reason = ?", (user_id, LOCK_WITHDRAWN)
        )
        if cur.rowcount:
            action = "unlocked"
    if life == "graduated":
        alumni = _dept_id(cur, "cuu_hoc_vien")
        if alumni:
            cur.execute("INSERT OR IGNORE INTO user_departments (user_id, department_id) VALUES (?, ?)", (user_id, alumni))
        conn.commit()
        try:
            from mba_ops import promote_graduated_to_alumni

            promote_graduated_to_alumni(conn, student_id)
        except Exception:
            pass
        action = "alumni" if action == "none" else f"{action},alumni"
    conn.commit()
    return {"changed": action != "none", "lifecycle": life, "account": user_id, "action": action}
