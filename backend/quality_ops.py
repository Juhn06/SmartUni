"""Rà soát đầy đủ / chính xác dữ liệu ops — đánh dấu thiếu sót và đề xuất cập nhật."""
from __future__ import annotations

import re

from ops_crud import queue_email

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[\d\s+\-().]{8,20}$")
GPA_RE = re.compile(r"^\d+([.,]\d+)?$")
_ADMIT_PACKET_STATUSES = frozenset(
    {"passed", "paid", "official", "approved_ts", "interview"}
)
_TRUTH = frozenset({"yes", "1", "ok", "verified", "true", "ready"})


def _blank(v) -> bool:
    return v is None or str(v).strip() in ("", "—", "-", "None", "null")


def _email_ok(v) -> bool:
    s = str(v or "").strip()
    return bool(s) and bool(EMAIL_RE.match(s))


def _phone_ok(v) -> bool:
    s = str(v or "").strip()
    digits = re.sub(r"\D", "", s)
    return len(digits) >= 8 and bool(PHONE_RE.match(s))


def _gpa_value(row: dict):
    return row.get("degree_grade") or row.get("gpa") or row.get("avg_score")


def _gpa_ok(v) -> bool:
    if _blank(v):
        return False
    s = str(v).strip().replace(",", ".")
    if GPA_RE.match(s):
        try:
            x = float(s)
            return 0 <= x <= 10
        except ValueError:
            return False
    return True


def _pic_of(row: dict) -> str:
    for k in (
        "owner",
        "assignee",
        "handler",
        "created_by",
        "admission_owner",
        "requester",
        "approver",
        "actor",
        "lecturer",
    ):
        if not _blank(row.get(k)):
            return str(row.get(k)).strip()
    return ""


def _truthy(v) -> bool:
    return str(v or "").strip().lower() in _TRUTH


def _dossier_flags(row: dict, *, packet: bool = False) -> list[dict]:
    flags = []
    if _blank(row.get("english_cert") or row.get("english_file")):
        flags.append(_issue("Thiếu chứng chỉ ngoại ngữ", "Upload file CC NN hoặc ghi tên chứng chỉ."))
    if _blank(row.get("degree_file")):
        flags.append(_issue("Thiếu bảng điểm / bằng ĐH", "Upload file bằng đại học / bảng điểm."))
    other = row.get("other_file") or row.get("has_other_doc")
    docs = int(row.get("doc_count") or 0)
    if _blank(other) or str(other).lower() in ("no", "0"):
        flags.append(
            _warn("Thiếu thư giới thiệu / minh chứng khác", "Bổ sung PDF thư giới thiệu hoặc minh chứng.")
            if packet
            else _warn("Hồ sơ giấy tờ chưa đủ", "Bổ sung thư giới thiệu / minh chứng khác nếu yêu cầu.")
        )
    elif docs < 2:
        flags.append(_warn("Hồ sơ giấy tờ chưa đủ", "Cần ít nhất bảng điểm và chứng chỉ ngoại ngữ."))
    if packet:
        if not _truthy(row.get("degree_verified")):
            flags.append(_warn("Văn bằng chưa xác nhận", "Đánh dấu degree_verified trước khi nộp Thanh tra / HTQT."))
        if not _truthy(row.get("english_verified")):
            flags.append(_warn("CC NN chưa xác nhận", "Đánh dấu english_verified trước khi nộp Thanh tra / HTQT."))
        ready = str(row.get("neu_packet_ready") or "").strip().lower()
        if ready in ("", "pending", "no", "0"):
            flags.append(
                _warn("Gói hồ sơ NEU chưa sẵn sàng", "Đánh dấu neu_packet_ready trước khi nộp Thanh tra Pháp chế / HTQT.")
            )
    return flags


def _issue(msg: str, suggest: str) -> dict:
    return {"level": "issue", "msg": msg, "suggest": suggest}


def _warn(msg: str, suggest: str) -> dict:
    return {"level": "warn", "msg": msg, "suggest": suggest}


def _contact_flags(row: dict, *, name_key="full_name") -> list[dict]:
    flags = []
    if _blank(row.get(name_key) or row.get("title")):
        flags.append(_issue("Thiếu họ tên", "Cập nhật họ tên đầy đủ."))
    email = row.get("email")
    if _blank(email):
        flags.append(_issue("Thiếu email", "Nhập địa chỉ email liên hệ."))
    elif not _email_ok(email):
        flags.append(_warn("Email không hợp lệ", f"Sửa định dạng email ({email})."))
    phone = row.get("phone")
    if _blank(phone):
        flags.append(_warn("Thiếu số điện thoại", "Bổ sung SĐT để gọi/nhắc."))
    elif not _phone_ok(phone):
        flags.append(_warn("SĐT không hợp lệ", "Kiểm tra lại số điện thoại."))
    return flags


