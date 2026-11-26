"""
Phân hệ Trợ lý Ban Giám đốc — Điều phối học viên & giảng viên quốc tế
(Theo file: Trịnh Huyền Diệu Linh_Trợ lý Ban Giám đốc)
"""
from __future__ import annotations

from datetime import date, timedelta


def ensure_asst_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_meetings ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "meeting_date TEXT, "
        "location TEXT, "
        "attendees TEXT, "
        "minutes_summary TEXT, "
        "status TEXT DEFAULT 'planned')"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_tasks ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "meeting_id INTEGER, "
        "title TEXT NOT NULL, "
        "assignee TEXT, "
        "department TEXT, "
        "due_date TEXT, "
        "status TEXT DEFAULT 'open', "  # open | doing | done | overdue
        "notes TEXT, "
        "FOREIGN KEY (meeting_id) REFERENCES asst_meetings(id))"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_calendar ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "cal_type TEXT DEFAULT 'general', "  # bgd | training | meeting | event | faculty | leave
        "starts_at TEXT, "
        "ends_at TEXT, "
        "location TEXT, "
        "owner TEXT, "
        "attendees TEXT, "
        "status TEXT DEFAULT 'confirmed', "
        "notes TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_intl_faculty ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "full_name TEXT NOT NULL, "
        "gender TEXT, "
        "nationality TEXT, "
        "organization TEXT, "
        "title TEXT, "
        "email TEXT, "
        "phone TEXT, "
        "passport_no TEXT, "
        "passport_type TEXT, "  # ordinary | diplomatic | service
        "passport_expiry TEXT, "
        "visa_needed INTEGER DEFAULT 1, "
        "visa_type TEXT, "
        "visa_no TEXT, "
        "visa_expiry TEXT, "
        "visa_status TEXT DEFAULT 'pending', "
        "arrival_date TEXT, "
        "arrival_flight TEXT, "
        "departure_date TEXT, "
        "departure_flight TEXT, "
        "hotel_name TEXT, "
        "hotel_checkin TEXT, "
        "hotel_checkout TEXT, "
        "airport_pickup TEXT, "
        "program_code TEXT, "
        "course_name TEXT, "
        "teach_dates TEXT, "
        "status TEXT DEFAULT 'preparing', "
        "notes TEXT)"
    )
    fac_cols = {r[1] for r in cur.execute("PRAGMA table_info(asst_intl_faculty)").fetchall()}
    if "partner_university" not in fac_cols:
        try:
            cur.execute("ALTER TABLE asst_intl_faculty ADD COLUMN partner_university TEXT")
        except Exception:
            pass
    if "partner_code" not in fac_cols:
        try:
            cur.execute("ALTER TABLE asst_intl_faculty ADD COLUMN partner_code TEXT")
        except Exception:
            pass
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_intl_students ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "full_name TEXT NOT NULL, "
        "nationality TEXT, "
        "email TEXT, "
        "phone TEXT, "
        "program_code TEXT, "
        "cohort TEXT, "
        "student_type TEXT, "  # exchange | intl_degree
        "home_university TEXT, "
        "passport_no TEXT, "
        "passport_expiry TEXT, "
        "visa_type TEXT, "
        "visa_status TEXT DEFAULT 'pending', "
        "arrival_date TEXT, "
        "departure_date TEXT, "
        "flight_info TEXT, "
        "onboarding_status TEXT DEFAULT 'pending', "
        "direction TEXT, "  # incoming | outgoing
        "semester TEXT, "
        "exchange_kind TEXT, "  # double_degree | one_semester
        "partner_university TEXT, "
        "handoff_visa_by TEXT, "
        "handoff_iae_by TEXT, "
        "handoff_courses_by TEXT, "
        "accounting_note TEXT, "
        "notes TEXT)"
    )
    try:
        cur.execute("ALTER TABLE asst_intl_students ADD COLUMN cccd TEXT")
    except Exception:
        pass
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_director_fr ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "full_name TEXT NOT NULL, "
        "relation TEXT, "  # self | spouse | child
        "nationality TEXT, "
        "passport_no TEXT, "
        "passport_expiry TEXT, "
        "visa_info TEXT, "
        "work_permit TEXT, "
        "residence_reg TEXT, "
        "insurance TEXT, "
        "doc_expiry TEXT, "
        "status TEXT DEFAULT 'valid', "
        "notes TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_documents ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "doc_direction TEXT NOT NULL, "  # in | out | seal
        "doc_no TEXT, "
        "doc_date TEXT, "
        "sender_or_receiver TEXT, "
        "subject TEXT, "
        "doc_type TEXT, "
        "urgency TEXT, "
        "handler TEXT, "
        "due_date TEXT, "
        "status TEXT DEFAULT 'received', "
        "seal_used INTEGER DEFAULT 0, "
        "notes TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_procurement ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "category TEXT NOT NULL, "  # stationery | water | taxi | other
        "item_name TEXT NOT NULL, "
        "quantity REAL, "
        "unit_price REAL, "
        "amount REAL, "
        "requester TEXT, "
        "supplier TEXT, "
        "request_date TEXT, "
        "status TEXT DEFAULT 'requested', "  # requested | approved | purchased | invoiced | paid
        "invoice_no TEXT, "
        "notes TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_payments ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "cost_type TEXT NOT NULL, "  # flight | taxi | stationery | water | other
        "beneficiary TEXT, "
        "program_code TEXT, "
        "supplier TEXT, "
        "amount REAL, "
        "invoice_no TEXT, "
        "invoice_date TEXT, "
        "payment_status TEXT DEFAULT 'unpaid', "
        "payment_date TEXT, "
        "month_key TEXT, "
        "notes TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_weekly_reports ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "week_label TEXT NOT NULL, "
        "week_start TEXT, "
        "done_summary TEXT, "
        "ongoing_summary TEXT, "
        "next_week_plan TEXT, "
        "issues TEXT, "
        "neu_coordination TEXT, "
        "status TEXT DEFAULT 'draft', "  # draft | review | approved | sent
        "sent_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS asst_leave ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "employee_name TEXT NOT NULL, "
        "department TEXT, "
        "leave_type TEXT, "  # annual | unpaid | personal | business
        "start_date TEXT, "
        "end_date TEXT, "
        "days REAL, "
        "reason TEXT, "
        "substitute TEXT, "
        "handover TEXT, "
        "approver TEXT, "
        "status TEXT DEFAULT 'pending')"
    )


