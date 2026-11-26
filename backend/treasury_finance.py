"""Kế hoạch thu, hỗ trợ, hoàn phí và hồ sơ xuất hóa đơn — gắn sổ student_charges."""
from __future__ import annotations

from datetime import datetime


REFUND_REASONS = {
    "withdraw_before_start": "Rút hồ sơ trước khai giảng",
    "class_not_opened": "Không đủ điều kiện mở lớp",
    "dropout": "Thôi học",
    "bgd_decision": "Quyết định Ban Giám đốc",
    "program_transfer": "Chuyển chương trình hoặc khóa",
    "wrong_payment": "Thu nhầm, nghĩa vụ vẫn còn",
}

BENEFIT_TYPES = {"scholarship", "discount", "aid"}


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _cols(cur, table: str) -> set[str]:
    try:
        return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def _audit(cur, *, actor: str, action: str, entity: str, entity_id, detail: str) -> None:
    if "ops_audit_log" not in {
        r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }:
        return
    user_id = None
    raw = str(actor or "")
    if raw.startswith("user:"):
        try:
            user_id = int(raw.split(":", 1)[1])
        except ValueError:
            user_id = None
    cur.execute(
        "INSERT INTO ops_audit_log (created_at, actor, user_id, action, entity, entity_id, detail) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (_now(), actor, user_id, action, entity, str(entity_id), detail[:500]),
    )


def _reject_self(created_by: str, actor: str) -> None:
    if str(created_by or "") and str(created_by) == str(actor or ""):
        raise ValueError("Người lập không tự duyệt hồ sơ này.")


def ensure_finance_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS fee_plans ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "program_code TEXT NOT NULL, "
        "intake TEXT NOT NULL, "
        "campus TEXT DEFAULT '', "
        "currency TEXT NOT NULL DEFAULT 'VND', "
        "title TEXT, "
        "status TEXT NOT NULL DEFAULT 'draft', "
        "notes TEXT, "
        "created_by TEXT, "
        "approved_by TEXT, "
        "created_at TEXT, "
        "approved_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS fee_plan_lines ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "plan_id INTEGER NOT NULL, "
        "fee_type TEXT NOT NULL, "
        "installment_no INTEGER NOT NULL, "
        "title TEXT NOT NULL, "
        "amount REAL NOT NULL, "
        "due_date TEXT, "
        "UNIQUE(plan_id, fee_type, installment_no))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS financial_benefits ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "benefit_type TEXT NOT NULL, "
        "effect TEXT NOT NULL, "
        "application_id INTEGER, "
        "class_student_id INTEGER, "
        "charge_id INTEGER, "
        "program_code TEXT, "
        "intake TEXT, "
        "student_code TEXT, "
        "full_name TEXT, "
        "basis TEXT, "
        "basis_value REAL, "
        "amount REAL NOT NULL DEFAULT 0, "
        "currency TEXT DEFAULT 'VND', "
        "status TEXT NOT NULL DEFAULT 'proposed', "
        "decision_note TEXT, "
        "beneficiary_account TEXT, "
        "beneficiary_bank TEXT, "
        "payer_method_used TEXT, "
        "adjustment_id INTEGER, "
        "created_by TEXT, "
        "approved_by TEXT, "
        "created_at TEXT, "
        "approved_at TEXT, "
        "applied_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS refund_cases ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "charge_id INTEGER NOT NULL, "
        "application_id INTEGER, "
        "program_code TEXT, "
        "student_code TEXT, "
        "full_name TEXT, "
        "reason_code TEXT NOT NULL, "
        "reason_note TEXT, "
        "amount_requested REAL NOT NULL, "
        "amount_approved REAL, "
        "amount_disbursed REAL, "
        "reduce_obligation INTEGER NOT NULL DEFAULT 0, "
        "status TEXT NOT NULL DEFAULT 'proposed', "
        "payee_name TEXT, "
        "payee_account TEXT, "
        "payee_bank TEXT, "
        "adjustment_id INTEGER, "
        "reversal_payment_id INTEGER, "
        "created_by TEXT, "
        "approved_by TEXT, "
        "disbursed_by TEXT, "
        "created_at TEXT, "
        "approved_at TEXT, "
        "disbursed_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS billing_profiles ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "application_id INTEGER, "
        "party_type TEXT NOT NULL, "
        "full_name TEXT, "
        "intake TEXT, "
        "company_name TEXT, "
        "tax_code TEXT, "
        "address TEXT, "
        "cccd TEXT, "
        "phone TEXT, "
        "email TEXT, "
        "note TEXT, "
        "program_code TEXT, "
        "is_current INTEGER NOT NULL DEFAULT 1, "
        "created_by TEXT, "
        "created_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS bank_statement_lines ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "txn_code TEXT, "
        "amount REAL, "
        "paid_at TEXT, "
        "payer_name TEXT, "
        "identity_number TEXT, "
        "program_code TEXT, "
        "fee_type TEXT, "
        "match_status TEXT NOT NULL DEFAULT 'unmatched', "
        "charge_id INTEGER, "
        "receipt_id INTEGER, "
        "note TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    if "program_code" not in _cols(cur, "bank_statement_lines"):
        cur.execute("ALTER TABLE bank_statement_lines ADD COLUMN program_code TEXT")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS fee_intake_plans ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "program_code TEXT NOT NULL, "
        "intake_code TEXT NOT NULL, "
        "fee_type TEXT NOT NULL, "
        "installment_no INTEGER NOT NULL, "
        "title TEXT NOT NULL, "
        "amount_due REAL NOT NULL, "
        "due_date TEXT, "
        "due_offset_days INTEGER, "
        "currency TEXT NOT NULL DEFAULT 'VND', "
        "status TEXT NOT NULL DEFAULT 'active', "
        "UNIQUE(program_code, intake_code, fee_type, installment_no))"
    )
    if "study_year" not in _cols(cur, "fee_intake_plans"):
        try:
            cur.execute("ALTER TABLE fee_intake_plans ADD COLUMN study_year INTEGER")
        except Exception:
            pass
    cur.execute(
        "CREATE TABLE IF NOT EXISTS payment_allocations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "payment_id INTEGER NOT NULL, "
        "charge_id INTEGER NOT NULL, "
        "amount REAL NOT NULL, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    cur.execute(
        "INSERT INTO payment_allocations (payment_id, charge_id, amount) "
        "SELECT p.id, p.charge_id, p.amount FROM fee_payments p "
        "WHERE p.charge_id IS NOT NULL AND NOT EXISTS ("
        "SELECT 1 FROM payment_allocations a WHERE a.payment_id = p.id)"
    )
    tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "payment_methods" in tables:
        for code, vi, en, sort in (
            ("pos", "POS", "POS", 5),
            ("qr", "QR", "QR", 6),
        ):
            cur.execute(
                "INSERT INTO payment_methods (code, label, label_en, sort_order, status) "
                "VALUES (?, ?, ?, ?, 'active') ON CONFLICT(code) DO NOTHING",
                (code, vi, en, sort),
            )


