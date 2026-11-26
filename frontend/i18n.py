"""
UI strings EN/VI for menus, flash messages, and common chrome.
"""
from __future__ import annotations

MESSAGES = {
    "login_ok": {"vi": "Đăng nhập thành công.", "en": "Signed in successfully."},
    "login_need": {
        "vi": "Vui lòng nhập tên đăng nhập và mật khẩu.",
        "en": "Please enter username and password.",
    },
    "login_bad": {
        "vi": "Sai tên đăng nhập hoặc mật khẩu.",
        "en": "Invalid username or password.",
    },
    "login_api_down": {
        "vi": "Không kết nối được máy chủ API. Kiểm tra backend đang chạy trên cổng 8026.",
        "en": "Cannot reach the API. Check that the backend is running on port 8026.",
    },
    "logout_ok": {"vi": "Bạn đã đăng xuất.", "en": "You have been logged out."},
    "lang_switched_vi": {
        "vi": "Đã chuyển sang tiếng Việt.",
        "en": "Switched to Vietnamese.",
    },
    "lang_switched_en": {
        "vi": "Đã chuyển sang tiếng Anh.",
        "en": "Switched to English.",
    },
    "no_permission": {
        "vi": "Bạn không có quyền truy cập chức năng này.",
        "en": "You do not have permission for this feature.",
    },
    "load_failed": {
        "vi": "Không tải được dữ liệu.",
        "en": "Could not load data.",
    },
    "api_error": {
        "vi": "Lỗi kết nối API.",
        "en": "API connection error.",
    },
    "pwd_fill_all": {
        "vi": "Vui lòng điền đầy đủ các trường.",
        "en": "Please fill in all fields.",
    },
    "pwd_mismatch": {
        "vi": "Mật khẩu mới và xác nhận không khớp.",
        "en": "New password and confirmation do not match.",
    },
    "pwd_short": {
        "vi": "Mật khẩu mới phải có ít nhất 4 ký tự.",
        "en": "New password must be at least 4 characters.",
    },
    "pwd_same": {
        "vi": "Mật khẩu mới phải khác mật khẩu hiện tại.",
        "en": "New password must differ from the current password.",
    },
    "pwd_ok": {
        "vi": "Đã đổi mật khẩu thành công.",
        "en": "Password changed successfully.",
    },
    "workspace": {"vi": "Làm việc", "en": "Workspace"},
    "workspace_page": {"vi": "Trang làm việc", "en": "Workspace"},
    "dashboard_home": {"vi": "Tổng quan", "en": "Dashboard"},
    "guide_menu": {"vi": "Hướng dẫn", "en": "Guide"},
    "guide_title": {"vi": "Hướng dẫn sử dụng", "en": "User guide"},
    "guide_open": {"vi": "Mở hướng dẫn", "en": "Open the guide"},
    "guide_back": {"vi": "Về Tổng quan", "en": "Back to dashboard"},
    "guide_prev": {"vi": "Trang trước", "en": "Previous slide"},
    "guide_next": {"vi": "Trang sau", "en": "Next slide"},
    "guide_contents": {"vi": "Mục lục", "en": "Contents"},
    "dashboard_section": {"vi": "Dashboard", "en": "Dashboard"},
    "modules_section": {"vi": "Chức năng của bạn", "en": "Your modules"},
    "change_password": {"vi": "Đổi mật khẩu", "en": "Change password"},
    "account_profile": {"vi": "Thông tin tài khoản", "en": "Account profile"},
    "profile_ok": {"vi": "Đã cập nhật thông tin tài khoản.", "en": "Profile updated."},
    "profile_avatar_removed": {"vi": "Đã xóa ảnh đại diện.", "en": "Avatar removed."},
    "logout": {"vi": "Đăng xuất", "en": "Logout"},
    "suggest": {"vi": "Đề xuất", "en": "Suggest"},
    "suggest_title": {"vi": "Đề xuất & góp ý", "en": "Suggestions & feedback"},
    "admin_users": {"vi": "Người dùng", "en": "Users"},
    "admin_departments": {"vi": "Bộ phận", "en": "Departments"},
    "admin_permissions": {"vi": "Phân quyền", "en": "Permissions"},
    "admin_suggestions": {"vi": "Thống kê đề xuất", "en": "Suggestion stats"},
    "admin_dashboard": {"vi": "Dashboard cũ", "en": "Legacy dashboard"},
    "admin_categories": {"vi": "Danh mục sách", "en": "Book categories"},
    "admin_status_types": {"vi": "Loại trạng thái", "en": "Status types"},
    "admin": {"vi": "Quản trị", "en": "Admin"},
    "brand_ops": {"vi": "Điều hành chương trình X", "en": "X Program Ops"},
    "brand_admin": {"vi": "Bảng điều khiển Admin", "en": "Admin Console"},
    "language": {"vi": "Ngôn ngữ", "en": "Language"},
    "lang_vi": {"vi": "Tiếng Việt", "en": "Vietnamese"},
    "lang_en": {"vi": "Tiếng Anh", "en": "English"},
    "open_menu": {"vi": "Mở menu", "en": "Open menu"},
    "main_nav": {"vi": "Điều hướng chính", "en": "Main"},
    "department": {"vi": "Bộ phận", "en": "Department"},
    "manage": {"vi": "Quản lý", "en": "Manage"},
    "view_search": {"vi": "Xem / Tra cứu", "en": "View / Search"},
    "no_modules": {
        "vi": "Chưa được gán chức năng.",
        "en": "No modules assigned.",
    },
    "applications": {"vi": "Hồ sơ", "en": "Applications"},
    "fees_pending": {"vi": "Phí chờ", "en": "Pending fees"},
    "classes": {"vi": "Lớp học", "en": "Classes"},
    "close": {"vi": "Đóng", "en": "Close"},
}

STATUS_LABELS_EN = {
    "submitted": "Submitted",
    "approved_ts": "Admissions approved",
    "interview": "Interview",
    "passed": "Passed",
    "failed": "Failed",
    "paid": "Fee paid",
    "official": "Officially enrolled",
    "reserved": "Reserved / deferred",
    "on_leave": "On leave",
    "withdrawn_program": "Withdrawn from program",
    "graduated": "Graduated",
    "deposit_pending": "Deposit pending",
    "deposit_verified": "Deposit verified",
    "withdrawn": "Withdrawn",
    "open": "Open",
    "opening": "Opening",
    "closed": "Closed",
    "pending": "Pending",
    "active": "Active",
    "planned": "Planned",
    "assigned": "Assigned",
    "lecturer": "Lecturer",
    "expert": "Expert",
    "doing": "In progress",
    "done": "Done",
    "overdue": "Overdue",
    "danger": "High",
    "warning": "Warning",
    "confirmed": "Confirmed",
    "cancelled": "Cancelled",
    "preparing": "Preparing",
    "not_required": "Not required",
    "approved": "Approved",
    "rejected": "Rejected",
    "draft": "Draft",
    "sent": "Sent",
    "unpaid": "Unpaid",
    "partial": "Partial",
    "due_soon": "Due soon",
    "waived": "Waived",
    "bank_transfer": "Bank transfer",
    "card": "Card",
    "cash": "Cash",
    "note": "Note",
    "under_screening": "Under screening",
    "eligible_for_exam": "Eligible for written exam",
    "exam_scheduled": "Written exam scheduled",
    "eligible_for_interview": "Eligible for interview",
    "admitted": "Admitted",
    "waiting_list": "Waiting list",
    "officially_enrolled": "Officially enrolled",
    "proposed": "Proposed",
    "invited": "Invited",
    "in_teaching": "In teaching",
    "completed": "Completed",
    "annual": "Annual leave",
    "personal": "Personal",
    "sick": "Sick / treatment",
    "business": "Business trip",
    "maternity": "Maternity",
    "other": "Other",
    "incoming": "Incoming",
    "outgoing": "Outgoing",
    "in": "Incoming",
    "out": "Outgoing",
    "seal": "Seal",
    "received": "Received",
    "issued": "Issued",
    "sealed": "Sealed",
    "stationery": "Stationery",
    "water": "Lavie water",
    "taxi": "Taxi / pickup",
    "flight": "Flight",
    "purchased": "Purchased",
    "invoiced": "Invoiced",
    "valid": "Valid",
    "exported": "Exported",
    "live": "Live on Canvas",
    "ready": "Ready",
    "marked_pushed": "Pushed to Canvas",
    "error": "Error",
    "published": "Published",
    "archived": "Archived",
    "released": "Released to students",
    "syllabus": "Syllabus",
    "slide": "Slide",
    "reading": "Reading",
    "exercise": "Exercise",
    "video": "Video",
    "theory": "Theory",
    "practice": "Practice / CG",
    "student": "Student",
    "coordinator": "Coordinator",
    "scheduled": "Defense scheduled",
    "defended": "Defended",
    "Admitted": "Admitted",
    "Non-Admitted": "Non-Admitted",
    "pass": "Passed / Admitted",
    "fail": "Failed",
    "Da thanh toan": "Paid",
    "Cho thanh toan": "Awaiting payment",
    "incomplete": "Missing documents",
    "yes": "Yes",
    "no": "No",
    "Pending": "Pending",
}

