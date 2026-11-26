"""
MMS programme catalog for LinhTK / LinhLT.

Source (mau file MMS — Trịnh Kiều Linh, Lê Thùy Linh):
- PV MMS Hanoi 20: 15 modules, ECTS and professors
- Schedule MMS 20 (2025–2027): Hanoi / HCMC dates where the module appears
- Canvas calendar: Services, E-business block (Jul 2026) and final exam
- Grade file Pricing Tactics: group work 50% + final exam 50%, grade /20
- Mau file text: Cohort 20 → copy to Cohort 21; 8 sessions
  (title, description, requirements); 2026 class follows Cohort 21
"""
from __future__ import annotations

import re
from datetime import datetime

# Even split across 4 semesters. The mau file requires semesters 1–4
# but does not label which module sits in which semester.
MODULES: list[dict] = [
    {
        "n": 1,
        "name": "International Marketing Decisions",
        "professor": "Nathalie Prime",
        "org": "ESCP",
        "expert": "Le Thi Minh Thao",
        "ects": 3,
        "coef": 1,
        "semester": 1,
        "schedule": (
            "Hanoi 20–23 Nov 2025 (Nathalie Prime); focus hour 13 Dec 2025 "
            "(Le Thi Minh Thao); Ho Chi Minh City 25–29 Nov 2025; exam 11 Jan 2026."
        ),
    },
    {
        "n": 2,
        "name": "Marketing Analytics",
        "professor": "Ngo Tan Vu Khanh",
        "org": "UEH",
        "ects": 3,
        "coef": 1,
        "semester": 1,
        "schedule": (
            "Hanoi 23–26 Oct 2025 (Ngo Tan Vu Khanh); Ho Chi Minh City 27 Oct–1 Nov 2025; "
            "exam 28 Dec 2025. No focus hour on the MMS 20 schedule."
        ),
    },
    {
        "n": 3,
        "name": "Services, E-business Approach and Digital Economy",
        "professor": "Damien Mourey",
        "org": "IAE",
        "ects": 3,
        "coef": 1,
        "semester": 1,
        "schedule": (
            "Canvas MMS20: Thu 23 Jul 2026 18:00–21:45; Fri 24 Jul 18:00–21:45; "
            "Sat 25 Jul 08:30–12:45 and 13:30–17:30; Sun 26 Jul 08:30–12:45 and 13:30–17:30; "
            "final exam Sun 6 Sep 2026 09:00–12:00. Professor Damien Mourey."
        ),
        "sessions": [
            ("Thu 23 Jul 2026, 18:00–21:45", "Opening block of Services, E-business Approach and Digital Economy.", "Attend the full evening block. The photo list is shared with the lecturer before the course."),
            ("Fri 24 Jul 2026, 18:00–21:45", "Second evening block with Prof. Damien Mourey.", "Read the syllabus section for this session before class."),
            ("Sat 25 Jul 2026, 08:30–12:45", "Morning workshop.", "Attendance is taken before and after the break."),
            ("Sat 25 Jul 2026, 13:30–17:30", "Afternoon workshop.", "Attendance is taken before and after the break."),
            ("Sun 26 Jul 2026, 08:30–12:45", "Morning application session.", "Prepare the case named in the syllabus."),
            ("Sun 26 Jul 2026, 13:30–17:30", "Closing teaching block.", "Group work is collected by Admin from the first session."),
            ("Group work", "Group assignment for the module. Weight on the MMS grade file: 50%.", "Submit to Admin by the lecturer's deadline. This component is not the final grade."),
            ("Final exam — Sun 6 Sep 2026, 09:00–12:00", "Final exam of Services, E-business Approach and Digital Economy.", "Sit the exam. Absence above the attendance rule makes the learner ineligible."),
        ],
    },
    {
        "n": 4,
        "name": "Consumer Behavior, the Digital Buyer",
        "professor": "Jean-Pierre Helfer",
        "org": "IAE",
        "expert": "Dang Thuy Ha",
        "ects": 3,
        "coef": 1,
        "semester": 1,
        "schedule": (
            "Hanoi 5–8 Oct 2025 (Jean-Pierre Helfer); focus hour 18 Oct 2025 (Dang Thuy Ha); "
            "Ho Chi Minh City 9–12 Oct 2025; exam 9 Nov 2025."
        ),
    },
    {
        "n": 5,
        "name": "Marketing Intelligence: Qualitative and Quantitative Studies in a Digital World",
        "professor": "Valerie Zaizon",
        "org": "IAE",
        "ects": 3,
        "coef": 1,
        "semester": 2,
        "schedule": "Professor Valerie Zaizon (IAE). Dates are set when the term calendar is published.",
    },
    {
        "n": 6,
        "name": "Business Negotiation",
        "professor": "Tran Van Nhu",
        "org": "CFVG",
        "ects": 3,
        "coef": 1,
        "semester": 2,
        "schedule": "Professor Tran Van Nhu (CFVG). Dates are set when the term calendar is published.",
    },
    {
        "n": 7,
        "name": "Data Analysis",
        "professor": "Nguyen Phu Hung",
        "org": "CFVG",
        "expert": "Tu Van Binh",
        "ects": 3,
        "coef": 1,
        "semester": 2,
        "schedule": (
            "Hanoi 28 Jan–1 Feb 2026 (Nguyen Phu Hung); Ho Chi Minh City (Tu Van Binh); "
            "group test 14 Mar 2026; exam 15 Mar 2026."
        ),
    },
    {
        "n": 8,
        "name": "Pricing Tactics: Cost-Based Procedure Versus Value-Pricing",
        "professor": "David Bargin",
        "org": "ESCP",
        "ects": 3,
        "coef": 1,
        "semester": 2,
        "schedule": "Professor David Bargin (ESCP). The sample grade file for Pricing Tactics uses group work 50% and final exam 50%.",
    },
    {
        "n": 9,
        "name": "Business to Business Marketing Management and Innovations",
        "professor": "Clive Gallery",
        "org": "IAE",
        "expert": "Le Quoc Thai",
        "ects": 3,
        "coef": 1,
        "semester": 3,
        "schedule": (
            "Hanoi 26 Feb–1 Mar 2026 (Clive Gallery); focus hour 8 and 12 May 2026 (Le Quoc Thai); "
            "Ho Chi Minh City 2–7 Mar 2026; exam 10 May 2026."
        ),
    },
    {
        "n": 10,
        "name": "Retailing and Supply Chain Organisation",
        "professor": "Jean-Charles Crouin",
        "org": "ESCP",
        "expert": "Tien Gia Tri",
        "ects": 3,
        "coef": 1,
        "semester": 3,
        "assessment": "Assignment only (Schedule MMS 20). No sit-in exam on that schedule.",
        "schedule": (
            "Hanoi 4–7 Dec 2025 (Jean-Charles Crouin); focus hour 10 Jan 2026 (Tien Gia Tri); "
            "Ho Chi Minh City 8–13 Dec 2025; assessment: assignment only."
        ),
    },
    {
        "n": 11,
        "name": "Promoting and Advertising: Integrated Marketing Communication in a Digital Era",
        "professor": "Ouidade Sabri",
        "org": "IAE",
        "ects": 3,
        "coef": 1,
        "semester": 3,
        "schedule": (
            "Professor Ouidade Sabri (IAE). Study trip 30 Mar–10 Apr 2026 (rooms B1–B3 reserved). "
            "Exam 31 May 2026."
        ),
    },
    {
        "n": 12,
        "name": "Sales Management: Digital Tools and Organisation",
        "professor": "Marylene Marquet",
        "org": "IAE",
        "ects": 3,
        "coef": 1,
        "semester": 3,
        "schedule": "Professor Marylene Marquet (IAE). Dates are set when the term calendar is published.",
    },
    {
        "n": 13,
        "name": "Brand Management and Building Strong Brands",
        "professor": "Geraldine Michel",
        "org": "IAE",
        "expert": "Dinh Cong Tai",
        "ects": 3,
        "coef": 1,
        "semester": 4,
        "schedule": (
            "Hanoi 15–18 Jan 2026 (Geraldine Michel); focus hour 4–5 Feb 2026 (Dinh Cong Tai); "
            "Ho Chi Minh City 19–24 Jan 2026; exam 8 Feb 2026. Tet holiday on the MMS 20 schedule: 12–23 Feb 2026."
        ),
    },
    {
        "n": 14,
        "name": "Business Game",
        "professor": "Sandrine Mace",
        "org": "ESCP",
        "ects": 3,
        "coef": 1,
        "semester": 4,
        "schedule": "Professor Sandrine Mace (ESCP). Played as a block; dates follow the term calendar.",
    },
    {
        "n": 15,
        "name": "Consultancy Project",
        "professor": "",
        "org": "CFVG",
        "ects": 18,
        "coef": 3,
        "semester": 4,
        "assessment": "Consultancy project. Coefficient 3, 18 ECTS. The programme director assigns the supervisor. The learner uploads the report on this module.",
        "schedule": "CP on PV MMS Hanoi 20. Supervisor is assigned by the programme director.",
        "sessions": [
            ("Topic and supervisor", "The programme director assigns the supervisor and the learner confirms the topic.", "Submit the topic before fieldwork starts."),
            ("Proposal", "Written proposal: question, method and timetable.", "The proposal is reviewed by the supervisor."),
            ("Fieldwork plan", "Plan of interviews, data and company access.", "Share the plan with the supervisor."),
            ("Interim review", "Mid-point review of evidence collected.", "Attend the review."),
            ("Analysis", "Analysis of the fieldwork against the proposal.", "Keep the working files available to the supervisor."),
            ("Draft report", "Full draft for supervisor comments.", "Submit the draft before the final deadline."),
            ("Final report upload", "Upload the consultancy report on the Consultancy Project module.", "Upload before the deadline set by the programme office."),
            ("Defense", "Oral defense with the jury named by the programme director.", "Attend the defense slot."),
        ],
    },
]

