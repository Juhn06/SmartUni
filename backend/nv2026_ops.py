"""Nghiệp vụ họp 18/09/2026 — phiếu thu, cam kết, cấp mã, đợt xét, quốc tế, nhật ký."""
from __future__ import annotations

import json
from datetime import datetime, date
from typing import Any


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _cols(cur, table: str) -> set[str]:
    try:
        return {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def _add_col(cur, table: str, name: str, spec: str) -> None:
    if name not in _cols(cur, table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {spec}")


def ensure_nv2026_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS ops_audit_log ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "created_at TEXT NOT NULL, "
        "actor TEXT, user_id INTEGER, "
        "action TEXT NOT NULL, "
        "entity TEXT, entity_id TEXT, "
        "detail TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS payment_methods ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "code TEXT UNIQUE NOT NULL, "
        "label TEXT NOT NULL, "
        "label_en TEXT, "
        "sort_order INTEGER DEFAULT 0, "
        "status TEXT DEFAULT 'active')"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS round_fee_settings ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "round_id INTEGER NOT NULL, "
        "fee_type TEXT NOT NULL, "
        "unit_price REAL NOT NULL DEFAULT 0, "
        "default_times INTEGER NOT NULL DEFAULT 1, "
        "due_date TEXT, "
        "UNIQUE(round_id, fee_type))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS fee_receipts ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "charge_id INTEGER NOT NULL, "
        "application_id INTEGER, "
        "amount REAL NOT NULL, "
        "paid_at TEXT NOT NULL, "
        "method_code TEXT, "
        "txn_code TEXT, "
        "note TEXT, "
        "created_by TEXT, "
        "created_at TEXT, "
        "email_status TEXT DEFAULT '', "
        "email_sent_at TEXT)"
    )
    for _col, _spec in (
        ("buyer_name", "TEXT"),
        ("tax_code", "TEXT"),
        ("buyer_address", "TEXT"),
        ("buyer_type", "TEXT"),
    ):
        try:
            cur.execute(f"ALTER TABLE fee_receipts ADD COLUMN {_col} {_spec}")
        except Exception:
            pass
    try:
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_fee_receipts_txn "
            "ON fee_receipts(txn_code) WHERE txn_code IS NOT NULL AND txn_code != ''"
        )
    except Exception:
        pass
    cur.execute(
        "CREATE TABLE IF NOT EXISTS fee_commitments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "charge_id INTEGER NOT NULL, "
        "application_id INTEGER, "
        "reason TEXT, "
        "approved INTEGER NOT NULL DEFAULT 0, "
        "approved_by TEXT, "
        "approved_at TEXT, "
        "created_by TEXT, "
        "created_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS learners ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "application_id INTEGER UNIQUE, "
        "student_code TEXT UNIQUE, "
        "full_name TEXT, "
        "program_code TEXT, "
        "cccd TEXT, "
        "email TEXT, "
        "phone TEXT, "
        "enrolled_at TEXT, "
        "enrolled_by TEXT, "
        "created_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS grade_review_batches ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "program_code TEXT, "
        "locked_at TEXT, "
        "locked_by TEXT, "
        "gpa_method TEXT DEFAULT 'credit_weighted', "
        "snapshot_json TEXT, "
        "created_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS grade_review_batch_students ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "batch_id INTEGER NOT NULL, "
        "student_id INTEGER, "
        "application_id INTEGER, "
        "student_code TEXT, "
        "full_name TEXT, "
        "gpa REAL)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS intl_partners ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "code TEXT UNIQUE NOT NULL, "
        "name TEXT NOT NULL, "
        "country TEXT, "
        "status TEXT DEFAULT 'active')"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS intl_coop_programs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "partner_id INTEGER NOT NULL, "
        "name TEXT NOT NULL, "
        "direction TEXT, "
        "status TEXT DEFAULT 'active')"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS intl_agreements ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "partner_id INTEGER NOT NULL, "
        "code TEXT, "
        "title TEXT NOT NULL, "
        "kind TEXT DEFAULT 'agreement', "
        "version_label TEXT, "
        "effective_from TEXT, "
        "effective_to TEXT, "
        "program_code TEXT, "
        "exchange_kind TEXT, "
        "quota INTEGER, "
        "payment_note TEXT, "
        "status TEXT DEFAULT 'active', "
        "FOREIGN KEY (partner_id) REFERENCES intl_partners(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS intl_workflow_step_defs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "direction TEXT NOT NULL, "
        "code TEXT NOT NULL, "
        "label TEXT NOT NULL, "
        "sort_order INTEGER DEFAULT 0, "
        "UNIQUE(direction, code))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS intl_student_steps ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "intl_student_id INTEGER, "
        "step_code TEXT NOT NULL, "
        "direction TEXT, "
        "done_at TEXT, "
        "evidence_path TEXT, "
        "note TEXT, "
        "created_by TEXT)"
    )
    cur.execute("SELECT COUNT(*) FROM payment_methods")
    if not cur.fetchone()[0]:
        for i, (code, vi, en) in enumerate(
            (
                ("bank_transfer", "Chuyển khoản", "Bank transfer"),
                ("card", "Thẻ", "Card"),
                ("cash", "Tiền mặt", "Cash"),
                ("other", "Khác", "Other"),
            ),
            start=1,
        ):
            cur.execute(
                "INSERT INTO payment_methods (code, label, label_en, sort_order) VALUES (?,?,?,?)",
                (code, vi, en, i),
            )
    cur.execute("SELECT COUNT(*) FROM intl_workflow_step_defs")
    if not cur.fetchone()[0]:
        incoming = [
            ("invite", "Thư mời"),
            ("visa", "Visa"),
            ("arrival", "Nhập cảnh"),
            ("onboard", "Onboarding"),
            ("depart", "Xuất cảnh"),
        ]
        outgoing = [
            ("nominate", "Đề cử"),
            ("accept", "Đối tác chấp nhận"),
            ("visa", "Visa"),
            ("depart", "Xuất cảnh"),
            ("return", "Về nước"),
        ]
        for i, (code, label) in enumerate(incoming, start=1):
            cur.execute(
                "INSERT INTO intl_workflow_step_defs (direction, code, label, sort_order) "
                "VALUES ('incoming', ?, ?, ?)",
                (code, label, i),
            )
        for i, (code, label) in enumerate(outgoing, start=1):
            cur.execute(
                "INSERT INTO intl_workflow_step_defs (direction, code, label, sort_order) "
                "VALUES ('outgoing', ?, ?, ?)",
                (code, label, i),
            )


