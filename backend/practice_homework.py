"""
Bài tập thực hành theo lớp–môn (teaching_assignments).

Mẫu import (Template Thuc hanh.doc / Excel):
  Mã câu hỏi | Nội dung | Điểm | Loại câu
  - Mã đề: C5-3-021 (parent / variant)
  - Câu: C5-3-021-1 … (sub-questions)
  HV làm online theo mã đề được giao; hiển thị STT_HoVaTen_MaDe.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

CODE_RE = re.compile(r"^(C\d+-\d+-\d+)(?:-(\d+))?$", re.I)
POINTS_RE = re.compile(r"(\d+[.,]\d+|\d+)\s*điểm", re.I)
PRACTICE_CHAPTER_RE = re.compile(r"^C(\d+)-", re.I)


def practice_chapter_token(code: str | None) -> str:
    """C5-3-021 → '5'."""
    m = PRACTICE_CHAPTER_RE.match(str(code or "").strip())
    return m.group(1) if m else ""


def ensure_practice_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS practice_homeworks ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "teaching_assignment_id INTEGER NOT NULL, "
        "title TEXT NOT NULL, "
        "instructions TEXT, "
        "due_at TEXT, "
        "status TEXT NOT NULL DEFAULT 'draft', "  # draft | published | closed
        "source_filename TEXT, "
        "created_by TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (teaching_assignment_id) REFERENCES teaching_assignments(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS practice_variants ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "homework_id INTEGER NOT NULL, "
        "code TEXT NOT NULL, "  # e.g. C5-3-021
        "context_text TEXT, "  # parent block content (DB name, table…)
        "sort_order INTEGER DEFAULT 0, "
        "UNIQUE(homework_id, code), "
        "FOREIGN KEY (homework_id) REFERENCES practice_homeworks(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS practice_questions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "homework_id INTEGER NOT NULL, "
        "variant_id INTEGER NOT NULL, "
        "code TEXT NOT NULL, "  # e.g. C5-3-021-1
        "title TEXT, "
        "content TEXT NOT NULL, "
        "points REAL DEFAULT 0, "
        "q_type TEXT DEFAULT 'practice', "
        "sort_order INTEGER DEFAULT 0, "
        "UNIQUE(homework_id, code), "
        "FOREIGN KEY (homework_id) REFERENCES practice_homeworks(id), "
        "FOREIGN KEY (variant_id) REFERENCES practice_variants(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS practice_submissions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "homework_id INTEGER NOT NULL, "
        "variant_id INTEGER NOT NULL, "
        "student_id INTEGER, "
        "student_name TEXT NOT NULL, "
        "student_email TEXT, "
        "student_code TEXT, "
        "display_label TEXT, "  # STT_HoVaTen_MaDe
        "status TEXT NOT NULL DEFAULT 'in_progress', "  # in_progress | submitted | graded
        "score REAL, "
        "started_at TEXT, "
        "submitted_at TEXT, "
        "graded_at TEXT, "
        "grader_note TEXT, "
        "UNIQUE(homework_id, student_email), "
        "FOREIGN KEY (homework_id) REFERENCES practice_homeworks(id), "
        "FOREIGN KEY (variant_id) REFERENCES practice_variants(id), "
        "FOREIGN KEY (student_id) REFERENCES class_students(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS practice_answers ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "submission_id INTEGER NOT NULL, "
        "question_id INTEGER NOT NULL, "
        "answer_text TEXT, "
        "score REAL, "
        "updated_at TEXT, "
        "UNIQUE(submission_id, question_id), "
        "FOREIGN KEY (submission_id) REFERENCES practice_submissions(id), "
        "FOREIGN KEY (question_id) REFERENCES practice_questions(id))"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_practice_hw_ta "
        "ON practice_homeworks(teaching_assignment_id)"
    )


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_practice_doc_bytes(raw: bytes) -> list[dict]:
    """Parse Template Thuc hanh (.doc binary) → list of variants with questions."""
    text = raw.decode("utf-16le", errors="ignore")
    buf: list[str] = []
    for ch in text:
        o = ord(ch)
        if (
            ch in "\n\r\t"
            or ch.isalnum()
            or ch in " .,;:!?()[]{}/\\-_+=*@#%&\"'<>|~`^$"
            or "\u00c0" <= ch <= "\u024f"
            or "\u1ea0" <= ch <= "\u1ef9"
        ):
            buf.append(ch)
        else:
            buf.append("\n")
    lines = []
    for line in "".join(buf).splitlines():
        line = " ".join(line.split())
        if len(line) >= 2:
            lines.append(line)
    return _parse_practice_lines(lines)


def parse_practice_text(text: str) -> list[dict]:
    lines = [" ".join(ln.split()) for ln in text.splitlines() if ln.strip()]
    return _parse_practice_lines(lines)


def _parse_practice_lines(lines: list[str]) -> list[dict]:
    variants: dict[str, dict] = {}
    order_v = 0
    current_parent: str | None = None
    current_q: dict | None = None
    collecting = "none"  # none | context | question

    def flush_q():
        nonlocal current_q
        if not current_q or not current_parent:
            return
        content = "\n".join(current_q["content_lines"]).strip()
        if not content:
            current_q = None
            return
        v = variants[current_parent]
        pts = current_q.get("points")
        if pts is None:
            for ln in current_q["content_lines"]:
                m = POINTS_RE.search(ln)
                if m:
                    pts = float(m.group(1).replace(",", "."))
                    break
        v["questions"].append(
            {
                "code": current_q["code"],
                "title": current_q.get("title") or "",
                "content": content,
                "points": float(pts or 0),
                "q_type": "practice",
                "sort_order": len(v["questions"]) + 1,
            }
        )
        current_q = None

    for line in lines:
        if line.lower() in ("mã câu hỏi", "nội dung", "điểm", "loại câu", "đáp án câu hỏi"):
            if line.lower() == "đáp án câu hỏi":
                collecting = "none"
            continue
        m = CODE_RE.match(line)
        if m:
            parent, sub = m.group(1).upper(), m.group(2)
            if sub is None:
                flush_q()
                current_parent = parent
                if parent not in variants:
                    order_v += 1
                    variants[parent] = {
                        "code": parent,
                        "context_text": "",
                        "context_lines": [],
                        "sort_order": order_v,
                        "questions": [],
                    }
                collecting = "context"
                current_q = None
            else:
                flush_q()
                current_parent = parent
                if parent not in variants:
                    order_v += 1
                    variants[parent] = {
                        "code": parent,
                        "context_text": "",
                        "context_lines": [],
                        "sort_order": order_v,
                        "questions": [],
                    }
                current_q = {
                    "code": f"{parent}-{sub}",
                    "title": "",
                    "content_lines": [],
                    "points": None,
                }
                collecting = "question"
            continue

        if collecting == "context" and current_parent:
            variants[current_parent]["context_lines"].append(line)
        elif collecting == "question" and current_q:
            if not current_q["title"] and len(line) < 80 and not POINTS_RE.search(line):
                # first short line often is title
                if not any(
                    x in line.lower()
                    for x in ("hãy ", "tạo ", "khởi tạo", "viết ")
                ):
                    current_q["title"] = line
                    continue
            current_q["content_lines"].append(line)
            pm = POINTS_RE.search(line)
            if pm and current_q.get("points") is None:
                current_q["points"] = float(pm.group(1).replace(",", "."))

    flush_q()
    out = []
    for v in sorted(variants.values(), key=lambda x: x["sort_order"]):
        ctx = "\n".join(v.get("context_lines") or []).strip()
        if not v["questions"] and not ctx:
            continue
        out.append(
            {
                "code": v["code"],
                "context_text": ctx,
                "sort_order": v["sort_order"],
                "questions": v["questions"],
            }
        )
    return out


def parse_practice_xlsx_bytes(raw: bytes) -> list[dict]:
    """Excel columns: Ma_cau_hoi | Noi_dung | Diem | Loai_cau | (optional Ma_de context rows)."""
    from io import BytesIO

    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ValueError("Cần openpyxl để import Excel")
    wb = load_workbook(BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    # skip header
    start = 1 if rows[0] and str(rows[0][0]).lower().startswith("ma") else 0
    lines: list[str] = []
    for r in rows[start:]:
        if not r or r[0] is None:
            continue
        code = str(r[0]).strip()
        content = str(r[1] or "").strip()
        points = r[2]
        lines.append(code)
        if content:
            for ln in content.splitlines():
                lines.append(ln)
        if points is not None and str(points).strip() != "":
            try:
                lines.append(f"{float(points)} điểm")
            except Exception:
                lines.append(f"{points} điểm")
    return _parse_practice_lines(lines)


def _ta_meta(conn, teaching_assignment_id: int) -> dict | None:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT ta.id, cg.id, cg.name, cg.program_code, c.id, c.code, c.name, "
        "f.full_name "
        "FROM teaching_assignments ta "
        "JOIN class_groups cg ON cg.id = ta.class_id "
        "JOIN courses c ON c.id = ta.course_id "
        "LEFT JOIN faculty f ON f.id = ta.lecturer_id "
        "WHERE ta.id = ?",
        (teaching_assignment_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "teaching_assignment_id": row[0],
        "class_id": row[1],
        "class_name": row[2],
        "program_code": row[3],
        "course_id": row[4],
        "course_code": row[5],
        "course_name": row[6],
        "lecturer": row[7] or "",
    }


def create_homework(
    conn,
    teaching_assignment_id: int,
    *,
    title: str,
    instructions: str = "",
    due_at: str = "",
    created_by: str = "",
    variants: list[dict] | None = None,
    source_filename: str = "",
    status: str = "draft",
) -> dict:
    cur = conn.cursor()
    ensure_practice_tables(cur)
    meta = _ta_meta(conn, teaching_assignment_id)
    if not meta:
        raise ValueError("Không tìm thấy phân công giảng dạy (lớp–môn)")
    title = (title or "").strip() or f"Bài thực hành — {meta['course_code']}"
    cur.execute(
        "INSERT INTO practice_homeworks "
        "(teaching_assignment_id, title, instructions, due_at, status, source_filename, created_by, created_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            teaching_assignment_id,
            title,
            instructions or "",
            due_at or "",
            status if status in ("draft", "published", "closed") else "draft",
            source_filename or "",
            created_by or "",
            _now(),
        ),
    )
    hw_id = cur.lastrowid
    if variants:
        _insert_variants(cur, hw_id, variants)
    conn.commit()
    return get_homework(conn, hw_id)


def _insert_variants(cur, homework_id: int, variants: list[dict]) -> None:
    for i, v in enumerate(variants, 1):
        code = (v.get("code") or "").strip().upper()
        if not code:
            continue
        cur.execute(
            "INSERT OR REPLACE INTO practice_variants "
            "(homework_id, code, context_text, sort_order) VALUES (?,?,?,?)",
            (homework_id, code, v.get("context_text") or "", v.get("sort_order") or i),
        )
        # get id
        vid = cur.execute(
            "SELECT id FROM practice_variants WHERE homework_id=? AND code=?",
            (homework_id, code),
        ).fetchone()[0]
        # clear old questions for this variant on replace
        cur.execute(
            "DELETE FROM practice_questions WHERE homework_id=? AND variant_id=?",
            (homework_id, vid),
        )
        for j, q in enumerate(v.get("questions") or [], 1):
            qcode = (q.get("code") or "").strip().upper()
            content = (q.get("content") or "").strip()
            if not qcode or not content:
                continue
            cur.execute(
                "INSERT INTO practice_questions "
                "(homework_id, variant_id, code, title, content, points, q_type, sort_order) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    homework_id,
                    vid,
                    qcode,
                    q.get("title") or "",
                    content,
                    float(q.get("points") or 0),
                    q.get("q_type") or "practice",
                    q.get("sort_order") or j,
                ),
            )


def import_homework_from_file(
    conn,
    teaching_assignment_id: int,
    *,
    filename: str,
    raw: bytes,
    title: str = "",
    created_by: str = "",
    publish: bool = False,
) -> dict:
    name = (filename or "").lower()
    if name.endswith(".xlsx") or name.endswith(".xlsm"):
        variants = parse_practice_xlsx_bytes(raw)
    elif name.endswith(".doc") or name.endswith(".docx"):
        # .docx zip — try text; .doc via utf-16 heuristic
        if name.endswith(".docx"):
            try:
                from io import BytesIO
                from zipfile import ZipFile

                with ZipFile(BytesIO(raw)) as zf:
                    xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
                text = re.sub(r"<[^>]+>", "\n", xml)
                variants = parse_practice_text(text)
            except Exception:
                variants = parse_practice_doc_bytes(raw)
        else:
            variants = parse_practice_doc_bytes(raw)
    elif name.endswith(".json"):
        data = json.loads(raw.decode("utf-8"))
        variants = data if isinstance(data, list) else data.get("variants") or []
    elif name.endswith(".txt"):
        variants = parse_practice_text(raw.decode("utf-8", errors="ignore"))
    else:
        raise ValueError("Định dạng hỗ trợ: .doc, .docx, .xlsx, .json, .txt")

    if not variants:
        raise ValueError("Không đọc được câu hỏi từ file mẫu")

    return create_homework(
        conn,
        teaching_assignment_id,
        title=title or f"Thực hành — {Path(filename).stem}",
        instructions=(
            "Làm bài online theo mã đề được giao. "
            "Hiển thị thông tin STT_HoVaTen_MaDe trong phần mở đầu bài làm."
        ),
        created_by=created_by,
        variants=variants,
        source_filename=filename,
        status="published" if publish else "draft",
    )


def list_homeworks_for_ta(conn, teaching_assignment_id: int) -> list[dict]:
    cur = conn.cursor()
    ensure_practice_tables(cur)
    rows = cur.execute(
        "SELECT h.id, h.title, h.status, h.due_at, h.source_filename, h.created_at, "
        "(SELECT COUNT(*) FROM practice_variants v WHERE v.homework_id=h.id), "
        "(SELECT COUNT(*) FROM practice_questions q WHERE q.homework_id=h.id), "
        "(SELECT COUNT(*) FROM practice_submissions s WHERE s.homework_id=h.id), "
        "(SELECT COUNT(*) FROM practice_submissions s WHERE s.homework_id=h.id AND s.status='submitted') "
        "FROM practice_homeworks h WHERE h.teaching_assignment_id=? ORDER BY h.id DESC",
        (teaching_assignment_id,),
    ).fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "status": r[2],
            "due_at": r[3],
            "source_filename": r[4],
            "created_at": r[5],
            "variant_count": r[6],
            "question_count": r[7],
            "submission_count": r[8],
            "submitted_count": r[9],
            "teaching_assignment_id": teaching_assignment_id,
        }
        for r in rows
    ]


def get_homework(conn, homework_id: int, *, include_questions: bool = True) -> dict:
    cur = conn.cursor()
    ensure_practice_tables(cur)
    r = cur.execute(
        "SELECT id, teaching_assignment_id, title, instructions, due_at, status, "
        "source_filename, created_by, created_at FROM practice_homeworks WHERE id=?",
        (homework_id,),
    ).fetchone()
    if not r:
        raise ValueError("Không tìm thấy bài thực hành")
    meta = _ta_meta(conn, r[1]) or {}
    out = {
        "id": r[0],
        "teaching_assignment_id": r[1],
        "title": r[2],
        "instructions": r[3],
        "due_at": r[4],
        "status": r[5],
        "source_filename": r[6],
        "created_by": r[7],
        "created_at": r[8],
        "meta": meta,
        "variants": [],
    }
    if not include_questions:
        return out
    vars_ = cur.execute(
        "SELECT id, code, context_text, sort_order FROM practice_variants "
        "WHERE homework_id=? ORDER BY sort_order, id",
        (homework_id,),
    ).fetchall()
    for v in vars_:
        qs = cur.execute(
            "SELECT id, code, title, content, points, q_type, sort_order "
            "FROM practice_questions WHERE variant_id=? ORDER BY sort_order, id",
            (v[0],),
        ).fetchall()
        out["variants"].append(
            {
                "id": v[0],
                "code": v[1],
                "context_text": v[2],
                "sort_order": v[3],
                "questions": [
                    {
                        "id": q[0],
                        "code": q[1],
                        "title": q[2],
                        "content": q[3],
                        "points": q[4],
                        "q_type": q[5],
                        "sort_order": q[6],
                    }
                    for q in qs
                ],
            }
        )
    return out


def set_homework_status(conn, homework_id: int, status: str) -> dict:
    if status not in ("draft", "published", "closed"):
        raise ValueError("status không hợp lệ")
    cur = conn.cursor()
    ensure_practice_tables(cur)
    cur.execute("UPDATE practice_homeworks SET status=? WHERE id=?", (status, homework_id))
    if cur.rowcount == 0:
        raise ValueError("Không tìm thấy bài thực hành")
    conn.commit()
    return get_homework(conn, homework_id, include_questions=False)


def list_class_students_for_ta(conn, teaching_assignment_id: int) -> list[dict]:
    cur = conn.cursor()
    meta = _ta_meta(conn, teaching_assignment_id)
    if not meta:
        return []
    rows = cur.execute(
        "SELECT id, full_name, email, student_code FROM class_students "
        "WHERE class_id=? ORDER BY full_name",
        (meta["class_id"],),
    ).fetchall()
    return [
        {"id": r[0], "full_name": r[1], "email": r[2] or "", "student_code": r[3] or ""}
        for r in rows
    ]


def _pick_variant(conn, homework_id: int, student_key: str) -> int:
    cur = conn.cursor()
    rows = cur.execute(
        "SELECT id FROM practice_variants WHERE homework_id=? ORDER BY sort_order, id",
        (homework_id,),
    ).fetchall()
    if not rows:
        raise ValueError("Bài thực hành chưa có mã đề")
    idx = abs(hash(student_key)) % len(rows)
    return rows[idx][0]


def start_or_get_submission(
    conn,
    homework_id: int,
    *,
    student_email: str,
    student_name: str = "",
    student_id: int | None = None,
    student_code: str = "",
) -> dict:
    cur = conn.cursor()
    ensure_practice_tables(cur)
    hw = cur.execute(
        "SELECT id, status, teaching_assignment_id, title FROM practice_homeworks WHERE id=?",
        (homework_id,),
    ).fetchone()
    if not hw:
        raise ValueError("Không tìm thấy bài thực hành")
    if hw[1] not in ("published", "closed"):
        raise ValueError("Bài chưa được mở cho học viên")
    email = (student_email or "").strip().lower()
    if not email:
        raise ValueError("Thiếu email học viên")

    existing = cur.execute(
        "SELECT id FROM practice_submissions WHERE homework_id=? AND lower(student_email)=?",
        (homework_id, email),
    ).fetchone()
    if existing:
        return get_submission(conn, existing[0])

    # resolve class student
    meta = _ta_meta(conn, hw[2])
    st_id = student_id
    st_name = student_name
    st_code = student_code
    if meta:
        row = cur.execute(
            "SELECT id, full_name, student_code FROM class_students "
            "WHERE class_id=? AND lower(IFNULL(email,''))=?",
            (meta["class_id"], email),
        ).fetchone()
        if row:
            st_id = row[0]
            st_name = st_name or row[1]
            st_code = st_code or (row[2] or "")
        else:
            # try login-like match on name
            pass
    if not st_name:
        st_name = email.split("@")[0]

    variant_id = _pick_variant(conn, homework_id, email)
    vcode = cur.execute(
        "SELECT code FROM practice_variants WHERE id=?", (variant_id,)
    ).fetchone()[0]
    # STT among class
    stt = 1
    if meta:
        names = [
            r[0]
            for r in cur.execute(
                "SELECT full_name FROM class_students WHERE class_id=? ORDER BY full_name",
                (meta["class_id"],),
            ).fetchall()
        ]
        if st_name in names:
            stt = names.index(st_name) + 1
    label = f"{stt}_{st_name.replace(' ', '')}_{vcode}"

    cur.execute(
        "INSERT INTO practice_submissions "
        "(homework_id, variant_id, student_id, student_name, student_email, student_code, "
        "display_label, status, started_at) VALUES (?,?,?,?,?,?,?,'in_progress',?)",
        (homework_id, variant_id, st_id, st_name, email, st_code, label, _now()),
    )
    conn.commit()
    return get_submission(conn, cur.lastrowid)


def get_submission(conn, submission_id: int) -> dict:
    cur = conn.cursor()
    ensure_practice_tables(cur)
    r = cur.execute(
        "SELECT s.id, s.homework_id, s.variant_id, s.student_id, s.student_name, s.student_email, "
        "s.student_code, s.display_label, s.status, s.score, s.started_at, s.submitted_at, "
        "s.graded_at, s.grader_note, v.code, h.title, h.instructions, h.status, h.due_at "
        "FROM practice_submissions s "
        "JOIN practice_variants v ON v.id=s.variant_id "
        "JOIN practice_homeworks h ON h.id=s.homework_id "
        "WHERE s.id=?",
        (submission_id,),
    ).fetchone()
    if not r:
        raise ValueError("Không tìm thấy bài làm")
    ctx = cur.execute(
        "SELECT context_text FROM practice_variants WHERE id=?", (r[2],)
    ).fetchone()
    qs = cur.execute(
        "SELECT q.id, q.code, q.title, q.content, q.points, q.sort_order, "
        "IFNULL(a.answer_text,''), a.score "
        "FROM practice_questions q "
        "LEFT JOIN practice_answers a ON a.question_id=q.id AND a.submission_id=? "
        "WHERE q.variant_id=? ORDER BY q.sort_order, q.id",
        (submission_id, r[2]),
    ).fetchall()
    return {
        "id": r[0],
        "homework_id": r[1],
        "variant_id": r[2],
        "student_id": r[3],
        "student_name": r[4],
        "student_email": r[5],
        "student_code": r[6],
        "display_label": r[7],
        "status": r[8],
        "score": r[9],
        "started_at": r[10],
        "submitted_at": r[11],
        "graded_at": r[12],
        "grader_note": r[13],
        "variant_code": r[14],
        "homework_title": r[15],
        "instructions": r[16],
        "homework_status": r[17],
        "due_at": r[18],
        "context_text": (ctx[0] if ctx else "") or "",
        "questions": [
            {
                "id": q[0],
                "code": q[1],
                "title": q[2],
                "content": q[3],
                "points": q[4],
                "sort_order": q[5],
                "answer_text": q[6],
                "answer_score": q[7],
            }
            for q in qs
        ],
    }


def save_answers(
    conn,
    submission_id: int,
    answers: dict[int | str, str],
    *,
    submit: bool = False,
) -> dict:
    cur = conn.cursor()
    ensure_practice_tables(cur)
    sub = cur.execute(
        "SELECT id, status, homework_id FROM practice_submissions WHERE id=?",
        (submission_id,),
    ).fetchone()
    if not sub:
        raise ValueError("Không tìm thấy bài làm")
    if sub[1] == "graded":
        raise ValueError("Bài đã chấm — không sửa được")
    hw_status = cur.execute(
        "SELECT status FROM practice_homeworks WHERE id=?", (sub[2],)
    ).fetchone()
    if hw_status and hw_status[0] == "closed" and submit:
        raise ValueError("Bài đã đóng")

    now = _now()
    for qid, text in (answers or {}).items():
        try:
            qid_i = int(qid)
        except Exception:
            continue
        # ensure question belongs to submission variant
        ok = cur.execute(
            "SELECT q.id FROM practice_questions q "
            "JOIN practice_submissions s ON s.variant_id=q.variant_id "
            "WHERE s.id=? AND q.id=?",
            (submission_id, qid_i),
        ).fetchone()
        if not ok:
            continue
        cur.execute(
            "INSERT INTO practice_answers (submission_id, question_id, answer_text, updated_at) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(submission_id, question_id) DO UPDATE SET "
            "answer_text=excluded.answer_text, updated_at=excluded.updated_at",
            (submission_id, qid_i, (text or "").strip(), now),
        )
    if submit:
        cur.execute(
            "UPDATE practice_submissions SET status='submitted', submitted_at=? WHERE id=?",
            (now, submission_id),
        )
    conn.commit()
    return get_submission(conn, submission_id)


def list_submissions(conn, homework_id: int) -> list[dict]:
    cur = conn.cursor()
    ensure_practice_tables(cur)
    rows = cur.execute(
        "SELECT s.id, s.student_name, s.student_email, s.student_code, s.display_label, "
        "s.status, s.score, s.submitted_at, v.code "
        "FROM practice_submissions s "
        "JOIN practice_variants v ON v.id=s.variant_id "
        "WHERE s.homework_id=? ORDER BY s.student_name",
        (homework_id,),
    ).fetchall()
    return [
        {
            "id": r[0],
            "student_name": r[1],
            "student_email": r[2],
            "student_code": r[3],
            "display_label": r[4],
            "status": r[5],
            "score": r[6],
            "submitted_at": r[7],
            "variant_code": r[8],
        }
        for r in rows
    ]


def grade_submission(
    conn, submission_id: int, *, score: float | None = None, note: str = ""
) -> dict:
    cur = conn.cursor()
    ensure_practice_tables(cur)
    cur.execute(
        "UPDATE practice_submissions SET status='graded', score=?, grader_note=?, graded_at=? "
        "WHERE id=?",
        (score, note or "", _now(), submission_id),
    )
    if cur.rowcount == 0:
        raise ValueError("Không tìm thấy bài làm")
    conn.commit()
    return get_submission(conn, submission_id)


def list_published_for_student(conn, *, student_email: str) -> list[dict]:
    """Homeworks published for classes where student email matches."""
    cur = conn.cursor()
    ensure_practice_tables(cur)
    email = (student_email or "").strip().lower()
    if not email:
        return []
    rows = cur.execute(
        "SELECT h.id, h.title, h.due_at, h.status, cg.name, c.code, c.name, "
        "s.id, s.status, s.display_label, s.score, ta.id "
        "FROM practice_homeworks h "
        "JOIN teaching_assignments ta ON ta.id=h.teaching_assignment_id "
        "JOIN class_groups cg ON cg.id=ta.class_id "
        "JOIN courses c ON c.id=ta.course_id "
        "JOIN class_students cs ON cs.class_id=cg.id AND lower(IFNULL(cs.email,''))=? "
        "LEFT JOIN practice_submissions s ON s.homework_id=h.id AND lower(s.student_email)=? "
        "WHERE h.status IN ('published','closed') "
        "ORDER BY h.due_at DESC, h.id DESC",
        (email, email),
    ).fetchall()
    return [
        {
            "id": r[0],
            "title": r[1],
            "due_at": r[2],
            "status": r[3],
            "class_name": r[4],
            "course_code": r[5],
            "course_name": r[6],
            "submission_id": r[7],
            "submission_status": r[8],
            "display_label": r[9],
            "score": r[10],
            "teaching_assignment_id": r[11],
        }
        for r in rows
    ]


def list_for_lesson_chapter(
    conn,
    *,
    teaching_assignment_id: int,
    lesson_no: int | str | None,
    student_email: str = "",
) -> list[dict]:
    """Published practice HWs whose mã đề/câu maps to this lesson chapter (C{n}-…)."""
    cur = conn.cursor()
    ensure_practice_tables(cur)
    ch = str(lesson_no or "").strip()
    m = re.search(r"(\d+)", ch)
    ch = m.group(1) if m else ""
    if not ch:
        return []
    email = (student_email or "").strip().lower()
    homeworks = cur.execute(
        "SELECT id, title, due_at, status FROM practice_homeworks "
        "WHERE teaching_assignment_id=? AND status IN ('published','closed') "
        "ORDER BY id DESC",
        (teaching_assignment_id,),
    ).fetchall()
    out: list[dict] = []
    for h in homeworks:
        variants = cur.execute(
            "SELECT id, code FROM practice_variants WHERE homework_id=?",
            (h[0],),
        ).fetchall()
        matched_variants = [v for v in variants if practice_chapter_token(v[1]) == ch]
        coded = [v for v in variants if practice_chapter_token(v[1])]
        if matched_variants:
            q_count = cur.execute(
                "SELECT COUNT(*) FROM practice_questions WHERE homework_id=? AND variant_id IN (%s)"
                % ",".join("?" * len(matched_variants)),
                [h[0]] + [v[0] for v in matched_variants],
            ).fetchone()[0]
            variant_codes = [v[1] for v in matched_variants]
        elif not coded:
            # Mã đề không theo C{n}-… → gắn mọi buổi của lớp–môn
            q_count = cur.execute(
                "SELECT COUNT(*) FROM practice_questions WHERE homework_id=?",
                (h[0],),
            ).fetchone()[0]
            variant_codes = [v[1] for v in variants]
        else:
            continue
        if not q_count and not variant_codes:
            continue
        sub = None
        if email:
            sub = cur.execute(
                "SELECT id, status, display_label, score FROM practice_submissions "
                "WHERE homework_id=? AND lower(IFNULL(student_email,''))=?",
                (h[0], email),
            ).fetchone()
        out.append(
            {
                "kind": "practice",
                "id": h[0],
                "title": h[1],
                "due_at": h[2],
                "status": h[3],
                "chapter": ch,
                "chapter_question_count": q_count or len(variant_codes),
                "variant_codes": variant_codes,
                "submission_id": sub[0] if sub else None,
                "submission_status": sub[1] if sub else None,
                "display_label": sub[2] if sub else None,
                "score": sub[3] if sub else None,
            }
        )
    return out


def list_teaching_assignments_with_practice(conn, scopes: list[str] | None) -> list[dict]:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_practice_tables(cur)
    frag, params = _scopes_sql(scopes, "cg.program_code")
    rows = cur.execute(
        "SELECT ta.id, cg.name, cg.program_code, c.code, c.name, "
        "(SELECT COUNT(*) FROM practice_homeworks h WHERE h.teaching_assignment_id=ta.id), "
        "(SELECT COUNT(*) FROM practice_homeworks h WHERE h.teaching_assignment_id=ta.id "
        " AND h.status='published') "
        "FROM teaching_assignments ta "
        "JOIN class_groups cg ON cg.id=ta.class_id "
        "JOIN courses c ON c.id=ta.course_id "
        f"WHERE {frag} ORDER BY cg.name, c.code",
        params,
    ).fetchall()
    return [
        {
            "id": r[0],
            "class_name": r[1],
            "program_code": r[2],
            "course_code": r[3],
            "course_name": r[4],
            "homework_count": r[5],
            "published_count": r[6],
        }
        for r in rows
    ]


def export_template_xlsx_bytes() -> bytes:
    from io import BytesIO

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Thuc_hanh"
    ws.append(["Ma_cau_hoi", "Noi_dung", "Diem", "Loai_cau"])
    sample = [
        ("C5-3-021", "Tên CSDL: MyDataBase\nBảng Customer …", "", "de"),
        ("C5-3-021-1", "Khởi tạo web và dữ liệu\nTạo file CSDL…", 2.0, "practice"),
        ("C5-3-021-2", "Tạo API GET/DELETE…", 2.0, "practice"),
        ("C5-3-022", "Tên CSDL: MyDataBase\nBảng Employee …", "", "de"),
        ("C5-3-022-1", "Khởi tạo web và dữ liệu…", 2.0, "practice"),
    ]
    for row in sample:
        ws.append(list(row))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