_STANDARD_SESSIONS = [
    (
        "Session 1 — Opening",
        "Opening block: module contract, outcomes and how the grade is built.",
        "Attend the opening session. The class photo list is shared with the lecturer.",
    ),
    (
        "Session 2 — Core concepts",
        "Main frameworks of the module.",
        "Read the syllabus section for this session before class.",
    ),
    (
        "Session 3 — Cases",
        "Cases and application in a digital or market context.",
        "Prepare the case named in the syllabus.",
    ),
    (
        "Session 4 — Workshop",
        "In-class workshop. Hanoi modules on the MMS 20 schedule usually run as a four-day block.",
        "Attendance is taken before and after the break.",
    ),
    (
        "Session 5 — Focus hour",
        "Focus hour with the local faculty member when the schedule names one.",
        "Attend the focus hour when it is on the calendar.",
    ),
    (
        "Session 6 — Group work",
        "Group work collected by Admin during the course. On the MMS grade file this component is 50%.",
        "Submit the group work to Admin by the lecturer's deadline.",
    ),
    (
        "Session 7 — Assignment",
        "Individual or group assignment. This mark supports the module; it is not the final grade by itself.",
        "Submit on the lecturer's deadline.",
    ),
    (
        "Session 8 — Final assessment",
        "Final exam, or the assignment-only close when the MMS 20 schedule says so.",
        "Sit the assessment. Absence above the attendance rule makes the learner ineligible.",
    ),
]