def audit(conn, *, actor: str = "", user_id: int | None = None, action: str,
          entity: str = "", entity_id: str | int | None = "", detail: str = "") -> None:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    cur.execute(
        "INSERT INTO ops_audit_log (created_at, actor, user_id, action, entity, entity_id, detail) "
        "VALUES (?,?,?,?,?,?,?)",
        (_now(), actor or "", user_id, action, entity, str(entity_id or ""), detail or ""),
    )


def list_audit_logs(conn, *, q: str = "", limit: int = 500) -> list[dict]:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    sql = (
        "SELECT id, created_at, actor, user_id, action, entity, entity_id, detail "
        "FROM ops_audit_log WHERE 1=1"
    )
    params: list[Any] = []
    if q:
        sql += " AND (action LIKE ? OR entity LIKE ? OR actor LIKE ? OR detail LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like, like])
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    keys = ["id", "created_at", "actor", "user_id", "action", "entity", "entity_id", "detail"]
    return [dict(zip(keys, r)) for r in cur.execute(sql, params).fetchall()]


def list_payment_methods(conn) -> list[dict]:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    keys = ["id", "code", "label", "label_en", "sort_order", "status"]
    return [
        dict(zip(keys, r))
        for r in cur.execute(
            "SELECT id, code, label, label_en, sort_order, status FROM payment_methods "
            "ORDER BY sort_order, id"
        ).fetchall()
    ]


