"""
Bài giảng theo lớp–môn (teaching_assignments):
- Import danh sách buổi từ syllabus học phần
- Thêm / upload bài học kèm file
- Preview + câu hỏi / comment của học viên
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from course_content import (
    _build_search_text,
    add_material,
    ensure_course_content_tables,
    ensure_sessions_for_course,
    get_material_file,
)


def ensure_class_lesson_tables(cur) -> None:
    ensure_course_content_tables(cur)
    cur.execute(
        "CREATE TABLE IF NOT EXISTS class_lessons ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "assignment_id INTEGER NOT NULL, "
        "source_session_id INTEGER, "
        "lesson_no INTEGER NOT NULL, "
        "title TEXT NOT NULL, "
        "content_outline TEXT, "
        "objectives TEXT, "
        "lesson_type TEXT DEFAULT 'theory', "
        "lesson_date TEXT, "
        "preview_summary TEXT, "
        "status TEXT DEFAULT 'draft', "  # draft | published | done
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "updated_at TEXT, "
        "UNIQUE(assignment_id, lesson_no), "
        "FOREIGN KEY (assignment_id) REFERENCES teaching_assignments(id))"
    )
    try:
        cur.execute("ALTER TABLE course_materials ADD COLUMN lesson_id INTEGER")
    except Exception:
        pass
    cur.execute(
        "CREATE TABLE IF NOT EXISTS lesson_comments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "lesson_id INTEGER NOT NULL, "
        "parent_id INTEGER, "
        "author_name TEXT NOT NULL, "
        "author_email TEXT, "
        "author_role TEXT DEFAULT 'student', "  # student | lecturer | coordinator
        "body TEXT NOT NULL, "
        "is_question INTEGER DEFAULT 0, "
        "comment_type TEXT DEFAULT 'discussion', "  # question | feedback | discussion
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (lesson_id) REFERENCES class_lessons(id), "
        "FOREIGN KEY (parent_id) REFERENCES lesson_comments(id))"
    )
    try:
        cur.execute(
            "ALTER TABLE lesson_comments ADD COLUMN comment_type TEXT DEFAULT 'discussion'"
        )
    except Exception:
        pass
    cur.execute(
        "UPDATE lesson_comments SET comment_type='question' "
        "WHERE IFNULL(comment_type,'')='' AND is_question=1"
    )
    cur.execute(
        "UPDATE lesson_comments SET comment_type='discussion' "
        "WHERE IFNULL(comment_type,'')='' AND IFNULL(is_question,0)=0"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS lesson_view_sessions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "lesson_id INTEGER NOT NULL, "
        "material_id INTEGER, "
        "user_id INTEGER, "
        "student_email TEXT, "
        "student_name TEXT, "
        "opened_at TEXT NOT NULL, "
        "closed_at TEXT, "
        "last_heartbeat_at TEXT, "
        "duration_sec INTEGER DEFAULT 0, "
        "user_agent TEXT, "
        "FOREIGN KEY (lesson_id) REFERENCES class_lessons(id), "
        "FOREIGN KEY (material_id) REFERENCES course_materials(id))"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_class_lessons_assignment "
        "ON class_lessons(assignment_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_lesson_comments_lesson "
        "ON lesson_comments(lesson_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_lesson_views_lesson "
        "ON lesson_view_sessions(lesson_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_lesson_views_email "
        "ON lesson_view_sessions(student_email)"
    )
    for col, typedef in (
        ("video_url", "TEXT"),
        ("publish_at", "TEXT"),
        ("duration_min", "INTEGER"),
        ("group_id", "INTEGER"),
    ):
        try:
            cur.execute(f"ALTER TABLE class_lessons ADD COLUMN {col} {typedef}")
        except Exception:
            pass


COMMENT_TYPES = ("question", "feedback", "discussion")
COMMENT_TYPE_LABELS = {
    "question": "Câu hỏi",
    "feedback": "Góp ý",
    "discussion": "Bàn luận",
}


def _normalize_comment_type(comment_type: str | None, is_question: bool = False) -> str:
    t = (comment_type or "").strip().lower()
    if t in COMMENT_TYPES:
        return t
    return "question" if is_question else "discussion"


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        raw = s.replace("Z", "").split("+")[0].split(".")[0]
        return datetime.fromisoformat(raw[:19])
    except Exception:
        return None


def _duration_from_session(opened_at: str, last_hb: str | None, closed_at: str | None) -> int:
    start = _parse_iso(opened_at)
    end = _parse_iso(closed_at) or _parse_iso(last_hb) or start
    if not start or not end:
        return 0
    sec = int((end - start).total_seconds())
    return max(0, min(sec, 8 * 3600))  # cap 8h per session


def seed_class_lessons(conn) -> dict:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    created = {"imported": 0}
    # Auto-import for first assignment per class-course if empty
    rows = cur.execute(
        "SELECT ta.id FROM teaching_assignments ta "
        "WHERE NOT EXISTS (SELECT 1 FROM class_lessons cl WHERE cl.assignment_id = ta.id) "
        "LIMIT 5"
    ).fetchall()
    for (aid,) in rows:
        r = import_lessons_from_syllabus(conn, aid, publish=True)
        created["imported"] += r.get("created", 0)
    return created


def _assignment_meta(conn, assignment_id: int) -> dict | None:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT ta.id, ta.class_id, ta.course_id, ta.status, "
        "cg.name, cg.program_code, c.code, c.name, "
        "fl.full_name, fe.full_name "
        "FROM teaching_assignments ta "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        "LEFT JOIN faculty fl ON fl.id = ta.lecturer_id "
        "LEFT JOIN faculty fe ON fe.id = ta.expert_id "
        "WHERE ta.id = ?",
        (assignment_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "assignment_id": row[0],
        "class_id": row[1],
        "course_id": row[2],
        "status": row[3],
        "class_name": row[4],
        "program_code": row[5],
        "course_code": row[6],
        "course_name": row[7],
        "lecturer": row[8],
        "expert": row[9],
    }


def import_lessons_from_syllabus(
    conn, assignment_id: int, *, publish: bool = False, replace: bool = False
) -> dict:
    """Copy course_sessions → class_lessons for this class–course offering."""
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    meta = _assignment_meta(conn, assignment_id)
    if not meta:
        raise ValueError("Teaching assignment not found")
    ensure_sessions_for_course(cur, meta["course_id"])
    if replace:
        # Keep comments only if lessons remain; on replace delete lessons+comments
        lids = [
            r[0]
            for r in cur.execute(
                "SELECT id FROM class_lessons WHERE assignment_id = ?",
                (assignment_id,),
            ).fetchall()
        ]
        for lid in lids:
            cur.execute("DELETE FROM lesson_comments WHERE lesson_id = ?", (lid,))
            cur.execute(
                "UPDATE course_materials SET lesson_id = NULL WHERE lesson_id = ?",
                (lid,),
            )
        cur.execute("DELETE FROM class_lessons WHERE assignment_id = ?", (assignment_id,))

    sessions = cur.execute(
        "SELECT id, session_no, session_type, title, content_outline, objectives "
        "FROM course_sessions WHERE course_id = ? ORDER BY sort_order, session_no",
        (meta["course_id"],),
    ).fetchall()
    created = 0
    skipped = 0
    status = "published" if publish else "draft"
    now = datetime.utcnow().isoformat() + "Z"
    for sid, no, stype, title, outline, objectives in sessions:
        cur.execute(
            "SELECT id FROM class_lessons WHERE assignment_id = ? AND lesson_no = ?",
            (assignment_id, no),
        )
        if cur.fetchone():
            skipped += 1
            continue
        preview = (outline or title or "")[:280]
        cur.execute(
            "INSERT INTO class_lessons "
            "(assignment_id, source_session_id, lesson_no, title, content_outline, "
            "objectives, lesson_type, preview_summary, status, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                assignment_id,
                sid,
                no,
                title,
                outline,
                objectives,
                stype or "theory",
                preview,
                status,
                now,
            ),
        )
        created += 1
    conn.commit()
    return {
        "assignment_id": assignment_id,
        "created": created,
        "skipped": skipped,
        "total_sessions": len(sessions),
        "meta": meta,
    }


def stamp_faculty_sessions(conn, assignment_id: int) -> dict:
    """Name theory sessions after the lecturer and practice sessions after the expert.

    Titles already renamed by hand (not the syllabus default) are left as-is.
    Missing lessons are imported from the 7 LT + 2 TH syllabus first.
    """
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    meta = _assignment_meta(conn, assignment_id)
    if not meta:
        raise ValueError("Không tìm thấy phân giảng.")
    ensure_sessions_for_course(cur, meta["course_id"])
    count = cur.execute(
        "SELECT COUNT(*) FROM class_lessons WHERE assignment_id = ?",
        (assignment_id,),
    ).fetchone()[0]
    if not count:
        import_lessons_from_syllabus(conn, assignment_id)
        cur = conn.cursor()
    lecturer = (meta.get("lecturer") or "").strip() or "Giảng viên lý thuyết"
    expert = (meta.get("expert") or "").strip() or "Chuyên gia"
    lessons = cur.execute(
        "SELECT id, lesson_type, title FROM class_lessons WHERE assignment_id = ? ORDER BY lesson_no",
        (assignment_id,),
    ).fetchall()
    updated = 0
    now = _now_iso()
    for lid, ltype, title in lessons:
        current = title or ""
        auto = (
            current.startswith("Buổi LT")
            or current.startswith("Buổi TH")
            or current.startswith("Session ")
            or current in ("Giảng viên lý thuyết", "Chuyên gia")
        )
        if not auto:
            continue
        new_title = expert if (ltype or "") == "practice" else lecturer
        cur.execute(
            "UPDATE class_lessons SET title = ?, updated_at = ? WHERE id = ?",
            (new_title, now, lid),
        )
        updated += 1
    conn.commit()
    return {
        "assignment_id": assignment_id,
        "updated": updated,
        "lecturer": lecturer,
        "expert": expert,
        "lessons": len(lessons),
    }


def list_class_lessons(conn, assignment_id: int, *, published_only: bool = False) -> dict:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    meta = _assignment_meta(conn, assignment_id)
    if not meta:
        raise ValueError("Teaching assignment not found")
    sql = (
        "SELECT cl.id, cl.lesson_no, cl.title, cl.content_outline, cl.objectives, "
        "cl.lesson_type, cl.lesson_date, cl.preview_summary, cl.status, "
        "cl.source_session_id, cl.video_url, cl.publish_at, cl.duration_min, cl.group_id, "
        "(SELECT COUNT(*) FROM course_materials m WHERE m.lesson_id = cl.id), "
        "(SELECT COUNT(*) FROM course_materials m WHERE m.lesson_id = cl.id "
        " AND m.release_status = 'released'), "
        "(SELECT COUNT(*) FROM lesson_comments lc WHERE lc.lesson_id = cl.id) "
        "FROM class_lessons cl WHERE cl.assignment_id = ?"
    )
    params: list[Any] = [assignment_id]
    if published_only:
        sql += " AND cl.status = 'published'"
    sql += " ORDER BY cl.lesson_no"
    rows = cur.execute(sql, params).fetchall()
    lessons = [
        {
            "id": r[0],
            "lesson_no": r[1],
            "title": r[2],
            "content_outline": r[3],
            "objectives": r[4],
            "lesson_type": r[5],
            "lesson_date": r[6],
            "preview_summary": r[7],
            "status": r[8],
            "source_session_id": r[9],
            "video_url": r[10] or "",
            "publish_at": r[11] or "",
            "duration_min": r[12],
            "group_id": r[13],
            "material_count": r[14] or 0,
            "released_files": r[15] or 0,
            "comment_count": r[16] or 0,
        }
        for r in rows
    ]
    return {
        "meta": meta,
        "lessons": lessons,
        "stats": {
            "total": len(lessons),
            "published": sum(1 for x in lessons if x["status"] == "published"),
            "draft": sum(1 for x in lessons if x["status"] == "draft"),
            "with_files": sum(1 for x in lessons if x["material_count"] > 0),
        },
    }


def add_class_lesson(conn, assignment_id: int, data: dict) -> dict:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    meta = _assignment_meta(conn, assignment_id)
    if not meta:
        raise ValueError("Teaching assignment not found")
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("title required")
    cur.execute(
        "SELECT COALESCE(MAX(lesson_no), 0) FROM class_lessons WHERE assignment_id = ?",
        (assignment_id,),
    )
    next_no = int(cur.fetchone()[0]) + 1
    lesson_no = int(data.get("lesson_no") or next_no)
    status = (data.get("status") or "draft").strip()
    if status not in ("draft", "published", "done"):
        status = "draft"
    now = datetime.utcnow().isoformat() + "Z"
    outline = (data.get("content_outline") or "").strip()
    preview = (data.get("preview_summary") or outline or title)[:280]
    cur.execute(
        "INSERT INTO class_lessons "
        "(assignment_id, lesson_no, title, content_outline, objectives, lesson_type, "
        "lesson_date, preview_summary, status, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            assignment_id,
            lesson_no,
            title,
            outline,
            (data.get("objectives") or "").strip(),
            (data.get("lesson_type") or "theory").strip(),
            (data.get("lesson_date") or "").strip() or None,
            preview,
            status,
            now,
        ),
    )
    lid = cur.lastrowid
    conn.commit()
    return get_class_lesson(conn, lid, as_student=False)  # type: ignore


def update_class_lesson(conn, lesson_id: int, data: dict) -> dict | None:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    fields = []
    params: list[Any] = []
    for key in (
        "title",
        "content_outline",
        "objectives",
        "lesson_type",
        "lesson_date",
        "preview_summary",
        "status",
        "lesson_no",
        "video_url",
        "publish_at",
        "duration_min",
        "group_id",
    ):
        if key in data and data[key] is not None:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if not fields:
        return get_class_lesson(conn, lesson_id, as_student=False)
    fields.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat() + "Z")
    params.append(lesson_id)
    cur.execute(f"UPDATE class_lessons SET {', '.join(fields)} WHERE id = ?", params)
    if cur.rowcount == 0:
        return None
    conn.commit()
    return get_class_lesson(conn, lesson_id, as_student=False)


def get_class_lesson(conn, lesson_id: int, *, as_student: bool = False) -> dict | None:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    row = cur.execute(
        "SELECT cl.id, cl.assignment_id, cl.lesson_no, cl.title, cl.content_outline, "
        "cl.objectives, cl.lesson_type, cl.lesson_date, cl.preview_summary, cl.status, "
        "cl.source_session_id, cl.video_url, cl.publish_at, cl.duration_min, cl.group_id "
        "FROM class_lessons cl WHERE cl.id = ?",
        (lesson_id,),
    ).fetchone()
    if not row:
        return None
    if as_student and row[9] != "published":
        return None
    if as_student:
        pub_at = (row[12] or "").strip()
        if pub_at:
            now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M")
            if pub_at[:16] > now:
                return None
    meta = _assignment_meta(conn, row[1])
    msql = (
        "SELECT id, title, description, material_type, original_filename, file_size, "
        "release_status, "
        "CASE WHEN file_path IS NOT NULL AND file_path != '' THEN 1 ELSE 0 END "
        "FROM course_materials WHERE lesson_id = ?"
    )
    mparams: list[Any] = [lesson_id]
    if as_student:
        msql += " AND release_status = 'released'"
    msql += " ORDER BY id"
    materials = [
        {
            "id": m[0],
            "title": m[1],
            "description": m[2],
            "material_type": m[3],
            "original_filename": m[4],
            "file_size": m[5],
            "release_status": m[6],
            "has_file": bool(m[7]),
            "can_download": bool(m[7]) and (not as_student or m[6] == "released"),
        }
        for m in cur.execute(msql, mparams).fetchall()
    ]
    comments = list_lesson_comments(conn, lesson_id)
    return {
        "id": row[0],
        "assignment_id": row[1],
        "lesson_no": row[2],
        "title": row[3],
        "content_outline": row[4],
        "objectives": row[5],
        "lesson_type": row[6],
        "lesson_date": row[7],
        "preview_summary": row[8],
        "status": row[9],
        "source_session_id": row[10],
        "video_url": row[11] or "",
        "publish_at": row[12] or "",
        "duration_min": row[13],
        "group_id": row[14],
        "meta": meta,
        "materials": materials,
        "comments": comments,
        "stats": {
            "materials": len(materials),
            "comments": len(comments),
            "questions": sum(1 for c in comments if c.get("is_question")),
        },
        "chapter_work": [],
    }


def attach_chapter_work(
    conn,
    detail: dict,
    *,
    student_email: str = "",
) -> dict:
    """Attach published practice/MC items matching this lesson's chapter number."""
    if not detail:
        return detail
    ta_id = detail.get("assignment_id")
    lesson_no = detail.get("lesson_no")
    if not ta_id:
        detail["chapter_work"] = []
        return detail
    try:
        from mc_quiz import list_for_lesson_chapter as mc_for_chapter
        from practice_homework import list_for_lesson_chapter as practice_for_chapter

        items = practice_for_chapter(
            conn,
            teaching_assignment_id=ta_id,
            lesson_no=lesson_no,
            student_email=student_email,
        ) + mc_for_chapter(
            conn,
            teaching_assignment_id=ta_id,
            lesson_no=lesson_no,
            student_email=student_email,
        )
        detail["chapter_work"] = items
        detail.setdefault("stats", {})["chapter_work"] = len(items)
    except Exception:
        detail["chapter_work"] = []
    return detail


