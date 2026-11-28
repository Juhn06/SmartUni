"""Demo student personas for the portal and UniBot tests: each account sits in a different learning situation."""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

JURY = ["PGS.TS. Trịnh Minh Sơn", "TS. Hà Thu Ngân", "TS. Đặng Hải Long"]
TUTOR = "TS. Lâm Quang Đức"
M = 1_000_000

PERSONAS = [
    {
        "login": "E2eMba",
        "program_code": "MBA",
        "full_name": "E2E Nguyễn Minh Anh",
        "cccd": "099000000001",
        "email": "e2e.mba@smartuni.test",
        "phone": "0909000001",
        "cfvg_app_no": "E2E-MBA-001",
        "student_code": "E2EMBA001",
        "company": "Ngân hàng Sao Mai",
        "job_title": "Chuyên viên Digital",
        "intake_session": "August",
        "class_name": "MBA E2E 2026",
        "situation": "Đã tốt nghiệp, học lực giỏi, còn học phí kỳ 2 sắp đến hạn",
        "lifecycle": "graduated",
        "admission": {
            "written": 14.5, "interview": 16.0,
            "english": {"type": "IELTS", "score": "7.0", "no": "IE-E2E-0001", "issued": -520},
            "degree": {"major": "Tài chính ngân hàng", "grade": "Giỏi", "issuer": "Trường Đại học Hải Đăng", "year": 2018},
        },
        "courses": [
            {"state": "done", "scores": (15.0, 16.5), "attendance": (4, 4), "exams": [(-40, "final")]},
            {"state": "done", "scores": (16.5, 17.0), "attendance": (4, 4), "exams": [(-38, "final")]},
            {"state": "done", "scores": (14.0, 15.5), "attendance": (3, 4), "exams": [(-12, "final")]},
        ],
        "thesis": {
            "title": "Digital transformation in retail banking", "status": "defended", "grade": 16.0,
            "tutor": TUTOR, "defense": -5, "time": "09:00", "room": "P.Defense 2", "jury": JURY,
        },
        "tuition": [(40 * M, -60, 0), (0, 20, 0)],
    },
    {
        "login": "E2eMms",
        "program_code": "MMS",
        "full_name": "E2E Trần Thu Hà",
        "cccd": "099000000002",
        "email": "e2e.mms@smartuni.test",
        "phone": "0909000002",
        "cfvg_app_no": "E2E-MMS-001",
        "student_code": "E2EMMS001",
        "company": "Công ty Sữa Đồng Xanh",
        "job_title": "Marketing Manager",
        "intake_session": "May",
        "class_name": "MMS E2E 2026",
        "situation": "Đang học kỳ 2, được miễn 1 môn, học bổng 50% và đã đóng đủ, có buổi học ngày mai, thi cuối kỳ sau 5 ngày",
        "lifecycle": "active",
        "admission": {
            "written": 13.0, "interview": 14.5,
            "english": {"type": "TOEIC", "score": "820", "no": "TO-E2E-0002", "issued": -300},
            "degree": {"major": "Marketing", "grade": "Khá", "issuer": "Trường Đại học Sao Việt", "year": 2020},
        },
        "courses": [
            {"state": "done", "scores": (13.0, 12.5), "attendance": (4, 4), "exams": [(-50, "final")]},
            {"state": "recognized"},
            {"state": "studying", "attendance": (3, 4), "lessons": [1, 8], "exams": [(5, "final")]},
        ],
        "thesis": None,
        "scholarship": "partial",
        "tuition": [(20 * M, -90, -20 * M), (20 * M, -10, -20 * M)],
    },
    {
        "login": "E2eMscm",
        "program_code": "MSCM",
        "full_name": "E2E Lê Quốc Bảo",
        "cccd": "099000000003",
        "email": "e2e.mscm@smartuni.test",
        "phone": "0909000003",
        "cfvg_app_no": "E2E-MSCM-001",
        "student_code": "E2EMSCM001",
        "company": "Công ty Giao vận Nhanh",
        "job_title": "Supply Chain Analyst",
        "intake_session": "May",
        "class_name": "MSCM E2E 2026",
        "situation": "Tài khoản demo: trượt 1 môn thi lại sau 2 ngày, chuyên cần thấp, được miễn 1 môn, học bổng 50% nhưng học phí kỳ 1 vẫn quá hạn",
        "lifecycle": "active",
        "admission": {
            "written": 11.0, "interview": 12.0,
            "english": {"type": "IELTS", "score": "5.5", "no": "IE-E2E-0003", "issued": -200},
            "degree": {"major": "Logistics và quản lý chuỗi cung ứng", "grade": "Trung bình khá", "issuer": "Trường Đại học Hải Đăng", "year": 2019},
        },
        "extra_courses": [("MSCM104", "Procurement & Sourcing", 1)],
        "courses": [
            {"state": "done", "scores": (11.0, 10.5), "attendance": (5, 6), "exams": [(-45, "final")]},
            {"state": "failed", "scores": (9.0, 10.0), "attendance": (3, 6), "exams": [(-44, "final"), (2, "retake")]},
            {"state": "studying", "attendance": (2, 5), "lessons": [0, 7], "exams": [(20, "final")]},
            {"state": "recognized"},
        ],
        "thesis": {"title": "Last-mile logistics optimization", "status": "draft", "grade": None, "tutor": None},
        "scholarship": "partial",
        "tuition": [(10 * M, -12, -20 * M), (0, 45, -20 * M)],
    },
]