def upsert_payment_method(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    code = (data.get("code") or "").strip().lower().replace(" ", "_")
    if not code:
        raise ValueError("Thiếu mã hình thức nộp")
    label = (data.get("label") or code).strip()
    existing = cur.execute("SELECT id FROM payment_methods WHERE code = ?", (code,)).fetchone()
    if existing:
        cur.execute(
            "UPDATE payment_methods SET label=?, label_en=?, sort_order=?, status=? WHERE id=?",
            (
                label,
                (data.get("label_en") or "")[:80],
                int(data.get("sort_order") or 0),
                (data.get("status") or "active")[:20],
                existing[0],
            ),
        )
        rid = existing[0]
    else:
        cur.execute(
            "INSERT INTO payment_methods (code, label, label_en, sort_order, status) VALUES (?,?,?,?,?)",
            (code, label, (data.get("label_en") or "")[:80], int(data.get("sort_order") or 0),
             (data.get("status") or "active")[:20]),
        )
        rid = cur.lastrowid
    conn.commit()
    return {"id": rid, "code": code, "label": label}


def list_round_fee_settings(conn, *, round_id: int | None = None, year: int | None = None) -> list[dict]:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    # Chỉ hiện khoản đóng của đúng một đợt. Năm chỉ để lọc danh sách đợt.
    if not round_id:
        return []
    sql = (
        "SELECT s.id, s.round_id, r.code, r.name, s.fee_type, s.unit_price, "
        "s.default_times, s.due_date FROM round_fee_settings s "
        "LEFT JOIN admission_rounds r ON r.id = s.round_id WHERE 1=1"
    )
    params: list[Any] = []
    if round_id:
        sql += " AND s.round_id = ?"
        params.append(round_id)
    if year:
        sql += " AND r.year = ?"
        params.append(int(year))
    sql += " ORDER BY s.round_id DESC, s.fee_type"
    keys = ["id", "round_id", "round_code", "round_name", "fee_type", "unit_price", "default_times", "due_date"]
    return [dict(zip(keys, r)) for r in cur.execute(sql, params).fetchall()]


def upsert_round_fee_setting(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    round_id = int(data.get("round_id") or 0)
    fee_type = (data.get("fee_type") or "").strip()
    if not round_id or not fee_type:
        raise ValueError("Thiếu đợt hoặc mã khoản thu")
    times = max(1, int(data.get("default_times") or 1))
    price = float(data.get("unit_price") or 0)
    due = (data.get("due_date") or "")[:10]
    cur.execute(
        "INSERT INTO round_fee_settings (round_id, fee_type, unit_price, default_times, due_date) "
        "VALUES (?,?,?,?,?) ON CONFLICT(round_id, fee_type) DO UPDATE SET "
        "unit_price=excluded.unit_price, default_times=excluded.default_times, due_date=excluded.due_date",
        (round_id, fee_type, price, times, due),
    )
    conn.commit()
    return {"round_id": round_id, "fee_type": fee_type, "unit_price": price, "default_times": times}


def list_receipts(conn, *, q: str = "", round_id: int | None = None) -> list[dict]:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    sql = (
        "SELECT fr.id, fr.charge_id, fr.application_id, fr.amount, fr.paid_at, fr.method_code, "
        "fr.txn_code, fr.note, fr.created_by, fr.email_status, "
        "IFNULL(fr.buyer_name, ''), IFNULL(fr.tax_code, ''), "
        "a.full_name, a.cccd, a.program_code, a.cfvg_app_no, sc.title, sc.fee_type "
        "FROM fee_receipts fr "
        "LEFT JOIN applications a ON a.id = fr.application_id "
        "LEFT JOIN student_charges sc ON sc.id = fr.charge_id WHERE 1=1"
    )
    params: list[Any] = []
    if q:
        like = f"%{q}%"
        sql += (
            " AND (IFNULL(a.full_name,'') LIKE ? OR IFNULL(a.cccd,'') LIKE ? "
            "OR IFNULL(fr.txn_code,'') LIKE ? OR IFNULL(a.cfvg_app_no,'') LIKE ?)"
        )
        params.extend([like, like, like, like])
    if round_id:
        sql += " AND a.round_id = ?"
        params.append(round_id)
    sql += " ORDER BY fr.id DESC LIMIT 800"
    keys = [
        "id", "charge_id", "application_id", "amount", "paid_at", "method_code",
        "txn_code", "note", "created_by", "email_status",
        "buyer_name", "tax_code",
        "full_name", "cccd", "program_code", "cfvg_app_no", "title", "fee_type",
    ]
    return [dict(zip(keys, r)) for r in cur.execute(sql, params).fetchall()]


def create_receipt(conn, data: dict, *, actor: str = "", user_id: int | None = None) -> dict:
    from treasury_ops import record_charge_payment, ensure_treasury_tables

    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    ensure_treasury_tables(cur)
    charge_id = int(data.get("charge_id") or 0)
    amount = float(data.get("amount") or 0)
    if charge_id <= 0 or amount <= 0:
        raise ValueError("Thiếu khoản thu hoặc số tiền")
    txn = (data.get("txn_code") or "").strip()
    if txn:
        hit = cur.execute("SELECT id FROM fee_receipts WHERE txn_code = ?", (txn,)).fetchone()
        if hit:
            raise ValueError(f"Mã giao dịch đã tồn tại (phiếu #{hit[0]})")
    method = (data.get("method_code") or "bank_transfer").strip()
    paid_at = (data.get("paid_at") or date.today().isoformat())[:19]
    note = (data.get("note") or "")[:400]
    ch = cur.execute(
        "SELECT id, application_id, student_id FROM student_charges WHERE id = ?",
        (charge_id,),
    ).fetchone()
    if not ch:
        raise ValueError("Không tìm thấy nghĩa vụ phí")
    app_id = ch[1]
    pay = record_charge_payment(
        conn,
        charge_id,
        amount=amount,
        proof_note=note or f"Phiếu thu {method}",
        method=method,
        bank_ref=txn,
        paid_at=paid_at[:10],
        created_by=actor,
    )
    buyer_name = (data.get("buyer_name") or "").strip()
    tax_code = (data.get("tax_code") or "").strip()
    buyer_address = (data.get("buyer_address") or data.get("address") or "").strip()
    buyer_type = (data.get("buyer_type") or "").strip() or ("company" if tax_code else "individual")
    cur.execute(
        "INSERT INTO fee_receipts (charge_id, application_id, amount, paid_at, method_code, "
        "txn_code, note, created_by, created_at, email_status, "
        "buyer_name, tax_code, buyer_address, buyer_type) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            charge_id, app_id, amount, paid_at, method, txn, note, actor, _now(), "",
            buyer_name, tax_code, buyer_address, buyer_type,
        ),
    )
    rid = cur.lastrowid
    try:
        from treasury_finance import save_invoice_profile

        person_id = None
        if app_id:
            link = cur.execute(
                "SELECT person_id FROM applications WHERE id = ?",
                (app_id,),
            ).fetchone()
            if link:
                person_id = link[0]
        save_invoice_profile(
            cur, data, application_id=app_id, person_id=person_id,
        )
    except Exception:
        pass
    refresh_exam_eligibility(conn, app_id)
    audit(conn, actor=actor, user_id=user_id, action="receipt.create", entity="fee_receipts",
          entity_id=rid, detail=f"charge={charge_id} amount={amount} txn={txn}")
    conn.commit()
    out = dict(pay)
    out["receipt_id"] = rid
    return out


def list_commitments(conn, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    sql = (
        "SELECT c.id, c.charge_id, c.application_id, c.reason, c.approved, c.approved_by, "
        "c.approved_at, a.full_name, a.cccd, a.program_code, a.cfvg_app_no "
        "FROM fee_commitments c LEFT JOIN applications a ON a.id = c.application_id WHERE 1=1"
    )
    params: list[Any] = []
    if q:
        like = f"%{q}%"
        sql += " AND (IFNULL(a.full_name,'') LIKE ? OR IFNULL(c.reason,'') LIKE ?)"
        params.extend([like, like])
    sql += " ORDER BY c.id DESC"
    keys = [
        "id", "charge_id", "application_id", "reason", "approved", "approved_by",
        "approved_at", "full_name", "cccd", "program_code", "cfvg_app_no",
    ]
    rows = []
    for r in cur.execute(sql, params).fetchall():
        d = dict(zip(keys, r))
        d["status"] = "approved" if d.get("approved") else "pending"
        rows.append(d)
    return rows


def create_commitment(conn, data: dict, *, actor: str = "", user_id: int | None = None) -> dict:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    charge_id = int(data.get("charge_id") or 0)
    if charge_id <= 0:
        raise ValueError("Thiếu nghĩa vụ phí")
    ch = cur.execute(
        "SELECT application_id FROM student_charges WHERE id = ?", (charge_id,)
    ).fetchone()
    if not ch:
        raise ValueError("Không tìm thấy nghĩa vụ")
    approved = 1 if str(data.get("approved") or "").lower() in ("1", "true", "yes") else 0
    cur.execute(
        "INSERT INTO fee_commitments (charge_id, application_id, reason, approved, approved_by, "
        "approved_at, created_by, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (
            charge_id, ch[0], (data.get("reason") or "")[:400], approved,
            actor if approved else "", _now() if approved else "",
            actor, _now(),
        ),
    )
    cid = cur.lastrowid
    refresh_exam_eligibility(conn, ch[0])
    audit(conn, actor=actor, user_id=user_id, action="commitment.create",
          entity="fee_commitments", entity_id=cid, detail=f"approved={approved}")
    conn.commit()
    return {"id": cid, "approved": approved, "charge_id": charge_id}


def approve_commitment(conn, commitment_id: int, *, actor: str = "", user_id: int | None = None) -> dict:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id, application_id FROM fee_commitments WHERE id = ?", (commitment_id,)
    ).fetchone()
    if not row:
        raise ValueError("Không tìm thấy cam kết")
    cur.execute(
        "UPDATE fee_commitments SET approved=1, approved_by=?, approved_at=? WHERE id=?",
        (actor, _now(), commitment_id),
    )
    refresh_exam_eligibility(conn, row[1])
    audit(conn, actor=actor, user_id=user_id, action="commitment.approve",
          entity="fee_commitments", entity_id=commitment_id)
    conn.commit()
    return {"id": commitment_id, "approved": 1}


