"""
Bulk Excel import + annotated result file + bulk delete for ops list modules.

Each import row is validated independently. Results are written to the last
column ``Ket_qua_import`` and the annotated workbook is returned for download.
"""
from __future__ import annotations

import io
import re
from typing import Any, Callable

STATUS_COL = "Ket_qua_import"
STATUS_ALIASES = {STATUS_COL.lower(), "import_status", "ket_qua", "ket_qua_import", "status_import"}


def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v).strip()


def _row_vals(row: dict, headers: list[str]) -> dict:
    """Normalize a parsed row to declared headers (skip status column)."""
    out = {}
    for h in headers:
        if h.lower() in STATUS_ALIASES:
            continue
        # tolerate case / spacing variants
        if h in row:
            out[h] = row[h]
            continue
        found = None
        hl = h.lower()
        for k, v in row.items():
            if str(k).strip().lower() == hl:
                found = v
                break
        out[h] = found if found is not None else ""
    return out


def _parse_id(v: Any) -> int | None:
    s = _s(v)
    if not s:
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Entity specs
# ---------------------------------------------------------------------------

def _spec_asst(table: str, required: list[str], headers: list[str], sample: dict, guide: list[str]) -> dict:
    return {
        "kind": "table",
        "table": table,
        "required": required,
        "headers": headers,
        "sample": sample,
        "guide": guide,
        "sheet": "Data",
    }