# Column-key fallback when the Vietnamese label is not in LABEL_TEXT_EN.
FIELD_LABELS_EN = {
    "absent_count": "Absent",
    "dossier_status": "Dossier",
    "sitting_status": "Exam sitting",
    "selection_status": "Selection",
    "decision_status": "Decision",
    "response_status": "Response",
    "access": "Access",
    "action": "Action",
    "activity_keywords": "Field",
    "actor": "Actor",
    "admission_owner": "Admissions owner",
    "amount": "Amount",
    "amount_adjust": "Adjustment",
    "amount_due": "Amount due",
    "amount_paid": "Amount paid",
    "waiver_pct": "Waiver %",
    "waived_amount": "Waived amount",
    "actual_due": "Actual due",
    "collected_incl_waived": "Collected + waived",
    "remaining": "Outstanding",
    "application_id": "Application",
    "application_status": "App. status",
    "arrival_date": "Arrival",
    "arrival_flight": "Flight",
    "asset_type": "Type",
    "assignee": "Owner",
    "attended_count": "Attended",
    "audience": "Audience",
    "beneficiary": "Beneficiary",
    "budget": "Budget",
    "budget_planned": "Planned budget",
    "budget_spent": "Spent",
    "cal_type": "Type",
    "campus": "Campus",
    "care_status": "Care status",
    "candidate_code": "Candidate no.",
    "admit_decision": "Admission decision",
    "enrolled_at": "Enrollment date",
    "converted_program": "Applicant program",
    "converted_at": "Converted at",
    "activity_count": "Campaigns",
    "pending_reminders": "Reminders",
    "next_remind_at": "Next reminder",
    "pic": "PIC",
    "prospect_level": "Level",
    "enquiry_date": "Enquiry date",
    "first_contact": "First contact",
    "follow_up_date": "Follow-up",
    "contact_count": "Contacts",
    "latest_contact_at": "Last contact",
    "care_log_count": "Daily log",
    "join_event": "Join event",
    "flag_apply": "Apply",
    "flag_candidate": "Candidate",
    "flag_select": "Select",
    "flag_enroll": "Enroll",
    "flag_postpone": "Postpone",
    "flag_quit": "Quit",
    "flag_fail": "Fail",
    "activity_type": "Activity type",
    "participant_count": "Participants",
    "high_interest": "High interest",
    "care_score": "Interest %",
    "activity_title": "Campaign",
    "remind_at": "Remind at",
    "category": "Category",
    "cfvg_app_no": "App. no.",
    "cfvg_payment_status": "CFVG status",
    "channel": "Channel",
    "checklist_status": "Checklist",
    "class_name": "Class",
    "closed_at": "Closed",
    "code": "Code",
    "cohort": "Cohort",
    "cohort_year": "Cohort",
    "comment_count": "Comments",
    "company": "Company",
    "contract_status": "Contract",
    "cost_type": "Cost type",
    "course_code": "Course",
    "course_count": "Courses",
    "course_links": "Mapped courses",
    "course_name": "Course",
    "courses_ready": "On Canvas",
    "courses_total": "Courses",
    "cp_number": "Charge code",
    "created_at": "Created",
    "days_overdue": "Days overdue",
    "days_until_due": "Days until due",
    "unpaid_count": "Unpaid items",
    "overdue_count": "Overdue items",
    "due_soon_count": "Due soon",
    "next_due_date": "Next due",
    "pay_status": "Payment status",
    "charge_title": "Charge",
    "severity": "Severity",
    "message": "Message",
    "default_amount": "Default amount",
    "defense_date": "Defense date",
    "degree": "Degree",
    "degree_verified": "Degree",
    "department": "Department",
    "description": "Description",
    "detail": "Details",
    "direction": "Direction",
    "doc_date": "Date",
    "doc_direction": "Direction",
    "doc_expiry": "Doc expiry",
    "doc_no": "Ref. no.",
    "done_summary": "Done",
    "due_at": "Due",
    "due_date": "Due",
    "email": "Email",
    "employee_name": "Staff",
    "end_date": "To",
    "ends_at": "End",
    "english_cert": "English cert",
    "english_file": "Language cert file",
    "degree_file": "Degree file",
    "other_file": "Other evidence PDF",
    "doc_count": "Documents",
    "related_apps": "Applications",
    "related_interviews": "Interviews",
    "has_english_doc": "Language cert uploaded",
    "has_degree_doc": "Degree uploaded",
    "has_other_doc": "Other evidence uploaded",
    "interview_score": "Interview score",
    "avg_score": "Average score",
    "english_verified": "English",
    "event_date": "Date",
    "event_type": "Type",
    "exam_date": "Date",
    "exam_eligibility_note": "Attendance",
    "exam_timeline": "Exam timeline",
    "exam_type": "Type",
    "exchange_kind": "Mode",
    "expert": "Expert",
    "fee_type": "Type",
    "file_path": "File",
    "final_result": "Result",
    "full_name": "Full name",
    "grade_return_date": "Grade return",
    "handler": "Handler",
    "handoff_iae_by": "IAE →",
    "handoff_visa_by": "Visa →",
    "has_file": "File",
    "homework_count": "Practice",
    "hotel_name": "Hotel",
    "id": "Id",
    "ineligible_count": "Ineligible",
    "intake": "Intake",
    "intake_session": "Session",
    "interview_date": "Interview date",
    "interview_timeline": "Interview timeline",
    "invitee_count": "Invited",
    "invoice_date": "Invoice date",
    "is_active": "Active",
    "item_name": "Item",
    "job_title": "Title",
    "kind": "Type",
    "kind_label": "Type",
    "kpi_notes": "KPI",
    "label": "Charge name",
    "lead_source": "Source",
    "leave_type": "Leave type",
    "lecturer": "Lecturer",
    "lesson_count": "Lessons",
    "lesson_no": "Session",
    "lesson_type": "Type",
    "lifecycle_status": "Academic status",
    "location": "Location",
    "login": "Login",
    "material_type": "Type",
    "mc_published_count": "MC published",
    "mc_quiz_count": "MC",
    "meeting_title": "Meeting",
    "member_names": "Members",
    "month_key": "Month",
    "name": "Name",
    "nationality": "Nationality",
    "neu_packet_ready": "NEU packet",
    "next_week_plan": "Next week",
    "notes": "Notes",
    "occupation": "Occupation",
    "onboarding_status": "Onboarding",
    "ongoing_summary": "In progress",
    "opened_at": "Opened",
    "organization": "Organization",
    "owner": "Owner",
    "paid_at": "Paid on",
    "partner_enrollment": "Partner/IAE",
    "partner_code": "Partner code",
    "partner_university": "Partner",
    "passport_expiry": "Passport expiry",
    "passport_no": "Passport",
    "payment_status": "Payment",
    "pending": "Pending push",
    "period_end": "To",
    "period_start": "From",
    "phase_label": "Phase",
    "phone": "Phone",
    "present_count": "Present",
    "print_entity": "Print template",
    "program_code": "Program",
    "program_codes": "Program",
    "program_filter": "Audience",
    "program_interest": "Program interest",
    "programs": "Programs",
    "proof_note": "Evidence",
    "published_count": "Published",
    "quantity": "Qty",
    "ready_faculty": "≥80% faculty",
    "ready_mgmt": "≥60% management",
    "reason": "Reason",
    "registrant_count": "Registrations",
    "relation": "Relation",
    "release_status": "Release",
    "released_count": "Released materials",
    "released_files": "Files",
    "remaining": "Remaining",
    "report_status": "Report",
    "request_date": "Date",
    "requester": "Requester",
    "residence_reg": "Residence",
    "response_pct": "Response %",
    "result": "Result",
    "role_type": "Role",
    "room": "Room",
    "round_code": "Round",
    "rounds_label": "Openings",
    "scholarship_type": "Scholarship",
    "score_label": "Score",
    "seal_used": "Seal",
    "semester": "Semester",
    "sender_or_receiver": "From/To",
    "sent_at": "Sent to NEU",
    "session_count": "Sessions",
    "session_date": "Date",
    "session_label": "Session",
    "session_no": "Session",
    "sis_course_id": "SIS Course",
    "slot_count": "Candidates",
    "slot_minutes": "Min/student",
    "sort_order": "Order",
    "source": "Source",
    "specialty": "Specialty",
    "stage_no": "#",
    "start_date": "From",
    "starts_at": "Start",
    "status": "Status",
    "student_code": "Student code",
    "student_count": "Students",
    "subject": "Subject",
    "submission_status": "Status",
    "substitute": "Substitute",
    "supplier": "Supplier",
    "syllabus_status": "Syllabus",
    "sync_label": "Canvas",
    "sync_status": "Canvas status",
    "synced": "Exported/live",
    "tags": "Tags",
    "teachable_courses": "Can teach",
    "title": "Title",
    "total_grade": "Score /20",
    "transferred_at": "Transferred on",
    "transferred_by": "Transferred by",
    "turnitin_pct": "Turnitin",
    "tutor": "Supervisor",
    "uploaded_by": "Uploaded by",
    "used_for": "Used for",
    "version_code": "Version",
    "visa_info": "Visa",
    "visa_status": "Visa",
    "week_label": "Week",
    "week_start": "Start",
    "work_permit": "Work permit",
    "written_exam_date": "Exam date",
    "written_exam_no": "Exam no.",
    "written_exam_room": "Exam room",
    "written_exam_session": "Exam session",
    "written_score": "Written score",
    "year": "Year",
}