TOPICS = ("Introduction and case study", "Frameworks in practice", "Group workshop", "Review and Q&A", "Guest lecture", "Project clinic")


def _day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def plan_signature() -> str:
    blob = json.dumps([PERSONAS, date.today().isoformat()], ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _assignment(cur, class_id: int, course_id: int) -> int:
    row = cur.execute(
        "SELECT id FROM teaching_assignments WHERE class_id = ? AND course_id = ?", (class_id, course_id)
    ).fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO teaching_assignments (class_id, course_id, status) VALUES (?, ?, 'in_teaching')", (class_id, course_id)
    )
    return cur.lastrowid


def _reset_course(cur, class_id: int, student_id: int, course_id: int, ta_id: int) -> None:
    sessions = [r[0] for r in cur.execute("SELECT id FROM attendance_sessions WHERE assignment_id = ?", (ta_id,))]
    for sid in sessions:
        cur.execute("DELETE FROM attendance_marks WHERE attendance_session_id = ?", (sid,))
    cur.execute("DELETE FROM attendance_sessions WHERE assignment_id = ?", (ta_id,))
    cur.execute("DELETE FROM class_lessons WHERE assignment_id = ?", (ta_id,))
    cur.execute("DELETE FROM exam_schedules WHERE class_id = ? AND course_id = ?", (class_id, course_id))
    cur.execute(
        "DELETE FROM course_grades WHERE class_id = ? AND student_id = ? AND course_id = ?", (class_id, student_id, course_id)
    )


def _sessions(cur, ta_id: int, student_id: int, code: str, present: int, total: int, first_offset: int) -> None:
    for i in range(total):
        cur.execute(
            "INSERT INTO attendance_sessions (assignment_id, session_no, session_label, session_date, present_count, absent_count) "
            "VALUES (?,?,?,?,?,?)",
            (ta_id, i + 1, f"E2E {code} buổi {i + 1}", _day(first_offset + 7 * i), 1 if i < present else 0, 0 if i < present else 1),
        )
        cur.execute(
            "INSERT INTO attendance_marks (attendance_session_id, student_id, present, present_after_break, check_in, check_out) "
            "VALUES (?,?,?,?,?,?)",
            (cur.lastrowid, student_id, *([1] * 4 if i < present else [0] * 4)),
        )


def _ensure_extra_courses(cur, pvid: int, extra: list) -> None:
    for code, name, semester in extra:
        if cur.execute("SELECT 1 FROM courses WHERE program_version_id = ? AND code = ?", (pvid, code)).fetchone():
            continue
        order = cur.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM courses WHERE program_version_id = ?", (pvid,)).fetchone()[0]
        cur.execute(
            "INSERT INTO courses (program_version_id, code, name, semester, sort_order, theory_sessions, practice_sessions) "
            "VALUES (?,?,?,?,?,7,2)",
            (pvid, code, name, semester, order),
        )


def admission_fields(c: dict) -> dict:
    adm = c.get("admission") or {}
    english = adm.get("english") or {}
    degree = adm.get("degree") or {}
    out = {}
    if english:
        out.update(
            english_cert=f"{english['type']} {english['score']}",
            english_cert_type=english["type"],
            english_cert_score=english["score"],
            english_cert_no=english.get("no") or "",
            english_cert_date=_day(english.get("issued", -365)),
        )
    if degree:
        out.update(
            degree_major=degree["major"],
            degree_grade=degree["grade"],
            degree_issuer=degree["issuer"],
            degree_year=degree["year"],
            degree_country="Việt Nam",
        )
    return out