def attach_file_to_lesson(
    conn,
    lesson_id: int,
    *,
    title: str,
    description: str = "",
    material_type: str = "slide",
    original_filename: str | None = None,
    stored_name: str | None = None,
    file_path: str | None = None,
    mime_type: str | None = None,
    file_size: int = 0,
    uploaded_by: str = "",
    release_status: str = "draft",
) -> dict:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    lesson = cur.execute(
        "SELECT id, assignment_id FROM class_lessons WHERE id = ?",
        (lesson_id,),
    ).fetchone()
    if not lesson:
        raise ValueError("Lesson not found")
    meta = _assignment_meta(conn, lesson[1])
    if not meta:
        raise ValueError("Assignment not found")
    row = add_material(
        conn,
        course_id=meta["course_id"],
        title=title,
        description=description,
        material_type=material_type,
        session_id=None,
        class_id=meta["class_id"],
        original_filename=original_filename,
        stored_name=stored_name,
        file_path=file_path,
        mime_type=mime_type,
        file_size=file_size,
        uploaded_by=uploaded_by,
        release_status=release_status,
    )
    cur.execute(
        "UPDATE course_materials SET lesson_id = ?, search_text = ? WHERE id = ?",
        (
            lesson_id,
            _build_search_text(title, description, original_filename, f"lesson:{lesson_id}"),
            row["id"],
        ),
    )
    conn.commit()
    row["lesson_id"] = lesson_id
    return row