# Exact Vietnamese UI strings → English (columns, buttons, actions, primary).
LABEL_TEXT_EN = {
    "Vắng": "Absent",
    "Truy cập": "Access",
    "Hành động": "Action",
    "Lĩnh vực": "Field",
    "Người thực hiện": "Actor",
    "TS phụ trách": "Admissions owner",
    "Số tiền": "Amount",
    "Thành tiền": "Amount",
    "Điều chỉnh": "Adjustment",
    "Phải thu": "Amount due",
    "Đã thu": "Amount paid",
    "Hồ sơ TS": "Application",
    "TT hồ sơ": "App. status",
    "Đến": "To",
    "Chuyến bay": "Flight",
    "Loại": "Type",
    "Phụ trách": "Owner",
    "Tham dự": "Attended",
    "Đối tượng": "Audience",
    "Người/ĐT": "Beneficiary",
    "Ngân sách": "Budget",
    "NS kế hoạch": "Planned budget",
    "NS đã chi": "Spent",
    "CS": "Campus",
    "Nhóm": "Group",
    "Mã hồ sơ": "App. no.",
    "Mã ứng viên": "Candidate no.",
    "Tên ứng viên": "Candidate name",
    "Quyết định trúng tuyển": "Admission decision",
    "Mã học viên": "Learner code",
    "Tên học viên": "Learner name",
    "Mã học viên": "Learner code",
    "TT theo học": "Study status",
    "Tư cách dự thi": "Exam standing",
    "Xác nhận dự thi": "Confirm examinee",
    "Hồ sơ xuyên suốt": "Full profile",
    "Đăng ký nội dung thi": "Register exam sitting",
    "Cấp mã học viên": "Assign learner codes",
    "Ngày nhập học": "Enrollment date",
    "Chương trình học": "Program",
    "TT CFVG": "CFVG status",
    "Kênh": "Channel",
    "Lớp": "Class",
    "Cohort": "Cohort",
    "Đóng": "Closed",
    "Mã": "Code",
    "Mã HP": "Course code",
    "Mã đợt": "Round code",
    "Khóa": "Cohort",
    "Thảo luận": "Comments",
    "Công ty": "Company",
    "Đơn vị": "Organization",
    "Hợp đồng": "Contract",
    "Loại CP": "Cost type",
    "HP": "Course",
    "Số môn": "Courses",
    "Môn map": "Mapped courses",
    "Học phần": "Course",
    "Môn": "Course",
    "Đã trên Canvas": "On Canvas",
    "Mã CP": "Charge code",
    "Thời điểm": "Time",
    "Tạo lúc": "Created",
    "Số ngày": "Days",
    "Mức mặc định": "Default amount",
    "Ngày BV": "Defense date",
    "Học vị": "Degree",
    "Văn bằng": "Degree",
    "Bộ phận": "Department",
    "Mô tả": "Description",
    "Chi tiết": "Details",
    "Chiều": "Direction",
    "Ngày": "Date",
    "Hết hạn GT": "Doc expiry",
    "Số/KH": "Ref. no.",
    "Đã làm": "Done",
    "Hạn": "Due",
    "Email login Canvas": "Canvas login email",
    "Nhân sự": "Staff",
    "Kết thúc": "End",
    "Chứng chỉ TA": "English cert",
    "TA": "English",
    "TA xác nhận": "English verified",
    "Chuyên cần": "Attendance",
    "Timeline thi": "Exam timeline",
    "Hình thức": "Mode",
    "Chuyên gia": "Expert",
    "KQ": "Result",
    "KQ cuối": "Final result",
    "Họ tên": "Full name",
    "Người phụ trách": "PIC",
    "GPA": "GPA",
    "Trả điểm": "Grade return",
    "Xử lý": "Handler",
    "IAE →": "IAE →",
    "Visa →": "Visa →",
    "TH": "Practice",
    "Khách sạn": "Hotel",
    "Mã gói": "Package",
    "Không đủ ĐK": "Ineligible",
    "Ngày PV": "Interview date",
    "Timeline PV": "Interview timeline",
    "Đã mời": "Invited",
    "Ngày HĐ": "Invoice date",
    "Hàng/DV": "Item",
    "Vị trí": "Title",
    "Tên khoản thu": "Charge name",
    "Nguồn": "Source",
    "Loại nghỉ": "Leave type",
    "GV LT": "Lecturer",
    "Giảng viên": "Lecturer",
    "Số bài": "Lessons",
    "Buổi": "Session",
    "TT học tập": "Academic status",
    "Địa điểm": "Location",
    "TN mở": "MC published",
    "TN": "MC",
    "Cuộc họp": "Meeting",
    "Thành viên": "Members",
    "Tháng": "Month",
    "Tên": "Name",
    "Tên học phần": "Course name",
    "Quốc tịch": "Nationality",
    "Gói NEU": "NEU packet",
    "Tuần tới": "Next week",
    "Ghi chú": "Notes",
    "Nghề nghiệp": "Occupation",
    "Đang làm": "In progress",
    "Mở": "Opened",
    "Ngày nộp": "Paid on",
    "Partner/IAE": "Partner/IAE",
    "Đối tác": "Partner",
    "Hết hạn HC": "Passport expiry",
    "Hộ chiếu": "Passport",
    "TT thanh toán": "Payment",
    "Thanh toán": "Payment",
    "Chờ đẩy": "Pending push",
    "Từ": "From",
    "Giai đoạn": "Phase",
    "Điện thoại": "Phone",
    "Có mặt": "Present",
    "Mẫu in/xuất": "Print template",
    "CT": "Program",
    "CT quan tâm": "Program interest",
    "Chương trình": "Programs",
    "Minh chứng": "Evidence",
    "TH mở": "Practice open",
    "Đã publish": "Published",
    "SL": "Qty",
    "≥80% GV": "≥80% faculty",
    "≥60% QL": "≥60% management",
    "Lý do": "Reason",
    "Đăng ký": "Registrations",
    "Quan hệ": "Relation",
    "TL đã release": "Released materials",
    "Còn lại": "Remaining",
    "Báo cáo": "Report",
    "Đề xuất": "Requester",
    "Cư trú": "Residence",
    "% phản hồi": "Response %",
    "TT": "Status",
    "Vai trò": "Role",
    "Phòng": "Room",
    "Đợt": "Round",
    "Lần mở": "Openings",
    "Học bổng": "Scholarship",
    "Điểm": "Score",
    "Con dấu": "Seal",
    "HK": "Semester",
    "Gửi/Nhận": "From/To",
    "Gửi NEU": "Sent to NEU",
    "Ngày học": "Session date",
    "Số thí sinh": "Candidates",
    "Phút/SV": "Min/student",
    "Thứ tự": "Order",
    "Chuyên môn": "Specialty",
    "Bắt đầu": "Start",
    "Thời gian": "Time",
    "TT đổi lịch": "Reschedule",
    "TT phân công": "Assignment",
    "TT phí": "Fee status",
    "Tiến độ": "Progress",
    "Trạng thái": "Status",
    "Trạng thái TS": "Admissions status",
    "Mã HV": "Student code",
    "HV": "Students",
    "Sĩ số": "Headcount",
    "Trích yếu": "Subject",
    "Người thay": "Substitute",
    "NCC": "Supplier",
    "TT Canvas": "Canvas status",
    "Đã xuất/live": "Exported/live",
    "Có thể dạy": "Can teach",
    "Buổi PV": "Interview",
    "Bài học": "Lesson",
    "Bài tập": "Assignment",
    "Chiến dịch": "Campaign",
    "Form": "Form",
    "Hoạt động": "Activity",
    "Khoản thu": "Charge",
    "Khâu": "Step",
    "Kỳ thi": "Exam",
    "Lịch": "Event",
    "Nhiệm vụ": "Task",
    "Nội dung": "Content",
    "Sự kiện": "Event",
    "Tài liệu": "Material",
    "Tên đề án": "Thesis title",
    "Điểm /20": "Score /20",
    "Ngày chuyển ĐP": "Transferred on",
    "Người chuyển": "Transferred by",
    "GVHD": "Supervisor",
    "Upload bởi": "Uploaded by",
    "Dùng cho": "Used for",
    "Mã phiên bản": "Version code",
    "Phiên bản": "Version",
    "Tuần": "Week",
    "Ngày thi": "Exam date",
    "SBD": "Exam no.",
    "Phòng thi": "Exam room",
    "Ca thi": "Exam session",
    "Điểm viết": "Written score",
    "Điểm PV": "Interview score",
    "Điểm TB": "Average score",
    "File CC NN": "Language cert file",
    "File bằng ĐH": "Degree file",
    "File minh chứng": "Other evidence",
    "Số TL": "Docs",
    "CC ngoại ngữ": "Language cert",
    "Bằng ĐH": "Degree",
    "Minh chứng": "Evidence",
    "Tài liệu hồ sơ": "Documents",
    "Năm": "Year",
    "Có": "Yes",
    "Không": "No",
    "Lifecycle": "Lifecycle",
    "Lớp / Cohort": "Class / cohort",
    # Primary actions
    "Cập nhật hồ sơ": "Update profile",
    "Ghi nhận công văn": "Log correspondence",
    "Lịch thi": "Exam schedule",
    "Thêm GV quốc tế": "Add visiting faculty",
    "Thêm HV quốc tế": "Add exchange student",
    "Thêm alumni": "Add alumni",
    "Thêm chiến dịch": "Add campaign",
    "Thêm giảng viên": "Add faculty",
    "Thêm lead": "Add lead",
    "Thêm lịch": "Add event",
    "Thêm nhiệm vụ": "Add task",
    "Thêm tài sản": "Add asset",
    "Tạo báo cáo tuần": "Create weekly report",
    "Tạo lớp": "Create class",
    "Tạo nhóm": "Create group",
    "Tạo sự kiện": "Create event",
    "Tạo sự kiện Marcom": "Create Marcom event",
    "Thêm mới": "Add new",
    "Tạo đề xuất": "Create request",
    "Tạo đợt mới": "Create round",
    "Xuất roster → Canvas": "Export roster → Canvas",
    "Đăng ký nghỉ": "Request leave",
    # Toolbar / actions
    "Báo cáo phép còn lại": "Leave balance report",
    "Báo cáo tháng": "Monthly report",
    "Xếp lớp hàng loạt": "Place in class",
    "Convert hàng loạt": "Place in class",
    "Cảnh báo chưa thanh toán": "Unpaid warning",
    "Cảnh báo hết hạn": "Expiry warning",
    "Cấp số": "Issue number",
    "DS visa cần làm": "Visas to process",
    "Gửi duyệt BGD": "Submit to Board",
    "Gửi email": "Send email",
    "Gửi email kết quả": "Email results",
    "Nhắc bổ sung giấy tờ": "Remind missing documents",
    "Gửi khảo thí": "Send to exam office",
    "In DS": "Print list",
    "In danh sách": "Print list",
    "In hồ sơ": "Print dossier",
    "In lịch": "Print calendar",
    "In lịch phỏng vấn": "Print interview schedule",
    "In lịch tuần": "Print week calendar",
    "In lộ trình": "Print timeline",
    "Lịch nghỉ tuần": "Weekly leave calendar",
    "Mở Canvas": "Open Canvas",
    "Quản lý nhóm": "Manage groups",
    "Thông báo thay đổi": "Notify change",
    "Tạo nhiệm vụ": "Create task",
    "Tạo đề thi": "Create exam paper",
    "Tải mẫu Excel": "Download template",
    "Xem gói export": "View export packages",
    "Xem gói đã tạo": "View generated packages",
    "Xuất CSV lộ trình": "Export timeline CSV",
    "Xuất DS": "Export list",
    "Đồng bộ kho": "Sync warehouse",
    "Thêm hồ sơ nguồn": "Add source profile",
    "Khai báo đợt": "Declare campaign",
    "Thêm nhắc": "Add reminder",
    "Gửi email nhắc": "Email reminders",
    "Gọi điện": "Phone follow-up",
    "Chuyển thành ứng viên": "Convert to applicant",
    "Xuất DS gửi Điều phối": "Export for Coordinator",
    "Xuất DS nhập cảnh": "Export arrival list",
    "Xuất DS đăng ký": "Export registrations",
    "Xuất Excel": "Export Excel",
    "Xuất Excel CĐTN": "Export thesis Excel",
    "Xuất Excel phí": "Export fees Excel",
    "Xuất Excel slot PV": "Export interview slots",
    "Xuất Grade Synthesis": "Export Grade Synthesis",
    "Xuất báo cáo": "Export report",
    "Xuất báo cáo sau họp": "Export post-meeting report",
    "Xuất báo cáo tháng": "Export monthly report",
    "Xuất báo cáo visa": "Export visa report",
    "Xuất file sau SK (mức quan tâm)": "Export post-event interest",
    "Xuất lộ trình E2E": "Export E2E timeline",
    "Xuất ma trận điểm danh": "Export attendance matrix",
    "Xuất mẫu NEU": "Export NEU template",
    "Xuất roster Canvas": "Export Canvas roster",
    "Xuất sổ CV đi": "Export outgoing register",
    "Xuất sổ CV đến": "Export incoming register",
    "Đánh dấu đã đẩy": "Mark as pushed",
    "Đăng nhập Canvas": "Canvas login",
    "Xuất gói lớp → Canvas": "Export class package → Canvas",
    # Row buttons / actions
    "Copy / chuyển HP": "Copy / transfer courses",
    "Chỉnh sửa": "Edit",
    "Sửa": "Edit",
    "Sửa hồ sơ": "Edit profile",
    "Sửa / giai đoạn": "Edit / phase",
    "Cập nhật": "Update",
    "Email lớp": "Email class",
    "Tạo hồ sơ TS": "Create application",
    "Mời Alumni": "Invite Alumni",
    "DS đăng ký / follow-up": "Registrations / follow-up",
    "Gửi GV": "Send to faculty",
    "Gửi QL": "Send to management",
    "Đồng bộ Alumni": "Sync Alumni",
    "Xem chi tiết": "View details",
    "Môn học / học phần": "Courses",
    "Xem kết quả": "View results",
    "Xem bài làm": "View submissions",
    "Xem SV": "Students",
    "Phê duyệt TS": "Approve application",
    "Phê duyệt hồ sơ": "Approve application",
    "Chuyển PV": "Move to interview",
    "Rút hồ sơ": "Withdraw",
    "Trượt": "Fail",
    "Đỗ": "Pass",
    "Luồng": "Flow",
    "Thao tác": "Actions",
    "Tìm Alumni": "Find Alumni",
    "Phép năm": "Annual leave",
    "Không lương": "Unpaid leave",
    "Việc riêng": "Personal",
    "Ốm": "Sick",
    "Ốm / điều trị": "Sick / treatment",
    "Công tác": "Business trip",
    "Thai sản": "Maternity",
    "Khác": "Other",
    "Họp": "Meeting",
    "Giảng dạy": "Teaching",
    "Nghỉ phép": "Leave",
    "Ngày bắt đầu": "Start date",
    "Giờ bắt đầu": "Start time",
    "Ngày kết thúc": "End date",
    "Giờ kết thúc": "End time",
    "Học kỳ": "Semester",
    "Cả năm": "Full year",
    "Hồ sơ": "Applications",
    "Tài liệu": "Documents",
    "Trường đối tác": "Partner university",
    "Trường gửi": "Home university",
    "Bàn giao visa": "Visa handoff",
    "Bàn giao IAE": "IAE handoff",
    "Bàn giao môn": "Course handoff",
    "Ghi chú KT": "Accounting note",
    "Trợ lý BGD": "Director Assistant",
    "Ngày quá hạn": "Days overdue",
    "Hạn gần nhất": "Next due date",
    "Khoản chưa nộp": "Unpaid items",
    "Khoản quá hạn": "Overdue items",
    "TT nộp phí": "Payment status",
    "Nội dung": "Message",
    "Mức": "Level",
    "Tiêu chí": "Criterion",
    "Xem công nợ": "View charges",
    "Hồ sơ xét tuyển": "Pre-enrollment files",
    "Hồ sơ đã nhập học": "Enrolled files",
    "Tìm kiếm tài liệu": "Search documents",
    "Phân loại tài liệu": "Document types",
    "Thêm khoản thu": "Add fee type",
    "Cập nhật mức": "Update amount",
    "Tải tài liệu lên": "Upload document",
    "Thêm loại tài liệu": "Add document type",
    "Tài liệu hồ sơ": "File documents",
    "Tài liệu đợt": "Round documents",
    "Số miễn": "Waiver amount",
    "Đủ ĐK thi": "Exam eligible",
    "TT thanh toán": "Payment status",
    "Mức mặc định": "Default amount",
    "Điều phối": "Coordinator",
    "Tạo đề xuất mua sắm": "Create purchase request",
    "Báo cáo tuần": "Weekly report",
    "Thêm HV quốc tế / Exchange": "Add exchange student",
    "Cập nhật hồ sơ GĐ Pháp": "Update French Director file",
    "Rà soát AI": "AI review",
    "Thiếu sót": "Gaps",
    "Đề xuất": "Suggestions",
    "Gửi email chương trình & lịch TS": "Send program & schedule email",
    "Issue checklist hồ sơ": "Issue dossier checklist",
    "Gửi thông báo lịch thi": "Send exam schedule",
    "Gửi thư mời phỏng vấn": "Send interview invites",
    "Thông báo trúng tuyển + học phí": "Admission notice + fees",
    "Xuất hồ sơ Thanh tra": "Export inspector packet",
    "Xuất hồ sơ HTQT": "Export international office packet",
    "Chỉ bản ghi thiếu sót": "Incomplete records only",
    "Gửi minh chứng": "Submit proof",
    "Minh chứng HV": "Student proof",
    "KN (năm)": "Work exp. (yrs)",
}