def check_crm(row: dict) -> list[dict]:
    flags = _contact_flags(row)
    if _blank(row.get("program_interest") or row.get("program_code")):
        flags.append(_issue("Thiếu ngành/CT quan tâm", "Chọn MBA / MMS / MSCM."))
    if _blank(row.get("dob") or row.get("birth_date")):
        flags.append(_warn("Thiếu ngày sinh", "Nhập ngày sinh trên hồ sơ nguồn."))
    care = str(row.get("care_status") or "")
    contacts = int(row.get("contact_count") or row.get("care_log_count") or 0)
    if care in ("consulting", "interested", "applicant") and contacts < 1:
        flags.append(_warn("Chưa có nhật ký giao tiếp", "Ghi cuộc gọi/email/Info Day vào nhật ký chăm sóc."))
    gpa = _gpa_value(row)
    if care in ("applicant", "interested") and _blank(gpa):
        flags.append(_warn("Thiếu GPA trên hồ sơ nguồn", "Ghi GPA nếu ứng viên đã cung cấp."))
    return flags


def check_crm_activity(row: dict) -> list[dict]:
    flags = check_generic_schedule(row)
    if _blank(row.get("activity_type") or row.get("event_type")):
        flags.append(_warn("Thiếu loại hoạt động", "Chọn tư vấn / hội thảo / Info Day."))
    if int(row.get("participant_count") or 0) < 1:
        flags.append(_warn("Chưa có người tham gia", "Chọn hồ sơ nguồn để follow-up."))
    if _blank(row.get("notes")) and str(row.get("status") or "") in ("done", "completed"):
        flags.append(_warn("Thiếu nhật ký giao tiếp", "Ghi cuộc gọi / email / trao đổi trực tuyến."))
    return flags


def check_application(row: dict) -> list[dict]:
    flags = _contact_flags(row)
    if _blank(row.get("program_code")):
        flags.append(_issue("Thiếu chương trình", "Gán MBA / MMS / MSCM."))
    if _blank(row.get("dob")):
        flags.append(_warn("Thiếu ngày sinh", "Cập nhật ngày sinh trên hồ sơ."))
    gpa = _gpa_value(row)
    if _blank(gpa):
        flags.append(_warn("Thiếu GPA / xếp loại bằng", "Nhập điểm GPA hoặc xếp loại tốt nghiệp."))
    elif not _gpa_ok(gpa):
        flags.append(_warn("GPA không hợp lệ", f"Kiểm tra lại điểm ({gpa}) — dùng thang 0–10 hoặc xếp loại."))
    if _blank(row.get("experience_years") or row.get("work_exp") or row.get("work_experience")):
        flags.append(_warn("Thiếu kinh nghiệm làm việc", "Nhập số năm KN (0 nếu chưa có)."))
    st = str(row.get("status") or "").lower()
    packet = st in ("passed", "paid", "official") or _truthy(row.get("neu_packet_ready"))
    flags.extend(_dossier_flags(row, packet=packet or st in _ADMIT_PACKET_STATUSES))
    chk = str(row.get("checklist_status") or "pending").lower()
    if chk in ("", "pending"):
        flags.append(_warn("Chưa phát hành checklist", "Issue checklist và phản hồi chất lượng hồ sơ."))
    return flags


def check_written_exam(row: dict) -> list[dict]:
    flags = _contact_flags(row)
    if _blank(row.get("program_code")):
        flags.append(_issue("Thiếu ngành/CT", "Gán chương trình trước khi gửi Admin CT."))
    if _blank(row.get("dob")):
        flags.append(_warn("Thiếu ngày sinh", "Bổ sung DOB trên danh sách dự thi."))
    gpa = _gpa_value(row)
    if _blank(gpa):
        flags.append(_warn("Thiếu GPA", "Điền GPA trước khi bàn giao Admin CT."))
    elif not _gpa_ok(gpa):
        flags.append(_warn("GPA không hợp lệ", f"Sửa GPA ({gpa}) trên hồ sơ trước khi gửi danh sách."))
    if _blank(row.get("written_exam_date") or row.get("exam_date")):
        flags.append(_issue("Thiếu ngày thi", "Cập nhật lịch thi viết."))
    if _blank(row.get("written_exam_room") or row.get("room")):
        flags.append(_warn("Thiếu phòng thi", "Gán phòng/ca trước khi gửi thông báo."))
    if _blank(row.get("written_exam_no")):
        flags.append(_warn("Chưa có SBD", "Gán số báo danh."))
    if _blank(_pic_of(row)) and _blank(row.get("written_exam_session")):
        flags.append(_warn("Thiếu người phụ trách / ca thi", "Gán ca thi hoặc PIC buổi thi."))
    return flags