def _table_exists_exam_commitment(cur, application_id: int) -> bool:
    cols = {r[1] for r in cur.execute("PRAGMA table_info(applications)").fetchall()}
    if "examinee_confirmed_at" not in cols:
        return False
    confirmed = cur.execute(
        "SELECT IFNULL(examinee_confirmed_at, '') FROM applications WHERE id = ?",
        (int(application_id),),
    ).fetchone()
    if not confirmed or not (confirmed[0] or "").strip():
        return False
    row = cur.execute(
        "SELECT 1 FROM student_charges sc "
        "JOIN fee_commitments fc ON fc.charge_id = sc.id AND fc.approved = 1 "
        "WHERE sc.application_id = ? AND sc.fee_type = 'entrance_exam' LIMIT 1",
        (int(application_id),),
    ).fetchone()
    return bool(row)


def refresh_exam_eligibility(conn, application_id: int | None) -> str:
    """Đủ điều kiện xếp hội đồng theo xác nhận dự thi và lệ phí thi của đợt."""
    if not application_id:
        return ""
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    from learner_spine import entrance_sitting_ready

    ready, _why = entrance_sitting_ready(cur, int(application_id))
    if not ready and _table_exists_exam_commitment(cur, int(application_id)):
        ready = True
    flag = "yes" if ready else "no"
    try:
        cur.execute(
            "UPDATE applications SET exam_eligible_flag = ? WHERE id = ?",
            (flag, application_id),
        )
    except Exception:
        pass
    return flag


def import_payments(conn, rows: list[dict], *, actor: str = "", user_id: int | None = None) -> dict:
    from admission_ops import normalize_cccd
    from treasury_ops import ensure_treasury_tables, ensure_inscription_charge

    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    ensure_treasury_tables(cur)
    from treasury_finance import record_bank_line

    created = skipped = errors = 0
    msgs = []
    for raw in rows:
        cccd = ""
        amount = 0.0
        fee_type = ""
        txn = ""
        paid_at = date.today().isoformat()
        payer = ""
        try:
            cccd = normalize_cccd(raw.get("cccd") or raw.get("CCCD") or "")
            payer = (raw.get("full_name") or raw.get("payer_name") or raw.get("ho_ten") or "").strip()
            if not cccd:
                raise ValueError("Thiếu CCCD")
            amount = float(raw.get("amount") or raw.get("so_tien") or 0)
            fee_type = (raw.get("fee_type") or raw.get("ma_khoan") or "inscription").strip()
            txn = (raw.get("txn_code") or raw.get("ma_gd") or "").strip()
            paid_at = (raw.get("paid_at") or raw.get("ngay") or date.today().isoformat())[:10]
            round_code = (raw.get("round_code") or raw.get("dot") or "").strip()
            app_sql = (
                "SELECT a.id FROM applications a "
                "WHERE REPLACE(REPLACE(REPLACE(UPPER(IFNULL(a.cccd,'')),' ',''),'-',''),'.','') = ?"
            )
            params: list[Any] = [cccd]
            if round_code:
                app_sql += (
                    " AND (a.round_id IN (SELECT id FROM admission_rounds WHERE code = ?) "
                    "OR IFNULL(a.intake_session,'') = ?)"
                )
                params.extend([round_code, round_code])
            app_sql += " ORDER BY a.id DESC LIMIT 1"
            hit = cur.execute(app_sql, params).fetchone()
            if not hit:
                raise ValueError("Không khớp CCCD/đợt")
            app_id = hit[0]
            ch = cur.execute(
                "SELECT id FROM student_charges WHERE application_id = ? AND fee_type = ? "
                "ORDER BY id DESC LIMIT 1",
                (app_id, fee_type),
            ).fetchone()
            if not ch:
                try:
                    ensure_inscription_charge(conn, app_id)
                except Exception:
                    pass
                ch = cur.execute(
                    "SELECT id FROM student_charges WHERE application_id = ? AND fee_type = ? "
                    "ORDER BY id DESC LIMIT 1",
                    (app_id, fee_type),
                ).fetchone()
            if not ch:
                raise ValueError("Không có nghĩa vụ phí tương ứng")
            bal = cur.execute(
                "SELECT COALESCE(amount_due,0) + COALESCE(amount_adjust,0) - COALESCE(amount_paid,0) "
                "FROM student_charges WHERE id = ?",
                (ch[0],),
            ).fetchone()
            remaining = float(bal[0] or 0) if bal else 0
            if amount + 0.01 < remaining:
                match_status = "short"
            elif amount > remaining + 0.01:
                match_status = "over"
            else:
                match_status = "matched"
            receipt = create_receipt(
                conn,
                {
                    "charge_id": ch[0],
                    "amount": amount,
                    "txn_code": txn,
                    "method_code": (raw.get("method_code") or raw.get("hinh_thuc") or "bank_transfer"),
                    "paid_at": paid_at,
                    "note": "Import thu",
                    "buyer_name": payer,
                    "identity_number": cccd,
                },
                actor=actor,
                user_id=user_id,
            )
            record_bank_line(
                cur,
                txn_code=txn,
                amount=amount,
                paid_at=paid_at,
                payer_name=payer,
                identity_number=cccd,
                fee_type=fee_type,
                match_status=match_status,
                charge_id=ch[0],
                receipt_id=receipt.get("receipt_id"),
                note="",
            )
            created += 1
        except ValueError as e:
            status = "duplicate" if "đã tồn tại" in str(e) else "unmatched"
            record_bank_line(
                cur,
                txn_code=txn,
                amount=amount,
                paid_at=paid_at,
                payer_name=payer,
                identity_number=cccd,
                fee_type=fee_type,
                match_status=status,
                note=str(e),
            )
            if status == "duplicate":
                skipped += 1
            else:
                errors += 1
                msgs.append(str(e))
        except Exception as e:
            record_bank_line(
                cur,
                txn_code=txn,
                amount=amount,
                paid_at=paid_at,
                payer_name=payer,
                identity_number=cccd,
                fee_type=fee_type,
                match_status="unmatched",
                note=str(e),
            )
            errors += 1
            msgs.append(str(e))
    audit(conn, actor=actor, user_id=user_id, action="receipt.import", entity="fee_receipts",
          detail=f"created={created} skipped={skipped} errors={errors}")
    conn.commit()
    return {"created": created, "skipped_dup": skipped, "errors": errors, "messages": msgs[:20]}


