"""
Treasury / Thủ quỹ — sổ thu & công nợ gắn với luồng TS → KT → HV hiện có.

Khâu liên thông:
  1) applications.status = passed  → tạo phí ghi danh (enrollment_fees) + charge inscription
  2) mark-paid                    → ghi payment + cập nhật charge/công nợ
  3) mark-official                → chốt HV chính thức; mở khung học phí (tuition plan)
  4) enroll-official → class_students → gắn charge với mã HV; áp scholarship_type nếu có
"""
from __future__ import annotations

import re
from datetime import date, timedelta


INSCRIPTION_DEFAULT_AMOUNT = 15_000_000.0

# Payment plan học phí mặc định sau Official (có thể chỉnh sau)
DEFAULT_TUITION_PLAN = [
    {"installment_no": 1, "title": "Học phí kỳ 1", "amount": 40_000_000.0, "due_offset_days": 30},
    {"installment_no": 2, "title": "Học phí kỳ 2", "amount": 40_000_000.0, "due_offset_days": 150},
]

# Cảnh báo tự động theo tiêu chí Thủ quỹ (hạn nộp / số khoản trễ)
DEFAULT_ALERT_CRITERIA = [
    {
        "code": "due_soon",
        "label": "Sắp đến hạn nộp học phí",
        "description": "Cảnh báo khi khoản chưa nộp còn ≤ N ngày đến hạn.",
        "enabled": 1,
        "threshold": 7,
        "severity": "warning",
        "sort_order": 10,
    },
    {
        "code": "overdue",
        "label": "Quá hạn nộp học phí",
        "description": "Cảnh báo khi khoản chưa nộp đã quá hạn ≥ N ngày.",
        "enabled": 1,
        "threshold": 1,
        "severity": "danger",
        "sort_order": 20,
    },
    {
        "code": "overdue_count",
        "label": "Nhiều khoản thanh toán trễ hạn",
        "description": "Cảnh báo khi một học viên có ≥ N khoản quá hạn.",
        "enabled": 1,
        "threshold": 2,
        "severity": "danger",
        "sort_order": 30,
    },
]


OTHER_FEE_CATALOG = [
    ("inscription", "Phí ghi danh (Inscription Fee)", 15_000_000, 10),
    ("entrance_exam", "Lệ phí thi đầu vào (Entrance exam fee)", 0, 15),
    ("tuition", "Học phí", 0, 20),
    ("retake", "Phí học lại (Retake)", 0, 30),
    ("resit", "Phí thi lại (Resit)", 0, 40),
    ("deferral", "Phí bảo lưu", 0, 50),
    ("extension", "Phí gia hạn thời gian học", 0, 60),
    ("study_trip", "Phí Study Trip", 0, 70),
    ("transcript", "Phí cấp bảng điểm", 0, 80),
    ("certificate", "Phí cấp bằng / chứng nhận", 0, 90),
    ("id_card", "Phí cấp lại thẻ HV", 0, 100),
    ("confirmation", "Phí xác nhận học viên", 0, 110),
    ("transfer", "Phí chuyển CT / khóa", 0, 120),
    ("canvas_email", "Phí thay đổi email/Canvas", 0, 130),
    ("partner_collection", "Khoản thu hộ đối tác quốc tế", 0, 140),
    ("other", "Khoản thu khác", 0, 200),
]


def ensure_treasury_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS fee_type_catalog ("
        "code TEXT PRIMARY KEY, "
        "label TEXT NOT NULL, "
        "default_amount REAL DEFAULT 0, "
        "sort_order INTEGER DEFAULT 0, "
        "is_active INTEGER DEFAULT 1)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS student_charges ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "application_id INTEGER, "
        "class_student_id INTEGER, "
        "program_code TEXT, "
        "fee_type TEXT NOT NULL, "
        "title TEXT NOT NULL, "
        "amount_due REAL NOT NULL DEFAULT 0, "
        "amount_paid REAL NOT NULL DEFAULT 0, "
        "amount_adjust REAL NOT NULL DEFAULT 0, "
        "due_date TEXT, "
        "status TEXT NOT NULL DEFAULT 'pending', "
        "installment_no INTEGER DEFAULT 0, "
        "enrollment_fee_id INTEGER, "
        "notes TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (application_id) REFERENCES applications(id), "
        "FOREIGN KEY (class_student_id) REFERENCES class_students(id), "
        "FOREIGN KEY (enrollment_fee_id) REFERENCES enrollment_fees(id))"
    )
    existing = {r[1] for r in cur.execute("PRAGMA table_info(student_charges)").fetchall()}
    if "waiver_pct" not in existing:
        cur.execute("ALTER TABLE student_charges ADD COLUMN waiver_pct REAL DEFAULT 0")
    if "waiver_amount" not in existing:
        try:
            cur.execute("ALTER TABLE student_charges ADD COLUMN waiver_amount REAL DEFAULT 0")
        except Exception:
            pass
    if "student_proof_note" not in existing:
        try:
            cur.execute("ALTER TABLE student_charges ADD COLUMN student_proof_note TEXT")
        except Exception:
            pass
    if "currency" not in existing:
        try:
            cur.execute("ALTER TABLE student_charges ADD COLUMN currency TEXT DEFAULT 'VND'")
        except Exception:
            pass
    if "intake" not in existing:
        try:
            cur.execute("ALTER TABLE student_charges ADD COLUMN intake TEXT")
        except Exception:
            pass
    if "study_year" not in existing:
        try:
            cur.execute("ALTER TABLE student_charges ADD COLUMN study_year INTEGER")
        except Exception:
            pass
    if "cohort_year" not in existing:
        try:
            cur.execute("ALTER TABLE student_charges ADD COLUMN cohort_year TEXT")
        except Exception:
            pass
    fee_cols = {r[1] for r in cur.execute("PRAGMA table_info(fee_type_catalog)").fetchall()}
    if "collection_kind" not in fee_cols:
        cur.execute(
            "ALTER TABLE fee_type_catalog ADD COLUMN collection_kind TEXT DEFAULT 'center'"
        )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS fee_payments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "charge_id INTEGER, "
        "enrollment_fee_id INTEGER, "
        "amount REAL NOT NULL, "
        "paid_at TEXT NOT NULL, "
        "method TEXT, "
        "bank_ref TEXT, "
        "proof_note TEXT, "
        "created_by TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (charge_id) REFERENCES student_charges(id), "
        "FOREIGN KEY (enrollment_fee_id) REFERENCES enrollment_fees(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS fee_adjustments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "charge_id INTEGER NOT NULL, "
        "adj_type TEXT NOT NULL, "  # scholarship | discount | aid | refund
        "amount REAL NOT NULL, "
        "decision_note TEXT, "
        "status TEXT DEFAULT 'applied', "
        "created_by TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (charge_id) REFERENCES student_charges(id))"
    )
    for code, label, default_amount, sort_order in OTHER_FEE_CATALOG:
        cur.execute(
            "INSERT INTO fee_type_catalog (code, label, default_amount, sort_order, is_active) "
            "VALUES (?, ?, ?, ?, 1) "
            "ON CONFLICT(code) DO UPDATE SET "
            "label = excluded.label, "
            "sort_order = excluded.sort_order, "
            "is_active = 1",
            (code, label, default_amount, sort_order),
        )
    cur.execute(
        "UPDATE fee_type_catalog SET collection_kind = 'pass_through' "
        "WHERE code = 'partner_collection'"
    )
    cur.execute(
        "UPDATE fee_type_catalog SET collection_kind = 'center' "
        "WHERE collection_kind IS NULL OR collection_kind = ''"
    )
    from treasury_finance import ensure_finance_tables

    ensure_finance_tables(cur)
    cur.execute(
        "CREATE TABLE IF NOT EXISTS fee_alert_criteria ("
        "code TEXT PRIMARY KEY, "
        "label TEXT NOT NULL, "
        "description TEXT, "
        "enabled INTEGER NOT NULL DEFAULT 1, "
        "threshold REAL NOT NULL DEFAULT 0, "
        "severity TEXT NOT NULL DEFAULT 'warning', "
        "sort_order INTEGER DEFAULT 0)"
    )
    for item in DEFAULT_ALERT_CRITERIA:
        cur.execute(
            "INSERT INTO fee_alert_criteria "
            "(code, label, description, enabled, threshold, severity, sort_order) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(code) DO UPDATE SET "
            "label = excluded.label, "
            "description = excluded.description, "
            "severity = excluded.severity, "
            "sort_order = excluded.sort_order",
            (
                item["code"],
                item["label"],
                item["description"],
                item["enabled"],
                item["threshold"],
                item["severity"],
                item["sort_order"],
            ),
        )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS intake_fee_plans ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "program_code TEXT NOT NULL, "
        "intake_code TEXT NOT NULL, "
        "fee_type TEXT NOT NULL, "
        "installment_no INTEGER NOT NULL DEFAULT 1, "
        "title TEXT NOT NULL, "
        "amount_due REAL NOT NULL, "
        "due_date TEXT, "
        "due_offset_days INTEGER, "
        "active INTEGER NOT NULL DEFAULT 1, "
        "UNIQUE(program_code, intake_code, fee_type, installment_no))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS invoice_profiles ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "person_id INTEGER, "
        "application_id INTEGER, "
        "buyer_type TEXT DEFAULT 'individual', "
        "buyer_name TEXT, "
        "tax_code TEXT, "
        "address TEXT, "
        "identity_number TEXT, "
        "phone TEXT, "
        "email TEXT, "
        "note TEXT, "
        "updated_at TEXT)"
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
    adj_cols = {r[1] for r in cur.execute("PRAGMA table_info(fee_adjustments)").fetchall()}
    for name, spec in (
        ("effect", "TEXT"),
        ("payout_account", "TEXT"),
        ("payout_bank", "TEXT"),
        ("request_no", "TEXT"),
        ("approved_no", "TEXT"),
        ("paid_out_ref", "TEXT"),
    ):
        if name not in adj_cols:
            try:
                cur.execute(f"ALTER TABLE fee_adjustments ADD COLUMN {name} {spec}")
            except Exception:
                pass


