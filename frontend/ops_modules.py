"""
Ops module UI config: search / view / manage actions per business function.

Column provenance (liên thông dữ liệu):
- source "own"  → nhập trực tiếp tại chức năng/bộ phận đang mở (tiêu đề xanh)
- source khác   → dữ liệu từ bộ phận khác (tiêu đề màu theo nguồn)
"""

# CSS class suffix: ops-src--{code}
SOURCE_META = {
    "own": {
        "label_vi": "Nhập tại chức năng này",
        "label_en": "Entered in this function",
    },
    "admissions": {
        "label_vi": "Từ Tuyển sinh",
        "label_en": "From Admissions",
    },
    "accounting": {
        "label_vi": "Từ Kế toán",
        "label_en": "From Accounting",
    },
    "coordinator": {
        "label_vi": "Từ Điều phối CT",
        "label_en": "From Program coordinator",
    },
    "teaching": {
        "label_vi": "Từ Giảng dạy",
        "label_en": "From Teaching",
    },
    "faculty": {
        "label_vi": "Từ Giảng viên / phân giảng",
        "label_en": "From Faculty / assignment",
    },
    "asst": {
        "label_vi": "Từ Trợ lý BGD",
        "label_en": "From Executive assistant",
    },
    "it": {
        "label_vi": "Từ IT / Canvas",
        "label_en": "From IT / Canvas",
    },
    "ref": {
        "label_vi": "Từ bộ phận khác",
        "label_en": "From another department",
    },
}

# permission_code -> { field_key: source_code }
# Fields not listed default to "own" (nhập tại màn hình đó).
FIELD_SOURCES = {
    "admissions.applications": {
        "written_exam_no": "coordinator",
        "written_score": "coordinator",
        "written_exam_room": "coordinator",
        "written_exam_session": "coordinator",
        "written_exam_date": "coordinator",
        "interview_date": "coordinator",
        "final_result": "coordinator",
        "no_show": "coordinator",
    },
    "admissions.written_exams": {
        "full_name": "admissions",
        "program_code": "admissions",
        "round_code": "admissions",
        "email": "admissions",
        "status": "admissions",
    },
    "admissions.results": {
        "cfvg_app_no": "admissions",
        "full_name": "admissions",
        "program_code": "admissions",
        "campus": "admissions",
        "email": "admissions",
        "degree_verified": "admissions",
        "english_verified": "admissions",
    },
    "admissions.pre_enroll": {
        "candidate_code": "own",
        "full_name": "own",
        "admit_decision": "own",
        "program_code": "admissions",
    },
    "admissions.enrolled_files": {
        "student_code": "own",
        "candidate_code": "admissions",
        "full_name": "admissions",
        "enrolled_at": "own",
        "program_code": "coordinator",
    },
    "admissions.interviews": {
        "program_code": "admissions",
        "round_code": "admissions",
    },
    "accounting.fees": {
        "full_name": "admissions",
        "program_code": "admissions",
        "application_status": "admissions",
    },
        "accounting.charges": {
        "full_name": "admissions",
        "student_code": "coordinator",
        "program_code": "admissions",
        "scholarship_type": "own",
    },
    "accounting.tuition_tracker": {
        "full_name": "admissions",
        "student_code": "coordinator",
        "program_code": "admissions",
        "scholarship_type": "own",
    },
    "accounting.fee_alerts": {
        "full_name": "admissions",
        "student_code": "coordinator",
        "program_code": "admissions",
    },
    "accounting.candidate_files": {
        "full_name": "admissions",
        "email": "admissions",
        "phone": "admissions",
        "program_code": "admissions",
        "cfvg_app_no": "admissions",
    },
    "accounting.collection_report": {
        "full_name": "admissions",
        "program_code": "admissions",
        "fee_type": "own",
    },
    "accounting.official_list": {
        "full_name": "admissions",
        "program_code": "admissions",
        "email": "admissions",
        "status": "admissions",
    },
    "students.manage": {
        "full_name": "admissions",
        "email": "admissions",
        "program_code": "coordinator",
        "class_name": "coordinator",
        "scholarship_type": "accounting",
        "partner_enrollment": "asst",
    },
    "teaching.schedule": {
        "class_name": "coordinator",
        "program_code": "coordinator",
        "course_code": "coordinator",
        "course_name": "coordinator",
        "lecturer": "faculty",
        "expert": "faculty",
    },
    "teaching.assign": {
        "class_name": "coordinator",
        "program_code": "coordinator",
        "course_code": "coordinator",
        "course_name": "coordinator",
    },
    "teaching.lessons": {
        "program_code": "coordinator",
        "class_name": "coordinator",
        "course_code": "coordinator",
        "course_name": "coordinator",
        "lecturer": "faculty",
        "status": "faculty",
    },
    "teaching.materials": {
        "program_code": "coordinator",
        "course_code": "coordinator",
        "course_name": "coordinator",
    },
    "teaching.exams": {
        "class_name": "coordinator",
        "program_code": "coordinator",
        "student_count": "students",
        "ineligible_count": "students",
        "exam_eligibility_note": "students",
    },
    "teaching.thesis": {
        "full_name": "students",
        "program_code": "coordinator",
        "payment_status": "accounting",
    },
    "teaching.grades": {
        "student_count": "students",
    },
    "asst.intl_faculty": {
        "program_code": "coordinator",
        "course_name": "coordinator",
        "partner_university": "asst",
        "partner_code": "asst",
    },
    "asst.intl_students": {
        "program_code": "coordinator",
        "direction": "asst",
        "exchange_kind": "asst",
        "handoff_visa_by": "asst",
        "handoff_iae_by": "accounting",
        "handoff_courses_by": "coordinator",
    },
    "teaching.faculty": {
        "contract_status": "faculty",
        "cfvg_payment_status": "accounting",
        "grade_return_date": "faculty",
    },
    "asst.payments": {
        "program_code": "coordinator",
    },
    "canvas.coordinator": {
        "student_count": "students",
        "pending": "it",
        "synced": "it",
        "sync_label": "it",
    },
    "canvas.faculty": {
        "class_name": "coordinator",
        "program_code": "coordinator",
        "course_code": "coordinator",
        "course_name": "coordinator",
        "lecturer": "faculty",
        "expert": "faculty",
        "sis_course_id": "it",
        "sync_status": "it",
    },
    "canvas.student": {
        "full_name": "admissions",
        "email": "admissions",
        "class_name": "coordinator",
        "program_code": "coordinator",
        "courses_total": "coordinator",
        "courses_ready": "it",
        "access": "it",
    },
    "canvas.accounting": {},
}

# Alias source used above when "students" is not in SOURCE_META
SOURCE_META["students"] = {
    "label_vi": "Từ Quản lý học viên",
    "label_en": "From Student management",
}


def normalize_column(col, source_map=None):
    """Normalize (key, label[, source]) or dict → {key, label, source, src_label}."""
    source_map = source_map or {}
    if isinstance(col, dict):
        key = col.get("key") or col.get("id")
        label = col.get("label") or key
        source = col.get("source") or source_map.get(key) or "own"
        if source not in SOURCE_META:
            source = "ref"
        meta = SOURCE_META.get(source) or SOURCE_META["ref"]
        return {
            "key": key,
            "label": label,
            "source": source,
            "src_label": col.get("src_label") or meta["label_vi"],
            "src_label_en": col.get("src_label_en") or meta["label_en"],
        }
    key = col[0]
    label = col[1]
    source = col[2] if len(col) > 2 else (source_map.get(key) or "own")
    if source not in SOURCE_META:
        source = "ref"
    meta = SOURCE_META.get(source) or SOURCE_META["ref"]
    return {
        "key": key,
        "label": label,
        "source": source,
        "src_label": meta["label_vi"],
        "src_label_en": meta["label_en"],
    }


def apply_column_provenance() -> None:
    """Attach source metadata to every module column for grid/edit coloring."""
    for code, cfg in OPS_MODULES.items():
        source_map = FIELD_SOURCES.get(code) or {}
        cols = [normalize_column(c, source_map) for c in (cfg.get("columns") or [])]
        cfg["columns"] = cols
        used = sorted({c["source"] for c in cols if c.get("source")})
        cfg["field_sources"] = source_map
        cfg["source_legend"] = [
            {
                "code": s,
                "label": SOURCE_META[s]["label_vi"],
                "label_en": SOURCE_META[s]["label_en"],
            }
            for s in used
            if s in SOURCE_META
        ]
        cfg["has_mixed_sources"] = any(s != "own" for s in used)