def list_receipt_emails(conn, *, q: str = "") -> list[dict]:
    rows = list_receipts(conn, q=q)
    for r in rows:
        r["status"] = r.get("email_status") or "unsent"
    return rows


def mark_receipt_email(conn, receipt_id: int, *, status: str = "sent", actor: str = "") -> dict:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    cur.execute(
        "UPDATE fee_receipts SET email_status=?, email_sent_at=? WHERE id=?",
        (status[:40], _now(), receipt_id),
    )
    if not cur.rowcount:
        raise ValueError("Không tìm thấy phiếu thu")
    audit(conn, actor=actor, action="receipt.email", entity="fee_receipts", entity_id=receipt_id,
          detail=status)
    conn.commit()
    return {"id": receipt_id, "email_status": status}


def bulk_receipt_emails(conn, *, round_id: int | None = None, actor: str = "") -> dict:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    sql = "SELECT fr.id FROM fee_receipts fr LEFT JOIN applications a ON a.id = fr.application_id WHERE IFNULL(fr.email_status,'') = ''"
    params: list[Any] = []
    if round_id:
        sql += " AND a.round_id = ?"
        params.append(round_id)
    ids = [r[0] for r in cur.execute(sql, params).fetchall()]
    for rid in ids:
        cur.execute(
            "UPDATE fee_receipts SET email_status='queued', email_sent_at=? WHERE id=?",
            (_now(), rid),
        )
    audit(conn, actor=actor, action="receipt.email_bulk", entity="fee_receipts",
          detail=f"queued={len(ids)} round={round_id}")
    conn.commit()
    return {"queued": len(ids)}


def list_verification_queue(conn, scopes, *, q: str = "") -> list[dict]:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    frag, params = _scopes_sql(scopes, "a.program_code")
    sql = (
        "SELECT a.id, a.cfvg_app_no, a.full_name, a.cccd, a.program_code, a.status, "
        "IFNULL(a.needs_verification,''), IFNULL(a.inspect_khao_thi,''), "
        "IFNULL(a.inspect_thanh_tra,''), IFNULL(a.english_verified,''), "
        "IFNULL(a.degree_verified,''), IFNULL(a.eligible_for_admit,''), r.code "
        "FROM applications a LEFT JOIN admission_rounds r ON r.id = a.round_id "
        f"WHERE {frag} AND ("
        "IFNULL(a.needs_verification,'') IN ('1','yes','true') "
        "OR IFNULL(a.inspect_khao_thi,'') IN ('1','yes','true') "
        "OR IFNULL(a.inspect_thanh_tra,'') IN ('1','yes','true') "
        "OR IFNULL(a.english_verified,'') IN ('','pending') "
        "OR IFNULL(a.degree_verified,'') IN ('','pending')"
        ")"
    )
    if q:
        like = f"%{q}%"
        sql += " AND (a.full_name LIKE ? OR IFNULL(a.cccd,'') LIKE ? OR IFNULL(a.cfvg_app_no,'') LIKE ?)"
        params.extend([like, like, like])
    sql += " ORDER BY a.id DESC LIMIT 800"
    keys = [
        "id", "cfvg_app_no", "full_name", "cccd", "program_code", "status",
        "needs_verification", "inspect_khao_thi", "inspect_thanh_tra",
        "english_verified", "degree_verified", "eligible_for_admit", "round_code",
    ]
    rows = []
    for r in cur.execute(sql, params).fetchall():
        d = dict(zip(keys, r))
        d["application_id"] = d["id"]
        rows.append(d)
    return rows


def bulk_flag_applications(conn, ids: list[int], field: str, value: str, *, actor: str = "") -> dict:
    allowed = {
        "needs_verification", "inspect_khao_thi", "inspect_thanh_tra", "inspect_partner",
        "eligible_for_admit", "english_verified", "degree_verified",
    }
    if field not in allowed:
        raise ValueError("Cột không được đánh dấu hàng loạt")
    cur = conn.cursor()
    n = 0
    for aid in ids:
        try:
            cur.execute(f"UPDATE applications SET {field} = ? WHERE id = ?", (str(value)[:40], aid))
            n += cur.rowcount
        except Exception:
            continue
    audit(conn, actor=actor, action="application.bulk_flag", entity="applications",
          detail=f"{field}={value} n={n}")
    conn.commit()
    return {"updated": n, "field": field, "value": value}