def list_lesson_comments(conn, lesson_id: int) -> list[dict]:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    rows = cur.execute(
        "SELECT id, parent_id, author_name, author_email, author_role, body, "
        "is_question, created_at, IFNULL(comment_type,'discussion') "
        "FROM lesson_comments WHERE lesson_id = ? ORDER BY created_at, id",
        (lesson_id,),
    ).fetchall()
    return [
        {
            "id": r[0],
            "parent_id": r[1],
            "author_name": r[2],
            "author_email": r[3],
            "author_role": r[4],
            "body": r[5],
            "is_question": bool(r[6]) or r[8] == "question",
            "created_at": r[7],
            "comment_type": r[8],
            "comment_type_label": COMMENT_TYPE_LABELS.get(r[8], r[8]),
        }
        for r in rows
    ]


def add_lesson_comment(
    conn,
    lesson_id: int,
    *,
    body: str,
    author_name: str,
    author_email: str = "",
    author_role: str = "student",
    is_question: bool = False,
    comment_type: str | None = None,
    parent_id: int | None = None,
) -> dict:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    body = (body or "").strip()
    if not body:
        raise ValueError("body required")
    author_name = (author_name or "").strip() or "Anonymous"
    ctype = _normalize_comment_type(comment_type, is_question=is_question)
    is_q = 1 if ctype == "question" else 0
    # Students may only comment on published lessons
    row = cur.execute(
        "SELECT status FROM class_lessons WHERE id = ?",
        (lesson_id,),
    ).fetchone()
    if not row:
        raise ValueError("Lesson not found")
    if author_role == "student" and row[0] != "published":
        raise ValueError("Bài học chưa publish — chưa nhận câu hỏi/comment")
    if parent_id:
        p = cur.execute(
            "SELECT id FROM lesson_comments WHERE id = ? AND lesson_id = ?",
            (parent_id, lesson_id),
        ).fetchone()
        if not p:
            raise ValueError("parent comment not found")
    cur.execute(
        "INSERT INTO lesson_comments "
        "(lesson_id, parent_id, author_name, author_email, author_role, body, is_question, comment_type) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            lesson_id,
            parent_id,
            author_name,
            author_email or None,
            author_role,
            body,
            is_q,
            ctype,
        ),
    )
    cid = cur.lastrowid
    conn.commit()
    return {
        "id": cid,
        "lesson_id": lesson_id,
        "parent_id": parent_id,
        "author_name": author_name,
        "author_role": author_role,
        "body": body,
        "is_question": bool(is_q),
        "comment_type": ctype,
        "comment_type_label": COMMENT_TYPE_LABELS.get(ctype, ctype),
    }