IMPORT_SPECS: dict[str, dict] = {
    "asst-tasks": _spec_asst(
        "asst_tasks",
        ["title"],
        ["id", "title", "assignee", "department", "due_date", "status", "notes"],
        {
            "title": "Chuẩn bị báo cáo tuần",
            "assignee": "Nguyen Van A",
            "department": "tro_ly_bgd",
            "due_date": "2026-08-01",
            "status": "open",
            "notes": "",
        },
        ["status: open | doing | done | overdue", "Để trống id = tạo mới; có id = cập nhật."],
    ),
    "asst-calendar": _spec_asst(
        "asst_calendar",
        ["title"],
        ["id", "title", "cal_type", "starts_at", "ends_at", "location", "owner", "attendees", "status", "notes"],
        {
            "title": "Họp BGD",
            "cal_type": "meeting",
            "starts_at": "2026-08-01 09:00",
            "ends_at": "2026-08-01 11:00",
            "location": "P. họp HN",
            "owner": "Trợ lý BGD",
            "status": "confirmed",
        },
        ["cal_type: bgd | training | meeting | event | faculty | leave"],
    ),
    "asst-intl-faculty": _spec_asst(
        "asst_intl_faculty",
        ["full_name"],
        [
            "id", "full_name", "gender", "nationality", "organization", "title", "email", "phone",
            "passport_no", "passport_expiry", "visa_status", "arrival_date", "departure_date",
            "hotel_name", "program_code", "course_name", "teach_dates", "status", "notes",
        ],
        {
            "full_name": "Jean Dupont",
            "nationality": "FR",
            "email": "jean@example.com",
            "program_code": "MBA",
            "visa_status": "pending",
            "status": "preparing",
        },
        ["program_code: MBA | MMS | MSCM"],
    ),
    "asst-intl-students": _spec_asst(
        "asst_intl_students",
        ["full_name", "cccd"],
        [
            "id", "full_name", "cccd", "nationality", "email", "phone", "program_code", "cohort",
            "student_type", "direction", "home_university", "partner_university",
            "visa_status", "arrival_date", "departure_date", "notes",
        ],
        {
            "full_name": "Maria Silva",
            "cccd": "079123456789",
            "nationality": "PT",
            "program_code": "MBA",
            "student_type": "exchange",
            "direction": "incoming",
            "visa_status": "pending",
        },
        ["cccd bắt buộc. Trùng CCCD = cập nhật.", "direction: incoming | outgoing", "student_type: exchange | intl_degree"],
    ),
    "asst-director-fr": _spec_asst(
        "asst_director_fr",
        ["full_name"],
        [
            "id", "full_name", "relation", "nationality", "passport_no", "passport_expiry",
            "visa_info", "work_permit", "residence_reg", "insurance", "doc_expiry", "status", "notes",
        ],
        {"full_name": "Directeur FR", "relation": "self", "nationality": "FR", "status": "valid"},
        ["relation: self | spouse | child"],
    ),
    "asst-documents": _spec_asst(
        "asst_documents",
        ["subject"],
        [
            "id", "doc_direction", "doc_no", "doc_date", "sender_or_receiver", "subject",
            "doc_type", "urgency", "handler", "due_date", "status", "notes",
        ],
        {
            "doc_direction": "in",
            "doc_no": "CV-001",
            "subject": "Công văn mẫu",
            "status": "received",
        },
        ["doc_direction: in | out | seal"],
    ),
    "asst-procurement": _spec_asst(
        "asst_procurement",
        ["item_name"],
        [
            "id", "category", "item_name", "quantity", "unit_price", "amount",
            "requester", "supplier", "request_date", "status", "invoice_no", "notes",
        ],
        {
            "category": "stationery",
            "item_name": "Giấy A4",
            "quantity": 10,
            "unit_price": 50000,
            "status": "requested",
        },
        ["category: stationery | water | taxi | other"],
    ),
    "asst-payments": _spec_asst(
        "asst_payments",
        ["beneficiary"],
        [
            "id", "cost_type", "beneficiary", "program_code", "supplier", "amount",
            "invoice_no", "invoice_date", "payment_status", "payment_date", "month_key", "notes",
        ],
        {
            "cost_type": "flight",
            "beneficiary": "Airline VN",
            "amount": 12000000,
            "payment_status": "unpaid",
            "month_key": "2026-08",
        },
        ["cost_type: flight | taxi | stationery | water | other"],
    ),
    "asst-weekly-reports": _spec_asst(
        "asst_weekly_reports",
        ["week_label"],
        [
            "id", "week_label", "week_start", "done_summary", "ongoing_summary",
            "next_week_plan", "issues", "neu_coordination", "status",
        ],
        {
            "week_label": "Tuần 32/2026",
            "week_start": "2026-08-03",
            "done_summary": "Hoàn thành...",
            "status": "draft",
        },
        ["status: draft | review | approved | sent"],
    ),
    "asst-leave": _spec_asst(
        "asst_leave",
        ["employee_name"],
        [
            "id", "employee_name", "department", "leave_type", "start_date", "end_date",
            "days", "reason", "substitute", "handover", "approver", "status",
        ],
        {
            "employee_name": "Nguyen Van A",
            "leave_type": "annual",
            "start_date": "2026-08-10",
            "end_date": "2026-08-12",
            "days": 3,
            "status": "pending",
        },
        ["leave_type: annual | unpaid | personal | business"],
    ),
    "marcom-leads": _spec_asst(
        "marcom_leads",
        ["full_name", "cccd"],
        [
            "id", "full_name", "cccd", "email", "phone", "occupation", "company",
            "program_interest", "source", "status", "notes",
        ],
        {
            "full_name": "Lead Mau",
            "cccd": "001234567890",
            "email": "lead@example.com",
            "phone": "0901111222",
            "program_interest": "MBA",
            "source": "event",
            "status": "new",
        },
        ["cccd bắt buộc. Trùng CCCD = cập nhật Hồ sơ → Thí sinh → Người học.", "status: new | nurturing | handed | closed"],
    ),
    "crm-source": {
        "kind": "crm_source",
        "headers": [
            "Ngày tiếp nhận / Date of enquiry",
            "Chuyên viên / PIC",
            "Họ tên / Fullname",
            "Tình trạng",
            "Mức độ quan tâm / Level",
            "Chương trình / Program",
            "Năm / Year",
            "Email",
            "Số điện thoại / Mobile No.",
            "Nhắc lịch / Follow up Date",
            "Liên hệ gần nhất / Latest Contact",
            "Chi tiết / Note",
            "Sự kiện tham gia / Events",
            "Kênh / Channel",
            "Chi tiết kênh 1 / Source 1",
            "Chi tiết kênh 2 / Source 2",
        ],
        "required": ["Họ tên / Fullname"],
        "sample": {
            "Họ tên / Fullname": "Nguyen Van A",
            "Chuyên viên / PIC": "Giao",
            "Mức độ quan tâm / Level": "Warm",
            "Chương trình / Program": "MBA",
            "Năm / Year": "2026",
            "Kênh / Channel": "FB",
            "Chi tiết kênh 1 / Source 1": "FB Ib",
            "Chi tiết / Note": "1. Gọi lại chiều nay",
        },
        "guide": [
            "Đúng cột file Enquiry (Database): chăm sóc ứng viên, không thêm cột ngoài file.",
            "Mức độ quan tâm: Hot, Warm, Cold, Email, Inactive, Prospect, Move to Application.",
            "Tình trạng: Người quan tâm, Ứng viên, Học viên, Cựu học viên.",
            "Trùng email / số điện thoại / họ tên + năm = cập nhật.",
        ],
        "sheet": "Database",
    },
    "marcom-campaigns": _spec_asst(
        "marcom_campaigns",
        ["title"],
        [
            "id", "title", "period_start", "period_end", "channel", "program_codes",
            "budget_planned", "budget_spent", "kpi_notes", "status", "report_summary",
        ],
        {
            "title": "Chiến dịch Open Day",
            "channel": "online",
            "program_codes": "MBA,MMS",
            "status": "planned",
        },
        ["channel: online | offline | hybrid"],
    ),
    "marcom-events": _spec_asst(
        "marcom_events",
        ["title"],
        [
            "id", "title", "event_type", "event_date", "location", "program_codes",
            "content", "speakers", "guest_list", "status", "budget", "notes",
        ],
        {
            "title": "Open Day MBA",
            "event_type": "workshop",
            "event_date": "2026-09-01",
            "location": "HN",
            "status": "planned",
        },
        ["event_type: workshop | open_day | webinar | other"],
    ),
    "marcom-assets": _spec_asst(
        "marcom_assets",
        ["title"],
        ["id", "title", "asset_type", "tags", "program_codes", "used_for", "notes"],
        {"title": "Banner Open Day", "asset_type": "image", "tags": "mba,openday"},
        ["asset_type: image | video | doc | other"],
    ),
    "applications": {
        "kind": "applications",
        "headers": [
            "full_name", "cccd", "program_code", "cfvg_app_no", "campus", "gender", "dob",
            "email", "phone", "university", "degree_major", "study_duration", "degree_grade",
            "experience_years", "credit_hours", "english_cert", "company",
            "lead_source", "checklist_status", "degree_verified", "english_verified",
            "neu_packet_ready", "interview_date", "final_result", "notes",
            "intake_session", "student_code_mba", "eco_background", "master_level",
            "bachelor_start_year", "bachelor_grad_year", "job_title", "management_years",
            "english_note", "naric_status", "naric_note", "exam_eligible_flag",
            "other_achievements", "interview_score", "interview_jury1", "interview_jury2",
            "interview_jury3", "written_score", "written_gk", "written_mle", "avg_score",
            "confirmation_status", "board_decision", "exam_format", "exam_board",
        ],
        "required": ["full_name", "cccd"],
        "sample": {
            "full_name": "Bùi Diệp Anh",
            "cccd": "001201012345",
            "program_code": "MBA",
            "cfvg_app_no": "",
            "campus": "Hanoi",
            "gender": "F",
            "dob": "2001-12-18",
            "email": "diepanhh.dvn@gmail.com",
            "phone": "705111520",
            "university": "NEU",
            "degree_major": "Marketing",
            "english_cert": "IELTS 6.5",
            "company": "Techcombank",
            "intake_session": "August",
            "student_code_mba": "HN34MBA001",
            "eco_background": "Yes",
            "job_title": "Digital Marketing Staff",
            "avg_score": 14.43,
            "interview_score": 15.33,
            "written_score": 13.53,
            "board_decision": "Trúng tuyển",
            "lead_source": "event",
            "checklist_status": "issued",
            "degree_verified": "pending",
            "english_verified": "yes",
            "neu_packet_ready": "pending",
        },
        "guide": [
            "cccd bắt buộc. Trùng CCCD + chương trình = cập nhật Hồ sơ → Thí sinh → Người học → Học.",
            "program_code: MBA | MMS | MSCM",
            "cfvg_app_no hoặc student_code_mba trùng sẽ cập nhật hồ sơ hiện có; trống = luôn tạo mới.",
            "MBA34: có thể import header tiếng Việt từ file 1.2.2 Student list (Session, Student code, Họ Tên…).",
            "checklist_status: pending | issued | confirmed | incomplete",
            "degree_verified / english_verified / neu_packet_ready: pending | yes | no",
            "lead_source: facebook | zalo | call | event | marcom | other",
            "intake_session: May | August",
        ],
        "sheet": "Candidates",
    },
    "rounds": {
        "kind": "rounds",
        "headers": [
            "id", "code", "name", "programs", "cohort", "year",
            "apply_due_date", "exam_date", "result_date",
            "intake", "exam_timeline", "interview_timeline", "status",
        ],
        "required": ["code", "name"],
        "sample": {
            "code": "TS2026-2",
            "name": "Đợt 2/2026",
            "programs": "MBA,MMS,MSCM",
            "cohort": "K35",
            "year": 2026,
            "apply_due_date": "2026-04-15",
            "exam_date": "2026-05-10",
            "result_date": "2026-05-25",
            "intake": "August",
            "status": "open",
        },
        "guide": ["programs: danh sách CT cách nhau bởi dấu phẩy"],
        "sheet": "Data",
    },
    "classes": {
        "kind": "classes",
        "headers": ["id", "name", "program_code", "cohort_year", "version_code", "status"],
        "required": ["name", "program_code"],
        "sample": {"name": "MBA K35", "program_code": "MBA", "cohort_year": 2026, "version_code": "MBA_K35"},
        "guide": ["program_code bắt buộc; version_code tùy chọn (map program_versions)."],
        "sheet": "Data",
    },
    "faculty": {
        "kind": "faculty",
        "headers": [
            "id", "full_name", "role_type", "degree", "title", "organization", "specialty",
            "teachable_courses", "email", "phone", "nationality", "passport_no",
            "bank_account", "contract_status", "contract_no", "notes",
        ],
        "required": ["full_name"],
        "sample": {
            "full_name": "Dr. Example",
            "role_type": "lecturer",
            "email": "gv@example.com",
            "specialty": "Marketing",
        },
        "guide": ["role_type: lecturer | expert | both"],
        "sheet": "Data",
    },
    "alumni": {
        "kind": "alumni",
        "headers": ["id", "full_name", "cccd", "program_code", "cohort", "class_name", "email", "phone", "company", "activity_keywords"],
        "required": ["full_name", "cccd"],
        "sample": {
            "full_name": "Alumni Mau",
            "cccd": "001201012345",
            "program_code": "MBA",
            "cohort": "K30",
            "email": "alumni@example.com",
            "company": "ABC",
        },
        "guide": ["cccd bắt buộc. Trùng CCCD = cập nhật (Hồ sơ → Thí sinh → Người học → Học).", "program_code mặc định MMS nếu trống."],
        "sheet": "Data",
    },
    "alumni-events": {
        "kind": "alumni_events",
        "headers": ["id", "title", "event_date", "location", "program_filter", "status", "description"],
        "required": ["title"],
        "sample": {
            "title": "Alumni Meetup",
            "event_date": "2026-10-01",
            "location": "HN",
            "program_filter": "MBA",
            "status": "planned",
        },
        "guide": [],
        "sheet": "Data",
    },
    "study-groups": {
        "kind": "study_groups",
        "headers": ["id", "name", "class_id", "member_names", "status"],
        "required": ["name", "class_id"],
        "sample": {"name": "Nhóm A", "class_id": 1, "member_names": "HV1, HV2", "status": "active"},
        "guide": ["class_id phải tồn tại trong danh sách lớp."],
        "sheet": "Data",
    },
    "exams": {
        "kind": "exams",
        "headers": ["id", "title", "class_id", "exam_date", "exam_type", "room", "status", "notes"],
        "required": ["title", "class_id"],
        "sample": {
            "title": "Thi cuối kỳ",
            "class_id": 1,
            "exam_date": "2026-12-15",
            "exam_type": "final",
            "room": "P.201",
            "status": "planned",
        },
        "guide": ["exam_type: final | midterm | retake"],
        "sheet": "Data",
    },
    "students": {
        "kind": "students",
        "headers": [
            "cccd", "full_name", "email", "phone", "student_code", "program_code",
            "lifecycle_status", "scholarship_type", "company", "job_title",
        ],
        "required": ["full_name", "cccd"],
        "sample": {
            "cccd": "001201012345",
            "full_name": "Nguyen Van A",
            "email": "hv@example.com",
            "phone": "0901111222",
            "student_code": "HN34MBA001",
            "program_code": "MBA",
            "lifecycle_status": "active",
        },
        "guide": [
            "cccd bắt buộc. Trùng CCCD = cập nhật Hồ sơ → Thí sinh → Người học → Học.",
            "lifecycle_status: active | reserved | on_leave | withdrawn_program | graduated",
        ],
        "sheet": "Data",
    },
    "evaluations": {
        "kind": "evaluations",
        "headers": ["id", "title", "class_id", "response_pct", "status", "summary"],
        "required": ["class_id"],
        "sample": {"title": "Đánh giá khóa học", "class_id": 1, "response_pct": 0, "status": "open"},
        "guide": ["class_id bắt buộc."],
        "sheet": "Data",
    },
}