def assign_student_codes(
    conn,
    *,
    prefix: str,
    start: int,
    application_ids: list[int] | None = None,
    round_id: int | None = None,
    preview: bool = False,
    actor: str = "",
) -> dict:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    prefix = (prefix or "HV").strip() or "HV"
    start = int(start or 1)
    from person_profile import ensure_person_tables

    ensure_person_tables(cur)
    sql = (
        "SELECT a.id, a.full_name, a.program_code, "
        "COALESCE(NULLIF(pe.learner_code,''), NULLIF(a.student_code_mba,''), ''), "
        "a.status "
        "FROM applications a "
        "LEFT JOIN program_enrollments pe ON pe.application_id = a.id WHERE 1=1 "
    )
    params: list[Any] = []
    if round_id:
        sql += " AND a.round_id = ?"
        params.append(round_id)
    if application_ids:
        ph = ",".join("?" * len(application_ids))
        sql += f" AND a.id IN ({ph})"
        params.extend(application_ids)
    sql += " ORDER BY a.id"
    apps = cur.execute(sql, params).fetchall()
    preview_rows = []
    assigned = 0
    skipped = 0
    n = start
    used = set()
    try:
        used |= {
            r[0] for r in cur.execute(
                "SELECT student_code FROM class_students "
                "WHERE student_code IS NOT NULL AND student_code != ''"
            ).fetchall()
            if r[0]
        }
    except Exception:
        pass
    used |= {
        r[0] for r in cur.execute(
            "SELECT student_code_mba FROM applications "
            "WHERE student_code_mba IS NOT NULL AND student_code_mba != ''"
        ).fetchall()
        if r[0]
    }
    used |= {
        r[0] for r in cur.execute(
            "SELECT learner_code FROM program_enrollments "
            "WHERE learner_code IS NOT NULL AND learner_code != ''"
        ).fetchall()
        if r[0]
    }
    for aid, name, prog, existing, status in apps:
        if (status or "") != "official":
            skipped += 1
            continue
        code = (existing or "").strip()
        if not code:
            while True:
                code = f"{prefix}{n:04d}"
                n += 1
                if code not in used:
                    break
            used.add(code)
        preview_rows.append({
            "application_id": aid,
            "full_name": name,
            "student_code": code,
            "learner_code": code,
            "program_code": prog,
        })
        if preview:
            continue
        cur.execute(
            "UPDATE applications SET student_code_mba = CASE "
            "WHEN IFNULL(student_code_mba,'')='' THEN ? ELSE student_code_mba END WHERE id=?",
            (code, aid),
        )
        from learner_spine import upsert_learner_for_application

        upsert_learner_for_application(conn, int(aid))
        cur.execute(
            "UPDATE program_enrollments SET learner_code = ? "
            "WHERE application_id = ? AND IFNULL(learner_code,'') = ''",
            (code, aid),
        )
        assigned += 1
    if not preview:
        audit(conn, actor=actor, action="student_code.assign", entity="applications",
              detail=f"assigned={assigned} prefix={prefix}")
        conn.commit()
    return {"preview": preview, "rows": preview_rows, "assigned": assigned, "skipped": skipped}


def confirm_enrollment(conn, application_id: int, *, actor: str = "") -> dict:
    """Ghi ngày vào học trên hồ sơ theo học đã có. Không tạo thêm một người."""
    cur = conn.cursor()
    from person_profile import ensure_person_tables

    ensure_person_tables(cur)
    app = cur.execute(
        "SELECT id, IFNULL(status,''), IFNULL(student_code_mba,'') FROM applications WHERE id = ?",
        (application_id,),
    ).fetchone()
    if not app:
        raise ValueError("Không tìm thấy hồ sơ")
    if app[1] != "official":
        raise ValueError("Chỉ ghi nhận vào học khi quyết định trúng tuyển đã có hiệu lực.")
    pe = cur.execute(
        "SELECT IFNULL(learner_code,'') FROM program_enrollments WHERE application_id = ?",
        (application_id,),
    ).fetchone()
    code = ((pe[0] if pe else "") or app[2] or "").strip()
    if not code:
        raise ValueError("Chưa cấp mã học viên")
    prior = cur.execute(
        "SELECT id, IFNULL(enrolled_at,'') FROM learners WHERE application_id = ?",
        (application_id,),
    ).fetchone()
    if prior and (prior[1] or "").strip():
        raise ValueError("Đã ghi nhận vào học")
    from learner_spine import upsert_learner_for_application

    upsert_learner_for_application(conn, int(application_id))
    today = _now()[:10]
    cur.execute(
        "UPDATE learners SET enrolled_at = ?, enrolled_by = ?, "
        "student_code = CASE WHEN IFNULL(student_code,'')='' THEN ? ELSE student_code END "
        "WHERE application_id = ?",
        (today, actor, code, application_id),
    )
    lid = cur.execute(
        "SELECT id FROM learners WHERE application_id = ?",
        (application_id,),
    ).fetchone()
    audit(conn, actor=actor, action="enrollment.confirm", entity="program_enrollments",
          entity_id=lid[0] if lid else application_id,
          detail=f"app={application_id} code={code}")
    conn.commit()
    return {
        "learner_id": lid[0] if lid else None,
        "learner_code": code,
        "student_code": code,
        "enrolled_at": today,
    }


