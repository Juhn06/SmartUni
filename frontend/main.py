"""
Flask frontend for user management.
"""
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

# Load .env before reading config (for local runs; Docker uses env vars)
load_dotenv(Path(__file__).resolve().parent / ".env")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["JSON_SORT_KEYS"] = False
# Behind host nginx (https://cfvg.neu.edu.vn → :8027)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
_scheme = (os.environ.get("PREFERRED_URL_SCHEME") or "http").strip().lower()
if _scheme in ("http", "https"):
    app.config["PREFERRED_URL_SCHEME"] = _scheme
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "").lower() in (
    "1",
    "true",
    "yes",
)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

API_BASE = os.environ.get("API_BASE_URL", "http://127.0.0.1:8026").rstrip("/")
USERS_URL = f"{API_BASE}/users"

LOGIN_REQUIRED = os.environ.get("LOGIN_REQUIRED", "true").lower() == "true"
from admission_bot_routes import PUBLIC_ENDPOINTS as ADMISSION_PUBLIC_ENDPOINTS
STORAGES_URL = f"{API_BASE}/storages"
ARTICLES_URL = f"{API_BASE}/articles"
THESES_URL = f"{API_BASE}/theses"
BOOKS_URL = f"{API_BASE}/books"
PROJECTS_URL = f"{API_BASE}/projects"


def _current_user_id():
    """Current logged-in user id from session, or None."""
    u = session.get("user") or {}
    uid = u.get("id")
    return int(uid) if uid is not None else None


def _user_scopes_header():
    """
    Header scope cho API ops.
    Kế toán / Thủ quỹ: luôn gửi * — sổ học phí xuyên suốt mọi chương trình
    (không bị thu hẹp bởi vai trò Điều phối kèm theo).
    """
    scopes = (session.get("user") or {}).get("program_scopes") or ["*"]
    headers = {}
    uid = _current_user_id()
    if uid is not None:
        headers["X-User-Id"] = str(uid)
    depts = (session.get("user") or {}).get("departments") or []
    codes = [d.get("code") for d in depts if d.get("code")]
    accounting_depts = {"ke_toan", "admin_he_thong", "it"}
    dual_coord = bool(set(codes) & {"mba", "master_chuyen_nganh"})
    if (session.get("user") or {}).get("is_admin"):
        headers["X-Program-Scopes"] = "*"
    elif set(codes) & {"admin_he_thong", "it"}:
        headers["X-Program-Scopes"] = "*"
    elif accounting_depts.intersection(codes) and not dual_coord:
        headers["X-Program-Scopes"] = "*"
    elif "*" in scopes:
        headers["X-Program-Scopes"] = "*"
    else:
        headers["X-Program-Scopes"] = ",".join(scopes)
    if codes:
        headers["X-Dept-Codes"] = ",".join(codes)
    from ops_modules import filter_role_mode

    headers["X-Role-Mode"] = filter_role_mode(codes)
    # Portal HV: forward email so library/lessons scope to this student
    u = session.get("user") or {}
    student_email = (u.get("student_email") or u.get("contact_email") or "").strip()
    if not student_email and "hoc_vien" in codes:
        # E2E / provisioned students: resolve contact email from known logins later on API;
        # still send login as hint when it looks like an email.
        login = (u.get("email") or "").strip()
        if "@" in login:
            student_email = login
    if student_email:
        headers["X-Student-Email"] = student_email
    return headers


def _dept_codes():
    depts = (session.get("user") or {}).get("departments") or []
    return [d.get("code") for d in depts if d.get("code")]


def _application_row_actions():
    from ops_modules import application_actions_for_depts

    actions = application_actions_for_depts(_dept_codes())
    if _ui_lang() != "en":
        return actions
    en_labels = {
        "approved_ts": "Approve application",
        "interview": "Move to interview",
        "passed": "Pass",
        "failed": "Fail",
        "withdrawn": "Withdraw",
    }
    out = []
    for a in actions:
        b = dict(a)
        if a.get("status") in en_labels:
            b["label"] = en_labels[a["status"]]
        out.append(b)
    return out


def _normalize_perm_codes(raw) -> list[str]:
    """Accept list of codes or list of {code: ...} dicts from API/session."""
    out: list[str] = []
    for p in raw or []:
        if isinstance(p, str) and p.strip():
            out.append(p.strip())
        elif isinstance(p, dict) and p.get("code"):
            out.append(str(p["code"]).strip())
    return out


def _fetch_user_access(uid: int, lang: str | None = None) -> dict:
    """Live access payload from backend (includes permission_codes + nav)."""
    params = {}
    if lang:
        params["lang"] = lang
    try:
        resp = requests.get(
            f"{USERS_URL}/{int(uid)}/access",
            params=params or None,
            timeout=4,
        )
        if resp.status_code == 200:
            return resp.json() or {}
    except Exception:
        pass
    return {}


def _session_permission_codes(u: dict | None = None) -> list[str]:
    """Effective permission codes for nav / _user_has_perm (cached on flask.g).

    Prefer backend ``GET /users/<id>/access`` (works in Docker — nav built server-side).
    Session / dept defaults are offline fallbacks when API is unreachable.
    """
    from flask import g

    cached = getattr(g, "_smartuni_perm_codes", None)
    if cached is not None:
        return cached

    u = u or (session.get("user") or {})
    codes: list[str] = []

    def _rbac():
        import sys
        from pathlib import Path

        here = Path(__file__).resolve().parent
        for candidate in (here, here.parent / "backend"):
            if (candidate / "rbac.py").exists() and str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
                break
        import rbac as rbac_mod

        return rbac_mod

    uid = u.get("id")
    if uid:
        data = _fetch_user_access(int(uid), lang=_ui_lang())
        codes = _normalize_perm_codes(
            data.get("permission_codes") or data.get("permissions")
        )
        # Cache nav from same response for inject_nav (avoid double HTTP + need for rbac.py)
        if "nav" in data:
            g._smartuni_nav = data.get("nav") or []

    if not codes and u.get("is_admin"):
        try:
            codes = [m["code"] for m in _rbac().MENU_ITEMS]
        except Exception:
            codes = _normalize_perm_codes(u.get("permissions"))

    if not codes:
        codes = _normalize_perm_codes(u.get("permissions"))

    if not codes:
        try:
            rbac_mod = _rbac()
            dept_map = rbac_mod.DEPT_DEFAULT_PERMISSIONS
            seen = set()
            for d in u.get("departments") or []:
                code = d.get("code") if isinstance(d, dict) else None
                for p in dept_map.get(code) or []:
                    if p not in seen:
                        seen.add(p)
                        codes.append(p)
        except Exception:
            pass

    # BGD: session cookie strips >40 perms — restore full ops view from dept.
    if _is_exec_viewer():
        try:
            ops_codes = list(_rbac().OPS_VIEW_CODES)
            if not codes:
                codes = ops_codes
            else:
                seen = set(codes)
                for p in ops_codes:
                    if p not in seen:
                        seen.add(p)
                        codes.append(p)
        except Exception:
            pass

    g._smartuni_perm_codes = codes
    return codes


def _user_has_perm(code: str) -> bool:
    u = session.get("user") or {}
    # Chỉ ThaoP (is_admin) bypass toàn bộ; Admin/NghiND dùng danh sách quyền tường minh
    if u.get("is_admin"):
        return True
    return code in _session_permission_codes(u)


def _slim_session_user(data: dict) -> dict:
    """Keep session cookie under browser ~4KB limit.

    Nav / effective rights are rebuilt each request from live ``/users/<id>/access``.
    Session may keep a small permission code list as offline fallback only.
    """
    is_admin = bool(data.get("is_admin", False))
    depts = data.get("departments") or []
    slim_depts = [
        {"id": d.get("id"), "code": d.get("code"), "name": d.get("name")}
        for d in depts
        if isinstance(d, dict)
    ]
    avatar = data.get("avatar_path") or None
    if avatar:
        avatar = str(avatar).replace("\\", "/").lstrip("/")
    # Never stuff large perm lists into the cookie — inject_nav loads live access by user id
    perm_codes: list[str] = []
    if not is_admin:
        raw = _normalize_perm_codes(data.get("permissions"))
        if 0 < len(raw) <= 40:
            perm_codes = raw
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "email": data.get("email"),
        "is_admin": is_admin,
        "is_locked": bool(data.get("is_locked", False)),
        "departments": slim_depts,
        "permissions": perm_codes,
        "program_scopes": list(data.get("program_scopes") or []),
        "lang": data.get("lang") or "vi",
        "theme": data.get("theme") or "courses",
        "theme_manual": bool(data.get("theme_manual")),
        "gender": (data.get("gender") or None),
        "birth_year": data.get("birth_year"),
        "avatar_path": avatar,
    }


def _user_dept_codes() -> list[str]:
    depts = (session.get("user") or {}).get("departments") or []
    return [d.get("code") for d in depts if isinstance(d, dict) and d.get("code")]


def _is_exec_viewer() -> bool:
    """Giám đốc: xem mọi báo cáo + dữ liệu chi tiết (không ghi). Trợ lý BGD ghi được asst/ops."""
    u = session.get("user") or {}
    if u.get("is_admin"):
        return False
    codes = set(_user_dept_codes())
    if codes & {"admin_he_thong", "it"}:
        return False
    return bool(codes & {"ban_giam_doc"})


def _perm_is_view_only(perm_code: str) -> bool:
    """Kế toán xem điểm, Khảo thí/Thanh tra, Marcom kết quả… — không ghi."""
    try:
        from ops_policy import can_write_perm

        u = session.get("user") or {}
        if u.get("is_admin"):
            return False
        actor = {
            "ok": True,
            "is_admin": False,
            "dept_codes": list(_dept_codes()),
            "permission_codes": list(_session_permission_codes(u)),
        }
        return not can_write_perm(actor, perm_code)
    except Exception:
        return False


def _can_open_ops_module(code: str) -> bool:
    """Whether current user may navigate into an ops function (RBAC-aware)."""
    if not code:
        return False
    u = session.get("user") or {}
    if u.get("is_admin") or _is_exec_viewer():
        return not str(code).startswith("admin.")
    return _user_has_perm(code)


def _summary_deep_links() -> dict:
    """KPI / pipeline shortcuts on Dashboard — only links the user can open."""
    mapping = {
        "applications": ("admissions.applications", "/ops/admissions/applications"),
        "fees_pending": ("accounting.fees", "/ops/accounting/fees?status=pending"),
        "fees_paid": ("accounting.fees", "/ops/accounting/fees?status=paid"),
        "classes": ("classes.manage", "/ops/classes"),
        "faculty": ("teaching.faculty", "/ops/teaching/faculty"),
        "alumni": ("alumni.members", "/ops/alumni"),
        "students_active": ("students.manage", "/ops/students"),
        "official": ("accounting.official_list", "/ops/accounting/official"),
        "fees_overdue": ("accounting.charges", "/ops/accounting/charges?status=overdue"),
        "fees_due_soon": ("accounting.charges", "/ops/accounting/charges?status=due_soon"),
        "fees_unpaid": ("accounting.charges", "/ops/accounting/charges?status=unpaid"),
        "overdue_students": ("accounting.tuition_tracker", "/ops/accounting/tuition-tracker?status=overdue"),
        "fee_alerts": ("accounting.fee_alerts", "/ops/accounting/fee-alerts"),
        "tasks_open": ("asst.exec_tasks", "/ops/asst/tasks"),
        "leave_pending": ("asst.leave", "/ops/asst/leave"),
        "intl_faculty_prep": ("asst.intl_faculty", "/ops/asst/intl-faculty"),
        "submitted": ("admissions.applications", "/ops/admissions/applications?status=submitted"),
        "approved_ts": ("admissions.applications", "/ops/admissions/applications?status=approved_ts"),
        "interview": ("admissions.interviews", "/ops/admissions/interviews"),
        "passed": ("admissions.results", "/ops/admissions/results?status=passed"),
        "failed": ("admissions.results", "/ops/admissions/results?status=failed"),
        "paid": ("accounting.fees", "/ops/accounting/fees?status=paid"),
        "withdrawn": ("admissions.applications", "/ops/admissions/applications?status=withdrawn"),
    }
    out = {}
    for key, (perm, path) in mapping.items():
        if _can_open_ops_module(perm):
            out[key] = path
    return out


def _is_org_admin_dept() -> bool:
    """Super Admin (ThaoP) hoặc BP admin_he_thong / it — dùng cho UI chrome, không bypass quyền."""
    u = session.get("user") or {}
    if u.get("is_admin"):
        return True
    return bool(set(_user_dept_codes()) & {"admin_he_thong", "it"})


def _fetch_deployment_mode() -> str:
    """Read Admin deployment_mode; default development (show workflow hints)."""
    from flask import g

    cached = getattr(g, "_deployment_mode", None)
    if cached in ("development", "production"):
        return cached
    mode = "development"
    try:
        resp = requests.get(f"{API_BASE}/admin/settings", timeout=3)
        if resp.status_code == 200:
            data = resp.json() or {}
            mode = (data.get("deployment_mode") or "development").strip().lower()
    except requests.RequestException:
        pass
    if mode not in ("development", "production"):
        mode = "development"
    g._deployment_mode = mode
    return mode


def _show_workflow_hints() -> bool:
    """Hide 'Luồng: …' guides when Admin sets Production."""
    return _fetch_deployment_mode() != "production"


def _filter_admin_sys_groups(groups: list) -> list:
    """Ẩn nhóm/mục Admin hub mà user không có quyền."""
    route_perm = {
        "admin_users": "admin.users",
        "admin_departments": "admin.departments",
        "admin_permissions": "admin.permissions",
        "admin_suggestions": "admin.suggestions",
        "admin_status_catalog": "admin.status_catalog",
        "admin_book_categories": "admin.status_catalog",
        "admin_settings": "admin.reports",
        "admin_system_hub": "admin.reports",
        "admin_index": "admin.reports",
        "ops_reports": "reports.dashboard",
    }
    out = []
    for g in groups or []:
        items = []
        for it in g.get("items") or []:
            need = route_perm.get(it.get("route") or "")
            if not need or _user_has_perm(need):
                items.append(it)
        if items:
            ng = dict(g)
            ng["items"] = items
            out.append(ng)
    return out


def _is_accounting_ui() -> bool:
    """Kế toán / Admin / IT — được thao tác xác nhận phí & official."""
    u = session.get("user") or {}
    if u.get("is_admin"):
        return True
    return bool(set(_dept_codes()) & {"ke_toan", "admin_he_thong", "it"})


def _is_admissions_staff_only() -> bool:
    """Tuyển sinh thuần (không kiêm ĐP / KT / Admin) — UI theo vai trò TS."""
    codes = set(_dept_codes())
    if codes & {"mba", "master_chuyen_nganh", "ke_toan", "admin_he_thong", "it"}:
        return False
    if (session.get("user") or {}).get("is_admin"):
        return False
    return bool(codes & {"tuyen_sinh", "marcom_tuyen_sinh"})


def _is_coordinator_ui() -> bool:
    codes = set(_dept_codes())
    u = session.get("user") or {}
    if u.get("is_admin") or codes & {"admin_he_thong", "it"}:
        return True
    return bool(codes & {"mba", "master_chuyen_nganh"})


def _apply_admissions_ops_role(cfg: dict, perm_code: str) -> dict:
    """Hiệu chỉnh thao tác theo mô tả nghiệp vụ Tuyển sinh (Admission Process).

    TS: tư vấn/lead, checklist hồ sơ, phê duyệt, theo dõi thi-PV-phí-official,
        xuất DS gửi ĐP / Khảo thí — không gán SBD, không tạo boards, không mark-paid.
    ĐP: tổ chức thi/PV, điểm, kết luận đỗ-trượt.
    KT: xác nhận Deposit / official.
    """
    cfg = dict(cfg)
    lang = _ui_lang()
    admissions_only = _is_admissions_staff_only()
    accounting = _is_accounting_ui()
    coordinator = _is_coordinator_ui()

    # Phí: chỉ KT mới có nút xác nhận nộp / chốt official
    if perm_code == "accounting.fees" and not accounting:
        cfg["fee_actions"] = False
        cfg["mode"] = "view"
        cfg["primary_action"] = None
        cfg["allow_delete"] = False
        cfg["row_buttons"] = [
            b for b in (cfg.get("row_buttons") or [])
            if (b.get("id") or "") not in ("create_receipt", "row_create")
        ]
        if admissions_only:
            cfg["actions"] = [
                {"id": "export_excel", "label": "Export Excel" if lang == "en" else "Xuất Excel"},
                {"id": "print_page", "label": "Print" if lang == "en" else "In"},
            ]

    if perm_code == "accounting.official_list":
        if admissions_only and not accounting:
            cfg["canvas_export_roster"] = False
            # Giữ Xuất Excel + Gửi khảo thí; bỏ Canvas
            kept = []
            for a in cfg.get("actions") or []:
                label = a.get("label") if isinstance(a, dict) else str(a)
                aid = a.get("id") if isinstance(a, dict) else str(a)
                blob = f"{aid} {label}".lower()
                if "canvas" in blob or "roster" in blob:
                    continue
                kept.append(a if isinstance(a, dict) else {"id": aid, "label": label})
            cfg["actions"] = kept

    if not admissions_only:
        # Điều phối MBA: cột hồ sơ theo Student list MBA34
        if coordinator and perm_code == "admissions.applications":
            cfg["columns"] = [
                ("identifier", "Mã định danh"),
                ("english_cert_score", "Điểm TA"),
                ("intake_session", "Session"),
                ("student_code_mba", "Student code"),
                ("full_name", "Họ tên"),
                ("gender", "Gd"),
                ("university", "Trường ĐH"),
                ("eco_background", "Eco"),
                ("company", "Đơn vị"),
                ("job_title", "Vị trí"),
                ("avg_score", "TB /20"),
                ("interview_score", "PV /20"),
                ("written_score", "Viết /20"),
                ("confirmation_status", "Confirm"),
                ("board_decision", "HĐ TS"),
                ("status", "Trạng thái"),
            ]
            # Giữ thao tác ĐP (SBD / import điểm qua written_exams)
            acts = list(cfg.get("actions") or [])
            labels = " ".join(
                (a.get("label") if isinstance(a, dict) else str(a)) for a in acts
            ).lower()
            if "mba34" not in labels and "student list" not in labels:
                acts.append(
                    {"id": "export_excel", "label": "Export MBA roster (Excel)"}
                    if lang == "en"
                    else {"id": "export_excel", "label": "Xuất DS thí sinh MBA"}
                )
            # ĐP: chọn thí sinh theo đợt → tạo lịch phỏng vấn từ DS đã chọn
            acts.append(
                {"id": "create_interview_boards_selected",
                 "label": "Create interview boards (selected)"}
                if lang == "en"
                else {"id": "create_interview_boards_selected",
                      "label": "Tạo lịch PV (DS đã chọn)"}
            )
            acts.append(
                {"id": "print_page", "label": "Print list"}
                if lang == "en"
                else {"id": "print_page", "label": "In danh sách"}
            )
            cfg["actions"] = acts
            cfg["round_filter"] = True
            cfg["select_interview"] = True
        if perm_code == "admissions.applications":
            if coordinator:
                cfg["row_actions"] = [
                    a for a in (cfg.get("row_actions") or [])
                    if (a.get("status") if isinstance(a, dict) else "") in (
                        "interview", "passed", "failed", "withdrawn",
                    )
                ]
            elif accounting:
                cfg["row_actions"] = [
                    a for a in (cfg.get("row_actions") or [])
                    if (a.get("status") if isinstance(a, dict) else "") in ("withdrawn",)
                ]
        if perm_code == "admissions.written_exams" and not accounting:
            cfg["row_buttons"] = [
                b for b in (cfg.get("row_buttons") or [])
                if (b.get("id") or "") != "mark_exam_fee"
            ]
        if coordinator and perm_code == "admissions.results":
            cfg["columns"] = [
                ("student_code_mba", "Student code"),
                ("full_name", "Họ tên"),
                ("intake_session", "Session"),
                ("avg_score", "TB"),
                ("interview_score", "PV"),
                ("written_score", "Viết"),
                ("confirmation_status", "Confirm"),
                ("final_result", "KQ"),
                ("status", "Trạng thái"),
                ("email", "Email"),
            ]
        return cfg

    # —— Tuyển sinh thuần ——
    coord_mutate = (
        "assign exam",
        "import round",
        "create interview",
        "gán sbd",
        "import điểm",
        "tạo bảng",
        "create boards",
    )

    def _filter_actions(actions, *, drop_hints, keep_extra=None):
        keep_extra = keep_extra or ()
        out = []
        seen = set()
        for a in actions or []:
            if isinstance(a, dict):
                aid = str(a.get("id") or "")
                label = str(a.get("label") or aid)
            else:
                aid = str(a)
                label = aid
            blob = f"{aid} {label}".lower()
            if any(h in blob for h in drop_hints) and not any(k in blob for k in keep_extra):
                continue
            key = aid or label
            if key in seen:
                continue
            seen.add(key)
            out.append(a if isinstance(a, dict) else {"id": aid, "label": label})
        return out

    if perm_code == "admissions.applications":
        cfg["actions"] = _filter_actions(
            cfg.get("actions"),
            drop_hints=coord_mutate + ("assign", "import round", "export written"),
        )
        # Đảm bảo có xuất DS gửi ĐP
        labels = " ".join(
            (a.get("label") if isinstance(a, dict) else str(a)) for a in (cfg.get("actions") or [])
        ).lower()
        if "điều phối" not in labels and "coord" not in labels:
            cfg.setdefault("actions", []).append(
                {"id": "export_coord_handoff", "label": "Xuất DS gửi Điều phối"}
                if lang != "en"
                else {"id": "export_coord_handoff", "label": "Export list for Coordinator"}
            )
        # TS không sửa điểm viết / SBD qua form — vẫn sửa checklist & hồ sơ
        buttons = []
        keep_ids = {
            "view_application", "edit_application", "update_application",
            "manage_app_docs", "confirm_examinee", "register_examinee",
            "open_person_dossier",
        }
        for b in cfg.get("row_buttons") or []:
            if b.get("id") in keep_ids:
                buttons.append(b)
        cfg["row_buttons"] = buttons or [{"id": "view_application", "label": "Xem chi tiết"}]
        cfg["row_actions"] = [
            a for a in (cfg.get("row_actions") or [])
            if (a.get("status") if isinstance(a, dict) else "") in ("approved_ts", "withdrawn")
        ]

    if perm_code == "admissions.written_exams":
        cfg["row_buttons"] = [
            b for b in (cfg.get("row_buttons") or [])
            if (b.get("id") or "") not in ("mark_exam_fee", "list_exam_board")
        ]
        cfg["actions"] = _filter_actions(
            cfg.get("actions"),
            drop_hints=coord_mutate + ("assign", "import", "create"),
            keep_extra=("export", "xuất"),
        )
        if not cfg["actions"]:
            cfg["actions"] = [
                {"id": "export_excel", "label": "Export written exam" if lang == "en" else "Xuất DS thi viết"}
            ]
        cfg["mode"] = "view"

    if perm_code == "admissions.interviews":
        cfg["actions"] = _filter_actions(
            cfg.get("actions"),
            drop_hints=coord_mutate + ("create",),
            keep_extra=("in lịch", "print", "lịch"),
        )
        # TS hỗ trợ buổi PV, không lập hội đồng — ẩn Thêm mới tạo board
        cfg["primary_action"] = None
        cfg["row_buttons"] = [
            b for b in (cfg.get("row_buttons") or [])
            if (b.get("id") or "") not in ("create_interview_boards", "row_create")
        ]

    if perm_code == "marcom.events" and admissions_only:
        # TS đồng tổ chức: không tạo/xóa sự kiện; được quản lý ĐK + follow-up + xuất
        cfg["primary_action"] = None
        cfg["allow_delete"] = False
        cfg["mode"] = "manage"
        cfg["actions"] = [
            {"id": "export_event_registrants", "label": "Export registrants" if lang == "en" else "Xuất DS đăng ký"},
            {"id": "export_event_followup", "label": "Export follow-up file" if lang == "en" else "Xuất file sau SK (mức quan tâm)"},
            {"id": "print_page", "label": "Print" if lang == "en" else "In danh sách"},
        ]
        cfg["row_buttons"] = [
            {"id": "manage_event_registrants", "label": "Registrants / follow-up" if lang == "en" else "DS đăng ký / follow-up"},
            {"id": "edit_marcom_event", "label": "Edit stages" if lang == "en" else "Sửa giai đoạn"},
        ]

    if perm_code == "marcom.leads" and admissions_only:
        cfg["primary_action"] = None
        cfg["allow_delete"] = False
        cfg["row_buttons"] = [
            {"id": "accept_lead", "label": "Confirm receipt" if lang == "en" else "Xác nhận tiếp nhận"},
            {"id": "open_person_dossier", "label": "Shared profile" if lang == "en" else "Hồ sơ chung"},
        ]

    return cfg


def _apply_exec_view_only(cfg: dict) -> dict:
    """Strip mutate controls; keep view/detail + Print / Export Excel for BGD & Trợ lý."""
    cfg = dict(cfg)
    cfg["mode"] = "view"
    cfg["primary_action"] = None
    cfg["list_add_action"] = None
    cfg["allow_delete"] = False
    cfg["fee_actions"] = False
    cfg["charge_actions"] = False
    cfg["leave_actions"] = False
    cfg["row_actions"] = []
    cfg["canvas_export_roster"] = False
    cfg["canvas_row_export"] = False
    cfg["canvas_it_panel"] = False
    cfg["import_bulk"] = False
    cfg["bulk_select"] = False
    cfg["import_entity"] = None
    buttons = []
    for b in cfg.get("row_buttons") or []:
        bid = (b.get("id") or "")
        if bid.startswith("edit_") or bid.startswith("create_") or bid in (
            "generic_edit", "update_application", "edit_student_lifecycle",
            "row_create", "generic_create", "asst_payment", "enroll_official", "copy_version",
        ):
            continue
        if bid.startswith("view_") or bid in (
            "open_person_dossier",
            "open_eval",
            "view_evals",
            "view_courses",
            "view_students",
            "view_program",
            "update_student_profile",
            "send_fee_proof",
            "manage_app_docs",
            "print_transcript",
            "print_progress",
            "print_student_progress",
        ):
            buttons.append(b)
    cfg["row_buttons"] = buttons
    cfg["row_edit_action"] = None
    cfg["edit_path"] = None
    # Always offer Print + Export Excel on every list for executive report viewing
    lang = _ui_lang()
    if lang == "en":
        report_actions = [
            {"id": "print_page", "label": "Print"},
            {"id": "export_excel", "label": "Export Excel"},
        ]
    else:
        report_actions = [
            {"id": "print_page", "label": "In"},
            {"id": "export_excel", "label": "Xuất Excel"},
        ]
    # Keep existing read-only export/print actions; drop create/import/mutate labels
    mutate_hints = (
        "thêm",
        "tạo",
        "gửi",
        "import",
        "assign",
        "create",
        "add",
        "đồng bộ",
        "bàn giao",
        "mở điểm",
        "qr",
        "enroll",
        "copy",
        "notify",
        "hand-",
        "sync",
    )
    kept = []
    seen = set()
    for a in cfg.get("actions") or []:
        if isinstance(a, dict):
            aid = str(a.get("id") or "")
            label = str(a.get("label") or aid)
        else:
            aid = str(a)
            label = aid
        blob = f"{aid} {label}".lower()
        if any(h in blob for h in mutate_hints):
            continue
        key = aid or label
        if key in seen:
            continue
        seen.add(key)
        kept.append(a if isinstance(a, dict) else {"id": aid, "label": label})
    for a in report_actions:
        if a["id"] not in seen and a["label"] not in seen:
            kept.append(a)
            seen.add(a["id"])
    cfg["actions"] = kept
    cfg["exec_view_only"] = True
    return cfg


def _ui_lang() -> str:
    from i18n import normalize_lang

    u = session.get("user") or {}
    dept_codes = {
        d.get("code")
        for d in (u.get("departments") or [])
        if isinstance(d, dict) and d.get("code")
    }
    if dept_codes == {"mba"}:
        return "en"
    pref = session.get("ui_lang_pref")
    if pref:
        return normalize_lang(pref)
    u = session.get("user") or {}
    if u.get("lang"):
        return normalize_lang(u.get("lang"))
    cookie = request.cookies.get("smartuni_lang") if request else None
    return normalize_lang(cookie or "vi")


def _flash_t(key: str, **kwargs):
    from i18n import t

    flash(t(key, _ui_lang(), **kwargs))


