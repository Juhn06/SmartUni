"""Configurable status catalogs (application, final result, lifecycle, fees…)."""
from __future__ import annotations

from typing import Any

# category -> list of (code, label_vi, label_en, sort_order)
DEFAULT_STATUS_SEED: dict[str, list[tuple[str, str, str, int]]] = {
    "application_status": [
        ("submitted", "Đã nộp", "Submitted", 10),
        ("approved_ts", "TS đã duyệt", "Admissions approved", 20),
        ("interview", "Chờ / đang PV", "Interview", 30),
        ("passed", "Đỗ", "Passed", 40),
        ("failed", "Trượt", "Failed", 50),
        ("paid", "Đã nộp phí", "Deposit verified", 60),
        ("official", "Nhập học chính thức", "Officially enrolled", 70),
        ("withdrawn", "Rút hồ sơ", "Withdrawn", 80),
    ],
    "final_result": [
        ("Pending", "Đang xử lý", "Pending", 10),
        ("Admitted", "Trúng tuyển", "Admitted", 20),
        ("Non-Admitted", "Không trúng tuyển", "Non-Admitted", 30),
        ("Waiting list", "Danh sách chờ", "Waiting list", 40),
    ],
    "admit_decision": [
        ("Chưa có", "Chưa có", "Not set", 10),
        ("Đã chấp thuận", "Đã chấp thuận", "Approved", 20),
        ("Không trúng tuyển", "Không trúng tuyển", "Not admitted", 30),
        ("Danh sách chờ", "Danh sách chờ", "Waiting list", 40),
    ],
    "lifecycle_status": [
        ("active", "Đang học", "Active", 10),
        ("reserved", "Bảo lưu", "Reserved / deferred", 20),
        ("on_leave", "Nghỉ học", "On leave", 30),
        ("withdrawn_program", "Xóa tên / rút CT", "Withdrawn from program", 40),
        ("graduated", "Tốt nghiệp", "Graduated", 50),
    ],
    "fee_status": [
        ("pending", "Chờ nộp", "Pending", 10),
        ("paid", "Đã nộp", "Paid", 20),
        ("unpaid", "Chưa TT", "Unpaid", 30),
        ("partial", "Một phần", "Partial", 40),
        ("due_soon", "Sắp hạn", "Due soon", 50),
        ("overdue", "Quá hạn", "Overdue", 60),
        ("waived", "Miễn phí", "Waived", 70),
    ],
    "payment_method": [
        ("bank_transfer", "Chuyển khoản", "Bank transfer", 10),
        ("card", "Nộp thẻ", "Card payment", 20),
        ("cash", "Tiền mặt", "Cash", 30),
        ("note", "Ghi chú", "Note / other", 40),
    ],
    "fee_waiver": [
        ("0", "Không miễn", "No waiver", 10),
        ("10", "Miễn 10%", "10% waiver", 20),
        ("50", "Miễn 50%", "50% waiver", 30),
        ("100", "Miễn 100%", "Full waiver", 40),
    ],
    "leave_type": [
        ("annual", "Phép năm", "Annual leave", 10),
        ("unpaid", "Không lương", "Unpaid leave", 20),
        ("personal", "Việc riêng", "Personal leave", 30),
        ("sick", "Ốm / điều trị", "Sick leave", 40),
        ("business", "Công tác", "Business trip", 50),
        ("maternity", "Thai sản", "Maternity / parental", 60),
        ("other", "Khác", "Other", 70),
    ],
    "crm_care_status": [
        ("potential", "Tiềm năng", "Potential", 10),
        ("interested", "Quan tâm", "Interested", 20),
        ("consulting", "Đang tư vấn", "Consulting", 30),
        ("applicant", "Ứng viên", "Applicant", 40),
        ("exam_prep", "Lập hồ sơ thi", "Exam file", 50),
        ("interviewed", "Đã tham gia phỏng vấn", "Interviewed", 60),
        ("admitted", "Trúng tuyển", "Admitted", 70),
        ("decided", "Quyết định", "Decided", 80),
        ("not_decided", "Không quyết định", "Not decided", 90),
        ("handed_ts", "Đã tạo hồ sơ TS", "Handed to admissions", 100),
    ],
    "crm_activity_type": [
        ("tu_van_rieng", "Tư vấn riêng", "Private consultation", 10),
        ("hoi_thao", "Hội thảo", "Workshop / seminar", 20),
        ("info_day", "Info Day / Open Day", "Info Day", 30),
        ("goi_dien", "Gọi điện", "Phone call", 40),
        ("email", "Email chăm sóc", "Care email", 50),
        ("gap_mat", "Gặp mặt", "In-person meeting", 60),
        ("khac", "Khác", "Other", 70),
    ],
}