# permission_code -> page config (endpoint = Flask view name)
OPS_MODULES = {
    # --- Canvas LMS theo nhóm đối tượng ---
    "canvas.coordinator": {
        "title": "Canvas — Điều phối",
        "desc": "Xuất gói lớp (Users / Courses / Enrollments) để đưa lên x.instructure.com.",
        "endpoint": "ops_canvas_coordinator",
        "api": "/ops/canvas/hub/coordinator",
        "mode": "manage",
        "search": False,
        "is_canvas_hub": True,
        "audience": "coordinator",
        "columns": [
            ("name", "Lớp"),
            ("program_code", "CT"),
            ("cohort_year", "Khóa"),
            ("student_count", "HV"),
            ("course_links", "Môn map"),
            ("pending", "Chờ đẩy"),
            ("synced", "Đã xuất/live"),
            ("sync_label", "Canvas"),
        ],
        "canvas_row_export": True,
        "actions": ["Xem gói đã tạo"],
        "primary_action": None,
    },
    "canvas.faculty": {
        "title": "Canvas — Giảng viên",
        "desc": "Lớp–môn trên Canvas: tài liệu, bài tập, chấm SpeedGrader.",
        "endpoint": "ops_canvas_faculty",
        "api": "/ops/canvas/hub/faculty",
        "mode": "view",
        "search": False,
        "is_canvas_hub": True,
        "audience": "faculty",
        "columns": [
            ("class_name", "Lớp"),
            ("program_code", "CT"),
            ("course_code", "Mã HP"),
            ("course_name", "Học phần"),
            ("lecturer", "GV LT"),
            ("expert", "Chuyên gia"),
            ("sis_course_id", "SIS Course"),
            ("sync_status", "TT Canvas"),
        ],
        "actions": ["Mở Canvas"],
        "primary_action": None,
    },
    "canvas.student": {
        "title": "Canvas — Học viên",
        "desc": "Trạng thái enroll và hướng dẫn đăng nhập Canvas.",
        "endpoint": "ops_canvas_student",
        "api": "/ops/canvas/hub/student",
        "mode": "view",
        "search": False,
        "is_canvas_hub": True,
        "audience": "student",
        "columns": [
            ("full_name", "Họ tên"),
            ("email", "Email login Canvas"),
            ("class_name", "Lớp"),
            ("program_code", "CT"),
            ("courses_total", "Số môn"),
            ("courses_ready", "Đã trên Canvas"),
            ("access", "Truy cập"),
        ],
        "actions": ["Đăng nhập Canvas"],
        "primary_action": None,
    },
    "canvas.accounting": {
        "title": "Canvas — Ghi danh",
        "desc": "Xuất roster HV official (sau nộp phí) cho Canvas People / SIS.",
        "endpoint": "ops_canvas_accounting",
        "api": "/ops/canvas/hub/accounting",
        "mode": "manage",
        "search": False,
        "is_canvas_hub": True,
        "audience": "accounting",
        "columns": [
            ("id", "Mã gói"),
            ("title", "Nội dung"),
            ("status", "TT"),
            ("created_at", "Tạo lúc"),
        ],
        "actions": ["Xuất roster → Canvas"],
        "primary_action": "Xuất roster → Canvas",
        "canvas_export_roster": True,
    },
    "canvas.it": {
        "title": "Canvas — IT / Sync",
        "desc": "SIS ID map, nhật ký đồng bộ, đánh dấu đã đẩy lên Canvas.",
        "endpoint": "ops_canvas_it",
        "api": "/ops/canvas/hub/it",
        "mode": "manage",
        "search": False,
        "is_canvas_hub": True,
        "audience": "it",
        "columns": [
            ("created_at", "Thời điểm"),
            ("action", "Hành động"),
            ("audience", "Đối tượng"),
            ("detail", "Chi tiết"),
            ("actor", "Người thực hiện"),
        ],
        "actions": ["Xem gói export", "Đánh dấu đã đẩy"],
        "primary_action": None,
        "canvas_it_panel": True,
    },
    "asst.exec_tasks": {
        "title": "Công việc & nhiệm vụ BGD",
        "desc": "Họp Ban Giám đốc → biên bản → nhiệm vụ → người phụ trách → hạn → tiến độ.",
        "endpoint": "ops_asst_tasks",
        "api": "/ops/asst/tasks",
        "mode": "manage",
        "search": True,
        "columns": [
            ("title", "Nhiệm vụ"),
            ("meeting_title", "Cuộc họp"),
            ("assignee", "Phụ trách"),
            ("department", "Bộ phận"),
            ("due_date", "Hạn"),
            ("status", "Tiến độ"),
            ("notes", "Ghi chú"),
        ],
        "actions": ["Tạo nhiệm vụ", "Xuất báo cáo sau họp"],
        "primary_action": "Thêm nhiệm vụ",
        "allow_delete": True,
        "delete_path": "asst/tasks",
    },
    "asst.calendar": {
        "title": "Lịch tuần X",
        "desc": "Lịch BGD, họp, sự kiện, giảng dạy, nghỉ phép — dùng chung và cảnh báo trùng.",
        "endpoint": "ops_asst_calendar",
        "api": "/ops/asst/calendar",
        "mode": "manage",
        "search": True,
        "columns": [
            ("title", "Hoạt động"),
            ("cal_type", "Loại"),
            ("starts_at", "Bắt đầu"),
            ("ends_at", "Kết thúc"),
            ("location", "Địa điểm"),
            ("owner", "Phụ trách"),
            ("conflict", "Trùng lịch"),
            ("status", "TT"),
        ],
        "actions": [
            {"id": "print_page", "label": "In lịch tuần"},
            "Thông báo thay đổi",
        ],
        "primary_action": "Thêm lịch",
        "allow_delete": True,
        "delete_path": "asst/calendar",
    },
    "asst.intl_faculty": {
        "title": "Giảng viên quốc tế",
        "desc": "Hộ chiếu → visa → vé máy bay → khách sạn → đón tiễn → lịch giảng.",
        "endpoint": "ops_asst_intl_faculty",
        "api": "/ops/asst/intl-faculty",
        "mode": "manage",
        "search": True,
        "columns": [
            ("full_name", "Họ tên"),
            ("nationality", "Quốc tịch"),
            ("partner_university", "Trường đối tác"),
            ("program_code", "CT"),
            ("course_name", "Môn"),
            ("passport_expiry", "Hết hạn HC"),
            ("visa_expiry", "Hết hạn visa"),
            ("visa_status", "Visa"),
            ("arrival_date", "Đến"),
            ("arrival_flight", "Chuyến bay"),
            ("hotel_name", "Khách sạn"),
            ("status", "TT hồ sơ"),
        ],
        "actions": [
            {"id": "open_partner_universities", "label": "Trường đối tác"},
            "Cảnh báo hết hạn",
            "Xuất báo cáo visa",
        ],
        "primary_action": "Thêm GV quốc tế",
        "row_buttons": [
            {"id": "generic_edit", "label": "Cập nhật"},
        ],
        "allow_delete": True,
        "delete_path": "asst/intl-faculty",
    },
    "asst.intl_students": {
        "title": "Học viên quốc tế",
        "desc": "Exchange In/Out · double degree / 1 học kỳ; Visa → Trợ lý BGD; IAE → KT; courses → Điều phối.",
        "endpoint": "ops_asst_intl_students",
        "api": "/ops/asst/intl-students",
        "mode": "manage",
        "search": True,
        "columns": [
            ("full_name", "Họ tên"),
            ("cccd", "CCCD"),
            ("direction", "Chiều"),
            ("exchange_kind", "Hình thức"),
            ("semester", "HK"),
            ("program_code", "CT"),
            ("partner_university", "Đối tác"),
            ("nationality", "Quốc tịch"),
            ("visa_status", "Visa"),
            ("handoff_visa_by", "Visa →"),
            ("handoff_iae_by", "IAE →"),
            ("onboarding_status", "Onboarding"),
            ("email", "Email"),
        ],
        "actions": ["DS visa cần làm", "Xuất DS nhập cảnh"],
        "primary_action": "Thêm HV quốc tế",
        "allow_delete": True,
        "delete_path": "asst/intl-students",
    },
    "asst.director_fr": {
        "title": "Hồ sơ GĐ Pháp & gia đình",
        "desc": "Visa, giấy phép lao động, đăng ký cư trú — cảnh báo hết hạn.",
        "endpoint": "ops_asst_director_fr",
        "api": "/ops/asst/director-fr",
        "mode": "manage",
        "search": False,
        "columns": [
            ("full_name", "Họ tên"),
            ("relation", "Quan hệ"),
            ("passport_no", "Hộ chiếu"),
            ("passport_expiry", "Hết hạn HC"),
            ("visa_info", "Visa"),
            ("work_permit", "Work permit"),
            ("residence_reg", "Cư trú"),
            ("doc_expiry", "Hết hạn GT"),
            ("status", "TT"),
        ],
        "actions": ["Cảnh báo hết hạn"],
        "primary_action": "Cập nhật hồ sơ",
        "row_buttons": [
            {"id": "view_director_fr", "label": "Xem chi tiết"},
            {"id": "generic_edit", "label": "Cập nhật"},
        ],
        "allow_delete": True,
        "delete_path": "asst/director-fr",
    },
    "asst.documents": {
        "title": "Văn thư & con dấu",
        "desc": "Công văn đến/đi, cấp số, đóng dấu, phát hành và lưu sổ.",
        "endpoint": "ops_asst_documents",
        "api": "/ops/asst/documents",
        "mode": "manage",
        "search": True,
        "columns": [
            ("doc_direction", "Chiều"),
            ("doc_no", "Số/KH"),
            ("doc_date", "Ngày"),
            ("sender_or_receiver", "Gửi/Nhận"),
            ("subject", "Trích yếu"),
            ("handler", "Xử lý"),
            ("due_date", "Hạn"),
            ("status", "TT"),
            ("seal_used", "Con dấu"),
        ],
        "actions": ["Cấp số", "Xuất sổ CV đến", "Xuất sổ CV đi"],
        "primary_action": "Ghi nhận công văn",
        "allow_delete": True,
        "delete_path": "asst/documents",
    },
    "asst.procurement": {
        "title": "Mua sắm & hậu cần",
        "desc": "VP phẩm, nước Lavie, taxi/đón tiễn — đề xuất đến thanh toán.",
        "endpoint": "ops_asst_procurement",
        "api": "/ops/asst/procurement",
        "mode": "manage",
        "search": True,
        "columns": [
            ("category", "Nhóm"),
            ("item_name", "Hàng/DV"),
            ("quantity", "SL"),
            ("amount", "Thành tiền"),
            ("requester", "Đề xuất"),
            ("supplier", "NCC"),
            ("request_date", "Ngày"),
            ("status", "TT"),
        ],
        "actions": ["Xuất báo cáo tháng"],
        "primary_action": "Tạo đề xuất",
        "allow_delete": True,
        "delete_path": "asst/procurement",
    },
    "asst.payments": {
        "title": "Hóa đơn & thanh toán",
        "desc": "Theo dõi vé máy bay, taxi, VP phẩm — hóa đơn và thanh toán hàng tháng.",
        "endpoint": "ops_asst_payments",
        "api": "/ops/asst/payments",
        "mode": "manage",
        "search": True,
        "columns": [
            ("month_key", "Tháng"),
            ("cost_type", "Loại CP"),
            ("beneficiary", "Người/ĐT"),
            ("program_code", "CT"),
            ("supplier", "NCC"),
            ("amount", "Số tiền"),
            ("invoice_date", "Ngày HĐ"),
            ("payment_status", "TT thanh toán"),
        ],
        "actions": ["Báo cáo tháng", "Cảnh báo chưa thanh toán"],
        "primary_action": None,
        "allow_delete": True,
        "delete_path": "asst/payments",
    },
    "asst.weekly_report": {
        "title": "Báo cáo tuần NEU",
        "desc": "Tổng hợp công việc các bộ phận → BGD duyệt → gửi NEU.",
        "endpoint": "ops_asst_weekly_report",
        "api": "/ops/asst/weekly-reports",
        "mode": "manage",
        "search": False,
        "columns": [
            ("week_label", "Tuần"),
            ("week_start", "Bắt đầu"),
            ("done_summary", "Đã làm"),
            ("ongoing_summary", "Đang làm"),
            ("next_week_plan", "Tuần tới"),
            ("status", "TT"),
            ("sent_at", "Gửi NEU"),
        ],
        "actions": ["Gửi duyệt BGD", "Xuất mẫu NEU"],
        "primary_action": "Tạo báo cáo tuần",
        "allow_delete": True,
        "delete_path": "asst/weekly-reports",
    },
    "asst.leave": {
        "title": "Nghỉ phép nhân sự",
        "desc": "Đăng ký/phê duyệt nghỉ; theo dõi số ngày phép; đồng bộ lịch làm việc.",
        "endpoint": "ops_asst_leave",
        "api": "/ops/asst/leave",
        "mode": "manage",
        "search": True,
        "columns": [
            ("employee_name", "Nhân sự"),
            ("department", "Bộ phận"),
            ("leave_type", "Loại nghỉ"),
            ("start_date", "Từ"),
            ("end_date", "Đến"),
            ("days", "Số ngày"),
            ("substitute", "Người thay"),
            ("status", "TT"),
            ("reason", "Lý do"),
        ],
        "leave_actions": True,
        "actions": ["Lịch nghỉ tuần", "Báo cáo phép còn lại"],
        "primary_action": "Đăng ký nghỉ",
        "allow_delete": True,
        "delete_path": "asst/leave",
    },
    "admissions.rounds": {
        "title": "Đợt tuyển sinh",
        "desc": "Tạo đợt theo CT/intake (MBA May & Aug…); mở–đóng hồ sơ; timeline thi viết & phỏng vấn.",
        "endpoint": "ops_admissions_rounds",
        "api": "/ops/admission-rounds",
        "mode": "manage",
        "search": True,
        "program_filter": True,
        "status_filter": True,
        "year_filter": True,
        "intake_filter": True,
        "columns": [
            ("code", "Mã đợt"),
            ("name", "Tên"),
            ("programs", "Chương trình"),
            ("intake", "Intake"),
            ("year", "Năm"),
            ("exam_timeline", "Timeline thi"),
            ("interview_timeline", "Timeline PV"),
            ("status", "Trạng thái"),
            ("related_apps", "Hồ sơ"),
            ("doc_count", "Tài liệu"),
            ("opened_at", "Mở"),
            ("closed_at", "Đóng"),
        ],
        "actions": [],
        "primary_action": "Tạo đợt mới",
        "row_buttons": [
            {"id": "view_round", "label": "Xem chi tiết"},
            {"id": "manage_round_docs", "label": "Tài liệu đợt"},
        ],
        "allow_delete": True,
        "delete_path": "rounds",
    },
    "admissions.round_docs": {
        "title": "Tìm kiếm tài liệu",
        "desc": "Chọn năm tuyển sinh trước, sau đó mới hiện các đợt của năm đó. Lọc tài liệu dùng chung hoặc riêng từng khóa.",
        "endpoint": "ops_admissions_round_docs",
        "api": "/ops/admission-round-docs",
        "mode": "manage",
        "search": True,
        "round_filter": True,
        "year_then_round": True,
        "doc_scope_filter": True,
        "program_filter": True,
        "is_round_docs": True,
        "columns": [
            ("round_year", "Năm"),
            ("round_code", "Đợt"),
            ("round_name", "Tên đợt"),
            ("doc_type_name", "Loại"),
            ("title", "Tên tài liệu"),
            ("original_name", "File"),
            ("program_codes", "CT"),
            ("share_scope", "Phạm vi"),
            ("cohort_code", "Khóa"),
            ("uploaded_at", "Ngày tải"),
            ("uploaded_by", "Người tải"),
        ],
        "row_buttons": [
            {"id": "preview_round_doc", "label": "Xem trước"},
            {"id": "download_round_doc", "label": "Tải xuống"},
            {"id": "delete_round_doc", "label": "Xóa"},
        ],
        "actions": [{"id": "print_page", "label": "In danh sách"}],
        "primary_action": {"id": "upload_round_doc", "label": "Tải tài liệu lên"},
    },
    "admissions.doc_types": {
        "title": "Phân loại tài liệu",
        "desc": "Khai báo danh mục loại tài liệu: quy chế cấp chương trình / phòng ban / trung tâm, thông báo, hội đồng, giấy phép, báo cáo, biên bản, minh chứng kiểm định.",
        "endpoint": "ops_admissions_doc_types",
        "api": "/ops/admission-doc-types",
        "mode": "manage",
        "search": True,
        "edit_path": "admission-doc-types",
        "allow_delete": True,
        "delete_path": "admission-doc-types",
        "columns": [
            ("code", "Mã"),
            ("name", "Tên loại"),
            ("name_en", "EN"),
            ("sort_order", "Thứ tự"),
            ("status", "Trạng thái"),
        ],
        "actions": [],
        "primary_action": {"id": "create_doc_type", "label": "Thêm loại tài liệu"},
    },
    "admissions.written_exams": {
        "title": "Thi viết",
        "desc": "Danh sách thi viết gửi Admin chương trình. Admin cập nhật không phản hồi sau deadline; Điều phối gán SBD và điểm.",
        "endpoint": "ops_admissions_written_exams",
        "api": "/ops/written-exams",
        "mode": "manage",
        "search": True,
        "columns": [
            ("written_exam_no", "SBD"),
            ("full_name", "Họ tên"),
            ("program_code", "CT"),
            ("dob", "Ngày sinh"),
            ("degree_grade", "GPA"),
            ("round_code", "Đợt"),
            ("written_exam_room", "Phòng thi"),
            ("written_exam_session", "Ca thi"),
            ("written_score", "Điểm viết"),
            ("written_gk", "Phần 1"),
            ("written_mle", "Phần 2"),
            ("interview_score", "Điểm PV"),
            ("avg_score", "TB"),
            ("exam_eligible_flag", "ĐK dự thi"),
            ("written_exam_date", "Ngày thi"),
            ("status", "Trạng thái"),
            ("no_response", "Không phản hồi"),
            ("no_show", "Không đến"),
            ("person_stage_label", "Vai trò"),
            ("exam_fee_status", "Lệ phí thi"),
            ("exam_roster_status", "DS hội đồng"),
            ("exam_board_listed", "Hội đồng"),
            ("email", "Email"),
        ],
        "actions": [
            "Assign exam numbers",
            "Import round scores",
            "Export written exam",
            "Create interview boards",
            {"id": "notify_exam_schedule", "label": "Gửi thông báo lịch thi"},
            {"id": "export_excel", "label": "Xuất DS gửi Admin CT"},
        ],
        "row_buttons": [
            {"id": "open_person_dossier", "label": "Hồ sơ xuyên suốt"},
            {"id": "confirm_examinee", "label": "Xác nhận dự thi"},
            {"id": "register_examinee", "label": "Đăng ký nội dung thi"},
            {"id": "mark_exam_fee", "label": "Xác nhận lệ phí thi"},
            {"id": "list_exam_board", "label": "Vào danh sách hội đồng"},
        ],
        "primary_action": None,
    },
    "admissions.applications": {
        "title": "Hồ sơ ứng viên",
        "desc": "Nhận hồ sơ ứng viên, issue checklist (X / Incompleted / Exempted / Not required), phản hồi giấy tờ thiếu, hướng dẫn lịch thi và phỏng vấn.",
        "endpoint": "ops_admissions_applications",
        "api": "/ops/applications",
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "round_filter": True,
        "program_filter": True,
        "columns": [
            ("identifier", "Mã định danh"),
            ("cfvg_app_no", "Mã hồ sơ"),
            ("full_name", "Họ tên"),
            ("cccd", "CCCD"),
            ("campus", "CS"),
            ("program_code", "CT"),
            ("lead_source", "Nguồn"),
            ("email", "Email"),
            ("phone", "SĐT"),
            ("dob", "Ngày sinh"),
            ("degree_grade", "GPA"),
            ("experience_years", "KN (năm)"),
            ("checklist_status", "Checklist"),
            ("checklist_received_by", "TS nhận hồ sơ"),
            ("no_response", "Không phản hồi"),
            ("english_cert", "Chứng chỉ TA"),
            ("english_cert_score", "Điểm TA"),
            ("english_file", "File CC NN"),
            ("degree_file", "File bằng ĐH"),
            ("other_file", "File minh chứng"),
            ("doc_count", "Số TL"),
            ("final_result", "KQ cuối"),
            ("dossier_status", "Hồ sơ"),
            ("sitting_status", "Dự thi"),
            ("selection_status", "Xét tuyển"),
            ("decision_status", "Quyết định"),
            ("response_status", "Phản hồi"),
            ("status", "Trạng thái"),
            ("person_stage_label", "Vai trò"),
            ("exam_fee_status", "Lệ phí thi"),
            ("transferred_at", "Ngày chuyển ĐP"),
            ("transferred_by", "Người chuyển"),
        ],
        "row_actions": [
            {"label": "Phê duyệt TS", "status": "approved_ts"},
            {"label": "Chuyển PV", "status": "interview"},
            {"label": "Đỗ", "status": "passed"},
            {"label": "Trượt", "status": "failed"},
            {"label": "Rút hồ sơ", "status": "withdrawn"},
        ],
        "row_buttons": [
            {"id": "view_application", "label": "Xem chi tiết"},
            {"id": "edit_application", "label": "Sửa"},
            {"id": "update_application", "label": "Cập nhật"},
            {"id": "manage_app_docs", "label": "Tài liệu hồ sơ"},
            {"id": "confirm_examinee", "label": "Xác nhận dự thi"},
            {"id": "register_examinee", "label": "Đăng ký nội dung thi"},
            {"id": "open_person_dossier", "label": "Hồ sơ xuyên suốt"},
        ],
        "actions": [
            "Tải mẫu Excel",
            "Import Excel",
            "Xuất Excel",
            "Xuất DS gửi Điều phối",
            {"id": "print_page", "label": "In danh sách"},
        ],
        "primary_action": None,
        "allow_delete": True,
        "delete_path": "applications",
    },
    "admissions.interviews": {
        "title": "Phỏng vấn",
        "desc": "Ba giảng viên chấm trên từng thí sinh. Hệ thống tính điểm trung bình ngay khi lưu.",
        "endpoint": "ops_admissions_interviews",
        "api": "/ops/interviews",
        "mode": "manage",
        "search": True,
        "edit_path": "interviews",
        "round_filter": True,
        "program_filter": True,
        "interview_score_link": True,
        "columns": [
            ("title", "Buổi PV"),
            ("program_code", "CT"),
            ("room", "Phòng"),
            ("starts_at", "Thời gian"),
            ("owner", "Người phụ trách"),
            ("slot_minutes", "Phút/SV"),
            ("slot_count", "Số thí sinh"),
            ("round_code", "Đợt"),
        ],
        "actions": [
            "Create interview boards",
            {"id": "print_page", "label": "In lịch phỏng vấn"},
            {"id": "export_interview_slots", "label": "Xuất Excel slot PV"},
            {"id": "notify_interview_invites", "label": "Gửi thư mời phỏng vấn"},
        ],
        "primary_action": None,
    },
    "admissions.results": {
        "title": "Kết quả tuyển sinh",
        "desc": "Danh sách thí sinh kèm điểm viết / phỏng vấn / trung bình và tài liệu đã upload (CC ngoại ngữ, bằng ĐH, minh chứng).",
        "endpoint": "ops_admissions_results",
        "api": "/ops/applications",
        "api_params": {"decision": "1"},
        "mode": "view",
        "search": True,
        "status_filter": True,
        "round_filter": True,
        "program_filter": True,
        "columns": [
            ("cfvg_app_no", "Mã hồ sơ"),
            ("full_name", "Họ tên"),
            ("cccd", "CCCD"),
            ("program_code", "CT"),
            ("campus", "CS"),
            ("written_score", "Điểm viết"),
            ("interview_score", "Điểm PV"),
            ("avg_score", "Điểm TB"),
            ("english_file", "CC ngoại ngữ"),
            ("degree_file", "Bằng ĐH"),
            ("other_file", "Minh chứng"),
            ("final_result", "KQ"),
            ("status", "Trạng thái"),
            ("email", "Email"),
        ],
        "row_buttons": [
            {"id": "open_person_dossier", "label": "Hồ sơ xuyên suốt"},
            {"id": "view_application", "label": "Xem chi tiết"},
            {"id": "manage_app_docs", "label": "Tài liệu hồ sơ"},
        ],
        "actions": [
            "Gửi email kết quả",
            {"id": "edit_result_templates", "label": "Mẫu thư đỗ / trượt"},
            "Nhắc bổ sung giấy tờ",
            {"id": "notify_admission_pack", "label": "Thông báo trúng tuyển + học phí"},
            {"id": "export_thanh_tra", "label": "Xuất hồ sơ Thanh tra"},
            {"id": "export_htqt", "label": "Xuất hồ sơ HTQT"},
            "Xuất Excel",
        ],
        "primary_action": None,
    },
    "admissions.mail": {
        "title": "Mẫu email tuyển sinh",
        "desc": "Tạo và sửa mẫu thư, rồi gửi cho ứng viên của chương trình theo loại thư đã chọn.",
        "endpoint": "ops_admissions_mail",
        "api": "/ops/email-templates",
        "api_params": {"catalog": "1"},
        "mode": "manage",
        "search": True,
        "columns": [
            ("program_code", "CT"),
            ("kind_label", "Loại mẫu"),
            ("subject", "Tiêu đề"),
        ],
        "row_buttons": [
            {"id": "edit_mail_template", "label": "Sửa mẫu"},
            {"id": "send_mail_template", "label": "Gửi email"},
        ],
        "actions": [],
        "primary_action": {"id": "edit_mail_template", "label": "Tạo / sửa mẫu"},
    },
    "admissions.pre_enroll": {
        "title": "Hồ sơ xét tuyển",
        "desc": "Hồ sơ tuyển sinh chưa trở thành học viên: cùng một hồ sơ cá nhân, có bước xác nhận người dự thi chính thức.",
        "endpoint": "ops_admissions_pre_enroll",
        "api": "/ops/candidate-pre-enroll",
        "mode": "manage",
        "search": True,
        "program_filter": True,
        "round_filter": True,
        "edit_path": "candidate-pre-enroll",
        "columns": [
            ("candidate_code", "Mã ứng viên"),
            ("full_name", "Tên ứng viên"),
            ("examinee_status_label", "Tư cách dự thi"),
            ("person_stage_label", "Vai trò"),
            ("admit_decision", "Quyết định trúng tuyển"),
            ("program_code", "CT"),
        ],
        "row_buttons": [
            {"id": "open_person_dossier", "label": "Hồ sơ xuyên suốt"},
            {"id": "confirm_examinee", "label": "Xác nhận dự thi"},
            {"id": "view_application", "label": "Xem chi tiết"},
            {"id": "manage_app_docs", "label": "Tài liệu hồ sơ"},
        ],
        "actions": [{"id": "print_page", "label": "In danh sách"}, "Xuất Excel"],
        "primary_action": None,
    },
    "admissions.enrolled_files": {
        "title": "Hồ sơ đã nhập học",
        "desc": "Hồ sơ theo học sau quyết định trúng tuyển có hiệu lực. Mã học viên theo chương trình, cùng mã ứng viên. Có thể đang chờ xếp lớp.",
        "endpoint": "ops_admissions_enrolled_files",
        "api": "/ops/candidate-enrolled",
        "mode": "manage",
        "search": True,
        "program_filter": True,
        "round_filter": True,
        "edit_path": "candidate-enrolled",
        "columns": [
            ("student_code", "Mã học viên"),
            ("candidate_code", "Mã ứng viên"),
            ("full_name", "Họ tên"),
            ("academic_status_label", "TT theo học"),
            ("enrolled_at", "Ngày vào học"),
            ("program_code", "Chương trình học"),
        ],
        "row_buttons": [
            {"id": "open_person_dossier", "label": "Hồ sơ xuyên suốt"},
            {"id": "view_application", "label": "Xem chi tiết"},
            {"id": "manage_app_docs", "label": "Tài liệu hồ sơ"},
        ],
        "actions": [{"id": "print_page", "label": "In danh sách"}, "Xuất Excel"],
        "primary_action": None,
    },
    "accounting.fees": {
        "title": "Phí ghi danh",
        "desc": "Theo dõi nộp phí sau khi đỗ. Điều phối chỉ xem. Kế toán xác nhận đã thu.",
        "endpoint": "ops_accounting_fees",
        "api": "/ops/fees",
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "columns": [
            ("cfvg_app_no", "Mã hồ sơ"),
            ("full_name", "Họ tên"),
            ("program_code", "CT"),
            ("amount", "Số tiền"),
            ("status", "TT phí"),
            ("application_status", "TT hồ sơ"),
            ("paid_at", "Ngày nộp"),
            ("proof_note", "Minh chứng"),
        ],
        "fee_actions": True,
        "actions": [
            {"id": "print_page", "label": "In danh sách"},
            {"id": "export_fees", "label": "Xuất Excel phí"},
        ],
        "primary_action": None,
    },
    "accounting.charges": {
        "title": "Công nợ / học phí",
        "desc": "Chọn khóa học trước. Trong khóa, lọc năm thứ nhất hoặc năm thứ hai để xem đúng đợt thu, không liệt kê mọi khóa cùng lúc.",
        "require_cohort": True,
        "study_year_filter": True,
        "endpoint": "ops_accounting_charges",
        "api": "/ops/treasury/charges",
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "treasury_kpis": True,
        "columns": [
            ("full_name", "Họ tên"),
            ("student_code", "Mã HV"),
            ("program_code", "CT"),
            ("currency", "Tiền tệ"),
            ("fee_type", "Loại"),
            ("title", "Khoản thu"),
            ("amount_due", "Phải thu"),
            ("waiver_pct", "% miễn"),
            ("actual_due", "Thực tế cần đóng"),
            ("amount_adjust", "Điều chỉnh"),
            ("amount_paid", "Đã thu"),
            ("remaining", "Còn lại"),
            ("due_date", "Hạn"),
            ("days_overdue", "Ngày quá hạn"),
            ("status", "TT"),
            ("scholarship_type", "Học bổng"),
        ],
        "charge_actions": True,
        "primary_action": None,
        "row_buttons": [
            {"id": "view_record", "label": "Xem chi tiết"},
        ],
    },
    "accounting.benefits": {
        "title": "Học bổng, giảm phí, hỗ trợ",
        "desc": "Một hồ sơ cho cả ba loại. Giảm nghĩa vụ hoặc chi ra tài khoản, không ghi cùng một khoản theo cả hai cách. Người lập không tự duyệt.",
        "endpoint": "ops_accounting_benefits",
        "api": "/ops/treasury/benefits",
        "mode": "manage",
        "search": True,
        "columns": [
            ("full_name", "Họ tên"),
            ("student_code", "Mã HV"),
            ("program_code", "CT"),
            ("intake", "Khóa"),
            ("benefit_type", "Loại"),
            ("effect", "Cách ghi"),
            ("amount", "Số tiền"),
            ("currency", "Tiền tệ"),
            ("status", "TT"),
            ("beneficiary_account", "Số TK"),
            ("beneficiary_bank", "Ngân hàng"),
            ("decision_note", "Quyết định"),
        ],
        "primary_action": {"id": "create_benefit", "label": "Lập đề nghị"},
        "row_buttons": [
            {"id": "approve_benefit", "label": "Duyệt"},
            {"id": "apply_benefit", "label": "Giảm nghĩa vụ"},
            {"id": "disburse_benefit", "label": "Chi tiền"},
        ],
    },
    "accounting.refunds": {
        "title": "Hoàn phí",
        "desc": "Đã duyệt chưa phải đã chi. Hoàn thu nhầm thì đảo giao dịch và giữ nghĩa vụ. Rút học thì giảm nghĩa vụ rồi mới chi.",
        "endpoint": "ops_accounting_refunds",
        "api": "/ops/treasury/refunds",
        "mode": "manage",
        "search": True,
        "columns": [
            ("full_name", "Họ tên"),
            ("student_code", "Mã HV"),
            ("program_code", "CT"),
            ("reason_code", "Lý do"),
            ("amount_requested", "Đề nghị"),
            ("amount_approved", "Đã duyệt"),
            ("amount_disbursed", "Đã chi"),
            ("reduce_obligation", "Nghĩa vụ"),
            ("status", "TT"),
            ("payee_account", "Số TK"),
            ("payee_bank", "Ngân hàng"),
        ],
        "primary_action": {"id": "create_refund", "label": "Lập hồ sơ hoàn"},
        "row_buttons": [
            {"id": "approve_refund", "label": "Duyệt"},
            {"id": "disburse_refund", "label": "Chi hoàn"},
        ],
    },
    "accounting.billing_profiles": {
        "title": "Thông tin xuất hóa đơn",
        "desc": "Cá nhân hoặc doanh nghiệp. Mã số thuế và CCCD giữ số 0 ở đầu. Sửa thông tin tạo bản mới, không đổi bản đã lưu.",
        "endpoint": "ops_accounting_billing_profiles",
        "api": "/ops/treasury/billing-profiles",
        "mode": "manage",
        "search": True,
        "columns": [
            ("party_type", "Đối tượng"),
            ("full_name", "Họ tên"),
            ("intake", "Khóa"),
            ("company_name", "Đơn vị"),
            ("tax_code", "MST"),
            ("address", "Địa chỉ"),
            ("cccd", "CCCD"),
            ("phone", "Điện thoại"),
            ("email", "Email"),
            ("program_code", "CT"),
        ],
        "primary_action": {"id": "create_billing_profile", "label": "Thêm thông tin"},
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "accounting.candidate_files": {
        "title": "Nghĩa vụ phí thí sinh",
        "desc": (
            "Hồ sơ đăng ký có nghĩa vụ phí: khoản thu, miễn % hoặc số tiền, phiếu thu, cam kết dự thi. "
            "Không gồm tài liệu đợt (dùng menu Tìm kiếm tài liệu)."
        ),
        "endpoint": "ops_accounting_candidate_files",
        "api": "/ops/treasury/candidate-files",
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "treasury_kpis": True,
        "charge_actions": True,
        "columns": [
            ("cfvg_app_no", "Mã hồ sơ"),
            ("full_name", "Họ tên"),
            ("email", "Email"),
            ("phone", "Điện thoại"),
            ("program_code", "CT"),
            ("title", "Khoản thu"),
            ("amount_due", "Phải thu"),
            ("waiver_pct", "% miễn"),
            ("waived_amount", "Số miễn"),
            ("actual_due", "Thực tế cần đóng"),
            ("amount_paid", "Đã nộp"),
            ("remaining", "Còn nợ"),
            ("due_date", "Hạn nộp"),
            ("exam_eligible_flag", "Đủ ĐK thi"),
            ("status", "TT thanh toán"),
        ],
        "actions": [
            {"id": "open_pre_enroll", "label": "Hồ sơ xét tuyển"},
            {"id": "open_enrolled", "label": "Hồ sơ đã nhập học"},
            {"id": "print_page", "label": "In danh sách"},
            "Xuất Excel",
        ],
        "primary_action": None,
        "row_buttons": [
            {"id": "view_application", "label": "Xem chi tiết"},
            {"id": "edit_candidate_file", "label": "Cập nhật"},
            {"id": "manage_app_docs", "label": "Tài liệu hồ sơ"},
        ],
        "workflow": "Xem/cập nhật · khoản thu catalog · miễn 10/50/100% · thực tế cần đóng",
    },
    "accounting.tuition_tracker": {
        "title": "Theo dõi học phí",
        "desc": "Chọn khóa, rồi năm học, để theo dõi đã nộp, một phần, sắp hạn và quá hạn của khóa đó.",
        "require_cohort": True,
        "study_year_filter": True,
        "endpoint": "ops_accounting_tuition_tracker",
        "api": "/ops/treasury/tuition-tracker",
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "treasury_kpis": True,
        "columns": [
            ("full_name", "Họ tên"),
            ("student_code", "Mã HV"),
            ("program_code", "CT"),
            ("amount_due", "Phải thu"),
            ("amount_paid", "Đã thu"),
            ("remaining", "Còn lại"),
            ("unpaid_count", "Khoản chưa nộp"),
            ("overdue_count", "Khoản quá hạn"),
            ("next_due_date", "Hạn gần nhất"),
            ("status", "TT nộp phí"),
            ("scholarship_type", "Học bổng"),
        ],
        "actions": [
            {"id": "print_page", "label": "In danh sách"},
            "Xuất Excel",
        ],
        "primary_action": None,
        "row_buttons": [
            {"id": "open_student_charges", "label": "Xem công nợ"},
        ],
    },
    "accounting.fee_alerts": {
        "title": "Cảnh báo học phí",
        "desc": "Cảnh báo tự động khi sắp hạn, quá hạn, hoặc học viên có nhiều khoản thanh toán trễ. Kế toán chỉnh ngưỡng tiêu chí.",
        "endpoint": "ops_accounting_fee_alerts",
        "api": "/ops/treasury/alerts",
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "is_fee_alerts": True,
        "treasury_kpis": True,
        "columns": [
            ("severity", "Mức"),
            ("title", "Tiêu chí"),
            ("full_name", "Họ tên"),
            ("student_code", "Mã HV"),
            ("program_code", "CT"),
            ("charge_title", "Khoản thu"),
            ("due_date", "Hạn nộp"),
            ("remaining", "Còn lại"),
            ("days_overdue", "Ngày quá hạn"),
            ("message", "Nội dung"),
        ],
        "actions": [
            {"id": "print_page", "label": "In danh sách"},
            "Xuất Excel",
        ],
        "primary_action": None,
        "row_buttons": [
            {"id": "open_student_charges", "label": "Xem công nợ"},
        ],
    },
    "accounting.fee_types": {
        "title": "Danh mục khoản thu",
        "desc": "Khai báo mã khoản thu và mức mặc định áp dụng chung cả đợt (gồm lệ phí thi đầu vào). Khi thu tiền chọn mã, hệ thống tự điền tên và số tiền.",
        "endpoint": "ops_accounting_fee_types",
        "api": "/ops/treasury/fee-types",
        "mode": "manage",
        "search": True,
        "columns": [
            ("code", "Mã"),
            ("label", "Tên khoản thu"),
            ("collection_kind", "Tính chất"),
            ("default_amount", "Mức mặc định"),
            ("sort_order", "Thứ tự"),
            ("status", "Trạng thái"),
        ],
        "actions": [{"id": "print_page", "label": "In danh sách"}],
        "primary_action": {"id": "create_fee_type", "label": "Thêm khoản thu"},
        "row_buttons": [
            {"id": "edit_fee_type", "label": "Cập nhật mức"},
        ],
    },
    "accounting.collection_report": {
        "title": "Báo cáo thu tiền",
        "desc": (
            "Tách phải thu ban đầu / miễn giảm / phải thu sau miễn / thực thu / còn phải thu. "
            "Miễn không cộng vào thực thu."
        ),
        "endpoint": "ops_accounting_collection_report",
        "api": "/ops/treasury/collection-report",
        "mode": "view",
        "search": True,
        "status_filter": True,
        "is_collection_report": True,
        "treasury_kpis": True,
        "columns": [
            ("full_name", "Họ tên"),
            ("cfvg_app_no", "Mã hồ sơ"),
            ("program_code", "CT"),
            ("title", "Khoản thu"),
            ("collection_kind", "Tính chất"),
            ("amount_due", "Phải thu ban đầu"),
            ("waiver_pct", "% miễn"),
            ("waived_amount", "Miễn giảm"),
            ("actual_due", "Phải thu sau miễn"),
            ("amount_paid", "Thực thu"),
            ("remaining", "Còn phải thu"),
            ("due_date", "Hạn nộp"),
            ("status", "TT"),
        ],
        "actions": [
            {"id": "print_page", "label": "In báo cáo"},
            "Xuất Excel",
        ],
        "primary_action": None,
        "workflow": "Phải thu ban đầu · miễn · phải thu sau miễn · thực thu · còn phải thu",
    },
    "accounting.receipts": {
        "title": "Phiếu thu",
        "desc": "Lập phiếu thu: tìm tên/CCCD, chọn khoản, số tiền, ngày, hình thức, mã giao dịch. Nhiều phiếu / một nghĩa vụ.",
        "endpoint": "ops_accounting_receipts",
        "api": "/ops/treasury/receipts",
        "mode": "manage",
        "search": True,
        "columns": [
            ("id", "Số phiếu"),
            ("full_name", "Họ tên"),
            ("cccd", "CCCD"),
            ("cfvg_app_no", "Mã hồ sơ"),
            ("program_code", "CT"),
            ("title", "Khoản thu"),
            ("amount", "Số tiền"),
            ("paid_at", "Ngày"),
            ("method_code", "Hình thức"),
            ("txn_code", "Mã GD"),
            ("buyer_name", "Người nhận HĐ"),
            ("tax_code", "MST"),
            ("email_status", "Email"),
        ],
        "actions": [{"id": "print_page", "label": "In"}, "Xuất Excel"],
        "primary_action": {"id": "create_receipt", "label": "Lập phiếu thu"},
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
        "allow_create": True,
    },
    "accounting.payment_methods": {
        "title": "Hình thức nộp tiền",
        "desc": "Danh mục chuyển khoản / thẻ / tiền mặt / khác.",
        "endpoint": "ops_accounting_payment_methods",
        "api": "/ops/treasury/payment-methods",
        "mode": "manage",
        "search": True,
        "columns": [
            ("code", "Mã"),
            ("label", "Tên"),
            ("label_en", "EN"),
            ("sort_order", "Thứ tự"),
            ("status", "TT"),
        ],
        "primary_action": {"id": "create_payment_method", "label": "Thêm hình thức"},
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "accounting.intake_plans": {
        "title": "Kế hoạch thu theo khóa",
        "desc": "Chọn khóa trước khi xem các đợt đóng. Mỗi đợt gắn năm thứ nhất hoặc năm thứ hai và mức học phí của chương trình đó.",
        "require_cohort": True,
        "study_year_filter": True,
        "endpoint": "ops_accounting_intake_plans",
        "api": "/ops/treasury/intake-plans",
        "mode": "manage",
        "search": True,
        "columns": [
            ("program_code", "CT"),
            ("intake_code", "Khóa"),
            ("study_year", "Năm học"),
            ("fee_type", "Loại"),
            ("installment_no", "Đợt"),
            ("title", "Tên đợt"),
            ("amount_due", "Số tiền"),
            ("due_date", "Hạn"),
            ("due_offset_days", "Số ngày"),
            ("status", "TT"),
        ],
        "primary_action": {"id": "create_intake_plan", "label": "Thêm đợt thu"},
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "accounting.round_fee_settings": {
        "title": "Khoản thu theo đợt",
        "desc": "Chọn năm để thấy các đợt của năm đó. Danh sách khoản đóng chỉ hiện sau khi chọn đúng một đợt.",
        "year_then_round": True,
        "round_filter": True,
        "endpoint": "ops_accounting_round_fees",
        "api": "/ops/treasury/round-fee-settings",
        "mode": "manage",
        "search": True,
        "columns": [
            ("round_code", "Đợt"),
            ("round_name", "Tên đợt"),
            ("fee_type", "Mã khoản"),
            ("unit_price", "Đơn giá"),
            ("default_times", "Số lần"),
            ("due_date", "Hạn nộp"),
        ],
        "primary_action": {"id": "create_round_fee", "label": "Thêm cấu hình"},
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "accounting.payment_imports": {
        "title": "Import thu tiền",
        "desc": "Đối soát sao kê: khớp, thiếu, thừa, trùng hoặc chưa rõ người nộp. Import vẫn ghi phiếu thu khi khớp được nghĩa vụ.",
        "endpoint": "ops_accounting_payment_imports",
        "api": "/ops/treasury/payment-imports",
        "mode": "manage",
        "search": True,
        "import_bulk": True,
        "columns": [
            ("id", "Dòng"),
            ("full_name", "Người nộp"),
            ("cccd", "CCCD"),
            ("amount", "Số tiền"),
            ("txn_code", "Mã GD"),
            ("paid_at", "Ngày"),
            ("fee_type", "Khoản"),
            ("match_status", "Đối soát"),
            ("note", "Ghi chú"),
        ],
        "actions": [{"id": "import_bulk", "label": "Import Excel"}, "Xuất Excel"],
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "accounting.receipt_emails": {
        "title": "Email cảm ơn",
        "desc": "Gửi email sau phiếu thu · hàng loạt theo đợt · lưu trạng thái gửi.",
        "endpoint": "ops_accounting_receipt_emails",
        "api": "/ops/treasury/receipt-emails",
        "mode": "manage",
        "search": True,
        "columns": [
            ("id", "Phiếu"),
            ("full_name", "Họ tên"),
            ("amount", "Số tiền"),
            ("paid_at", "Ngày"),
            ("email_status", "Trạng thái gửi"),
        ],
        "actions": [{"id": "bulk_thankyou", "label": "Gửi hàng loạt theo đợt"}, "Xuất Excel"],
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "accounting.my_fees": {
        "title": "Nghĩa vụ phí của tôi",
        "desc": "Học viên xem phải nộp / đã nộp / còn nợ. Gửi minh chứng không tự xác nhận đã thu.",
        "endpoint": "ops_student_my_fees",
        "api": "/ops/student/me/charges",
        "mode": "view",
        "search": True,
        "columns": [
            ("title", "Khoản"),
            ("amount_due", "Phải thu"),
            ("amount_paid", "Đã nộp"),
            ("remaining", "Còn nợ"),
            ("due_date", "Hạn"),
            ("status", "TT"),
            ("student_proof_note", "Minh chứng HV"),
        ],
        "row_buttons": [
            {"id": "view_record", "label": "Xem chi tiết"},
            {"id": "send_fee_proof", "label": "Gửi minh chứng"},
        ],
    },
    "admissions.verification_queue": {
        "title": "Danh sách cần xác minh",
        "desc": "Khảo thí / Thanh tra xem minh chứng, lọc đợt/ngành, xuất. Không sửa hồ sơ.",
        "endpoint": "ops_admissions_verification",
        "api": "/ops/verification-queue",
        "mode": "view",
        "search": True,
        "columns": [
            ("cfvg_app_no", "Mã hồ sơ"),
            ("full_name", "Họ tên"),
            ("cccd", "CCCD"),
            ("program_code", "CT"),
            ("round_code", "Đợt"),
            ("needs_verification", "Cần xác minh"),
            ("inspect_khao_thi", "Khảo thí"),
            ("inspect_thanh_tra", "Thanh tra"),
            ("english_verified", "CC NN"),
            ("degree_verified", "Bằng"),
            ("status", "TT"),
        ],
        "actions": [{"id": "print_page", "label": "In"}, "Xuất Excel"],
        "row_buttons": [{"id": "view_application", "label": "Xem chi tiết"}],
    },
    "admissions.student_numbering": {
        "title": "Cấp mã học viên",
        "desc": "Cấp mã học viên trên hồ sơ theo học khi quyết định đã có hiệu lực (official). Hồ sơ mới đỗ vẫn hiện để theo dõi nhưng chưa được cấp mã. Không tạo thêm một người.",
        "endpoint": "ops_admissions_student_numbering",
        "api": "/ops/student-numbering",
        "mode": "manage",
        "search": True,
        "columns": [
            ("cfvg_app_no", "Mã UV"),
            ("full_name", "Họ tên"),
            ("program_code", "CT"),
            ("student_code", "Mã HV"),
            ("enrolled_at", "Ngày nhập học"),
            ("status", "TT"),
            ("board_decision", "HĐ"),
        ],
        "actions": [{"id": "assign_student_codes", "label": "Cấp mã (xem trước)"}, "Xuất Excel"],
        "row_buttons": [
            {"id": "view_application", "label": "Xem chi tiết"},
        ],
    },
    "teaching.review_batches": {
        "title": "Đợt xét kết quả",
        "desc": "Chọn học viên, chốt ảnh chụp điểm, GPA trọng số tín chỉ. Bảng điểm lớp–môn giữ nguyên.",
        "endpoint": "ops_teaching_review_batches",
        "api": "/ops/review-batches",
        "mode": "manage",
        "search": True,
        "columns": [
            ("title", "Tiêu đề"),
            ("program_code", "CT"),
            ("student_count", "Số HV"),
            ("gpa_method", "Cách GPA"),
            ("locked_at", "Chốt lúc"),
            ("locked_by", "Người chốt"),
            ("status", "TT"),
        ],
        "primary_action": {"id": "create_review_batch", "label": "Tạo đợt xét"},
        "row_buttons": [
            {"id": "view_record", "label": "Xem chi tiết"},
            {"id": "lock_review_batch", "label": "Chốt đợt"},
        ],
    },
    "intl.partners": {
        "title": "Trường đối tác",
        "desc": "Danh mục trường, mã viết tắt, import đối chiếu.",
        "endpoint": "ops_intl_partners",
        "api": "/ops/intl/partners",
        "mode": "manage",
        "search": True,
        "import_bulk": True,
        "columns": [
            ("code", "Mã"),
            ("name", "Tên trường"),
            ("country", "Quốc gia"),
            ("status", "TT"),
        ],
        "primary_action": {"id": "create_partner", "label": "Thêm trường"},
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "intl.cooperation_programs": {
        "title": "Chương trình hợp tác",
        "desc": "Liên kết đối tác Incoming/Outgoing.",
        "endpoint": "ops_intl_coop",
        "api": "/ops/intl/coop-programs",
        "mode": "manage",
        "search": True,
        "columns": [
            ("name", "Tên CT"),
            ("partner_code", "Mã trường"),
            ("partner_name", "Trường"),
            ("direction", "Chiều"),
            ("status", "TT"),
        ],
        "primary_action": {"id": "create_coop", "label": "Thêm CT hợp tác"},
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "intl.workflow_steps": {
        "title": "Bước Incoming / Outgoing",
        "desc": "Danh mục bước + lịch sử minh chứng theo HV.",
        "endpoint": "ops_intl_steps",
        "api": "/ops/intl/workflow-steps",
        "mode": "manage",
        "search": True,
        "columns": [
            ("direction", "Chiều"),
            ("code", "Mã bước"),
            ("label", "Tên bước"),
            ("sort_order", "Thứ tự"),
        ],
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "intl.exchange_reports": {
        "title": "Báo cáo trao đổi",
        "desc": "Báo cáo theo trường đối tác / thời gian.",
        "endpoint": "ops_intl_reports",
        "api": "/ops/intl/exchange-reports",
        "mode": "view",
        "search": True,
        "columns": [
            ("partner_code", "Mã"),
            ("partner_name", "Trường"),
            ("country", "Quốc gia"),
            ("program_count", "Số CT hợp tác"),
        ],
        "actions": [{"id": "print_page", "label": "In"}, "Xuất Excel"],
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "admin.audit_logs": {
        "title": "Nhật ký thao tác",
        "desc": "Chỉ xem/xuất: điểm, phiếu thu, miễn, trạng thái, cấp mã, import.",
        "endpoint": "ops_admin_audit_logs",
        "api": "/ops/audit-logs",
        "mode": "view",
        "search": True,
        "columns": [
            ("created_at", "Thời điểm"),
            ("actor", "Người"),
            ("action", "Thao tác"),
            ("entity", "Đối tượng"),
            ("entity_id", "ID"),
            ("detail", "Chi tiết"),
        ],
        "actions": [{"id": "print_page", "label": "In"}, "Xuất Excel"],
        "row_buttons": [{"id": "view_record", "label": "Xem chi tiết"}],
    },
    "students.manage": {
        "title": "Danh sách học viên",
        "desc": "Hồ sơ HV: Tài chính (học bổng) + Học tập (enrolled/deferred/withdrawn/graduated).",
        "endpoint": "ops_students_manage",
        "api": "/ops/students",
        "mode": "manage",
        "search": True,
        "assign_class": True,
        "cohort_filter": True,
        "mobility_filter": True,
        "columns": [
            ("student_code", "Mã HV"),
            ("full_name", "Họ tên"),
            ("cohort_label", "Khóa"),
            ("mobility_group", "Incoming/Outgoing"),
            ("intake_session", "Session"),
            ("program_code", "CT"),
            ("class_name", "Lớp"),
            ("lifecycle_status", "TT học tập"),
            ("scholarship_type", "Học bổng"),
            ("company", "Đơn vị"),
            ("job_title", "Vị trí"),
            ("partner_enrollment", "Partner/IAE"),
            ("email", "Email"),
            ("person_stage_label", "Vai trò"),
            ("candidate_code", "Mã ứng viên"),
        ],
        "actions": ["Export exam eligibility", "Xuất Excel"],
        "primary_action": None,
        "row_buttons": [
            {"id": "open_person_dossier", "label": "Hồ sơ xuyên suốt"},
            {"id": "view_student", "label": "Xem chi tiết"},
            {"id": "edit_student_lifecycle", "label": "Cập nhật"},
            {"id": "print_student_progress", "label": "In tiến độ"},
        ],
    },
    "students.academic": {
        "title": "Kết quả & tiến độ học tập",
        "desc": "Điểm trung bình cá nhân đặt cạnh điểm trung bình của lớp. Chọn học kỳ để xuất bảng điểm của kỳ đó. Xếp hạng dùng 5 môn kỳ 1 nếu đã chọn căn cứ học bổng.",
        "semester_filter": True,
        "endpoint": "ops_students_academic",
        "api": "/ops/academic-records",
        "mode": "view",
        "search": True,
        "columns": [
            ("candidate_code", "Mã ứng viên"),
            ("student_code", "Mã HV"),
            ("full_name", "Họ tên"),
            ("person_stage_label", "Vai trò"),
            ("program_code", "CT"),
            ("class_name", "Lớp"),
            ("application_status", "TT hồ sơ"),
            ("board_decision", "Quyết định"),
            ("exam_fee_status", "Lệ phí thi"),
            ("exam_roster_status", "DS hội đồng"),
            ("courses_done", "Đã học"),
            ("courses_current", "Đang học"),
            ("courses_upcoming", "Sắp học"),
            ("gpa_to_date", "Điểm TB cá nhân"),
            ("class_gpa", "Điểm TB lớp"),
            ("scholarship_gpa", "Điểm xét HB"),
            ("class_rank", "Xếp hạng"),
            ("progress_note", "Tiến độ"),
        ],
        "actions": [
            {"id": "print_page", "label": "In danh sách"},
            "Xuất Excel",
            {"id": "export_class_transcript", "label": "Xuất bảng điểm lớp"},
        ],
        "row_buttons": [
            {"id": "print_transcript", "label": "In bảng chính thức"},
            {"id": "print_progress", "label": "In bảng theo dõi"},
        ],
        "primary_action": None,
    },
    "teaching.schedule": {
        "title": "Lịch học",
        "desc": "Lớp · môn · buổi · phòng · giảng viên · ngày học. Lọc theo ngày, môn và chương. Nhập phòng từ Excel.",
        "endpoint": "ops_teaching_schedule",
        "api": "/ops/teaching-schedule",
        "mode": "manage",
        "search": True,
        "schedule_filters": True,
        "edit_path": "attendance-sessions",
        "columns": [
            ("session_date", "Ngày học"),
            ("class_name", "Lớp"),
            ("program_code", "CT"),
            ("course_code", "Mã môn"),
            ("course_name", "Môn học"),
            ("chapter", "Chương"),
            ("session_label", "Buổi"),
            ("room", "Phòng"),
            ("lecturer", "Giảng viên"),
            ("expert", "Chuyên gia"),
            ("status", "TT / đổi lịch"),
        ],
        "actions": [{"id": "import_schedule", "label": "Nhập phòng từ Excel"}],
        "primary_action": None,
    },
    "accounting.official_list": {
        "title": "Nhập học chính thức",
        "desc": "Sau khi đã thu phí ghi danh: Kế toán chốt chính thức, hồ sơ theo học ở trạng thái Chờ xếp lớp. Tuyển sinh gửi Khảo thí. Điều phối cấp mã và xếp lớp.",
        "endpoint": "ops_accounting_official",
        "api": "/ops/applications",
        "api_params": {"status": "official"},
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "columns": [
            ("cfvg_app_no", "Mã hồ sơ"),
            ("full_name", "Họ tên"),
            ("program_code", "CT"),
            ("email", "Email"),
            ("english_cert", "Chứng chỉ TA"),
            ("degree_verified", "Văn bằng"),
            ("english_verified", "TA xác nhận"),
            ("neu_packet_ready", "Gói NEU"),
            ("status", "Trạng thái"),
            ("notes", "Ghi chú"),
        ],
        "row_buttons": [
            {"id": "view_application", "label": "Xem chi tiết"},
            {"id": "manage_app_docs", "label": "Tài liệu hồ sơ"},
        ],
        "actions": [
            {"id": "convert_official_bulk", "label": "Xếp lớp hàng loạt"},
            {"id": "create_class", "label": "Tạo lớp"},
            "Xuất Excel",
            "Gửi khảo thí",
            "Xuất roster Canvas",
        ],
        "primary_action": None,
        "canvas_export_roster": True,
    },
    "programs.structure": {
        "title": "Phiên bản chương trình",
        "desc": "Mỗi khóa một phiên bản: số khóa, năm bắt đầu và năm kết thúc. Ví dụ Khóa 21 – 2026–2028.",
        "cohort_filter": True,
        "endpoint": "ops_programs",
        "api": "/ops/program-versions",
        "mode": "manage",
        "search": True,
        "program_filter": True,
        "version_code_filter": True,
        "columns": [
            ("program_code", "CT"),
            ("cohort_label", "Khóa"),
            ("version_code", "Mã phiên bản"),
            ("name", "Tên"),
            ("course_count", "Số môn học"),
            ("description", "Mô tả"),
            ("is_active", "Active"),
        ],
        "actions": [],
        "primary_action": None,
        "row_buttons": [
            {"id": "view_program", "label": "Xem chi tiết"},
            {"id": "view_courses", "label": "Môn học / học phần"},
            {"id": "copy_version", "label": "Copy / chuyển HP"},
        ],
    },
    "programs.courses": {
        "title": "Môn học",
        "desc": "Danh sách môn học theo khóa. Mỗi môn có lịch học, syllabus và chuẩn đầu ra.",
        "cohort_filter": True,
        "endpoint": "ops_courses",
        "api": "/ops/courses",
        "mode": "manage",
        "search": True,
        "program_filter": True,
        "version_code_filter": True,
        "course_detail_link": True,
        "columns": [
            ("program_code", "CT"),
            ("cohort_label", "Khóa"),
            ("version_code", "Phiên bản"),
            ("code", "Mã môn"),
            ("name", "Tên môn học"),
            ("semester", "HK"),
            ("session_count", "Buổi"),
            ("released_count", "TL đã release"),
            ("syllabus_status", "Syllabus"),
        ],
        "actions": [],
        "primary_action": None,
    },
    "classes.manage": {
        "title": "Danh sách lớp",
        "desc": "Danh sách lớp theo khóa. Chọn khóa để xem lớp tương ứng, rồi đưa học viên vào lớp từ danh sách học viên.",
        "cohort_filter": True,
        "endpoint": "ops_classes",
        "api": "/ops/classes",
        "mode": "manage",
        "search": True,
        "columns": [
            ("name", "Lớp"),
            ("program_code", "CT"),
            ("version_code", "Phiên bản"),
            ("cohort_label", "Khóa"),
            ("student_count", "Sĩ số"),
            ("status", "Trạng thái"),
        ],
        "actions": [],
        "primary_action": "Tạo lớp",
        "row_buttons": [
            {"id": "view_students", "label": "Xem SV"},
            {"id": "enroll_official", "label": "Enroll official"},
            {"id": "email_class", "label": "Email lớp"},
        ],
        "allow_delete": True,
        "delete_path": "classes",
        "canvas_row_export": True,
    },
    "teaching.faculty": {
        "title": "Giảng viên & Chuyên gia",
        "desc": "Hồ sơ GV: lịch sử dạy CFVG, HĐ/TT, trả điểm; vé/KS/BH → Trợ lý quốc tế.",
        "endpoint": "ops_faculty",
        "api": "/ops/faculty",
        "mode": "manage",
        "search": True,
        "columns": [
            ("full_name", "Họ tên"),
            ("role_type", "Vai trò"),
            ("degree", "Học vị"),
            ("nationality", "Quốc tịch"),
            ("organization", "Đơn vị"),
            ("specialty", "Chuyên môn"),
            ("contract_status", "Hợp đồng"),
            ("cfvg_payment_status", "TT CFVG"),
            ("grade_return_date", "Trả điểm"),
            ("teachable_courses", "Có thể dạy"),
        ],
        "actions": [],
        "primary_action": "Thêm giảng viên",
        "row_buttons": [
            {"id": "view_faculty", "label": "Xem chi tiết"},
            {"id": "edit_faculty", "label": "Sửa hồ sơ"},
        ],
        "allow_delete": True,
        "delete_path": "faculty",
    },
    "teaching.assign": {
        "title": "Lớp theo môn học",
        "desc": "Mỗi dòng là một lớp của một môn: sĩ số quản lý qua lớp, giảng viên và lịch học gắn với môn đó.",
        "cohort_filter": True,
        "endpoint": "ops_teaching_assign",
        "api": "/ops/teaching-assignments",
        "mode": "manage",
        "search": True,
        "edit_path": "teaching-assignments",
        "class_lessons_link": True,
        "columns": [
            ("class_name", "Lớp"),
            ("cohort_label", "Khóa"),
            ("program_code", "CT"),
            ("course_code", "Mã môn"),
            ("course_name", "Môn học"),
            ("lecturer", "GV LT"),
            ("expert", "Chuyên gia"),
            ("status", "Trạng thái"),
        ],
        "actions": [],
        "primary_action": {"id": "create_assignment", "label": "Thêm phân giảng"},
        "row_buttons": [
            {"id": "stamp_sessions", "label": "Ghi tên buổi"},
        ],
    },
    "teaching.lessons": {
        "title": "Bài giảng lớp–môn",
        "desc": "Upload slide pptx/docx/xlsx theo buổi; HV xem online; ghi thời gian học; thảo luận Câu hỏi/Góp ý/Bàn luận.",
        "endpoint": "ops_class_lessons_hub",
        "api": "/ops/class-lesson-offerings",
        "mode": "manage",
        "search": False,
        "class_lessons_hub": True,
        "columns": [
            ("program_code", "CT"),
            ("class_name", "Lớp"),
            ("course_code", "Mã HP"),
            ("course_name", "Học phần"),
            ("lecturer", "GV LT"),
            ("lesson_count", "Số bài"),
            ("published_count", "Đã publish"),
            ("status", "TT phân công"),
        ],
        "actions": [],
        "primary_action": None,
    },
    "teaching.materials": {
        "title": "Tài liệu môn học",
        "desc": "Upload tài liệu theo HP/buổi; release tới HV; tìm kiếm và tải file.",
        "endpoint": "ops_materials",
        "api": "/ops/materials",
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "materials_manage": True,
        "columns": [
            ("program_code", "CT"),
            ("course_code", "Mã HP"),
            ("course_name", "Học phần"),
            ("title", "Tài liệu"),
            ("material_type", "Loại"),
            ("session_no", "Buổi"),
            ("release_status", "Release"),
            ("has_file", "File"),
            ("uploaded_by", "Upload bởi"),
        ],
        "actions": [],
        "primary_action": None,
    },
    "student.library": {
        "title": "Học liệu & Syllabus",
        "desc": "Xem đề cương, nội dung từng buổi; tìm kiếm và tải tài liệu đã release.",
        "endpoint": "ops_student_library",
        "api": "/ops/student/library",
        "mode": "view",
        "search": True,
        "is_student_library": True,
        "columns": [],
        "actions": [],
        "primary_action": None,
    },
    "student.lessons": {
        "title": "Bài học và thảo luận",
        "desc": "Xem slide/docx/xlsx online; hệ thống ghi thời gian học; gửi Câu hỏi / Góp ý / Bàn luận.",
        "endpoint": "ops_student_lessons",
        "api": "/ops/student/lessons",
        "mode": "view",
        "search": True,
        "is_student_lessons": True,
        "columns": [
            ("class_name", "Lớp"),
            ("course_code", "Mã HP"),
            ("course_name", "Học phần"),
            ("lesson_no", "Buổi"),
            ("title", "Bài học"),
            ("lesson_type", "Loại"),
            ("released_files", "File"),
            ("comment_count", "Thảo luận"),
        ],
        "actions": [],
        "primary_action": None,
    },
    "teaching.groups": {
        "title": "Nhóm học tập",
        "desc": "Tạo nhóm theo môn; học viên nhìn thấy nhóm của mình.",
        "endpoint": "ops_groups",
        "api": "/ops/study-groups",
        "mode": "manage",
        "search": True,
        "columns": [
            ("name", "Nhóm"),
            ("class_name", "Lớp"),
            ("program_code", "CT"),
            ("member_names", "Thành viên"),
            ("status", "TT"),
        ],
        "actions": ["Quản lý nhóm"],
        "primary_action": "Tạo nhóm",
        "allow_delete": True,
        "delete_path": "study-groups",
    },
    "teaching.attendance": {
        "title": "Điểm danh",
        "desc": "Điểm danh 2 lần/buổi (thủ công + QR tại lớp); vắng >30% → không đủ ĐK thi.",
        "endpoint": "ops_attendance",
        "api": "/ops/attendance",
        "mode": "manage",
        "search": True,
        "attendance_session_link": True,
        "student_filter": True,
        "student_columns": [
            ("session_date", "Ngày"),
            ("course_name", "Môn học"),
            ("chapter", "Chương / buổi"),
            ("attendance_mark", "Tham gia"),
            ("attended_total", "Số buổi có mặt"),
            ("absent_total", "Số buổi vắng"),
        ],
        "columns": [
            ("session_date", "Ngày"),
            ("class_name", "Lớp"),
            ("program_code", "CT"),
            ("course_code", "HP"),
            ("session_label", "Buổi"),
            ("rounds_label", "Lần mở"),
            ("present_count", "Có mặt"),
            ("absent_count", "Vắng"),
        ],
        "actions": [
            "Export exam eligibility",
            "Notify ineligible students",
            "Xuất Excel",
            "Xuất ma trận điểm danh",
        ],
        "primary_action": None,
    },
    "teaching.assignments": {
        "title": "Bài tập",
        "desc": "Giao bài thực hành / trắc nghiệm theo lớp–môn; import mẫu; học viên làm online.",
        "endpoint": "ops_assignments",
        "api": "/ops/practice/teaching-assignments",
        "mode": "view",
        "search": True,
        "practice_homework_link": True,
        "mc_quiz_link": True,
        "columns": [
            ("class_name", "Lớp"),
            ("program_code", "CT"),
            ("course_code", "Mã HP"),
            ("course_name", "Học phần"),
            ("homework_count", "TH"),
            ("mc_quiz_count", "TN"),
            ("published_count", "TH mở"),
            ("mc_published_count", "TN mở"),
        ],
        "actions": [],
        "primary_action": None,
    },
    "student.practice": {
        "title": "Bài tập của tôi",
        "desc": "Làm bài thực hành / trắc nghiệm online đã được giảng viên mở.",
        "endpoint": "ops_student_practice",
        "api": "/ops/practice/student/homeworks",
        "mode": "view",
        "search": True,
        "is_student_practice": True,
        "columns": [
            ("kind_label", "Loại"),
            ("title", "Bài tập"),
            ("class_name", "Lớp"),
            ("course_code", "Mã HP"),
            ("course_name", "Học phần"),
            ("due_at", "Hạn"),
            ("submission_status", "Trạng thái"),
            ("score_label", "Điểm"),
        ],
        "actions": [],
        "primary_action": None,
    },
    "teaching.grades": {
        "title": "Quản lý điểm",
        "desc": "Bảng điểm tổng hợp theo lớp–môn; Group assignment (30%) + Final exam (70%); khóa điểm; xuất Grade Synthesis.",
        "endpoint": "ops_grades",
        "api": "/ops/classes",
        "mode": "manage",
        "search": False,
        "gradebook_link": True,
        "columns": [
            ("name", "Lớp"),
            ("program_code", "CT"),
            ("version_code", "Phiên bản"),
            ("student_count", "Sĩ số"),
        ],
        "actions": [
            "Xuất Grade Synthesis",
            {"id": "pick_scholarship_courses", "label": "Chọn 5 môn kỳ 1"},
        ],
        "primary_action": None,
    },
    "teaching.exams": {
        "title": "Thi cử",
        "desc": "Lịch thi; cảnh báo HV không đủ ĐK thi (vắng >30%); thi lại.",
        "endpoint": "ops_exams",
        "api": "/ops/exams-schedule",
        "mode": "manage",
        "search": True,
        "columns": [
            ("title", "Kỳ thi"),
            ("class_name", "Lớp"),
            ("program_code", "CT"),
            ("exam_date", "Ngày"),
            ("exam_type", "Loại"),
            ("room", "Phòng"),
            ("student_count", "Sĩ số"),
            ("ineligible_count", "Không đủ ĐK"),
            ("exam_eligibility_note", "Chuyên cần"),
            ("status", "Trạng thái"),
        ],
        "actions": ["Tạo đề thi", "Export exam eligibility"],
        "primary_action": "Lịch thi",
        "row_buttons": [
            {"id": "view_exams", "label": "Xem bài làm"},
        ],
        "allow_delete": True,
        "delete_path": "exams",
    },
    "teaching.evaluation": {
        "title": "Đánh giá môn học",
        "desc": "Form đánh giá sau thi; ≥60% gửi QL, ≥80% gửi GV trong 24h.",
        "endpoint": "ops_evaluation",
        "api": "/ops/evaluations",
        "mode": "manage",
        "search": True,
        "columns": [
            ("title", "Form"),
            ("name", "Lớp"),
            ("program_code", "CT"),
            ("response_pct", "% phản hồi"),
            ("ready_mgmt", "≥60% QL"),
            ("ready_faculty", "≥80% GV"),
            ("report_status", "Báo cáo"),
            ("status", "Trạng thái"),
        ],
        "actions": [],
        "primary_action": None,
        "row_buttons": [
            {"id": "view_evals", "label": "Xem kết quả"},
            {"id": "generic_edit", "label": "Cập nhật"},
            {"id": "send_eval_mgmt", "label": "Gửi QL"},
            {"id": "send_eval_faculty", "label": "Gửi GV"},
            {"id": "close_eval", "label": "Đóng form"},
        ],
        "allow_delete": True,
        "delete_path": "evaluations",
    },
    "teaching.thesis": {
        "title": "Luận văn / Đề án (CP)",
        "desc": "Theo dõi đề án: mã CP, GVHD, Turnitin/AI%, hội đồng, lịch bảo vệ, điểm /20.",
        "endpoint": "ops_thesis",
        "api": "/ops/thesis-records",
        "mode": "manage",
        "search": True,
        "thesis_detail_link": True,
        "columns": [
            ("cp_number", "Mã CP"),
            ("full_name", "Họ tên"),
            ("program_code", "CT"),
            ("title", "Tên đề án"),
            ("tutor", "GVHD"),
            ("payment_status", "Thanh toán"),
            ("turnitin_pct", "Turnitin"),
            ("defense_date", "Ngày BV"),
            ("room", "Phòng"),
            ("total_grade", "Điểm /20"),
            ("status", "TT"),
        ],
        "actions": [
            {"id": "print_page", "label": "In danh sách"},
            {"id": "export_thesis", "label": "Xuất Excel CĐTN"},
        ],
        "primary_action": None,
    },
    "alumni.members": {
        "title": "Cựu học viên",
        "desc": "Danh sách alumni theo khóa/CT/lớp; tìm kiếm; gửi email.",
        "endpoint": "ops_alumni",
        "api": "/ops/alumni",
        "mode": "manage",
        "search": True,
        "columns": [
            ("full_name", "Họ tên"),
            ("cccd", "CCCD"),
            ("program_code", "CT"),
            ("cohort", "Khóa"),
            ("class_name", "Lớp"),
            ("company", "Đơn vị"),
            ("activity_keywords", "Lĩnh vực"),
            ("email", "Email"),
            ("phone", "Điện thoại"),
            ("portal_login", "Cổng"),
        ],
        "actions": ["Gửi email", "Xuất DS"],
        "primary_action": "Thêm alumni",
        "row_buttons": [
            {"id": "view_alumni", "label": "Xem chi tiết"},
            {"id": "open_alumni_portal", "label": "Cấp tài khoản cổng"},
        ],
        "allow_delete": True,
        "delete_path": "alumni",
    },
    "alumni.events": {
        "title": "Sự kiện Alumni",
        "desc": "Tạo sự kiện, lọc đối tượng, gửi lời mời, in danh sách.",
        "endpoint": "ops_alumni_events",
        "api": "/ops/alumni-events",
        "mode": "manage",
        "search": True,
        "columns": [
            ("title", "Sự kiện"),
            ("event_date", "Ngày"),
            ("location", "Địa điểm"),
            ("program_filter", "Đối tượng"),
            ("invitee_count", "Đã mời"),
            ("status", "Trạng thái"),
            ("description", "Mô tả"),
        ],
        "actions": ["In DS"],
        "primary_action": "Tạo sự kiện",
        "row_buttons": [
            {"id": "view_event", "label": "Xem chi tiết"},
            {"id": "invite_event_members", "label": "Mời Alumni"},
        ],
        "allow_delete": True,
        "delete_path": "alumni-events",
    },
    "marcom.leads": {
        "title": "Người quan tâm",
        "desc": (
            "Marcom tiếp nhận người quan tâm trên hồ sơ cá nhân chung với tuyển sinh. "
            "Không bắt CCCD. Email hoặc điện thoại chỉ để phát hiện trùng, không tự gộp. "
            "Sau bàn giao, tuyển sinh xác nhận và phụ trách tư vấn."
        ),
        "endpoint": "ops_marcom_leads",
        "api": "/ops/marcom/leads",
        "mode": "manage",
        "search": True,
        "columns": [
            ("profile_code", "Hồ sơ"),
            ("full_name", "Họ tên"),
            ("phone", "Điện thoại"),
            ("email", "Email"),
            ("occupation", "Nghề nghiệp"),
            ("company", "Công ty"),
            ("program_interest", "CT quan tâm"),
            ("source", "Nguồn"),
            ("owner", "Phụ trách"),
            ("status", "Bàn giao"),
            ("application_status", "TT hồ sơ"),
        ],
        "actions": ["Xuất DS"],
        "primary_action": "Thêm người quan tâm",
        "row_buttons": [
            {"id": "hand_lead_ts", "label": "Bàn giao tuyển sinh"},
            {"id": "open_person_dossier", "label": "Hồ sơ chung"},
        ],
        "allow_delete": True,
        "delete_path": "marcom/leads",
        "workflow": (
            "Tiếp nhận → kiểm tra trùng → hồ sơ chung → bàn giao tuyển sinh → tuyển sinh xác nhận"
        ),
    },
    "marcom.campaigns": {
        "title": "Chiến dịch và ngân sách",
        "desc": (
            "Lập kế hoạch quảng bá và đề xuất ngân sách. Kế toán duyệt, sau đó Ban Giám đốc duyệt, "
            "rồi mới triển khai. Chi phí thực tế là khoản Kế toán đã xác nhận, không phải số Marcom tự nhập."
        ),
        "endpoint": "ops_marcom_campaigns",
        "api": "/ops/marcom/campaigns",
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "columns": [
            ("title", "Chiến dịch"),
            ("owner", "Phụ trách"),
            ("period_start", "Từ"),
            ("period_end", "Đến"),
            ("channel", "Kênh"),
            ("program_codes", "CT"),
            ("budget_planned", "NS đề xuất"),
            ("budget_approved", "NS được duyệt"),
            ("budget_actual", "Chi phí đã xác nhận"),
            ("status", "TT"),
            ("activity_count", "Hoạt động"),
            ("kpi_plan", "KPI"),
        ],
        "actions": ["Xuất báo cáo"],
        "primary_action": "Thêm chiến dịch",
        "allow_delete": True,
        "delete_path": "marcom/campaigns",
        "workflow": "Lập kế hoạch → Kế toán duyệt → BGD duyệt → triển khai → đánh giá → đối soát → kết thúc",
    },
    "marcom.events": {
        "title": "Sự kiện",
        "desc": "Một chức năng sự kiện cho tuyển sinh, workshop, webinar, hội thảo, gặp khách hàng và Alumni. Triển khai sau khi Kế toán và Ban Giám đốc duyệt ngân sách. Khách mời không mặc định là ứng viên.",
        "endpoint": "ops_marcom_events",
        "api": "/ops/marcom/events",
        "mode": "manage",
        "search": True,
        "event_type_filter": True,
        "status_filter": True,
        "workflow": (
            "Trước: Marcom kế hoạch TT + TS mời/chăm sóc → "
            "Trong: TS tư vấn + đồng vận hành → "
            "Sau: follow-up + cập nhật mức quan tâm / xuất file"
        ),
        "columns": [
            ("title", "Sự kiện"),
            ("event_type", "Loại"),
            ("event_date", "Ngày"),
            ("location", "Địa điểm"),
            ("program_codes", "CT"),
            ("phase_label", "Giai đoạn"),
            ("status", "TT"),
            ("budget_status", "Ngân sách"),
            ("registrant_count", "Đăng ký"),
            ("attended_count", "Tham dự"),
            ("admission_owner", "TS phụ trách"),
            ("budget", "NS dự kiến"),
            ("budget_actual", "Chi phí đã xác nhận"),
        ],
        "actions": [
            {"id": "export_event_registrants", "label": "Xuất DS đăng ký"},
            {"id": "export_event_followup", "label": "Xuất file sau SK (mức quan tâm)"},
            {"id": "print_page", "label": "In danh sách"},
        ],
        "primary_action": "Tạo sự kiện",
        "row_buttons": [
            {"id": "manage_event_registrants", "label": "DS đăng ký / follow-up"},
            {"id": "edit_marcom_event", "label": "Sửa / giai đoạn"},
            {"id": "sync_alumni_event", "label": "Đồng bộ Alumni"},
        ],
        "allow_delete": True,
        "delete_path": "marcom/events",
    },
    "marcom.assets": {
        "title": "Nội dung và tư liệu truyền thông",
        "desc": (
            "Text, hình ảnh, video, thiết kế và ấn phẩm. Hạng mục thuê ngoài chỉ sản xuất sau khi "
            "ngân sách được duyệt. File nằm ở kho tải lên chung. Lịch đăng website và mạng xã hội "
            "được ghi nhận bằng kênh và đường dẫn, chưa đăng tự động."
        ),
        "endpoint": "ops_marcom_assets",
        "api": "/ops/marcom/assets",
        "mode": "manage",
        "search": True,
        "columns": [
            ("title", "Tên"),
            ("asset_type", "Loại"),
            ("topic", "Chủ đề"),
            ("outsource", "Thuê ngoài"),
            ("content_status", "Tiến độ"),
            ("budget_status", "Ngân sách"),
            ("channel_code", "Kênh"),
            ("publish_at", "Lịch đăng"),
            ("program_codes", "CT"),
            ("usage_until", "Hạn dùng"),
        ],
        "actions": [],
        "primary_action": "Thêm nội dung",
        "allow_delete": True,
        "delete_path": "marcom/assets",
        "workflow": "Yêu cầu → phân công → sản xuất → nghiệm thu → phát hành / lưu trữ",
    },
    "admissions.crm_source": {
        "title": "Dữ liệu Nguồn",
        "desc": (
            "File Enquiry của Tuyển sinh: ngày tiếp nhận, chuyên viên, họ tên, tình trạng, "
            "mức độ quan tâm, chương trình, năm, email, điện thoại, nhắc lịch, liên hệ gần nhất, "
            "chi tiết, sự kiện, kênh và hai chi tiết kênh."
        ),
        "endpoint": "ops_admissions_crm_source",
        "api": "/ops/crm/source",
        "mode": "manage",
        "search": True,
        "program_filter": True,
        "crm_bulk_convert": True,
        "columns": [
            ("enquiry_date", "Ngày tiếp nhận"),
            ("pic", "Chuyên viên"),
            ("full_name", "Họ tên"),
            ("person_status_label", "Tình trạng"),
            ("prospect_level", "Mức độ quan tâm"),
            ("program_interest", "Chương trình"),
            ("intake", "Năm"),
            ("email", "Email"),
            ("phone", "Số điện thoại"),
            ("follow_up_date", "Nhắc lịch"),
            ("latest_contact_at", "Liên hệ gần nhất"),
            ("channel", "Kênh"),
            ("source_1", "Chi tiết kênh 1"),
            ("source_2", "Chi tiết kênh 2"),
            ("join_event", "Sự kiện tham gia"),
            ("notes", "Chi tiết"),
        ],
        "actions": ["Đồng bộ kho", "Xuất DS"],
        "primary_action": None,
        "row_buttons": [
            {"id": "open_person_dossier", "label": "Theo dõi theo tên"},
            {"id": "crm_daily_update", "label": "Cập nhật hôm nay"},
            {"id": "convert_to_applicant", "label": "Chuyển ứng viên"},
            {"id": "crm_view_reminders", "label": "Lịch nhắc"},
        ],
        "allow_delete": True,
        "delete_path": "crm-source",
        "edit_path": "crm-source",
        "workflow": (
            "Ngày tiếp nhận · chuyên viên · mức độ quan tâm · kênh · nhắc lịch · chi tiết"
        ),
    },
    "admissions.crm_activities": {
        "title": "Đợt chăm sóc",
        "desc": (
            "Sự kiện tham gia ghi trên file Enquiry. Mỗi đợt chỉ có tên, thời gian, "
            "chương trình và chi tiết chăm sóc của người tham gia."
        ),
        "endpoint": "ops_admissions_crm_activities",
        "api": "/ops/crm/activities",
        "mode": "manage",
        "search": True,
        "columns": [
            ("title", "Sự kiện tham gia"),
            ("starts_at", "Thời gian"),
            ("program_codes", "Chương trình"),
            ("participant_count", "Số người"),
            ("notes", "Chi tiết"),
        ],
        "actions": ["Xuất DS"],
        "primary_action": "Khai báo đợt",
        "row_buttons": [
            {"id": "crm_pick_profiles", "label": "Chọn hồ sơ"},
            {"id": "crm_view_participants", "label": "Ghi chú chăm sóc"},
        ],
        "allow_delete": True,
        "delete_path": "crm-activities",
        "edit_path": "crm-activities",
        "workflow": "Tên sự kiện · thời gian · chương trình · chi tiết chăm sóc",
    },
    "admissions.crm_reminders": {
        "title": "Nhắc nhở CRM",
        "desc": (
            "Nhắc lịch trên file Enquiry: ngày nhắc, họ tên, điện thoại, email, "
            "chương trình và mức độ quan tâm. Gửi email hoặc đánh dấu đã gọi."
        ),
        "endpoint": "ops_admissions_crm_reminders",
        "api": "/ops/crm/reminders",
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "columns": [
            ("remind_at", "Nhắc lịch"),
            ("full_name", "Họ tên"),
            ("phone", "Số điện thoại"),
            ("email", "Email"),
            ("program_interest", "Chương trình"),
            ("prospect_level", "Mức độ quan tâm"),
            ("channel", "Hình thức nhắc"),
            ("title", "Nội dung"),
            ("status", "TT nhắc"),
        ],
        "actions": ["In danh sách", "Gửi email nhắc", "Gọi điện"],
        "primary_action": "Thêm nhắc",
        "row_buttons": [
            {"id": "crm_dispatch_email", "label": "Email"},
            {"id": "crm_dispatch_phone", "label": "Gọi ĐT"},
        ],
        "allow_delete": True,
        "delete_path": "crm-reminders",
        "edit_path": "crm-reminders",
        "workflow": "Tự tạo trước đợt → in / email / gọi → đánh dấu đã gửi",
    },
    "admissions.crm_reports": {
        "title": "Báo cáo CRM",
        "desc": (
            "Báo cáo file Enquiry: số hồ sơ theo mức độ quan tâm "
            "(Hot, Warm, Cold, Email, Inactive, Prospect, Move to Application) và theo chương trình."
        ),
        "endpoint": "ops_admissions_crm_reports",
        "api": "/ops/crm/reports",
        "mode": "view",
        "search": False,
        "is_crm_report": True,
        "columns": [
            ("program_interest", "Chương trình"),
            ("hot", "Hot"),
            ("warm", "Warm"),
            ("cold", "Cold"),
            ("email", "Email"),
            ("inactive", "Inactive"),
            ("prospect", "Prospect"),
            ("move_to_application", "Move to Application"),
            ("apply", "Apply"),
            ("candidate", "Candidate"),
            ("fail", "Fail"),
            ("select", "Select"),
            ("quit", "Quit"),
            ("postpone", "Postpone"),
            ("enroll", "Enroll"),
            ("total", "Tổng"),
        ],
        "actions": ["Xuất Excel", "In"],
        "workflow": "Mức quan tâm và phễu Apply → Enroll theo chương trình — sheet Report của file Enquiry",
    },
    "admissions.events": {
        "title": "Sự kiện tuyển sinh",
        "desc": (
            "Info Day, workshop, campaign: Marcom quảng bá và lên nội dung. "
            "Tuyển sinh mời, tư vấn trong sự kiện, chăm sóc sau sự kiện và cập nhật mức quan tâm vào file Enquiry."
        ),
        "endpoint": "ops_admissions_events",
        "api": "/ops/marcom/events",
        "mode": "manage",
        "search": True,
        "columns": [
            ("title", "Sự kiện"),
            ("event_type", "Loại"),
            ("event_date", "Ngày"),
            ("location", "Địa điểm"),
            ("program_codes", "CT"),
            ("phase_label", "Giai đoạn"),
            ("admission_owner", "TS phụ trách"),
            ("registrant_count", "Đăng ký"),
            ("attended_count", "Tham dự"),
            ("phase_before_notes", "Trước"),
            ("phase_during_notes", "Trong"),
            ("phase_after_notes", "Sau"),
        ],
        "actions": [
            {"id": "export_event_registrants", "label": "Xuất DS đăng ký"},
            {"id": "export_event_followup", "label": "Xuất file sau SK"},
            {"id": "print_page", "label": "In danh sách"},
        ],
        "primary_action": None,
        "row_buttons": [
            {"id": "manage_event_registrants", "label": "DS đăng ký / follow-up"},
            {"id": "edit_marcom_event", "label": "Giai đoạn chăm sóc"},
        ],
        "workflow": "Trước: mời đăng ký · Trong: tư vấn tại sự kiện · Sau: remind và cập nhật mức quan tâm",
    },
    "admissions.neu_prep": {
        "title": "Chuẩn bị xét duyệt NEU",
        "desc": (
            "Hồ sơ đã đỗ: nộp Thanh tra Pháp chế, minh chứng tiếng Anh gửi Khảo thí, "
            "theo dõi văn bản NEU và nộp phòng Hợp tác quốc tế. Admin chương trình thực thi, Tuyển sinh phối hợp."
        ),
        "endpoint": "ops_admissions_neu_prep",
        "api": "/ops/applications",
        "api_params": {"neu_prep": "1"},
        "mode": "manage",
        "search": True,
        "program_filter": True,
        "round_filter": True,
        "columns": [
            ("cfvg_app_no", "Mã hồ sơ"),
            ("full_name", "Họ tên"),
            ("program_code", "CT"),
            ("english_cert", "Chứng chỉ TA"),
            ("degree_verified", "Văn bằng"),
            ("english_verified", "TA đầu vào"),
            ("chk_naric", "VN-NARIC"),
            ("thanh_tra_status", "Thanh tra"),
            ("khao_thi_status", "Khảo thí"),
            ("neu_doc_status", "Văn bản NEU"),
            ("htqt_status", "HTQT"),
            ("neu_packet_ready", "Gói NEU"),
            ("status", "TT hồ sơ"),
        ],
        "row_buttons": [
            {"id": "edit_application", "label": "Cập nhật gói NEU"},
            {"id": "view_application", "label": "Xem chi tiết"},
            {"id": "manage_app_docs", "label": "Tài liệu hồ sơ"},
        ],
        "actions": [
            {"id": "export_thanh_tra", "label": "Xuất hồ sơ Thanh tra"},
            {"id": "export_htqt", "label": "Xuất hồ sơ HTQT"},
            {"id": "print_page", "label": "In danh sách"},
            "Xuất Excel",
        ],
        "primary_action": None,
        "workflow": "Thanh tra Pháp chế · Khảo thí (TA) · văn bản NEU · nộp HTQT",
    },
    "student.profile": {
        "title": "Hồ sơ của tôi",
        "desc": "Học viên / thí sinh xem hồ sơ cá nhân gắn với tài khoản portal.",
        "endpoint": "ops_student_profile",
        "api": "/ops/student/me",
        "mode": "view",
        "search": False,
        "columns": [
            ("full_name", "Họ tên"),
            ("student_code", "Mã HV"),
            ("cfvg_app_no", "Mã hồ sơ"),
            ("program_code", "CT"),
            ("class_name", "Lớp"),
            ("status", "Trạng thái TS"),
            ("english_file", "CC ngoại ngữ"),
            ("degree_file", "Bằng ĐH"),
            ("other_file", "Minh chứng"),
            ("doc_count", "Số TL"),
            ("email", "Email"),
            ("phone", "SĐT"),
            ("dob", "Ngày sinh"),
            ("login", "Login"),
        ],
        "row_buttons": [
            {"id": "manage_app_docs", "label": "Tài liệu hồ sơ"},
            {"id": "update_student_profile", "label": "Cập nhật hồ sơ"},
        ],
        "actions": [
            {"id": "print_page", "label": "In hồ sơ"},
            {"id": "export_student_timeline", "label": "Xuất lộ trình E2E"},
        ],
        "primary_action": None,
    },
    "student.schedule": {
        "title": "Lịch học / Lịch PV",
        "desc": "Lịch phỏng vấn và lịch thi của bạn.",
        "endpoint": "ops_student_schedule",
        "api": "/ops/student/me/schedule",
        "mode": "view",
        "search": False,
        "columns": [
            ("kind", "Loại"),
            ("title", "Lịch"),
            ("program_code", "CT"),
            ("room", "Phòng"),
            ("starts_at", "Thời gian"),
            ("result", "KQ / TT"),
        ],
        "actions": [{"id": "print_page", "label": "In lịch"}],
        "primary_action": None,
    },
    "student.results": {
        "title": "Kết quả của tôi",
        "desc": "Lộ trình tuần tự: TS → phí → PV → nhập học → môn học → thi → CĐTN → tốt nghiệp.",
        "endpoint": "ops_student_results",
        "api": "/ops/student/me/timeline",
        "mode": "view",
        "search": False,
        "columns": [
            ("stage_no", "#"),
            ("title", "Khâu"),
            ("status", "TT"),
            ("detail", "Chi tiết"),
            ("print_entity", "Mẫu in/xuất"),
            ("program_code", "CT"),
            ("student_code", "Mã HV"),
            ("degree_grade", "GPA"),
        ],
        "actions": [
            {"id": "print_page", "label": "In lộ trình"},
            {"id": "export_student_timeline", "label": "Xuất CSV lộ trình"},
        ],
        "primary_action": None,
    },
    "student.progress": {
        "title": "Bảng điểm & tiến độ",
        "desc": "Điểm học tập và điểm thi từng môn so với chương trình đang theo học. Môn đã học xong, đang học và sắp tới.",
        "endpoint": "ops_student_progress",
        "api": "/ops/student/me/progress-courses",
        "mode": "view",
        "search": False,
        "columns": [
            ("course_code", "Mã môn"),
            ("course_name", "Môn học"),
            ("semester", "Kỳ"),
            ("progress_label", "Tiến độ"),
            ("study_score", "Điểm học tập"),
            ("exam_score", "Điểm thi"),
            ("final_score", "Điểm môn"),
            ("attendance", "Điểm danh"),
            ("lessons_viewed", "Bài đã xem"),
            ("study_minutes", "Phút học"),
            ("advisor", "GV hướng dẫn"),
            ("gpa_to_date", "Điểm TB"),
        ],
        "actions": [
            {"id": "print_my_transcript", "label": "In bảng điểm"},
            {"id": "print_my_progress", "label": "In báo cáo tiến độ"},
        ],
        "primary_action": None,
    },
    "teaching.online_lectures": {
        "title": "Bài giảng trực tuyến",
        "desc": "Tạo và phát bài (file/link) theo lịch; HV xem, hỏi đáp; thảo luận nhóm.",
        "endpoint": "ops_online_lectures",
        "api": "/ops/elearn/lectures",
        "mode": "manage",
        "search": True,
        "program_filter": True,
        "edit_path": "elearn-lectures",
        "allow_delete": True,
        "delete_path": "elearn-lectures",
        "columns": [
            ("program_code", "CT"),
            ("class_name", "Lớp"),
            ("course_code", "Mã HP"),
            ("lesson_no", "Buổi"),
            ("title", "Bài giảng"),
            ("publish_at", "Lịch phát"),
            ("duration_min", "Phút"),
            ("comment_count", "Hỏi đáp"),
            ("status", "Trạng thái"),
        ],
        "row_buttons": [
            {"id": "preview_online_lecture", "label": "Xem bài"},
        ],
        "actions": [],
        "primary_action": {"id": "create_online_lecture", "label": "Thêm mới"},
    },
    "teaching.objectives": {
        "title": "Cố vấn mục tiêu học",
        "desc": "Phân tích syllabus/buổi học để xác định mục tiêu và bước đạt mục tiêu.",
        "endpoint": "ops_elearn_objectives",
        "api": "/ops/elearn/objectives",
        "mode": "manage",
        "search": True,
        "edit_path": "elearn-objectives",
        "allow_delete": True,
        "delete_path": "elearn-objectives",
        "columns": [
            ("program_code", "CT"),
            ("class_name", "Lớp"),
            ("course_code", "HP"),
            ("title", "Mục tiêu"),
            ("steps_text", "Các bước"),
            ("source", "Nguồn"),
            ("status", "Trạng thái"),
        ],
        "actions": [],
        "primary_action": {"id": "generate_objectives", "label": "Tạo từ syllabus"},
    },
    "teaching.instructor_intel": {
        "title": "Hỗ trợ GV thông minh",
        "desc": "Theo dõi tiến độ lớp: thời gian xem, câu hỏi, học viên rủi ro.",
        "endpoint": "ops_instructor_intel",
        "api": "/ops/elearn/instructor-intel",
        "mode": "manage",
        "search": True,
        "columns": [
            ("program_code", "CT"),
            ("class_name", "Lớp"),
            ("course_code", "HP"),
            ("course_name", "Học phần"),
            ("published_count", "Bài đã phát"),
            ("avg_watch_min", "TB phút xem"),
            ("open_questions", "Câu hỏi"),
            ("at_risk_count", "HV rủi ro"),
            ("status", "TT"),
        ],
        "actions": [],
        "primary_action": None,
    },
    "teaching.student_tracker": {
        "title": "Theo dõi học viên",
        "desc": "Phút học, tiến độ xem bài, cảnh báo HV chậm.",
        "endpoint": "ops_student_tracker",
        "api": "/ops/elearn/tracker",
        "mode": "manage",
        "search": True,
        "columns": [
            ("full_name", "Học viên"),
            ("student_code", "Mã HV"),
            ("class_name", "Lớp"),
            ("course_code", "HP"),
            ("watch_min", "Phút xem"),
            ("progress_pct", "% tiến độ"),
            ("lifecycle_status", "TT học tập"),
            ("status", "TT"),
        ],
        "actions": [],
        "primary_action": None,
    },
    "teaching.exam_integrity": {
        "title": "Phiên thi trực tuyến",
        "desc": "Xác minh danh tính trước thi: CCCD, ảnh chân dung, cam kết. Không so khớp khuôn mặt.",
        "endpoint": "ops_exam_integrity",
        "api": "/ops/elearn/sittings",
        "mode": "manage",
        "search": True,
        "status_filter": True,
        "edit_path": "elearn-sittings",
        "allow_delete": True,
        "delete_path": "elearn-sittings",
        "columns": [
            ("exam_title", "Kỳ thi"),
            ("exam_date", "Ngày thi"),
            ("student_name", "Học viên"),
            ("program_code", "CT"),
            ("cccd_confirmed", "CCCD"),
            ("honor_ack", "Cam kết"),
            ("has_selfie", "Ảnh"),
            ("identity_status", "Xác minh"),
        ],
        "row_buttons": [
            {"id": "verify_exam_sitting", "label": "Xác minh"},
            {"id": "upload_exam_selfie", "label": "Ảnh selfie"},
        ],
        "actions": [],
        "primary_action": {"id": "generate_exam_sittings", "label": "Tạo phiên từ lịch thi"},
    },
    "teaching.return_meetings": {
        "title": "Họp HV tạm ngưng",
        "desc": "Lịch họp trực tuyến cho HV bảo lưu / nghỉ học; lưu URL hỗ trợ trở lại.",
        "endpoint": "ops_return_meetings",
        "api": "/ops/elearn/meetings",
        "mode": "manage",
        "search": True,
        "edit_path": "elearn-meetings",
        "allow_delete": True,
        "delete_path": "elearn-meetings",
        "columns": [
            ("starts_at", "Thời điểm"),
            ("student_name", "Học viên"),
            ("lifecycle_status", "TT học tập"),
            ("class_name", "Lớp"),
            ("meeting_url", "URL họp"),
            ("reason", "Lý do"),
            ("status", "Trạng thái"),
        ],
        "actions": [],
        "primary_action": {"id": "create_return_meeting", "label": "Thêm mới"},
    },
    "student.study_plan": {
        "title": "Cố vấn kế hoạch học",
        "desc": "Đề xuất kế hoạch ôn tập theo mục tiêu và tiến độ cá nhân.",
        "endpoint": "ops_student_study_plan",
        "api": "/ops/elearn/plans",
        "mode": "view",
        "search": True,
        "columns": [
            ("title", "Kế hoạch"),
            ("student_name", "Học viên"),
            ("item_count", "Số chủ đề"),
            ("remaining_min", "Phút còn lại"),
            ("generated_at", "Tạo lúc"),
            ("status", "Trạng thái"),
        ],
        "actions": [],
        "primary_action": {"id": "generate_study_plan", "label": "Tạo kế hoạch"},
    },
    "student.time_to_learn": {
        "title": "Thời gian hoàn thành chủ đề",
        "desc": "Ước lượng phút còn lại theo mức độ xem bài hiện tại.",
        "endpoint": "ops_student_time_to_learn",
        "api": "/ops/elearn/ttl",
        "mode": "view",
        "search": True,
        "columns": [
            ("topic", "Chủ đề"),
            ("estimated_min", "Ước lượng (phút)"),
            ("mastery", "Mức nắm"),
            ("remaining_min", "Còn lại (phút)"),
            ("status", "TT"),
        ],
        "actions": [],
        "primary_action": {"id": "generate_ttl", "label": "Tính thời gian"},
    },
    "student.objective_recs": {
        "title": "Đề xuất mục tiêu cá nhân",
        "desc": "Gợi ý mục tiêu chưa đạt và cách hoàn thành.",
        "endpoint": "ops_student_objective_recs",
        "api": "/ops/elearn/recs",
        "mode": "view",
        "search": True,
        "columns": [
            ("title", "Mục tiêu"),
            ("reason", "Lý do"),
            ("how_to", "Cách đạt"),
            ("status", "TT"),
        ],
        "actions": [],
        "primary_action": {"id": "generate_objective_recs", "label": "Đề xuất mục tiêu"},
    },
    "student.agenda": {
        "title": "Lịch học cá nhân",
        "desc": "Xếp lịch ngày/tuần theo thời gian còn lại của từng chủ đề.",
        "endpoint": "ops_student_agenda",
        "api": "/ops/elearn/agenda",
        "mode": "view",
        "search": True,
        "columns": [
            ("starts_at", "Bắt đầu"),
            ("ends_at", "Kết thúc"),
            ("title", "Chủ đề"),
            ("status", "TT"),
        ],
        "actions": [],
        "primary_action": {"id": "generate_agenda", "label": "Tạo lịch tuần"},
    },
    "student.return_meetings": {
        "title": "Họp hỗ trợ trở lại",
        "desc": "Lịch họp trực tuyến khi HV bảo lưu hoặc nghỉ học, để theo dõi lại khóa học.",
        "endpoint": "ops_student_return_meetings",
        "api": "/ops/elearn/meetings",
        "mode": "view",
        "search": True,
        "columns": [
            ("starts_at", "Thời điểm"),
            ("student_name", "Học viên"),
            ("lifecycle_status", "TT học tập"),
            ("meeting_url", "URL họp"),
            ("reason", "Lý do"),
            ("status", "Trạng thái"),
        ],
        "actions": [],
        "primary_action": None,
    },
    "reports.dashboard": {
        "title": "Báo cáo",
        "desc": "Tổng quan số liệu theo phạm vi chương trình được giao.",
        "endpoint": "ops_reports",
        "api": "/ops/summary",
        "mode": "view",
        "search": False,
        "is_summary": True,
        "columns": [],
        "actions": [],
        "primary_action": None,
    },
}

# Nút «Xem chi tiết» (form readonly) — bỏ qua hub/summary/nav-only
_VIEW_DETAIL_SKIP = {
    "reports.dashboard",
    "student.library",
    "student.lessons",
    "student.study_plan",
    "student.time_to_learn",
    "student.objective_recs",
    "student.agenda",
    "student.return_meetings",
    "teaching.instructor_intel",
    "teaching.student_tracker",
    "student.profile",
    "admissions.round_docs",
    "canvas.coordinator",
    "canvas.faculty",
    "canvas.student",
    "canvas.accounting",
    "canvas.it",
}
# view_* chỉ điều hướng / export — vẫn cần thêm view_record cho form quan sát
_VIEW_NAV_IDS = {
    "view_students",
    "view_courses",
    "view_submissions",
}


def _ensure_view_detail_buttons() -> None:
    for code, cfg in OPS_MODULES.items():
        if code in _VIEW_DETAIL_SKIP:
            continue
        if cfg.get("is_summary") or cfg.get("is_canvas_hub") or cfg.get("is_student_library") or cfg.get(
            "is_student_lessons"
        ) or cfg.get("is_crm_report") or cfg.get("is_collection_report"):
            continue
        if not cfg.get("columns"):
            continue
        buttons = list(cfg.get("row_buttons") or [])
        has_detail = any(
            (b.get("id") or "").startswith("view_") and (b.get("id") not in _VIEW_NAV_IDS)
            for b in buttons
        )
        if has_detail:
            continue
        # Ưu tiên form hồ sơ ứng viên khi module dùng applications
        view_id = "view_application" if code in (
            "admissions.results",
            "accounting.official_list",
            "accounting.candidate_files",
        ) else "view_record"
        buttons.insert(0, {"id": view_id, "label": "Xem chi tiết"})
        cfg["row_buttons"] = buttons


_ensure_view_detail_buttons()


# Modules cần nút «Chỉnh sửa» cạnh Xem (theo kiểm thử) — không trùng edit_* sẵn có
_EDIT_ROW_SKIP = {
    "reports.dashboard",
    "student.library",
    "student.lessons",
    "student.profile",
    "student.schedule",
    "student.results",
    "student.practice",
    "student.study_plan",
    "student.time_to_learn",
    "student.objective_recs",
    "student.agenda",
    "student.return_meetings",
    "teaching.instructor_intel",
    "teaching.student_tracker",
    "teaching.grades",  # gradebook riêng
    "teaching.attendance",  # session page
    "teaching.lessons",  # hub → detail
    "teaching.materials",
    "accounting.fees",
    "accounting.charges",
    "accounting.tuition_tracker",
    "accounting.fee_alerts",
    "accounting.candidate_files",
    "accounting.collection_report",
    "accounting.fee_types",
    "accounting.my_fees",
    "admissions.crm_reports",
    "canvas.coordinator",
    "canvas.faculty",
    "canvas.student",
    "canvas.accounting",
    "canvas.it",
}

# perm → path PATCH /ops/rows/<path>/<id> (hoặc asst/marcom qua delete_path)
EDIT_PATH_BY_PERM = {
    "admissions.rounds": "rounds",
    "admissions.interviews": "interviews",
    "admissions.applications": None,  # edit_application
    "admissions.results": None,
    "admissions.pre_enroll": "candidate-pre-enroll",
    "admissions.enrolled_files": "candidate-enrolled",
    "admissions.doc_types": "admission-doc-types",
    "admissions.crm_source": "crm-source",
    "admissions.crm_activities": "crm-activities",
    "admissions.crm_reminders": "crm-reminders",
    "accounting.official_list": None,
    "programs.structure": "program-versions",
    "programs.courses": "courses",
    "classes.manage": "classes",
    "teaching.faculty": None,  # edit_faculty
    "teaching.assign": "teaching-assignments",
    "teaching.schedule": "attendance-sessions",
    "teaching.groups": "study-groups",
    "teaching.exams": "exams",
    "teaching.evaluation": "evaluations",
    "teaching.thesis": "thesis-records",
    "students.manage": None,
    "alumni.members": "alumni",
    "alumni.events": "alumni-events",
    "marcom.leads": "marcom/leads",
    "marcom.campaigns": "marcom/campaigns",
    "marcom.events": None,
    "marcom.assets": "marcom/assets",
    "asst.exec_tasks": "asst/tasks",
    "asst.calendar": "asst/calendar",
    "asst.intl_faculty": "asst/intl-faculty",
    "asst.intl_students": "asst/intl-students",
    "asst.director_fr": "asst/director-fr",
    "asst.documents": "asst/documents",
    "asst.procurement": "asst/procurement",
    "asst.payments": "asst/payments",
    "asst.weekly_report": "asst/weekly-reports",
    "asst.leave": "asst/leave",
}


def _ensure_edit_row_buttons() -> None:
    """Đồng nhất: mọi list manage có Xem thì có Chỉnh sửa (icon) trừ hub/self-service."""
    for code, cfg in OPS_MODULES.items():
        if code in _EDIT_ROW_SKIP or code in _VIEW_DETAIL_SKIP:
            continue
        if cfg.get("is_summary") or cfg.get("is_canvas_hub") or cfg.get("is_crm_report") or cfg.get("is_collection_report"):
            continue
        if code.startswith("student.") and cfg.get("mode") == "view":
            continue
        if not cfg.get("columns"):
            continue
        # Gắn edit_path cho generic PATCH
        if "edit_path" not in cfg and code in EDIT_PATH_BY_PERM:
            ep = EDIT_PATH_BY_PERM[code]
            if ep:
                cfg["edit_path"] = ep
            elif cfg.get("delete_path"):
                cfg["edit_path"] = cfg["delete_path"]
        elif "edit_path" not in cfg and cfg.get("delete_path"):
            cfg["edit_path"] = cfg["delete_path"]

        buttons = list(cfg.get("row_buttons") or [])
        has_edit = any(
            (b.get("id") or "").startswith("edit_")
            or (b.get("id") or "") in ("generic_edit", "update_application", "edit_student_lifecycle")
            for b in buttons
        )
        if has_edit or cfg.get("row_edit_action"):
            continue
        # Chỉ thêm khi đã có view chi tiết
        has_view = any(
            (b.get("id") or "").startswith("view_") and (b.get("id") not in _VIEW_NAV_IDS)
            for b in buttons
        )
        if not has_view and not cfg.get("edit_path"):
            continue
        # Spec edit action
        if code in ("admissions.applications", "admissions.results", "accounting.official_list"):
            edit_id, edit_label = "edit_application", "Chỉnh sửa"
        elif code == "teaching.faculty":
            edit_id, edit_label = "edit_faculty", "Sửa hồ sơ"
        elif code == "students.manage":
            edit_id, edit_label = "edit_student_lifecycle", "Cập nhật"
        elif code == "marcom.events":
            edit_id, edit_label = "edit_marcom_event", "Sửa / giai đoạn"
        else:
            if not cfg.get("edit_path"):
                continue
            edit_id, edit_label = "generic_edit", "Chỉnh sửa"
        # Chèn sau nút view đầu tiên
        insert_at = 0
        for i, b in enumerate(buttons):
            if (b.get("id") or "").startswith("view_"):
                insert_at = i + 1
                break
        buttons.insert(insert_at, {"id": edit_id, "label": edit_label})
        cfg["row_buttons"] = buttons


_ensure_edit_row_buttons()
apply_column_provenance()


# Manage lists: toolbar «Thêm mới» when the page does not already have a create button.
# Skip hubs, reports, student self-service, and workflow-derived ledgers.
_CHROME_SKIP_CREATE = {
    "reports.dashboard",
    "admissions.crm_reports",
    "admissions.results",
    "admissions.round_docs",
    "accounting.collection_report",
    "accounting.fee_alerts",
    "accounting.tuition_tracker",
    "accounting.my_fees",
    "student.profile",
    "student.schedule",
    "student.results",
    "student.library",
    "student.lessons",
    "student.practice",
    "student.study_plan",
    "student.time_to_learn",
    "student.objective_recs",
    "student.agenda",
    "student.return_meetings",
    "teaching.instructor_intel",
    "teaching.student_tracker",
    "canvas.coordinator",
    "canvas.faculty",
    "canvas.student",
    "canvas.it",
    "canvas.accounting",
    "teaching.lessons",
    "teaching.materials",
    "teaching.assignments",
    "teaching.grades",
    "teaching.attendance",
}

CREATE_PRIMARY_BY_PERM = {
    "admissions.applications": {"id": "create_application", "label": "Thêm mới"},
    "admissions.written_exams": {"id": "create_application", "label": "Thêm mới"},
    "admissions.interviews": {"id": "create_interview_boards", "label": "Thêm mới"},
    "admissions.pre_enroll": {"id": "create_application", "label": "Thêm mới"},
    "admissions.enrolled_files": {"id": "create_class", "label": "Thêm mới"},
    "asst.payments": {"id": "asst_payment", "label": "Thêm mới"},
    "students.manage": {"id": "create_class", "label": "Thêm mới"},
    "teaching.schedule": {"id": "create_session", "label": "Thêm mới"},
    "teaching.assign": {"id": "create_assignment", "label": "Thêm mới"},
    "programs.structure": {"id": "create_program_version", "label": "Thêm mới"},
    "programs.courses": {"id": "create_course", "label": "Thêm mới"},
    "accounting.official_list": {"id": "create_class", "label": "Thêm mới"},
    "accounting.fees": {"id": "create_receipt", "label": "Thêm mới"},
    "accounting.charges": {"id": "create_receipt", "label": "Thêm mới"},
    "accounting.candidate_files": {"id": "create_receipt", "label": "Thêm mới"},
    "teaching.thesis": {"id": "create_thesis", "label": "Thêm mới"},
    "teaching.evaluation": {"id": "open_eval", "label": "Thêm mới"},
    "accounting.payment_imports": {"id": "create_receipt", "label": "Thêm mới"},
    "accounting.receipt_emails": {"id": "create_receipt", "label": "Thêm mới"},
    "admissions.student_numbering": {"id": "assign_student_codes", "label": "Thêm mới"},
    "intl.workflow_steps": {"id": "create_workflow_step", "label": "Thêm mới"},
    "teaching.online_lectures": {"id": "create_online_lecture", "label": "Thêm mới"},
    "teaching.objectives": {"id": "generate_objectives", "label": "Tạo từ syllabus"},
    "teaching.exam_integrity": {"id": "generate_exam_sittings", "label": "Tạo phiên từ lịch thi"},
    "teaching.return_meetings": {"id": "create_return_meeting", "label": "Thêm mới"},
    "student.study_plan": {"id": "generate_study_plan", "label": "Tạo kế hoạch"},
    "student.time_to_learn": {"id": "generate_ttl", "label": "Tính thời gian"},
    "student.objective_recs": {"id": "generate_objective_recs", "label": "Đề xuất mục tiêu"},
    "student.agenda": {"id": "generate_agenda", "label": "Tạo lịch tuần"},
}

_AUTO_DELETE_PERMS = {
    "admissions.interviews": "interviews",
    "admissions.pre_enroll": "candidate-pre-enroll",
    "admissions.enrolled_files": "candidate-enrolled",
    "programs.structure": "program-versions",
    "programs.courses": "courses",
    "teaching.assign": "teaching-assignments",
    "teaching.schedule": "attendance-sessions",
    "teaching.thesis": "thesis-records",
}

_DEDICATED_TOOLBAR_IDS = frozenset({"print_page", "export_excel"})
_DEDICATED_TOOLBAR_LABELS = frozenset(
    {"in", "print", "xuất excel", "xuat excel", "export excel"}
)


def _is_list_add_action(action_id: str, label: str = "") -> bool:
    """List-level create (Thêm mới). These belong on the pager, not on each grid row."""
    a = (action_id or "").strip()
    lab = (label or "").strip().lower()
    if lab in {"thêm mới", "add new"} and a:
        return True
    if not a:
        return False
    return (
        a.startswith("create_")
        or a.startswith("Tạo")
        or a.startswith("Thêm")
        or a in ("row_create", "asst_payment")
    )


def _ensure_list_chrome() -> None:
    """Every management list: Thêm mới on the pager, In/Xuất Excel, row view/edit/delete."""
    for code, cfg in OPS_MODULES.items():
        if cfg.get("is_summary"):
            actions = list(cfg.get("actions") or [])
            ids = {_normalize_action_item(a)["id"] for a in actions}
            if "print_page" not in ids:
                actions.append({"id": "print_page", "label": "In"})
            if "export_excel" not in ids:
                actions.append({"id": "export_excel", "label": "Xuất Excel"})
            cfg["actions"] = actions
            continue
        if not cfg.get("columns") and not cfg.get("is_canvas_hub"):
            continue

        actions = list(cfg.get("actions") or [])
        seen_ids = set()
        seen_labels = set()
        for a in actions:
            item = _normalize_action_item(a)
            seen_ids.add(item["id"])
            seen_labels.add(item["label"].strip().lower())
        if "print_page" not in seen_ids and not (
            seen_labels & {"in", "print", "in danh sách", "print list"}
        ):
            actions.append({"id": "print_page", "label": "In"})
            seen_ids.add("print_page")
        if "export_excel" not in seen_ids and not any(
            "xuất excel" in x or "xuat excel" in x or "export excel" in x for x in seen_labels
        ):
            actions.append({"id": "export_excel", "label": "Xuất Excel"})
        cfg["actions"] = actions

        if cfg.get("mode") != "manage":
            continue
        if code in _CHROME_SKIP_CREATE or cfg.get("is_canvas_hub") or cfg.get("is_crm_report"):
            continue
        if cfg.get("is_collection_report") or cfg.get("is_student_library") or cfg.get("is_student_lessons"):
            continue

        pa = cfg.get("primary_action")
        if not pa:
            mapped = CREATE_PRIMARY_BY_PERM.get(code)
            if mapped:
                cfg["primary_action"] = dict(mapped)
                pa = cfg["primary_action"]

        if code in _AUTO_DELETE_PERMS and not cfg.get("allow_delete"):
            cfg["allow_delete"] = True
            cfg.setdefault("delete_path", _AUTO_DELETE_PERMS[code])
            cfg.setdefault("edit_path", _AUTO_DELETE_PERMS[code])

        create_id = None
        create_label = "Thêm mới"
        if isinstance(pa, dict):
            create_id = str(pa.get("id") or "").strip() or None
            create_label = str(pa.get("label") or create_label)
        elif pa:
            create_id = str(pa).strip()
            create_label = create_id
        if not create_id or not _is_list_add_action(create_id, create_label):
            cfg["list_add_action"] = None
            continue
        cfg["list_add_action"] = {"id": create_id, "label": create_label}
        # Add is a list action. Do not repeat it on every grid row.
        buttons = [
            b for b in (cfg.get("row_buttons") or [])
            if not (
                isinstance(b, dict)
                and (b.get("id") or "") in (create_id, "row_create")
            )
        ]
        cfg["row_buttons"] = buttons


STATUS_LABELS = {
    "ok": "Đủ",
    "issue": "Thiếu",
    "warn": "Cần cập nhật",
    "submitted": "Đã nộp",
    "approved_ts": "TS đã duyệt",
    "interview": "Chờ / đang PV",
    "passed": "Đỗ",
    "failed": "Trượt",
    "paid": "Đã nộp phí",
    "official": "Nhập học chính thức",
    "withdrawn": "Rút hồ sơ",
    # Design doc aliases (Applicant / Student / Teaching)
    "draft": "Nháp",
    "under_screening": "Đang sơ duyệt",
    "eligible_for_exam": "Đủ ĐK thi viết",
    "exam_scheduled": "Đã xếp thi viết",
    "eligible_for_interview": "Đủ ĐK PV",
    "admitted": "Admitted",
    "rejected": "Từ chối",
    "waiting_list": "Waiting list",
    "deposit_pending": "Chờ phí ghi danh",
    "deposit_verified": "Đã xác nhận phí",
    "officially_enrolled": "Nhập học chính thức",
    "reserved": "Bảo lưu",
    "on_leave": "Nghỉ học",
    "withdrawn_program": "Xóa tên / rút CT",
    "graduated": "Tốt nghiệp",
    "open": "Mở / chờ làm",
    "opening": "Đang mở",
    "closed": "Đã đóng",
    "pending": "Chờ",
    "active": "Đang học",
    "verified": "Đã xác minh",
    "flagged": "Cần rà soát",
    "suggested": "Đề xuất",
    "accepted": "Đã nhận",
    "at_risk": "Rủi ro",
    "scheduled": "Đã lên lịch",
    "planned": "Kế hoạch",
    "budget_submitted": "Chờ Kế toán",
    "approved_kt": "KT đã duyệt",
    "approved": "BGD đã duyệt",
    "running": "Đang triển khai",
    "evaluating": "Đánh giá / nghiệm thu",
    "reconciling": "Đối soát chứng từ",
    "requested": "Yêu cầu",
    "producing": "Đang sản xuất",
    "payment_file": "Hồ sơ thanh toán",
    "archived": "Lưu trữ",
    "assigned": "Đã phân công",
    "proposed": "Đề xuất",
    "invited": "Đã mời",
    "confirmed": "Xác nhận",
    "in_teaching": "Đang giảng",
    "completed": "Hoàn thành",
    "lecturer": "Giảng viên",
    "expert": "Chuyên gia",
    "potential": "Tiềm năng",
    "interested": "Quan tâm",
    "consulting": "Đang tư vấn",
    "applicant": "Ứng viên",
    "exam_prep": "Lập hồ sơ thi",
    "interviewed": "Đã tham gia phỏng vấn",
    "admitted": "Trúng tuyển",
    "decided": "Quyết định",
    "not_decided": "Không quyết định",
    "handed_ts": "Đã tạo hồ sơ TS",
    "tu_van_rieng": "Tư vấn riêng",
    "hoi_thao": "Hội thảo",
    "info_day": "Info Day",
    "goi_dien": "Gọi điện",
    "gap_mat": "Gặp mặt",
    "khac": "Khác",
    "hot": "Rất quan tâm",
    # Trợ lý BGD
    "doing": "Đang làm",
    "done": "Hoàn thành",
    "overdue": "Quá hạn",
    "due_soon": "Sắp hạn",
    "waived": "Miễn / không thu",
    "bank_transfer": "Chuyển khoản",
    "card": "Nộp thẻ",
    "cash": "Tiền mặt",
    "note": "Ghi chú",
    "danger": "Cao",
    "warning": "Cảnh báo",
    "confirmed": "Xác nhận",
    "cancelled": "Hủy",
    "preparing": "Chuẩn bị",
    "not_required": "Không cần",
    "approved": "Đã duyệt",
    "rejected": "Từ chối",
    "draft": "Nháp",
    "sent": "Đã gửi",
    "unpaid": "Chưa TT",
    "partial": "Một phần",
    "due_soon": "Sắp hạn",
    "waived": "Miễn / không thu",
    "annual": "Phép năm",
    "personal": "Việc riêng",
    "sick": "Ốm / điều trị",
    "business": "Công tác",
    "maternity": "Thai sản",
    "other": "Khác",
    "incoming": "Đến",
    "outgoing": "Đi",
    "in": "Đến",
    "out": "Đi",
    "seal": "Đóng dấu",
    "received": "Đã nhận",
    "issued": "Đã phát hành",
    "sealed": "Đã đóng dấu",
    "stationery": "VP phẩm",
    "water": "Nước Lavie",
    "taxi": "Taxi/đón tiễn",
    "flight": "Vé máy bay",
    "purchased": "Đã mua",
    "invoiced": "Có hóa đơn",
    "valid": "Còn hiệu lực",
    "exported": "Đã xuất",
    "live": "Live trên Canvas",
    "ready": "Sẵn sàng",
    "marked_pushed": "Đã đẩy Canvas",
    "error": "Lỗi",
    "published": "Đã công bố",
    "archived": "Lưu trữ",
    "released": "Đã release HV",
    "syllabus": "Syllabus",
    "slide": "Slide",
    "reading": "Đọc thêm",
    "exercise": "Bài tập",
    "video": "Video",
    "other": "Khác",
    "theory": "Lý thuyết",
    "practice": "Thực hành/CG",
    "student": "Học viên",
    "coordinator": "Điều phối",
    "lecturer": "Giảng viên",
    "scheduled": "Đã xếp lịch BV",
    "defended": "Đã bảo vệ",
    "Admitted": "Admitted",
    "Non-Admitted": "Non-Admitted",
    "pass": "Đỗ / Admitted",
    "fail": "Trượt",
    "Da thanh toan": "Đã thanh toán",
    "Cho thanh toan": "Chờ thanh toán",
    # Checklist / xác minh (Tuyển sinh)
    "pending": "Chờ xử lý",
    "issued": "Đã gửi checklist",
    "confirmed": "Đã xác nhận đủ",
    "incomplete": "Thiếu giấy tờ",
    "yes": "Có / Đạt",
    "no": "Không / Chưa",
    "x": "X",
    "incompleted": "Incompleted",
    "exempted": "Exempted",
    "not_required": "Not required",
    "not_sent": "Chưa nộp",
    "sent": "Đã nộp",
    "received": "Đã nhận văn bản",
    "email": "Email",
    "hot": "Hot",
    "warm": "Warm",
    "cold": "Cold",
    "inactive": "Inactive",
    "prospect": "Prospect",
    "move_to_application": "Move to Application",
}

# ?status=overdue is tuition watch only. Never dump STATUS_LABELS into every module filter.
_WATCH_OR_QA_CODES = frozenset({"overdue", "due_soon", "overdue_count", "ok", "issue", "warn"})

_STATUS_FILTER_KIND = {
    "admissions.applications": "application_status",
    "admissions.results": "application_status",
    "accounting.official_list": "application_status",
    "admissions.crm_source": "crm_care_status",
    "accounting.fees": "fee_ledger",
    "accounting.charges": "payment_watch",
    "accounting.candidate_files": "payment_watch",
    "accounting.tuition_tracker": "payment_watch",
    "accounting.collection_report": "payment_watch",
    "accounting.fee_alerts": "fee_alerts",
    "teaching.materials": "materials",
    "marcom.events": "marcom_event",
    "marcom.campaigns": "marcom_budget",
    "marcom.assets": "marcom_content",
    "admissions.crm_activities": "crm_activity",
    "admissions.crm_reminders": "crm_reminder",
    "admissions.rounds": "round_status",
}

_STATUS_FILTER_CODES = {
    "application_status": [
        "submitted", "approved_ts", "interview", "passed", "failed",
        "paid", "official", "withdrawn",
    ],
    "crm_care_status": [
        "potential", "interested", "consulting", "applicant", "exam_prep",
        "interviewed", "admitted", "decided", "not_decided", "handed_ts",
    ],
    "lifecycle_status": ["active", "reserved", "on_leave", "withdrawn_program", "graduated"],
    "fee_ledger": ["pending", "paid", "unpaid", "partial", "waived"],
    "payment_watch": ["unpaid", "due_soon", "overdue", "partial", "paid", "waived"],
    "fee_alerts": ["due_soon", "overdue", "overdue_count"],
    "materials": ["draft", "released", "archived"],
    "marcom_event": ["planned", "promoting", "ongoing", "done", "cancelled"],
    "marcom_budget": [
        "planned", "budget_submitted", "approved_kt", "approved",
        "running", "evaluating", "reconciling", "closed", "cancelled",
    ],
    "marcom_content": ["requested", "producing", "accepted", "payment_file", "archived"],
    "crm_activity": ["planned", "done", "cancelled"],
    "crm_reminder": ["pending", "sent"],
    "round_status": ["planned", "open", "opening", "active", "closed"],
}


def allowed_status_filter_codes(perm_code):
    """None = module has no status filter — do not forward ?status= to the API."""
    kind = _STATUS_FILTER_KIND.get(perm_code or "")
    if not kind:
        return None
    return frozenset(_STATUS_FILTER_CODES.get(kind) or [])


def build_status_filter_options(perm_code, *, status_options=None, status_labels=None):
    kind = _STATUS_FILTER_KIND.get(perm_code or "")
    if not kind:
        return []
    labels = status_labels or STATUS_LABELS
    catalog_kinds = ("application_status", "crm_care_status", "lifecycle_status")
    if kind in catalog_kinds:
        raw = (status_options or {}).get(kind) or []
        out = []
        for o in raw:
            v = (o.get("v") if isinstance(o, dict) else o) or ""
            v = str(v).strip()
            if not v or v.lower() in _WATCH_OR_QA_CODES:
                continue
            lab = (o.get("l") if isinstance(o, dict) else None) or labels.get(v, v)
            out.append({"v": v, "l": lab})
        if out:
            return out
    codes = list(_STATUS_FILTER_CODES.get(kind) or [])
    if kind == "round_status":
        is_en = str(labels.get("closed") or "") in ("Closed", "closed")
        round_labs = {
            "planned": "Planned" if is_en else "Kế hoạch",
            "open": "Open" if is_en else "Mở",
            "opening": "Opening" if is_en else "Đang mở",
            "active": "Running" if is_en else "Đang diễn ra",
            "closed": "Closed" if is_en else "Đã đóng",
        }
        return [{"v": c, "l": round_labs.get(c, labels.get(c, c))} for c in codes]
    return [{"v": c, "l": labels.get(c, c)} for c in codes]

# Thao tác hồ sơ theo bộ phận (bàn giao)
DEPT_APPLICATION_ACTIONS = {
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
        {"label": "Rút hồ sơ (ghi chú)", "status": "withdrawn"},
    ],
}


# perm_code → import entity key (backend /ops/bulk-import/<entity>)
IMPORT_BULK_ENTITIES = {
    "asst.exec_tasks": "asst-tasks",
    "asst.calendar": "asst-calendar",
    "asst.intl_faculty": "asst-intl-faculty",
    "asst.intl_students": "asst-intl-students",
    "asst.director_fr": "asst-director-fr",
    "asst.documents": "asst-documents",
    "asst.procurement": "asst-procurement",
    "asst.payments": "asst-payments",
    "asst.weekly_report": "asst-weekly-reports",
    "asst.leave": "asst-leave",
    "admissions.rounds": "rounds",
    "admissions.applications": "applications",
    "classes.manage": "classes",
    "teaching.faculty": "faculty",
    "teaching.groups": "study-groups",
    "teaching.exams": "exams",
    "teaching.evaluation": "evaluations",
    "alumni.members": "alumni",
    "alumni.events": "alumni-events",
    "marcom.leads": "marcom-leads",
    "marcom.campaigns": "marcom-campaigns",
    "marcom.events": "marcom-events",
    "marcom.assets": "marcom-assets",
    "admissions.crm_source": "crm-source",
    "students.manage": "students",
}


def _apply_import_bulk_flags() -> None:
    for code, entity in IMPORT_BULK_ENTITIES.items():
        m = OPS_MODULES.get(code)
        if not m:
            continue
        m["import_bulk"] = True
        m["import_entity"] = entity
        m["bulk_select"] = True


_apply_import_bulk_flags()


QA_EXTRA_ACTIONS = {
    "admissions.crm_source": [
        {"id": "send_timeline", "label": "Gửi email chương trình & lịch TS"},
    ],
    "admissions.crm_activities": [],
    "admissions.applications": [
        {"id": "send_timeline", "label": "Gửi email chương trình & lịch TS"},
        {"id": "issue_checklists", "label": "Issue checklist hồ sơ"},
    ],
    "admissions.written_exams": [
        {"id": "notify_exam_schedule", "label": "Gửi thông báo lịch thi"},
    ],
    "admissions.interviews": [
        {"id": "notify_interview_invites", "label": "Gửi thư mời phỏng vấn"},
    ],
    "admissions.results": [
        {"id": "notify_admission_pack", "label": "Thông báo trúng tuyển + học phí"},
    ],
    "admissions.rounds": [],
    "admissions.pre_enroll": [],
    "accounting.fees": [],
    "accounting.charges": [],
    "accounting.my_fees": [],
    "accounting.official_list": [],
    "admin.audit_logs": [],
    "student.profile": [],
    "student.schedule": [],
    "student.results": [],
    "student.lessons": [],
    "student.library": [],
    "alumni.members": [],
    "alumni.events": [],
    "marcom.leads": [],
    "marcom.campaigns": [],
    "marcom.events": [],
    "asst.exec_tasks": [],
    "asst.calendar": [],
    "asst.documents": [],
    "asst.procurement": [],
    "asst.payments": [],
    "asst.leave": [],
    "asst.weekly_report": [],
    "asst.director_fr": [],
    "canvas.coordinator": [],
    "canvas.faculty": [],
    "canvas.student": [],
    "canvas.it": [],
    "canvas.accounting": [],
}


def _ensure_qa_ui() -> None:
    extra_cols = [
        ("qa_label", "Rà soát AI"),
        ("qa_flags", "Thiếu sót"),
        ("qa_suggestions", "Đề xuất"),
    ]
    filter_act = {"id": "qa_filter_issues", "label": "Chỉ bản ghi thiếu sót"}
    for code, extra in QA_EXTRA_ACTIONS.items():
        cfg = OPS_MODULES.get(code)
        if not cfg:
            continue
        cols = list(cfg.get("columns") or [])
        keys = set()
        for c in cols:
            keys.add(c[0] if isinstance(c, (tuple, list)) else (c.get("key") if isinstance(c, dict) else ""))
        for col in extra_cols:
            if col[0] not in keys:
                cols.append(col)
        if cols:
            cfg["columns"] = cols
        actions = list(cfg.get("actions") or [])
        seen = set()
        for a in actions:
            if isinstance(a, dict):
                seen.add(str(a.get("id") or ""))
                seen.add(str(a.get("label") or ""))
            else:
                seen.add(str(a))
        for a in list(extra) + [filter_act]:
            if a["id"] not in seen and a["label"] not in seen:
                actions.append(a)
                seen.add(a["id"])
                seen.add(a["label"])
        cfg["actions"] = actions


_ensure_qa_ui()


# ── Toolbar action menus (Xuất / Nhập / Thao tác) ─────────────────────

_IMPORT_HINTS = (
    "import",
    "tải mẫu",
    "tai mau",
    "download template",
    "import_template",
    "import_excel",
    "import_round",
    "import round",
    "nhập",
    "nhap ",
)

_EXPORT_HINTS = (
    "export",
    "xuất",
    "xuat",
    "print",
    "in ",
    "in_",
    "in lịch",
    "in lich",
    "in ds",
    "in danh",
    "print_page",
    "print_list",
    "print_interview",
    "roster",
    "handoff",
    "khao-thi",
    "khảo thí",
    "synthesis",
    "matrix",
    "timeline",
    "excel",
    "csv",
    "mẫu neu",
    "mau neu",
    "xuất sổ",
    "xuat so",
    "xuất báo",
    "xuat bao",
    "xuất ds",
    "xuat ds",
    "xuất điểm",
    "xuat diem",
    "xuất ma trận",
    "visa_export",
    "visa_list",
    "export_",
)


def _normalize_action_item(a) -> dict:
    if isinstance(a, dict):
        aid = str(a.get("id") or a.get("label") or "").strip()
        label = str(a.get("label") or aid).strip()
        return {"id": aid or label, "label": label or aid, **{k: v for k, v in a.items() if k not in ("id", "label")}}
    s = str(a).strip()
    return {"id": s, "label": s}


def classify_action_group(aid: str, label: str) -> str:
    """Return 'import' | 'export' | 'process' for a toolbar action."""
    blob = f"{aid} {label}".lower().strip()
    # Import first (template / import excel)
    if any(h in blob for h in _IMPORT_HINTS):
        # Avoid "export template" false positives — none currently
        if "export" in blob and "import" not in blob and "tải mẫu" not in blob and "download template" not in blob:
            pass
        else:
            return "import"
    if any(h in blob for h in _EXPORT_HINTS):
        # "Import Excel" already caught; "Create…" not export
        if blob.startswith("create ") or "tạo " in blob or "them " in blob or "thêm " in blob:
            if not any(x in blob for x in ("xuất", "xuat", "export", "print", "in ")):
                return "process"
        return "export"
    # Short labels: In / Print alone
    if blob in ("in", "print", "xuất", "xuat", "export"):
        return "export"
    return "process"


def group_toolbar_actions(actions, lang: str = "vi") -> list[dict]:
    """
    Build dropdown menus for list toolbars:
      - Xuất danh sách / Export list
      - Nhập danh sách / Import list
      - Thao tác / Actions  (create, notify, assign, …)
    Empty groups are omitted. Order: Import → Export → Process (primary create stays outside).
    """
    buckets = {"import": [], "export": [], "process": []}
    seen = set()
    for raw in actions or []:
        item = _normalize_action_item(raw)
        key = item["id"] or item["label"]
        if not key or key in seen:
            continue
        # Dedicated In / Xuất Excel sit next to Thêm mới, not inside the export menu.
        if item["id"] in _DEDICATED_TOOLBAR_IDS or item["label"].strip().lower() in _DEDICATED_TOOLBAR_LABELS:
            continue
        seen.add(key)
        g = classify_action_group(item["id"], item["label"])
        buckets[g].append(item)

    is_en = (lang or "vi") == "en"
    menus = []
    # Import first so staff see template/import together, then export, then process
    if buckets["import"]:
        menus.append(
            {
                "id": "import",
                "label": "Import list" if is_en else "Nhập danh sách",
                "entries": buckets["import"],
            }
        )
    if buckets["export"]:
        menus.append(
            {
                "id": "export",
                "label": "Export list" if is_en else "Xuất danh sách",
                "entries": buckets["export"],
            }
        )
    if buckets["process"]:
        menus.append(
            {
                "id": "process",
                "label": "Actions" if is_en else "Thao tác",
                "entries": buckets["process"],
            }
        )
    return menus


_ensure_list_chrome()


def application_actions_for_depts(dept_codes):
    seen = set()
    actions = []
    for code in dept_codes or []:
        for a in DEPT_APPLICATION_ACTIONS.get(code, []):
            if a["status"] not in seen:
                seen.add(a["status"])
                actions.append(a)
    return actions


def filter_role_mode(dept_codes):
    codes = set(dept_codes or [])
    # Dual Thủ quỹ + Điều phối (vd. HanhNT): xem đủ dữ liệu hai phía
    if codes & {"ke_toan"} and codes & {"mba", "master_chuyen_nganh"}:
        return "all"
    if codes & {"mba", "master_chuyen_nganh"} and not (codes & {"tuyen_sinh", "marcom_tuyen_sinh"}):
        return "coordinator"
    if codes & {"ke_toan"} and not (codes & {"tuyen_sinh", "mba", "master_chuyen_nganh"}):
        return "accounting"
    if codes & {"tuyen_sinh", "marcom_tuyen_sinh"}:
        return "admissions"
    return "all"