def _fetch_status_catalog():
    """Load configurable status options/labels from backend."""
    try:
        resp = requests.get(
            f"{API_BASE}/ops/status-options",
            params={"lang": _ui_lang()},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json() or {}
            return {
                "options": data.get("options") or {},
                "labels": data.get("labels") or {},
                "categories": data.get("categories") or [],
            }
    except Exception:
        pass
    return {"options": {}, "labels": {}, "categories": []}


def _localized_status_labels():
    from i18n import status_label
    from ops_modules import STATUS_LABELS

    lang = _ui_lang()
    labels = {k: status_label(k, lang, STATUS_LABELS) for k in STATUS_LABELS}
    catalog = _fetch_status_catalog()
    labels.update(catalog.get("labels") or {})
    return labels


def _status_options_map():
    return _fetch_status_catalog().get("options") or {}


def _rebuild_session_nav(lang: str | None = None):
    """Update UI language in session (nav is not stored — rebuilt per request)."""
    u = session.get("user")
    if not u:
        return
    lang = lang or _ui_lang()
    u = dict(u)
    u["lang"] = lang
    u.pop("nav", None)
    session["user"] = _slim_session_user(u)
    session.modified = True


def _ops_get(path: str, params=None):
    headers = _user_scopes_header()
    return requests.get(
        f"{API_BASE}{path}",
        params=params or {},
        headers=headers,
        timeout=8,
    )


@app.context_processor
def inject_nav():
    from flask import g

    u = session.get("user") or {}
    feature_code = getattr(g, "feature_code", None)
    if not feature_code and request.endpoint:
        # Detail / sub-pages → parent ops feature for feedback tagging
        DETAIL_FEATURE_MAP = {
            "ops_course_detail": "programs.courses",
            "ops_class_students_page": "classes.manage",
            "ops_assignment_lessons": "teaching.lessons",
            "ops_class_lesson_detail": "teaching.lessons",
            "ops_lesson_preview": "teaching.lessons",
            "ops_lesson_learning_stats": "teaching.lessons",
            "ops_assignment_learning_stats": "teaching.lessons",
            "ops_lesson_comments_inbox": "teaching.lessons",
            "ops_student_lessons": "student.lessons",
            "ops_material_preview": "teaching.materials",
            "ops_interview_detail": "admissions.interviews",
            "ops_gradebook": "teaching.grades",
            "ops_attendance_session": "teaching.attendance",
            "ops_attendance_from_lesson": "teaching.attendance",
            "ops_attendance_scan": "teaching.attendance",
            "ops_practice_ta": "teaching.assignments",
            "ops_practice_hw": "teaching.assignments",
            "ops_practice_submission": "teaching.assignments",
            "ops_practice_do": "teaching.assignments",
            "ops_student_practice": "teaching.assignments",
            "ops_mc_ta": "teaching.assignments",
            "ops_mc_quiz": "teaching.assignments",
            "ops_mc_submission": "teaching.assignments",
            "ops_mc_do": "teaching.assignments",
            "ops_thesis_detail": "teaching.thesis",
            "ops_student_library": "student.library",
            "ops_marcom_event_registrants_page": "marcom.events",
            "ops_marcom_reports": "marcom.reports",
            "ops_canvas_coordinator": "canvas.coordinator",
            "ops_canvas_faculty": "canvas.faculty",
            "ops_canvas_student": "canvas.student",
            "ops_canvas_accounting": "canvas.accounting",
            "ops_canvas_it": "canvas.it",
            "admin_departments": "admin.departments",
            "admin_permissions": "admin.permissions",
            "admin_users": "admin.users",
            "admin_suggestions": "admin.suggestions",
            "admin_status_catalog": "admin.status_catalog",
            "admin_system_hub": "admin.reports",
            "admin_index": "admin.reports",
            "admin_book_categories": "admin.status_catalog",
            "admin_settings": "admin.reports",
            "change_password": "account.password",
            "account_profile": "account.profile",
        }
        feature_code = DETAIL_FEATURE_MAP.get(request.endpoint)
        if not feature_code:
            try:
                import sys
                from pathlib import Path

                be = Path(__file__).resolve().parent.parent / "backend"
                if str(be) not in sys.path:
                    sys.path.insert(0, str(be))
                from rbac import MENU_ITEMS

                for m in MENU_ITEMS:
                    if m.get("route") == request.endpoint:
                        feature_code = m["code"]
                        break
            except Exception:
                pass
    if not feature_code:
        feature_code = request.endpoint or ""
    lang = _ui_lang()
    nav = []
    perms = _session_permission_codes(u) if u else []
    if u:
        from flask import g as flask_g

        # Prefer nav built by backend /access (Docker-safe — no local rbac.py needed)
        cached_nav = getattr(flask_g, "_smartuni_nav", None)
        if isinstance(cached_nav, list):
            nav = cached_nav
        if not nav and u.get("id"):
            data = _fetch_user_access(int(u["id"]), lang=lang)
            nav = data.get("nav") if isinstance(data.get("nav"), list) else []
            if not perms:
                perms = _normalize_perm_codes(
                    data.get("permission_codes") or data.get("permissions")
                )
                flask_g._smartuni_perm_codes = perms
        if not nav and perms:
            # Local-dev fallback when access omits nav but rbac.py is on disk
            try:
                import sys
                from pathlib import Path

                here = Path(__file__).resolve().parent
                for candidate in (here, here.parent / "backend"):
                    if (candidate / "rbac.py").exists() and str(candidate) not in sys.path:
                        sys.path.insert(0, str(candidate))
                        break
                from rbac import build_nav_from_permissions

                nav = build_nav_from_permissions(
                    perms, lang=lang, departments=(u or {}).get("departments")
                )
            except Exception as exc:
                import logging

                logging.getLogger("smartuni").exception(
                    "inject_nav rebuild failed: %s", exc
                )
        try:
            if u.get("lang") != lang:
                slim = _slim_session_user({**u, "lang": lang})
                session["user"] = slim
                session.modified = True
        except Exception:
            pass

    from i18n import t as i18n_t, L_pair
    from admin_nav import ADMIN_SYS_GROUPS

    show_admin_nav = bool(u) and (
        bool(u.get("is_admin"))
        or any(
            c.startswith("admin.")
            for c in perms
        )
    )

    return {
        "nav_groups": nav,
        "user_scopes": u.get("program_scopes") or [],
        "user_departments": u.get("departments") or [],
        "ui_theme": "courses",
        "ui_lang": lang,
        "t": lambda key, **kw: i18n_t(key, lang, **kw),
        "L": lambda vi, en="": L_pair(vi, en or vi, lang),
        "feature_code": feature_code,
        "feature_path": request.path if request else "/",
        "admin_sys_groups": _filter_admin_sys_groups(ADMIN_SYS_GROUPS) if u else [],
        "show_admin_nav": show_admin_nav,
        "deployment_mode": _fetch_deployment_mode() if u else "development",
        "show_workflow_hints": _show_workflow_hints() if u else True,
    }


def _parse_thesis_analysis(text):
    """Parse thesis analysis markdown into list of {num, name, content} for table display."""
    if not text or not isinstance(text, str):
        return []
    import re
    sections = []
    # Match "## N. Section Name" followed by content until next ## or end
    pattern = r"##\s*(\d+)\.\s*([^\n]+)\n(.*?)(?=##\s*\d+\.|$)"
    for m in re.finditer(pattern, text, re.DOTALL):
        num, name, content = m.group(1), m.group(2).strip(), m.group(3).strip()
        sections.append({"num": int(num), "name": name, "content": content})
    # Fallback: if no matches, treat whole text as single section
    if not sections and text.strip():
        sections.append({"num": 0, "name": "Analysis", "content": text.strip()})
    return sections


@app.template_filter("parse_thesis_analysis")
def parse_thesis_analysis_filter(text):
    return _parse_thesis_analysis(text)


@app.before_request
def require_login():
    """Redirect to login if LOGIN_REQUIRED and user not in session."""
    if not LOGIN_REQUIRED:
        return
    if request.endpoint in (
        "login",
        "logout",
        "signup",
        "static",
        "search_index",
        "api_admin_search",
        "set_language",
    ) or request.endpoint in ADMISSION_PUBLIC_ENDPOINTS:
        return
    if "user" not in session:
        # For JSON/fetch requests, return 401 JSON so client can handle (avoids HTML-in-JSON parse error)
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "Session expired. Please log in again.", "login_required": True}), 401
        return redirect(url_for("login", next=request.url))
    if session.get("must_change_password") and request.endpoint not in ("change_password", "logout", "static", "set_language"):
        if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.path.startswith("/api/"):
            return jsonify({"error": "Bạn cần đổi mật khẩu trước.", "must_change_password": True}), 403
        return redirect(url_for("change_password"))


def _api_error(resp, fallback="Something went wrong. Please try again later."):
    """Get error message from API response or fallback."""
    try:
        data = resp.json()
        return data.get("error", fallback)
    except Exception:
        return fallback


def _normalize_storages(data):
    """Ensure storages is a list of dicts with valid integer ids."""
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        if isinstance(data.get("storages"), list):
            items = data["storages"]
        elif "id" in data and "product" in data:
            items = [data]
        else:
            return []
    else:
        return []
    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            sid = item.get("id")
            item = dict(item)
            item["id"] = int(sid) if sid is not None else None
            if item["id"] is not None and item["id"] >= 0:
                result.append(item)
        except (TypeError, ValueError):
            continue
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if session.get("user"):
        return redirect(url_for("ops_home"))
    from admission_bot_routes import render_landing

    return render_landing(API_BASE)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login with username (không dấu) and password."""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = (request.form.get("password") or "").strip()
        if not email or not password:
            _flash_t("login_need")
            return render_template("login.html", email=email)
        try:
            resp = requests.post(
                f"{USERS_URL}/login",
                json={"email": email, "password": password},
                timeout=8,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code == 200:
                from i18n import normalize_lang

                default_lang = normalize_lang(data.get("lang") or "vi")
                preferred = default_lang
                session["ui_lang_pref"] = preferred
                session["user"] = _slim_session_user(
                    {
                        "id": data["id"],
                        "name": data["name"],
                        "email": data["email"],
                        "is_admin": bool(data.get("is_admin", False)),
                        "is_locked": bool(data.get("is_locked", False)),
                        "departments": data.get("departments") or [],
                        "permissions": data.get("permissions") or [],
                        "program_scopes": data.get("program_scopes") or [],
                        "lang": preferred,
                        "theme": data.get("theme") or "courses",
                        "theme_manual": bool(data.get("theme_manual")),
                        "gender": data.get("gender"),
                        "birth_year": data.get("birth_year"),
                        "avatar_path": data.get("avatar_path"),
                    }
                )
                _rebuild_session_nav(preferred)
                if data.get("must_change_password"):
                    session["must_change_password"] = True
                    flash(
                        "Please set a new password before using the portal."
                        if preferred == "en" else "Bạn cần đặt mật khẩu mới trước khi dùng cổng thông tin."
                    )
                    resp_force = redirect(url_for("change_password"))
                    resp_force.set_cookie("smartuni_lang", preferred, max_age=86400 * 365)
                    return resp_force
                session.pop("must_change_password", None)
                _flash_t("login_ok")
                next_url = request.args.get("next") or url_for("ops_home")
                resp_redir = redirect(next_url)
                resp_redir.set_cookie("smartuni_lang", preferred, max_age=86400 * 365)
                return resp_redir
            _flash_t("login_bad") if not data.get("error") else flash(data.get("error"))
        except requests.RequestException:
            _flash_t("login_api_down")
        return render_template("login.html", email=email)
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Create a new user account (Name, Email, Password)."""
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        if not all([name, email, password]):
            flash("Name, email, and password are required.")
            return render_template("signup.html", name=name, email=email)

        try:
            resp = requests.post(
                USERS_URL,
                json={"name": name, "email": email, "password": password},
                timeout=5,
            )
            data = resp.json()
            if resp.status_code in (200, 201):
                flash("Account created successfully. Please log in.")
                return redirect(url_for("login"))
            flash(data.get("error", "Could not create account."))
        except requests.RequestException:
            flash("Could not reach the server. Please try again.")
        return render_template("signup.html", name=name, email=email)
    return render_template("signup.html")


@app.route("/logout")
def logout():
    """Logout and clear session."""
    lang = _ui_lang()
    session.pop("user", None)
    from i18n import t

    flash(t("logout_ok", lang))
    return redirect(url_for("login"))


@app.route("/account/language/<lang>", methods=["GET", "POST"])
def set_language(lang):
    """Switch UI language (en/vi); rebuild nav labels and persist preference."""
    from i18n import normalize_lang, t

    lang = normalize_lang(lang)
    session["ui_lang_pref"] = lang
    if session.get("user"):
        _rebuild_session_nav(lang)
    next_url = request.args.get("next") or request.referrer or url_for("ops_home")
    # Avoid open redirect off-site
    if not next_url.startswith("/") and not next_url.startswith(request.host_url):
        next_url = url_for("ops_home")
    resp = redirect(next_url)
    resp.set_cookie(
        "smartuni_lang",
        lang,
        max_age=60 * 60 * 24 * 365,
        samesite="Lax",
    )
    flash(t("lang_switched_en" if lang == "en" else "lang_switched_vi", lang))
    return resp


