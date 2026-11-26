"""
Phân hệ Marcom — Trần Anh Tuấn (TuanTA).

Nguồn: Tran_Anh_Tuan_digitalized_revised_v2.
Ba hoạt động: marketing (kế hoạch, ngân sách, người quan tâm), sự kiện, thiết kế và nội dung kênh.
Ngân sách do Kế toán rồi Ban Giám đốc phê duyệt trước khi triển khai.
Chi phí thực tế lấy từ phân bổ đã xác nhận, Marcom không tự đánh dấu đã thanh toán.
Hồ sơ cá nhân dùng chung với tuyển sinh; CCCD không bắt buộc lúc tiếp nhận marketing.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta


def ensure_marcom_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS marcom_leads ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "full_name TEXT NOT NULL, "
        "email TEXT, "
        "phone TEXT, "
        "occupation TEXT, "
        "company TEXT, "
        "program_interest TEXT, "  # MBA,MMS,MSCM or free text
        "source TEXT, "  # web | facebook | event | referral | other
        "status TEXT DEFAULT 'new', "  # new | nurturing | handed_ts | converted | dropped
        "notes TEXT, "
        "handed_at TEXT, "
        "application_id INTEGER, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    try:
        cur.execute("ALTER TABLE marcom_leads ADD COLUMN cccd TEXT")
    except Exception:
        pass
    cur.execute(
        "CREATE TABLE IF NOT EXISTS marcom_campaigns ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "period_start TEXT, "
        "period_end TEXT, "
        "channel TEXT DEFAULT 'online', "  # online | offline | mixed
        "program_codes TEXT, "
        "budget_planned REAL DEFAULT 0, "
        "budget_spent REAL DEFAULT 0, "
        "kpi_notes TEXT, "
        "status TEXT DEFAULT 'planned', "  # planned | running | done | cancelled
        "report_summary TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS marcom_events ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "event_type TEXT DEFAULT 'workshop', "
        # tuyen_sinh | workshop | webinar | conference | customer | alumni | other
        "event_date TEXT, "
        "location TEXT, "
        "program_codes TEXT, "
        "content TEXT, "
        "speakers TEXT, "  # bio / profile diễn giả
        "guest_list TEXT, "
        "status TEXT DEFAULT 'planned', "
        # planned|promoting = trước; ongoing = trong; done = sau; cancelled
        "post_event_report TEXT, "
        "budget REAL DEFAULT 0, "
        "alumni_event_id INTEGER, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS marcom_assets ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "asset_type TEXT DEFAULT 'image', "  # image | video | design | text | print
        "file_path TEXT, "
        "tags TEXT, "
        "program_codes TEXT, "
        "used_for TEXT, "
        "notes TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    # 1.5 — đồng tổ chức Marcom + TS; kế hoạch truyền thông
    for col, typ in (
        ("comms_plan", "TEXT"),
        ("co_org_notes", "TEXT"),
        ("admission_owner", "TEXT"),
        ("phase_before_notes", "TEXT"),
        ("phase_during_notes", "TEXT"),
        ("phase_after_notes", "TEXT"),
    ):
        try:
            cur.execute(f"ALTER TABLE marcom_events ADD COLUMN {col} {typ}")
        except Exception:
            pass
    # Danh sách người quan tâm / đăng ký tham dự (có cấu trúc)
    cur.execute(
        "CREATE TABLE IF NOT EXISTS marcom_event_registrants ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "event_id INTEGER NOT NULL, "
        "full_name TEXT NOT NULL, "
        "email TEXT, "
        "phone TEXT, "
        "company TEXT, "
        "occupation TEXT, "
        "program_interest TEXT, "
        "interest_level TEXT DEFAULT 'medium', "  # low | medium | high | hot
        "attendance_status TEXT DEFAULT 'registered', "
        # invited | registered | attended | no_show
        "followup_status TEXT DEFAULT 'pending', "
        # pending | contacted | reminded | handed_ts | closed
        "contact_note TEXT, "
        "notes TEXT, "
        "lead_id INTEGER, "
        "updated_at TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "FOREIGN KEY (event_id) REFERENCES marcom_events(id))"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_marcom_reg_event "
        "ON marcom_event_registrants(event_id)"
    )
    _extend_marcom_schema(cur)


def _extend_marcom_schema(cur) -> None:
    """Cột và bảng bổ sung theo mô tả v2. Thêm cột nếu DB đã có bảng cũ."""
    additions = {
        "marcom_leads": (
            ("person_id", "INTEGER"),
            ("owner", "TEXT"),
            ("consent_marketing", "TEXT"),
            ("processing_basis", "TEXT"),
            ("campaign_id", "INTEGER"),
            ("event_id", "INTEGER"),
            ("received_at", "TEXT"),
        ),
        "marcom_campaigns": (
            ("campaign_code", "TEXT"),
            ("objective", "TEXT"),
            ("owner", "TEXT"),
            ("budget_approved", "REAL DEFAULT 0"),
            ("kpi_plan", "TEXT"),
            ("kpi_result", "TEXT"),
            ("round_refs", "TEXT"),
            ("approved_kt_by", "TEXT"),
            ("approved_bgd_by", "TEXT"),
            ("voucher_note", "TEXT"),
            ("acceptance_note", "TEXT"),
        ),
        "marcom_events": (
            ("objective", "TEXT"),
            ("online_url", "TEXT"),
            ("host_unit", "TEXT"),
            ("co_units", "TEXT"),
            ("campaign_id", "INTEGER"),
            ("supplier_notes", "TEXT"),
            ("budget_status", "TEXT DEFAULT 'planned'"),
            ("approved_kt_by", "TEXT"),
            ("approved_bgd_by", "TEXT"),
            ("voucher_note", "TEXT"),
            ("acceptance_note", "TEXT"),
        ),
        "marcom_event_registrants": (
            ("person_id", "INTEGER"),
            ("participant_role", "TEXT DEFAULT 'guest'"),
            ("checkin_token", "TEXT"),
            ("checked_in_at", "TEXT"),
        ),
        "marcom_assets": (
            ("topic", "TEXT"),
            ("campaign_id", "INTEGER"),
            ("event_id", "INTEGER"),
            ("assignee", "TEXT"),
            ("approver", "TEXT"),
            ("due_date", "TEXT"),
            ("version_no", "TEXT"),
            ("content_status", "TEXT DEFAULT 'requested'"),
            ("outsource", "TEXT DEFAULT 'no'"),
            ("budget_planned", "REAL DEFAULT 0"),
            ("budget_status", "TEXT DEFAULT 'planned'"),
            ("usage_rights", "TEXT"),
            ("usage_until", "TEXT"),
            ("published_url", "TEXT"),
            ("publish_at", "TEXT"),
            ("channel_code", "TEXT"),
            ("acceptance_note", "TEXT"),
            ("payment_note", "TEXT"),
            ("approved_kt_by", "TEXT"),
            ("approved_bgd_by", "TEXT"),
        ),
    }
    for table, cols in additions.items():
        have = {r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, typ in cols:
            if name not in have:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS source_touchpoints ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "person_id INTEGER, "
        "lead_id INTEGER, "
        "source TEXT, "
        "campaign_id INTEGER, "
        "event_id INTEGER, "
        "channel_code TEXT, "
        "received_at TEXT, "
        "note TEXT, "
        "touch_kind TEXT DEFAULT 'intake')"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS candidate_interests ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "person_id INTEGER, "
        "lead_id INTEGER, "
        "program_code TEXT NOT NULL, "
        "care_status TEXT DEFAULT 'new', "
        "owner TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_interest_lead_prog "
        "ON candidate_interests(lead_id, program_code)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS marketing_channels ("
        "code TEXT PRIMARY KEY, "
        "name TEXT NOT NULL, "
        "kind TEXT DEFAULT 'online')"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS campaign_cost_allocations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "campaign_id INTEGER, "
        "event_id INTEGER, "
        "content_id INTEGER, "
        "payment_id INTEGER, "
        "amount REAL NOT NULL DEFAULT 0, "
        "note TEXT, "
        "status TEXT DEFAULT 'proposed', "
        "confirmed_by TEXT, "
        "confirmed_at TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS content_publications ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "content_id INTEGER NOT NULL, "
        "channel_code TEXT, "
        "scheduled_at TEXT, "
        "published_url TEXT, "
        "status TEXT DEFAULT 'scheduled', "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS marcom_event_speakers ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "event_id INTEGER NOT NULL, "
        "full_name TEXT NOT NULL, "
        "email TEXT, "
        "phone TEXT, "
        "bio TEXT, "
        "material_note TEXT)"
    )
    for code, name, kind in (
        ("web", "Website", "online"),
        ("facebook", "Mạng xã hội", "online"),
        ("email", "Email", "online"),
        ("event", "Sự kiện", "offline"),
        ("press", "Báo chí", "offline"),
        ("referral", "Giới thiệu", "offline"),
        ("other", "Khác", "offline"),
    ):
        cur.execute(
            "INSERT OR IGNORE INTO marketing_channels (code, name, kind) VALUES (?,?,?)",
            (code, name, kind),
        )
    try:
        cur.execute("ALTER TABLE asst_tasks ADD COLUMN source_ref TEXT")
    except Exception:
        pass


EVENT_STATUS_PHASE = {
    "planned": "before",
    "submitted": "before",
    "approved": "before",
    "promoting": "before",
    "ongoing": "during",
    "followup": "after",
    "done": "after",
    "reported": "after",
    "cancelled": "n/a",
}

BUDGET_STATUSES = (
    "planned",
    "submitted",
    "approved_kt",
    "approved",
    "running",
    "evaluating",
    "reconciling",
    "closed",
    "cancelled",
    "done",
)
PARTICIPANT_ROLES = ("guest", "candidate", "learner", "alumni", "speaker", "partner")
CONTENT_STATUSES = (
    "requested",
    "producing",
    "accepted",
    "payment_file",
    "archived",
)

INTEREST_LEVELS = ("low", "medium", "high", "hot")
ATTENDANCE_STATUSES = ("invited", "registered", "attended", "no_show")
FOLLOWUP_STATUSES = ("pending", "contacted", "reminded", "handed_ts", "closed")


def event_phase_label(status: str, lang: str = "vi") -> str:
    phase = EVENT_STATUS_PHASE.get((status or "").strip(), "")
    if lang == "en":
        return {
            "before": "Before event",
            "during": "During event",
            "after": "After event",
            "n/a": "—",
        }.get(phase, "")
    return {
        "before": "Trước sự kiện",
        "during": "Trong sự kiện",
        "after": "Sau sự kiện",
        "n/a": "—",
    }.get(phase, "")


def list_marcom_events(conn, *, q: str = "", event_type: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    rows = cur.execute(
        "SELECT e.id, e.title, e.event_type, e.event_date, e.location, e.program_codes, "
        "e.content, e.speakers, e.guest_list, e.status, e.post_event_report, e.budget, "
        "e.alumni_event_id, e.created_at, "
        "IFNULL(e.comms_plan,''), IFNULL(e.co_org_notes,''), IFNULL(e.admission_owner,''), "
        "IFNULL(e.phase_before_notes,''), IFNULL(e.phase_during_notes,''), "
        "IFNULL(e.phase_after_notes,''), "
        "(SELECT COUNT(*) FROM marcom_event_registrants r WHERE r.event_id = e.id) AS reg_count, "
        "(SELECT COUNT(*) FROM marcom_event_registrants r WHERE r.event_id = e.id "
        " AND r.attendance_status = 'attended') AS attended_count, "
        "IFNULL(e.objective,''), IFNULL(e.online_url,''), IFNULL(e.host_unit,''), e.campaign_id, "
        "IFNULL(e.supplier_notes,''), IFNULL(e.budget_status,'planned'), "
        "IFNULL(e.voucher_note,''), IFNULL(e.acceptance_note,'') "
        "FROM marcom_events e ORDER BY COALESCE(e.event_date, '') DESC, e.id DESC"
    ).fetchall()
    out = []
    for r in rows:
        item = {
            "id": r[0],
            "title": r[1],
            "event_type": r[2],
            "event_date": r[3],
            "location": r[4],
            "program_codes": r[5],
            "content": r[6],
            "speakers": r[7],
            "guest_list": r[8],
            "status": r[9],
            "post_event_report": r[10],
            "budget": r[11],
            "alumni_event_id": r[12],
            "created_at": r[13],
            "comms_plan": r[14],
            "co_org_notes": r[15],
            "admission_owner": r[16],
            "phase_before_notes": r[17],
            "phase_during_notes": r[18],
            "phase_after_notes": r[19],
            "registrant_count": r[20] or 0,
            "attended_count": r[21] or 0,
            "objective": r[22],
            "online_url": r[23],
            "host_unit": r[24],
            "campaign_id": r[25],
            "supplier_notes": r[26],
            "budget_status": r[27] or "planned",
            "voucher_note": r[28],
            "acceptance_note": r[29],
            "phase": EVENT_STATUS_PHASE.get(r[9] or "", ""),
            "phase_label": event_phase_label(r[9] or ""),
            "budget_actual": confirmed_cost(cur, event_id=r[0]),
        }
        out.append(item)
    if event_type:
        et = event_type.strip().lower()
        out = [x for x in out if str(x.get("event_type") or "").lower() == et]
    if q:
        ql = q.lower()
        out = [
            x
            for x in out
            if ql in " ".join(str(v or "") for v in x.values()).lower()
        ]
    return out


def get_marcom_event(conn, event_id: int) -> dict | None:
    rows = list_marcom_events(conn)
    for r in rows:
        if r["id"] == event_id:
            return r
    return None


def list_event_registrants(conn, event_id: int, *, q: str = "") -> list[dict]:
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    rows = cur.execute(
        "SELECT r.id, r.event_id, r.full_name, r.email, r.phone, r.company, r.occupation, "
        "r.program_interest, r.interest_level, r.attendance_status, r.followup_status, "
        "r.contact_note, r.notes, r.lead_id, r.updated_at, r.created_at, "
        "l.application_id, l.status AS lead_status, "
        "r.person_id, IFNULL(r.participant_role,'guest'), r.checkin_token, r.checked_in_at "
        "FROM marcom_event_registrants r "
        "LEFT JOIN marcom_leads l ON l.id = r.lead_id "
        "WHERE r.event_id = ? ORDER BY r.id DESC",
        (event_id,),
    ).fetchall()
    keys = [
        "id", "event_id", "full_name", "email", "phone", "company", "occupation",
        "program_interest", "interest_level", "attendance_status", "followup_status",
        "contact_note", "notes", "lead_id", "updated_at", "created_at",
        "application_id", "lead_status",
        "person_id", "participant_role", "checkin_token", "checked_in_at",
    ]
    out = [dict(zip(keys, r)) for r in rows]
    if q:
        ql = q.lower()
        out = [
            x for x in out
            if ql in " ".join(str(v or "") for v in x.values()).lower()
        ]
    return out


def upsert_event_registrant(conn, event_id: int, data: dict, *, registrant_id: int | None = None) -> dict:
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    if not get_marcom_event(conn, event_id):
        raise ValueError("Sự kiện không tồn tại")
    name = (data.get("full_name") or "").strip()
    if not name and not registrant_id:
        raise ValueError("Cần họ tên người quan tâm")
    interest = (data.get("interest_level") or "medium").strip().lower()
    if interest not in INTEREST_LEVELS:
        interest = "medium"
    attendance = (data.get("attendance_status") or "registered").strip().lower()
    if attendance not in ATTENDANCE_STATUSES:
        attendance = "registered"
    followup = (data.get("followup_status") or "pending").strip().lower()
    if followup not in FOLLOWUP_STATUSES:
        followup = "pending"
    role = (data.get("participant_role") or "guest").strip().lower()
    if role not in PARTICIPANT_ROLES:
        role = "guest"
    now = date.today().isoformat()
    fields = {
        "full_name": name,
        "email": (data.get("email") or "").strip(),
        "phone": (data.get("phone") or "").strip(),
        "company": (data.get("company") or "").strip(),
        "occupation": (data.get("occupation") or "").strip(),
        "program_interest": (data.get("program_interest") or "").strip(),
        "interest_level": interest,
        "attendance_status": attendance,
        "followup_status": followup,
        "contact_note": (data.get("contact_note") or "").strip(),
        "notes": (data.get("notes") or "").strip(),
        "participant_role": role,
        "updated_at": now,
    }
    if registrant_id:
        existing = cur.execute(
            "SELECT id, full_name FROM marcom_event_registrants WHERE id = ? AND event_id = ?",
            (registrant_id, event_id),
        ).fetchone()
        if not existing:
            raise ValueError("Người đăng ký không tồn tại")
        if not fields["full_name"]:
            fields["full_name"] = existing[1]
        sets = ", ".join(f"{k}=?" for k in fields)
        cur.execute(
            f"UPDATE marcom_event_registrants SET {sets} WHERE id = ?",
            (*fields.values(), registrant_id),
        )
        rid = registrant_id
    else:
        token = uuid.uuid4().hex[:12]
        cur.execute(
            "INSERT INTO marcom_event_registrants "
            "(event_id, full_name, email, phone, company, occupation, program_interest, "
            "interest_level, attendance_status, followup_status, contact_note, notes, "
            "participant_role, checkin_token, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                event_id,
                fields["full_name"],
                fields["email"],
                fields["phone"],
                fields["company"],
                fields["occupation"],
                fields["program_interest"],
                fields["interest_level"],
                fields["attendance_status"],
                fields["followup_status"],
                fields["contact_note"],
                fields["notes"],
                fields["participant_role"],
                token,
                now,
            ),
        )
        rid = cur.lastrowid
    person_id, _created, _hints = resolve_person(
        cur,
        full_name=fields["full_name"],
        email=fields["email"],
        phone=fields["phone"],
    )
    cur.execute(
        "UPDATE marcom_event_registrants SET person_id = ? "
        "WHERE id = ? AND IFNULL(person_id, 0) = 0",
        (person_id, rid),
    )
    conn.commit()
    rows = list_event_registrants(conn, event_id)
    return next(x for x in rows if x["id"] == rid)


def registrant_to_lead(conn, registrant_id: int) -> dict:
    """Create/link marcom_leads from event registrant (sau sự kiện → chăm sóc lead)."""
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    row = cur.execute(
        "SELECT id, event_id, full_name, email, phone, company, occupation, "
        "program_interest, interest_level, notes, lead_id, contact_note, "
        "IFNULL(participant_role,'guest') "
        "FROM marcom_event_registrants WHERE id = ?",
        (registrant_id,),
    ).fetchone()
    if not row:
        raise ValueError("Người đăng ký không tồn tại")
    if (row[12] or "guest") != "candidate":
        raise ValueError(
            "Người này không phải ứng viên. Đặt vai trò «Ứng viên» trước khi ghi nhận nhu cầu tuyển sinh."
        )
    if row[10]:
        # Already linked — return lead + application if any
        lead_id = row[10]
        cur.execute(
            "SELECT application_id, status FROM marcom_leads WHERE id = ?",
            (lead_id,),
        )
        lr = cur.fetchone()
        return {
            "registrant_id": registrant_id,
            "lead_id": lead_id,
            "created": False,
            "application_id": (lr[0] if lr else None),
            "lead_status": (lr[1] if lr else None),
        }
    note_bits = [
        f"Từ sự kiện Marcom #{row[1]}",
        f"mức quan tâm: {row[8] or '—'}",
    ]
    if row[11]:
        note_bits.append(f"LH: {row[11]}")
    if row[9]:
        note_bits.append(str(row[9]))
    note = "; ".join(note_bits)
    created_lead = intake_interest(
        conn,
        {
            "full_name": row[2],
            "email": row[3],
            "phone": row[4],
            "occupation": row[6],
            "company": row[5],
            "program_interest": row[7],
            "source": "event",
            "notes": note,
            "event_id": row[1],
        },
    )
    lead_id = created_lead["id"]
    cur = conn.cursor()
    cur.execute(
        "UPDATE marcom_event_registrants SET lead_id = ?, followup_status = 'contacted', "
        "updated_at = ? WHERE id = ?",
        (lead_id, date.today().isoformat(), registrant_id),
    )
    conn.commit()
    return {
        "registrant_id": registrant_id,
        "lead_id": lead_id,
        "created": bool(created_lead.get("created")),
        "application_id": None,
        "lead_status": created_lead.get("status") or "new",
        "duplicate_hints": created_lead.get("duplicate_hints") or [],
    }


def registrant_hand_to_ts(conn, registrant_id: int, round_id: int | None = None) -> dict:
    """Event registrant → lead (nếu chưa) → hồ sơ TS (Nhận hồ sơ)."""
    to_lead = registrant_to_lead(conn, registrant_id)
    lead_id = to_lead["lead_id"]
    handed = hand_lead_to_ts(conn, lead_id, round_id=round_id)
    return {
        "registrant_id": registrant_id,
        "lead_id": lead_id,
        "lead_created": to_lead.get("created"),
        "application_id": handed.get("application_id"),
        "status": handed.get("status"),
        "program_code": handed.get("program_code"),
        "round_id": handed.get("round_id"),
    }


def export_event_registrants(conn, event_id: int | None = None) -> list[dict]:
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    sql = (
        "SELECT e.title, e.event_type, e.event_date, e.location, e.program_codes, e.status, "
        "r.full_name, r.email, r.phone, r.company, r.occupation, r.program_interest, "
        "r.interest_level, r.attendance_status, r.followup_status, r.contact_note, r.notes, "
        "r.lead_id, r.updated_at "
        "FROM marcom_event_registrants r "
        "JOIN marcom_events e ON e.id = r.event_id "
    )
    params: list = []
    if event_id:
        sql += "WHERE r.event_id = ? "
        params.append(event_id)
    sql += "ORDER BY e.event_date DESC, r.id DESC"
    rows = cur.execute(sql, params).fetchall()
    keys = [
        "event_title", "event_type", "event_date", "location", "program_codes", "event_status",
        "full_name", "email", "phone", "company", "occupation", "program_interest",
        "interest_level", "attendance_status", "followup_status", "contact_note", "notes",
        "lead_id", "updated_at",
    ]
    return [dict(zip(keys, r)) for r in rows]


def export_event_followup(conn, event_id: int | None = None) -> list[dict]:
    """File sau sự kiện: liên hệ + mức độ quan tâm (1.5.4)."""
    rows = export_event_registrants(conn, event_id=event_id)
    # Prefer attended / high interest for follow-up report
    out = []
    for r in rows:
        out.append(
            {
                "event_title": r["event_title"],
                "event_date": r["event_date"],
                "full_name": r["full_name"],
                "email": r["email"],
                "phone": r["phone"],
                "company": r["company"],
                "program_interest": r["program_interest"],
                "interest_level": r["interest_level"],
                "attendance_status": r["attendance_status"],
                "followup_status": r["followup_status"],
                "contact_note": r["contact_note"],
                "updated_at": r["updated_at"],
            }
        )
    return out



def seed_marcom_draft_data(conn) -> dict:
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    created = {"leads": 0, "campaigns": 0, "events": 0, "assets": 0}

    cur.execute("SELECT COUNT(*) FROM marcom_leads")
    if cur.fetchone()[0] == 0:
        samples = [
            (
                "Nguyễn Minh Hà",
                "ha.nm@email.com",
                "0902111001",
                "Chuyên viên marketing",
                "FPT Software",
                "MBA",
                "facebook",
                "new",
                "Quan tâm khóa tối",
            ),
            (
                "Trần Quốc Bảo",
                "bao.tq@email.com",
                "0902111002",
                "Trưởng phòng logistics",
                "Shopee Express",
                "MSCM",
                "event",
                "nurturing",
                "Gặp tại workshop SCM",
            ),
            (
                "Lê Thị Mai",
                "mai.lt@email.com",
                "0902111003",
                "Analyst",
                "Vietcombank",
                "MMS",
                "web",
                "handed_ts",
                "Đã chuyển Tuyển sinh",
            ),
        ]
        for row in samples:
            cur.execute(
                "INSERT INTO marcom_leads "
                "(full_name, email, phone, occupation, company, program_interest, source, status, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
            created["leads"] += 1
        # mark handed sample
        cur.execute(
            "UPDATE marcom_leads SET handed_at = ? WHERE status = 'handed_ts'",
            (date.today().isoformat(),),
        )

    cur.execute("SELECT COUNT(*) FROM marcom_campaigns")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO marcom_campaigns "
            "(title, period_start, period_end, channel, program_codes, budget_planned, budget_spent, "
            "kpi_notes, status, report_summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "Quảng bá tuyển sinh Q3",
                date.today().replace(month=7, day=1).isoformat(),
                date.today().replace(month=9, day=30).isoformat(),
                "mixed",
                "MBA,MMS,MSCM",
                120_000_000,
                45_000_000,
                "Leads mục tiêu 200; conversion TS 15%",
                "running",
                "",
            ),
        )
        created["campaigns"] += 1

    cur.execute("SELECT COUNT(*) FROM marcom_events")
    if cur.fetchone()[0] == 0:
        events = [
            (
                "Workshop Supply Chain 4.0",
                "workshop",
                (date.today() + timedelta(days=21)).isoformat(),
                "X Hà Nội",
                "MSCM",
                "Giới thiệu chương trình MSCM và case study ngành logistics.",
                "TS. Nguyễn A — chuyên gia SCM (bio ngắn).",
                "Khách doanh nghiệp + alumni MSCM",
                "promoting",
                "",
                15_000_000,
                "FB Ads + email alumni; landing đăng ký.",
                "Đồng tổ chức với Tuyển sinh — booth tư vấn tại sự kiện.",
                "NhungLH",
                "Mời doanh nghiệp logistics; checklist booth TS.",
                "",
                "",
            ),
            (
                "Webinar MBA Evening",
                "webinar",
                (date.today() - timedelta(days=2)).isoformat(),
                "Online Zoom",
                "MBA",
                "Tư vấn lộ trình MBA bán thời gian.",
                "Đồng GĐ học thuật",
                "Ứng viên quan tâm MBA",
                "done",
                "50 đăng ký / 38 tham dự; follow-up hot leads.",
                5_000_000,
                "Zoom + LinkedIn + Zalo OA.",
                "TS hỗ trợ Q&A và thu lead trong webinar.",
                "GiaoNTQ",
                "Gửi invitation + remind 1 ngày trước.",
                "TS tư vấn live chat; Marcom vận hành Zoom.",
                "Cập nhật mức quan tâm; remind nộp hồ sơ tuần tới.",
            ),
            (
                "Gặp gỡ Alumni X",
                "alumni",
                (date.today() + timedelta(days=45)).isoformat(),
                "X TP.HCM",
                "MBA,MMS,MSCM",
                "Networking alumni toàn CT.",
                "Đại diện Alumni board",
                "Alumni các khóa",
                "planned",
                "",
                25_000_000,
                "Email alumni + poster campus.",
                "TS hỗ trợ khách mời tiềm năng (ứng viên).",
                "",
                "Lên list khách mời + nội dung truyền thông.",
                "",
                "",
            ),
        ]
        for row in events:
            cur.execute(
                "INSERT INTO marcom_events "
                "(title, event_type, event_date, location, program_codes, content, speakers, "
                "guest_list, status, post_event_report, budget, "
                "comms_plan, co_org_notes, admission_owner, "
                "phase_before_notes, phase_during_notes, phase_after_notes) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                row,
            )
            created["events"] += 1

        # Registrants sample for done webinar + promoting workshop
        cur.execute("SELECT id, title FROM marcom_events")
        by_title = {r[1]: r[0] for r in cur.fetchall()}
        webinar_id = by_title.get("Webinar MBA Evening")
        workshop_id = by_title.get("Workshop Supply Chain 4.0")
        if webinar_id:
            regs = [
                ("Phạm Thu Trang", "trang.pt@email.com", "0903000001", "VCB", "Analyst", "MBA", "hot", "attended", "reminded", "Quan tâm khai giảng Aug"),
                ("Hoàng Minh Đức", "duc.hm@email.com", "0903000002", "FPT", "PM", "MBA", "high", "attended", "contacted", "Nhắc gửi brochure"),
                ("Vũ Lan Anh", "anh.vl@email.com", "0903000003", "", "Freelance", "MBA", "medium", "registered", "pending", "No-show Zoom — gọi lại"),
            ]
            for full_name, email, phone, company, occ, prog, interest, att, fu, note in regs:
                cur.execute(
                    "INSERT INTO marcom_event_registrants "
                    "(event_id, full_name, email, phone, company, occupation, program_interest, "
                    "interest_level, attendance_status, followup_status, contact_note, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        webinar_id, full_name, email, phone, company, occ, prog,
                        interest, att, fu, note, date.today().isoformat(),
                    ),
                )
        if workshop_id:
            cur.execute(
                "INSERT INTO marcom_event_registrants "
                "(event_id, full_name, email, phone, company, occupation, program_interest, "
                "interest_level, attendance_status, followup_status, contact_note, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    workshop_id,
                    "Trần Quốc Bảo",
                    "bao.tq@email.com",
                    "0902111002",
                    "Shopee Express",
                    "Trưởng phòng logistics",
                    "MSCM",
                    "high",
                    "registered",
                    "pending",
                    "Đã mời — chờ xác nhận tham dự",
                    date.today().isoformat(),
                ),
            )
    cur.execute("SELECT COUNT(*) FROM marcom_assets")
    if cur.fetchone()[0] == 0:
        assets = [
            ("Logo X chuẩn", "design", None, "logo,brand", "*", "Slide / ấn phẩm", "File gốc AI/PNG"),
            ("Banner tuyển sinh Q3", "image", None, "banner,ts", "MBA,MMS,MSCM", "Facebook Ads", ""),
            ("Video teaser workshop", "video", None, "video,event", "MSCM", "YouTube / FB", ""),
        ]
        for title, atype, path, tags, programs, used, notes in assets:
            cur.execute(
                "INSERT INTO marcom_assets "
                "(title, asset_type, file_path, tags, program_codes, used_for, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (title, atype, path, tags, programs, used, notes),
            )
            created["assets"] += 1

    # Backfill demo registrants if events exist but table empty (existing DBs)
    cur.execute("SELECT COUNT(*) FROM marcom_event_registrants")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "SELECT id FROM marcom_events WHERE title LIKE '%Webinar%' OR status = 'done' "
            "ORDER BY id LIMIT 1"
        )
        ev = cur.fetchone()
        if ev:
            cur.execute(
                "INSERT INTO marcom_event_registrants "
                "(event_id, full_name, email, phone, company, program_interest, "
                "interest_level, attendance_status, followup_status, contact_note, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ev[0],
                    "Phạm Thu Trang",
                    "trang.pt@email.com",
                    "0903000001",
                    "VCB",
                    "MBA",
                    "hot",
                    "attended",
                    "reminded",
                    "Demo E2E — follow-up sau sự kiện",
                    date.today().isoformat(),
                ),
            )

    # Enrich old event rows missing 1.5 phase fields + more registrants for demo
    cur.execute(
        "SELECT id, title, status, IFNULL(comms_plan,''), IFNULL(admission_owner,'') "
        "FROM marcom_events"
    )
    for eid, title, status, comms, owner in cur.fetchall():
        if not (comms or "").strip():
            updates = {
                "comms_plan": "Kế hoạch truyền thông (demo): kênh online + email.",
                "co_org_notes": "Đồng tổ chức Marcom + Tuyển sinh (demo).",
                "phase_before_notes": "Trước SK: mời / chăm sóc người quan tâm đăng ký.",
                "phase_during_notes": "Trong SK: TS tư vấn; Marcom vận hành.",
                "phase_after_notes": "Sau SK: follow-up + cập nhật mức quan tâm.",
            }
            if not (owner or "").strip():
                updates["admission_owner"] = "NhungLH"
            # Align demo statuses for 3 phases when still all planned
            tlow = (title or "").lower()
            if "webinar" in tlow and status not in ("done", "cancelled", "ongoing"):
                updates["status"] = "done"
            elif status in ("planned", "") and "workshop" in tlow:
                updates["status"] = "promoting"
            elif status in ("planned", "") and "alumni" in tlow:
                updates["status"] = "planned"
            sets = ", ".join(f"{k}=?" for k in updates)
            cur.execute(
                f"UPDATE marcom_events SET {sets} WHERE id = ?",
                (*updates.values(), eid),
            )
            status = updates.get("status", status)
        cur.execute(
            "SELECT COUNT(*) FROM marcom_event_registrants WHERE event_id = ?", (eid,)
        )
        nreg = cur.fetchone()[0]
        if nreg >= 2:
            continue
        demo_regs = [
            ("Nguyễn Thị Hoa", "hoa.nt@email.com", "0903111001", "Techcombank", "MBA", "high", "registered", "pending", "Đã mời — chờ xác nhận"),
            ("Lê Văn Nam", "nam.lv@email.com", "0903111002", "Vinamilk", "MMS", "medium", "invited", "pending", "Gửi brochure"),
        ]
        if (status or "") == "done" or "webinar" in (title or "").lower():
            demo_regs = [
                ("Phạm Thu Trang", "trang.pt@email.com", "0903000001", "VCB", "MBA", "hot", "attended", "reminded", "Quan tâm khai giảng"),
                ("Hoàng Minh Đức", "duc.hm@email.com", "0903000002", "FPT", "MBA", "high", "attended", "contacted", "Nhắc gửi brochure"),
                ("Vũ Lan Anh", "anh.vl@email.com", "0903000003", "", "MBA", "medium", "no_show", "pending", "Gọi lại sau no-show"),
            ]
        for full_name, email, phone, company, prog, interest, att, fu, note in demo_regs:
            exists = cur.execute(
                "SELECT 1 FROM marcom_event_registrants WHERE event_id = ? AND email = ?",
                (eid, email),
            ).fetchone()
            if exists:
                continue
            cur.execute(
                "INSERT INTO marcom_event_registrants "
                "(event_id, full_name, email, phone, company, program_interest, "
                "interest_level, attendance_status, followup_status, contact_note, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    eid, full_name, email, phone, company, prog,
                    interest, att, fu, note, date.today().isoformat(),
                ),
            )

    # One-shot: ensure demo webinar is in «sau sự kiện» phase for 1.5 walkthrough
    cur.execute(
        "UPDATE marcom_events SET status = 'done' "
        "WHERE lower(title) LIKE '%webinar%' AND status NOT IN ('done','cancelled')"
    )

    conn.commit()
    return created


def _now_ts() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def _norm_email(value: str | None) -> str:
    return (value or "").strip().lower()


def _norm_phone(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _norm_name(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _norm_identity(value: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", (value or "")).upper()


def _split_programs(text: str | None) -> list[str]:
    out = []
    for part in re.split(r"[,;/|]+", text or ""):
        code = part.strip().upper()
        if code and code not in out:
            out.append(code)
    return out


def _row_get(row, key, default=""):
    try:
        val = row[key]
    except Exception:
        return default
    return default if val is None else val


def confirmed_cost(cur, *, campaign_id=None, event_id=None, content_id=None) -> float:
    clauses, params = ["status = 'confirmed'"], []
    if campaign_id:
        clauses.append("campaign_id = ?")
        params.append(int(campaign_id))
    elif event_id:
        clauses.append("event_id = ?")
        params.append(int(event_id))
    elif content_id:
        clauses.append("content_id = ?")
        params.append(int(content_id))
    else:
        return 0.0
    row = cur.execute(
        f"SELECT COALESCE(SUM(amount), 0) FROM campaign_cost_allocations WHERE {' AND '.join(clauses)}",
        params,
    ).fetchone()
    return float(row[0] or 0)


def resolve_person(cur, *, full_name: str, email: str = "", phone: str = "", cccd: str = ""):
    """Ghép hồ sơ khi trùng giấy tờ, hoặc trùng họ tên kèm email/điện thoại.

    Trùng mỗi email hoặc mỗi số điện thoại chỉ là gợi ý, không gộp hai người.
    """
    from person_profile import ensure_person_tables_light

    ensure_person_tables_light(cur)
    identity = _norm_identity(cccd)
    email_n = _norm_email(email)
    phone_n = _norm_phone(phone)
    name = (full_name or "").strip() or "Chưa có tên"
    name_n = _norm_name(name)
    found = None
    if identity:
        found = cur.execute(
            "SELECT id FROM person_profiles WHERE identity_number = ? ORDER BY id LIMIT 1",
            (identity,),
        ).fetchone()
    if not found and email_n and name_n:
        found = cur.execute(
            "SELECT id FROM person_profiles WHERE lower(IFNULL(email,'')) = ? "
            "AND lower(full_name) = ? ORDER BY id LIMIT 1",
            (email_n, name_n),
        ).fetchone()
    if not found and phone_n and name_n:
        found = cur.execute(
            "SELECT id FROM person_profiles WHERE phone = ? AND lower(full_name) = ? "
            "ORDER BY id LIMIT 1",
            (phone_n, name_n),
        ).fetchone()
    hints = []
    if email_n:
        for row in cur.execute(
            "SELECT id, full_name FROM person_profiles WHERE lower(IFNULL(email,'')) = ? LIMIT 6",
            (email_n,),
        ).fetchall():
            if not found or int(row[0]) != int(found[0]):
                hints.append({"person_id": row[0], "full_name": row[1], "reason": "email"})
    if phone_n:
        for row in cur.execute(
            "SELECT id, full_name FROM person_profiles WHERE phone = ? LIMIT 6",
            (phone_n,),
        ).fetchall():
            if (not found or int(row[0]) != int(found[0])) and not any(
                h["person_id"] == row[0] for h in hints
            ):
                hints.append({"person_id": row[0], "full_name": row[1], "reason": "phone"})
    now = _now_ts()
    if found:
        pid = int(found[0])
        current = cur.execute(
            "SELECT email, phone, identity_number FROM person_profiles WHERE id = ?",
            (pid,),
        ).fetchone()
        sets, params = [], []
        if current and not (current[0] or "").strip() and email_n:
            sets.append("email = ?")
            params.append(email_n)
        if current and not (current[1] or "").strip() and phone_n:
            sets.append("phone = ?")
            params.append(phone_n)
        if current and not (current[2] or "").strip() and identity:
            sets.append("identity_number = ?")
            params.append(identity)
        if sets:
            sets.append("updated_at = ?")
            params.append(now)
            params.append(pid)
            cur.execute(
                f"UPDATE person_profiles SET {', '.join(sets)} WHERE id = ?",
                params,
            )
        return pid, False, hints
    cur.execute(
        "INSERT INTO person_profiles "
        "(full_name, email, phone, identity_number, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (name, email_n or None, phone_n or None, identity or None, now, now),
    )
    pid = int(cur.lastrowid)
    cur.execute(
        "UPDATE person_profiles SET profile_code = ? WHERE id = ?",
        (f"HS{pid:05d}", pid),
    )
    return pid, True, hints


def _fill_empty(cur, table: str, row_id: int, values: dict, keys: list[str]) -> None:
    current = cur.execute(f"SELECT * FROM {table} WHERE id = ?", (int(row_id),)).fetchone()
    if not current:
        return
    sets, params = [], []
    for key in keys:
        new = values.get(key)
        if new is None or (isinstance(new, str) and not str(new).strip()):
            continue
        try:
            old = current[key]
        except Exception:
            continue
        if old not in (None, ""):
            continue
        sets.append(f"{key} = ?")
        params.append(new)
    if sets:
        params.append(int(row_id))
        cur.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?", params)


def add_touchpoint(
    cur,
    *,
    person_id,
    lead_id,
    source: str,
    campaign_id=None,
    event_id=None,
    note: str = "",
    kind: str = "intake",
) -> None:
    cur.execute(
        "INSERT INTO source_touchpoints "
        "(person_id, lead_id, source, campaign_id, event_id, channel_code, received_at, note, touch_kind) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            person_id,
            lead_id,
            source or "other",
            campaign_id,
            event_id,
            source or "",
            _now_ts(),
            note or "",
            kind,
        ),
    )


def add_interests(cur, lead_id: int, person_id: int, programs: list[str], owner: str = "") -> None:
    for code in programs:
        cur.execute(
            "INSERT OR IGNORE INTO candidate_interests "
            "(person_id, lead_id, program_code, care_status, owner) VALUES (?,?,?,'new',?)",
            (person_id, int(lead_id), code, owner or ""),
        )


def sync_crm_from_lead(cur, lead_id: int) -> None:
    """Ghi nhu cầu vào CRM tuyển sinh theo lead, không gộp vì trùng email."""
    from crm_ops import ensure_crm_tables
    from person_profile import _add_col

    ensure_crm_tables(cur)
    _add_col(cur, "crm_source_profiles", "person_id", "INTEGER")
    lead = cur.execute("SELECT * FROM marcom_leads WHERE id = ?", (int(lead_id),)).fetchone()
    if not lead:
        return
    payload = {
        "full_name": _row_get(lead, "full_name"),
        "email": _row_get(lead, "email"),
        "phone": _row_get(lead, "phone"),
        "company": _row_get(lead, "company"),
        "occupation": _row_get(lead, "occupation"),
        "program_interest": _row_get(lead, "program_interest"),
        "source": _row_get(lead, "source") or "marcom",
        "person_id": _row_get(lead, "person_id", None),
        "notes": _row_get(lead, "notes"),
        "cccd": _row_get(lead, "cccd"),
    }
    existing = cur.execute(
        "SELECT id FROM crm_source_profiles WHERE lead_id = ?",
        (int(lead_id),),
    ).fetchone()
    if existing:
        _fill_empty(
            cur,
            "crm_source_profiles",
            int(existing[0]),
            payload,
            list(payload.keys()),
        )
        return
    cur.execute(
        "INSERT INTO crm_source_profiles ("
        "full_name, email, phone, company, occupation, program_interest, source, "
        "lead_id, person_id, care_status, notes, cccd, updated_at"
        ") VALUES (?,?,?,?,?,?,?,?,?,'potential',?,?,?)",
        (
            payload["full_name"],
            payload["email"],
            payload["phone"],
            payload["company"],
            payload["occupation"],
            payload["program_interest"],
            payload["source"],
            int(lead_id),
            payload["person_id"],
            payload["notes"],
            payload["cccd"],
            _now_ts(),
        ),
    )


def _optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def intake_interest(conn, data: dict) -> dict:
    """Tiếp nhận người quan tâm. Không bắt CCCD. Không ghi đè dữ liệu đã có."""
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    name = (data.get("full_name") or "").strip()
    if not name:
        raise ValueError("Thiếu họ tên")
    email = (data.get("email") or "").strip()
    phone = (data.get("phone") or "").strip()
    cccd = (data.get("cccd") or "").strip()
    source = (data.get("source") or "other").strip() or "other"
    programs = _split_programs(data.get("program_interest"))
    person_id, _created, hints = resolve_person(
        cur, full_name=name, email=email, phone=phone, cccd=cccd
    )
    existing = cur.execute(
        "SELECT id, status FROM marcom_leads WHERE person_id = ? "
        "AND IFNULL(status,'new') != 'dropped' ORDER BY id DESC LIMIT 1",
        (person_id,),
    ).fetchone()
    created = False
    if existing:
        lead_id = int(existing[0])
        _fill_empty(
            cur,
            "marcom_leads",
            lead_id,
            data,
            [
                "email",
                "phone",
                "occupation",
                "company",
                "program_interest",
                "source",
                "notes",
                "owner",
                "consent_marketing",
                "processing_basis",
                "campaign_id",
                "event_id",
                "cccd",
            ],
        )
        status = existing[1] or "new"
    else:
        cur.execute(
            "INSERT INTO marcom_leads ("
            "full_name, email, phone, occupation, company, program_interest, source, status, notes, "
            "cccd, person_id, owner, consent_marketing, processing_basis, campaign_id, event_id, received_at"
            ") VALUES (?,?,?,?,?,?,?,'new',?,?,?,?,?,?,?,?,?)",
            (
                name,
                email,
                phone,
                (data.get("occupation") or "").strip(),
                (data.get("company") or "").strip(),
                (data.get("program_interest") or "").strip(),
                source,
                (data.get("notes") or "").strip(),
                cccd,
                person_id,
                (data.get("owner") or "").strip(),
                (data.get("consent_marketing") or "").strip(),
                (data.get("processing_basis") or "").strip(),
                _optional_int(data.get("campaign_id")),
                _optional_int(data.get("event_id")),
                _now_ts(),
            ),
        )
        lead_id = int(cur.lastrowid)
        created = True
        status = "new"
    add_touchpoint(
        cur,
        person_id=person_id,
        lead_id=lead_id,
        source=source,
        campaign_id=_optional_int(data.get("campaign_id")),
        event_id=_optional_int(data.get("event_id")),
        note=(data.get("notes") or "").strip(),
        kind="event" if source == "event" else "intake",
    )
    add_interests(cur, lead_id, person_id, programs, (data.get("owner") or "").strip())
    try:
        sync_crm_from_lead(cur, lead_id)
    except Exception:
        pass
    conn.commit()
    return {
        "id": lead_id,
        "person_id": person_id,
        "created": created,
        "status": status,
        "duplicate_hints": hints,
    }


def _application_locked(cur, app_id: int) -> bool:
    row = cur.execute("SELECT * FROM applications WHERE id = ?", (int(app_id),)).fetchone()
    if not row:
        return False
    status = (_row_get(row, "status") or "").strip()
    if status not in ("", "submitted"):
        return True
    for key in ("degree_verified", "english_verified"):
        flag = str(_row_get(row, key, "") or "").lower()
        if flag in ("yes", "1", "ok", "verified"):
            return True
    return False


def hand_lead_to_ts(conn, lead_id: int, round_id: int | None = None) -> dict:
    """Mark lead handed to Admissions; create application with profile fields from lead.

    Liên thông 1.2: Chăm sóc lead → Nhận hồ sơ (submitted + checklist pending).
    """
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    cur.execute(
        "SELECT id, full_name, email, phone, program_interest, status, application_id, "
        "occupation, company, source, notes, cccd "
        "FROM marcom_leads WHERE id = ?",
        (lead_id,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("Lead không tồn tại")
    keys = row.keys() if hasattr(row, "keys") else []
    app_id = row["application_id"] if "application_id" in keys else None
    if app_id:
        cur.execute(
            "UPDATE marcom_leads SET status = 'handed_ts', handed_at = ? WHERE id = ?",
            (date.today().isoformat(), lead_id),
        )
        # Keep registrant follow-up in sync when linked from event
        cur.execute(
            "UPDATE marcom_event_registrants SET followup_status = 'handed_ts', "
            "updated_at = ? WHERE lead_id = ?",
            (date.today().isoformat(), lead_id),
        )
        try:
            from learner_spine import bind_application_spine

            bind_application_spine(conn, int(app_id))
        except Exception:
            pass
        conn.commit()
        return {"id": lead_id, "status": "handed_ts", "application_id": app_id}

    from admission_ops import find_application_by_cccd_program, normalize_cccd, parse_program_list
    from person_profile import _add_col, ensure_person_tables_light

    ensure_person_tables_light(cur)
    _add_col(cur, "applications", "person_id", "INTEGER")
    cccd_raw = ""
    try:
        cccd_raw = (row["cccd"] or "").strip()
    except Exception:
        cccd_raw = ""
    person_id = _row_get(row, "person_id", None)
    if not person_id:
        person_id, _created, _hints = resolve_person(
            cur,
            full_name=row["full_name"],
            email=row["email"] or "",
            phone=row["phone"] or "",
            cccd=cccd_raw,
        )
        cur.execute("UPDATE marcom_leads SET person_id = ? WHERE id = ?", (person_id, lead_id))

    programs = parse_program_list(row["program_interest"]) or _split_programs(row["program_interest"]) or ["MBA"]
    program = programs[0]

    if round_id is None:
        cur.execute(
            "SELECT id FROM admission_rounds WHERE status = 'open' "
            "AND (programs LIKE ? OR programs = '*') ORDER BY id DESC LIMIT 1",
            (f"%{program}%",),
        )
        r = cur.fetchone()
        if r:
            round_id = r[0]
        else:
            cur.execute("SELECT id FROM admission_rounds ORDER BY id DESC LIMIT 1")
            r = cur.fetchone()
            round_id = r[0] if r else None

    if not round_id:
        raise ValueError("Chưa có đợt tuyển sinh để tạo hồ sơ — tạo đợt trước.")

    from coord_ops import ensure_coord_tables

    ensure_coord_tables(cur)

    source = (row["source"] or "marcom").strip().lower() or "marcom"
    if source not in ("facebook", "zalo", "call", "event", "marcom", "other"):
        # Map common variants
        if "event" in source or "workshop" in source or "info" in source:
            source = "event"
        elif source in ("fb", "meta"):
            source = "facebook"
        else:
            source = "marcom"

    note_parts = [f"Từ Marcom lead #{lead_id}"]
    if row["notes"]:
        note_parts.append(str(row["notes"]).strip())
    note = " — ".join(p for p in note_parts if p)

    app_ids = []
    fill = {
        "full_name": row["full_name"],
        "cccd": cccd_raw,
        "email": row["email"],
        "phone": row["phone"],
        "company": row["company"] or "",
        "job_title": row["occupation"] or "",
        "lead_source": source,
        "person_id": person_id,
    }
    for prog in programs:
        existing = None
        if normalize_cccd(cccd_raw):
            existing = find_application_by_cccd_program(cur, cccd_raw, prog)
        if not existing and person_id:
            existing = cur.execute(
                "SELECT id FROM applications WHERE person_id = ? AND program_code = ?",
                (person_id, prog),
            ).fetchone()
        if existing:
            app_id_exist = int(existing[0])
            if not _application_locked(cur, app_id_exist):
                _fill_empty(
                    cur,
                    "applications",
                    app_id_exist,
                    fill,
                    ["full_name", "cccd", "email", "phone", "company", "job_title", "lead_source", "person_id"],
                )
            else:
                _fill_empty(cur, "applications", app_id_exist, {"person_id": person_id}, ["person_id"])
            app_ids.append(app_id_exist)
            continue
        cur.execute(
            "INSERT INTO applications ("
            "round_id, program_code, full_name, cccd, email, phone, status, notes, "
            "company, job_title, lead_source, checklist_status, person_id"
            ") VALUES (?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?, 'pending', ?)",
            (
                round_id,
                prog,
                row["full_name"],
                cccd_raw,
                row["email"],
                row["phone"],
                note,
                row["company"] or "",
                row["occupation"] or "",
                source,
                person_id,
            ),
        )
        app_ids.append(cur.lastrowid)

    app_id = app_ids[0] if app_ids else None

    cur.execute(
        "UPDATE marcom_leads SET status = 'handed_ts', handed_at = ?, application_id = ?, person_id = ? WHERE id = ?",
        (date.today().isoformat(), app_id, person_id, lead_id),
    )
    cur.execute(
        "UPDATE marcom_event_registrants SET followup_status = 'handed_ts', "
        "updated_at = ? WHERE lead_id = ?",
        (date.today().isoformat(), lead_id),
    )
    try:
        sync_crm_from_lead(cur, lead_id)
        if app_id:
            cur.execute(
                "UPDATE crm_source_profiles SET application_id = ? "
                "WHERE lead_id = ? AND IFNULL(application_id, 0) = 0",
                (app_id, lead_id),
            )
    except Exception:
        pass
    spines = []
    try:
        from learner_spine import bind_application_spine

        for linked_id in app_ids:
            spines.append(bind_application_spine(conn, int(linked_id)))
    except Exception:
        spines = []
    conn.commit()
    return {
        "id": lead_id,
        "status": "handed_ts",
        "application_id": app_id,
        "application_ids": app_ids,
        "round_id": round_id,
        "program_code": program,
        "program_codes": programs,
        "lead_source": source,
        "person_id": (spines[0].get("person_id") if spines else None),
        "learner_id": (spines[0].get("learner_id") if spines else None),
    }


def accept_lead(conn, lead_id: int, actor_name: str = "") -> dict:
    """Tuyển sinh xác nhận đã tiếp nhận người quan tâm."""
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    row = cur.execute(
        "SELECT id, status, application_id FROM marcom_leads WHERE id = ?",
        (int(lead_id),),
    ).fetchone()
    if not row:
        raise ValueError("Lead không tồn tại")
    if (row[1] or "") not in ("handed_ts", "accepted"):
        raise ValueError("Chưa bàn giao — Tuyển sinh chỉ xác nhận sau khi Marcom bàn giao.")
    cur.execute(
        "UPDATE marcom_leads SET status = 'accepted' WHERE id = ?",
        (int(lead_id),),
    )
    note = f"Tuyển sinh xác nhận tiếp nhận ({actor_name or 'TS'})"
    cur.execute(
        "UPDATE marcom_leads SET notes = CASE "
        "WHEN IFNULL(notes,'') = '' THEN ? "
        "WHEN notes LIKE ? THEN notes "
        "ELSE notes || ' — ' || ? END WHERE id = ?",
        (note, "%xác nhận tiếp nhận%", note, int(lead_id)),
    )
    conn.commit()
    return {"id": int(lead_id), "status": "accepted", "application_id": row[2]}


def _budget_step(current: str, decision: str, depts: set[str], is_admin: bool) -> str:
    current = (current or "planned").strip()
    if current == "done":
        current = "closed"
    decision = (decision or "").strip()
    if decision == "submit":
        if current not in ("planned", "cancelled"):
            raise ValueError("Chỉ trình duyệt khi kế hoạch đang ở trạng thái lập kế hoạch.")
        if not is_admin and "marcom" not in depts:
            raise ValueError("Chỉ Marcom trình ngân sách.")
        return "budget_submitted"
    if decision == "approve":
        if current in ("submitted", "budget_submitted"):
            if not is_admin and "ke_toan" not in depts:
                raise ValueError("Kế toán phê duyệt bước này.")
            return "approved_kt"
        if current == "approved_kt":
            if not is_admin and "ban_giam_doc" not in depts:
                raise ValueError("Ban Giám đốc phê duyệt bước này.")
            return "approved"
        raise ValueError("Không có bước phê duyệt nào đang chờ.")
    if decision == "return":
        if current in ("submitted", "budget_submitted") and (is_admin or "ke_toan" in depts):
            return "planned"
        if current == "approved_kt" and (is_admin or "ban_giam_doc" in depts):
            return "planned"
        raise ValueError("Không đúng thẩm quyền trả lại kế hoạch.")
    raise ValueError("Quyết định không hợp lệ.")


def decide_budget(conn, entity: str, row_id: int, decision: str, actor: dict, note: str = "") -> dict:
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    depts = set(actor.get("dept_codes") or [])
    is_admin = bool(actor.get("is_admin"))
    label = ""
    uid = actor.get("user_id")
    if uid:
        user = cur.execute("SELECT name, email FROM user WHERE id = ?", (int(uid),)).fetchone()
        if user:
            label = user[0] or user[1] or ""
    table = {"campaigns": "marcom_campaigns", "events": "marcom_events", "assets": "marcom_assets"}.get(entity)
    if not table:
        raise ValueError("Không có đối tượng ngân sách.")
    status_col = "status" if entity == "campaigns" else "budget_status"
    row = cur.execute(f"SELECT id, {status_col} FROM {table} WHERE id = ?", (int(row_id),)).fetchone()
    if not row:
        raise ValueError("Không tìm thấy bản ghi.")
    if entity == "assets":
        flag = cur.execute("SELECT IFNULL(outsource,'no') FROM marcom_assets WHERE id = ?", (int(row_id),)).fetchone()
        if flag and (flag[0] or "no") not in ("yes", "1", "true"):
            raise ValueError("Hạng mục nội bộ không thuê ngoài — không cần duyệt ngân sách.")
    nxt = _budget_step(row[1] or "planned", decision, depts, is_admin)
    who_col = None
    if nxt == "approved_kt":
        who_col = "approved_kt_by"
    elif nxt == "approved":
        who_col = "approved_bgd_by"
    sets = [f"{status_col} = ?"]
    params = [nxt]
    if who_col:
        sets.append(f"{who_col} = ?")
        params.append(label)
    if note and entity == "campaigns":
        sets.append("voucher_note = ?")
        params.append(note)
    params.append(int(row_id))
    cur.execute(f"UPDATE {table} SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    return {"id": int(row_id), "entity": entity, status_col: nxt}


def propose_cost(conn, data: dict, actor_name: str = "") -> dict:
    """Marcom đề xuất phân bổ. Chưa phải xác nhận đã thanh toán."""
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    amount = data.get("amount")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise ValueError("Cần số tiền phân bổ.")
    if amount <= 0:
        raise ValueError("Số tiền phải lớn hơn 0.")
    campaign_id = _optional_int(data.get("campaign_id"))
    event_id = _optional_int(data.get("event_id"))
    content_id = _optional_int(data.get("content_id"))
    if not any((campaign_id, event_id, content_id)):
        raise ValueError("Cần gắn chiến dịch, sự kiện hoặc hạng mục nội dung.")
    cur.execute(
        "INSERT INTO campaign_cost_allocations "
        "(campaign_id, event_id, content_id, payment_id, amount, note, status) "
        "VALUES (?,?,?,?,?,?,'proposed')",
        (
            campaign_id,
            event_id,
            content_id,
            _optional_int(data.get("payment_id")),
            amount,
            (data.get("note") or actor_name or "").strip(),
        ),
    )
    conn.commit()
    return {"id": int(cur.lastrowid), "status": "proposed", "amount": amount}


def confirm_costs(conn, data: dict, actor: dict) -> dict:
    """Kế toán xác nhận phân bổ. Marcom không tự xác nhận đã thanh toán."""
    depts = set(actor.get("dept_codes") or [])
    if not actor.get("is_admin") and "ke_toan" not in depts:
        raise ValueError("Chỉ Kế toán xác nhận chi phí.")
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    label = ""
    uid = actor.get("user_id")
    if uid:
        user = cur.execute("SELECT name FROM user WHERE id = ?", (int(uid),)).fetchone()
        label = (user[0] if user else "") or ""
    clauses, params = ["status = 'proposed'"], []
    campaign_id = _optional_int(data.get("campaign_id"))
    event_id = _optional_int(data.get("event_id"))
    content_id = _optional_int(data.get("content_id"))
    if campaign_id:
        clauses.append("campaign_id = ?")
        params.append(campaign_id)
    elif event_id:
        clauses.append("event_id = ?")
        params.append(event_id)
    elif content_id:
        clauses.append("content_id = ?")
        params.append(content_id)
    else:
        raise ValueError("Cần chọn bản ghi để xác nhận chi phí.")
    params_upd = [label, _now_ts(), *params]
    cur.execute(
        "UPDATE campaign_cost_allocations SET status = 'confirmed', confirmed_by = ?, confirmed_at = ? "
        f"WHERE {' AND '.join(clauses)}",
        params_upd,
    )
    count = cur.rowcount
    conn.commit()
    return {"confirmed": count}


def advance_campaign(cur, campaign_id: int, new_status: str, depts: set[str], is_admin: bool) -> None:
    """Marcom chỉ đi tiếp sau khi ngân sách đã được cả hai cấp duyệt."""
    order = ["approved", "running", "evaluating", "reconciling", "closed"]
    row = cur.execute(
        "SELECT IFNULL(status,'planned') FROM marcom_campaigns WHERE id = ?",
        (int(campaign_id),),
    ).fetchone()
    if not row:
        raise ValueError("Chiến dịch không tồn tại")
    current = "closed" if row[0] == "done" else (row[0] or "planned")
    new_status = "closed" if new_status == "done" else new_status
    if new_status == current:
        return
    if new_status not in order:
        raise ValueError("Trình và phê duyệt ngân sách bằng thao tác riêng, không sửa thẳng trạng thái.")
    if current not in order:
        raise ValueError("Chỉ triển khai sau khi Kế toán và Ban Giám đốc đã phê duyệt ngân sách.")
    if order.index(new_status) <= order.index(current):
        raise ValueError("Luồng đi tiếp: triển khai → đánh giá → đối soát chứng từ → kết thúc.")
    if not is_admin and "marcom" not in depts:
        raise ValueError("Chỉ Marcom cập nhật triển khai và đối soát.")


def guard_event_phase(cur, event_id: int, new_status: str) -> None:
    if new_status not in ("promoting", "ongoing", "followup", "done", "reported"):
        return
    row = cur.execute(
        "SELECT IFNULL(status,''), IFNULL(budget_status,'planned') FROM marcom_events WHERE id = ?",
        (int(event_id),),
    ).fetchone()
    if not row:
        raise ValueError("Sự kiện không tồn tại")
    if row[0] == new_status:
        return
    if (row[1] or "planned") != "approved" and row[0] in ("", "planned", "submitted", "cancelled"):
        raise ValueError("Sự kiện chỉ triển khai sau khi Kế toán và Ban Giám đốc phê duyệt ngân sách.")


def guard_content_status(cur, asset_id: int, new_status: str) -> None:
    if new_status not in ("producing", "accepted", "payment_file", "archived", "published"):
        return
    row = cur.execute(
        "SELECT IFNULL(content_status,'requested'), IFNULL(outsource,'no'), IFNULL(budget_status,'planned') "
        "FROM marcom_assets WHERE id = ?",
        (int(asset_id),),
    ).fetchone()
    if not row:
        raise ValueError("Hạng mục không tồn tại")
    if row[0] == new_status:
        return
    outsource = (row[1] or "no") in ("yes", "1", "true")
    if outsource and (row[2] or "planned") != "approved":
        raise ValueError("Hạng mục thuê ngoài chỉ sản xuất sau khi ngân sách được phê duyệt.")


def add_campaign_activity(conn, campaign_id: int, data: dict) -> dict:
    """Hoạt động và hạn dùng nhiệm vụ chung, không tạo bộ công việc riêng."""
    from asst_ops import ensure_asst_tables

    cur = conn.cursor()
    ensure_marcom_tables(cur)
    ensure_asst_tables(cur)
    try:
        cur.execute("ALTER TABLE asst_tasks ADD COLUMN source_ref TEXT")
    except Exception:
        pass
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("Cần tên hoạt động")
    hit = cur.execute("SELECT id FROM marcom_campaigns WHERE id = ?", (int(campaign_id),)).fetchone()
    if not hit:
        raise ValueError("Chiến dịch không tồn tại")
    ref = f"campaign:{int(campaign_id)}"
    cur.execute(
        "INSERT INTO asst_tasks (title, assignee, department, due_date, status, notes, source_ref) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            title,
            (data.get("assignee") or "").strip(),
            "marcom",
            (data.get("due_date") or "").strip(),
            "open",
            (data.get("notes") or "").strip(),
            ref,
        ),
    )
    conn.commit()
    return {"id": int(cur.lastrowid), "source_ref": ref}


def add_publication(conn, content_id: int, data: dict) -> dict:
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    hit = cur.execute("SELECT id FROM marcom_assets WHERE id = ?", (int(content_id),)).fetchone()
    if not hit:
        raise ValueError("Hạng mục nội dung không tồn tại")
    cur.execute(
        "INSERT INTO content_publications (content_id, channel_code, scheduled_at, published_url, status) "
        "VALUES (?,?,?,?,?)",
        (
            int(content_id),
            (data.get("channel_code") or "").strip(),
            (data.get("scheduled_at") or "").strip(),
            (data.get("published_url") or "").strip(),
            (data.get("status") or "scheduled").strip() or "scheduled",
        ),
    )
    conn.commit()
    return {"id": int(cur.lastrowid), "content_id": int(content_id)}


def check_in_registrant(conn, registrant_id: int) -> dict:
    """Check-in sự kiện. Không ghi vào điểm danh lớp học."""
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    row = cur.execute(
        "SELECT id FROM marcom_event_registrants WHERE id = ?",
        (int(registrant_id),),
    ).fetchone()
    if not row:
        raise ValueError("Người đăng ký không tồn tại")
    now = _now_ts()
    cur.execute(
        "UPDATE marcom_event_registrants SET attendance_status = 'attended', checked_in_at = ?, "
        "updated_at = ? WHERE id = ?",
        (now, date.today().isoformat(), int(registrant_id)),
    )
    conn.commit()
    return {"id": int(registrant_id), "attendance_status": "attended", "checked_in_at": now}


def list_marcom_leads(conn) -> list[dict]:
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    from person_profile import ensure_person_tables_light

    ensure_person_tables_light(cur)
    rows = cur.execute(
        "SELECT l.id, l.full_name, l.email, l.phone, l.occupation, l.company, l.program_interest, "
        "l.source, l.status, l.notes, l.handed_at, l.application_id, l.created_at, "
        "l.person_id, IFNULL(l.owner,''), IFNULL(l.consent_marketing,''), "
        "IFNULL(a.status,''), IFNULL(p.profile_code,'') "
        "FROM marcom_leads l "
        "LEFT JOIN applications a ON a.id = l.application_id "
        "LEFT JOIN person_profiles p ON p.id = l.person_id "
        "ORDER BY l.id DESC"
    ).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r[0],
            "full_name": r[1],
            "email": r[2],
            "phone": r[3],
            "occupation": r[4],
            "company": r[5],
            "program_interest": r[6],
            "source": r[7],
            "status": r[8],
            "notes": r[9],
            "handed_at": r[10],
            "application_id": r[11],
            "created_at": r[12],
            "person_id": r[13],
            "owner": r[14],
            "consent_marketing": r[15],
            "application_status": r[16],
            "profile_code": r[17],
        })
    return out


def list_marcom_campaigns(conn) -> list[dict]:
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    rows = cur.execute(
        "SELECT id, title, period_start, period_end, channel, program_codes, "
        "budget_planned, kpi_notes, status, report_summary, "
        "IFNULL(campaign_code,''), IFNULL(objective,''), IFNULL(owner,''), "
        "IFNULL(budget_approved,0), IFNULL(kpi_plan,''), IFNULL(kpi_result,''), "
        "IFNULL(round_refs,''), IFNULL(voucher_note,''), IFNULL(acceptance_note,'') "
        "FROM marcom_campaigns ORDER BY id DESC"
    ).fetchall()
    out = []
    for r in rows:
        cid = r[0]
        tasks = 0
        try:
            hit = cur.execute(
                "SELECT COUNT(*) FROM asst_tasks WHERE source_ref = ?",
                (f"campaign:{cid}",),
            ).fetchone()
            tasks = int(hit[0] or 0) if hit else 0
        except Exception:
            tasks = 0
        out.append({
            "id": cid,
            "title": r[1],
            "period_start": r[2],
            "period_end": r[3],
            "channel": r[4],
            "program_codes": r[5],
            "budget_planned": r[6],
            "budget_actual": confirmed_cost(cur, campaign_id=cid),
            "kpi_notes": r[7],
            "status": "closed" if r[8] == "done" else r[8],
            "report_summary": r[9],
            "campaign_code": r[10],
            "objective": r[11],
            "owner": r[12],
            "budget_approved": r[13],
            "kpi_plan": r[14],
            "kpi_result": r[15],
            "round_refs": r[16],
            "voucher_note": r[17],
            "acceptance_note": r[18],
            "activity_count": tasks,
        })
    return out


def list_marcom_assets(conn) -> list[dict]:
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    rows = cur.execute(
        "SELECT id, title, asset_type, file_path, tags, program_codes, used_for, notes, "
        "IFNULL(topic,''), IFNULL(assignee,''), IFNULL(approver,''), IFNULL(due_date,''), "
        "IFNULL(content_status,'requested'), IFNULL(outsource,'no'), IFNULL(budget_planned,0), "
        "IFNULL(budget_status,'planned'), IFNULL(channel_code,''), IFNULL(publish_at,''), "
        "IFNULL(published_url,''), IFNULL(usage_rights,''), IFNULL(usage_until,''), "
        "IFNULL(acceptance_note,''), IFNULL(payment_note,'') "
        "FROM marcom_assets ORDER BY id DESC"
    ).fetchall()
    out = []
    for r in rows:
        pubs = cur.execute(
            "SELECT COUNT(*) FROM content_publications WHERE content_id = ?",
            (r[0],),
        ).fetchone()
        out.append({
            "id": r[0],
            "title": r[1],
            "asset_type": r[2],
            "file_path": r[3],
            "tags": r[4],
            "program_codes": r[5],
            "used_for": r[6],
            "notes": r[7],
            "topic": r[8],
            "assignee": r[9],
            "approver": r[10],
            "due_date": r[11],
            "content_status": r[12] or "requested",
            "outsource": r[13] or "no",
            "budget_planned": r[14],
            "budget_status": r[15] or "planned",
            "channel_code": r[16],
            "publish_at": r[17],
            "published_url": r[18],
            "usage_rights": r[19],
            "usage_until": r[20],
            "acceptance_note": r[21],
            "payment_note": r[22],
            "has_file": bool(r[3]),
            "publication_count": int(pubs[0] or 0) if pubs else 0,
            "budget_actual": confirmed_cost(cur, content_id=r[0]),
        })
    return out


def _period_start(as_of: date, period: str) -> date:
    if period == "month":
        return as_of.replace(day=1)
    if period == "quarter":
        month = ((as_of.month - 1) // 3) * 3 + 1
        return date(as_of.year, month, 1)
    if period == "half":
        return date(as_of.year, 1 if as_of.month <= 6 else 7, 1)
    return date(as_of.year, 1, 1)


def build_marcom_report(conn, *, period: str = "month", as_of: str = "", attribution: str = "first") -> dict:
    """Báo cáo tổng hợp. Không nhập lại số liệu. Không có chỉ số tiếp cận kênh."""
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    try:
        day = date.fromisoformat((as_of or "")[:10])
    except ValueError:
        day = date.today()
    period = period if period in ("month", "quarter", "half", "year") else "month"
    attribution = "last" if attribution == "last" else "first"
    start = _period_start(day, period)
    start_s = start.isoformat()
    end_s = day.isoformat() + " 23:59:59"
    order = "ASC" if attribution == "first" else "DESC"
    people = cur.execute(
        "SELECT person_id, lead_id, source, campaign_id, event_id, received_at "
        "FROM source_touchpoints "
        "WHERE IFNULL(touch_kind,'intake') != 'handoff' "
        "AND IFNULL(received_at,'') >= ? AND IFNULL(received_at,'') <= ? "
        f"ORDER BY received_at {order}, id {order}",
        (start_s, end_s),
    ).fetchall()
    seen = set()
    by_campaign = {}
    for person_id, lead_id, source, campaign_id, event_id, _received in people:
        key = f"p{person_id}" if person_id else f"l{lead_id}"
        if key in seen:
            continue
        seen.add(key)
        bucket = str(campaign_id or 0)
        by_campaign.setdefault(bucket, {"people": 0, "source": source or ""})
        by_campaign[bucket]["people"] += 1
    unique_people = len(seen)
    handed = cur.execute(
        "SELECT COUNT(*) FROM marcom_leads WHERE status IN ('handed_ts','accepted') "
        "AND IFNULL(handed_at, created_at) >= ? AND IFNULL(handed_at, created_at) <= ?",
        (start_s, end_s),
    ).fetchone()[0]
    funnel = {"submitted": 0, "exam": 0, "admitted": 0, "learner": 0}
    apps = cur.execute(
        "SELECT DISTINCT a.id, IFNULL(a.status,''), IFNULL(a.examinee_confirmed_at,'') "
        "FROM marcom_leads l JOIN applications a ON a.id = l.application_id "
        "WHERE IFNULL(l.handed_at, l.created_at) >= ? AND IFNULL(l.handed_at, l.created_at) <= ?",
        (start_s, end_s),
    ).fetchall()
    seen_apps = set()
    for app_id, status, exam_at in apps:
        if app_id in seen_apps:
            continue
        seen_apps.add(app_id)
        funnel["submitted"] += 1
        if exam_at or status in ("interview", "passed", "failed", "paid", "official"):
            funnel["exam"] += 1
        if status in ("passed", "paid", "official"):
            funnel["admitted"] += 1
        if status == "official":
            funnel["learner"] += 1
    cost = cur.execute(
        "SELECT COALESCE(SUM(amount),0) FROM campaign_cost_allocations "
        "WHERE status = 'confirmed' AND IFNULL(confirmed_at, created_at) >= ? "
        "AND IFNULL(confirmed_at, created_at) <= ?",
        (start_s, end_s),
    ).fetchone()[0]
    cost = float(cost or 0)
    events = cur.execute(
        "SELECT COUNT(*), COALESCE(SUM(budget),0) FROM marcom_events "
        "WHERE IFNULL(event_date,'') >= ? AND IFNULL(event_date,'') <= ?",
        (start.isoformat(), day.isoformat()),
    ).fetchone()
    regs = cur.execute(
        "SELECT COUNT(*), "
        "SUM(CASE WHEN attendance_status = 'attended' THEN 1 ELSE 0 END) "
        "FROM marcom_event_registrants r JOIN marcom_events e ON e.id = r.event_id "
        "WHERE IFNULL(e.event_date,'') >= ? AND IFNULL(e.event_date,'') <= ?",
        (start.isoformat(), day.isoformat()),
    ).fetchone()
    contents = cur.execute(
        "SELECT asset_type, content_status, COUNT(*) FROM marcom_assets "
        "GROUP BY asset_type, content_status"
    ).fetchall()
    content_rows = [
        {"metric": f"{a or '—'} · {b or 'requested'}", "value": c, "note": ""}
        for a, b, c in contents
    ]
    def money(n):
        return f"{float(n):,.0f}".replace(",", ".")

    sections = [
        {
            "title": "Marketing",
            "rows": [
                {"metric": "Người quan tâm duy nhất", "value": unique_people, "note": f"Quy kết nguồn {('đầu' if attribution == 'first' else 'cuối')}. Mỗi người tính một lần."},
                {"metric": "Đã bàn giao tuyển sinh", "value": handed, "note": ""},
                {"metric": "Hồ sơ đã tạo", "value": funnel["submitted"], "note": ""},
                {"metric": "Đăng ký / vào thi", "value": funnel["exam"], "note": ""},
                {"metric": "Trúng tuyển", "value": funnel["admitted"], "note": ""},
                {"metric": "Thành học viên", "value": funnel["learner"], "note": "Trạng thái official."},
                {"metric": "Chi phí đã xác nhận", "value": money(cost), "note": "Chỉ khoản Kế toán đã xác nhận."},
                {"metric": "Chi phí / người quan tâm", "value": money(cost / unique_people) if unique_people else "—", "note": ""},
                {"metric": "Chi phí / học viên", "value": money(cost / funnel["learner"]) if funnel["learner"] else "—", "note": ""},
            ],
        },
        {
            "title": "Sự kiện",
            "rows": [
                {"metric": "Số sự kiện trong kỳ", "value": events[0] or 0, "note": ""},
                {"metric": "Ngân sách dự kiến", "value": money(events[1] or 0), "note": "Không phải chi phí đã thanh toán."},
                {"metric": "Đăng ký", "value": regs[0] or 0, "note": ""},
                {"metric": "Tham dự", "value": regs[1] or 0, "note": ""},
            ],
        },
        {
            "title": "Nội dung và thiết kế",
            "rows": content_rows or [{"metric": "Hạng mục", "value": 0, "note": "Chưa có tư liệu."}],
        },
    ]
    return {
        "period": period,
        "period_start": start.isoformat(),
        "as_of": day.isoformat(),
        "cutoff_at": _now_ts(),
        "attribution": attribution,
        "audience": "Ban Giám đốc CFVG",
        "note": "Không hiển thị tiếp cận hoặc tương tác kênh vì chưa có nguồn đo độc lập.",
        "sections": sections,
    }


def sync_event_to_alumni(conn, event_id: int) -> dict:
    """Create/link an alumni_events row for a marcom alumni-type event."""
    cur = conn.cursor()
    ensure_marcom_tables(cur)
    from ops_data import ensure_ops_tables

    ensure_ops_tables(cur)
    cur.execute(
        "SELECT id, title, event_date, location, program_codes, content, status, alumni_event_id "
        "FROM marcom_events WHERE id = ?",
        (event_id,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("Sự kiện không tồn tại")
    if row["alumni_event_id"]:
        return {"id": event_id, "alumni_event_id": row["alumni_event_id"], "linked": True}

    cur.execute(
        "INSERT INTO alumni_events (title, event_date, location, program_filter, status, description) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            row["title"],
            row["event_date"],
            row["location"],
            row["program_codes"] or "*",
            "planned",
            row["content"] or "",
        ),
    )
    aid = cur.lastrowid
    cur.execute(
        "UPDATE marcom_events SET alumni_event_id = ?, event_type = 'alumni' WHERE id = ?",
        (aid, event_id),
    )
    conn.commit()
    return {"id": event_id, "alumni_event_id": aid, "linked": False}