def open_view_session(
    conn,
    *,
    lesson_id: int,
    material_id: int | None = None,
    student_email: str = "",
    student_name: str = "",
    user_id: int | None = None,
    user_agent: str = "",
) -> dict:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    lesson = cur.execute(
        "SELECT id, status FROM class_lessons WHERE id=?", (lesson_id,)
    ).fetchone()
    if not lesson:
        raise ValueError("Lesson not found")
    email = (student_email or "").strip().lower()
    name = (student_name or "").strip() or (email.split("@")[0] if email else "HV")
    now = _now_iso()
    mid = int(material_id) if material_id else None
    if mid:
        ok = cur.execute(
            "SELECT id FROM course_materials WHERE id=? AND lesson_id=?",
            (mid, lesson_id),
        ).fetchone()
        if not ok:
            # allow material linked to same course/class even if lesson_id mismatch
            ok2 = cur.execute("SELECT id FROM course_materials WHERE id=?", (mid,)).fetchone()
            if not ok2:
                raise ValueError("Material not found")
    cur.execute(
        "INSERT INTO lesson_view_sessions "
        "(lesson_id, material_id, user_id, student_email, student_name, opened_at, "
        "last_heartbeat_at, user_agent) VALUES (?,?,?,?,?,?,?,?)",
        (lesson_id, mid, user_id, email or None, name, now, now, (user_agent or "")[:400]),
    )
    sid = cur.lastrowid
    conn.commit()
    return {
        "id": sid,
        "lesson_id": lesson_id,
        "material_id": mid,
        "opened_at": now,
        "student_email": email,
        "student_name": name,
    }