# delete_path (frontend) → SQL table
DELETE_PATH_TABLE = {
    "asst/tasks": "asst_tasks",
    "asst/calendar": "asst_calendar",
    "asst/intl-faculty": "asst_intl_faculty",
    "asst/intl-students": "asst_intl_students",
    "asst/director-fr": "asst_director_fr",
    "asst/documents": "asst_documents",
    "asst/procurement": "asst_procurement",
    "asst/payments": "asst_payments",
    "asst/weekly-reports": "asst_weekly_reports",
    "asst/leave": "asst_leave",
    "marcom/leads": "marcom_leads",
    "marcom/campaigns": "marcom_campaigns",
    "marcom/events": "marcom_events",
    "marcom/assets": "marcom_assets",
    "crm/source": "crm_source_profiles",
    "crm/activities": "crm_activities",
    "crm/reminders": "crm_reminders",
    "crm-source": "crm_source_profiles",
    "crm-activities": "crm_activities",
    "crm-reminders": "crm_reminders",
    "faculty": "faculty",
    "alumni": "alumni_members",
    "alumni-events": "alumni_events",
    "study-groups": "study_groups",
    "exams": "exam_schedules",
    "evaluations": "course_evaluations",
    "classes": "class_groups",
    "rounds": "admission_rounds",
    "applications": "applications",
    "admission-doc-types": "admission_doc_types",
    "interviews": "interview_sessions",
    "teaching-assignments": "teaching_assignments",
    "program-versions": "program_versions",
    "courses": "courses",
    "thesis-records": "thesis_records",
}