_PLACEHOLDER = re.compile(r"^MMS\d{3}$")
_VERSIONS = (
    ("MMS_Khoa_20", "HN.MMS20.", "MMS Cohort 20", "PV MMS Hanoi 20 — 15 modules, 60 ECTS, 4 semesters."),
    (
        "MMS_Khoa_21",
        "HN.MMS21.",
        "MMS Cohort 21",
        "Copy of Cohort 20 for the 2026 class. Adjust one module or the order before the term if needed.",
    ),
)


def _sessions_for(mod: dict) -> list[tuple[str, str, str]]:
    custom = mod.get("sessions")
    if custom:
        return list(custom)
    schedule = mod.get("schedule") or ""
    rows = []
    for i, (title, outline, req) in enumerate(_STANDARD_SESSIONS, start=1):
        extra = ""
        if i == 1 and schedule:
            extra = " Calendar: " + schedule
        if i == 8 and mod.get("assessment"):
            extra = " " + mod["assessment"]
            if "Assignment only" in (mod.get("assessment") or ""):
                title = "Session 8 — Assignment only"
                outline = "Schedule MMS 20 closes this module with an assignment, not a sit-in exam."
                req = "Submit the assignment. There is no sit-in exam on the MMS 20 schedule."
        rows.append((title, outline + extra, req))
    return rows


def _syllabus(mod: dict, cohort: str) -> tuple[str, str, str, str]:
    prof = mod.get("professor") or "Assigned by the programme director"
    org = mod.get("org") or ""
    note = (
        f"MMS {cohort} · module {mod['n']:02d} · semester {mod['semester']} · "
        f"{mod['ects']} ECTS · coefficient {mod['coef']}. "
        f"Professor: {prof}" + (f" ({org})." if org else ".")
    )
    if mod.get("expert"):
        note += f" Focus-hour / second city: {mod['expert']}."
    if mod.get("schedule"):
        note += " " + mod["schedule"]
    outcomes = (
        f"Apply {mod['name']} to an MMS marketing and sales situation "
        "and present the result in the group or individual assignment."
    )
    assessment = mod.get("assessment") or (
        "Group work 50% + final exam 50%. Grade /20, as on the MMS grade file (Pricing Tactics)."
    )
    reading = (
        "Reading list comes with the lecturer syllabus, requested 2.5 months before the course. "
        "Materials are released to learners at least 4 weeks before the course starts."
    )
    return note, outcomes, assessment, reading


