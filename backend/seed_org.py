"""
Seed departments, staff users, permissions, and program scopes from nghiepvu.
Username = Tên + viết tắt Họ/Đệm (không dấu). Password tạm: 123!
"""
from __future__ import annotations

import unicodedata

from rbac import (
    ADMIN_CATALOG_CODES,
    ADMIN_DATA_RECORD_CODES,
    ADMIN_SUPER_CODES,
    DEPT_DEFAULT_PERMISSIONS,
    DEPT_DEFAULT_PROGRAM_SCOPES,
    DEPT_PERMISSIONS_FORCE_SYNC,
    MENU_ITEMS,
    PROGRAMS,
    USER_CAMPUS_SCOPES,
    USER_PROGRAM_SCOPES,
)

TEMP_PASSWORD = "123!"


def _reset_staff_passwords_enabled() -> bool:
    """On server/Docker, default reset staff passwords to TEMP_PASSWORD each seed."""
    import os

    return os.environ.get("RESET_STAFF_PASSWORDS", "true").lower() in (
        "1",
        "true",
        "yes",
    )

# (code, name, sort_order)
DEPARTMENTS = [
    ("ban_giam_doc", "Ban giám đốc", 1),
    ("tro_ly_bgd", "Trợ lý Ban giám đốc", 2),
    ("ke_toan", "Bộ phận Kế toán", 3),
    ("tuyen_sinh", "Bộ phận Tuyển sinh", 4),
    ("marcom", "Bộ phận Marcom", 5),
    ("mba", "Chương trình MBA", 6),
    ("master_chuyen_nganh", "Chương trình Master Chuyên ngành", 7),
    ("giang_vien", "Giảng viên / Chuyên gia", 8),
    ("it", "Bộ phận IT", 9),
    ("logistic", "Bộ phận Logistic, bảo vệ", 10),
    ("admin_he_thong", "Admin Quản trị hệ thống", 11),
    ("hoc_vien", "Học viên", 12),
    ("cuu_hoc_vien", "Cựu học viên", 15),
    ("khao_thi", "Bộ phận Khảo thí", 13),
    ("thanh_tra", "Bộ phận Thanh tra", 14),
    # legacy — giữ để migrate membership cũ
    ("marcom_tuyen_sinh", "Bộ phận Marcom + tuyển sinh (legacy)", 99),
]

# (full_name, title, department_codes, is_admin)
STAFF = [
    ("Trương Tuấn Anh", "Đồng giám đốc Việt Nam", ["ban_giam_doc"], False),
    ("Trần Vân Như", "Giám đốc học thuật", ["ban_giam_doc"], False),
    ("Trịnh Huyền Diệu Linh", "Trợ lý Ban giám đốc", ["tro_ly_bgd"], False),
    ("Bùi Thị Loan", "Kế toán trưởng", ["ke_toan"], False),
    ("Nguyễn Thị Hạnh", "Thủ quỹ (toàn CT) / Điều phối MBA", ["ke_toan", "mba"], False),
    ("Trần Anh Tuấn", "Marcom", ["marcom"], False),
    ("Lê Hồng Nhung", "Tuyển sinh", ["tuyen_sinh"], False),
    ("Nguyễn Thị Quỳnh Giao", "Tuyển sinh", ["tuyen_sinh"], False),
    ("Lê Phương Hà", "Quản lý chương trình MBA", ["mba"], False),
    ("Nguyễn Thị Ngọc Đoan", "Điều phối chương trình MBA", ["mba"], False),
    ("Trịnh Kiều Linh", "Quản lý chương trình MMS", ["master_chuyen_nganh"], False),
    ("Lê Thùy Linh", "Điều phối chương trình MMS", ["master_chuyen_nganh"], False),
    ("Phạm Thị Xuân Anh", "Quản lý chương trình MSCM + X Alumni", ["master_chuyen_nganh"], False),
    # NghiND: quyền danh mục do ADMIN_ACCOUNTS đồng bộ (không is_admin, không kế thừa ALL ops)
    ("Ngô Đức Nghị", "Quản trị danh mục hệ thống", [], False),
    ("Nguyễn Huy Tiến", "Bảo vệ", ["logistic"], False),
    ("Nguyễn Khắc Cường", "Bảo vệ", ["logistic"], False),
    # Giảng viên mẫu (từ hồ sơ phân giảng)
    ("Jean Dupont", "Giảng viên lý thuyết", ["giang_vien"], False),
    ("Prof. Jean Dupont", "Giảng viên lý thuyết", ["giang_vien"], False),
    ("Nguyễn Văn Chuyên", "Chuyên gia", ["giang_vien"], False),
]

