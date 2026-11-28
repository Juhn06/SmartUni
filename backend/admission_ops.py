"""
Admission rounds + candidate dossiers + round documents.

Nghiệp vụ:
- Đợt TS: chương trình, khóa, năm, mã/tên, ngày nộp/thi/kết quả.
- Hồ sơ độc lập theo (CCCD, chương trình) — đăng ký 2 CT = 2 hồ sơ.
- Hội đồng chỉ công nhận trúng tuyển ngành đủ điều kiện.
- Chuyển nhập học: một bộ hồ sơ duy nhất, đánh dấu ngành đã trúng tuyển.
- Tài liệu đợt: 10 loại, upload / preview / download / tìm theo đợt.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from course_content import MATERIAL_EXTS, allowed_material_filename

BACKEND_DIR = Path(__file__).resolve().parent
ROUND_DOCS_DIR = BACKEND_DIR / "uploads" / "admission_rounds"
APP_DOCS_DIR = BACKEND_DIR / "uploads" / "application_docs"
APP_DOC_MAX_BYTES = 25 * 1024 * 1024

ROUND_EXTRA_COLUMNS = [
    ("intake", "TEXT"),
    ("exam_timeline", "TEXT"),
    ("interview_timeline", "TEXT"),
    ("cohort", "TEXT"),
    ("apply_due_date", "TEXT"),
    ("exam_date", "TEXT"),
    ("result_date", "TEXT"),
]

APP_ADMISSION_COLUMNS = [
    ("exam_format", "TEXT"),
    ("exam_board", "TEXT"),
    ("admitted_program", "TEXT"),
]

PERM_DOC_MANAGE = "admissions.round_docs"
PERM_DOC_VIEW = "admissions.round_docs.view"
PERM_DOC_DOWNLOAD = "admissions.round_docs.download"

PERM_APP_DOC_MANAGE = ("admissions.applications", "accounting.candidate_files")
PERM_APP_DOC_VIEW = (
    "admissions.applications",
    "admissions.results",
    "accounting.official_list",
    "accounting.candidate_files",
)

APP_DOC_TYPES = {
    "english_cert": {
        "name": "Chứng chỉ ngoại ngữ",
        "name_en": "Language certificate",
        "exts": {"pdf", "jpg", "jpeg", "png"},
        "hint": "IELTS, TOEFL, DELF… (PDF hoặc ảnh)",
    },
    "degree": {
        "name": "Bằng đại học",
        "name_en": "University degree",
        "exts": {"pdf", "jpg", "jpeg", "png"},
        "hint": "Bằng / bảng điểm đại học",
    },
    "other_evidence": {
        "name": "Tài liệu minh chứng khác",
        "name_en": "Other supporting documents",
        "exts": {"pdf"},
        "hint": "Một file PDF gồm giấy khen, học bạ và minh chứng khác",
    },
}

DEFAULT_DOC_TYPES = [
    ("quy_che_chuong_trinh", "Quy định / Quy chế cấp chương trình", "Program-level regulations", 10),
    ("quy_che_phong_ban", "Quy định / Quy chế cấp phòng ban", "Department-level regulations", 20),
    ("quy_che_trung_tam", "Quy định / Quy chế cấp trung tâm", "Center-level regulations", 30),
    ("thong_bao", "Thông báo", "Announcement", 40),
    ("qd_hoi_dong", "Quyết định thành lập hội đồng", "Board establishment decision", 50),
    ("giay_phep_ct", "Giấy phép chương trình", "Program license", 60),
    ("bao_cao_dh", "Báo cáo từ Trung tâm lên Đại học", "Center report to the University", 70),
    ("bao_cao_bo", "Báo cáo từ Trung tâm lên Cấp bộ", "Center report to the Ministry", 80),
    ("bien_ban_hop", "Biên bản họp nội bộ", "Internal meeting minutes", 90),
    ("minh_chung_kd", "Tài liệu minh chứng Kiểm định", "Accreditation evidence", 100),
    ("quy_dinh", "Quy định tuyển sinh", "Admission regulations", 110),
    ("quy_che", "Quy chế tuyển sinh", "Admission rules", 120),
    ("huong_dan_nop", "Hướng dẫn nộp hồ sơ", "Application guide", 130),
    ("danh_sach_ts", "Danh sách thí sinh", "Candidate list", 140),
    ("hinh_thuc_thi", "Hình thức / đề thi", "Exam format / papers", 150),
    ("qd_trung_tuyen", "Quyết định trúng tuyển", "Admission decision", 160),
    ("ds_nhap_hoc", "Danh sách nhập học", "Enrollment list", 170),
    ("bao_cao", "Báo cáo khác", "Other reports", 180),
    ("bien_ban", "Biên bản / tài liệu khác", "Minutes / other", 190),
]

ADMIT_TOKENS = (
    "trúng tuyển", "trung tuyen", "admitted", "đỗ", "do ", "pass",
    "chấp thuận", "chap thuan", "đã chấp thuận",
)
REJECT_TOKENS = (
    "không trúng",
    "khong trung",
    "non-admitted",
    "non admitted",
    "trượt",
    "truot",
    "rejected",
    "fail",
)
NOT_ELIGIBLE = {"no", "không", "khong", "0", "n", "false", "chưa", "chua"}
PROGRAMS = ("MBA", "MMS", "MSCM")


def _table_cols(cur, table: str) -> set[str]:
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_missing_columns(cur, table: str, columns: list[tuple[str, str]]) -> None:
    existing = _table_cols(cur, table)
    for name, typ in columns:
        if name not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")


def normalize_cccd(value: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", (value or "")).upper()


def parse_program_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        parts = [str(x) for x in raw]
    else:
        parts = re.split(r"[,;/|]+", str(raw))
    out: list[str] = []
    for p in parts:
        code = (p or "").strip().upper()
        if code in PROGRAMS and code not in out:
            out.append(code)
    return out


def pick_default_round_id(cur, programs: list[str] | None = None) -> int:
    """Prefer the latest open round that includes all requested programs."""
    needed = set(parse_program_list(programs) if programs else [])
    rows = cur.execute(
        "SELECT id, programs, status FROM admission_rounds "
        "ORDER BY CASE WHEN lower(ifnull(status,'')) = 'open' THEN 0 ELSE 1 END, "
        "year DESC, id DESC"
    ).fetchall()
    if not rows:
        raise ValueError("Chưa có đợt tuyển sinh — hãy tạo đợt trước.")
    if needed:
        for row in rows:
            allowed = set(parse_program_list(row[1]) or PROGRAMS)
            if needed.issubset(allowed):
                return int(row[0])
    return int(rows[0][0])


def classify_board_decision(text: str | None) -> str:
    """Return 'admit' | 'reject' | ''."""
    s = (text or "").strip().lower()
    if not s:
        return ""
    if any(tok in s for tok in REJECT_TOKENS):
        return "reject"
    if any(tok in s for tok in ADMIT_TOKENS):
        return "admit"
    return ""


def ensure_admission_tables(cur) -> None:
    from ops_data import ensure_ops_tables

    ensure_ops_tables(cur)
    _add_missing_columns(cur, "admission_rounds", ROUND_EXTRA_COLUMNS)
    _add_missing_columns(cur, "applications", APP_ADMISSION_COLUMNS)
    cur.execute(
        "CREATE TABLE IF NOT EXISTS admission_doc_types ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "code TEXT NOT NULL UNIQUE, "
        "name TEXT NOT NULL, "
        "name_en TEXT, "
        "sort_order INTEGER DEFAULT 0, "
        "active INTEGER DEFAULT 1)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS admission_round_docs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "round_id INTEGER NOT NULL, "
        "doc_type_id INTEGER, "
        "title TEXT NOT NULL, "
        "original_name TEXT, "
        "stored_name TEXT, "
        "file_path TEXT, "
        "mime TEXT, "
        "size_bytes INTEGER DEFAULT 0, "
        "notes TEXT, "
        "program_codes TEXT, "
        "uploaded_at TEXT, "
        "uploaded_by TEXT, "
        "FOREIGN KEY (round_id) REFERENCES admission_rounds(id), "
        "FOREIGN KEY (doc_type_id) REFERENCES admission_doc_types(id))"
    )
    _add_missing_columns(
        cur,
        "admission_round_docs",
        [("program_codes", "TEXT"), ("share_scope", "TEXT"), ("cohort_code", "TEXT")],
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS application_docs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "application_id INTEGER NOT NULL, "
        "doc_type TEXT NOT NULL, "
        "title TEXT NOT NULL, "
        "original_name TEXT, "
        "stored_name TEXT, "
        "file_path TEXT, "
        "mime TEXT, "
        "size_bytes INTEGER DEFAULT 0, "
        "notes TEXT, "
        "uploaded_at TEXT, "
        "uploaded_by TEXT, "
        "FOREIGN KEY (application_id) REFERENCES applications(id))"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_application_docs_app "
        "ON application_docs(application_id, doc_type)"
    )
    existing = {
        r[0]
        for r in cur.execute("SELECT code FROM admission_doc_types").fetchall()
    }
    for code, name, name_en, sort_order in DEFAULT_DOC_TYPES:
        if code in existing:
            continue
        cur.execute(
            "INSERT INTO admission_doc_types (code, name, name_en, sort_order, active) "
            "VALUES (?, ?, ?, ?, 1)",
            (code, name, name_en, sort_order),
        )


def _round_dict(row, cols: list[str]) -> dict:
    return {cols[i]: (row[i] if row[i] is not None else "") for i in range(len(cols))}


def list_admission_rounds(
    conn,
    q: str = "",
    *,
    program_code: str = "",
    status: str = "",
    year: str | int | None = None,
    intake: str = "",
) -> list[dict]:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    cols = [
        "id", "code", "name", "programs", "year", "status", "opened_at", "closed_at",
        "intake", "exam_timeline", "interview_timeline",
        "cohort", "apply_due_date", "exam_date", "result_date",
    ]
    present = _table_cols(cur, "admission_rounds")
    select_cols = [c for c in cols if c in present or c == "id"]
    sql = (
        f"SELECT {', '.join('r.' + c for c in select_cols)} "
        "FROM admission_rounds r ORDER BY r.year DESC, r.id DESC"
    )
    rows = [_round_dict(r, select_cols) for r in cur.execute(sql).fetchall()]
    doc_map: dict[int, list[str]] = {}
    try:
        for rid, title, dtype, orig in cur.execute(
            "SELECT d.round_id, d.title, t.name, d.original_name "
            "FROM admission_round_docs d "
            "LEFT JOIN admission_doc_types t ON t.id = d.doc_type_id"
        ):
            bits = [x for x in (title, dtype, orig) if x]
            doc_map.setdefault(int(rid), []).extend(bits)
    except Exception:
        pass
    app_counts: dict[int, int] = {}
    iv_counts: dict[int, int] = {}
    try:
        for rid, n in cur.execute(
            "SELECT round_id, COUNT(*) FROM applications WHERE round_id IS NOT NULL GROUP BY round_id"
        ):
            app_counts[int(rid)] = int(n or 0)
    except Exception:
        pass
    try:
        for rid, n in cur.execute(
            "SELECT round_id, COUNT(*) FROM interview_sessions WHERE round_id IS NOT NULL GROUP BY round_id"
        ):
            iv_counts[int(rid)] = int(n or 0)
    except Exception:
        pass
    out = []
    ql = (q or "").strip().lower()
    prog = (program_code or "").strip().upper()
    st = (status or "").strip().lower()
    year_s = str(year).strip() if year not in (None, "") else ""
    intake_s = (intake or "").strip().lower()
    for row in rows:
        rid = int(row["id"])
        titles = doc_map.get(rid) or []
        row["doc_count"] = len({t for t in titles if t})
        row["doc_titles"] = " · ".join(dict.fromkeys(titles))
        row["related_apps"] = app_counts.get(rid, 0)
        row["related_interviews"] = iv_counts.get(rid, 0)
        row["has_related_data"] = int(
            (row["related_apps"] or 0) + (row["doc_count"] or 0) + (row["related_interviews"] or 0) > 0
        )
        if ql:
            blob = " ".join(str(v) for v in row.values() if v not in (None, "") and not isinstance(v, (dict, list)))
            if ql not in blob.lower():
                continue
        if prog:
            progs = {p.strip().upper() for p in str(row.get("programs") or "").split(",") if p.strip()}
            if prog not in progs:
                continue
        if st and str(row.get("status") or "").strip().lower() != st:
            continue
        if year_s and str(row.get("year") or "").strip() != year_s:
            continue
        if intake_s and intake_s not in str(row.get("intake") or "").strip().lower():
            continue
        out.append(row)
    return out


def get_admission_round(conn, round_id: int) -> dict | None:
    rows = list_admission_rounds(conn)
    return next((r for r in rows if int(r["id"]) == int(round_id)), None)


def _normalize_round_payload(data: dict) -> dict:
    programs = data.get("programs")
    if isinstance(programs, (list, tuple)):
        programs = ",".join(parse_program_list(programs))
    else:
        programs = ",".join(parse_program_list(programs)) or (str(programs or "").strip())
    year_raw = data.get("year")
    try:
        year = int(year_raw) if year_raw not in (None, "") else date.today().year
    except (TypeError, ValueError):
        year = date.today().year
    exam_date = (data.get("exam_date") or "").strip()
    exam_timeline = (data.get("exam_timeline") or "").strip() or exam_date
    return {
        "code": (data.get("code") or "").strip(),
        "name": (data.get("name") or "").strip(),
        "programs": programs or "MBA,MMS,MSCM",
        "year": year,
        "status": (data.get("status") or "open").strip() or "open",
        "intake": (data.get("intake") or "").strip(),
        "exam_timeline": exam_timeline,
        "interview_timeline": (data.get("interview_timeline") or "").strip(),
        "cohort": (data.get("cohort") or "").strip(),
        "apply_due_date": (data.get("apply_due_date") or "").strip(),
        "exam_date": exam_date,
        "result_date": (data.get("result_date") or "").strip(),
        "opened_at": (data.get("opened_at") or "").strip(),
        "closed_at": (data.get("closed_at") or "").strip(),
    }


def create_admission_round(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    payload = _normalize_round_payload(data)
    if not payload["code"] or not payload["name"]:
        raise ValueError("Cần mã đợt và tên đợt tuyển sinh.")
    if not payload["programs"]:
        raise ValueError("Chọn ít nhất một chương trình.")
    dup = cur.execute(
        "SELECT id FROM admission_rounds WHERE lower(trim(code)) = lower(trim(?))",
        (payload["code"],),
    ).fetchone()
    if dup:
        raise ValueError("Mã đợt bị trùng, vui lòng nhập đợt khác")
    opened = payload["opened_at"] or date.today().isoformat()
    cur.execute(
        "INSERT INTO admission_rounds "
        "(code, name, programs, year, status, opened_at, closed_at, intake, "
        "exam_timeline, interview_timeline, cohort, apply_due_date, exam_date, result_date) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            payload["code"], payload["name"], payload["programs"], payload["year"],
            payload["status"], opened, payload["closed_at"] or None,
            payload["intake"], payload["exam_timeline"], payload["interview_timeline"],
            payload["cohort"], payload["apply_due_date"], payload["exam_date"],
            payload["result_date"],
        ),
    )
    conn.commit()
    return get_admission_round(conn, cur.lastrowid) or {"id": cur.lastrowid, **payload}


def update_admission_round(conn, round_id: int, data: dict) -> dict:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    exists = cur.execute("SELECT id FROM admission_rounds WHERE id = ?", (round_id,)).fetchone()
    if not exists:
        raise ValueError("Không tìm thấy đợt tuyển sinh")
    payload = _normalize_round_payload(data)
    if payload["code"]:
        dup = cur.execute(
            "SELECT id FROM admission_rounds WHERE lower(trim(code)) = lower(trim(?)) AND id <> ?",
            (payload["code"], round_id),
        ).fetchone()
        if dup:
            raise ValueError("Mã đợt bị trùng, vui lòng nhập đợt khác")
    allowed = [
        "code", "name", "programs", "year", "status", "opened_at", "closed_at",
        "intake", "exam_timeline", "interview_timeline", "cohort",
        "apply_due_date", "exam_date", "result_date",
    ]
    fields, params = [], []
    for k in allowed:
        if k not in data and not (k in payload and payload.get(k) not in (None, "") and k != "status"):
            # Still allow explicit empty strings for dates when key is present
            if k not in data:
                continue
        val = payload.get(k)
        if k in ("code", "name") and not val:
            continue
        fields.append(f"{k} = ?")
        params.append(val)
    if not fields:
        raise ValueError("Không có trường để cập nhật")
    params.append(round_id)
    cur.execute(f"UPDATE admission_rounds SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    return get_admission_round(conn, round_id) or {"id": round_id}


def find_application_by_cccd_program(cur, cccd: str, program_code: str, *, exclude_id: int | None = None):
    norm = normalize_cccd(cccd)
    if not norm:
        return None
    sql = (
        "SELECT id FROM applications WHERE program_code = ? AND "
        "REPLACE(REPLACE(REPLACE(UPPER(IFNULL(cccd,'')),' ',''),'-',''),'.','') = ?"
    )
    params: list[Any] = [program_code, norm]
    if exclude_id:
        sql += " AND id <> ?"
        params.append(exclude_id)
    return cur.execute(sql, params).fetchone()


def application_eligible_for_admit(row: dict) -> tuple[bool, str]:
    flag = str(row.get("exam_eligible_flag") or "").strip().lower()
    if flag in NOT_ELIGIBLE:
        return False, "Thí sinh chưa đủ điều kiện xét tuyển cho ngành này."
    fmt = str(row.get("exam_format") or "").strip().lower()
    try:
        written = float(row.get("written_score") or 0)
    except (TypeError, ValueError):
        written = 0.0
    try:
        interview = float(row.get("interview_score") or 0)
    except (TypeError, ValueError):
        interview = 0.0
    if fmt in ("written", "thi_viet", "thi viết") and row.get("written_score") not in (None, "") and written <= 0:
        return False, "Điểm thi viết chưa đạt — không công nhận trúng tuyển ngành này."
    if fmt in ("interview", "phong_van", "phỏng vấn") and row.get("interview_score") not in (None, "") and interview <= 0:
        return False, "Điểm phỏng vấn chưa đạt — không công nhận trúng tuyển ngành này."
    return True, ""


def apply_board_decision_fields(row: dict, data: dict) -> dict:
    """Mutate data with status/final_result/admitted_program based on board or status."""
    program = (row.get("program_code") or data.get("program_code") or "").strip().upper()
    board = data.get("board_decision") if "board_decision" in data else row.get("board_decision")
    kind = classify_board_decision(str(board or ""))
    new_status = (data.get("status") or "").strip()
    if kind == "admit" and not new_status:
        data["status"] = "passed"
        new_status = "passed"
    if kind == "reject" and not new_status:
        data["status"] = "failed"
        new_status = "failed"
    if new_status == "passed" or kind == "admit":
        ok, msg = application_eligible_for_admit({**row, **data})
        if not ok:
            raise ValueError(msg)
        data["final_result"] = data.get("final_result") or "Admitted"
        data["admitted_program"] = program
    elif new_status == "failed" or kind == "reject":
        data["final_result"] = data.get("final_result") or "Non-Admitted"
        data["admitted_program"] = ""
    elif new_status in ("paid", "official"):
        admitted = (data.get("admitted_program") or row.get("admitted_program") or program).strip().upper()
        if admitted and admitted != program:
            raise ValueError(
                f"Hồ sơ ngành {program} không được chuyển nhập học vì đã gắn ngành {admitted}."
            )
        data["admitted_program"] = program
        data["final_result"] = data.get("final_result") or "Admitted"
    return data


def assert_can_mark_official(row: dict) -> None:
    status = (row.get("status") or "").strip()
    program = (row.get("program_code") or "").strip().upper()
    admitted = (row.get("admitted_program") or "").strip().upper()
    final_result = (row.get("final_result") or "").strip()
    if status in ("failed", "withdrawn"):
        raise ValueError("Không chuyển nhập học hồ sơ chưa trúng tuyển / đã rút.")
    if status not in ("passed", "paid", "official") and final_result != "Admitted":
        raise ValueError("Chỉ chuyển nhập học khi thí sinh đã được công nhận trúng tuyển ngành này.")
    if admitted and admitted != program:
        raise ValueError(
            f"Bộ hồ sơ này gắn ngành {admitted}, không chuyển nhập học ngành {program}."
        )
    ok, msg = application_eligible_for_admit(row)
    if not ok:
        raise ValueError(msg)


def mark_decision_effective(cur, app_id: int) -> None:
    cols = {r[1] for r in cur.execute("PRAGMA table_info(applications)").fetchall()}
    if "decision_status" not in cols:
        return
    cur.execute(
        "UPDATE applications SET decision_status = 'effective', "
        "selection_status = CASE WHEN IFNULL(selection_status, '') IN ('', 'pending') THEN 'admitted' ELSE selection_status END "
        "WHERE id = ? AND IFNULL(decision_status, '') IN ('', 'draft', 'approved')",
        (app_id,),
    )


def create_candidate_applications(conn, data: dict) -> dict:
    """Create one independent dossier per selected program (upsert by CCCD+program)."""
    from coord_ops import ensure_coord_tables

    cur = conn.cursor()
    ensure_coord_tables(cur)
    ensure_admission_tables(cur)
    full_name = (data.get("full_name") or "").strip()
    cccd_raw = (data.get("cccd") or "").strip()
    cccd = normalize_cccd(cccd_raw)
    if not full_name:
        raise ValueError("Cần họ tên thí sinh.")
    if not cccd:
        raise ValueError("Cần Căn cước công dân.")
    programs = parse_program_list(data.get("programs") or data.get("program_code"))
    if not programs:
        raise ValueError("Chọn ít nhất một chương trình.")
    round_id = data.get("round_id")
    try:
        round_id = int(round_id) if round_id not in (None, "") else None
    except (TypeError, ValueError):
        round_id = None
    if not round_id:
        round_id = pick_default_round_id(cur, programs)
    rnd = cur.execute(
        "SELECT id, programs FROM admission_rounds WHERE id = ?", (round_id,)
    ).fetchone()
    if not rnd:
        raise ValueError("Không tìm thấy đợt tuyển sinh.")
    allowed = parse_program_list(rnd[1]) or list(PROGRAMS)
    for prog in programs:
        if allowed and prog not in allowed:
            raise ValueError(f"Đợt này không mở ngành {prog}.")
    created, updated, apps = [], [], []
    shared = {
        "email": (data.get("email") or "").strip(),
        "phone": (data.get("phone") or "").strip(),
        "notes": (data.get("notes") or "").strip(),
        "exam_format": (data.get("exam_format") or "").strip(),
        "exam_board": (data.get("exam_board") or "").strip(),
        "campus": (data.get("campus") or "").strip(),
        "lead_source": (data.get("lead_source") or "").strip() or "other",
        "checklist_status": (data.get("checklist_status") or "pending").strip() or "pending",
        "exam_eligible_flag": (data.get("exam_eligible_flag") or "").strip(),
    }
    for prog in programs:
        existing = find_application_by_cccd_program(cur, cccd_raw, prog)
        if existing:
            app_id = existing[0]
            cur.execute(
                "UPDATE applications SET full_name=?, cccd=?, email=?, phone=?, notes=?, "
                "exam_format=?, exam_board=?, campus=?, lead_source=?, exam_eligible_flag=? "
                "WHERE id=?",
                (
                    full_name, cccd_raw, shared["email"], shared["phone"], shared["notes"],
                    shared["exam_format"], shared["exam_board"], shared["campus"],
                    shared["lead_source"], shared["exam_eligible_flag"], app_id,
                ),
            )
            updated.append(app_id)
            apps.append({"id": app_id, "program_code": prog, "action": "updated"})
        else:
            cur.execute(
                "INSERT INTO applications "
                "(round_id, program_code, full_name, cccd, email, phone, status, notes, "
                "campus, lead_source, checklist_status, exam_format, exam_board, exam_eligible_flag) "
                "VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?, ?, ?, ?)",
                (
                    round_id, prog, full_name, cccd_raw, shared["email"], shared["phone"],
                    shared["notes"], shared["campus"], shared["lead_source"],
                    shared["checklist_status"], shared["exam_format"], shared["exam_board"],
                    shared["exam_eligible_flag"],
                ),
            )
            app_id = cur.lastrowid
            created.append(app_id)
            apps.append({"id": app_id, "program_code": prog, "action": "created"})
    try:
        from learner_spine import upsert_learner_for_application

        for aid in created + updated:
            upsert_learner_for_application(conn, int(aid))
    except Exception:
        pass
    conn.commit()
    from admission_bot import link_applications_to_lead

    lead = link_applications_to_lead(
        conn, phone=shared["phone"], email=shared["email"], applications=apps, actor=str(data.get("actor") or "")
    )
    return {
        "ok": True,
        "lead_linked": lead,
        "round_id": round_id,
        "cccd": cccd_raw,
        "full_name": full_name,
        "created_ids": created,
        "updated_ids": updated,
        "applications": apps,
        "handoff": (
            "Mỗi chương trình là một hồ sơ độc lập. "
            "Hội đồng chỉ công nhận trúng tuyển ngành đủ điều kiện; "
            "nhập học chuyển đúng bộ hồ sơ ngành đã trúng tuyển."
        ),
    }


def list_doc_types(conn, *, include_inactive: bool = False) -> list[dict]:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    sql = (
        "SELECT id, code, name, name_en, sort_order, active FROM admission_doc_types "
    )
    if not include_inactive:
        sql += "WHERE active = 1 "
    sql += "ORDER BY sort_order, id"
    rows = cur.execute(sql).fetchall()
    return [
        {
            "id": r[0],
            "code": r[1],
            "name": r[2],
            "name_en": r[3] or "",
            "sort_order": r[4] or 0,
            "active": int(r[5] or 0),
            "status": "active" if int(r[5] or 0) else "inactive",
        }
        for r in rows
    ]


def create_doc_type(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    name = (data.get("name") or data.get("label") or "").strip()
    if not name:
        raise ValueError("Cần tên loại tài liệu.")
    raw_code = (data.get("code") or "").strip().lower()
    code = re.sub(r"[^a-z0-9_]+", "_", raw_code).strip("_") or re.sub(
        r"[^a-z0-9_]+", "_", name.lower()
    ).strip("_")
    if not code:
        raise ValueError("Cần mã loại tài liệu.")
    exists = cur.execute("SELECT id FROM admission_doc_types WHERE code = ?", (code,)).fetchone()
    if exists:
        raise ValueError("Mã loại tài liệu đã tồn tại.")
    sort_order = int(data.get("sort_order") or 200)
    name_en = (data.get("name_en") or data.get("label_en") or "").strip()
    cur.execute(
        "INSERT INTO admission_doc_types (code, name, name_en, sort_order, active) "
        "VALUES (?, ?, ?, ?, 1)",
        (code, name, name_en, sort_order),
    )
    conn.commit()
    return {
        "id": cur.lastrowid,
        "code": code,
        "name": name,
        "name_en": name_en,
        "sort_order": sort_order,
        "active": 1,
        "status": "active",
    }


def update_doc_type(conn, type_id: int, data: dict) -> dict:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    row = cur.execute(
        "SELECT id, code FROM admission_doc_types WHERE id = ?", (type_id,)
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy loại tài liệu.")
    fields, params = [], []
    if "name" in data and (data.get("name") or "").strip():
        fields.append("name = ?")
        params.append((data.get("name") or "").strip())
    if "name_en" in data:
        fields.append("name_en = ?")
        params.append((data.get("name_en") or "").strip())
    if "sort_order" in data and data.get("sort_order") is not None:
        fields.append("sort_order = ?")
        params.append(int(data.get("sort_order") or 0))
    if "active" in data or "status" in data:
        active = data.get("active")
        if active is None:
            active = 0 if str(data.get("status") or "").lower() in ("inactive", "0", "off") else 1
        fields.append("active = ?")
        params.append(1 if active in (1, True, "1", "true", "active") else 0)
    if not fields:
        raise ValueError("Không có trường để cập nhật")
    params.append(type_id)
    cur.execute(f"UPDATE admission_doc_types SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    items = list_doc_types(conn, include_inactive=True)
    return next((x for x in items if x["id"] == type_id), {"id": type_id})


def delete_doc_type(conn, type_id: int) -> bool:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    used = cur.execute(
        "SELECT COUNT(*) FROM admission_round_docs WHERE doc_type_id = ?", (type_id,)
    ).fetchone()[0]
    if used:
        raise ValueError(
            "Không xóa được vì khâu sau đã có dữ liệu: "
            f"{used} tài liệu đợt tuyển sinh. "
            "/ Cannot delete — later stage already has round documents."
        )
    cur.execute("DELETE FROM admission_doc_types WHERE id = ?", (type_id,))
    conn.commit()
    return cur.rowcount > 0


def _cccd_sql_eq() -> str:
    return "REPLACE(REPLACE(REPLACE(UPPER(IFNULL(cccd,'')),' ',''),'-',''),'.','')"


def propagate_person_update_by_cccd(conn, cccd: str, fields: dict | None = None) -> dict:
    """When CCCD exists, replace person fields across Hồ sơ → Thí sinh → Người học → Học."""
    from ops_data import ensure_ops_tables

    fields = fields or {}
    norm = normalize_cccd(cccd)
    if not norm:
        return {"updated": 0}
    cur = conn.cursor()
    ensure_admission_tables(cur)
    ensure_ops_tables(cur)
    try:
        from mba_ops import ensure_mba_tables

        ensure_mba_tables(cur)
    except Exception:
        pass
    try:
        from marcom_ops import ensure_marcom_tables

        ensure_marcom_tables(cur)
    except Exception:
        pass
    try:
        from crm_ops import ensure_crm_tables

        ensure_crm_tables(cur)
    except Exception:
        pass
    name = (fields.get("full_name") or "").strip()
    email = (fields.get("email") or "").strip()
    phone = (fields.get("phone") or "").strip()
    company = (fields.get("company") or "").strip()
    counts = {"applications": 0, "class_students": 0, "alumni": 0, "crm": 0, "leads": 0}

    def _set_cols(table: str, extra_where: str = "", extra_params: tuple = ()):
        sets, params = [], []
        cols = _table_cols(cur, table)
        if name and "full_name" in cols:
            sets.append("full_name = ?")
            params.append(name)
        if email and "email" in cols:
            sets.append("email = ?")
            params.append(email)
        if phone and "phone" in cols:
            sets.append("phone = ?")
            params.append(phone)
        if company and "company" in cols:
            sets.append("company = ?")
            params.append(company)
        if not sets:
            return 0
        sql = f"UPDATE {table} SET {', '.join(sets)} WHERE {_cccd_sql_eq()} = ?"
        params.append(norm)
        if extra_where:
            sql += " " + extra_where
            params.extend(extra_params)
        cur.execute(sql, params)
        return cur.rowcount

    if "cccd" in _table_cols(cur, "applications"):
        counts["applications"] = _set_cols("applications")
        app_ids = [
            int(r[0])
            for r in cur.execute(
                f"SELECT id FROM applications WHERE {_cccd_sql_eq()} = ?", (norm,)
            ).fetchall()
        ]
        cs_cols = _table_cols(cur, "class_students")
        if app_ids and cs_cols:
            sets, params = [], []
            if name and "full_name" in cs_cols:
                sets.append("full_name = ?")
                params.append(name)
            if email and "email" in cs_cols:
                sets.append("email = ?")
                params.append(email)
            if phone and "phone" in cs_cols:
                sets.append("phone = ?")
                params.append(phone)
            if "cccd" in cs_cols:
                sets.append("cccd = ?")
                params.append((fields.get("cccd") or cccd or "").strip() or norm)
            if sets:
                placeholders = ",".join("?" * len(app_ids))
                cur.execute(
                    f"UPDATE class_students SET {', '.join(sets)} "
                    f"WHERE application_id IN ({placeholders})",
                    params + app_ids,
                )
                counts["class_students"] = cur.rowcount
    if "cccd" in _table_cols(cur, "alumni_members"):
        counts["alumni"] = _set_cols("alumni_members")
    if "cccd" in _table_cols(cur, "crm_source_profiles"):
        counts["crm"] = _set_cols("crm_source_profiles")
    if "cccd" in _table_cols(cur, "marcom_leads"):
        counts["leads"] = _set_cols("marcom_leads")
    conn.commit()
    return {"updated": sum(counts.values()), "stages": counts}


def propagate_row_by_id(conn, table: str, row_id: int, extra: dict | None = None) -> dict:
    """Load current person fields from a row and replace downstream stages by CCCD."""
    extra = extra or {}
    cur = conn.cursor()
    cols = _table_cols(cur, table)
    if "cccd" not in cols:
        return {"updated": 0}
    fields = ["cccd"]
    for c in ("full_name", "email", "phone", "company"):
        if c in cols:
            fields.append(c)
    row = cur.execute(
        f"SELECT {', '.join(fields)} FROM {table} WHERE id = ?", (row_id,)
    ).fetchone()
    if not row:
        return {"updated": 0}
    data = {fields[i]: (row[i] or "") for i in range(len(fields))}
    for k, v in extra.items():
        if k in ("full_name", "email", "phone", "company", "cccd") and v not in (None, ""):
            data[k] = v
    return propagate_person_update_by_cccd(conn, data.get("cccd") or "", data)


def round_doc_caps(actor: dict | None) -> dict:
    """Live caps from actor permission_codes (re-read mỗi request)."""
    actor = actor or {}
    codes = {str(c) for c in (actor.get("permission_codes") or [])}
    admin = bool(actor.get("is_admin"))
    manage = admin or PERM_DOC_MANAGE in codes
    download = admin or manage or PERM_DOC_DOWNLOAD in codes
    view = admin or manage or download or PERM_DOC_VIEW in codes
    return {"manage": manage, "view": view, "download": download}


def _doc_matches_program(row: dict, program_code: str) -> bool:
    pc = (program_code or "").strip().upper()
    if not pc:
        return True
    tagged = parse_program_list(row.get("program_codes"))
    if tagged:
        return pc in tagged
    round_progs = parse_program_list(row.get("round_programs"))
    return (not round_progs) or pc in round_progs


def _doc_matches_scopes(row: dict, scopes: list[str] | None) -> bool:
    if not scopes or "*" in scopes:
        return True
    allowed = {str(s).strip().upper() for s in scopes if str(s).strip() and s != "*"}
    if not allowed:
        return True
    tagged = parse_program_list(row.get("program_codes")) or parse_program_list(row.get("round_programs"))
    if not tagged:
        return True
    return bool(allowed.intersection(tagged))


def _doc_row(r) -> dict:
    return {
        "id": r[0],
        "round_id": r[1],
        "doc_type_id": r[2],
        "doc_type_code": r[3] or "",
        "doc_type_name": r[4] or "",
        "doc_type_name_en": r[5] or "",
        "title": r[6] or "",
        "original_name": r[7] or "",
        "stored_name": r[8] or "",
        "file_path": r[9] or "",
        "mime": r[10] or "",
        "size_bytes": r[11] or 0,
        "notes": r[12] or "",
        "program_codes": r[13] or "",
        "uploaded_at": r[14] or "",
        "uploaded_by": r[15] or "",
        "round_code": r[16] or "",
        "round_name": r[17] or "",
        "round_programs": r[18] or "",
        "share_scope": (r[19] or "shared") if len(r) > 19 else "shared",
        "cohort_code": (r[20] or "") if len(r) > 20 else "",
        "round_year": r[21] if len(r) > 21 else "",
        "has_file": bool(r[9] and Path(str(r[9])).is_file()),
    }


_DOC_SQL = (
    "SELECT d.id, d.round_id, d.doc_type_id, t.code, t.name, t.name_en, "
    "d.title, d.original_name, d.stored_name, d.file_path, d.mime, d.size_bytes, "
    "d.notes, IFNULL(d.program_codes,''), d.uploaded_at, d.uploaded_by, "
    "r.code, r.name, r.programs, IFNULL(d.share_scope,'shared'), IFNULL(d.cohort_code,''), "
    "IFNULL(r.year,'') "
    "FROM admission_round_docs d "
    "JOIN admission_rounds r ON r.id = d.round_id "
    "LEFT JOIN admission_doc_types t ON t.id = d.doc_type_id "
)


def list_round_docs(
    conn,
    round_id: int | None = None,
    q: str = "",
    program_code: str = "",
    scopes: list[str] | None = None,
    year: int | None = None,
    doc_scope: str = "",
    require_year: bool = False,
) -> list[dict]:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    if require_year and not year and not round_id:
        return []
    sql = _DOC_SQL
    params: list[Any] = []
    clauses: list[str] = []
    if round_id:
        clauses.append("d.round_id = ?")
        params.append(round_id)
    if year:
        clauses.append("r.year = ?")
        params.append(int(year))
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY r.year DESC, d.id DESC"
    rows = [_doc_row(r) for r in cur.execute(sql, params).fetchall()]
    ql = (q or "").strip().lower()
    out = []
    for r in rows:
        if not _doc_matches_program(r, program_code):
            continue
        if not _doc_matches_scopes(r, scopes):
            continue
        scope = (doc_scope or "").strip()
        share = (r.get("share_scope") or "shared").strip().lower()
        cohort = (r.get("cohort_code") or "").strip()
        is_shared = share != "cohort" or not cohort
        if scope == "shared" and not is_shared:
            continue
        if scope and scope != "shared" and cohort != scope and not is_shared:
            continue
        if ql:
            blob = " ".join(
                str(r.get(k) or "") for k in (
                    "title", "doc_type_name", "original_name", "notes",
                    "round_code", "round_name", "program_codes", "round_programs",
                )
            ).lower()
            if ql not in blob:
                continue
        out.append(r)
    return out


def get_round_doc(conn, doc_id: int) -> dict | None:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    row = cur.execute(_DOC_SQL + " WHERE d.id = ?", (doc_id,)).fetchone()
    return _doc_row(row) if row else None


def add_round_doc(
    conn,
    *,
    round_id: int,
    title: str,
    doc_type_id: int | None = None,
    notes: str = "",
    program_codes: str = "",
    share_scope: str = "",
    cohort_code: str = "",
    original_filename: str | None = None,
    stored_name: str | None = None,
    file_path: str | None = None,
    mime: str | None = None,
    size_bytes: int = 0,
    uploaded_by: str = "",
) -> dict:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    exists = cur.execute("SELECT id FROM admission_rounds WHERE id = ?", (round_id,)).fetchone()
    if not exists:
        raise ValueError("Không tìm thấy đợt tuyển sinh")
    title = (title or "").strip() or (Path(original_filename or "").stem if original_filename else "")
    if not title:
        raise ValueError("Cần tiêu đề hoặc file tài liệu.")
    if original_filename and not allowed_material_filename(original_filename):
        raise ValueError("Định dạng file không hỗ trợ: " + ", ".join(sorted(MATERIAL_EXTS)))
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    tagged = ",".join(parse_program_list(program_codes))
    scope = (share_scope or "").strip().lower()
    cohort = (cohort_code or "").strip()
    if scope not in ("shared", "cohort"):
        scope = "cohort" if cohort else "shared"
    cur.execute(
        "INSERT INTO admission_round_docs "
        "(round_id, doc_type_id, title, original_name, stored_name, file_path, mime, "
        "size_bytes, notes, program_codes, share_scope, cohort_code, uploaded_at, uploaded_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            round_id, doc_type_id, title, original_filename, stored_name, file_path,
            mime, size_bytes, (notes or "").strip(), tagged, scope, cohort, now, uploaded_by,
        ),
    )
    conn.commit()
    return get_round_doc(conn, cur.lastrowid) or {"id": cur.lastrowid, "title": title}


def update_round_doc(
    conn,
    doc_id: int,
    *,
    title: str | None = None,
    doc_type_id: int | None = None,
    notes: str | None = None,
    program_codes: str | None = None,
    original_filename: str | None = None,
    stored_name: str | None = None,
    file_path: str | None = None,
    mime: str | None = None,
    size_bytes: int | None = None,
    uploaded_by: str = "",
) -> dict:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    existing = get_round_doc(conn, doc_id)
    if not existing:
        raise ValueError("Không tìm thấy tài liệu")
    fields, params = [], []
    if title is not None and str(title).strip():
        fields.append("title = ?")
        params.append(str(title).strip())
    if doc_type_id is not None:
        fields.append("doc_type_id = ?")
        params.append(doc_type_id or None)
    if notes is not None:
        fields.append("notes = ?")
        params.append(str(notes).strip())
    if program_codes is not None:
        fields.append("program_codes = ?")
        params.append(",".join(parse_program_list(program_codes)))
    old_path = existing.get("file_path") or ""
    if file_path:
        fields.extend(["original_name = ?", "stored_name = ?", "file_path = ?", "mime = ?", "size_bytes = ?"])
        params.extend([original_filename, stored_name, file_path, mime, size_bytes or 0])
        fields.append("uploaded_at = ?")
        params.append(datetime.now().isoformat(sep=" ", timespec="seconds"))
        if uploaded_by:
            fields.append("uploaded_by = ?")
            params.append(uploaded_by)
    if not fields:
        raise ValueError("Không có trường để cập nhật")
    params.append(doc_id)
    cur.execute(f"UPDATE admission_round_docs SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    if file_path and old_path and old_path != file_path:
        try:
            Path(old_path).unlink(missing_ok=True)
        except Exception:
            pass
    return get_round_doc(conn, doc_id) or existing


def delete_round_doc(conn, doc_id: int) -> bool:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    row = cur.execute(
        "SELECT file_path FROM admission_round_docs WHERE id = ?", (doc_id,)
    ).fetchone()
    if not row:
        return False
    cur.execute("DELETE FROM admission_round_docs WHERE id = ?", (doc_id,))
    conn.commit()
    fp = row[0]
    if fp:
        try:
            Path(fp).unlink(missing_ok=True)
        except Exception:
            pass
    return True


def save_round_doc_file(file_storage) -> tuple[str, str, str, str, int]:
    """Return original_name, stored_name, file_path, mime, size."""
    filename = file_storage.filename or ""
    if not allowed_material_filename(filename):
        raise ValueError("Định dạng file không hỗ trợ: " + ", ".join(sorted(MATERIAL_EXTS)))
    stored = f"{uuid.uuid4().hex}_{filename}"
    dest = ROUND_DOCS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / stored
    file_storage.save(str(path))
    return filename, stored, str(path), file_storage.mimetype or "", path.stat().st_size


def app_doc_type_catalog() -> list[dict]:
    return [
        {
            "code": code,
            "name": meta["name"],
            "name_en": meta["name_en"],
            "exts": sorted(meta["exts"]),
            "hint": meta.get("hint") or "",
        }
        for code, meta in APP_DOC_TYPES.items()
    ]


def app_doc_caps(actor: dict | None, *, owns: bool = False) -> dict:
    actor = actor or {}
    codes = {str(c) for c in (actor.get("permission_codes") or [])}
    admin = bool(actor.get("is_admin"))
    manage = admin or owns or any(c in codes for c in PERM_APP_DOC_MANAGE)
    view = admin or manage or owns or any(c in codes for c in PERM_APP_DOC_VIEW)
    return {"manage": manage, "view": view, "download": view}


def _app_doc_ext(filename: str) -> str:
    return Path(filename or "").suffix.lower().lstrip(".")


def _validate_app_doc_type(doc_type: str) -> str:
    code = (doc_type or "").strip()
    if code not in APP_DOC_TYPES:
        raise ValueError(
            "Loại tài liệu không hợp lệ. Chọn: "
            + ", ".join(APP_DOC_TYPES.keys())
        )
    return code


def save_application_doc_file(file_storage, doc_type: str) -> tuple[str, str, str, str, int]:
    filename = file_storage.filename or ""
    code = _validate_app_doc_type(doc_type)
    ext = _app_doc_ext(filename)
    allowed = APP_DOC_TYPES[code]["exts"]
    if ext not in allowed:
        raise ValueError(
            f"{APP_DOC_TYPES[code]['name']}: chỉ nhận "
            + ", ".join(sorted(allowed)).upper()
        )
    if not allowed_material_filename(filename) and ext not in allowed:
        raise ValueError("Định dạng file không hỗ trợ.")
    dest = APP_DOCS_DIR
    dest.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}_{filename}"
    path = dest / stored
    file_storage.save(str(path))
    size = path.stat().st_size
    if size > APP_DOC_MAX_BYTES:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        raise ValueError("File vượt quá 25MB.")
    if size <= 0:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        raise ValueError("File rỗng.")
    return filename, stored, str(path), file_storage.mimetype or "", size


def _app_doc_row(row) -> dict:
    keys = [
        "id", "application_id", "doc_type", "title", "original_name",
        "stored_name", "file_path", "mime", "size_bytes", "notes",
        "uploaded_at", "uploaded_by",
    ]
    data = {keys[i]: row[i] for i in range(len(keys))}
    meta = APP_DOC_TYPES.get(data.get("doc_type") or "", {})
    data["doc_type_name"] = meta.get("name") or data.get("doc_type")
    data["doc_type_name_en"] = meta.get("name_en") or data.get("doc_type")
    return data


def list_application_docs(conn, application_id: int) -> list[dict]:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    rows = cur.execute(
        "SELECT id, application_id, doc_type, title, original_name, stored_name, "
        "file_path, mime, size_bytes, notes, uploaded_at, uploaded_by "
        "FROM application_docs WHERE application_id = ? ORDER BY "
        "CASE doc_type WHEN 'english_cert' THEN 1 WHEN 'degree' THEN 2 "
        "WHEN 'other_evidence' THEN 3 ELSE 9 END, id",
        (application_id,),
    ).fetchall()
    return [_app_doc_row(r) for r in rows]


def get_application_doc(conn, doc_id: int) -> dict | None:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    row = cur.execute(
        "SELECT id, application_id, doc_type, title, original_name, stored_name, "
        "file_path, mime, size_bytes, notes, uploaded_at, uploaded_by "
        "FROM application_docs WHERE id = ?",
        (doc_id,),
    ).fetchone()
    return _app_doc_row(row) if row else None


def get_application_brief(conn, application_id: int) -> dict | None:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id, full_name, cccd, email, phone, program_code, cfvg_app_no, "
        "english_cert, university, degree_major, status, campus "
        "FROM applications WHERE id = ?",
        (application_id,),
    ).fetchone()
    if not row:
        return None
    keys = [
        "id", "full_name", "cccd", "email", "phone", "program_code", "cfvg_app_no",
        "english_cert", "university", "degree_major", "status", "campus",
    ]
    return {keys[i]: (row[i] if row[i] is not None else "") for i in range(len(keys))}


def add_application_doc(
    conn,
    *,
    application_id: int,
    doc_type: str,
    title: str,
    original_filename: str,
    stored_name: str,
    file_path: str,
    mime: str = "",
    size_bytes: int = 0,
    notes: str = "",
    uploaded_by: str = "",
) -> dict:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    if not get_application_brief(conn, application_id):
        raise ValueError("Không tìm thấy hồ sơ thí sinh.")
    code = _validate_app_doc_type(doc_type)
    label = (title or "").strip() or (original_filename or "").strip() or APP_DOC_TYPES[code]["name"]
    if not file_path:
        raise ValueError("Cần chọn file để upload.")
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    cur.execute(
        "INSERT INTO application_docs ("
        "application_id, doc_type, title, original_name, stored_name, file_path, "
        "mime, size_bytes, notes, uploaded_at, uploaded_by"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            application_id, code, label, original_filename, stored_name, file_path,
            mime or "", size_bytes or 0, (notes or "").strip(), now, uploaded_by or "",
        ),
    )
    conn.commit()
    return get_application_doc(conn, cur.lastrowid)


def delete_application_doc(conn, doc_id: int) -> bool:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    row = cur.execute(
        "SELECT file_path FROM application_docs WHERE id = ?", (doc_id,)
    ).fetchone()
    if not row:
        return False
    cur.execute("DELETE FROM application_docs WHERE id = ?", (doc_id,))
    conn.commit()
    fp = row[0]
    if fp:
        try:
            Path(fp).unlink(missing_ok=True)
        except Exception:
            pass
    return True


def attach_application_doc_summary(conn, rows: list[dict]) -> list[dict]:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    if not rows:
        return rows
    ids = [int(r["id"]) for r in rows if r.get("id")]
    if not ids:
        return rows
    placeholders = ",".join("?" * len(ids))
    recs = cur.execute(
        "SELECT application_id, doc_type, title, original_name FROM application_docs "
        f"WHERE application_id IN ({placeholders}) ORDER BY id",
        ids,
    ).fetchall()
    by_app: dict[int, dict[str, list[str]]] = {}
    for aid, dtype, title, orig in recs:
        slot = by_app.setdefault(int(aid), {k: [] for k in APP_DOC_TYPES})
        label = (title or orig or "").strip()
        if not label:
            continue
        if dtype not in slot:
            slot[dtype] = []
        slot[dtype].append(label)
    for r in rows:
        docs = by_app.get(int(r.get("id") or 0)) or {}
        r["english_file"] = "; ".join(docs.get("english_cert") or [])
        r["degree_file"] = "; ".join(docs.get("degree") or [])
        r["other_file"] = "; ".join(docs.get("other_evidence") or [])
        r["doc_count"] = sum(len(v) for v in docs.values())
        r["has_english_doc"] = "yes" if docs.get("english_cert") else "no"
        r["has_degree_doc"] = "yes" if docs.get("degree") else "no"
        r["has_other_doc"] = "yes" if docs.get("other_evidence") else "no"
    return rows


ADMIT_DECISION_APPROVED = "Đã chấp thuận"
ADMIT_DECISION_REJECTED = "Không trúng tuyển"
ADMIT_DECISION_WAITLIST = "Danh sách chờ"
ADMIT_DECISION_PENDING = "Chưa có"


def candidate_code_of(app_id: int, cfvg_app_no: str | None) -> str:
    code = (cfvg_app_no or "").strip()
    return code or f"UV{int(app_id):03d}"


def student_code_of(student_id: int, *codes: str | None) -> str:
    for c in codes:
        if (c or "").strip():
            return str(c).strip()
    return f"SV{int(student_id):03d}"


def derive_admit_decision(status: str, board: str, final_result: str) -> str:
    board_s = (board or "").strip()
    kind = classify_board_decision(board_s)
    if kind == "admit":
        return board_s or ADMIT_DECISION_APPROVED
    if kind == "reject":
        return board_s or ADMIT_DECISION_REJECTED
    fr = (final_result or "").strip()
    if fr in ("Admitted", "Trúng tuyển"):
        return ADMIT_DECISION_APPROVED
    if fr in ("Non-Admitted", "Không trúng tuyển"):
        return ADMIT_DECISION_REJECTED
    if fr in ("Waiting list", "Danh sách chờ"):
        return ADMIT_DECISION_WAITLIST
    st = (status or "").strip()
    if st in ("passed", "paid", "official"):
        return ADMIT_DECISION_APPROVED
    if st == "failed":
        return ADMIT_DECISION_REJECTED
    return board_s or ADMIT_DECISION_PENDING


def sync_candidate_link_tables(conn) -> None:
    """Ngừng sao chép hồ sơ cá nhân sang hai bảng chiếu. Giữ tên hàm cho chỗ gọi cũ."""
    cur = conn.cursor()
    ensure_admission_tables(cur)
    from person_profile import retire_projection_tables

    retire_projection_tables(cur)
    conn.commit()


def _examinee_label(confirmed_at: str | None) -> str:
    return "Đã xác nhận" if (confirmed_at or "").strip() else "Chưa xác nhận"


def list_pre_enroll_files(conn, scopes: list[str] | None, *, q: str = "") -> list[dict]:
    from ops_data import _scopes_sql
    from learner_spine import ensure_learner_spine, stage_label

    cur = conn.cursor()
    ensure_admission_tables(cur)
    ensure_learner_spine(cur)
    try:
        from mba_ops import ensure_mba_tables
        from coord_ops import ensure_coord_tables

        ensure_mba_tables(cur)
        ensure_coord_tables(cur)
    except Exception:
        pass
    frag, params = _scopes_sql(scopes, "a.program_code")
    sql = (
        "SELECT a.id, a.cfvg_app_no, a.full_name, a.program_code, a.status, "
        "IFNULL(a.board_decision,''), IFNULL(a.final_result,''), IFNULL(a.cccd,''), "
        "IFNULL(a.email,''), IFNULL(a.phone,''), IFNULL(a.person_id,0), "
        "IFNULL(a.examinee_confirmed_at,''), IFNULL(l.stage,'') "
        "FROM applications a "
        "LEFT JOIN learners l ON l.application_id = a.id "
        f"WHERE {frag} AND IFNULL(a.status,'') != 'withdrawn' "
        "AND NOT EXISTS (SELECT 1 FROM program_enrollments pe WHERE pe.application_id = a.id) "
        "AND NOT EXISTS (SELECT 1 FROM class_students cs WHERE cs.application_id = a.id)"
    )
    if q:
        sql += " AND (IFNULL(a.cfvg_app_no,'') LIKE ? OR a.full_name LIKE ? OR IFNULL(a.program_code,'') LIKE ?)"
        params.extend([f"%{q}%"] * 3)
    sql += " ORDER BY a.id DESC"
    rows = []
    for r in cur.execute(sql, params).fetchall():
        stage = r[12] or "candidate"
        rows.append({
            "id": r[0],
            "application_id": r[0],
            "candidate_code": candidate_code_of(r[0], r[1]),
            "full_name": r[2] or "",
            "admit_decision": derive_admit_decision(r[4] or "", r[5], r[6]),
            "program_code": r[3] or "",
            "status": r[4] or "",
            "cccd": r[7] or "",
            "email": r[8] or "",
            "phone": r[9] or "",
            "cfvg_app_no": r[1] or candidate_code_of(r[0], r[1]),
            "person_id": r[10] or None,
            "examinee_status_label": _examinee_label(r[11]),
            "person_stage": stage,
            "person_stage_label": stage_label(stage),
        })
    return rows


def list_enrolled_files(conn, scopes: list[str] | None, *, q: str = "") -> list[dict]:
    from ops_data import _scopes_sql
    from learner_spine import ensure_learner_spine, stage_label
    from person_profile import ACADEMIC_LABELS

    cur = conn.cursor()
    ensure_admission_tables(cur)
    ensure_learner_spine(cur)
    try:
        from mba_ops import ensure_mba_tables
        from coord_ops import ensure_coord_tables

        ensure_mba_tables(cur)
        ensure_coord_tables(cur)
    except Exception:
        pass
    cs_cols = _table_cols(cur, "class_students")
    app_cols = _table_cols(cur, "applications")
    code_sql = "IFNULL(cs.student_code,'')" if "student_code" in cs_cols else "''"
    at_sql = "IFNULL(cs.enrolled_at,'')" if "enrolled_at" in cs_cols else "''"
    cfvg_sql = "IFNULL(a.cfvg_app_no,'')" if "cfvg_app_no" in app_cols else "''"
    mba_sql = "IFNULL(a.student_code_mba,'')" if "student_code_mba" in app_cols else "''"
    frag, params = _scopes_sql(scopes, "pe.program_code")
    sql = (
        f"SELECT a.id, {cfvg_sql}, IFNULL(a.full_name,''), pe.program_code, "
        f"IFNULL(pe.learner_code,''), {code_sql}, {mba_sql}, "
        f"{at_sql}, IFNULL(pe.created_at,''), pe.academic_status, "
        "IFNULL(a.cccd,''), IFNULL(a.email,''), IFNULL(a.phone,''), IFNULL(pe.person_id,0), "
        "IFNULL(l.stage,''), IFNULL(cs.id,0) "
        "FROM program_enrollments pe "
        "JOIN applications a ON a.id = pe.application_id "
        "LEFT JOIN learners l ON l.application_id = a.id "
        "LEFT JOIN class_students cs ON cs.id = ("
        "SELECT id FROM class_students WHERE application_id = a.id ORDER BY id DESC LIMIT 1) "
        f"WHERE {frag}"
    )
    if q:
        sql += (
            f" AND (IFNULL(pe.learner_code,'') LIKE ? OR {cfvg_sql} LIKE ? "
            "OR IFNULL(a.full_name,'') LIKE ? OR IFNULL(pe.program_code,'') LIKE ?)"
        )
        params.extend([f"%{q}%"] * 4)
    sql += " ORDER BY pe.id DESC"
    rows = []
    for r in cur.execute(sql, params).fetchall():
        code = (r[4] or r[5] or r[6] or "").strip()
        stage = r[14] or "learner"
        rows.append({
            "id": r[0],
            "application_id": r[0],
            "student_id": r[15] or None,
            "student_code": code,
            "candidate_code": candidate_code_of(r[0], r[1]),
            "full_name": r[2] or "",
            "enrolled_at": r[7] or r[8] or "",
            "program_code": r[3] or "",
            "cccd": r[10] or "",
            "email": r[11] or "",
            "phone": r[12] or "",
            "cfvg_app_no": r[1] or candidate_code_of(r[0], r[1]),
            "person_id": r[13] or None,
            "academic_status_label": ACADEMIC_LABELS.get(r[9] or "", r[9] or ""),
            "person_stage": stage,
            "person_stage_label": stage_label(stage, enrolled=True),
        })
    return rows



def update_pre_enroll_file(conn, application_id: int, data: dict) -> dict:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    from learner_spine import ensure_learner_spine

    ensure_learner_spine(cur)
    row = cur.execute(
        "SELECT id FROM applications WHERE id = ?",
        (application_id,),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy hồ sơ ứng viên.")
    fields, params = [], []
    if "full_name" in data and (data.get("full_name") or "").strip():
        fields.append("full_name = ?")
        params.append((data.get("full_name") or "").strip())
    if "candidate_code" in data:
        fields.append("cfvg_app_no = ?")
        params.append((data.get("candidate_code") or "").strip())
    if "admit_decision" in data:
        fields.append("board_decision = ?")
        params.append((data.get("admit_decision") or "").strip())
    if not fields:
        raise ValueError("Không có trường để cập nhật")
    params.append(application_id)
    cur.execute(f"UPDATE applications SET {', '.join(fields)} WHERE id = ?", params)
    from person_profile import apply_person_edit

    apply_person_edit(cur, application_id, data)
    conn.commit()
    try:
        propagate_row_by_id(conn, "applications", application_id, data)
    except Exception:
        pass
    sync_candidate_link_tables(conn)
    items = list_pre_enroll_files(conn, ["*"])
    hit = next((x for x in items if x["id"] == application_id), None)
    return hit or {"id": application_id}


def update_enrolled_file(conn, row_id: int, data: dict) -> dict:
    cur = conn.cursor()
    ensure_admission_tables(cur)
    from learner_spine import ensure_learner_spine

    ensure_learner_spine(cur)
    try:
        from mba_ops import ensure_mba_tables

        ensure_mba_tables(cur)
    except Exception:
        pass
    app_id = None
    class_student_id = None
    app_row = cur.execute("SELECT id FROM applications WHERE id = ?", (row_id,)).fetchone()
    if app_row:
        app_id = int(app_row[0])
        cs = cur.execute(
            "SELECT id FROM class_students WHERE application_id = ? ORDER BY id DESC LIMIT 1",
            (app_id,),
        ).fetchone()
        if cs:
            class_student_id = int(cs[0])
    else:
        row = cur.execute(
            "SELECT id, application_id FROM class_students WHERE id = ?",
            (row_id,),
        ).fetchone()
        if not row:
            raise ValueError("Không tìm thấy hồ sơ theo học.")
        class_student_id = int(row[0])
        app_id = int(row[1]) if row[1] else None
    st_fields, st_params = [], []
    if class_student_id and "full_name" in data and (data.get("full_name") or "").strip():
        st_fields.append("full_name = ?")
        st_params.append((data.get("full_name") or "").strip())
    if class_student_id and "student_code" in data:
        st_fields.append("student_code = ?")
        st_params.append((data.get("student_code") or "").strip())
    if class_student_id and "enrolled_at" in data:
        st_fields.append("enrolled_at = ?")
        st_params.append((data.get("enrolled_at") or "").strip())
    if st_fields:
        st_params.append(class_student_id)
        cur.execute(
            f"UPDATE class_students SET {', '.join(st_fields)} WHERE id = ?", st_params
        )
    if app_id:
        app_fields, app_params = [], []
        if "full_name" in data and (data.get("full_name") or "").strip():
            app_fields.append("full_name = ?")
            app_params.append((data.get("full_name") or "").strip())
        if "candidate_code" in data:
            app_fields.append("cfvg_app_no = ?")
            app_params.append((data.get("candidate_code") or "").strip())
        if "student_code" in data:
            app_fields.append("student_code_mba = ?")
            app_params.append((data.get("student_code") or "").strip())
        if app_fields:
            app_params.append(app_id)
            cur.execute(
                f"UPDATE applications SET {', '.join(app_fields)} WHERE id = ?", app_params
            )
        if "student_code" in data and (data.get("student_code") or "").strip():
            cur.execute(
                "UPDATE program_enrollments SET learner_code = ? WHERE application_id = ?",
                ((data.get("student_code") or "").strip(), app_id),
            )
        from person_profile import apply_person_edit

        apply_person_edit(cur, app_id, data)
    conn.commit()
    try:
        if app_id:
            propagate_row_by_id(conn, "applications", app_id, data)
        else:
            propagate_row_by_id(conn, "class_students", class_student_id or row_id, data)
    except Exception:
        pass
    sync_candidate_link_tables(conn)
    items = list_enrolled_files(conn, ["*"])
    hit = next((x for x in items if x["id"] == (app_id or row_id)), None)
    return hit or {"id": app_id or row_id}


def enrich_sibling_programs(rows: list[dict]) -> list[dict]:
    by_key: dict[str, list[dict]] = {}
    for r in rows:
        key = normalize_cccd(r.get("cccd") or "") or (r.get("email") or "").strip().lower()
        if not key:
            r["sibling_programs"] = ""
            r["sibling_statuses"] = ""
            continue
        by_key.setdefault(key, []).append(r)
    for r in rows:
        key = normalize_cccd(r.get("cccd") or "") or (r.get("email") or "").strip().lower()
        sibs = [s for s in by_key.get(key, []) if s.get("id") != r.get("id")]
        r["sibling_programs"] = ", ".join(
            f"{s.get('program_code')}" for s in sibs if s.get("program_code")
        )
        r["sibling_statuses"] = ", ".join(
            f"{s.get('program_code')}:{(s.get('status') or '')}" for s in sibs
        )
    return rows