CATEGORY_LABELS = {
    "application_status": ("Trạng thái hồ sơ", "Application status"),
    "final_result": ("Kết quả cuối", "Final result"),
    "admit_decision": ("Quyết định trúng tuyển", "Admission decision"),
    "lifecycle_status": ("Trạng thái học tập HV", "Student lifecycle"),
    "fee_status": ("Trạng thái phí", "Fee status"),
    "payment_method": ("Hình thức nộp tiền", "Payment method"),
    "fee_waiver": ("Mức miễn phí", "Fee waiver"),
    "leave_type": ("Loại nghỉ phép", "Leave type"),
    "crm_care_status": ("Trạng thái chăm sóc CRM", "CRM care status"),
    "crm_activity_type": ("Loại hoạt động CRM", "CRM activity type"),
}


def ensure_status_catalog_table(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS status_catalog ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "category TEXT NOT NULL, "
        "code TEXT NOT NULL, "
        "label_vi TEXT NOT NULL, "
        "label_en TEXT, "
        "sort_order INTEGER NOT NULL DEFAULT 0, "
        "is_active INTEGER NOT NULL DEFAULT 1, "
        "is_system INTEGER NOT NULL DEFAULT 0, "
        "UNIQUE(category, code))"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_status_catalog_cat "
        "ON status_catalog(category, sort_order, id)"
    )


def seed_status_catalog(conn) -> int:
    """Insert default rows if missing. Returns number of inserted rows."""
    cur = conn.cursor()
    ensure_status_catalog_table(cur)
    inserted = 0
    for category, rows in DEFAULT_STATUS_SEED.items():
        for code, label_vi, label_en, sort_order in rows:
            cur.execute(
                "SELECT id FROM status_catalog WHERE category = ? AND code = ?",
                (category, code),
            )
            if cur.fetchone():
                continue
            cur.execute(
                "INSERT INTO status_catalog "
                "(category, code, label_vi, label_en, sort_order, is_active, is_system) "
                "VALUES (?,?,?,?,?,1,1)",
                (category, code, label_vi, label_en, sort_order),
            )
            inserted += 1
    conn.commit()
    return inserted


def _row(r) -> dict:
    if r is None:
        return {}
    if hasattr(r, "keys"):
        return {k: r[k] for k in r.keys()}
    return {
        "id": r[0],
        "category": r[1],
        "code": r[2],
        "label_vi": r[3],
        "label_en": r[4],
        "sort_order": r[5],
        "is_active": r[6],
        "is_system": r[7],
    }


def list_status_catalog(
    conn,
    *,
    category: str | None = None,
    active_only: bool = False,
    lang: str = "vi",
) -> list[dict]:
    cur = conn.cursor()
    ensure_status_catalog_table(cur)
    sql = (
        "SELECT id, category, code, label_vi, label_en, sort_order, is_active, is_system "
        "FROM status_catalog WHERE 1=1"
    )
    params: list[Any] = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY category ASC, sort_order ASC, id ASC"
    cur.execute(sql, params)
    out = []
    for r in cur.fetchall():
        item = _row(r)
        item["label"] = (
            (item.get("label_en") or item.get("label_vi") or item.get("code"))
            if lang == "en"
            else (item.get("label_vi") or item.get("label_en") or item.get("code"))
        )
        out.append(item)
    return out


def status_options_map(conn, *, lang: str = "vi", active_only: bool = True) -> dict[str, list[dict]]:
    """category -> [{v, l}, ...] for frontend selects."""
    items = list_status_catalog(conn, active_only=active_only, lang=lang)
    by_cat: dict[str, list[dict]] = {}
    for it in items:
        by_cat.setdefault(it["category"], []).append(
            {"v": it["code"], "l": it["label"], "id": it["id"]}
        )
    return by_cat