def get_spec(entity: str) -> dict:
    spec = IMPORT_SPECS.get(entity)
    if not spec:
        raise ValueError(f"Unknown import entity: {entity}")
    return spec


def build_import_template(entity: str) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    spec = get_spec(entity)
    headers = list(spec["headers"])
    wb = Workbook()
    ws = wb.active
    ws.title = (spec.get("sheet") or "Data")[:31]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(1, col, h)
        cell.font = Font(bold=True)
    # Status column header (empty in template — filled on import result)
    ws.cell(1, len(headers) + 1, STATUS_COL).font = Font(bold=True)
    sample = spec.get("sample") or {}
    for col, h in enumerate(headers, 1):
        ws.cell(2, col, sample.get(h, ""))
    ws2 = wb.create_sheet("Huong_dan")
    ws2["A1"] = "Giữ nguyên dòng tiêu đề (row 1). Điền dữ liệu từ row 2."
    ws2["A2"] = f"Cột cuối «{STATUS_COL}» sẽ được hệ thống ghi kết quả sau khi Import."
    ws2["A3"] = "Để trống id = tạo mới; điền id hiện có = cập nhật (nếu hỗ trợ)."
    for i, line in enumerate(spec.get("guide") or [], start=4):
        ws2[f"A{i}"] = line
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _ensure_tables(conn) -> None:
    cur = conn.cursor()
    from asst_ops import ensure_asst_tables
    from marcom_ops import ensure_marcom_tables
    from ops_crud import ensure_extra_ops_tables
    from ops_data import ensure_ops_tables

    ensure_asst_tables(cur)
    ensure_marcom_tables(cur)
    ensure_extra_ops_tables(cur)
    ensure_ops_tables(cur)
    try:
        from mba_ops import ensure_mba_tables

        ensure_mba_tables(cur)
    except Exception:
        pass
    try:
        from coord_ops import ensure_coord_tables

        ensure_coord_tables(cur)
    except Exception:
        pass
    try:
        from crm_ops import ensure_crm_tables

        ensure_crm_tables(cur)
    except Exception:
        pass


def _table_columns(conn, table: str) -> set[str]:
    cur = conn.cursor()
    rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


PERSON_CCCD_TABLES = {"marcom_leads", "asst_intl_students", "alumni_members"}

PERSONAL_SYNC_FIELDS = {
    "full_name", "email", "phone", "cccd", "gender", "dob", "nationality",
    "address", "passport", "company", "job_title",
}
BUSINESS_CONTEXT_FIELDS = {
    "round_id", "round_code", "program_code", "course_code", "transaction_code",
    "fee_type", "class_id", "txn_code",
}


def _cccd_eq_sql(alias: str = "") -> str:
    col = f"{alias}.cccd" if alias else "cccd"
    return f"REPLACE(REPLACE(REPLACE(UPPER(IFNULL({col},'')),' ',''),'-',''),'.','')"


def _require_cccd(raw: dict) -> str:
    from admission_ops import normalize_cccd

    cccd = _s(raw.get("cccd") or raw.get("CCCD") or raw.get("Căn cước công dân"))
    if not normalize_cccd(cccd):
        raise ValueError("Thiếu Căn cước công dân (cccd)")
    return cccd


def _propagate_cccd(conn, cccd: str, data: dict) -> None:
    try:
        from admission_ops import propagate_person_update_by_cccd

        propagate_person_update_by_cccd(conn, cccd, data)
    except Exception:
        pass