def _charge_status(amount_due: float, amount_paid: float, amount_adjust: float) -> str:
    net = max(0.0, float(amount_due or 0) + float(amount_adjust or 0))
    paid = float(amount_paid or 0)
    if net <= 0:
        return "waived"
    if paid <= 0:
        return "pending"
    if paid + 0.01 >= net:
        return "paid"
    return "partial"


def _recompute_charge(cur, charge_id: int) -> None:
    n_pay, paid_sum = cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM fee_payments WHERE charge_id = ?",
        (charge_id,),
    ).fetchone()
    if n_pay:
        cur.execute("UPDATE student_charges SET amount_paid = ? WHERE id = ?", (paid_sum, charge_id))
    row = cur.execute(
        "SELECT amount_due, amount_paid, amount_adjust FROM student_charges WHERE id = ?",
        (charge_id,),
    ).fetchone()
    if not row:
        return
    status = _charge_status(row[0], row[1], row[2])
    cur.execute("UPDATE student_charges SET status = ? WHERE id = ?", (status, charge_id))


def _catalog_fee(cur, fee_type: str, fallback_amount: float = 0.0) -> tuple[str, float]:
    row = cur.execute(
        "SELECT label, default_amount FROM fee_type_catalog WHERE code = ? AND is_active = 1",
        (fee_type,),
    ).fetchone()
    if not row:
        return fee_type, float(fallback_amount or 0)
    return str(row[0] or fee_type), float(row[1] if row[1] is not None else fallback_amount or 0)


def ensure_inscription_charge(conn, application_id: int, *, amount: float | None = None) -> dict:
    """Khâu 1: sau khi Đỗ — đồng bộ enrollment_fees + student_charges(inscription)."""
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    app = cur.execute(
        "SELECT id, full_name, program_code, status FROM applications WHERE id = ?",
        (application_id,),
    ).fetchone()
    if not app:
        raise ValueError("Application not found")
    cat_label, cat_amt = _catalog_fee(cur, "inscription", INSCRIPTION_DEFAULT_AMOUNT)
    amt = float(amount if amount is not None else cat_amt)

    cur.execute("SELECT id, amount, status FROM enrollment_fees WHERE application_id = ?", (application_id,))
    fee = cur.fetchone()
    if not fee:
        cur.execute(
            "INSERT INTO enrollment_fees (application_id, amount, status) VALUES (?, ?, 'pending')",
            (application_id, amt),
        )
        fee_id = cur.lastrowid
        fee_status = "pending"
    else:
        fee_id, amt, fee_status = fee[0], float(fee[1] or amt), fee[2]

    cur.execute(
        "SELECT id FROM student_charges WHERE application_id = ? AND fee_type = 'inscription' "
        "AND COALESCE(installment_no,0) = 0",
        (application_id,),
    )
    ch = cur.fetchone()
    if not ch:
        paid = amt if fee_status == "paid" else 0.0
        status = _charge_status(amt, paid, 0)
        due_date = (date.today() + timedelta(days=14)).isoformat()
        cur.execute(
            "INSERT INTO student_charges ("
            "application_id, program_code, fee_type, title, amount_due, amount_paid, "
            "amount_adjust, due_date, status, installment_no, enrollment_fee_id, notes"
            ") VALUES (?, ?, 'inscription', ?, ?, ?, 0, ?, ?, 0, ?, ?)",
            (
                application_id,
                app[2],
                cat_label or "Phí ghi danh (Inscription Fee)",
                amt,
                paid,
                due_date,
                status,
                fee_id,
                "Tạo khi Đỗ — bàn giao Thủ quỹ",
            ),
        )
        charge_id = cur.lastrowid
    else:
        charge_id = ch[0]
        cur.execute(
            "UPDATE student_charges SET enrollment_fee_id = ?, program_code = COALESCE(program_code, ?) "
            "WHERE id = ?",
            (fee_id, app[2], charge_id),
        )
    conn.commit()
    return {"enrollment_fee_id": fee_id, "charge_id": charge_id, "amount": amt, "stage": "passed"}


def inscription_is_paid(cur, application_id: int) -> bool:
    """Phí ghi danh đã có dòng sổ và trạng thái paid. Không suy ra từ status hồ sơ."""
    row = cur.execute(
        "SELECT status FROM enrollment_fees WHERE application_id = ? ORDER BY id DESC LIMIT 1",
        (int(application_id),),
    ).fetchone()
    return bool(row and (row[0] or "") == "paid")