def heartbeat_view_session(conn, session_id: int) -> dict:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    row = cur.execute(
        "SELECT id, opened_at, closed_at, last_heartbeat_at FROM lesson_view_sessions WHERE id=?",
        (session_id,),
    ).fetchone()
    if not row:
        raise ValueError("View session not found")
    if row[2]:
        return {"id": session_id, "closed": True, "duration_sec": _duration_from_session(row[1], row[3], row[2])}
    now = _now_iso()
    cur.execute(
        "UPDATE lesson_view_sessions SET last_heartbeat_at=? WHERE id=?",
        (now, session_id),
    )
    conn.commit()
    return {
        "id": session_id,
        "last_heartbeat_at": now,
        "duration_sec": _duration_from_session(row[1], now, None),
    }


def close_view_session(conn, session_id: int) -> dict:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    row = cur.execute(
        "SELECT id, opened_at, closed_at, last_heartbeat_at FROM lesson_view_sessions WHERE id=?",
        (session_id,),
    ).fetchone()
    if not row:
        raise ValueError("View session not found")
    if row[2]:
        dur = _duration_from_session(row[1], row[3], row[2])
        return {"id": session_id, "closed_at": row[2], "duration_sec": dur}
    now = _now_iso()
    # If last heartbeat is stale (>3 min), close at last heartbeat instead of now
    last = _parse_iso(row[3]) or _parse_iso(row[1])
    end_iso = now
    if last and (_parse_iso(now) - last).total_seconds() > 180:
        end_iso = row[3] or row[1]
    dur = _duration_from_session(row[1], row[3], end_iso)
    cur.execute(
        "UPDATE lesson_view_sessions SET closed_at=?, duration_sec=?, last_heartbeat_at=COALESCE(last_heartbeat_at,?) "
        "WHERE id=?",
        (end_iso, dur, end_iso, session_id),
    )
    conn.commit()
    return {"id": session_id, "closed_at": end_iso, "duration_sec": dur}