BUTTON_BY_ID = {
    "view_application": "View",
    "edit_application": "Edit",
    "update_application": "Update",
    "manage_app_docs": "Documents",
    "edit_candidate_file": "Update",
    "edit_fee_type": "Update amount",
    "preview_round_doc": "Preview",
    "download_round_doc": "Download",
    "delete_round_doc": "Delete",
    "open_student_charges": "Charges",
    "view_round": "View",
    "manage_round_docs": "Round documents",
    "open_partner_universities": "Partner universities",
    "view_students": "Students",
    "email_class": "Email class",
    "view_courses": "Courses",
    "view_program": "View version",
    "copy_version": "Copy / transfer",
    "create_application": "Add new",
    "create_class": "Add new",
    "create_course": "Add new",
    "create_assignment": "Add new",
    "create_session": "Add new",
    "create_thesis": "Add new",
    "create_program_version": "Add new",
    "create_interview_boards": "Add new",
    "create_online_lecture": "Add lecture",
    "preview_online_lecture": "Watch",
    "generate_objectives": "From syllabus",
    "generate_study_plan": "Create plan",
    "generate_ttl": "Calculate time",
    "generate_objective_recs": "Recommend",
    "generate_agenda": "Build week",
    "generate_exam_sittings": "Create sittings",
    "verify_exam_sitting": "Verify",
    "upload_exam_selfie": "Selfie",
    "create_return_meeting": "Add meeting",
    "asst_payment": "Add new",
    "edit_faculty": "Edit",
    "view_faculty": "View",
    "view_director_fr": "View",
    "conflict": "Conflict",
    "visa_expiry": "Visa expiry",
    "open_eval": "Open form",
    "view_evals": "Results",
    "send_eval_mgmt": "Send to management",
    "send_eval_faculty": "Send to faculty",
    "close_eval": "Close form",
    "view_record": "View",
    "view_student": "View",
    "edit_student_lifecycle": "Update",
    "enroll_official": "Enroll official",
    "generic_edit": "Edit",
    "hand_lead_ts": "Create application",
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
    "invite_event_members": "Invite Alumni",
    "manage_event_registrants": "Registrations / follow-up",
    "sync_alumni_event": "Sync Alumni",
    "view_alumni": "View",
    "view_event": "View",
    "view_exams": "View submissions",
    "edit_marcom_event": "Edit / phase",
}

