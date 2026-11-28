"""Kiểm thử hành trình đầy đủ của một người học, qua đúng API và đúng bộ phận phụ trách từng bước:
khách hỏi UniBot và để lại liên hệ → chuyên viên tuyển sinh tiếp nhận, lập hồ sơ ứng tuyển → điều phối phỏng vấn, kết luận trúng tuyển
→ kế toán thu phí ghi danh, chốt nhập học → điều phối xếp lớp, hệ thống tạo tài khoản và gửi email → học viên đăng nhập, đổi mật khẩu,
hỏi UniBot → điểm danh bằng mã QR.

Cần backend (8026) và frontend (8027) đang chạy.
Cách dùng: python eval_full_journey.py          chạy rồi xóa sạch dữ liệu thử
           python eval_full_journey.py --keep   giữ lại tài khoản học viên vừa tạo để trình diễn
"""

from __future__ import annotations

import re
import sqlite3
import sys
import uuid
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

API = "http://127.0.0.1:8026"
WEB = "http://127.0.0.1:8027"
DB = HERE / "db" / "website.db"
CONSULTANT, COORDINATOR, ACCOUNTANT = "NhungLH", "HaLP", "HanhNT"
PHONE, EMAIL = "0987000555", "hanh.trinh@eval.test"
NEW_PASSWORD = "HanhTrinh2026"

results: list[bool] = []
created: dict = {"session": "", "applications": [], "class_id": None, "user_id": None, "lesson_id": None, "cccd": ""}


def check(name: str, ok: bool, detail="") -> bool:
    results.append(bool(ok))
    print(f"[{'ĐẠT' if ok else 'SAI'}] {name}" + (f"  ({detail})" if detail not in ("", None) else ""))
    return bool(ok)


def db():
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def user_id(login: str) -> int:
    with db() as conn:
        return conn.execute("SELECT id FROM user WHERE email = ?", (login,)).fetchone()[0]


def call(method: str, path: str, login: str | None = None, body=None):
    headers = {"X-User-Id": str(user_id(login))} if login else {}
    r = requests.request(method, API + path, json=body, headers=headers, timeout=180)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