def _purge_courses(cur, ids: list[int]) -> None:
    if not ids:
        return
    ph = ",".join("?" * len(ids))
    tables = [
        r[0]
        for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]
    for name in tables:
        if name == "courses":
            continue
        quoted = '"' + name.replace('"', '""') + '"'
        cols = [r[1] for r in cur.execute(f"PRAGMA table_info({quoted})").fetchall()]
        if "course_id" in cols:
            cur.execute(f"DELETE FROM {quoted} WHERE course_id IN ({ph})", ids)
    cur.execute(f"DELETE FROM courses WHERE id IN ({ph})", ids)


def _ensure_version(cur, code: str, name: str, description: str) -> int:
    row = cur.execute(
        "SELECT id FROM program_versions WHERE version_code = ?", (code,)
    ).fetchone()
    if row:
        cur.execute(
            "UPDATE program_versions SET name = ?, description = ?, is_active = 1 WHERE id = ?",
            (name, description, row[0]),
        )
        return row[0]
    cur.execute(
        "INSERT INTO program_versions (program_code, version_code, name, description, is_active) "
        "VALUES ('MMS', ?, ?, ?, 1)",
        (code, name, description),
    )
    return cur.lastrowid


def _fill_version(cur, version_id: int, prefix: str, cohort_label: str) -> int:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    created = 0
    for mod in MODULES:
        code = f"{prefix}M{mod['n']:02d}"
        note, outcomes, assessment, reading = _syllabus(mod, cohort_label)
        cur.execute(
            "INSERT INTO courses "
            "(program_version_id, code, name, semester, sort_order, theory_sessions, "
            "practice_sessions, syllabus_note, learning_outcomes, assessment_note, "
            "reading_list, syllabus_status, credits) "
            "VALUES (?,?,?,?,?, 8, 0, ?,?,?,?, 'published', ?)",
            (
                version_id,
                code,
                mod["name"],
                mod["semester"],
                mod["n"],
                note,
                outcomes,
                assessment,
                reading,
                float(mod["ects"]),
            ),
        )
        cid = cur.lastrowid
        created += 1
        for i, (title, outline, req) in enumerate(_sessions_for(mod), start=1):
            cur.execute(
                "INSERT INTO course_sessions "
                "(course_id, session_no, session_type, title, content_outline, "
                "requirements, duration_hours, sort_order, status) "
                "VALUES (?,?, 'theory', ?, ?, ?, 3, ?, 'planned')",
                (cid, i, f"{title} — {mod['name']}", outline, req, i),
            )
        cur.execute(
            "INSERT INTO course_materials "
            "(course_id, title, description, material_type, release_status, "
            "uploaded_by, search_text, created_at) "
            "VALUES (?, ?, ?, 'syllabus', 'draft', 'seed-mms', ?, ?)",
            (
                cid,
                f"Syllabus — {mod['name']}",
                "Attach the lecturer syllabus file. Learners see it after release.",
                f"{code} {mod['name']} syllabus".lower(),
                now,
            ),
        )
    return created


def _upsert_faculty(cur, full_name: str, organization: str, teachable: str, role: str) -> int:
    row = cur.execute(
        "SELECT id, teachable_courses FROM faculty WHERE full_name = ?", (full_name,)
    ).fetchone()
    if row:
        existing = row[1] or ""
        merged = existing
        for bit in teachable.split(","):
            bit = bit.strip()
            if bit and bit not in existing:
                merged = (merged + "," + bit).strip(",")
        cur.execute(
            "UPDATE faculty SET organization = COALESCE(NULLIF(organization,''), ?), "
            "specialty = COALESCE(NULLIF(specialty,''), 'Marketing and Sales'), "
            "teachable_courses = ?, role_type = COALESCE(NULLIF(role_type,''), ?) "
            "WHERE id = ?",
            (organization, merged, role, row[0]),
        )
        return row[0]
    cur.execute(
        "INSERT INTO faculty "
        "(full_name, role_type, organization, specialty, teachable_courses) "
        "VALUES (?, ?, ?, 'Marketing and Sales', ?)",
        (full_name, role, organization, teachable),
    )
    return cur.lastrowid