ACTION_BY_ID = {
    "import_template": "Download template",
    "import_excel": "Import Excel",
    "print_page": "Print list",
    "export_excel": "Export Excel",
    "open_pre_enroll": "Pre-enrollment files",
    "open_enrolled": "Enrolled files",
    "open_round_docs": "Search documents",
    "open_doc_types": "Document types",
    "open_partner_universities": "Partner universities",
    "create_fee_type": "Add fee type",
    "upload_round_doc": "Upload document",
    "create_doc_type": "Add document type",
    "export_fees": "Export fees Excel",
    "export_interview_slots": "Export interview slots",
    "export_thesis": "Export thesis Excel",
    "convert_official_bulk": "Bulk convert",
    "crm_source_create": "Add source profile",
    "crm_sync_warehouse": "Sync warehouse",
    "crm_daily_update": "Daily update",
    "crm_activity_create": "Declare campaign",
    "crm_reminder_create": "Add reminder",
    "crm_dispatch_email_bulk": "Email reminders",
    "crm_dispatch_phone_bulk": "Phone follow-up",
    "send_timeline": "Send admissions timeline",
    "issue_checklists": "Issue dossier checklist",
    "notify_exam_schedule": "Send exam schedule",
    "notify_interview_invites": "Send interview invites",
    "notify_admission_pack": "Admission pack (start + fees)",
    "export_thanh_tra": "Export inspector packet",
    "export_htqt": "Export international office packet",
    "qa_filter_issues": "Show incomplete records only",
    "update_student_profile": "Update profile",
    "send_fee_proof": "Submit payment proof",
}

FLOW_GROUPS = {
    "asst": {"vi": "0. Trợ lý BGD", "en": "0. Director Assistant"},
    "admissions": {"vi": "1. Tuyển sinh", "en": "1. Admissions"},
    "accounting": {"vi": "Thu tiền", "en": "Collections"},
    "programs": {"vi": "3. Chương trình", "en": "3. Program"},
    "classes": {"vi": "4. Lớp học", "en": "4. Classes"},
    "teaching": {"vi": "5–6. Giảng dạy & đánh giá", "en": "5–6. Teaching & assessment"},
    "alumni": {"vi": "7. Alumni", "en": "7. Alumni"},
    "canvas": {"vi": "Canvas LMS", "en": "Canvas LMS"},
    "student": {"vi": "Học viên", "en": "Student"},
    "reports": {"vi": "8. Báo cáo", "en": "8. Reports"},
    "admin": {"vi": "9. Hệ thống", "en": "9. System"},
    "marcom": {"vi": "Truyền thông", "en": "Marcom"},
}

PIPELINE_EN = {
    "submitted": "Submitted",
    "approved_ts": "Admissions OK",
    "interview": "Interview",
    "passed": "Passed",
    "failed": "Failed",
    "paid": "Fee paid",
    "official": "Enrolled",
    "withdrawn": "Withdrawn",
}