def check_interview(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("title")):
        flags.append(_issue("Thiếu tên buổi PV", "Đặt tên board / buổi phỏng vấn."))
    if _blank(row.get("starts_at")):
        flags.append(_issue("Thiếu thời gian", "Nhập ngày giờ phỏng vấn."))
    if _blank(row.get("room") or row.get("location")):
        flags.append(_warn("Thiếu địa điểm", "Ghi phòng / địa điểm PV."))
    if _blank(_pic_of(row)):
        flags.append(_warn("Thiếu người phụ trách", "Gán PIC buổi PV (Điều phối / Admin CT)."))
    if int(row.get("slot_count") or 0) < 1:
        flags.append(_warn("Chưa có thí sinh trong board", "Gán slot thí sinh."))
    return flags


def check_generic_schedule(row: dict, *, title="title") -> list[dict]:
    flags = []
    if _blank(row.get(title) or row.get("full_name") or row.get("item_name") or row.get("subject")):
        flags.append(_issue("Thiếu tên", "Cập nhật tiêu đề / họ tên."))
    if _blank(
        row.get("starts_at")
        or row.get("event_date")
        or row.get("due_date")
        or row.get("start_date")
        or row.get("scheduled_at")
        or row.get("lesson_date")
        or row.get("exam_date")
        or row.get("ends_at")
    ):
        flags.append(_warn("Thiếu thời gian", "Nhập ngày/giờ."))
    if _blank(row.get("location") or row.get("room")):
        flags.append(_warn("Thiếu địa điểm", "Nhập địa điểm nếu đã chốt."))
    if _blank(_pic_of(row)) and (
        row.get("owner") is not None or row.get("assignee") is not None or row.get("handler") is not None
    ):
        flags.append(_warn("Thiếu người phụ trách", "Gán PIC / owner."))
    return flags


def check_lead(row: dict) -> list[dict]:
    flags = _contact_flags(row)
    if _blank(row.get("program_interest") or row.get("program_code")):
        flags.append(_warn("Thiếu CT quan tâm", "Ghi MBA/MMS/MSCM."))
    return flags


def check_campaign(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("title")):
        flags.append(_issue("Thiếu tên chiến dịch", "Đặt tên chiến dịch."))
    if _blank(row.get("budget_planned") or row.get("budget")):
        flags.append(_warn("Thiếu ngân sách", "Nhập NS kế hoạch online/offline."))
    if _blank(row.get("kpi_notes") or row.get("report_summary")):
        flags.append(_warn("Thiếu KPI / báo cáo BGD", "Điền KPI và tóm tắt tháng/quý/năm."))
    if _blank(row.get("period_start") or row.get("period_end")):
        flags.append(_warn("Thiếu kỳ chiến dịch", "Nhập thời gian bắt đầu / kết thúc."))
    return flags


def check_event(row: dict) -> list[dict]:
    flags = check_generic_schedule(row)
    if _blank(row.get("event_date") or row.get("starts_at")):
        flags.append(_issue("Thiếu ngày sự kiện", "Nhập ngày Info Day / workshop."))
    return flags


def check_task(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("title")):
        flags.append(_issue("Thiếu tên nhiệm vụ", "Nhập nội dung nhiệm vụ."))
    if _blank(row.get("assignee")):
        flags.append(_warn("Thiếu người phụ trách", "Gán người thực hiện."))
    if _blank(row.get("due_date")):
        flags.append(_warn("Thiếu hạn", "Đặt deadline."))
    return flags


def check_document(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("subject") or row.get("title")):
        flags.append(_issue("Thiếu trích yếu", "Nhập trích yếu công văn."))
    if _blank(row.get("handler")):
        flags.append(_warn("Thiếu người xử lý", "Gán người phụ trách."))
    return flags


def check_procurement(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("item_name") or row.get("title")):
        flags.append(_issue("Thiếu tên hàng/DV", "Nhập sản phẩm."))
    if _blank(row.get("requester") or row.get("assignee")):
        flags.append(_warn("Thiếu người đề xuất", "Ghi người phụ trách."))
    return flags


