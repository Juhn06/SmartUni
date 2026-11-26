"""
Bài trắc nghiệm theo lớp–môn (teaching_assignments).

Mẫu import Template_MultipleChoice_50.xlsx:
  No | Chapter | Difficulty Level | question | cho1 | cho2 | cho3 | cho4 | Answer | Explain
  Answer = 1..4 (đáp án đúng).
"""
from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any


def chapter_token(value: Any) -> str:
    """Normalize '1' / 'Chapter 1' / 'Chương 5' → '1'."""
    m = re.search(r"(\d+)", str(value or "").strip())
    return m.group(1) if m else ""


def ensure_mc_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS mc_quizzes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "teaching_assignment_id INTEGER NOT NULL, "
        "title TEXT NOT NULL, "
        "instructions TEXT, "
        "due_at TEXT, "
        "status TEXT NOT NULL DEFAULT 'draft', "  # draft | published | closed
        "source_filename TEXT, "
        "show_explain_after INTEGER DEFAULT 1, "
        "created_by TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (teaching_assignment_id) REFERENCES teaching_assignments(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS mc_questions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "quiz_id INTEGER NOT NULL, "
        "q_no INTEGER, "
        "chapter TEXT, "
        "difficulty TEXT, "
        "question TEXT NOT NULL, "
        "choice1 TEXT NOT NULL, "
        "choice2 TEXT NOT NULL, "
        "choice3 TEXT NOT NULL, "
        "choice4 TEXT NOT NULL, "
        "answer INTEGER NOT NULL, "  # 1..4
        "explain_text TEXT, "
        "sort_order INTEGER DEFAULT 0, "
        "FOREIGN KEY (quiz_id) REFERENCES mc_quizzes(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS mc_submissions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "quiz_id INTEGER NOT NULL, "
        "student_id INTEGER, "
        "student_name TEXT NOT NULL, "
        "student_email TEXT, "
        "student_code TEXT, "
        "status TEXT NOT NULL DEFAULT 'in_progress', "  # in_progress | submitted | graded
        "score REAL, "
        "max_score REAL, "
        "correct_count INTEGER, "
        "started_at TEXT, "
        "submitted_at TEXT, "
        "UNIQUE(quiz_id, student_email), "
        "FOREIGN KEY (quiz_id) REFERENCES mc_quizzes(id), "
        "FOREIGN KEY (student_id) REFERENCES class_students(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS mc_answers ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "submission_id INTEGER NOT NULL, "
        "question_id INTEGER NOT NULL, "
        "chosen INTEGER, "  # 1..4 or NULL
        "is_correct INTEGER, "
        "updated_at TEXT, "
        "UNIQUE(submission_id, question_id), "
        "FOREIGN KEY (submission_id) REFERENCES mc_submissions(id), "
        "FOREIGN KEY (question_id) REFERENCES mc_questions(id))"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_mc_quiz_ta ON mc_quizzes(teaching_assignment_id)"
    )


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm_header(v: Any) -> str:
    return str(v or "").strip().lower().replace(" ", "").replace("_", "")


def _parse_answer(val: Any) -> int | None:
    if val is None or val == "":
        return None
    s = str(val).strip().upper()
    if s in ("1", "2", "3", "4"):
        return int(s)
    if s in ("A", "B", "C", "D"):
        return {"A": 1, "B": 2, "C": 3, "D": 4}[s]
    try:
        n = int(float(s))
        if 1 <= n <= 4:
            return n
    except Exception:
        pass
    return None