def record_inscription_payment(
    conn,
    enrollment_fee_id: int,
    *,
    amount: float | None = None,
    proof_note: str = "",
    method: str = "bank_transfer",
    bank_ref: str = "",
    created_by: str = "",
) -> dict:
    """Khâu 2: Thủ quỹ xác nhận nộp phí ghi danh."""
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    row = cur.execute(
        "SELECT ef.id, ef.application_id, ef.amount, ef.status, a.program_code "
        "FROM enrollment_fees ef JOIN applications a ON a.id = ef.application_id "
        "WHERE ef.id = ?",
        (enrollment_fee_id,),
    ).fetchone()
    if not row:
        raise ValueError("Fee record not found")
    fee_id, app_id, fee_amt, fee_status, program_code = row
    pay_amt = float(amount if amount is not None else fee_amt or INSCRIPTION_DEFAULT_AMOUNT)
    proof = (proof_note or "").strip() or "Kế toán xác nhận"
    today = date.today().isoformat()

    cur.execute(
        "UPDATE enrollment_fees SET status = 'paid', paid_at = ?, proof_note = ? WHERE id = ?",
        (today, proof, fee_id),
    )
    cur.execute(
        "UPDATE applications SET status = 'paid', "
        "final_result = COALESCE(NULLIF(final_result,''), 'Admitted') "
        "WHERE id = ? AND status IN ('passed','paid')",
        (app_id,),
    )

    # Ensure charge exists
    ensure_inscription_charge(conn, app_id, amount=fee_amt)
    cur.execute(
        "SELECT id, amount_due, amount_paid FROM student_charges "
        "WHERE enrollment_fee_id = ? OR (application_id = ? AND fee_type = 'inscription') "
        "ORDER BY id LIMIT 1",
        (fee_id, app_id),
    )
    ch = cur.fetchone()
    charge_id = ch[0] if ch else None
    cur.execute(
        "INSERT INTO fee_payments ("
        "charge_id, enrollment_fee_id, amount, paid_at, method, bank_ref, proof_note, created_by"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (charge_id, fee_id, pay_amt, today, method, bank_ref, proof, created_by),
    )
    payment_id = cur.lastrowid
    if charge_id:
        cur.execute(
            "INSERT INTO payment_allocations (payment_id, charge_id, amount) VALUES (?, ?, ?)",
            (payment_id, charge_id, pay_amt),
        )
    new_paid = pay_amt
    if charge_id:
        _recompute_charge(cur, charge_id)
        paid_row = cur.execute(
            "SELECT amount_paid FROM student_charges WHERE id = ?",
            (charge_id,),
        ).fetchone()
        new_paid = float(paid_row[0] or 0) if paid_row else pay_amt
    conn.commit()
    return {
        "ok": True,
        "stage": "paid",
        "enrollment_fee_id": fee_id,
        "charge_id": charge_id,
        "payment_id": payment_id,
        "application_id": app_id,
        "program_code": program_code,
        "handoff": "Deposit Verified — chốt Official rồi Điều phối tạo lớp + enroll HV",
    }


def open_tuition_plan_after_official(conn, application_id: int) -> dict:
    """Khâu 3: sau Official — mở các đợt học phí (Payment Plan) nếu chưa có."""
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    app = cur.execute(
        "SELECT id, program_code, status FROM applications WHERE id = ?",
        (application_id,),
    ).fetchone()
    if not app:
        raise ValueError("Application not found")
    cur.execute(
        "SELECT COUNT(*) FROM student_charges WHERE application_id = ? AND fee_type = 'tuition'",
        (application_id,),
    )
    if cur.fetchone()[0] > 0:
        return {"created": 0, "stage": "official", "note": "Tuition plan already exists"}

    from treasury_finance import apply_intake_plan

    planned = apply_intake_plan(conn, application_id=application_id)
    if planned.get("matched"):
        return planned

    created = 0
    today = date.today()
    for item in DEFAULT_TUITION_PLAN:
        due = date.fromordinal(today.toordinal() + int(item["due_offset_days"])).isoformat()
        cur.execute(
            "INSERT INTO student_charges ("
            "application_id, program_code, fee_type, title, amount_due, amount_paid, "
            "amount_adjust, due_date, status, installment_no, notes"
            ") VALUES (?, ?, 'tuition', ?, ?, 0, 0, ?, 'pending', ?, ?)",
            (
                application_id,
                app[1],
                item["title"],
                float(item["amount"]),
                due,
                int(item["installment_no"]),
                "Payment Plan mặc định sau Official — Thủ quỹ theo dõi",
            ),
        )
        created += 1
    conn.commit()
    return {"created": created, "stage": "official", "application_id": application_id}


def link_charges_to_student(conn, application_id: int, class_student_id: int) -> dict:
    """Khâu 4: enroll official → gắn charge với class_students; áp học bổng text nếu có."""
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    cur.execute(
        "UPDATE student_charges SET class_student_id = ? WHERE application_id = ? "
        "AND (class_student_id IS NULL OR class_student_id = 0)",
        (class_student_id, application_id),
    )
    linked = cur.rowcount
    conn.commit()
    return {
        "linked": linked,
        "scholarship_applied": 0,
        "stage": "enrolled",
        "class_student_id": class_student_id,
    }