def learning_stats_for_lesson(conn, lesson_id: int) -> dict:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    lesson = get_class_lesson(conn, lesson_id, as_student=False)
    if not lesson:
        raise ValueError("Lesson not found")
    # Finalize open sessions older than 3 min without heartbeat as soft-closed
    stale = cur.execute(
        "SELECT id, opened_at, last_heartbeat_at FROM lesson_view_sessions "
        "WHERE lesson_id=? AND closed_at IS NULL",
        (lesson_id,),
    ).fetchall()
    now = _parse_iso(_now_iso())
    for sid, opened, hb in stale:
        last = _parse_iso(hb) or _parse_iso(opened)
        if last and now and (now - last).total_seconds() > 180:
            close_view_session(conn, sid)

    rows = cur.execute(
        "SELECT IFNULL(student_email,''), IFNULL(student_name,''), material_id, "
        "SUM(IFNULL(duration_sec,0)), COUNT(*), "
        "MIN(opened_at), MAX(IFNULL(closed_at, last_heartbeat_at)) "
        "FROM lesson_view_sessions WHERE lesson_id=? "
        "GROUP BY lower(IFNULL(student_email,'')), material_id "
        "ORDER BY IFNULL(student_name,''), material_id",
        (lesson_id,),
    ).fetchall()
    mat_names = {
        m["id"]: m.get("title") or m.get("original_filename") or f"File #{m['id']}"
        for m in lesson.get("materials") or []
    }
    by_student: dict[str, dict] = {}
    file_rows = []
    for email, name, mid, total_sec, opens, first_at, last_at in rows:
        key = (email or name or "unknown").lower()
        st = by_student.setdefault(
            key,
            {
                "student_email": email,
                "student_name": name or email or "—",
                "total_sec": 0,
                "open_count": 0,
                "files": [],
            },
        )
        sec = int(total_sec or 0)
        st["total_sec"] += sec
        st["open_count"] += int(opens or 0)
        label = "Trang bài giảng" if not mid else mat_names.get(mid) or f"File #{mid}"
        entry = {
            "material_id": mid,
            "material_title": label,
            "total_sec": sec,
            "open_count": int(opens or 0),
            "first_opened_at": first_at,
            "last_activity_at": last_at,
        }
        st["files"].append(entry)
        file_rows.append({**entry, "student_email": email, "student_name": st["student_name"]})

    students = sorted(by_student.values(), key=lambda x: -x["total_sec"])
    for s in students:
        s["total_hm"] = _fmt_hm(s["total_sec"])
        for f in s["files"]:
            f["total_hm"] = _fmt_hm(f["total_sec"])
    for f in file_rows:
        f["total_hm"] = _fmt_hm(f["total_sec"])

    return {
        "lesson": {
            "id": lesson["id"],
            "lesson_no": lesson["lesson_no"],
            "title": lesson["title"],
            "assignment_id": lesson["assignment_id"],
            "meta": lesson.get("meta"),
        },
        "students": students,
        "file_rows": file_rows,
        "totals": {
            "students": len(students),
            "total_sec": sum(s["total_sec"] for s in students),
            "total_hm": _fmt_hm(sum(s["total_sec"] for s in students)),
            "opens": sum(s["open_count"] for s in students),
        },
    }