WORKFLOWS = {
    "asst.exec_tasks": {
        "vi": "Họp BGD → biên bản → nhiệm vụ → deadline → tiến độ",
        "en": "Board meeting → minutes → tasks → deadline → progress",
    },
    "asst.calendar": {
        "vi": "Lịch BGD / họp / sự kiện / giảng dạy / nghỉ phép",
        "en": "Board / meeting / event / teaching / leave calendar",
    },
    "asst.intl_faculty": {
        "vi": "Hộ chiếu → visa → vé → KS → đón tiễn → lịch giảng",
        "en": "Passport → visa → flight → hotel → pickup → teaching calendar",
    },
    "asst.intl_students": {
        "vi": "Exchange In/Out · Visa→Trợ lý · IAE→KT · môn→ĐP",
        "en": "Exchange In/Out · Visa→Assistant · IAE→Accounting · courses→Coordinator",
    },
    "asst.director_fr": {
        "vi": "Visa / work permit / cư trú GĐ Pháp & gia đình",
        "en": "Visa / work permit / residence for French Director & family",
    },
    "asst.documents": {
        "vi": "CV đến/đi → cấp số → đóng dấu → phát hành",
        "en": "Incoming/outgoing mail → numbering → seal → issue",
    },
    "asst.procurement": {
        "vi": "Đề xuất → mua → hóa đơn → thanh toán",
        "en": "Request → purchase → invoice → payment",
    },
    "asst.payments": {
        "vi": "Theo dõi HĐ & thanh toán hàng tháng",
        "en": "Track contracts and monthly payments",
    },
    "asst.weekly_report": {
        "vi": "Tổng hợp bộ phận → BGD duyệt → gửi NEU",
        "en": "Department summary → Board approval → send to NEU",
    },
    "asst.leave": {
        "vi": "Đăng ký nghỉ → phê duyệt → đồng bộ lịch",
        "en": "Leave request → approval → calendar sync",
    },
    "admissions.rounds": {
        "vi": "ĐP lập timeline May/Aug → TS mở/đóng hồ sơ",
        "en": "Coordinator sets May/Aug timeline → Admissions opens/closes intake",
    },
    "admissions.round_docs": {
        "vi": "Tìm theo đợt · tải lên · xem trước · tải xuống",
        "en": "Search by round · upload · preview · download",
    },
    "admissions.doc_types": {
        "vi": "Khai báo phân loại tài liệu dùng cho đợt tuyển sinh",
        "en": "Declare document types used on admission rounds",
    },
    "admissions.applications": {
        "vi": "Checklist → phê duyệt TS → xác nhận dự thi (ghi căn cứ) trên cùng hồ sơ → bàn giao Điều phối",
        "en": "Checklist → admissions approval → confirm the examinee (write the basis) on the same file → hand off to coordination",
    },
    "admissions.written_exams": {
        "vi": "Đã xác nhận dự thi và, nếu đợt yêu cầu, đã thu lệ phí thi → SBD → điểm viết → hội đồng",
        "en": "Examinee confirmed and, if the round requires it, exam fee paid → exam no. → written score → board",
    },
    "admissions.interviews": {
        "vi": "Boards ~10 TS · email xác nhận · CFVG/IAE/Alumni",
        "en": "Boards ~10 candidates · confirmation email · CFVG/IAE/Alumni",
    },
    "admissions.results": {
        "vi": "Điểm viết / phỏng vấn · Điều phối chốt Đỗ hoặc Trượt · Tuyển sinh gửi cả thư đỗ và thư trượt",
        "en": "Written and interview scores · coordination sets pass or fail · admissions sends both letters",
    },
    "admissions.pre_enroll": {
        "vi": "Cùng một người, chưa thành học viên · xác nhận người dự thi chính thức",
        "en": "The same person, not yet a learner · confirm the official examinee",
    },
    "admissions.enrolled_files": {
        "vi": "Mã học viên + mã ứng viên · hồ sơ theo học · có thể đang chờ xếp lớp",
        "en": "Learner code + candidate code · programme file · may still be waiting for a class",
    },
    "admissions.crm_source": {
        "vi": "Ngày tiếp nhận · chuyên viên · mức độ quan tâm · kênh · nhắc lịch · chi tiết",
        "en": "Enquiry date · officer · interest · channel · follow-up · note",
    },
    "admissions.crm_activities": {
        "vi": "Sự kiện tham gia · thời gian · chương trình · chi tiết",
        "en": "Event attended · time · program · note",
    },
    "admissions.crm_reminders": {
        "vi": "Nhắc lịch · họ tên · điện thoại · email · chương trình · mức độ quan tâm",
        "en": "Follow-up · name · mobile · email · program · interest",
    },
    "admissions.crm_reports": {
        "vi": "Mức quan tâm và phễu Apply → Enroll theo chương trình",
        "en": "Interest level and Apply → Enroll funnel by program",
    },
    "admissions.events": {
        "vi": "Trước: mời đăng ký · Trong: tư vấn · Sau: cập nhật mức quan tâm",
        "en": "Before: invite · During: advise · After: update interest",
    },
    "admissions.neu_prep": {
        "vi": "Thanh tra Pháp chế · Khảo thí (TA) · văn bản NEU · nộp HTQT",
        "en": "Legal inspection · English evidence · NEU letters · international office",
    },
    "accounting.fees": {
        "vi": "Hồ sơ Đỗ → phí ghi danh chờ thu → Kế toán xác nhận đã thu · Tuyển sinh chỉ xem",
        "en": "Passed file → enrollment fee waiting → Accounting confirms payment · Admissions only watches",
    },
    "accounting.official_list": {
        "vi": "Đã thu → chốt chính thức → hồ sơ theo học (Chờ xếp lớp) → cấp mã và xếp lớp",
        "en": "Paid → mark official → programme file (waiting for a class) → assign the code and place the class",
    },
    "accounting.charges": {
        "vi": "Ghi nhận thanh toán. Học bổng, giảm phí và hoàn là đề nghị, người khác duyệt.",
        "en": "Record a payment. Scholarship, discount and refund stay proposals until another person approves.",
    },
    "accounting.benefits": {
        "vi": "Đề nghị → người khác duyệt → giảm nghĩa vụ hoặc chi ra tài khoản",
        "en": "Propose → another person approves → reduce the fee or pay out",
    },
    "accounting.refunds": {
        "vi": "Đề nghị → duyệt → chi. Đã duyệt chưa phải đã hoàn tiền.",
        "en": "Propose → approve → pay out. Approved is not the same as paid.",
    },
    "accounting.billing_profiles": {
        "vi": "Cá nhân hoặc doanh nghiệp. MST và CCCD giữ số 0 đầu.",
        "en": "Person or company. Tax code and ID keep a leading zero.",
    },
    "accounting.intake_plans": {
        "vi": "Biểu phí theo khóa, đơn vị VND. Nhập học chính thức sinh khoản phải thu, không tạo đợt trùng.",
        "en": "Intake fee plan in VND. Official enrollment creates the charges and skips installments that already exist.",
    },
    "accounting.tuition_tracker": {
        "vi": "Theo dõi nộp học phí từng HV — sắp hạn / quá hạn",
        "en": "Track each student’s tuition: due soon / overdue",
    },
    "accounting.fee_alerts": {
        "vi": "Cảnh báo hạn nộp & số khoản trễ — chỉnh ngưỡng",
        "en": "Alerts for due dates and overdue counts — adjustable thresholds",
    },
    "accounting.candidate_files": {
        "vi": "Nghĩa vụ lệ phí thi · miễn · phiếu thu · chỉ Kế toán xác nhận đã thu",
        "en": "Exam-fee obligation · waiver · receipt · only Accounting confirms payment",
    },
    "accounting.collection_report": {
        "vi": "Tổng đã thu (kể cả miễn) · còn nợ · theo loại phí",
        "en": "Collected (incl. waived) · outstanding · by fee type",
    },
    "programs.structure": {
        "vi": "Copy phiên bản (MMS Khóa 20→21, MBA K34→K35)",
        "en": "Copy a version (MMS Cohort 20→21, MBA K34→K35)",
    },
    "programs.courses": {
        "vi": "Syllabus; 8 buổi (MMS/MBA) / 7+2 (MSCM)",
        "en": "Syllabus; 8 sessions (MMS/MBA) / 7+2 (MSCM)",
    },
    "classes.manage": {
        "vi": "Cohort + version → welcome email → Canvas",
        "en": "Cohort + version → welcome email → Canvas",
    },
    "students.manage": {
        "vi": "Financial + Academic · học bổng / bảo lưu / IAE",
        "en": "Financial + academic · scholarship / deferral / IAE",
    },
    "students.academic": {
        "vi": "Học viên gốc · bảng điểm · tiến độ so với chương trình",
        "en": "Learner record · transcript · progress versus the programme",
    },
    "student.progress": {
        "vi": "In bảng điểm và báo cáo môn đã học / sắp học",
        "en": "Print transcript and completed / upcoming courses",
    },
    "teaching.faculty": {
        "vi": "HĐ/trả điểm/CFVG · vé/KS → Quốc tế/Trợ lý",
        "en": "Contract/grades/CFVG · flight/hotel → Intl / Assistant",
    },
    "teaching.assign": {
        "vi": "Proposed → Confirmed → In Teaching",
        "en": "Proposed → confirmed → in teaching",
    },
    "teaching.schedule": {
        "vi": "Lịch học → Logistics / GV QT",
        "en": "Class timetable → logistics / visiting faculty",
    },
    "teaching.materials": {
        "vi": "Upload tài liệu theo buổi",
        "en": "Upload materials by session",
    },
    "teaching.groups": {
        "vi": "Nhóm học tập theo môn",
        "en": "Study groups by course",
    },
    "teaching.attendance": {
        "vi": "2 lần/buổi · vắng >30% → email + không ĐK thi",
        "en": "Twice per session · >30% absence → email + exam block",
    },
    "teaching.assignments": {
        "vi": "Giao BT thực hành / trắc nghiệm theo lớp–môn; import mẫu; HV làm online",
        "en": "Practice / MC by class–course; import templates; students complete online",
    },
    "student.practice": {
        "vi": "Làm bài thực hành / trắc nghiệm online theo bài đã mở",
        "en": "Complete published practice / MC assignments online",
    },
    "teaching.grades": {
        "vi": "Draft → Approved → Locked",
        "en": "Draft → approved → locked",
    },
    "teaching.exams": {
        "vi": "Đề thi / thi lại / khiếu nại điểm",
        "en": "Exam papers / retakes / grade appeals",
    },
    "teaching.evaluation": {
        "vi": "≥60% QL · ≥80% GV (24h)",
        "en": "≥60% management · ≥80% faculty (24h)",
    },
    "teaching.thesis": {
        "vi": "Topic → supervisor → defense",
        "en": "Topic → supervisor → defense",
    },
    "alumni.members": {
        "vi": "Alumni sau graduation",
        "en": "Alumni after graduation",
    },
    "alumni.events": {
        "vi": "Tạo sự kiện → lọc đối tượng → gửi lời mời",
        "en": "Create event → filter audience → send invitations",
    },
    "reports.dashboard": {
        "vi": "Analytics theo scope CT",
        "en": "Analytics by program scope",
    },
    "marcom.leads": {
        "vi": "Tiếp nhận → hồ sơ chung → bàn giao tuyển sinh",
        "en": "Capture → shared profile → hand to Admissions",
    },
    "marcom.events": {
        "vi": "Duyệt ngân sách → tổ chức → báo cáo sau sự kiện",
        "en": "Approve budget → run event → post-event report",
    },
    "marcom.campaigns": {
        "vi": "Kế hoạch → KT duyệt → BGD duyệt → đối soát",
        "en": "Plan → Accounting approval → Board approval → reconcile",
    },
    "marcom.assets": {
        "vi": "Nội dung / thiết kế → nghiệm thu → lịch phát hành",
        "en": "Content / design → acceptance → publish schedule",
    },
    "marcom.reports": {
        "vi": "Báo cáo tháng, quý, nửa năm, năm cho BGD",
        "en": "Monthly, quarterly, half-year and annual report for the Board",
    },
    "canvas.coordinator": {
        "vi": "Xuất gói lớp (Users / Courses / Enrollments) lên Canvas",
        "en": "Export class packages (Users / Courses / Enrollments) to Canvas",
    },
}

