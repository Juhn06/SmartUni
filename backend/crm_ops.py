"""
CRM tuyển sinh — kho Dữ liệu Nguồn, đợt chăm sóc, nhắc nhở, báo cáo.

Hợp nhất lead Marcom + hồ sơ applications + import Excel vào form mẫu chung.
Cán bộ TS chăm sóc / báo cáo; lãnh đạo xem báo cáo tổng quan.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

from status_catalog import list_status_options

CARE_STATUSES = [
    ("potential", "Tiềm năng", "Potential"),
    ("interested", "Quan tâm", "Interested"),
    ("consulting", "Đang tư vấn", "Consulting"),
    ("applicant", "Ứng viên", "Applicant"),
    ("exam_prep", "Lập hồ sơ thi", "Exam file"),
    ("interviewed", "Đã tham gia phỏng vấn", "Interviewed"),
    ("admitted", "Trúng tuyển", "Admitted"),
    ("decided", "Quyết định", "Decided"),
    ("not_decided", "Không quyết định", "Not decided"),
    ("handed_ts", "Đã tạo hồ sơ TS", "Handed to admissions"),
]

# Hồ sơ còn ở kho chăm sóc — chưa thành ứng viên đăng ký
PRE_APPLICANT_STATUSES = {"potential", "interested", "consulting"}
PIPELINE_STATUSES = (
    "potential",
    "interested",
    "consulting",
    "applicant",
    "exam_prep",
    "interviewed",
    "admitted",
)
APP_STATUS_TO_CARE = {
    "submitted": "applicant",
    "approved_ts": "applicant",
    "under_screening": "applicant",
    "eligible_for_exam": "exam_prep",
    "exam_scheduled": "exam_prep",
    "interview": "interviewed",
    "eligible_for_interview": "interviewed",
    "passed": "admitted",
    "paid": "admitted",
    "official": "admitted",
    "admitted": "admitted",
    "failed": "not_decided",
    "withdrawn": "not_decided",
    "rejected": "not_decided",
}

ACTIVITY_TYPES = [
    ("tu_van_rieng", "Tư vấn riêng", "Private consultation"),
    ("hoi_thao", "Hội thảo", "Workshop / seminar"),
    ("info_day", "Info Day / Open Day", "Info Day"),
    ("goi_dien", "Gọi điện", "Phone call"),
    ("email", "Email chăm sóc", "Care email"),
    ("gap_mat", "Gặp mặt", "In-person meeting"),
    ("khac", "Khác", "Other"),
]

INTEREST_LEVELS = ("low", "medium", "high", "hot")
REMIND_CHANNELS = ("email", "phone", "print")
ACTIVITY_STATUSES = ("planned", "done", "cancelled")
# Mức độ quan tâm đúng cột Level của file Enquiry 20261006
PROSPECT_LEVELS = (
    "hot",
    "warm",
    "cold",
    "email",
    "inactive",
    "prospect",
    "move_to_application",
)
PERSON_STATUSES = (
    ("prospect", "Người quan tâm", "Prospect"),
    ("applicant", "Ứng viên", "Applicant"),
    ("learner", "Học viên", "Learner"),
    ("alumnus", "Cựu học viên", "Alumnus"),
)
APP_STAGES = (
    ("apply", "Nộp hồ sơ online", "Apply"),
    ("candidate", "Ứng viên", "Candidate"),
    ("fail", "Trượt", "Fail"),
    ("select", "Đỗ", "Select"),
    ("quit", "Không nhập học", "Quit"),
    ("enroll", "Nhập học", "Enroll"),
    ("postpone", "Bảo lưu kết quả", "Postpone"),
)

# Cột file Enquiry 20261006 (Database). Không gồm ma trận sự kiện cũ (JPO…)
# và checklist trùng HARD/SOFT COPIES.
ENQUIRY_EXTRA_COLUMNS = [
    ("pic", "TEXT"),
    ("enquiry_date", "TEXT"),
    ("person_status", "TEXT"),
    ("prospect_level", "TEXT"),
    ("intake", "TEXT"),
    ("follow_up_date", "TEXT"),
    ("latest_contact_at", "TEXT"),
    ("join_event", "TEXT"),
    ("channel", "TEXT"),
    ("source_1", "TEXT"),
    ("source_2", "TEXT"),
    ("app_stage", "TEXT"),
    ("apply_session", "TEXT"),
    ("apply_program", "TEXT"),
    ("dob", "TEXT"),
    ("gender", "TEXT"),
    ("place_of_birth", "TEXT"),
    ("address", "TEXT"),
    ("university", "TEXT"),
    ("specialization", "TEXT"),
    ("graduation_year", "TEXT"),
    ("classification", "TEXT"),
    ("study_years", "TEXT"),
    ("credit_hours", "TEXT"),
    ("other_degrees", "TEXT"),
    ("job_title", "TEXT"),
    ("working_years", "TEXT"),
    ("management_years", "TEXT"),
    ("application_fee", "TEXT"),
    ("promotion", "TEXT"),
    ("chk_hard", "TEXT"),
    ("chk_web", "TEXT"),
    ("chk_cv", "TEXT"),
    ("chk_motivation", "TEXT"),
    ("chk_reference", "TEXT"),
    ("chk_degree", "TEXT"),
    ("chk_transcript", "TEXT"),
    ("chk_id", "TEXT"),
    ("chk_ccta", "TEXT"),
    ("chk_naric", "TEXT"),
    ("chk_written", "TEXT"),
    ("english_cert", "TEXT"),
    ("id_app", "TEXT"),
    ("cert_issued_on", "TEXT"),
    ("cert_exam_on", "TEXT"),
    ("intensive_course", "TEXT"),
    ("intensive_fee", "TEXT"),
    ("intensive_until", "TEXT"),
    ("intensive_micro", "TEXT"),
    ("intensive_stats", "TEXT"),
    ("intensive_macro", "TEXT"),
    ("intensive_accounting", "TEXT"),
    ("intensive_math", "TEXT"),
    # Cột cũ — giữ trong DB, không hiện trên màn chăm sóc
    ("first_contact", "TEXT"),
    ("flag_apply", "INTEGER DEFAULT 0"),
    ("flag_candidate", "INTEGER DEFAULT 0"),
    ("flag_fail", "INTEGER DEFAULT 0"),
    ("flag_select", "INTEGER DEFAULT 0"),
    ("flag_quit", "INTEGER DEFAULT 0"),
    ("flag_postpone", "INTEGER DEFAULT 0"),
    ("flag_enroll", "INTEGER DEFAULT 0"),
    ("contact_count", "INTEGER DEFAULT 0"),
    ("exchange_program", "TEXT"),
    ("english_ability", "TEXT"),
    ("degree_verified", "TEXT"),
    ("written_exam_mms", "TEXT"),
    ("campus", "TEXT"),
]

FLAG_KEYS = (
    "flag_apply",
    "flag_candidate",
    "flag_fail",
    "flag_select",
    "flag_quit",
    "flag_postpone",
    "flag_enroll",
)
DATE_KEYS = (
    "enquiry_date",
    "dob",
    "follow_up_date",
    "latest_contact_at",
    "cert_issued_on",
    "cert_exam_on",
    "intensive_until",
)
EXTRA_FIELD_NAMES = [c[0] for c in ENQUIRY_EXTRA_COLUMNS]

ENQUIRY_HEADER_ALIASES = {
    "date of enquiry": "enquiry_date",
    "first contact": "first_contact",
    "pic": "pic",
    "fullname": "full_name",
    "full name": "full_name",
    "họ tên": "full_name",
    "ho ten": "full_name",
    "level": "prospect_level",
    "mức độ quan tâm / level": "prospect_level",
    "prog": "program_interest",
    "program": "program_interest",
    "chương trình / program": "program_interest",
    "năm / year": "intake",
    "year": "intake",
    "what's program you want to apply?": "program_interest",
    "intake": "intake",
    "apply": "flag_apply",
    "candidate": "flag_candidate",
    "fail": "flag_fail",
    "select": "flag_select",
    "neu select": "flag_select",
    "cfvg select": "flag_select",
    "quit": "flag_quit",
    "postpone": "flag_postpone",
    "enroll": "flag_enroll",
    "email": "email",
    "mobile no.": "phone",
    "mobile no": "phone",
    "mobile": "phone",
    "phone": "phone",
    "phone number": "phone",
    "work position": "job_title",
    "location": "campus",
    "campaign": "join_event",
    "created": "enquiry_date",
    "updated": "latest_contact_at",
    "dob/ age": "dob",
    "dob": "dob",
    "birthday": "dob",
    "follow up date": "follow_up_date",
    "no. of contact": "contact_count",
    "latest contact": "latest_contact_at",
    "take care note": "notes",
    "join event": "join_event",
    "exchange program": "exchange_program",
    "english ability": "english_ability",
    "management experience": "management_years",
    "working experience": "working_years",
    "work experience : (total years)": "working_years",
    "management experience : (total years)": "management_years",
    "graduation year": "graduation_year",
    "year of graduation": "graduation_year",
    "university": "university",
    "specialization": "specialization",
    "major": "specialization",
    "degree verification": "degree_verified",
    "take written exam for mms": "written_exam_mms",
    "thi trắc nghiệm mms": "written_exam_mms",
    "position": "occupation",
    "job title": "job_title",
    "company": "company",
    "channel": "channel",
    "source": "source_1",
    "source 1": "source_1",
    "chi tiết kênh 1 / source 1": "source_1",
    "source 2": "source_2",
    "chi tiết kênh 2 / source 2": "source_2",
    "id number": "cccd",
    "id/passport number": "cccd",
    "gender": "gender",
    "city of birth": "place_of_birth",
    "address": "address",
    "sessions": "apply_session",
    "đợt tuyển sinh / sessions": "apply_session",
    "street line": "address",
    "what's school you want to apply?": "campus",
    "city of birth": "place_of_birth",
    "giấy tờ chứng minh": "english_cert",
    "english cert": "english_cert",
    "year of birth": "dob",
    "cccd": "chk_id",
    "fee": "intensive_fee",
}

# Khớp tiêu đề song ngữ của file Enquiry 20261006 (chuỗi dài ưu tiên hơn).
ENQUIRY_HEADER_PREFIXES = [
    ("ngày tiếp nhận", "enquiry_date"),
    ("date of enquiry", "enquiry_date"),
    ("chuyên viên", "pic"),
    ("họ tên", "full_name"),
    ("người quan tâm / ứng viên", "person_status"),
    ("mức độ quan tâm", "prospect_level"),
    ("chương trình ứng tuyển", "apply_program"),
    ("chương trình / program", "program_interest"),
    ("năm tốt nghiệp", "graduation_year"),
    ("year of graduation", "graduation_year"),
    ("năm / year", "intake"),
    ("số điện thoại", "phone"),
    ("mobile no", "phone"),
    ("nhắc lịch", "follow_up_date"),
    ("follow up date", "follow_up_date"),
    ("liên hệ gần nhất", "latest_contact_at"),
    ("latest contact", "latest_contact_at"),
    ("chi tiết kênh 2", "source_2"),
    ("source 2", "source_2"),
    ("chi tiết kênh 1", "source_1"),
    ("source 1", "source_1"),
    ("chi tiết / note", "notes"),
    ("take care note", "notes"),
    ("sự kiện tham gia", "join_event"),
    ("join event", "join_event"),
    ("kênh / channel", "channel"),
    ("bạn quan tâm chương trình", "campus"),
    ("phone number", "phone"),
    ("work position", "job_title"),
    ("nộp hồ sơ online", "app_stage"),
    ("đợt tuyển sinh", "apply_session"),
    ("giới tính", "gender"),
    ("ngày sinh", "dob"),
    ("nơi sinh", "place_of_birth"),
    ("city of birth", "place_of_birth"),
    ("số cccd", "cccd"),
    ("id / passport", "cccd"),
    ("địa chỉ", "address"),
    ("đại học", "university"),
    ("ngành / major", "specialization"),
    ("xếp loại tốt nghiệp", "classification"),
    ("số năm đại học", "study_years"),
    ("tổng số tín chỉ", "credit_hours"),
    ("bằng cấp khác", "other_degrees"),
    ("công ty / company", "company"),
    ("chức danh", "job_title"),
    ("job title", "job_title"),
    ("số năm làm việc", "working_years"),
    ("work experience", "working_years"),
    ("số năm giữ chức vụ", "management_years"),
    ("management experience", "management_years"),
    ("phí tuyển sinh", "application_fee"),
    ("application fee", "application_fee"),
    ("ưu đãi", "promotion"),
    ("hồ sơ bản cứng", "chk_hard"),
    ("form đăng ký", "chk_web"),
    ("form đăng ky", "chk_web"),
    ("cv tiếng anh", "chk_cv"),
    ("cv tieng anh", "chk_cv"),
    ("thư xin học", "chk_motivation"),
    ("thư giới thiệu", "chk_reference"),
    ("công chứng bằng", "chk_degree"),
    ("công chứng bằng", "chk_degree"),
    ("công chứng bảng", "chk_transcript"),
    ("công chứng bảng", "chk_transcript"),
    ("xác nhận văn bằng", "chk_naric"),
    ("xác nhận văn bằng", "chk_naric"),
    ("yêu cầu thi viết", "chk_written"),
    ("giấy tờ chứng minh", "english_cert"),
    ("ngày cấp chứng chỉ", "cert_issued_on"),
    ("ngày thi chứng chỉ", "cert_exam_on"),
    ("1. micro", "intensive_micro"),
    ("2. probability", "intensive_stats"),
    ("3. macro", "intensive_macro"),
    ("4. accounting", "intensive_accounting"),
    ("5. mathematical", "intensive_math"),
    ("có giá trị tới ngày", "intensive_until"),
    ("intensive course", "intensive_course"),
    ("id app", "id_app"),
]


def _truthy(value) -> int:
    s = str(value or "").strip().lower()
    if s in ("1", "true", "yes", "x", "y", "✓", "checked"):
        return 1
    if s in ("0", "false", "no", "", "none", "null"):
        return 0
    try:
        return 1 if float(s) else 0
    except (TypeError, ValueError):
        return 0


def _date_str(value) -> str:
    if value is None or value == "":
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    if " " in s:
        s = s.split(" ")[0]
    if "T" in s:
        s = s.split("T")[0]
    return s[:10]


def map_enquiry_headers(raw: dict) -> dict:
    """Map tiêu đề file Enquiry 20261006 → khóa nội bộ. Khớp chuỗi dài trước."""
    prefixes = sorted(ENQUIRY_HEADER_PREFIXES, key=lambda item: len(item[0]), reverse=True)
    out = {}
    for k, v in (raw or {}).items():
        key = unicodedata.normalize(
            "NFC", re.sub(r"\s+", " ", str(k or "").strip().lower())
        )
        mapped = None
        for prefix, dest in prefixes:
            if key == prefix or key.startswith(prefix):
                mapped = dest
                break
        if not mapped:
            mapped = ENQUIRY_HEADER_ALIASES.get(key) or ENQUIRY_HEADER_ALIASES.get(key.replace(".", ""))
        if not mapped:
            continue
        if mapped in FLAG_KEYS:
            out[mapped] = max(int(out.get(mapped) or 0), _truthy(v))
            continue
        if mapped not in out or out.get(mapped) in (None, ""):
            out[mapped] = v
    return out


def _normalize_prospect_level(value: str) -> str:
    s = re.sub(r"\s+", " ", (value or "").strip().lower())
    aliases = {
        "hot": "hot",
        "warm": "warm",
        "cold": "cold",
        "email": "email",
        "inactive": "inactive",
        "prospect": "prospect",
        "move to application": "move_to_application",
        "move_to_application": "move_to_application",
    }
    return aliases.get(s, s[:40] if s else "")


def _normalize_person_status(value: str) -> str:
    s = re.sub(r"\s+", " ", (value or "").strip().lower())
    aliases = {
        "prospect": "prospect",
        "prospects": "prospect",
        "người quan tâm": "prospect",
        "applicant": "applicant",
        "applicants": "applicant",
        "ứng viên": "applicant",
        "student": "learner",
        "students": "learner",
        "sinh viên": "learner",
        "học viên": "learner",
        "learner": "learner",
        "alumnus": "alumnus",
        "alumni": "alumnus",
        "cựu học viên": "alumnus",
    }
    return aliases.get(s, s[:40] if s else "")


def _normalize_app_stage(value: str) -> str:
    s = re.sub(r"\s+", " ", (value or "").strip().lower())
    aliases = {
        "apply": "apply",
        "nộp hồ sơ online": "apply",
        "candidate": "candidate",
        "ứng viên": "candidate",
        "fail": "fail",
        "trượt": "fail",
        "select": "select",
        "đỗ": "select",
        "quit": "quit",
        "không nhập học": "quit",
        "enroll": "enroll",
        "nhập học": "enroll",
        "postpone": "postpone",
        "postponse": "postpone",
        "bảo lưu kết quả": "postpone",
        "bảo lưu": "postpone",
    }
    return aliases.get(s, s[:40] if s else "")


def _interest_from_level(level: str) -> str:
    lv = _normalize_prospect_level(level)
    return {
        "hot": "hot",
        "warm": "high",
        "email": "medium",
        "prospect": "medium",
        "move_to_application": "hot",
        "cold": "low",
        "inactive": "low",
    }.get(lv, "")


def _care_from_flags(data: dict) -> str:
    if _truthy(data.get("flag_enroll")):
        return "admitted"
    if _truthy(data.get("flag_select")):
        return "admitted"
    if _truthy(data.get("flag_fail")) or _truthy(data.get("flag_quit")):
        return "not_decided"
    if _truthy(data.get("flag_postpone")):
        return "consulting"
    if _truthy(data.get("flag_candidate")) or _truthy(data.get("flag_apply")):
        return "applicant"
    return ""


def _coerce_extra(name: str, value) -> Any:
    if name in FLAG_KEYS:
        return _truthy(value)
    if name == "contact_count":
        try:
            return int(float(value or 0))
        except (TypeError, ValueError):
            return 0
    if name in DATE_KEYS:
        return _date_str(value)
    if name == "prospect_level":
        return _normalize_prospect_level(str(value or ""))
    if name == "person_status":
        return _normalize_person_status(str(value or ""))
    if name == "app_stage":
        return _normalize_app_stage(str(value or ""))
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    s = str(value).strip()
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return s


def _extras_from_data(data: dict, *, skip_empty: bool = False) -> dict:
    out = {}
    for name in EXTRA_FIELD_NAMES:
        if name not in data:
            continue
        val = _coerce_extra(name, data.get(name))
        if skip_empty and val in ("", None, 0) and name not in FLAG_KEYS and name != "contact_count":
            continue
        out[name] = val
    return out


def enquiry_payload_from_row(raw: dict) -> dict:
    """Chuẩn hóa 1 dòng Excel Enquiry / Application list thành payload CRM."""
    mapped = map_enquiry_headers(raw)
    payload = dict(mapped)
    if payload.get("enquiry_date"):
        payload["enquiry_date"] = _date_str(payload.get("enquiry_date"))
    if payload.get("dob"):
        payload["dob"] = _date_str(payload.get("dob"))
    if payload.get("follow_up_date"):
        payload["follow_up_date"] = _date_str(payload.get("follow_up_date"))
    if payload.get("latest_contact_at"):
        payload["latest_contact_at"] = _date_str(payload.get("latest_contact_at"))
    if payload.get("first_contact"):
        payload["first_contact"] = str(payload.get("first_contact") or "").strip()
    if payload.get("prospect_level"):
        payload["prospect_level"] = _normalize_prospect_level(str(payload.get("prospect_level") or ""))
        derived_interest = _interest_from_level(payload["prospect_level"])
        if derived_interest:
            payload["interest_level"] = derived_interest
    stage = _normalize_app_stage(str(payload.get("app_stage") or ""))
    if stage:
        payload["app_stage"] = stage
        stage_flag = {
            "apply": "flag_apply",
            "candidate": "flag_candidate",
            "fail": "flag_fail",
            "select": "flag_select",
            "quit": "flag_quit",
            "postpone": "flag_postpone",
            "enroll": "flag_enroll",
        }.get(stage)
        if stage_flag and not _truthy(payload.get(stage_flag)):
            payload[stage_flag] = 1
    derived_care = _care_from_flags(payload)
    if derived_care and not (payload.get("care_status") or "").strip():
        payload["care_status"] = derived_care
    if not (payload.get("source") or "").strip():
        payload["source"] = "excel"
    if payload.get("job_title") and not payload.get("occupation"):
        payload["occupation"] = payload.get("job_title")
    if payload.get("follow_up_date") and not payload.get("next_remind_at"):
        payload["next_remind_at"] = payload["follow_up_date"]
    return payload


def _table_cols(cur, table: str) -> set[str]:
    return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def _add_missing(cur, table: str, columns: list[tuple[str, str]]) -> None:
    existing = _table_cols(cur, table)
    for name, typ in columns:
        if name not in existing:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")


def normalize_cccd(value: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", (value or "")).upper()


def ensure_crm_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS crm_source_profiles ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "full_name TEXT NOT NULL, "
        "cccd TEXT, "
        "email TEXT, "
        "phone TEXT, "
        "company TEXT, "
        "occupation TEXT, "
        "program_interest TEXT, "
        "source TEXT DEFAULT 'other', "
        "source_ref TEXT, "
        "lead_id INTEGER, "
        "application_id INTEGER, "
        "care_status TEXT DEFAULT 'potential', "
        "interest_level TEXT DEFAULT 'medium', "
        "notes TEXT, "
        "next_remind_at TEXT, "
        "converted_at TEXT, "
        "converted_round_id INTEGER, "
        "converted_program TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "updated_at TEXT)"
    )
    _add_missing(
        cur,
        "crm_source_profiles",
        [
            ("converted_at", "TEXT"),
            ("converted_round_id", "INTEGER"),
            ("converted_program", "TEXT"),
            *ENQUIRY_EXTRA_COLUMNS,
        ],
    )
    if "person_status" in {r[1] for r in cur.execute("PRAGMA table_info(crm_source_profiles)").fetchall()}:
        cur.execute(
            "UPDATE crm_source_profiles SET person_status = 'learner' WHERE person_status = 'student'"
        )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS crm_care_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "profile_id INTEGER NOT NULL, "
        "logged_at TEXT NOT NULL, "
        "actor TEXT, "
        "note TEXT, "
        "channel TEXT, "
        "follow_up_date TEXT, "
        "FOREIGN KEY (profile_id) REFERENCES crm_source_profiles(id))"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_src_pic ON crm_source_profiles(pic)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_src_intake ON crm_source_profiles(intake)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_care_log ON crm_care_log(profile_id, logged_at)")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS crm_activities ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "activity_type TEXT NOT NULL DEFAULT 'hoi_thao', "
        "starts_at TEXT, "
        "location TEXT, "
        "program_codes TEXT, "
        "status TEXT DEFAULT 'planned', "
        "notes TEXT, "
        "created_by TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS crm_activity_participants ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "activity_id INTEGER NOT NULL, "
        "profile_id INTEGER NOT NULL, "
        "interest_level TEXT DEFAULT 'medium', "
        "feedback TEXT, "
        "discussion_note TEXT, "
        "care_note TEXT, "
        "attended TEXT DEFAULT '', "
        "UNIQUE(activity_id, profile_id), "
        "FOREIGN KEY (activity_id) REFERENCES crm_activities(id), "
        "FOREIGN KEY (profile_id) REFERENCES crm_source_profiles(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS crm_reminders ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "profile_id INTEGER, "
        "activity_id INTEGER, "
        "remind_at TEXT NOT NULL, "
        "channel TEXT DEFAULT 'print', "
        "title TEXT, "
        "body TEXT, "
        "status TEXT DEFAULT 'pending', "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (profile_id) REFERENCES crm_source_profiles(id), "
        "FOREIGN KEY (activity_id) REFERENCES crm_activities(id))"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_src_cccd ON crm_source_profiles(cccd)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_src_email ON crm_source_profiles(email)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_src_status ON crm_source_profiles(care_status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_crm_rem_at ON crm_reminders(remind_at, status)")


def care_status_options(conn) -> list[dict]:
    try:
        opts = list_status_options(conn, "crm_care_status")
        if opts:
            return [{"v": o["code"], "l": o.get("label_vi") or o["code"]} for o in opts]
    except Exception:
        pass
    return [{"v": c, "l": vi} for c, vi, _en in CARE_STATUSES]


def activity_type_options(conn) -> list[dict]:
    try:
        opts = list_status_options(conn, "crm_activity_type")
        if opts:
            return [{"v": o["code"], "l": o.get("label_vi") or o["code"]} for o in opts]
    except Exception:
        pass
    return [{"v": c, "l": vi} for c, vi, _en in ACTIVITY_TYPES]


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _find_profile(
    cur,
    *,
    cccd: str = "",
    email: str = "",
    phone: str = "",
    lead_id=None,
    application_id=None,
    full_name: str = "",
    intake: str = "",
    pic: str = "",
):
    if lead_id:
        r = cur.execute("SELECT id FROM crm_source_profiles WHERE lead_id = ?", (lead_id,)).fetchone()
        if r:
            return r[0]
    if application_id:
        r = cur.execute(
            "SELECT id FROM crm_source_profiles WHERE application_id = ?", (application_id,)
        ).fetchone()
        if r:
            return r[0]
    norm = normalize_cccd(cccd)
    if norm:
        r = cur.execute(
            "SELECT id FROM crm_source_profiles WHERE "
            "REPLACE(REPLACE(REPLACE(UPPER(IFNULL(cccd,'')),' ',''),'-',''),'.','') = ?",
            (norm,),
        ).fetchone()
        if r:
            return r[0]
    email = (email or "").strip().lower()
    if email:
        r = cur.execute(
            "SELECT id FROM crm_source_profiles WHERE lower(IFNULL(email,'')) = ?",
            (email,),
        ).fetchone()
        if r:
            return r[0]
    phone = re.sub(r"\D", "", phone or "")
    if len(phone) >= 9:
        r = cur.execute(
            "SELECT id FROM crm_source_profiles WHERE "
            "REPLACE(REPLACE(IFNULL(phone,''),' ',''),'-','') LIKE ?",
            (f"%{phone[-9:]}%",),
        ).fetchone()
        if r:
            return r[0]
    name = (full_name or "").strip().lower()
    intake_s = str(intake or "").strip()
    pic_s = (pic or "").strip().lower()
    if name and intake_s:
        r = cur.execute(
            "SELECT id FROM crm_source_profiles WHERE lower(full_name) = ? AND IFNULL(intake,'') = ?",
            (name, intake_s),
        ).fetchone()
        if r:
            return r[0]
    if name and pic_s:
        r = cur.execute(
            "SELECT id FROM crm_source_profiles WHERE lower(full_name) = ? AND lower(IFNULL(pic,'')) = ?",
            (name, pic_s),
        ).fetchone()
        if r:
            return r[0]
    return None


def upsert_source_profile(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    full_name = (data.get("full_name") or "").strip()
    if not full_name:
        raise ValueError("Cần họ tên.")
    cccd = (data.get("cccd") or "").strip()
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    pid = data.get("id")
    if pid:
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            pid = None
    if not pid:
        pid = _find_profile(
            cur,
            cccd=cccd,
            email=email,
            phone=phone,
            lead_id=data.get("lead_id"),
            application_id=data.get("application_id"),
            full_name=full_name,
            intake=data.get("intake") or "",
            pic=data.get("pic") or "",
        )
    existing = None
    if pid:
        existing = cur.execute(
            "SELECT * FROM crm_source_profiles WHERE id = ?", (pid,)
        ).fetchone()
        if not existing:
            raise ValueError("Không tìm thấy hồ sơ nguồn.")
        existing_cols = [d[0] for d in cur.description]
        existing = dict(zip(existing_cols, existing))
        if not cccd:
            cccd = existing.get("cccd") or ""
        if not email:
            email = existing.get("email") or ""
        if not phone:
            phone = existing.get("phone") or ""

    extras = _extras_from_data(data, skip_empty=bool(pid))
    derived_care = _care_from_flags({**({} if not existing else existing), **data, **extras})
    care_status = (data.get("care_status") or "").strip()
    if not care_status:
        care_status = derived_care or ((existing or {}).get("care_status") if existing else "") or "potential"
    interest_level = (data.get("interest_level") or "").strip()
    if extras.get("prospect_level"):
        mapped_interest = _interest_from_level(extras["prospect_level"])
        if mapped_interest and not (data.get("interest_level") or "").strip():
            interest_level = mapped_interest
    if not interest_level:
        interest_level = ((existing or {}).get("interest_level") if existing else "") or "medium"

    payload = {
        "full_name": full_name,
        "cccd": cccd,
        "email": email,
        "phone": phone,
        "company": (data.get("company") or "").strip() or ((existing or {}).get("company") if existing and "company" not in data else "") or (data.get("company") or ""),
        "occupation": (data.get("occupation") or data.get("job_title") or "").strip()
        or ((existing or {}).get("occupation") if existing and "occupation" not in data and "job_title" not in data else ""),
        "program_interest": (data.get("program_interest") or "").strip()
        or ((existing or {}).get("program_interest") if existing and "program_interest" not in data else ""),
        "source": (data.get("source") or "").strip()
        or ((existing or {}).get("source") if existing else "")
        or "other",
        "source_ref": (data.get("source_ref") or "").strip()
        if "source_ref" in data
        else ((existing or {}).get("source_ref") or ""),
        "lead_id": data.get("lead_id") if data.get("lead_id") not in (None, "") else ((existing or {}).get("lead_id") if existing else None),
        "application_id": data.get("application_id") if data.get("application_id") not in (None, "") else ((existing or {}).get("application_id") if existing else None),
        "care_status": care_status,
        "interest_level": interest_level,
        "notes": (data.get("notes") if "notes" in data else None),
        "next_remind_at": (data.get("next_remind_at") if "next_remind_at" in data else None),
        "updated_at": _now(),
    }
    if payload["notes"] is None:
        payload["notes"] = (existing or {}).get("notes") or ""
    else:
        payload["notes"] = str(payload["notes"] or "").strip()
    if payload["next_remind_at"] is None:
        payload["next_remind_at"] = extras.get("follow_up_date") or ((existing or {}).get("next_remind_at") or "")
    else:
        payload["next_remind_at"] = str(payload["next_remind_at"] or "").strip()
    if existing and "company" not in data and not (data.get("company") or "").strip():
        payload["company"] = existing.get("company") or ""
    if existing and "occupation" not in data and "job_title" not in data:
        payload["occupation"] = existing.get("occupation") or ""
    if existing and "program_interest" not in data:
        payload["program_interest"] = existing.get("program_interest") or ""

    allowed_status = {c for c, *_ in CARE_STATUSES}
    if payload["care_status"] not in allowed_status:
        payload["care_status"] = "potential"
    if payload["interest_level"] not in INTEREST_LEVELS:
        payload["interest_level"] = "medium"

    payload.update(extras)
    table_cols = _table_cols(cur, "crm_source_profiles")
    cols = [
        c
        for c in (
            "full_name",
            "cccd",
            "email",
            "phone",
            "company",
            "occupation",
            "program_interest",
            "source",
            "source_ref",
            "lead_id",
            "application_id",
            "care_status",
            "interest_level",
            "notes",
            "next_remind_at",
            "updated_at",
            *EXTRA_FIELD_NAMES,
        )
        if c in table_cols and c in payload
    ]
    if pid:
        sets = ", ".join(f"{c} = ?" for c in cols)
        cur.execute(
            f"UPDATE crm_source_profiles SET {sets} WHERE id = ?",
            [payload.get(c) for c in cols] + [pid],
        )
        action = "updated"
    else:
        cur.execute(
            "INSERT INTO crm_source_profiles ("
            + ", ".join(cols)
            + ") VALUES ("
            + ", ".join("?" * len(cols))
            + ")",
            [payload.get(c) for c in cols],
        )
        pid = cur.lastrowid
        action = "created"
    conn.commit()
    try:
        from admission_ops import propagate_row_by_id

        propagate_row_by_id(conn, "crm_source_profiles", pid, payload)
    except Exception:
        pass
    row = get_source_profile(conn, pid)
    if row:
        row["action"] = action
    return row or {"id": pid, "action": action, "full_name": full_name}


def get_source_profile(conn, profile_id: int) -> dict | None:
    rows = list_source_profiles(conn, profile_id=int(profile_id))
    return rows[0] if rows else None


def list_source_profiles(
    conn,
    *,
    q: str = "",
    care_status: str = "",
    program_code: str = "",
    source: str = "",
    converted: str = "",
    pic: str = "",
    intake: str = "",
    prospect_level: str = "",
    profile_id: int | None = None,
) -> list[dict]:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    cols = [r[1] for r in cur.execute("PRAGMA table_info(crm_source_profiles)").fetchall()]
    sql = "SELECT " + ", ".join(cols) + " FROM crm_source_profiles WHERE 1=1"
    params: list[Any] = []
    if profile_id:
        sql += " AND id = ?"
        params.append(int(profile_id))
    if care_status:
        sql += " AND care_status = ?"
        params.append(care_status)
    if source:
        sql += " AND source = ?"
        params.append(source)
    if program_code:
        sql += (
            " AND (IFNULL(converted_program,'') = ? OR IFNULL(program_interest,'') LIKE ?)"
        )
        params.extend([program_code, f"%{program_code}%"])
    if converted in ("1", "true", "yes"):
        sql += " AND IFNULL(converted_at,'') != ''"
    if pic:
        sql += " AND IFNULL(pic,'') LIKE ?"
        params.append(f"%{pic.strip()}%")
    if intake:
        sql += " AND IFNULL(intake,'') LIKE ?"
        params.append(f"%{intake.strip()}%")
    if prospect_level:
        sql += " AND IFNULL(prospect_level,'') = ?"
        params.append(_normalize_prospect_level(prospect_level))
    if q:
        like = f"%{q}%"
        extra_q = []
        for name in ("pic", "intake", "university", "company", "occupation", "job_title"):
            if name in cols:
                extra_q.append(f"IFNULL({name},'') LIKE ?")
        sql += (
            " AND (full_name LIKE ? OR IFNULL(email,'') LIKE ? OR IFNULL(phone,'') LIKE ? "
            "OR IFNULL(cccd,'') LIKE ? OR IFNULL(notes,'') LIKE ?"
            + ("" if not extra_q else " OR " + " OR ".join(extra_q))
            + ")"
        )
        params.extend([like] * (5 + len(extra_q)))
    sql += " ORDER BY updated_at DESC, id DESC"
    rows = [dict(zip(cols, r)) for r in cur.execute(sql, params).fetchall()]
    if rows:
        ids = [r["id"] for r in rows]
        placeholders = ",".join("?" * len(ids))
        counts = {
            pid: n
            for pid, n in cur.execute(
                f"SELECT profile_id, COUNT(*) FROM crm_activity_participants "
                f"WHERE profile_id IN ({placeholders}) GROUP BY profile_id",
                ids,
            )
        }
        rem_counts = {
            pid: n
            for pid, n in cur.execute(
                f"SELECT profile_id, COUNT(*) FROM crm_reminders "
                f"WHERE profile_id IN ({placeholders}) GROUP BY profile_id",
                ids,
            )
        }
        pending = {
            pid: n
            for pid, n in cur.execute(
                f"SELECT profile_id, COUNT(*) FROM crm_reminders "
                f"WHERE status='pending' AND profile_id IN ({placeholders}) GROUP BY profile_id",
                ids,
            )
        }
        log_counts = {
            pid: n
            for pid, n in cur.execute(
                f"SELECT profile_id, COUNT(*) FROM crm_care_log "
                f"WHERE profile_id IN ({placeholders}) GROUP BY profile_id",
                ids,
            )
        }
        for r in rows:
            r["activity_count"] = counts.get(r["id"], 0)
            r["reminder_count"] = rem_counts.get(r["id"], 0)
            r["pending_reminders"] = pending.get(r["id"], 0)
            r["care_log_count"] = log_counts.get(r["id"], 0)
            r["status"] = r.get("care_status") or ""
            r["converted"] = "yes" if r.get("converted_at") else ""
            code = r.get("person_status") or ""
            r["person_status_label"] = next(
                (vi for key, vi, _en in PERSON_STATUSES if key == code),
                code,
            )
        app_ids = [int(r["application_id"]) for r in rows if r.get("application_id")]
        has_apps = cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'applications'"
        ).fetchone()
        if app_ids and has_apps:
            ph = ",".join("?" * len(app_ids))
            linked = {
                int(aid): pid
                for aid, pid in cur.execute(
                    f"SELECT id, person_id FROM applications WHERE id IN ({ph}) AND person_id IS NOT NULL",
                    app_ids,
                )
            }
            for r in rows:
                aid = r.get("application_id")
                if aid and int(aid) in linked:
                    r["person_id"] = linked[int(aid)]
        need = [r for r in rows if not r.get("person_id")]
        has_people = cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'person_profiles'"
        ).fetchone()
        if need and has_people:
            emails = sorted({
                (r.get("email") or "").strip().lower()
                for r in need if (r.get("email") or "").strip()
            })
            names = sorted({
                (r.get("full_name") or "").strip().lower()
                for r in need if (r.get("full_name") or "").strip()
            })
            by_email: dict[str, int] = {}
            by_name: dict[str, int] = {}
            if emails:
                ph = ",".join("?" * len(emails))
                by_email = {
                    (em or "").strip().lower(): int(pid)
                    for pid, em in cur.execute(
                        f"SELECT id, email FROM person_profiles WHERE lower(IFNULL(email,'')) IN ({ph})",
                        emails,
                    )
                }
            if names:
                ph = ",".join("?" * len(names))
                by_name = {
                    (nm or "").strip().lower(): int(pid)
                    for pid, nm in cur.execute(
                        f"SELECT id, full_name FROM person_profiles WHERE lower(IFNULL(full_name,'')) IN ({ph})",
                        names,
                    )
                }
            for r in need:
                em = (r.get("email") or "").strip().lower()
                nm = (r.get("full_name") or "").strip().lower()
                r["person_id"] = by_email.get(em) or by_name.get(nm)
    return rows


def sync_source_warehouse(conn) -> dict:
    """Pull Marcom leads + applications into Dữ liệu Nguồn (upsert)."""
    cur = conn.cursor()
    ensure_crm_tables(cur)
    from marcom_ops import ensure_marcom_tables

    ensure_marcom_tables(cur)
    created = updated = 0
    leads = cur.execute(
        "SELECT id, full_name, email, phone, occupation, company, program_interest, "
        "source, status, notes, application_id FROM marcom_leads"
    ).fetchall()
    lead_status_map = {
        "new": "potential",
        "nurturing": "interested",
        "handed_ts": "applicant",
        "converted": "decided",
        "dropped": "not_decided",
        "closed": "not_decided",
    }
    for row in leads:
        lid, name, email, phone, occ, company, prog, source, st, notes, app_id = row
        before = _find_profile(cur, email=email or "", phone=phone or "", lead_id=lid)
        upsert_source_profile(
            conn,
            {
                "full_name": name,
                "email": email,
                "phone": phone,
                "occupation": occ,
                "company": company,
                "program_interest": prog,
                "source": source or "marcom",
                "source_ref": f"lead:{lid}",
                "lead_id": lid,
                "application_id": app_id,
                "care_status": lead_status_map.get((st or "").strip(), "potential"),
                "notes": notes,
            },
        )
        if before:
            updated += 1
        else:
            created += 1
    apps = cur.execute(
        "SELECT id, full_name, cccd, email, phone, company, job_title, program_code, "
        "lead_source, status, notes FROM applications"
    ).fetchall()
    app_status_map = {
        "submitted": "interested",
        "approved_ts": "interested",
        "interview": "consulting",
        "passed": "decided",
        "paid": "decided",
        "official": "decided",
        "failed": "not_decided",
        "withdrawn": "not_decided",
    }
    for row in apps:
        aid, name, cccd, email, phone, company, job, prog, src, st, notes = row
        before = _find_profile(
            cur, cccd=cccd or "", email=email or "", phone=phone or "", application_id=aid
        )
        upsert_source_profile(
            conn,
            {
                "full_name": name,
                "cccd": cccd,
                "email": email,
                "phone": phone,
                "company": company,
                "occupation": job,
                "program_interest": prog,
                "source": src or "application",
                "source_ref": f"app:{aid}",
                "application_id": aid,
                "care_status": app_status_map.get((st or "").strip(), "interested"),
                "notes": notes,
            },
        )
        if before:
            updated += 1
        else:
            created += 1
    synced = sync_care_from_applications(conn)
    return {"created": created, "updated": updated, "pipeline_synced": synced}


def patch_source_inline(conn, profile_id: int, field: str, value: str) -> dict:
    field = (field or "").strip()
    if field == "care_status":
        return set_care_status(conn, profile_id, value)
    if field not in ("prospect_level", "person_status"):
        raise ValueError("Chỉ đổi được mức độ quan tâm, tình trạng hoặc tình trạng chăm sóc.")
    cur = conn.cursor()
    ensure_crm_tables(cur)
    coerced = _coerce_extra(field, value)
    if field == "prospect_level" and not coerced:
        raise ValueError("Mức độ quan tâm không hợp lệ")
    cur.execute(
        f"UPDATE crm_source_profiles SET {field} = ?, updated_at = ? WHERE id = ?",
        (coerced, _now(), int(profile_id)),
    )
    if cur.rowcount == 0:
        raise ValueError("Không tìm thấy hồ sơ nguồn")
    conn.commit()
    return get_source_profile(conn, int(profile_id)) or {"id": profile_id, field: coerced}


def set_care_status(conn, profile_id: int, care_status: str, notes: str | None = None) -> dict:
    allowed = {c for c, *_ in CARE_STATUSES}
    if care_status not in allowed:
        raise ValueError("Trạng thái không hợp lệ.")
    cur = conn.cursor()
    ensure_crm_tables(cur)
    exists = cur.execute("SELECT id FROM crm_source_profiles WHERE id = ?", (profile_id,)).fetchone()
    if not exists:
        raise ValueError("Không tìm thấy hồ sơ nguồn.")
    if notes is not None:
        cur.execute(
            "UPDATE crm_source_profiles SET care_status = ?, notes = ?, updated_at = ? WHERE id = ?",
            (care_status, notes, _now(), profile_id),
        )
    else:
        cur.execute(
            "UPDATE crm_source_profiles SET care_status = ?, updated_at = ? WHERE id = ?",
            (care_status, _now(), profile_id),
        )
    conn.commit()
    return get_source_profile(conn, profile_id) or {"id": profile_id, "care_status": care_status}


def list_care_log(conn, profile_id: int) -> list[dict]:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    rows = cur.execute(
        "SELECT id, profile_id, logged_at, actor, note, channel, follow_up_date "
        "FROM crm_care_log WHERE profile_id = ? ORDER BY id DESC LIMIT 200",
        (int(profile_id),),
    ).fetchall()
    keys = ["id", "profile_id", "logged_at", "actor", "note", "channel", "follow_up_date"]
    return [dict(zip(keys, r)) for r in rows]


def log_daily_update(conn, profile_id: int, data: dict, actor: str = "") -> dict:
    """Ghi nhật ký chăm sóc hằng ngày (file Enquiry: Take care Note + Follow up + flags)."""
    cur = conn.cursor()
    ensure_crm_tables(cur)
    row = get_source_profile(conn, profile_id)
    if not row:
        raise ValueError("Không tìm thấy hồ sơ nguồn.")
    note = (data.get("note") or data.get("notes") or data.get("take_care_note") or "").strip()
    channel = (data.get("channel") or row.get("channel") or "").strip()
    follow_up = _date_str(data.get("follow_up_date") or data.get("next_remind_at") or "")
    today = date.today().isoformat()
    contact_n = int(row.get("contact_count") or 0) + 1
    stamp = f"{contact_n}. {today}"
    if note:
        line = f"{stamp} — {note}"
        prev = (row.get("notes") or "").strip()
        notes = f"{prev}\n{line}".strip() if prev else line
    else:
        notes = row.get("notes") or ""
        if not note:
            raise ValueError("Cần ghi chú chăm sóc hôm nay.")

    patch = {
        "id": profile_id,
        "full_name": row.get("full_name"),
        "cccd": row.get("cccd") or "",
        "email": row.get("email") or "",
        "phone": row.get("phone") or "",
        "notes": notes,
        "contact_count": contact_n,
        "latest_contact_at": today,
        "channel": channel or (row.get("channel") or ""),
    }
    if follow_up:
        patch["follow_up_date"] = follow_up
        patch["next_remind_at"] = follow_up
    if data.get("pic") not in (None, ""):
        patch["pic"] = data.get("pic")
    if data.get("prospect_level") not in (None, ""):
        patch["prospect_level"] = data.get("prospect_level")
    if data.get("intake") not in (None, ""):
        patch["intake"] = data.get("intake")
    if data.get("join_event") not in (None, ""):
        patch["join_event"] = data.get("join_event")
    if data.get("source_1") not in (None, ""):
        patch["source_1"] = data.get("source_1")
    if data.get("source_2") not in (None, ""):
        patch["source_2"] = data.get("source_2")
    if data.get("person_status") not in (None, ""):
        patch["person_status"] = data.get("person_status")
    if data.get("program_interest") not in (None, ""):
        patch["program_interest"] = data.get("program_interest")
    if data.get("care_status"):
        patch["care_status"] = data.get("care_status")
    for fk in FLAG_KEYS:
        if fk in data:
            patch[fk] = _truthy(data.get(fk))
    upsert_source_profile(conn, patch)
    cur.execute(
        "INSERT INTO crm_care_log (profile_id, logged_at, actor, note, channel, follow_up_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (profile_id, _now(), actor or "", note, channel, follow_up),
    )
    conn.commit()
    out = get_source_profile(conn, profile_id) or {"id": profile_id}
    out["care_log"] = list_care_log(conn, profile_id)
    return out


def care_from_app_status(app_status: str) -> str:
    return APP_STATUS_TO_CARE.get((app_status or "").strip(), "applicant")


def sync_profile_from_application(conn, application_id: int) -> None:
    """Keep CRM care_status aligned with the admissions application pipeline."""
    try:
        application_id = int(application_id)
    except (TypeError, ValueError):
        return
    cur = conn.cursor()
    ensure_crm_tables(cur)
    row = cur.execute(
        "SELECT status, program_code FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    if not row:
        return
    care = care_from_app_status(row[0])
    cur.execute(
        "UPDATE crm_source_profiles SET care_status = ?, "
        "converted_program = COALESCE(NULLIF(converted_program,''), ?), "
        "updated_at = ? WHERE application_id = ?",
        (care, row[1] or "", _now(), application_id),
    )
    conn.commit()


def sync_care_from_applications(conn) -> int:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    n = 0
    for pid, aid in cur.execute(
        "SELECT id, application_id FROM crm_source_profiles "
        "WHERE application_id IS NOT NULL AND application_id > 0"
    ):
        row = cur.execute("SELECT status FROM applications WHERE id = ?", (aid,)).fetchone()
        if not row:
            continue
        care = care_from_app_status(row[0])
        cur.execute(
            "UPDATE crm_source_profiles SET care_status = ?, updated_at = ? "
            "WHERE id = ? AND IFNULL(care_status,'') != ?",
            (care, _now(), pid, care),
        )
        n += cur.rowcount
    conn.commit()
    return n


def list_open_program_options(conn) -> list[dict]:
    from admission_ops import list_admission_rounds, parse_program_list

    out = []
    for rnd in list_admission_rounds(conn):
        if (rnd.get("status") or "").strip() != "open":
            continue
        for prog in parse_program_list(rnd.get("programs")) or ["MBA"]:
            out.append(
                {
                    "round_id": rnd["id"],
                    "round_code": rnd.get("code") or "",
                    "round_name": rnd.get("name") or "",
                    "program_code": prog,
                    "label": f"{prog} — {rnd.get('code') or rnd.get('name')}",
                }
            )
    return out


def convert_potential_to_applicant(
    conn,
    profile_ids: list,
    *,
    round_id: int,
    program_code: str,
    actor: str = "",
) -> dict:
    """Move potential CRM profiles into an open admission round as applicants."""
    from admission_ops import get_admission_round, parse_program_list
    from coord_ops import ensure_coord_tables

    try:
        round_id = int(round_id)
    except (TypeError, ValueError):
        raise ValueError("Cần chọn đợt tuyển sinh đang mở.") from None
    program_code = (program_code or "").strip().upper()
    if not program_code:
        raise ValueError("Cần chọn chương trình đang mở.")
    rnd = get_admission_round(conn, round_id)
    if not rnd:
        raise ValueError("Không tìm thấy đợt tuyển sinh.")
    if (rnd.get("status") or "").strip() != "open":
        raise ValueError("Chỉ chuyển vào đợt đang mở.")
    allowed = {p.upper() for p in parse_program_list(rnd.get("programs"))}
    if allowed and program_code not in allowed:
        raise ValueError(f"Chương trình {program_code} không mở trong đợt {rnd.get('code') or round_id}.")

    cur = conn.cursor()
    ensure_crm_tables(cur)
    ensure_coord_tables(cur)
    converted, skipped, errors = [], [], []
    now = _now()
    note = f"Chuyển từ Dữ liệu Nguồn → ứng viên {program_code} / đợt {rnd.get('code') or round_id}"
    if actor:
        note += f" ({actor})"

    CONVERTIBLE = PRE_APPLICANT_STATUSES | {"applicant"}
    for raw in profile_ids or []:
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        row = cur.execute(
            "SELECT * FROM crm_source_profiles WHERE id = ?",
            (pid,),
        ).fetchone()
        if not row:
            errors.append(f"#{raw}: không tìm thấy")
            continue
        src = dict(zip([d[0] for d in cur.description], row))
        name = src.get("full_name") or ""
        cccd = src.get("cccd") or ""
        email = src.get("email") or ""
        phone = src.get("phone") or ""
        company = src.get("company") or ""
        occupation = src.get("job_title") or src.get("occupation") or ""
        notes = src.get("notes") or ""
        care_status = src.get("care_status") or ""
        app_id = src.get("application_id")
        lead_id = src.get("lead_id")
        if (care_status or "").strip() not in CONVERTIBLE and not app_id:
            skipped.append({"id": pid, "full_name": name, "reason": "không còn ở trạng thái tiềm năng"})
            continue
        if app_id:
            cur.execute(
                "UPDATE crm_source_profiles SET care_status = 'applicant', "
                "converted_at = COALESCE(NULLIF(converted_at,''), ?), "
                "converted_round_id = COALESCE(converted_round_id, ?), "
                "converted_program = COALESCE(NULLIF(converted_program,''), ?), "
                "program_interest = ?, flag_apply = 1, flag_candidate = 1, updated_at = ? WHERE id = ?",
                (now, round_id, program_code, program_code, now, pid),
            )
            converted.append({"id": pid, "full_name": name, "application_id": app_id, "existing": True})
            continue
        existing = None
        if email:
            existing = cur.execute(
                "SELECT id FROM applications WHERE lower(IFNULL(email,'')) = ? AND program_code = ?",
                ((email or "").strip().lower(), program_code),
            ).fetchone()
        if not existing and cccd:
            existing = cur.execute(
                "SELECT id FROM applications WHERE "
                "REPLACE(REPLACE(REPLACE(UPPER(IFNULL(cccd,'')),' ',''),'-',''),'.','') = ? "
                "AND program_code = ?",
                (normalize_cccd(cccd), program_code),
            ).fetchone()
        if existing:
            app_id = existing[0]
        else:
            app_cols = _table_cols(cur, "applications")
            insert_map = {
                "round_id": round_id,
                "program_code": program_code,
                "full_name": name,
                "cccd": cccd or "",
                "email": email or "",
                "phone": phone or "",
                "status": "submitted",
                "notes": " — ".join(p for p in (note, notes) if p),
                "company": company or "",
                "job_title": occupation or "",
                "lead_source": "crm_source",
                "checklist_status": "pending",
                "university": src.get("university") or "",
                "degree_major": src.get("specialization") or "",
                "dob": src.get("dob") or "",
                "gender": src.get("gender") or "",
                "campus": src.get("campus") or "",
                "experience_years": src.get("working_years") or "",
                "management_years": src.get("management_years") or "",
                "degree_year": src.get("graduation_year") or "",
                "bachelor_grad_year": src.get("graduation_year") or "",
                "intake_session": src.get("intake") or "",
                "degree_verified": src.get("degree_verified") or "",
                "english_cert": src.get("english_cert") or src.get("english_ability") or "",
            }
            use_cols = [c for c in insert_map if c in app_cols]
            cur.execute(
                "INSERT INTO applications ("
                + ", ".join(use_cols)
                + ") VALUES ("
                + ", ".join("?" * len(use_cols))
                + ")",
                [insert_map[c] for c in use_cols],
            )
            app_id = cur.lastrowid
        cur.execute(
            "UPDATE crm_source_profiles SET care_status = 'applicant', application_id = ?, "
            "converted_at = ?, converted_round_id = ?, converted_program = ?, "
            "program_interest = ?, flag_apply = 1, flag_candidate = 1, updated_at = ? WHERE id = ?",
            (app_id, now, round_id, program_code, program_code, now, pid),
        )
        if lead_id:
            try:
                cur.execute(
                    "UPDATE marcom_leads SET status = 'handed_ts', handed_at = ?, application_id = ? "
                    "WHERE id = ?",
                    (now[:10], app_id, lead_id),
                )
            except Exception:
                pass
        converted.append({"id": pid, "full_name": name, "application_id": app_id, "existing": False})

    try:
        from learner_spine import bind_application_spine
    except Exception:
        bind_application_spine = None
    if bind_application_spine:
        for item in converted:
            aid = item.get("application_id")
            if not aid:
                continue
            try:
                spine = bind_application_spine(conn, int(aid))
                item["person_id"] = spine.get("person_id")
                item["learner_id"] = spine.get("learner_id")
            except Exception:
                pass
    conn.commit()
    return {
        "converted": converted,
        "skipped": skipped,
        "errors": errors,
        "round_id": round_id,
        "program_code": program_code,
        "count": len(converted),
    }


def list_activities(conn, *, q: str = "", activity_type: str = "", status: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    sql = (
        "SELECT a.id, a.title, a.activity_type, a.starts_at, a.location, a.program_codes, "
        "a.status, a.notes, a.created_by, a.created_at, "
        "(SELECT COUNT(*) FROM crm_activity_participants p WHERE p.activity_id = a.id) "
        "FROM crm_activities a WHERE 1=1"
    )
    params: list[Any] = []
    if activity_type:
        sql += " AND a.activity_type = ?"
        params.append(activity_type)
    if status:
        sql += " AND a.status = ?"
        params.append(status)
    if q:
        sql += " AND (a.title LIKE ? OR IFNULL(a.notes,'') LIKE ? OR IFNULL(a.location,'') LIKE ?)"
        params.extend([f"%{q}%"] * 3)
    sql += " ORDER BY IFNULL(a.starts_at,'' ) DESC, a.id DESC"
    rows = []
    for r in cur.execute(sql, params):
        rows.append(
            {
                "id": r[0],
                "title": r[1],
                "activity_type": r[2],
                "starts_at": r[3] or "",
                "location": r[4] or "",
                "program_codes": r[5] or "",
                "status": r[6] or "planned",
                "notes": r[7] or "",
                "created_by": r[8] or "",
                "created_at": r[9] or "",
                "participant_count": r[10] or 0,
            }
        )
    return rows


def create_activity(conn, data: dict, *, created_by: str = "") -> dict:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    title = (data.get("title") or "").strip()
    activity_type = (data.get("activity_type") or "hoi_thao").strip() or "hoi_thao"
    if not title:
        raise ValueError("Cần tên đợt hoạt động.")
    allowed_types = {c for c, *_ in ACTIVITY_TYPES}
    if activity_type not in allowed_types:
        activity_type = "khac"
    status = (data.get("status") or "planned").strip() or "planned"
    if status not in ACTIVITY_STATUSES:
        status = "planned"
    cur.execute(
        "INSERT INTO crm_activities "
        "(title, activity_type, starts_at, location, program_codes, status, notes, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            title,
            activity_type,
            (data.get("starts_at") or "").strip(),
            (data.get("location") or "").strip(),
            (data.get("program_codes") or "").strip(),
            status,
            (data.get("notes") or "").strip(),
            created_by,
        ),
    )
    aid = cur.lastrowid
    ids = data.get("profile_ids") or data.get("participant_ids") or []
    conn.commit()
    if ids:
        add_participants(conn, aid, ids)
    generate_activity_reminders(conn, aid)
    return get_activity(conn, aid) or {"id": aid, "title": title}


def get_activity(conn, activity_id: int) -> dict | None:
    rows = list_activities(conn)
    act = next((r for r in rows if int(r["id"]) == int(activity_id)), None)
    if not act:
        return None
    act["participants"] = list_participants(conn, activity_id)
    return act


def list_participants(conn, activity_id: int) -> list[dict]:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    rows = cur.execute(
        "SELECT p.id, p.profile_id, s.full_name, s.phone, s.email, s.prospect_level, "
        "s.program_interest, s.join_event, p.care_note "
        "FROM crm_activity_participants p "
        "JOIN crm_source_profiles s ON s.id = p.profile_id "
        "WHERE p.activity_id = ? ORDER BY s.full_name",
        (activity_id,),
    ).fetchall()
    keys = [
        "id", "profile_id", "full_name", "phone", "email", "prospect_level",
        "program_interest", "join_event", "care_note",
    ]
    return [dict(zip(keys, r)) for r in rows]


def add_participants(conn, activity_id: int, profile_ids: list) -> dict:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    exists = cur.execute("SELECT id FROM crm_activities WHERE id = ?", (activity_id,)).fetchone()
    if not exists:
        raise ValueError("Không tìm thấy đợt hoạt động.")
    added = 0
    for raw in profile_ids:
        try:
            pid = int(raw)
        except (TypeError, ValueError):
            continue
        if not cur.execute("SELECT id FROM crm_source_profiles WHERE id = ?", (pid,)).fetchone():
            continue
        cur.execute(
            "INSERT OR IGNORE INTO crm_activity_participants (activity_id, profile_id) VALUES (?, ?)",
            (activity_id, pid),
        )
        if cur.rowcount:
            added += 1
    conn.commit()
    generate_activity_reminders(conn, activity_id)
    return {"activity_id": activity_id, "added": added, "participants": list_participants(conn, activity_id)}


def update_participant(conn, participant_id: int, data: dict) -> dict:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    row = cur.execute(
        "SELECT id, activity_id, profile_id FROM crm_activity_participants WHERE id = ?",
        (participant_id,),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy người tham gia.")
    fields, params = [], []
    for key in ("interest_level", "feedback", "discussion_note", "care_note", "attended"):
        if key in data:
            val = data.get(key)
            if key == "interest_level" and val not in INTEREST_LEVELS:
                val = "medium"
            fields.append(f"{key} = ?")
            params.append(val)
    if not fields:
        raise ValueError("Không có trường để cập nhật")
    params.append(participant_id)
    cur.execute(
        f"UPDATE crm_activity_participants SET {', '.join(fields)} WHERE id = ?",
        params,
    )
    conn.commit()
    parts = list_participants(conn, row[1])
    return next((p for p in parts if p["id"] == participant_id), {"id": participant_id})


def create_private_consult(conn, data: dict, *, created_by: str = "") -> dict:
    profile_id = data.get("profile_id")
    try:
        profile_id = int(profile_id)
    except (TypeError, ValueError):
        raise ValueError("Cần chọn hồ sơ tiềm năng.") from None
    profile = get_source_profile(conn, profile_id)
    if not profile:
        raise ValueError("Không tìm thấy hồ sơ nguồn.")
    title = (data.get("title") or "").strip() or f"Tư vấn riêng — {profile['full_name']}"
    act = create_activity(
        conn,
        {
            "title": title,
            "activity_type": "tu_van_rieng",
            "starts_at": (data.get("starts_at") or "").strip(),
            "location": (data.get("location") or "").strip(),
            "program_codes": profile.get("program_interest") or "",
            "notes": (data.get("notes") or "").strip(),
            "profile_ids": [profile_id],
        },
        created_by=created_by,
    )
    consult_note = (data.get("consult_note") or data.get("discussion_note") or "").strip()
    info_note = (data.get("info_note") or data.get("care_note") or "").strip()
    next_at = (data.get("next_remind_at") or "").strip()
    parts = list_participants(conn, act["id"])
    if parts:
        update_participant(
            conn,
            parts[0]["id"],
            {
                "discussion_note": consult_note,
                "care_note": info_note,
                "interest_level": data.get("interest_level") or "high",
            },
        )
    set_care_status(conn, profile_id, "consulting", notes=None)
    if next_at:
        cur = conn.cursor()
        cur.execute(
            "UPDATE crm_source_profiles SET next_remind_at = ?, updated_at = ? WHERE id = ?",
            (next_at, _now(), profile_id),
        )
        conn.commit()
        add_reminder(
            conn,
            {
                "profile_id": profile_id,
                "activity_id": act["id"],
                "remind_at": next_at,
                "channel": data.get("channel") or "phone",
                "title": f"Nhắc hẹn tư vấn — {profile['full_name']}",
                "body": consult_note or info_note or title,
            },
        )
    return get_activity(conn, act["id"]) or act


def add_reminder(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    remind_at = (data.get("remind_at") or "").strip()
    if not remind_at:
        raise ValueError("Cần ngày/giờ nhắc.")
    cur.execute(
        "INSERT INTO crm_reminders (profile_id, activity_id, remind_at, channel, title, body, status) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending')",
        (
            data.get("profile_id") or None,
            data.get("activity_id") or None,
            remind_at,
            (data.get("channel") or "print").strip() or "print",
            (data.get("title") or "Nhắc chăm sóc").strip(),
            (data.get("body") or "").strip(),
        ),
    )
    conn.commit()
    return {"id": cur.lastrowid, "remind_at": remind_at, "status": "pending"}


def generate_activity_reminders(conn, activity_id: int, *, days_before: int = 1) -> dict:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    act = cur.execute(
        "SELECT id, title, starts_at FROM crm_activities WHERE id = ?", (activity_id,)
    ).fetchone()
    if not act:
        return {"created": 0}
    starts = (act[2] or "").strip()
    if not starts:
        return {"created": 0}
    try:
        when = datetime.fromisoformat(starts.replace("Z", ""))
    except ValueError:
        try:
            when = datetime.strptime(starts[:10], "%Y-%m-%d")
        except ValueError:
            return {"created": 0}
    remind_at = (when - timedelta(days=max(days_before, 0))).strftime("%Y-%m-%d %H:%M:%S")
    parts = cur.execute(
        "SELECT profile_id FROM crm_activity_participants WHERE activity_id = ?",
        (activity_id,),
    ).fetchall()
    created = 0
    for (pid,) in parts:
        dup = cur.execute(
            "SELECT id FROM crm_reminders WHERE activity_id = ? AND profile_id = ? AND remind_at = ?",
            (activity_id, pid, remind_at),
        ).fetchone()
        if dup:
            continue
        cur.execute(
            "INSERT INTO crm_reminders (profile_id, activity_id, remind_at, channel, title, body, status) "
            "VALUES (?, ?, ?, 'print', ?, ?, 'pending')",
            (pid, activity_id, remind_at, f"Nhắc đợt: {act[1]}", f"Hoạt động «{act[1]}» vào {starts}"),
        )
        created += 1
    conn.commit()
    return {"created": created, "remind_at": remind_at}


def list_reminders(
    conn,
    *,
    q: str = "",
    status: str = "",
    profile_id: int | None = None,
    upcoming_only: bool = False,
) -> list[dict]:
    cur = conn.cursor()
    ensure_crm_tables(cur)
    sql = (
        "SELECT r.id, r.profile_id, r.activity_id, r.remind_at, r.channel, r.title, r.body, r.status, "
        "s.full_name, s.phone, s.email, s.prospect_level, s.program_interest "
        "FROM crm_reminders r "
        "LEFT JOIN crm_source_profiles s ON s.id = r.profile_id "
        "WHERE 1=1"
    )
    params: list[Any] = []
    if status:
        sql += " AND r.status = ?"
        params.append(status)
    if profile_id:
        sql += " AND r.profile_id = ?"
        params.append(profile_id)
    if upcoming_only:
        sql += " AND r.remind_at >= date('now') AND r.status = 'pending'"
    if q:
        sql += (
            " AND (IFNULL(s.full_name,'') LIKE ? OR IFNULL(r.title,'') LIKE ? "
            "OR IFNULL(s.phone,'') LIKE ? OR IFNULL(s.program_interest,'') LIKE ?)"
        )
        params.extend([f"%{q}%"] * 4)
    sql += " ORDER BY r.remind_at, r.id"
    rows = []
    for r in cur.execute(sql, params):
        rows.append(
            {
                "id": r[0],
                "profile_id": r[1],
                "activity_id": r[2],
                "remind_at": r[3] or "",
                "channel": r[4] or "print",
                "title": r[5] or "",
                "body": r[6] or "",
                "status": r[7] or "pending",
                "full_name": r[8] or "",
                "phone": r[9] or "",
                "email": r[10] or "",
                "prospect_level": r[11] or "",
                "program_interest": r[12] or "",
            }
        )
    return rows


def dispatch_reminders(conn, reminder_ids: list, *, channel: str = "email") -> dict:
    from ops_crud import queue_email

    cur = conn.cursor()
    ensure_crm_tables(cur)
    queued = printed = called = 0
    for raw in reminder_ids:
        try:
            rid = int(raw)
        except (TypeError, ValueError):
            continue
        row = cur.execute(
            "SELECT r.id, r.title, r.body, s.full_name, s.email, s.phone "
            "FROM crm_reminders r LEFT JOIN crm_source_profiles s ON s.id = r.profile_id "
            "WHERE r.id = ?",
            (rid,),
        ).fetchone()
        if not row:
            continue
        _id, title, body, name, email, phone = row
        if channel == "email" and email:
            queue_email(
                conn,
                kind="crm_reminder",
                recipient=email,
                subject=title or "Nhắc chăm sóc CFVG",
                body=f"Kính gửi {name or ''},\n\n{body or title or ''}\n\nCFVG / X",
            )
            queued += 1
        elif channel == "phone":
            called += 1
        else:
            printed += 1
        cur.execute(
            "UPDATE crm_reminders SET status = 'sent', channel = ? WHERE id = ?",
            (channel, rid),
        )
    conn.commit()
    return {"email_queued": queued, "phone_marked": called, "print": printed}


def crm_report(conn, *, level: str = "overview", activity_id: int | None = None) -> dict:
    """Báo cáo đúng sheet Report của file Enquiry: Level × Chương trình."""
    cur = conn.cursor()
    ensure_crm_tables(cur)
    level_labels = [
        ("hot", "Hot"),
        ("warm", "Warm"),
        ("cold", "Cold"),
        ("email", "Email"),
        ("inactive", "Inactive"),
        ("prospect", "Prospect"),
        ("move_to_application", "Move to Application"),
    ]
    total = cur.execute("SELECT COUNT(*) FROM crm_source_profiles").fetchone()[0]
    by_level = []
    for code, label in level_labels:
        n = cur.execute(
            "SELECT COUNT(*) FROM crm_source_profiles WHERE IFNULL(prospect_level,'') = ?",
            (code,),
        ).fetchone()[0]
        by_level.append({"code": code, "label": label, "count": n})
    stage_labels = [
        ("apply", "Apply"),
        ("candidate", "Candidate"),
        ("fail", "Fail"),
        ("select", "Select"),
        ("quit", "Quit"),
        ("postpone", "Postpone"),
        ("enroll", "Enroll"),
    ]
    programs = [
        (r[0] or "").strip()
        for r in cur.execute(
            "SELECT DISTINCT IFNULL(program_interest,'') FROM crm_source_profiles "
            "WHERE TRIM(IFNULL(program_interest,'')) != '' ORDER BY program_interest"
        )
    ]
    level_counts = {
        ((r[0] or "").strip(), (r[1] or "").strip()): r[2]
        for r in cur.execute(
            "SELECT IFNULL(program_interest,''), IFNULL(prospect_level,''), COUNT(*) "
            "FROM crm_source_profiles GROUP BY 1, 2"
        )
    }
    stage_counts = {
        ((r[0] or "").strip(), (r[1] or "").strip()): r[2]
        for r in cur.execute(
            "SELECT IFNULL(program_interest,''), IFNULL(app_stage,''), COUNT(*) "
            "FROM crm_source_profiles GROUP BY 1, 2"
        )
    }
    by_program = []
    for prog in programs:
        row = {"program_interest": prog, "total": 0}
        for code, _label in level_labels:
            n = int(level_counts.get((prog, code), 0) or 0)
            row[code] = n
            row["total"] += n
        for code, _label in stage_labels:
            row[code] = int(stage_counts.get((prog, code), 0) or 0)
        by_program.append(row)
    pending = cur.execute(
        "SELECT COUNT(*) FROM crm_reminders WHERE status='pending'"
    ).fetchone()[0]
    out: dict[str, Any] = {
        "level": level,
        "generated_at": _now(),
        "overview": {
            "total_profiles": total,
            "pending_reminders": pending,
            "by_level": by_level,
            "pipeline": by_level,
            "by_program": by_program,
        },
        "pipeline": by_level,
        "by_program": by_program,
        "rows": by_program,
    }
    return out


def export_crm_rows(conn, *, kind: str = "source") -> tuple[list[dict], list[str]]:
    if kind == "reminders":
        rows = list_reminders(conn)
        fields = [
            "remind_at", "full_name", "phone", "email", "program_interest",
            "prospect_level", "channel", "title", "body", "status",
        ]
        return rows, fields
    if kind == "activities":
        rows = list_activities(conn)
        fields = [
            "title", "starts_at", "program_codes", "participant_count", "notes",
        ]
        return rows, fields
    if kind == "report":
        report = crm_report(conn)
        rows = report.get("pipeline") or []
        fields = ["code", "label", "count"]
        return rows, fields
    rows = list_source_profiles(conn)
    fields = [
        "enquiry_date", "pic", "full_name", "person_status", "prospect_level",
        "program_interest", "intake", "email", "phone", "follow_up_date",
        "latest_contact_at", "channel", "source_1", "source_2", "join_event",
        "notes", "app_stage", "apply_session", "apply_program", "gender", "dob",
        "place_of_birth", "cccd", "address", "university", "specialization",
        "graduation_year", "classification", "study_years", "credit_hours",
        "other_degrees", "company", "job_title", "working_years", "management_years",
        "application_fee", "promotion",
    ]
    return rows, fields


def import_enquiry_workbook(conn, path: str) -> dict:
    """Nạp sheet Database của file Enquiry (sổ master Tuyển sinh) vào crm_source_profiles."""
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["Database"] if "Database" in wb.sheetnames else wb.worksheets[0]
    header = None
    row_iter = ws.iter_rows(values_only=True)
    for i, row in enumerate(row_iter):
        cells = ["" if c is None else str(c).strip() for c in row]
        blob = " ".join(cells).lower()
        if "fullname" in blob or "họ tên" in blob:
            header = cells
            break
        if i > 15:
            break
    if not header:
        wb.close()
        return {"ok": False, "error": "Không thấy dòng tiêu đề Fullname"}
    inserted = updated = skipped = 0
    for row in row_iter:
        raw = {}
        for idx, title in enumerate(header):
            if not title or idx >= len(row):
                continue
            val = row[idx]
            if val is None or val == "":
                continue
            raw[title] = val
        payload = enquiry_payload_from_row(raw)
        if not str(payload.get("full_name") or "").strip():
            skipped += 1
            continue
        result = upsert_source_profile(conn, payload)
        if result.get("action") == "created":
            inserted += 1
        else:
            updated += 1
    wb.close()
    conn.commit()
    return {"ok": True, "inserted": inserted, "updated": updated, "skipped": skipped}