def _upsert_table(conn, table: str, required: list[str], headers: list[str], raw: dict) -> str:
    from ops_crud import asst_insert

    data = _row_vals(raw, headers)
    cols = _table_columns(conn, table)
    payload = {}
    for k, v in data.items():
        if k == "id" or k not in cols:
            continue
        if isinstance(v, str) and v == "":
            continue
        payload[k] = v if not isinstance(v, str) else v
    # stringify numbers that came as float from excel for text cols — keep as-is
    for k in list(payload.keys()):
        if isinstance(payload[k], float) and payload[k] == int(payload[k]):
            # keep int for REAL/INTEGER friendly
            payload[k] = int(payload[k])

    rid = _parse_id(data.get("id") or raw.get("id"))
    for req in required:
        val = payload.get(req)
        if val is None or (isinstance(val, str) and not str(val).strip()):
            if not _s(data.get(req)):
                raise ValueError(f"Thiếu trường bắt buộc: {req}")

    cur = conn.cursor()
    cccd_val = ""
    if "cccd" in cols or "cccd" in required or table in PERSON_CCCD_TABLES:
        from admission_ops import normalize_cccd

        cccd_val = _s(payload.get("cccd") or data.get("cccd") or raw.get("Căn cước công dân"))
        if not normalize_cccd(cccd_val):
            raise ValueError("Thiếu Căn cước công dân (cccd)")
        payload["cccd"] = cccd_val
        if table == "asst_intl_students":
            passport = _s(payload.get("passport") or raw.get("passport") or raw.get("Hộ chiếu"))
            nationality = _s(payload.get("nationality") or raw.get("nationality") or "").lower()
            foreign = nationality and nationality not in ("vn", "viet nam", "vietnam", "việt nam")
            if foreign and not passport:
                raise ValueError("Người nước ngoài: cần hộ chiếu, không bịa CCCD")
        if not rid:
            hit = cur.execute(
                f"SELECT id FROM {table} WHERE {_cccd_eq_sql()} = ?",
                (normalize_cccd(cccd_val),),
            ).fetchone()
            if hit:
                rid = int(hit[0])

    if rid:
        exists = cur.execute(f"SELECT id FROM {table} WHERE id = ?", (rid,)).fetchone()
        if not exists:
            raise ValueError(f"Không tìm thấy bản ghi id={rid}")
        # CCCD match: only sync personal fields unless business context also matches
        if cccd_val:
            ctx_ok = True
            existing_row = cur.execute(f"SELECT * FROM {table} WHERE id = ?", (rid,)).fetchone()
            existing_keys = [d[0] for d in cur.description]
            existing = dict(zip(existing_keys, existing_row)) if existing_row else {}
            for ck in BUSINESS_CONTEXT_FIELDS:
                if ck in payload and ck in existing and str(payload[ck] or "").strip():
                    if str(existing.get(ck) or "").strip() and str(existing.get(ck)) != str(payload[ck]):
                        ctx_ok = False
                        break
            if not ctx_ok:
                payload = {k: v for k, v in payload.items() if k in PERSONAL_SYNC_FIELDS}
        if not payload:
            raise ValueError("Không có cột nào để cập nhật")
        sets = ", ".join(f"{k} = ?" for k in payload)
        cur.execute(f"UPDATE {table} SET {sets} WHERE id = ?", [*payload.values(), rid])
        conn.commit()
        if cccd_val:
            _propagate_cccd(conn, cccd_val, payload)
        return f"OK — cập nhật id={rid}"

    # insert via asst_insert (works for asst/marcom tables with defaults)
    if table.startswith("asst_") or table.startswith("marcom_"):
        row = asst_insert(conn, table, payload, required)
        if cccd_val:
            _propagate_cccd(conn, cccd_val, payload)
        return f"OK — tạo mới id={row.get('id')}"

    # generic insert for other tables
    if not payload:
        raise ValueError("Không có dữ liệu")
    keys = list(payload.keys())
    cur.execute(
        f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' * len(keys))})",
        [payload[k] for k in keys],
    )
    conn.commit()
    if cccd_val:
        _propagate_cccd(conn, cccd_val, payload)
    return f"OK — tạo mới id={cur.lastrowid}"


def _import_applications_row(conn, raw: dict, round_id: int | None) -> str:
    from coord_ops import import_candidates

    name = _s(raw.get("full_name") or raw.get("Fullname"))
    cccd = _s(raw.get("cccd") or raw.get("CCCD") or raw.get("Căn cước công dân"))
    if not name:
        raise ValueError("Thiếu full_name")
    if not cccd:
        raise ValueError("Thiếu Căn cước công dân (cccd)")
    # Reuse batch helper for one row
    result = import_candidates(conn, [raw], round_id=round_id)
    if result.get("skipped_no_cccd"):
        raise ValueError("Thiếu Căn cước công dân (cccd)")
    _propagate_cccd(conn, cccd, {
        "full_name": name,
        "cccd": cccd,
        "email": _s(raw.get("email")),
        "phone": _s(raw.get("phone")),
        "company": _s(raw.get("company")),
    })
    if result.get("updated"):
        return "OK — cập nhật (khớp CCCD + chương trình)"
    if result.get("created"):
        return "OK — tạo mới"
    raise ValueError("Bỏ qua (không có thay đổi)")


def _import_rounds_row(conn, raw: dict, headers: list[str]) -> str:
    from ops_crud import create_admission_round

    data = _row_vals(raw, headers)
    rid = _parse_id(data.get("id"))
    cur = conn.cursor()
    if rid:
        exists = cur.execute("SELECT id FROM admission_rounds WHERE id = ?", (rid,)).fetchone()
        if not exists:
            raise ValueError(f"Không tìm thấy đợt id={rid}")
        allowed = {
            "code", "name", "programs", "year", "intake", "exam_timeline", "interview_timeline",
            "status", "cohort", "apply_due_date", "exam_date", "result_date",
        }
        payload = {k: data[k] for k in allowed if _s(data.get(k)) != "" or data.get(k) == 0}
        if "year" in payload:
            payload["year"] = int(payload["year"])
        if not payload:
            raise ValueError("Không có cột để cập nhật")
        sets = ", ".join(f"{k} = ?" for k in payload)
        cur.execute(f"UPDATE admission_rounds SET {sets} WHERE id = ?", [*payload.values(), rid])
        conn.commit()
        return f"OK — cập nhật id={rid}"
    row = create_admission_round(conn, data)
    return f"OK — tạo mới id={row['id']}"