def check_payment(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("beneficiary") or row.get("item_name") or row.get("cost_type")):
        flags.append(_issue("Thiếu tên khoản / sản phẩm", "Nhập tên khoản chi (vé máy bay, taxi, VP phẩm…)."))
    if row.get("amount") in (None, "", 0, "0"):
        flags.append(_warn("Thiếu số tiền", "Nhập số tiền hóa đơn."))
    return flags


def check_leave(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("employee_name")):
        flags.append(_issue("Thiếu tên nhân viên", "Nhập người nghỉ."))
    if _blank(row.get("start_date")):
        flags.append(_issue("Thiếu thời gian nghỉ", "Nhập ngày bắt đầu."))
    return flags


def check_weekly(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("week_label")):
        flags.append(_issue("Thiếu nhãn tuần", "Nhập tuần báo cáo."))
    if _blank(row.get("done_summary")):
        flags.append(_warn("Thiếu hoạt động đã làm", "Tổng hợp tên bộ phận và số lượng hoạt động."))
    blob = f"{row.get('done_summary') or ''} {row.get('ongoing_summary') or ''}"
    if blob.strip() and len(blob.strip()) < 20:
        flags.append(_warn("Tóm tắt hoạt động quá ngắn", "Ghi rõ bộ phận và số hoạt động trong tuần."))
    return flags


def check_director_fr(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("full_name")):
        flags.append(_issue("Thiếu họ tên", "Nhập tên thành viên GĐ Pháp / gia đình."))
    if _blank(row.get("passport_expiry")) and _blank(row.get("doc_expiry")):
        flags.append(_warn("Thiếu hạn giấy tờ", "Nhập hết hạn hộ chiếu / visa / cư trú."))
    return flags


def check_alumni(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("full_name")):
        flags.append(_issue("Thiếu họ tên", "Cập nhật tên cựu học viên."))
    if _blank(row.get("program_code")):
        flags.append(_warn("Thiếu ngành/CT", "Gán chương trình / khóa / lớp."))
    email = row.get("email")
    if not _blank(email) and not _email_ok(email):
        flags.append(_warn("Email không hợp lệ", f"Sửa email trước khi gửi lời mời ({email})."))
    return flags


def check_alumni_event(row: dict) -> list[dict]:
    return check_event(row)


def check_student_profile(row: dict) -> list[dict]:
    flags = _contact_flags(row)
    if _blank(row.get("dob")):
        flags.append(_warn("Thiếu ngày sinh", "Cập nhật ngày sinh trên hồ sơ."))
    return flags


def check_charge(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("full_name")):
        flags.append(_issue("Thiếu tên HV", "Gắn khoản thu với học viên."))
    if row.get("amount_due") in (None, ""):
        flags.append(_warn("Thiếu số tiền", "Nhập phải nộp."))
    try:
        remaining = float(row.get("remaining") or 0)
    except (TypeError, ValueError):
        remaining = 0
    if remaining > 0 and _blank(row.get("student_proof_note")):
        flags.append(_warn("Chưa có minh chứng HV", "HV gửi minh chứng; kế toán mới xác nhận đã thu."))
    return flags


def check_canvas_row(row: dict) -> list[dict]:
    flags = []
    if row.get("action") or (row.get("detail") is not None and row.get("audience") is not None):
        if _blank(row.get("detail")):
            flags.append(_warn("Thiếu chi tiết sync", "Ghi tên HV / môn học trong nhật ký SIS."))
        blob = f"{row.get('detail') or ''} {row.get('action') or ''}".lower()
        if blob.strip() and ("user" in (row.get("action") or "").lower() or "enroll" in blob) and _blank(row.get("full_name")):
            if "—" in str(row.get("detail") or "") or len(str(row.get("detail") or "")) < 4:
                flags.append(_warn("Thiếu tên học viên trên map SIS", "Bổ sung tên HV trước khi đánh dấu đã đẩy."))
        if _blank(row.get("created_at")):
            flags.append(_warn("Thiếu thời điểm sync", "Ghi thời gian nhật ký Canvas."))
        return flags
    name = row.get("full_name") or row.get("name") or row.get("class_name") or row.get("title")
    course = (
        row.get("course_name")
        or row.get("course_code")
        or row.get("sis_course_id")
        or row.get("syllabus")
        or row.get("released_files")
    )
    if _blank(name):
        flags.append(_warn("Thiếu tên HV / lớp", "Kiểm tra roster SIS / enroll."))
    if _blank(course) and _blank(row.get("sync_label")) and _blank(row.get("access")):
        flags.append(_warn("Thiếu môn học / giáo trình", "Bổ sung map SIS hoặc file đã release."))
    try:
        ready = int(row.get("courses_ready") or 0)
        total = int(row.get("courses_total") or 0)
    except (TypeError, ValueError):
        ready, total = 0, 0
    if total and ready < 1:
        flags.append(_warn("Chưa enroll Canvas", "Điều phối xuất lớp; IT đánh dấu đã đẩy."))
    if _blank(row.get("sis_course_id") or row.get("sync_status") or row.get("sync_label") or row.get("access")):
        if not _blank(name) and _blank(course):
            flags.append(_warn("Thiếu SIS / trạng thái sync", "Map course và nhật ký sync Canvas."))
    return flags


