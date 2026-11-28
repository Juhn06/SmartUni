"""Sinh dữ liệu huấn luyện LoRA cho UniBot học viên: hồ sơ giả định, câu hỏi đa dạng, đáp án do code tính.

Cách dùng: python training/gen_dataset.py --train 2000 --val 150
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import admission_bot as ab
import student_bot as sb

OUT_DIR = ROOT / "training" / "data"
KB_DIR = ROOT / "backend" / "data" / "student_kb"

SURNAMES = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Ngô", "Dương", "Lý", "Phan", "Võ", "Trịnh"]
MIDDLES = ["Văn", "Thị", "Minh", "Thu", "Quốc", "Hải", "Ngọc", "Đức", "Thanh", "Gia", "Hoài", "Bảo"]
GIVENS = ["An", "Bình", "Chi", "Dũng", "Giang", "Hà", "Hùng", "Khánh", "Lan", "Long", "Mai", "Nam", "Phương", "Quân", "Sơn", "Trang", "Tuấn", "Vy", "Yến", "Hiếu", "Linh", "Thảo"]
CATALOG = {
    "MBA": (["MB", "QT", "BA"], [
        "Leadership", "Corporate Finance", "Business Game", "Marketing Management", "Operations Management",
        "Strategic Management", "Accounting for Managers", "Business Ethics", "Organizational Behavior", "Negotiation",
        "Quản trị chiến lược", "Kinh tế quản lý", "Phương pháp nghiên cứu", "Quản trị nhân sự",
    ]),
    "MMS": (["MM", "MK", "MS"], [
        "Consumer Behavior", "Digital Marketing", "Sales Management", "Brand Management", "Market Research",
        "Pricing Strategy", "B2B Marketing", "Hành vi khách hàng", "Truyền thông tích hợp", "Quản trị kênh phân phối",
    ]),
    "MSCM": (["SC", "LG", "CM"], [
        "Logistics Management", "Procurement", "Inventory Planning", "Supply Chain Analytics", "Warehouse Operations",
        "Transport Management", "Supplier Relationship", "Quản trị mua hàng", "Dự báo nhu cầu", "Quản trị rủi ro chuỗi cung ứng",
    ]),
}
PROGRESS_LABELS = {"completed": "Đã học xong", "studying": "Đang học", "scheduled": "Sắp học", "not_started": "Chưa học"}
STATUS_PHRASE = {"completed": "đã học xong", "studying": "đang học", "scheduled": "chưa học", "not_started": "chưa học"}
ATTENDANCE = ["100%", "100%", "95%", "90%", "90%", "85%", "80%", "75%", "70%"]
TOPICS = ["Case study", "Thảo luận nhóm", "Bài giảng chương 3", "Thuyết trình nhóm", "Ôn tập", "Khách mời doanh nghiệp"]
TUTORS = ["TS. Lê Minh Châu", "PGS.TS. Trần Quốc Việt", "TS. Phạm Thu Hằng", "TS. Đỗ Gia Huy", "ThS. Nguyễn Hải Yến"]
STAGES = [
    ("application", "Nộp / tiếp nhận hồ sơ tuyển sinh"),
    ("approved_ts", "TS phê duyệt → chuyển Điều phối"),
    ("written", "Thi viết"),
    ("interview", "Lịch & kết quả phỏng vấn"),
    ("admission_result", "Kết quả trúng tuyển"),
    ("fee", "Thanh toán phí ghi danh"),
    ("official", "Nhập học chính thức (Official)"),
    ("enrolled", "Xếp lớp / danh sách học viên"),
    ("grades", "Điểm từng môn học"),
    ("attendance", "Điểm danh các buổi học"),
    ("exams", "Lịch / hoàn thành bài thi"),
    ("thesis", "Chuyên đề / luận văn tốt nghiệp"),
    ("graduation", "Xét tốt nghiệp"),
    ("alumni", "Chuyển Alumni"),
]
NO_INFO_QUESTIONS = [
    "căng tin mở cửa mấy giờ", "trung tâm có ký túc xá không", "mật khẩu wifi của trung tâm là gì",
    "học phí khóa sau có tăng không", "trượt môn thì học lại mất bao nhiêu tiền", "trung tâm có bãi đỗ ô tô không",
    "lớp mình có đi dã ngoại không", "khi nào tổ chức lễ trao bằng", "ai là giám đốc trung tâm", "có được miễn môn tiếng Anh không",
    "phòng thư viện ở tầng mấy", "học viên có được giảm giá gửi xe không", "giảng viên môn này có dạy lớp khác không",
    "lớp có học bù vào chủ nhật không", "có được thi lại để nâng điểm không", "đổi lớp sang khóa khác có mất phí không",
    "trung tâm có cho mượn laptop không", "lễ khai giảng khóa mới tổ chức ở đâu", "có xe đưa đón học viên không",
]
STOP_PHRASES = [
    "nếu tôi dừng học thì {fee} xử lý ra sao", "tôi muốn thôi học thì {fee} có phải đóng tiếp không",
    "nghỉ giữa chừng thì {fee} của tôi thế nào", "tôi muốn bảo lưu thì {fee} xử lý sao",
    "nếu tôi tạm nghỉ thì {fee} còn phải đóng không", "nghỉ học giữa chừng có được hoàn {fee} không",
    "bảo lưu thì {fee} của mình có được giữ lại không",
]
OFF_TOPIC = [
    "kể cho tôi nghe một chuyện vui", "làm thơ tặng tôi đi", "viết hộ tôi bài tiểu luận", "dự báo giá vàng tuần tới",
    "đội bóng nào sẽ vô địch năm nay", "giải giúp tôi bài toán đạo hàm", "gợi ý quán cà phê gần đây",
]
DECLINE = "Mình là trợ lý học vụ nên chỉ hỗ trợ câu hỏi về học tập, học phí, lịch và thủ tục của bạn. Bạn cần hỏi gì về việc học không?"


def label(c: dict) -> str:
    return f"{c['course_code']} {c['course_name']}"


def money(v) -> str:
    return sb._money(v)


def day(v) -> str:
    return sb._day(v)


def score(v) -> str:
    return sb._score(v)


def make_student(rng: random.Random, today: date) -> dict:
    program = rng.choice(list(CATALOG))
    prefixes, names = CATALOG[program]
    prefix = rng.choice(prefixes)
    n_sem = rng.randint(1, 4)
    scenario = rng.choice(["midway", "midway", "midway", "start", "graduated", "graduated"])
    current = {"start": 1, "graduated": n_sem + 1, "midway": rng.randint(1, n_sem)}[scenario]
    pool = rng.sample(names, k=min(len(names), n_sem * 4))
    courses, k = [], 0
    for sem in range(1, n_sem + 1):
        for _ in range(rng.randint(1, 4)):
            if k >= len(pool):
                break
            name = pool[k]
            k += 1
            if sem < current:
                progress = "completed"
            elif sem == current:
                progress = rng.choice(["studying", "studying", "studying", "scheduled"] if scenario != "start" else ["studying", "scheduled"])
            else:
                progress = rng.choice(["scheduled", "not_started"])
            study = exam = final = None
            if progress == "completed":
                study = round(rng.uniform(10, 18), 1)
                exam = round(rng.uniform(9, 18.5), 1)
                final = round(0.4 * study + 0.6 * exam, 1)
                if rng.random() < 0.08:
                    exam = final = None
            elif progress == "studying" and rng.random() < 0.5:
                study = round(rng.uniform(10, 18), 1)
            courses.append({
                "semester": sem,
                "course_code": f"{prefix}{sem}{k:02d}",
                "course_name": name,
                "progress": progress,
                "progress_label": PROGRESS_LABELS[progress],
                "study_score": study,
                "exam_score": exam,
                "final_score": final,
                "attendance": rng.choice(ATTENDANCE) if progress in ("completed", "studying") else None,
                "sort_order": k,
            })
    finals = [c["final_score"] for c in courses if c["final_score"] is not None]
    gpa = round(sum(finals) / len(finals), 2) if finals else None

    start = today - timedelta(days=rng.randint(60, 200) + 150 * (current - 1))
    fees = []
    insc = rng.choice([10, 12, 15, 18, 20]) * 1_000_000
    fees.append(("Phí ghi danh (Inscription Fee)", insc, start - timedelta(days=rng.randint(10, 40))))
    per_sem = rng.choice([30, 35, 40, 45, 50, 60]) * 1_000_000
    for sem in range(1, n_sem + 1):
        fees.append((f"Học phí kỳ {sem}", per_sem, start + timedelta(days=150 * (sem - 1) + rng.randint(10, 30))))
    fee_rows = []
    for title, due, due_date in fees:
        if due_date < today - timedelta(days=20):
            paid = due if rng.random() < 0.85 else rng.choice([0, due // 2])
        elif due_date < today:
            paid = rng.choice([due, 0, due // 2])
        else:
            paid = due if rng.random() < 0.25 else 0
        remaining = due - paid
        delta = (due_date - today).days
        fee_rows.append({
            "title": title,
            "actual_due": float(due),
            "amount_due": float(due),
            "amount_paid": float(paid),
            "remaining": float(remaining),
            "due_date": due_date.isoformat(),
            "days_overdue": -delta if remaining > 0 and delta < 0 else 0,
            "days_until_due": delta if remaining > 0 and delta >= 0 else None,
        })

    schedule = []
    interview_day = start - timedelta(days=rng.randint(30, 60))
    schedule.append({"starts_at": f"{interview_day.isoformat()} 09:00", "title": f"PV tuyển sinh {program}", "room": f"P.{rng.randint(1, 6)}0{rng.randint(1, 9)}", "kind": "interview"})
    for c in courses:
        room = f"P.{rng.randint(1, 6)}0{rng.randint(1, 9)}"
        if c["progress"] == "completed":
            when = today - timedelta(days=rng.randint(5, 150))
            schedule.append({"starts_at": when.isoformat(), "title": f"Final {c['course_code']} — {c['course_name']}", "room": room, "kind": "exam"})
        elif c["progress"] == "studying":
            if rng.random() < 0.7:
                when = today + timedelta(days=rng.randint(3, 60))
                schedule.append({"starts_at": when.isoformat(), "title": f"Final {c['course_code']} — {c['course_name']}", "room": room, "kind": "exam"})
            when = today + timedelta(days=rng.randint(1, 20))
            schedule.append({"starts_at": when.isoformat(), "title": f"Buổi học {c['course_code']} {c['course_name']}: {rng.choice(TOPICS)}", "room": "", "kind": "lesson"})

    done_courses = all(c["progress"] == "completed" for c in courses)
    thesis = None
    graduated = scenario == "graduated" and rng.random() < 0.7
    if scenario == "graduated" or (current == n_sem and rng.random() < 0.5):
        jury = rng.sample(TUTORS, k=3) if rng.random() < 0.5 else []
        defended = graduated or (done_courses and rng.random() < 0.5)
        thesis = {
            "title": rng.choice(["Chuyển đổi số trong bán lẻ", "Tối ưu tồn kho cho doanh nghiệp vừa", "Chiến lược thương hiệu cho sản phẩm mới", "Đo lường hiệu quả kênh số"]),
            "tutor": rng.choice(TUTORS) if rng.random() < 0.75 else None,
            "defense_date": (today - timedelta(days=rng.randint(3, 40))).isoformat() if defended else ((today + timedelta(days=rng.randint(10, 60))).isoformat() if rng.random() < 0.5 else None),
            "defense_time": rng.choice([None, "09:00", "14:00"]),
            "room": rng.choice([None, "P.Defense", "P.501"]),
            "total_grade": round(rng.uniform(12, 18), 1) if defended else None,
            "status": "defended" if defended else None,
            "jury_host": jury[0] if jury else None,
            "jury_member_1": jury[1] if jury else None,
            "jury_member_2": jury[2] if jury else None,
        }
    insc_paid = fee_rows[0]["remaining"] <= 0
    written = round(rng.uniform(10, 18), 1)
    flags = {
        "application": True, "approved_ts": True, "written": True, "interview": True, "admission_result": True,
        "fee": insc_paid, "official": insc_paid, "enrolled": insc_paid, "grades": bool(finals), "attendance": scenario != "start",
        "exams": bool(finals), "thesis": bool(thesis and thesis["status"] == "defended"), "graduation": graduated, "alumni": graduated and rng.random() < 0.8,
    }
    code = f"HV{rng.randint(10000, 99999)}"
    details = {
        "application": f"{program} · TT: official" if insc_paid else f"{program} · TT: passed",
        "written": f"Điểm viết: {written}",
        "interview": "KQ: pass",
        "official": f"Mã HV: {code}" if insc_paid else "",
        "graduation": "Lifecycle: graduated" if graduated else "",
    }
    stages = [{"code": c, "title": t, "status": "done" if flags[c] else "pending", "detail": details.get(c, "")} for c, t in STAGES]
    profile = {
        "full_name": f"{rng.choice(SURNAMES)} {rng.choice(MIDDLES)} {rng.choice(GIVENS)}",
        "student_code": code if insc_paid else "",
        "program_code": program,
        "class_name": f"{program} K{rng.randint(10, 25)}" if insc_paid else "",
    }
    return {
        "profile": profile, "courses": courses, "gpa": gpa, "fees": fee_rows, "schedule": schedule,
        "stages": stages, "thesis": thesis, "written": written, "graduated": graduated, "scenario": scenario,
    }


def sems(S) -> dict:
    out: dict = {}
    for c in S["courses"]:
        out.setdefault(c["semester"], []).append(c)
    return out


def listing(cs: list[dict], with_status: bool = True) -> str:
    return ", ".join(label(c) + (f" ({STATUS_PHRASE[c['progress']]})" if with_status else "") for c in cs)


def g_current(rng, S):
    sem, note = sb._current_semester(S["courses"])
    if sem is None:
        return None
    cs = sems(S)[sem]
    english = rng.random() < 0.35
    q = rng.choice([
        "What am I studying this semester?", "How many courses do I have this semester?", "What subjects do I have now?",
        "List my courses for the current semester", "this semester which courses do I have",
    ] if english else [
        "kỳ này tôi học mấy môn", "học kỳ này mình có bao nhiêu môn vậy", "kì này em học những môn nào",
        "học kỳ hiện tại tôi có môn gì", "kỳ này có mấy môn thế", "bây giờ tôi đang học những môn nào",
    ])
    names = ", ".join(label(c) for c in cs)
    if english:
        if "đã học xong toàn bộ" in note:
            return q, f"You have finished all your courses. Your most recent semester is semester {sem}, with {len(cs)} course(s): {names}."
        return q, f"This semester (semester {sem}) you have {len(cs)} course(s): {names}."
    if "đã học xong toàn bộ" in note:
        return q, f"Bạn đã học xong tất cả các môn. Học kỳ gần nhất là học kỳ {sem}, có {len(cs)} môn: {listing(cs, False)}."
    return q, f"Kỳ này (học kỳ {sem}) bạn có {len(cs)} môn: {listing(cs)}."


def g_semester(rng, S):
    by = sems(S)
    n = rng.choice(list(by) + [max(by) + 1])
    q = rng.choice([f"học kỳ {n} tôi học những môn gì", f"kỳ {n} có bao nhiêu môn", f"các môn học kỳ {n} của tôi", f"kì {n} mình học gì"])
    if n not in by:
        return q, f"Bạn không có môn nào trong học kỳ {n}. Các môn của bạn thuộc học kỳ {', '.join(str(k) for k in sorted(by))}."
    return q, f"Học kỳ {n} bạn có {len(by[n])} môn: {listing(by[n])}."


def g_course_semester(rng, S):
    c = rng.choice(S["courses"])
    q = rng.choice([f"môn {c['course_name']} học vào kỳ nào", f"{c['course_name']} thuộc học kỳ mấy", f"khi nào tôi học môn {c['course_name']}"])
    tail = {"completed": "bạn đã học xong môn này", "studying": "bạn đang học môn này", "scheduled": "bạn chưa bắt đầu học môn này", "not_started": "bạn chưa bắt đầu học môn này"}[c["progress"]]
    return q, f"Môn {label(c)} thuộc học kỳ {c['semester']}, {tail}."


def g_remaining(rng, S):
    left = [c for c in S["courses"] if c["progress"] != "completed"]
    q = rng.choice(["tôi còn phải học bao nhiêu môn nữa", "còn mấy môn nữa là mình xong", "những môn nào tôi chưa học xong", "toi con may mon chua hoc"])
    if not left:
        return q, f"Bạn đã học xong tất cả {len(S['courses'])} môn, không còn môn nào phải học."
    return q, f"Bạn còn {len(left)} môn chưa học xong: {listing(left)}."


def g_done(rng, S):
    done = [c for c in S["courses"] if c["progress"] == "completed"]
    q = rng.choice(["tôi đã học xong mấy môn", "đến giờ mình hoàn thành bao nhiêu môn rồi", "những môn tôi đã học xong"])
    if not done:
        return q, f"Bạn chưa học xong môn nào. Toàn khóa có {len(S['courses'])} môn."
    return q, f"Bạn đã học xong {len(done)}/{len(S['courses'])} môn: {listing(done, False)}."


def g_total(rng, S):
    by = sems(S)
    q = rng.choice(["cả khóa tôi có tổng cộng bao nhiêu môn", "chương trình của tôi gồm mấy môn", "toàn khóa mình học bao nhiêu môn"])
    return q, f"Toàn khóa bạn có {len(S['courses'])} môn (" + "; ".join(f"học kỳ {k}: {len(v)} môn" for k, v in sorted(by.items())) + ")."


def course_grade_text(c) -> str:
    if c["progress"] in ("scheduled", "not_started"):
        return f"Bạn chưa học môn {label(c)} nên chưa có điểm."
    if c["study_score"] is None and c["exam_score"] is None and c["final_score"] is None:
        return f"Môn {label(c)} chưa được công bố điểm."
    return (
        f"Môn {label(c)}: điểm quá trình {score(c['study_score'])}, điểm thi {score(c['exam_score'])}, "
        f"điểm tổng kết {score(c['final_score'])}" + (f", chuyên cần {c['attendance']}" if c.get("attendance") else "") + "."
    )


def g_course_grade(rng, S):
    c = rng.choice(S["courses"])
    q = rng.choice([f"điểm môn {c['course_name']} của tôi", f"{c['course_name']} tôi được bao nhiêu điểm", f"cho mình xem điểm {c['course_code']}",
                    f"môn {c['course_name']} điểm thi bao nhiêu", f"diem mon {ab.fold(c['course_name'])}"])
    return q, course_grade_text(c)


def g_sem_grades(rng, S):
    by = sems(S)
    n = rng.choice(list(by))
    q = rng.choice([f"điểm kỳ {n} của tôi", f"kết quả học kỳ {n} thế nào", f"học kỳ {n} mình được điểm ra sao"])
    scored = [c for c in by[n] if c["final_score"] is not None]
    if not scored:
        return q, f"Học kỳ {n} bạn chưa có môn nào có điểm tổng kết."
    rest = [c for c in by[n] if c["final_score"] is None]
    return q, f"Điểm tổng kết học kỳ {n}: " + ", ".join(f"{label(c)} {score(c['final_score'])}" for c in scored) + "." + (
        f" Chưa có điểm: {listing(rest, False)}." if rest else "")


def g_gpa(rng, S):
    q = rng.choice(["điểm trung bình của tôi bao nhiêu", "GPA hiện tại của mình", "điểm tích lũy của tôi là mấy", "what is my GPA"])
    if S["gpa"] is None:
        return q, ("You have no course with a final score yet, so there is no GPA." if q.startswith("what") else "Bạn chưa có môn nào có điểm tổng kết nên chưa có điểm trung bình tích lũy.")
    return q, (f"Your current cumulative GPA is {score(S['gpa'])}." if q.startswith("what") else f"Điểm trung bình tích lũy hiện tại của bạn là {score(S['gpa'])}.")


def g_best(rng, S):
    scored = [c for c in S["courses"] if c["final_score"] is not None]
    hi = rng.random() < 0.6
    q = rng.choice(["môn nào tôi được điểm cao nhất", "môn tôi học tốt nhất là môn gì"] if hi else ["môn nào điểm thấp nhất của tôi", "môn tôi học kém nhất"])
    if not scored:
        return q, "Bạn chưa có môn nào có điểm tổng kết."
    v = (max if hi else min)(c["final_score"] for c in scored)
    hits = [c for c in scored if c["final_score"] == v]
    word = "cao nhất" if hi else "thấp nhất"
    return q, f"Điểm tổng kết {word} của bạn là {score(v)}, ở môn {', '.join(label(c) for c in hits)}."


def g_compare(rng, S):
    by = sems(S)
    if len(by) < 2:
        return None
    a, b = sorted(rng.sample(list(by), 2))
    q = rng.choice([f"so với kỳ {a} thì kỳ {b} tôi học thế nào", f"kỳ {b} điểm có tốt hơn kỳ {a} không", f"so sánh kết quả kỳ {a} và kỳ {b} của tôi"])
    parts = []
    for n in (a, b):
        scored = [c for c in by[n] if c["final_score"] is not None]
        parts.append(f"Học kỳ {n}: " + (", ".join(f"{label(c)} {score(c['final_score'])}" for c in scored) if scored else "chưa có điểm tổng kết"))
    sa = [c["final_score"] for c in by[a] if c["final_score"] is not None]
    sb_ = [c["final_score"] for c in by[b] if c["final_score"] is not None]
    if sa and sb_:
        verdict = f"Điểm cao nhất kỳ {a} là {score(max(sa))}, kỳ {b} là {score(max(sb_))}."
    else:
        verdict = "Chưa đủ điểm tổng kết của cả hai kỳ để so sánh."
    return q, ". ".join(parts) + ". " + verdict


def g_attendance(rng, S):
    cs = [c for c in S["courses"] if c.get("attendance")]
    q = rng.choice([
        "chuyên cần của tôi thế nào", "môn nào tôi vắng nhiều nhất", "tôi có bị thiếu chuyên cần môn nào không",
        "môn nào mình đi học ít nhất", "môn nào tôi lên lớp ít buổi nhất", "tỷ lệ đi học các môn của tôi",
    ])
    sessions = "buổi" in q
    note = " Hồ sơ chỉ ghi tỷ lệ chuyên cần, không ghi số buổi cụ thể." if sessions else ""
    if not cs:
        return q, "Bạn chưa có dữ liệu chuyên cần môn nào."
    values = {int(c["attendance"].rstrip("%")) for c in cs}
    listing_ = ", ".join(f"{c['course_code']} {c['attendance']}" for c in cs)
    if len(values) == 1 and len(cs) > 1:
        return q, f"Tất cả {len(cs)} môn có dữ liệu đều có chuyên cần {cs[0]['attendance']}, không có môn nào thấp hơn.{note}"
    low = min(values)
    lows = [c for c in cs if int(c["attendance"].rstrip("%")) == low]
    return q, f"Chuyên cần của bạn: {listing_}. Thấp nhất là {', '.join(label(c) for c in lows)} với {low}%.{note}"


def g_sessions(rng, S):
    c = rng.choice(S["courses"])
    q = rng.choice([f"môn {c['course_name']} tôi đã đi học bao nhiêu buổi", f"tôi vắng mấy buổi môn {c['course_name']}", f"môn {c['course_code']} mình nghỉ mấy buổi rồi"])
    if not c.get("attendance"):
        return q, f"Môn {label(c)} chưa có dữ liệu chuyên cần."
    return q, f"Hồ sơ chỉ ghi tỷ lệ chuyên cần môn {label(c)} là {c['attendance']}, không có số buổi cụ thể."


def fee_text(r) -> str:
    if r["remaining"] <= 0:
        return f"{r['title']}: đã đóng đủ {money(r['actual_due'])}"
    tail = f", hạn {day(r['due_date'])}"
    if r["days_overdue"]:
        tail += f", đã quá hạn {r['days_overdue']} ngày"
    return f"{r['title']}: còn {money(r['remaining'])}{tail}"


def g_owe(rng, S):
    open_rows = [r for r in S["fees"] if r["remaining"] > 0]
    total = sum(r["remaining"] for r in open_rows)
    english = rng.random() < 0.25
    q = rng.choice(["What do I still need to pay?", "How much do I owe?"] if english else ["tôi còn nợ bao nhiêu tiền", "mình còn phải đóng bao nhiêu", "công nợ học phí của tôi", "toi con no bao nhieu"])
    if not open_rows:
        return q, "You have paid all recorded fees in full." if english else "Bạn đã đóng đủ tất cả các khoản phí đã ghi nhận."
    if english:
        return q, f"You still owe {money(total)} in total: " + "; ".join(f"{r['title']} {money(r['remaining'])}, due {day(r['due_date'])}" for r in open_rows) + "."
    return q, f"Bạn còn {money(total)} chưa đóng: " + "; ".join(fee_text(r) for r in open_rows) + "."


def g_paid(rng, S):
    paid = sum(r["amount_paid"] for r in S["fees"])
    q = rng.choice(["tôi đã đóng được bao nhiêu tiền rồi", "tổng số tiền mình đã nộp", "mình nộp được bao nhiêu học phí rồi"])
    full = [r for r in S["fees"] if r["remaining"] <= 0]
    return q, f"Bạn đã đóng tổng cộng {money(paid)}." + (f" Các khoản đã đóng đủ: {', '.join(r['title'] for r in full)}." if full else " Chưa có khoản nào được đóng đủ.")


def g_total_fee(rng, S):
    due = sum(r["actual_due"] for r in S["fees"])
    paid = sum(r["amount_paid"] for r in S["fees"])
    left = sum(r["remaining"] for r in S["fees"])
    q = rng.choice(["tổng học phí cả khóa của tôi", "toàn bộ chương trình tôi phải đóng bao nhiêu", "tất cả các khoản phí của mình là bao nhiêu"])
    return q, f"Tổng {len(S['fees'])} khoản phí của bạn: phải đóng {money(due)}, đã đóng {money(paid)}, còn {money(left)}."


def g_fee_item(rng, S):
    r = rng.choice(S["fees"])
    name = r["title"].split(" (")[0].lower()
    q = rng.choice([f"{name} của tôi đã đóng chưa", f"tôi đóng {name} chưa", f"{name} hạn đóng khi nào"])
    if r["remaining"] <= 0:
        return q, f"{r['title']} bạn đã đóng đủ {money(r['actual_due'])}."
    paid = f", đã đóng {money(r['amount_paid'])}" if r["amount_paid"] else ""
    late = f", đã quá hạn {r['days_overdue']} ngày" if r["days_overdue"] else ""
    return q, f"{r['title']} chưa đóng đủ: phải đóng {money(r['actual_due'])}{paid}, còn {money(r['remaining'])}, hạn {day(r['due_date'])}{late}."


def g_next_due(rng, S):
    open_rows = sorted((r for r in S["fees"] if r["remaining"] > 0), key=lambda r: r["due_date"])
    q = rng.choice(["khoản tiếp theo tôi phải đóng là gì", "hạn đóng tiền gần nhất của tôi", "sắp tới mình phải đóng khoản nào"])
    if not open_rows:
        return q, "Bạn không còn khoản phí nào phải đóng."
    return q, f"Khoản cần đóng tiếp theo là {fee_text(open_rows[0])}."


def g_overdue(rng, S):
    late = [r for r in S["fees"] if r["remaining"] > 0 and r["days_overdue"]]
    q = rng.choice(["tôi có khoản nào quá hạn không", "mình có bị trễ hạn đóng phí không", "có khoản nào tôi nợ quá hạn chưa"])
    if not late:
        return q, "Bạn không có khoản phí nào quá hạn."
    return q, "Các khoản đã quá hạn: " + "; ".join(fee_text(r) for r in late) + "."


def upcoming(S, today, kinds):
    return sorted((i for i in S["schedule"] if i["kind"] in kinds and i["starts_at"][:10] >= today.isoformat()), key=lambda i: i["starts_at"])


def g_next_exam(rng, S, today):
    q = rng.choice(["khi nào tôi thi môn tiếp theo", "lịch thi sắp tới của mình", "bài thi gần nhất của tôi là gì"])
    ex = upcoming(S, today, ("exam",))
    if not ex:
        return q, "Hiện bạn chưa có lịch thi nào sắp tới."
    i = ex[0]
    return q, f"Bài thi tiếp theo của bạn là {i['title']} ngày {day(i['starts_at'])}" + (f", phòng {i['room']}" if i["room"] else "") + "."


def g_course_exam(rng, S, today):
    c = rng.choice(S["courses"])
    q = rng.choice([f"lịch thi môn {c['course_name']}", f"môn {c['course_name']} thi ngày nào", f"khi nào thi {c['course_code']}"])
    ex = [i for i in S["schedule"] if i["kind"] == "exam" and c["course_code"] in i["title"]]
    if not ex:
        return q, f"Môn {label(c)} chưa có lịch thi."
    i = ex[0]
    when = "đã diễn ra" if i["starts_at"][:10] < today.isoformat() else "sắp tới"
    return q, f"Môn {label(c)} thi ngày {day(i['starts_at'])} ({when})" + (f", phòng {i['room']}" if i["room"] else "") + "."


def g_upcoming(rng, S, today):
    q = rng.choice(["sắp tới tôi có lịch gì", "lịch của tôi những ngày tới", "mình có buổi học hay bài thi nào sắp tới không"])
    items = upcoming(S, today, ("exam", "lesson", "interview"))[:4]
    if not items:
        return q, "Hiện bạn chưa có lịch học hay lịch thi nào sắp tới."
    return q, "Lịch sắp tới của bạn: " + "; ".join(f"{day(i['starts_at'])}: {i['title']}" for i in items) + "."


def g_progress(rng, S):
    done = sum(1 for s in S["stages"] if s["status"] == "done")
    total = len(S["stages"])
    q = rng.choice(["tiến độ của tôi đến đâu rồi", "tôi hoàn thành bao nhiêu phần lộ trình rồi", "mình đang ở giai đoạn nào"])
    nxt = next((s["title"] for s in S["stages"] if s["status"] != "done"), None)
    courses_done = sum(1 for c in S["courses"] if c["progress"] == "completed")
    text = f"Bạn đã xong {done}/{total} giai đoạn của lộ trình và học xong {courses_done}/{len(S['courses'])} môn."
    return q, text + (f" Giai đoạn tiếp theo: {nxt}." if nxt else " Bạn đã hoàn thành tất cả giai đoạn.")


def g_thesis(rng, S):
    t = S["thesis"]
    kind = rng.choice(["tutor", "jury", "date"])
    q = {
        "tutor": rng.choice(["ai hướng dẫn luận văn của tôi", "giảng viên hướng dẫn luận văn của mình là ai"]),
        "jury": rng.choice(["hội đồng chấm luận văn của tôi gồm ai", "ai trong hội đồng bảo vệ của mình"]),
        "date": rng.choice(["khi nào tôi bảo vệ luận văn", "ngày bảo vệ luận văn của mình"]),
    }[kind]
    if not t:
        return q, "Hiện chưa có thông tin về luận văn của bạn."
    if kind == "tutor":
        return q, f"Người hướng dẫn luận văn của bạn là {t['tutor']}." if t["tutor"] else "Luận văn của bạn chưa được phân công người hướng dẫn."
    if kind == "jury":
        jury = [t[k] for k in ("jury_host", "jury_member_1", "jury_member_2") if t[k]]
        return q, ("Hội đồng bảo vệ luận văn của bạn gồm: " + ", ".join(jury) + ".") if jury else "Hiện chưa có thông tin về hội đồng bảo vệ luận văn của bạn."
    if not t["defense_date"]:
        return q, "Hiện chưa có ngày bảo vệ luận văn của bạn."
    return q, f"Ngày bảo vệ luận văn của bạn là {day(t['defense_date'])}" + (f" lúc {t['defense_time']}" if t["defense_time"] else "") + (f", phòng {t['room']}" if t["room"] else "") + "."


def g_graduated(rng, S):
    q = rng.choice(["tôi tốt nghiệp chưa", "mình đã được xét tốt nghiệp chưa"])
    return q, "Bạn đã được xét tốt nghiệp." if S["graduated"] else "Bạn chưa được xét tốt nghiệp, giai đoạn Xét tốt nghiệp đang chờ."


def g_written(rng, S):
    q = rng.choice(["điểm thi viết đầu vào của tôi", "lúc tuyển sinh tôi thi viết được mấy điểm"])
    return q, f"Điểm thi viết đầu vào của bạn là {S['written']}."


DATED = [g_next_exam, g_course_exam, g_upcoming]


def load_faqs() -> list[dict]:
    return json.loads((KB_DIR / "faq.json").read_text(encoding="utf-8"))


def faq_doc(f: dict) -> dict:
    return {"kind": "faq", "question": f["question"], "title": f["question"], "text": f["answer"]}


def g_policy(rng, S, faqs):
    f = rng.choice(faqs)
    q = rng.choice([f["question"], *f.get("variants", [])])
    return q, f["answer"], [faq_doc(f)]


def g_policy_mix(rng, S, faqs):
    f = next(x for x in faqs if x["question"].startswith("Muốn bảo lưu"))
    r = rng.choice(S["fees"])
    name = r["title"].split(" (")[0].lower()
    q = rng.choice(STOP_PHRASES).format(fee=name)
    status = (
        f"{r['title']} của bạn đã đóng đủ {money(r['actual_due'])}"
        if r["remaining"] <= 0
        else f"{r['title']} của bạn còn {money(r['remaining'])}, hạn {day(r['due_date'])}"
    )
    return q, (
        "Việc dừng học, bảo lưu và cách xử lý học phí được giải quyết theo từng trường hợp, bạn gửi yêu cầu cho bộ phận "
        f"chương trình để được hướng dẫn hồ sơ và thời hạn cụ thể. Hiện {status}."
    ), [faq_doc(f)]


def g_missing_course(rng, S):
    have = {c["course_name"] for c in S["courses"]}
    others = [n for _p, (_x, names) in CATALOG.items() for n in names if n not in have]
    name = rng.choice(others)
    q = rng.choice([f"điểm môn {name} của tôi", f"môn {name} tôi học kỳ nào", f"lịch thi môn {name}", f"What is my grade in {name}?"])
    if q.startswith("What"):
        return q, f"There is no course named {name} in your record."
    return q, f"Hồ sơ của bạn không có môn {name}. Các môn của bạn: {', '.join(label(c) for c in S['courses'])}."


PERSONAL = [g_current, g_semester, g_course_semester, g_remaining, g_done, g_total, g_course_grade, g_sem_grades, g_gpa, g_best,
            g_compare, g_attendance, g_sessions, g_owe, g_paid, g_total_fee, g_fee_item, g_next_due, g_overdue, g_progress,
            g_thesis, g_graduated, g_written, g_missing_course]
WEIGHTS = {g_current: 3, g_attendance: 3, g_thesis: 3, g_progress: 2, g_owe: 2, g_missing_course: 2, g_compare: 2}


def strip_marks(rng, q: str) -> str:
    r = rng.random()
    if r < 0.12:
        return ab.fold(q)
    if r < 0.25:
        return q.replace("kỳ", "kì")
    if r < 0.35:
        return q[0].upper() + q[1:] + "?"
    return q


def sample(rng, today, faqs, banned) -> dict | None:
    S = make_student(rng, today)
    roll = rng.random()
    docs = [faq_doc(f) for f in rng.sample(faqs, k=rng.randint(1, 3))]
    if roll < 0.62:
        out = rng.choices(PERSONAL, weights=[WEIGHTS.get(g, 1) for g in PERSONAL])[0](rng, S)
    elif roll < 0.72:
        out = rng.choice(DATED)(rng, S, today)
    elif roll < 0.82:
        q, a, extra = g_policy(rng, S, faqs)
        docs = extra + [d for d in docs if d["question"] != extra[0]["question"]][:2]
        out = (q, a)
    elif roll < 0.88:
        got = g_policy_mix(rng, S, faqs)
        if not got:
            return None
        q, a, extra = got
        docs = extra + docs[:1]
        out = (q, a)
    elif roll < 0.95:
        out = (rng.choice(NO_INFO_QUESTIONS), ab.NO_INFO_MARK)
    else:
        out = (rng.choice(OFF_TOPIC), DECLINE)
    if not out:
        return None
    q, a = out
    q = strip_marks(rng, q) if not q.isascii() or rng.random() < 0.2 else q
    if any(ab._faq_match(b, q, {}) > 0.6 for b in banned):
        return None
    history = []
    if rng.random() < 0.05:
        prev = rng.choice(PERSONAL)(rng, S)
        if prev:
            history = [{"role": "user", "content": prev[0]}, {"role": "assistant", "content": prev[1]}]
    sheet = sb.format_sheet(S, today)
    messages = sb.build_messages(sheet, sb.format_docs(docs), q, today, history)
    messages.append({"role": "assistant", "content": a})
    return {"messages": messages}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=int, default=2000)
    parser.add_argument("--val", type=int, default=150)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    rng = random.Random(args.seed)
    faqs = load_faqs()
    banned = [c["q"] for c in json.loads((KB_DIR / "eval_questions.json").read_text(encoding="utf-8"))]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, count in (("train", args.train), ("val", args.val)):
        rows = []
        while len(rows) < count:
            today = date(2026, 3, 1) + timedelta(days=rng.randint(0, 480))
            item = sample(rng, today, faqs, banned)
            if item:
                rows.append(item)
        path = OUT_DIR / f"{name}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        chars = sum(len(m["content"]) for r in rows for m in r["messages"])
        print(f"{path}: {len(rows)} mẫu, khoảng {chars // 3 // 1000}k token")


if __name__ == "__main__":
    main()
