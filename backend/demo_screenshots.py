"""Tự chạy hành trình người học trên trình duyệt thật và chụp ảnh màn hình từng bước cho báo cáo.

Cần backend (8026), frontend (8027), Ollama đang chạy và Google Chrome.
Cách dùng: python demo_screenshots.py            chạy, chụp ảnh, xóa dữ liệu thử
           python demo_screenshots.py --keep     giữ lại học viên vừa tạo
           python demo_screenshots.py --show     mở cửa sổ trình duyệt để xem trực tiếp
Ảnh và chú thích lưu ở docs/screenshots/<ngày giờ>/ (README.md liệt kê theo thứ tự).
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

import eval_full_journey as j
import lesson_attendance as la

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots" / datetime.now().strftime("%Y%m%d-%H%M")
CAPTIONS: list[tuple[str, str]] = []
DEMO_STUDENT = "E2eMscm"


def shot(page, name: str, caption: str) -> None:
    page.wait_for_timeout(600)
    path = OUT / f"{len(CAPTIONS) + 1:02d}_{name}.png"
    page.screenshot(path=str(path), full_page=False)
    CAPTIONS.append((path.name, caption))
    print(f"  ảnh {path.name}: {caption}")


def login(browser, user: str, password: str = "123!"):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="vi-VN")
    page = ctx.new_page()
    page.goto(j.WEB + "/login")
    page.fill("#email", user)
    page.fill("#password", password)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    return page


def wait_bot(page, selector: str, before: int, timeout: int = 180_000) -> None:
    page.wait_for_function(
        "([sel, n]) => document.querySelectorAll(sel).length > n", arg=[selector, before], timeout=timeout
    )
    page.wait_for_timeout(400)


def widget_ask(page, text: str) -> None:
    sel = "#messages .row.bot:not(.typing)"
    before = page.locator(sel).count()
    page.fill("#input", text)
    page.click("#send")
    wait_bot(page, sel, before)


def student_ask(page, text: str) -> None:
    sel = "#sb-msgs .sb-row.bot"
    before = page.locator(sel).count()
    page.fill("#sb-input", text)
    page.click("#sb-send")
    wait_bot(page, sel, before)


def open_module(page, path: str, query: str) -> None:
    page.goto(f"{j.WEB}{path}?q={query}")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(800)


def run(browser) -> None:
    j.created["session"] = ""
    j.created["cccd"] = "0990" + str(uuid.uuid4().int)[:8]
    name = "Nguyễn Hành Trình"

    print("1. Khách tìm hiểu và để lại liên hệ")
    guest = browser.new_context(viewport={"width": 1440, "height": 900}, locale="vi-VN").new_page()
    guest.goto(j.WEB + "/")
    guest.wait_for_load_state("networkidle")
    shot(guest, "trang_gioi_thieu", "Trang giới thiệu công khai của trung tâm, có icon UniBot tuyển sinh ở góc phải")
    guest.set_viewport_size({"width": 480, "height": 820})
    guest.goto(j.WEB + "/tu-van/widget")
    guest.wait_for_load_state("networkidle")
    widget_ask(guest, "Chương trình MBA dành cho ai?")
    shot(guest, "unibot_tuyen_sinh_tra_loi", "Khách hỏi UniBot tuyển sinh, bot trả lời từ kho kiến thức đã duyệt")
    widget_ask(guest, "Học phí MBA bao nhiêu?")
    shot(guest, "unibot_khong_bia_hoc_phi", "Hỏi học phí: bot không đưa con số, mời đăng ký tư vấn")
    widget_ask(guest, f"Tôi là {name}, {j.PHONE}, {j.EMAIL}")
    shot(guest, "khach_de_lai_lien_he", "Khách để lại liên hệ trong khung chat, hệ thống tạo yêu cầu tư vấn")

    print("2. Chuyên viên tuyển sinh tiếp nhận và lập hồ sơ ứng tuyển")
    staff = login(browser, j.CONSULTANT)
    staff.goto(j.WEB + "/ops/tuyen-sinh/chatbot#requests")
    staff.wait_for_load_state("networkidle")
    staff.locator("#req-list .cb-item", has_text=name).first.click()
    staff.wait_for_selector("[data-act=apply]")
    shot(staff, "yeu_cau_tu_van", "Chuyên viên tuyển sinh thấy yêu cầu tư vấn kèm lịch sử khách đã hỏi UniBot")
    staff.once("dialog", lambda d: d.accept(j.created["cccd"]))
    staff.click("[data-act=apply]")
    staff.wait_for_selector("text=Đã có hồ sơ ứng tuyển", timeout=30_000)
    shot(staff, "lap_ho_so_ung_tuyen", "Bấm Tạo hồ sơ ứng tuyển: yêu cầu chuyển sang Đã nộp hồ sơ, gắn số hồ sơ")
    with j.db() as conn:
        app_id = conn.execute("SELECT id FROM applications WHERE phone = ? ORDER BY id DESC LIMIT 1", (j.PHONE,)).fetchone()[0]
    j.created["applications"] = [app_id]
    open_module(staff, "/ops/admissions/crm-source", j.PHONE)
    shot(staff, "crm_da_tao_ho_so", "Hồ sơ khách trong CRM tự chuyển sang Đã tạo hồ sơ TS")
    j.call("POST", f"/ops/applications/{app_id}/status", j.CONSULTANT, {"status": "approved_ts"})

    print("3. Điều phối phỏng vấn và kết luận trúng tuyển")
    coord = login(browser, j.COORDINATOR)
    j.call("POST", f"/ops/applications/{app_id}/status", j.COORDINATOR, {"status": "interview"})
    j.call("PATCH", f"/ops/applications/{app_id}", j.COORDINATOR, {"written_score": 14.5, "interview_score": 15.5})
    j.call("POST", f"/ops/applications/{app_id}/status", j.COORDINATOR, {"status": "passed"})
    open_module(coord, "/ops/admissions/applications", j.created["cccd"])
    shot(coord, "ho_so_trung_tuyen", "Điều phối nhập điểm thi viết, phỏng vấn và kết luận trúng tuyển")

    print("4. Kế toán thu phí ghi danh và chốt nhập học")
    acc = login(browser, j.ACCOUNTANT)
    with j.db() as conn:
        fee_id = conn.execute("SELECT id FROM enrollment_fees WHERE application_id = ?", (app_id,)).fetchone()[0]
    j.call("POST", f"/ops/fees/{fee_id}/mark-paid", j.ACCOUNTANT, {"proof_note": "Chuyển khoản", "bank_ref": "DEMO"})
    j.call("POST", f"/ops/fees/{fee_id}/mark-official", j.ACCOUNTANT)
    open_module(acc, "/ops/accounting/fees", j.created["cccd"])
    shot(acc, "ke_toan_chot_nhap_hoc", "Kế toán xác nhận đã thu phí ghi danh và chốt nhập học chính thức")

    print("5. Xếp lớp, hệ thống tạo tài khoản học viên")
    class_name = f"MBA Hanh trinh {uuid.uuid4().hex[:4].upper()}"
    _code, out = j.call("POST", "/ops/classes", j.COORDINATOR, {"name": class_name, "program_code": "MBA", "enroll_official": True})
    j.created["class_id"] = out.get("id") or out.get("class_id")
    open_module(coord, "/ops/students", "Hành Trình")
    shot(coord, "xep_lop_cap_ma", "Điều phối xếp lớp: hệ thống cấp mã học viên và tạo tài khoản cổng học viên")
    with j.db() as conn:
        st = conn.execute("SELECT id, student_code, portal_user_id FROM class_students WHERE application_id = ?", (app_id,)).fetchone()
        login_id = conn.execute("SELECT email FROM user WHERE id = ?", (st["portal_user_id"],)).fetchone()[0]
        body = conn.execute("SELECT body FROM email_outbox WHERE recipient = ? ORDER BY id DESC LIMIT 1", (j.EMAIL,)).fetchone()[0]
    j.created["user_id"] = st["portal_user_id"]
    temp = body.split("Mật khẩu tạm: ")[1].split()[0]

    print("6. Học viên đăng nhập lần đầu và hỏi UniBot")
    learner = browser.new_context(viewport={"width": 1440, "height": 900}, locale="vi-VN").new_page()
    learner.goto(j.WEB + "/login")
    learner.fill("#email", login_id)
    learner.fill("#password", temp)
    learner.click("button[type=submit]")
    learner.wait_for_load_state("networkidle")
    shot(learner, "bat_doi_mat_khau", "Đăng nhập lần đầu bằng mật khẩu tạm: hệ thống bắt đổi mật khẩu")
    learner.fill("input[name=current_password]", temp)
    learner.fill("input[name=new_password]", j.NEW_PASSWORD)
    learner.fill("input[name=confirm_password]", j.NEW_PASSWORD)
    learner.click("button[type=submit]")
    learner.wait_for_load_state("networkidle")
    learner.click("#sb-launch")
    learner.wait_for_selector("#sb-panel")
    learner.wait_for_timeout(1500)
    shot(learner, "unibot_hoc_vien_moi", "Học viên mới vào cổng học viên, mở UniBot")
    student_ask(learner, "Tôi còn những khoản học phí nào chưa đóng?")
    shot(learner, "bot_hoc_phi_hoc_vien_moi", "UniBot trả lời học phí đúng của chính học viên mới")
    student_ask(learner, "Điểm thi viết và phỏng vấn của tôi")
    shot(learner, "bot_ho_so_dau_vao", "UniBot đọc hồ sơ đầu vào: điểm thi viết và phỏng vấn của người này")

    print("7. Buổi học đầu tiên: điểm danh QR")
    with j.db() as conn:
        course = conn.execute(
            "SELECT c.id FROM courses c JOIN class_groups cg ON cg.program_version_id = c.program_version_id WHERE cg.id = ? ORDER BY c.sort_order LIMIT 1",
            (j.created["class_id"],),
        ).fetchone()
        conn.execute("INSERT INTO teaching_assignments (class_id, course_id, status) VALUES (?, ?, 'in_teaching')", (j.created["class_id"], course["id"]))
        ta = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            "INSERT INTO class_lessons (assignment_id, lesson_no, title, lesson_type, lesson_date, status) VALUES (?, 1, 'Buổi khai giảng', 'offline', ?, 'published')",
            (ta, date.today().isoformat()),
        )
        lesson = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        sid = la.ensure_session_for_lesson(conn, lesson)["id"]
        la.set_round_open(conn, sid, 1, True)
        conn.commit()
    coord.goto(f"{j.WEB}/ops/attendance/sessions/{sid}")
    coord.wait_for_load_state("networkidle")
    coord.click("#btn-qr-r1")
    coord.wait_for_timeout(1500)
    shot(coord, "chieu_ma_qr", "Giảng viên hoặc điều phối chiếu mã QR điểm danh lần 1, mã tự đổi liên tục")
    with j.db() as conn:
        token = la.rotate_qr_token(conn, sid, 1, created_by="demo", public_base="")["token"]
        conn.commit()
    learner.goto(f"{j.WEB}/ops/attendance/scan?t={token}")
    learner.wait_for_load_state("networkidle")
    shot(learner, "hoc_vien_quet_qr", "Học viên đã đăng nhập quét mã: điểm danh thành công")

    print("8. Trình diễn UniBot trên tài khoản học viên nhiều tình huống")
    demo = login(browser, DEMO_STUDENT)
    demo.click("#sb-launch")
    demo.wait_for_selector("#sb-panel")
    demo.wait_for_timeout(1500)
    shot(demo, "can_chu_y", "UniBot tự nhắc việc: học phí quá hạn, lịch thi lại, buổi học hôm nay")
    for i, (q, cap) in enumerate((
        ("Tôi có môn nào bị trượt không?", "Môn chưa đạt kèm lịch thi lại"),
        ("Tôi có học bổng không?", "Học bổng 50%: học phí gốc, phần được giảm, phần còn phải đóng"),
        ("Did I fail any course?", "Hỏi tiếng Anh, bot trả lời tiếng Anh ngay"),
        ("Điểm thi lại của tôi là bao nhiêu?", "Câu bẫy: chưa thi nên bot không bịa điểm"),
    ), start=1):
        student_ask(demo, q)
        shot(demo, f"demo_{i}", cap)
    j.call("POST", "/student/bot/reset", DEMO_STUDENT, {})


def write_readme() -> None:
    lines = ["# Ảnh chụp hành trình người học", "", f"Chụp tự động lúc {datetime.now():%H:%M %d/%m/%Y} bằng `python backend/demo_screenshots.py`.", ""]
    for i, (file, caption) in enumerate(CAPTIONS, start=1):
        lines += [f"## {i}. {caption}", "", f"![{caption}]({file})", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    keep = "--keep" in sys.argv
    j.cleanup()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless="--show" not in sys.argv, slow_mo=150 if "--show" in sys.argv else 0)
        try:
            run(browser)
        finally:
            browser.close()
            write_readme()
            if not keep:
                j.cleanup()
    print(f"\nĐã chụp {len(CAPTIONS)} ảnh, lưu ở {OUT}")


if __name__ == "__main__":
    main()