# Tài khoản Admin cố định (login không qua make_username)
# - NghiND: chỉ nhóm quản trị danh mục hệ thống
# - Admin: quản trị toàn bộ bản ghi dữ liệu nghiệp vụ (ops)
# - ThaoP: toàn quyền (is_admin) — mọi dữ liệu + mọi báo cáo + cấu hình
ADMIN_ACCOUNTS = [
    {
        "login": "NghiND",
        "name": "Ngô Đức Nghị — Quản trị danh mục hệ thống",
        "password": TEMP_PASSWORD,
        "is_admin": False,
        "admin_role": "catalog",
        "departments": [],
        "direct_permissions": list(ADMIN_CATALOG_CODES),
        "sync_departments": True,
        "sync_permissions": True,
        "program_scopes": ["*"],
    },
    {
        "login": "Admin",
        "name": "Admin — Quản trị bản ghi dữ liệu hệ thống",
        "password": TEMP_PASSWORD,
        "is_admin": False,
        "admin_role": "data",
        "departments": ["admin_he_thong"],
        "direct_permissions": list(ADMIN_DATA_RECORD_CODES),
        "sync_departments": True,
        "sync_permissions": True,
        "program_scopes": ["*"],
    },
    {
        "login": "ThaoP",
        "name": "ThaoP — Super Admin (toàn quyền)",
        "password": TEMP_PASSWORD,
        "is_admin": True,
        "admin_role": "super",
        "departments": ["admin_he_thong", "it"],
        "direct_permissions": list(ADMIN_SUPER_CODES),
        "sync_departments": True,
        "sync_permissions": True,
        "program_scopes": ["*"],
    },
]


def strip_accents(text: str) -> str:
    """Remove Vietnamese diacritics; Đ/đ are separate letters (not NFD marks)."""
    text = text.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def make_username(full_name: str) -> str:
    """Tên + chữ cái đầu của Họ và các phần Đệm (không dấu)."""
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return ""
    ten = strip_accents(parts[-1])
    # Capitalize first letter of given name for stable login ids
    ten = ten[:1].upper() + ten[1:] if ten else ten
    initials = "".join(strip_accents(p)[0].upper() for p in parts[:-1] if p)
    return f"{ten}{initials}"


def _migrate_accented_usernames(cur) -> int:
    """Rename or merge legacy logins that still contain Vietnamese diacritics."""
    cur.execute("SELECT id, email FROM user")
    rows = list(cur.fetchall())
    fixed = 0
    for user_id, email in rows:
        if not email:
            continue
        clean = strip_accents(email)
        if clean == email:
            continue
        cur.execute("SELECT id FROM user WHERE email = ? AND id != ?", (clean, user_id))
        existing = cur.fetchone()
        if existing:
            keep_id = existing[0]
            # Move memberships/scopes then drop accented duplicate
            cur.execute(
                "INSERT OR IGNORE INTO user_departments (user_id, department_id) "
                "SELECT ?, department_id FROM user_departments WHERE user_id = ?",
                (keep_id, user_id),
            )
            cur.execute("DELETE FROM user_departments WHERE user_id = ?", (user_id,))
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO user_program_scopes (user_id, program_code) "
                    "SELECT ?, program_code FROM user_program_scopes WHERE user_id = ?",
                    (keep_id, user_id),
                )
                cur.execute("DELETE FROM user_program_scopes WHERE user_id = ?", (user_id,))
            except Exception:
                pass
            cur.execute("DELETE FROM user WHERE id = ?", (user_id,))
        else:
            cur.execute("UPDATE user SET email = ? WHERE id = ?", (clean, user_id))
        fixed += 1
    return fixed