def list_review_batches(conn, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    sql = (
        "SELECT id, title, program_code, locked_at, locked_by, gpa_method, created_at "
        "FROM grade_review_batches WHERE 1=1"
    )
    params: list[Any] = []
    if q:
        sql += " AND (title LIKE ? OR IFNULL(program_code,'') LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    sql += " ORDER BY id DESC"
    keys = ["id", "title", "program_code", "locked_at", "locked_by", "gpa_method", "created_at"]
    rows = [dict(zip(keys, r)) for r in cur.execute(sql, params).fetchall()]
    for r in rows:
        r["status"] = "locked" if r.get("locked_at") else "open"
        r["student_count"] = cur.execute(
            "SELECT COUNT(*) FROM grade_review_batch_students WHERE batch_id=?", (r["id"],)
        ).fetchone()[0]
    return rows


def create_review_batch(conn, data: dict, *, actor: str = "") -> dict:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Thiếu tiêu đề đợt xét")
    cur.execute(
        "INSERT INTO grade_review_batches (title, program_code, gpa_method, created_at) VALUES (?,?,?,?)",
        (title, (data.get("program_code") or "")[:20], "credit_weighted", _now()),
    )
    bid = cur.lastrowid
    ids = [int(x) for x in (data.get("student_ids") or []) if str(x).strip()]
    for sid in ids:
        st = cur.execute(
            "SELECT cs.id, cs.full_name, cs.student_code, cs.application_id FROM class_students cs WHERE cs.id=?",
            (sid,),
        ).fetchone()
        if not st:
            continue
        gpa = compute_student_gpa(conn, sid)
        cur.execute(
            "INSERT INTO grade_review_batch_students (batch_id, student_id, application_id, student_code, full_name, gpa) "
            "VALUES (?,?,?,?,?,?)",
            (bid, st[0], st[3], st[2], st[1], gpa),
        )
    conn.commit()
    return {"id": bid, "title": title, "student_count": len(ids)}


def lock_review_batch(conn, batch_id: int, *, actor: str = "") -> dict:
    cur = conn.cursor()
    row = cur.execute("SELECT id, locked_at FROM grade_review_batches WHERE id=?", (batch_id,)).fetchone()
    if not row:
        raise ValueError("Không tìm thấy đợt xét")
    if row[1]:
        raise ValueError("Đợt đã khóa")
    students = cur.execute(
        "SELECT student_id, student_code, full_name, gpa FROM grade_review_batch_students WHERE batch_id=?",
        (batch_id,),
    ).fetchall()
    snap = []
    for sid, code, name, gpa in students:
        grades = []
        try:
            grades = [
                {"course": r[0], "score": r[1], "credits": r[2]}
                for r in cur.execute(
                    "SELECT c.code, cg.score, IFNULL(c.credits, 3) "
                    "FROM course_grades cg JOIN courses c ON c.id = cg.course_id "
                    "WHERE cg.student_id = ?",
                    (sid,),
                ).fetchall()
            ]
        except Exception:
            pass
        snap.append({"student_id": sid, "student_code": code, "full_name": name, "gpa": gpa, "grades": grades})
    cur.execute(
        "UPDATE grade_review_batches SET locked_at=?, locked_by=?, snapshot_json=? WHERE id=?",
        (_now(), actor, json.dumps(snap, ensure_ascii=False), batch_id),
    )
    audit(conn, actor=actor, action="review_batch.lock", entity="grade_review_batches", entity_id=batch_id)
    conn.commit()
    return {"id": batch_id, "locked": True, "students": len(snap)}


def compute_student_gpa(conn, student_id: int) -> float | None:
    cur = conn.cursor()
    try:
        rows = cur.execute(
            "SELECT cg.score, IFNULL(c.credits, 3) FROM course_grades cg "
            "JOIN courses c ON c.id = cg.course_id WHERE cg.student_id = ? AND cg.score IS NOT NULL",
            (student_id,),
        ).fetchall()
    except Exception:
        return None
    num = den = 0.0
    for score, cred in rows:
        try:
            s = float(score)
            cr = float(cred or 0) or 1.0
        except (TypeError, ValueError):
            continue
        num += s * cr
        den += cr
    if den <= 0:
        return None
    return round(num / den, 2)


def list_partners(conn, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    sql = "SELECT id, code, name, country, status FROM intl_partners WHERE 1=1"
    params: list[Any] = []
    if q:
        sql += " AND (code LIKE ? OR name LIKE ? OR IFNULL(country,'') LIKE ?)"
        params.extend([f"%{q}%"] * 3)
    sql += " ORDER BY code"
    return [dict(zip(["id", "code", "name", "country", "status"], r)) for r in cur.execute(sql, params)]


def upsert_partner(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "").strip()
    if not code or not name:
        raise ValueError("Thiếu mã hoặc tên trường đối tác")
    cur.execute(
        "INSERT INTO intl_partners (code, name, country, status) VALUES (?,?,?,?) "
        "ON CONFLICT(code) DO UPDATE SET name=excluded.name, country=excluded.country, status=excluded.status",
        (code, name, (data.get("country") or "")[:80], (data.get("status") or "active")[:20]),
    )
    conn.commit()
    return {"code": code, "name": name}


def import_partners(conn, rows: list[dict]) -> dict:
    n = 0
    for raw in rows:
        code = (raw.get("code") or raw.get("ma") or "").strip().upper()
        name = (raw.get("name") or raw.get("ten") or "").strip()
        if not code or not name:
            continue
        upsert_partner(conn, {"code": code, "name": name, "country": raw.get("country") or raw.get("quoc_gia")})
        n += 1
    return {"imported": n}


def list_coop_programs(conn, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    sql = (
        "SELECT c.id, c.name, c.direction, c.status, p.code, p.name FROM intl_coop_programs c "
        "JOIN intl_partners p ON p.id = c.partner_id WHERE 1=1"
    )
    params: list[Any] = []
    if q:
        sql += " AND (c.name LIKE ? OR p.code LIKE ? OR p.name LIKE ?)"
        params.extend([f"%{q}%"] * 3)
    sql += " ORDER BY c.id DESC"
    keys = ["id", "name", "direction", "status", "partner_code", "partner_name"]
    return [dict(zip(keys, r)) for r in cur.execute(sql, params)]


def create_coop_program(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    partner_id = int(data.get("partner_id") or 0)
    if not partner_id:
        code = (data.get("partner_code") or "").strip().upper()
        hit = cur.execute("SELECT id FROM intl_partners WHERE code = ?", (code,)).fetchone()
        if not hit:
            raise ValueError("Không tìm thấy trường đối tác")
        partner_id = hit[0]
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Thiếu tên chương trình hợp tác")
    cur.execute(
        "INSERT INTO intl_coop_programs (partner_id, name, direction, status) VALUES (?,?,?,?)",
        (partner_id, name, (data.get("direction") or "incoming")[:20], (data.get("status") or "active")[:20]),
    )
    conn.commit()
    return {"id": cur.lastrowid, "name": name}


def list_workflow_steps(conn, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    sql = (
        "SELECT id, direction, code, label, sort_order FROM intl_workflow_step_defs WHERE 1=1"
    )
    params: list[Any] = []
    if q:
        sql += " AND (code LIKE ? OR label LIKE ? OR direction LIKE ?)"
        params.extend([f"%{q}%"] * 3)
    sql += " ORDER BY direction, sort_order"
    return [dict(zip(["id", "direction", "code", "label", "sort_order"], r)) for r in cur.execute(sql, params)]


def create_workflow_step(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    direction = (data.get("direction") or "incoming").strip().lower()
    if direction not in ("incoming", "outgoing"):
        direction = "incoming"
    code = (data.get("code") or "").strip()
    label = (data.get("label") or "").strip()
    if not code or not label:
        raise ValueError("Cần mã bước và tên bước.")
    try:
        sort_order = int(data.get("sort_order") or 0)
    except (TypeError, ValueError):
        sort_order = 0
    exists = cur.execute(
        "SELECT id FROM intl_workflow_step_defs WHERE direction = ? AND code = ?",
        (direction, code),
    ).fetchone()
    if exists:
        raise ValueError("Mã bước đã tồn tại cho chiều này.")
    cur.execute(
        "INSERT INTO intl_workflow_step_defs (direction, code, label, sort_order) VALUES (?, ?, ?, ?)",
        (direction, code, label, sort_order),
    )
    conn.commit()
    return {
        "id": cur.lastrowid,
        "direction": direction,
        "code": code,
        "label": label,
        "sort_order": sort_order,
    }


def list_exchange_reports(conn, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    sql = (
        "SELECT p.code, p.name, p.country, COUNT(c.id) FROM intl_partners p "
        "LEFT JOIN intl_coop_programs c ON c.partner_id = p.id WHERE 1=1"
    )
    params: list[Any] = []
    if q:
        sql += " AND (p.code LIKE ? OR p.name LIKE ?)"
        params.extend([f"%{q}%"] * 2)
    sql += " GROUP BY p.id ORDER BY p.code"
    rows = []
    for r in cur.execute(sql, params).fetchall():
        rows.append({"id": r[0], "partner_code": r[0], "partner_name": r[1], "country": r[2], "program_count": r[3]})
    return rows


def list_student_numbering(conn, scopes, *, q: str = "") -> list[dict]:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    ensure_nv2026_tables(cur)
    frag, params = _scopes_sql(scopes, "a.program_code")
    from person_profile import ensure_person_tables

    ensure_person_tables(cur)
    sql = (
        "SELECT a.id, a.full_name, a.program_code, a.cccd, a.cfvg_app_no, "
        "IFNULL(a.student_code_mba,''), "
        "COALESCE(NULLIF(pe.learner_code,''), NULLIF(l.student_code,''), ''), "
        "IFNULL(l.enrolled_at,''), a.status, a.board_decision "
        "FROM applications a "
        "LEFT JOIN learners l ON l.application_id = a.id "
        "LEFT JOIN program_enrollments pe ON pe.application_id = a.id "
        f"WHERE {frag} AND (a.status IN ('passed','paid','official') "
        "OR IFNULL(a.final_result,'') IN ('Admitted','Trúng tuyển') "
        "OR IFNULL(a.board_decision,'') LIKE '%trúng%')"
    )
    if q:
        like = f"%{q}%"
        sql += (
            " AND (a.full_name LIKE ? OR IFNULL(a.cccd,'') LIKE ? "
            "OR IFNULL(a.student_code_mba,'') LIKE ? OR IFNULL(pe.learner_code,'') LIKE ?)"
        )
        params.extend([like, like, like, like])
    sql += " ORDER BY a.id DESC"
    keys = [
        "id", "full_name", "program_code", "cccd", "cfvg_app_no",
        "student_code_mba", "learner_code", "enrolled_at", "status", "board_decision",
    ]
    rows = []
    for r in cur.execute(sql, params).fetchall():
        d = dict(zip(keys, r))
        d["student_code"] = d["learner_code"] or d["student_code_mba"]
        d["application_id"] = d["id"]
        rows.append(d)
    return rows


def import_course_grades(conn, rows: list[dict], *, actor: str = "") -> dict:
    """Import điểm: CCCD + mã SV + mã HP + khóa. Không ghi đè điểm đã khóa."""
    from admission_ops import normalize_cccd
    from coord_ops import upsert_grade

    cur = conn.cursor()
    updated = skipped_locked = not_found = 0
    for raw in rows:
        cccd = normalize_cccd(raw.get("cccd") or raw.get("CCCD") or "")
        scode = str(raw.get("student_code") or raw.get("ma_sv") or "").strip()
        course_code = str(raw.get("course_code") or raw.get("ma_hp") or "").strip()
        if not course_code or (not cccd and not scode):
            not_found += 1
            continue
        sql = (
            "SELECT cs.id, cs.class_id FROM class_students cs "
            "JOIN class_groups cg ON cg.id = cs.class_id WHERE 1=1"
        )
        params: list[Any] = []
        if scode:
            sql += " AND IFNULL(cs.student_code,'') = ?"
            params.append(scode)
        if cccd:
            sql += (
                " AND cs.application_id IN (SELECT id FROM applications WHERE "
                "REPLACE(REPLACE(REPLACE(UPPER(IFNULL(cccd,'')),' ',''),'-',''),'.','') = ?)"
            )
            params.append(cccd)
        cohort = raw.get("cohort") or raw.get("khoa") or raw.get("cohort_year")
        if cohort:
            sql += " AND CAST(IFNULL(cg.cohort_year,'') AS TEXT) = ?"
            params.append(str(cohort))
        sql += " LIMIT 1"
        st = cur.execute(sql, params).fetchone()
        if not st:
            not_found += 1
            continue
        course = cur.execute(
            "SELECT id FROM courses WHERE code = ? ORDER BY id DESC LIMIT 1", (course_code,)
        ).fetchone()
        if not course:
            not_found += 1
            continue
        score = raw.get("score") or raw.get("diem")
        try:
            upsert_grade(conn, int(st[1]), int(st[0]), int(course[0]), score=float(score))
            updated += 1
        except ValueError as e:
            if "khóa" in str(e).lower() or "lock" in str(e).lower():
                skipped_locked += 1
            else:
                not_found += 1
        except Exception:
            not_found += 1
    audit(conn, actor=actor, action="grades.import", entity="course_grades",
          detail=f"updated={updated} locked={skipped_locked} miss={not_found}")
    conn.commit()
    return {"updated": updated, "skipped_locked": skipped_locked, "not_found": not_found}
