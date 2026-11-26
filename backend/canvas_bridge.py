"""
Canvas LMS bridge — hỗ trợ giao tiếp SmartUni ↔ x.instructure.com
theo từng nhóm đối tượng (Điều phối, GV, HV, Kế toán, IT).

Giai đoạn hiện tại: chuẩn bị gói SIS/JSON, nhật ký đồng bộ, hub theo vai trò.
Khi có API token, cùng payload có thể đẩy qua Canvas REST/SIS Import.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

CANVAS_LOGIN_URL = "https://cfvg.instructure.com/login/canvas"
CANVAS_BASE_HINT = "https://cfvg.instructure.com"


def ensure_canvas_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS canvas_exports ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "kind TEXT NOT NULL, "  # roster | class_package | teachers | grades_pull
        "audience TEXT, "  # coordinator | faculty | student | accounting | it
        "program_code TEXT, "
        "class_id INTEGER, "
        "title TEXT, "
        "payload_json TEXT NOT NULL, "
        "status TEXT DEFAULT 'ready', "  # ready | marked_pushed | error
        "created_by TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "notes TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS canvas_id_map ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "entity_type TEXT NOT NULL, "  # user | course | section | enrollment
        "local_key TEXT NOT NULL, "
        "sis_id TEXT NOT NULL, "
        "canvas_id TEXT, "
        "label TEXT, "
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "UNIQUE(entity_type, local_key))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS canvas_course_links ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "class_id INTEGER NOT NULL, "
        "course_id INTEGER, "
        "assignment_id INTEGER, "
        "sis_course_id TEXT NOT NULL, "
        "course_name TEXT, "
        "sync_status TEXT DEFAULT 'pending', "  # pending | exported | live | error
        "last_export_id INTEGER, "
        "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "UNIQUE(class_id, course_id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS canvas_sync_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "action TEXT NOT NULL, "
        "audience TEXT, "
        "detail TEXT, "
        "actor TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS canvas_audience_guides ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "audience TEXT NOT NULL, "
        "step_order INTEGER NOT NULL, "
        "title TEXT NOT NULL, "
        "detail TEXT, "
        "smartuni_perm TEXT, "
        "canvas_area TEXT)"
    )


def _log(cur, action: str, audience: str, detail: str, actor: str = "") -> None:
    cur.execute(
        "INSERT INTO canvas_sync_log (action, audience, detail, actor) VALUES (?,?,?,?)",
        (action, audience, detail, actor),
    )


def _sis_user_id(email: str | None, prefix: str, local_id: int | str) -> str:
    if email:
        local = email.split("@")[0].lower().replace(".", "_")
        return f"{prefix}_{local}"
    return f"{prefix}_{local_id}"


def seed_canvas_draft_data(conn) -> dict:
    cur = conn.cursor()
    ensure_canvas_tables(cur)
    created = {"guides": 0, "links": 0}

    cur.execute("SELECT COUNT(*) FROM canvas_audience_guides")
    if cur.fetchone()[0] == 0:
        guides = [
            # coordinator
            ("coordinator", 1, "Nhận DS trúng tuyển chính thức",
             "Chỉ enroll HV đã official (sau nộp phí).", "accounting.official_list", "People"),
            ("coordinator", 2, "Tạo lớp SmartUni & gắn phiên bản CT",
             "Mỗi lớp–môn sẽ map 1 Course/Section Canvas.", "classes.manage", "Courses"),
            ("coordinator", 3, "Xuất gói Canvas (Users + Enrollments + Teachers)",
             "Tải SIS/JSON hoặc đánh dấu đã đẩy lên Canvas.", "canvas.coordinator", "SIS Import"),
            ("coordinator", 4, "Gửi tài liệu / syllabus đã duyệt",
             "Files/Modules; hạn 2–4 tuần trước khai giảng.", "teaching.materials", "Files"),
            ("coordinator", 5, "Theo dõi điểm từ Canvas về SmartUni",
             "Import Gradebook → khóa điểm X.", "teaching.grades", "Grades"),
            # faculty
            ("faculty", 1, "Nhận phân công giảng dạy",
             "Xem lớp–môn đã được enroll Teacher trên Canvas.", "teaching.assign", "People"),
            ("faculty", 2, "Upload tài liệu / syllabus",
             "Upload trực tiếp Canvas hoặc gửi Admin hỗ trợ.", "teaching.materials", "Files"),
            ("faculty", 3, "Tạo bài tập & đề thi",
             "Assignments / Quizzes + LockDown Browser khi cần.", "teaching.assignments", "Assignments"),
            ("faculty", 4, "Chấm điểm trên SpeedGrader",
             "Comment + điểm; Admin import về SmartUni khi khóa.", "teaching.grades", "SpeedGrader"),
            ("faculty", 5, "Nhận xét luận văn (nếu có)",
             "Nộp LV qua Assignment; chấm trên Canvas.", "teaching.thesis", "Assignments"),
            # student
            ("student", 1, "Nhận email chào mừng + hướng dẫn Canvas",
             "Login: x.instructure.com — dùng email X.", "student.profile", "Login"),
            ("student", 2, "Vào các Course đã được enroll",
             "Chỉ thấy môn thuộc lớp chính thức của mình.", "student.schedule", "Courses"),
            ("student", 3, "Xem tài liệu & nộp bài tập",
             "Files/Modules + Assignments theo hạn GV.", "teaching.assignments", "Assignments"),
            ("student", 4, "Thi & xem điểm (khi được mở)",
             "Quizzes; điểm hiện theo cấu hình manual release.", "student.results", "Grades"),
            ("student", 5, "Đánh giá khóa học sau thi",
             "Survey/Announcement do Điều phối gửi.", "teaching.evaluation", "Announcements"),
            # accounting
            ("accounting", 1, "Xác nhận nộp phí ghi danh",
             "Chỉ HV đã paid → official mới đủ điều kiện Canvas.", "accounting.fees", "—"),
            ("accounting", 2, "Lập / khóa DS trúng tuyển chính thức",
             "Nguồn roster cho Điều phối xuất Canvas.", "accounting.official_list", "People"),
            ("accounting", 3, "Xuất roster sẵn sàng cho Canvas",
             "Gói Users (Student) theo chương trình.", "canvas.accounting", "SIS users"),
            # it
            ("it", 1, "Cấu hình token / Account Canvas",
             "CANVAS_BASE_URL + Access Token (Admin).", "canvas.it", "Settings"),
            ("it", 2, "Quản lý map SIS ID",
             "Giữ local_key ổn định giữa SmartUni và Canvas.", "canvas.it", "SIS"),
            ("it", 3, "Theo dõi nhật ký đồng bộ",
             "Export / marked_pushed / lỗi.", "canvas.it", "—"),
            ("it", 4, "Provisioning tài khoản HV/GV",
             "Đồng bộ từ admin.users khi cần.", "admin.users", "People"),
        ]
        for row in guides:
            cur.execute(
                "INSERT INTO canvas_audience_guides "
                "(audience, step_order, title, detail, smartuni_perm, canvas_area) "
                "VALUES (?,?,?,?,?,?)",
                row,
            )
            created["guides"] += 1

    # Link pending courses from teaching_assignments if empty
    cur.execute("SELECT COUNT(*) FROM canvas_course_links")
    if cur.fetchone()[0] == 0:
        rows = cur.execute(
            "SELECT ta.id, ta.class_id, ta.course_id, cg.name, cg.program_code, c.code, c.name "
            "FROM teaching_assignments ta "
            "JOIN class_groups cg ON cg.id = ta.class_id "
            "JOIN courses c ON c.id = ta.course_id"
        ).fetchall()
        for ta_id, class_id, course_id, class_name, prog, ccode, cname in rows:
            sis = f"{prog}_{class_name}_{ccode}".replace(" ", "_")
            cur.execute(
                "INSERT OR IGNORE INTO canvas_course_links "
                "(class_id, course_id, assignment_id, sis_course_id, course_name, sync_status) "
                "VALUES (?,?,?,?,?, 'pending')",
                (class_id, course_id, ta_id, sis, f"{class_name} — {cname}"),
            )
            created["links"] += 1

    return created


def build_roster_package(conn, scopes: list[str] | None, actor: str = "") -> dict[str, Any]:
    """Official students → Canvas users + suggested enrollments by program."""
    cur = conn.cursor()
    ensure_canvas_tables(cur)
    from ops_data import _scopes_sql

    frag, params = _scopes_sql(scopes, "a.program_code")
    rows = cur.execute(
        "SELECT a.id, a.full_name, a.email, a.program_code, a.cccd, a.status "
        "FROM applications a WHERE a.status = 'official' AND "
        + frag
        + " ORDER BY a.program_code, a.full_name",
        params,
    ).fetchall()

    users = []
    for app_id, name, email, prog, cccd, status in rows:
        sis = _sis_user_id(email, "stu", app_id)
        users.append(
            {
                "user_id": sis,
                "login_id": email or sis,
                "first_name": name.split()[-1] if name else "",
                "last_name": " ".join(name.split()[:-1]) if name and " " in name else name,
                "full_name": name,
                "email": email,
                "status": "active",
                "program_code": prog,
                "local_application_id": app_id,
                "role": "student",
            }
        )
        cur.execute(
            "INSERT INTO canvas_id_map (entity_type, local_key, sis_id, label) VALUES (?,?,?,?) "
            "ON CONFLICT(entity_type, local_key) DO UPDATE SET sis_id=excluded.sis_id, "
            "label=excluded.label, updated_at=CURRENT_TIMESTAMP",
            ("user", f"app:{app_id}", sis, name),
        )

    payload = {
        "kind": "roster",
        "canvas_login_url": CANVAS_LOGIN_URL,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "users": users,
        "counts": {"students": len(users)},
        "sis_csv_hint": "users.csv columns: user_id,login_id,first_name,last_name,email,status",
    }
    title = f"Roster official ({len(users)} HV)"
    cur.execute(
        "INSERT INTO canvas_exports (kind, audience, title, payload_json, created_by, status) "
        "VALUES ('roster','accounting',?,?,?,'ready')",
        (title, json.dumps(payload, ensure_ascii=False), actor),
    )
    export_id = cur.lastrowid
    _log(cur, "export_roster", "accounting", f"export_id={export_id} count={len(users)}", actor)
    conn.commit()
    payload["export_id"] = export_id
    return payload


def build_class_package(conn, class_id: int, actor: str = "") -> dict[str, Any]:
    """One class → courses (from teaching assignments) + student/teacher enrollments."""
    cur = conn.cursor()
    ensure_canvas_tables(cur)
    cg = cur.execute(
        "SELECT id, program_code, name, cohort_year, program_version_id FROM class_groups WHERE id = ?",
        (class_id,),
    ).fetchone()
    if not cg:
        raise ValueError("Class not found")

    class_id, prog, class_name, cohort, _ver = cg
    students = cur.execute(
        "SELECT id, application_id, full_name, email FROM class_students WHERE class_id = ? "
        "ORDER BY full_name",
        (class_id,),
    ).fetchall()
    assignments = cur.execute(
        "SELECT ta.id, ta.course_id, c.code, c.name, "
        "fl.full_name, fl.email, fl.id, "
        "fe.full_name, fe.email, fe.id "
        "FROM teaching_assignments ta "
        "JOIN courses c ON c.id = ta.course_id "
        "LEFT JOIN faculty fl ON fl.id = ta.lecturer_id "
        "LEFT JOIN faculty fe ON fe.id = ta.expert_id "
        "WHERE ta.class_id = ?",
        (class_id,),
    ).fetchall()

    canvas_courses = []
    enrollments = []
    users_by_sis: dict[str, dict] = {}

    def add_user(sis: str, full_name: str, email: str | None, role: str, local_key: str):
        if sis not in users_by_sis:
            users_by_sis[sis] = {
                "user_id": sis,
                "login_id": email or sis,
                "full_name": full_name,
                "email": email,
                "status": "active",
                "role_hint": role,
            }
            cur.execute(
                "INSERT INTO canvas_id_map (entity_type, local_key, sis_id, label) VALUES (?,?,?,?) "
                "ON CONFLICT(entity_type, local_key) DO UPDATE SET sis_id=excluded.sis_id, "
                "label=excluded.label, updated_at=CURRENT_TIMESTAMP",
                ("user", local_key, sis, full_name),
            )

    for sid, app_id, full_name, email in students:
        sis = _sis_user_id(email, "stu", app_id or sid)
        add_user(sis, full_name, email, "student", f"stu:{sid}")

    for (
        ta_id,
        course_id,
        ccode,
        cname,
        lect_name,
        lect_email,
        lect_id,
        exp_name,
        exp_email,
        exp_id,
    ) in assignments:
        sis_course = f"{prog}_{class_name}_{ccode}".replace(" ", "_")
        canvas_courses.append(
            {
                "course_id": sis_course,
                "short_name": ccode,
                "long_name": f"{class_name} — {cname}",
                "status": "active",
                "local_class_id": class_id,
                "local_course_id": course_id,
                "assignment_id": ta_id,
            }
        )
        cur.execute(
            "INSERT INTO canvas_course_links "
            "(class_id, course_id, assignment_id, sis_course_id, course_name, sync_status, updated_at) "
            "VALUES (?,?,?,?,?, 'exported', CURRENT_TIMESTAMP) "
            "ON CONFLICT(class_id, course_id) DO UPDATE SET "
            "sis_course_id=excluded.sis_course_id, sync_status='exported', "
            "course_name=excluded.course_name, updated_at=CURRENT_TIMESTAMP",
            (class_id, course_id, ta_id, sis_course, f"{class_name} — {cname}"),
        )
        cur.execute(
            "INSERT INTO canvas_id_map (entity_type, local_key, sis_id, label) VALUES (?,?,?,?) "
            "ON CONFLICT(entity_type, local_key) DO UPDATE SET sis_id=excluded.sis_id, "
            "label=excluded.label, updated_at=CURRENT_TIMESTAMP",
            ("course", f"class:{class_id}:course:{course_id}", sis_course, cname),
        )

        for sid, app_id, full_name, email in students:
            sis_u = _sis_user_id(email, "stu", app_id or sid)
            enrollments.append(
                {
                    "course_id": sis_course,
                    "user_id": sis_u,
                    "role": "student",
                    "status": "active",
                }
            )
        if lect_id and lect_name:
            sis_t = _sis_user_id(lect_email, "tch", lect_id)
            add_user(sis_t, lect_name, lect_email, "teacher", f"fac:{lect_id}")
            enrollments.append(
                {
                    "course_id": sis_course,
                    "user_id": sis_t,
                    "role": "teacher",
                    "status": "active",
                }
            )
        if exp_id and exp_name:
            sis_e = _sis_user_id(exp_email, "exp", exp_id)
            add_user(sis_e, exp_name, exp_email, "ta", f"fac:{exp_id}")
            enrollments.append(
                {
                    "course_id": sis_course,
                    "user_id": sis_e,
                    "role": "ta",
                    "status": "active",
                }
            )

    payload = {
        "kind": "class_package",
        "canvas_login_url": CANVAS_LOGIN_URL,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "class": {
            "id": class_id,
            "name": class_name,
            "program_code": prog,
            "cohort_year": cohort,
        },
        "users": list(users_by_sis.values()),
        "courses": canvas_courses,
        "enrollments": enrollments,
        "counts": {
            "users": len(users_by_sis),
            "courses": len(canvas_courses),
            "enrollments": len(enrollments),
            "students": len(students),
        },
        "sis_csv_hint": "users.csv, courses.csv, enrollments.csv (Canvas SIS Import)",
    }
    title = f"Lớp {class_name} → Canvas ({len(canvas_courses)} môn)"
    cur.execute(
        "INSERT INTO canvas_exports "
        "(kind, audience, program_code, class_id, title, payload_json, created_by, status) "
        "VALUES ('class_package','coordinator',?,?,?,?,?,'ready')",
        (prog, class_id, title, json.dumps(payload, ensure_ascii=False), actor),
    )
    export_id = cur.lastrowid
    cur.execute(
        "UPDATE canvas_course_links SET last_export_id = ? WHERE class_id = ?",
        (export_id, class_id),
    )
    _log(
        cur,
        "export_class",
        "coordinator",
        f"class_id={class_id} export_id={export_id} courses={len(canvas_courses)}",
        actor,
    )
    conn.commit()
    payload["export_id"] = export_id
    return payload


def payload_to_sis_csvs(payload: dict) -> dict[str, str]:
    """Build SIS CSV strings from a package payload."""
    out: dict[str, str] = {}
    users = payload.get("users") or []
    if users:
        buf = io.StringIO()
        w = csv.DictWriter(
            buf,
            fieldnames=["user_id", "login_id", "first_name", "last_name", "email", "status"],
            extrasaction="ignore",
        )
        w.writeheader()
        for u in users:
            name = u.get("full_name") or ""
            parts = name.split()
            first = parts[-1] if parts else ""
            last = " ".join(parts[:-1]) if len(parts) > 1 else ""
            w.writerow(
                {
                    "user_id": u.get("user_id"),
                    "login_id": u.get("login_id"),
                    "first_name": u.get("first_name") or first,
                    "last_name": u.get("last_name") or last,
                    "email": u.get("email") or "",
                    "status": u.get("status") or "active",
                }
            )
        out["users.csv"] = buf.getvalue()

    courses = payload.get("courses") or []
    if courses:
        buf = io.StringIO()
        w = csv.DictWriter(
            buf, fieldnames=["course_id", "short_name", "long_name", "status"], extrasaction="ignore"
        )
        w.writeheader()
        for c in courses:
            w.writerow(
                {
                    "course_id": c.get("course_id"),
                    "short_name": c.get("short_name"),
                    "long_name": c.get("long_name"),
                    "status": c.get("status") or "active",
                }
            )
        out["courses.csv"] = buf.getvalue()

    enrollments = payload.get("enrollments") or []
    if enrollments:
        buf = io.StringIO()
        w = csv.DictWriter(
            buf, fieldnames=["course_id", "user_id", "role", "status"], extrasaction="ignore"
        )
        w.writeheader()
        for e in enrollments:
            w.writerow(
                {
                    "course_id": e.get("course_id"),
                    "user_id": e.get("user_id"),
                    "role": e.get("role"),
                    "status": e.get("status") or "active",
                }
            )
        out["enrollments.csv"] = buf.getvalue()
    return out


def mark_export_pushed(conn, export_id: int, actor: str = "") -> dict:
    cur = conn.cursor()
    cur.execute("SELECT id, class_id, kind FROM canvas_exports WHERE id = ?", (export_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError("Export not found")
    cur.execute(
        "UPDATE canvas_exports SET status = 'marked_pushed' WHERE id = ?",
        (export_id,),
    )
    if row[1]:
        cur.execute(
            "UPDATE canvas_course_links SET sync_status = 'sent', updated_at = CURRENT_TIMESTAMP "
            "WHERE class_id = ?",
            (row[1],),
        )
    _log(cur, "mark_pushed", "it", f"export_id={export_id} kind={row[2]}", actor)
    conn.commit()
    return {"ok": True, "export_id": export_id, "status": "sent", "sync_status": "sent"}


def mark_canvas_accepted(conn, class_id: int, actor: str = "") -> dict:
    cur = conn.cursor()
    cur.execute(
        "UPDATE canvas_course_links SET sync_status = 'accepted', updated_at = CURRENT_TIMESTAMP "
        "WHERE class_id = ?",
        (class_id,),
    )
    if not cur.rowcount:
        raise ValueError("Không tìm thấy liên kết Canvas")
    _log(cur, "canvas_accepted", "it", f"class_id={class_id}", actor)
    conn.commit()
    return {"ok": True, "class_id": class_id, "sync_status": "accepted"}


def hub_for_audience(conn, audience: str, scopes: list[str] | None = None) -> dict[str, Any]:
    cur = conn.cursor()
    ensure_canvas_tables(cur)
    from ops_data import _scopes_sql

    guides = cur.execute(
        "SELECT step_order, title, detail, smartuni_perm, canvas_area "
        "FROM canvas_audience_guides WHERE audience = ? ORDER BY step_order",
        (audience,),
    ).fetchall()
    guide_list = [
        {
            "step": r[0],
            "title": r[1],
            "detail": r[2],
            "smartuni_perm": r[3],
            "canvas_area": r[4],
        }
        for r in guides
    ]

    base = {
        "audience": audience,
        "canvas_login_url": CANVAS_LOGIN_URL,
        "canvas_base": CANVAS_BASE_HINT,
        "guides": guide_list,
        "actions": [],
        "stats": {},
        "rows": [],
        "columns": [],
    }

    if audience == "coordinator":
        frag, params = _scopes_sql(scopes, "cg.program_code")
        rows = cur.execute(
            "SELECT cg.id, cg.name, cg.program_code, cg.cohort_year, "
            "COUNT(DISTINCT cs.id), COUNT(DISTINCT ccl.id), "
            "SUM(CASE WHEN ccl.sync_status = 'pending' THEN 1 ELSE 0 END), "
            "SUM(CASE WHEN ccl.sync_status IN ('exported','sent','accepted','live') THEN 1 ELSE 0 END) "
            "FROM class_groups cg "
            "LEFT JOIN class_students cs ON cs.class_id = cg.id "
            "LEFT JOIN canvas_course_links ccl ON ccl.class_id = cg.id "
            f"WHERE {frag} "
            "GROUP BY cg.id ORDER BY cg.program_code, cg.name",
            params,
        ).fetchall()
        base["columns"] = [
            ("name", "Lớp"),
            ("program_code", "CT"),
            ("cohort_year", "Khóa"),
            ("student_count", "HV"),
            ("course_links", "Môn map"),
            ("pending", "Chờ đẩy"),
            ("synced", "Đã xuất/live"),
            ("sync_label", "Canvas"),
        ]
        base["rows"] = [
            {
                "id": r[0],
                "name": r[1],
                "program_code": r[2],
                "cohort_year": r[3],
                "student_count": r[4] or 0,
                "course_links": r[5] or 0,
                "pending": r[6] or 0,
                "synced": r[7] or 0,
                "sync_label": "Cần xuất" if (r[6] or 0) > 0 or (r[5] or 0) == 0 else "Đã chuẩn bị",
                "status": "pending" if (r[6] or 0) > 0 or (r[5] or 0) == 0 else "exported",
            }
            for r in rows
        ]
        base["stats"] = {
            "classes": len(rows),
            "need_export": sum(1 for x in base["rows"] if x["status"] == "pending"),
        }
        base["actions"] = [
            {"id": "export_class", "label": "Xuất gói lớp → Canvas"},
            {"id": "view_exports", "label": "Xem gói đã tạo"},
        ]
        base["title"] = "Canvas — Điều phối chương trình"
        base["desc"] = (
            "Tạo gói SIS (users/courses/enrollments) từ lớp SmartUni để đưa lên Canvas."
        )

    elif audience == "faculty":
        rows = cur.execute(
            "SELECT ta.id, cg.name, c.code, c.name, fl.full_name, fe.full_name, "
            "ccl.sis_course_id, ccl.sync_status, cg.program_code "
            "FROM teaching_assignments ta "
            "JOIN class_groups cg ON cg.id = ta.class_id "
            "JOIN courses c ON c.id = ta.course_id "
            "LEFT JOIN faculty fl ON fl.id = ta.lecturer_id "
            "LEFT JOIN faculty fe ON fe.id = ta.expert_id "
            "LEFT JOIN canvas_course_links ccl ON ccl.assignment_id = ta.id "
            "ORDER BY cg.program_code, cg.name, c.code"
        ).fetchall()
        # scope filter in python if needed
        if scopes and "*" not in scopes:
            rows = [r for r in rows if r[8] in scopes]
        base["columns"] = [
            ("class_name", "Lớp"),
            ("program_code", "CT"),
            ("course_code", "Mã HP"),
            ("course_name", "Học phần"),
            ("lecturer", "GV LT"),
            ("expert", "Chuyên gia"),
            ("sis_course_id", "SIS Course"),
            ("sync_status", "TT Canvas"),
        ]
        base["rows"] = [
            {
                "id": r[0],
                "class_name": r[1],
                "course_code": r[2],
                "course_name": r[3],
                "lecturer": r[4] or "—",
                "expert": r[5] or "—",
                "sis_course_id": r[6] or "—",
                "sync_status": r[7] or "pending",
                "program_code": r[8],
                "status": r[7] or "pending",
            }
            for r in rows
        ]
        base["stats"] = {
            "assignments": len(base["rows"]),
            "live": sum(1 for x in base["rows"] if x["sync_status"] == "live"),
        }
        base["actions"] = [
            {"id": "open_canvas", "label": "Mở Canvas"},
            {"id": "materials_checklist", "label": "Checklist tài liệu"},
        ]
        base["title"] = "Canvas — Giảng viên / Chuyên gia"
        base["desc"] = (
            "Theo dõi lớp–môn trên Canvas: tài liệu, bài tập, chấm SpeedGrader."
        )

    elif audience == "student":
        rows = cur.execute(
            "SELECT cs.id, cs.full_name, cs.email, cg.name, cg.program_code, "
            "COUNT(ccl.id), "
            "SUM(CASE WHEN ccl.sync_status IN ('exported','sent','accepted','live') THEN 1 ELSE 0 END) "
            "FROM class_students cs "
            "JOIN class_groups cg ON cg.id = cs.class_id "
            "LEFT JOIN canvas_course_links ccl ON ccl.class_id = cg.id "
            "GROUP BY cs.id ORDER BY cg.program_code, cs.full_name"
        ).fetchall()
        if scopes and "*" not in scopes:
            rows = [r for r in rows if r[4] in scopes]
        base["columns"] = [
            ("full_name", "Họ tên"),
            ("email", "Email login Canvas"),
            ("class_name", "Lớp"),
            ("program_code", "CT"),
            ("courses_total", "Số môn"),
            ("courses_ready", "Đã trên Canvas"),
            ("access", "Truy cập"),
        ]
        base["rows"] = [
            {
                "id": r[0],
                "full_name": r[1],
                "email": r[2] or "—",
                "class_name": r[3],
                "program_code": r[4],
                "courses_total": r[5] or 0,
                "courses_ready": r[6] or 0,
                "access": "Sẵn sàng" if (r[6] or 0) > 0 else "Chờ Điều phối xuất",
                "status": "live" if (r[6] or 0) > 0 else "pending",
            }
            for r in rows
        ]
        base["stats"] = {
            "students": len(base["rows"]),
            "ready": sum(1 for x in base["rows"] if x["status"] == "live"),
        }
        base["actions"] = [
            {"id": "open_canvas", "label": "Đăng nhập Canvas"},
            {"id": "guide", "label": "Hướng dẫn sử dụng"},
        ]
        base["title"] = "Canvas — Học viên"
        base["desc"] = (
            "Trạng thái enroll và hướng dẫn truy cập https://cfvg.instructure.com"
        )

    elif audience == "accounting":
        frag, params = _scopes_sql(scopes, "program_code")
        official = cur.execute(
            "SELECT COUNT(*) FROM applications WHERE status='official' AND " + frag,
            params,
        ).fetchone()[0]
        paid_pending = cur.execute(
            "SELECT COUNT(*) FROM enrollment_fees ef "
            "JOIN applications a ON a.id = ef.application_id "
            f"WHERE ef.status='paid' AND a.status != 'official' AND {_scopes_sql(scopes, 'a.program_code')[0]}",
            _scopes_sql(scopes, "a.program_code")[1],
        ).fetchone()[0]
        recent = cur.execute(
            "SELECT id, title, status, created_at FROM canvas_exports "
            "WHERE kind='roster' ORDER BY id DESC LIMIT 10"
        ).fetchall()
        base["columns"] = [
            ("id", "Mã gói"),
            ("title", "Nội dung"),
            ("status", "TT"),
            ("created_at", "Tạo lúc"),
        ]
        base["rows"] = [
            {"id": r[0], "title": r[1], "status": r[2], "created_at": r[3]} for r in recent
        ]
        base["stats"] = {
            "official": official,
            "paid_not_official": paid_pending,
            "roster_exports": len(recent),
        }
        base["actions"] = [
            {"id": "export_roster", "label": "Xuất roster → Canvas"},
            {"id": "open_official", "label": "DS trúng tuyển chính thức"},
        ]
        base["title"] = "Canvas — Kế toán / Ghi danh"
        base["desc"] = (
            "Chỉ HV official (sau nộp phí) được đưa vào gói Users Canvas."
        )

    elif audience == "it":
        maps = cur.execute("SELECT COUNT(*) FROM canvas_id_map").fetchone()[0]
        exports = cur.execute("SELECT COUNT(*) FROM canvas_exports").fetchone()[0]
        pending_links = cur.execute(
            "SELECT COUNT(*) FROM canvas_course_links WHERE sync_status='pending'"
        ).fetchone()[0]
        logs = cur.execute(
            "SELECT id, action, audience, detail, actor, created_at "
            "FROM canvas_sync_log ORDER BY id DESC LIMIT 30"
        ).fetchall()
        base["columns"] = [
            ("created_at", "Thời điểm"),
            ("action", "Hành động"),
            ("audience", "Đối tượng"),
            ("detail", "Chi tiết"),
            ("actor", "Người thực hiện"),
        ]
        base["rows"] = [
            {
                "id": r[0],
                "action": r[1],
                "audience": r[2],
                "detail": r[3],
                "actor": r[4] or "—",
                "created_at": r[5],
            }
            for r in logs
        ]
        base["stats"] = {
            "id_maps": maps,
            "exports": exports,
            "pending_course_links": pending_links,
        }
        base["actions"] = [
            {"id": "view_maps", "label": "Xem SIS map"},
            {"id": "mark_pushed", "label": "Đánh dấu đã đẩy Canvas"},
        ]
        base["title"] = "Canvas — IT / Quản trị"
        base["desc"] = (
            "Cấu hình, map SIS ID, nhật ký đồng bộ. Token API gắn khi triển khai production."
        )
        id_rows = cur.execute(
            "SELECT entity_type, local_key, sis_id, label, updated_at "
            "FROM canvas_id_map ORDER BY updated_at DESC LIMIT 50"
        ).fetchall()
        base["id_maps"] = [
            {
                "entity_type": r[0],
                "local_key": r[1],
                "sis_id": r[2],
                "label": r[3],
                "updated_at": r[4],
            }
            for r in id_rows
        ]

    else:
        raise ValueError("Unknown audience")

    return base


def list_exports(conn, limit: int = 50) -> list[dict]:
    cur = conn.cursor()
    ensure_canvas_tables(cur)
    rows = cur.execute(
        "SELECT id, kind, audience, program_code, class_id, title, status, created_by, created_at "
        "FROM canvas_exports ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {
            "id": r[0],
            "kind": r[1],
            "audience": r[2],
            "program_code": r[3],
            "class_id": r[4],
            "title": r[5],
            "status": r[6],
            "created_by": r[7],
            "created_at": r[8],
        }
        for r in rows
    ]


def get_export(conn, export_id: int) -> dict | None:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id, kind, audience, program_code, class_id, title, payload_json, status, "
        "created_by, created_at FROM canvas_exports WHERE id = ?",
        (export_id,),
    ).fetchone()
    if not row:
        return None
    payload = json.loads(row[6])
    return {
        "id": row[0],
        "kind": row[1],
        "audience": row[2],
        "program_code": row[3],
        "class_id": row[4],
        "title": row[5],
        "payload": payload,
        "sis_csvs": payload_to_sis_csvs(payload),
        "status": row[7],
        "created_by": row[8],
        "created_at": row[9],
    }
