"""
Điểm danh theo buổi học (class_lessons): lần 1 + lần 2.
- GV check thủ công trên danh sách lớp
- QR xoay vòng ngắn hạn (chiếu trên máy chiếu) — HV đăng nhập + thuộc lớp mới quét được
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

QR_TTL_SEC = 25
QR_ROTATE_EVERY_SEC = 20


def ensure_lesson_attendance_tables(cur) -> None:
    from ops_data import ensure_ops_tables
    from mba_ops import ensure_mba_tables

    ensure_ops_tables(cur)
    ensure_mba_tables(cur)
    for col, typ in (
        ("lesson_id", "INTEGER"),
        ("round1_open", "INTEGER DEFAULT 0"),
        ("round2_open", "INTEGER DEFAULT 0"),
        ("round1_opened_at", "TEXT"),
        ("round2_opened_at", "TEXT"),
    ):
        try:
            cur.execute(f"ALTER TABLE attendance_sessions ADD COLUMN {col} {typ}")
        except Exception:
            pass
    for col, typ in (
        ("source_r1", "TEXT"),  # faculty | qr
        ("source_r2", "TEXT"),
        ("marked_at_r1", "TEXT"),
        ("marked_at_r2", "TEXT"),
    ):
        try:
            cur.execute(f"ALTER TABLE attendance_marks ADD COLUMN {col} {typ}")
        except Exception:
            pass
    cur.execute(
        "CREATE TABLE IF NOT EXISTS attendance_qr_tokens ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "session_id INTEGER NOT NULL, "
        "round INTEGER NOT NULL, "  # 1 | 2
        "token_hash TEXT NOT NULL UNIQUE, "
        "token_plain TEXT, "  # short-lived display only; cleared after expiry window
        "expires_at TEXT NOT NULL, "
        "created_by TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (session_id) REFERENCES attendance_sessions(id))"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_att_sess_lesson ON attendance_sessions(lesson_id)"
    )
    try:
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_att_sess_lesson_uniq "
            "ON attendance_sessions(lesson_id) WHERE lesson_id IS NOT NULL"
        )
    except Exception:
        pass


def _now() -> datetime:
    return datetime.utcnow()


def _now_iso() -> str:
    return _now().isoformat() + "Z"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _recalc_counts(cur, session_id: int) -> None:
    row = cur.execute(
        "SELECT COUNT(*), "
        "SUM(CASE WHEN COALESCE(present,0)=1 OR COALESCE(check_in,0)>0 THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN COALESCE(present_after_break,0)=1 OR COALESCE(check_out,0)>0 THEN 1 ELSE 0 END) "
        "FROM attendance_marks WHERE attendance_session_id=?",
        (session_id,),
    ).fetchone()
    total = int(row[0] or 0)
    # present_count = students present in at least one round; absent = total roster later
    present_either = cur.execute(
        "SELECT COUNT(*) FROM attendance_marks WHERE attendance_session_id=? AND ("
        "COALESCE(present,0)=1 OR COALESCE(present_after_break,0)=1 "
        "OR COALESCE(check_in,0)>0 OR COALESCE(check_out,0)>0)",
        (session_id,),
    ).fetchone()[0]
    # Get class size from session → assignment → class
    meta = cur.execute(
        "SELECT ta.class_id FROM attendance_sessions ats "
        "JOIN teaching_assignments ta ON ta.id=ats.assignment_id WHERE ats.id=?",
        (session_id,),
    ).fetchone()
    class_size = 0
    if meta:
        class_size = cur.execute(
            "SELECT COUNT(*) FROM class_students WHERE class_id=?", (meta[0],)
        ).fetchone()[0]
    present = int(present_either or 0)
    absent = max(0, int(class_size) - present) if class_size else max(0, total - present)
    cur.execute(
        "UPDATE attendance_sessions SET present_count=?, absent_count=? WHERE id=?",
        (present, absent, session_id),
    )


def ensure_session_for_lesson(conn, lesson_id: int) -> dict:
    cur = conn.cursor()
    ensure_lesson_attendance_tables(cur)
    lesson = cur.execute(
        "SELECT cl.id, cl.assignment_id, cl.lesson_no, cl.title, cl.lesson_date, cl.status "
        "FROM class_lessons cl WHERE cl.id=?",
        (lesson_id,),
    ).fetchone()
    if not lesson:
        raise ValueError("Lesson not found")
    existing = cur.execute(
        "SELECT id FROM attendance_sessions WHERE lesson_id=?", (lesson_id,)
    ).fetchone()
    if existing:
        return get_session(conn, existing[0])
    label = f"Buổi {lesson[2]}: {lesson[3]}"
    cur.execute(
        "INSERT INTO attendance_sessions "
        "(assignment_id, session_no, session_label, session_date, present_count, absent_count, "
        "lesson_id, round1_open, round2_open) VALUES (?,?,?,?,0,0,?,0,0)",
        (
            lesson[1],
            lesson[2],
            label,
            lesson[4] or _now().date().isoformat(),
            lesson_id,
        ),
    )
    sid = cur.lastrowid
    conn.commit()
    return get_session(conn, sid)


def get_session(conn, session_id: int) -> dict:
    cur = conn.cursor()
    ensure_lesson_attendance_tables(cur)
    r = cur.execute(
        "SELECT ats.id, ats.assignment_id, ats.session_no, ats.session_label, ats.session_date, "
        "ats.present_count, ats.absent_count, ats.lesson_id, "
        "IFNULL(ats.round1_open,0), IFNULL(ats.round2_open,0), "
        "ats.round1_opened_at, ats.round2_opened_at, "
        "cg.id, cg.name, cg.program_code, c.id, c.code, c.name, cl.title "
        "FROM attendance_sessions ats "
        "JOIN teaching_assignments ta ON ta.id=ats.assignment_id "
        "JOIN class_groups cg ON cg.id=ta.class_id "
        "JOIN courses c ON c.id=ta.course_id "
        "LEFT JOIN class_lessons cl ON cl.id=ats.lesson_id "
        "WHERE ats.id=?",
        (session_id,),
    ).fetchone()
    if not r:
        raise ValueError("Attendance session not found")
    return {
        "id": r[0],
        "assignment_id": r[1],
        "session_no": r[2],
        "session_label": r[3],
        "session_date": r[4],
        "present_count": r[5],
        "absent_count": r[6],
        "lesson_id": r[7],
        "round1_open": bool(r[8]),
        "round2_open": bool(r[9]),
        "round1_opened_at": r[10],
        "round2_opened_at": r[11],
        "class_id": r[12],
        "class_name": r[13],
        "program_code": r[14],
        "course_id": r[15],
        "course_code": r[16],
        "course_name": r[17],
        "lesson_title": r[18] or r[3],
    }


def set_round_open(conn, session_id: int, round_no: int, open_: bool) -> dict:
    if round_no not in (1, 2):
        raise ValueError("round must be 1 or 2")
    cur = conn.cursor()
    ensure_lesson_attendance_tables(cur)
    col = "round1_open" if round_no == 1 else "round2_open"
    at_col = "round1_opened_at" if round_no == 1 else "round2_opened_at"
    if open_:
        cur.execute(
            f"UPDATE attendance_sessions SET {col}=1, {at_col}=? WHERE id=?",
            (_now_iso(), session_id),
        )
    else:
        cur.execute(
            f"UPDATE attendance_sessions SET {col}=0 WHERE id=?",
            (session_id,),
        )
    if cur.rowcount == 0:
        raise ValueError("Attendance session not found")
    conn.commit()
    return get_session(conn, session_id)


def get_roster(conn, session_id: int) -> dict:
    cur = conn.cursor()
    ensure_lesson_attendance_tables(cur)
    sess = get_session(conn, session_id)
    students = cur.execute(
        "SELECT cs.id, cs.full_name, cs.email, cs.student_code "
        "FROM class_students cs WHERE cs.class_id=? ORDER BY cs.full_name",
        (sess["class_id"],),
    ).fetchall()
    marks = {
        r[0]: r
        for r in cur.execute(
            "SELECT student_id, present, present_after_break, "
            "COALESCE(check_in, CAST(present AS REAL)), "
            "COALESCE(check_out, CAST(COALESCE(present_after_break,0) AS REAL)), "
            "IFNULL(source_r1,''), IFNULL(source_r2,''), marked_at_r1, marked_at_r2, note "
            "FROM attendance_marks WHERE attendance_session_id=?",
            (session_id,),
        ).fetchall()
    }
    roster = []
    for sid, name, email, code in students:
        m = marks.get(sid)
        r1 = False
        r2 = False
        if m:
            r1 = bool(m[1]) or (float(m[3] or 0) > 0)
            r2 = bool(m[2]) or (float(m[4] or 0) > 0)
        roster.append(
            {
                "student_id": sid,
                "full_name": name,
                "email": email or "",
                "student_code": code or "",
                "round1": r1,
                "round2": r2,
                "source_r1": (m[5] if m else "") or "",
                "source_r2": (m[6] if m else "") or "",
                "marked_at_r1": m[7] if m else None,
                "marked_at_r2": m[8] if m else None,
                "note": (m[9] if m else "") or "",
                "has_mark": bool(m),
            }
        )
    present_r1 = sum(1 for x in roster if x["round1"])
    present_r2 = sum(1 for x in roster if x["round2"])
    return {
        "session": sess,
        "roster": roster,
        "stats": {
            "students": len(roster),
            "present_r1": present_r1,
            "present_r2": present_r2,
            "absent_r1": len(roster) - present_r1,
            "absent_r2": len(roster) - present_r2,
        },
    }


def save_marks(
    conn,
    session_id: int,
    marks: list[dict],
    *,
    source: str = "faculty",
    reason: str = "",
    actor: str = "",
) -> dict:
    """marks: [{student_id, round1?, round2?, note?}]

    QR chỉ ghi nhận lần đầu. Sửa một điểm danh đã có phải kèm lý do và được ghi nhật ký.
    """
    cur = conn.cursor()
    ensure_lesson_attendance_tables(cur)
    sess = get_session(conn, session_id)
    now = _now_iso()
    reason = (reason or "").strip()
    for item in marks or []:
        try:
            st_id = int(item.get("student_id"))
        except Exception:
            continue
        ok = cur.execute(
            "SELECT id FROM class_students WHERE id=? AND class_id=?",
            (st_id, sess["class_id"]),
        ).fetchone()
        if not ok:
            continue
        existing = cur.execute(
            "SELECT id, present, present_after_break, source_r1, source_r2 "
            "FROM attendance_marks WHERE attendance_session_id=? AND student_id=?",
            (session_id, st_id),
        ).fetchone()
        r1 = existing[1] if existing else 0
        r2 = existing[2] if existing else 0
        src1 = existing[3] if existing else None
        src2 = existing[4] if existing else None
        touch_r1 = "round1" in item
        touch_r2 = "round2" in item
        if touch_r1:
            r1 = 1 if item.get("round1") else 0
            src1 = source if r1 else None
        if touch_r2:
            r2 = 1 if item.get("round2") else 0
            src2 = source if r2 else None
        note = item.get("note")
        changed = bool(existing) and (
            (touch_r1 and int(r1 or 0) != int(existing[1] or 0))
            or (touch_r2 and int(r2 or 0) != int(existing[2] or 0))
        )
        if source == "qr" and existing:
            continue
        if changed and not (reason or str(item.get("reason") or "").strip()):
            raise ValueError("Sửa điểm danh đã có cần ghi lý do")
        if existing:
            cur.execute(
                "UPDATE attendance_marks SET present=?, present_after_break=?, "
                "check_in=?, check_out=?, source_r1=?, source_r2=?, "
                "marked_at_r1=CASE WHEN ? THEN ? ELSE marked_at_r1 END, "
                "marked_at_r2=CASE WHEN ? THEN ? ELSE marked_at_r2 END, "
                "note=COALESCE(?, note) WHERE id=?",
                (
                    r1,
                    r2,
                    float(r1),
                    float(r2),
                    src1,
                    src2,
                    1 if touch_r1 else 0,
                    now if touch_r1 else None,
                    1 if touch_r2 else 0,
                    now if touch_r2 else None,
                    note,
                    existing[0],
                ),
            )
            if changed:
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS ops_audit_log ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "created_at TEXT NOT NULL, actor TEXT, user_id INTEGER, "
                    "action TEXT NOT NULL, entity TEXT, entity_id TEXT, detail TEXT)"
                )
                cur.execute(
                    "INSERT INTO ops_audit_log (created_at, actor, action, entity, entity_id, detail) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        now,
                        actor or source,
                        "attendance_mark_edit",
                        "attendance_marks",
                        str(existing[0]),
                        f"session={session_id}; student={st_id}; "
                        f"r1 {existing[1]}→{r1}; r2 {existing[2]}→{r2}; "
                        f"reason={reason or item.get('reason') or ''}",
                    ),
                )
        else:
            cur.execute(
                "INSERT INTO attendance_marks "
                "(attendance_session_id, student_id, present, present_after_break, "
                "check_in, check_out, source_r1, source_r2, marked_at_r1, marked_at_r2, note) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    session_id,
                    st_id,
                    r1,
                    r2,
                    float(r1),
                    float(r2),
                    src1,
                    src2,
                    now if touch_r1 and r1 else None,
                    now if touch_r2 and r2 else None,
                    note or None,
                ),
            )
    _recalc_counts(cur, session_id)
    conn.commit()
    return get_roster(conn, session_id)


def rotate_qr_token(
    conn, session_id: int, round_no: int, *, created_by: str = "", public_base: str = ""
) -> dict:
    if round_no not in (1, 2):
        raise ValueError("round must be 1 or 2")
    cur = conn.cursor()
    ensure_lesson_attendance_tables(cur)
    sess = get_session(conn, session_id)
    open_flag = sess["round1_open"] if round_no == 1 else sess["round2_open"]
    if not open_flag:
        raise ValueError(f"Chưa mở điểm danh lần {round_no}")
    token = secrets.token_urlsafe(16)
    expires = (_now() + timedelta(seconds=QR_TTL_SEC)).isoformat() + "Z"
    cur.execute(
        "INSERT INTO attendance_qr_tokens "
        "(session_id, round, token_hash, token_plain, expires_at, created_by, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            session_id,
            round_no,
            _hash_token(token),
            token,
            expires,
            created_by or "",
            _now_iso(),
        ),
    )
    # prune old tokens for this session/round (keep last 5)
    old = cur.execute(
        "SELECT id FROM attendance_qr_tokens WHERE session_id=? AND round=? "
        "ORDER BY id DESC",
        (session_id, round_no),
    ).fetchall()
    for (oid,) in old[5:]:
        cur.execute("DELETE FROM attendance_qr_tokens WHERE id=?", (oid,))
    conn.commit()
    scan_path = f"/ops/attendance/scan?t={token}"
    scan_url = (public_base.rstrip("/") + scan_path) if public_base else scan_path
    return {
        "session_id": session_id,
        "round": round_no,
        "token": token,
        "expires_at": expires,
        "ttl_sec": QR_TTL_SEC,
        "rotate_every_sec": QR_ROTATE_EVERY_SEC,
        "scan_url": scan_url,
        "scan_path": scan_path,
        "session": sess,
    }


def scan_qr_checkin(
    conn,
    *,
    token: str,
    student_email: str,
    student_name: str = "",
) -> dict:
    cur = conn.cursor()
    ensure_lesson_attendance_tables(cur)
    token = (token or "").strip()
    if not token:
        raise ValueError("Thiếu mã QR")
    email = (student_email or "").strip().lower()
    if not email:
        raise ValueError("Cần đăng nhập tài khoản học viên")
    th = _hash_token(token)
    row = cur.execute(
        "SELECT id, session_id, round, expires_at FROM attendance_qr_tokens "
        "WHERE token_hash=?",
        (th,),
    ).fetchone()
    if not row:
        raise ValueError("Mã QR không hợp lệ hoặc đã hết hạn — hãy quét mã mới trên màn hình lớp")
    exp = row[3]
    try:
        exp_dt = datetime.fromisoformat(exp.replace("Z", ""))
    except Exception:
        exp_dt = _now() - timedelta(seconds=1)
    if exp_dt < _now():
        raise ValueError("Mã QR đã hết hạn — hãy quét mã mới trên màn hình lớp")
    session_id = row[1]
    round_no = int(row[2])
    sess = get_session(conn, session_id)
    if round_no == 1 and not sess["round1_open"]:
        raise ValueError("Điểm danh lần 1 đã đóng")
    if round_no == 2 and not sess["round2_open"]:
        raise ValueError("Điểm danh lần 2 đã đóng")
    st = cur.execute(
        "SELECT id, full_name FROM class_students "
        "WHERE class_id=? AND lower(IFNULL(email,''))=?",
        (sess["class_id"], email),
    ).fetchone()
    if not st:
        raise ValueError(
            "Email của bạn không có trong danh sách lớp này — chỉ học viên tại lớp mới điểm danh được"
        )
    # already marked this round?
    existing = cur.execute(
        "SELECT id, present, present_after_break FROM attendance_marks "
        "WHERE attendance_session_id=? AND student_id=?",
        (session_id, st[0]),
    ).fetchone()
    already = False
    if existing:
        already = True
    if already:
        return {
            "ok": True,
            "already": True,
            "message": "Đã có điểm danh cho buổi này. QR chỉ ghi nhận một lần, không thay điểm danh đã có.",
            "round": round_no,
            "session": sess,
            "student_name": st[1],
        }
    payload = {"student_id": st[0]}
    if round_no == 1:
        payload["round1"] = True
    else:
        payload["round2"] = True
    save_marks(conn, session_id, [payload], source="qr")
    return {
        "ok": True,
        "already": False,
        "message": f"Điểm danh lần {round_no} thành công",
        "round": round_no,
        "session": sess,
        "student_name": st[1] or student_name,
    }


def list_sessions_enriched(conn, scopes: list[str] | None) -> list[dict]:
    """Attendance list for teaching.attendance hub — include lesson link."""
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_lesson_attendance_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    rows = cur.execute(
        "SELECT ats.id, cg.name, cg.program_code, c.code, ats.session_no, "
        "ats.session_label, ats.session_date, ats.present_count, ats.absent_count, "
        "ats.lesson_id, IFNULL(ats.round1_open,0), IFNULL(ats.round2_open,0) "
        "FROM attendance_sessions ats "
        "JOIN teaching_assignments ta ON ta.id = ats.assignment_id "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        f"WHERE {frag} ORDER BY ats.session_date DESC, ats.id DESC LIMIT 200",
        params,
    ).fetchall()
    out = []
    for r in rows:
        sid = r[0]
        live = cur.execute(
            "SELECT COUNT(*), "
            "SUM(CASE WHEN COALESCE(present,0)=1 OR COALESCE(check_in,0)>0 "
            " OR COALESCE(present_after_break,0)=1 OR COALESCE(check_out,0)>0 THEN 1 ELSE 0 END) "
            "FROM attendance_marks WHERE attendance_session_id=?",
            (sid,),
        ).fetchone()
        present_either = int(live[1] or 0)
        class_size = cur.execute(
            "SELECT COUNT(*) FROM class_students cs "
            "JOIN teaching_assignments ta ON ta.class_id = cs.class_id "
            "JOIN attendance_sessions ats ON ats.assignment_id = ta.id "
            "WHERE ats.id=?",
            (sid,),
        ).fetchone()[0]
        absent = max(0, int(class_size or 0) - present_either)
        present_r1 = cur.execute(
            "SELECT COUNT(*) FROM attendance_marks WHERE attendance_session_id=? AND "
            "(COALESCE(present,0)=1 OR COALESCE(check_in,0)>0)",
            (sid,),
        ).fetchone()[0]
        present_r2 = cur.execute(
            "SELECT COUNT(*) FROM attendance_marks WHERE attendance_session_id=? AND "
            "(COALESCE(present_after_break,0)=1 OR COALESCE(check_out,0)>0)",
            (sid,),
        ).fetchone()[0]
        out.append(
            {
                "id": r[0],
                "class_name": r[1],
                "program_code": r[2],
                "course_code": r[3],
                "session_no": r[4],
                "session_label": r[5],
                "session_date": r[6],
                "present_count": present_either,
                "absent_count": absent,
                "present_r1": present_r1,
                "present_r2": present_r2,
                "lesson_id": r[9],
                "round1_open": bool(r[10]),
                "round2_open": bool(r[11]),
                "rounds_label": (
                    ("L1● " if r[10] else "L1○ ") + ("L2●" if r[11] else "L2○")
                ),
            }
        )
    return out


def list_student_attendance(conn, student_id: int, scopes: list[str] | None) -> list[dict]:
    """Buổi đã tham gia và buổi vắng của một học viên."""
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_lesson_attendance_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    params = [int(student_id), *params]
    rows = cur.execute(
        "SELECT ats.id, ats.session_date, cg.name, c.code, c.name, "
        "IFNULL(ats.session_label,''), IFNULL(ats.chapter,''), "
        "COALESCE(am.present,0), COALESCE(am.present_after_break, am.present, 0), "
        "IFNULL(am.excused,0) "
        "FROM attendance_marks am "
        "JOIN attendance_sessions ats ON ats.id = am.attendance_session_id "
        "JOIN teaching_assignments ta ON ta.id = ats.assignment_id "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        f"WHERE am.student_id = ? AND {frag} "
        "ORDER BY ats.session_date DESC, ats.id DESC",
        params,
    ).fetchall()
    attended = 0
    absent = 0
    parsed = []
    for r in rows:
        present = int(r[7] or 0) == 1 or int(r[8] or 0) == 1
        excused = int(r[9] or 0) == 1
        if present or excused:
            attended += 1
            mark = "Có mặt" if present else "Có phép"
        else:
            absent += 1
            mark = "Vắng"
        parsed.append((r, mark))
    return [
        {
            "id": r[0],
            "session_date": r[1] or "",
            "class_name": r[2] or "",
            "course_code": r[3] or "",
            "course_name": r[4] or "",
            "session_label": r[5] or "",
            "chapter": r[6] or r[5] or "",
            "attendance_mark": mark,
            "attended_total": attended,
            "absent_total": absent,
        }
        for r, mark in parsed
    ]
