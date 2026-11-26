"""
Chương trình đào tạo · Học phần / Syllabus · Buổi học · Tài liệu (release tới HV).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


MATERIAL_EXTS = {
    "pdf",
    "ppt",
    "pptx",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "zip",
    "rar",
    "jpg",
    "jpeg",
    "png",
    "txt",
    "mp4",
    "webm",
    "mov",
}


def allowed_material_filename(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in MATERIAL_EXTS


def ensure_course_content_tables(cur) -> None:
    # Enrich courses with syllabus fields (SQLite ADD COLUMN)
    for col, typedef in (
        ("syllabus_note", "TEXT"),
        ("learning_outcomes", "TEXT"),
        ("assessment_note", "TEXT"),
        ("reading_list", "TEXT"),
        ("syllabus_status", "TEXT DEFAULT 'draft'"),  # draft | published
        ("credits", "REAL DEFAULT 3"),
        ("independent", "INTEGER DEFAULT 0"),
    ):
        try:
            cur.execute(f"ALTER TABLE courses ADD COLUMN {col} {typedef}")
        except Exception:
            pass

    cur.execute(
        "CREATE TABLE IF NOT EXISTS course_sessions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "course_id INTEGER NOT NULL, "
        "session_no INTEGER NOT NULL, "
        "session_type TEXT DEFAULT 'theory', "  # theory | practice | other
        "title TEXT NOT NULL, "
        "content_outline TEXT, "
        "objectives TEXT, "
        "duration_hours REAL DEFAULT 3, "
        "sort_order INTEGER DEFAULT 0, "
        "status TEXT DEFAULT 'planned', "  # planned | ready | done
        "UNIQUE(course_id, session_no), "
        "FOREIGN KEY (course_id) REFERENCES courses(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS course_materials ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "course_id INTEGER NOT NULL, "
        "session_id INTEGER, "
        "class_id INTEGER, "  # optional: chỉ lớp này; NULL = mọi lớp dùng HP
        "title TEXT NOT NULL, "
        "description TEXT, "
        "material_type TEXT DEFAULT 'slide', "
        # syllabus | slide | reading | exercise | video | other
        "original_filename TEXT, "
        "stored_name TEXT, "
        "file_path TEXT, "
        "mime_type TEXT, "
        "file_size INTEGER DEFAULT 0, "
        "release_status TEXT DEFAULT 'draft', "  # draft | released | archived
        "released_at TEXT, "
        "uploaded_by TEXT, "
        "search_text TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (course_id) REFERENCES courses(id), "
        "FOREIGN KEY (session_id) REFERENCES course_sessions(id))"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_course_materials_search "
        "ON course_materials(course_id, release_status)"
    )
    try:
        cur.execute("ALTER TABLE course_sessions ADD COLUMN requirements TEXT")
    except Exception:
        pass


def _build_search_text(title: str, description: str | None, filename: str | None, extra: str = "") -> str:
    parts = [title or "", description or "", filename or "", extra or ""]
    return " ".join(p for p in parts if p).lower()


def ensure_sessions_for_course(cur, course_id: int) -> int:
    """Create default LT/TH sessions from course theory/practice counts if none.

    MBA and MMS default to 8 sessions. MSCM and others keep 7 LT + 2 TH.
    """
    cur.execute("SELECT COUNT(*) FROM course_sessions WHERE course_id = ?", (course_id,))
    if cur.fetchone()[0] > 0:
        return 0
    row = cur.execute(
        "SELECT c.theory_sessions, c.practice_sessions, c.name, v.program_code "
        "FROM courses c JOIN program_versions v ON v.id = c.program_version_id "
        "WHERE c.id = ?",
        (course_id,),
    ).fetchone()
    if not row:
        return 0
    theory_n, practice_n, cname, prog = row[0], row[1], row[2], row[3]
    if prog in ("MBA", "MMS"):
        if theory_n is None and practice_n is None:
            theory_n, practice_n = 8, 0
        elif (theory_n or 0) + (practice_n or 0) == 0:
            theory_n, practice_n = 8, 0
        else:
            theory_n = theory_n if theory_n is not None else 8
            practice_n = practice_n if practice_n is not None else 0
    else:
        theory_n = theory_n if theory_n is not None else 7
        practice_n = practice_n if practice_n is not None else 2
    created = 0
    n = 0
    for i in range(1, int(theory_n) + 1):
        n += 1
        title = f"Session {i}: {cname}" if prog in ("MBA", "MMS") else f"Buổi LT {i}: {cname}"
        outline = f"Session {i} content." if prog in ("MBA", "MMS") else f"Nội dung lý thuyết buổi {i}."
        cur.execute(
            "INSERT INTO course_sessions "
            "(course_id, session_no, session_type, title, content_outline, sort_order, status) "
            "VALUES (?,?, 'theory', ?, ?, ?, 'planned')",
            (course_id, n, title, outline, n),
        )
        created += 1
    for i in range(1, int(practice_n) + 1):
        n += 1
        cur.execute(
            "INSERT INTO course_sessions "
            "(course_id, session_no, session_type, title, content_outline, sort_order, status) "
            "VALUES (?,?, 'practice', ?, ?, ?, 'planned')",
            (
                course_id,
                n,
                f"Buổi TH/CG {i}: {cname}",
                f"Nội dung chuyên gia / thực hành buổi {i}.",
                n,
            ),
        )
        created += 1
    return created


def seed_course_content(conn) -> dict:
    cur = conn.cursor()
    ensure_course_content_tables(cur)
    created = {"sessions": 0, "materials": 0, "syllabus": 0}

    courses = cur.execute(
        "SELECT c.id, c.code, c.name, c.syllabus_note, v.program_code "
        "FROM courses c JOIN program_versions v ON v.id = c.program_version_id"
    ).fetchall()
    for cid, code, name, note, prog in courses:
        created["sessions"] += ensure_sessions_for_course(cur, cid)
        if not note:
            cur.execute(
                "UPDATE courses SET syllabus_note = ?, learning_outcomes = ?, "
                "assessment_note = ?, reading_list = ?, syllabus_status = 'published' "
                "WHERE id = ?",
                (
                    f"Đề cương học phần {code} — {name} ({prog}). "
                    "Mô tả mục tiêu, nội dung theo buổi và hình thức đánh giá.",
                    f"- Nắm vững kiến thức cốt lõi của {name}\n"
                    "- Áp dụng vào tình huống thực tiễn X\n"
                    "- Làm việc nhóm và thuyết trình",
                    "Điểm thành phần 40% + điểm thi/cuối kỳ 60% (mặc định; Điều phối có thể chỉnh).",
                    "Tài liệu do GV cung cấp trên SmartUni / Canvas trước khai giảng.",
                    cid,
                ),
            )
            created["syllabus"] += 1

    # Placeholder released materials (metadata-only if no physical file yet)
    cur.execute("SELECT COUNT(*) FROM course_materials")
    if cur.fetchone()[0] == 0:
        sample = cur.execute(
            "SELECT c.id, c.code, c.name, s.id, s.title "
            "FROM courses c "
            "JOIN course_sessions s ON s.course_id = c.id AND s.session_no = 1 "
            "LIMIT 5"
        ).fetchall()
        for cid, code, cname, sid, stitle in sample:
            title = f"Syllabus {code}"
            cur.execute(
                "INSERT INTO course_materials "
                "(course_id, session_id, title, description, material_type, "
                "original_filename, release_status, released_at, uploaded_by, search_text) "
                "VALUES (?,?,?,?, 'syllabus', ?, 'released', ?, 'seed', ?)",
                (
                    cid,
                    None,
                    title,
                    f"Đề cương học phần {cname}",
                    f"{code}_syllabus.pdf",
                    datetime.utcnow().isoformat() + "Z",
                    _build_search_text(title, cname, f"{code}_syllabus.pdf", code),
                ),
            )
            created["materials"] += 1
            title2 = f"Slide buổi 1 — {code}"
            cur.execute(
                "INSERT INTO course_materials "
                "(course_id, session_id, title, description, material_type, "
                "original_filename, release_status, released_at, uploaded_by, search_text) "
                "VALUES (?,?,?,?, 'slide', ?, 'released', ?, 'seed', ?)",
                (
                    cid,
                    sid,
                    title2,
                    stitle,
                    f"{code}_buoi1.pptx",
                    datetime.utcnow().isoformat() + "Z",
                    _build_search_text(title2, stitle, f"{code}_buoi1.pptx", code),
                ),
            )
            created["materials"] += 1
            # one draft (not visible to students)
            cur.execute(
                "INSERT INTO course_materials "
                "(course_id, session_id, title, description, material_type, "
                "original_filename, release_status, uploaded_by, search_text) "
                "VALUES (?,?,?,?, 'reading', ?, 'draft', 'seed', ?)",
                (
                    cid,
                    sid,
                    f"Reading pack {code} (nháp)",
                    "Tài liệu đọc thêm — chưa release",
                    f"{code}_reading.pdf",
                    _build_search_text(f"Reading pack {code}", "nháp", f"{code}_reading.pdf"),
                ),
            )
            created["materials"] += 1

    return created


def list_program_versions(
    conn, scopes: list[str] | None, *, q: str = "", program_code: str = "", version_code: str = "", cohort: str = ""
) -> list[dict]:
    from ops_data import _scopes_sql, ensure_ops_tables, format_cohort_label

    cur = conn.cursor()
    ensure_ops_tables(cur)
    frag, params = _scopes_sql(scopes, "v.program_code")
    sql = (
        "SELECT v.id, v.program_code, v.version_code, v.name, v.description, v.is_active, "
        "COUNT(c.id), IFNULL(v.cohort_no,''), IFNULL(v.year_start,''), IFNULL(v.year_end,'') "
        "FROM program_versions v "
        "LEFT JOIN courses c ON c.program_version_id = v.id "
        f"WHERE {frag}"
    )
    if program_code:
        sql += " AND v.program_code = ?"
        params.append(program_code.strip().upper())
    if version_code:
        sql += " AND v.version_code LIKE ?"
        params.append(f"%{version_code.strip()}%")
    if (cohort or "").strip():
        sql += (
            " AND (IFNULL(v.cohort_no,'') = ? OR CAST(IFNULL(v.year_start,'') AS TEXT) = ? "
            "OR v.version_code LIKE ?)"
        )
        token = cohort.strip()
        params.extend([token, token, f"%{token}%"])
    if q:
        like = f"%{q}%"
        sql += (
            " AND (v.program_code LIKE ? OR v.version_code LIKE ? OR v.name LIKE ? "
            "OR COALESCE(v.description,'') LIKE ?)"
        )
        params.extend([like, like, like, like])
    sql += " GROUP BY v.id ORDER BY v.program_code, v.version_code"
    rows = cur.execute(sql, params).fetchall()
    return [
        {
            "id": r[0],
            "program_code": r[1],
            "version_code": r[2],
            "name": r[3],
            "description": r[4],
            "is_active": bool(r[5]),
            "course_count": r[6] or 0,
            "cohort_no": r[7] if len(r) > 7 else "",
            "year_start": r[8] if len(r) > 8 else "",
            "year_end": r[9] if len(r) > 9 else "",
            "cohort_label": format_cohort_label(
                r[7] if len(r) > 7 else "",
                r[8] if len(r) > 8 else "",
                r[9] if len(r) > 9 else "",
            ),
        }
        for r in rows
    ]


def list_courses(
    conn,
    scopes: list[str] | None,
    version_id: int | None = None,
    q: str = "",
    *,
    program_code: str = "",
    version_code: str = "",
    cohort: str = "",
) -> list[dict]:
    from ops_data import _scopes_sql, ensure_ops_tables, format_cohort_label

    cur = conn.cursor()
    ensure_course_content_tables(cur)
    ensure_ops_tables(cur)
    frag, params = _scopes_sql(scopes, "v.program_code")
    sql = (
        "SELECT c.id, c.code, c.name, c.semester, c.sort_order, "
        "c.theory_sessions, c.practice_sessions, c.syllabus_note, c.learning_outcomes, "
        "c.assessment_note, c.reading_list, c.syllabus_status, "
        "v.version_code, v.program_code, v.id, "
        "(SELECT COUNT(*) FROM course_sessions s WHERE s.course_id = c.id), "
        "(SELECT COUNT(*) FROM course_materials m WHERE m.course_id = c.id), "
        "(SELECT COUNT(*) FROM course_materials m WHERE m.course_id = c.id AND m.release_status='released'), "
        "IFNULL(v.cohort_no,''), IFNULL(v.year_start,''), IFNULL(v.year_end,'') "
        "FROM courses c JOIN program_versions v ON v.id = c.program_version_id "
        f"WHERE {frag}"
    )
    if version_id:
        sql += " AND c.program_version_id = ?"
        params.append(version_id)
    if program_code:
        sql += " AND v.program_code = ?"
        params.append(program_code.strip().upper())
    if version_code:
        sql += " AND v.version_code LIKE ?"
        params.append(f"%{version_code.strip()}%")
    if (cohort or "").strip():
        sql += (
            " AND (IFNULL(v.cohort_no,'') = ? OR CAST(IFNULL(v.year_start,'') AS TEXT) = ? "
            "OR v.version_code LIKE ?)"
        )
        token = cohort.strip()
        params.extend([token, token, f"%{token}%"])
    if q:
        like = f"%{q}%"
        sql += (
            " AND (c.code LIKE ? OR c.name LIKE ? OR c.syllabus_note LIKE ? "
            "OR v.program_code LIKE ? OR v.version_code LIKE ?)"
        )
        params.extend([like, like, like, like, like])
    sql += " ORDER BY v.program_code, c.sort_order"
    rows = cur.execute(sql, params).fetchall()
    return [
        {
            "id": r[0],
            "code": r[1],
            "name": r[2],
            "semester": r[3],
            "sort_order": r[4],
            "theory_sessions": r[5],
            "practice_sessions": r[6],
            "syllabus_note": r[7],
            "learning_outcomes": r[8],
            "assessment_note": r[9],
            "reading_list": r[10],
            "syllabus_status": r[11] or "draft",
            "version_code": r[12],
            "program_code": r[13],
            "program_version_id": r[14],
            "session_count": r[15] or 0,
            "material_count": r[16] or 0,
            "released_count": r[17] or 0,
            "cohort_label": format_cohort_label(
                r[18] if len(r) > 18 else "",
                r[19] if len(r) > 19 else "",
                r[20] if len(r) > 20 else "",
            ),
        }
        for r in rows
    ]


def get_course_detail(conn, course_id: int) -> dict | None:
    cur = conn.cursor()
    ensure_course_content_tables(cur)
    ensure_sessions_for_course(cur, course_id)
    row = cur.execute(
        "SELECT c.id, c.code, c.name, c.semester, c.sort_order, "
        "c.theory_sessions, c.practice_sessions, c.syllabus_note, c.learning_outcomes, "
        "c.assessment_note, c.reading_list, c.syllabus_status, c.credits, "
        "v.version_code, v.program_code, v.id, v.name "
        "FROM courses c JOIN program_versions v ON v.id = c.program_version_id "
        "WHERE c.id = ?",
        (course_id,),
    ).fetchone()
    if not row:
        return None
    sessions = cur.execute(
        "SELECT id, session_no, session_type, title, content_outline, objectives, "
        "duration_hours, sort_order, status, requirements "
        "FROM course_sessions WHERE course_id = ? ORDER BY sort_order, session_no",
        (course_id,),
    ).fetchall()
    materials = cur.execute(
        "SELECT id, session_id, class_id, title, description, material_type, "
        "original_filename, file_size, release_status, released_at, uploaded_by, created_at, "
        "CASE WHEN file_path IS NOT NULL AND file_path != '' THEN 1 ELSE 0 END "
        "FROM course_materials WHERE course_id = ? ORDER BY created_at DESC",
        (course_id,),
    ).fetchall()
    return {
        "id": row[0],
        "code": row[1],
        "name": row[2],
        "semester": row[3],
        "sort_order": row[4],
        "theory_sessions": row[5],
        "practice_sessions": row[6],
        "syllabus_note": row[7],
        "learning_outcomes": row[8],
        "assessment_note": row[9],
        "reading_list": row[10],
        "syllabus_status": row[11] or "draft",
        "credits": row[12],
        "version_code": row[13],
        "program_code": row[14],
        "program_version_id": row[15],
        "version_name": row[16],
        "sessions": [
            {
                "id": s[0],
                "session_no": s[1],
                "session_type": s[2],
                "title": s[3],
                "content_outline": s[4],
                "objectives": s[5],
                "duration_hours": s[6],
                "sort_order": s[7],
                "status": s[8],
                "requirements": s[9],
            }
            for s in sessions
        ],
        "materials": [
            {
                "id": m[0],
                "session_id": m[1],
                "class_id": m[2],
                "title": m[3],
                "description": m[4],
                "material_type": m[5],
                "original_filename": m[6],
                "file_size": m[7],
                "release_status": m[8],
                "released_at": m[9],
                "uploaded_by": m[10],
                "created_at": m[11],
                "has_file": bool(m[12]),
            }
            for m in materials
        ],
    }


def update_course_syllabus(conn, course_id: int, data: dict) -> dict | None:
    cur = conn.cursor()
    ensure_course_content_tables(cur)
    fields = []
    params: list[Any] = []
    for key in (
        "name",
        "syllabus_note",
        "learning_outcomes",
        "assessment_note",
        "reading_list",
        "syllabus_status",
        "theory_sessions",
        "practice_sessions",
        "semester",
    ):
        if key in data and data[key] is not None:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if not fields:
        return get_course_detail(conn, course_id)
    params.append(course_id)
    cur.execute(f"UPDATE courses SET {', '.join(fields)} WHERE id = ?", params)
    if cur.rowcount == 0:
        return None
    # regenerate sessions if counts changed and requested
    if data.get("rebuild_sessions"):
        cur.execute("DELETE FROM course_sessions WHERE course_id = ?", (course_id,))
        ensure_sessions_for_course(cur, course_id)
    conn.commit()
    return get_course_detail(conn, course_id)


def update_session(conn, session_id: int, data: dict) -> dict | None:
    cur = conn.cursor()
    ensure_course_content_tables(cur)
    fields = []
    params: list[Any] = []
    for key in (
        "title",
        "content_outline",
        "objectives",
        "requirements",
        "session_type",
        "status",
        "duration_hours",
    ):
        if key in data and data[key] is not None:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if not fields:
        return None
    params.append(session_id)
    cur.execute(f"UPDATE course_sessions SET {', '.join(fields)} WHERE id = ?", params)
    if cur.rowcount == 0:
        return None
    conn.commit()
    row = cur.execute(
        "SELECT id, course_id, session_no, session_type, title, content_outline, objectives, "
        "requirements, duration_hours, status FROM course_sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    return {
        "id": row[0],
        "course_id": row[1],
        "session_no": row[2],
        "session_type": row[3],
        "title": row[4],
        "content_outline": row[5],
        "objectives": row[6],
        "requirements": row[7],
        "duration_hours": row[8],
        "status": row[9],
    }


def reorder_course_sessions(conn, course_id: int, session_ids: list[int]) -> dict:
    """Reorder sessions by drag-drop. Updates session_no + sort_order to 1..n."""
    cur = conn.cursor()
    ensure_course_content_tables(cur)
    exists = cur.execute("SELECT id FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not exists:
        raise ValueError("Course not found")
    if not session_ids:
        raise ValueError("session_ids required")
    try:
        ordered = [int(x) for x in session_ids]
    except (TypeError, ValueError) as e:
        raise ValueError("session_ids must be integers") from e
    if len(ordered) != len(set(ordered)):
        raise ValueError("session_ids contains duplicates")
    rows = cur.execute(
        "SELECT id FROM course_sessions WHERE course_id = ?", (course_id,)
    ).fetchall()
    current_ids = {r[0] for r in rows}
    if set(ordered) != current_ids:
        raise ValueError("session_ids must include every session of this course exactly once")

    # Avoid UNIQUE(course_id, session_no): park numbers then assign final order.
    for i, sid in enumerate(ordered):
        cur.execute(
            "UPDATE course_sessions SET session_no = ?, sort_order = ? WHERE id = ? AND course_id = ?",
            (-(i + 1), i + 1, sid, course_id),
        )
    for i, sid in enumerate(ordered):
        cur.execute(
            "UPDATE course_sessions SET session_no = ?, sort_order = ? WHERE id = ? AND course_id = ?",
            (i + 1, i + 1, sid, course_id),
        )
    conn.commit()
    sessions = cur.execute(
        "SELECT id, session_no, session_type, title, sort_order, status "
        "FROM course_sessions WHERE course_id = ? ORDER BY sort_order, session_no",
        (course_id,),
    ).fetchall()
    return {
        "ok": True,
        "course_id": course_id,
        "sessions": [
            {
                "id": s[0],
                "session_no": s[1],
                "session_type": s[2],
                "title": s[3],
                "sort_order": s[4],
                "status": s[5],
            }
            for s in sessions
        ],
    }


def add_material(
    conn,
    *,
    course_id: int,
    title: str,
    description: str = "",
    material_type: str = "slide",
    session_id: int | None = None,
    class_id: int | None = None,
    original_filename: str | None = None,
    stored_name: str | None = None,
    file_path: str | None = None,
    mime_type: str | None = None,
    file_size: int = 0,
    uploaded_by: str = "",
    release_status: str = "draft",
) -> dict:
    cur = conn.cursor()
    ensure_course_content_tables(cur)
    released_at = datetime.utcnow().isoformat() + "Z" if release_status == "released" else None
    search = _build_search_text(title, description, original_filename)
    cur.execute(
        "INSERT INTO course_materials "
        "(course_id, session_id, class_id, title, description, material_type, "
        "original_filename, stored_name, file_path, mime_type, file_size, "
        "release_status, released_at, uploaded_by, search_text) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            course_id,
            session_id,
            class_id,
            title,
            description,
            material_type,
            original_filename,
            stored_name,
            file_path,
            mime_type,
            file_size,
            release_status,
            released_at,
            uploaded_by,
            search,
        ),
    )
    mid = cur.lastrowid
    conn.commit()
    return {"id": mid, "title": title, "release_status": release_status}


def set_material_release(conn, material_id: int, release_status: str) -> dict | None:
    if release_status not in ("draft", "released", "archived"):
        raise ValueError("Invalid release_status")
    cur = conn.cursor()
    released_at = datetime.utcnow().isoformat() + "Z" if release_status == "released" else None
    cur.execute(
        "UPDATE course_materials SET release_status = ?, released_at = ? WHERE id = ?",
        (release_status, released_at, material_id),
    )
    if cur.rowcount == 0:
        return None
    conn.commit()
    return {"id": material_id, "release_status": release_status, "released_at": released_at}


def get_material_file(conn, material_id: int) -> dict | None:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id, title, original_filename, file_path, mime_type, release_status, course_id, "
        "lesson_id "
        "FROM course_materials WHERE id = ?",
        (material_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "title": row[1],
        "original_filename": row[2],
        "file_path": row[3],
        "mime_type": row[4],
        "release_status": row[5],
        "course_id": row[6],
        "lesson_id": row[7],
    }


def list_materials_admin(
    conn,
    scopes: list[str] | None,
    q: str = "",
    release_status: str = "",
) -> list[dict]:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_course_content_tables(cur)
    frag, params = _scopes_sql(scopes, "v.program_code")
    sql = (
        "SELECT m.id, m.title, m.material_type, m.release_status, m.original_filename, "
        "m.file_size, m.released_at, m.created_at, m.uploaded_by, "
        "c.code, c.name, v.program_code, s.session_no, s.title, "
        "CASE WHEN m.file_path IS NOT NULL AND m.file_path != '' THEN 1 ELSE 0 END, "
        "c.id "
        "FROM course_materials m "
        "JOIN courses c ON c.id = m.course_id "
        "JOIN program_versions v ON v.id = c.program_version_id "
        "LEFT JOIN course_sessions s ON s.id = m.session_id "
        f"WHERE {frag}"
    )
    if release_status:
        sql += " AND m.release_status = ?"
        params.append(release_status)
    if q:
        sql += " AND (m.search_text LIKE ? OR c.code LIKE ? OR c.name LIKE ? OR m.title LIKE ?)"
        ql = f"%{q.lower()}%"
        params.extend([ql, f"%{q}%", f"%{q}%", f"%{q}%"])
    sql += " ORDER BY m.created_at DESC"
    rows = cur.execute(sql, params).fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "material_type": r[2],
            "release_status": r[3],
            "original_filename": r[4],
            "file_size": r[5],
            "released_at": r[6],
            "created_at": r[7],
            "uploaded_by": r[8],
            "course_code": r[9],
            "course_name": r[10],
            "program_code": r[11],
            "session_no": r[12],
            "session_title": r[13],
            "has_file": bool(r[14]),
            "course_id": r[15],
            "status": r[3],
        }
        for r in rows
    ]


def student_course_ids(conn, student_email: str | None = None, scopes: list[str] | None = None) -> list[int]:
    """Courses visible to a student via class enrollment (or all in scope for demo)."""
    cur = conn.cursor()
    if student_email:
        rows = cur.execute(
            "SELECT DISTINCT ta.course_id "
            "FROM class_students cs "
            "JOIN class_groups cg ON cg.id = cs.class_id "
            "JOIN teaching_assignments ta ON ta.class_id = cg.id "
            "WHERE lower(cs.email) = lower(?)",
            (student_email,),
        ).fetchall()
        ids = [r[0] for r in rows]
        if ids:
            return ids
    # Fallback demo: all courses in program scope (coordinator preview / draft SV)
    from ops_data import _scopes_sql

    frag, params = _scopes_sql(scopes, "v.program_code")
    rows = cur.execute(
        "SELECT c.id FROM courses c "
        "JOIN program_versions v ON v.id = c.program_version_id "
        f"WHERE {frag}",
        params,
    ).fetchall()
    return [r[0] for r in rows]


def list_student_library(
    conn,
    *,
    q: str = "",
    scopes: list[str] | None = None,
    student_email: str | None = None,
    course_id: int | None = None,
) -> dict:
    cur = conn.cursor()
    ensure_course_content_tables(cur)
    course_ids = student_course_ids(conn, student_email, scopes)
    if not course_ids:
        return {"courses": [], "materials": [], "stats": {"courses": 0, "files": 0}}

    placeholders = ",".join("?" * len(course_ids))
    params: list[Any] = list(course_ids)
    course_sql = (
        f"SELECT c.id, c.code, c.name, c.syllabus_note, c.learning_outcomes, "
        f"c.assessment_note, c.reading_list, c.syllabus_status, v.program_code, v.version_code "
        f"FROM courses c JOIN program_versions v ON v.id = c.program_version_id "
        f"WHERE c.id IN ({placeholders}) AND c.syllabus_status = 'published'"
    )
    if course_id:
        course_sql += " AND c.id = ?"
        params.append(course_id)
    if q:
        course_sql += " AND (c.code LIKE ? OR c.name LIKE ? OR c.syllabus_note LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    course_sql += " ORDER BY v.program_code, c.code"
    courses = [
        {
            "id": r[0],
            "code": r[1],
            "name": r[2],
            "syllabus_note": r[3],
            "learning_outcomes": r[4],
            "assessment_note": r[5],
            "reading_list": r[6],
            "syllabus_status": r[7],
            "program_code": r[8],
            "version_code": r[9],
        }
        for r in cur.execute(course_sql, params).fetchall()
    ]

    mparams: list[Any] = list(course_ids)
    msql = (
        f"SELECT m.id, m.title, m.description, m.material_type, m.original_filename, "
        f"m.file_size, m.released_at, c.code, c.name, v.program_code, s.session_no, s.title, "
        f"CASE WHEN m.file_path IS NOT NULL AND m.file_path != '' THEN 1 ELSE 0 END, m.course_id "
        f"FROM course_materials m "
        f"JOIN courses c ON c.id = m.course_id "
        f"JOIN program_versions v ON v.id = c.program_version_id "
        f"LEFT JOIN course_sessions s ON s.id = m.session_id "
        f"WHERE m.course_id IN ({placeholders}) AND m.release_status = 'released'"
    )
    if course_id:
        msql += " AND m.course_id = ?"
        mparams.append(course_id)
    if q:
        msql += " AND (m.search_text LIKE ? OR m.title LIKE ? OR c.code LIKE ? OR c.name LIKE ?)"
        ql = f"%{q.lower()}%"
        mparams.extend([ql, f"%{q}%", f"%{q}%", f"%{q}%"])
    msql += " ORDER BY v.program_code, c.code, s.session_no, m.title"
    materials = [
        {
            "id": r[0],
            "title": r[1],
            "description": r[2],
            "material_type": r[3],
            "original_filename": r[4],
            "file_size": r[5],
            "released_at": r[6],
            "course_code": r[7],
            "course_name": r[8],
            "program_code": r[9],
            "session_no": r[10],
            "session_title": r[11],
            "has_file": bool(r[12]),
            "course_id": r[13],
            "can_download": bool(r[12]),
        }
        for r in cur.execute(msql, mparams).fetchall()
    ]

    sessions_by_course: dict[int, list] = {}
    for cid in course_ids:
        if course_id and cid != course_id:
            continue
        srows = cur.execute(
            "SELECT id, session_no, session_type, title, content_outline, requirements, status "
            "FROM course_sessions WHERE course_id = ? ORDER BY sort_order",
            (cid,),
        ).fetchall()
        sessions_by_course[cid] = [
            {
                "id": s[0],
                "session_no": s[1],
                "session_type": s[2],
                "title": s[3],
                "content_outline": s[4],
                "requirements": s[5],
                "status": s[6],
            }
            for s in srows
        ]

    for c in courses:
        c["sessions"] = sessions_by_course.get(c["id"], [])
        c["materials"] = [m for m in materials if m["course_id"] == c["id"]]

    return {
        "courses": courses,
        "materials": materials,
        "stats": {"courses": len(courses), "files": len(materials)},
        "query": q,
    }


def safe_download_name(name: str | None, fallback: str = "material.bin") -> str:
    raw = (name or fallback).strip() or fallback
    return re.sub(r"[^\w.\- ()\u00C0-\u1EF9]+", "_", raw)[:180]