def _import_classes_row(conn, raw: dict, headers: list[str]) -> str:
    from ops_crud import create_class_group

    data = _row_vals(raw, headers)
    rid = _parse_id(data.get("id"))
    cur = conn.cursor()
    if rid:
        exists = cur.execute("SELECT id FROM class_groups WHERE id = ?", (rid,)).fetchone()
        if not exists:
            raise ValueError(f"Không tìm thấy lớp id={rid}")
        allowed = {"name", "program_code", "cohort_year", "status"}
        payload = {}
        for k in allowed:
            if _s(data.get(k)) != "" or data.get(k) == 0:
                payload[k] = data[k]
        if "program_code" in payload:
            payload["program_code"] = _s(payload["program_code"]).upper()
        if "cohort_year" in payload:
            payload["cohort_year"] = int(payload["cohort_year"])
        if not payload:
            raise ValueError("Không có cột để cập nhật")
        sets = ", ".join(f"{k} = ?" for k in payload)
        cur.execute(f"UPDATE class_groups SET {sets} WHERE id = ?", [*payload.values(), rid])
        conn.commit()
        return f"OK — cập nhật id={rid}"
    row = create_class_group(conn, data)
    return f"OK — tạo mới id={row['id']}"


def _import_faculty_row(conn, raw: dict, headers: list[str]) -> str:
    from ops_crud import create_faculty, update_faculty

    data = _row_vals(raw, headers)
    rid = _parse_id(data.get("id"))
    if rid:
        update_faculty(conn, rid, data)
        return f"OK — cập nhật id={rid}"
    row = create_faculty(conn, data)
    return f"OK — tạo mới id={row['id']}"


def _import_alumni_row(conn, raw: dict, headers: list[str]) -> str:
    from admission_ops import normalize_cccd
    from ops_crud import create_alumni

    data = _row_vals(raw, headers)
    cccd = _require_cccd(data)
    data["cccd"] = cccd
    rid = _parse_id(data.get("id"))
    cur = conn.cursor()
    cols = _table_columns(conn, "alumni_members")
    if "cccd" in cols and not rid:
        hit = cur.execute(
            f"SELECT id FROM alumni_members WHERE {_cccd_eq_sql()} = ?",
            (normalize_cccd(cccd),),
        ).fetchone()
        if hit:
            rid = int(hit[0])
    if rid:
        exists = cur.execute("SELECT id FROM alumni_members WHERE id = ?", (rid,)).fetchone()
        if not exists:
            raise ValueError(f"Không tìm thấy alumni id={rid}")
        allowed = {
            "full_name", "program_code", "cohort", "class_name",
            "email", "phone", "company", "activity_keywords", "cccd",
        }
        payload = {k: data[k] for k in allowed if k in cols and _s(data.get(k)) != ""}
        if not payload:
            raise ValueError("Không có cột để cập nhật")
        sets = ", ".join(f"{k} = ?" for k in payload)
        cur.execute(f"UPDATE alumni_members SET {sets} WHERE id = ?", [*payload.values(), rid])
        conn.commit()
        _propagate_cccd(conn, cccd, payload)
        return f"OK — cập nhật id={rid}"
    row = create_alumni(conn, data)
    _propagate_cccd(conn, cccd, data)
    return f"OK — tạo mới id={row['id']}"


def _import_alumni_events_row(conn, raw: dict, headers: list[str]) -> str:
    from ops_crud import create_alumni_event

    data = _row_vals(raw, headers)
    rid = _parse_id(data.get("id"))
    cur = conn.cursor()
    if rid:
        exists = cur.execute("SELECT id FROM alumni_events WHERE id = ?", (rid,)).fetchone()
        if not exists:
            raise ValueError(f"Không tìm thấy sự kiện id={rid}")
        allowed = {"title", "event_date", "location", "program_filter", "status", "description"}
        payload = {k: data[k] for k in allowed if _s(data.get(k)) != ""}
        if not payload:
            raise ValueError("Không có cột để cập nhật")
        sets = ", ".join(f"{k} = ?" for k in payload)
        cur.execute(f"UPDATE alumni_events SET {sets} WHERE id = ?", [*payload.values(), rid])
        conn.commit()
        return f"OK — cập nhật id={rid}"
    row = create_alumni_event(conn, data)
    return f"OK — tạo mới id={row['id']}"


def _import_study_groups_row(conn, raw: dict, headers: list[str]) -> str:
    from ops_crud import create_study_group

    data = _row_vals(raw, headers)
    rid = _parse_id(data.get("id"))
    cur = conn.cursor()
    if rid:
        exists = cur.execute("SELECT id FROM study_groups WHERE id = ?", (rid,)).fetchone()
        if not exists:
            raise ValueError(f"Không tìm thấy nhóm id={rid}")
        allowed = {"name", "class_id", "member_names", "status", "course_id"}
        payload = {}
        for k in allowed:
            if _s(data.get(k)) != "" or data.get(k) == 0:
                payload[k] = int(data[k]) if k in ("class_id", "course_id") else data[k]
        if not payload:
            raise ValueError("Không có cột để cập nhật")
        sets = ", ".join(f"{k} = ?" for k in payload)
        cur.execute(f"UPDATE study_groups SET {sets} WHERE id = ?", [*payload.values(), rid])
        conn.commit()
        return f"OK — cập nhật id={rid}"
    if not _parse_id(data.get("class_id")):
        raise ValueError("Thiếu class_id")
    data["class_id"] = int(float(data["class_id"]))
    row = create_study_group(conn, data)
    return f"OK — tạo mới id={row['id']}"