def list_status_options(conn, category: str, *, lang: str = "vi") -> list[dict]:
    """Alias used by CRM / ops selects: [{v, l}, ...]."""
    return status_options_map(conn, lang=lang).get(category) or []


def status_label_map(conn, *, lang: str = "vi") -> dict[str, str]:
    """Flat code -> label (active + inactive) for display."""
    items = list_status_catalog(conn, active_only=False, lang=lang)
    return {it["code"]: it["label"] for it in items}


def create_status_item(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_status_catalog_table(cur)
    category = (data.get("category") or "").strip()
    code = (data.get("code") or "").strip()
    label_vi = (data.get("label_vi") or data.get("label") or "").strip()
    label_en = (data.get("label_en") or label_vi).strip()
    if category not in CATEGORY_LABELS:
        raise ValueError("Loại trạng thái không hợp lệ")
    if not code or not label_vi:
        raise ValueError("Cần mã và nhãn trạng thái")
    sort_order = int(data.get("sort_order") or 100)
    cur.execute(
        "INSERT INTO status_catalog "
        "(category, code, label_vi, label_en, sort_order, is_active, is_system) "
        "VALUES (?,?,?,?,?,1,0)",
        (category, code, label_vi, label_en, sort_order),
    )
    conn.commit()
    sid = cur.lastrowid
    cur.execute(
        "SELECT id, category, code, label_vi, label_en, sort_order, is_active, is_system "
        "FROM status_catalog WHERE id = ?",
        (sid,),
    )
    return _row(cur.fetchone())


def update_status_item(conn, item_id: int, data: dict) -> dict | None:
    cur = conn.cursor()
    ensure_status_catalog_table(cur)
    cur.execute(
        "SELECT id, category, code, label_vi, label_en, sort_order, is_active, is_system "
        "FROM status_catalog WHERE id = ?",
        (item_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    current = _row(row)
    label_vi = (data.get("label_vi") if "label_vi" in data else current["label_vi"]) or ""
    label_en = (data.get("label_en") if "label_en" in data else current["label_en"]) or label_vi
    sort_order = int(data["sort_order"]) if "sort_order" in data and data["sort_order"] is not None else current["sort_order"]
    is_active = current["is_active"]
    if "is_active" in data:
        is_active = 1 if data.get("is_active") in (1, True, "1", "true", "True") else 0
    # System codes: allow rename labels / active toggle, not code change
    code = current["code"]
    if not current.get("is_system") and data.get("code"):
        code = str(data.get("code")).strip() or code
    cur.execute(
        "UPDATE status_catalog SET code = ?, label_vi = ?, label_en = ?, sort_order = ?, is_active = ? "
        "WHERE id = ?",
        (code, str(label_vi).strip(), str(label_en).strip(), sort_order, is_active, item_id),
    )
    conn.commit()
    cur.execute(
        "SELECT id, category, code, label_vi, label_en, sort_order, is_active, is_system "
        "FROM status_catalog WHERE id = ?",
        (item_id,),
    )
    return _row(cur.fetchone())


def delete_status_item(conn, item_id: int) -> tuple[bool, str]:
    cur = conn.cursor()
    ensure_status_catalog_table(cur)
    cur.execute(
        "SELECT is_system, code FROM status_catalog WHERE id = ?",
        (item_id,),
    )
    row = cur.fetchone()
    if not row:
        return False, "Not found"
    if int(row[0] or 0) == 1:
        return False, "Không xóa được trạng thái hệ thống — hãy tắt (ẩn) thay vì xóa."
    cur.execute("DELETE FROM status_catalog WHERE id = ?", (item_id,))
    conn.commit()
    return True, "OK"


def allowed_codes(conn, category: str) -> set[str]:
    items = list_status_catalog(conn, category=category, active_only=True)
    return {it["code"] for it in items}


# pay_status / QA codes — never valid as application, CRM, materials, or enrollment-fee filters
WATCH_OR_QA_CODES = frozenset({"overdue", "due_soon", "overdue_count", "ok", "issue", "warn"})


def drop_watch_or_qa_status(status: str) -> str:
    """Ignore leaked ?status=overdue (and QA codes) on entities that are not tuition-watch."""
    s = (status or "").strip()
    if not s or s.lower() in WATCH_OR_QA_CODES:
        return ""
    return s