def ensure_rbac_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS departments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "code TEXT NOT NULL UNIQUE, "
        "name TEXT NOT NULL, "
        "sort_order INTEGER NOT NULL DEFAULT 0)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS user_departments ("
        "user_id INTEGER NOT NULL, "
        "department_id INTEGER NOT NULL, "
        "PRIMARY KEY (user_id, department_id), "
        "FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE, "
        "FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS programs ("
        "code TEXT PRIMARY KEY, "
        "name TEXT NOT NULL)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS permissions ("
        "code TEXT PRIMARY KEY, "
        "label TEXT NOT NULL, "
        "group_name TEXT NOT NULL, "
        "route TEXT NOT NULL, "
        "sort_order INTEGER NOT NULL DEFAULT 0)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS department_permissions ("
        "department_id INTEGER NOT NULL, "
        "permission_code TEXT NOT NULL, "
        "PRIMARY KEY (department_id, permission_code), "
        "FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE, "
        "FOREIGN KEY (permission_code) REFERENCES permissions(code) ON DELETE CASCADE)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS user_program_scopes ("
        "user_id INTEGER NOT NULL, "
        "program_code TEXT NOT NULL, "
        "PRIMARY KEY (user_id, program_code), "
        "FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS user_campus_scopes ("
        "user_id INTEGER NOT NULL, "
        "campus_code TEXT NOT NULL, "
        "PRIMARY KEY (user_id, campus_code), "
        "FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS user_permissions ("
        "user_id INTEGER NOT NULL, "
        "permission_code TEXT NOT NULL, "
        "PRIMARY KEY (user_id, permission_code), "
        "FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE, "
        "FOREIGN KEY (permission_code) REFERENCES permissions(code) ON DELETE CASCADE)"
    )