def seed_asst_draft_data(conn) -> dict:
    cur = conn.cursor()
    ensure_asst_tables(cur)
    created = {"meetings": 0, "faculty": 0}

    cur.execute("SELECT COUNT(*) FROM asst_meetings")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO asst_meetings (title, meeting_date, location, attendees, minutes_summary, status) "
            "VALUES (?, ?, ?, ?, ?, 'done')",
            (
                "Họp Ban Giám đốc X tuần",
                date.today().isoformat(),
                "Phòng họp X HN",
                "Đồng GĐ VN, Đồng GĐ Pháp, Trợ lý BGD",
                "Thống nhất lịch đón GV quốc tế MSCM; giao nhiệm vụ báo cáo tuần NEU.",
            ),
        )
        mid = cur.lastrowid
        created["meetings"] += 1
        tasks = [
            ("Chuẩn bị hồ sơ visa GV MSCM", "Trịnh Huyền Diệu Linh", "tro_ly_bgd", 7, "doing"),
            ("Tổng hợp báo cáo tuần gửi NEU", "Trịnh Huyền Diệu Linh", "tro_ly_bgd", 3, "open"),
            ("Xác nhận lịch đón sân bay", "Nguyễn Huy Tiến", "logistic", 5, "open"),
        ]
        for title, assignee, dept, days, st in tasks:
            cur.execute(
                "INSERT INTO asst_tasks (meeting_id, title, assignee, department, due_date, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (mid, title, assignee, dept, (date.today() + timedelta(days=days)).isoformat(), st),
            )

    cur.execute("SELECT COUNT(*) FROM asst_calendar")
    if cur.fetchone()[0] == 0:
        rows = [
            ("Họp BGD X", "bgd", "09:00", "10:30", "P.Họp", "Ban Giám đốc"),
            ("Đón GV quốc tế MSCM", "faculty", "14:00", "16:00", "Nội Bài", "Trợ lý BGD"),
            ("Sự kiện Alumni networking", "event", "18:00", "20:00", "X HN", "Alumni"),
        ]
        for title, ctype, st, et, loc, owner in rows:
            d = date.today() + timedelta(days=2)
            cur.execute(
                "INSERT INTO asst_calendar "
                "(title, cal_type, starts_at, ends_at, location, owner, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'confirmed')",
                (title, ctype, f"{d} {st}", f"{d} {et}", loc, owner),
            )

    cur.execute("SELECT COUNT(*) FROM asst_intl_faculty")
    if cur.fetchone()[0] == 0:
        faculty = [
            (
                "Prof. Jean Dupont", "M", "France", "ESCP", "Professor",
                "j.dupont@escp.eu", "P1234567", "ordinary",
                (date.today() + timedelta(days=400)).isoformat(),
                1, "e-visa", "pending",
                (date.today() + timedelta(days=20)).isoformat(), "AF238",
                (date.today() + timedelta(days=30)).isoformat(), "AF239",
                "Melia Hanoi", "MSCM", "Supply Chain Strategy", "preparing",
            ),
            (
                "Dr. Marie Curie", "F", "Belgium", "X Partner", "Associate Prof.",
                "m.curie@partner.eu", "B7654321", "ordinary",
                (date.today() + timedelta(days=200)).isoformat(),
                0, "visa-exempt", "not_required",
                (date.today() + timedelta(days=40)).isoformat(), "SN501",
                (date.today() + timedelta(days=48)).isoformat(), "SN502",
                "Sofitel Legend", "MMS", "Marketing Strategy", "confirmed",
            ),
        ]
        for f in faculty:
            cur.execute(
                "INSERT INTO asst_intl_faculty "
                "(full_name, gender, nationality, organization, title, email, passport_no, passport_type, "
                "passport_expiry, visa_needed, visa_type, visa_status, arrival_date, arrival_flight, "
                "departure_date, departure_flight, hotel_name, program_code, course_name, status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                f,
            )
            created["faculty"] += 1

    cur.execute("SELECT COUNT(*) FROM asst_intl_students")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO asst_intl_students "
            "(full_name, nationality, email, program_code, cohort, student_type, home_university, "
            "passport_no, visa_status, arrival_date, onboarding_status, "
            "direction, semester, exchange_kind, partner_university, "
            "handoff_visa_by, handoff_iae_by, handoff_courses_by, accounting_note) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "Sophie Martin", "France", "sophie.m@exchange.fr", "MBA", "2026",
                "exchange", "ESCP Europe", "X998877", "pending",
                (date.today() + timedelta(days=45)).isoformat(), "pending",
                "incoming", "S1", "one_semester", "ESCP Europe",
                "Trợ lý BGD", "Hạnh (KT)", "Đoan (ĐP MBA)", "",
            ),
        )

    cur.execute("SELECT COUNT(*) FROM asst_director_fr")
    if cur.fetchone()[0] == 0:
        for name, rel, exp_days in (
            ("Directeur Français X", "self", 180),
            ("Épouse du Directeur", "spouse", 180),
        ):
            cur.execute(
                "INSERT INTO asst_director_fr "
                "(full_name, relation, nationality, passport_no, passport_expiry, "
                "visa_info, work_permit, residence_reg, doc_expiry, status) "
                "VALUES (?,?,?,?,?,?,?,?,?, 'valid')",
                (
                    name, rel, "France", "FR-DEMO",
                    (date.today() + timedelta(days=exp_days)).isoformat(),
                    "Visa công tác", "Work permit đang theo dõi",
                    "Đăng ký cư trú HN",
                    (date.today() + timedelta(days=exp_days)).isoformat(),
                ),
            )

    cur.execute("SELECT COUNT(*) FROM asst_documents")
    if cur.fetchone()[0] == 0:
        docs = [
            ("in", "CVĐến-12", "NEU / Phòng HTQT", "Công văn phối hợp đón GV quốc tế", "received"),
            ("out", "X-HN-08", "Ban Giám đốc X", "Thư mời giảng viên quốc tế MSCM", "issued"),
            ("seal", "X-HN-08", "Trợ lý BGD", "Đóng dấu thư mời GV", "sealed"),
        ]
        for direction, no, party, subject, st in docs:
            cur.execute(
                "INSERT INTO asst_documents "
                "(doc_direction, doc_no, doc_date, sender_or_receiver, subject, status, handler) "
                "VALUES (?,?,?,?,?,?,?)",
                (direction, no, date.today().isoformat(), party, subject, st, "Trịnh Huyền Diệu Linh"),
            )

    cur.execute("SELECT COUNT(*) FROM asst_procurement")
    if cur.fetchone()[0] == 0:
        items = [
            ("stationery", "Giấy A4 Double A", 10, 95000, "Trợ lý BGD", "Văn phòng phẩm ABC", "purchased"),
            ("water", "Nước Lavie bình 19L", 20, 35000, "Hành chính", "Lavie", "invoiced"),
            ("taxi", "Xe đón sân bay GV Jean Dupont", 1, 450000, "Logistics", "Taxi Nội Bài", "approved"),
        ]
        for cat, name, qty, price, req, supplier, st in items:
            cur.execute(
                "INSERT INTO asst_procurement "
                "(category, item_name, quantity, unit_price, amount, requester, supplier, request_date, status) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (cat, name, qty, price, qty * price, req, supplier, date.today().isoformat(), st),
            )

    cur.execute("SELECT COUNT(*) FROM asst_payments")
    if cur.fetchone()[0] == 0:
        month = date.today().strftime("%Y-%m")
        pays = [
            ("flight", "Jean Dupont", "MSCM", "Vietnam Airlines", 18500000, "unpaid"),
            ("taxi", "Jean Dupont", "MSCM", "Taxi Nội Bài", 450000, "unpaid"),
            ("water", "X HN", "", "Lavie", 700000, "paid"),
        ]
        for ctype, bene, prog, supplier, amount, st in pays:
            cur.execute(
                "INSERT INTO asst_payments "
                "(cost_type, beneficiary, program_code, supplier, amount, payment_status, month_key, invoice_date) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (ctype, bene, prog, supplier, amount, st, month, date.today().isoformat()),
            )

    cur.execute("SELECT COUNT(*) FROM asst_weekly_reports")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO asst_weekly_reports "
            "(week_label, week_start, done_summary, ongoing_summary, next_week_plan, issues, neu_coordination, status) "
            "VALUES (?,?,?,?,?,?,?, 'draft')",
            (
                f"Tuần {date.today().isocalendar()[1]}/{date.today().year}",
                date.today().isoformat(),
                "Hoàn thành lịch đón GV; cập nhật sổ công văn đến.",
                "Đang theo dõi visa e-visa Prof. Dupont; tổng hợp chi phí taxi.",
                "Gửi báo cáo tuần NEU; xác nhận khách sạn GV MMS.",
                "Chờ scan hộ chiếu bổ sung từ 1 GV.",
                "Phối hợp Phòng HTQT NEU về danh sách HV trao đổi.",
            ),
        )

    cur.execute("SELECT COUNT(*) FROM asst_leave")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO asst_leave "
            "(employee_name, department, leave_type, start_date, end_date, days, reason, substitute, status, approver) "
            "VALUES (?,?,?,?,?,?,?,?, 'pending', ?)",
            (
                "Lê Hồng Nhung", "tuyen_sinh", "annual",
                (date.today() + timedelta(days=10)).isoformat(),
                (date.today() + timedelta(days=12)).isoformat(),
                3, "Việc gia đình", "Nguyễn Thị Quỳnh Giao", "Trợ lý BGD",
            ),
        )

    conn.commit()
    return created