def _scope_sql(scopes, column: str) -> tuple[str, list]:
    from ops_data import _scopes_sql

    return _scopes_sql(scopes, column)


def _charge_context(cur, charge_id: int) -> dict:
    row = cur.execute(
        "SELECT sc.id, sc.application_id, sc.class_student_id, sc.program_code, "
        "sc.amount_due, sc.amount_paid, sc.amount_adjust, sc.fee_type, "
        "COALESCE(cs.student_code, ''), COALESCE(cs.full_name, a.full_name, ''), "
        "COALESCE(r.intake, ''), COALESCE(sc.currency, 'VND') "
        "FROM student_charges sc "
        "LEFT JOIN applications a ON a.id = sc.application_id "
        "LEFT JOIN class_students cs ON cs.id = sc.class_student_id "
        "LEFT JOIN admission_rounds r ON r.id = a.round_id "
        "WHERE sc.id = ?",
        (charge_id,),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy khoản phải thu.")
    due = float(row[4] or 0)
    paid = float(row[5] or 0)
    adj = float(row[6] or 0)
    return {
        "id": row[0],
        "application_id": row[1],
        "class_student_id": row[2],
        "program_code": row[3],
        "amount_due": due,
        "amount_paid": paid,
        "actual_due": max(0.0, due + adj),
        "fee_type": row[7],
        "student_code": row[8],
        "full_name": row[9],
        "intake": row[10],
        "currency": row[11] or "VND",
    }


def list_payment_plans(conn, scopes) -> list[dict]:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    frag, params = _scope_sql(scopes, "program_code")
    rows = cur.execute(
        f"SELECT id, program_code, intake, campus, currency, title, status, notes, created_by "
        f"FROM fee_plans WHERE {frag} ORDER BY id DESC",
        params,
    ).fetchall()
    out = []
    for r in rows:
        lines = cur.execute(
            "SELECT fee_type, installment_no, title, amount, due_date "
            "FROM fee_plan_lines WHERE plan_id = ? ORDER BY installment_no, id",
            (r[0],),
        ).fetchall()
        label = " · ".join(
            f"{ln[0]} đợt {ln[1]}: {ln[3]:g}" + (f" hạn {ln[4]}" if ln[4] else "")
            for ln in lines[:6]
        )
        out.append(
            {
                "id": r[0],
                "program_code": r[1],
                "intake": r[2],
                "campus": r[3] or "",
                "currency": r[4] or "VND",
                "title": r[5] or "",
                "status": r[6],
                "notes": r[7] or "",
                "created_by": r[8] or "",
                "line_count": len(lines),
                "lines_label": label,
            }
        )
    return out


def create_payment_plan(conn, data: dict, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    program = (data.get("program_code") or "").strip().upper()
    intake = (data.get("intake") or "").strip()
    if not program or not intake:
        raise ValueError("Cần chương trình và Intake.")
    currency = (data.get("currency") or "VND").strip().upper() or "VND"
    cur.execute(
        "INSERT INTO fee_plans (program_code, intake, campus, currency, title, status, notes, created_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?)",
        (
            program,
            intake,
            (data.get("campus") or "").strip(),
            currency,
            (data.get("title") or f"Kế hoạch {program} {intake}").strip(),
            (data.get("notes") or "").strip(),
            actor,
            _now(),
        ),
    )
    plan_id = cur.lastrowid
    _audit(cur, actor=actor, action="create", entity="fee_plans", entity_id=plan_id, detail=f"{program} {intake} {currency}")
    conn.commit()
    return {"id": plan_id, "status": "draft"}


def add_plan_line(conn, plan_id: int, data: dict, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    plan = cur.execute("SELECT id, status FROM fee_plans WHERE id = ?", (plan_id,)).fetchone()
    if not plan:
        raise ValueError("Không tìm thấy kế hoạch thu.")
    if plan[1] != "draft":
        raise ValueError("Kế hoạch đã duyệt. Lập phiên bản mới thay vì sửa đợt đã chốt.")
    fee_type = (data.get("fee_type") or "").strip()
    title = (data.get("title") or "").strip()
    try:
        installment = int(data.get("installment_no") or 0)
        amount = float(data.get("amount") or 0)
    except (TypeError, ValueError):
        raise ValueError("Số đợt hoặc số tiền không hợp lệ.") from None
    if not fee_type or not title or amount < 0 or installment < 0:
        raise ValueError("Cần loại khoản, nội dung, số đợt và số tiền.")
    exists = cur.execute(
        "SELECT id FROM fee_plan_lines WHERE plan_id = ? AND fee_type = ? AND installment_no = ?",
        (plan_id, fee_type, installment),
    ).fetchone()
    if exists:
        raise ValueError("Đợt này đã có trong kế hoạch. Không tạo khoản trùng.")
    cur.execute(
        "INSERT INTO fee_plan_lines (plan_id, fee_type, installment_no, title, amount, due_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (plan_id, fee_type, installment, title, amount, (data.get("due_date") or "").strip() or None),
    )
    _audit(cur, actor=actor, action="add_line", entity="fee_plans", entity_id=plan_id, detail=f"{fee_type} #{installment}")
    conn.commit()
    return {"id": cur.lastrowid, "plan_id": plan_id}


def approve_payment_plan(conn, plan_id: int, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    row = cur.execute(
        "SELECT status, created_by, (SELECT COUNT(*) FROM fee_plan_lines WHERE plan_id = fee_plans.id) "
        "FROM fee_plans WHERE id = ?",
        (plan_id,),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy kế hoạch thu.")
    if row[0] != "draft":
        raise ValueError("Chỉ duyệt kế hoạch đang ở trạng thái nháp.")
    if not row[2]:
        raise ValueError("Kế hoạch chưa có đợt thanh toán.")
    _reject_self(row[1], actor)
    cur.execute(
        "UPDATE fee_plans SET status = 'approved', approved_by = ?, approved_at = ? WHERE id = ?",
        (actor, _now(), plan_id),
    )
    _audit(cur, actor=actor, action="approve", entity="fee_plans", entity_id=plan_id, detail="approved")
    conn.commit()
    return {"id": plan_id, "status": "approved"}


def _matching_applications(cur, plan, application_id: int | None) -> list:
    program, intake, campus = plan[1], plan[2], (plan[3] or "").strip()
    intake_l = intake.strip().lower()
    sql = (
        "SELECT a.id FROM applications a "
        "JOIN admission_rounds r ON r.id = a.round_id "
        "WHERE a.program_code = ? AND a.status = 'official' AND ("
        "lower(COALESCE(r.intake,'')) = ? OR lower(COALESCE(r.code,'')) = ? "
        "OR lower(COALESCE(r.name,'')) LIKE ?)"
    )
    params: list = [program, intake_l, intake_l, f"%{intake_l}%"]
    if application_id:
        sql += " AND a.id = ?"
        params.append(application_id)
    app_cols = _cols(cur, "applications")
    rows = cur.execute(sql, params).fetchall()
    if campus and "campus" in app_cols:
        kept = []
        for (app_id,) in rows:
            got = cur.execute("SELECT campus FROM applications WHERE id = ?", (app_id,)).fetchone()
            if (got[0] or "").strip().lower() == campus.lower():
                kept.append((app_id,))
        return kept
    return rows


def _apply_flat_intake(conn, application_id: int) -> dict:
    """Đợt trên màn Kế hoạch thu theo khóa (status active). Không tạo đợt đã có."""
    cur = conn.cursor()
    ensure_finance_tables(cur)
    app = cur.execute(
        "SELECT a.program_code, COALESCE(r.intake,''), COALESCE(r.code,''), COALESCE(r.name,'') "
        "FROM applications a JOIN admission_rounds r ON r.id = a.round_id WHERE a.id = ?",
        (application_id,),
    ).fetchone()
    if not app:
        return {"matched": False, "created": 0}
    keys = {str(x or "").strip().lower() for x in app[1:] if str(x or "").strip()}
    lines = cur.execute(
        "SELECT fee_type, installment_no, title, amount_due, due_date, due_offset_days, "
        "COALESCE(currency, 'VND'), intake_code, IFNULL(study_year,'') "
        "FROM fee_intake_plans WHERE program_code = ? AND status = 'active' "
        "ORDER BY installment_no, id",
        (app[0],),
    ).fetchall()
    chosen = []
    for line in lines:
        code = str(line[7] or "").strip().lower()
        if code in ("*", "") or code in keys:
            chosen.append(line)
    if not chosen:
        return {"matched": False, "created": 0}
    created = 0
    today = datetime.now().date()
    for fee_type, installment_no, title, amount, due_date, offset_days, currency, intake_code, study_year in chosen:
        exists = cur.execute(
            "SELECT id FROM student_charges WHERE application_id = ? AND fee_type = ? "
            "AND COALESCE(installment_no, 0) = ?",
            (application_id, fee_type, int(installment_no)),
        ).fetchone()
        if exists:
            continue
        due = (due_date or "").strip()
        if not due:
            try:
                offset = int(offset_days or 0)
            except (TypeError, ValueError):
                offset = 0
            due = (today.fromordinal(today.toordinal() + max(offset, 0))).isoformat()
        cur.execute(
            "INSERT INTO student_charges ("
            "application_id, program_code, fee_type, title, amount_due, amount_paid, "
            "amount_adjust, due_date, status, installment_no, notes, currency, intake, study_year"
            ") VALUES (?, ?, ?, ?, ?, 0, 0, ?, 'pending', ?, ?, ?, ?, ?)",
            (
                application_id,
                app[0],
                fee_type,
                title,
                float(amount or 0),
                due,
                int(installment_no),
                f"Kế hoạch khóa {intake_code}",
                currency or "VND",
                intake_code,
                study_year or None,
            ),
        )
        created += 1
    conn.commit()
    return {"matched": True, "created": created, "stage": "official", "application_id": application_id}


def apply_intake_plan(conn, *, application_id: int | None = None, plan_id: int | None = None) -> dict:
    """Sinh khoản phải thu từ kế hoạch đã chốt. Bỏ qua đợt đã có. Không đụng khoản đã thu."""
    if application_id and not plan_id:
        flat = _apply_flat_intake(conn, application_id)
        if flat.get("matched"):
            return flat
    cur = conn.cursor()
    ensure_finance_tables(cur)
    if plan_id:
        plans = cur.execute(
            "SELECT id, program_code, intake, campus, currency, status FROM fee_plans WHERE id = ?",
            (plan_id,),
        ).fetchall()
    elif application_id:
        app = cur.execute(
            "SELECT a.program_code, COALESCE(r.intake,''), COALESCE(r.code,''), COALESCE(r.name,'') "
            "FROM applications a JOIN admission_rounds r ON r.id = a.round_id WHERE a.id = ?",
            (application_id,),
        ).fetchone()
        if not app:
            return {"matched": False, "created": 0}
        keys = [str(x or "").strip().lower() for x in app[1:]]
        plans = [
            p
            for p in cur.execute(
                "SELECT id, program_code, intake, campus, currency, status FROM fee_plans "
                "WHERE status = 'approved' AND program_code = ?",
                (app[0],),
            ).fetchall()
            if str(p[2] or "").strip().lower() in keys or any(str(p[2] or "").strip().lower() in k for k in keys if k)
        ]
    else:
        plans = []
    if not plans:
        return {"matched": False, "created": 0, "stage": "official"}
    plan = plans[0]
    if plan[5] != "approved":
        raise ValueError("Chỉ áp dụng kế hoạch đã được người khác duyệt.")
    lines = cur.execute(
        "SELECT fee_type, installment_no, title, amount, due_date FROM fee_plan_lines WHERE plan_id = ? "
        "ORDER BY installment_no, id",
        (plan[0],),
    ).fetchall()
    apps = _matching_applications(cur, plan, application_id)
    if application_id and not apps:
        return {"matched": False, "created": 0, "stage": "official"}
    created = 0
    for (app_id,) in apps:
        for fee_type, installment_no, title, amount, due_date in lines:
            exists = cur.execute(
                "SELECT id FROM student_charges WHERE application_id = ? AND fee_type = ? "
                "AND COALESCE(installment_no, 0) = ?",
                (app_id, fee_type, int(installment_no)),
            ).fetchone()
            if exists:
                continue
            cur.execute(
                "INSERT INTO student_charges ("
                "application_id, program_code, fee_type, title, amount_due, amount_paid, "
                "amount_adjust, due_date, status, installment_no, notes, currency, intake"
                ") VALUES (?, ?, ?, ?, ?, 0, 0, ?, 'pending', ?, ?, ?, ?)",
                (
                    app_id,
                    plan[1],
                    fee_type,
                    title,
                    float(amount),
                    due_date,
                    int(installment_no),
                    f"Kế hoạch thu {plan[2]} #{plan[0]}",
                    plan[4] or "VND",
                    plan[2],
                ),
            )
            created += 1
    conn.commit()
    return {
        "matched": True,
        "created": created,
        "plan_id": plan[0],
        "stage": "official",
        "application_id": application_id,
        "currency": plan[4] or "VND",
    }


def list_benefits(conn, scopes) -> list[dict]:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    frag, params = _scope_sql(scopes, "COALESCE(program_code, '')")
    rows = cur.execute(
        "SELECT id, benefit_type, effect, full_name, student_code, program_code, intake, "
        "basis, basis_value, amount, currency, status, decision_note, beneficiary_account, "
        "beneficiary_bank, payer_method_used, charge_id, created_by "
        f"FROM financial_benefits WHERE {frag} ORDER BY id DESC",
        params,
    ).fetchall()
    labels = {
        "scholarship": "Học bổng",
        "discount": "Giảm phí",
        "aid": "Hỗ trợ",
        "reduce": "Giảm nghĩa vụ",
        "disburse": "Chi ra tài khoản",
        "proposed": "Chờ duyệt",
        "approved": "Đã duyệt",
        "applied": "Đã giảm nghĩa vụ",
        "disbursed": "Đã chi",
        "cancelled": "Đã hủy",
    }
    out = []
    for r in rows:
        out.append(
            {
                "id": r[0],
                "benefit_type": labels.get(r[1], r[1]),
                "effect": labels.get(r[2], r[2]),
                "full_name": r[3] or "",
                "student_code": r[4] or "",
                "program_code": r[5] or "",
                "intake": r[6] or "",
                "basis": r[7] or "",
                "basis_value": r[8],
                "amount": r[9],
                "currency": r[10] or "VND",
                "status": labels.get(r[11], r[11]),
                "status_code": r[11],
                "decision_note": r[12] or "",
                "beneficiary_account": r[13] or "",
                "beneficiary_bank": r[14] or "",
                "payer_method_used": r[15] or "",
                "charge_id": r[16],
                "created_by": r[17] or "",
            }
        )
    return out


def create_benefit(conn, data: dict, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    kind = (data.get("benefit_type") or data.get("kind") or "").strip().lower()
    effect = (data.get("effect") or "reduce").strip().lower()
    if kind not in BENEFIT_TYPES:
        raise ValueError("Loại hỗ trợ không hợp lệ.")
    if effect not in ("reduce", "disburse"):
        raise ValueError("Chọn giảm nghĩa vụ hoặc chi ra tài khoản, không ghi cả hai.")
    charge_id = int(data.get("charge_id") or 0)
    ctx = _charge_context(cur, charge_id) if charge_id else None
    if ctx is None:
        raise ValueError("Cần ID khoản phải thu để gắn học bổng, giảm phí hoặc hỗ trợ.")
    open_row = cur.execute(
        "SELECT id, effect FROM financial_benefits WHERE charge_id = ? AND benefit_type = ? "
        "AND status NOT IN ('cancelled')",
        (charge_id, kind),
    ).fetchone()
    if open_row:
        raise ValueError("Khoản này đã có hồ sơ cùng loại. Hủy hồ sơ cũ trước khi lập hồ sơ mới.")
    basis = (data.get("basis") or "fixed").strip().lower()
    if basis not in ("fixed", "percent"):
        basis = "fixed"
    try:
        basis_value = float(data.get("basis_value") if data.get("basis_value") not in (None, "") else data.get("amount") or 0)
    except (TypeError, ValueError):
        raise ValueError("Giá trị không hợp lệ.") from None
    if effect == "reduce" and basis == "percent":
        amount = round(ctx["amount_due"] * basis_value / 100.0, 0)
    else:
        amount = basis_value
    if amount <= 0:
        raise ValueError("Số tiền phải lớn hơn 0.")
    if effect == "reduce" and amount > ctx["actual_due"] + 0.01:
        raise ValueError("Số giảm lớn hơn nghĩa vụ còn lại.")
    if effect == "disburse" and not (data.get("beneficiary_account") or "").strip():
        raise ValueError("Chi ra tài khoản cần số tài khoản thụ hưởng.")
    cur.execute(
        "INSERT INTO financial_benefits ("
        "benefit_type, effect, application_id, class_student_id, charge_id, program_code, intake, "
        "student_code, full_name, basis, basis_value, amount, currency, status, decision_note, "
        "beneficiary_account, beneficiary_bank, payer_method_used, created_by, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', ?, ?, ?, ?, ?, ?)",
        (
            kind,
            effect,
            ctx["application_id"],
            ctx["class_student_id"],
            charge_id,
            ctx["program_code"],
            (data.get("intake") or ctx["intake"] or "").strip(),
            ctx["student_code"],
            ctx["full_name"],
            basis,
            basis_value,
            amount,
            ctx["currency"],
            (data.get("decision_note") or data.get("note") or "").strip(),
            (data.get("beneficiary_account") or "").strip(),
            (data.get("beneficiary_bank") or "").strip(),
            (data.get("payer_method_used") or "").strip(),
            actor,
            _now(),
        ),
    )
    benefit_id = cur.lastrowid
    _audit(
        cur,
        actor=actor,
        action="propose",
        entity="financial_benefits",
        entity_id=benefit_id,
        detail=f"{kind} {effect} {amount}",
    )
    conn.commit()
    return {"id": benefit_id, "status": "proposed", "amount": amount, "effect": effect}


def _benefit_row(cur, benefit_id: int):
    row = cur.execute(
        "SELECT id, status, effect, charge_id, amount, benefit_type, created_by, adjustment_id, decision_note "
        "FROM financial_benefits WHERE id = ?",
        (benefit_id,),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy hồ sơ hỗ trợ.")
    return row


def approve_benefit(conn, benefit_id: int, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    row = _benefit_row(cur, benefit_id)
    if row[1] != "proposed":
        raise ValueError("Chỉ duyệt hồ sơ đang chờ.")
    _reject_self(row[6], actor)
    cur.execute(
        "UPDATE financial_benefits SET status = 'approved', approved_by = ?, approved_at = ? WHERE id = ?",
        (actor, _now(), benefit_id),
    )
    _audit(cur, actor=actor, action="approve", entity="financial_benefits", entity_id=benefit_id, detail="approved")
    conn.commit()
    return {"id": benefit_id, "status": "approved"}


def apply_benefit(conn, benefit_id: int, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    row = _benefit_row(cur, benefit_id)
    if row[1] != "approved":
        raise ValueError("Chỉ áp dụng hồ sơ đã được người khác duyệt.")
    if row[2] != "reduce":
        raise ValueError("Hồ sơ chi ra tài khoản không được ghi giảm nghĩa vụ.")
    if row[7]:
        raise ValueError("Hồ sơ đã áp dụng.")
    from treasury_ops import apply_adjustment

    result = apply_adjustment(
        conn,
        int(row[3]),
        adj_type=row[5],
        amount=float(row[4]),
        decision_note=row[8] or f"Benefit #{benefit_id}",
        created_by=actor,
    )
    cur = conn.cursor()
    cur.execute(
        "UPDATE financial_benefits SET status = 'applied', adjustment_id = ?, applied_at = ? WHERE id = ?",
        (result.get("adjustment_id"), _now(), benefit_id),
    )
    _audit(cur, actor=actor, action="apply", entity="financial_benefits", entity_id=benefit_id, detail="reduce")
    conn.commit()
    return {"id": benefit_id, "status": "applied", "adjustment_id": result.get("adjustment_id")}


def disburse_benefit(conn, benefit_id: int, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    row = _benefit_row(cur, benefit_id)
    if row[1] != "approved":
        raise ValueError("Chỉ chi hồ sơ đã duyệt.")
    if row[2] != "disburse":
        raise ValueError("Hồ sơ giảm nghĩa vụ không chi ra tài khoản.")
    cur.execute(
        "UPDATE financial_benefits SET status = 'disbursed', applied_at = ? WHERE id = ?",
        (_now(), benefit_id),
    )
    _audit(cur, actor=actor, action="disburse", entity="financial_benefits", entity_id=benefit_id, detail="cash out")
    conn.commit()
    return {"id": benefit_id, "status": "disbursed"}


def list_refunds(conn, scopes) -> list[dict]:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    frag, params = _scope_sql(scopes, "COALESCE(program_code, '')")
    rows = cur.execute(
        "SELECT id, full_name, student_code, program_code, reason_code, amount_requested, "
        "amount_approved, amount_disbursed, reduce_obligation, status, payee_name, "
        "payee_account, payee_bank, charge_id, reason_note "
        f"FROM refund_cases WHERE {frag} ORDER BY id DESC",
        params,
    ).fetchall()
    status_vi = {
        "proposed": "Chờ duyệt",
        "approved": "Đã duyệt, chưa chi",
        "disbursed": "Đã chi",
        "cancelled": "Đã hủy",
    }
    return [
        {
            "id": r[0],
            "full_name": r[1] or "",
            "student_code": r[2] or "",
            "program_code": r[3] or "",
            "reason_code": REFUND_REASONS.get(r[4], r[4]),
            "amount_requested": r[5],
            "amount_approved": r[6],
            "amount_disbursed": r[7],
            "reduce_obligation": "Có giảm nghĩa vụ" if r[8] else "Giữ nghĩa vụ",
            "status": status_vi.get(r[9], r[9]),
            "status_code": r[9],
            "payee_name": r[10] or "",
            "payee_account": r[11] or "",
            "payee_bank": r[12] or "",
            "charge_id": r[13],
            "reason_note": r[14] or "",
        }
        for r in rows
    ]


def create_refund(conn, data: dict, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    try:
        charge_id = int(data.get("charge_id") or 0)
        amount = float(data.get("amount") or data.get("amount_requested") or 0)
    except (TypeError, ValueError):
        raise ValueError("Khoản phải thu hoặc số tiền không hợp lệ.") from None
    reason = (data.get("reason_code") or "").strip()
    if reason not in REFUND_REASONS:
        raise ValueError("Chọn lý do hoàn trong danh mục.")
    if amount <= 0:
        raise ValueError("Số đề nghị hoàn phải lớn hơn 0.")
    ctx = _charge_context(cur, charge_id)
    reduce = str(data.get("reduce_obligation") or "0").strip().lower() in ("1", "true", "yes", "có")
    if reason == "wrong_payment":
        reduce = False
    already = cur.execute(
        "SELECT COALESCE(SUM(amount_disbursed), 0) FROM refund_cases "
        "WHERE charge_id = ? AND status = 'disbursed'",
        (charge_id,),
    ).fetchone()[0]
    if float(already or 0) + amount > ctx["amount_paid"] + 0.01:
        raise ValueError("Tổng hoàn vượt số đã thu trên khoản này.")
    cur.execute(
        "INSERT INTO refund_cases ("
        "charge_id, application_id, program_code, student_code, full_name, reason_code, reason_note, "
        "amount_requested, reduce_obligation, status, payee_name, payee_account, payee_bank, "
        "created_by, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', ?, ?, ?, ?, ?)",
        (
            charge_id,
            ctx["application_id"],
            ctx["program_code"],
            ctx["student_code"],
            ctx["full_name"],
            reason,
            (data.get("reason_note") or data.get("note") or "").strip(),
            amount,
            1 if reduce else 0,
            (data.get("payee_name") or ctx["full_name"] or "").strip(),
            (data.get("payee_account") or "").strip(),
            (data.get("payee_bank") or "").strip(),
            actor,
            _now(),
        ),
    )
    refund_id = cur.lastrowid
    _audit(cur, actor=actor, action="propose", entity="refund_cases", entity_id=refund_id, detail=reason)
    conn.commit()
    return {"id": refund_id, "status": "proposed"}


def approve_refund(conn, refund_id: int, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    row = cur.execute(
        "SELECT status, created_by, amount_requested FROM refund_cases WHERE id = ?",
        (refund_id,),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy hồ sơ hoàn.")
    if row[0] != "proposed":
        raise ValueError("Chỉ duyệt hồ sơ đang chờ.")
    _reject_self(row[1], actor)
    cur.execute(
        "UPDATE refund_cases SET status = 'approved', amount_approved = ?, approved_by = ?, approved_at = ? "
        "WHERE id = ?",
        (row[2], actor, _now(), refund_id),
    )
    _audit(cur, actor=actor, action="approve", entity="refund_cases", entity_id=refund_id, detail="approved")
    conn.commit()
    return {"id": refund_id, "status": "approved", "amount_approved": row[2]}


def disburse_refund(conn, refund_id: int, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    row = cur.execute(
        "SELECT status, charge_id, amount_approved, reduce_obligation, reason_note, reason_code "
        "FROM refund_cases WHERE id = ?",
        (refund_id,),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy hồ sơ hoàn.")
    if row[0] != "approved":
        raise ValueError("Đã duyệt chưa đồng nghĩa đã chi. Chỉ chi hồ sơ đang ở trạng thái đã duyệt.")
    amount = float(row[2] or 0)
    charge_id = int(row[1])
    ctx = _charge_context(cur, charge_id)
    already = cur.execute(
        "SELECT COALESCE(SUM(amount_disbursed), 0) FROM refund_cases "
        "WHERE charge_id = ? AND status = 'disbursed'",
        (charge_id,),
    ).fetchone()[0]
    if float(already or 0) + amount > ctx["amount_paid"] + 0.01:
        raise ValueError("Số chi vượt số đã thu còn lại.")
    adjustment_id = None
    reversal_id = None
    if int(row[3] or 0):
        from treasury_ops import apply_adjustment

        result = apply_adjustment(
            conn,
            charge_id,
            adj_type="refund",
            amount=amount,
            decision_note=row[4] or REFUND_REASONS.get(row[5], ""),
            created_by=actor,
        )
        adjustment_id = result.get("adjustment_id")
        cur = conn.cursor()
    else:
        from treasury_ops import _recompute_charge

        cur.execute(
            "INSERT INTO fee_payments (charge_id, amount, paid_at, method, bank_ref, proof_note, created_by) "
            "VALUES (?, ?, ?, 'refund_reversal', ?, ?, ?)",
            (
                charge_id,
                -amount,
                _now()[:10],
                f"refund:{refund_id}",
                "Đảo giao dịch thu nhầm — nghĩa vụ vẫn còn",
                actor,
            ),
        )
        reversal_id = cur.lastrowid
        cur.execute(
            "INSERT INTO payment_allocations (payment_id, charge_id, amount) VALUES (?, ?, ?)",
            (reversal_id, charge_id, -amount),
        )
        _recompute_charge(cur, charge_id)
    cur.execute(
        "UPDATE refund_cases SET status = 'disbursed', amount_disbursed = ?, disbursed_by = ?, "
        "disbursed_at = ?, adjustment_id = ?, reversal_payment_id = ? WHERE id = ?",
        (amount, actor, _now(), adjustment_id, reversal_id, refund_id),
    )
    _audit(cur, actor=actor, action="disburse", entity="refund_cases", entity_id=refund_id, detail=str(amount))
    conn.commit()
    return {"id": refund_id, "status": "disbursed", "amount_disbursed": amount}


def list_billing_profiles(conn, scopes) -> list[dict]:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    frag, params = _scope_sql(scopes, "COALESCE(program_code, '')")
    rows = cur.execute(
        "SELECT id, party_type, full_name, intake, company_name, tax_code, address, cccd, "
        "phone, email, note, program_code, application_id "
        f"FROM billing_profiles WHERE is_current = 1 AND {frag} ORDER BY id DESC",
        params,
    ).fetchall()
    return [
        {
            "id": r[0],
            "party_type": "Doanh nghiệp" if r[1] == "company" else "Cá nhân",
            "full_name": r[2] or "",
            "intake": r[3] or "",
            "company_name": r[4] or "",
            "tax_code": r[5] or "",
            "address": r[6] or "",
            "cccd": r[7] or "",
            "phone": r[8] or "",
            "email": r[9] or "",
            "note": r[10] or "",
            "program_code": r[11] or "",
            "application_id": r[12],
        }
        for r in rows
    ]


def create_billing_profile(conn, data: dict, *, actor: str) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    party = (data.get("party_type") or "").strip().lower()
    if party in ("doanh nghiệp", "company", "dn"):
        party = "company"
    else:
        party = "individual"
    full_name = (data.get("full_name") or "").strip()
    company = (data.get("company_name") or "").strip()
    tax_code = str(data.get("tax_code") or "").strip()
    address = (data.get("address") or "").strip()
    cccd = str(data.get("cccd") or "").strip()
    if not address:
        raise ValueError("Địa chỉ xuất hóa đơn là bắt buộc.")
    if party == "company" and (not company or not tax_code):
        raise ValueError("Hóa đơn doanh nghiệp cần tên đơn vị và mã số thuế.")
    if party == "individual" and (not full_name or not cccd):
        raise ValueError("Hóa đơn cá nhân cần họ tên và CCCD.")
    application_id = int(data.get("application_id") or 0) or None
    program = (data.get("program_code") or "").strip().upper()
    if application_id and not program:
        got = cur.execute("SELECT program_code FROM applications WHERE id = ?", (application_id,)).fetchone()
        program = got[0] if got else ""
    if application_id:
        cur.execute(
            "UPDATE billing_profiles SET is_current = 0 WHERE application_id = ? AND is_current = 1",
            (application_id,),
        )
    cur.execute(
        "INSERT INTO billing_profiles ("
        "application_id, party_type, full_name, intake, company_name, tax_code, address, cccd, "
        "phone, email, note, program_code, is_current, created_by, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
        (
            application_id,
            party,
            full_name,
            (data.get("intake") or "").strip(),
            company,
            tax_code,
            address,
            cccd,
            str(data.get("phone") or "").strip(),
            (data.get("email") or "").strip(),
            (data.get("note") or "").strip(),
            program,
            actor,
            _now(),
        ),
    )
    profile_id = cur.lastrowid
    _audit(cur, actor=actor, action="create", entity="billing_profiles", entity_id=profile_id, detail=party)
    conn.commit()
    return {"id": profile_id, "party_type": party}


def list_intake_plans(conn, *, cohort: str = "", study_year: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    cohort = (cohort or "").strip()
    if not cohort:
        return []
    sql = (
        "SELECT id, program_code, intake_code, fee_type, installment_no, title, amount_due, "
        "due_date, due_offset_days, status, currency, IFNULL(study_year,'') "
        "FROM fee_intake_plans WHERE intake_code = ?"
    )
    params: list = [cohort]
    if (study_year or "").strip():
        sql += " AND CAST(IFNULL(study_year,'') AS TEXT) = ?"
        params.append(str(study_year).strip())
    sql += " ORDER BY program_code, intake_code, IFNULL(study_year,0), installment_no"
    rows = cur.execute(sql, params).fetchall()
    return [
        {
            "id": r[0],
            "program_code": r[1],
            "intake_code": r[2],
            "fee_type": r[3],
            "installment_no": r[4],
            "title": r[5],
            "amount_due": r[6],
            "due_date": r[7] or "",
            "due_offset_days": r[8],
            "status": r[9],
            "currency": r[10] or "VND",
            "study_year": r[11] if len(r) > 11 else "",
        }
        for r in rows
    ]


def upsert_intake_plan(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    program = (data.get("program_code") or "").strip().upper()
    intake = (data.get("intake_code") or "").strip()
    fee_type = (data.get("fee_type") or "").strip()
    title = (data.get("title") or "").strip()
    if not program or not intake or not fee_type or not title:
        raise ValueError("Cần chương trình, mã khóa, loại khoản và tên đợt.")
    try:
        installment = int(data.get("installment_no") or 0)
        amount = float(data.get("amount_due") or 0)
    except (TypeError, ValueError):
        raise ValueError("Số đợt hoặc số tiền không hợp lệ.") from None
    if amount < 0:
        raise ValueError("Số tiền không âm.")
    currency = (data.get("currency") or "VND").strip().upper() or "VND"
    due = (data.get("due_date") or "").strip() or None
    offset = data.get("due_offset_days")
    try:
        offset_n = int(offset) if offset not in (None, "") else None
    except (TypeError, ValueError):
        offset_n = None
    exists = cur.execute(
        "SELECT id FROM fee_intake_plans WHERE program_code = ? AND intake_code = ? "
        "AND fee_type = ? AND installment_no = ?",
        (program, intake, fee_type, installment),
    ).fetchone()
    if exists:
        raise ValueError("Đợt này đã có trong kế hoạch khóa. Không tạo khoản trùng.")
    study_year = data.get("study_year")
    try:
        study_year_n = int(study_year) if study_year not in (None, "") else None
    except (TypeError, ValueError):
        study_year_n = None
    cur.execute(
        "INSERT INTO fee_intake_plans ("
        "program_code, intake_code, fee_type, installment_no, title, amount_due, "
        "due_date, due_offset_days, currency, status, study_year"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)",
        (program, intake, fee_type, installment, title, amount, due, offset_n, currency, study_year_n),
    )
    conn.commit()
    return {"id": cur.lastrowid, "status": "active", "currency": currency}


_MATCH_VI = {
    "matched": "Khớp",
    "short": "Thiếu",
    "over": "Thừa",
    "unmatched": "Chưa rõ người nộp",
    "duplicate": "Trùng",
}


def record_bank_line(cur, **data) -> None:
    ensure_finance_tables(cur)
    cur.execute(
        "INSERT INTO bank_statement_lines ("
        "txn_code, amount, paid_at, payer_name, identity_number, program_code, fee_type, "
        "match_status, charge_id, receipt_id, note, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            (data.get("txn_code") or "") or None,
            float(data.get("amount") or 0),
            data.get("paid_at") or "",
            data.get("payer_name") or "",
            data.get("identity_number") or "",
            data.get("program_code") or "",
            data.get("fee_type") or "",
            data.get("match_status") or "",
            data.get("charge_id"),
            data.get("receipt_id"),
            (data.get("note") or "")[:400],
            _now(),
        ),
    )


def list_bank_lines(conn, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_finance_tables(cur)
    sql = (
        "SELECT id, payer_name, identity_number, amount, txn_code, paid_at, fee_type, "
        "match_status, note FROM bank_statement_lines WHERE 1=1"
    )
    params: list = []
    if q:
        sql += (
            " AND (IFNULL(payer_name,'') LIKE ? OR IFNULL(identity_number,'') LIKE ? "
            "OR IFNULL(txn_code,'') LIKE ? OR IFNULL(note,'') LIKE ?)"
        )
        like = f"%{q}%"
        params.extend([like, like, like, like])
    sql += " ORDER BY id DESC"
    rows = cur.execute(sql, params).fetchall()
    return [
        {
            "id": r[0],
            "full_name": r[1] or "",
            "cccd": r[2] or "",
            "amount": r[3],
            "txn_code": r[4] or "",
            "paid_at": r[5] or "",
            "fee_type": r[6] or "",
            "match_status": _MATCH_VI.get(r[7] or "", r[7] or ""),
            "note": r[8] or "",
        }
        for r in rows
    ]


def save_invoice_profile(cur, data: dict, *, application_id=None, person_id=None) -> int | None:
    """Lưu bản thông tin người nhận tại lúc lập phiếu. Bản cũ giữ nguyên."""
    ensure_finance_tables(cur)
    full_name = (data.get("buyer_name") or data.get("full_name") or "").strip()
    tax_code = str(data.get("tax_code") or "").strip()
    address = (data.get("buyer_address") or data.get("address") or "").strip()
    cccd = str(data.get("identity_number") or data.get("cccd") or "").strip()
    party = (data.get("buyer_type") or data.get("party_type") or "").strip().lower()
    if party not in ("company", "individual"):
        party = "company" if tax_code else "individual"
    if not address and not full_name and not tax_code:
        return None
    program = ""
    if application_id:
        got = cur.execute("SELECT program_code FROM applications WHERE id = ?", (application_id,)).fetchone()
        program = got[0] if got else ""
        cur.execute(
            "UPDATE billing_profiles SET is_current = 0 WHERE application_id = ? AND is_current = 1",
            (application_id,),
        )
    cur.execute(
        "INSERT INTO billing_profiles ("
        "application_id, party_type, full_name, company_name, tax_code, address, cccd, "
        "email, phone, note, program_code, is_current, created_at"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
        (
            application_id,
            party,
            full_name,
            full_name if party == "company" else "",
            tax_code,
            address,
            cccd,
            (data.get("email") or "").strip(),
            str(data.get("phone") or "").strip(),
            f"person:{person_id}" if person_id else "",
            program,
            _now(),
        ),
    )
    return cur.lastrowid