def check_user(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("name") or row.get("full_name")):
        flags.append(_issue("Thiếu họ tên user", "Cập nhật tên hiển thị."))
    email = row.get("email") or row.get("login")
    if _blank(email):
        flags.append(_issue("Thiếu login/email", "Gán địa chỉ đăng nhập."))
    elif not _email_ok(email) and "@" in str(email):
        flags.append(_warn("Email không hợp lệ", f"Sửa login ({email})."))
    depts = row.get("departments") or []
    if not depts:
        flags.append(_warn("Chưa gán bộ phận", "Gán ít nhất một bộ phận."))
    if row.get("is_locked") in (1, True, "1") and row.get("is_admin") in (1, True, "1"):
        flags.append(_warn("Admin đang bị khóa", "Mở khóa hoặc bỏ quyền admin."))
    scopes = row.get("program_scopes") or []
    if not scopes and row.get("is_admin") not in (1, True, "1"):
        flags.append(_warn("Chưa gán scope CT", "Gán MBA / MMS / MSCM (hoặc *) theo user."))
    return flags


def check_department(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("name") or row.get("code")):
        flags.append(_issue("Thiếu tên/mã bộ phận", "Đặt tên bộ phận."))
    try:
        n = int(row.get("member_count") or 0)
    except (TypeError, ValueError):
        n = 0
    if n < 1:
        flags.append(_warn("Chưa có thành viên", "Gán user vào bộ phận."))
    return flags


def check_suggestion(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("body") or row.get("title") or row.get("message")):
        flags.append(_issue("Thiếu nội dung phản hồi", "Nhập nội dung đề xuất."))
    if _blank(row.get("user_name") or row.get("user_email")):
        flags.append(_warn("Thiếu người gửi", "Ghi tên / email người gửi."))
    return flags


def check_status_item(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("code") or row.get("value")):
        flags.append(_issue("Thiếu mã trạng thái", "Nhập mã."))
    if _blank(row.get("label") or row.get("label_vi") or row.get("name")):
        flags.append(_warn("Thiếu mô tả", "Nhập nhãn hiển thị."))
    return flags


def check_audit(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("created_at") or row.get("at")):
        flags.append(_issue("Thiếu thời gian", "Ghi thời điểm thao tác."))
    if _blank(row.get("actor") or row.get("user_name")):
        flags.append(_warn("Thiếu người thực hiện", "Ghi actor / user."))
    return flags


def check_material(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("course_name") or row.get("title") or row.get("course_code") or row.get("name")):
        flags.append(_issue("Thiếu tên môn / bài", "Kiểm tra học phần đã công bố."))
    files = row.get("released_files") or row.get("has_file") or row.get("file_name") or row.get("syllabus_note") or row.get("reading_list")
    if files in (None, "", 0, "0", False) and not row.get("has_file"):
        flags.append(_warn("Thiếu giáo trình / file release", "Release tài liệu trước khi HV tải."))
    return flags


def check_student_result(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("full_name")):
        flags.append(_issue("Thiếu họ tên", "Cập nhật hồ sơ học viên."))
    if _blank(row.get("program_code")):
        flags.append(_warn("Thiếu ngành học", "Gán chương trình trên hồ sơ."))
    gpa = _gpa_value(row)
    if _blank(gpa) and _blank(row.get("written_score") or row.get("interview_score") or row.get("detail")):
        flags.append(_warn("Thiếu GPA / điểm", "Cập nhật GPA hoặc điểm thi/PV khi đã mở."))
    return flags


def check_admin_stat(row: dict) -> list[dict]:
    flags = []
    if row.get("users_count") in (None, ""):
        flags.append(_issue("Thiếu số lượng người dùng", "Kiểm tra thống kê tài khoản."))
    if row.get("applications_count") in (None, ""):
        flags.append(_warn("Thiếu số lượng hồ sơ", "Liên kết báo cáo tuyển sinh / applications."))
    return flags