def journey() -> None:
    session = f"eval-journey-{uuid.uuid4().hex[:8]}"
    created["session"] = session
    created["cccd"] = "0990" + uuid.uuid4().int.__str__()[:8]

    print("== 1. Khách hỏi UniBot tuyển sinh và để lại liên hệ")
    call("POST", "/bot/public/chat", body={"message": "Tôi đang làm quản lý, quan tâm chương trình MBA", "session": session})
    code, out = call("POST", "/bot/public/chat", body={"message": f"Tôi là Nguyễn Hành Trình, {PHONE}, {EMAIL}", "session": session})
    check("UniBot ghi nhận liên hệ của khách", code == 200 and out.get("mode") == "contact", out.get("mode"))
    with db() as conn:
        req = conn.execute("SELECT * FROM consult_requests WHERE phone = ? ORDER BY id DESC LIMIT 1", (PHONE,)).fetchone()
    if not check("Hệ thống tạo yêu cầu tư vấn và giao cho chuyên viên tuyển sinh", req is not None and req["assigned_user_id"], req and req["assigned_name"]):
        return

    print("\n== 2. Chuyên viên tuyển sinh tiếp nhận và lập hồ sơ ứng tuyển")
    code, detail = call("GET", f"/ops/chatbot/requests/{req['id']}", CONSULTANT)
    check("Chuyên viên thấy yêu cầu kèm lịch sử khách đã hỏi bot", code == 200 and len([m for m in detail.get("messages", []) if m["role"] == "user"]) >= 2)
    code, out = call("POST", f"/ops/chatbot/requests/{req['id']}/application", CONSULTANT, {"cccd": created["cccd"], "programs": "MBA"})
    apps = out.get("applications") or []
    created["applications"] = [a["id"] for a in apps]
    if not check("Lập hồ sơ ứng tuyển ngay từ yêu cầu tư vấn", code == 201 and apps, out.get("error") or [a["id"] for a in apps]):
        return
    app_id = apps[0]["id"]
    with db() as conn:
        req2 = conn.execute("SELECT status, application_id FROM consult_requests WHERE id = ?", (req["id"],)).fetchone()
        prof = conn.execute("SELECT care_status, application_id FROM crm_source_profiles WHERE phone = ?", (PHONE,)).fetchone()
    check("Yêu cầu tư vấn tự chuyển sang Đã nộp hồ sơ, gắn số hồ sơ", req2["status"] == "converted" and req2["application_id"] == app_id, tuple(req2))
    check("Hồ sơ CRM tự chuyển sang Đã tạo hồ sơ TS", prof is not None and prof["care_status"] == "handed_ts" and prof["application_id"] == app_id, prof and tuple(prof))
    code, _ = call("POST", f"/ops/applications/{app_id}/status", CONSULTANT, {"status": "approved_ts"})
    check("Tuyển sinh duyệt hồ sơ, chuyển cho điều phối", code == 200, code)
    code, _ = call("POST", f"/ops/applications/{app_id}/status", CONSULTANT, {"status": "interview"})
    check("Tuyển sinh không được làm thay bước của điều phối", code == 403, code)

    print("\n== 3. Điều phối xếp phỏng vấn, nhập điểm, kết luận trúng tuyển")
    code, _ = call("POST", f"/ops/applications/{app_id}/status", COORDINATOR, {"status": "interview"})
    check("Điều phối nhận hồ sơ, xếp phỏng vấn", code == 200, code)
    code, out = call("PATCH", f"/ops/applications/{app_id}", COORDINATOR, {"written_score": 14.5, "interview_score": 15.5})
    check("Nhập điểm thi viết và điểm phỏng vấn", code == 200, out.get("error") or code)
    code, out = call("POST", f"/ops/applications/{app_id}/status", COORDINATOR, {"status": "passed"})
    check("Kết luận trúng tuyển", code == 200, out.get("error") or code)
    with db() as conn:
        fee = conn.execute("SELECT id, status FROM enrollment_fees WHERE application_id = ?", (app_id,)).fetchone()
    if not check("Trúng tuyển thì hệ thống tự sinh khoản phí ghi danh", fee is not None, fee and fee["status"]):
        return

    print("\n== 4. Kế toán thu phí ghi danh, chốt nhập học chính thức")
    code, _ = call("POST", f"/ops/fees/{fee['id']}/mark-paid", COORDINATOR, {"proof_note": "thử"})
    check("Điều phối không được xác nhận thu tiền", code == 403, code)
    code, out = call("POST", f"/ops/fees/{fee['id']}/mark-paid", ACCOUNTANT, {"proof_note": "Chuyển khoản", "bank_ref": "EVAL"})
    check("Kế toán xác nhận đã thu phí ghi danh", code == 200, out.get("error") or code)
    code, out = call("POST", f"/ops/fees/{fee['id']}/mark-official", ACCOUNTANT)
    check("Kế toán chốt nhập học chính thức", code == 200, out.get("error") or code)
    with db() as conn:
        status = conn.execute("SELECT status FROM applications WHERE id = ?", (app_id,)).fetchone()[0]
        tuition = conn.execute("SELECT COUNT(*) FROM student_charges WHERE application_id = ? AND fee_type = 'tuition'", (app_id,)).fetchone()[0]
    check("Hồ sơ ở trạng thái official và đã mở các đợt học phí", status == "official" and tuition >= 1, (status, tuition))

    print("\n== 5. Điều phối xếp lớp, hệ thống tạo học viên và tài khoản")
    class_name = f"MBA Hanh trinh {uuid.uuid4().hex[:4].upper()}"
    code, out = call("POST", "/ops/classes", COORDINATOR, {"name": class_name, "program_code": "MBA", "enroll_official": True})
    created["class_id"] = out.get("id") or out.get("class_id")
    check("Tạo lớp và đưa hồ sơ official vào lớp", code == 201 and created["class_id"], out.get("error") or out.get("handoff"))
    with db() as conn:
        student = conn.execute("SELECT id, student_code, portal_user_id, email FROM class_students WHERE application_id = ?", (app_id,)).fetchone()
        account = conn.execute("SELECT id, email, must_change_password FROM user WHERE id = ?", (student["portal_user_id"],)).fetchone() if student else None
        mail = conn.execute("SELECT body FROM email_outbox WHERE recipient = ? AND kind = 'student_account' ORDER BY id DESC LIMIT 1", (EMAIL,)).fetchone()
    if not check("Có mã học viên và tài khoản cổng học viên, bắt đổi mật khẩu lần đầu", student and account and account["must_change_password"] == 1,
                 student and student["student_code"]):
        return
    created["user_id"] = account["id"]
    temp = re.search(r"Mật khẩu tạm: (\S+)", mail["body"]).group(1) if mail else ""
    check("Email báo tài khoản đã vào hàng đợi, có tên đăng nhập và mật khẩu tạm", bool(temp) and account["email"] in mail["body"])

    print("\n== 6. Học viên đăng nhập lần đầu, đổi mật khẩu, hỏi UniBot")
    web = requests.Session()
    r = web.post(WEB + "/login", data={"email": account["email"], "password": temp}, allow_redirects=False, timeout=30)
    check("Đăng nhập bằng mật khẩu tạm thì bị chuyển sang đổi mật khẩu", "/account/password" in r.headers.get("Location", ""), r.headers.get("Location"))
    web.post(WEB + "/account/password", data={"current_password": temp, "new_password": NEW_PASSWORD, "confirm_password": NEW_PASSWORD}, timeout=30)
    r = web.get(WEB + "/ops", allow_redirects=False, timeout=30)
    check("Đổi xong vào được cổng học viên, có UniBot", r.status_code == 200 and "sb-root" in r.text, r.status_code)
    code, out = call("POST", "/student/bot/chat", account["email"], {"text": "Tôi còn những khoản học phí nào chưa đóng?"})
    reply = (out.get("message") or {}).get("content", "")
    check("UniBot trả lời học phí đúng của học viên mới", code == 200 and "Học phí kỳ 1" in reply, reply[:90])
    code, out = call("POST", "/student/bot/chat", account["email"], {"text": "Điểm thi viết và phỏng vấn của tôi"})
    reply = (out.get("message") or {}).get("content", "")
    check("UniBot đọc được hồ sơ đầu vào của chính người này", "14.5" in reply and "15.5" in reply, reply[:90])
    code, out = call("POST", "/student/bot/chat", account["email"], {"text": "Mã học viên của tôi là gì?"})
    reply = (out.get("message") or {}).get("content", "")
    check("UniBot trả lời đúng mã học viên vừa cấp", student["student_code"] in reply, reply[:90])

    print("\n== 7. Buổi học đầu tiên: điểm danh bằng mã QR")
    import lesson_attendance as la

    with db() as conn:
        course = conn.execute(
            "SELECT c.id FROM courses c JOIN class_groups cg ON cg.program_version_id = c.program_version_id "
            "WHERE cg.id = ? ORDER BY c.sort_order LIMIT 1", (created["class_id"],),
        ).fetchone()
        conn.execute("INSERT INTO teaching_assignments (class_id, course_id, status) VALUES (?, ?, 'in_teaching')", (created["class_id"], course["id"]))
        ta_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO class_lessons (assignment_id, lesson_no, title, lesson_type, lesson_date, status) VALUES (?, 1, 'Buổi khai giảng', 'offline', ?, 'published')",
            (ta_id, date.today().isoformat()),
        )
        created["lesson_id"] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        sid = la.ensure_session_for_lesson(conn, created["lesson_id"])["id"]
        la.set_round_open(conn, sid, 1, True)
        token = la.rotate_qr_token(conn, sid, 1, created_by="eval", public_base="")["token"]
        conn.commit()
    r = web.get(WEB + "/ops/attendance/scan", params={"t": token}, timeout=30)
    check("Học viên mới quét QR điểm danh thành công", "Điểm danh lần 1 thành công" in r.text)
    with db() as conn:
        mark = conn.execute("SELECT present, source_r1 FROM attendance_marks WHERE attendance_session_id = ? AND student_id = ?", (sid, student["id"])).fetchone()
    check("Điểm danh được ghi vào sổ của lớp", mark is not None and mark["present"] == 1 and mark["source_r1"] == "qr", mark and tuple(mark))