def _import_exams_row(conn, raw: dict, headers: list[str]) -> str:
    from ops_crud import create_exam

    data = _row_vals(raw, headers)
    rid = _parse_id(data.get("id"))
    cur = conn.cursor()
    if rid:
        exists = cur.execute("SELECT id FROM exam_schedules WHERE id = ?", (rid,)).fetchone()
        if not exists:
            raise ValueError(f"Không tìm thấy lịch thi id={rid}")
        allowed = {"title", "class_id", "course_id", "exam_date", "exam_type", "room", "status", "notes"}
        payload = {}
        for k in allowed:
            if _s(data.get(k)) != "" or data.get(k) == 0:
                payload[k] = int(data[k]) if k in ("class_id", "course_id") else data[k]
        if not payload:
            raise ValueError("Không có cột để cập nhật")
        sets = ", ".join(f"{k} = ?" for k in payload)
        cur.execute(f"UPDATE exam_schedules SET {sets} WHERE id = ?", [*payload.values(), rid])
        conn.commit()
        return f"OK — cập nhật id={rid}"
    if not _parse_id(data.get("class_id")):
        raise ValueError("Thiếu class_id")
    data["class_id"] = int(float(data["class_id"]))
    row = create_exam(conn, data)
    return f"OK — tạo mới id={row['id']}"


def _import_evaluations_row(conn, raw: dict, headers: list[str]) -> str:
    from ops_crud import create_evaluation

    data = _row_vals(raw, headers)
    rid = _parse_id(data.get("id"))
    cur = conn.cursor()
    if rid:
        exists = cur.execute("SELECT id FROM course_evaluations WHERE id = ?", (rid,)).fetchone()
        if not exists:
            raise ValueError(f"Không tìm thấy đánh giá id={rid}")
        allowed = {"title", "class_id", "course_id", "response_pct", "status", "summary"}
        payload = {}
        for k in allowed:
            if _s(data.get(k)) != "" or data.get(k) == 0:
                if k in ("class_id", "course_id"):
                    payload[k] = int(data[k])
                elif k == "response_pct":
                    payload[k] = float(data[k])
                else:
                    payload[k] = data[k]
        if not payload:
            raise ValueError("Không có cột để cập nhật")
        sets = ", ".join(f"{k} = ?" for k in payload)
        cur.execute(f"UPDATE course_evaluations SET {sets} WHERE id = ?", [*payload.values(), rid])
        conn.commit()
        return f"OK — cập nhật id={rid}"
    if not _parse_id(data.get("class_id")):
        raise ValueError("Thiếu class_id")
    data["class_id"] = int(float(data["class_id"]))
    row = create_evaluation(conn, data)
    return f"OK — tạo mới id={row['id']}"


def _import_students_row(conn, raw: dict, headers: list[str]) -> str:
    from admission_ops import find_application_by_cccd_program, normalize_cccd

    data = _row_vals(raw, headers)
    cccd = _require_cccd(data)
    name = _s(data.get("full_name"))
    if not name:
        raise ValueError("Thiếu họ tên")
    prog = _s(data.get("program_code")).upper()
    cur = conn.cursor()
    app_id = None
    if prog:
        hit = find_application_by_cccd_program(cur, cccd, prog)
        if hit:
            app_id = int(hit[0])
    if not app_id:
        row = cur.execute(
            f"SELECT id FROM applications WHERE {_cccd_eq_sql()} = ? ORDER BY id DESC LIMIT 1",
            (normalize_cccd(cccd),),
        ).fetchone()
        app_id = int(row[0]) if row else None
    payload = {
        "full_name": name,
        "cccd": cccd,
        "email": _s(data.get("email")),
        "phone": _s(data.get("phone")),
        "company": _s(data.get("company")),
        "job_title": _s(data.get("job_title")),
        "student_code": _s(data.get("student_code")),
        "lifecycle_status": _s(data.get("lifecycle_status")),
        "scholarship_type": _s(data.get("scholarship_type")),
    }
    if app_id:
        sets, params = [], []
        for k in ("full_name", "email", "phone", "cccd"):
            if payload.get(k):
                sets.append(f"{k} = ?")
                params.append(payload[k])
        if _s(data.get("student_code")):
            try:
                sets.append("student_code_mba = ?")
                params.append(payload["student_code"])
            except Exception:
                pass
        if sets:
            params.append(app_id)
            cur.execute(f"UPDATE applications SET {', '.join(sets)} WHERE id = ?", params)
        cs_cols = _table_columns(conn, "class_students")
        cs_sets, cs_params = [], []
        mapping = {
            "full_name": "full_name",
            "email": "email",
            "phone": "phone",
            "cccd": "cccd",
            "student_code": "student_code",
            "lifecycle_status": "lifecycle_status",
            "scholarship_type": "scholarship_type",
            "company": "company",
            "job_title": "job_title",
        }
        for src, col in mapping.items():
            if col in cs_cols and payload.get(src):
                cs_sets.append(f"{col} = ?")
                cs_params.append(payload[src])
        if cs_sets:
            cs_params.append(app_id)
            cur.execute(
                f"UPDATE class_students SET {', '.join(cs_sets)} WHERE application_id = ?",
                cs_params,
            )
        conn.commit()
        _propagate_cccd(conn, cccd, payload)
        return f"OK — cập nhật thí sinh/HV theo CCCD (application #{app_id})"
    _propagate_cccd(conn, cccd, payload)
    return "OK — chưa có hồ sơ thí sinh; đã ghi nhận CCCD để cập nhật khi có hồ sơ"


def _import_crm_source_row(conn, raw: dict) -> str:
    from crm_ops import enquiry_payload_from_row, normalize_cccd, upsert_source_profile

    payload = enquiry_payload_from_row(raw)
    if not str(payload.get("full_name") or "").strip():
        raise ValueError("Thiếu họ tên")
    rid = _parse_id(payload.get("id") or raw.get("id"))
    if rid:
        payload["id"] = rid
    payload["source"] = (payload.get("source") or "excel").strip() or "excel"
    row = upsert_source_profile(conn, payload)
    cccd = normalize_cccd(payload.get("cccd") or "")
    if cccd:
        _propagate_cccd(conn, payload.get("cccd") or "", payload)
    return f"OK — {row.get('action')} id={row.get('id')}"