def check_round(row: dict) -> list[dict]:
    flags = []
    if _blank(row.get("name") or row.get("code")):
        flags.append(_issue("Thiếu tên/mã đợt", "Đặt mã đợt TS."))
    if _blank(row.get("exam_timeline")) and _blank(row.get("exam_date")):
        flags.append(_warn("Thiếu timeline thi", "Nhập lịch thi viết."))
    if _blank(row.get("interview_timeline")):
        flags.append(_warn("Thiếu timeline PV", "Nhập lịch phỏng vấn."))
    return flags


CHECKERS = {
    "crm": check_crm,
    "application": check_application,
    "written_exam": check_written_exam,
    "interview": check_interview,
    "lead": check_lead,
    "campaign": check_campaign,
    "event": check_event,
    "calendar": lambda r: check_generic_schedule(r),
    "task": check_task,
    "document": check_document,
    "procurement": check_procurement,
    "payment": check_payment,
    "leave": check_leave,
    "weekly": check_weekly,
    "director_fr": check_director_fr,
    "alumni": check_alumni,
    "alumni_event": check_alumni_event,
    "student_profile": check_student_profile,
    "student_result": check_student_result,
    "charge": check_charge,
    "canvas": check_canvas_row,
    "round": check_round,
    "user": check_user,
    "department": check_department,
    "suggestion": check_suggestion,
    "status_item": check_status_item,
    "audit": check_audit,
    "material": check_material,
    "crm_activity": check_crm_activity,
    "admin_stat": check_admin_stat,
}


def attach(kind: str, row: dict) -> dict:
    fn = CHECKERS.get(kind)
    flags = fn(row) if fn else []
    issues = [f for f in flags if f["level"] == "issue"]
    warns = [f for f in flags if f["level"] == "warn"]
    if issues:
        status, label = "issue", "Thiếu"
    elif warns:
        status, label = "warn", "Cần cập nhật"
    else:
        status, label = "ok", "Đủ"
    out = dict(row)
    out["qa_status"] = status
    out["qa_label"] = label
    out["qa_flags"] = "; ".join(f["msg"] for f in flags[:4])
    out["qa_suggestions"] = " ".join(f["suggest"] for f in flags[:6])
    return out


def apply_qa(kind: str, rows: list[dict], qa: str = "") -> list[dict]:
    out = [attach(kind, r) for r in (rows or [])]
    if (qa or "").strip().lower() in ("issues", "1", "warn", "yes"):
        out = [r for r in out if r.get("qa_status") in ("issue", "warn")]
    return out


