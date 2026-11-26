"""
Liên kết hành vi giữa các bộ phận (thiết kế chung Smart University).

Luồng bàn giao (§8):
  Applicant nộp hồ sơ
    → Tuyển sinh screening / phê duyệt
    → Điều phối CT: thi viết (nếu có) → phỏng vấn → AdmissionDecision
    → Kế toán: Deposit Pending → Deposit Verified
    → Nhập học chính thức (cùng người thành học viên, trạng thái Chờ xếp lớp)
    → Điều phối: ProgrammeVersion → Class → Schedule → phân giảng
    → Attendance / Grade / Exam / Evaluation / Thesis
    → Graduation → Alumni
  Song song: Lịch học → Logistics / GV quốc tế; BC tuần → Trợ lý BGD → NEU
"""
from __future__ import annotations

# Ai được phép chuyển sang status mới (theo mã bộ phận)
# "*" = mọi bộ phận có quyền admissions.applications
STATUS_TRANSITIONS: dict[str, dict] = {
    "submitted": {
        "to": ["approved_ts", "withdrawn"],
        "by_departments": ["tuyen_sinh", "marcom_tuyen_sinh", "admin_he_thong", "it"],
        "label": "TS tiếp nhận / phê duyệt hồ sơ",
    },
    "approved_ts": {
        "to": ["interview", "withdrawn"],
        "by_departments": [
            "mba",
            "master_chuyen_nganh",
            "admin_he_thong",
            "it",
        ],
        "label": "Điều phối nhận hồ sơ đã duyệt → xếp PV (không phải bước của Tuyển sinh)",
    },
    "interview": {
        "to": ["passed", "failed", "withdrawn"],
        "by_departments": ["mba", "master_chuyen_nganh", "admin_he_thong", "it"],
        "label": "Điều phối / hội đồng kết luận đỗ-trượt",
    },
    "passed": {
        "to": ["withdrawn"],
        "by_departments": ["mba", "master_chuyen_nganh", "ke_toan", "tuyen_sinh", "admin_he_thong", "it"],
        "label": "Đỗ — Kế toán xác nhận đã thu phí ghi danh trên sổ phí (mark-paid), không đổi paid tại hồ sơ",
    },
    "failed": {
        "to": ["interview"],  # cho phép PV lại nếu cần
        "by_departments": ["mba", "master_chuyen_nganh", "admin_he_thong", "it"],
        "label": "Trượt",
    },
    "paid": {
        "to": ["official", "withdrawn"],
        "by_departments": ["ke_toan", "admin_he_thong", "it"],
        "label": "Đã thu phí ghi danh → Kế toán chốt nhập học chính thức",
    },
    "official": {
        "to": ["withdrawn"],
        "by_departments": ["ke_toan", "mba", "master_chuyen_nganh", "admin_he_thong", "it"],
        "label": "Đã chính thức — Điều phối cấp mã và xếp lớp",
    },
    "withdrawn": {
        "to": ["submitted", "approved_ts"],
        "by_departments": ["tuyen_sinh", "ke_toan", "mba", "master_chuyen_nganh", "admin_he_thong", "it"],
        "label": "Rút hồ sơ (ghi chú bắt buộc)",
    },
}

# Thao tác UI gợi ý theo bộ phận (trên hồ sơ)
DEPT_APPLICATION_ACTIONS: dict[str, list[dict]] = {
    "tuyen_sinh": [
        {"label": "Phê duyệt hồ sơ", "status": "approved_ts"},
        {"label": "Rút hồ sơ", "status": "withdrawn"},
    ],
    "marcom_tuyen_sinh": [
        {"label": "Phê duyệt hồ sơ", "status": "approved_ts"},
        {"label": "Rút hồ sơ", "status": "withdrawn"},
    ],
    "mba": [
        {"label": "Chuyển phỏng vấn", "status": "interview"},
        {"label": "Đỗ", "status": "passed"},
        {"label": "Trượt", "status": "failed"},
        {"label": "Rút hồ sơ", "status": "withdrawn"},
    ],
    "master_chuyen_nganh": [
        {"label": "Chuyển phỏng vấn", "status": "interview"},
        {"label": "Đỗ", "status": "passed"},
        {"label": "Trượt", "status": "failed"},
        {"label": "Rút hồ sơ", "status": "withdrawn"},
    ],
    "ke_toan": [
        {"label": "Chốt nhập học (official)", "status": "official"},
        {"label": "Rút hồ sơ (có ghi chú)", "status": "withdrawn"},
    ],
}