def parse_mc_xlsx_bytes(raw: bytes) -> list[dict]:
    from openpyxl import load_workbook

    wb = load_workbook(BytesIO(raw), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [_norm_header(c) for c in rows[0]]

    def col(*aliases: str) -> int | None:
        for a in aliases:
            a2 = a.replace(" ", "").replace("_", "")
            if a2 in header:
                return header.index(a2)
        return None

    i_no = col("no", "stt", "number")
    i_ch = col("chapter")
    i_diff = col("difficultylevel", "difficulty", "level")
    i_q = col("question", "cauhoi", "noidung")
    i_c1 = col("cho1", "choice1", "a", "option1")
    i_c2 = col("cho2", "choice2", "b", "option2")
    i_c3 = col("cho3", "choice3", "c", "option3")
    i_c4 = col("cho4", "choice4", "d", "option4")
    i_ans = col("answer", "dapan", "correct")
    i_exp = col("explain", "explanation", "giaithich")

    if i_q is None or i_c1 is None or i_ans is None:
        raise ValueError(
            "File thiếu cột bắt buộc (question, cho1..cho4, Answer). "
            "Dùng mẫu Template_MultipleChoice_50.xlsx"
        )

    out: list[dict] = []
    for r in rows[1:]:
        if not r or all(c is None or str(c).strip() == "" for c in r):
            continue
        q = str(r[i_q] or "").strip()
        if not q:
            continue
        c1 = str(r[i_c1] or "").strip() if i_c1 is not None else ""
        c2 = str(r[i_c2] or "").strip() if i_c2 is not None else ""
        c3 = str(r[i_c3] or "").strip() if i_c3 is not None else ""
        c4 = str(r[i_c4] or "").strip() if i_c4 is not None else ""
        ans = _parse_answer(r[i_ans] if i_ans is not None else None)
        if not c1 or not c2 or not c3 or not c4 or not ans:
            continue
        out.append(
            {
                "q_no": int(r[i_no]) if i_no is not None and r[i_no] not in (None, "") else len(out) + 1,
                "chapter": str(r[i_ch] or "").strip() if i_ch is not None else "",
                "difficulty": str(r[i_diff] or "").strip() if i_diff is not None else "",
                "question": q,
                "choice1": c1,
                "choice2": c2,
                "choice3": c3,
                "choice4": c4,
                "answer": ans,
                "explain_text": str(r[i_exp] or "").strip() if i_exp is not None else "",
                "sort_order": len(out) + 1,
            }
        )
    return out


def _ta_meta(conn, teaching_assignment_id: int) -> dict | None:
    from practice_homework import _ta_meta as practice_ta_meta

    return practice_ta_meta(conn, teaching_assignment_id)


def create_quiz(
    conn,
    teaching_assignment_id: int,
    *,
    title: str,
    instructions: str = "",
    due_at: str = "",
    created_by: str = "",
    questions: list[dict] | None = None,
    source_filename: str = "",
    status: str = "draft",
) -> dict:
    cur = conn.cursor()
    ensure_mc_tables(cur)
    meta = _ta_meta(conn, teaching_assignment_id)
    if not meta:
        raise ValueError("Không tìm thấy phân công giảng dạy (lớp–môn)")
    title = (title or "").strip() or f"Trắc nghiệm — {meta['course_code']}"
    cur.execute(
        "INSERT INTO mc_quizzes "
        "(teaching_assignment_id, title, instructions, due_at, status, source_filename, "
        "created_by, created_at) VALUES (?,?,?,?,?,?,?,?)",
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
    quiz_id = cur.lastrowid
    for q in questions or []:
        cur.execute(
            "INSERT INTO mc_questions "
            "(quiz_id, q_no, chapter, difficulty, question, choice1, choice2, choice3, choice4, "
            "answer, explain_text, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                quiz_id,
                q.get("q_no"),
                q.get("chapter") or "",
                q.get("difficulty") or "",
                q.get("question") or "",
                q.get("choice1") or "",
                q.get("choice2") or "",
                q.get("choice3") or "",
                q.get("choice4") or "",
                int(q.get("answer") or 0),
                q.get("explain_text") or "",
                q.get("sort_order") or 0,
            ),
        )
    conn.commit()
    return get_quiz(conn, quiz_id)


def import_quiz_from_file(
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
    if not (name.endswith(".xlsx") or name.endswith(".xlsm")):
        raise ValueError("Định dạng hỗ trợ: .xlsx (Template_MultipleChoice_50)")
    questions = parse_mc_xlsx_bytes(raw)
    if not questions:
        raise ValueError("Không đọc được câu hỏi từ file mẫu")
    return create_quiz(
        conn,
        teaching_assignment_id,
        title=title or f"Trắc nghiệm — {Path(filename).stem}",
        instructions=(
            "Làm bài trắc nghiệm online. Chọn một đáp án cho mỗi câu rồi nộp bài. "
            "Hệ thống chấm tự động."
        ),
        created_by=created_by,
        questions=questions,
        source_filename=filename,
        status="published" if publish else "draft",
    )


def list_quizzes_for_ta(conn, teaching_assignment_id: int) -> list[dict]:
    cur = conn.cursor()
    ensure_mc_tables(cur)
    rows = cur.execute(
        "SELECT q.id, q.title, q.status, q.due_at, q.source_filename, q.created_at, "
        "(SELECT COUNT(*) FROM mc_questions mq WHERE mq.quiz_id=q.id), "
        "(SELECT COUNT(*) FROM mc_submissions s WHERE s.quiz_id=q.id), "
        "(SELECT COUNT(*) FROM mc_submissions s WHERE s.quiz_id=q.id AND s.status IN ('submitted','graded')) "
        "FROM mc_quizzes q WHERE q.teaching_assignment_id=? ORDER BY q.id DESC",
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
            "question_count": r[6],
            "submission_count": r[7],
            "submitted_count": r[8],
            "teaching_assignment_id": teaching_assignment_id,
        }
        for r in rows
    ]


def get_quiz(
    conn, quiz_id: int, *, include_questions: bool = True, hide_answers: bool = False
) -> dict:
    cur = conn.cursor()
    ensure_mc_tables(cur)
    r = cur.execute(
        "SELECT id, teaching_assignment_id, title, instructions, due_at, status, "
        "source_filename, show_explain_after, created_by, created_at "
        "FROM mc_quizzes WHERE id=?",
        (quiz_id,),
    ).fetchone()
    if not r:
        raise ValueError("Không tìm thấy bài trắc nghiệm")
    meta = _ta_meta(conn, r[1]) or {}
    out = {
        "id": r[0],
        "teaching_assignment_id": r[1],
        "title": r[2],
        "instructions": r[3],
        "due_at": r[4],
        "status": r[5],
        "source_filename": r[6],
        "show_explain_after": bool(r[7]),
        "created_by": r[8],
        "created_at": r[9],
        "meta": meta,
        "questions": [],
    }
    if not include_questions:
        return out
    qs = cur.execute(
        "SELECT id, q_no, chapter, difficulty, question, choice1, choice2, choice3, choice4, "
        "answer, explain_text, sort_order FROM mc_questions WHERE quiz_id=? "
        "ORDER BY sort_order, q_no, id",
        (quiz_id,),
    ).fetchall()
    for q in qs:
        item = {
            "id": q[0],
            "q_no": q[1],
            "chapter": q[2],
            "difficulty": q[3],
            "question": q[4],
            "choice1": q[5],
            "choice2": q[6],
            "choice3": q[7],
            "choice4": q[8],
            "sort_order": q[11],
        }
        if not hide_answers:
            item["answer"] = q[9]
            item["explain_text"] = q[10]
        out["questions"].append(item)
    return out


def set_quiz_status(conn, quiz_id: int, status: str) -> dict:
    if status not in ("draft", "published", "closed"):
        raise ValueError("status không hợp lệ")
    cur = conn.cursor()
    ensure_mc_tables(cur)
    cur.execute("UPDATE mc_quizzes SET status=? WHERE id=?", (status, quiz_id))
    if cur.rowcount == 0:
        raise ValueError("Không tìm thấy bài trắc nghiệm")
    conn.commit()
    return get_quiz(conn, quiz_id, include_questions=False)


def start_or_get_submission(
    conn,
    quiz_id: int,
    *,
    student_email: str,
    student_name: str = "",
    student_id: int | None = None,
    student_code: str = "",
) -> dict:
    cur = conn.cursor()
    ensure_mc_tables(cur)
    quiz = cur.execute(
        "SELECT id, status, teaching_assignment_id, title FROM mc_quizzes WHERE id=?",
        (quiz_id,),
    ).fetchone()
    if not quiz:
        raise ValueError("Không tìm thấy bài trắc nghiệm")
    if quiz[1] not in ("published", "closed"):
        raise ValueError("Bài chưa được mở cho học viên")
    email = (student_email or "").strip().lower()
    if not email:
        raise ValueError("Thiếu email học viên")

    existing = cur.execute(
        "SELECT id FROM mc_submissions WHERE quiz_id=? AND lower(student_email)=?",
        (quiz_id, email),
    ).fetchone()
    if existing:
        return get_submission(conn, existing[0], for_student=True)

    meta = _ta_meta(conn, quiz[2])
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
    if not st_name:
        st_name = email.split("@")[0]

    nq = cur.execute(
        "SELECT COUNT(*) FROM mc_questions WHERE quiz_id=?", (quiz_id,)
    ).fetchone()[0]
    cur.execute(
        "INSERT INTO mc_submissions "
        "(quiz_id, student_id, student_name, student_email, student_code, status, "
        "max_score, started_at) VALUES (?,?,?,?,?,'in_progress',?,?)",
        (quiz_id, st_id, st_name, email, st_code, float(nq), _now()),
    )
    conn.commit()
    return get_submission(conn, cur.lastrowid, for_student=True)


def get_submission(conn, submission_id: int, *, for_student: bool = False) -> dict:
    cur = conn.cursor()
    ensure_mc_tables(cur)
    r = cur.execute(
        "SELECT s.id, s.quiz_id, s.student_id, s.student_name, s.student_email, s.student_code, "
        "s.status, s.score, s.max_score, s.correct_count, s.started_at, s.submitted_at, "
        "q.title, q.instructions, q.status, q.due_at, q.show_explain_after, q.teaching_assignment_id "
        "FROM mc_submissions s JOIN mc_quizzes q ON q.id=s.quiz_id WHERE s.id=?",
        (submission_id,),
    ).fetchone()
    if not r:
        raise ValueError("Không tìm thấy bài làm")
    done = r[6] in ("submitted", "graded")
    show_key = done and (not for_student or bool(r[16]))
    qs = cur.execute(
        "SELECT mq.id, mq.q_no, mq.chapter, mq.difficulty, mq.question, "
        "mq.choice1, mq.choice2, mq.choice3, mq.choice4, mq.answer, mq.explain_text, "
        "a.chosen, a.is_correct "
        "FROM mc_questions mq "
        "LEFT JOIN mc_answers a ON a.question_id=mq.id AND a.submission_id=? "
        "WHERE mq.quiz_id=? ORDER BY mq.sort_order, mq.q_no, mq.id",
        (submission_id, r[1]),
    ).fetchall()
    questions = []
    for q in qs:
        item = {
            "id": q[0],
            "q_no": q[1],
            "chapter": q[2],
            "difficulty": q[3],
            "question": q[4],
            "choice1": q[5],
            "choice2": q[6],
            "choice3": q[7],
            "choice4": q[8],
            "chosen": q[11],
        }
        if show_key:
            item["answer"] = q[9]
            item["explain_text"] = q[10]
            item["is_correct"] = q[12]
        item["chapter_key"] = chapter_token(q[2])
        questions.append(item)
    chapter_order: list[str] = []
    chapter_groups: dict[str, list] = {}
    for item in questions:
        key = item.get("chapter_key") or "_"
        if key not in chapter_groups:
            chapter_groups[key] = []
            chapter_order.append(key)
        chapter_groups[key].append(item)
    chapters = [
        {
            "key": k,
            "label": ("Khác" if k == "_" else f"Chương {k}"),
            "label_en": ("Other" if k == "_" else f"Chapter {k}"),
            "count": len(chapter_groups[k]),
            "answered": sum(
                1 for x in chapter_groups[k] if x.get("chosen") not in (None, "")
            ),
        }
        for k in chapter_order
    ]
    return {
        "id": r[0],
        "quiz_id": r[1],
        "student_id": r[2],
        "student_name": r[3],
        "student_email": r[4],
        "student_code": r[5],
        "status": r[6],
        "score": r[7],
        "max_score": r[8],
        "correct_count": r[9],
        "started_at": r[10],
        "submitted_at": r[11],
        "quiz_title": r[12],
        "instructions": r[13],
        "quiz_status": r[14],
        "due_at": r[15],
        "show_explain_after": bool(r[16]),
        "teaching_assignment_id": r[17],
        "questions": questions,
        "chapters": chapters,
        "questions_by_chapter": [
            {"key": c["key"], "label": c["label"], "label_en": c["label_en"], "questions": chapter_groups[c["key"]]}
            for c in chapters
        ],
    }


def save_answers(
    conn,
    submission_id: int,
    answers: dict[int | str, Any],
    *,
    submit: bool = False,
) -> dict:
    cur = conn.cursor()
    ensure_mc_tables(cur)
    sub = cur.execute(
        "SELECT id, status, quiz_id FROM mc_submissions WHERE id=?",
        (submission_id,),
    ).fetchone()
    if not sub:
        raise ValueError("Không tìm thấy bài làm")
    if sub[1] in ("submitted", "graded"):
        raise ValueError("Bài đã nộp, không sửa được")
    quiz_status = cur.execute(
        "SELECT status FROM mc_quizzes WHERE id=?", (sub[2],)
    ).fetchone()
    if not quiz_status or quiz_status[0] == "closed":
        raise ValueError("Bài đã đóng")
    now = _now()
    for qid, chosen in (answers or {}).items():
        try:
            qid_i = int(qid)
        except Exception:
            continue
        ch = None
        if chosen not in (None, ""):
            ch = _parse_answer(chosen)
        ok = cur.execute(
            "SELECT id FROM mc_questions WHERE id=? AND quiz_id=?",
            (qid_i, sub[2]),
        ).fetchone()
        if not ok:
            continue
        cur.execute(
            "INSERT INTO mc_answers (submission_id, question_id, chosen, updated_at) "
            "VALUES (?,?,?,?) "
            "ON CONFLICT(submission_id, question_id) DO UPDATE SET "
            "chosen=excluded.chosen, updated_at=excluded.updated_at",
            (submission_id, qid_i, ch, now),
        )
    if submit:
        _auto_grade(cur, submission_id, now)
    conn.commit()
    return get_submission(conn, submission_id, for_student=True)


def _auto_grade(cur, submission_id: int, now: str) -> None:
    rows = cur.execute(
        "SELECT mq.id, mq.answer, a.chosen FROM mc_questions mq "
        "JOIN mc_submissions s ON s.quiz_id=mq.quiz_id "
        "LEFT JOIN mc_answers a ON a.question_id=mq.id AND a.submission_id=s.id "
        "WHERE s.id=?",
        (submission_id,),
    ).fetchall()
    correct = 0
    for qid, ans, chosen in rows:
        is_ok = 1 if chosen is not None and int(chosen) == int(ans) else 0
        if is_ok:
            correct += 1
        cur.execute(
            "INSERT INTO mc_answers (submission_id, question_id, chosen, is_correct, updated_at) "
            "VALUES (?,?,?,?,?) "
            "ON CONFLICT(submission_id, question_id) DO UPDATE SET "
            "is_correct=excluded.is_correct, updated_at=excluded.updated_at",
            (submission_id, qid, chosen, is_ok, now),
        )
    total = len(rows)
    cur.execute(
        "UPDATE mc_submissions SET status='graded', score=?, max_score=?, correct_count=?, "
        "submitted_at=? WHERE id=?",
        (float(correct), float(total), correct, now, submission_id),
    )


def list_submissions(conn, quiz_id: int) -> list[dict]:
    cur = conn.cursor()
    ensure_mc_tables(cur)
    rows = cur.execute(
        "SELECT id, student_name, student_email, student_code, status, score, max_score, "
        "correct_count, submitted_at FROM mc_submissions WHERE quiz_id=? "
        "ORDER BY student_name",
        (quiz_id,),
    ).fetchall()
    return [
        {
            "id": r[0],
            "student_name": r[1],
            "student_email": r[2],
            "student_code": r[3],
            "status": r[4],
            "score": r[5],
            "max_score": r[6],
            "correct_count": r[7],
            "submitted_at": r[8],
        }
        for r in rows
    ]


def list_published_for_student(conn, *, student_email: str) -> list[dict]:
    cur = conn.cursor()
    ensure_mc_tables(cur)
    email = (student_email or "").strip().lower()
    if not email:
        return []
    rows = cur.execute(
        "SELECT q.id, q.title, q.due_at, q.status, cg.name, c.code, c.name, "
        "s.id, s.status, s.score, s.max_score, ta.id, "
        "(SELECT COUNT(*) FROM mc_questions mq WHERE mq.quiz_id=q.id) "
        "FROM mc_quizzes q "
        "JOIN teaching_assignments ta ON ta.id=q.teaching_assignment_id "
        "JOIN class_groups cg ON cg.id=ta.class_id "
        "JOIN courses c ON c.id=ta.course_id "
        "JOIN class_students cs ON cs.class_id=cg.id AND lower(IFNULL(cs.email,''))=? "
        "LEFT JOIN mc_submissions s ON s.quiz_id=q.id AND lower(s.student_email)=? "
        "WHERE q.status IN ('published','closed') "
        "ORDER BY q.due_at DESC, q.id DESC",
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
            "score": r[9],
            "max_score": r[10],
            "teaching_assignment_id": r[11],
            "question_count": r[12],
            "kind": "mc",
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
    """Published MC quizzes that have questions for this lesson/chapter number."""
    cur = conn.cursor()
    ensure_mc_tables(cur)
    ch = chapter_token(lesson_no)
    if not ch:
        return []
    email = (student_email or "").strip().lower()
    quizzes = cur.execute(
        "SELECT id, title, due_at, status FROM mc_quizzes "
        "WHERE teaching_assignment_id=? AND status IN ('published','closed') "
        "ORDER BY id DESC",
        (teaching_assignment_id,),
    ).fetchall()
    out: list[dict] = []
    for q in quizzes:
        qs = cur.execute(
            "SELECT id, chapter FROM mc_questions WHERE quiz_id=?",
            (q[0],),
        ).fetchall()
        matched = [row for row in qs if chapter_token(row[1]) == ch]
        if not matched:
            # Không có câu gắn chương này; nếu toàn bộ câu chưa gắn chapter → vẫn hiện
            if any(chapter_token(row[1]) for row in qs):
                continue
            if not qs:
                continue
            matched = qs
        sub = None
        if email:
            sub = cur.execute(
                "SELECT id, status, score, max_score FROM mc_submissions "
                "WHERE quiz_id=? AND lower(student_email)=?",
                (q[0], email),
            ).fetchone()
        out.append(
            {
                "kind": "mc",
                "id": q[0],
                "title": q[1],
                "due_at": q[2],
                "status": q[3],
                "chapter": ch,
                "chapter_question_count": len(matched),
                "question_count": len(qs),
                "submission_id": sub[0] if sub else None,
                "submission_status": sub[1] if sub else None,
                "score": sub[2] if sub else None,
                "max_score": sub[3] if sub else None,
            }
        )
    return out


def enrich_ta_list_with_mc(conn, rows: list[dict]) -> list[dict]:
    """Add mc_quiz_count / mc_published_count onto practice TA list rows."""
    cur = conn.cursor()
    ensure_mc_tables(cur)
    for row in rows:
        ta_id = row.get("id")
        if not ta_id:
            continue
        counts = cur.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM mc_quizzes WHERE teaching_assignment_id=?), "
            "(SELECT COUNT(*) FROM mc_quizzes WHERE teaching_assignment_id=? AND status='published')",
            (ta_id, ta_id),
        ).fetchone()
        row["mc_quiz_count"] = counts[0]
        row["mc_published_count"] = counts[1]
    return rows


def export_template_xlsx_bytes() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "MC"
    ws.append(
        [
            "No",
            "Chapter",
            "Difficulty Level",
            "question",
            "cho1",
            "cho2",
            "cho3",
            "cho4",
            "Answer",
            "Explain",
        ]
    )
    sample = [
        (
            1,
            1,
            1,
            "What is information in IT?",
            "Processed data",
            "Data that is stored",
            "Symbols",
            "Unstructured knowledge",
            1,
            "Processed data",
        ),
        (
            2,
            1,
            1,
            "What is an example of data?",
            "Raw facts",
            "Raw facts",
            "Processed statistics",
            "Conclusions",
            2,
            "Raw facts",
        ),
    ]
    for row in sample:
        ws.append(list(row))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