def learning_stats_for_assignment(conn, assignment_id: int) -> dict:
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    meta = _assignment_meta(conn, assignment_id)
    if not meta:
        raise ValueError("Teaching assignment not found")
    lids = [
        r[0]
        for r in cur.execute(
            "SELECT id FROM class_lessons WHERE assignment_id=? ORDER BY lesson_no",
            (assignment_id,),
        ).fetchall()
    ]
    lessons = []
    agg: dict[str, dict] = {}
    for lid in lids:
        try:
            st = learning_stats_for_lesson(conn, lid)
        except ValueError:
            continue
        lessons.append(
            {
                "lesson_id": lid,
                "lesson_no": st["lesson"]["lesson_no"],
                "title": st["lesson"]["title"],
                "totals": st["totals"],
            }
        )
        for s in st["students"]:
            key = (s.get("student_email") or s.get("student_name") or "").lower()
            a = agg.setdefault(
                key,
                {
                    "student_email": s.get("student_email"),
                    "student_name": s.get("student_name"),
                    "total_sec": 0,
                    "open_count": 0,
                    "lessons": 0,
                },
            )
            a["total_sec"] += s["total_sec"]
            a["open_count"] += s["open_count"]
            a["lessons"] += 1
    students = sorted(agg.values(), key=lambda x: -x["total_sec"])
    for s in students:
        s["total_hm"] = _fmt_hm(s["total_sec"])
    return {
        "meta": meta,
        "lessons": lessons,
        "students": students,
        "totals": {
            "students": len(students),
            "total_sec": sum(s["total_sec"] for s in students),
            "total_hm": _fmt_hm(sum(s["total_sec"] for s in students)),
            "lessons": len(lessons),
        },
    }


def _fmt_hm(sec: int) -> str:
    sec = max(0, int(sec or 0))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def list_comments_inbox(
    conn,
    *,
    scopes: list[str] | None = None,
    course_id: int | None = None,
    class_id: int | None = None,
    lesson_no: int | None = None,
    assignment_id: int | None = None,
    comment_type: str | None = None,
    q: str = "",
) -> list[dict]:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    sql = (
        "SELECT lc.id, lc.lesson_id, lc.author_name, lc.author_email, lc.author_role, "
        "lc.body, lc.is_question, lc.created_at, IFNULL(lc.comment_type,'discussion'), "
        "cl.lesson_no, cl.title, cg.id, cg.name, c.id, c.code, c.name, ta.id "
        "FROM lesson_comments lc "
        "JOIN class_lessons cl ON cl.id = lc.lesson_id "
        "JOIN teaching_assignments ta ON ta.id = cl.assignment_id "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        f"WHERE {frag}"
    )
    if course_id:
        sql += " AND c.id = ?"
        params.append(int(course_id))
    if class_id:
        sql += " AND cg.id = ?"
        params.append(int(class_id))
    if lesson_no:
        sql += " AND cl.lesson_no = ?"
        params.append(int(lesson_no))
    if assignment_id:
        sql += " AND ta.id = ?"
        params.append(int(assignment_id))
    if comment_type and comment_type in COMMENT_TYPES:
        sql += " AND IFNULL(lc.comment_type,'discussion') = ?"
        params.append(comment_type)
    sql += " ORDER BY lc.created_at DESC, lc.id DESC LIMIT 500"
    rows = cur.execute(sql, params).fetchall()
    items = [
        {
            "id": r[0],
            "lesson_id": r[1],
            "author_name": r[2],
            "author_email": r[3],
            "author_role": r[4],
            "body": r[5],
            "is_question": bool(r[6]) or r[8] == "question",
            "created_at": r[7],
            "comment_type": r[8],
            "comment_type_label": COMMENT_TYPE_LABELS.get(r[8], r[8]),
            "lesson_no": r[9],
            "lesson_title": r[10],
            "class_id": r[11],
            "class_name": r[12],
            "course_id": r[13],
            "course_code": r[14],
            "course_name": r[15],
            "assignment_id": r[16],
        }
        for r in rows
    ]
    if q:
        ql = q.lower()
        items = [
            it
            for it in items
            if ql in (it["body"] or "").lower()
            or ql in (it["author_name"] or "").lower()
            or ql in (it["lesson_title"] or "").lower()
            or ql in (it["course_code"] or "").lower()
            or ql in (it["class_name"] or "").lower()
        ]
    return items


def list_comment_filter_options(conn, scopes: list[str] | None = None) -> dict:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    courses = [
        {"id": r[0], "code": r[1], "name": r[2]}
        for r in cur.execute(
            "SELECT DISTINCT c.id, c.code, c.name FROM courses c "
            "JOIN teaching_assignments ta ON ta.course_id=c.id "
            "JOIN class_groups cg ON cg.id=ta.class_id "
            f"WHERE {frag} ORDER BY c.code",
            params,
        ).fetchall()
    ]
    classes = [
        {"id": r[0], "name": r[1], "program_code": r[2]}
        for r in cur.execute(
            "SELECT DISTINCT cg.id, cg.name, cg.program_code FROM class_groups cg "
            "JOIN teaching_assignments ta ON ta.class_id=cg.id "
            f"WHERE {frag} ORDER BY cg.name",
            params,
        ).fetchall()
    ]
    chapters = [
        {"lesson_no": r[0]}
        for r in cur.execute(
            "SELECT DISTINCT cl.lesson_no FROM class_lessons cl "
            "JOIN teaching_assignments ta ON ta.id=cl.assignment_id "
            "JOIN class_groups cg ON cg.id=ta.class_id "
            f"WHERE {frag} ORDER BY cl.lesson_no",
            params,
        ).fetchall()
    ]
    return {
        "courses": courses,
        "classes": classes,
        "chapters": chapters,
        "comment_types": [
            {"id": k, "label": v} for k, v in COMMENT_TYPE_LABELS.items()
        ],
    }