# Optional English descriptions for workspace cards (fallback: keep VI)
MODULE_DESC_EN = {
    "admissions.rounds": "Create admission rounds (MBA May/Aug…); open/close intake; exam & interview timelines.",
    "admissions.applications": "Receive dossier; upload language cert, degree and one combined evidence PDF; TS approve → Program Admin.",
    "admissions.written_exams": "Export candidate list for written exam; Coordinator assigns SBD/scores.",
    "admissions.interviews": "Support interview boards; track no-shows (Coordinator schedules).",
    "admissions.results": "Candidate scores report; document completeness; notify pass/fail; remind missing docs.",
    "admissions.pre_enroll": "The same person, not yet a learner: candidate code, examinee confirmation, admit decision.",
    "admissions.enrolled_files": "Programme file after the decision takes effect: learner code, candidate code, may still be waiting for a class.",
    "admissions.round_docs": "Search documents by admission round; upload, preview and download.",
    "admissions.doc_types": "Declare document types used for admission-round files (regulations, announcements, reports, accreditation evidence).",
    "admissions.crm_source": "Enquiry file: enquiry date, officer, interest, program, year, channel, follow-up and note.",
    "admissions.crm_activities": "Events attended: name, time, program, and one care note per person.",
    "admissions.crm_reminders": "Follow-up date, name, mobile, email, program and interest level.",
    "admissions.crm_reports": "Enquiry report by interest level and Apply to Enroll funnel, by program.",
    "admissions.events": "Info Days and workshops: invite, advise on site, then update interest in the enquiry file.",
    "admissions.neu_prep": "Selected files for NEU: legal inspection, English evidence, issued letters, international office.",
    "accounting.fees": "Track enrollment fee after admission; Accounting confirms Deposit.",
    "accounting.official_list": "Officially enrolled list; export for NEU exam office; class handoff.",
    "marcom.leads": "Shared prospect profile with Admissions. ID number is not required at intake.",
    "marcom.events": "One event function. Budget is approved by Accounting then the Board before go-live.",
    "marcom.campaigns": "Campaign plan and budget. Actual cost comes from confirmed finance allocations.",
    "marcom.assets": "Content, design and channel schedule. Outsourced work waits for budget approval.",
    "marcom.reports": "Aggregated marketing, event and content figures for the Board. No re-keying.",
    "programs.structure": "Copy a programme version (MMS Cohort 20 → 21, MBA K34 → K35).",
    "programs.courses": "Courses by semester; MMS and MBA use 8 sessions.",
    "classes.manage": "Cohort/class from official list; welcome email; Canvas sync.",
    "students.manage": "Student list: scholarship types + academic lifecycle.",
    "students.academic": "Learner is the root record, linked to the original application, grades and progress.",
    "student.progress": "Transcript and progress against the programme the learner is following.",
    "teaching.schedule": "Class schedule: session, room, lecturer, change status.",
    "teaching.faculty": "Faculty: CFVG history, contract/payment, grade return; travel via Assistant.",
    "teaching.assign": "Assign lecturers/experts; generate sessions.",
    "teaching.class_lessons": "Class–course lesson plans and materials.",
    "teaching.materials": "Upload/share materials by session.",
    "teaching.groups": "Student groups by course.",
    "teaching.attendance": "Dual attendance (manual + in-class rotating QR); >30% blocks exam.",
    "teaching.assignments": "Practice & MC quizzes by class–course; import templates; students complete online.",
    "student.practice": "Complete published practice / multiple-choice assignments online.",
    "teaching.grades": "Gradebook, weights, lock, print.",
    "teaching.exams": "Exams, retakes, grade appeals.",
    "teaching.evaluation": "≥60% send to management; ≥80% send to faculty.",
    "teaching.thesis": "Thesis assignment and supervisors.",
    "asst.intl_students": "Exchange In/Out; visa→Assistant, IAE→Accounting, courses→Coordinator.",
    "asst.exec_tasks": "Board tasks from meetings: assignee, deadline, progress.",
    "asst.calendar": "Board / meeting / teaching / leave calendar.",
    "asst.intl_faculty": "Visiting faculty logistics: passport, visa, flight, hotel, pickup.",
    "asst.director_fr": "French Director & family: visa, work permit, residence.",
    "asst.documents": "Incoming/outgoing correspondence: number, seal, issue.",
    "asst.procurement": "Purchase requests, invoices and payment follow-up.",
    "asst.payments": "Monthly contract and payment tracking.",
    "asst.weekly_report": "Weekly department summary for Board / NEU.",
    "asst.leave": "Staff leave requests, approval and calendar sync.",
    "accounting.charges": "Student charges / receivables after enrollment.",
    "accounting.tuition_tracker": "Per-student tuition status: paid, due soon, overdue.",
    "accounting.fee_alerts": "Automatic tuition alerts (due soon, overdue, many late items) with editable thresholds.",
    "accounting.candidate_files": "Accounting candidate files: fees, waiver, two linked tables, document types, search by round, upload.",
    "accounting.collection_report": "Collection report: total collected including waived cases, outstanding balances, by fee type and period.",
    "accounting.fee_types": "Declare fee codes and default amounts (including entrance exam fee).",
    "teaching.lessons": "Class–course lesson plans, files and student preview.",
    "teaching.online_lectures": "Create and schedule online lectures (file or link); student Q&A.",
    "teaching.objectives": "Derive learning objectives and steps from the syllabus.",
    "teaching.instructor_intel": "Class watch time, unanswered questions, at-risk students.",
    "teaching.student_tracker": "Per-student watch minutes and progress.",
    "teaching.exam_integrity": "Exam sitting identity checklist (ID / selfie / honor pledge).",
    "teaching.return_meetings": "Meetings for students on leave or reserved.",
    "student.study_plan": "Personal study plan from remaining topics.",
    "student.time_to_learn": "Estimated minutes left per topic from watch progress.",
    "student.objective_recs": "Recommended objectives and how to reach them.",
    "student.agenda": "Weekly study slots from remaining time.",
    "student.return_meetings": "Return-to-class support meetings.",
    "student.library": "Released course materials for the signed-in student.",
    "student.lessons": "Published lessons for the signed-in student.",
    "student.profile": "Student profile, visa and enrollment data.",
    "student.schedule": "Personal class timetable.",
    "student.results": "Personal grades and exam results.",
    "canvas.coordinator": "Export class SIS packages (users / courses / enrollments) to Canvas.",
    "canvas.faculty": "Class–course on Canvas: materials, assignments, SpeedGrader.",
    "canvas.student": "Student Canvas login and published courses.",
    "canvas.accounting": "Canvas billing / SIS finance view.",
    "canvas.it": "Canvas IT operations and push status.",
    "alumni.members": "Alumni directory by cohort/program/class.",
    "alumni.events": "Alumni events and invitations.",
    "reports.dashboard": "Live KPIs and admissions-to-enrollment pipeline.",
}