def seed_departments_and_users(conn) -> dict:
    """Idempotent seed: departments, users, permissions, scopes."""
    cur = conn.cursor()
    ensure_rbac_tables(cur)
    created = {
        "departments": 0,
        "users": 0,
        "memberships": 0,
        "permissions": 0,
        "dept_perms": 0,
        "scopes": 0,
        "renamed_logins": 0,
        "passwords_reset": 0,
    }

    created["renamed_logins"] = _migrate_accented_usernames(cur)

    for code, name in PROGRAMS:
        cur.execute(
            "INSERT INTO programs (code, name) VALUES (?, ?) "
            "ON CONFLICT(code) DO UPDATE SET name = excluded.name",
            (code, name),
        )

    for m in MENU_ITEMS:
        cur.execute(
            "INSERT INTO permissions (code, label, group_name, route, sort_order) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(code) DO UPDATE SET "
            "label = excluded.label, group_name = excluded.group_name, "
            "route = excluded.route, sort_order = excluded.sort_order",
            (m["code"], m["label"], m["group"], m["route"], m["sort"]),
        )
        created["permissions"] += 1

    dept_ids: dict[str, int] = {}
    for code, name, sort_order in DEPARTMENTS:
        cur.execute("SELECT id FROM departments WHERE code = ?", (code,))
        row = cur.fetchone()
        if row:
            dept_ids[code] = row[0]
            cur.execute(
                "UPDATE departments SET name = ?, sort_order = ? WHERE id = ?",
                (name, sort_order, row[0]),
            )
        else:
            cur.execute(
                "INSERT INTO departments (code, name, sort_order) VALUES (?, ?, ?)",
                (code, name, sort_order),
            )
            dept_ids[code] = cur.lastrowid
            created["departments"] += 1

    # Seed department permissions:
    # - most depts: additive only (preserve manual grants)
    # - it / admin_he_thong: force-sync to defaults (gỡ ALL-menu cũ)
    for code, perm_codes in DEPT_DEFAULT_PERMISSIONS.items():
        dept_id = dept_ids.get(code)
        if not dept_id:
            continue
        want = list(perm_codes)
        if code in DEPT_PERMISSIONS_FORCE_SYNC:
            cur.execute(
                "DELETE FROM department_permissions WHERE department_id = ?",
                (dept_id,),
            )
            for pcode in want:
                cur.execute(
                    "INSERT OR IGNORE INTO department_permissions "
                    "(department_id, permission_code) VALUES (?, ?)",
                    (dept_id, pcode),
                )
                created["dept_perms"] += 1
            continue
        for pcode in want:
            cur.execute(
                "SELECT 1 FROM department_permissions WHERE department_id = ? AND permission_code = ?",
                (dept_id, pcode),
            )
            if cur.fetchone():
                continue
            cur.execute(
                "INSERT OR IGNORE INTO department_permissions (department_id, permission_code) "
                "VALUES (?, ?)",
                (dept_id, pcode),
            )
            created["dept_perms"] += 1

    for full_name, title, dept_codes, is_admin in STAFF:
        username = make_username(full_name)
        login = username
        display_name = f"{full_name} — {title}" if title else full_name

        cur.execute("SELECT id FROM user WHERE email = ?", (login,))
        row = cur.fetchone()
        if not row:
            # Match staff already seeded under accented login / same full name
            cur.execute(
                "SELECT id, email FROM user WHERE name LIKE ?",
                (full_name + "%",),
            )
            row = cur.fetchone()

        if row:
            user_id = row[0]
            # Keep login/name in sync; optionally reset temp password (server default)
            if _reset_staff_passwords_enabled():
                cur.execute(
                    "UPDATE user SET email = ?, name = ?, password = ?, is_locked = 0 WHERE id = ?",
                    (login, display_name, TEMP_PASSWORD, user_id),
                )
                created["passwords_reset"] = created.get("passwords_reset", 0) + 1
            else:
                cur.execute(
                    "UPDATE user SET email = ?, name = ? WHERE id = ?",
                    (login, display_name, user_id),
                )
            if is_admin:
                cur.execute("UPDATE user SET is_admin = 1 WHERE id = ?", (user_id,))
        else:
            cur.execute(
                "INSERT INTO user (name, email, password, is_admin, is_locked) VALUES (?, ?, ?, ?, 0)",
                (display_name, login, TEMP_PASSWORD, 1 if is_admin else 0),
            )
            user_id = cur.lastrowid
            created["users"] += 1

        # Add missing STAFF memberships only (do not remove admin-assigned depts)
        for dcode in dept_codes:
            dept_id = dept_ids[dcode]
            cur.execute(
                "SELECT 1 FROM user_departments WHERE user_id = ? AND department_id = ?",
                (user_id, dept_id),
            )
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO user_departments (user_id, department_id) VALUES (?, ?)",
                    (user_id, dept_id),
                )
                created["memberships"] += 1

        # Program scopes: seed if empty; sync forced overrides from USER_PROGRAM_SCOPES
        # Kế toán thuần (LoanBT): * mọi CT. Kèm ĐP (HanhNT): USER_PROGRAM_SCOPES = MBA;
        # API tài chính vẫn mở * nhờ ops_policy.scopes_for_perm.
        cur.execute(
            "SELECT COUNT(*) FROM user_program_scopes WHERE user_id = ?",
            (user_id,),
        )
        existing_scope_count = cur.fetchone()[0]
        forced = USER_PROGRAM_SCOPES.get(username)
        if "ke_toan" in dept_codes and not (
            set(dept_codes) & {"mba", "master_chuyen_nganh"}
        ):
            forced = ["*"]
        if forced is not None:
            cur.execute(
                "SELECT program_code FROM user_program_scopes WHERE user_id = ?",
                (user_id,),
            )
            current = sorted(r[0] for r in cur.fetchall())
            want = sorted(forced)
            if current != want:
                cur.execute(
                    "DELETE FROM user_program_scopes WHERE user_id = ?",
                    (user_id,),
                )
                for sc in forced:
                    cur.execute(
                        "INSERT INTO user_program_scopes (user_id, program_code) VALUES (?, ?)",
                        (user_id, sc),
                    )
                    created["scopes"] += 1
        elif existing_scope_count == 0:
            scopes = []
            for dcode in dept_codes:
                scopes.extend(DEPT_DEFAULT_PROGRAM_SCOPES.get(dcode, []))
            seen = set()
            scopes = [s for s in scopes if not (s in seen or seen.add(s))]
            # Nếu có cả ke_toan + mba: ưu tiên * (đã xử lý ở nhánh trên); giữ dedupe
            if "*" in scopes:
                scopes = ["*"]
            for sc in scopes:
                cur.execute(
                    "INSERT INTO user_program_scopes (user_id, program_code) VALUES (?, ?)",
                    (user_id, sc),
                )
                created["scopes"] += 1

        campus_want = USER_CAMPUS_SCOPES.get(username)
        if campus_want is not None:
            cur.execute(
                "SELECT campus_code FROM user_campus_scopes WHERE user_id = ?",
                (user_id,),
            )
            current_campus = sorted(r[0] for r in cur.fetchall())
            if current_campus != sorted(campus_want):
                cur.execute(
                    "DELETE FROM user_campus_scopes WHERE user_id = ?",
                    (user_id,),
                )
                for campus in campus_want:
                    cur.execute(
                        "INSERT INTO user_campus_scopes (user_id, campus_code) VALUES (?, ?)",
                        (user_id, campus),
                    )

    # Dedicated Admin login(s): Admin / 123!
    # Always ensure password + unlock for these accounts (even if RESET_STAFF_PASSWORDS=false),
    # so Admin never becomes unreachable on server after volume/password drift.
    for acc in ADMIN_ACCOUNTS:
        login = acc["login"]
        cur.execute("SELECT id FROM user WHERE lower(email) = lower(?)", (login,))
        row = cur.fetchone()
        if row:
            user_id = row[0]
            cur.execute(
                "UPDATE user SET name = ?, password = ?, is_admin = ?, is_locked = 0 WHERE id = ?",
                (
                    acc["name"],
                    acc.get("password") or TEMP_PASSWORD,
                    1 if acc.get("is_admin") else 0,
                    user_id,
                ),
            )
            created["passwords_reset"] = created.get("passwords_reset", 0) + 1
            print(
                f"[SEED] Admin ensured: login={login} password={TEMP_PASSWORD} "
                f"(force reset + unlock)"
            )
        else:
            cur.execute(
                "INSERT INTO user (name, email, password, is_admin, is_locked) VALUES (?, ?, ?, ?, 0)",
                (
                    acc["name"],
                    login,
                    acc.get("password") or TEMP_PASSWORD,
                    1 if acc.get("is_admin") else 0,
                ),
            )
            user_id = cur.lastrowid
            created["users"] += 1
            print(
                f"[SEED] Admin created: login={login} password={TEMP_PASSWORD}"
            )

        want_depts = list(acc.get("departments") or [])
        if acc.get("sync_departments"):
            cur.execute(
                "SELECT d.code FROM departments d "
                "JOIN user_departments ud ON ud.department_id = d.id "
                "WHERE ud.user_id = ?",
                (user_id,),
            )
            have = {r[0] for r in cur.fetchall()}
            want_set = set(want_depts)
            for drop in have - want_set:
                did = dept_ids.get(drop)
                if did:
                    cur.execute(
                        "DELETE FROM user_departments WHERE user_id = ? AND department_id = ?",
                        (user_id, did),
                    )
            for dcode in want_depts:
                dept_id = dept_ids.get(dcode)
                if not dept_id:
                    continue
                cur.execute(
                    "SELECT 1 FROM user_departments WHERE user_id = ? AND department_id = ?",
                    (user_id, dept_id),
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO user_departments (user_id, department_id) VALUES (?, ?)",
                        (user_id, dept_id),
                    )
                    created["memberships"] += 1
        else:
            for dcode in want_depts:
                dept_id = dept_ids.get(dcode)
                if not dept_id:
                    continue
                cur.execute(
                    "SELECT 1 FROM user_departments WHERE user_id = ? AND department_id = ?",
                    (user_id, dept_id),
                )
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO user_departments (user_id, department_id) VALUES (?, ?)",
                        (user_id, dept_id),
                    )
                    created["memberships"] += 1

        want_perms = list(acc.get("direct_permissions") or [])
        if acc.get("sync_permissions"):
            cur.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
            for pcode in want_perms:
                cur.execute(
                    "INSERT OR IGNORE INTO user_permissions (user_id, permission_code) "
                    "VALUES (?, ?)",
                    (user_id, pcode),
                )
        else:
            for pcode in want_perms:
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO user_permissions "
                        "(user_id, permission_code) VALUES (?, ?)",
                        (user_id, pcode),
                    )
                except Exception:
                    pass

        # Program scopes for dedicated admins — sync exact when listed
        want_scopes = list(acc.get("program_scopes") or [])
        if want_scopes:
            cur.execute(
                "SELECT program_code FROM user_program_scopes WHERE user_id = ?",
                (user_id,),
            )
            current = sorted(r[0] for r in cur.fetchall())
            want = sorted(want_scopes)
            if current != want:
                cur.execute(
                    "DELETE FROM user_program_scopes WHERE user_id = ?",
                    (user_id,),
                )
                for sc in want_scopes:
                    cur.execute(
                        "INSERT INTO user_program_scopes (user_id, program_code) "
                        "VALUES (?, ?)",
                        (user_id, sc),
                    )
                    created["scopes"] = created.get("scopes", 0) + 1

    # Legacy personal email → ensure ThaoP system admin flag if present
    try:
        cur.execute(
            "UPDATE user SET is_admin = 1, is_locked = 0 WHERE lower(email) IN (?, ?)",
            ("thaofami@gmail.com", "thaop@neu.edu.vn"),
        )
    except Exception:
        pass

    # Ép toàn bộ user sang theme xanh NEU AI
    try:
        cur.execute(
            "UPDATE user SET theme = 'courses', theme_manual = 0 "
            "WHERE COALESCE(theme, '') != 'courses' OR COALESCE(theme_manual, 0) != 0"
        )
    except Exception:
        pass

    conn.commit()
    return created