def list_assignments_for_lessons(conn, scopes: list[str] | None) -> list[dict]:
    """List class–course offerings with lesson counts (for coordinator hub)."""
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    rows = cur.execute(
        "SELECT ta.id, cg.name, cg.program_code, c.code, c.name, "
        "fl.full_name, fe.full_name, ta.status, "
        "(SELECT COUNT(*) FROM class_lessons cl WHERE cl.assignment_id = ta.id), "
        "(SELECT COUNT(*) FROM class_lessons cl WHERE cl.assignment_id = ta.id "
        " AND cl.status = 'published') "
        "FROM teaching_assignments ta "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        "LEFT JOIN faculty fl ON fl.id = ta.lecturer_id "
        "LEFT JOIN faculty fe ON fe.id = ta.expert_id "
        f"WHERE {frag} "
        "ORDER BY cg.program_code, cg.name, c.code",
        params,
    ).fetchall()
    return [
        {
            "id": r[0],
            "assignment_id": r[0],
            "class_name": r[1],
            "program_code": r[2],
            "course_code": r[3],
            "course_name": r[4],
            "lecturer": r[5] or "—",
            "expert": r[6] or "—",
            "status": r[7],
            "lesson_count": r[8] or 0,
            "published_count": r[9] or 0,
        }
        for r in rows
    ]


def list_student_lessons(
    conn,
    *,
    scopes: list[str] | None = None,
    student_email: str | None = None,
    q: str = "",
) -> list[dict]:
    """Published lessons visible to student (by class enrollment or scope fallback)."""
    cur = conn.cursor()
    ensure_class_lesson_tables(cur)
    from ops_data import _scopes_sql

    if student_email:
        rows = cur.execute(
            "SELECT cl.id, cl.lesson_no, cl.title, cl.preview_summary, cl.lesson_type, "
            "cl.lesson_date, cg.name, c.code, c.name, ta.id, "
            "(SELECT COUNT(*) FROM course_materials m WHERE m.lesson_id = cl.id "
            " AND m.release_status='released'), "
            "(SELECT COUNT(*) FROM lesson_comments lc WHERE lc.lesson_id = cl.id) "
            "FROM class_lessons cl "
            "JOIN teaching_assignments ta ON ta.id = cl.assignment_id "
            "JOIN class_groups cg ON cg.id = ta.class_id "
            "JOIN courses c ON c.id = ta.course_id "
            "JOIN class_students cs ON cs.class_id = cg.id "
            "WHERE cl.status = 'published' AND lower(cs.email) = lower(?) "
            "AND (IFNULL(cl.publish_at,'') = '' OR cl.publish_at <= ?) "
            "ORDER BY cg.name, c.code, cl.lesson_no",
            (student_email, datetime.utcnow().strftime("%Y-%m-%dT%H:%M")),
        ).fetchall()
    else:
        frag, params = _scopes_sql(scopes, "cg.program_code")
        rows = cur.execute(
            "SELECT cl.id, cl.lesson_no, cl.title, cl.preview_summary, cl.lesson_type, "
            "cl.lesson_date, cg.name, c.code, c.name, ta.id, "
            "(SELECT COUNT(*) FROM course_materials m WHERE m.lesson_id = cl.id "
            " AND m.release_status='released'), "
            "(SELECT COUNT(*) FROM lesson_comments lc WHERE lc.lesson_id = cl.id) "
            "FROM class_lessons cl "
            "JOIN teaching_assignments ta ON ta.id = cl.assignment_id "
            "JOIN class_groups cg ON cg.id = ta.class_id "
            "JOIN courses c ON c.id = ta.course_id "
            f"WHERE cl.status = 'published' AND {frag} "
            "AND (IFNULL(cl.publish_at,'') = '' OR cl.publish_at <= ?) "
            "ORDER BY cg.name, c.code, cl.lesson_no",
            [*params, datetime.utcnow().strftime("%Y-%m-%dT%H:%M")],
        ).fetchall()
    items = [
        {
            "id": r[0],
            "lesson_no": r[1],
            "title": r[2],
            "preview_summary": r[3],
            "lesson_type": r[4],
            "lesson_date": r[5],
            "class_name": r[6],
            "course_code": r[7],
            "course_name": r[8],
            "assignment_id": r[9],
            "released_files": r[10] or 0,
            "comment_count": r[11] or 0,
            "status": "published",
        }
        for r in rows
    ]
    if q:
        ql = q.lower()
        items = [
            it
            for it in items
            if ql in (it["title"] or "").lower()
            or ql in (it["preview_summary"] or "").lower()
            or ql in (it["course_code"] or "").lower()
            or ql in (it["course_name"] or "").lower()
            or ql in (it["class_name"] or "").lower()
        ]
    return items