@app.route("/account/password", methods=["GET", "POST"])
def change_password():
    """Logged-in user changes their own password (confirm + save)."""
    user = session.get("user")
    if not user:
        return redirect(url_for("login", next=request.url))

    if request.method == "POST":
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not current_password or not new_password or not confirm_password:
            _flash_t("pwd_fill_all")
            return render_template("account/password.html")
        if new_password != confirm_password:
            _flash_t("pwd_mismatch")
            return render_template("account/password.html")
        if len(new_password) < 4:
            _flash_t("pwd_short")
            return render_template("account/password.html")
        if new_password == current_password:
            _flash_t("pwd_same")
            return render_template("account/password.html")

        try:
            resp = requests.post(
                f"{USERS_URL}/{user['id']}/password",
                json={
                    "current_password": current_password,
                    "new_password": new_password,
                },
                timeout=8,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code == 200:
                session.pop("must_change_password", None)
                _flash_t("pwd_ok")
                return redirect(url_for("ops_home"))
            err = data.get("error") or (
                "Could not change password." if _ui_lang() == "en" else "Không đổi được mật khẩu."
            )
            if resp.status_code == 401:
                err = (
                    "Current password is incorrect."
                    if _ui_lang() == "en"
                    else "Mật khẩu hiện tại không đúng."
                )
            flash(err)
        except requests.RequestException:
            _flash_t("login_api_down")
        return render_template("account/password.html")

    return render_template("account/password.html")


def _merge_session_profile(data: dict):
    """Refresh slim session fields after profile/avatar update."""
    u = dict(session.get("user") or {})
    for key in (
        "name",
        "theme",
        "theme_manual",
        "gender",
        "birth_year",
        "avatar_path",
    ):
        if key in data:
            u[key] = data.get(key)
    session["user"] = _slim_session_user(u)
    session.modified = True


@app.route("/account/profile", methods=["GET", "POST"])
def account_profile():
    """Self-service profile: gender, birth year, theme, avatar."""
    user = session.get("user")
    if not user:
        return redirect(url_for("login", next=request.url))

    profile = {
        "name": user.get("name") or "",
        "email": user.get("email") or "",
        "gender": user.get("gender") or "",
        "birth_year": user.get("birth_year") or "",
        "theme": user.get("theme") or "courses",
        "theme_manual": bool(user.get("theme_manual")),
        "avatar_path": user.get("avatar_path") or "",
    }

    # Refresh from API when possible
    try:
        resp = requests.get(f"{USERS_URL}/{user['id']}/profile", timeout=8)
        if resp.status_code == 200:
            data = resp.json() or {}
            profile.update(
                {
                    "name": data.get("name") or profile["name"],
                    "email": data.get("email") or profile["email"],
                    "gender": data.get("gender") or "",
                    "birth_year": data.get("birth_year") or "",
                    "theme": data.get("theme") or "courses",
                    "theme_manual": bool(data.get("theme_manual")),
                    "avatar_path": data.get("avatar_path") or "",
                }
            )
            _merge_session_profile(profile)
    except requests.RequestException:
        pass

    if request.method == "POST":
        action = (request.form.get("action") or "save").strip()
        if action == "remove_avatar":
            try:
                resp = requests.delete(f"{USERS_URL}/{user['id']}/avatar", timeout=15)
                data = resp.json() if resp.content else {}
                if resp.status_code == 200:
                    profile["avatar_path"] = ""
                    _merge_session_profile({"avatar_path": None})
                    _flash_t("profile_avatar_removed")
                    return redirect(url_for("account_profile"))
                flash(data.get("error") or "Không xóa được ảnh.")
            except requests.RequestException:
                _flash_t("login_api_down")
            return render_template("account/profile.html", profile=profile)

        name = (request.form.get("name") or "").strip()
        gender = (request.form.get("gender") or "").strip().upper()
        birth_year_raw = (request.form.get("birth_year") or "").strip()
        avatar_file = request.files.get("avatar")

        body = {
            "name": name or profile["name"],
            "gender": gender if gender in ("F", "M") else "",
            "birth_year": birth_year_raw if birth_year_raw else None,
            "theme": "courses",
        }

        try:
            resp = requests.patch(
                f"{USERS_URL}/{user['id']}/profile",
                json=body,
                timeout=8,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code != 200:
                flash(data.get("error") or "Không cập nhật được hồ sơ.")
                return render_template("account/profile.html", profile={**profile, **body})

            profile.update(
                {
                    "name": data.get("name") or body["name"],
                    "gender": data.get("gender") or "",
                    "birth_year": data.get("birth_year") or "",
                    "theme": data.get("theme") or "courses",
                    "theme_manual": bool(data.get("theme_manual")),
                    "avatar_path": data.get("avatar_path") or profile.get("avatar_path") or "",
                }
            )
            _merge_session_profile(profile)

            if avatar_file and avatar_file.filename:
                files = {
                    "avatar": (
                        avatar_file.filename,
                        avatar_file.stream,
                        avatar_file.mimetype or "application/octet-stream",
                    )
                }
                aresp = requests.post(
                    f"{USERS_URL}/{user['id']}/avatar",
                    files=files,
                    timeout=30,
                )
                adata = aresp.json() if aresp.content else {}
                if aresp.status_code == 200:
                    profile["avatar_path"] = adata.get("avatar_path") or ""
                    _merge_session_profile({"avatar_path": profile["avatar_path"]})
                else:
                    flash(adata.get("error") or "Đã lưu hồ sơ nhưng không tải được ảnh.")
                    return render_template("account/profile.html", profile=profile)

            _flash_t("profile_ok")
            return redirect(url_for("account_profile"))
        except requests.RequestException:
            _flash_t("login_api_down")
            return render_template("account/profile.html", profile=profile)

    return render_template("account/profile.html", profile=profile)


@app.route("/api/uploads/<path:relpath>", methods=["GET"])
def api_uploads(relpath):
    """Proxy uploaded files (avatars…) from backend."""
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    safe = Path(relpath).as_posix()
    if ".." in safe.split("/"):
        return jsonify({"error": "Invalid path"}), 400
    try:
        resp = requests.get(
            f"{API_BASE}/uploads/{safe}",
            timeout=30,
            stream=True,
        )
        if resp.status_code != 200:
            try:
                return jsonify(resp.json()), resp.status_code
            except Exception:
                return jsonify({"error": "Not found"}), resp.status_code
        excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        headers = {
            k: v
            for k, v in resp.headers.items()
            if k.lower() not in excluded
        }
        return Response(resp.iter_content(chunk_size=8192), status=resp.status_code, headers=headers)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/users-list")
def users_list():
    try:
        resp = requests.get(USERS_URL, timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Is the backend running?")
        return render_template("users/index.html", users=[])

    if resp.status_code != 200:
        flash(_api_error(resp))
        return render_template("users/index.html", users=[])

    return render_template("users/index.html", users=resp.json())


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        if not all([name, email, password]):
            flash("Name, email, and password are required.")
            return render_template("users/add.html", name=name, email=email)

        try:
            resp = requests.post(
                USERS_URL,
                json={"name": name, "email": email, "password": password},
                timeout=5,
            )
        except requests.RequestException:
            flash("Could not reach the API. Please try again.")
            return render_template("users/add.html", name=name, email=email)

        if resp.status_code in (200, 201):
            data = resp.json()
            flash(f"User {data.get('id', '')} added successfully.")
            return redirect("/")

        flash(_api_error(resp))
        return render_template("users/add.html", name=name, email=email)

    return render_template("users/add.html")


@app.route("/edit/<int:user_id>", methods=["GET", "POST"])
def edit(user_id):
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        if not all([name, email, password]):
            flash("Name, email, and password are required.")
            user = {"id": user_id, "name": name, "email": email, "password": password}
            return render_template("users/edit.html", user=user)

        try:
            resp = requests.put(
                f"{USERS_URL}/{user_id}",
                json={"name": name, "email": email, "password": password},
                timeout=5,
            )
        except requests.RequestException:
            flash("Could not reach the API. Please try again.")
            return render_template(
                "users/edit.html",
                user={"id": user_id, "name": name, "email": email, "password": password},
            )

        if resp.status_code == 200:
            flash(f"User {user_id} updated successfully.")
            return redirect("/")

        flash(_api_error(resp))
        user = {"id": user_id, "name": name, "email": email, "password": password}
        return render_template("users/edit.html", user=user)

    try:
        resp = requests.get(f"{USERS_URL}/{user_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Please try again.")
        return redirect("/")

    if resp.status_code != 200:
        flash(_api_error(resp, "User not found."))
        return redirect("/")

    return render_template("users/edit.html", user=resp.json())


@app.route("/delete/<int:user_id>", methods=["GET", "POST"])
def delete(user_id):
    if request.method == "POST":
        try:
            resp = requests.delete(f"{USERS_URL}/{user_id}", timeout=5)
        except requests.RequestException:
            flash("Could not reach the API. Please try again.")
            return redirect("/")

        if resp.status_code == 200:
            flash(f"User {user_id} deleted successfully.")
            return redirect("/")
        flash(_api_error(resp, "User not found."))
        return redirect("/")

    try:
        resp = requests.get(f"{USERS_URL}/{user_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Please try again.")
        return redirect("/")

    if resp.status_code != 200:
        flash(_api_error(resp, "User not found."))
        return redirect("/")

    return render_template("users/delete.html", user=resp.json())


# ---------------------------------------------------------------------------
# Storages routes
# ---------------------------------------------------------------------------
@app.route("/storages")
def storages_index():
    try:
        resp = requests.get(STORAGES_URL, timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Is the backend running?")
        return render_template("storages/index.html", storages=[])

    if resp.status_code != 200:
        flash(_api_error(resp))
        return render_template("storages/index.html", storages=[])

    data = resp.json()
    storages = _normalize_storages(data)
    return render_template("storages/index.html", storages=storages)


@app.route("/storages/<int:storage_id>")
def storages_detail(storage_id):
    try:
        resp = requests.get(f"{STORAGES_URL}/{storage_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Please try again.")
        return redirect("/storages")

    if resp.status_code != 200:
        flash(_api_error(resp, "Storage not found."))
        return redirect("/storages")

    return render_template("storages/detail.html", storage=resp.json())


@app.route("/storages/add", methods=["GET", "POST"])
def storages_add():
    if request.method == "POST":
        data = {
            "product": (request.form.get("product") or "").strip(),
            "brand": (request.form.get("brand") or "").strip(),
            "rating": request.form.get("rating") or "",
            "model": (request.form.get("model") or "").strip(),
            "picture": (request.form.get("picture") or "").strip(),
            "price": (request.form.get("price") or "").strip(),
            "RAM": (request.form.get("RAM") or "").strip(),
            "details": (request.form.get("details") or "").strip(),
        }
        if not data["product"]:
            flash("Product is required.")
            return render_template("storages/add.html", **data)

        try:
            resp = requests.post(STORAGES_URL, json=data, timeout=5)
        except requests.RequestException:
            flash("Could not reach the API. Please try again.")
            return render_template("storages/add.html", **data)

        if resp.status_code in (200, 201):
            flash(f"Storage added successfully.")
            return redirect("/storages")

        flash(_api_error(resp))
        return render_template("storages/add.html", **data)

    return render_template("storages/add.html")


@app.route("/storages/edit/<int:storage_id>", methods=["GET", "POST"])
def storages_edit(storage_id):
    if request.method == "POST":
        data = {
            "product": (request.form.get("product") or "").strip(),
            "brand": (request.form.get("brand") or "").strip(),
            "rating": request.form.get("rating") or "",
            "model": (request.form.get("model") or "").strip(),
            "picture": (request.form.get("picture") or "").strip(),
            "price": (request.form.get("price") or "").strip(),
            "RAM": (request.form.get("RAM") or "").strip(),
            "details": (request.form.get("details") or "").strip(),
        }
        if not data["product"]:
            flash("Product is required.")
            storage = {"id": storage_id, **data}
            return render_template("storages/edit.html", storage=storage)

        try:
            resp = requests.put(f"{STORAGES_URL}/{storage_id}", json=data, timeout=5)
        except requests.RequestException:
            flash("Could not reach the API. Please try again.")
            storage = {"id": storage_id, **data}
            return render_template("storages/edit.html", storage=storage)

        if resp.status_code == 200:
            flash("Storage updated successfully.")
            return redirect("/storages")

        flash(_api_error(resp))
        storage = {"id": storage_id, **data}
        return render_template("storages/edit.html", storage=storage)

    try:
        resp = requests.get(f"{STORAGES_URL}/{storage_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Please try again.")
        return redirect("/storages")

    if resp.status_code != 200:
        flash(_api_error(resp, "Storage not found."))
        return redirect("/storages")

    return render_template("storages/edit.html", storage=resp.json())


# ---------------------------------------------------------------------------
# Articles & Admin (PDF upload, RAG Q&A)
# ---------------------------------------------------------------------------
OPS_PER_PAGE_OPTIONS = (10, 20, 50, 100, 200)
DEFAULT_OPS_PER_PAGE = 20


def _paginate_list(items, *, default_per_page=DEFAULT_OPS_PER_PAGE, allowed=OPS_PER_PAGE_OPTIONS):
    """Slice a list by ?page=&per_page= query args. Returns (page_items, pagination_dict)."""
    if not isinstance(items, list):
        items = list(items or [])
    per_page = request.args.get("per_page", type=int) or default_per_page
    if per_page not in allowed:
        per_page = default_per_page
    page = request.args.get("page", type=int) or 1
    if page < 1:
        page = 1
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page) if per_page else 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    page_items = items[start : start + per_page]
    return page_items, {"total": total, "page": page, "per_page": per_page}


def _parse_list_response(data, items_key="items"):
    """Parse paginated API response. Handles both {items,total,page,per_page} and legacy array."""
    if isinstance(data, list):
        return data, len(data), 1, len(data) if data else 10
    items = data.get(items_key) or []
    return items, data.get("total", len(items)), data.get("page", 1), data.get("per_page", 20)


@app.route("/articles")
def articles_index():
    """List articles for users to browse and chat with."""
    q = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or 12
    if per_page not in (12, 14, 48, 100):
        per_page = 12
    params = {"page": page, "per_page": per_page}
    if q:
        params["q"] = q
    try:
        resp = requests.get(ARTICLES_URL, timeout=5, params=params)
    except requests.RequestException:
        flash("Could not reach the API. Is the backend running?")
        return render_template("articles/index.html", articles=[], pagination=None, search_q=q)

    if resp.status_code != 200:
        flash(_api_error(resp))
        return render_template("articles/index.html", articles=[], pagination=None, search_q=q)

    try:
        data = resp.json()
        articles, total, page, per_page = _parse_list_response(data)
        pagination = {"total": total, "page": page, "per_page": per_page}
    except Exception:
        articles, pagination = [], None
    pagination_params = {"q": q} if q else {}
    return render_template(
        "articles/index.html",
        articles=articles,
        pagination=pagination,
        pagination_url="articles_index",
        pagination_params=pagination_params,
        search_q=q,
    )


@app.route("/articles/<int:article_id>")
def article_detail(article_id):
    """Article detail with summary and chat."""
    try:
        resp = requests.get(f"{ARTICLES_URL}/{article_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Please try again.")
        return redirect(url_for("articles_index"))

    if resp.status_code != 200:
        flash(_api_error(resp, "Article not found."))
        return redirect(url_for("articles_index"))

    chats = []
    try:
        chat_resp = requests.get(f"{ARTICLES_URL}/{article_id}/chats", timeout=5)
        if chat_resp.status_code == 200:
            chats = chat_resp.json()
    except Exception:
        pass

    models = []
    try:
        model_resp = requests.get(f"{API_BASE}/models", timeout=5)
        if model_resp.status_code == 200 and model_resp.text:
            data = model_resp.json()
            if isinstance(data, list):
                models = [m if isinstance(m, str) else str(m) for m in data if m]
    except Exception:
        pass
    if not models:
        models = [os.environ.get("CHAT_MODEL", "qwen3:8b")]

    return render_template(
        "articles/detail.html",
        article=resp.json(),
        chats=chats,
        user_id=_current_user_id(),
        chat_models=models,
    )


@app.route("/api/admin/bulk-import/scan", methods=["GET"])
def api_admin_bulk_import_scan():
    """Proxy: scan folder for PDFs."""
    try:
        resp = requests.get(
            f"{API_BASE}/admin/bulk-import/scan",
            params={"folder": request.args.get("folder", "").strip()},
            timeout=10,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/bulk-import/process", methods=["POST"])
def api_admin_bulk_import_process():
    """Proxy: process PDFs from folder. Body: {folder, filenames?, retry_errors?}."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(
            f"{API_BASE}/admin/bulk-import/process",
            json=data,
            timeout=600,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/search", methods=["GET"])
def api_admin_search():
    """Proxy: RAG search across all articles. Passes page, per_page."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": [], "items": [], "total": 0, "page": 1, "per_page": 12, "query": ""})
    try:
        params = {"q": q}
        if request.args.get("page"):
            params["page"] = request.args.get("page")
        if request.args.get("per_page"):
            params["per_page"] = request.args.get("per_page")
        resp = requests.get(
            f"{API_BASE}/admin/search",
            params=params,
            timeout=30,
        )
        data = resp.json() if resp.text else {}
        if resp.status_code != 200:
            return jsonify({"error": data.get("error", "Search failed")}), resp.status_code
        return jsonify(data)
    except requests.RequestException as e:
        return jsonify({"error": str(e), "results": []}), 503


@app.route("/search")
def search_index():
    """Search page: semantic RAG search across all articles."""
    q = request.args.get("q", "").strip()
    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or 10
    if per_page not in (10, 25, 50):
        per_page = 10
    return render_template(
        "search/index.html",
        initial_query=q,
        initial_page=page,
        initial_per_page=per_page,
    )


@app.route("/admin")
def admin_index():
    """Admin: dashboard and manage articles."""
    stats = {
        "articles_count": 0,
        "projects_count": 0,
        "theses_count": 0,
        "books_count": 0,
        "article_chats_count": 0,
        "thesis_chats_count": 0,
        "project_chats_count": 0,
        "book_chats_count": 0,
        "article_likes": 0,
        "article_dislikes": 0,
        "thesis_likes": 0,
        "thesis_dislikes": 0,
        "project_likes": 0,
        "project_dislikes": 0,
        "book_likes": 0,
        "book_dislikes": 0,
        "likes_total": 0,
        "dislikes_total": 0,
    }
    try:
        stats_resp = requests.get(f"{API_BASE}/admin/stats", timeout=5)
        if stats_resp.status_code == 200:
            stats = stats_resp.json()
    except Exception:
        pass

    try:
        resp = requests.get(ARTICLES_URL, timeout=5, params={"page": 1, "per_page": 100})
    except requests.RequestException:
        flash("Could not reach the API. Is the backend running?")
        return render_template("admin/index.html", articles=[], books=[], llm_ok=False, stats=stats)

    if resp.status_code != 200:
        flash(_api_error(resp))
        return render_template("admin/index.html", articles=[], books=[], llm_ok=False, stats=stats)

    try:
        articles, _, _, _ = _parse_list_response(resp.json())
    except Exception:
        articles = []

    books = []
    try:
        books_resp = requests.get(BOOKS_URL, timeout=5, params={"page": 1, "per_page": 100})
        if books_resp.status_code == 200:
            books, _, _, _ = _parse_list_response(books_resp.json())
    except Exception:
        pass

    llm_ok = False
    try:
        health = requests.get(f"{API_BASE}/articles/health", timeout=3)
        if health.status_code == 200:
            llm_ok = health.json().get("llm_configured", False)
    except Exception:
        pass

    return render_template("admin/index.html", articles=articles, books=books, llm_ok=llm_ok, stats=stats)


@app.route("/admin/system")
def admin_system_hub():
    """Admin hub: 4 function groups + quick stats."""
    user = session.get("user") or {}
    if not user.get("is_admin") and not (
        _user_has_perm("admin.reports")
        or _user_has_perm("admin.users")
        or _user_has_perm("admin.permissions")
        or _user_has_perm("admin.status_catalog")
        or _user_has_perm("admin.suggestions")
    ):
        flash("Cần quyền quản trị hệ thống.")
        return redirect(url_for("ops_home"))
    from flask import g

    g.feature_code = "admin.reports"
    stats = {"users": 0, "departments": 0, "suggestions_open": 0, "status_items": 0}
    try:
        users = requests.get(USERS_URL, timeout=5)
        if users.status_code == 200:
            stats["users"] = len(users.json() or [])
        depts = requests.get(f"{API_BASE}/departments", timeout=5)
        if depts.status_code == 200:
            stats["departments"] = len(depts.json() or [])
        sug = requests.get(
            f"{API_BASE}/ops/suggestions",
            params={"status": "open", "page": 1, "per_page": 1},
            headers=_user_scopes_header(),
            timeout=8,
        )
        if sug.status_code == 200:
            data = sug.json() or {}
            stats["suggestions_open"] = int(
                (data.get("stats") or {}).get("open") or data.get("total") or 0
            )
        st = requests.get(f"{API_BASE}/admin/status-catalog", timeout=5)
        if st.status_code == 200:
            payload = st.json() or {}
            items = payload.get("items") if isinstance(payload, dict) else payload
            stats["status_items"] = len(items or [])
    except requests.RequestException:
        pass
    return render_template("admin/system_hub.html", stats=stats)


@app.route("/admin/settings", methods=["GET"])
def admin_settings():
    """Admin: deployment mode (Development / Production)."""
    user = session.get("user") or {}
    if not user.get("is_admin") and not _user_has_perm("admin.reports"):
        flash("Cần quyền quản trị hệ thống." if _ui_lang() != "en" else "System admin permission required.")
        return redirect(url_for("ops_home"))
    from flask import g

    g.feature_code = "admin.reports"
    mode = "development"
    updated_at = ""
    try:
        resp = requests.get(f"{API_BASE}/admin/settings", timeout=5)
        if resp.status_code == 200:
            data = resp.json() or {}
            mode = (data.get("deployment_mode") or "development").strip().lower()
            meta = (data.get("settings") or {}).get("deployment_mode") or {}
            updated_at = meta.get("updated_at") or ""
    except requests.RequestException:
        flash("Không tải được cấu hình." if _ui_lang() != "en" else "Could not load settings.")
    if mode not in ("development", "production"):
        mode = "development"
    return render_template(
        "admin/settings.html",
        deployment_mode=mode,
        updated_at=updated_at,
    )


@app.route("/api/admin/settings", methods=["GET", "PUT"])
def api_admin_settings():
    """Proxy Admin system settings."""
    user = session.get("user") or {}
    if not user.get("is_admin") and not _user_has_perm("admin.reports"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        if request.method == "GET":
            resp = requests.get(f"{API_BASE}/admin/settings", timeout=5)
        else:
            resp = requests.put(
                f"{API_BASE}/admin/settings",
                json=request.get_json(silent=True) or {},
                timeout=5,
            )
        return (resp.content, resp.status_code, {"Content-Type": "application/json"})
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 502


@app.route("/admin/bulk-import")
def admin_bulk_import():
    """Admin: Add Multiple Articles from Data Folder."""
    return render_template("admin/bulk_import.html")


@app.route("/admin/users")
def admin_users():
    """Admin: manage users, departments, permissions, reset password."""
    user = session.get("user") or {}
    if not user.get("is_admin") and not _user_has_perm("admin.users"):
        flash("Cần quyền quản trị người dùng.")
        return redirect(url_for("ops_home"))
    users = []
    departments = []
    try:
        resp = requests.get(USERS_URL, timeout=5)
        if resp.status_code == 200:
            users = resp.json()
        dresp = requests.get(f"{API_BASE}/departments", timeout=5)
        if dresp.status_code == 200:
            departments = dresp.json()
    except requests.RequestException:
        flash("Could not reach the API.")
    return render_template("admin/users.html", users=users, departments=departments)


@app.route("/admin/departments")
def admin_departments():
    if not _user_has_perm("admin.departments") and not (session.get("user") or {}).get("is_admin"):
        flash("Cần quyền quản lý bộ phận.")
        return redirect(url_for("ops_home"))
    departments = []
    try:
        resp = requests.get(f"{API_BASE}/departments", timeout=5)
        if resp.status_code == 200:
            departments = resp.json()
    except requests.RequestException:
        flash("Không lấy được danh sách bộ phận.")
    return render_template("admin/departments.html", departments=departments)


@app.route("/api/departments", methods=["POST"])
def api_departments_create():
    user = session.get("user") or {}
    if not user.get("is_admin") and not _user_has_perm("admin.departments"):
        return jsonify({"error": "Admin access required"}), 403
    return _api_proxy("post", "/departments", request.get_json(silent=True) or {})


@app.route("/admin/permissions")
def admin_permissions():
    if not _user_has_perm("admin.permissions") and not (session.get("user") or {}).get("is_admin"):
        flash("Cần quyền phân quyền.")
        return redirect(url_for("ops_home"))
    from flask import g

    g.feature_code = "admin.permissions"
    departments = []
    programs = []
    users = []
    try:
        departments = requests.get(f"{API_BASE}/departments", timeout=5).json()
        programs = requests.get(f"{API_BASE}/programs", timeout=5).json()
        users = requests.get(USERS_URL, timeout=5).json()
    except Exception:
        flash("Không tải được dữ liệu phân quyền.")
    dept_id = request.args.get("dept_id", type=int)
    catalog = []
    selected_dept = None
    if dept_id:
        try:
            detail = requests.get(f"{API_BASE}/departments/{dept_id}/permissions", timeout=5).json()
            catalog = detail.get("catalog") or []
            selected_dept = detail.get("department")
        except Exception:
            pass
    return render_template(
        "admin/permissions.html",
        departments=departments,
        programs=programs,
        users=users,
        catalog=catalog,
        selected_dept=selected_dept,
        dept_id=dept_id,
    )


@app.route("/admin/suggestions")
def admin_suggestions():
    """Admin: thống kê / lọc / đánh dấu / xuất đề xuất góp ý."""
    user = session.get("user") or {}
    if not user.get("is_admin") and not _user_has_perm("admin.suggestions"):
        flash("Cần quyền thống kê đề xuất.")
        return redirect(url_for("ops_home"))
    from flask import g

    g.feature_code = "admin.suggestions"
    params = {
        "function_code": (request.args.get("function_code") or "").strip() or None,
        "status": (request.args.get("status") or "").strip() or None,
        "from": (request.args.get("from") or "").strip() or None,
        "to": (request.args.get("to") or "").strip() or None,
        "q": (request.args.get("q") or "").strip() or None,
    }
    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or DEFAULT_OPS_PER_PAGE
    if per_page not in OPS_PER_PAGE_OPTIONS:
        per_page = DEFAULT_OPS_PER_PAGE
    items, stats = [], {"total": 0, "open": 0, "done": 0, "by_function": []}
    total = 0
    try:
        qs = {k: v for k, v in params.items() if v}
        qs["page"] = page
        qs["per_page"] = per_page
        resp = requests.get(
            f"{API_BASE}/ops/suggestions",
            params=qs,
            headers=_user_scopes_header(),
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items") or []
            stats = data.get("stats") or stats
            total = int(data.get("total") or len(items))
            page = int(data.get("page") or page)
            per_page = int(data.get("per_page") or per_page)
    except requests.RequestException:
        flash("Không tải được danh sách đề xuất.")
    pag_params = {k: v for k, v in params.items() if v}
    return render_template(
        "admin/suggestions.html",
        items=items,
        stats=stats,
        filters=params,
        pagination={"total": total, "page": page, "per_page": per_page},
        pagination_url="admin_suggestions",
        pagination_params=pag_params,
        pagination_sizes=list(OPS_PER_PAGE_OPTIONS),
    )


def _admin_gate_users_or_perms():
    u = session.get("user") or {}
    if u.get("is_admin"):
        return None
    if _user_has_perm("admin.users") or _user_has_perm("admin.permissions"):
        return None
    return jsonify({"error": "Forbidden"}), 403


@app.route("/api/admin/departments/<int:dept_id>/permissions", methods=["PUT"])
def api_admin_dept_permissions(dept_id):
    if not _user_has_perm("admin.permissions") and not (session.get("user") or {}).get("is_admin"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.put(
            f"{API_BASE}/departments/{dept_id}/permissions",
            json=request.get_json(silent=True) or {},
            timeout=8,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/users/<int:user_id>/scopes", methods=["PUT"])
def api_admin_user_scopes(user_id):
    if not _user_has_perm("admin.permissions") and not (session.get("user") or {}).get("is_admin"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.put(
            f"{API_BASE}/users/{user_id}/scopes",
            json=request.get_json(silent=True) or {},
            timeout=8,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/users/<int:user_id>/reset-password", methods=["POST"])
def api_admin_reset_password(user_id):
    denied = _admin_gate_users_or_perms()
    if denied:
        return denied
    u = session.get("user") or {}
    if not u.get("is_admin") and not _user_has_perm("admin.users"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{USERS_URL}/{user_id}/admin-reset-password",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=8,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/users/<int:user_id>/departments", methods=["PUT"])
def api_admin_user_departments(user_id):
    if not (session.get("user") or {}).get("is_admin") and not _user_has_perm("admin.users"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.put(
            f"{USERS_URL}/{user_id}/departments",
            json=request.get_json(silent=True) or {},
            timeout=8,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/users/<int:user_id>/permissions", methods=["GET", "PUT"])
def api_admin_user_permissions(user_id):
    if not (session.get("user") or {}).get("is_admin") and not (
        _user_has_perm("admin.users") or _user_has_perm("admin.permissions")
    ):
        return jsonify({"error": "Forbidden"}), 403
    try:
        if request.method == "GET":
            resp = requests.get(f"{USERS_URL}/{user_id}/permissions", timeout=8)
        else:
            resp = requests.put(
                f"{USERS_URL}/{user_id}/permissions",
                json=request.get_json(silent=True) or {},
                timeout=8,
            )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503

# ---------------------------------------------------------------------------
# Operational modules (nghiepvu)
# ---------------------------------------------------------------------------
@app.route("/huong-dan")
def ops_guide():
    """Slide guide for every signed-in audience. Opens on the user's department."""
    from guide_content import audience_ids_for_user, build_guide

    user = session.get("user") or {}
    mine = audience_ids_for_user(user)
    lang = _ui_lang()

    def link_for(endpoint):
        return url_for(endpoint)

    # Luôn mở từ đầu trình tự (cấu hình → nhập học). «Của bạn» đánh dấu bước của tài khoản.
    deck = build_guide(lang, mine, "mo-dau", link_for)
    return render_template("ops/guide.html", deck=deck)


@app.route("/ops")
def ops_home():
    """Home after login: modules available to current user."""
    from ops_modules import OPS_MODULES

    u = session.get("user") or {}
    perms = set(_session_permission_codes(u))
    # Enrich with workflow metadata from backend rbac catalog if available
    catalog = {}
    try:
        r = requests.get(f"{API_BASE}/permissions", timeout=5)
        if r.status_code == 200:
            for p in r.json():
                catalog[p["code"]] = p
    except Exception:
        pass

    from i18n import flow_group_label, localize_module, localize_pipeline, workflow_blurb

    lang = _ui_lang()
    flow_map = {
        "asst": flow_group_label("asst", lang),
        "admissions": flow_group_label("admissions", lang),
        "accounting": flow_group_label("accounting", lang),
        "programs": flow_group_label("programs", lang),
        "classes": flow_group_label("classes", lang),
        "teaching": flow_group_label("teaching", lang),
        "alumni": flow_group_label("alumni", lang),
        "canvas": flow_group_label("canvas", lang),
        "student": flow_group_label("student", lang),
        "reports": flow_group_label("reports", lang),
        "admin": flow_group_label("admin", lang),
        "marcom": flow_group_label("marcom", lang),
    }

    items = []
    # ThaoP (is_admin): mọi module; Giám đốc/Trợ lý: mọi module nghiệp vụ (xem)
    # Admin / NghiND: chỉ module trong danh sách quyền tường minh
    if u.get("is_admin") or _is_exec_viewer():
        source = OPS_MODULES.items()
    else:
        source = ((k, v) for k, v in OPS_MODULES.items() if k in perms)

    for code, m in source:
        if code == "reports.dashboard":
            continue  # Dashboard stats already on this page
        # Exec không hiện module cấu hình Admin
        if _is_exec_viewer() and code.startswith("admin."):
            continue
        prefix = code.split(".")[0]
        enriched = localize_module(dict(m), code, lang)
        if _is_exec_viewer():
            enriched = _apply_exec_view_only(enriched)
        enriched["flow_group"] = flow_map.get(prefix, "")
        if code in catalog and lang != "en":
            enriched.setdefault("title", catalog[code].get("label") or m["title"])
        items.append((code, enriched))

    # Sort by OPS_MODULES insertion / known sort via permission catalog
    sort_keys = {p["code"]: p.get("sort", 999) for p in catalog.values()} if catalog else {}
    items.sort(key=lambda kv: sort_keys.get(kv[0], OPS_MODULES[kv[0]].get("sort", 999) if False else 100))

    # Stable order from ops_modules dict order
    order = list(OPS_MODULES.keys())
    items.sort(key=lambda kv: order.index(kv[0]) if kv[0] in order else 999)

    summary = {}
    try:
        r = _ops_get("/ops/summary")
        if r.status_code == 200:
            summary = r.json()
            if isinstance(summary, dict) and summary.get("pipeline"):
                summary["pipeline"] = localize_pipeline(summary.get("pipeline"), lang)
    except Exception:
        pass
    return render_template(
        "ops/home.html",
        modules=items,
        summary=summary,
        summary_links=_summary_deep_links(),
    )


def _ensure_import_bulk_ui(cfg: dict, lang: str) -> dict:
    """Inject Tải mẫu / Import Excel actions for data-management lists."""
    if not cfg.get("import_bulk") or not cfg.get("import_entity"):
        return cfg
    cfg = dict(cfg)
    cfg["bulk_select"] = True
    if lang == "en":
        need = [
            {"id": "import_template", "label": "Download template"},
            {"id": "import_excel", "label": "Import Excel"},
        ]
    else:
        need = [
            {"id": "import_template", "label": "Tải mẫu Excel"},
            {"id": "import_excel", "label": "Import Excel"},
        ]
    actions = list(cfg.get("actions") or [])
    seen = set()
    for a in actions:
        if isinstance(a, dict):
            seen.add(str(a.get("id") or ""))
            seen.add(str(a.get("label") or ""))
        else:
            seen.add(str(a))
    for a in need:
        if a["id"] not in seen and a["label"] not in seen:
            actions.append(a)
            seen.add(a["id"])
    # Drop legacy applications-only duplicate string labels if dict form already present
    cfg["actions"] = actions
    return cfg


def _render_ops_module(perm_code: str):
    from flask import g
    from ops_modules import OPS_MODULES, group_toolbar_actions

    g.feature_code = perm_code
    if not _user_has_perm(perm_code):
        aliases = {
            "admissions.round_docs": (
                "admissions.round_docs.view",
                "admissions.round_docs.download",
            ),
        }
        extra = aliases.get(perm_code) or ()
        if not any(_user_has_perm(c) for c in extra):
            _flash_t("no_permission")
            return redirect(url_for("ops_home"))
    from i18n import localize_module

    lang = _ui_lang()
    cfg = localize_module(dict(OPS_MODULES[perm_code]), perm_code, lang)
    cfg = _ensure_import_bulk_ui(cfg, lang)
    cfg = _apply_admissions_ops_role(cfg, perm_code)
    if _is_exec_viewer() or _perm_is_view_only(perm_code):
        cfg = _apply_exec_view_only(cfg)
    if perm_code in ("marcom.campaigns", "marcom.events", "marcom.assets"):
        depts = set(_dept_codes())
        buttons = list(cfg.get("row_buttons") or [])
        if "marcom" in depts and not _is_exec_viewer():
            buttons.append({"id": "submit_marcom_budget", "label": "Trình duyệt ngân sách"})
            buttons.append({"id": "propose_marcom_cost", "label": "Đề xuất đối soát"})
        if "ke_toan" in depts:
            buttons.append({"id": "approve_marcom_budget", "label": "Kế toán duyệt ngân sách"})
            buttons.append({"id": "confirm_marcom_cost", "label": "Xác nhận chi phí"})
        if "ban_giam_doc" in depts or (session.get("user") or {}).get("is_admin"):
            buttons.append({"id": "approve_marcom_budget", "label": "BGD duyệt ngân sách"})
        if perm_code == "marcom.campaigns" and "marcom" in depts:
            buttons.append({"id": "add_campaign_activity", "label": "Thêm hoạt động"})
        if perm_code == "marcom.assets" and "marcom" in depts:
            buttons.append({"id": "add_content_publication", "label": "Lịch phát hành"})
        seen = set()
        unique = []
        for b in buttons:
            key = b.get("id")
            if key in seen and key == "approve_marcom_budget" and "ban_giam_doc" not in depts:
                continue
            if key == "approve_marcom_budget" and key in seen:
                continue
            seen.add(key)
            unique.append(b)
        cfg["row_buttons"] = unique
    # Jinja tojson requires concrete bools (Undefined breaks |tojson)
    cfg.setdefault("bulk_select", False)
    cfg.setdefault("allow_delete", False)
    cfg.setdefault("exec_view_only", False)
    cfg.setdefault("import_bulk", False)
    cfg.setdefault("fee_actions", False)
    cfg.setdefault("charge_actions", False)
    cfg.setdefault("leave_actions", False)
    cfg.setdefault("canvas_export_roster", False)
    cfg.setdefault("round_filter", False)
    cfg.setdefault("select_interview", False)
    cfg.setdefault("treasury_kpis", False)
    cfg.setdefault("is_fee_alerts", False)
    cfg.setdefault("is_crm_report", False)
    cfg.setdefault("is_collection_report", False)
    cfg.setdefault("crm_bulk_convert", False)
    cfg.setdefault("round_docs_manage", False)
    cfg.setdefault("round_docs_download", False)
    cfg.setdefault("import_entity", "")
    if perm_code == "admissions.rounds":
        cfg["program_filter"] = True
        cfg["status_filter"] = True
        cfg["year_filter"] = True
        cfg["intake_filter"] = True
    if perm_code == "admissions.round_docs":
        cfg["round_docs_manage"] = _user_has_perm("admissions.round_docs") or bool(
            (session.get("user") or {}).get("is_admin")
        )
        cfg["round_docs_download"] = cfg["round_docs_manage"] or _user_has_perm(
            "admissions.round_docs.download"
        )
        if not cfg["round_docs_manage"]:
            cfg["primary_action"] = None
            cfg["row_buttons"] = [
                b for b in (cfg.get("row_buttons") or [])
                if (b.get("id") or "") not in ("upload_round_doc", "delete_round_doc")
            ]
        if not cfg["round_docs_download"]:
            cfg["row_buttons"] = [
                b for b in (cfg.get("row_buttons") or [])
                if (b.get("id") or "") != "download_round_doc"
            ]
    primary = cfg.get("primary_action")
    primary_id = primary.get("id") if isinstance(primary, dict) else None
    if primary_id == "create_receipt":
        if "ke_toan" not in set(_dept_codes()) and not (session.get("user") or {}).get("is_admin"):
            cfg["primary_action"] = None
    cfg["action_menus"] = group_toolbar_actions(cfg.get("actions") or [], lang)
    workflows = {
        "asst.exec_tasks": "Họp BGD → biên bản → nhiệm vụ → deadline → tiến độ",
        "asst.calendar": "Lịch BGD / họp / sự kiện / giảng dạy / nghỉ phép",
        "asst.intl_faculty": "Hộ chiếu → visa → vé → KS → đón tiễn → lịch giảng",
        "asst.intl_students": "HV trao đổi → visa → chuyến bay → onboarding",
        "asst.director_fr": "Visa / work permit / cư trú GĐ Pháp & gia đình",
        "asst.documents": "CV đến/đi → cấp số → đóng dấu → phát hành",
        "asst.procurement": "Đề xuất → mua → hóa đơn → thanh toán",
        "asst.payments": "Theo dõi HĐ & thanh toán hàng tháng",
        "asst.weekly_report": "Tổng hợp bộ phận → BGD duyệt → gửi NEU",
        "asst.leave": "Đăng ký nghỉ → phê duyệt → đồng bộ lịch",
        "admissions.rounds": "TS tạo đợt → thí sinh nộp hồ sơ",
        "admissions.round_docs": "Tìm theo đợt · tải lên · xem trước · tải xuống",
        "admissions.doc_types": "Khai báo phân loại tài liệu dùng cho đợt tuyển sinh",
        "admissions.applications": "Checklist → phê duyệt TS → xác nhận dự thi (ghi căn cứ) trên cùng hồ sơ → bàn giao Điều phối",
        "admissions.written_exams": "Đã xác nhận dự thi và, nếu đợt yêu cầu, đã thu lệ phí thi → SBD → điểm viết → hội đồng",
        "admissions.interviews": "Boards ~10 TS · email xác nhận · CFVG/IAE/Alumni",
        "admissions.results": "Điểm viết / phỏng vấn · Điều phối chốt Đỗ hoặc Trượt · Tuyển sinh gửi cả thư đỗ và thư trượt",
        "admissions.pre_enroll": "Cùng một người, chưa thành học viên · xác nhận người dự thi chính thức",
        "admissions.enrolled_files": "Hồ sơ theo học: mã học viên theo chương trình, cùng mã ứng viên, có thể chờ xếp lớp",
        "admissions.crm_source": "Ngày tiếp nhận · chuyên viên · mức độ quan tâm · kênh · nhắc lịch · chi tiết",
        "admissions.crm_activities": "Chọn loại hoạt động → tạo đợt → chọn hồ sơ nguồn → ghi chú",
        "admissions.crm_reminders": "Nhắc trước đợt → in / email / gọi",
        "admissions.crm_reports": "Theo mức độ quan tâm và theo chương trình",
        "accounting.fees": "Hồ sơ Đỗ → phí ghi danh chờ thu → Kế toán xác nhận đã thu · Tuyển sinh chỉ xem",
        "accounting.official_list": "Đã thu → chốt chính thức → hồ sơ theo học (Chờ xếp lớp) → cấp mã và xếp lớp",
        "accounting.charges": "Sổ công nợ: ghi nhận thanh toán / điều chỉnh HB",
        "accounting.tuition_tracker": "Theo dõi nộp học phí từng HV — sắp hạn / quá hạn",
        "accounting.fee_alerts": "Cảnh báo hạn nộp & số khoản trễ — chỉnh ngưỡng",
        "accounting.candidate_files": "Nghĩa vụ lệ phí thi · miễn · phiếu thu · chỉ Kế toán xác nhận đã thu",
        "accounting.collection_report": "Tổng đã thu (kể cả miễn) · còn nợ · theo loại phí",
        "programs.structure": "Copy phiên bản (MBA_K34→K35 / MSCM_2026)",
        "programs.courses": "Môn theo HK; 7+2 (MSCM) / 8 buổi (MBA)",
        "classes.manage": "Cohort + version + welcome email + Canvas sync",
        "students.manage": "Financial + Academic · học bổng / bảo lưu / IAE",
        "teaching.faculty": "HĐ/trả điểm/CFVG · vé/KS → Quốc tế / Trợ lý",
        "teaching.assign": "Proposed → Confirmed → In Teaching",
        "teaching.schedule": "Semester schedule → Logistics / GV QT",
        "teaching.materials": "Upload/gửi tài liệu theo buổi",
        "teaching.groups": "Nhóm học tập; SV thấy nhóm của mình",
        "teaching.attendance": "2 lần/buổi · vắng >30% → email + không ĐK thi",
        "teaching.assignments": "Giao BT thực hành / trắc nghiệm theo lớp–môn; import mẫu; HV làm online",
        "student.practice": "Làm bài thực hành / trắc nghiệm online theo bài đã mở",
        "teaching.grades": "Draft → Approved → Locked",
        "teaching.exams": "Đề thi / thi lại / khiếu nại điểm",
        "teaching.evaluation": "≥60% gửi QL · ≥80% gửi GV (24h)",
        "teaching.thesis": "Topic → supervisor → defense",
        "asst.intl_students": "Exchange In/Out · Visa→Trợ lý · IAE→KT · môn→ĐP",
        "asst.intl_faculty": "Passport → visa → vé → KS → BH",
        "alumni.members": "Alumni sau graduation",
        "alumni.events": "Tạo sự kiện → lọc đối tượng → gửi lời mời",
        "reports.dashboard": "Analytics theo scope chương trình",
    }
    if lang == "en":
        from i18n import workflow_blurb as _wf_en

        cfg["workflow"] = _wf_en(perm_code, "en") or cfg.get("workflow") or workflows.get(perm_code, "")
    else:
        cfg["workflow"] = workflows.get(perm_code, "") or cfg.get("workflow") or ""
    if lang == "en" and cfg.get("row_buttons"):
        btn_en = {
            "view_application": "View",
            "edit_application": "Edit",
            "update_application": "Update",
            "manage_app_docs": "Documents",
            "view_round": "View",
            "view_students": "Students",
            "email_class": "Email class",
            "view_courses": "Courses",
            "view_program": "View version",
            "copy_version": "Copy / transfer",
            "edit_faculty": "Edit",
            "view_director_fr": "View",
            "open_eval": "Open form",
            "view_evals": "Results",
            "send_eval_mgmt": "Send to Mgmt",
            "send_eval_faculty": "Send to Faculty",
            "close_eval": "Close form",
            "convert_to_applicant": "Convert to applicant",
            "crm_daily_update": "Daily update",
            "crm_private_consult": "Private consult",
            "crm_change_status": "Change status",
            "crm_view_reminders": "Reminders",
            "crm_pick_profiles": "Select profiles",
            "crm_view_participants": "Care notes",
            "crm_dispatch_email": "Email",
            "crm_dispatch_phone": "Call",
            "update_student_profile": "Update profile",
            "send_fee_proof": "Submit proof",
        }
        cfg["row_buttons"] = [
            {**b, "label": btn_en.get(b.get("id"), b.get("label"))}
            for b in cfg["row_buttons"]
        ]
    if perm_code == "admissions.applications":
        cfg["row_actions"] = _application_row_actions()
        # dual-role HanhNT (ke_toan+mba): show coordinator actions too
        if not cfg["row_actions"] and (session.get("user") or {}).get("is_admin"):
            cfg["row_actions"] = [
                {"label": "Phê duyệt TS", "status": "approved_ts"},
                {"label": "Chuyển PV", "status": "interview"},
                {"label": "Đỗ", "status": "passed"},
                {"label": "Trượt", "status": "failed"},
            ]
    rows = []
    summary = None
    hub = None
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    version_id = request.args.get("version_id", type=int)
    program_code = (request.args.get("program_code") or "").strip()
    version_code = (request.args.get("version_code") or "").strip()
    round_id = request.args.get("round_id", type=int)
    intake_session = (request.args.get("intake_session") or "").strip()
    event_type = (request.args.get("event_type") or "").strip()
    converted = (request.args.get("converted") or "").strip()
    pic = (request.args.get("pic") or "").strip()
    intake = (request.args.get("intake") or "").strip()
    prospect_level = (request.args.get("prospect_level") or "").strip()
    expiry = (request.args.get("expiry") or "").strip()
    year = (request.args.get("year") or "").strip()
    params = dict(cfg.get("api_params") or {})
    if q:
        params["q"] = q
    from ops_modules import allowed_status_filter_codes, build_status_filter_options

    status_filter_options = []
    allowed_st = None
    if cfg.get("status_filter"):
        status_filter_options = build_status_filter_options(
            perm_code,
            status_options=_status_options_map(),
            status_labels=_localized_status_labels(),
        )
        allowed_st = frozenset(o["v"] for o in status_filter_options) if status_filter_options else (
            allowed_status_filter_codes(perm_code) or frozenset()
        )
    else:
        status = ""
    # Explicit status in query (including empty = all) overrides api_params default —
    # but only codes that belong to this module (never leak overdue onto applications/CRM).
    if cfg.get("status_filter") and "status" in request.args:
        if status and allowed_st and status in allowed_st:
            params["status"] = status
        elif not status:
            params.pop("status", None)
        else:
            status = ""
    elif cfg.get("status_filter") and status and allowed_st and status in allowed_st:
        params["status"] = status
    elif not cfg.get("status_filter"):
        params.pop("status", None)
    if version_id:
        params["version_id"] = version_id
    if program_code:
        params["program_code"] = program_code
    if version_code:
        params["version_code"] = version_code
    if round_id:
        params["round_id"] = round_id
    if intake_session:
        params["intake_session"] = intake_session
    if event_type:
        params["event_type"] = event_type
    if converted:
        params["converted"] = converted
    if pic:
        params["pic"] = pic
    if intake:
        params["intake"] = intake
    if year:
        params["year"] = year
    if prospect_level:
        params["prospect_level"] = prospect_level
    if expiry:
        params["expiry"] = expiry
    doc_scope = (request.args.get("doc_scope") or "").strip()
    cohort = (request.args.get("cohort") or "").strip()
    study_year = (request.args.get("study_year") or "").strip()
    mobility = (request.args.get("mobility") or "").strip()
    session_date = (request.args.get("session_date") or "").strip()
    subject = (request.args.get("subject") or "").strip()
    chapter = (request.args.get("chapter") or "").strip()
    student_id = request.args.get("student_id", type=int)
    semester = (request.args.get("semester") or "").strip()
    if doc_scope:
        params["doc_scope"] = doc_scope
    if cohort:
        params["cohort"] = cohort
    if study_year:
        params["study_year"] = study_year
    if mobility:
        params["mobility"] = mobility
    if session_date:
        params["session_date"] = session_date
    if subject:
        params["course_code"] = subject
    if chapter:
        params["chapter"] = chapter
    if student_id:
        params["student_id"] = student_id
    if semester in ("1", "2"):
        params["semester"] = semester
    if student_id and cfg.get("student_columns"):
        cfg["columns"] = cfg["student_columns"]
    qa = (request.args.get("qa") or "").strip()
    if qa:
        params["qa"] = qa
    # role_mode also sent via header from _ops_get
    params["role_mode"] = _user_scopes_header().get("X-Role-Mode", "all")

    # Rounds list for the toolbar filter (admissions modules)
    rounds = []
    if cfg.get("round_filter"):
        try:
            r_resp = _ops_get("/ops/admission-rounds", {})
            if r_resp.status_code == 200:
                rounds = r_resp.json() or []
        except requests.RequestException:
            rounds = []
    cohort_options = []
    student_options = []
    if cfg.get("cohort_filter") or cfg.get("require_cohort") or cfg.get("doc_scope_filter"):
        try:
            c_resp = _ops_get("/ops/cohort-options", {})
            if c_resp.status_code == 200 and isinstance(c_resp.json(), list):
                cohort_options = c_resp.json()
        except requests.RequestException:
            cohort_options = []
    if cfg.get("student_filter"):
        try:
            s_resp = _ops_get("/ops/students", {})
            if s_resp.status_code == 200 and isinstance(s_resp.json(), list):
                student_options = s_resp.json()
        except requests.RequestException:
            student_options = []
    programs = []
    if cfg.get("program_filter"):
        try:
            p_resp = requests.get(f"{API_BASE}/programs", timeout=5)
            if p_resp.status_code == 200:
                programs = p_resp.json() or []
        except requests.RequestException:
            programs = []
    intl_partners = []
    if perm_code in ("asst.intl_faculty", "asst.intl_students"):
        try:
            pr_resp = _ops_get("/ops/intl/partners", {})
            if pr_resp.status_code == 200:
                intl_partners = pr_resp.json() or []
        except requests.RequestException:
            intl_partners = []
    try:
        resp = _ops_get(cfg["api"], params)
        if resp.status_code == 200:
            data = resp.json()
            if cfg.get("is_summary"):
                summary = data
            elif cfg.get("is_canvas_hub") and isinstance(data, dict):
                hub = data
                rows = data.get("rows") or []
                if data.get("title"):
                    cfg["title"] = data["title"]
                if data.get("desc"):
                    cfg["desc"] = data["desc"]
            elif cfg.get("is_student_library") and isinstance(data, dict):
                summary = data  # reuse summary slot for library payload
            elif cfg.get("is_crm_report") and isinstance(data, dict):
                summary = data
                rows = data.get("rows") or data.get("by_activity") or []
            elif cfg.get("is_collection_report") and isinstance(data, dict):
                summary = data
                rows = data.get("rows") or data.get("by_type") or []
            else:
                rows = data if isinstance(data, list) else []
        else:
            flash("Không tải được dữ liệu." if _ui_lang() != "en" else "Could not load data.")
    except requests.RequestException:
        flash("Lỗi kết nối API." if _ui_lang() != "en" else "API connection error.")

    if q and isinstance(rows, list) and rows and isinstance(rows[0], dict):
        ql = q.lower()
        filtered = []
        for r in rows:
            blob = " ".join(
                str(v) for v in r.values()
                if v is not None and not isinstance(v, (dict, list, bool))
            )
            if ql in blob.lower():
                filtered.append(r)
        rows = filtered

    if cfg.get("is_canvas_hub"):
        page_rows, pagination = _paginate_list(rows)
        return render_template(
            "ops/canvas_hub.html",
            perm_code=perm_code,
            cfg=cfg,
            hub=hub or {
                "title": cfg["title"],
                "desc": cfg["desc"],
                "canvas_login_url": "https://cfvg.instructure.com/login/canvas",
                "guides": [],
                "stats": {},
            },
            rows=page_rows,
            all_rows=rows,
            status_labels=_localized_status_labels(),
            status_options=_status_options_map(),
            user_scopes=(session.get("user") or {}).get("program_scopes") or [],
            pagination=pagination,
            pagination_url=request.endpoint,
            pagination_params={k: v for k, v in (("q", q), ("status", status)) if v},
            pagination_sizes=list(OPS_PER_PAGE_OPTIONS),
        )

    if cfg.get("is_student_library"):
        library = summary or {"courses": [], "materials": [], "stats": {"courses": 0, "files": 0}}
        return render_template(
            "ops/student_library.html",
            library=library,
            q=q,
            status_labels=_localized_status_labels(),
            status_options=_status_options_map(),
        )

    page_rows, pagination = _paginate_list(rows)
    pag_params = {}
    if q:
        pag_params["q"] = q
    if status:
        pag_params["status"] = status
    if version_id:
        pag_params["version_id"] = version_id
    if program_code:
        pag_params["program_code"] = program_code
    if version_code:
        pag_params["version_code"] = version_code
    if round_id:
        pag_params["round_id"] = round_id
    if intake_session:
        pag_params["intake_session"] = intake_session
    if event_type:
        pag_params["event_type"] = event_type
    if converted:
        pag_params["converted"] = converted
    if pic:
        pag_params["pic"] = pic
    if intake:
        pag_params["intake"] = intake
    if year:
        pag_params["year"] = year
    for _extra_key in (
        "doc_scope", "cohort", "study_year", "mobility", "session_date", "subject", "chapter", "student_id", "semester",
    ):
        _extra_val = locals().get(_extra_key)
        if _extra_val:
            pag_params[_extra_key] = _extra_val
    if prospect_level:
        pag_params["prospect_level"] = prospect_level
    if expiry:
        pag_params["expiry"] = expiry
    version_filter = None
    if version_id and rows:
        sample = rows[0] if isinstance(rows, list) and rows else None
        if sample:
            version_filter = {
                "id": version_id,
                "version_code": sample.get("version_code") or "",
                "program_code": sample.get("program_code") or "",
                "name": sample.get("version_name") or sample.get("program_version_name") or "",
            }
        else:
            version_filter = {"id": version_id, "version_code": "", "program_code": "", "name": ""}
    elif version_id:
        version_filter = {"id": version_id, "version_code": "", "program_code": "", "name": ""}
    # KPI deep-links for reports (RBAC-aware, live access — not slim session perms)
    summary_links = _summary_deep_links() if cfg.get("is_summary") and summary else None
    treasury_kpis = None
    fee_alert_criteria = None
    if cfg.get("treasury_kpis") or perm_code in (
        "accounting.charges",
        "accounting.candidate_files",
        "accounting.tuition_tracker",
        "accounting.fee_alerts",
    ):
        try:
            k_resp = _ops_get("/ops/treasury/summary")
            if k_resp.status_code == 200:
                treasury_kpis = k_resp.json() or {}
        except requests.RequestException:
            treasury_kpis = None
    if cfg.get("is_fee_alerts"):
        try:
            c_resp = _ops_get("/ops/treasury/alert-criteria")
            if c_resp.status_code == 200:
                fee_alert_criteria = c_resp.json() or []
        except requests.RequestException:
            fee_alert_criteria = []
    return render_template(
        "ops/module.html",
        perm_code=perm_code,
        cfg=cfg,
        rows=page_rows,
        all_rows=rows,
        summary=summary,
        summary_links=summary_links,
        q=q,
        status=status,
        version_id=version_id,
        version_filter=version_filter,
        program_code=program_code,
        version_code=version_code,
        round_id=round_id,
        intake_session=intake_session,
        event_type=event_type,
        converted=converted,
        pic=pic,
        intake=intake,
        year=year,
        prospect_level=prospect_level,
        expiry=expiry,
        doc_scope=doc_scope,
        cohort=cohort,
        study_year=study_year,
        mobility=mobility,
        session_date=session_date,
        subject=subject,
        chapter=chapter,
        student_id=student_id,
        semester=semester,
        round_years=sorted({str(r.get("year")) for r in rounds if isinstance(r, dict) and r.get("year")}, reverse=True),
        cohort_options=cohort_options,
        student_options=student_options,
        rounds=rounds,
        programs=programs,
        intl_partners=intl_partners,
        status_labels=_localized_status_labels(),
        status_options=_status_options_map(),
        status_filter_options=status_filter_options,
        pagination=pagination,
        pagination_url=request.endpoint,
        pagination_params=pag_params,
        pagination_sizes=list(OPS_PER_PAGE_OPTIONS),
        treasury_kpis=treasury_kpis,
        fee_alert_criteria=fee_alert_criteria,
        crm_report=summary if (cfg.get("is_crm_report") or cfg.get("is_collection_report")) else None,
    )


@app.route("/ops/admissions/rounds")
def ops_admissions_rounds():
    return _render_ops_module("admissions.rounds")


@app.route("/ops/admissions/round-docs")
def ops_admissions_round_docs():
    return _render_ops_module("admissions.round_docs")


@app.route("/ops/admissions/doc-types")
def ops_admissions_doc_types():
    return _render_ops_module("admissions.doc_types")


@app.route("/ops/admissions/applications")
def ops_admissions_applications():
    return _render_ops_module("admissions.applications")


@app.route("/ops/admissions/interviews")
def ops_admissions_interviews():
    return _render_ops_module("admissions.interviews")


@app.route("/ops/admissions/interviews/<int:session_id>")
def ops_interview_detail(session_id):
    from ops_modules import STATUS_LABELS

    if not (
        _user_has_perm("admissions.interviews")
        or _user_has_perm("admissions.applications")
        or _user_has_perm("admissions.results")
    ):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/interviews/{session_id}")
        if resp.status_code != 200:
            flash("Không tải được buổi phỏng vấn.")
            return redirect(url_for("ops_admissions_interviews"))
        data = resp.json()
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_admissions_interviews"))
    return render_template(
        "ops/interview_scores.html",
        user=session.get("user"),
        data=data,
        status_labels=_localized_status_labels(),
    )


@app.route("/ops/admissions/mail")
def ops_admissions_mail():
    return _render_ops_module("admissions.mail")


@app.route("/ops/admissions/results")
def ops_admissions_results():
    return _render_ops_module("admissions.results")


@app.route("/ops/admissions/pre-enroll")
def ops_admissions_pre_enroll():
    return _render_ops_module("admissions.pre_enroll")


@app.route("/ops/admissions/enrolled")
def ops_admissions_enrolled_files():
    return _render_ops_module("admissions.enrolled_files")


def _render_person_dossier(resp):
    if resp.status_code == 200:
        return render_template(
            "ops/person_dossier.html",
            user=session.get("user"),
            dossier=resp.json(),
        )
    try:
        err = resp.json().get("error") or "Không mở được hồ sơ."
    except Exception:
        err = "Không mở được hồ sơ."
    flash(err)
    return redirect(url_for("ops_home"))


@app.route("/ops/persons/<int:person_id>")
def ops_person_dossier_page(person_id):
    if not session.get("user"):
        return redirect(url_for("login"))
    return _render_person_dossier(_ops_get(f"/ops/persons/{person_id}"))


@app.route("/ops/persons/by-application/<int:app_id>")
def ops_person_dossier_by_application_page(app_id):
    if not session.get("user"):
        return redirect(url_for("login"))
    return _render_person_dossier(_ops_get(f"/ops/persons/by-application/{app_id}"))


@app.route("/ops/admissions/crm-source")
def ops_admissions_crm_source():
    return _render_ops_module("admissions.crm_source")


@app.route("/ops/admissions/crm-activities")
def ops_admissions_crm_activities():
    return _render_ops_module("admissions.crm_activities")


@app.route("/ops/admissions/crm-reminders")
def ops_admissions_crm_reminders():
    return _render_ops_module("admissions.crm_reminders")


@app.route("/ops/admissions/crm-reports")
def ops_admissions_crm_reports():
    return _render_ops_module("admissions.crm_reports")


@app.route("/ops/admissions/events")
def ops_admissions_events():
    return _render_ops_module("admissions.events")


@app.route("/ops/admissions/neu-prep")
def ops_admissions_neu_prep():
    return _render_ops_module("admissions.neu_prep")


@app.route("/ops/admissions/written-exams")
def ops_admissions_written_exams():
    return _render_ops_module("admissions.written_exams")


@app.route("/ops/students")
def ops_students_manage():
    return _render_ops_module("students.manage")


@app.route("/ops/students/academic")
def ops_students_academic():
    return _render_ops_module("students.academic")


@app.route("/ops/students/academic/<int:learner_id>/print")
def ops_academic_print(learner_id):
    if not session.get("user"):
        return redirect(url_for("login"))
    if not (
        _user_has_perm("students.academic")
        or _user_has_perm("students.manage")
        or _user_has_perm("teaching.grades")
        or (session.get("user") or {}).get("is_admin")
    ):
        _flash_t("no_permission")
        return redirect(url_for("ops_home"))
    kind = (request.args.get("kind") or "progress").strip()
    edition = "official" if kind == "transcript" else "tracking"
    resp = _ops_get(f"/ops/academic-records/{learner_id}?edition={edition}")
    if resp.status_code != 200:
        try:
            err = resp.json().get("error") or "Không tải được bảng điểm."
        except Exception:
            err = "Không tải được bảng điểm."
        from flask import flash
        flash(err, "error")
        return redirect(url_for("ops_students_academic"))
    return render_template(
        "ops/academic_print.html",
        doc=resp.json(),
        kind=kind,
        ui_lang=_ui_lang(),
    )


@app.route("/ops/student/progress")
def ops_student_progress():
    return _render_ops_module("student.progress")


@app.route("/ops/student/progress/print")
def ops_student_progress_print():
    if not session.get("user"):
        return redirect(url_for("login"))
    if not (_user_has_perm("student.progress") or (session.get("user") or {}).get("is_admin")):
        _flash_t("no_permission")
        return redirect(url_for("ops_home"))
    kind = (request.args.get("kind") or "progress").strip()
    edition = "official" if kind == "transcript" else "tracking"
    resp = _ops_get(f"/ops/student/me/progress?edition={edition}")
    if resp.status_code != 200:
        _flash_t("no_permission")
        return redirect(url_for("ops_student_progress"))
    return render_template(
        "ops/academic_print.html",
        doc=resp.json(),
        kind=kind,
        ui_lang=_ui_lang(),
    )


@app.route("/ops/teaching/schedule")
def ops_teaching_schedule():
    return _render_ops_module("teaching.schedule")


@app.route("/ops/accounting/fees")
def ops_accounting_fees():
    return _render_ops_module("accounting.fees")


@app.route("/ops/accounting/official")
def ops_accounting_official():
    return _render_ops_module("accounting.official_list")


@app.route("/ops/accounting/charges")
def ops_accounting_charges():
    return _render_ops_module("accounting.charges")


@app.route("/ops/accounting/benefits")
def ops_accounting_benefits():
    return _render_ops_module("accounting.benefits")


@app.route("/ops/accounting/refunds")
def ops_accounting_refunds():
    return _render_ops_module("accounting.refunds")


@app.route("/ops/accounting/billing-profiles")
def ops_accounting_billing_profiles():
    return _render_ops_module("accounting.billing_profiles")


@app.route("/ops/accounting/tuition-tracker")
def ops_accounting_tuition_tracker():
    return _render_ops_module("accounting.tuition_tracker")


@app.route("/ops/accounting/fee-alerts")
def ops_accounting_fee_alerts():
    return _render_ops_module("accounting.fee_alerts")


@app.route("/ops/accounting/fee-types")
def ops_accounting_fee_types():
    return _render_ops_module("accounting.fee_types")


@app.route("/ops/accounting/candidate-files")
def ops_accounting_candidate_files():
    return _render_ops_module("accounting.candidate_files")


@app.route("/ops/accounting/collection-report")
def ops_accounting_collection_report():
    return _render_ops_module("accounting.collection_report")


@app.route("/ops/accounting/receipts")
def ops_accounting_receipts():
    return _render_ops_module("accounting.receipts")


@app.route("/ops/accounting/payment-methods")
def ops_accounting_payment_methods():
    return _render_ops_module("accounting.payment_methods")


@app.route("/ops/accounting/round-fees")
def ops_accounting_round_fees():
    return _render_ops_module("accounting.round_fee_settings")


@app.route("/ops/accounting/intake-plans")
def ops_accounting_intake_plans():
    return _render_ops_module("accounting.intake_plans")


@app.route("/ops/accounting/payment-imports")
def ops_accounting_payment_imports():
    return _render_ops_module("accounting.payment_imports")


@app.route("/ops/accounting/receipt-emails")
def ops_accounting_receipt_emails():
    return _render_ops_module("accounting.receipt_emails")


@app.route("/ops/student/my-fees")
def ops_student_my_fees():
    return _render_ops_module("accounting.my_fees")


@app.route("/ops/admissions/verification")
def ops_admissions_verification():
    return _render_ops_module("admissions.verification_queue")


@app.route("/ops/admissions/student-numbering")
def ops_admissions_student_numbering():
    return _render_ops_module("admissions.student_numbering")


@app.route("/ops/teaching/review-batches")
def ops_teaching_review_batches():
    return _render_ops_module("teaching.review_batches")


@app.route("/ops/intl/partners")
def ops_intl_partners():
    return _render_ops_module("intl.partners")


@app.route("/ops/intl/coop")
def ops_intl_coop():
    return _render_ops_module("intl.cooperation_programs")


@app.route("/ops/intl/steps")
def ops_intl_steps():
    return _render_ops_module("intl.workflow_steps")


@app.route("/ops/intl/reports")
def ops_intl_reports():
    return _render_ops_module("intl.exchange_reports")


@app.route("/ops/admin/audit-logs")
def ops_admin_audit_logs():
    return _render_ops_module("admin.audit_logs")


@app.route("/api/ops/treasury/receipts", methods=["GET", "POST"])
def api_nv_receipts():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/treasury/receipts", params=request.args)
    return _api_proxy("post", "/ops/treasury/receipts", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/payment-methods", methods=["GET", "POST"])
def api_nv_payment_methods():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/treasury/payment-methods", params=request.args)
    return _api_proxy("post", "/ops/treasury/payment-methods", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/benefits", methods=["GET", "POST"])
def api_ops_treasury_benefits():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/treasury/benefits", params=request.args)
    return _api_proxy("post", "/ops/treasury/benefits", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/benefits/<int:benefit_id>/<action>", methods=["POST"])
def api_ops_treasury_benefit_action(benefit_id, action):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", f"/ops/treasury/benefits/{benefit_id}/{action}", {})


@app.route("/api/ops/treasury/refunds", methods=["GET", "POST"])
def api_ops_treasury_refunds():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/treasury/refunds", params=request.args)
    return _api_proxy("post", "/ops/treasury/refunds", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/refunds/<int:refund_id>/<action>", methods=["POST"])
def api_ops_treasury_refund_action(refund_id, action):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", f"/ops/treasury/refunds/{refund_id}/{action}", {})


@app.route("/api/ops/treasury/billing-profiles", methods=["GET", "POST"])
def api_ops_treasury_billing_profiles():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/treasury/billing-profiles", params=request.args)
    return _api_proxy("post", "/ops/treasury/billing-profiles", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/intake-plans", methods=["GET", "POST"])
def api_ops_treasury_intake_plans():
    if request.method == "GET":
        return _api_proxy("get", "/ops/treasury/intake-plans", params=request.args)
    return _api_proxy("post", "/ops/treasury/intake-plans", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/round-fee-settings", methods=["GET", "POST"])
def api_nv_round_fees():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/treasury/round-fee-settings", params=request.args)
    return _api_proxy("post", "/ops/treasury/round-fee-settings", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/payment-imports", methods=["POST"])
def api_nv_payment_imports():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", "/ops/treasury/payment-imports", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/receipt-emails", methods=["GET", "POST"])
def api_nv_receipt_emails():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/treasury/receipt-emails", params=request.args)
    return _api_proxy("post", "/ops/treasury/receipt-emails", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/commitments", methods=["GET", "POST"])
def api_nv_commitments():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/treasury/commitments", params=request.args)
    return _api_proxy("post", "/ops/treasury/commitments", request.get_json(silent=True) or {})


@app.route("/api/ops/student-numbering", methods=["GET", "POST"])
def api_nv_student_numbering():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/student-numbering", params=request.args)
    return _api_proxy("post", "/ops/student-numbering", request.get_json(silent=True) or {})


@app.route("/api/ops/applications/<int:app_id>/confirm-enrollment", methods=["POST"])
def api_nv_confirm_enrollment(app_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", f"/ops/applications/{app_id}/confirm-enrollment", request.get_json(silent=True) or {})


@app.route("/api/ops/review-batches", methods=["GET", "POST"])
def api_nv_review_batches():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/review-batches", params=request.args)
    return _api_proxy("post", "/ops/review-batches", request.get_json(silent=True) or {})


@app.route("/api/ops/review-batches/<int:bid>/lock", methods=["POST"])
def api_nv_review_lock(bid):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", f"/ops/review-batches/{bid}/lock", {})


@app.route("/api/ops/intl/partners", methods=["GET", "POST"])
def api_nv_partners():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/intl/partners", params=request.args)
    return _api_proxy("post", "/ops/intl/partners", request.get_json(silent=True) or {})


@app.route("/api/ops/intl/coop-programs", methods=["GET", "POST"])
def api_nv_coop():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/intl/coop-programs", params=request.args)
    return _api_proxy("post", "/ops/intl/coop-programs", request.get_json(silent=True) or {})


@app.route("/api/ops/intl/workflow-steps", methods=["GET", "POST"])
def api_nv_workflow_steps():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/intl/workflow-steps", params=request.args)
    return _api_proxy("post", "/ops/intl/workflow-steps", request.get_json(silent=True) or {})


@app.route("/api/ops/applications/bulk-flag", methods=["POST"])
def api_nv_bulk_flag():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", "/ops/applications/bulk-flag", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/fee-types", methods=["GET", "POST"])
def api_ops_treasury_fee_types():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/treasury/fee-types", params=request.args)
    return _api_proxy("post", "/ops/treasury/fee-types", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/fee-types/<code>", methods=["PATCH"])
def api_ops_treasury_fee_type_patch(code):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("patch", f"/ops/treasury/fee-types/{code}", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/charges/<int:charge_id>/pay", methods=["POST"])
def api_ops_treasury_charge_pay(charge_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(
            f"{API_BASE}/ops/treasury/charges/{charge_id}/pay",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/treasury/charges/<int:charge_id>/adjust", methods=["POST"])
def api_ops_treasury_charge_adjust(charge_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(
            f"{API_BASE}/ops/treasury/charges/{charge_id}/adjust",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/treasury/charges/<int:charge_id>/waiver", methods=["POST", "PATCH"])
def api_ops_treasury_charge_waiver(charge_id):
    return _api_proxy(request.method.lower(), f"/ops/treasury/charges/{charge_id}/waiver", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/candidate-files/<int:charge_id>", methods=["PATCH"])
def api_ops_treasury_candidate_file_patch(charge_id):
    return _api_proxy("patch", f"/ops/treasury/candidate-files/{charge_id}", request.get_json(silent=True) or {})


@app.route("/api/ops/treasury/alert-criteria/<code>", methods=["PATCH"])
def api_ops_treasury_alert_criteria_patch(code):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("accounting.fee_alerts")
        or _user_has_perm("accounting.charges")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("patch", f"/ops/treasury/alert-criteria/{code}", request.get_json(silent=True) or {})


@app.route("/ops/programs")
def ops_programs():
    return _render_ops_module("programs.structure")


@app.route("/ops/courses")
def ops_courses():
    return _render_ops_module("programs.courses")


@app.route("/ops/courses/<int:course_id>")
def ops_course_detail(course_id):
    from ops_modules import STATUS_LABELS

    if not (_user_has_perm("programs.courses") or _user_has_perm("teaching.materials")):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    course = None
    try:
        resp = _ops_get(f"/ops/courses/{course_id}")
        if resp.status_code == 200:
            course = resp.json()
        else:
            flash("Không tải được học phần.")
            return redirect(url_for("ops_courses"))
    except requests.RequestException:
        flash("Lỗi kết nối API.")
        return redirect(url_for("ops_courses"))
    return render_template(
        "ops/course_detail.html",
        course=course,
        status_labels=_localized_status_labels(),
    )


@app.route("/ops/classes")
def ops_classes():
    return _render_ops_module("classes.manage")


@app.route("/ops/classes/<int:class_id>/students")
def ops_class_students_page(class_id):
    from ops_modules import STATUS_LABELS

    if not _user_has_perm("classes.manage"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/classes/{class_id}/students")
        if resp.status_code != 200:
            flash("Không tải được danh sách SV.")
            return redirect(url_for("ops_classes"))
        data = resp.json()
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_classes"))
    return render_template(
        "ops/class_students.html",
        data=data,
        status_labels=_localized_status_labels(),
        status_options=_status_options_map(),
        user=session.get("user"),
    )


@app.route("/ops/faculty")
def ops_faculty():
    return _render_ops_module("teaching.faculty")


@app.route("/ops/teaching/assign")
def ops_teaching_assign():
    return _render_ops_module("teaching.assign")


@app.route("/ops/teaching/lessons")
def ops_class_lessons_hub():
    return _render_ops_module("teaching.lessons")


@app.route("/ops/teaching/assignments/<int:assignment_id>/lessons")
def ops_assignment_lessons(assignment_id):
    from ops_modules import STATUS_LABELS

    if not (
        _user_has_perm("teaching.lessons")
        or _user_has_perm("teaching.materials")
        or _user_has_perm("teaching.assign")
    ):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/teaching-assignments/{assignment_id}/lessons")
        if resp.status_code != 200:
            flash("Không tải được bài giảng.")
            return redirect(url_for("ops_class_lessons_hub"))
        data = resp.json()
    except requests.RequestException:
        flash("Lỗi kết nối API.")
        return redirect(url_for("ops_class_lessons_hub"))
    return render_template(
        "ops/class_lessons.html",
        data=data,
        status_labels=_localized_status_labels(),
    )


@app.route("/ops/class-lessons/<int:lesson_id>")
def ops_class_lesson_detail(lesson_id):
    from ops_modules import STATUS_LABELS

    if not (
        _user_has_perm("teaching.lessons")
        or _user_has_perm("teaching.materials")
    ):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/class-lessons/{lesson_id}")
        if resp.status_code != 200:
            flash("Không tải được bài học.")
            return redirect(url_for("ops_class_lessons_hub"))
        lesson = resp.json()
    except requests.RequestException:
        flash("Lỗi kết nối API.")
        return redirect(url_for("ops_class_lessons_hub"))
    return render_template(
        "ops/lesson_detail.html",
        lesson=lesson,
        status_labels=_localized_status_labels(),
    )


@app.route("/ops/class-lessons/<int:lesson_id>/learning-stats")
def ops_lesson_learning_stats(lesson_id):
    if not (
        _user_has_perm("teaching.lessons") or _user_has_perm("teaching.materials")
    ):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/class-lessons/{lesson_id}/learning-stats")
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không tải được thống kê.")
            return redirect(url_for("ops_class_lesson_detail", lesson_id=lesson_id))
        stats = resp.json()
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_class_lesson_detail", lesson_id=lesson_id))
    return render_template("ops/lesson_learning_stats.html", stats=stats)


@app.route("/ops/teaching/assignments/<int:assignment_id>/learning-stats")
def ops_assignment_learning_stats(assignment_id):
    if not (
        _user_has_perm("teaching.lessons") or _user_has_perm("teaching.materials")
    ):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/teaching-assignments/{assignment_id}/learning-stats")
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không tải được thống kê.")
            return redirect(url_for("ops_assignment_lessons", assignment_id=assignment_id))
        stats = resp.json()
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_assignment_lessons", assignment_id=assignment_id))
    return render_template("ops/assignment_learning_stats.html", stats=stats)


@app.route("/ops/teaching/lesson-comments")
def ops_lesson_comments_inbox():
    if not (
        _user_has_perm("teaching.lessons") or _user_has_perm("teaching.materials")
    ):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    params = {
        k: v
        for k, v in {
            "course_id": request.args.get("course_id") or None,
            "class_id": request.args.get("class_id") or None,
            "lesson_no": request.args.get("lesson_no") or None,
            "comment_type": request.args.get("comment_type") or None,
            "q": request.args.get("q") or None,
        }.items()
        if v
    }
    try:
        resp = _ops_get("/ops/lesson-comments", params)
        data = resp.json() if resp.status_code == 200 else {"items": [], "filters": {}}
    except Exception as e:
        flash(str(e))
        data = {"items": [], "filters": {}}
    return render_template(
        "ops/lesson_comments_inbox.html",
        items=data.get("items") or [],
        filters=data.get("filters")
        or {"courses": [], "classes": [], "chapters": [], "comment_types": []},
    )


@app.route("/ops/lessons/<int:lesson_id>/preview")
def ops_lesson_preview(lesson_id):
    from ops_modules import STATUS_LABELS

    is_student = _user_has_perm("student.lessons") and not (
        _user_has_perm("teaching.lessons") or _user_has_perm("teaching.materials") or _user_has_perm("teaching.online_lectures")
    )
    # Staff may also open preview; students need student.lessons
    if not (
        _user_has_perm("student.lessons")
        or _user_has_perm("teaching.lessons")
        or _user_has_perm("teaching.materials")
        or _user_has_perm("teaching.online_lectures")
        or _user_has_perm("student.library")
    ):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    params = {"as_student": "1"} if is_student else {}
    # Staff preview uses coordinator payload (all files) so upload/release stays usable.
    try:
        if params.get("as_student"):
            resp = _ops_get(f"/ops/class-lessons/{lesson_id}", params)
        else:
            resp = _ops_get(f"/ops/class-lessons/{lesson_id}")
        if resp.status_code != 200:
            flash("Bài học chưa publish hoặc không tồn tại.")
            return redirect(url_for("ops_student_lessons") if is_student else url_for("ops_class_lessons_hub"))
        lesson = resp.json()
        if lesson.get("status") != "published" and params.get("as_student"):
            flash("Bài học chưa được publish.")
            return redirect(url_for("ops_student_lessons"))
    except requests.RequestException:
        flash("Lỗi kết nối API.")
        return redirect(url_for("ops_home"))
    return render_template(
        "ops/lesson_preview.html",
        lesson=lesson,
        status_labels=_localized_status_labels(),
        is_student=bool(is_student),
    )


@app.route("/ops/student/lessons")
def ops_student_lessons():
    return _render_ops_module("student.lessons")


@app.route("/ops/elearn/lectures")
def ops_online_lectures():
    return _render_ops_module("teaching.online_lectures")


@app.route("/ops/elearn/objectives")
def ops_elearn_objectives():
    return _render_ops_module("teaching.objectives")


@app.route("/ops/elearn/instructor-intel")
def ops_instructor_intel():
    return _render_ops_module("teaching.instructor_intel")


@app.route("/ops/elearn/tracker")
def ops_student_tracker():
    return _render_ops_module("teaching.student_tracker")


@app.route("/ops/elearn/exam-integrity")
def ops_exam_integrity():
    return _render_ops_module("teaching.exam_integrity")


@app.route("/ops/elearn/return-meetings")
def ops_return_meetings():
    return _render_ops_module("teaching.return_meetings")


@app.route("/ops/student/study-plan")
def ops_student_study_plan():
    return _render_ops_module("student.study_plan")


@app.route("/ops/student/time-to-learn")
def ops_student_time_to_learn():
    return _render_ops_module("student.time_to_learn")


@app.route("/ops/student/objective-recs")
def ops_student_objective_recs():
    return _render_ops_module("student.objective_recs")


@app.route("/ops/student/agenda")
def ops_student_agenda():
    return _render_ops_module("student.agenda")


@app.route("/ops/student/return-meetings")
def ops_student_return_meetings():
    return _render_ops_module("student.return_meetings")


@app.route("/ops/materials")
def ops_materials():
    return _render_ops_module("teaching.materials")


@app.route("/ops/groups")
def ops_groups():
    return _render_ops_module("teaching.groups")


@app.route("/ops/attendance")
def ops_attendance():
    return _render_ops_module("teaching.attendance")


@app.route("/ops/attendance/sessions/<int:session_id>")
def ops_attendance_session(session_id):
    if not (
        _user_has_perm("teaching.attendance") or _user_has_perm("teaching.lessons")
    ):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/attendance/sessions/{session_id}")
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không tải được điểm danh.")
            return redirect(url_for("ops_attendance"))
        data = resp.json()
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_attendance"))
    return render_template("ops/attendance_session.html", data=data)


@app.route("/ops/attendance/lessons/<int:lesson_id>")
def ops_attendance_from_lesson(lesson_id):
    if not (
        _user_has_perm("teaching.attendance") or _user_has_perm("teaching.lessons")
    ):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = requests.post(
            f"{API_BASE}/ops/attendance/lessons/{lesson_id}/session",
            json={},
            headers=_user_scopes_header(),
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            flash((resp.json() or {}).get("error") or "Không tạo được phiên điểm danh.")
            return redirect(url_for("ops_class_lesson_detail", lesson_id=lesson_id))
        data = resp.json() or {}
        sid = (data.get("session") or {}).get("id")
        if not sid:
            flash("Không tạo được phiên điểm danh.")
            return redirect(url_for("ops_class_lesson_detail", lesson_id=lesson_id))
        return redirect(url_for("ops_attendance_session", session_id=sid))
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_class_lesson_detail", lesson_id=lesson_id))


@app.route("/ops/attendance/scan")
def ops_attendance_scan():
    """Student QR check-in landing (requires login)."""
    if not session.get("user"):
        return redirect(url_for("login", next=request.url))
    token = (request.args.get("t") or "").strip()
    result = None
    if token:
        u = session.get("user") or {}
        try:
            resp = requests.post(
                f"{API_BASE}/ops/attendance/scan",
                json={
                    "token": token,
                    "student_name": u.get("name") or "",
                    "student_email": (
                        u.get("student_email")
                        or u.get("contact_email")
                        or u.get("email")
                        or ""
                    ),
                },
                headers=_user_scopes_header(),
                timeout=15,
            )
            data = resp.json() if resp.content else {}
            if resp.status_code == 200:
                result = data
            else:
                result = {
                    "ok": False,
                    "error": data.get("error") or "Không điểm danh được",
                }
        except Exception as e:
            result = {"ok": False, "error": str(e)}
    return render_template("ops/attendance_scan.html", result=result, token=token)


@app.route("/ops/assignments")
def ops_assignments():
    depts = set(_dept_codes())
    # Học viên thuần → danh sách bài đã mở; GV / điều phối → hub lớp–môn
    if (
        "hoc_vien" in depts
        and "giang_vien" not in depts
        and not _user_has_perm("teaching.assign")
    ):
        return _render_student_practice()
    return _render_ops_module("teaching.assignments")


@app.route("/ops/student-practice")
def ops_student_practice():
    return _render_student_practice()


def _render_student_practice():
    """Student list of published practice homeworks (perm: teaching.assignments)."""
    from flask import g
    from ops_modules import OPS_MODULES, group_toolbar_actions
    from i18n import localize_module

    if not _user_has_perm("teaching.assignments"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    g.feature_code = "teaching.assignments"
    lang = _ui_lang()
    cfg = localize_module(dict(OPS_MODULES["student.practice"]), "student.practice", lang)
    for k, v in (
        ("bulk_select", False),
        ("allow_delete", False),
        ("exec_view_only", False),
        ("import_bulk", False),
        ("fee_actions", False),
        ("charge_actions", False),
        ("leave_actions", False),
        ("canvas_export_roster", False),
        ("round_filter", False),
        ("select_interview", False),
    ):
        cfg.setdefault(k, v)
    cfg["action_menus"] = group_toolbar_actions(cfg.get("actions") or [], lang)
    cfg["workflow"] = (
        "Complete published practice online by assigned variant"
        if lang == "en"
        else "Làm bài thực hành online theo mã đề được giao"
    )
    q = (request.args.get("q") or "").strip()
    try:
        resp = _ops_get(cfg["api"])
        rows = resp.json() if resp.status_code == 200 else []
        if not isinstance(rows, list):
            rows = []
    except Exception as e:
        flash(str(e))
        rows = []
    is_en = lang == "en"
    for r in rows:
        kind = r.get("kind") or "practice"
        r["kind"] = kind
        if kind == "mc":
            r["kind_label"] = "MC" if is_en else "Trắc nghiệm"
            if r.get("score") is not None and r.get("max_score") is not None:
                r["score_label"] = f"{r['score']}/{r['max_score']}"
            else:
                r["score_label"] = "—"
        else:
            r["kind_label"] = "Practice" if is_en else "Thực hành"
            if r.get("score") is not None:
                r["score_label"] = str(r["score"])
            else:
                r["score_label"] = r.get("display_label") or "—"
    if q:
        ql = q.lower()
        rows = [
            r
            for r in rows
            if ql in str(r.get("title") or "").lower()
            or ql in str(r.get("course_code") or "").lower()
            or ql in str(r.get("class_name") or "").lower()
        ]
    page_rows, pagination = _paginate_list(rows)
    return render_template(
        "ops/module.html",
        perm_code="teaching.assignments",
        cfg=cfg,
        rows=page_rows,
        all_rows=rows,
        summary=None,
        summary_links=None,
        q=q,
        status="",
        version_id="",
        version_filter=None,
        program_code="",
        version_code="",
        round_id="",
        intake_session="",
        rounds=[],
        status_labels=_localized_status_labels(),
        status_options=_status_options_map(),
        status_filter_options=[],
        pagination=pagination,
        pagination_url=request.endpoint,
        pagination_params={k: v for k, v in (("q", q),) if v},
        pagination_sizes=list(OPS_PER_PAGE_OPTIONS),
    )


@app.route("/ops/practice/ta/<int:ta_id>")
def ops_practice_ta(ta_id):
    if not _user_has_perm("teaching.assignments"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    depts = set(_dept_codes())
    if "hoc_vien" in depts and "giang_vien" not in depts and not _user_has_perm("teaching.assign"):
        flash("Chức năng dành cho giảng viên / điều phối.")
        return redirect(url_for("ops_assignments"))
    try:
        resp = _ops_get(f"/ops/practice/teaching-assignments/{ta_id}/homeworks")
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không tải được bài thực hành.")
            return redirect(url_for("ops_assignments"))
        data = resp.json() or {}
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_assignments"))
    return render_template(
        "ops/practice_ta.html",
        user=session.get("user"),
        meta=data.get("meta") or {},
        items=data.get("items") or [],
    )


@app.route("/ops/practice/hw/<int:hw_id>")
def ops_practice_hw(hw_id):
    if not _user_has_perm("teaching.assignments"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/practice/homeworks/{hw_id}")
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không tìm thấy bài.")
            return redirect(url_for("ops_assignments"))
        hw = resp.json() or {}
        subs = _ops_get(f"/ops/practice/homeworks/{hw_id}/submissions")
        submissions = subs.json() if subs.status_code == 200 else []
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_assignments"))
    return render_template(
        "ops/practice_hw.html",
        user=session.get("user"),
        hw=hw,
        submissions=submissions if isinstance(submissions, list) else [],
    )


@app.route("/ops/practice/submissions/<int:sub_id>")
def ops_practice_submission(sub_id):
    if not _user_has_perm("teaching.assignments"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/practice/submissions/{sub_id}")
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không tìm thấy bài nộp.")
            return redirect(url_for("ops_assignments"))
        sub = resp.json() or {}
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_assignments"))
    depts = set(_dept_codes())
    is_student = (
        "hoc_vien" in depts
        and "giang_vien" not in depts
        and not _user_has_perm("teaching.assign")
    )
    if is_student:
        return redirect(url_for("ops_practice_do", hw_id=sub.get("homework_id")))
    return render_template(
        "ops/practice_grade.html",
        user=session.get("user"),
        sub=sub,
    )


@app.route("/ops/practice/do/<int:hw_id>")
def ops_practice_do(hw_id):
    if not _user_has_perm("teaching.assignments"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    u = session.get("user") or {}
    try:
        resp = requests.post(
            f"{API_BASE}/ops/practice/homeworks/{hw_id}/start",
            json={
                "student_name": u.get("name") or "",
                "student_email": (
                    u.get("student_email") or u.get("contact_email") or u.get("email") or ""
                ),
                "student_code": u.get("student_code") or "",
            },
            headers=_user_scopes_header(),
            timeout=15,
        )
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không mở được bài làm.")
            return redirect(url_for("ops_assignments"))
        sub = resp.json() or {}
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_assignments"))
    return render_template(
        "ops/practice_do.html",
        user=u,
        sub=sub,
    )


@app.route("/ops/mc/ta/<int:ta_id>")
def ops_mc_ta(ta_id):
    if not _user_has_perm("teaching.assignments"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    depts = set(_dept_codes())
    if "hoc_vien" in depts and "giang_vien" not in depts and not _user_has_perm("teaching.assign"):
        flash("Chức năng dành cho giảng viên / điều phối.")
        return redirect(url_for("ops_assignments"))
    try:
        resp = _ops_get(f"/ops/mc/teaching-assignments/{ta_id}/quizzes")
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không tải được bài TN.")
            return redirect(url_for("ops_assignments"))
        data = resp.json() or {}
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_assignments"))
    return render_template(
        "ops/mc_ta.html",
        user=session.get("user"),
        meta=data.get("meta") or {},
        items=data.get("items") or [],
    )


@app.route("/ops/mc/quiz/<int:quiz_id>")
def ops_mc_quiz(quiz_id):
    if not _user_has_perm("teaching.assignments"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/mc/quizzes/{quiz_id}")
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không tìm thấy bài TN.")
            return redirect(url_for("ops_assignments"))
        quiz = resp.json() or {}
        subs = _ops_get(f"/ops/mc/quizzes/{quiz_id}/submissions")
        submissions = subs.json() if subs.status_code == 200 else []
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_assignments"))
    return render_template(
        "ops/mc_quiz.html",
        user=session.get("user"),
        quiz=quiz,
        submissions=submissions if isinstance(submissions, list) else [],
    )


@app.route("/ops/mc/submissions/<int:sub_id>")
def ops_mc_submission(sub_id):
    if not _user_has_perm("teaching.assignments"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/mc/submissions/{sub_id}")
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không tìm thấy bài nộp.")
            return redirect(url_for("ops_assignments"))
        sub = resp.json() or {}
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_assignments"))
    return render_template(
        "ops/mc_grade.html",
        user=session.get("user"),
        sub=sub,
    )


@app.route("/ops/mc/do/<int:quiz_id>")
def ops_mc_do(quiz_id):
    if not _user_has_perm("teaching.assignments"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    u = session.get("user") or {}
    focus_chapter = (request.args.get("chapter") or "").strip()
    try:
        resp = requests.post(
            f"{API_BASE}/ops/mc/quizzes/{quiz_id}/start",
            json={
                "student_name": u.get("name") or "",
                "student_email": (
                    u.get("student_email") or u.get("contact_email") or u.get("email") or ""
                ),
                "student_code": u.get("student_code") or "",
            },
            headers=_user_scopes_header(),
            timeout=15,
        )
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không mở được bài TN.")
            return redirect(url_for("ops_assignments"))
        sub = resp.json() or {}
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_assignments"))
    return render_template(
        "ops/mc_do.html",
        user=u,
        sub=sub,
        focus_chapter=focus_chapter,
    )


@app.route("/ops/grades")
def ops_grades():
    return _render_ops_module("teaching.grades")


@app.route("/ops/grades/<int:class_id>")
def ops_gradebook(class_id):
    from ops_modules import STATUS_LABELS

    if not _user_has_perm("teaching.grades"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/classes/{class_id}/grades")
        if resp.status_code != 200:
            flash("Không tải được bảng điểm.")
            return redirect(url_for("ops_grades"))
        book = resp.json()
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_grades"))
    return render_template(
        "ops/gradebook.html",
        user=session.get("user"),
        book=book,
        status_labels=_localized_status_labels(),
    )


@app.route("/ops/exams")
def ops_exams():
    return _render_ops_module("teaching.exams")


@app.route("/ops/evaluation")
def ops_evaluation():
    return _render_ops_module("teaching.evaluation")


@app.route("/ops/thesis")
def ops_thesis():
    return _render_ops_module("teaching.thesis")


@app.route("/ops/thesis/<int:thesis_id>")
def ops_thesis_detail(thesis_id):
    from ops_modules import STATUS_LABELS

    if not _user_has_perm("teaching.thesis"):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/thesis-records/{thesis_id}")
        if resp.status_code != 200:
            flash("Không tải được hồ sơ đề án.")
            return redirect(url_for("ops_thesis"))
        row = resp.json()
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_thesis"))
    return render_template(
        "ops/thesis_detail.html",
        user=session.get("user"),
        row=row,
        status_labels=_localized_status_labels(),
    )

@app.route("/ops/alumni")
def ops_alumni():
    return _render_ops_module("alumni.members")


@app.route("/ops/alumni/events")
def ops_alumni_events():
    return _render_ops_module("alumni.events")


@app.route("/ops/alumni/portal")
def ops_alumni_portal():
    if not session.get("user"):
        return redirect(url_for("login"))
    if not _user_has_perm("alumni.portal"):
        flash("Bạn không có quyền cổng cựu học viên.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get("/ops/alumni/me")
    except Exception as e:
        flash(str(e))
        return redirect(url_for("ops_home"))
    if resp.status_code != 200:
        try:
            err = (resp.json() or {}).get("error") or "Không mở được cổng."
        except Exception:
            err = "Không mở được cổng."
        flash(err)
        return redirect(url_for("ops_home"))
    return render_template("ops/alumni_portal.html", user=session.get("user"), profile=resp.json())


@app.route("/ops/marcom/leads")
def ops_marcom_leads():
    return _render_ops_module("marcom.leads")


@app.route("/ops/marcom/campaigns")
def ops_marcom_campaigns():
    return _render_ops_module("marcom.campaigns")


@app.route("/ops/marcom/events")
def ops_marcom_events():
    return _render_ops_module("marcom.events")


@app.route("/ops/marcom/events/<int:event_id>/registrants")
def ops_marcom_event_registrants_page(event_id):
    if not (_user_has_perm("marcom.events") or _user_has_perm("admissions.events")):
        flash("Bạn không có quyền truy cập chức năng này.")
        return redirect(url_for("ops_home"))
    try:
        resp = _ops_get(f"/ops/marcom/events/{event_id}")
        back = "ops_admissions_events" if _user_has_perm("admissions.events") and not _user_has_perm("marcom.events") else "ops_marcom_events"
        if resp.status_code != 200:
            flash("Không tải được sự kiện.")
            return redirect(url_for(back))
        event = resp.json()
        regs = event.get("registrants")
        if regs is None:
            r2 = _ops_get(f"/ops/marcom/events/{event_id}/registrants")
            regs = r2.json() if r2.status_code == 200 else []
    except Exception as e:
        flash(str(e))
        back = "ops_admissions_events" if _user_has_perm("admissions.events") and not _user_has_perm("marcom.events") else "ops_marcom_events"
        return redirect(url_for(back))
    return render_template(
        "ops/marcom_event_registrants.html",
        event=event,
        registrants=regs or [],
        user=session.get("user"),
    )


@app.route("/ops/marcom/assets")
def ops_marcom_assets():
    return _render_ops_module("marcom.assets")


@app.route("/ops/marcom/reports")
def ops_marcom_reports():
    if not (_user_has_perm("marcom.reports") or _user_has_perm("marcom.campaigns") or _is_exec_viewer()):
        _flash_t("no_permission")
        return redirect(url_for("ops_home"))
    period = request.args.get("period") or "month"
    as_of = request.args.get("as_of") or ""
    attribution = request.args.get("attribution") or "first"
    qs = f"period={period}&attribution={attribution}"
    if as_of:
        qs += f"&as_of={as_of}"
    resp = _ops_get(f"/ops/marcom/reports?{qs}")
    report = resp.json() if resp.status_code == 200 else {"sections": [], "note": "Không tải được báo cáo."}
    return render_template("ops/marcom_reports.html", report=report, period=period, attribution=attribution)


@app.route("/ops/student/profile")
def ops_student_profile():
    return _render_ops_module("student.profile")


@app.route("/ops/student/schedule")
def ops_student_schedule():
    return _render_ops_module("student.schedule")


@app.route("/ops/student/results")
def ops_student_results():
    return _render_ops_module("student.results")


@app.route("/ops/student/library")
def ops_student_library():
    return _render_ops_module("student.library")


@app.route("/ops/reports")
def ops_reports():
    """Dashboard tích hợp vào trang SmartUni (/ops)."""
    return redirect(url_for("ops_home"))


@app.route("/ops/asst/tasks")
def ops_asst_tasks():
    return _render_ops_module("asst.exec_tasks")


@app.route("/ops/asst/calendar")
def ops_asst_calendar():
    return _render_ops_module("asst.calendar")


@app.route("/ops/asst/intl-faculty")
def ops_asst_intl_faculty():
    return _render_ops_module("asst.intl_faculty")


@app.route("/ops/asst/intl-students")
def ops_asst_intl_students():
    return _render_ops_module("asst.intl_students")


@app.route("/ops/asst/director-fr")
def ops_asst_director_fr():
    return _render_ops_module("asst.director_fr")


@app.route("/ops/asst/documents")
def ops_asst_documents():
    return _render_ops_module("asst.documents")


@app.route("/ops/asst/procurement")
def ops_asst_procurement():
    return _render_ops_module("asst.procurement")


@app.route("/ops/asst/payments")
def ops_asst_payments():
    return _render_ops_module("asst.payments")


@app.route("/ops/asst/weekly-reports")
def ops_asst_weekly_report():
    return _render_ops_module("asst.weekly_report")


@app.route("/ops/asst/leave")
def ops_asst_leave():
    return _render_ops_module("asst.leave")


@app.route("/ops/canvas/coordinator")
def ops_canvas_coordinator():
    return _render_ops_module("canvas.coordinator")


@app.route("/ops/canvas/faculty")
def ops_canvas_faculty():
    return _render_ops_module("canvas.faculty")


@app.route("/ops/canvas/student")
def ops_canvas_student():
    return _render_ops_module("canvas.student")


@app.route("/ops/canvas/accounting")
def ops_canvas_accounting():
    return _render_ops_module("canvas.accounting")


@app.route("/ops/canvas/it")
def ops_canvas_it():
    return _render_ops_module("canvas.it")


@app.route("/api/ops/applications/<int:app_id>", methods=["PATCH"])
def api_ops_application_patch(app_id):
    if not (
        session.get("user", {}).get("is_admin")
        or _user_has_perm("admissions.applications")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("patch", f"/ops/applications/{app_id}", request.get_json(silent=True) or {})


def _can_access_app_docs(*, manage: bool = False) -> bool:
    if not session.get("user"):
        return False
    if (session.get("user") or {}).get("is_admin"):
        return True
    if _user_has_perm("admissions.applications"):
        return True
    if manage:
        return _user_has_perm("accounting.candidate_files") or _user_has_perm("student.profile")
    return (
        _user_has_perm("admissions.results")
        or _user_has_perm("accounting.official_list")
        or _user_has_perm("accounting.candidate_files")
        or _user_has_perm("student.profile")
    )


def _stream_ops_file(path, params=None):
    try:
        resp = requests.get(
            f"{API_BASE}{path}",
            params=params or None,
            headers=_user_scopes_header(),
            timeout=60,
            stream=True,
        )
        if resp.status_code != 200:
            try:
                return jsonify(resp.json()), resp.status_code
            except Exception:
                return jsonify({"error": "Download failed"}), resp.status_code
        from flask import Response

        headers = {}
        if resp.headers.get("Content-Disposition"):
            headers["Content-Disposition"] = resp.headers["Content-Disposition"]
        if resp.headers.get("Content-Type"):
            headers["Content-Type"] = resp.headers["Content-Type"]
        return Response(resp.iter_content(chunk_size=8192), headers=headers)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/admission-doc-types", methods=["GET", "POST"])
def api_ops_admission_doc_types():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/admission-doc-types")
    return _api_proxy("post", "/ops/admission-doc-types", json_body=request.get_json(silent=True) or {})


@app.route("/api/ops/admission-round-docs", methods=["GET"])
def api_ops_admission_round_docs_search():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("get", "/ops/admission-round-docs", params=request.args)


@app.route("/api/ops/admission-rounds/<int:round_id>/docs", methods=["GET", "POST"])
def api_ops_admission_round_docs(round_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", f"/ops/admission-rounds/{round_id}/docs", params=request.args)
    f = request.files.get("file")
    files = None
    if f and f.filename:
        files = {"file": (f.filename, f.stream, f.mimetype)}
    data = {
        "title": request.form.get("title") or "",
        "notes": request.form.get("notes") or "",
        "program_codes": request.form.get("program_codes") or "",
        "doc_type_id": request.form.get("doc_type_id") or "",
        "share_scope": request.form.get("share_scope") or "",
        "cohort_code": request.form.get("cohort_code") or "",
    }
    try:
        resp = requests.post(
            f"{API_BASE}/ops/admission-rounds/{round_id}/docs",
            data=data,
            files=files or None,
            headers=_user_scopes_header(),
            timeout=60,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/admission-round-docs/<int:doc_id>", methods=["PATCH", "DELETE"])
def api_ops_admission_round_doc_one(doc_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "DELETE":
        return _api_proxy("delete", f"/ops/admission-round-docs/{doc_id}")
    return _api_proxy(
        "patch",
        f"/ops/admission-round-docs/{doc_id}",
        json_body=request.get_json(silent=True) or {},
    )


@app.route("/api/ops/admission-round-docs/<int:doc_id>/file", methods=["GET"])
def api_ops_admission_round_doc_file(doc_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    inline = (request.args.get("inline") or "") in ("1", "true", "yes")
    try:
        resp = requests.get(
            f"{API_BASE}/ops/admission-round-docs/{doc_id}/file",
            params={"inline": "1" if inline else "0"},
            headers=_user_scopes_header(),
            timeout=60,
            stream=True,
        )
        from flask import Response

        headers = {}
        if resp.headers.get("Content-Disposition"):
            headers["Content-Disposition"] = resp.headers["Content-Disposition"]
        if resp.headers.get("Content-Type"):
            headers["Content-Type"] = resp.headers["Content-Type"]
        return Response(resp.iter_content(chunk_size=8192), status=resp.status_code, headers=headers)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/applications/<int:app_id>/docs", methods=["GET", "POST"])
def api_ops_application_docs(app_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        if not _can_access_app_docs():
            return jsonify({"error": "Forbidden"}), 403
        return _api_proxy("get", f"/ops/applications/{app_id}/docs")
    if not _can_access_app_docs(manage=True):
        return jsonify({"error": "Forbidden"}), 403
    f = request.files.get("file")
    files = None
    if f and f.filename:
        files = {"file": (f.filename, f.stream, f.mimetype)}
    data = {
        "doc_type": request.form.get("doc_type") or "",
        "title": request.form.get("title") or "",
        "notes": request.form.get("notes") or "",
    }
    try:
        resp = requests.post(
            f"{API_BASE}/ops/applications/{app_id}/docs",
            data=data,
            files=files or None,
            headers=_user_scopes_header(),
            timeout=60,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/application-docs/<int:doc_id>", methods=["DELETE"])
def api_ops_application_doc_delete(doc_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _can_access_app_docs(manage=True):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("delete", f"/ops/application-docs/{doc_id}")


@app.route("/api/ops/application-docs/<int:doc_id>/file", methods=["GET"])
def api_ops_application_doc_file(doc_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _can_access_app_docs():
        return jsonify({"error": "Forbidden"}), 403
    inline = request.args.get("inline", "")
    params = {"inline": inline} if inline else None
    return _stream_ops_file(f"/ops/application-docs/{doc_id}/file", params)


@app.route("/api/ops/applications/<int:app_id>/register-exam", methods=["POST"])
@app.route("/api/ops/applications/<int:app_id>/confirm-examinee", methods=["POST"])
@app.route("/api/ops/applications/<int:app_id>/exam-fee", methods=["POST"])
@app.route("/api/ops/applications/<int:app_id>/exam-board", methods=["POST"])
def api_ops_application_exam_step(app_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    tail = request.path.rstrip("/").split("/")[-1]
    return _api_proxy(
        "post",
        f"/ops/applications/{app_id}/{tail}",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/applications/<int:app_id>/status", methods=["POST"])
def api_ops_application_status(app_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    payload = dict(request.get_json(silent=True) or {})
    payload["departments"] = _dept_codes()
    try:
        resp = requests.post(
            f"{API_BASE}/ops/applications/{app_id}/status",
            json=payload,
            headers=_user_scopes_header(),
            timeout=8,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/interview-slots/<int:slot_id>/scores", methods=["POST"])
def api_ops_interview_scores(slot_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("admissions.interviews")
        or _user_has_perm("admissions.applications")
    ):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/interview-slots/{slot_id}/scores",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/classes/<int:class_id>/grades", methods=["POST"])
def api_ops_class_grades(class_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.grades"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/classes/{class_id}/grades",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/classes/<int:class_id>/grade-scheme", methods=["POST"])
def api_ops_class_grade_scheme(class_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.grades"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/classes/{class_id}/grade-scheme",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/teaching-schedule/import", methods=["POST"])
def api_ops_teaching_schedule_import():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.schedule"):
        return jsonify({"error": "Forbidden"}), 403
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Chọn file Excel"}), 400
    try:
        resp = requests.post(
            f"{API_BASE}/ops/teaching-schedule/import",
            files={"file": (f.filename, f.stream, f.mimetype)},
            headers=_user_scopes_header(),
            timeout=60,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/classes/<int:class_id>/welcome-email", methods=["POST"])
def api_ops_class_welcome(class_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("classes.manage"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/classes/{class_id}/welcome-email",
            json={},
            headers=_user_scopes_header(),
            timeout=20,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/classes/<int:class_id>/grades/lock", methods=["POST"])
def api_ops_class_grades_lock(class_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.grades"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/classes/{class_id}/grades/lock",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/thesis-records/<int:thesis_id>", methods=["PATCH"])
def api_ops_thesis_patch(thesis_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.thesis"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.patch(
            f"{API_BASE}/ops/thesis-records/{thesis_id}",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


def _api_proxy(method, path, json_body=None, timeout=20, params=None):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        fn = getattr(requests, method.lower())
        kwargs = {"headers": _user_scopes_header(), "timeout": timeout}
        if json_body is not None:
            kwargs["json"] = json_body
        if params is not None:
            kwargs["params"] = params
        resp = fn(f"{API_BASE}{path}", **kwargs)
        ctype = resp.headers.get("Content-Type", "")
        if ctype.startswith("text/csv") or "spreadsheetml" in ctype or "octet-stream" in ctype:
            from flask import Response
            return Response(
                resp.content,
                status=resp.status_code,
                mimetype=ctype or "application/octet-stream",
                headers={
                    "Content-Disposition": resp.headers.get(
                        "Content-Disposition", "attachment; filename=export.bin"
                    )
                },
            )
        try:
            return jsonify(resp.json()), resp.status_code
        except Exception:
            return resp.content, resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/elearn/<path:rest>", methods=["GET", "POST", "PATCH", "DELETE"])
def api_ops_elearn(rest):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    path = "/ops/elearn/" + rest
    if request.method == "GET":
        return _api_proxy("get", path, params=request.args)
    if rest.endswith("/selfie") and request.method == "POST":
        files = {}
        if "file" in request.files:
            f = request.files["file"]
            files["file"] = (f.filename, f.stream, f.mimetype)
        try:
            resp = requests.post(
                f"{API_BASE}{path}",
                files=files or None,
                data={k: v for k, v in request.form.items()},
                headers=_user_scopes_header(),
                timeout=60,
            )
            return jsonify(resp.json()), resp.status_code
        except requests.RequestException as e:
            return jsonify({"error": str(e)}), 503
    if request.method == "POST":
        return _api_proxy("post", path, request.get_json(silent=True) or {})
    if request.method == "PATCH":
        return _api_proxy("patch", path, request.get_json(silent=True) or {})
    return _api_proxy("delete", path)


@app.route("/api/ops/admission-rounds", methods=["GET", "POST"])
def api_ops_rounds_create():
    if request.method == "GET":
        return _api_proxy("get", "/ops/admission-rounds", params=request.args)
    return _api_proxy("post", "/ops/admission-rounds", request.get_json(silent=True) or {})


@app.route("/api/ops/applications", methods=["GET", "POST"])
def api_ops_applications():
    if request.method == "GET":
        return _api_proxy("get", "/ops/applications", params=request.args)
    return _api_proxy("post", "/ops/applications", request.get_json(silent=True) or {})


@app.route("/api/ops/program-versions", methods=["GET", "POST"])
def api_ops_program_versions():
    if request.method == "GET":
        return _api_proxy("get", "/ops/program-versions", params=request.args)
    return _api_proxy("post", "/ops/program-versions", request.get_json(silent=True) or {})


@app.route("/api/ops/courses", methods=["GET", "POST"])
def api_ops_courses():
    if request.method == "GET":
        return _api_proxy("get", "/ops/courses", params=request.args)
    return _api_proxy("post", "/ops/courses", request.get_json(silent=True) or {})


@app.route("/api/ops/teaching-assignments", methods=["GET", "POST"])
def api_ops_teaching_assignments():
    if request.method == "GET":
        return _api_proxy("get", "/ops/teaching-assignments", params=request.args)
    return _api_proxy("post", "/ops/teaching-assignments", request.get_json(silent=True) or {})


@app.route("/api/ops/attendance-sessions", methods=["POST"])
def api_ops_attendance_sessions():
    return _api_proxy("post", "/ops/attendance-sessions", request.get_json(silent=True) or {})


@app.route("/api/ops/thesis-records", methods=["GET", "POST"])
def api_ops_thesis_records():
    if request.method == "GET":
        return _api_proxy("get", "/ops/thesis-records", params=request.args)
    return _api_proxy("post", "/ops/thesis-records", request.get_json(silent=True) or {})


@app.route("/api/ops/classes", methods=["GET", "POST"])
def api_ops_classes():
    if request.method == "GET":
        return _api_proxy("get", "/ops/classes")
    return _api_proxy("post", "/ops/classes", request.get_json(silent=True) or {})


@app.route("/api/ops/official/convert-bulk", methods=["POST"])
def api_ops_official_convert_bulk():
    return _api_proxy("post", "/ops/official/convert-bulk", request.get_json(silent=True) or {})


@app.route("/api/ops/faculty", methods=["POST"])
def api_ops_faculty_create():
    return _api_proxy("post", "/ops/faculty", request.get_json(silent=True) or {})


@app.route("/api/ops/faculty/<int:faculty_id>", methods=["PATCH"])
def api_ops_faculty_patch(faculty_id):
    return _api_proxy("patch", f"/ops/faculty/{faculty_id}", request.get_json(silent=True) or {})


@app.route("/api/ops/alumni", methods=["GET", "POST"])
def api_ops_alumni():
    if request.method == "GET":
        return _api_proxy("get", "/ops/alumni", params=request.args)
    return _api_proxy("post", "/ops/alumni", request.get_json(silent=True) or {})


@app.route("/api/ops/alumni-events", methods=["POST"])
def api_ops_alumni_events_create():
    return _api_proxy("post", "/ops/alumni-events", request.get_json(silent=True) or {})


@app.route("/api/ops/alumni-events/<int:event_id>/invitees", methods=["GET", "POST"])
def api_ops_alumni_event_invitees(event_id):
    if request.method == "GET":
        return _api_proxy("get", f"/ops/alumni-events/{event_id}/invitees")
    return _api_proxy(
        "post",
        f"/ops/alumni-events/{event_id}/invitees",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/alumni-events/<int:event_id>/send-invites", methods=["POST"])
def api_ops_alumni_event_send_invites(event_id):
    return _api_proxy("post", f"/ops/alumni-events/{event_id}/send-invites", {})


@app.route("/api/ops/study-groups", methods=["POST"])
def api_ops_study_groups_create():
    return _api_proxy("post", "/ops/study-groups", request.get_json(silent=True) or {})


@app.route("/api/ops/exams-schedule", methods=["POST"])
def api_ops_exams_create():
    return _api_proxy("post", "/ops/exams-schedule", request.get_json(silent=True) or {})


@app.route("/api/ops/evaluations", methods=["POST"])
def api_ops_evaluations_create():
    return _api_proxy("post", "/ops/evaluations", request.get_json(silent=True) or {})


@app.route("/api/ops/email-templates", methods=["GET", "POST"])
def api_ops_email_templates():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (_user_has_perm("admissions.results") or _user_has_perm("admissions.mail")):
        return jsonify({"error": "Forbidden"}), 403
    try:
        if request.method == "GET":
            resp = requests.get(
                f"{API_BASE}/ops/email-templates",
                params=request.args,
                headers=_user_scopes_header(),
                timeout=15,
            )
        else:
            resp = requests.post(
                f"{API_BASE}/ops/email-templates",
                json=request.get_json(silent=True) or {},
                headers=_user_scopes_header(),
                timeout=15,
            )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/email-templates/send", methods=["POST"])
def api_ops_email_templates_send():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (_user_has_perm("admissions.mail") or _user_has_perm("admissions.results")):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("post", "/ops/email-templates/send", request.get_json(silent=True) or {})


@app.route("/api/ops/students", methods=["GET"])
def api_ops_students_list():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("get", "/ops/students", params=request.args)


@app.route("/api/ops/students/assign-class", methods=["POST"])
def api_ops_students_assign_class():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("students.manage"):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("post", "/ops/students/assign-class", request.get_json(silent=True) or {})


@app.route("/api/ops/scholarship-basis", methods=["GET", "POST"])
def api_ops_scholarship_basis():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "GET":
        return _api_proxy("get", "/ops/scholarship-basis", params=request.args)
    return _api_proxy("post", "/ops/scholarship-basis", request.get_json(silent=True) or {})


@app.route("/api/ops/teaching-assignments/<int:assignment_id>/stamp-sessions", methods=["POST"])
def api_ops_stamp_sessions(assignment_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.assign"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/teaching-assignments/{assignment_id}/stamp-sessions",
            json={},
            headers=_user_scopes_header(),
            timeout=20,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/alumni/<int:alumni_id>/portal-account", methods=["POST"])
def api_ops_alumni_portal_account(alumni_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("alumni.members"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/alumni/{alumni_id}/portal-account",
            json={},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/alumni/me", methods=["GET", "PATCH"])
def api_ops_alumni_me():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("alumni.portal"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        if request.method == "GET":
            resp = requests.get(
                f"{API_BASE}/ops/alumni/me",
                headers=_user_scopes_header(),
                timeout=15,
            )
        else:
            resp = requests.patch(
                f"{API_BASE}/ops/alumni/me",
                json=request.get_json(silent=True) or {},
                headers=_user_scopes_header(),
                timeout=15,
            )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/actions/notify-results", methods=["POST"])
def api_ops_notify_results():
    return _api_proxy("post", "/ops/actions/notify-results", {})


@app.route("/api/ops/actions/notify-missing-docs", methods=["POST"])
def api_ops_notify_missing_docs():
    return _api_proxy("post", "/ops/actions/notify-missing-docs", {})


@app.route("/api/ops/actions/send-timeline", methods=["POST"])
def api_ops_send_timeline():
    return _api_proxy("post", "/ops/actions/send-timeline", {})


@app.route("/api/ops/actions/issue-checklists", methods=["POST"])
def api_ops_issue_checklists():
    return _api_proxy("post", "/ops/actions/issue-checklists", {})


@app.route("/api/ops/actions/notify-exam-schedule", methods=["POST"])
def api_ops_notify_exam_schedule():
    return _api_proxy("post", "/ops/actions/notify-exam-schedule", {})


@app.route("/api/ops/actions/notify-interview-invites", methods=["POST"])
def api_ops_notify_interview_invites():
    return _api_proxy("post", "/ops/actions/notify-interview-invites", {})


@app.route("/api/ops/actions/notify-admission-pack", methods=["POST"])
def api_ops_notify_admission_pack():
    return _api_proxy("post", "/ops/actions/notify-admission-pack", {})


@app.route("/api/ops/student/me", methods=["GET", "PATCH"])
def api_ops_student_me():
    if request.method == "PATCH":
        return _api_proxy("patch", "/ops/student/me", request.get_json(silent=True) or {})
    return _api_proxy("get", "/ops/student/me", params=request.args)


@app.route("/api/ops/student/me/charges", methods=["GET"])
def api_ops_student_me_charges():
    return _api_proxy("get", "/ops/student/me/charges", params=request.args)


@app.route("/api/ops/student/me/charges/<int:charge_id>/proof", methods=["POST"])
def api_ops_student_me_charge_proof(charge_id):
    return _api_proxy(
        "post",
        f"/ops/student/me/charges/{charge_id}/proof",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/export/<entity>", methods=["GET"])
def api_ops_export(entity):
    qs = request.query_string.decode() if request.query_string else ""
    path = f"/ops/export/{entity}" + (f"?{qs}" if qs else "")
    return _api_proxy("get", path)


@app.route("/api/ops/export-table", methods=["POST"])
def api_ops_export_table():
    return _api_proxy(
        "post",
        "/ops/export-table",
        request.get_json(silent=True) or {},
        timeout=60,
    )


@app.route("/api/ops/suggestions", methods=["GET", "POST"])
def api_ops_suggestions():
    u = session.get("user") or {}
    if not u:
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "POST":
        body = dict(request.get_json(silent=True) or {})
        body["user_id"] = u.get("id")
        # Support both em-dash and hyphen name suffixes: "Admin — ..." / "Name - ..."
        raw_name = (u.get("name") or "").strip()
        for sep in ("—", "–", " - ", " — "):
            if sep in raw_name:
                raw_name = raw_name.split(sep, 1)[0].strip()
                break
        body["user_name"] = raw_name or u.get("email") or "User"
        body["user_email"] = u.get("email")
        if not body.get("relative_path"):
            body["relative_path"] = "/"
        if not (body.get("function_code") or "").strip():
            return jsonify({"error": "Thiếu mã chức năng"}), 400
        return _api_proxy("post", "/ops/suggestions", body)
    # GET: mine=1 → only current user; otherwise admin list
    params = {k: v for k, v in request.args.items() if v}
    mine = params.pop("mine", None)
    if mine in ("1", "true", "yes"):
        params["user_id"] = u.get("id")
    elif not u.get("is_admin") and not _user_has_perm("admin.suggestions"):
        # Non-admin may only list own items
        params["user_id"] = u.get("id")
    try:
        resp = requests.get(
            f"{API_BASE}/ops/suggestions",
            params=params,
            headers=_user_scopes_header(),
            timeout=20,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/suggestions/<int:suggestion_id>", methods=["PATCH"])
def api_ops_suggestion_patch(suggestion_id):
    u = session.get("user") or {}
    if not u.get("is_admin") and not _user_has_perm("admin.suggestions"):
        return jsonify({"error": "Forbidden"}), 403
    body = dict(request.get_json(silent=True) or {})
    body["processed_by"] = (u.get("name") or "").split("—")[0].strip() or u.get("email")
    return _api_proxy("patch", f"/ops/suggestions/{suggestion_id}", body)


@app.route("/api/ops/suggestions/bulk-status", methods=["POST"])
def api_ops_suggestions_bulk_status():
    u = session.get("user") or {}
    if not u.get("is_admin") and not _user_has_perm("admin.suggestions"):
        return jsonify({"error": "Forbidden"}), 403
    body = dict(request.get_json(silent=True) or {})
    body["processed_by"] = (u.get("name") or "").split("—")[0].strip() or u.get("email")
    return _api_proxy("post", "/ops/suggestions/bulk-status", body)


@app.route("/api/ops/suggestions/export", methods=["GET"])
def api_ops_suggestions_export():
    u = session.get("user") or {}
    if not u.get("is_admin") and not _user_has_perm("admin.suggestions"):
        return jsonify({"error": "Forbidden"}), 403
    params = {k: v for k, v in request.args.items() if v}
    try:
        resp = requests.get(
            f"{API_BASE}/ops/suggestions/export",
            params=params,
            headers=_user_scopes_header(),
            timeout=30,
        )
        from flask import Response

        return Response(
            resp.content,
            status=resp.status_code,
            mimetype=resp.headers.get(
                "Content-Type",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            headers={
                "Content-Disposition": resp.headers.get(
                    "Content-Disposition",
                    "attachment; filename=de_xuat_gop_y.xlsx",
                )
            },
        )
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/applications/import/template", methods=["GET"])
def api_ops_applications_import_template():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("admissions.applications")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    # Prefer generic bulk-import template (includes Ket_qua_import column)
    return _api_proxy("get", "/ops/bulk-import/applications/template")


@app.route("/api/ops/applications/import", methods=["POST"])
def api_ops_applications_import():
    """Legacy JSON import kept; file uploads go through bulk-import for annotated xlsx."""
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("admissions.applications")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    try:
        if request.files.get("file"):
            files = {
                "file": (
                    request.files["file"].filename,
                    request.files["file"].stream,
                    request.files["file"].mimetype
                    or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            }
            data = {}
            if request.form.get("round_id"):
                data["round_id"] = request.form.get("round_id")
            resp = requests.post(
                f"{API_BASE}/ops/bulk-import/applications",
                files=files,
                data=data,
                headers=_user_scopes_header(),
                timeout=120,
            )
            # Pass through annotated workbook
            from flask import Response as FlaskResponse

            excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
            headers = {
                k: v
                for k, v in resp.headers.items()
                if k.lower() not in excluded
            }
            return FlaskResponse(resp.content, status=resp.status_code, headers=headers)
        resp = requests.post(
            f"{API_BASE}/ops/applications/import",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=60,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/bulk-import/<entity>/template", methods=["GET"])
def api_ops_bulk_import_template(entity):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if _is_exec_viewer():
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("get", f"/ops/bulk-import/{entity}/template")


@app.route("/api/ops/bulk-import/<entity>", methods=["POST"])
def api_ops_bulk_import(entity):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if _is_exec_viewer():
        return jsonify({"error": "Forbidden"}), 403
    if not request.files.get("file"):
        return jsonify({"error": "Thiếu file Excel (.xlsx)"}), 400
    try:
        files = {
            "file": (
                request.files["file"].filename,
                request.files["file"].stream,
                request.files["file"].mimetype
                or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        data = {}
        if request.form.get("round_id"):
            data["round_id"] = request.form.get("round_id")
        resp = requests.post(
            f"{API_BASE}/ops/bulk-import/{entity}",
            files=files,
            data=data,
            headers=_user_scopes_header(),
            timeout=120,
        )
        from flask import Response as FlaskResponse

        excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}
        return FlaskResponse(resp.content, status=resp.status_code, headers=headers)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/bulk-delete", methods=["POST"])
def api_ops_bulk_delete():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if _is_exec_viewer():
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("post", "/ops/bulk-delete", request.get_json(silent=True) or {})


@app.route("/api/ops/mba/written-exam/assign-numbers", methods=["POST"])
def api_ops_mba_assign_exam_numbers():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("admissions.applications")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("post", "/ops/mba/written-exam/assign-numbers", request.get_json(silent=True) or {})


@app.route("/api/ops/mba/scores/import", methods=["POST"])
def api_ops_mba_scores_import():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("admissions.applications")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    try:
        if request.files.get("file"):
            files = {
                "file": (
                    request.files["file"].filename,
                    request.files["file"].stream,
                    request.files["file"].mimetype
                    or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            }
            data = {"program_code": request.form.get("program_code") or "MBA"}
            resp = requests.post(
                f"{API_BASE}/ops/mba/scores/import",
                files=files,
                data=data,
                headers=_user_scopes_header(),
                timeout=60,
            )
        else:
            resp = requests.post(
                f"{API_BASE}/ops/mba/scores/import",
                json=request.get_json(silent=True) or {},
                headers=_user_scopes_header(),
                timeout=60,
            )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/mba/interview-boards", methods=["POST"])
def api_ops_mba_interview_boards():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("admissions.interviews")
        or _user_has_perm("admissions.applications")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("post", "/ops/mba/interview-boards", request.get_json(silent=True) or {})


@app.route("/api/ops/mba/attendance/notify-ineligible", methods=["POST"])
def api_ops_mba_notify_ineligible():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("teaching.attendance")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy(
        "post",
        "/ops/mba/attendance/notify-ineligible",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/program-versions/<int:version_id>/copy", methods=["POST"])
def api_ops_program_version_copy(version_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("programs.structure")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy(
        "post",
        f"/ops/program-versions/{version_id}/copy",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/program-versions/<int:version_id>/transfer-courses", methods=["POST"])
def api_ops_program_version_transfer_courses(version_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("programs.structure")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy(
        "post",
        f"/ops/program-versions/{version_id}/transfer-courses",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/evaluations/<int:eval_id>/send", methods=["POST"])
def api_ops_evaluation_send(eval_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("teaching.evaluation")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy(
        "post",
        f"/ops/evaluations/{eval_id}/send",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/evaluations/<int:eval_id>/close", methods=["POST"])
def api_ops_evaluation_close(eval_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("teaching.evaluation")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("post", f"/ops/evaluations/{eval_id}/close", {})


@app.route("/api/ops/class-students/<int:student_id>", methods=["PATCH"])
def api_ops_class_student_patch(student_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("classes.manage")
        or _user_has_perm("teaching.grades")
        or _user_has_perm("students.manage")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy(
        "patch",
        f"/ops/class-students/{student_id}",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/asst/<entity>", methods=["POST"])
def api_ops_asst_create(entity):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", f"/ops/asst/{entity}", request.get_json(silent=True) or {})


@app.route("/api/ops/asst/calendar/notify-changes", methods=["POST"])
def api_ops_asst_calendar_notify():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", "/ops/asst/calendar/notify-changes", request.get_json(silent=True) or {})


@app.route("/api/ops/asst/<path:entity>/<int:row_id>", methods=["PATCH", "DELETE"])
def api_ops_asst_row(entity, row_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "PATCH":
        return _api_proxy("patch", f"/ops/asst/{entity}/{row_id}", request.get_json(silent=True) or {})
    return _api_proxy("delete", f"/ops/asst/{entity}/{row_id}")


@app.route("/api/ops/rows/<path:table>/<int:row_id>", methods=["PATCH", "DELETE"])
def api_ops_rows_row(table, row_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "PATCH":
        return _api_proxy("patch", f"/ops/rows/{table}/{row_id}", request.get_json(silent=True) or {})
    return _api_proxy("delete", f"/ops/rows/{table}/{row_id}")


@app.route("/api/ops/asst/weekly-reports/<int:row_id>/submit", methods=["POST"])
def api_ops_asst_weekly_submit(row_id):
    return _api_proxy("post", f"/ops/asst/weekly-reports/{row_id}/submit", {})


@app.route("/api/ops/marcom/<entity>", methods=["POST"])
def api_ops_marcom_create(entity):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", f"/ops/marcom/{entity}", request.get_json(silent=True) or {})


@app.route("/api/ops/marcom/<path:entity>/<int:row_id>", methods=["PATCH", "DELETE"])
def api_ops_marcom_row(entity, row_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if request.method == "PATCH":
        return _api_proxy("patch", f"/ops/marcom/{entity}/{row_id}", request.get_json(silent=True) or {})
    return _api_proxy("delete", f"/ops/marcom/{entity}/{row_id}")


@app.route("/api/ops/marcom/leads/<int:lead_id>/accept", methods=["POST"])
def api_ops_marcom_accept_lead(lead_id):
    return _api_proxy("post", f"/ops/marcom/leads/{lead_id}/accept", request.get_json(silent=True) or {})


@app.route("/api/ops/marcom/<entity>/<int:row_id>/budget-decision", methods=["POST"])
def api_ops_marcom_budget_decision(entity, row_id):
    return _api_proxy(
        "post",
        f"/ops/marcom/{entity}/{row_id}/budget-decision",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/marcom/costs/confirm", methods=["POST"])
def api_ops_marcom_confirm_cost():
    return _api_proxy("post", "/ops/marcom/costs/confirm", request.get_json(silent=True) or {})


@app.route("/api/ops/marcom/campaigns/<int:campaign_id>/activities", methods=["POST"])
def api_ops_marcom_campaign_activity(campaign_id):
    return _api_proxy(
        "post",
        f"/ops/marcom/campaigns/{campaign_id}/activities",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/marcom/assets/<int:asset_id>/publications", methods=["POST"])
def api_ops_marcom_publication(asset_id):
    return _api_proxy(
        "post",
        f"/ops/marcom/assets/{asset_id}/publications",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/marcom/reports", methods=["GET"])
def api_ops_marcom_reports():
    qs = request.query_string.decode()
    path = "/ops/marcom/reports" + (f"?{qs}" if qs else "")
    return _api_proxy("get", path)


@app.route("/api/ops/marcom/leads/<int:lead_id>/hand-to-ts", methods=["POST"])
def api_ops_marcom_hand_lead(lead_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy(
        "post",
        f"/ops/marcom/leads/{lead_id}/hand-to-ts",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/crm/<path:subpath>", methods=["GET", "POST", "PATCH", "DELETE"])
def api_ops_crm(subpath):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    qs = request.query_string.decode() if request.query_string else ""
    path = "/ops/crm/" + subpath + (f"?{qs}" if qs else "")
    if request.method == "GET":
        return _api_proxy("get", path)
    body = request.get_json(silent=True) or {}
    return _api_proxy(request.method.lower(), "/ops/crm/" + subpath, body)


@app.route("/api/ops/marcom/events/<int:event_id>", methods=["GET", "PATCH"])
def api_ops_marcom_event_detail(event_id):
    if request.method == "GET":
        return _api_proxy("get", f"/ops/marcom/events/{event_id}")
    return _api_proxy(
        "patch",
        f"/ops/marcom/events/{event_id}",
        request.get_json(silent=True) or {},
    )


@app.route(
    "/api/ops/marcom/events/<int:event_id>/registrants",
    methods=["GET", "POST"],
)
def api_ops_marcom_event_registrants(event_id):
    if request.method == "GET":
        qs = request.query_string.decode() if request.query_string else ""
        path = f"/ops/marcom/events/{event_id}/registrants" + (f"?{qs}" if qs else "")
        return _api_proxy("get", path)
    return _api_proxy(
        "post",
        f"/ops/marcom/events/{event_id}/registrants",
        request.get_json(silent=True) or {},
    )


@app.route(
    "/api/ops/marcom/events/<int:event_id>/registrants/<int:reg_id>",
    methods=["PATCH"],
)
def api_ops_marcom_event_registrant_patch(event_id, reg_id):
    return _api_proxy(
        "patch",
        f"/ops/marcom/events/{event_id}/registrants/{reg_id}",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/marcom/events/registrants/<int:reg_id>/check-in", methods=["POST"])
def api_ops_marcom_check_in(reg_id):
    return _api_proxy("post", f"/ops/marcom/events/registrants/{reg_id}/check-in", {})


@app.route("/api/ops/marcom/events/registrants/<int:reg_id>/to-lead", methods=["POST"])
def api_ops_marcom_registrant_to_lead(reg_id):
    return _api_proxy(
        "post",
        f"/ops/marcom/events/registrants/{reg_id}/to-lead",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/marcom/events/registrants/<int:reg_id>/hand-to-ts", methods=["POST"])
def api_ops_marcom_registrant_hand_to_ts(reg_id):
    return _api_proxy(
        "post",
        f"/ops/marcom/events/registrants/{reg_id}/hand-to-ts",
        request.get_json(silent=True) or {},
    )


@app.route("/api/ops/marcom/events/<int:event_id>/sync-alumni", methods=["POST"])
def api_ops_marcom_sync_alumni(event_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", f"/ops/marcom/events/{event_id}/sync-alumni", {})


@app.route("/api/ops/fees/<int:fee_id>/mark-official", methods=["POST"])
def api_ops_fee_mark_official(fee_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    return _api_proxy("post", f"/ops/fees/{fee_id}/mark-official", request.get_json(silent=True) or {})


@app.route("/api/ops/classes/<int:class_id>/enroll-official", methods=["POST"])
def api_ops_class_enroll_official(class_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("classes.manage")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    return _api_proxy("post", f"/ops/classes/{class_id}/enroll-official", {})


@app.route("/api/ops/fees/<int:fee_id>/mark-paid", methods=["POST"])
def api_ops_fee_mark_paid(fee_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    payload = dict(request.get_json(silent=True) or {})
    payload["departments"] = _dept_codes()
    try:
        resp = requests.post(
            f"{API_BASE}/ops/fees/{fee_id}/mark-paid",
            json=payload,
            headers=_user_scopes_header(),
            timeout=8,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/asst/leave/<int:leave_id>/status", methods=["POST"])
def api_ops_asst_leave_status(leave_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("asst.leave"):
        return jsonify({"error": "Forbidden"}), 403
    payload = dict(request.get_json(silent=True) or {})
    try:
        resp = requests.post(
            f"{API_BASE}/ops/asst/leave/{leave_id}/status",
            json=payload,
            headers=_user_scopes_header(),
            timeout=8,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/courses/<int:course_id>", methods=["PATCH"])
def api_ops_course_update(course_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("programs.courses"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.patch(
            f"{API_BASE}/ops/courses/{course_id}",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/course-sessions/<int:session_id>", methods=["PATCH"])
def api_ops_course_session_update(session_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("programs.courses"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.patch(
            f"{API_BASE}/ops/course-sessions/{session_id}",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/courses/<int:course_id>/sessions/reorder", methods=["POST"])
def api_ops_course_sessions_reorder(course_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("programs.courses")
        or (session.get("user") or {}).get("is_admin")
    ):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/courses/{course_id}/sessions/reorder",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/materials/upload", methods=["POST"])
def api_ops_materials_upload():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (_user_has_perm("teaching.materials") or _user_has_perm("programs.courses")):
        return jsonify({"error": "Forbidden"}), 403
    u = session.get("user") or {}
    files = {}
    if "file" in request.files:
        f = request.files["file"]
        files["file"] = (f.filename, f.stream, f.mimetype)
    data = {k: v for k, v in request.form.items()}
    data["uploaded_by"] = u.get("email") or u.get("name") or ""
    try:
        resp = requests.post(
            f"{API_BASE}/ops/materials/upload",
            data=data,
            files=files or None,
            headers=_user_scopes_header(),
            timeout=60,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/materials/<int:material_id>/release", methods=["POST"])
def api_ops_materials_release(material_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.materials"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/materials/{material_id}/release",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/materials/<int:material_id>/file", methods=["GET"])
def api_ops_materials_file(material_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    as_student = request.args.get("as_student", "")
    inline = request.args.get("inline", "")
    # Students need library or materials; staff need materials/courses
    if as_student in ("1", "true", "yes"):
        if not (
            _user_has_perm("student.library")
            or _user_has_perm("student.lessons")
            or _user_has_perm("teaching.materials")
            or _user_has_perm("programs.courses")
        ):
            return jsonify({"error": "Forbidden"}), 403
    elif not (
        _user_has_perm("teaching.materials")
        or _user_has_perm("programs.courses")
        or _user_has_perm("student.library")
        or _user_has_perm("teaching.lessons")
    ):
        return jsonify({"error": "Forbidden"}), 403
    try:
        params = {}
        if as_student:
            params["as_student"] = as_student
        if inline:
            params["inline"] = inline
        resp = requests.get(
            f"{API_BASE}/ops/materials/{material_id}/file",
            params=params or None,
            headers=_user_scopes_header(),
            timeout=60,
            stream=True,
        )
        if resp.status_code != 200:
            try:
                return jsonify(resp.json()), resp.status_code
            except Exception:
                return jsonify({"error": "Download failed"}), resp.status_code
        from flask import Response

        headers = {}
        if resp.headers.get("Content-Disposition"):
            headers["Content-Disposition"] = resp.headers["Content-Disposition"]
        if resp.headers.get("Content-Type"):
            headers["Content-Type"] = resp.headers["Content-Type"]
        return Response(resp.iter_content(chunk_size=8192), headers=headers)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/ops/materials/<int:material_id>/preview")
def ops_material_preview(material_id):
    """In-browser preview for PDF / images / office files."""
    if not session.get("user"):
        return redirect(url_for("login", next=request.url))
    as_student = request.args.get("as_student", "")
    lesson_id = request.args.get("lesson_id", type=int)
    try:
        params = {"as_student": as_student} if as_student else None
        resp = requests.get(
            f"{API_BASE}/ops/materials/{material_id}/preview",
            params=params,
            headers=_user_scopes_header(),
            timeout=60,
        )
        if resp.status_code != 200:
            flash((resp.json() or {}).get("error") or "Không xem trước được.")
            return redirect(request.referrer or url_for("ops_home"))
        data = resp.json()
    except Exception as e:
        flash(str(e))
        return redirect(request.referrer or url_for("ops_home"))
    file_qs = "inline=1"
    if as_student in ("1", "true", "yes"):
        file_qs += "&as_student=1"
    track_views = as_student in ("1", "true", "yes") or _user_has_perm("student.lessons")
    lid = lesson_id or data.get("lesson_id")
    return render_template(
        "ops/material_preview.html",
        preview=data,
        material_id=material_id,
        lesson_id=lid,
        track_views=bool(track_views and lid),
        file_url=f"/api/ops/materials/{material_id}/file?{file_qs}",
        download_url=f"/api/ops/materials/{material_id}/file"
        + ("?as_student=1" if as_student else ""),
        as_student=as_student,
    )


def _actor_name():
    u = session.get("user") or {}
    return (u.get("name") or "").split("—")[0].strip() or u.get("email") or "User"


# —— Practice homework API proxies ——

@app.route("/api/ops/practice/template.xlsx", methods=["GET"])
def api_ops_practice_template():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.assignments"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.get(
            f"{API_BASE}/ops/practice/template.xlsx",
            headers=_user_scopes_header(),
            timeout=30,
        )
        excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        headers = {
            k: v for k, v in resp.headers.items() if k.lower() not in excluded
        }
        return Response(resp.content, status=resp.status_code, headers=headers)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route(
    "/api/ops/practice/teaching-assignments/<int:ta_id>/homeworks/import",
    methods=["POST"],
)
def api_ops_practice_import(ta_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.assignments"):
        return jsonify({"error": "Forbidden"}), 403
    files = {}
    if "file" in request.files:
        f = request.files["file"]
        files["file"] = (f.filename, f.stream, f.mimetype or "application/octet-stream")
    data = {k: v for k, v in request.form.items()}
    try:
        resp = requests.post(
            f"{API_BASE}/ops/practice/teaching-assignments/{ta_id}/homeworks/import",
            data=data,
            files=files or None,
            headers=_user_scopes_header(),
            timeout=120,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/practice/homeworks/<int:hw_id>/status", methods=["POST"])
def api_ops_practice_status(hw_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.assignments"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/practice/homeworks/{hw_id}/status",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/practice/submissions/<int:sub_id>/answers", methods=["POST"])
def api_ops_practice_answers(sub_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.assignments"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/practice/submissions/{sub_id}/answers",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=30,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/practice/submissions/<int:sub_id>/grade", methods=["POST"])
def api_ops_practice_grade(sub_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.assignments"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/practice/submissions/{sub_id}/grade",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/mc/template.xlsx", methods=["GET"])
def api_ops_mc_template():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.assignments"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.get(
            f"{API_BASE}/ops/mc/template.xlsx",
            headers=_user_scopes_header(),
            timeout=30,
        )
        excluded = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        headers = {
            k: v for k, v in resp.headers.items() if k.lower() not in excluded
        }
        return Response(resp.content, status=resp.status_code, headers=headers)
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route(
    "/api/ops/mc/teaching-assignments/<int:ta_id>/quizzes/import",
    methods=["POST"],
)
def api_ops_mc_import(ta_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.assignments"):
        return jsonify({"error": "Forbidden"}), 403
    files = {}
    if "file" in request.files:
        f = request.files["file"]
        files["file"] = (f.filename, f.stream, f.mimetype or "application/octet-stream")
    data = {k: v for k, v in request.form.items()}
    try:
        resp = requests.post(
            f"{API_BASE}/ops/mc/teaching-assignments/{ta_id}/quizzes/import",
            data=data,
            files=files or None,
            headers=_user_scopes_header(),
            timeout=120,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/mc/quizzes/<int:quiz_id>/status", methods=["POST"])
def api_ops_mc_status(quiz_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.assignments"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/mc/quizzes/{quiz_id}/status",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/mc/submissions/<int:sub_id>/answers", methods=["POST"])
def api_ops_mc_answers(sub_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("teaching.assignments"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/mc/submissions/{sub_id}/answers",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=30,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/teaching-assignments/<int:assignment_id>/lessons/import", methods=["POST"])
def api_ops_lessons_import(assignment_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (_user_has_perm("teaching.lessons") or _user_has_perm("teaching.materials")):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/teaching-assignments/{assignment_id}/lessons/import",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=30,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/teaching-assignments/<int:assignment_id>/lessons", methods=["POST"])
def api_ops_lessons_create(assignment_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (_user_has_perm("teaching.lessons") or _user_has_perm("teaching.materials")):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/teaching-assignments/{assignment_id}/lessons",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/class-lessons/<int:lesson_id>", methods=["PATCH"])
def api_ops_lesson_update(lesson_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (_user_has_perm("teaching.lessons") or _user_has_perm("teaching.materials")):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.patch(
            f"{API_BASE}/ops/class-lessons/{lesson_id}",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/class-lessons/<int:lesson_id>/upload", methods=["POST"])
def api_ops_lesson_upload(lesson_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (_user_has_perm("teaching.lessons") or _user_has_perm("teaching.materials")):
        return jsonify({"error": "Forbidden"}), 403
    u = session.get("user") or {}
    files = {}
    if "file" in request.files:
        f = request.files["file"]
        files["file"] = (f.filename, f.stream, f.mimetype)
    data = {k: v for k, v in request.form.items()}
    data["uploaded_by"] = u.get("email") or u.get("name") or ""
    try:
        resp = requests.post(
            f"{API_BASE}/ops/class-lessons/{lesson_id}/upload",
            data=data,
            files=files or None,
            headers=_user_scopes_header(),
            timeout=60,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/class-lessons/<int:lesson_id>/comments", methods=["POST"])
def api_ops_lesson_comment(lesson_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("student.lessons")
        or _user_has_perm("teaching.lessons")
        or _user_has_perm("teaching.materials")
    ):
        return jsonify({"error": "Forbidden"}), 403
    payload = dict(request.get_json(silent=True) or {})
    u = session.get("user") or {}
    payload.setdefault("author_name", _actor_name())
    payload.setdefault(
        "author_email",
        u.get("student_email") or u.get("contact_email") or u.get("email") or "",
    )
    if _user_has_perm("teaching.lessons") or _user_has_perm("teaching.materials"):
        if payload.get("author_role") not in ("coordinator", "lecturer", "student"):
            payload["author_role"] = "coordinator"
    else:
        payload["author_role"] = "student"
    try:
        resp = requests.post(
            f"{API_BASE}/ops/class-lessons/{lesson_id}/comments",
            json=payload,
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/class-lessons/<int:lesson_id>/views/open", methods=["POST"])
def api_ops_lesson_view_open(lesson_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    payload = dict(request.get_json(silent=True) or {})
    u = session.get("user") or {}
    payload.setdefault("student_name", _actor_name())
    payload.setdefault(
        "student_email",
        u.get("student_email") or u.get("contact_email") or u.get("email") or "",
    )
    try:
        resp = requests.post(
            f"{API_BASE}/ops/class-lessons/{lesson_id}/views/open",
            json=payload,
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/lesson-views/<int:session_id>/heartbeat", methods=["POST"])
def api_ops_lesson_view_heartbeat(session_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(
            f"{API_BASE}/ops/lesson-views/{session_id}/heartbeat",
            json={},
            headers=_user_scopes_header(),
            timeout=10,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/lesson-views/<int:session_id>/close", methods=["POST"])
def api_ops_lesson_view_close(session_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.post(
            f"{API_BASE}/ops/lesson-views/{session_id}/close",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=10,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/attendance/sessions/<int:session_id>/rounds", methods=["POST"])
def api_ops_attendance_rounds(session_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("teaching.attendance") or _user_has_perm("teaching.lessons")
    ):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/attendance/sessions/{session_id}/rounds",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/attendance/sessions/<int:session_id>/marks", methods=["PUT"])
def api_ops_attendance_marks(session_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("teaching.attendance") or _user_has_perm("teaching.lessons")
    ):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.put(
            f"{API_BASE}/ops/attendance/sessions/{session_id}/marks",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=30,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/attendance/sessions/<int:session_id>/qr/rotate", methods=["POST"])
def api_ops_attendance_qr_rotate(session_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("teaching.attendance") or _user_has_perm("teaching.lessons")
    ):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/attendance/sessions/{session_id}/qr/rotate",
            json=request.get_json(silent=True) or {},
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json() if resp.content else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


def _canvas_actor_payload():
    u = session.get("user") or {}
    payload = dict(request.get_json(silent=True) or {})
    payload["actor"] = u.get("email") or u.get("name") or ""
    return payload


@app.route("/api/ops/canvas/export/roster", methods=["POST"])
def api_ops_canvas_export_roster():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (
        _user_has_perm("canvas.accounting")
        or _user_has_perm("canvas.coordinator")
        or _user_has_perm("accounting.official_list")
    ):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/canvas/export/roster",
            json=_canvas_actor_payload(),
            headers=_user_scopes_header(),
            timeout=30,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/canvas/export/class/<int:class_id>", methods=["POST"])
def api_ops_canvas_export_class(class_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not (_user_has_perm("canvas.coordinator") or _user_has_perm("classes.manage")):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/canvas/export/class/{class_id}",
            json=_canvas_actor_payload(),
            headers=_user_scopes_header(),
            timeout=30,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/canvas/exports/<int:export_id>", methods=["GET"])
def api_ops_canvas_export_detail(export_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(
            f"{API_BASE}/ops/canvas/exports/{export_id}",
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/ops/canvas/exports/<int:export_id>/mark-pushed", methods=["POST"])
def api_ops_canvas_mark_pushed(export_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    if not _user_has_perm("canvas.it"):
        return jsonify({"error": "Forbidden"}), 403
    try:
        resp = requests.post(
            f"{API_BASE}/ops/canvas/exports/{export_id}/mark-pushed",
            json=_canvas_actor_payload(),
            headers=_user_scopes_header(),
            timeout=15,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/admin/book-categories")
def admin_book_categories():
    """Admin: manage book categories."""
    user = session.get("user") or {}
    if not user.get("is_admin") and not _user_has_perm("admin.status_catalog"):
        flash("Cần quyền quản trị danh mục.")
        return redirect(url_for("ops_home"))
    book_categories = []
    try:
        cat_resp = requests.get(f"{API_BASE}/admin/book-categories", timeout=5)
        if cat_resp.status_code == 200:
            book_categories = cat_resp.json()
    except Exception:
        pass
    return render_template("admin/book_categories.html", book_categories=book_categories)


@app.route("/admin/status-catalog")
def admin_status_catalog():
    """Admin: configure status values by category."""
    user = session.get("user") or {}
    if not user.get("is_admin") and not _user_has_perm("admin.status_catalog"):
        flash("Cần quyền quản trị danh mục trạng thái.")
        return redirect(url_for("ops_home"))
    items = []
    categories = []
    try:
        resp = requests.get(
            f"{API_BASE}/admin/status-catalog",
            params={"lang": _ui_lang()},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json() or {}
            items = data.get("items") or []
            categories = data.get("categories") or []
    except Exception:
        pass
    if not categories:
        categories = [
            {"code": "application_status", "label": "Trạng thái hồ sơ" if _ui_lang() != "en" else "Application status"},
            {"code": "final_result", "label": "Kết quả cuối" if _ui_lang() != "en" else "Final result"},
            {"code": "lifecycle_status", "label": "Trạng thái học tập HV" if _ui_lang() != "en" else "Student lifecycle"},
            {"code": "fee_status", "label": "Trạng thái phí" if _ui_lang() != "en" else "Fee status"},
            {"code": "leave_type", "label": "Loại nghỉ phép" if _ui_lang() != "en" else "Leave type"},
        ]
    return render_template(
        "admin/status_catalog.html",
        items=items,
        categories=categories,
    )


@app.route("/admin/upload", methods=["GET", "POST"])
def admin_upload():
    """Admin: upload PDF form and handler."""
    _debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    if request.method == "POST":
        import time as _time
        t0 = _time.time()
        title = (request.form.get("title") or "").strip()
        source_url = (request.form.get("source_url") or "").strip()
        file = request.files.get("file")

        print(f"[FRONTEND] === Upload started at {_time.strftime('%H:%M:%S')} ===")
        print(f"[FRONTEND] title={title!r} source_url={source_url!r}")
        print(f"[FRONTEND] file={file.filename if file else None}")
        print(f"[FRONTEND] file size={file.content_length if file else 0}")
        print(f"[FRONTEND] API_BASE={API_BASE}")
        print(f"[FRONTEND] target URL: {API_BASE}/admin/articles/upload")

        if not file or file.filename == "":
            flash("Please select a PDF file.")
            return render_template("admin/upload.html", title=title, source_url=source_url)

        if not file.filename.lower().endswith(".pdf"):
            flash("Only PDF files are allowed.")
            return render_template("admin/upload.html", title=title, source_url=source_url)

        try:
            file_bytes = file.read()
            print(f"[FRONTEND] file read OK, {len(file_bytes)} bytes, took {_time.time()-t0:.2f}s")
            files = {"file": (file.filename, file_bytes, "application/pdf")}
            data = {}
            if title:
                data["title"] = title
            if source_url:
                data["source_url"] = source_url
            print(f"[FRONTEND] sending POST to backend... ({_time.strftime('%H:%M:%S')})")
            resp = requests.post(
                f"{API_BASE}/admin/articles/upload",
                files=files,
                data=data,
                timeout=300,
            )
            print(f"[FRONTEND] response received! took {_time.time()-t0:.2f}s")
            print(f"[FRONTEND] status={resp.status_code}")
            print(f"[FRONTEND] body={resp.text[:500] if resp.text else '(empty)'}")
        except requests.exceptions.Timeout as exc:
            print(f"[FRONTEND] TIMEOUT after {_time.time()-t0:.2f}s: {exc}")
            flash(f"Upload timed out after {_time.time()-t0:.0f}s. The file may be large or the LLM is slow. Try again.")
            return render_template("admin/upload.html", title=title, source_url=source_url)
        except requests.RequestException as exc:
            print(f"[FRONTEND] REQUEST FAILED after {_time.time()-t0:.2f}s: {type(exc).__name__}: {exc}")
            flash(f"Could not reach the API: {type(exc).__name__}: {exc}")
            return render_template("admin/upload.html", title=title, source_url=source_url)

        if resp.status_code in (200, 201):
            flash(f"Article uploaded successfully: {resp.json().get('title', '')}")
            return redirect(url_for("admin_index"))

        flash(_api_error(resp))
        return render_template("admin/upload.html", title=title, source_url=source_url)

    return render_template("admin/upload.html")


@app.route("/api/users", methods=["GET", "POST"])
def api_users_list():
    """Proxy: list / create users for admin."""
    user = session.get("user") or {}
    if request.method == "POST":
        if not user.get("is_admin") and not _user_has_perm("admin.users"):
            return jsonify({"error": "Admin access required"}), 403
        try:
            resp = requests.post(USERS_URL, json=request.get_json(silent=True) or {}, timeout=8)
            return jsonify(resp.json() if resp.text else {}), resp.status_code
        except requests.RequestException:
            return jsonify({"error": "Could not reach API"}), 503
    try:
        resp = requests.get(USERS_URL, timeout=5)
        return jsonify(resp.json() if resp.text else []), resp.status_code
    except requests.RequestException:
        return jsonify({"error": "Could not reach API"}), 503


@app.route("/api/users/<int:user_id>", methods=["PATCH", "DELETE"])
def api_users_patch(user_id):
    """Proxy: PATCH user is_admin, is_locked; DELETE user. Requires admin or admin.users."""
    user = session.get("user") or {}
    if not user.get("is_admin") and not _user_has_perm("admin.users"):
        return jsonify({"error": "Admin access required"}), 403
    if request.method == "DELETE":
        try:
            resp = requests.delete(f"{USERS_URL}/{user_id}", timeout=8)
            return jsonify(resp.json() if resp.text else {"ok": True}), resp.status_code
        except requests.RequestException:
            return jsonify({"error": "Could not reach API"}), 503
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.patch(
            f"{USERS_URL}/{user_id}",
            json=data,
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException:
        return jsonify({"error": "Could not reach API"}), 503


@app.route("/api/models", methods=["GET"])
def api_models():
    """Proxy: return available chat models from backend. Falls back to default when unreachable."""
    try:
        resp = requests.get(f"{API_BASE}/models", timeout=5)
        data = resp.json() if resp.text else []
        if not isinstance(data, list) or len(data) == 0:
            data = [os.environ.get("CHAT_MODEL", "qwen3:8b")]
        return jsonify(data), 200
    except requests.RequestException:
        return jsonify([os.environ.get("CHAT_MODEL", "qwen3:8b")]), 200


@app.route("/api/articles/upload", methods=["POST"])
def api_articles_upload():
    """Proxy: upload PDF to create article. Returns JSON {id, title} or {error}."""
    file = request.files.get("file")
    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are allowed"}), 400
    try:
        title = (request.form.get("title") or "").strip()
        source_url = (request.form.get("source_url") or "").strip()
        files = {"file": (file.filename, file.read(), "application/pdf")}
        data = {}
        if title:
            data["title"] = title
        if source_url:
            data["source_url"] = source_url
        resp = requests.post(
            f"{API_BASE}/admin/articles/upload",
            files=files,
            data=data,
            timeout=300,
        )
        body = resp.json() if resp.text else {}
        if resp.status_code in (200, 201):
            return jsonify(body), resp.status_code
        return jsonify({"error": body.get("error", "Upload failed")}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles", methods=["GET"])
def api_articles_list():
    """Proxy: list articles with optional ?q= search, ?page=, ?per_page=."""
    try:
        params = {}
        if request.args.get("q"):
            params["q"] = request.args.get("q")
        params["page"] = max(1, request.args.get("page", type=int) or 1)
        pp = request.args.get("per_page", type=int) or 12
        params["per_page"] = pp if pp in (12, 14, 48, 100) else 12
        resp = requests.get(ARTICLES_URL, params=params, timeout=10)
        return jsonify(resp.json() if resp.text else {"items": [], "total": 0, "page": 1, "per_page": 12}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/chat", methods=["POST"])
def api_articles_chat():
    """Proxy chat request to backend (for JS fetch from browser)."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(
            f"{ARTICLES_URL}/chat",
            json=data,
            timeout=300,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/rerun", methods=["POST"])
def api_articles_rerun():
    """Proxy: rerun selected articles."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{ARTICLES_URL}/rerun", json=data, timeout=600)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/<int:article_id>/chats/<int:chat_id>", methods=["DELETE"])
def api_article_chat_delete(article_id, chat_id):
    """Proxy: delete a chat from article history."""
    try:
        resp = requests.delete(
            f"{ARTICLES_URL}/{article_id}/chats/{chat_id}",
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/<int:article_id>/notes", methods=["GET"])
def api_article_notes(article_id):
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "Log in to view notes", "notes": []}), 401
    try:
        resp = requests.get(f"{ARTICLES_URL}/{article_id}/notes", params={"user_id": uid}, timeout=5)
        return jsonify(resp.json() if resp.text else []), resp.status_code
    except requests.RequestException:
        return jsonify({"error": "Could not load notes", "notes": []}), 503


@app.route("/api/articles/<int:article_id>/notes", methods=["POST"])
def api_article_notes_create(article_id):
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "Log in to add notes"}), 401
    data = dict(request.get_json(silent=True) or {})
    data["user_id"] = uid
    try:
        resp = requests.post(f"{ARTICLES_URL}/{article_id}/notes", json=data, timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/<int:article_id>/notes/<int:note_id>", methods=["DELETE"])
def api_article_note_delete(article_id, note_id):
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "Log in to delete notes"}), 401
    try:
        resp = requests.delete(f"{ARTICLES_URL}/{article_id}/notes/{note_id}", json={"user_id": uid}, timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/<int:article_id>/notes/export")
def api_article_notes_export(article_id):
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "Log in to export notes"}), 401
    fmt = request.args.get("format", "excel")
    try:
        resp = requests.get(
            f"{ARTICLES_URL}/{article_id}/notes/export",
            params={"user_id": uid, "format": fmt},
            timeout=30,
            stream=True,
        )
        if resp.status_code != 200:
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return jsonify({"error": data.get("error", "Export failed")}), resp.status_code

        def gen():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        ctype = resp.headers.get(
            "content-type",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if fmt == "excel"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        cd = resp.headers.get("Content-Disposition", f"attachment; filename=notes.{'xlsx' if fmt == 'excel' else 'docx'}")
        return Response(gen(), status=200, mimetype=ctype, headers={"Content-Disposition": cd})
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/<int:article_id>/chats/<int:chat_id>/feedback", methods=["POST"])
def api_article_chat_feedback(article_id, chat_id):
    """Proxy: set like/dislike feedback for article chat."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(
            f"{ARTICLES_URL}/{article_id}/chats/{chat_id}/feedback",
            json=data,
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/<int:article_id>/summary/pptx", methods=["GET"])
def api_article_summary_pptx(article_id):
    """Proxy: get PPTX for article summary."""
    try:
        resp = requests.get(
            f"{ARTICLES_URL}/{article_id}/summary/pptx",
            timeout=30,
            stream=True,
        )
        if resp.status_code != 200:
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return jsonify({"error": data.get("error", "Failed to generate PPTX")}), resp.status_code
        def gen():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        headers = dict(resp.headers)
        return Response(
            gen(),
            status=200,
            mimetype=resp.headers.get("content-type", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            headers={
                "Content-Disposition": resp.headers.get("Content-Disposition", "attachment; filename=summary.pptx"),
            },
        )
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/<int:article_id>/analysis/pptx", methods=["GET"])
def api_article_analysis_pptx(article_id):
    """Proxy: get PPTX for article analysis."""
    try:
        resp = requests.get(
            f"{ARTICLES_URL}/{article_id}/analysis/pptx",
            timeout=30,
            stream=True,
        )
        if resp.status_code != 200:
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return jsonify({"error": data.get("error", "Failed to generate PPTX")}), resp.status_code
        def gen():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        return Response(
            gen(),
            status=200,
            mimetype=resp.headers.get("content-type", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            headers={"Content-Disposition": resp.headers.get("Content-Disposition", "attachment; filename=analysis.pptx")},
        )
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/<int:article_id>/summary/feedback", methods=["POST"])
def api_article_summary_feedback(article_id):
    """Proxy: set like/dislike feedback for article summary."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(
            f"{ARTICLES_URL}/{article_id}/summary/feedback",
            json=data,
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/articles/batch-delete", methods=["POST"])
def api_articles_batch_delete():
    """Proxy: delete multiple articles."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{ARTICLES_URL}/batch-delete", json=data, timeout=30)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/admin/articles/<int:article_id>/delete", methods=["POST"])
def admin_delete_article(article_id):
    """Admin: delete article."""
    try:
        resp = requests.delete(f"{ARTICLES_URL}/{article_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Please try again.")
        return redirect(url_for("admin_index"))

    if resp.status_code == 200:
        flash("Article deleted.")
    else:
        flash(_api_error(resp))
    return redirect(url_for("admin_index"))


@app.route("/storages/delete/<int:storage_id>", methods=["GET", "POST"])
def storages_delete(storage_id):
    if request.method == "POST":
        try:
            resp = requests.delete(f"{STORAGES_URL}/{storage_id}", timeout=5)
        except requests.RequestException:
            flash("Could not reach the API. Please try again.")
            return redirect("/storages")

        if resp.status_code == 200:
            flash("Storage deleted successfully.")
            return redirect("/storages")
        flash(_api_error(resp, "Storage not found."))
        return redirect("/storages")

    try:
        resp = requests.get(f"{STORAGES_URL}/{storage_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Please try again.")
        return redirect("/storages")

    if resp.status_code != 200:
        flash(_api_error(resp, "Storage not found."))
        return redirect("/storages")

    return render_template("storages/delete.html", storage=resp.json())


# ---------------------------------------------------------------------------
# Theses
# ---------------------------------------------------------------------------
@app.route("/theses")
def theses_index():
    q = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or 12
    if per_page not in (12, 14, 48, 100):
        per_page = 12
    params = {"page": page, "per_page": per_page}
    if q:
        params["q"] = q
    try:
        resp = requests.get(THESES_URL, timeout=5, params=params)
    except requests.RequestException:
        flash("Could not reach the API. Is the backend running?")
        return render_template("theses/index.html", theses=[], pagination=None, search_q=q)
    if resp.status_code != 200:
        flash(_api_error(resp))
        return render_template("theses/index.html", theses=[], pagination=None, search_q=q)
    try:
        data = resp.json()
        theses, total, page, per_page = _parse_list_response(data)
        pagination = {"total": total, "page": page, "per_page": per_page}
    except Exception:
        theses, pagination = [], None
    pagination_params = {"q": q} if q else {}
    return render_template(
        "theses/index.html",
        theses=theses,
        pagination=pagination,
        pagination_url="theses_index",
        pagination_params=pagination_params,
        search_q=q,
    )


@app.route("/theses/<int:thesis_id>")
def thesis_detail(thesis_id):
    try:
        resp = requests.get(f"{THESES_URL}/{thesis_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Please try again.")
        return redirect(url_for("theses_index"))
    if resp.status_code != 200:
        flash(_api_error(resp, "Thesis not found."))
        return redirect(url_for("theses_index"))

    chats = []
    try:
        chat_resp = requests.get(f"{THESES_URL}/{thesis_id}/chats", timeout=5)
        if chat_resp.status_code == 200:
            chats = chat_resp.json()
    except Exception:
        pass

    return render_template("theses/detail.html", thesis=resp.json(), chats=chats)


@app.route("/theses/upload", methods=["GET", "POST"])
def theses_upload():
    if request.method == "POST":
        import time as _time
        t0 = _time.time()
        title = (request.form.get("title") or "").strip()
        source_url = (request.form.get("source_url") or "").strip()
        file = request.files.get("file")

        print(f"[FRONTEND] thesis upload: title={title!r} file={file.filename if file else None}")

        if not file or file.filename == "":
            flash("Please select a PDF file.")
            return render_template("theses/upload.html", title=title, source_url=source_url)
        if not file.filename.lower().endswith(".pdf"):
            flash("Only PDF files are allowed.")
            return render_template("theses/upload.html", title=title, source_url=source_url)

        try:
            file_bytes = file.read()
            files = {"file": (file.filename, file_bytes, "application/pdf")}
            data = {}
            if title:
                data["title"] = title
            if source_url:
                data["source_url"] = source_url
            resp = requests.post(
                f"{API_BASE}/admin/theses/upload",
                files=files,
                data=data,
                timeout=600,
            )
            print(f"[FRONTEND] thesis upload response: {resp.status_code} ({_time.time()-t0:.1f}s)")
        except requests.exceptions.Timeout:
            flash(f"Upload timed out after {_time.time()-t0:.0f}s. The thesis may be large.")
            return render_template("theses/upload.html", title=title, source_url=source_url)
        except requests.RequestException as exc:
            flash(f"Could not reach the API: {type(exc).__name__}: {exc}")
            return render_template("theses/upload.html", title=title, source_url=source_url)

        if resp.status_code in (200, 201):
            flash(f"Thesis uploaded successfully: {resp.json().get('title', '')}")
            return redirect(url_for("theses_index"))

        flash(_api_error(resp))
        return render_template("theses/upload.html", title=title, source_url=source_url)

    return render_template("theses/upload.html")


@app.route("/theses/<int:thesis_id>/delete", methods=["POST"])
def theses_delete(thesis_id):
    try:
        resp = requests.delete(f"{THESES_URL}/{thesis_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Please try again.")
        return redirect(url_for("theses_index"))
    if resp.status_code == 200:
        flash("Thesis deleted.")
    else:
        flash(_api_error(resp))
    return redirect(url_for("theses_index"))


@app.route("/api/theses/rerun", methods=["POST"])
def api_theses_rerun():
    """Proxy: rerun selected theses."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{THESES_URL}/rerun", json=data, timeout=600)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/theses/batch-delete", methods=["POST"])
def api_theses_batch_delete():
    """Proxy: delete multiple theses."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{THESES_URL}/batch-delete", json=data, timeout=30)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/theses/chat", methods=["POST"])
def api_theses_chat():
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{THESES_URL}/chat", json=data, timeout=300)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/theses/<int:thesis_id>/chats/<int:chat_id>", methods=["DELETE"])
def api_thesis_chat_delete(thesis_id, chat_id):
    """Proxy: delete a chat from thesis history."""
    try:
        resp = requests.delete(
            f"{THESES_URL}/{thesis_id}/chats/{chat_id}",
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/theses/<int:thesis_id>/summary/pptx", methods=["GET"])
def api_thesis_summary_pptx(thesis_id):
    """Proxy: get PPTX for thesis summary."""
    try:
        resp = requests.get(f"{THESES_URL}/{thesis_id}/summary/pptx", timeout=30, stream=True)
        if resp.status_code != 200:
            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            return jsonify({"error": data.get("error", "Failed to generate PPTX")}), resp.status_code

        def gen():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        return Response(
            gen(),
            status=200,
            mimetype=resp.headers.get("content-type", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            headers={"Content-Disposition": resp.headers.get("Content-Disposition", "attachment; filename=thesis.pptx")},
        )
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/theses/<int:thesis_id>/chats/<int:chat_id>/feedback", methods=["POST"])
def api_thesis_chat_feedback(thesis_id, chat_id):
    """Proxy: set like/dislike feedback for thesis chat."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(
            f"{THESES_URL}/{thesis_id}/chats/{chat_id}/feedback",
            json=data,
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


# ---------------------------------------------------------------------------
# Books
# ---------------------------------------------------------------------------
@app.route("/books")
def books_index():
    category_id = request.args.get("category_id", type=int)
    q = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or 12
    if per_page not in (12, 14, 48, 100):
        per_page = 12
    book_categories = []
    try:
        cat_resp = requests.get(f"{API_BASE}/admin/book-categories", timeout=5)
        if cat_resp.status_code == 200:
            book_categories = cat_resp.json()
    except Exception:
        pass
    params = {"page": page, "per_page": per_page}
    if category_id is not None:
        params["category_id"] = category_id
    if q:
        params["q"] = q
    try:
        resp = requests.get(BOOKS_URL, timeout=5, params=params)
    except requests.RequestException:
        flash("Could not reach the API. Is the backend running?")
        return render_template("books/index.html", books=[], book_categories=book_categories, pagination=None, search_q=q)
    if resp.status_code != 200:
        flash(_api_error(resp))
        return render_template("books/index.html", books=[], book_categories=book_categories, pagination=None, search_q=q)
    try:
        data = resp.json()
        books, total, page, per_page = _parse_list_response(data)
        pagination = {"total": total, "page": page, "per_page": per_page}
    except Exception:
        books, pagination = [], None
    pagination_params = {}
    if category_id is not None:
        pagination_params["category_id"] = category_id
    if q:
        pagination_params["q"] = q
    return render_template(
        "books/index.html",
        books=books,
        book_categories=book_categories,
        current_category_id=category_id,
        pagination=pagination,
        pagination_url="books_index",
        pagination_params=pagination_params,
        search_q=q,
    )


@app.route("/books/<int:book_id>")
def book_detail(book_id):
    try:
        resp = requests.get(f"{BOOKS_URL}/{book_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API. Please try again.")
        return redirect(url_for("books_index"))
    if resp.status_code != 200:
        flash(_api_error(resp, "Book not found."))
        return redirect(url_for("books_index"))
    chats = []
    try:
        chat_resp = requests.get(f"{BOOKS_URL}/{book_id}/chats", timeout=5)
        if chat_resp.status_code == 200:
            chats = chat_resp.json()
    except Exception:
        pass
    return render_template("books/detail.html", book=resp.json(), chats=chats, user_id=_current_user_id())


@app.route("/books/upload", methods=["GET", "POST"])
def books_upload():
    book_categories = []
    try:
        cat_resp = requests.get(f"{API_BASE}/admin/book-categories", timeout=5)
        if cat_resp.status_code == 200:
            book_categories = cat_resp.json()
    except Exception:
        pass
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        source_url = (request.form.get("source_url") or "").strip()
        category_id = request.form.get("category_id", type=int) or None
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("Please select a PDF file.")
            return render_template("books/upload.html", title=title, source_url=source_url, book_categories=book_categories)
        if not file.filename.lower().endswith(".pdf"):
            flash("Only PDF files are allowed.")
            return render_template("books/upload.html", title=title, source_url=source_url, book_categories=book_categories)
        try:
            files = {"file": (file.filename, file.read(), "application/pdf")}
            data = {}
            if title:
                data["title"] = title
            if source_url:
                data["source_url"] = source_url
            if category_id:
                data["category_id"] = str(category_id)
            resp = requests.post(f"{API_BASE}/admin/books/upload", files=files, data=data, timeout=600)
        except requests.exceptions.Timeout:
            flash("Upload timed out. The book may be large.")
            return render_template("books/upload.html", title=title, source_url=source_url, book_categories=book_categories)
        except requests.RequestException as exc:
            flash(f"Could not reach the API: {exc}")
            return render_template("books/upload.html", title=title, source_url=source_url, book_categories=book_categories)
        if resp.status_code in (200, 201):
            flash(f"Book uploaded: {resp.json().get('title', '')}")
            return redirect(url_for("books_index"))
        flash(_api_error(resp))
        return render_template("books/upload.html", title=title, source_url=source_url, book_categories=book_categories)
    return render_template("books/upload.html", book_categories=book_categories)


@app.route("/books/<int:book_id>/delete", methods=["POST"])
def books_delete(book_id):
    try:
        resp = requests.delete(f"{BOOKS_URL}/{book_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API.")
        return redirect(url_for("books_index"))
    if resp.status_code == 200:
        flash("Book deleted.")
    else:
        flash(_api_error(resp))
    return redirect(url_for("books_index"))


@app.route("/api/books/rerun", methods=["POST"])
def api_books_rerun():
    """Proxy: rerun selected books."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{BOOKS_URL}/rerun", json=data, timeout=600)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/books/batch-delete", methods=["POST"])
def api_books_batch_delete():
    """Proxy: delete multiple books."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{BOOKS_URL}/batch-delete", json=data, timeout=30)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/books/chat", methods=["POST"])
def api_books_chat():
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{BOOKS_URL}/chat", json=data, timeout=300)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/books/<int:book_id>/chats/<int:chat_id>", methods=["DELETE"])
def api_book_chat_delete(book_id, chat_id):
    try:
        resp = requests.delete(f"{BOOKS_URL}/{book_id}/chats/{chat_id}", timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/books/<int:book_id>/chats/<int:chat_id>/feedback", methods=["POST"])
def api_book_chat_feedback(book_id, chat_id):
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{BOOKS_URL}/{book_id}/chats/{chat_id}/feedback", json=data, timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/books/<int:book_id>/notes", methods=["GET"])
def api_book_notes(book_id):
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "Log in to view notes", "notes": []}), 401
    try:
        resp = requests.get(f"{BOOKS_URL}/{book_id}/notes", params={"user_id": uid}, timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e), "notes": []}), 503


@app.route("/api/books/<int:book_id>/notes", methods=["POST"])
def api_book_notes_create(book_id):
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "Log in to add notes"}), 401
    data = dict(request.get_json(silent=True) or {})
    data["user_id"] = uid
    try:
        resp = requests.post(f"{BOOKS_URL}/{book_id}/notes", json=data, timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/books/<int:book_id>/notes/<int:note_id>", methods=["DELETE"])
def api_book_note_delete(book_id, note_id):
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "Log in to delete notes"}), 401
    try:
        resp = requests.delete(f"{BOOKS_URL}/{book_id}/notes/{note_id}", json={"user_id": uid}, timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/books/<int:book_id>/notes/export")
def api_book_notes_export(book_id):
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "Log in to export notes"}), 401
    fmt = request.args.get("format", "excel")
    try:
        resp = requests.get(f"{BOOKS_URL}/{book_id}/notes/export", params={"user_id": uid, "format": fmt}, timeout=30, stream=True)
        if resp.status_code != 200:
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return jsonify({"error": data.get("error", "Export failed")}), resp.status_code
        def gen():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        ctype = resp.headers.get("content-type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "excel" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        cd = resp.headers.get("Content-Disposition", f"attachment; filename=notes.{'xlsx' if fmt == 'excel' else 'docx'}")
        return Response(gen(), status=200, mimetype=ctype, headers={"Content-Disposition": cd})
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/book-categories", methods=["GET"])
def api_book_categories():
    try:
        resp = requests.get(f"{API_BASE}/admin/book-categories", timeout=5)
        return jsonify(resp.json() if resp.text else []), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/book-categories", methods=["POST"])
def api_book_categories_create():
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{API_BASE}/admin/book-categories", json=data, timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/book-categories/<int:cat_id>", methods=["PUT"])
def api_book_category_update(cat_id):
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.put(f"{API_BASE}/admin/book-categories/{cat_id}", json=data, timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/book-categories/<int:cat_id>", methods=["DELETE"])
def api_book_category_delete(cat_id):
    try:
        resp = requests.delete(f"{API_BASE}/admin/book-categories/{cat_id}", timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/status-catalog", methods=["GET"])
def api_admin_status_catalog_list():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.get(
            f"{API_BASE}/admin/status-catalog",
            params={"lang": _ui_lang()},
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/status-catalog", methods=["POST"])
def api_admin_status_catalog_create():
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{API_BASE}/admin/status-catalog", json=data, timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/status-catalog/<int:item_id>", methods=["PUT"])
def api_admin_status_catalog_update(item_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.put(
            f"{API_BASE}/admin/status-catalog/{item_id}", json=data, timeout=5
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/admin/status-catalog/<int:item_id>", methods=["DELETE"])
def api_admin_status_catalog_delete(item_id):
    if not session.get("user"):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        resp = requests.delete(f"{API_BASE}/admin/status-catalog/{item_id}", timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/books/<int:book_id>", methods=["PATCH"])
def api_book_update(book_id):
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.patch(f"{BOOKS_URL}/{book_id}", json=data, timeout=5)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/books/<int:book_id>/summary/pptx", methods=["GET"])
def api_book_summary_pptx(book_id):
    try:
        resp = requests.get(f"{BOOKS_URL}/{book_id}/summary/pptx", timeout=30, stream=True)
        if resp.status_code != 200:
            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            return jsonify({"error": data.get("error", "Failed to generate PPTX")}), resp.status_code
        def gen():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        return Response(gen(), status=200, mimetype=resp.headers.get("content-type", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            headers={"Content-Disposition": resp.headers.get("Content-Disposition", "attachment; filename=book.pptx")})
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


# ---------------------------------------------------------------------------
# Research Projects
# ---------------------------------------------------------------------------
@app.route("/projects")
def projects_index():
    q = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or 12
    if per_page not in (12, 14, 48, 100):
        per_page = 12
    params = {"page": page, "per_page": per_page}
    if q:
        params["q"] = q
    if (uid := _current_user_id()) is not None:
        params["user_id"] = uid
    try:
        resp = requests.get(PROJECTS_URL, timeout=30, params=params)
    except requests.RequestException:
        flash("Could not reach the API. Is the backend running?")
        return render_template("projects/index.html", projects=[], pagination=None, search_q=q)
    if resp.status_code != 200:
        flash(_api_error(resp, "Could not load projects."))
        return render_template("projects/index.html", projects=[], pagination=None, search_q=q)
    try:
        data = resp.json()
        projects, total, page, per_page = _parse_list_response(data)
        pagination = {"total": total, "page": page, "per_page": per_page}
    except Exception:
        projects, pagination = [], None
    pagination_params = {"q": q} if q else {}
    return render_template(
        "projects/index.html",
        projects=projects or [],
        pagination=pagination,
        pagination_url="projects_index",
        pagination_params=pagination_params,
        search_q=q,
    )


@app.route("/projects/create", methods=["GET", "POST"])
def projects_create():
    if request.method == "POST":
        import time as _time
        t0 = _time.time()
        # Accept either form (legacy) or JSON (new flow)
        if request.is_json:
            data = request.get_json(silent=True) or {}
            title = (data.get("title") or "").strip()
            description = (data.get("description") or "").strip()
            aims = (data.get("aims") or "").strip()
            instructions = (data.get("instructions") or "").strip()
            article_ids = data.get("article_ids") or []
        else:
            title = (request.form.get("title") or "").strip()
            description = (request.form.get("description") or "").strip()
            aims = (request.form.get("aims") or "").strip()
            instructions = (request.form.get("instructions") or "").strip()
            article_ids = request.form.getlist("article_ids") or []
            article_ids = [int(x) for x in article_ids if str(x).isdigit()]

        if not title:
            if request.is_json:
                return jsonify({"error": "Title is required."}), 400
            flash("Title is required.")
            return render_template(
                "projects/create.html", title=title, description=description, aims=aims, instructions=instructions
            )

        try:
            payload = {
                "title": title,
                "description": description,
                "aims": aims,
                "instructions": instructions,
                "article_ids": article_ids,
            }
            uid = _current_user_id()
            if uid is not None:
                payload["user_id"] = uid
            resp = requests.post(PROJECTS_URL, json=payload, timeout=30)
        except requests.RequestException as exc:
            _msg = f"Could not reach the API at {API_BASE}. Is the backend running? ({exc!r})"
            if request.is_json:
                return jsonify({"error": _msg}), 503
            flash(_msg)
            return render_template(
                "projects/create.html", title=title, description=description, aims=aims, instructions=instructions
            )

        if resp.status_code not in (200, 201):
            err = _api_error(resp)
            if request.is_json:
                return jsonify({"error": err}), resp.status_code
            flash(err)
            return render_template(
                "projects/create.html", title=title, description=description, aims=aims, instructions=instructions
            )

        project_id = resp.json().get("id")

        # For JSON (fetch) requests: return JSON so client can redirect; don't return HTML redirect
        if request.is_json:
            return jsonify({"id": project_id, "ok": True}), 200

        # Legacy: optional direct file upload to project
        uploaded_files = request.files.getlist("files") if not request.is_json else []
        has_files = uploaded_files and any(f.filename != "" for f in uploaded_files)
        if has_files:
            try:
                files_payload = []
                for f in uploaded_files:
                    if f and f.filename and f.filename.lower().endswith(".pdf"):
                        files_payload.append(("files", (f.filename, f.read(), "application/pdf")))
                if files_payload:
                    upload_data = {"user_id": uid} if (uid := _current_user_id()) is not None else {}
                    upload_resp = requests.post(
                        f"{PROJECTS_URL}/{project_id}/files",
                        files=files_payload,
                        data=upload_data,
                        timeout=600,
                    )
                    print(f"[FRONTEND] project files upload: {upload_resp.status_code} ({_time.time()-t0:.1f}s)")
            except Exception as exc:
                print(f"[FRONTEND] project files upload error: {exc}")
                flash(f"Project created but file upload had errors: {exc}")

        flash(f"Project '{title}' created successfully.")
        return redirect(url_for("project_detail", project_id=project_id))

    return render_template("projects/create.html")


@app.route("/projects/<int:project_id>")
def project_detail(project_id):
    try:
        params = {}
        if (uid := _current_user_id()) is not None:
            params["user_id"] = uid
        try:
            resp = requests.get(f"{PROJECTS_URL}/{project_id}", params=params, timeout=30)
        except requests.RequestException:
            flash("Could not reach the API.")
            return redirect(url_for("projects_index"))
        if resp.status_code != 200:
            flash(_api_error(resp, "Project not found."))
            return redirect(url_for("projects_index"))

        project = resp.json()
        # Ensure project has expected structure (files, articles as lists)
        if project.get("files") is None:
            project["files"] = []
        if project.get("articles") is None:
            project["articles"] = []

        chats = []
        try:
            chat_resp = requests.get(f"{PROJECTS_URL}/{project_id}/chats", params=params, timeout=30)
            if chat_resp.status_code == 200:
                chats = chat_resp.json()
        except Exception:
            pass

        # Build projectAskAllItems for template (Jinja2 doesn't support list comprehensions)
        articles = project.get("articles") or []
        files = project.get("files") or []
        project_ask_all_items = [
            {"type": "article", "id": a["id"], "title": a.get("title", "")}
            for a in articles
        ] + [
            {"type": "file", "id": f["id"], "title": f.get("title", "")}
            for f in files
            if f.get("status") == "ready"
        ]

        return render_template(
            "projects/detail.html",
            project=project,
            chats=chats,
            project_ask_all_items=project_ask_all_items,
        )
    except Exception as e:
        import traceback
        err_msg = str(e)
        tb = traceback.format_exc()
        print(f"[FRONTEND] project_detail error: {err_msg}\n{tb}")
        flash(f"Error loading project: {err_msg}")
        return redirect(url_for("projects_index"))


@app.route("/projects/<int:project_id>/delete", methods=["POST"])
def projects_delete(project_id):
    try:
        params = {}
        if (uid := _current_user_id()) is not None:
            params["user_id"] = uid
        resp = requests.delete(f"{PROJECTS_URL}/{project_id}", params=params, timeout=10)
    except requests.RequestException:
        flash("Could not reach the API.")
        return redirect(url_for("projects_index"))
    if resp.status_code == 200:
        flash("Project deleted.")
    else:
        flash(_api_error(resp))
    return redirect(url_for("projects_index"))


@app.route("/api/projects/<int:project_id>/draft/export", methods=["POST"])
def api_project_draft_export(project_id):
    """Proxy: export publication draft to Word."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(
            f"{PROJECTS_URL}/{project_id}/draft/export",
            json=data,
            timeout=60,
        )
        if resp.status_code != 200:
            err = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            return jsonify({"error": err.get("error", "Export failed")}), resp.status_code
        return Response(
            resp.content,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": resp.headers.get("Content-Disposition", "attachment; filename=publication_draft.docx")},
        )
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/projects/<int:project_id>/summary/pptx", methods=["GET"])
def api_project_summary_pptx(project_id):
    """Proxy: get PPTX for project combined summary."""
    params = {}
    if (uid := _current_user_id()) is not None:
        params["user_id"] = uid
    try:
        resp = requests.get(
            f"{PROJECTS_URL}/{project_id}/summary/pptx",
            params=params,
            timeout=30,
            stream=True,
        )
        if resp.status_code != 200:
            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            return jsonify({"error": data.get("error", "Failed to generate PPTX")}), resp.status_code

        def gen():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk

        return Response(
            gen(),
            status=200,
            mimetype=resp.headers.get("content-type", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
            headers={"Content-Disposition": resp.headers.get("Content-Disposition", "attachment; filename=project.pptx")},
        )
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/projects/<int:project_id>/articles", methods=["POST"])
def api_projects_add_articles(project_id):
    """Proxy: link articles to project."""
    data = dict(request.get_json(silent=True) or {})
    uid = _current_user_id()
    if uid is not None:
        data["user_id"] = uid
    try:
        resp = requests.post(
            f"{PROJECTS_URL}/{project_id}/articles",
            json=data,
            timeout=30,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/projects/<int:project_id>/shares", methods=["GET"])
def api_projects_shares(project_id):
    """Proxy: list project shares."""
    try:
        params = {}
        if (uid := _current_user_id()) is not None:
            params["user_id"] = uid
        resp = requests.get(f"{PROJECTS_URL}/{project_id}/shares", params=params, timeout=5)
        return jsonify(resp.json() if resp.text else []), resp.status_code
    except requests.RequestException:
        return jsonify({"error": "Could not reach API"}), 503


@app.route("/api/projects/<int:project_id>/shares", methods=["POST"])
def api_projects_add_share(project_id):
    """Proxy: add share by email."""
    data = request.get_json(silent=True) or {}
    try:
        payload = dict(data)
        if (uid := _current_user_id()) is not None:
            payload["user_id"] = uid
        resp = requests.post(
            f"{PROJECTS_URL}/{project_id}/shares",
            json=payload,
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException:
        return jsonify({"error": "Could not reach API"}), 503


@app.route("/api/projects/<int:project_id>/shares/<int:shared_user_id>", methods=["DELETE"])
def api_projects_remove_share(project_id, shared_user_id):
    """Proxy: remove share."""
    try:
        params = {}
        if (uid := _current_user_id()) is not None:
            params["user_id"] = uid
        resp = requests.delete(
            f"{PROJECTS_URL}/{project_id}/shares/{shared_user_id}",
            params=params,
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException:
        return jsonify({"error": "Could not reach API"}), 503


@app.route("/api/projects/<int:project_id>/articles/<int:article_id>", methods=["DELETE"])
def api_projects_remove_article(project_id, article_id):
    """Proxy: unlink article from project."""
    try:
        resp = requests.delete(
            f"{PROJECTS_URL}/{project_id}/articles/{article_id}",
            timeout=10,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/projects/<int:project_id>/articles/upload", methods=["POST"])
def api_projects_upload_article(project_id):
    """Proxy: upload PDF, create article, link to project."""
    try:
        files = {"file": request.files.get("file")} if request.files.get("file") else None
        if not files or not files["file"] or not files["file"].filename:
            return jsonify({"error": "No file"}), 400
        form = dict(request.form)
        if (uid := _current_user_id()) is not None:
            form["user_id"] = str(uid)
        resp = requests.post(
            f"{PROJECTS_URL}/{project_id}/articles/upload",
            files=files,
            data=form,
            timeout=600,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/projects/<int:project_id>/upload", methods=["POST"])
def projects_upload_files(project_id):
    uploaded_files = request.files.getlist("files")
    if not uploaded_files or all(f.filename == "" for f in uploaded_files):
        return jsonify({"error": "No files"}), 400
    try:
        files_payload = []
        for f in uploaded_files:
            if f and f.filename and f.filename.lower().endswith(".pdf"):
                files_payload.append(("files", (f.filename, f.read(), "application/pdf")))
        if not files_payload:
            return jsonify({"error": "No valid PDF files"}), 400
        data = {}
        if (uid := _current_user_id()) is not None:
            data["user_id"] = uid
        resp = requests.post(
            f"{PROJECTS_URL}/{project_id}/files",
            files=files_payload,
            data=data,
            timeout=600,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/projects/<int:project_id>/files/<int:file_id>/delete", methods=["POST"])
def projects_delete_file(project_id, file_id):
    try:
        resp = requests.delete(f"{PROJECTS_URL}/{project_id}/files/{file_id}", timeout=5)
    except requests.RequestException:
        flash("Could not reach the API.")
        return redirect(url_for("project_detail", project_id=project_id))
    if resp.status_code == 200:
        flash("File removed.")
    else:
        flash(_api_error(resp))
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/projects/<int:project_id>/rerun", methods=["POST"])
def projects_rerun(project_id):
    data = {}
    if (uid := _current_user_id()) is not None:
        data["user_id"] = uid
    try:
        resp = requests.post(f"{PROJECTS_URL}/{project_id}/rerun", json=data, timeout=600)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/projects/batch-rerun", methods=["POST"])
def api_projects_batch_rerun():
    """Proxy: rerun selected projects."""
    data = dict(request.get_json(silent=True) or {})
    if (uid := _current_user_id()) is not None:
        data["user_id"] = uid
    try:
        resp = requests.post(f"{PROJECTS_URL}/batch-rerun", json=data, timeout=600)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/projects/batch-delete", methods=["POST"])
def api_projects_batch_delete():
    """Proxy: delete multiple projects."""
    data = request.get_json(silent=True) or {}
    try:
        resp = requests.post(f"{PROJECTS_URL}/batch-delete", json=data, timeout=30)
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/projects/<int:project_id>/chats/<int:chat_id>", methods=["DELETE"])
def api_project_chat_delete(project_id, chat_id):
    """Proxy: delete a chat from project history."""
    params = {}
    if (uid := _current_user_id()) is not None:
        params["user_id"] = uid
    try:
        resp = requests.delete(
            f"{PROJECTS_URL}/{project_id}/chats/{chat_id}",
            params=params,
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/projects/<int:project_id>/chats/<int:chat_id>/feedback", methods=["POST"])
def api_project_chat_feedback(project_id, chat_id):
    """Proxy: set like/dislike feedback for project chat."""
    data = dict(request.get_json(silent=True) or {})
    if (uid := _current_user_id()) is not None:
        data["user_id"] = uid
    try:
        resp = requests.post(
            f"{PROJECTS_URL}/{project_id}/chats/{chat_id}/feedback",
            json=data,
            timeout=5,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


@app.route("/api/projects/<int:project_id>/chat", methods=["POST"])
def api_projects_chat(project_id):
    data = dict(request.get_json(silent=True) or {})
    if (uid := _current_user_id()) is not None:
        data["user_id"] = uid
    try:
        resp = requests.post(
            f"{PROJECTS_URL}/{project_id}/chat",
            json=data,
            timeout=300,
        )
        return jsonify(resp.json() if resp.text else {}), resp.status_code
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 503


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
from admission_bot_routes import register_admission_bot

register_admission_bot(app, API_BASE, _api_proxy, _user_has_perm, _is_exec_viewer, _user_scopes_header)

from student_bot_routes import register_student_bot

register_student_bot(app, API_BASE, _api_proxy, _user_has_perm, _is_exec_viewer, _user_scopes_header)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8027))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