def get_user_access(conn, user_id: int) -> dict:
    """Resolve departments, permissions, program scopes for a user."""
    cur = conn.cursor()
    ensure_rbac_tables(cur)
    cur.execute(
        "SELECT d.id, d.code, d.name FROM departments d "
        "JOIN user_departments ud ON ud.department_id = d.id "
        "WHERE ud.user_id = ? ORDER BY d.sort_order",
        (user_id,),
    )
    departments = [{"id": r[0], "code": r[1], "name": r[2]} for r in cur.fetchall()]

    cur.execute(
        "SELECT DISTINCT p.code, p.label, p.group_name, p.route, p.sort_order "
        "FROM permissions p "
        "JOIN department_permissions dp ON dp.permission_code = p.code "
        "JOIN user_departments ud ON ud.department_id = dp.department_id "
        "WHERE ud.user_id = ? "
        "ORDER BY p.sort_order",
        (user_id,),
    )
    perm_by_code: dict[str, dict] = {}
    for r in cur.fetchall():
        perm_by_code[r[0]] = {
            "code": r[0],
            "label": r[1],
            "group": r[2],
            "route": r[3],
            "sort": r[4],
        }

    # Direct user grants (admin overrides / extras)
    cur.execute(
        "SELECT p.code, p.label, p.group_name, p.route, p.sort_order "
        "FROM permissions p "
        "JOIN user_permissions up ON up.permission_code = p.code "
        "WHERE up.user_id = ? "
        "ORDER BY p.sort_order",
        (user_id,),
    )
    direct_codes = []
    for r in cur.fetchall():
        direct_codes.append(r[0])
        if r[0] not in perm_by_code:
            perm_by_code[r[0]] = {
                "code": r[0],
                "label": r[1],
                "group": r[2],
                "route": r[3],
                "sort": r[4],
            }

    cur.execute("SELECT is_admin FROM user WHERE id = ?", (user_id,))
    row = cur.fetchone()
    is_admin = bool(row[0]) if row else False
    if is_admin:
        cur.execute(
            "SELECT code, label, group_name, route, sort_order FROM permissions ORDER BY sort_order"
        )
        perm_by_code = {
            r[0]: {
                "code": r[0],
                "label": r[1],
                "group": r[2],
                "route": r[3],
                "sort": r[4],
            }
            for r in cur.fetchall()
        }

    permissions = sorted(perm_by_code.values(), key=lambda p: p.get("sort", 0))

    cur.execute(
        "SELECT program_code FROM user_program_scopes WHERE user_id = ?",
        (user_id,),
    )
    scopes = [r[0] for r in cur.fetchall()]
    cur.execute(
        "SELECT campus_code FROM user_campus_scopes WHERE user_id = ? ORDER BY campus_code",
        (user_id,),
    )
    campus_scopes = [r[0] for r in cur.fetchall()]

    # Mau file MMS: giao diện tiếng Anh cho LinhTK và LinhLT.
    email_row = cur.execute("SELECT email FROM user WHERE id = ?", (user_id,)).fetchone()
    login = ((email_row[0] if email_row else "") or "").strip().lower()
    dept_code_set = {d["code"] for d in departments}
    # Quản lý chương trình MBA dùng giao diện tiếng Anh. MMS giữ ngoại lệ login đã có.
    lang = "en" if dept_code_set == {"mba"} or login in {"linhtk", "linhlt"} else "vi"

    # Theme: stored preference wins; else gender default; else role default
    gender = ""
    theme_manual = 0
    stored_theme = None
    try:
        prow = cur.execute(
            "SELECT gender, theme, theme_manual, birth_year, avatar_path "
            "FROM user WHERE id = ?",
            (user_id,),
        ).fetchone()
        if prow:
            gender = (prow[0] or "").strip().upper()
            stored_theme = (prow[1] or "").strip() or None
            theme_manual = int(prow[2] or 0)
            birth_year = prow[3]
            avatar_path = prow[4]
        else:
            birth_year = None
            avatar_path = None
    except Exception:
        birth_year = None
        avatar_path = None

    # Toàn bộ chức năng dùng theme xanh NEU AI (courses)
    theme = "courses"

    return {
        "departments": departments,
        "permissions": permissions,
        "permission_codes": [p["code"] for p in permissions],
        "direct_permission_codes": direct_codes,
        "program_scopes": scopes,
        "campus_scopes": campus_scopes,
        "is_admin": is_admin,
        "lang": lang,
        "theme": theme,
        "theme_manual": bool(theme_manual),
        "gender": gender or None,
        "birth_year": birth_year,
        "avatar_path": avatar_path,
    }
