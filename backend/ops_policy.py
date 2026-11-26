"""Write vs view, dual-role program scopes (họp 18/09/2026)."""
from __future__ import annotations

from rbac import DEPT_DEFAULT_PERMISSIONS

# Menu vẫn hiện nhưng không được thêm/sửa/xóa/import (API + UI).
DEPT_VIEW_ONLY: dict[str, set[str]] = {
    "ke_toan": {
        "admissions.applications",
        "admissions.results",
        "admissions.rounds",
        "admissions.pre_enroll",
        "admissions.enrolled_files",
        "admissions.written_exams",
        "programs.structure",
        "programs.courses",
        "teaching.faculty",
        "teaching.grades",
        "students.manage",
        "students.academic",
        "asst.procurement",
        "marcom.campaigns",
        "marcom.events",
        "marcom.assets",
        "marcom.reports",
    },
    "tuyen_sinh": {
        "accounting.fees",
        "accounting.official_list",
        "admissions.written_exams",
    },
    # Điều phối xem phí, ưu đãi, dữ liệu khách hàng và sự kiện; không xác nhận thu, không duyệt chi.
    "mba": {
        "accounting.benefits",
        "accounting.fees",
        "accounting.official_list",
        "admissions.crm_source",
        "admissions.crm_activities",
        "admissions.crm_reminders",
        "admissions.events",
    },
    "marcom": {
        "admissions.results",
        "admissions.applications",
        "admissions.rounds",
    },
    "giang_vien": set(),
    "logistic": {
        "teaching.schedule",
        "reports.dashboard",
    },
    "khao_thi": {
        "admissions.verification_queue",
        "admissions.neu_prep",
        "admissions.applications",
        "admissions.results",
        "admissions.rounds",
        "admissions.round_docs.view",
    },
    "thanh_tra": {
        "admissions.verification_queue",
        "admissions.neu_prep",
        "admissions.applications",
        "admissions.results",
        "admissions.rounds",
        "admissions.round_docs.view",
    },
    "hoc_vien": {
        "student.schedule",
        "student.results",
        "student.library",
        "student.lessons",
        "canvas.student",
    },
    "master_chuyen_nganh": {"accounting.fees"},
}

FINANCE_PERM_PREFIXES = ("accounting.",)
COORD_PERM_PREFIXES = (
    "programs.",
    "teaching.",
    "students.",
    "classes.",
    "asst.intl_",
    "intl.",
)
COORD_PERM_CODES = {
    "admissions.written_exams",
    "admissions.interviews",
    "admissions.results",
    "admissions.pre_enroll",
    "admissions.enrolled_files",
    "admissions.student_numbering",
    "teaching.review_batches",
}


def can_write_perm(actor: dict | None, perm_code: str) -> bool:
    """True if any department grants write (not view-only) for this menu code."""
    if not actor or not actor.get("ok"):
        return False
    if actor.get("is_admin"):
        return True
    depts = list(actor.get("dept_codes") or [])
    if "admin_he_thong" in depts and not str(perm_code).startswith("admin."):
        return True
    if "it" in depts and perm_code in ("canvas.it", "reports.dashboard"):
        return perm_code == "canvas.it"
    codes = set(actor.get("permission_codes") or [])
    if perm_code not in codes and not actor.get("is_admin"):
        # still allow write if dept default includes it (session lag)
        pass
    for d in depts:
        if d == "ban_giam_doc":
            continue  # Giám đốc: chỉ xem
        if d == "tro_ly_bgd":
            if str(perm_code).startswith("admin."):
                continue
            granted = set(DEPT_DEFAULT_PERMISSIONS.get(d) or [])
            if perm_code in granted or perm_code in codes:
                return True
            continue
        granted = set(DEPT_DEFAULT_PERMISSIONS.get(d) or [])
        if perm_code not in granted and perm_code not in codes:
            continue
        if perm_code in DEPT_VIEW_ONLY.get(d, set()):
            continue
        if d in ("khao_thi", "thanh_tra"):
            return False
        return True
    return False


def scopes_for_perm(actor: dict | None, perm_code: str | None) -> list[str]:
    """HanhNT: finance * ; coordinator perms → MBA only."""
    if not actor:
        return ["*"]
    if actor.get("is_admin"):
        return ["*"]
    depts = set(actor.get("dept_codes") or [])
    base = list(actor.get("program_scopes") or [])
    if "ke_toan" in depts and ("mba" in depts or "master_chuyen_nganh" in depts):
        code = perm_code or ""
        finance = code.startswith(FINANCE_PERM_PREFIXES) or code in (
            "admissions.round_docs",
            "admissions.doc_types",
            "asst.payments",
            "canvas.accounting",
        )
        coord = (
            code.startswith(COORD_PERM_PREFIXES)
            or code in COORD_PERM_CODES
        )
        if finance and not coord:
            return ["*"]
        if coord:
            out = []
            if "mba" in depts:
                out.append("MBA")
            if "master_chuyen_nganh" in depts:
                out.extend(["MMS", "MSCM"])
            return out or ["MBA"]
    if "ke_toan" in depts and code_is_finance(perm_code):
        return ["*"]
    return base if base else ["*"]


def code_is_finance(perm_code: str | None) -> bool:
    return bool(perm_code) and str(perm_code).startswith("accounting.")


def deny_write_message(perm_code: str) -> str:
    return (
        "Bạn chỉ được xem chức năng này — không thêm/sửa/xóa/import. "
        f"({perm_code})"
    )