def normalize_lang(lang: str | None) -> str:
    return "en" if (lang or "").lower().startswith("en") else "vi"


def t(key: str, lang: str | None = "vi", **kwargs) -> str:
    lang = normalize_lang(lang)
    entry = MESSAGES.get(key) or {}
    text = entry.get(lang) or entry.get("vi") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def L_pair(vi: str, en: str | None = None, lang: str | None = "vi") -> str:
    """Pick VI or EN chrome for templates: {{ L('Đóng', 'Close') }}."""
    if normalize_lang(lang) == "en":
        return en if en else translate_label(vi, "en")
    return vi


def status_label(code: str, lang: str | None, vi_map: dict | None = None) -> str:
    lang = normalize_lang(lang)
    if lang == "en":
        return STATUS_LABELS_EN.get(code) or (vi_map or {}).get(code) or code
    return (vi_map or {}).get(code) or code


def translate_label(text, lang: str | None = "en"):
    """Translate a Vietnamese UI string; pass through if already English / unknown."""
    if normalize_lang(lang) != "en" or text is None:
        return text
    s = str(text).strip()
    if not s:
        return text
    return LABEL_TEXT_EN.get(s) or s


def flow_group_label(prefix: str, lang: str | None) -> str:
    entry = FLOW_GROUPS.get(prefix) or {}
    lang = normalize_lang(lang)
    return entry.get(lang) or entry.get("vi") or prefix


def workflow_blurb(perm_code: str, lang: str | None) -> str:
    entry = WORKFLOWS.get(perm_code) or {}
    lang = normalize_lang(lang)
    return entry.get(lang) or entry.get("vi") or ""


def localize_pipeline(steps, lang: str | None):
    lang = normalize_lang(lang)
    out = []
    for step in steps or []:
        item = dict(step)
        code = str(item.get("code") or "")
        if lang == "en":
            item["label"] = (
                PIPELINE_EN.get(code)
                or STATUS_LABELS_EN.get(code)
                or item.get("label")
                or code
            )
        out.append(item)
    return out


def _localize_column(col, lang: str):
    if lang != "en":
        if isinstance(col, dict):
            return dict(col)
        return col
    if isinstance(col, dict):
        cc = dict(col)
        vi = cc.get("label") or ""
        key = cc.get("key")
        cc["label"] = LABEL_TEXT_EN.get(vi) or FIELD_LABELS_EN.get(key) or vi
        if cc.get("src_label_en"):
            cc["src_label"] = cc["src_label_en"]
        return cc
    if isinstance(col, (tuple, list)) and len(col) >= 2:
        key, vi = col[0], col[1]
        extra = list(col[2:])
        new_label = LABEL_TEXT_EN.get(vi) or FIELD_LABELS_EN.get(key) or vi
        return tuple([key, new_label] + extra)
    return col


def localize_columns(columns, lang: str | None):
    lang = normalize_lang(lang)
    return [_localize_column(c, lang) for c in (columns or [])]


def _localize_action_item(item, lang: str):
    if lang != "en":
        if isinstance(item, dict):
            return dict(item)
        return item
    if isinstance(item, dict):
        out = dict(item)
        aid = str(out.get("id") or "")
        label = str(out.get("label") or "")
        out["label"] = ACTION_BY_ID.get(aid) or LABEL_TEXT_EN.get(label) or label
        return out
    s = str(item)
    return ACTION_BY_ID.get(s) or LABEL_TEXT_EN.get(s) or s


def localize_module(cfg: dict, perm_code: str, lang: str | None) -> dict:
    """Apply selected-language labels to a module config (title, columns, actions…)."""
    lang = normalize_lang(lang)
    out = dict(cfg)
    # Always copy nested lists so EN localization never mutates OPS_MODULES.
    out["columns"] = [dict(c) if isinstance(c, dict) else c for c in (cfg.get("columns") or [])]
    if cfg.get("actions") is not None:
        out["actions"] = list(cfg.get("actions") or [])
    if cfg.get("row_buttons") is not None:
        out["row_buttons"] = [dict(b) if isinstance(b, dict) else b for b in (cfg.get("row_buttons") or [])]
    if cfg.get("row_actions") is not None:
        out["row_actions"] = [dict(a) if isinstance(a, dict) else a for a in (cfg.get("row_actions") or [])]
    if cfg.get("source_legend") is not None:
        out["source_legend"] = [dict(s) if isinstance(s, dict) else s for s in (cfg.get("source_legend") or [])]
    if isinstance(cfg.get("row_edit_action"), dict):
        out["row_edit_action"] = dict(cfg["row_edit_action"])
    if isinstance(cfg.get("primary_action"), dict):
        out["primary_action"] = dict(cfg["primary_action"])
    if isinstance(cfg.get("list_add_action"), dict):
        out["list_add_action"] = dict(cfg["list_add_action"])

    blur = workflow_blurb(perm_code, lang)
    if blur:
        out["workflow"] = blur

    if lang != "en":
        return out

    try:
        import sys
        from pathlib import Path

        be = Path(__file__).resolve().parent.parent / "backend"
        if str(be) not in sys.path:
            sys.path.insert(0, str(be))
        from rbac import menu_by_code

        m = menu_by_code().get(perm_code) or {}
        if m.get("label_en"):
            out["title"] = m["label_en"]
    except Exception:
        pass
    if MODULE_DESC_EN.get(perm_code):
        out["desc"] = MODULE_DESC_EN[perm_code]
    out["title_en"] = out.get("title")
    out["desc_en"] = out.get("desc")

    out["columns"] = localize_columns(out.get("columns"), lang)
    legend = []
    for item in out.get("source_legend") or []:
        if not isinstance(item, dict):
            legend.append(item)
            continue
        it = dict(item)
        if it.get("label_en"):
            it["label"] = it["label_en"]
        legend.append(it)
    if legend:
        out["source_legend"] = legend

    pa = out.get("primary_action")
    if isinstance(pa, dict):
        out["primary_action"] = _localize_action_item(pa, lang)
    elif pa:
        out["primary_action"] = translate_label(pa, lang)

    add = out.get("list_add_action")
    if isinstance(add, dict):
        lab = str(add.get("label") or "")
        add["label"] = LABEL_TEXT_EN.get(lab) or translate_label(lab, lang) or lab
        out["list_add_action"] = add

    if out.get("actions") is not None:
        out["actions"] = [_localize_action_item(a, lang) for a in out["actions"]]

    buttons = []
    for b in out.get("row_buttons") or []:
        if isinstance(b, dict):
            bb = dict(b)
            bid = str(bb.get("id") or "")
            lab = str(bb.get("label") or "")
            bb["label"] = BUTTON_BY_ID.get(bid) or LABEL_TEXT_EN.get(lab) or lab
            buttons.append(bb)
        else:
            buttons.append(b)
    if buttons:
        out["row_buttons"] = buttons

    actions = []
    for a in out.get("row_actions") or []:
        if isinstance(a, dict):
            aa = dict(a)
            lab = str(aa.get("label") or "")
            aa["label"] = LABEL_TEXT_EN.get(lab) or lab
            actions.append(aa)
        else:
            actions.append(a)
    if actions:
        out["row_actions"] = actions

    rea = out.get("row_edit_action")
    if isinstance(rea, dict):
        bid = str(rea.get("id") or "")
        lab = str(rea.get("label") or "")
        rea["label"] = BUTTON_BY_ID.get(bid) or LABEL_TEXT_EN.get(lab) or lab
        out["row_edit_action"] = rea

    return out
