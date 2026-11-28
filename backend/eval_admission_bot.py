"""Đánh giá UniBot tuyển sinh: bộ câu hỏi chấm hướng xử lý và nội dung, cộng kịch bản chuyển khách tiềm năng sang chuyên viên và CRM.

Chạy qua đúng luồng thật (handle_message, submit_contact) rồi xóa sạch dữ liệu thử.
Cách dùng: python eval_admission_bot.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

import admission_bot as ab

ANSWERED = {"faq", "llm", "extractive"}
TEST_PHONES = ("0987000111", "0987000222", "0987000333", "0987000444")
TEST_EMAIL = "khach.kiemthu@eval.test"


def passed(expect, mode: str) -> bool:
    if isinstance(expect, list):
        return any(passed(e, mode) for e in expect)
    if expect == "answer":
        return mode in ANSWERED
    return mode == expect


def content_ok(case: dict, answer: str) -> tuple[bool, str]:
    low = answer.lower()
    missing = [m for m in case.get("must", []) if m.lower() not in low]
    if missing:
        return False, f"thiếu {missing}"
    if case.get("must_any") and not any(m.lower() in low for m in case["must_any"]):
        return False, f"thiếu một trong {case['must_any']}"
    banned = [m for m in case.get("must_not", []) if m.lower() in low]
    if banned:
        return False, f"có nội dung sai {banned}"
    return True, ""


class Run:
    def __init__(self, conn):
        self.conn = conn
        self.sessions: list[str] = []

    def chat(self, text: str, session: str | None = None) -> tuple[dict, float]:
        session = session or f"eval-{uuid.uuid4().hex[:12]}"
        if session not in self.sessions:
            self.sessions.append(session)
        start = time.time()
        out = ab.handle_message(self.conn, session_key=session, text=text, page_url="/eval", client_ip="eval")
        return out, time.time() - start

    def cleanup(self) -> None:
        c = self.conn
        conv_ids = [r[0] for s in self.sessions for r in c.execute("SELECT id FROM bot_conversations WHERE session_key = ?", (s,))]
        marks = ",".join("?" * len(conv_ids)) or "NULL"
        phones = list(TEST_PHONES)
        profiles = {r[0] for r in c.execute(
            f"SELECT profile_id FROM consult_requests WHERE profile_id IS NOT NULL AND (conversation_id IN ({marks}) "
            f"OR phone IN ({','.join('?' * len(phones))}) OR lower(email) = ?)", [*conv_ids, *phones, TEST_EMAIL])}
        profiles |= {r[0] for r in c.execute(
            f"SELECT id FROM crm_source_profiles WHERE phone IN ({','.join('?' * len(phones))}) OR lower(email) = ?", [*phones, TEST_EMAIL])}
        profiles |= {r[0] for r in c.execute(f"SELECT profile_id FROM bot_conversations WHERE id IN ({marks}) AND profile_id IS NOT NULL", conv_ids)}
        c.execute(f"DELETE FROM consult_requests WHERE conversation_id IN ({marks}) OR phone IN ({','.join('?' * len(phones))}) OR lower(email) = ?",
                  [*conv_ids, *phones, TEST_EMAIL])
        for pid in profiles:
            for table in ("crm_reminders", "crm_care_log", "crm_activity_participants"):
                c.execute(f"DELETE FROM {table} WHERE profile_id = ?", (pid,))
            c.execute("DELETE FROM crm_source_profiles WHERE id = ?", (pid,))
        for table, col in (("bot_gaps", "conversation_id"), ("bot_messages", "conversation_id"), ("bot_conversations", "id")):
            c.execute(f"DELETE FROM {table} WHERE {col} IN ({marks})", conv_ids)
        c.commit()


def question_suite(run: Run, cases: list[dict]) -> list[dict]:
    results = []
    for case in cases:
        out, took = run.chat(case["q"])
        mode = out.get("mode") or ""
        reply = out.get("reply") or ""
        expect = case.get("expect", "answer")
        route_ok = passed(expect, mode)
        checked = any(k in case for k in ("must", "must_any", "must_not"))
        fine, note = content_ok(case, reply) if checked else (True, "")
        good = route_ok and fine
        if not route_ok:
            note = f"hướng xử lý sai, mong đợi {expect}" + (f"; {note}" if note else "")
        print(f"[{'ĐẠT' if good else 'SAI'}] {case['group']} · {case['q']}" + (f"  ({note})" if note else ""))
        print(f"      bot chọn {mode}, {took:.1f}s: {reply.replace(chr(10), ' / ')[:230]}")
        results.append({**case, "mode": mode, "route_ok": route_ok, "content_ok": fine, "checked": checked, "ok": good, "seconds": took})
    return results


def lead_flows(run: Run) -> list[bool]:
    c = run.conn
    checks: list[bool] = []

    def check(name: str, ok: bool, detail="") -> None:
        checks.append(ok)
        print(f"[{'ĐẠT' if ok else 'SAI'}] {name}" + (f"  ({detail})" if detail else ""))

    session = f"eval-{uuid.uuid4().hex[:12]}"
    run.chat("tôi đang làm logistics, quan tâm chương trình MSCM", session)
    second, _ = run.chat("học phí chương trình này bao nhiêu", session)
    check("Hỏi học phí thì bot mời để lại liên hệ, không đưa con số", second.get("ask_contact") and "triệu" not in second["reply"], second.get("mode"))
    third, _ = run.chat("tôi là Trần Thị Kiểm Thử, số điện thoại 0987000111", session)
    check("Khách để lại số điện thoại trong chat được ghi nhận", third.get("mode") == "contact" and third.get("crm_linked"), third.get("mode"))
    conv = ab.get_conversation(c, session_key=session)
    req = c.execute("SELECT * FROM consult_requests WHERE conversation_id = ? ORDER BY id DESC LIMIT 1", (conv["id"],)).fetchone()
    check("Tạo yêu cầu tư vấn gắn với hội thoại", req is not None)
    check("Yêu cầu được giao cho chuyên viên bộ phận tuyển sinh", bool(req and req["assigned_user_id"]), req and req["assigned_name"])
    check("Yêu cầu ghi nhận đúng chương trình khách quan tâm", bool(req and req["program"] == "MSCM"), req and req["program"])
    detail = ab.request_detail(c, req["id"]) if req else {}
    check("Chuyên viên xem được lịch sử khách đã hỏi bot", len([m for m in detail.get("messages", []) if m["role"] == "user"]) >= 3)
    profile = c.execute("SELECT * FROM crm_source_profiles WHERE id = ?", (req["profile_id"],)).fetchone() if req else None
    check("Tự tạo hồ sơ khách hàng tiềm năng trong CRM", bool(profile and profile["phone"] == "0987000111"), profile and profile["care_status"])
    reminder = c.execute("SELECT COUNT(*) FROM crm_reminders WHERE profile_id = ?", (req["profile_id"],)).fetchone()[0] if req else 0
    check("Tạo lịch nhắc chuyên viên liên hệ", reminder >= 1, reminder)
    check("Mức quan tâm của khách được chấm điểm", conv.get("lead_level") in ("medium", "high", "hot"), conv.get("lead_level"))

    form_session = f"eval-{uuid.uuid4().hex[:12]}"
    run.sessions.append(form_session)
    try:
        ab.submit_contact(c, session_key=form_session, data={"full_name": "Khách Form", "phone": "0987000222", "program": "MBA"})
        check("Form thiếu xác nhận đồng ý thì bị từ chối", False)
    except ValueError:
        check("Form thiếu xác nhận đồng ý thì bị từ chối", True)
    made = ab.submit_contact(c, session_key=form_session, data={"full_name": "Khách Form", "phone": "0987000222", "email": TEST_EMAIL, "program": "MBA", "consent": True})
    check("Form đăng ký tư vấn tạo yêu cầu và giao chuyên viên", made.get("ok") and made.get("assigned"), made.get("request_id"))
    again = ab.submit_contact(c, session_key=form_session, data={"full_name": "Khách Form", "phone": "0987000222", "program": "MBA", "consent": True})
    check("Đăng ký lại cùng số điện thoại không tạo yêu cầu trùng", again.get("duplicate") and again.get("request_id") == made.get("request_id"))

    handoff_session = f"eval-{uuid.uuid4().hex[:12]}"
    out, _ = run.chat("tôi muốn gặp tư vấn viên, gọi cho tôi số 0987000444", handoff_session)
    conv2 = ab.get_conversation(c, session_key=handoff_session)
    req2 = c.execute("SELECT id FROM consult_requests WHERE conversation_id = ?", (conv2["id"],)).fetchone()
    check("Khách đòi gặp tư vấn viên kèm số điện thoại: chuyển ngay và tạo yêu cầu", out.get("mode") == "handoff" and req2 is not None, out.get("mode"))

    gap_session = f"eval-{uuid.uuid4().hex[:12]}"
    run.chat("trung tâm có chỗ gửi xe ô tô cho học viên không", gap_session)
    conv3 = ab.get_conversation(c, session_key=gap_session)
    gaps = c.execute("SELECT COUNT(*) FROM bot_gaps WHERE conversation_id = ?", (conv3["id"],)).fetchone()[0]
    check("Câu bot chưa trả lời được đưa vào danh sách cần bổ sung kho kiến thức", gaps >= 1, gaps)

    _clean, hidden = ab.redact_personal("Liên hệ chị Lan 0912345678 hoặc lan@example.com, CCCD 001234567890")
    check("Kho kiến thức công khai tự ẩn số điện thoại, email, số giấy tờ", hidden >= 3, hidden)
    return checks


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    conn = sqlite3.connect(HERE / "db" / "website.db", timeout=30)
    conn.row_factory = sqlite3.Row
    ab.ensure_bot_tables(conn.cursor())
    ab.bootstrap(conn, HERE / "data")
    conn.commit()
    run = Run(conn)
    try:
        print("=== Bộ câu hỏi UniBot tuyển sinh ===")
        cases = json.loads((HERE / "data" / "admission_kb" / "eval_questions.json").read_text(encoding="utf-8"))
        results = question_suite(run, cases)
        print("\n=== Luồng chuyển khách tiềm năng ===")
        checks = lead_flows(run)
    finally:
        run.cleanup()
    ok = sum(r["ok"] for r in results)
    checked = [r for r in results if r["checked"]]
    print(f"\nBộ câu hỏi: {ok}/{len(results)} câu đạt hoàn toàn; {sum(r['route_ok'] for r in results)}/{len(results)} đúng hướng xử lý; "
          f"{sum(r['content_ok'] for r in checked)}/{len(checked)} đúng nội dung.")
    groups: dict = defaultdict(list)
    for r in results:
        groups[r["group"]].append(r)
    print("  Theo nhóm:")
    for name, rows in groups.items():
        print(f"    {name:<14} {sum(r['ok'] for r in rows)}/{len(rows)}")
    modes: dict = defaultdict(list)
    for r in results:
        modes[r["mode"]].append(r["seconds"])
    print("  Theo cách trả lời:")
    for mode, secs in sorted(modes.items(), key=lambda kv: -len(kv[1])):
        print(f"    {mode:<12} {len(secs):>3} câu, trung bình {sum(secs) / len(secs):.1f}s")
    print(f"Luồng chuyển khách tiềm năng: {sum(checks)}/{len(checks)} bước đạt.")


if __name__ == "__main__":
    main()