def _parse_dt(value: str):
    from datetime import datetime as _dt

    raw = (value or "").strip()
    if not raw:
        return None
    raw = raw.replace("Z", "").replace("/", "-")
    try:
        return _dt.fromisoformat(raw)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return _dt.strptime(raw[:19] if fmt.count(":") else raw[:10], fmt)
        except Exception:
            continue
    return None


def is_expiring_soon(value: str, *, days: int = 30) -> bool:
    dt = _parse_dt(value)
    if not dt:
        return False
    today = date.today()
    delta = (dt.date() - today).days
    return 0 <= delta <= int(days)


def annotate_calendar_conflicts(items: list[dict]) -> list[dict]:
    parsed = []
    for it in items:
        start = _parse_dt(str(it.get("starts_at") or ""))
        end = _parse_dt(str(it.get("ends_at") or "")) or start
        parsed.append((it, start, end))
    for it, start, end in parsed:
        titles = []
        if start and end:
            for other, os, oe in parsed:
                if other is it or not os or not oe:
                    continue
                if start < oe and os < end:
                    titles.append(str(other.get("title") or f"#{other.get('id')}"))
        it["conflict"] = "; ".join(titles[:4]) if titles else ""
        it["has_conflict"] = bool(titles)
    return items


def calendar_conflict_titles(conn, row: dict) -> list[str]:
    cur = conn.cursor()
    ensure_asst_tables(cur)
    start = _parse_dt(str(row.get("starts_at") or ""))
    end = _parse_dt(str(row.get("ends_at") or "")) or start
    if not start:
        return []
    rid = int(row.get("id") or 0)
    out = []
    for oid, title, st, et in cur.execute(
        "SELECT id, title, starts_at, ends_at FROM asst_calendar WHERE IFNULL(status,'') != 'cancelled'"
    ).fetchall():
        if rid and int(oid) == rid:
            continue
        os = _parse_dt(str(st or ""))
        oe = _parse_dt(str(et or "")) or os
        if os and oe and start < oe and os < end:
            out.append(str(title or f"#{oid}"))
    return out