# Điều phối chỉ thấy hồ sơ sau khi TS duyệt (và các bước sau)
COORDINATOR_VISIBLE_STATUSES = {
    "approved_ts",
    "interview",
    "passed",
    "failed",
    "paid",
    "official",
    "withdrawn",
}

# Kế toán tập trung hồ sơ đã đỗ / đang thu phí
ACCOUNTING_FOCUS_STATUSES = {"passed", "paid", "official", "withdrawn"}

COORDINATOR_DEPTS = {"mba", "master_chuyen_nganh"}
ADMISSIONS_DEPTS = {"tuyen_sinh", "marcom_tuyen_sinh"}
ACCOUNTING_DEPTS = {"ke_toan"}


def actor_may_transition(dept_codes: list[str], current: str, new_status: str) -> tuple[bool, str]:
    rule = STATUS_TRANSITIONS.get(current)
    if not rule:
        return False, f"Không có quy tắc cho trạng thái '{current}'"
    if new_status not in rule["to"]:
        return False, f"Không được chuyển {current} → {new_status}. {rule['label']}"
    codes = {c for c in (dept_codes or []) if c}
    if not codes:
        return False, "Không xác định được bộ phận của người dùng — từ chối thao tác."
    allowed = set(rule["by_departments"])
    if not allowed.intersection(codes):
        return False, (
            f"Bộ phận của bạn không được phép thao tác này. "
            f"Cần một trong: {', '.join(sorted(rule['by_departments']))}"
        )
    return True, rule["label"]


def is_accounting_actor(dept_codes: list[str] | None, *, is_admin: bool = False) -> bool:
    """Kế toán / Thủ quỹ (và Admin/IT) — quản lý học phí xuyên suốt mọi CT."""
    codes = set(dept_codes or [])
    if is_admin:
        return True
    return bool(codes & (ACCOUNTING_DEPTS | {"admin_he_thong", "it"}))


def scopes_for_accounting(
    dept_codes: list[str] | None,
    program_scopes: list[str] | None = None,
    *,
    is_admin: bool = False,
) -> list[str]:
    """
    Sổ học phí / công nợ là nghiệp vụ toàn hệ thống: Kế toán luôn thấy mọi chương trình.
    Vai trò Điều phối kèm theo (vd. HanhNT) không thu hẹp phạm vi thu phí.
    """
    if is_accounting_actor(dept_codes, is_admin=is_admin):
        return ["*"]
    scopes = list(program_scopes or [])
    return scopes if scopes else ["*"]


def actor_may_mutate_program(scopes: list[str] | None, program_code: str | None) -> tuple[bool, str]:
    """Điều phối chỉ được xử lý hồ sơ thuộc chương trình trong scope."""
    if not program_code:
        return True, ""
    scopes = scopes or []
    if not scopes or "*" in scopes:
        return True, ""
    if program_code in scopes:
        return True, ""
    return False, f"Hồ sơ thuộc chương trình {program_code} ngoài phạm vi của bạn ({', '.join(scopes)})."


def application_actions_for_depts(dept_codes: list[str]) -> list[dict]:
    seen = set()
    actions = []
    for code in dept_codes:
        for a in DEPT_APPLICATION_ACTIONS.get(code, []):
            key = a["status"]
            if key not in seen:
                seen.add(key)
                actions.append(a)
    return actions


def filter_mode_for_depts(dept_codes: list[str]) -> str:
    """Trả về chế độ lọc danh sách hồ sơ theo vai trò."""
    codes = set(dept_codes)
    if codes & COORDINATOR_DEPTS and not (codes & ADMISSIONS_DEPTS):
        return "coordinator"
    if codes & ACCOUNTING_DEPTS and not (codes & (ADMISSIONS_DEPTS | COORDINATOR_DEPTS)):
        return "accounting"
    if codes & ADMISSIONS_DEPTS:
        return "admissions"
    return "all"