def apply_plan(cur, class_id: int, student_id: int, pvid: int, c: dict) -> dict:
    _ensure_extra_courses(cur, pvid, c.get("extra_courses") or [])
    courses = cur.execute(
        "SELECT id, code, name FROM courses WHERE program_version_id = ? ORDER BY sort_order", (pvid,)
    ).fetchall()
    out = {"grades": 0, "attendance": 0, "exams": 0, "lessons": 0, "thesis": 0}
    for (course_id, code, name), plan in zip(courses, c.get("courses") or []):
        ta_id = _assignment(cur, class_id, course_id)
        _reset_course(cur, class_id, student_id, course_id, ta_id)
        state = plan["state"]
        if state in ("done", "failed"):
            ga, fe = plan["scores"]
            cur.execute(
                "INSERT INTO course_grades (class_id, course_id, student_id, score, locked, group_assignment, final_exam, remarks) "
                "VALUES (?,?,?,?,1,?,?,?)",
                (class_id, course_id, student_id, round(ga * 0.3 + fe * 0.7, 1), ga, fe, "E2E"),
            )
            out["grades"] += 1
        elif state == "recognized":
            cur.execute(
                "INSERT INTO course_grades (class_id, course_id, student_id, score, locked, remarks) VALUES (?,?,?,NULL,1,?)",
                (class_id, course_id, student_id, "Miễn học phần, công nhận tín chỉ"),
            )
        if plan.get("attendance"):
            present, total = plan["attendance"]
            first = -7 * total - (60 if state in ("done", "failed") else 0)
            _sessions(cur, ta_id, student_id, code, present, total, first)
            out["attendance"] += total
        if state == "upcoming":
            cur.execute(
                "INSERT INTO attendance_sessions (assignment_id, session_no, session_label, session_date) VALUES (?,?,?,?)",
                (ta_id, 1, f"E2E {code} buổi 1", _day(plan.get("start", 30))),
            )
        for n, offset in enumerate(plan.get("lessons") or [], start=1):
            cur.execute(
                "INSERT INTO class_lessons (assignment_id, lesson_no, title, content_outline, lesson_type, lesson_date, status) "
                "VALUES (?,?,?,?,?,?,?)",
                (ta_id, n, f"Session {n}: {TOPICS[(n - 1) % len(TOPICS)]}", "E2E", "offline", _day(offset), "published"),
            )
            out["lessons"] += 1
        for offset, kind in plan.get("exams") or []:
            label = "Retake" if kind == "retake" else "Final"
            cur.execute(
                "INSERT INTO exam_schedules (class_id, course_id, title, exam_date, exam_type, room, status) VALUES (?,?,?,?,?,?,?)",
                (class_id, course_id, f"{label} {code} — {name}", _day(offset), kind, f"P.{code[-3:]}",
                 "completed" if offset < 0 else "scheduled"),
            )
            out["exams"] += 1
    _apply_thesis(cur, class_id, student_id, c)
    out["thesis"] = 1 if c.get("thesis") else 0
    return out


def _apply_thesis(cur, class_id: int, student_id: int, c: dict) -> None:
    t = c.get("thesis")
    if not t:
        cur.execute("DELETE FROM thesis_records WHERE student_id = ?", (student_id,))
        return
    jury = (t.get("jury") or []) + [None, None, None]
    values = {
        "class_id": class_id,
        "program_code": c["program_code"],
        "full_name": c["full_name"],
        "email": c["email"],
        "title": t["title"],
        "tutor": t.get("tutor"),
        "status": t["status"],
        "total_grade": t.get("grade"),
        "defense_date": _day(t["defense"]) if t.get("defense") is not None else None,
        "defense_time": t.get("time"),
        "room": t.get("room"),
        "jury_host": jury[0],
        "jury_member_1": jury[1],
        "jury_member_2": jury[2],
    }
    row = cur.execute("SELECT id FROM thesis_records WHERE student_id = ?", (student_id,)).fetchone()
    if row:
        cur.execute(
            f"UPDATE thesis_records SET {', '.join(f'{k} = ?' for k in values)} WHERE id = ?", (*values.values(), row[0])
        )
    else:
        cols = ["student_id", *values]
        cur.execute(
            f"INSERT INTO thesis_records ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", (student_id, *values.values())
        )


def apply_tuition(conn, app_id: int, c: dict) -> None:
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT id, amount_due FROM student_charges WHERE application_id = ? AND fee_type = 'tuition' ORDER BY installment_no, id",
        (app_id,),
    ).fetchall()
    for (charge_id, due), (paid, offset, adjust) in zip(rows, c.get("tuition") or []):
        net = max(0.0, float(due or 0) + float(adjust))
        paid = min(float(paid), net)
        status = "waived" if net <= 0 else "paid" if paid + 0.01 >= net else "partial" if paid > 0 else "pending"
        cur.execute(
            "UPDATE student_charges SET amount_paid = ?, amount_adjust = ?, due_date = ?, status = ? WHERE id = ?",
            (paid, float(adjust), _day(offset), status, charge_id),
        )
    conn.commit()
