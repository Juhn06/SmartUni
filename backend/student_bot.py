"""Student assistant: academic Q&A from the student knowledge base plus the signed-in student's own records."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import admission_bot as ab
import student_bot_lang as sl

SEED_VERSION = "4"
PERSONA = (
    "Bạn là UniBot, trợ lý học vụ cho học viên sau đại học của trung tâm. "
    "Bạn trả lời câu hỏi về quy chế, thủ tục học vụ, luận văn, tốt nghiệp và cách dùng cổng học viên."
)
PREFIX = "Theo tài liệu học vụ hiện có:"
QUICK_REPLIES = [
    "Điểm các môn của tôi",
    "Môn nào tôi có điểm cao nhất?",
    "Tôi còn khoản phí nào chưa đóng?",
    "Lịch thi sắp tới của tôi",
    "Tiến trình học tập của tôi",
    "Xem học liệu ở đâu?",
]

PROGRAM_DEPARTMENTS = {"MBA": "mba", "MMS": "master_chuyen_nganh", "MSCM": "master_chuyen_nganh"}
DEPARTMENT_LABELS = {"mba": "Chương trình MBA", "master_chuyen_nganh": "Chương trình Master Chuyên ngành"}
STAFF_DEPARTMENTS = ("mba", "master_chuyen_nganh")
OVERSIGHT_DEPARTMENTS = ("ban_giam_doc", "tro_ly_bgd", "admin_he_thong")
REQUEST_STATUSES = {"new": "Mới", "in_progress": "Đang xử lý", "answered": "Đã trả lời", "closed": "Đóng"}

PERSONAL_INTENTS = {
    "admission": (
        "ielts", "toeic", "toefl", "chung chi tieng anh", "chung chi", "bang dai hoc", "bang cap", "van bang",
        "bang tot nghiep dai hoc", "nganh dai hoc", "diem thi viet", "diem phong van", "diem dau vao", "diem xet tuyen",
        "diem tuyen sinh", "ket qua xet tuyen", "ho so dau vao", "tot nghiep dai hoc", "truong dai hoc", "dai hoc nganh",
    ),
    "courses": (
        "bao nhieu mon", "may mon", "nhung mon", "mon gi", "mon nao", "cac mon", "mon hoc", "con phai hoc",
        "chua hoc", "dang hoc", "hoc xong", "ky nay", "hoc ky nay", "ky truoc", "ky sau", "ky toi",
        "mien mon", "duoc mien", "cong nhan tin chi", "cac mon",
    ),
    "grades": (
        "diem", "ket qua hoc tap", "ket qua mon", "bang diem", "gpa", "qua mon", "truot mon", "rot mon",
        "may diem", "bao nhieu diem", "cao nhat", "thap nhat", "chuyen can", "truot", "khong dat", "chua dat",
        "hoc lai", "qua het",
    ),
    "fees": (
        "hoc phi", "cong no", "con no", "no phi", "dong phi", "dong tien", "thanh toan", "khoan phi",
        "phi ghi danh", "han dong", "chua dong", "qua han", "tien hoc", "khoan nao", "bao nhieu tien", "dong duoc",
        "dong bao nhieu", "no bao nhieu", "hoc bong", "mien giam", "giam hoc phi", "khoan tiep theo", "phai dong", "can dong",
    ),
    "schedule": (
        "lich thi", "lich hoc", "buoi hoc", "lich phong van", "phong thi", "ngay thi", "khi nao thi",
        "thi luc nao", "thi ngay nao", "sap toi", "len lop", "thi lai", "hom nay", "ngay mai", "tuan nay", "tuan sau",
        "co hoc khong", "co lich hoc", "co buoi hoc", "di hoc",
    ),
    "progress": (
        "tien trinh", "tien do", "trang thai ho so", "giai doan", "lo trinh", "ma hoc vien", "lop cua toi",
        "toi hoc lop", "luan van", "chuyen de", "tot nghiep", "trung tuyen", "nhap hoc", "cuu hoc vien", "alumni",
        "huong dan", "bao ve", "bao luu", "tam nghi", "thoi hoc", "trang thai hoc",
    ),
}
SEMESTER_RE = re.compile(r"(?<![a-z0-9])(?:hoc )?ky\s*(\d{1,2}|nay|hien tai|truoc|sau|toi)(?![a-z0-9])")
SELF_MARKERS = ("toi", "cua toi", "minh", "cua minh", "em", "cua em", "con toi")
POLICY_MARKERS = (
    "quy che", "quy dinh", "cach tinh", "thu tuc", "nhu the nao", "lam sao", "lam the nao", "bao nhieu lan",
    "dieu kien", "o dau", "la gi", "can gi", "can nhung gi", "gom nhung", "muon",
    "muc nao", "vao dau", "tai sao", "vi sao", "sao van", "sao chua", "bao lau",
    "xin nghi", "xin phep", "vang mat", "nghi hoc", "the nao", "cach nao", "bao cho", "thi sao",
)
HUMAN_KEYS = (
    "gap can bo", "gap giao vu", "nguoi ho tro", "chuyen cho can bo", "lien he can bo",
    "noi chuyen voi", "can bo ho tro", "hoi truc tiep", "gap nguoi that",
)
GENERIC_WORDS = set(
    "diem mon hoc ket qua lich thi phi bao nhieu cua toi minh em xem cho hoi khoan ngay nao khi luc dong con chua da "
    "nhat cao thap tot kem the sao vay may tien han ky".split()
)
STAGE_KEYS = {
    "thesis": ("luan van", "chuyen de", "bao ve", "huong dan", "hoi dong"),
    "graduation": ("tot nghiep",),
    "admission_result": ("trung tuyen", "ket qua tuyen sinh"),
    "official": ("nhap hoc", "ma hoc vien"),
    "enrolled": ("xep lop", "lop cua toi", "toi hoc lop"),
    "attendance": ("diem danh",),
    "interview": ("phong van",),
    "written": ("thi viet",),
    "alumni": ("cuu hoc vien", "alumni"),
    "fee": ("phi ghi danh",),
}


def _now() -> str:
    return ab._now()


def _has(folded: str, phrases) -> bool:
    return any(ab._has_phrase(folded, p) for p in phrases)


def ensure_tables(cur) -> None:
    ab.ensure_bot_tables(cur)
    cur.execute(
        "CREATE TABLE IF NOT EXISTS student_bot_messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL, "
        "role TEXT NOT NULL, "
        "content TEXT NOT NULL, "
        "mode TEXT, "
        "sources TEXT, "
        "request_id INTEGER, "
        "author TEXT, "
        "created_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS student_support_requests ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "user_id INTEGER NOT NULL, "
        "full_name TEXT, "
        "student_code TEXT, "
        "program_code TEXT, "
        "class_name TEXT, "
        "department_code TEXT, "
        "question TEXT NOT NULL, "
        "reason TEXT, "
        "status TEXT DEFAULT 'new', "
        "reply TEXT, "
        "handled_by TEXT, "
        "faq_id INTEGER, "
        "created_at TEXT, "
        "updated_at TEXT, "
        "answered_at TEXT)"
    )
    for table, column in (("student_support_requests", "faq_id INTEGER"), ("student_bot_messages", "cleared INTEGER DEFAULT 0")):
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column}")
        except Exception:
            pass
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stu_msg_user ON student_bot_messages(user_id, id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stu_req_dept ON student_support_requests(department_code, status)")


def bootstrap(conn, data_dir) -> dict:
    from app_settings import get_setting, set_setting

    ensure_tables(conn.cursor())
    conn.commit()
    out = {"docs": 0, "faqs": 0}
    seed = Path(data_dir) / "student_kb"
    if not seed.is_dir() or get_setting(conn, "studentkb.seed_version", "") == SEED_VERSION:
        return out
    seed_filter = "created_by = 'seed' AND audience = 'student'"
    for (doc_id,) in conn.execute(f"SELECT id FROM bot_kb_docs WHERE {seed_filter}").fetchall():
        conn.execute("DELETE FROM bot_kb_chunks WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM bot_kb_docs WHERE id = ?", (doc_id,))
    conn.execute(f"DELETE FROM bot_faqs WHERE {seed_filter}")
    conn.commit()
    out["docs"] = len(ab.import_folder(conn, str(seed), created_by="seed", audience="student")["imported"])
    faq_file = seed / "faq.json"
    if faq_file.is_file():
        for item in json.loads(faq_file.read_text(encoding="utf-8")):
            ab.save_faq(conn, {**item, "audience": "student"}, actor="seed")
            out["faqs"] += 1
    set_setting(conn, "studentkb.seed_version", SEED_VERSION)
    return out


def access_for(conn, user_id: int | None) -> dict:
    from seed_org import get_user_access

    if not user_id:
        return {"user_id": None, "depts": [], "is_admin": False, "name": "", "login": ""}
    access = get_user_access(conn, user_id)
    row = conn.execute("SELECT email, name FROM user WHERE id = ?", (user_id,)).fetchone()
    return {
        "user_id": user_id,
        "depts": [d.get("code") for d in (access.get("departments") or []) if d.get("code")],
        "is_admin": bool(access.get("is_admin")),
        "login": row[0] if row else "",
        "name": ((row[1] or row[0]) if row else "").split(" — ")[0],
    }


def can_approve(actor: dict) -> bool:
    return bool(actor.get("is_admin") or set(actor.get("depts") or []) & set(OVERSIGHT_DEPARTMENTS))


DEPARTMENT_PROGRAMS = {"mba": {"MBA"}, "master_chuyen_nganh": {"MMS", "MSCM"}}


def allowed_programs(actor: dict) -> set | None:
    if can_approve(actor):
        return None
    out: set = set()
    for dept in actor.get("depts") or []:
        out |= DEPARTMENT_PROGRAMS.get(dept, set())
    return out


def may_publish(actor: dict, program: str) -> bool:
    allowed = allowed_programs(actor)
    return allowed is None or not program or program.upper() in allowed


def may_change_doc(actor: dict, doc: dict) -> bool:
    allowed = allowed_programs(actor)
    if allowed is None or (doc.get("created_by") or "") == actor.get("login"):
        return True
    program = (doc.get("program_code") or "").upper()
    return bool(program) and program in allowed


def review_fields(actor: dict, data) -> dict:
    return {
        "review_status": "approved" if can_approve(actor) else "pending",
        "effective_from": (data.get("effective_from") or "").strip(),
        "effective_to": (data.get("effective_to") or "").strip(),
    }


def staff_departments(actor: dict) -> list[str] | None:
    if actor.get("is_admin") or set(actor["depts"]) & set(OVERSIGHT_DEPARTMENTS):
        return list(STAFF_DEPARTMENTS)
    own = [d for d in actor["depts"] if d in STAFF_DEPARTMENTS]
    return own or None


SCHOLARSHIP_LABELS = {
    "cfvg": "Học bổng CFVG",
    "partner": "Học bổng đối tác",
    "french_gov": "Học bổng Chính phủ Pháp",
    "partial": "Học bổng một phần học phí",
    "other": "Học bổng khác",
}


def scholarship_label(code: str) -> str:
    code = (code or "").strip()
    if code.lower() in ("", "none", "khong"):
        return ""
    return SCHOLARSHIP_LABELS.get(code.lower(), code)


def student_context(conn, user_id: int) -> dict | None:
    from e2e_pipeline import resolve_student_identity

    ident = resolve_student_identity(conn, user_id=user_id)
    if not ident:
        return None
    app = ident.get("application") or {}
    st = ident.get("student") or {}
    program = (st.get("program_code") or app.get("program_code") or "").upper()
    extra = None
    if st.get("id"):
        try:
            extra = conn.execute(
                "SELECT IFNULL(reserve_note, ''), IFNULL(scholarship_type, '') FROM class_students WHERE id = ?", (st["id"],)
            ).fetchone()
        except Exception:
            extra = None
    return {
        "lifecycle": st.get("lifecycle_status") or "",
        "reserve_note": (extra or ("", ""))[0],
        "scholarship": scholarship_label((extra or ("", ""))[1]),
        "user_id": user_id,
        "application_id": app.get("id"),
        "student_id": st.get("id"),
        "class_id": st.get("class_id"),
        "full_name": st.get("full_name") or app.get("full_name") or "",
        "student_code": st.get("student_code") or app.get("student_code") or "",
        "class_name": st.get("class_name") or "",
        "program_code": program,
        "department_code": PROGRAM_DEPARTMENTS.get(program, "mba"),
    }


def _money(value) -> str:
    try:
        return f"{float(value or 0):,.0f}".replace(",", ".") + " VND"
    except (TypeError, ValueError):
        return str(value)


def _day(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        dt = datetime.fromisoformat(text.replace("T", " ")[:19])
    except ValueError:
        return text
    return dt.strftime("%H:%M %d/%m/%Y") if len(text) > 10 and (dt.hour or dt.minute) else dt.strftime("%d/%m/%Y")


def _score(value) -> str:
    if value is None or value == "":
        return "chưa công bố"
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return str(value)


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _label_tokens(label: str) -> set[str]:
    spaced = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", label or "")
    toks = set(ab.tokens(f"{label} {spaced}"))
    return {t for t in toks if not all(part in GENERIC_WORDS for part in t.split("_"))}


def pick(items: list[dict], text: str, label_fn) -> list[dict]:
    q = set(ab.tokens(text))
    scored = []
    for item in items:
        common = _label_tokens(label_fn(item)) & q
        score = sum(2 if "_" in t else 1 for t in common)
        if score:
            scored.append((score, item))
    if not scored:
        return []
    best = max(s for s, _ in scored)
    return [item for s, item in scored if s == best]


def _named_after(folded: str, word: str, known: set[str]) -> list[str]:
    m = re.search(rf"(?<![a-z0-9]){word}\s+([a-z0-9 ]+)", folded)
    if not m:
        return []
    words = [w for w in ab._words(m.group(1)) if w not in GENERIC_WORDS and w not in {"nay", "do", "kia", "cac", "nhung"}]
    return [w for w in words if w not in known]


def _course_label(c: dict) -> str:
    return f"{c.get('course_code') or ''} {c.get('course_name') or ''}"


def _load_courses(conn, ctx: dict) -> tuple[list[dict], dict]:
    from learner_spine import academic_record, learner_id_for_user

    lid = learner_id_for_user(conn, ctx["user_id"])
    if not lid:
        return [], {}
    doc = academic_record(conn, lid, edition="tracking", mask_unpublished=True)
    return doc.get("courses") or [], doc.get("summary") or {}


def _course_detail(c: dict) -> str:
    head = f"Môn {_course_label(c).strip()}"
    extra = [x for x in (f"học kỳ {c['semester']}" if c.get("semester") else "", (c.get("progress_label") or "").lower()) if x]
    if extra:
        head += f" ({', '.join(extra)})"
    if c.get("final_score") is None and c.get("exam_score") is None and c.get("study_score") is None:
        if c.get("progress") == "recognized":
            return f"{head}: môn này được miễn học, công nhận tín chỉ."
        attendance = f"\n- Chuyên cần: {c['attendance']}" if c.get("attendance") else ""
        if c.get("progress") in CURRENT_PROGRESS + UPCOMING_PROGRESS:
            return f"{head}: môn này chưa có điểm vì bạn {'đang học' if c.get('progress') in CURRENT_PROGRESS else 'chưa học'}.{attendance}"
        return f"{head}: điểm môn này chưa được công bố.{attendance}"
    lines = [
        f"- Điểm quá trình: {_score(c.get('study_score'))}",
        f"- Điểm thi: {_score(c.get('exam_score'))}",
        f"- Điểm tổng kết: {_score(c.get('final_score'))}",
    ]
    if c.get("attendance"):
        lines.append(f"- Chuyên cần: {c['attendance']}")
    return f"{head}:\n" + "\n".join(lines)


ATTENDANCE_KEYS = ("chuyen can", "diem danh", "vang mat", "nghi may buoi", "di hoc day du")


def _grade_text(c: dict) -> str:
    label = (c.get("progress_label") or "").lower()
    if c.get("final_score") is not None:
        return _score(c["final_score"]) + (f" ({label})" if label else "")
    if c.get("progress") == "recognized":
        return "miễn học, được công nhận tín chỉ"
    if c.get("progress") in CURRENT_PROGRESS + UPCOMING_PROGRESS:
        return f"chưa có điểm ({label})" if label else "chưa có điểm"
    return f"chưa công bố ({label})" if label else "chưa công bố"


def not_enrolled_reply(conn, ctx: dict, what: str) -> str | None:
    if ctx.get("class_id"):
        return None
    courses, _summary = _load_courses(conn, ctx)
    names = ", ".join(_course_label(c).strip() for c in courses)
    program = ctx.get("program_code") or ""
    head = f"Bạn chưa được xếp lớp nên chưa có {what}."
    return head + (f" Chương trình {program} gồm {len(courses)} môn: {names}." if courses else "") + (
        " Lớp và lịch học sẽ hiện trong cổng học viên khi bạn được xếp lớp."
    )


def semester_filter(text: str, courses: list[dict]) -> tuple[int | None, str]:
    found = semester_filters(text, courses)
    return found[0] if found else (None, "")


def semester_filters(text: str, courses: list[dict]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for m in SEMESTER_RE.finditer(ab.fold(text)):
        sem, label = _semester_token(m.group(1), courses)
        if sem is not None and sem not in [x[0] for x in out]:
            out.append((sem, label))
    return out


def _semester_token(token: str, courses: list[dict]) -> tuple[int | None, str]:
    if token.isdigit():
        return int(token), f"học kỳ {int(token)}"
    current, _note = _current_semester(courses)
    if current is None:
        return None, ""
    if token == "truoc":
        return current - 1, f"học kỳ trước (học kỳ {current - 1})"
    if token in ("sau", "toi"):
        return current + 1, f"học kỳ sau (học kỳ {current + 1})"
    return current, f"học kỳ này (học kỳ {current})"


def _in_semester(courses: list[dict], sem: int) -> list[dict]:
    return [c for c in courses if str(c.get("semester") or "") == str(sem)]


def personal_courses(conn, ctx: dict, text: str) -> str:
    waiting = not_enrolled_reply(conn, ctx, "môn nào đang học")
    if waiting:
        return waiting
    courses, _summary = _load_courses(conn, ctx)
    if not courses:
        return "Hiện chưa có môn học nào được ghi nhận cho bạn."
    folded = ab.fold(text)
    sem, sem_label = semester_filter(text, courses)
    pool = _in_semester(courses, sem) if sem is not None else courses
    scope = sem_label or "toàn khóa"
    if sem is not None and not pool:
        known = sorted({str(c.get("semester")) for c in courses if c.get("semester")})
        return f"Bạn không có môn nào trong {scope}. Các môn của bạn thuộc học kỳ {', '.join(known)}."
    if _has(folded, ("mien", "cong nhan")):
        exempt = [c for c in pool if c.get("progress") == "recognized"]
        if not exempt:
            return f"Trong {scope}, bạn không được miễn môn nào."
        return f"Bạn được miễn {len(exempt)} môn, đã công nhận tín chỉ:\n" + "\n".join(f"- {_course_label(c).strip()}" for c in exempt)
    groups = (
        ("đã học xong", DONE_PROGRESS, ("hoc xong", "da hoc", "hoan thanh", "xong")),
        ("đang học", CURRENT_PROGRESS, ("dang hoc",)),
        ("chưa học", UPCOMING_PROGRESS, ("chua hoc", "con phai hoc", "con lai", "sap hoc")),
    )
    for label, progress, keys in groups:
        if _has(folded, keys):
            chosen = [c for c in pool if c.get("progress") in progress]
            if not chosen:
                return f"Trong {scope}, bạn không có môn nào {label}." + (
                    f" Tất cả {len(pool)} môn đều đã học xong: {', '.join(_course_label(c).strip() for c in pool)}."
                    if label != "đã học xong" and all(c.get("progress") in DONE_PROGRESS for c in pool) else ""
                )
            return f"Trong {scope}, bạn có {len(chosen)} môn {label}:\n" + "\n".join(f"- {_course_label(c).strip()}" for c in chosen)
    lines = [f"- {_course_label(c).strip()} ({(c.get('progress_label') or '').lower()})" for c in pool]
    head = f"Trong {scope}, bạn có {len(pool)} môn"
    if sem is None:
        by_sem: dict = {}
        for c in pool:
            by_sem.setdefault(c.get("semester") or "?", 0)
            by_sem[c.get("semester") or "?"] += 1
        head += " (" + ", ".join((f"học kỳ {k}: {v} môn" if k != "?" else f"học phần khác: {v} môn") for k, v in sorted(by_sem.items(), key=lambda kv: str(kv[0]))) + ")"
    elif "này" in sem_label and all(c.get("progress") in DONE_PROGRESS for c in courses):
        head = f"Bạn đã học xong tất cả các môn. Học kỳ gần nhất là học kỳ {sem}, có {len(pool)} môn"
    return head + ":\n" + "\n".join(lines)


def _semester_grades(in_sem: list[dict], sem_label: str) -> tuple[str, float | None]:
    values = [_num(c.get("final_score")) for c in in_sem if _num(c.get("final_score")) is not None]
    avg = round(sum(values) / len(values), 2) if values else None
    tail = f"\nĐiểm trung bình các môn đã có điểm trong {sem_label}: {avg:g}." if avg is not None else ""
    return f"Điểm {sem_label} của bạn ({len(in_sem)} môn):\n" + "\n".join(
        f"- {_course_label(c).strip()}: tổng kết {_score(c.get('final_score'))} (quá trình {_score(c.get('study_score'))}, thi {_score(c.get('exam_score'))})"
        if c.get("final_score") is not None else f"- {_course_label(c).strip()}: {_grade_text(c)}"
        for c in in_sem
    ) + tail, avg


def _compare_semesters(courses: list[dict], wanted: list[tuple[int, str]]) -> str:
    blocks, avgs = [], []
    for sem, label in wanted:
        in_sem = _in_semester(courses, sem)
        if not in_sem:
            blocks.append(f"Bạn không có môn nào trong {label}.")
            continue
        block, avg = _semester_grades(in_sem, label)
        blocks.append(block)
        if avg is not None:
            avgs.append((label, avg))
    if len(avgs) == 2:
        (la, a), (lb, b) = avgs
        if a == b:
            blocks.append(f"Điểm trung bình {la} và {lb} bằng nhau ({a:g}).")
        else:
            hi, lo = (avgs[0], avgs[1]) if a > b else (avgs[1], avgs[0])
            blocks.append(f"Điểm trung bình {hi[0]} ({hi[1]:g}) cao hơn {lo[0]} ({lo[1]:g}) {round(hi[1] - lo[1], 2):g} điểm.")
    return "\n\n".join(blocks)


def personal_grades(conn, ctx: dict, text: str) -> str:
    waiting = not_enrolled_reply(conn, ctx, "điểm môn nào")
    if waiting:
        return waiting
    courses, summary = _load_courses(conn, ctx)
    if not courses:
        return "Hiện chưa có điểm môn học nào được ghi nhận cho bạn. Điểm sẽ hiện ở mục Bảng điểm & tiến độ khi giảng viên công bố."
    folded = ab.fold(text)
    if _has(folded, FAIL_KEYS):
        return failed_reply(conn, ctx, courses)
    wanted = semester_filters(text, courses)
    if len(wanted) > 1 and not pick(courses, text, _course_label):
        return _compare_semesters(courses, wanted)
    sem, sem_label = semester_filter(text, courses)
    if sem is not None:
        in_sem = _in_semester(courses, sem)
        if not in_sem:
            return f"Bạn không có môn nào trong {sem_label}."
        if not pick(in_sem, text, _course_label):
            return _semester_grades(in_sem, sem_label)[0]
        courses = in_sem
    scored = [c for c in courses if _num(c.get("final_score")) is not None]
    for words, label, fn in (
        (("cao nhat", "tot nhat", "lon nhat"), "cao nhất", max),
        (("thap nhat", "kem nhat", "nho nhat"), "thấp nhất", min),
    ):
        if scored and _has(folded, words):
            value = fn(_num(c["final_score"]) for c in scored)
            hits = [c for c in scored if _num(c["final_score"]) == value]
            if len(hits) == len(scored) and len(hits) > 1:
                return f"Cả {len(hits)} môn đã có điểm của bạn đều bằng nhau, cùng điểm tổng kết {_score(value)}."
            if len(hits) > 1:
                names = ", ".join(_course_label(c).strip() for c in hits)
                return f"Điểm tổng kết {label} của bạn là {_score(value)}, đồng điểm ở {len(hits)} môn: {names}."
            return f"Điểm tổng kết {label} của bạn là {_score(value)}, ở môn {_course_label(hits[0]).strip()}.\n\n{_course_detail(hits[0])}"
    chosen = pick(courses, text, _course_label)
    if _has(folded, ATTENDANCE_KEYS):
        pool = chosen if chosen and len(chosen) < len(courses) else courses
        lines = [
            f"- {_course_label(c).strip()}: {c['attendance']}" if c.get("attendance")
            else f"- {_course_label(c).strip()}: chưa có dữ liệu điểm danh"
            for c in pool
        ]
        return "Chuyên cần của bạn:\n" + "\n".join(lines) + "\nChi tiết từng buổi xem ở mục Bảng điểm & tiến độ."
    if chosen and len(chosen) < len(courses):
        return "\n\n".join(_course_detail(c) for c in chosen) + "\n\nĐiểm các môn khác xem ở mục Bảng điểm & tiến độ."
    known = set().union(*(_label_tokens(_course_label(c)) for c in courses))
    missing = _named_after(folded, "mon", known)
    if missing and not chosen:
        names = ", ".join(_course_label(c).strip() for c in courses)
        return f"Mình không thấy môn \"{' '.join(missing)}\" trong bảng điểm của bạn. Các môn hiện có: {names}. Bạn hỏi lại đúng tên môn nhé."
    lines = [f"- {_course_label(c).strip()}: {_grade_text(c)}" for c in courses]
    tail = f"\nĐiểm trung bình tích lũy hiện tại: {_score(summary.get('gpa'))}." if summary.get("gpa") is not None else ""
    return (
        f"Điểm tổng kết các môn của bạn ({len(courses)} môn):\n" + "\n".join(lines) + tail
        + "\nMuốn xem điểm quá trình, điểm thi của một môn, bạn hỏi kèm tên môn, ví dụ \"điểm môn "
        + (courses[0].get("course_name") or courses[0].get("course_code") or "") + "\"."
    )


def _fee_line(r: dict) -> str:
    remaining = float(r.get("remaining") or 0)
    parts = [f"phải đóng {_money(r.get('actual_due') if r.get('actual_due') is not None else r.get('amount_due'))}", f"đã đóng {_money(r.get('amount_paid'))}"]
    if float(r.get("amount_adjust") or 0) < 0:
        reduced = -float(r["amount_adjust"])
        pct = round(100 * reduced / float(r["amount_due"])) if float(r.get("amount_due") or 0) else 0
        parts.insert(0, f"học phí gốc {_money(r.get('amount_due'))}, được giảm {_money(reduced)}" + (f" ({pct}%)" if pct else ""))
    if remaining > 0:
        parts.append(f"còn {_money(remaining)}")
    if r.get("due_date"):
        due = f"hạn {_day(r['due_date'])}"
        if remaining > 0 and int(r.get("days_overdue") or 0) > 0:
            due += f", đã quá hạn {r['days_overdue']} ngày"
        elif remaining > 0 and r.get("days_until_due") not in (None, ""):
            due += f", còn {r['days_until_due']} ngày"
        parts.append(due)
    status = "đã đóng đủ" if remaining <= 0 else "chưa đóng đủ"
    return f"- {r.get('title') or 'Khoản phí'} ({status}): " + ", ".join(parts)


def personal_fees(conn, ctx: dict, text: str) -> str:
    from treasury_ops import list_student_charges

    if not ctx.get("application_id"):
        return "Mình chưa tìm thấy hồ sơ phí gắn với tài khoản của bạn. Bạn xem mục Nghĩa vụ phí của tôi hoặc nhắn \"gặp cán bộ\" nhé."
    rows = [r for r in list_student_charges(conn, ["*"]) if int(r.get("application_id") or 0) == int(ctx["application_id"])]
    if not rows:
        return "Hiện chưa có khoản phí nào được ghi nhận cho bạn."
    rows.sort(key=lambda x: str(x.get("due_date") or "9999"))
    folded = ab.fold(text)
    open_rows = [r for r in rows if float(r.get("remaining") or 0) > 0]
    tail = "\nMinh chứng chuyển khoản bạn tải ở mục Nghĩa vụ phí của tôi."
    if ctx.get("scholarship"):
        tail = f"\nBạn đang hưởng {ctx['scholarship'][:1].lower() + ctx['scholarship'][1:]}, số phải đóng ở trên đã trừ phần được giảm." + tail
        if _has(folded, ("hoc bong", "mien giam", "giam hoc phi")):
            reduced = sum(-float(r.get("amount_adjust") or 0) for r in rows if float(r.get("amount_adjust") or 0) < 0)
            return f"Bạn đang hưởng {ctx['scholarship'][:1].lower() + ctx['scholarship'][1:]}, tổng được giảm {_money(reduced)}:\n" + "\n".join(
                _fee_line(r) for r in rows if float(r.get("amount_adjust") or 0) < 0
            )
    elif _has(folded, ("hoc bong", "mien giam", "giam hoc phi")):
        return "Hồ sơ của bạn hiện không có học bổng hay khoản miễn giảm học phí nào."
    chosen = pick(rows, text, lambda r: r.get("title") or "")
    if chosen and len(chosen) < len(rows):
        return "\n".join(_fee_line(r) for r in chosen) + tail
    if _has(folded, ("qua han", "tre han", "tre hen")):
        late = [r for r in open_rows if int(r.get("days_overdue") or 0) > 0]
        if not late:
            return "Bạn không có khoản phí nào quá hạn." + (f" Khoản sắp đến hạn gần nhất: {open_rows[0].get('title')}, hạn {_day(open_rows[0].get('due_date'))}." if open_rows and open_rows[0].get("due_date") else "")
        return "Các khoản đã quá hạn:\n" + "\n".join(_fee_line(r) for r in late) + tail
    total_due = sum(float(r.get("actual_due") or r.get("amount_due") or 0) for r in rows)
    total_paid = sum(float(r.get("amount_paid") or 0) for r in rows)
    total_left = sum(float(r.get("remaining") or 0) for r in rows)
    totals = (
        f"Tổng {len(rows)} khoản phí của bạn: phải đóng {_money(total_due)}, đã đóng {_money(total_paid)}, "
        f"còn {_money(total_left)}."
    )
    if _has(folded, ("tong", "ca khoa", "tat ca", "toan khoa", "het bao nhieu")):
        return f"{totals}\n" + "\n".join(_fee_line(r) for r in rows)
    if _has(folded, ("da dong", "da thanh toan", "da nop", "da tra")):
        paid = [r for r in rows if float(r.get("remaining") or 0) <= 0]
        head = f"Bạn đã đóng tổng cộng {_money(total_paid)}."
        if not paid:
            return f"{head} Chưa có khoản nào được đóng đủ."
        return f"{head} Các khoản đã đóng đủ ({len(paid)}):\n" + "\n".join(_fee_line(r) for r in paid)
    if _has(folded, ("gan nhat", "sap den han", "tiep theo", "khi nao phai dong", "bao gio phai dong", "han dong")) and open_rows:
        nxt = open_rows[0]
        return f"Khoản cần đóng tiếp theo:\n{_fee_line(nxt)}" + (f"\nSau đó còn {len(open_rows) - 1} khoản chưa đóng." if len(open_rows) > 1 else "") + tail
    if not open_rows:
        return f"Bạn đã đóng đủ {len(rows)} khoản phí đã ghi nhận, hiện không còn khoản nào chưa đóng."
    total = sum(float(r.get("remaining") or 0) for r in open_rows)
    paid_count = len(rows) - len(open_rows)
    return (
        f"Bạn còn {len(open_rows)} khoản chưa đóng, tổng {_money(total)}:\n" + "\n".join(_fee_line(r) for r in open_rows)
        + (f"\nĐã đóng đủ {paid_count} khoản khác." if paid_count else "") + tail
    )


def _lessons(conn, class_id) -> list[dict]:
    if not class_id:
        return []
    try:
        rows = conn.execute(
            "SELECT cl.lesson_date, cl.title, c.code, c.name FROM class_lessons cl "
            "JOIN teaching_assignments ta ON ta.id = cl.assignment_id "
            "JOIN courses c ON c.id = ta.course_id "
            "WHERE ta.class_id = ? AND cl.lesson_date IS NOT NULL AND cl.lesson_date != '' "
            "ORDER BY cl.lesson_date",
            (class_id,),
        ).fetchall()
    except Exception:
        return []
    return [{"starts_at": r[0], "title": f"Buổi học {r[2]} {r[3]}: {r[1]}", "room": "", "kind": "lesson"} for r in rows]


def _schedule_line(i: dict, today: str) -> str:
    when = "sắp tới" if str(i.get("starts_at") or "")[:10] >= today else "đã diễn ra"
    room = f", phòng {i['room']}" if i.get("room") else ""
    return f"- {_day(i.get('starts_at'))} ({when}): {i.get('title')}{room}"


SCHEDULE_WINDOWS = {
    "hom nay": (0, 0, "hôm nay"),
    "ngay mai": (1, 1, "ngày mai"),
    "tuan nay": (0, 6, "trong 7 ngày tới"),
    "tuan sau": (7, 13, "tuần sau"),
}
FAIL_KEYS = ("truot", "rot mon", "khong dat", "chua dat", "hoc lai", "qua mon", "qua het")


def failed_reply(conn, ctx: dict, courses: list[dict]) -> str:
    from e2e_pipeline import student_schedule_rows

    failed = [c for c in courses if c.get("progress") == "failed"]
    pending = [c for c in courses if c.get("progress") in CURRENT_PROGRESS + UPCOMING_PROGRESS]
    if not failed:
        return "Bạn không có môn nào chưa đạt." + (f" Còn {len(pending)} môn chưa có điểm." if pending else "")
    today = date.today().isoformat()
    retakes = [
        i for i in student_schedule_rows(conn, user_id=ctx["user_id"])
        if "retake" in str(i.get("title") or "").lower() and str(i.get("starts_at") or "")[:10] >= today
    ]
    lines = []
    for c in failed:
        line = f"- {_course_label(c).strip()}: {_score(c.get('final_score'))}"
        hit = next((i for i in retakes if (c.get("course_code") or "") in str(i.get("title"))), None)
        if hit:
            line += f", thi lại {_day(hit['starts_at'])}" + (f", phòng {hit['room']}" if hit.get("room") else "")
        lines.append(line)
    return f"Bạn có {len(failed)} môn chưa đạt:\n" + "\n".join(lines)


def personal_schedule(conn, ctx: dict, text: str) -> str:
    from e2e_pipeline import student_schedule_rows

    today = date.today().isoformat()
    folded = ab.fold(text)
    items = [i for i in student_schedule_rows(conn, user_id=ctx["user_id"]) + _lessons(conn, ctx.get("class_id")) if i.get("starts_at")]
    kinds = set()
    if _has(folded, ("thi", "lich thi", "phong thi", "ngay thi")):
        kinds.add("exam")
    if _has(folded, ("phong van",)):
        kinds.add("interview")
    if _has(folded, ("lich hoc", "buoi hoc", "len lop", "hoc buoi")):
        kinds.add("lesson")
    pool = [i for i in items if not kinds or i.get("kind") in kinds]
    if _has(folded, ("thi lai",)):
        pool = [i for i in pool if "retake" in str(i.get("title") or "").lower() or "thi lại" in str(i.get("title") or "").lower()]
    label = {"exam": "lịch thi", "interview": "lịch phỏng vấn", "lesson": "lịch học"}
    what = " và ".join(label[k] for k in ("exam", "lesson", "interview") if k in kinds) or "lịch thi, lịch học hay phỏng vấn"
    for key, (lo, hi, when) in SCHEDULE_WINDOWS.items():
        if _has(folded, (key,)):
            start, end = (date.today() + timedelta(days=lo)).isoformat(), (date.today() + timedelta(days=hi)).isoformat()
            inside = sorted((i for i in pool if start <= str(i["starts_at"])[:10] <= end), key=lambda i: str(i["starts_at"]))
            if inside:
                return f"Lịch của bạn {when}:\n" + "\n".join(_schedule_line(i, today) for i in inside)
            later = sorted((i for i in pool if str(i["starts_at"])[:10] > end), key=lambda i: str(i["starts_at"]))
            return f"Bạn không có {what} nào {when}." + (f"\nGần nhất sắp tới:\n{_schedule_line(later[0], today)}" if later else "")
    chosen = pick(pool, text, lambda i: i.get("title") or "")
    if chosen and len(chosen) < len(pool):
        chosen.sort(key=lambda i: str(i.get("starts_at")))
        return "\n".join(_schedule_line(i, today) for i in chosen) + "\nLịch đầy đủ xem ở mục Lịch học / Lịch PV."
    upcoming = sorted((i for i in pool if str(i["starts_at"])[:10] >= today), key=lambda i: str(i["starts_at"]))
    if upcoming:
        return f"{what[0].upper() + what[1:]} sắp tới của bạn:\n" + "\n".join(_schedule_line(i, today) for i in upcoming[:6]) + "\nLịch đầy đủ xem ở mục Lịch học / Lịch PV."
    past = sorted(pool, key=lambda i: str(i["starts_at"]), reverse=True)
    if past:
        return (
            f"Hiện chưa có {what} nào sắp tới. Gần nhất:\n" + "\n".join(_schedule_line(i, today) for i in past[:3])
            + "\nLịch mới sẽ hiện ở mục Lịch học / Lịch PV khi được xếp."
        )
    return f"Hiện chưa có {what} nào được xếp cho bạn."


STATUS_WORDS = {
    "graduated": "đã tốt nghiệp",
    "defended": "đã bảo vệ",
    "official": "chính thức",
    "enrolled": "đang học",
    "studying": "đang học",
    "active": "đang học",
    "paid": "đã đóng",
    "pending": "đang chờ",
    "pass": "đạt",
    "fail": "không đạt",
    "completed": "đã hoàn thành",
    "draft": "đang thực hiện",
    "scheduled": "đã xếp lịch bảo vệ",
    "reserved": "đang bảo lưu",
    "on_leave": "đang tạm nghỉ",
    "withdrawn_program": "đã thôi học",
}
LIFECYCLE_WORDS = {
    "active": "đang học",
    "reserved": "đang bảo lưu",
    "on_leave": "đang tạm nghỉ",
    "withdrawn_program": "đã thôi học",
    "graduated": "đã tốt nghiệp",
}
STAGE_LABELS = {
    "thesis": "luận văn",
    "graduation": "xét tốt nghiệp",
    "official": "nhập học chính thức",
    "enrolled": "xếp lớp",
    "attendance": "điểm danh",
    "alumni": "cựu học viên",
}


def _humanize(detail: str) -> str:
    detail = re.sub(r"\s*·\s*(điểm None|BV)\s*(?=·|$)", "", detail or "")
    detail = re.sub(r"Lifecycle:\s*$", "", detail)
    detail = re.sub(r"Lifecycle:\s*", "Trạng thái: ", detail)
    detail = re.sub(r"\bBV\b", "bảo vệ", detail)
    detail = re.sub(r"\bTT:\s*", "trạng thái ", detail)
    detail = re.sub(r"(\d{4})-(\d{2})-(\d{2})", lambda m: f"{m.group(3)}/{m.group(2)}/{m.group(1)}", detail)
    return re.sub(r"\b(" + "|".join(STATUS_WORDS) + r")\b", lambda m: STATUS_WORDS[m.group(1)], detail).strip(" ·")


def _stage_text(s: dict) -> str:
    status = {"done": "đã xong", "pending": "đang chờ", "n/a": "chưa áp dụng"}.get(s["status"], s["status"])
    detail = _humanize(s.get("detail") or "")
    return f"- {s['title']}: {status}" + (f" ({detail})" if detail else "")


LIFECYCLE_KEYS = ("bao luu", "tam nghi", "thoi hoc", "nghi hoc tam thoi", "trang thai hoc", "con dang hoc", "dang hoc khong")


def lifecycle_text(ctx: dict) -> str:
    life = ctx.get("lifecycle") or ""
    if life not in ("reserved", "on_leave", "withdrawn_program"):
        return ""
    note = f" ({ctx['reserve_note']})" if ctx.get("reserve_note") else ""
    return f"Trạng thái học tập: bạn {LIFECYCLE_WORDS[life]}{note}."


def personal_progress(conn, ctx: dict, text: str) -> str:
    from e2e_pipeline import get_student_timeline

    data = get_student_timeline(conn, user_id=ctx["user_id"])
    if not data.get("ok"):
        return "Mình chưa tìm thấy hồ sơ học tập gắn với tài khoản của bạn."
    stages = data.get("stages") or []
    folded = ab.fold(text)
    status_line = lifecycle_text(ctx)
    if _has(folded, LIFECYCLE_KEYS):
        if status_line:
            return status_line
        if ctx.get("lifecycle") == "graduated":
            return "Bạn đã tốt nghiệp, hồ sơ không có quyết định bảo lưu, tạm nghỉ hay thôi học."
        return "Bạn đang học bình thường, hồ sơ không có quyết định bảo lưu, tạm nghỉ hay thôi học."
    wanted = [code for code, keys in STAGE_KEYS.items() if _has(folded, keys)]
    missing_note = ""
    if wanted:
        picked = [s for s in stages if s["code"] in wanted]
        if picked:
            extra = thesis_info(conn, ctx) if "thesis" in wanted else ""
            return "\n".join(_stage_text(s) for s in picked) + (f"\n{extra}" if extra else "") + "\nToàn bộ lộ trình xem ở mục Kết quả của tôi."
        labels = [STAGE_LABELS[c] for c in wanted if c in STAGE_LABELS]
        if labels:
            missing_note = f"Hồ sơ của bạn chưa có thông tin về {', '.join(labels)}."
    done = [s for s in stages if s["status"] == "done"]
    pending = [s for s in stages if s["status"] == "pending"]
    parts = [missing_note] if missing_note else []
    if ctx.get("student_code") or ctx.get("class_name"):
        parts.append(
            "Bạn là học viên"
            + (f" {ctx['program_code']}" if ctx.get("program_code") else "")
            + (f", mã học viên {ctx['student_code']}" if ctx.get("student_code") else "")
            + (f", lớp {ctx['class_name']}" if ctx.get("class_name") else "")
            + "."
        )
    elif not ctx.get("class_id"):
        parts.append(f"Bạn đã trúng tuyển chương trình {ctx.get('program_code') or ''}, hiện chưa được xếp lớp.")
    if status_line:
        parts.append(status_line)
    if ctx.get("scholarship"):
        parts.append(f"Bạn đang hưởng {ctx['scholarship'][:1].lower() + ctx['scholarship'][1:]}.")
    if pending:
        parts.append(f"Bạn đã hoàn thành {len(done)}/{len(stages)} giai đoạn. Giai đoạn tiếp theo: {pending[0]['title']}.")
        if len(pending) > 1:
            parts.append("Các giai đoạn còn lại: " + ", ".join(s["title"] for s in pending[1:4]) + ".")
    else:
        parts.append(f"Bạn đã hoàn thành tất cả {len(stages)} giai đoạn, từ hồ sơ tuyển sinh đến tốt nghiệp.")
    parts.append("Hỏi riêng từng giai đoạn được, ví dụ \"luận văn của tôi\" hay \"tôi tốt nghiệp chưa\".")
    return " ".join(parts)


ADMISSION_COLUMNS = (
    "english_cert", "english_cert_type", "english_cert_score", "english_cert_no", "english_cert_date", "english_verified",
    "degree_major", "degree_grade", "degree_issuer", "degree_year", "degree_verified",
    "written_score", "interview_score", "avg_score", "final_result", "status",
)
ADMISSION_ENGLISH = ("ielts", "toeic", "toefl", "chung chi", "tieng anh")
ADMISSION_DEGREE = ("bang dai hoc", "bang cap", "van bang", "bang tot nghiep", "nganh dai hoc", "tot nghiep dai hoc")
ADMISSION_SCORES = ("diem thi viet", "diem phong van", "diem dau vao", "diem xet tuyen", "diem tuyen sinh", "ket qua tuyen sinh", "ket qua xet tuyen")
RESULT_WORDS = {"admitted": "trúng tuyển", "passed": "trúng tuyển", "official": "trúng tuyển", "paid": "trúng tuyển", "failed": "không trúng tuyển"}


def admission_info(conn, ctx: dict) -> dict | None:
    if not ctx.get("application_id"):
        return None
    cols = {r[1] for r in conn.execute("PRAGMA table_info(applications)")}
    wanted = [c for c in ADMISSION_COLUMNS if c in cols]
    row = conn.execute(f"SELECT {', '.join(wanted)} FROM applications WHERE id = ?", (ctx["application_id"],)).fetchone()
    return dict(zip(wanted, row)) if row else None


def _verified(value) -> str:
    return ", đã được xác minh" if str(value or "").lower() in ("yes", "1", "true", "verified") else ", chưa xác minh"


def admission_lines(a: dict) -> dict:
    kind = (a.get("english_cert_type") or "").strip()
    score = (a.get("english_cert_score") or "").strip()
    cert = f"{kind} {score}".strip() or (a.get("english_cert") or "").strip()
    if cert:
        english = f"- Chứng chỉ tiếng Anh: {cert}" + (f", cấp ngày {_day(a['english_cert_date'])}" if a.get("english_cert_date") else "")
        english += (f", số {a['english_cert_no']}" if a.get("english_cert_no") else "") + _verified(a.get("english_verified"))
    else:
        english = "- Chứng chỉ tiếng Anh: hồ sơ chưa ghi nhận."
    if a.get("degree_major") or a.get("degree_issuer"):
        degree = "- Bằng đại học: " + ", ".join(x for x in (
            f"ngành {a['degree_major']}" if a.get("degree_major") else "",
            f"xếp loại {a['degree_grade']}" if a.get("degree_grade") else "",
            a.get("degree_issuer") or "",
            f"năm {a['degree_year']}" if a.get("degree_year") else "",
        ) if x) + _verified(a.get("degree_verified"))
    else:
        degree = "- Bằng đại học: hồ sơ chưa ghi nhận."
    result = RESULT_WORDS.get(str(a.get("final_result") or a.get("status") or "").lower(), "")
    scores = (
        f"- Điểm thi viết: {_score(a.get('written_score'))}; điểm phỏng vấn: {_score(a.get('interview_score'))}; "
        f"điểm trung bình xét tuyển: {_score(a.get('avg_score'))}" + (f"; kết quả: {result}" if result else "") + "."
    )
    return {"english": english, "degree": degree, "scores": scores}


def personal_admission(conn, ctx: dict, text: str) -> str:
    a = admission_info(conn, ctx)
    if not a:
        return "Mình chưa tìm thấy hồ sơ tuyển sinh gắn với tài khoản của bạn."
    lines = admission_lines(a)
    folded = ab.fold(text)
    picked = [k for k, keys in (("english", ADMISSION_ENGLISH), ("degree", ADMISSION_DEGREE), ("scores", ADMISSION_SCORES)) if _has(folded, keys)]
    return "Hồ sơ đầu vào của bạn:\n" + "\n".join(lines[k] for k in (picked or ["english", "degree", "scores"]))


PERSONAL_HANDLERS = {
    "admission": personal_admission,
    "courses": personal_courses,
    "grades": personal_grades,
    "fees": personal_fees,
    "schedule": personal_schedule,
    "progress": personal_progress,
}


def detect_personal(text: str) -> list[str]:
    folded = ab.fold(text)
    found = [name for name, keys in PERSONAL_INTENTS.items() if _has(folded, keys)]
    if "admission" in found:
        found = [n for n in found if n not in ("grades", "progress", "schedule", "courses")]
    if "courses" in found and len(found) > 1:
        found.remove("courses")
    if "schedule" in found and "grades" in found and not _has(folded, ("diem thi", "bao nhieu diem", "may diem", "bang diem")):
        found.remove("grades")
    if "progress" in found and len(found) > 1 and not _has(folded, ("tien trinh", "tien do", "luan van", "tot nghiep")):
        found.remove("progress")
    return found


HYPOTHETICAL_MARKERS = ("neu toi", "neu minh", "neu em", "gia su", "trong truong hop", "neu nhu", "lo nhu")


def is_policy_question(text: str) -> bool:
    folded = ab.fold(text)
    if _has(folded, HYPOTHETICAL_MARKERS):
        return True
    has_self = _has(folded, SELF_MARKERS)
    return _has(folded, POLICY_MARKERS) and not has_self


def _last_personal_intents(conn, user_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT mode, sources FROM student_bot_messages WHERE user_id = ? AND role = 'bot' AND COALESCE(cleared, 0) = 0 "
        "ORDER BY id DESC LIMIT 2",
        (user_id,),
    ).fetchall()
    for mode, sources in rows:
        if mode not in ("personal", "smart"):
            continue
        try:
            detail = (json.loads(sources or "[]") or [{}])[0].get("detail") or ""
        except (ValueError, AttributeError):
            detail = ""
        return [d for d in detail.split(",") if d in PERSONAL_HANDLERS]
    return []


FOLLOW_UP_MARKERS = ("con", "the con", "vay con", "con ky", "con mon", "con khoan", "con lai", "how about", "what about")
WORRY_KEYS = (
    "lo qua", "lo lang", "dang lo", "toi lo", "em lo", "minh lo", "so truot", "so rot", "so bi", "so khong",
    "buon qua", "ap luc", "cang thang", "stress", "khong kip", "gap qua", "hoang", "met moi", "that vong", "bi truot",
)
EMPATHY_PREFIX = "Mình hiểu bạn đang lo, mình cùng xem cụ thể nhé."
EMPATHY_SUFFIX = "Nếu cần trao đổi trực tiếp, bạn nhắn \"gặp cán bộ\", mình sẽ chuyển ngay cho cán bộ chương trình hỗ trợ bạn."


def _follow_up(conn, ctx: dict, text: str) -> list[str]:
    previous = _last_personal_intents(conn, ctx["user_id"])
    if not previous or len(ab._words(text)) > 8:
        return []
    if "grades" in previous:
        courses, _summary = _load_courses(conn, ctx)
        if pick(courses, text, _course_label):
            return ["grades"]
    folded = ab.fold(text)
    if _has(folded, FOLLOW_UP_MARKERS) or SEMESTER_RE.search(folded):
        return previous
    return []


def is_worried(text: str) -> bool:
    return _has(ab.fold(text), WORRY_KEYS)


def _days_until(value) -> int | None:
    try:
        return (date.fromisoformat(str(value)[:10]) - date.today()).days
    except ValueError:
        return None


def notices(conn, ctx: dict) -> list[dict]:
    from e2e_pipeline import student_schedule_rows

    out: list[dict] = []
    if ctx.get("application_id"):
        from treasury_ops import list_student_charges

        for r in list_student_charges(conn, ["*"]):
            if int(r.get("application_id") or 0) != int(ctx["application_id"]) or float(r.get("remaining") or 0) <= 0:
                continue
            days = _days_until(r.get("due_date"))
            title = r.get("title") or "Khoản phí"
            if days is not None and days < 0:
                out.append({
                    "level": "urgent", "kind": "fee", "order": days,
                    "text": f"{title} đã quá hạn {-days} ngày, còn {_money(r.get('remaining'))} chưa đóng.",
                    "ask": "Tôi có khoản nào quá hạn không?",
                })
            elif days is not None and days <= 30:
                out.append({
                    "level": "urgent" if days <= 7 else "info", "kind": "fee", "order": days,
                    "text": f"{title} đến hạn {_day(r.get('due_date'))} ({'hôm nay' if days == 0 else f'còn {days} ngày'}), cần đóng {_money(r.get('remaining'))}.",
                    "ask": "Khoản tiếp theo tôi phải đóng là gì?",
                })
    items = student_schedule_rows(conn, user_id=ctx["user_id"]) + _lessons(conn, ctx.get("class_id"))
    for i in items:
        days = _days_until(i.get("starts_at"))
        if days is None or days < 0:
            continue
        when = "hôm nay" if days == 0 else "ngày mai" if days == 1 else f"ngày {_day(i.get('starts_at'))}"
        room = f", phòng {i['room']}" if i.get("room") else ""
        if i.get("kind") == "exam" and days <= 7:
            out.append({
                "level": "urgent" if days <= 2 else "info", "kind": "exam", "order": days,
                "text": f"Bạn có {i.get('title')} {when}{room}.", "ask": "Lịch thi sắp tới của tôi",
            })
        elif i.get("kind") == "interview" and days <= 7:
            out.append({
                "level": "urgent" if days <= 2 else "info", "kind": "interview", "order": days,
                "text": f"Bạn có lịch phỏng vấn {when}{room}.", "ask": "Lịch phỏng vấn của tôi",
            })
        elif i.get("kind") == "lesson" and days <= 1:
            out.append({
                "level": "info", "kind": "lesson", "order": days,
                "text": f"{when.capitalize()} bạn có {i.get('title')}.", "ask": "Lịch học sắp tới của tôi",
            })
    thesis = thesis_row(conn, ctx)
    if thesis and thesis.get("defense_date") and thesis.get("status") != "defended":
        days = _days_until(thesis["defense_date"])
        if days is not None and 0 <= days <= 14:
            when = "hôm nay" if days == 0 else f"ngày {_day(thesis['defense_date'])}"
            out.append({
                "level": "urgent" if days <= 3 else "info", "kind": "thesis", "order": days,
                "text": f"Bạn bảo vệ luận văn {when}.", "ask": "Ngày bảo vệ luận văn của tôi",
            })
    out.sort(key=lambda n: (n["level"] != "urgent", n["order"]))
    return [{k: v for k, v in n.items() if k != "order"} for n in out[:4]]


DONE_PROGRESS = ("completed", "recognized", "done")
CURRENT_PROGRESS = ("studying", "current")
UPCOMING_PROGRESS = ("not_started", "scheduled", "upcoming")
FILLER_WORDS = set(
    "cac nhung cua toi minh em la co khong bao nhieu nao gi the vay oi nhe xem cho hoi duoc may con da chua mon "
    "hien tai bay gio ban oi a nua roi luc ngay lo lang so kip hoang ap cang thang stress buon met moi that vong gap qua dang "
    "thi sao how about what lan".split()
)
INTENT_EXTRA_WORDS = {
    "courses": set("ky hoc nay truoc sau toi xong dang chua phai con lai sap hoan thanh tat ca nhung gi mien cong nhan tin chi".split()),
    "grades": set("cao nhat thap tot kem lon nho thanh phan tong ket hoc tap ky nay truoc sau truot rot dat lai het qua".split()),
    "fees": set("tiep theo gan sap den bao gio khi phai tra nop tong tat ca khoa toan het bong giam mien".split()),
    "schedule": set("thi phong van lich hoc buoi sap toi ngay khi nao luc len lop dien ra lai hom mai tuan sau di truot rot".split()),
    "admission": set(
        "chung chi tieng anh ielts toeic toefl bang dai hoc cap van nganh loai xep diem thi viet phong van dau vao xet "
        "tuyen sinh ket qua ho so bao nhieu nam nao truong xac minh chua so ngay".split()
    ),
    "progress": set(
        "giai doan trang thai ho so tien trinh do lo ma hoc vien lop luan van chuyen de tot nghiep trung tuyen "
        "nhap cuu alumni bao ve xep diem danh hoi dong cham ngoi gom ai nhung ngay luu tam nghi thoi khong dang".split()
    ),
}


def normalize_question(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()[:1000]
    return re.sub(r"(?i)\bk[iì](?=\s|$|[?.,!])", lambda m: "Kỳ" if m.group(0)[0] == "K" else "kỳ", text)


def _entity_words(conn, ctx: dict, intents: list[str]) -> set[str]:
    labels: list[str] = []
    if "grades" in intents or "schedule" in intents:
        courses, _summary = _load_courses(conn, ctx)
        labels += [_course_label(c) for c in courses]
    if "fees" in intents and ctx.get("application_id"):
        from treasury_ops import list_student_charges

        labels += [
            r.get("title") or ""
            for r in list_student_charges(conn, ["*"])
            if int(r.get("application_id") or 0) == int(ctx["application_id"])
        ]
    words: set[str] = set()
    for label in labels:
        spaced = re.sub(r"(?<=[A-Za-z])(?=\d)", " ", label)
        words |= set(ab._words(f"{label} {spaced}"))
    return words


def rule_confident(conn, ctx: dict, intents: list[str], text: str) -> bool:
    explained = set(FILLER_WORDS) | {w for m in SELF_MARKERS for w in m.split()}
    for name in intents:
        explained |= {w for k in PERSONAL_INTENTS[name] for w in k.split()} | INTENT_EXTRA_WORDS[name]
    explained |= _entity_words(conn, ctx, intents)
    leftover = [w for w in ab._words(SEMESTER_RE.sub(" ", ab.fold(text))) if w not in explained]
    return not leftover


def thesis_row(conn, ctx: dict) -> dict | None:
    if not ctx.get("student_id"):
        return None
    try:
        row = conn.execute(
            "SELECT title, tutor, defense_date, defense_time, room, total_grade, status, jury_host, jury_member_1, jury_member_2 "
            "FROM thesis_records WHERE student_id = ? ORDER BY id DESC LIMIT 1",
            (ctx["student_id"],),
        ).fetchone()
    except Exception:
        return None
    if not row:
        return None
    keys = ("title", "tutor", "defense_date", "defense_time", "room", "total_grade", "status", "jury_host", "jury_member_1", "jury_member_2")
    return dict(zip(keys, row))


def format_thesis(t: dict | None) -> str:
    if not t:
        return ""
    parts = [
        f"đề tài \"{t['title']}\"" if t.get("title") else "",
        f"người hướng dẫn: {t['tutor']}" if t.get("tutor") else "người hướng dẫn: chưa phân công",
    ]
    if t.get("status"):
        parts.append(f"trạng thái: {STATUS_WORDS.get(t['status'], t['status'])}")
    if t.get("defense_date"):
        parts.append(f"ngày bảo vệ: {_day(t['defense_date'])}" + (f" lúc {t['defense_time']}" if t.get("defense_time") else ""))
    if t.get("room"):
        parts.append(f"phòng {t['room']}")
    if t.get("total_grade") is not None:
        parts.append(f"điểm {_score(t['total_grade'])}")
    jury = [t.get(k) for k in ("jury_host", "jury_member_1", "jury_member_2") if t.get(k)]
    parts.append("hội đồng: " + (", ".join(jury) if jury else "chưa có thông tin"))
    return "Luận văn: " + "; ".join(p for p in parts if p) + "."


def thesis_info(conn, ctx: dict) -> str:
    return format_thesis(thesis_row(conn, ctx))


NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
FOREIGN_SCRIPT_RE = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
NO_INFO_PHRASES = (
    "khong cung cap thong tin", "khong co thong tin", "chua co thong tin", "khong tim thay thong tin",
    "no information", "not have any information", "don t have information", "do not have information",
    "information is not available", "not provided in",
)


def _numbers(text: str) -> set[str]:
    out = set()
    for raw in NUMBER_RE.findall(text or ""):
        out.add(raw)
        out.add(re.sub(r"[.,]", "", raw))
    return out


def grounded(answer: str, source: str) -> bool:
    allowed = _numbers(source)
    for raw in NUMBER_RE.findall(answer or ""):
        if raw not in allowed and re.sub(r"[.,]", "", raw) not in allowed:
            return False
    return True


def _current_semester(courses: list[dict]) -> tuple[int | None, str]:
    def sems(progress):
        return sorted({int(c["semester"]) for c in courses if c.get("semester") and c.get("progress") in progress})

    current = sems(CURRENT_PROGRESS)
    if current:
        return current[0], "đang học"
    upcoming = sems(UPCOMING_PROGRESS)
    done = sems(DONE_PROGRESS)
    if upcoming and (not done or upcoming[0] > done[-1]):
        return upcoming[0], "sắp học"
    if done:
        return done[-1], "đã học xong toàn bộ, đây là học kỳ gần nhất"
    return None, ""


def sheet_data(conn, ctx: dict) -> dict:
    from e2e_pipeline import get_student_timeline, student_schedule_rows

    courses, summary = _load_courses(conn, ctx)
    fees = []
    if ctx.get("application_id"):
        from treasury_ops import list_student_charges

        fees = [r for r in list_student_charges(conn, ["*"]) if int(r.get("application_id") or 0) == int(ctx["application_id"])]
    schedule = [i for i in student_schedule_rows(conn, user_id=ctx["user_id"]) + _lessons(conn, ctx.get("class_id")) if i.get("starts_at")]
    return {
        "profile": {k: ctx.get(k) for k in ("full_name", "student_code", "program_code", "class_name")},
        "courses": courses,
        "gpa": summary.get("gpa"),
        "fees": fees,
        "schedule": schedule,
        "stages": get_student_timeline(conn, user_id=ctx["user_id"]).get("stages") or [],
        "thesis": thesis_row(conn, ctx),
        "admission": admission_info(conn, ctx),
    }


def format_sheet(data: dict, today: date, sections: set | None = None) -> str:
    def want(name: str) -> bool:
        return sections is None or name in sections

    profile = data.get("profile") or {}
    lines = [
        f"Họ tên: {profile.get('full_name') or ''}; mã học viên: {profile.get('student_code') or 'chưa cấp'}; "
        f"chương trình: {profile.get('program_code') or ''}; lớp: {profile.get('class_name') or 'chưa xếp lớp'}."
    ]
    if data.get("admission"):
        lines.append("HỒ SƠ ĐẦU VÀO:\n" + "\n".join(admission_lines(data["admission"]).values()))
    courses = data.get("courses") or []
    if courses and want("courses"):
        sem, sem_note = _current_semester(courses)
        by_sem: dict = {}
        for c in courses:
            by_sem.setdefault(c.get("semester") or "?", []).append(c)
        counts = "; ".join(f"học kỳ {k}: {len(v)} môn" for k, v in sorted(by_sem.items(), key=lambda kv: str(kv[0])))
        status_counts = {
            label: sum(1 for c in courses if c.get("progress") in group)
            for label, group in (("đã học xong", DONE_PROGRESS), ("đang học", CURRENT_PROGRESS), ("chưa học", UPCOMING_PROGRESS))
        }
        not_done = sum(1 for c in courses if c.get("progress") not in DONE_PROGRESS)
        lines.append(
            f"MÔN HỌC: tổng {len(courses)} môn ({counts}). "
            + ", ".join(f"{k} {v} môn" for k, v in status_counts.items())
            + f"; còn {not_done} môn chưa học xong."
        )
        if sem is not None:
            lines.append(f"Học kỳ hiện tại (\"kỳ này\"): học kỳ {sem} ({sem_note}), có {len(by_sem.get(sem, []))} môn.")
        for c in sorted(courses, key=lambda c: (str(c.get("semester") or ""), c.get("sort_order") or 0)):
            lines.append(
                f"- Học kỳ {c.get('semester') or '?'} | {_course_label(c).strip()} | {c.get('progress_label') or ''} | "
                f"điểm quá trình {_score(c.get('study_score'))} | điểm thi {_score(c.get('exam_score'))} | "
                f"điểm tổng kết {_score(c.get('final_score'))} | chuyên cần {c.get('attendance') or 'chưa có'}"
            )
        if data.get("gpa") is not None:
            lines.append(f"Điểm trung bình tích lũy: {_score(data.get('gpa'))}.")
    elif want("courses"):
        lines.append("MÔN HỌC: chưa có môn nào được ghi nhận.")

    fees = data.get("fees") or []
    if fees and want("fees"):
        due = sum(float(r.get("actual_due") or r.get("amount_due") or 0) for r in fees)
        paid = sum(float(r.get("amount_paid") or 0) for r in fees)
        left = sum(float(r.get("remaining") or 0) for r in fees)
        open_count = sum(1 for r in fees if float(r.get("remaining") or 0) > 0)
        lines.append(
            f"HỌC PHÍ: {len(fees)} khoản, tổng phải đóng {_money(due)}, đã đóng {_money(paid)}, còn {_money(left)}; "
            f"{open_count} khoản chưa đóng đủ."
        )
        for r in sorted(fees, key=lambda x: str(x.get("due_date") or "9999")):
            lines.append(_fee_line(r))

    iso_today = today.isoformat()
    items = data.get("schedule") or []
    if items and want("schedule"):
        upcoming = sum(1 for i in items if str(i["starts_at"])[:10] >= iso_today)
        lines.append(f"LỊCH: {len(items)} mục, {upcoming} mục sắp tới.")
        for i in sorted(items, key=lambda i: str(i["starts_at"]))[-12:]:
            lines.append(_schedule_line(i, iso_today))

    stages = data.get("stages") or []
    if stages and want("progress"):
        done = sum(1 for s in stages if s["status"] == "done")
        lines.append(f"TIẾN TRÌNH: đã xong {done}/{len(stages)} giai đoạn.")
        lines += [_stage_text(s) for s in stages]
    thesis = format_thesis(data.get("thesis"))
    if thesis and want("progress"):
        lines.append(thesis)
    return "\n".join(lines)


def student_sheet(conn, ctx: dict, sections: set | None = None) -> str:
    return format_sheet(sheet_data(conn, ctx), date.today(), sections)


def build_messages(sheet: str, docs: str, question: str, today: date, history: list[dict] | None = None) -> list[dict]:
    messages = [{"role": "system", "content": f"{PERSONA}\n{SHEET_RULES}"}]
    messages += history or []
    messages.append({
        "role": "user",
        "content": f"HỒ SƠ HỌC VIÊN (hôm nay {today:%d/%m/%Y}):\n{sheet}\n\nTÀI LIỆU:\n{docs}\n\nCÂU HỎI: {question}",
    })
    return messages


def format_docs(hits: list[dict]) -> str:
    return "\n\n".join(
        f"- {(h.get('question') or h['title']) if h['kind'] == 'faq' else h['title']}: {h['text'][:600]}" for h in hits
    ) or "(không có)"


SHEET_RULES = (
    "Quy tắc bắt buộc:\n"
    "1. Câu hỏi về bản thân học viên (môn học, học kỳ, điểm, học phí, lịch, tiến trình) chỉ trả lời từ HỒ SƠ HỌC VIÊN.\n"
    "2. Câu hỏi về quy chế, thủ tục, cách dùng cổng học viên chỉ trả lời từ TÀI LIỆU.\n"
    "3. Con số, ngày tháng, tên môn phải chép đúng. Dùng các con số đã đếm sẵn trong hồ sơ, không tự cộng trừ hay đếm lại.\n"
    f"4. Nếu hồ sơ và tài liệu đều không có thông tin để trả lời, chỉ trả về đúng chuỗi {ab.NO_INFO_MARK}.\n"
    "5. Trả lời đúng trọng tâm câu hỏi, không liệt kê thừa thông tin không được hỏi. Ngắn gọn, tối đa khoảng 100 từ.\n"
    "6. Không suy luận điều hồ sơ không ghi rõ. Khoản phí nào đã đóng hay chưa phải đọc đúng dòng của khoản đó.\n"
    "7. Trả lời bằng ngôn ngữ của câu hỏi (tiếng Việt thì xưng 'bạn', tiếng Anh thì trả lời tiếng Anh). "
    "Không nhắc tới chữ HỒ SƠ HỌC VIÊN hay TÀI LIỆU, không ghi ký hiệu nguồn.\n"
)
COURSE_CODE_RE = re.compile(r"\b[A-Z]{2,6}\d{2,4}\b")


def mentions_unknown_course(answer: str, sheet: str) -> bool:
    known = {c.upper() for c in COURSE_CODE_RE.findall(sheet)}
    return any(code.upper() not in known for code in COURSE_CODE_RE.findall(answer))


_ANSWER_CACHE: dict[str, str] = {}
_ANSWER_CACHE_LIMIT = 300


def student_model() -> str:
    import os

    return os.environ.get("STUDENT_CHAT_MODEL") or os.environ.get("CHAT_MODEL", "qwen3:8b")


def sheet_answer(conn, ctx: dict, text: str, intents: list[str] | None = None, probe: str | None = None, lang: str = "vi") -> dict | None:
    import hashlib

    if not ab.llm_status(conn)["enabled"]:
        return None
    intents = intents or []
    probe = probe or text
    policy = is_policy_question(probe)
    personal_only = bool(intents) and not policy
    policy_only = policy and not intents and not _has(ab.fold(probe), SELF_MARKERS)
    try:
        from rag_service import _get_client

        hits = [] if personal_only else ab.retrieve(conn, probe, program=ctx.get("program_code") or "", k=3, audience="student")
        sheet = student_sheet(conn, ctx, set() if policy_only else None)
        messages = build_messages(sheet, format_docs(hits), text, date.today())
        prompt = messages[-1]["content"]
        model = student_model()
        key = hashlib.sha256(json.dumps([model, messages], ensure_ascii=False).encode("utf-8")).hexdigest()
        content = _ANSWER_CACHE.get(key)
        if content is None:
            resp = _get_client().chat.completions.create(model=model, messages=messages, temperature=0, max_tokens=350)
            content = resp.choices[0].message.content or ""
            if len(_ANSWER_CACHE) >= _ANSWER_CACHE_LIMIT:
                _ANSWER_CACHE.pop(next(iter(_ANSWER_CACHE)))
            _ANSWER_CACHE[key] = content
    except Exception as e:
        print(f"[STUDENT BOT] LLM error: {e}")
        return None
    answer = ab.NO_INFO_RE.sub("", ab.THINK_RE.sub("", content)).strip()
    answer = re.sub(r"\s*\[\d+\]", "", answer).strip().strip("[]").strip()
    if len(ab._words(answer)) < 3 or FOREIGN_SCRIPT_RE.search(answer) or _has(ab.fold(answer), NO_INFO_PHRASES):
        return {"answered": False, "reason": "no_info"}
    if not grounded(answer, prompt) or mentions_unknown_course(answer, sheet):
        print(f"[STUDENT BOT] rejected ungrounded answer: {answer[:160]}")
        return {"answered": False, "reason": "ungrounded"}
    return {"answered": True, "text": answer, "used": hits}


def strong_faq(conn, text: str, threshold: float = 0.6) -> dict | None:
    index = ab.get_index(conn, "student")
    scored = [(ab._faq_match(ab._faq_text(u), text, index.idf), u) for u in index.units if u["kind"] == "faq"]
    if scored:
        score, best = max(scored, key=lambda s: s[0])
        if score >= threshold:
            return {"answered": True, "text": best["text"], "used": [best], "mode": "faq"}
    return None


def _add_message(conn, user_id: int, role: str, content: str, **extra) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO student_bot_messages (user_id, role, content, mode, sources, request_id, author, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            user_id,
            role,
            content,
            extra.get("mode"),
            json.dumps(extra.get("sources") or [], ensure_ascii=False),
            extra.get("request_id"),
            extra.get("author"),
            _now(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def _message_row(r) -> dict:
    out = dict(r)
    try:
        out["sources"] = json.loads(out.get("sources") or "[]")
    except ValueError:
        out["sources"] = []
    return out


def messages(conn, user_id: int, after_id: int = 0, limit: int = 60) -> list[dict]:
    rows = conn.execute(
        "SELECT id, role, content, mode, sources, request_id, author, created_at FROM student_bot_messages "
        "WHERE user_id = ? AND id > ? AND COALESCE(cleared, 0) = 0 ORDER BY id DESC LIMIT ?",
        (user_id, after_id, limit),
    ).fetchall()
    return [_message_row(r) for r in reversed(rows)]


def reset_conversation(conn, user_id: int) -> dict:
    cur = conn.execute("UPDATE student_bot_messages SET cleared = 1 WHERE user_id = ? AND COALESCE(cleared, 0) = 0", (user_id,))
    conn.commit()
    return {"ok": True, "cleared": cur.rowcount}


def create_request(conn, ctx: dict, question: str, reason: str) -> dict:
    now = _now()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO student_support_requests (user_id, full_name, student_code, program_code, class_name, department_code, "
        "question, reason, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            ctx["user_id"],
            ctx.get("full_name"),
            ctx.get("student_code"),
            ctx.get("program_code"),
            ctx.get("class_name"),
            ctx["department_code"],
            question[:1000],
            reason,
            "new",
            now,
            now,
        ),
    )
    conn.commit()
    return {"id": cur.lastrowid, "department": DEPARTMENT_LABELS.get(ctx["department_code"], ctx["department_code"])}


def state(conn, user_id: int, lang: str = "vi") -> dict:
    ctx = student_context(conn, user_id)
    first = ((ctx or {}).get("full_name") or "").split(" ")[-1]
    items = notices(conn, ctx) if ctx else []
    if lang == "en":
        greeting = (
            f"Hi {first or 'there'}! I'm UniBot, your academic assistant. You can ask about your course grades, fees, exams, "
            "study progress, or academic rules and procedures, in English or Vietnamese. If I can't answer something, "
            "I'll forward it to program staff, who will reply right here in this chat."
        )
        quick = [sl.VI_FIXED.get(q, q) for q in QUICK_REPLIES]
        items = [dict(n, text=sl.to_english(n["text"]), ask=sl.VI_FIXED.get(n["ask"], n["ask"])) for n in items]
    else:
        greeting = (
            f"Chào {first or 'bạn'}! Mình là UniBot, trợ lý học vụ. Bạn có thể hỏi về điểm từng môn, học phí, lịch thi, "
            "tiến trình học tập của bạn, hoặc quy chế và thủ tục học vụ, bằng tiếng Việt hoặc tiếng Anh. "
            "Câu nào mình chưa trả lời được, mình sẽ chuyển cho cán bộ chương trình và cán bộ sẽ trả lời ngay trong khung chat này."
        )
        quick = QUICK_REPLIES
    return {
        "name": "UniBot",
        "greeting": greeting,
        "quick_replies": quick,
        "student": ctx,
        "notices": items,
        "messages": messages(conn, user_id),
    }


def question_lang(text: str, ui_lang: str = "vi") -> str:
    return sl.detect_lang(text) or (ui_lang if ui_lang in sl.LANGS else "vi")


def routing_text(text: str, lang: str) -> str:
    return sl.to_vi_query(text) if lang == "en" else text


def _personal_reply(conn, ctx: dict, intents: list[str], text: str) -> tuple[str, list[dict]]:
    reply = "\n\n".join(PERSONAL_HANDLERS[name](conn, ctx, text) for name in intents[:2])
    return reply, [{"kind": "personal", "title": "Dữ liệu học tập của bạn", "detail": ",".join(intents[:2])}]


def course_mentioned(conn, ctx: dict, text: str) -> bool:
    courses, _summary = _load_courses(conn, ctx)
    chosen = pick(courses, text, _course_label)
    return bool(chosen) and len(chosen) < len(courses)


def route(conn, ctx: dict, text: str, lang: str = "vi") -> dict:
    probe = routing_text(text, lang)
    folded = ab.fold(probe).strip(" !.?")
    intents = detect_personal(probe)
    if not intents and course_mentioned(conn, ctx, probe):
        intents = ["grades"]
    follow = [] if intents else _follow_up(conn, ctx, probe)
    personal = intents or follow
    policy = is_policy_question(probe) and not follow
    has_self = _has(ab.fold(probe), SELF_MARKERS)

    if folded in ab.GREETING_WORDS:
        return {"mode": "greeting", "text": "Chào bạn! Bạn cần hỏi gì về học tập, học phí, lịch thi hay thủ tục học vụ?"}
    if any(ab._has_phrase(folded, t) for t in ab.THANKS_WORDS) and len(folded) <= 40:
        return {"mode": "smalltalk", "text": "Rất vui được hỗ trợ bạn! Cần gì cứ nhắn mình nhé."}
    if _has(folded, HUMAN_KEYS):
        return {"mode": "handoff", "reason": "human"}
    if personal and not policy and rule_confident(conn, ctx, personal, probe):
        reply, sources = _personal_reply(conn, ctx, personal, probe)
        return {"mode": "personal", "text": reply, "sources": sources}

    faq = strong_faq(conn, probe, 0.85 if (personal or has_self) else 0.6)
    if faq:
        return {"mode": "faq", "text": faq["text"], "used": faq["used"]}
    smart = sheet_answer(conn, ctx, text, personal, probe, lang)
    if smart and smart.get("answered"):
        return {"mode": "smart", "text": smart["text"], "used": [], "detail": ",".join(personal)}
    if smart and smart.get("reason") == "no_info":
        return {"mode": "fallback", "reason": "unanswered"}
    if personal:
        reply, sources = _personal_reply(conn, ctx, personal, probe)
        return {"mode": "personal", "text": reply, "sources": sources}
    if smart is None:
        result = ab.generate_reply(
            conn, probe, program=ctx.get("program_code") or "", history=[], audience="student", persona=PERSONA, prefix=PREFIX,
        )
        if result.get("answered"):
            return {"mode": result["mode"], "text": result["text"], "used": result.get("used")}
    return {"mode": "fallback", "reason": "unanswered"}


def localize_reply(reply: str, lang: str, mode: str) -> str:
    return sl.localize(reply, lang, student_model())


def compose_reply(ctx: dict, text: str, decision: dict, lang: str) -> str:
    department = DEPARTMENT_LABELS.get(ctx["department_code"], "bộ phận chương trình")
    mode = decision["mode"]
    reply = decision.get("text") or ""
    if mode == "handoff":
        reply = f"Mình đã chuyển yêu cầu của bạn tới {department}. Cán bộ sẽ trả lời ngay trong khung chat này."
    elif mode == "fallback":
        reply = (
            "Câu này mình chưa có trong hồ sơ của bạn và tài liệu học vụ nên không trả lời để tránh sai. "
            f"Mình đã chuyển câu hỏi tới {department}, cán bộ sẽ trả lời ngay trong khung chat này."
        )
    if is_worried(routing_text(text, lang)) and mode not in ("handoff", "greeting", "smalltalk"):
        reply = f"{EMPATHY_PREFIX}\n\n{reply}"
        if mode != "fallback":
            reply = f"{reply}\n\n{EMPATHY_SUFFIX}"
    return localize_reply(reply, lang, mode)


def handle_chat(conn, user_id: int, text: str, ui_lang: str = "vi") -> dict:
    text = normalize_question(text)
    if not text:
        raise ValueError("Tin nhắn trống.")
    ctx = student_context(conn, user_id)
    if not ctx:
        raise PermissionError("Tài khoản chưa gắn với hồ sơ học viên.")
    lang = question_lang(text, ui_lang)
    decision = route(conn, ctx, text, lang)
    _add_message(conn, user_id, "user", text)
    mode, request = decision["mode"], None
    sources = decision.get("sources") or ab._dedupe_sources(decision.get("used") or [])
    if mode == "smart":
        sources = [{"kind": "personal", "title": "Hồ sơ và tài liệu học vụ", "detail": decision.get("detail") or ""}]
    for unit in decision.get("used") or []:
        if unit["kind"] == "faq":
            conn.execute("UPDATE bot_faqs SET hits = hits + 1 WHERE id = ?", (unit["ref_id"],))
    conn.commit()
    if mode == "handoff":
        request = create_request(conn, ctx, text, "human")
    elif mode == "fallback":
        request = create_request(conn, ctx, text, "unanswered")
    reply = compose_reply(ctx, text, decision, lang)

    bot_id = _add_message(conn, user_id, "bot", reply, mode=mode, sources=sources, request_id=(request or {}).get("id"))
    return {
        "message": _message_row(conn.execute("SELECT * FROM student_bot_messages WHERE id = ?", (bot_id,)).fetchone()),
        "request": request,
    }


def list_requests(conn, departments: list[str], *, status: str = "", q: str = "") -> list[dict]:
    marks = ",".join("?" for _ in departments)
    sql = f"SELECT * FROM student_support_requests WHERE department_code IN ({marks})"
    params: list = list(departments)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if q:
        sql += " AND (full_name LIKE ? OR student_code LIKE ? OR question LIKE ?)"
        params += [f"%{q}%"] * 3
    sql += " ORDER BY CASE status WHEN 'new' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END, id DESC LIMIT 300"
    out = []
    for r in conn.execute(sql, params).fetchall():
        item = dict(r)
        item["status_label"] = REQUEST_STATUSES.get(item["status"], item["status"])
        item["department_label"] = DEPARTMENT_LABELS.get(item["department_code"], item["department_code"])
        out.append(item)
    return out


def request_detail(conn, req_id: int, departments: list[str]) -> dict | None:
    row = conn.execute("SELECT * FROM student_support_requests WHERE id = ?", (req_id,)).fetchone()
    if not row or row["department_code"] not in departments:
        return None
    item = dict(row)
    item["status_label"] = REQUEST_STATUSES.get(item["status"], item["status"])
    item["department_label"] = DEPARTMENT_LABELS.get(item["department_code"], item["department_code"])
    since = (datetime.fromisoformat(item["created_at"]) - timedelta(hours=6)).isoformat(sep=" ", timespec="seconds")
    item["conversation"] = [
        _message_row(r)
        for r in conn.execute(
            "SELECT id, role, content, mode, sources, request_id, author, created_at FROM student_bot_messages "
            "WHERE user_id = ? AND created_at >= ? ORDER BY id LIMIT 80",
            (item["user_id"], since),
        ).fetchall()
    ]
    return item


def update_request(conn, req_id: int, data: dict, departments: list[str], actor: dict) -> dict:
    item = request_detail(conn, req_id, departments)
    if not item:
        raise LookupError("Không tìm thấy yêu cầu.")
    reply = re.sub(r"[ \t]+", " ", (data.get("reply") or "")).strip()[:2000]
    status = data.get("status") if data.get("status") in REQUEST_STATUSES else ""
    if not reply and not status:
        raise ValueError("Nhập câu trả lời hoặc chọn trạng thái.")
    now = _now()
    fields = {"updated_at": now, "handled_by": actor.get("name") or actor.get("login")}
    if reply:
        _add_message(conn, item["user_id"], "staff", reply, mode="staff", request_id=req_id, author=fields["handled_by"])
        fields.update({"reply": reply, "answered_at": now, "status": status or "answered"})
        if data.get("save_faq"):
            faq = ab.save_faq(
                conn,
                {
                    "question": (data.get("faq_question") or item["question"]).strip(),
                    "answer": reply,
                    "program_code": item.get("program_code") if data.get("program_only") else "",
                    "audience": "student",
                    "review_status": "approved" if can_approve(actor) else "pending",
                },
                actor=actor.get("login") or "",
            )
            fields["faq_id"] = faq["id"]
    elif status:
        fields["status"] = status
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE student_support_requests SET {sets} WHERE id = ?", [*fields.values(), req_id])
    conn.commit()
    return request_detail(conn, req_id, departments)


HEADING_QUESTION_TEMPLATES = ("{h}?", "{h} như thế nào?", "Cho mình hỏi về {l}")


def suggest_faqs(conn, departments: list[str]) -> list[dict]:
    existing = {ab.fold(r[0]).strip(" ?") for r in conn.execute("SELECT question FROM bot_faqs WHERE audience = 'student'").fetchall()}
    out: list[dict] = []
    marks = ",".join("?" for _ in departments)
    for r in conn.execute(
        f"SELECT id, question, reply, program_code FROM student_support_requests WHERE department_code IN ({marks}) "
        "AND reply IS NOT NULL AND reply != '' AND faq_id IS NULL ORDER BY id DESC LIMIT 50",
        departments,
    ).fetchall():
        if ab.fold(r[1]).strip(" ?") in existing:
            continue
        out.append({"source": "Cán bộ đã trả lời học viên", "question": r[1], "answer": r[2], "variants": [], "request_id": r[0]})
    for doc in conn.execute("SELECT id, title, content FROM bot_kb_docs WHERE audience = 'student' AND status = 'active'").fetchall():
        sections = re.split(r"(?m)^#{2,6}\s+(.+)$", doc[2] or "")
        for i in range(1, len(sections) - 1, 2):
            heading = sections[i].strip()
            body = re.sub(r"\s+", " ", sections[i + 1]).strip()
            if len(body) < 30 or ab.fold(heading).strip(" ?") in existing:
                continue
            variants = [t.format(h=heading, l=heading[0].lower() + heading[1:]) for t in HEADING_QUESTION_TEMPLATES[1:]]
            out.append({
                "source": f"Tài liệu: {doc[1]}",
                "question": f"{heading}?",
                "answer": body[:700],
                "variants": variants,
                "request_id": None,
            })
    return out


def warm_up() -> None:
    import os

    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_BASE_URL")):
        return
    try:
        from rag_service import _embed_chunks, _get_client

        _get_client().chat.completions.create(model=student_model(), messages=[{"role": "user", "content": "ok"}], max_tokens=1)
        _embed_chunks(["khởi động"])
        print(f"[STUDENT BOT] đã nạp sẵn mô hình {student_model()}")
    except Exception as e:
        print(f"[STUDENT BOT] warm-up failed: {e}")


def register_routes(app, get_db, uploads_dir: Path) -> None:
    import threading

    from flask import jsonify, request

    threading.Thread(target=warm_up, daemon=True).start()

    def err(message, status=400):
        return jsonify({"error": message}), status

    def current(conn):
        try:
            uid = int(request.headers.get("X-User-Id") or 0)
        except ValueError:
            uid = 0
        return access_for(conn, uid or None)

    def student(conn):
        actor = current(conn)
        if not actor["user_id"]:
            return None, err("Bạn cần đăng nhập.", 401)
        if "hoc_vien" not in actor["depts"]:
            return None, err("Trợ lý học vụ chỉ dành cho tài khoản học viên.", 403)
        return actor, None

    def staff(conn):
        actor = current(conn)
        if not actor["user_id"]:
            return None, None, err("Bạn cần đăng nhập.", 401)
        departments = staff_departments(actor)
        if not departments:
            return None, None, err("Chỉ bộ phận chương trình được xử lý yêu cầu học viên.", 403)
        return actor, departments, None

    @app.route("/student/bot/state", methods=["GET"])
    def student_bot_state():
        with get_db() as conn:
            ensure_tables(conn.cursor())
            actor, problem = student(conn)
            if problem:
                return problem
            return jsonify(state(conn, actor["user_id"], (request.args.get("lang") or "vi")[:2]))

    @app.route("/student/bot/messages", methods=["GET"])
    def student_bot_messages():
        with get_db() as conn:
            actor, problem = student(conn)
            if problem:
                return problem
            return jsonify({"messages": messages(conn, actor["user_id"], request.args.get("after", 0, type=int))})

    @app.route("/student/bot/reset", methods=["POST"])
    def student_bot_reset():
        with get_db() as conn:
            ensure_tables(conn.cursor())
            actor, problem = student(conn)
            if problem:
                return problem
            return jsonify(reset_conversation(conn, actor["user_id"]))

    @app.route("/student/bot/chat", methods=["POST"])
    def student_bot_chat():
        with get_db() as conn:
            ensure_tables(conn.cursor())
            actor, problem = student(conn)
            if problem:
                return problem
            if ab.rate_limited(f"student:{actor['user_id']}", limit=20):
                return err("Bạn gửi hơi nhanh, đợi một chút rồi hỏi tiếp nhé.", 429)
            try:
                body = request.get_json(silent=True) or {}
                return jsonify(handle_chat(conn, actor["user_id"], body.get("text", ""), str(body.get("lang") or "vi")[:2]))
            except PermissionError as e:
                return err(str(e), 403)
            except ValueError as e:
                return err(str(e))

    @app.route("/ops/student-support/requests", methods=["GET"])
    def student_support_requests():
        with get_db() as conn:
            ensure_tables(conn.cursor())
            _actor, departments, problem = staff(conn)
            if problem:
                return problem
            rows = list_requests(
                conn,
                departments,
                status=(request.args.get("status") or "").strip(),
                q=(request.args.get("q") or "").strip(),
            )
            return jsonify({
                "rows": rows,
                "departments": [{"code": d, "label": DEPARTMENT_LABELS[d]} for d in departments],
                "open_count": sum(1 for r in rows if r["status"] in ("new", "in_progress")),
            })

    @app.route("/ops/student-support/requests/<int:req_id>", methods=["GET", "POST"])
    def student_support_request(req_id):
        with get_db() as conn:
            actor, departments, problem = staff(conn)
            if problem:
                return problem
            if request.method == "GET":
                item = request_detail(conn, req_id, departments)
                return jsonify(item) if item else err("Không tìm thấy yêu cầu.", 404)
            try:
                return jsonify(update_request(conn, req_id, request.get_json(silent=True) or {}, departments, actor))
            except LookupError as e:
                return err(str(e), 404)
            except ValueError as e:
                return err(str(e))

    @app.route("/ops/student-support/docs", methods=["GET", "POST"])
    def student_support_docs():
        with get_db() as conn:
            actor, _departments, problem = staff(conn)
            if problem:
                return problem
            if request.method == "GET":
                return jsonify(ab.list_documents(conn, "student"))
            data = request.get_json(silent=True) or {}
            if not may_publish(actor, data.get("program_code") or ""):
                return err("Bạn chỉ được đưa tài liệu cho chương trình mình phụ trách.", 403)
            try:
                return jsonify(ab.add_document(
                    conn,
                    title=data.get("title") or "",
                    content=data.get("content") or "",
                    program_code=data.get("program_code") or "",
                    created_by=actor["login"],
                    audience="student",
                    **review_fields(actor, data),
                ))
            except ValueError as e:
                return err(str(e))

    @app.route("/ops/student-support/docs/upload", methods=["POST"])
    def student_support_docs_upload():
        with get_db() as conn:
            actor, _departments, problem = staff(conn)
            if problem:
                return problem
            if not may_publish(actor, request.form.get("program_code") or ""):
                return err("Bạn chỉ được đưa tài liệu cho chương trình mình phụ trách.", 403)
            folder = Path(uploads_dir) / "student_kb"
            folder.mkdir(parents=True, exist_ok=True)
            done, failed = [], []
            for f in request.files.getlist("files"):
                name = Path(f.filename or "").name
                if Path(name).suffix.lower() not in ab.SUPPORTED_EXTS:
                    failed.append({"file": name, "error": "Định dạng chưa hỗ trợ (PDF, DOCX, XLSX, TXT, MD)."})
                    continue
                path = folder / f"{datetime.now():%Y%m%d%H%M%S}_{name}"
                f.save(path)
                try:
                    done.append(ab.import_file(
                        conn,
                        str(path),
                        program_code=request.form.get("program_code") or "",
                        created_by=actor["login"],
                        file_name=name,
                        audience="student",
                        **review_fields(actor, request.form),
                    ))
                except Exception as e:
                    failed.append({"file": name, "error": str(e)})
            return jsonify({"imported": done, "failed": failed})

    def own_doc(conn, doc_id):
        doc = ab.get_document(conn, doc_id)
        return doc if doc and doc.get("audience") == "student" else None

    @app.route("/ops/student-support/me", methods=["GET"])
    def student_support_me():
        with get_db() as conn:
            actor, departments, problem = staff(conn)
            if problem:
                return problem
            allowed = allowed_programs(actor)
            return jsonify({
                "login": actor["login"],
                "departments": departments,
                "can_approve": can_approve(actor),
                "programs": sorted(allowed) if allowed is not None else ["MBA", "MMS", "MSCM"],
            })

    @app.route("/ops/student-support/docs/<int:doc_id>", methods=["PUT", "DELETE"])
    def student_support_doc(doc_id):
        with get_db() as conn:
            actor, _departments, problem = staff(conn)
            if problem:
                return problem
            doc = own_doc(conn, doc_id)
            if not doc:
                return err("Không tìm thấy tài liệu.", 404)
            if not may_change_doc(actor, doc):
                return err("Tài liệu này thuộc chương trình khác hoặc của người khác, bạn không được sửa hay xóa.", 403)
            if "program_code" in (request.get_json(silent=True) or {}) and not may_publish(actor, (request.get_json(silent=True) or {}).get("program_code") or ""):
                return err("Bạn chỉ được gắn tài liệu cho chương trình mình phụ trách.", 403)
            if request.method == "DELETE":
                ab.delete_document(conn, doc_id)
                return jsonify({"ok": True})
            data = {k: v for k, v in (request.get_json(silent=True) or {}).items() if k not in ("review_status", "reviewed_by", "review_note")}
            changed = "content" in data and (data["content"] or "").strip() != (doc.get("content") or "").strip()
            if changed or any(k in data and (data[k] or "") != (doc.get(k) or "") for k in ("effective_from", "effective_to")):
                data["review_status"] = "approved" if can_approve(actor) else "pending"
                data["reviewed_by"] = actor["login"]
            try:
                return jsonify(ab.update_document(conn, doc_id, data))
            except ValueError as e:
                return err(str(e))

    @app.route("/ops/student-support/docs/<int:doc_id>/review", methods=["POST"])
    def student_support_doc_review(doc_id):
        with get_db() as conn:
            actor, _departments, problem = staff(conn)
            if problem:
                return problem
            if not can_approve(actor):
                return err("Chỉ Ban giám đốc, Trợ lý BGĐ hoặc Admin được duyệt tài liệu cho bot.", 403)
            if not own_doc(conn, doc_id):
                return err("Không tìm thấy tài liệu.", 404)
            data = request.get_json(silent=True) or {}
            action = data.get("action")
            if action not in ("approve", "reject"):
                return err("Thao tác duyệt không hợp lệ.")
            note = (data.get("note") or "").strip()
            if action == "reject" and not note:
                return err("Cần ghi lý do khi trả lại tài liệu.")
            return jsonify(ab.update_document(conn, doc_id, {
                "review_status": "approved" if action == "approve" else "rejected",
                "reviewed_by": actor["login"],
                "review_note": note,
            }))

    @app.route("/ops/student-support/faqs", methods=["GET", "POST"])
    def student_support_faqs():
        with get_db() as conn:
            actor, _departments, problem = staff(conn)
            if problem:
                return problem
            if request.method == "GET":
                return jsonify(ab.list_faqs(conn, "student"))
            data = request.get_json(silent=True) or {}
            review = "approved" if can_approve(actor) else "pending"
            try:
                faq = ab.save_faq(conn, {**data, "audience": "student", "review_status": review}, actor=actor["login"])
            except ValueError as e:
                return err(str(e))
            if str(data.get("request_id") or "").isdigit():
                conn.execute("UPDATE student_support_requests SET faq_id = ? WHERE id = ?", (faq["id"], int(data["request_id"])))
                conn.commit()
            return jsonify(faq)

    @app.route("/ops/student-support/faqs/suggest", methods=["GET"])
    def student_support_faq_suggest():
        with get_db() as conn:
            _actor, departments, problem = staff(conn)
            if problem:
                return problem
            return jsonify(suggest_faqs(conn, departments))

    @app.route("/ops/student-support/faqs/<int:faq_id>/review", methods=["POST"])
    def student_support_faq_review(faq_id):
        with get_db() as conn:
            actor, _departments, problem = staff(conn)
            if problem:
                return problem
            if not can_approve(actor):
                return err("Chỉ Ban giám đốc, Trợ lý BGĐ hoặc Admin được duyệt câu trả lời cho bot.", 403)
            row = conn.execute("SELECT * FROM bot_faqs WHERE id = ? AND audience = 'student'", (faq_id,)).fetchone()
            if not row:
                return err("Không tìm thấy câu hỏi.", 404)
            data = request.get_json(silent=True) or {}
            if data.get("action") not in ("approve", "reject"):
                return err("Thao tác duyệt không hợp lệ.")
            note = (data.get("note") or "").strip()
            if data["action"] == "reject" and not note:
                return err("Cần ghi lý do khi trả lại câu trả lời.")
            faq = dict(row)
            return jsonify(ab.save_faq(conn, {
                **faq,
                "variants": faq.get("variants") or "",
                "review_status": "approved" if data["action"] == "approve" else "rejected",
                "review_note": note,
            }, faq_id=faq_id, actor=actor["login"]))

    @app.route("/ops/student-support/faqs/<int:faq_id>", methods=["DELETE"])
    def student_support_faq(faq_id):
        with get_db() as conn:
            actor, _departments, problem = staff(conn)
            if problem:
                return problem
            row = conn.execute("SELECT audience, program_code, created_by FROM bot_faqs WHERE id = ?", (faq_id,)).fetchone()
            if not row or row[0] != "student":
                return err("Không tìm thấy câu hỏi.", 404)
            if not may_change_doc(actor, {"program_code": row[1], "created_by": row[2]}):
                return err("Câu hỏi này thuộc chương trình khác hoặc của người khác, bạn không được xóa.", 403)
            ab.delete_faq(conn, faq_id)
            return jsonify({"ok": True})

    @app.route("/ops/student-support/test", methods=["POST"])
    def student_support_test():
        with get_db() as conn:
            _actor, departments, problem = staff(conn)
            if problem:
                return problem
            data = request.get_json(silent=True) or {}
            question = normalize_question(data.get("question") or "")
            if not question:
                return err("Nhập câu hỏi.")
            login = (data.get("student_login") or "").strip()
            if login:
                row = conn.execute("SELECT id FROM user WHERE email = ?", (login,)).fetchone()
                ctx = student_context(conn, row[0]) if row else None
                if not ctx:
                    return err("Không tìm thấy học viên với tài khoản này.", 404)
                if ctx["department_code"] not in departments:
                    return err("Học viên này không thuộc chương trình bạn phụ trách.", 403)
                started = datetime.now()
                decision = route(conn, ctx, question)
                return jsonify({
                    "answered": decision["mode"] not in ("fallback", "handoff"),
                    "mode": decision["mode"],
                    "text": decision.get("text") or "Bot chưa trả lời được, câu này sẽ được chuyển cho cán bộ.",
                    "personal_intents": detect_personal(question),
                    "seconds": round((datetime.now() - started).total_seconds(), 1),
                    "hits": [],
                })
            result = ab.generate_reply(conn, question, audience="student", persona=PERSONA, prefix=PREFIX)
            return jsonify({
                "answered": bool(result.get("answered")),
                "mode": result.get("mode") or "fallback",
                "text": result.get("text") or "Bot chưa trả lời được, câu này sẽ được chuyển cho cán bộ.",
                "personal_intents": detect_personal(question),
                "hits": [
                    {"kind": h["kind"], "title": h.get("question") or h["title"], "score": h.get("score"), "coverage": h.get("coverage")}
                    for h in (result.get("hits") or [])[:5]
                ],
            })