def _row_importer(entity: str, spec: dict, round_id: int | None) -> Callable[[Any, dict], str]:
    kind = spec["kind"]
    headers = list(spec["headers"])

    if kind == "table":
        table = spec["table"]
        required = list(spec["required"])

        def _fn(conn, raw):
            return _upsert_table(conn, table, required, headers, raw)

        return _fn

    if kind == "applications":
        def _fn(conn, raw):
            return _import_applications_row(conn, raw, round_id)

        return _fn

    if kind == "crm_source":
        def _fn(conn, raw):
            return _import_crm_source_row(conn, raw)

        return _fn

    mapping = {
        "rounds": _import_rounds_row,
        "classes": _import_classes_row,
        "faculty": _import_faculty_row,
        "alumni": _import_alumni_row,
        "alumni_events": _import_alumni_events_row,
        "study_groups": _import_study_groups_row,
        "exams": _import_exams_row,
        "evaluations": _import_evaluations_row,
        "students": _import_students_row,
    }
    fn = mapping.get(kind)
    if not fn:
        raise ValueError(f"Unsupported kind: {kind}")

    def _fn(conn, raw):
        return fn(conn, raw, headers)

    return _fn


def run_import_xlsx(conn, entity: str, file_bytes: bytes, *, round_id: int | None = None) -> tuple[bytes, dict]:
    """
    Import rows from xlsx; annotate last column with per-row status.
    Returns (result_xlsx_bytes, stats).
    """
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill

    spec = get_spec(entity)
    _ensure_tables(conn)
    importer = _row_importer(entity, spec, round_id)

    wb = load_workbook(io.BytesIO(file_bytes))
    ws = wb.active
    preferred = (spec.get("sheet") or "").strip().lower()
    if entity in ("crm-source", "crm/source"):
        for name in wb.sheetnames:
            n = (name or "").strip().lower()
            if n in ("database", "application list", "data") or (preferred and n == preferred):
                ws = wb[name]
                break
    # Header row — Enquiry/Application workbooks have merged titles above Fullname
    header_row = 1
    if entity in ("crm-source", "crm/source"):
        max_scan = min(ws.max_row or 1, 12)
        max_col = min(ws.max_column or 1, 80)
        for r in range(1, max_scan + 1):
            vals = [
                re.sub(r"\s+", " ", str(ws.cell(r, c).value or "").strip().lower())
                for c in range(1, max_col + 1)
            ]
            if any(("họ tên" in v) or ("fullname" in v) or (v in ("full name", "ho ten")) for v in vals):
                header_row = r
                break

    headers_raw = [ws.cell(header_row, c).value for c in range(1, ws.max_column + 1)]
    headers = [str(h).strip() if h is not None else "" for h in headers_raw]
    # Find or append status column
    status_col = None
    for i, h in enumerate(headers, 1):
        if h and h.strip().lower() in STATUS_ALIASES:
            status_col = i
            break
    if status_col is None:
        status_col = len(headers) + 1
        ws.cell(header_row, status_col, STATUS_COL)
        headers.append(STATUS_COL)
    else:
        ws.cell(header_row, status_col, STATUS_COL)

    ok_fill = PatternFill("solid", fgColor="C6EFCE")
    err_fill = PatternFill("solid", fgColor="FFC7CE")
    bold = Font(bold=True)
    ws.cell(header_row, status_col).font = bold

    stats = {"created": 0, "updated": 0, "errors": 0, "total": 0}
    for r in range(header_row + 1, ws.max_row + 1):
        values = [ws.cell(r, c).value for c in range(1, status_col)]
        # skip fully empty
        if all(v is None or str(v).strip() == "" for v in values):
            continue
        raw = {}
        for i, h in enumerate(headers):
            if not h or h.strip().lower() in STATUS_ALIASES:
                continue
            raw[h] = values[i] if i < len(values) else None
            # normalize excel values
            if isinstance(raw[h], float) and raw[h] == int(raw[h]):
                raw[h] = int(raw[h])
            elif raw[h] is not None and not isinstance(raw[h], (int, float)):
                raw[h] = str(raw[h]).strip()
        if entity in ("crm-source", "crm/source"):
            from crm_ops import map_enquiry_headers

            mapped = map_enquiry_headers(raw)
            if not str(mapped.get("full_name") or "").strip():
                continue
        stats["total"] += 1

        cell = ws.cell(r, status_col)
        try:
            msg = importer(conn, raw)
            cell.value = msg
            cell.fill = ok_fill
            if "updated" in msg.lower() or "cập nhật" in msg.lower():
                stats["updated"] += 1
            else:
                stats["created"] += 1
        except Exception as e:
            cell.value = f"Lỗi: {e}"
            cell.fill = err_fill
            stats["errors"] += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), stats


def bulk_delete_rows(conn, delete_path: str, ids: list[int]) -> dict:
    from ops_crud import delete_ops_row

    path = (delete_path or "").strip().strip("/")
    table = DELETE_PATH_TABLE.get(path)
    if not table:
        # allow raw table name if already allowlisted
        table = path.replace("-", "_")
    deleted = 0
    failed: list[dict] = []
    for rid in ids:
        try:
            rid_i = int(rid)
        except (TypeError, ValueError):
            failed.append({"id": rid, "error": "id không hợp lệ"})
            continue
        try:
            ok = delete_ops_row(conn, table, rid_i)
            if ok:
                deleted += 1
            else:
                failed.append({"id": rid_i, "error": "Không tìm thấy"})
        except Exception as e:
            failed.append({"id": rid_i, "error": str(e)})
    return {"deleted": deleted, "failed": failed, "table": table}