def _assign(cur, class_id: int, course_id: int, lecturer_id: int | None, expert_id: int | None) -> None:
    row = cur.execute(
        "SELECT id FROM teaching_assignments WHERE class_id = ? AND course_id = ?",
        (class_id, course_id),
    ).fetchone()
    if row:
        return
    cur.execute(
        "INSERT INTO teaching_assignments (class_id, course_id, lecturer_id, expert_id, status) "
        "VALUES (?, ?, ?, ?, 'assigned')",
        (class_id, course_id, lecturer_id, expert_id),
    )


def seed_mms_program(conn) -> dict:
    """Install Cohort 20 and Cohort 21 (15 modules × 8 sessions). Idempotent."""
    from course_content import ensure_course_content_tables

    cur = conn.cursor()
    ensure_course_content_tables(cur)
    out: dict = {"versions": {}, "faculty": 0, "assignments": 0, "classes": 0}

    version_ids: dict[str, int] = {}
    for code, prefix, name, desc in _VERSIONS:
        vid = _ensure_version(cur, code, name, desc)
        version_ids[code] = vid
        rows = cur.execute(
            "SELECT id, code FROM courses WHERE program_version_id = ?", (vid,)
        ).fetchall()
        codes = [r[1] or "" for r in rows]
        ready = sum(1 for c in codes if c.startswith(prefix))
        if ready >= 15:
            out["versions"][code] = {"id": vid, "courses": ready, "action": "kept"}
            continue
        if codes and any(not _PLACEHOLDER.match(c) and not c.startswith(prefix) for c in codes):
            out["versions"][code] = {
                "id": vid,
                "courses": len(codes),
                "action": "skipped_custom",
            }
            continue
        _purge_courses(cur, [r[0] for r in rows])
        cohort = "Cohort 20" if code.endswith("20") else "Cohort 21"
        n = _fill_version(cur, vid, prefix, cohort)
        out["versions"][code] = {"id": vid, "courses": n, "action": "installed"}

    # 2026 class follows Cohort 21 (mau file). Leave the E2E class on its own version.
    k21 = version_ids["MMS_Khoa_21"]
    cur.execute(
        "UPDATE class_groups SET program_version_id = ? "
        "WHERE program_code = 'MMS' AND IFNULL(name,'') NOT LIKE '%E2E%' "
        "AND (cohort_year = 2026 OR name LIKE '%K21%' OR name LIKE '%Khóa 21%' "
        "OR name LIKE '%Cohort 21%')",
        (k21,),
    )
    out["classes"] = cur.rowcount
    exists = cur.execute(
        "SELECT id FROM class_groups WHERE program_code = 'MMS' AND name = 'MMS K21'"
    ).fetchone()
    if not exists:
        cur.execute(
            "INSERT INTO class_groups (program_code, name, program_version_id, cohort_year, status) "
            "VALUES ('MMS', 'MMS K21', ?, 2026, 'active')",
            (k21,),
        )
        out["classes"] += 1

    faculty_ids: dict[str, int] = {}
    for mod in MODULES:
        codes = ",".join(f"{prefix}M{mod['n']:02d}" for _, prefix, _, _ in _VERSIONS)
        if mod.get("professor"):
            fid = _upsert_faculty(cur, mod["professor"], mod.get("org") or "", codes, "lecturer")
            faculty_ids[mod["professor"]] = fid
            out["faculty"] += 1
        if mod.get("expert"):
            eid = _upsert_faculty(cur, mod["expert"], "CFVG", codes, "expert")
            faculty_ids[mod["expert"]] = eid
            out["faculty"] += 1

    classes = cur.execute(
        "SELECT id FROM class_groups WHERE program_version_id = ? AND IFNULL(name,'') NOT LIKE '%E2E%'",
        (k21,),
    ).fetchall()
    course_rows = cur.execute(
        "SELECT id, sort_order FROM courses WHERE program_version_id = ? ORDER BY sort_order",
        (k21,),
    ).fetchall()
    by_n = {int(sort): cid for cid, sort in course_rows}
    for (class_id,) in classes:
        for mod in MODULES:
            cid = by_n.get(mod["n"])
            if not cid:
                continue
            before = cur.execute(
                "SELECT id FROM teaching_assignments WHERE class_id = ? AND course_id = ?",
                (class_id, cid),
            ).fetchone()
            _assign(
                cur,
                class_id,
                cid,
                faculty_ids.get(mod.get("professor") or ""),
                faculty_ids.get(mod.get("expert") or ""),
            )
            if not before:
                out["assignments"] += 1

    conn.commit()
    return out