def _parse_iso_date(value) -> date | None:
    raw = str(value or "").strip()[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _watch_thresholds(conn) -> dict:
    crit = {c["code"]: c for c in list_alert_criteria(conn)}
    def _n(code: str, default: float) -> float:
        row = crit.get(code) or {}
        try:
            return float(row.get("threshold") if row.get("threshold") is not None else default)
        except (TypeError, ValueError):
            return float(default)

    return {
        "due_soon_days": max(0, int(_n("due_soon", 7))),
        "overdue_days": max(0, int(_n("overdue", 1))),
        "overdue_count": max(1, int(_n("overdue_count", 2))),
        "enabled": {k: bool(int(v.get("enabled") or 0)) for k, v in crit.items()},
        "criteria": crit,
    }


def _charge_watch(due_date, ledger_status: str, remaining: float, *, due_soon_days: int, overdue_days: int) -> dict:
    """Derived payment watch: paid / waived / partial / pending / due_soon / overdue."""
    status = (ledger_status or "pending").strip() or "pending"
    rem = float(remaining or 0)
    days_until = None
    days_overdue = 0
    if rem <= 0.01 or status in ("paid", "waived"):
        pay_status = "waived" if status == "waived" else "paid"
        return {"pay_status": pay_status, "days_until_due": days_until, "days_overdue": 0}
    pay_status = "partial" if status == "partial" else "pending"
    due = _parse_iso_date(due_date)
    if due:
        delta = (due - date.today()).days
        days_until = delta
        if delta < 0 and abs(delta) >= overdue_days:
            days_overdue = abs(delta)
            pay_status = "overdue"
        elif 0 <= delta <= due_soon_days:
            pay_status = "due_soon"
    return {"pay_status": pay_status, "days_until_due": days_until, "days_overdue": days_overdue}


def _matches_charge_status(row: dict, status: str) -> bool:
    st = (status or "").strip().lower()
    if not st:
        return True
    pay = row.get("pay_status") or row.get("status") or ""
    ledger = row.get("status") or ""
    remaining = float(row.get("remaining") or 0)
    if st in ("unpaid", "open"):
        return remaining > 0.01 and ledger not in ("paid", "waived")
    if st in ("overdue", "due_soon", "paid", "partial", "pending", "waived"):
        if st == "paid":
            return pay == "paid" or ledger == "paid"
        if st == "pending":
            return pay in ("pending", "due_soon", "overdue") or ledger == "pending"
        return pay == st or ledger == st
    return ledger == st or pay == st


def list_student_charges(
    conn,
    scopes,
    *,
    q: str = "",
    fee_type: str = "",
    status: str = "",
    cohort: str = "",
    study_year: str = "",
    require_cohort: bool = False,
) -> list[dict]:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_treasury_tables(cur)
    from ops_data import ensure_ops_tables

    ensure_ops_tables(cur)
    cohort = (cohort or "").strip()
    if require_cohort and not cohort:
        return []
    watch = _watch_thresholds(conn)
    frag, params = _scopes_sql(scopes, "COALESCE(sc.program_code, a.program_code)")
    sql = (
        "SELECT sc.id, sc.application_id, sc.class_student_id, "
        "COALESCE(cs.full_name, a.full_name) AS full_name, "
        "COALESCE(cs.student_code, '') AS student_code, "
        "COALESCE(sc.program_code, a.program_code) AS program_code, "
        "sc.fee_type, sc.title, sc.amount_due, sc.amount_paid, sc.amount_adjust, "
        "sc.due_date, sc.status, sc.installment_no, sc.enrollment_fee_id, sc.notes, "
        "a.status AS application_status, cs.scholarship_type, "
        "COALESCE(sc.waiver_pct, 0) AS waiver_pct, "
        "COALESCE(a.email, cs.email, '') AS email, "
        "COALESCE(a.phone, '') AS phone, "
        "COALESCE(a.cfvg_app_no, '') AS cfvg_app_no, "
        "COALESCE(a.cccd, '') AS cccd, "
        "COALESCE(sc.student_proof_note, '') AS student_proof_note, "
        "COALESCE(sc.currency, 'VND') AS currency "
        "FROM student_charges sc "
        "LEFT JOIN applications a ON a.id = sc.application_id "
        "LEFT JOIN class_students cs ON cs.id = sc.class_student_id "
        "LEFT JOIN class_groups cg ON cg.id = cs.class_id "
        f"WHERE {frag}"
    )
    if cohort:
        sql += (
            " AND (IFNULL(sc.intake,'') = ? OR IFNULL(sc.cohort_year,'') = ? "
            "OR CAST(IFNULL(cg.cohort_year,'') AS TEXT) = ? OR IFNULL(cg.cohort_no,'') = ?)"
        )
        params.extend([cohort, cohort, cohort, cohort])
    if study_year:
        sql += " AND CAST(IFNULL(sc.study_year,'') AS TEXT) = ?"
        params.append(str(study_year).strip())
    if fee_type:
        sql += " AND sc.fee_type = ?"
        params.append(fee_type)
    if q:
        sql += (
            " AND (COALESCE(cs.full_name,a.full_name) LIKE ? OR COALESCE(cs.student_code,'') LIKE ? "
            "OR COALESCE(sc.title,'') LIKE ? OR COALESCE(a.email,'') LIKE ? "
            "OR COALESCE(a.phone,'') LIKE ? OR COALESCE(a.cccd,'') LIKE ? "
            "OR COALESCE(a.cfvg_app_no,'') LIKE ?)"
        )
        like = f"%{q}%"
        params.extend([like, like, like, like, like, like, like])
    sql += " ORDER BY sc.due_date IS NULL, sc.due_date, sc.id DESC"
    rows = cur.execute(sql, params).fetchall()
    out = []
    for r in rows:
        due = float(r[8] or 0)
        paid = float(r[9] or 0)
        adj = float(r[10] or 0)
        waiver_pct = float(r[18] or 0) if len(r) > 18 else 0.0
        actual_due = max(0.0, due + adj)
        remaining = max(0.0, actual_due - paid)
        waived_amount = round(due * waiver_pct / 100.0, 0) if waiver_pct else max(0.0, due - actual_due)
        watch_info = _charge_watch(
            r[11],
            r[12] or "pending",
            remaining,
            due_soon_days=watch["due_soon_days"],
            overdue_days=watch["overdue_days"],
        )
        ledger = r[12] or "pending"
        if actual_due <= 0.01:
            ledger = "waived"
        row = {
            "id": r[0],
            "application_id": r[1],
            "class_student_id": r[2],
            "full_name": r[3],
            "student_code": r[4],
            "program_code": r[5],
            "fee_type": r[6],
            "title": r[7],
            "amount_due": due,
            "amount_paid": paid,
            "amount_adjust": adj,
            "waiver_pct": waiver_pct,
            "waived_amount": waived_amount,
            "actual_due": actual_due,
            "remaining": remaining,
            "due_date": r[11],
            "status": watch_info["pay_status"] if watch_info["pay_status"] in ("overdue", "due_soon") else ledger,
            "ledger_status": ledger,
            "pay_status": "waived" if ledger == "waived" else watch_info["pay_status"],
            "days_until_due": watch_info["days_until_due"],
            "days_overdue": watch_info["days_overdue"],
            "installment_no": r[13],
            "enrollment_fee_id": r[14],
            "notes": r[15],
            "application_status": r[16],
            "scholarship_type": r[17],
            "email": r[19] if len(r) > 19 else "",
            "phone": r[20] if len(r) > 20 else "",
            "cfvg_app_no": r[21] if len(r) > 21 else "",
            "cccd": r[22] if len(r) > 22 else "",
            "student_proof_note": r[23] if len(r) > 23 else "",
            "currency": r[24] if len(r) > 24 and r[24] else "VND",
        }
        if _matches_charge_status(row, status):
            out.append(row)
    return out


def record_student_proof(conn, charge_id: int, *, note: str, application_id: int, created_by: str = "") -> dict:
    """HV gửi minh chứng — không đổi status / amount_paid (kế toán mới xác nhận đã thu)."""
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    text = (note or "").strip()
    if not text:
        raise ValueError("Nhập nội dung minh chứng (mã GD, ngân hàng, ngày nộp…).")
    row = cur.execute(
        "SELECT id, application_id, status, amount_paid FROM student_charges WHERE id = ?",
        (charge_id,),
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy khoản thu.")
    if int(row[1] or 0) != int(application_id or 0):
        raise ValueError("Khoản thu không thuộc hồ sơ của bạn.")
    cur.execute(
        "UPDATE student_charges SET student_proof_note = ? WHERE id = ?",
        (text[:800], charge_id),
    )
    conn.commit()
    return {
        "ok": True,
        "id": charge_id,
        "paid": False,
        "status_unchanged": True,
        "ledger_status": row[2],
        "amount_paid": row[3],
        "student_proof_note": text[:800],
        "message": "Đã ghi minh chứng. Kế toán sẽ xác nhận đã thu — hệ thống không tự đánh dấu nộp phí.",
        "created_by": created_by,
    }


def record_charge_payment(
    conn,
    charge_id: int,
    *,
    amount: float,
    proof_note: str = "",
    method: str = "bank_transfer",
    bank_ref: str = "",
    paid_at: str = "",
    created_by: str = "",
) -> dict:
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    row = cur.execute(
        "SELECT id, enrollment_fee_id, amount_due, amount_paid, amount_adjust, fee_type, application_id "
        "FROM student_charges WHERE id = ?",
        (charge_id,),
    ).fetchone()
    if not row:
        raise ValueError("Charge not found")
    pay_amt = float(amount)
    if pay_amt <= 0:
        raise ValueError("Số tiền thanh toán phải > 0")
    pay_day = str(paid_at or "").strip()[:10] or date.today().isoformat()
    try:
        date.fromisoformat(pay_day)
    except ValueError:
        pay_day = date.today().isoformat()
    cur.execute(
        "INSERT INTO fee_payments ("
        "charge_id, enrollment_fee_id, amount, paid_at, method, bank_ref, proof_note, created_by"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (charge_id, row[1], pay_amt, pay_day, method or "bank_transfer", bank_ref, proof_note, created_by),
    )
    payment_id = cur.lastrowid
    cur.execute(
        "INSERT INTO payment_allocations (payment_id, charge_id, amount) VALUES (?, ?, ?)",
        (payment_id, charge_id, pay_amt),
    )
    _recompute_charge(cur, charge_id)
    paid_row = cur.execute(
        "SELECT amount_paid, amount_due, amount_adjust FROM student_charges WHERE id = ?",
        (charge_id,),
    ).fetchone()
    new_paid = float(paid_row[0] or 0)
    net = max(0.0, float(paid_row[1] or 0) + float(paid_row[2] or 0))

    # Sync legacy inscription fee if linked
    if row[1] and row[5] == "inscription":
        if new_paid + 0.01 >= net:
            cur.execute(
                "UPDATE enrollment_fees SET status = 'paid', paid_at = COALESCE(paid_at, ?), "
                "proof_note = COALESCE(NULLIF(proof_note,''), ?) WHERE id = ?",
                (pay_day, proof_note or "Thu qua sổ công nợ", row[1]),
            )
            if row[6]:
                cur.execute(
                    "UPDATE applications SET status = 'paid' WHERE id = ? AND status IN ('passed','paid')",
                    (row[6],),
                )
    conn.commit()
    return {
        "ok": True,
        "payment_id": payment_id,
        "charge_id": charge_id,
        "amount_paid": new_paid,
        "actual_due": net,
        "remaining": max(0.0, net - new_paid),
        "paid_at": pay_day,
    }


def apply_adjustment(
    conn,
    charge_id: int,
    *,
    adj_type: str,
    amount: float,
    decision_note: str = "",
    created_by: str = "",
    effect: str = "",
    payout_account: str = "",
    payout_bank: str = "",
    request_no: str = "",
    approved_no: str = "",
    paid_out_ref: str = "",
) -> dict:
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    if adj_type not in ("scholarship", "discount", "aid", "refund", "waiver"):
        raise ValueError("adj_type không hợp lệ")
    cur.execute("SELECT id FROM student_charges WHERE id = ?", (charge_id,))
    if not cur.fetchone():
        raise ValueError("Charge not found")
    effect_s = (effect or "").strip().lower()
    account = (payout_account or "").strip()
    if not effect_s:
        effect_s = "payout" if account else "reduce"
    if effect_s not in ("reduce", "payout"):
        raise ValueError("Cách ghi không hợp lệ.")
    raw_amt = abs(float(amount or 0))
    if raw_amt <= 0:
        raise ValueError("Số tiền không hợp lệ")
    if effect_s == "payout":
        if not account:
            raise ValueError("Chi ra tài khoản cần số tài khoản thụ hưởng.")
        if paid_out_ref:
            status = "paid_out"
        elif approved_no:
            status = "approved"
        else:
            status = "proposed"
        stored = raw_amt
        handoff = "Đã ghi giấy đề nghị chi, không tính vào số đã thu."
    else:
        status = "applied"
        stored = -raw_amt
        handoff = "Đã giảm nghĩa vụ phải thu."
    cur.execute(
        "INSERT INTO fee_adjustments ("
        "charge_id, adj_type, amount, decision_note, status, created_by, effect, "
        "payout_account, payout_bank, request_no, approved_no, paid_out_ref"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            charge_id, adj_type, stored, decision_note, status, created_by, effect_s,
            account, (payout_bank or "").strip(), (request_no or "").strip(),
            (approved_no or "").strip(), (paid_out_ref or "").strip(),
        ),
    )
    adj_id = cur.lastrowid
    if effect_s == "reduce":
        cur.execute(
            "UPDATE student_charges SET amount_adjust = COALESCE(amount_adjust,0) + ? WHERE id = ?",
            (stored, charge_id),
        )
        _recompute_charge(cur, charge_id)
    conn.commit()
    return {
        "ok": True,
        "adjustment_id": adj_id,
        "charge_id": charge_id,
        "amount": stored,
        "effect": effect_s,
        "status": status,
        "handoff": handoff,
    }


def treasury_summary(conn, scopes) -> dict:
    charges = list_student_charges(conn, scopes)
    due = paid = adjust = remaining = waived_total = actual_due = 0.0
    by_type: dict[str, dict] = {}
    overdue = due_soon = unpaid = waived_count = 0
    foreign_count = 0
    students_overdue: set = set()
    students_due_soon: set = set()
    for c in charges:
        if str(c.get("currency") or "VND").upper() != "VND":
            foreign_count += 1
            continue
        d, p, a = float(c["amount_due"] or 0), float(c["amount_paid"] or 0), float(c["amount_adjust"] or 0)
        rem = float(c["remaining"] or 0)
        due += d
        paid += p
        adjust += a
        remaining += rem
        waived_amt = float(c.get("waived_amount") or 0)
        actual = float(c.get("actual_due") or 0)
        waived_total += waived_amt
        actual_due += actual
        slot = by_type.setdefault(
            c.get("fee_type") or "other",
            {"due": 0, "paid": 0, "adjust": 0, "remaining": 0, "waived": 0, "actual_due": 0},
        )
        slot["due"] += d
        slot["paid"] += p
        slot["adjust"] += a
        slot["remaining"] += rem
        slot["waived"] += waived_amt
        slot["actual_due"] += actual
        key = c.get("class_student_id") or c.get("application_id") or c.get("id")
        if c.get("pay_status") == "overdue":
            overdue += 1
            students_overdue.add(key)
        elif c.get("pay_status") == "due_soon":
            due_soon += 1
            students_due_soon.add(key)
        if c.get("pay_status") == "waived" or actual <= 0.01:
            waived_count += 1
        if rem > 0.01:
            unpaid += 1
    return {
        "amount_due": due,
        "amount_paid": paid,
        "amount_adjust": adjust,
        "amount_remaining": remaining,
        "amount_waived": waived_total,
        "amount_actual_due": actual_due,
        "collected_incl_waived": paid,
        "overdue_count": overdue,
        "due_soon_count": due_soon,
        "unpaid_count": unpaid,
        "waived_count": waived_count,
        "overdue_students": len(students_overdue),
        "due_soon_students": len(students_due_soon),
        "charge_count": len(charges),
        "foreign_charge_count": foreign_count,
        "by_type": by_type,
        "alert_count": overdue + due_soon,
    }


def list_tuition_tracker(
    conn, scopes, *, q: str = "", status: str = "", cohort: str = "", study_year: str = "",
) -> list[dict]:
    """One row per student: payment status, overdue count, next due date."""
    charges = list_student_charges(
        conn, scopes, q=q, cohort=cohort, study_year=study_year, require_cohort=True,
    )
    groups: dict[str, dict] = {}
    for c in charges:
        key = str(c.get("class_student_id") or c.get("application_id") or f"c-{c['id']}")
        slot = groups.get(key)
        if not slot:
            slot = {
                "id": key,
                "application_id": c.get("application_id"),
                "class_student_id": c.get("class_student_id"),
                "full_name": c.get("full_name") or "",
                "student_code": c.get("student_code") or "",
                "program_code": c.get("program_code") or "",
                "scholarship_type": c.get("scholarship_type") or "",
                "amount_due": 0.0,
                "amount_paid": 0.0,
                "amount_adjust": 0.0,
                "remaining": 0.0,
                "charge_count": 0,
                "unpaid_count": 0,
                "overdue_count": 0,
                "due_soon_count": 0,
                "next_due_date": None,
                "pay_status": "paid",
                "status": "paid",
            }
            groups[key] = slot
        slot["amount_due"] += float(c["amount_due"] or 0)
        slot["amount_paid"] += float(c["amount_paid"] or 0)
        slot["amount_adjust"] += float(c["amount_adjust"] or 0)
        slot["remaining"] += float(c["remaining"] or 0)
        slot["charge_count"] += 1
        if float(c["remaining"] or 0) > 0.01:
            slot["unpaid_count"] += 1
        if c.get("pay_status") == "overdue":
            slot["overdue_count"] += 1
        elif c.get("pay_status") == "due_soon":
            slot["due_soon_count"] += 1
        due = c.get("due_date") or ""
        if due and float(c["remaining"] or 0) > 0.01:
            if not slot["next_due_date"] or str(due) < str(slot["next_due_date"]):
                slot["next_due_date"] = due
    rank = {"overdue": 4, "due_soon": 3, "partial": 2, "pending": 1, "paid": 0, "waived": 0}
    out = []
    for slot in groups.values():
        if slot["overdue_count"]:
            pay = "overdue"
        elif slot["due_soon_count"]:
            pay = "due_soon"
        elif slot["remaining"] > 0.01 and slot["amount_paid"] > 0:
            pay = "partial"
        elif slot["remaining"] > 0.01:
            pay = "pending"
        else:
            pay = "paid"
        slot["pay_status"] = pay
        slot["status"] = pay
        if status and not _matches_charge_status(slot, status):
            continue
        out.append(slot)
    out.sort(
        key=lambda r: (
            -rank.get(r["pay_status"], 0),
            -int(r["overdue_count"] or 0),
            str(r.get("next_due_date") or "9999"),
            str(r.get("full_name") or ""),
        )
    )
    return out


def list_alert_criteria(conn) -> list[dict]:
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    rows = cur.execute(
        "SELECT code, label, description, enabled, threshold, severity, sort_order "
        "FROM fee_alert_criteria ORDER BY sort_order, code"
    ).fetchall()
    return [
        {
            "id": r[0],
            "code": r[0],
            "label": r[1],
            "description": r[2] or "",
            "enabled": int(r[3] or 0),
            "threshold": r[4],
            "severity": r[5] or "warning",
            "sort_order": r[6] or 0,
        }
        for r in rows
    ]


def update_alert_criterion(conn, code: str, data: dict) -> dict:
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    row = cur.execute("SELECT code FROM fee_alert_criteria WHERE code = ?", (code,)).fetchone()
    if not row:
        raise ValueError("Không tìm thấy tiêu chí cảnh báo")
    fields: list[str] = []
    params: list = []
    if "enabled" in data:
        fields.append("enabled = ?")
        params.append(1 if str(data.get("enabled")).lower() in ("1", "true", "yes", "on") or data.get("enabled") is True else 0)
    if "threshold" in data and data.get("threshold") is not None and str(data.get("threshold")).strip() != "":
        try:
            th = float(data["threshold"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Ngưỡng không hợp lệ") from exc
        if th < 0:
            raise ValueError("Ngưỡng phải ≥ 0")
        fields.append("threshold = ?")
        params.append(th)
    if not fields:
        raise ValueError("Không có trường để cập nhật")
    params.append(code)
    cur.execute(f"UPDATE fee_alert_criteria SET {', '.join(fields)} WHERE code = ?", params)
    conn.commit()
    return next(c for c in list_alert_criteria(conn) if c["code"] == code)


def list_fee_alerts(conn, scopes, *, q: str = "", status: str = "") -> list[dict]:
    """Live alerts from current charges vs enabled criteria (recomputed on every view)."""
    watch = _watch_thresholds(conn)
    enabled = watch["enabled"]
    charges = list_student_charges(conn, scopes, q=q)
    alerts: list[dict] = []
    by_student: dict[str, list[dict]] = {}
    crit = watch["criteria"]

    if enabled.get("overdue", True):
        for c in charges:
            if c.get("pay_status") != "overdue":
                continue
            meta = crit.get("overdue") or {}
            days = int(c.get("days_overdue") or 0)
            alerts.append(
                {
                    "id": f"overdue-{c['id']}",
                    "criterion": "overdue",
                    "severity": meta.get("severity") or "danger",
                    "title": meta.get("label") or "Quá hạn nộp học phí",
                    "message": (
                        f"{c.get('full_name') or 'HV'} — {c.get('title') or 'khoản thu'} "
                        f"quá hạn {days} ngày (hạn {c.get('due_date') or '—'})."
                    ),
                    "full_name": c.get("full_name") or "",
                    "student_code": c.get("student_code") or "",
                    "program_code": c.get("program_code") or "",
                    "fee_type": c.get("fee_type") or "",
                    "charge_title": c.get("title") or "",
                    "due_date": c.get("due_date") or "",
                    "remaining": c.get("remaining") or 0,
                    "days_overdue": days,
                    "days_until_due": c.get("days_until_due"),
                    "charge_id": c.get("id"),
                    "status": "overdue",
                }
            )
            key = str(c.get("class_student_id") or c.get("application_id") or c["id"])
            by_student.setdefault(key, []).append(c)

    if enabled.get("due_soon", True):
        for c in charges:
            if c.get("pay_status") != "due_soon":
                continue
            meta = crit.get("due_soon") or {}
            days = c.get("days_until_due")
            alerts.append(
                {
                    "id": f"due-soon-{c['id']}",
                    "criterion": "due_soon",
                    "severity": meta.get("severity") or "warning",
                    "title": meta.get("label") or "Sắp đến hạn nộp học phí",
                    "message": (
                        f"{c.get('full_name') or 'HV'} — {c.get('title') or 'khoản thu'} "
                        f"đến hạn trong {days if days is not None else '?'} ngày "
                        f"({c.get('due_date') or '—'})."
                    ),
                    "full_name": c.get("full_name") or "",
                    "student_code": c.get("student_code") or "",
                    "program_code": c.get("program_code") or "",
                    "fee_type": c.get("fee_type") or "",
                    "charge_title": c.get("title") or "",
                    "due_date": c.get("due_date") or "",
                    "remaining": c.get("remaining") or 0,
                    "days_overdue": 0,
                    "days_until_due": days,
                    "charge_id": c.get("id"),
                    "status": "due_soon",
                }
            )

    if enabled.get("overdue_count", True):
        threshold = watch["overdue_count"]
        # Rebuild student overdue groups from all overdue charges
        grouped: dict[str, list[dict]] = {}
        for c in charges:
            if c.get("pay_status") != "overdue":
                continue
            key = str(c.get("class_student_id") or c.get("application_id") or c["id"])
            grouped.setdefault(key, []).append(c)
        meta = crit.get("overdue_count") or {}
        for key, items in grouped.items():
            if len(items) < threshold:
                continue
            sample = items[0]
            alerts.append(
                {
                    "id": f"overdue-count-{key}",
                    "criterion": "overdue_count",
                    "severity": meta.get("severity") or "danger",
                    "title": meta.get("label") or "Nhiều khoản thanh toán trễ hạn",
                    "message": (
                        f"{sample.get('full_name') or 'HV'} có {len(items)} khoản quá hạn "
                        f"(ngưỡng ≥ {int(threshold)})."
                    ),
                    "full_name": sample.get("full_name") or "",
                    "student_code": sample.get("student_code") or "",
                    "program_code": sample.get("program_code") or "",
                    "fee_type": "",
                    "charge_title": f"{len(items)} khoản",
                    "due_date": "",
                    "remaining": sum(float(x.get("remaining") or 0) for x in items),
                    "days_overdue": max(int(x.get("days_overdue") or 0) for x in items),
                    "days_until_due": None,
                    "charge_id": None,
                    "overdue_count": len(items),
                    "status": "overdue",
                }
            )

    st = (status or "").strip().lower()
    if st:
        alerts = [a for a in alerts if a.get("status") == st or a.get("criterion") == st]
    alerts.sort(
        key=lambda a: (
            0 if a.get("severity") == "danger" else 1,
            -int(a.get("days_overdue") or 0),
            str(a.get("due_date") or ""),
            str(a.get("full_name") or ""),
        )
    )
    return alerts


def list_fee_types(conn, *, include_inactive: bool = False) -> list[dict]:
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    sql = (
        "SELECT code, label, default_amount, sort_order, is_active, "
        "COALESCE(collection_kind, 'center') "
        "FROM fee_type_catalog "
    )
    if not include_inactive:
        sql += "WHERE is_active = 1 "
    sql += "ORDER BY sort_order, code"
    rows = cur.execute(sql).fetchall()
    return [
        {
            "id": r[0],
            "code": r[0],
            "label": r[1],
            "default_amount": r[2],
            "sort_order": r[3],
            "is_active": r[4],
            "collection_kind": "Thu hộ" if (r[5] or "") == "pass_through" else "Thu trung tâm",
            "collection_kind_code": r[5] or "center",
            "status": "active" if int(r[4] or 0) else "inactive",
        }
        for r in rows
    ]


def upsert_fee_type(conn, data: dict) -> dict:
    """Khai báo mã khoản thu + mức mặc định (áp dụng chung đợt khi chọn mã)."""
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    code = re.sub(r"[^a-z0-9_]+", "_", str(data.get("code") or "").strip().lower()).strip("_")
    if not code:
        raise ValueError("Cần mã khoản thu.")
    label = (data.get("label") or data.get("name") or "").strip() or code
    try:
        amount = float(data.get("default_amount") if data.get("default_amount") not in (None, "") else 0)
    except (TypeError, ValueError):
        raise ValueError("Mức mặc định không hợp lệ") from None
    sort_order = int(data.get("sort_order") or 200)
    active = data.get("is_active", data.get("status", 1))
    is_active = 0 if str(active).lower() in ("0", "inactive", "off", "false") else 1
    kind_raw = (data.get("collection_kind") or "center").strip().lower()
    kind = "pass_through" if kind_raw in ("pass_through", "thu hộ", "thu ho") else "center"
    exists = cur.execute("SELECT code FROM fee_type_catalog WHERE code = ?", (code,)).fetchone()
    if exists:
        cur.execute(
            "UPDATE fee_type_catalog SET label = ?, default_amount = ?, sort_order = ?, "
            "is_active = ?, collection_kind = ? WHERE code = ?",
            (label, amount, sort_order, is_active, kind, code),
        )
    else:
        cur.execute(
            "INSERT INTO fee_type_catalog (code, label, default_amount, sort_order, is_active, collection_kind) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (code, label, amount, sort_order, is_active, kind),
        )
    conn.commit()
    return {
        "id": code,
        "code": code,
        "label": label,
        "default_amount": amount,
        "sort_order": sort_order,
        "is_active": is_active,
        "collection_kind": kind,
        "status": "active" if is_active else "inactive",
    }


ALLOWED_WAIVER_PCTS = {0.0, 10.0, 50.0, 100.0}


def set_charge_waiver(
    conn,
    charge_id: int,
    *,
    waiver_pct: float | None = None,
    waiver_amount: float | None = None,
    due_date: str = "",
    decision_note: str = "",
    created_by: str = "",
) -> dict:
    """Miễn theo % hoặc số tiền (không cộng hai lần). 100% → phải đóng = 0."""
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    row = cur.execute(
        "SELECT id, amount_due, amount_adjust, COALESCE(waiver_pct, 0), due_date "
        "FROM student_charges WHERE id = ?",
        (charge_id,),
    ).fetchone()
    if not row:
        raise ValueError("Charge not found")
    due = float(row[1] or 0)
    current_adj = float(row[2] or 0)
    old_pct = float(row[3] or 0)
    old_waiver = -round(due * old_pct / 100.0, 0)
    other_adj = current_adj - old_waiver
    amt_raw = waiver_amount
    use_amount = amt_raw not in (None, "")
    if use_amount:
        try:
            amt = float(amt_raw)
        except (TypeError, ValueError):
            raise ValueError("Số tiền miễn không hợp lệ") from None
        if amt < 0:
            raise ValueError("Số tiền miễn không âm")
        if due > 0 and amt > due + 0.01:
            raise ValueError("Số miễn không vượt phải thu ban đầu")
        if due <= 0.01 or amt + 0.01 >= due:
            pct = 100.0
            new_waiver = -due
        else:
            pct = round(amt / due * 100.0, 4) if due else 0.0
            new_waiver = -round(amt, 0)
    else:
        try:
            pct = float(waiver_pct if waiver_pct is not None else 0)
        except (TypeError, ValueError):
            raise ValueError("Mức miễn không hợp lệ") from None
        if pct < 0 or pct > 100:
            raise ValueError("Mức miễn 0–100%")
        new_waiver = -round(due * pct / 100.0, 0)
        if pct >= 100:
            new_waiver = -due
            pct = 100.0
    new_adj = -due if pct >= 100 else other_adj + new_waiver
    delta = new_adj - current_adj
    due_val = str(due_date or "").strip()[:10] or (row[4] or "")
    if due_val:
        try:
            date.fromisoformat(due_val)
        except ValueError:
            due_val = row[4] or ""
    cur.execute(
        "UPDATE student_charges SET waiver_pct = ?, amount_adjust = ?, due_date = ? WHERE id = ?",
        (pct, new_adj, due_val or None, charge_id),
    )
    if abs(delta) > 0.01:
        cur.execute(
            "INSERT INTO fee_adjustments (charge_id, adj_type, amount, decision_note, status, created_by) "
            "VALUES (?, 'waiver', ?, ?, 'applied', ?)",
            (
                charge_id,
                delta,
                decision_note or (f"Miễn {abs(new_waiver):,.0f}" if use_amount else f"Miễn {pct:g}%"),
                created_by,
            ),
        )
    _recompute_charge(cur, charge_id)
    conn.commit()
    actual = max(0.0, due + new_adj)
    return {
        "ok": True,
        "charge_id": charge_id,
        "waiver_pct": pct,
        "amount_due": due,
        "amount_adjust": new_adj,
        "waived_amount": abs(new_waiver),
        "actual_due": actual,
        "due_date": due_val,
    }


def update_candidate_fee_file(
    conn,
    charge_id: int,
    *,
    full_name: str = "",
    email: str = "",
    phone: str = "",
    notes: str = "",
    fee_type: str = "",
    waiver_pct=None,
    waiver_amount=None,
    due_date: str = "",
    created_by: str = "",
) -> dict:
    """Kế toán cập nhật liên hệ hồ sơ thí sinh + khoản thu catalog + mức miễn."""
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    ch = cur.execute(
        "SELECT id, application_id, fee_type, title, amount_due, notes FROM student_charges WHERE id = ?",
        (charge_id,),
    ).fetchone()
    if not ch:
        raise ValueError("Charge not found")
    app_id = ch[1]
    if app_id:
        app = cur.execute(
            "SELECT full_name, email, phone, notes FROM applications WHERE id = ?",
            (app_id,),
        ).fetchone()
        if app:
            cur.execute(
                "UPDATE applications SET full_name = ?, email = ?, phone = ?, notes = ? WHERE id = ?",
                (
                    (full_name or "").strip() or app[0],
                    (email or "").strip() or (app[1] or ""),
                    (phone or "").strip() or (app[2] or ""),
                    notes if notes is not None and str(notes) != "" else (app[3] or ""),
                    app_id,
                ),
            )
    fee_code = (fee_type or "").strip()
    if fee_code and fee_code != (ch[2] or ""):
        known = {r[0] for r in cur.execute("SELECT code FROM fee_type_catalog").fetchall()}
        if fee_code not in known:
            raise ValueError("Khoản thu chưa được khai báo trong danh mục")
        label, default_amt = _catalog_fee(cur, fee_code, float(ch[4] or 0))
        new_due = default_amt if default_amt > 0 else float(ch[4] or 0)
        cur.execute(
            "UPDATE student_charges SET fee_type = ?, title = ?, amount_due = ? WHERE id = ?",
            (fee_code, label, new_due, charge_id),
        )
    if notes is not None and str(notes) != "" and not app_id:
        cur.execute("UPDATE student_charges SET notes = ? WHERE id = ?", (notes, charge_id))
    conn.commit()
    result = {"ok": True, "charge_id": charge_id, "application_id": app_id}
    if (waiver_amount is not None and str(waiver_amount) != "") or (
        waiver_pct is not None and str(waiver_pct) != ""
    ):
        result.update(
            set_charge_waiver(
                conn,
                charge_id,
                waiver_pct=waiver_pct,
                waiver_amount=waiver_amount,
                due_date=due_date,
                decision_note="Cập nhật hồ sơ thí sinh",
                created_by=created_by,
            )
        )
    elif due_date:
        due_val = str(due_date).strip()[:10]
        try:
            date.fromisoformat(due_val)
            cur.execute("UPDATE student_charges SET due_date = ? WHERE id = ?", (due_val, charge_id))
            conn.commit()
            result["due_date"] = due_val
        except ValueError:
            pass
    return result


def list_candidate_fee_files(conn, scopes, *, q: str = "", status: str = "") -> list[dict]:
    """Hồ sơ đăng ký có nghĩa vụ phí (không chỉ Đỗ+)."""
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_treasury_tables(cur)
    frag, params = _scopes_sql(scopes, "a.program_code")
    sql = (
        "SELECT a.id FROM applications a "
        f"WHERE {frag} AND a.status NOT IN ('withdrawn')"
    )
    if q:
        sql += (
            " AND (a.full_name LIKE ? OR COALESCE(a.email,'') LIKE ? OR COALESCE(a.phone,'') LIKE ? "
            "OR COALESCE(a.cccd,'') LIKE ? OR COALESCE(a.cfvg_app_no,'') LIKE ?)"
        )
        like = f"%{q}%"
        params.extend([like, like, like, like, like])
    app_ids = [r[0] for r in cur.execute(sql, params).fetchall()]
    for app_id in app_ids:
        try:
            ensure_inscription_charge(conn, app_id)
        except ValueError:
            continue
    charges = list_student_charges(conn, scopes, q=q, status=status)
    wanted = set(app_ids)
    by_app: dict = {}
    for c in charges:
        app_id = c.get("application_id")
        if app_id not in wanted:
            continue
        prev = by_app.get(app_id)
        if not prev or (c.get("fee_type") == "inscription" and prev.get("fee_type") != "inscription"):
            by_app[app_id] = c
    rows = list(by_app.values())
    if rows:
        try:
            placeholders = ",".join("?" * len(rows))
            flags = {
                r[0]: r
                for r in cur.execute(
                    f"SELECT id, IFNULL(exam_eligible_flag,''), IFNULL(english_cert,''), "
                    f"IFNULL(degree_verified,''), IFNULL(english_verified,''), IFNULL(final_result,''), "
                    f"IFNULL(board_decision,'') FROM applications WHERE id IN ({placeholders})",
                    [c.get("application_id") for c in rows],
                ).fetchall()
            }
            for c in rows:
                extra = flags.get(c.get("application_id"))
                if extra:
                    c["exam_eligible_flag"] = extra[1]
                    c["english_cert"] = extra[2]
                    c["degree_verified"] = extra[3]
                    c["english_verified"] = extra[4]
                    c["final_result"] = extra[5]
                    c["admit_decision"] = extra[6] or extra[5]
        except Exception:
            pass
    return rows


def collection_report(conn, scopes, *, q: str = "", fee_type: str = "", status: str = "") -> dict:
    """Báo cáo thu tiền chi tiết: đã thu, miễn phí, còn nợ — theo loại khoản thu và tháng nộp."""
    charges = list_student_charges(conn, scopes, q=q, fee_type=fee_type, status=status)
    fee_types = list_fee_types(conn)
    types = {t["code"]: t["label"] for t in fee_types}
    kinds = {t["code"]: t.get("collection_kind_code") or "center" for t in fee_types}
    due = paid = remaining = waived_total = actual_due = 0.0
    waived_count = overdue = foreign_count = 0
    by_type: dict[str, dict] = {}
    for c in charges:
        if str(c.get("currency") or "VND").upper() != "VND":
            foreign_count += 1
            continue
        d = float(c.get("amount_due") or 0)
        p = float(c.get("amount_paid") or 0)
        rem = float(c.get("remaining") or 0)
        w = float(c.get("waived_amount") or 0)
        ad = float(c.get("actual_due") or 0)
        due += d
        paid += p
        remaining += rem
        waived_total += w
        actual_due += ad
        if c.get("pay_status") == "waived" or ad <= 0.01:
            waived_count += 1
        if c.get("pay_status") == "overdue":
            overdue += 1
        slot = by_type.setdefault(
            c.get("fee_type") or "other",
            {"due": 0, "paid": 0, "remaining": 0, "waived": 0, "actual_due": 0},
        )
        slot["due"] += d
        slot["paid"] += p
        slot["remaining"] += rem
        slot["waived"] += w
        slot["actual_due"] += ad
    by_type_rows = []
    for code, slot in sorted(by_type.items()):
        by_type_rows.append(
            {
                "id": code,
                "fee_type": code,
                "title": types.get(code) or code,
                "amount_due": slot["due"],
                "waived_amount": slot["waived"],
                "actual_due": slot["actual_due"],
                "amount_paid": slot["paid"],
                "remaining": slot["remaining"],
                "collected_incl_waived": slot["paid"],
                "collection_kind": "Thu hộ" if kinds.get(code) == "pass_through" else "Thu trung tâm",
            }
        )
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    pay_rows = cur.execute(
        "SELECT substr(p.paid_at, 1, 7) AS ym, COALESCE(SUM(p.amount), 0) "
        "FROM fee_payments p "
        "JOIN student_charges sc ON sc.id = p.charge_id "
        "WHERE COALESCE(sc.currency, 'VND') = 'VND' "
        "GROUP BY ym ORDER BY ym DESC LIMIT 24"
    ).fetchall()
    by_month = [{"period": r[0] or "—", "amount_paid": float(r[1] or 0)} for r in pay_rows]
    rows = []
    for c in charges:
        row = dict(c)
        row["collected_incl_waived"] = float(c.get("amount_paid") or 0)
        row["actual_collected"] = float(c.get("amount_paid") or 0)
        row["amount_due_original"] = float(c.get("amount_due") or 0)
        kind = kinds.get(c.get("fee_type")) or "center"
        row["collection_kind"] = "Thu hộ" if kind == "pass_through" else "Thu trung tâm"
        rows.append(row)
    return {
        "overview": {
            "amount_due": due,
            "amount_waived": waived_total,
            "amount_actual_due": actual_due,
            "amount_paid": paid,
            "amount_remaining": remaining,
            "collected_incl_waived": paid,
            "actual_collected": paid,
            "waived_count": waived_count,
            "overdue_count": overdue,
            "charge_count": len(charges),
            "foreign_charge_count": foreign_count,
        },
        "by_type": by_type_rows,
        "by_month": by_month,
        "pipeline": [
            {"code": "due", "label": "Phải thu", "count": int(due)},
            {"code": "waived", "label": "Miễn phí", "count": int(waived_total)},
            {"code": "paid", "label": "Đã thu", "count": int(paid)},
            {"code": "remaining", "label": "Còn nợ", "count": int(remaining)},
        ],
        "rows": rows,
    }


def backfill_from_enrollment_fees(conn) -> dict:
    """Đồng bộ charge inscription từ enrollment_fees đã có (idempotent)."""
    cur = conn.cursor()
    ensure_treasury_tables(cur)
    rows = cur.execute("SELECT application_id FROM enrollment_fees").fetchall()
    n = 0
    for (app_id,) in rows:
        ensure_inscription_charge(conn, app_id)
        n += 1
    return {"synced": n}