def _round_timelines(conn, program_code: str) -> tuple[str, str, str]:
    cur = conn.cursor()
    row = cur.execute(
        "SELECT name, IFNULL(exam_timeline,''), IFNULL(interview_timeline,''), IFNULL(exam_date,'') "
        "FROM admission_rounds WHERE status IN ('open','opening','active') "
        "AND (IFNULL(programs,'') LIKE ? OR IFNULL(program_code,'') = ?) "
        "ORDER BY id DESC LIMIT 1",
        (f"%{program_code or ''}%", program_code or ""),
    ).fetchone()
    if not row:
        row = cur.execute(
            "SELECT name, IFNULL(exam_timeline,''), IFNULL(interview_timeline,''), IFNULL(exam_date,'') "
            "FROM admission_rounds ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return ("", "", "")
    return (row[0] or "", row[1] or row[3] or "", row[2] or "")


def send_timeline_emails(conn, scopes: list[str] | None = None) -> dict:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    frag, params = _scopes_sql(scopes, "a.program_code")
    rows = cur.execute(
        "SELECT a.id, a.full_name, a.email, a.program_code, "
        "IFNULL(r.name,''), IFNULL(r.exam_timeline,''), IFNULL(r.interview_timeline,''), IFNULL(r.exam_date,'') "
        "FROM applications a LEFT JOIN admission_rounds r ON r.id = a.round_id "
        f"WHERE IFNULL(a.email,'') != '' AND {frag}",
        params,
    ).fetchall()
    n = 0
    for _aid, name, email, prog, rname, exam_tl, pv_tl, exam_date in rows:
        exam = exam_tl or exam_date or "theo thông báo đợt"
        pv = pv_tl or "theo thông báo đợt"
        gaps = []
        if not exam_tl and not exam_date:
            gaps.append("lịch thi chưa chốt trên đợt")
        if not pv_tl:
            gaps.append("lịch PV chưa chốt trên đợt")
        note = ("\nLưu ý: " + "; ".join(gaps)) if gaps else ""
        queue_email(
            conn,
            kind="admission_timeline",
            recipient=email,
            subject=f"[X] Thông tin chương trình & timeline tuyển sinh {prog}",
            body=(
                f"Kính gửi {name},\n\n"
                f"Chương trình: {prog}\n"
                f"Đợt: {rname or '—'}\n"
                f"Lịch thi viết: {exam}\n"
                f"Lịch phỏng vấn: {pv}\n"
                f"Hồ sơ cần: CV, bảng điểm/bằng ĐH, chứng chỉ ngoại ngữ, CCCD.\n"
                f"{note}\n\nX / CFVG"
            ),
        )
        n += 1
    return {"sent": n}


def issue_checklists(conn, scopes: list[str] | None = None) -> dict:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    frag, params = _scopes_sql(scopes, "a.program_code")
    rows = cur.execute(
        "SELECT a.id, a.full_name, a.email, a.program_code, "
        "IFNULL(a.english_cert,''), IFNULL(a.english_file,''), IFNULL(a.degree_file,''), "
        "IFNULL(a.doc_count,0), IFNULL(a.degree_grade,''), IFNULL(a.checklist_status,'') "
        "FROM applications a "
        f"WHERE IFNULL(a.email,'') != '' AND {frag} "
        "AND a.status IN ('submitted','approved_ts','interview','passed','paid')",
        params,
    ).fetchall()
    n = 0
    for aid, name, email, prog, eng, eng_file, deg_file, docs, gpa, _chk in rows:
        missing = []
        if not (eng or eng_file):
            missing.append("chứng chỉ ngoại ngữ")
        if not deg_file:
            missing.append("bảng điểm / bằng đại học")
        if not gpa:
            missing.append("GPA / xếp loại")
        if int(docs or 0) < 2:
            missing.append("thư giới thiệu / minh chứng khác")
        quality = "Hồ sơ đạt yêu cầu tối thiểu." if not missing else (
            "Cần bổ sung: " + ", ".join(missing) + "."
        )
        new_st = "confirmed" if not missing else "incomplete"
        try:
            cur.execute(
                "UPDATE applications SET checklist_status = ? WHERE id = ?",
                (new_st if not missing else "issued", aid),
            )
        except Exception:
            pass
        queue_email(
            conn,
            kind="dossier_checklist",
            recipient=email,
            subject=f"[CFVG] Application checklist — {prog}",
            body=(
                f"Dear {name},\n\n"
                f"{prog} — APPLICATION CHECKLIST\n"
                f"Status values: X | Incompleted | Exempted | Not required\n\n"
                f"- A notarized copy of the University Degree\n"
                f"- A notarized copy of the University Transcript\n"
                f"- A CV/Resume in English\n"
                f"- A letter of motivation\n"
                f"- A copy of an ID\n"
                f"- A letter of reference(s)\n"
                f"- Online Application on the website\n"
                f"- Language certificate\n"
                f"- Admission Fee\n"
                f"- VN-NARIC foreign degree recognition\n\n"
                f"Quality note: {quality}\n"
                f"Please complete missing items before the exam / interview deadline.\n\n"
                f"CFVG Admissions\n"
            ),
        )
        n += 1
        _ = new_st
    conn.commit()
    return {"sent": n}


def notify_exam_schedule(conn, scopes: list[str] | None = None) -> dict:
    from ops_data import _scopes_sql

    cur = conn.cursor()
    frag, params = _scopes_sql(scopes, "a.program_code")
    rows = cur.execute(
        "SELECT a.id, a.full_name, a.email, a.program_code, "
        "IFNULL(a.written_exam_date,''), IFNULL(a.written_exam_room,''), "
        "IFNULL(a.written_exam_session,''), IFNULL(a.written_exam_no,'') "
        f"FROM applications a WHERE IFNULL(a.email,'') != '' AND {frag} "
        "AND (IFNULL(a.exam_eligible_flag,'') IN ('1','yes','true','eligible','Y') "
        "OR a.status IN ('approved_ts','interview','submitted'))",
        params,
    ).fetchall()
    n = 0
    skipped = 0
    for _aid, name, email, prog, dt, room, session, sbd in rows:
        if not dt and not room:
            skipped += 1
            continue
        queue_email(
            conn,
            kind="exam_invite",
            recipient=email,
            subject=f"[X] Thông báo lịch thi viết — {prog}",
            body=(
                f"Kính gửi {name},\n\n"
                f"Lịch thi viết {prog}:\n"
                f"- Thời gian: {dt or 'sẽ thông báo'}\n"
                f"- Địa điểm / phòng: {room or '—'}\n"
                f"- Ca: {session or '—'}\n"
                f"- SBD: {sbd or 'sẽ gửi trước ngày thi'}\n\n"
                f"Vui lòng có mặt trước 15 phút.\n\nX / CFVG"
            ),
        )
        n += 1
    return {"sent": n, "skipped_incomplete": skipped}


def notify_interview_invites(conn, scopes: list[str] | None = None) -> dict:
    from ops_data import _scopes_sql, ensure_ops_tables

    cur = conn.cursor()
    ensure_ops_tables(cur)
    frag, params = _scopes_sql(scopes, "s.program_code")
    try:
        rows = cur.execute(
            "SELECT a.full_name, a.email, s.program_code, s.title, s.room, sl.scheduled_at, "
            "s.slot_minutes, IFNULL(s.owner,'') "
            "FROM interview_slots sl "
            "JOIN interview_sessions s ON s.id = sl.session_id "
            "JOIN applications a ON a.id = sl.application_id "
            f"WHERE IFNULL(a.email,'') != '' AND {frag}",
            params,
        ).fetchall()
    except Exception:
        rows = cur.execute(
            "SELECT a.full_name, a.email, s.program_code, s.title, s.room, sl.scheduled_at, "
            "s.slot_minutes, '' "
            "FROM interview_slots sl "
            "JOIN interview_sessions s ON s.id = sl.session_id "
            "JOIN applications a ON a.id = sl.application_id "
            f"WHERE IFNULL(a.email,'') != '' AND {frag}",
            params,
        ).fetchall()
    n = 0
    skipped = 0
    for name, email, prog, title, room, when, mins, owner in rows:
        if not when and not room:
            skipped += 1
            continue
        pic = (owner or "").strip() or "Điều phối chương trình"
        queue_email(
            conn,
            kind="interview_invite",
            recipient=email,
            subject=f"[X] Thư mời phỏng vấn — {prog}",
            body=(
                f"Kính gửi {name},\n\n"
                f"Mời bạn phỏng vấn chương trình {prog}:\n"
                f"- Buổi: {title or '—'}\n"
                f"- Thời gian: {when or '—'}\n"
                f"- Địa điểm: {room or '—'}\n"
                f"- Người phụ trách: {pic}\n"
                f"- Thời lượng: {mins or 20} phút\n\n"
                f"Vui lòng có mặt trước 10 phút.\n\nX / CFVG"
            ),
        )
        n += 1
    return {"sent": n, "skipped_incomplete": skipped}


def notify_admission_pack(conn, scopes: list[str] | None = None) -> dict:
    """Thông báo trúng tuyển kèm khai giảng / học phí (nếu có)."""
    from ops_data import _scopes_sql

    cur = conn.cursor()
    frag, params = _scopes_sql(scopes, "a.program_code")
    rows = cur.execute(
        "SELECT a.id, a.full_name, a.email, a.program_code, IFNULL(a.board_decision,''), "
        "IFNULL(a.final_result,''), a.status "
        f"FROM applications a WHERE IFNULL(a.email,'') != '' AND {frag}",
        params,
    ).fetchall()
    n = 0
    for _aid, name, email, prog, board, final, status in rows:
        blob = f"{board} {final} {status}".lower()
        if not any(x in blob for x in ("trúng", "đỗ", "passed", "admitted", "paid", "official")):
            continue
        fee = cur.execute(
            "SELECT IFNULL(SUM(amount_due),0), IFNULL(MIN(due_date),'') FROM student_charges "
            "WHERE application_id = ? AND status != 'paid'",
            (_aid,),
        ).fetchone()
        due_amt, due_date = (fee[0] if fee else 0), (fee[1] if fee else "")
        queue_email(
            conn,
            kind="admission_offer",
            recipient=email,
            subject=f"[X] Thông báo trúng tuyển & khai giảng — {prog}",
            body=(
                f"Kính gửi {name},\n\n"
                f"Chúc mừng bạn trúng tuyển {prog}.\n"
                f"Thông tin khai giảng sẽ gửi theo đợt nhập học.\n"
                f"Học phí / phí ghi danh còn phải nộp: {due_amt or 'xem thông báo KT'}"
                f"{(' (hạn ' + due_date + ')') if due_date else ''}.\n\nX / CFVG"
            ),
        )
        n += 1
    return {"sent": n}