def cleanup() -> None:
    conn = db()
    cur = conn.cursor()
    apps = created["applications"] or [r[0] for r in cur.execute("SELECT id FROM applications WHERE phone = ?", (PHONE,))]
    marks = ",".join("?" * len(apps)) or "NULL"
    students = [r[0] for r in cur.execute(f"SELECT id FROM class_students WHERE application_id IN ({marks})", apps)]
    smarks = ",".join("?" * len(students)) or "NULL"
    if created["class_id"]:
        tas = [r[0] for r in cur.execute("SELECT id FROM teaching_assignments WHERE class_id = ?", (created["class_id"],))]
        for ta in tas:
            for (sid,) in cur.execute("SELECT id FROM attendance_sessions WHERE assignment_id = ?", (ta,)).fetchall():
                cur.execute("DELETE FROM attendance_marks WHERE attendance_session_id = ?", (sid,))
                cur.execute("DELETE FROM attendance_qr_tokens WHERE session_id = ?", (sid,))
            cur.execute("DELETE FROM attendance_sessions WHERE assignment_id = ?", (ta,))
            cur.execute("DELETE FROM class_lessons WHERE assignment_id = ?", (ta,))
        cur.execute("DELETE FROM teaching_assignments WHERE class_id = ?", (created["class_id"],))
    users = {r[0] for r in cur.execute(f"SELECT portal_user_id FROM class_students WHERE id IN ({smarks}) AND portal_user_id IS NOT NULL", students)}
    users |= {r[0] for r in cur.execute(f"SELECT portal_user_id FROM applications WHERE id IN ({marks}) AND portal_user_id IS NOT NULL", apps)}
    for uid in users:
        for table in ("user_departments", "user_program_scopes", "student_bot_messages", "student_support_requests"):
            cur.execute(f"DELETE FROM {table} WHERE user_id = ?", (uid,))
        cur.execute("DELETE FROM user WHERE id = ?", (uid,))
    cur.execute(f"DELETE FROM course_grades WHERE student_id IN ({smarks})", students)
    cur.execute(f"DELETE FROM class_students WHERE id IN ({smarks})", students)
    if created["class_id"]:
        cur.execute("DELETE FROM class_groups WHERE id = ?", (created["class_id"],))
    for table in ("fee_payments", "student_charges", "enrollment_fees", "learners", "interview_slots"):
        try:
            if table == "fee_payments":
                cur.execute(f"DELETE FROM fee_payments WHERE charge_id IN (SELECT id FROM student_charges WHERE application_id IN ({marks}))", apps)
            else:
                cur.execute(f"DELETE FROM {table} WHERE application_id IN ({marks})", apps)
        except sqlite3.OperationalError:
            pass
    profiles = [r[0] for r in cur.execute("SELECT id FROM crm_source_profiles WHERE phone = ? OR lower(email) = ?", (PHONE, EMAIL))]
    for pid in profiles:
        for table in ("crm_reminders", "crm_care_log", "crm_activity_participants"):
            cur.execute(f"DELETE FROM {table} WHERE profile_id = ?", (pid,))
        cur.execute("DELETE FROM crm_source_profiles WHERE id = ?", (pid,))
    cur.execute("DELETE FROM consult_requests WHERE phone = ? OR lower(email) = ?", (PHONE, EMAIL))
    convs = [r[0] for r in cur.execute("SELECT id FROM bot_conversations WHERE session_key = ? OR phone = ?", (created["session"], PHONE))]
    for cid in convs:
        for table, col in (("bot_messages", "conversation_id"), ("bot_gaps", "conversation_id"), ("bot_conversations", "id")):
            cur.execute(f"DELETE FROM {table} WHERE {col} = ?", (cid,))
    cur.execute("DELETE FROM email_outbox WHERE recipient = ?", (EMAIL,))
    cur.execute(f"DELETE FROM applications WHERE id IN ({marks})", apps)
    try:
        cur.execute("DELETE FROM persons WHERE cccd = ?", (created["cccd"],))
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(HERE))
    keep = "--keep" in sys.argv
    cleanup()
    try:
        journey()
    finally:
        if keep and created["user_id"]:
            with db() as conn:
                login = conn.execute("SELECT email FROM user WHERE id = ?", (created["user_id"],)).fetchone()[0]
            print(f"\nĐã giữ lại tài khoản học viên {login} / {NEW_PASSWORD} để trình diễn.")
        else:
            cleanup()
    print(f"\nKết quả: {sum(results)}/{len(results)} bước đạt.")


if __name__ == "__main__":
    main()