def notify_calendar_changes(conn, *, actor: str = "", recipient: str = "") -> dict:
    from ops_crud import queue_email

    cur = conn.cursor()
    ensure_asst_tables(cur)
    rows = cur.execute(
        "SELECT id, title, starts_at, ends_at, location, owner, attendees, status "
        "FROM asst_calendar ORDER BY starts_at"
    ).fetchall()
    items = [
        {
            "id": r[0],
            "title": r[1],
            "starts_at": r[2],
            "ends_at": r[3],
            "location": r[4],
            "owner": r[5],
            "attendees": r[6],
            "status": r[7],
        }
        for r in rows
    ]
    annotate_calendar_conflicts(items)
    upcoming = []
    now = date.today()
    for it in items:
        st = _parse_dt(str(it.get("starts_at") or ""))
        if not st:
            continue
        delta = (st.date() - now).days
        if 0 <= delta <= 7:
            upcoming.append(it)
    conflicts = [it for it in items if it.get("has_conflict")]
    lines = ["Lịch tuần X — thông báo thay đổi / sắp diễn ra:", ""]
    for it in upcoming:
        flag = " [TRÙNG]" if it.get("has_conflict") else ""
        lines.append(
            f"- {it.get('starts_at') or ''}–{it.get('ends_at') or ''} {it.get('title') or ''}"
            f" ({it.get('location') or '—'}){flag}"
        )
    if conflicts:
        lines.append("")
        lines.append("Cảnh báo trùng lịch:")
        for it in conflicts[:20]:
            lines.append(f"- {it.get('title')}: {it.get('conflict')}")
    body = "\n".join(lines) if (upcoming or conflicts) else "Không có lịch 7 ngày tới."
    to = (recipient or "").strip()
    queued = 0
    if to and "@" in to:
        queue_email(
            conn,
            kind="calendar_change",
            recipient=to,
            subject="[X] Thông báo thay đổi lịch tuần",
            body=body,
        )
        queued += 1
    seen = set()
    for it in upcoming:
        for raw in (str(it.get("owner") or ""), str(it.get("attendees") or "")):
            for part in raw.replace(";", ",").split(","):
                addr = part.strip()
                if "@" in addr and addr.lower() not in seen:
                    seen.add(addr.lower())
                    queue_email(
                        conn,
                        kind="calendar_change",
                        recipient=addr,
                        subject=f"[X] Lịch: {it.get('title') or ''}",
                        body=body,
                    )
                    queued += 1
    if queued == 0:
        queue_email(
            conn,
            kind="calendar_change",
            recipient=actor or "ops@cfvg.local",
            subject="[X] Thông báo thay đổi lịch tuần",
            body=body,
        )
        queued = 1
    return {"queued": queued, "upcoming": len(upcoming), "conflicts": len(conflicts)}
