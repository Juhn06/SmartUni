"""
eLearning ops v1: online lectures, objectives, tracker, exam integrity,
study plan / time-to-learn / agenda, return meetings.

Rule-based advisors (no LLM). Face match / video studio are out of scope.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ops_data import _scopes_sql

BACKEND_DIR = Path(__file__).resolve().parent
EXAM_SELFIE_DIR = BACKEND_DIR / "uploads" / "elearn_exam"
DEFAULT_LESSON_MIN = 45
DEFAULT_STEPS = ["Xem bài giảng", "Thảo luận / hỏi đáp", "Làm bài tập"]


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def _now_cmp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M")


def ensure_elearn_tables(cur) -> None:
    from class_lessons import ensure_class_lesson_tables

    ensure_class_lesson_tables(cur)
    cur.execute(
        "CREATE TABLE IF NOT EXISTS elearn_objectives ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "assignment_id INTEGER, "
        "course_id INTEGER, "
        "lesson_id INTEGER, "
        "source_key TEXT NOT NULL, "
        "title TEXT NOT NULL, "
        "steps_json TEXT, "
        "source TEXT DEFAULT 'syllabus', "
        "program_code TEXT, "
        "class_name TEXT, "
        "course_code TEXT, "
        "status TEXT DEFAULT 'active', "
        "created_at TEXT)"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_elearn_obj_source "
        "ON elearn_objectives(assignment_id, source_key)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS elearn_objective_recs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "student_id INTEGER, "
        "student_email TEXT, "
        "student_name TEXT, "
        "objective_id INTEGER, "
        "title TEXT, "
        "reason TEXT, "
        "how_to TEXT, "
        "status TEXT DEFAULT 'suggested', "
        "program_code TEXT, "
        "created_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS elearn_study_plans ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "student_id INTEGER, "
        "student_email TEXT, "
        "student_name TEXT, "
        "title TEXT, "
        "status TEXT DEFAULT 'active', "
        "program_code TEXT, "
        "generated_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS elearn_plan_items ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "plan_id INTEGER NOT NULL, "
        "lesson_id INTEGER, "
        "topic TEXT NOT NULL, "
        "estimated_min INTEGER DEFAULT 45, "
        "remaining_min INTEGER DEFAULT 45, "
        "mastery REAL DEFAULT 0.1, "
        "due_date TEXT, "
        "status TEXT DEFAULT 'open', "
        "FOREIGN KEY (plan_id) REFERENCES elearn_study_plans(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS elearn_agenda ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "student_id INTEGER, "
        "student_email TEXT, "
        "student_name TEXT, "
        "plan_item_id INTEGER, "
        "title TEXT NOT NULL, "
        "starts_at TEXT, "
        "ends_at TEXT, "
        "status TEXT DEFAULT 'planned', "
        "program_code TEXT, "
        "created_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS elearn_exam_sittings ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "exam_id INTEGER NOT NULL, "
        "student_id INTEGER, "
        "student_email TEXT, "
        "student_name TEXT, "
        "class_id INTEGER, "
        "identity_status TEXT DEFAULT 'pending', "
        "cccd_confirmed INTEGER DEFAULT 0, "
        "honor_ack INTEGER DEFAULT 0, "
        "selfie_path TEXT, "
        "selfie_name TEXT, "
        "notes TEXT, "
        "program_code TEXT, "
        "exam_title TEXT, "
        "exam_date TEXT, "
        "created_at TEXT)"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_elearn_sitting "
        "ON elearn_exam_sittings(exam_id, student_id)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS elearn_return_meetings ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "student_id INTEGER, "
        "student_email TEXT, "
        "student_name TEXT, "
        "lifecycle_status TEXT, "
        "starts_at TEXT, "
        "meeting_url TEXT, "
        "reason TEXT, "
        "support_note TEXT, "
        "status TEXT DEFAULT 'scheduled', "
        "program_code TEXT, "
        "class_name TEXT, "
        "created_at TEXT)"
    )


def _user_login(conn, user_id: int | None) -> tuple[str, str]:
    if not user_id:
        return "", ""
    row = conn.execute(
        "SELECT email, name FROM user WHERE id = ?", (user_id,)
    ).fetchone()
    if not row:
        return "", ""
    return (row[0] or "", row[1] or "")


def _student_ident(conn, actor: dict | None) -> dict:
    from e2e_pipeline import resolve_student_identity

    if not actor or not actor.get("user_id"):
        return {}
    ident = resolve_student_identity(conn, user_id=actor["user_id"]) or {}
    st = ident.get("student") or {}
    app = ident.get("application") or {}
    login, name = _user_login(conn, actor.get("user_id"))
    email = (st.get("email") or app.get("email") or login or "").strip()
    return {
        "student_id": st.get("id"),
        "student_email": email,
        "student_name": st.get("full_name") or app.get("full_name") or name,
        "program_code": st.get("program_code") or app.get("program_code") or "",
        "class_id": st.get("class_id"),
        "lifecycle_status": st.get("lifecycle_status") or "",
    }


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _watch_sec_by_lesson(conn, email: str = "", user_id: int | None = None) -> dict[int, int]:
    cur = conn.cursor()
    if email:
        rows = cur.execute(
            "SELECT lesson_id, COALESCE(SUM(duration_sec),0) FROM lesson_view_sessions "
            "WHERE lower(student_email)=lower(?) GROUP BY lesson_id",
            (email,),
        ).fetchall()
    elif user_id:
        rows = cur.execute(
            "SELECT lesson_id, COALESCE(SUM(duration_sec),0) FROM lesson_view_sessions "
            "WHERE user_id=? GROUP BY lesson_id",
            (user_id,),
        ).fetchall()
    else:
        return {}
    return {int(r[0]): int(r[1] or 0) for r in rows}


def _published_sql() -> str:
    return (
        "cl.status = 'published' AND ("
        "IFNULL(cl.publish_at,'') = '' OR cl.publish_at <= ?"
        ")"
    )


def list_online_lectures(
    conn, scopes: list[str] | None, *, q: str = "", as_student: bool = False
) -> list[dict]:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    now = _now_cmp()
    extra = ""
    extra_params: list[Any] = []
    if as_student:
        extra = f" AND {_published_sql()}"
        extra_params.append(now)
    sql = (
        "SELECT cl.id, cl.assignment_id, cl.lesson_no, cl.title, cl.status, "
        "cl.video_url, cl.publish_at, cl.duration_min, cl.group_id, cl.preview_summary, "
        "cg.name, cg.program_code, c.code, c.name, ta.id, "
        "(SELECT COUNT(*) FROM lesson_comments lc WHERE lc.lesson_id = cl.id), "
        "(SELECT COUNT(*) FROM course_materials m WHERE m.lesson_id = cl.id) "
        "FROM class_lessons cl "
        "JOIN teaching_assignments ta ON ta.id = cl.assignment_id "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        f"WHERE {frag}{extra} "
        "ORDER BY cg.name, c.code, cl.lesson_no"
    )
    rows = cur.execute(sql, [*params, *extra_params]).fetchall()
    out = []
    ql = q.lower().strip()
    for r in rows:
        item = {
            "id": r[0],
            "assignment_id": r[1],
            "lesson_no": r[2],
            "title": r[3],
            "status": r[4],
            "video_url": r[5] or "",
            "publish_at": r[6] or "",
            "duration_min": r[7] or DEFAULT_LESSON_MIN,
            "group_id": r[8],
            "preview_summary": r[9] or "",
            "class_name": r[10],
            "program_code": r[11],
            "course_code": r[12],
            "course_name": r[13],
            "comment_count": r[15] or 0,
            "material_count": r[16] or 0,
        }
        if ql:
            blob = " ".join(str(v) for v in item.values() if v not in (None, "")).lower()
            if ql not in blob:
                continue
        out.append(item)
    return out


def create_online_lecture(conn, data: dict) -> dict:
    from class_lessons import add_class_lesson, get_class_lesson, update_class_lesson

    aid = data.get("assignment_id")
    try:
        aid = int(aid)
    except (TypeError, ValueError):
        raise ValueError("Cần ID phân giảng (assignment_id).")
    payload = dict(data)
    status = (payload.get("status") or "draft").strip() or "draft"
    if payload.get("publish_now") in (1, "1", True, "true"):
        status = "published"
    payload["status"] = status
    row = add_class_lesson(conn, aid, payload)
    extra = {}
    for key in ("video_url", "publish_at", "duration_min", "group_id"):
        if key in data and data[key] not in (None, ""):
            extra[key] = data[key]
    if extra:
        update_class_lesson(conn, row["id"], extra)
        row = get_class_lesson(conn, row["id"], as_student=False) or row
    return row


def list_objectives(conn, scopes: list[str] | None, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    frag, params = _scopes_sql(scopes, "program_code")
    rows = cur.execute(
        "SELECT id, assignment_id, course_id, lesson_id, source_key, title, steps_json, "
        "source, program_code, class_name, course_code, status, created_at "
        f"FROM elearn_objectives WHERE {frag} ORDER BY id DESC",
        params,
    ).fetchall()
    ql = q.lower().strip()
    out = []
    for r in rows:
        steps = []
        try:
            steps = json.loads(r[6] or "[]")
        except Exception:
            steps = []
        item = {
            "id": r[0],
            "assignment_id": r[1],
            "course_id": r[2],
            "lesson_id": r[3],
            "source_key": r[4],
            "title": r[5],
            "steps": steps,
            "steps_text": " → ".join(steps) if isinstance(steps, list) else str(steps or ""),
            "source": r[7],
            "program_code": r[8],
            "class_name": r[9],
            "course_code": r[10],
            "status": r[11],
            "created_at": r[12],
        }
        if ql:
            blob = " ".join(str(v) for v in item.values() if v not in (None, "")).lower()
            if ql not in blob:
                continue
        out.append(item)
    return out


def generate_objectives_from_syllabus(conn, scopes: list[str] | None) -> dict:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    lessons = cur.execute(
        "SELECT cl.id, cl.assignment_id, cl.lesson_no, cl.title, cl.objectives, "
        "ta.course_id, cg.program_code, cg.name, c.code "
        "FROM class_lessons cl "
        "JOIN teaching_assignments ta ON ta.id = cl.assignment_id "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        f"WHERE {frag} ORDER BY ta.id, cl.lesson_no",
        params,
    ).fetchall()
    created = 0
    now = _now()
    steps = json.dumps(DEFAULT_STEPS, ensure_ascii=False)
    for r in lessons:
        lid, aid, no, title, obj, course_id, prog, cname, ccode = r
        source_key = f"lesson:{lid}"
        goal = (obj or "").strip() or f"Hoàn thành buổi {no}: {title}"
        exists = cur.execute(
            "SELECT id FROM elearn_objectives WHERE assignment_id=? AND source_key=?",
            (aid, source_key),
        ).fetchone()
        if exists:
            continue
        cur.execute(
            "INSERT INTO elearn_objectives "
            "(assignment_id, course_id, lesson_id, source_key, title, steps_json, source, "
            "program_code, class_name, course_code, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                aid, course_id, lid, source_key, goal[:400], steps, "syllabus",
                prog, cname, ccode, "active", now,
            ),
        )
        created += 1
    if created == 0 and not lessons:
        frag_s, params_s = _scopes_sql(scopes, "v.program_code")
        sessions = cur.execute(
            "SELECT s.id, s.course_id, s.session_no, s.title, v.program_code, c.code "
            "FROM course_sessions s "
            "JOIN courses c ON c.id = s.course_id "
            "JOIN program_versions v ON v.id = c.program_version_id "
            f"WHERE {frag_s}",
            params_s,
        ).fetchall()
        for s in sessions:
            source_key = f"session:{s[0]}"
            exists = cur.execute(
                "SELECT id FROM elearn_objectives WHERE source_key=? AND IFNULL(assignment_id,0)=0",
                (source_key,),
            ).fetchone()
            if exists:
                continue
            title = (s[3] or f"Buổi {s[2]}").strip()
            cur.execute(
                "INSERT INTO elearn_objectives "
                "(assignment_id, course_id, lesson_id, source_key, title, steps_json, source, "
                "program_code, class_name, course_code, status, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    None, s[1], None, source_key, f"Đạt mục tiêu: {title}"[:400], steps,
                    "syllabus", s[4], "", s[5], "active", now,
                ),
            )
            created += 1
    conn.commit()
    return {"ok": True, "created": created, "rows": list_objectives(conn, scopes)}


def list_instructor_intel(conn, scopes: list[str] | None, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    rows = cur.execute(
        "SELECT ta.id, cg.name, cg.program_code, c.code, c.name, "
        "(SELECT COUNT(*) FROM class_lessons cl WHERE cl.assignment_id=ta.id), "
        "(SELECT COUNT(*) FROM class_lessons cl WHERE cl.assignment_id=ta.id AND cl.status='published'), "
        "(SELECT COUNT(*) FROM lesson_comments lc JOIN class_lessons cl ON cl.id=lc.lesson_id "
        " WHERE cl.assignment_id=ta.id AND lc.comment_type='question'), "
        "(SELECT COALESCE(SUM(vs.duration_sec),0) FROM lesson_view_sessions vs "
        " JOIN class_lessons cl ON cl.id=vs.lesson_id WHERE cl.assignment_id=ta.id), "
        "(SELECT COUNT(*) FROM class_students cs WHERE cs.class_id=ta.class_id) "
        "FROM teaching_assignments ta "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        f"WHERE {frag} ORDER BY cg.name, c.code",
        params,
    ).fetchall()
    ql = q.lower().strip()
    out = []
    for r in rows:
        watch_min = int((r[8] or 0) / 60)
        students = r[9] or 0
        avg_min = round(watch_min / students, 1) if students else 0
        item = {
            "id": r[0],
            "assignment_id": r[0],
            "class_name": r[1],
            "program_code": r[2],
            "course_code": r[3],
            "course_name": r[4],
            "lesson_count": r[5] or 0,
            "published_count": r[6] or 0,
            "open_questions": r[7] or 0,
            "watch_min": watch_min,
            "student_count": students,
            "avg_watch_min": avg_min,
            "at_risk_count": 0,
            "status": "watch" if avg_min < 10 and students else "ok",
        }
        if ql:
            blob = " ".join(str(v) for v in item.values()).lower()
            if ql not in blob:
                continue
        out.append(item)
    track = list_student_tracker(conn, scopes)
    by_asg: dict[int, int] = {}
    for t in track:
        if t.get("at_risk"):
            by_asg[int(t.get("assignment_id") or 0)] = by_asg.get(int(t.get("assignment_id") or 0), 0) + 1
    for item in out:
        item["at_risk_count"] = by_asg.get(item["assignment_id"], 0)
        if item["at_risk_count"]:
            item["status"] = "at_risk"
    return out


def list_student_tracker(
    conn, scopes: list[str] | None, *, q: str = "", student_email: str = ""
) -> list[dict]:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    extra = ""
    extra_p: list[Any] = []
    if student_email:
        extra = " AND lower(cs.email)=lower(?)"
        extra_p.append(student_email)
    rows = cur.execute(
        "SELECT cs.id, cs.full_name, cs.email, cs.student_code, cs.lifecycle_status, "
        "cg.name, cg.program_code, ta.id, c.code, "
        "(SELECT COALESCE(SUM(vs.duration_sec),0) FROM lesson_view_sessions vs "
        " JOIN class_lessons cl ON cl.id=vs.lesson_id "
        " WHERE cl.assignment_id=ta.id AND lower(vs.student_email)=lower(cs.email)), "
        "(SELECT COUNT(*) FROM class_lessons cl WHERE cl.assignment_id=ta.id AND cl.status='published') "
        "FROM class_students cs "
        "JOIN class_groups cg ON cg.id = cs.class_id "
        "JOIN teaching_assignments ta ON ta.class_id = cg.id "
        "JOIN courses c ON c.id = ta.course_id "
        f"WHERE {frag}{extra} "
        "ORDER BY cs.full_name, c.code",
        [*params, *extra_p],
    ).fetchall()
    ql = q.lower().strip()
    out = []
    for r in rows:
        watch_min = int((r[9] or 0) / 60)
        lessons = r[10] or 0
        expected = lessons * DEFAULT_LESSON_MIN
        pct = round(100.0 * watch_min / expected, 1) if expected else 0
        at_risk = pct < 30 and lessons > 0
        item = {
            "id": f"{r[0]}-{r[7]}",
            "student_id": r[0],
            "full_name": r[1],
            "email": r[2],
            "student_code": r[3],
            "lifecycle_status": r[4] or "active",
            "class_name": r[5],
            "program_code": r[6],
            "assignment_id": r[7],
            "course_code": r[8],
            "watch_min": watch_min,
            "lesson_count": lessons,
            "progress_pct": pct,
            "at_risk": 1 if at_risk else 0,
            "status": "at_risk" if at_risk else "ok",
        }
        if ql:
            blob = " ".join(str(v) for v in item.values() if v not in (None, "")).lower()
            if ql not in blob:
                continue
        out.append(item)
    return out


def _topic_rows_for_student(conn, ident: dict) -> list[dict]:
    cur = conn.cursor()
    email = ident.get("student_email") or ""
    now = _now_cmp()
    if ident.get("class_id"):
        rows = cur.execute(
            "SELECT cl.id, cl.title, cl.duration_min, cl.lesson_no, c.code, cg.program_code "
            "FROM class_lessons cl "
            "JOIN teaching_assignments ta ON ta.id = cl.assignment_id "
            "JOIN class_groups cg ON cg.id = ta.class_id "
            "JOIN courses c ON c.id = ta.course_id "
            f"WHERE ta.class_id=? AND {_published_sql()} "
            "ORDER BY c.code, cl.lesson_no",
            (ident["class_id"], now),
        ).fetchall()
    else:
        rows = cur.execute(
            "SELECT cl.id, cl.title, cl.duration_min, cl.lesson_no, c.code, cg.program_code "
            "FROM class_lessons cl "
            "JOIN teaching_assignments ta ON ta.id = cl.assignment_id "
            "JOIN class_groups cg ON cg.id = ta.class_id "
            "JOIN courses c ON c.id = ta.course_id "
            f"WHERE {_published_sql()} ORDER BY c.code, cl.lesson_no LIMIT 40",
            (now,),
        ).fetchall()
    watch = _watch_sec_by_lesson(conn, email=email, user_id=None)
    topics = []
    for r in rows:
        est = int(r[2] or DEFAULT_LESSON_MIN) or DEFAULT_LESSON_MIN
        seen_min = (watch.get(int(r[0]), 0) or 0) / 60.0
        mastery = _clamp(seen_min / est if est else 0.1, 0.1, 0.95)
        remaining = int(round(est * (1.0 - mastery)))
        topics.append(
            {
                "lesson_id": r[0],
                "topic": f"{r[4]} · Buổi {r[3]}: {r[1]}",
                "estimated_min": est,
                "remaining_min": remaining,
                "mastery": round(mastery, 2),
                "program_code": r[5],
                "status": "done" if remaining <= 5 else "open",
            }
        )
    return topics


def list_time_to_learn(conn, actor: dict, scopes: list[str] | None, *, q: str = "") -> list[dict]:
    ensure_elearn_tables(conn.cursor())
    ident = _student_ident(conn, actor)
    depts = set(actor.get("dept_codes") or [])
    staff = bool(actor.get("is_admin") or (depts & {"mba", "master_chuyen_nganh", "giang_vien", "admin_he_thong"}))
    if staff and not ident.get("student_id"):
        track = list_student_tracker(conn, scopes, q=q)
        out = []
        for t in track:
            est = (t.get("lesson_count") or 0) * DEFAULT_LESSON_MIN
            remaining = max(0, est - (t.get("watch_min") or 0))
            mastery = _clamp((t.get("watch_min") or 0) / est if est else 0.1, 0.1, 0.95)
            out.append(
                {
                    "id": t["id"],
                    "student_name": t.get("full_name"),
                    "topic": t.get("course_code"),
                    "estimated_min": est,
                    "remaining_min": remaining,
                    "mastery": round(mastery, 2),
                    "program_code": t.get("program_code"),
                    "status": t.get("status"),
                }
            )
        return out
    topics = _topic_rows_for_student(conn, ident)
    ql = q.lower().strip()
    out = []
    for i, t in enumerate(topics, start=1):
        item = {"id": t.get("lesson_id") or i, **t, "student_name": ident.get("student_name")}
        if ql and ql not in " ".join(str(v) for v in item.values()).lower():
            continue
        out.append(item)
    return out


def generate_time_to_learn(conn, actor: dict, scopes: list[str] | None) -> dict:
    rows = list_time_to_learn(conn, actor, scopes)
    return {"ok": True, "count": len(rows), "rows": rows}


def list_study_plans(conn, actor: dict, scopes: list[str] | None, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    ident = _student_ident(conn, actor)
    depts = set(actor.get("dept_codes") or [])
    staff = bool(actor.get("is_admin") or (depts & {"mba", "master_chuyen_nganh", "giang_vien", "admin_he_thong"}))
    sql = (
        "SELECT p.id, p.student_id, p.student_email, p.student_name, p.title, p.status, "
        "p.program_code, p.generated_at, "
        "(SELECT COUNT(*) FROM elearn_plan_items i WHERE i.plan_id=p.id), "
        "(SELECT COALESCE(SUM(i.remaining_min),0) FROM elearn_plan_items i WHERE i.plan_id=p.id) "
        "FROM elearn_study_plans p WHERE 1=1"
    )
    params: list[Any] = []
    if not staff:
        if ident.get("student_id"):
            sql += " AND p.student_id=?"
            params.append(ident["student_id"])
        elif ident.get("student_email"):
            sql += " AND lower(p.student_email)=lower(?)"
            params.append(ident["student_email"])
        else:
            return []
    else:
        frag, sp = _scopes_sql(scopes, "p.program_code")
        sql += f" AND {frag}"
        params.extend(sp)
    sql += " ORDER BY p.id DESC"
    rows = cur.execute(sql, params).fetchall()
    ql = q.lower().strip()
    out = []
    for r in rows:
        item = {
            "id": r[0],
            "student_id": r[1],
            "student_email": r[2],
            "student_name": r[3],
            "title": r[4],
            "status": r[5],
            "program_code": r[6],
            "generated_at": r[7],
            "item_count": r[8] or 0,
            "remaining_min": r[9] or 0,
        }
        if ql:
            blob = " ".join(str(v) for v in item.values() if v not in (None, "")).lower()
            if ql not in blob:
                continue
        out.append(item)
    return out


def generate_study_plan(conn, actor: dict, scopes: list[str] | None) -> dict:
    ident = _student_ident(conn, actor)
    if not ident.get("student_email") and not ident.get("student_id"):
        raise ValueError("Không gắn được tài khoản với học viên — chỉ HV đã nhập học mới tạo kế hoạch.")
    topics = _topic_rows_for_student(conn, ident)
    open_topics = [t for t in topics if (t.get("remaining_min") or 0) > 5]
    if not open_topics:
        open_topics = topics[:8]
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    cur.execute(
        "UPDATE elearn_study_plans SET status='archived' WHERE student_email=? AND status='active'",
        (ident.get("student_email") or "",),
    )
    now = _now()
    title = f"Kế hoạch học {now[:10]}"
    cur.execute(
        "INSERT INTO elearn_study_plans "
        "(student_id, student_email, student_name, title, status, program_code, generated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            ident.get("student_id"), ident.get("student_email"), ident.get("student_name"),
            title, "active", ident.get("program_code") or "", now,
        ),
    )
    pid = cur.lastrowid
    day = datetime.utcnow().date()
    for i, t in enumerate(open_topics):
        due = (day + timedelta(days=i + 1)).isoformat()
        cur.execute(
            "INSERT INTO elearn_plan_items "
            "(plan_id, lesson_id, topic, estimated_min, remaining_min, mastery, due_date, status) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                pid, t.get("lesson_id"), t["topic"], t["estimated_min"], t["remaining_min"],
                t["mastery"], due, t.get("status") or "open",
            ),
        )
    conn.commit()
    return {"ok": True, "plan_id": pid, "items": len(open_topics)}


def list_objective_recs(conn, actor: dict, scopes: list[str] | None, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    ident = _student_ident(conn, actor)
    depts = set(actor.get("dept_codes") or [])
    staff = bool(actor.get("is_admin") or (depts & {"mba", "master_chuyen_nganh", "giang_vien", "admin_he_thong"}))
    sql = (
        "SELECT id, student_id, student_email, student_name, objective_id, title, reason, "
        "how_to, status, program_code, created_at FROM elearn_objective_recs WHERE 1=1"
    )
    params: list[Any] = []
    if not staff:
        if ident.get("student_email"):
            sql += " AND lower(student_email)=lower(?)"
            params.append(ident["student_email"])
        else:
            return []
    else:
        frag, sp = _scopes_sql(scopes, "program_code")
        sql += f" AND {frag}"
        params.extend(sp)
    sql += " ORDER BY id DESC"
    rows = cur.execute(sql, params).fetchall()
    ql = q.lower().strip()
    keys = [
        "id", "student_id", "student_email", "student_name", "objective_id", "title",
        "reason", "how_to", "status", "program_code", "created_at",
    ]
    out = []
    for r in rows:
        item = dict(zip(keys, r))
        if ql and ql not in " ".join(str(v) for v in item.values() if v).lower():
            continue
        out.append(item)
    return out


def generate_objective_recs(conn, actor: dict, scopes: list[str] | None) -> dict:
    ident = _student_ident(conn, actor)
    if not ident.get("student_email"):
        raise ValueError("Không gắn được tài khoản với học viên.")
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    objs = list_objectives(conn, scopes)
    topics = _topic_rows_for_student(conn, ident)
    weak = {t["topic"]: t for t in topics if t.get("mastery", 1) < 0.5}
    created = 0
    now = _now()
    for obj in objs[:30]:
        title = obj.get("title") or ""
        match = None
        for topic, t in weak.items():
            if (obj.get("course_code") or "") and obj.get("course_code") in topic:
                match = t
                break
        if not match and not weak:
            continue
        if not match:
            match = next(iter(weak.values()), None)
        reason = "Chưa xem đủ bài / tiến độ thấp trên chủ đề liên quan."
        how = obj.get("steps_text") or " → ".join(DEFAULT_STEPS)
        exists = cur.execute(
            "SELECT id FROM elearn_objective_recs WHERE student_email=? AND title=? AND status='suggested'",
            (ident["student_email"], title),
        ).fetchone()
        if exists:
            continue
        cur.execute(
            "INSERT INTO elearn_objective_recs "
            "(student_id, student_email, student_name, objective_id, title, reason, how_to, "
            "status, program_code, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                ident.get("student_id"), ident.get("student_email"), ident.get("student_name"),
                obj.get("id"), title, reason, how, "suggested",
                ident.get("program_code") or obj.get("program_code") or "", now,
            ),
        )
        created += 1
    conn.commit()
    return {"ok": True, "created": created}


def list_agenda(conn, actor: dict, scopes: list[str] | None, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    ident = _student_ident(conn, actor)
    depts = set(actor.get("dept_codes") or [])
    staff = bool(actor.get("is_admin") or (depts & {"mba", "master_chuyen_nganh", "giang_vien", "admin_he_thong"}))
    sql = (
        "SELECT id, student_id, student_email, student_name, plan_item_id, title, "
        "starts_at, ends_at, status, program_code, created_at FROM elearn_agenda WHERE 1=1"
    )
    params: list[Any] = []
    if not staff:
        if ident.get("student_email"):
            sql += " AND lower(student_email)=lower(?)"
            params.append(ident["student_email"])
        else:
            return []
    else:
        frag, sp = _scopes_sql(scopes, "program_code")
        sql += f" AND {frag}"
        params.extend(sp)
    sql += " ORDER BY starts_at"
    rows = cur.execute(sql, params).fetchall()
    keys = [
        "id", "student_id", "student_email", "student_name", "plan_item_id", "title",
        "starts_at", "ends_at", "status", "program_code", "created_at",
    ]
    ql = q.lower().strip()
    out = []
    for r in rows:
        item = dict(zip(keys, r))
        if ql and ql not in " ".join(str(v) for v in item.values() if v).lower():
            continue
        out.append(item)
    return out


def generate_agenda(conn, actor: dict, scopes: list[str] | None) -> dict:
    ident = _student_ident(conn, actor)
    if not ident.get("student_email"):
        raise ValueError("Không gắn được tài khoản với học viên.")
    topics = [t for t in _topic_rows_for_student(conn, ident) if t.get("remaining_min", 0) > 5]
    if not topics:
        topics = _topic_rows_for_student(conn, ident)[:6]
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    cur.execute(
        "DELETE FROM elearn_agenda WHERE student_email=? AND status='planned'",
        (ident["student_email"],),
    )
    now = datetime.utcnow()
    created = 0
    slot_start = datetime(now.year, now.month, now.day, 19, 0)
    if slot_start < now:
        slot_start += timedelta(days=1)
    for t in topics:
        mins = max(30, min(int(t["remaining_min"]), 90))
        # weekend morning
        while slot_start.weekday() >= 5:
            slot_start = datetime(slot_start.year, slot_start.month, slot_start.day, 9, 0)
            break
        end = slot_start + timedelta(minutes=mins)
        cur.execute(
            "INSERT INTO elearn_agenda "
            "(student_id, student_email, student_name, plan_item_id, title, starts_at, ends_at, "
            "status, program_code, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                ident.get("student_id"), ident.get("student_email"), ident.get("student_name"),
                None, t["topic"], slot_start.strftime("%Y-%m-%dT%H:%M"),
                end.strftime("%Y-%m-%dT%H:%M"), "planned",
                ident.get("program_code") or t.get("program_code") or "", _now(),
            ),
        )
        created += 1
        slot_start = datetime(slot_start.year, slot_start.month, slot_start.day, 19, 0) + timedelta(days=1)
    conn.commit()
    return {"ok": True, "created": created}


def list_exam_sittings(conn, scopes: list[str] | None, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    frag, params = _scopes_sql(scopes, "program_code")
    rows = cur.execute(
        "SELECT id, exam_id, student_id, student_email, student_name, class_id, "
        "identity_status, cccd_confirmed, honor_ack, selfie_name, notes, program_code, "
        "exam_title, exam_date, created_at FROM elearn_exam_sittings "
        f"WHERE {frag} ORDER BY id DESC",
        params,
    ).fetchall()
    keys = [
        "id", "exam_id", "student_id", "student_email", "student_name", "class_id",
        "identity_status", "cccd_confirmed", "honor_ack", "selfie_name", "notes",
        "program_code", "exam_title", "exam_date", "created_at",
    ]
    ql = q.lower().strip()
    out = []
    for r in rows:
        item = dict(zip(keys, r))
        item["cccd_confirmed"] = "yes" if item.get("cccd_confirmed") else "no"
        item["honor_ack"] = "yes" if item.get("honor_ack") else "no"
        item["status"] = item.get("identity_status") or "pending"
        item["has_selfie"] = "yes" if item.get("selfie_name") else "no"
        if ql and ql not in " ".join(str(v) for v in item.values() if v).lower():
            continue
        out.append(item)
    return out


def generate_exam_sittings(conn, scopes: list[str] | None) -> dict:
    from ops_crud import list_exams, seed_extra_ops

    seed_extra_ops(conn)
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    exams = list_exams(conn, scopes)
    created = 0
    now = _now()
    for ex in exams:
        cid = ex.get("class_id")
        if not cid:
            continue
        students = cur.execute(
            "SELECT id, full_name, email FROM class_students WHERE class_id=?",
            (cid,),
        ).fetchall()
        for st in students:
            exists = cur.execute(
                "SELECT id FROM elearn_exam_sittings WHERE exam_id=? AND student_id=?",
                (ex["id"], st[0]),
            ).fetchone()
            if exists:
                continue
            cur.execute(
                "INSERT INTO elearn_exam_sittings "
                "(exam_id, student_id, student_email, student_name, class_id, identity_status, "
                "program_code, exam_title, exam_date, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    ex["id"], st[0], st[2], st[1], cid, "pending",
                    ex.get("program_code") or "", ex.get("title") or "", ex.get("exam_date") or "",
                    now,
                ),
            )
            created += 1
    conn.commit()
    return {"ok": True, "created": created}


def create_exam_sitting(conn, data: dict, scopes: list[str] | None) -> dict:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    exam_id = data.get("exam_id")
    student_id = data.get("student_id")
    try:
        exam_id = int(exam_id)
        student_id = int(student_id)
    except (TypeError, ValueError):
        raise ValueError("Cần exam_id và student_id.")
    ex = cur.execute(
        "SELECT e.id, e.title, e.exam_date, e.class_id, cg.program_code "
        "FROM exam_schedules e JOIN class_groups cg ON cg.id=e.class_id WHERE e.id=?",
        (exam_id,),
    ).fetchone()
    if not ex:
        raise ValueError("Không tìm thấy kỳ thi.")
    st = cur.execute(
        "SELECT id, full_name, email FROM class_students WHERE id=?",
        (student_id,),
    ).fetchone()
    if not st:
        raise ValueError("Không tìm thấy học viên.")
    cur.execute(
        "INSERT INTO elearn_exam_sittings "
        "(exam_id, student_id, student_email, student_name, class_id, identity_status, "
        "cccd_confirmed, honor_ack, notes, program_code, exam_title, exam_date, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            exam_id, student_id, st[2], st[1], ex[3],
            (data.get("identity_status") or "pending").strip() or "pending",
            1 if data.get("cccd_confirmed") in (1, "1", True, "true", "yes") else 0,
            1 if data.get("honor_ack") in (1, "1", True, "true", "yes") else 0,
            (data.get("notes") or "").strip(),
            ex[4], ex[1], ex[2], _now(),
        ),
    )
    conn.commit()
    return {"ok": True, "id": cur.lastrowid}


def verify_exam_sitting(conn, sitting_id: int, data: dict) -> dict:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    row = cur.execute(
        "SELECT id FROM elearn_exam_sittings WHERE id=?", (sitting_id,)
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy phiên thi.")
    status = (data.get("identity_status") or "verified").strip() or "verified"
    if status not in ("pending", "verified", "flagged"):
        status = "verified"
    cccd = 1 if data.get("cccd_confirmed") in (1, "1", True, "true", "yes", None) else 0
    honor = 1 if data.get("honor_ack") in (1, "1", True, "true", "yes", None) else 0
    if "cccd_confirmed" not in data:
        cccd = 1
    if "honor_ack" not in data:
        honor = 1
    notes = (data.get("notes") or "").strip()
    cur.execute(
        "UPDATE elearn_exam_sittings SET identity_status=?, cccd_confirmed=?, honor_ack=?, notes=? WHERE id=?",
        (status, cccd, honor, notes, sitting_id),
    )
    conn.commit()
    return {"ok": True, "id": sitting_id, "identity_status": status}


def save_exam_selfie(conn, sitting_id: int, file_storage) -> dict:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    row = cur.execute(
        "SELECT id FROM elearn_exam_sittings WHERE id=?", (sitting_id,)
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy phiên thi.")
    name = (getattr(file_storage, "filename", None) or "selfie.jpg").strip()
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp"):
        raise ValueError("Chỉ nhận ảnh jpg/png.")
    EXAM_SELFIE_DIR.mkdir(parents=True, exist_ok=True)
    stored = f"{sitting_id}_{uuid.uuid4().hex[:10]}.{ext}"
    dest = EXAM_SELFIE_DIR / stored
    file_storage.save(str(dest))
    cur.execute(
        "UPDATE elearn_exam_sittings SET selfie_path=?, selfie_name=? WHERE id=?",
        (str(dest), name, sitting_id),
    )
    conn.commit()
    return {"ok": True, "id": sitting_id, "selfie_name": name}


def list_return_meetings(
    conn, scopes: list[str] | None, *, q: str = "", student_email: str = ""
) -> list[dict]:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    frag, params = _scopes_sql(scopes, "program_code")
    extra = ""
    extra_p: list[Any] = []
    if student_email:
        extra = " AND lower(student_email)=lower(?)"
        extra_p.append(student_email)
    rows = cur.execute(
        "SELECT id, student_id, student_email, student_name, lifecycle_status, starts_at, "
        "meeting_url, reason, support_note, status, program_code, class_name, created_at "
        f"FROM elearn_return_meetings WHERE {frag}{extra} ORDER BY starts_at DESC, id DESC",
        [*params, *extra_p],
    ).fetchall()
    keys = [
        "id", "student_id", "student_email", "student_name", "lifecycle_status", "starts_at",
        "meeting_url", "reason", "support_note", "status", "program_code", "class_name",
        "created_at",
    ]
    ql = q.lower().strip()
    out = []
    for r in rows:
        item = dict(zip(keys, r))
        if ql and ql not in " ".join(str(v) for v in item.values() if v).lower():
            continue
        out.append(item)
    return out


def create_return_meeting(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_elearn_tables(cur)
    sid = data.get("student_id")
    try:
        sid = int(sid)
    except (TypeError, ValueError):
        raise ValueError("Cần student_id.")
    st = cur.execute(
        "SELECT cs.id, cs.full_name, cs.email, cs.lifecycle_status, cg.program_code, cg.name "
        "FROM class_students cs JOIN class_groups cg ON cg.id=cs.class_id WHERE cs.id=?",
        (sid,),
    ).fetchone()
    if not st:
        raise ValueError("Không tìm thấy học viên.")
    life = (st[3] or "active").strip() or "active"
    starts = (data.get("starts_at") or "").strip()
    if not starts:
        raise ValueError("Cần thời điểm họp (starts_at).")
    url = (data.get("meeting_url") or "").strip()
    reason = (data.get("reason") or "").strip() or f"Hỗ trợ HV {life}"
    note = (data.get("support_note") or "").strip()
    status = (data.get("status") or "scheduled").strip() or "scheduled"
    cur.execute(
        "INSERT INTO elearn_return_meetings "
        "(student_id, student_email, student_name, lifecycle_status, starts_at, meeting_url, "
        "reason, support_note, status, program_code, class_name, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (st[0], st[2], st[1], life, starts, url, reason, note, status, st[4], st[5], _now()),
    )
    conn.commit()
    return {"ok": True, "id": cur.lastrowid}


def list_paused_students(conn, scopes: list[str] | None) -> list[dict]:
    cur = conn.cursor()
    frag, params = _scopes_sql(scopes, "cg.program_code")
    rows = cur.execute(
        "SELECT cs.id, cs.full_name, cs.email, cs.lifecycle_status, cg.program_code, cg.name "
        "FROM class_students cs JOIN class_groups cg ON cg.id=cs.class_id "
        f"WHERE {frag} AND lower(IFNULL(cs.lifecycle_status,'')) IN ('on_leave','reserved') "
        "ORDER BY cs.full_name",
        params,
    ).fetchall()
    return [
        {
            "id": r[0],
            "full_name": r[1],
            "email": r[2],
            "lifecycle_status": r[3],
            "program_code": r[4],
            "class_name": r[5],
        }
        for r in rows
    ]
