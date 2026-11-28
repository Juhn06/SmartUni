"""
RBAC: permissions, menus ordered by business workflow (MSCM/MMS nghiepvu).
"""
from __future__ import annotations

# Menu ordered by end-to-end flow:
# Tuyển sinh → Phí/CT chính thức → Chương trình → Lớp → Giảng dạy → Đánh giá/Thi → Alumni → Hệ thống
MENU_ITEMS = [
    # --- 1. Tuyển sinh (dữ liệu nguồn đứng đầu menu) ---
    {
        "code": "admissions.crm_source",
        "label": "Dữ liệu Nguồn",
        "label_en": "Source profiles",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_crm_source",
        "sort": 5,
        "workflow": "Sổ Enquiry (chỉ TS): tiếp nhận lần đầu, PIC Giao/Nhung, mức quan tâm, kênh; T10–T3 tạo nguồn, T3–T9 chuyển hồ sơ",
    },
    {
        "code": "admissions.rounds",
        "label": "Đợt tuyển sinh",
        "label_en": "Admission rounds",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_rounds",
        "sort": 6,
        "workflow": "TS tạo đợt (MBA May/Aug…) → mở/đóng hồ sơ + timeline thi/PV",
    },
    {
        "code": "admissions.round_docs",
        "label": "Tìm kiếm tài liệu",
        "label_en": "Search round documents",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_round_docs",
        "sort": 10,
        "workflow": "Tìm theo đợt; tải lên, xem trước và tải xuống tài liệu đợt tuyển sinh",
    },
    {
        "code": "admissions.applications",
        "label": "Hồ sơ ứng viên",
        "label_en": "Applicants",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_applications",
        "sort": 11,
        "workflow": "Nhận hồ sơ, issue checklist (X / Incompleted / Exempted / Not required), phản hồi chất lượng, hướng dẫn lịch thi/PV",
    },
    {
        "code": "admissions.interviews",
        "label": "Phỏng vấn",
        "label_en": "Interviews",
        "group": "2.TS.Thi",
        "group_en": "2.TS.Exams",
        "route": "ops_admissions_interviews",
        "sort": 21,
        "workflow": "TS gửi DS và trực hỗ trợ PV; Admin CT cập nhật ngay no-show cho TS",
    },
    {
        "code": "admissions.written_exams",
        "label": "Thi viết",
        "label_en": "Written exams",
        "group": "2.TS.Thi",
        "group_en": "2.TS.Exams",
        "route": "ops_admissions_written_exams",
        "sort": 20,
        "workflow": "TS lập DS thi viết gửi Admin CT; Admin cập nhật không phản hồi sau deadline; ĐP gán SBD/điểm",
    },
    {
        "code": "admissions.results",
        "label": "Kết quả tuyển sinh",
        "label_en": "Admission results",
        "group": "2.TS.Thi",
        "group_en": "2.TS.Exams",
        "route": "ops_admissions_results",
        "sort": 22,
        "workflow": "Admin gửi KQ đầu vào; T8–T9 TS nhắc TA/xác nhận văn bằng trước khai giảng và bàn giao hồ sơ HV",
    },
    {
        "code": "admissions.pre_enroll",
        "label": "Hồ sơ xét tuyển",
        "label_en": "Pre-enrollment files",
        "group": "2.TS.Xét duyệt",
        "group_en": "2.TS.Review",
        "route": "ops_admissions_pre_enroll",
        "sort": 30,
        "workflow": "Bảng hồ sơ chưa thành học viên: cùng hồ sơ cá nhân, trạng thái xác nhận dự thi",
    },
    {
        "code": "admissions.enrolled_files",
        "label": "Hồ sơ đã nhập học",
        "label_en": "Learner program files",
        "group": "2.TS.Bàn giao",
        "group_en": "2.TS.Handoff",
        "route": "ops_admissions_enrolled_files",
        "sort": 43,
        "workflow": "Bàn giao hồ sơ học viên đầy đủ cho Admin CT: mã HV theo chương trình, cùng mã ứng viên",
    },
    {
        "code": "admissions.verification_queue",
        "label": "Danh sách cần xác minh",
        "label_en": "Verification queue",
        "group": "2.TS.Xét duyệt",
        "group_en": "2.TS.Review",
        "route": "ops_admissions_verification",
        "sort": 31,
        "workflow": "Khảo thí/Thanh tra xem minh chứng · lọc đợt/ngành · xuất; không sửa hồ sơ",
    },
    {
        "code": "admissions.student_numbering",
        "label": "Cấp mã học viên",
        "label_en": "Assign learner codes",
        "group": "2.TS.Xét duyệt",
        "group_en": "2.TS.Review",
        "route": "ops_admissions_student_numbering",
        "sort": 32,
        "workflow": "Sau quyết định trúng tuyển: xem trước · cấp mã chống trùng; không tự tạo người học",
    },
    {
        "code": "admissions.round_docs.view",
        "label": "Xem tài liệu đợt TS",
        "label_en": "View round documents",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_round_docs",
        "sort": 12,
        "nav": False,
        "workflow": "Chỉ xem/preview tài liệu đợt — không tải xuống",
    },
    {
        "code": "admissions.round_docs.download",
        "label": "Tải tài liệu đợt TS",
        "label_en": "Download round documents",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_round_docs",
        "sort": 13,
        "nav": False,
        "workflow": "Tải xuống tài liệu đợt (kèm quyền xem)",
    },
    {
        "code": "admissions.crm_activities",
        "label": "Đợt chăm sóc",
        "label_en": "Care activities",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_crm_activities",
        "sort": 7,
        "workflow": "Khai báo đợt (tư vấn riêng, hội thảo…) → chọn hồ sơ nguồn → ghi chú chăm sóc",
    },
    {
        "code": "admissions.crm_reminders",
        "label": "Nhắc nhở CRM",
        "label_en": "CRM reminders",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_crm_reminders",
        "sort": 8,
        "workflow": "Nhắc trước đợt chăm sóc: in danh sách / email / gọi điện",
    },
    {
        "code": "admissions.chatbot",
        "label": "Yêu cầu tư vấn & chatbot",
        "label_en": "Consultation requests & chatbot",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_chatbot",
        "sort": 8.5,
        "workflow": "Người quan tâm đăng ký tư vấn trên trang giới thiệu hoặc qua UniBot → giao chuyên viên → liên hệ, ghi nhật ký chăm sóc",
    },
    {
        "code": "admissions.chatbot_publish",
        "label": "Duyệt nội dung UniBot tuyển sinh",
        "label_en": "Approve admissions UniBot content",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_chatbot",
        "sort": 8.6,
        "nav": False,
        "workflow": "Tuyển sinh soạn tài liệu, FAQ → chờ duyệt → người có quyền duyệt công bố theo thời gian hiệu lực của đợt → UniBot dùng; hết hạn tự gỡ",
    },
    {
        "code": "admissions.crm_reports",
        "label": "Báo cáo CRM",
        "label_en": "CRM reports",
        "group": "2.TS.Báo cáo",
        "group_en": "2.TS.Reports",
        "route": "ops_admissions_crm_reports",
        "sort": 48,
        "workflow": "Báo cáo Enquiry: mức quan tâm × chương trình và phễu Apply/Candidate/Fail/Select/Quit/Postpone/Enroll",
    },
    {
        "code": "admissions.events",
        "label": "Sự kiện tuyển sinh",
        "label_en": "Admission events",
        "group": "2.TS.Sự kiện",
        "group_en": "2.TS.Events",
        "route": "ops_admissions_events",
        "sort": 46,
        "workflow": "Marcom quảng bá; TS mời và chăm sóc trước / trong / sau sự kiện, cập nhật mức quan tâm vào Enquiry",
    },
    {
        "code": "admissions.neu_prep",
        "label": "Chuẩn bị xét duyệt NEU",
        "label_en": "NEU admission pack",
        "group": "2.TS.Xét duyệt",
        "group_en": "2.TS.Review",
        "route": "ops_admissions_neu_prep",
        "sort": 33,
        "workflow": "Admin thực thi, TS phối hợp: hồ sơ Thanh tra Pháp chế, minh chứng TA Khảo thí, văn bản NEU, nộp HTQT",
    },
    {
        "code": "admissions.mail",
        "label": "Mẫu email tuyển sinh",
        "label_en": "Admission email templates",
        "group": "2.TS.Email",
        "group_en": "2.TS.Email",
        "route": "ops_admissions_mail",
        "sort": 45,
        "workflow": "Tạo mẫu, sửa nội dung và gửi email cho ứng viên theo đợt",
    },
    # --- 2. Ghi danh & trúng tuyển chính thức ---
    {
        "code": "accounting.fees",
        "label": "Phí ghi danh",
        "label_en": "Enrollment fees",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_fees",
        "sort": 50,
        "workflow": "Sau đỗ: Điều phối chỉ xem · Kế toán xác nhận đã thu",
    },
    {
        "code": "accounting.official_list",
        "label": "Nhập học chính thức",
        "label_en": "Official enrollment",
        "group": "2.TS.Bàn giao",
        "group_en": "2.TS.Handoff",
        "route": "ops_accounting_official",
        "sort": 42,
        "workflow": "Deposit xong → DS chính thức → xuất Khảo thí NEU / bàn giao ĐP",
    },
    {
        "code": "accounting.charges",
        "label": "Công nợ / học phí",
        "label_en": "Student charges (all programs)",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_charges",
        "sort": 56,
        "workflow": "Sổ thu toàn CT: Payment Plan · học phí · học bổng/giảm/hỗ trợ/hoàn",
    },
    {
        "code": "accounting.benefits",
        "label": "Học bổng, giảm phí, hỗ trợ",
        "label_en": "Scholarships and aid",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_benefits",
        "sort": 56.4,
        "workflow": "Một hồ sơ: giảm nghĩa vụ hoặc chi ra tài khoản · người lập không tự duyệt",
    },
    {
        "code": "accounting.refunds",
        "label": "Hoàn phí",
        "label_en": "Refunds",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_refunds",
        "sort": 56.6,
        "workflow": "Đề nghị · duyệt · chi · đã duyệt chưa phải đã chi",
    },
    {
        "code": "accounting.billing_profiles",
        "label": "Thông tin xuất hóa đơn",
        "label_en": "Invoice billing profiles",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_billing_profiles",
        "sort": 56.8,
        "workflow": "Cá nhân hoặc doanh nghiệp · MST và CCCD giữ số 0 đầu · bản mới không sửa chứng từ cũ",
    },
    {
        "code": "accounting.intake_plans",
        "label": "Kế hoạch thu theo khóa",
        "label_en": "Intake fee plan",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_intake_plans",
        "sort": 57.5,
        "workflow": "Biểu phí theo chương trình và khóa. Khi chốt nhập học, các đợt học phí sinh từ kế hoạch này.",
    },
    {
        "code": "accounting.tuition_tracker",
        "label": "Theo dõi học phí",
        "label_en": "Tuition tracker",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_tuition_tracker",
        "sort": 58,
        "workflow": "Kế toán theo dõi tình trạng đóng học phí từng HV: đã nộp / một phần / sắp hạn / quá hạn",
    },
    {
        "code": "accounting.fee_alerts",
        "label": "Cảnh báo học phí",
        "label_en": "Tuition alerts",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_fee_alerts",
        "sort": 59,
        "workflow": "Cảnh báo tự động khi sắp hạn, quá hạn, hoặc HV có nhiều khoản trễ — chỉnh ngưỡng tiêu chí",
    },
    {
        "code": "accounting.fee_types",
        "label": "Danh mục khoản thu",
        "label_en": "Fee type catalog",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_fee_types",
        "sort": 57,
        "workflow": "Inscription · tuition · retake · transcript · …",
    },
    {
        "code": "accounting.candidate_files",
        "label": "Nghĩa vụ phí thí sinh",
        "label_en": "Candidate fee obligations",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_candidate_files",
        "sort": 54,
        "workflow": "Nghĩa vụ phí theo hồ sơ/đợt/khoản thu · miễn · phiếu thu · cam kết dự thi",
    },
    {
        "code": "accounting.receipts",
        "label": "Phiếu thu",
        "label_en": "Payment receipts",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_receipts",
        "sort": 54.2,
        "workflow": "Lập phiếu thu: tìm thí sinh · khoản thu · số tiền · hình thức · mã giao dịch",
    },
    {
        "code": "accounting.payment_methods",
        "label": "Hình thức nộp tiền",
        "label_en": "Payment methods",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_payment_methods",
        "sort": 57.2,
        "workflow": "Danh mục chuyển khoản / thẻ / hình thức khác",
    },
    {
        "code": "accounting.round_fee_settings",
        "label": "Khoản thu theo đợt",
        "label_en": "Round fee settings",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_round_fees",
        "sort": 57.4,
        "workflow": "Đơn giá · số lần tính thu · hạn nộp theo đợt tuyển sinh",
    },
    {
        "code": "accounting.payment_imports",
        "label": "Import thu tiền",
        "label_en": "Import payments",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_payment_imports",
        "sort": 57.6,
        "workflow": "Import phiếu thu: CCCD + đợt + mã khoản + mã giao dịch (chống trùng)",
    },
    {
        "code": "accounting.receipt_emails",
        "label": "Email cảm ơn",
        "label_en": "Thank-you emails",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_receipt_emails",
        "sort": 59.6,
        "workflow": "Gửi email sau phiếu thu · hàng loạt theo đợt · lưu trạng thái gửi",
    },
    {
        "code": "accounting.my_fees",
        "label": "Nghĩa vụ phí của tôi",
        "label_en": "My fee obligations",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_my_fees",
        "sort": 505.5,
        "workflow": "HV xem phải nộp / đã nộp / công nợ; gửi minh chứng không tự xác nhận đã thu",
    },
    {
        "code": "accounting.collection_report",
        "label": "Báo cáo thu tiền",
        "label_en": "Collection report",
        "group": "Thu tiền",
        "group_en": "Collections",
        "route": "ops_accounting_collection_report",
        "sort": 59.5,
        "workflow": "Tổng đã thu (kể cả miễn phí) · còn nợ · theo loại khoản thu và thời gian",
    },
    # --- 3. Chương trình ---
    {
        "code": "programs.structure",
        "label": "Phiên bản chương trình",
        "label_en": "Programme versions",
        "group": "4. Chương trình",
        "group_en": "4. Programme",
        "route": "ops_programs",
        "sort": 70,
        "workflow": "Copy phiên bản (MMS_Khoa_20 → MMS_Khoa_21, MBA_K34 → K35) → hiệu chỉnh",
    },
    {
        "code": "programs.courses",
        "label": "Môn học / học phần",
        "label_en": "Courses",
        "group": "4. Chương trình",
        "group_en": "4. Programme",
        "route": "ops_courses",
        "sort": 80,
        "workflow": "Môn theo HK; 8 buổi (MMS/MBA) / 7 LT + 2 TH (MSCM)",
    },
    # --- 4. Lớp ---
    {
        "code": "classes.manage",
        "label": "Danh sách lớp",
        "label_en": "Classes",
        "group": "5. Lớp học & Lịch học",
        "group_en": "5. Classes & Schedule",
        "route": "ops_classes",
        "sort": 90,
        "workflow": "Tạo lớp từ DS chính thức + gắn version CT + email chào mừng",
    },
    # --- 5. Giảng dạy ---
    {
        "code": "teaching.faculty",
        "label": "Hồ sơ giảng viên",
        "label_en": "Faculty profiles",
        "group": "6. Giảng viên",
        "group_en": "6. Lecturers",
        "route": "ops_faculty",
        "sort": 110,
        "workflow": "Danh mục GV/CG; tìm theo chuyên môn để phân giảng",
    },
    {
        "code": "teaching.schedule",
        "label": "Lịch học",
        "label_en": "Schedule",
        "group": "5. Lớp học & Lịch học",
        "group_en": "5. Classes & Schedule",
        "route": "ops_teaching_schedule",
        "sort": 100,
        "workflow": "Semester schedule → room/time → bàn giao logistics GV",
    },
    {
        "code": "teaching.assign",
        "label": "Phân công giảng dạy",
        "label_en": "Teaching assign",
        "group": "6. Giảng viên",
        "group_en": "6. Lecturers",
        "route": "ops_teaching_assign",
        "sort": 120,
        "workflow": "Lớp–môn → GV LT + chuyên gia; tự sinh buổi",
    },
    {
        "code": "teaching.lessons",
        "label": "Bài giảng",
        "label_en": "Class lessons",
        "group": "7. Học vụ",
        "group_en": "7. Academic Affairs",
        "route": "ops_class_lessons_hub",
        "sort": 135,
        "workflow": "Import buổi từ syllabus → thêm/upload → publish → HV preview/Q&A",
    },
    {
        "code": "teaching.online_lectures",
        "label": "Bài giảng trực tuyến",
        "label_en": "Online lectures",
        "group": "7b. Học trực tuyến",
        "group_en": "7b. Online learning",
        "route": "ops_online_lectures",
        "sort": 136,
        "workflow": "Tạo/phát bài (file hoặc link) theo lịch; HV xem + hỏi đáp; thảo luận nhóm",
    },
    {
        "code": "teaching.objectives",
        "label": "Cố vấn mục tiêu học",
        "label_en": "Learning objectives advisor",
        "group": "7b. Học trực tuyến",
        "group_en": "7b. Online learning",
        "route": "ops_elearn_objectives",
        "sort": 137,
        "workflow": "Phân tích syllabus/buổi học → mục tiêu + bước đạt mục tiêu",
    },
    {
        "code": "teaching.instructor_intel",
        "label": "Hỗ trợ GV thông minh",
        "label_en": "Intelligent instructor services",
        "group": "7b. Học trực tuyến",
        "group_en": "7b. Online learning",
        "route": "ops_instructor_intel",
        "sort": 138,
        "workflow": "Theo dõi tiến độ lớp: thời gian xem, câu hỏi chưa trả lời, HV rủi ro",
    },
    {
        "code": "teaching.student_tracker",
        "label": "Theo dõi học viên",
        "label_en": "Student tracker",
        "group": "7b. Học trực tuyến",
        "group_en": "7b. Online learning",
        "route": "ops_student_tracker",
        "sort": 139,
        "workflow": "Phút học, chuyên cần, điểm BT; báo cáo từng HV",
    },
    {
        "code": "teaching.exam_integrity",
        "label": "Phiên thi trực tuyến",
        "label_en": "Exam integrity",
        "group": "7b. Học trực tuyến",
        "group_en": "7b. Online learning",
        "route": "ops_exam_integrity",
        "sort": 140,
        "workflow": "Phiên thi: xác minh CCCD / ảnh chân dung / cam kết — không so khớp khuôn mặt",
    },
    {
        "code": "teaching.return_meetings",
        "label": "Họp HV tạm ngưng",
        "label_en": "Return meetings",
        "group": "7b. Học trực tuyến",
        "group_en": "7b. Online learning",
        "route": "ops_return_meetings",
        "sort": 141,
        "workflow": "Lịch họp trực tuyến cho HV bảo lưu / nghỉ học; lưu URL + hỗ trợ trở lại",
    },
    {
        "code": "teaching.materials",
        "label": "Tài liệu học tập",
        "label_en": "Learning materials",
        "group": "7. Học vụ",
        "group_en": "7. Academic Affairs",
        "route": "ops_materials",
        "sort": 130,
        "workflow": "Upload/gửi tài liệu theo buổi; SV xem theo lớp–môn",
    },
    {
        "code": "teaching.groups",
        "label": "Nhóm học tập",
        "label_en": "Study groups",
        "group": "7. Học vụ",
        "group_en": "7. Academic Affairs",
        "route": "ops_groups",
        "sort": 140,
        "workflow": "Tạo nhóm theo môn; SV thấy nhóm của mình",
    },
    {
        "code": "teaching.attendance",
        "label": "Điểm danh",
        "label_en": "Attendance",
        "group": "7. Học vụ",
        "group_en": "7. Academic Affairs",
        "route": "ops_attendance",
        "sort": 150,
        "workflow": "Logistics điểm danh buổi; tổng hợp vắng / đủ điều kiện thi",
    },
    {
        "code": "teaching.assignments",
        "label": "Bài tập",
        "label_en": "Assignments",
        "group": "7. Học vụ",
        "group_en": "7. Academic Affairs",
        "route": "ops_assignments",
        "sort": 160,
        "workflow": "Giao BT thực hành / trắc nghiệm theo lớp–môn; import mẫu; HV làm online",
    },
    {
        "code": "teaching.grades",
        "label": "Điểm",
        "label_en": "Grades",
        "group": "7. Học vụ",
        "group_en": "7. Academic Affairs",
        "route": "ops_grades",
        "sort": 170,
        "workflow": "Đầu điểm + tỷ trọng; nhập/import; khóa; in bảng điểm",
    },
    {
        "code": "teaching.grades.publish",
        "label": "Công bố điểm",
        "label_en": "Publish grades",
        "group": "7. Học vụ",
        "group_en": "7. Academic Affairs",
        "route": "ops_grades",
        "sort": 171,
        "workflow": "Khóa và công bố điểm chính thức. Dành cho điều phối MBA và Master.",
    },
    {
        "code": "teaching.review_batches",
        "label": "Đợt xét kết quả",
        "label_en": "Grade review batches",
        "group": "7. Học vụ",
        "group_en": "7. Academic Affairs",
        "route": "ops_teaching_review_batches",
        "sort": 172,
        "workflow": "Chọn SV · chốt ảnh chụp điểm · GPA trọng số tín chỉ",
    },
    # --- 6. Thi / đánh giá ---
    {
        "code": "teaching.exams",
        "label": "Thi cử",
        "label_en": "Exams",
        "group": "7. Học vụ",
        "group_en": "7. Academic Affairs",
        "route": "ops_exams",
        "sort": 180,
        "workflow": "Đề tự luận/trắc nghiệm; thi lại; khiếu nại điểm",
    },
    {
        "code": "teaching.evaluation",
        "label": "Đánh giá môn học",
        "label_en": "Course evaluation",
        "group": "7. Học vụ",
        "group_en": "7. Academic Affairs",
        "route": "ops_evaluation",
        "sort": 190,
        "workflow": "Form sau thi; ≥80% phản hồi → gửi báo cáo",
    },
    {
        "code": "teaching.thesis",
        "label": "Luận văn",
        "label_en": "Thesis",
        "group": "8. Luận văn",
        "group_en": "8. Thesis",
        "route": "ops_thesis",
        "sort": 200,
        "workflow": "Assignment LV; phân công GVHD; theo dõi nộp",
    },
    # --- 7. Alumni ---
    {
        "code": "students.manage",
        "label": "Danh sách học viên",
        "label_en": "Learners",
        "group": "3. Học viên",
        "group_en": "3. Students",
        "route": "ops_students_manage",
        "sort": 60,
        "workflow": "Financial + Academic · bảo lưu/nghỉ · học bổng · đủ ĐK thi → alumni",
    },
    {
        "code": "students.academic",
        "label": "Kết quả & tiến độ học tập",
        "label_en": "Academic record",
        "group": "3. Học viên",
        "group_en": "3. Students",
        "route": "ops_students_academic",
        "sort": 61,
        "workflow": "Học viên gốc → hồ sơ ứng viên, điểm môn, bảng điểm, tiến độ so với chương trình",
    },
    {
        "code": "alumni.members",
        "label": "Danh sách alumni",
        "label_en": "Alumni list",
        "group": "11. Alumni",
        "group_en": "11. Alumni",
        "route": "ops_alumni",
        "sort": 300,
        "workflow": "DS theo khóa/CT/lớp; tìm kiếm; gửi email",
    },
    {
        "code": "alumni.events",
        "label": "Sự kiện Alumni",
        "label_en": "Alumni events",
        "group": "11. Alumni",
        "group_en": "11. Alumni",
        "route": "ops_alumni_events",
        "sort": 310,
        "workflow": "Tạo sự kiện → lọc đối tượng → gửi lời mời",
    },
    {
        "code": "alumni.portal",
        "label": "Cổng cựu học viên",
        "label_en": "Alumni portal",
        "group": "11. Alumni",
        "group_en": "11. Alumni",
        "route": "ops_alumni_portal",
        "sort": 315,
        "workflow": "Cựu học viên sửa hồ sơ cá nhân; xem sự kiện chung và sự kiện được mời",
    },
    # --- Marcom / Truyền thông (TuanTA) ---
    {
        "code": "marcom.leads",
        "label": "Người quan tâm",
        "label_en": "Leads / prospects",
        "group": "12. Truyền thông",
        "group_en": "12. Marcom",
        "route": "ops_marcom_leads",
        "sort": 320,
        "workflow": "Tiếp nhận (không bắt CCCD) → kiểm tra trùng → hồ sơ chung → bàn giao tuyển sinh → tuyển sinh xác nhận",
    },
    {
        "code": "marcom.campaigns",
        "label": "Chiến dịch và ngân sách",
        "label_en": "Campaigns and budget",
        "group": "12. Truyền thông",
        "group_en": "12. Marcom",
        "route": "ops_marcom_campaigns",
        "sort": 330,
        "workflow": "Lập kế hoạch → Kế toán duyệt → Ban Giám đốc duyệt → triển khai → đánh giá → đối soát chứng từ",
    },
    {
        "code": "marcom.events",
        "label": "Sự kiện",
        "label_en": "Events",
        "group": "12. Truyền thông",
        "group_en": "12. Marcom",
        "route": "ops_marcom_events",
        "sort": 340,
        "workflow": "Duyệt ngân sách → truyền thông → khách mời / diễn giả → vận hành → báo cáo sau sự kiện",
    },
    {
        "code": "marcom.assets",
        "label": "Nội dung và tư liệu",
        "label_en": "Content and materials",
        "group": "12. Truyền thông",
        "group_en": "12. Marcom",
        "route": "ops_marcom_assets",
        "sort": 350,
        "workflow": "Yêu cầu → duyệt ngân sách nếu thuê ngoài → sản xuất → nghiệm thu → hồ sơ thanh toán → lịch phát hành",
    },
    {
        "code": "marcom.reports",
        "label": "Báo cáo truyền thông",
        "label_en": "Marcom reports",
        "group": "12. Truyền thông",
        "group_en": "12. Marcom",
        "route": "ops_marcom_reports",
        "sort": 355,
        "workflow": "Tổng hợp tháng / quý / nửa năm / năm cho Ban Giám đốc — không nhập lại số liệu",
    },
    # --- Trợ lý Ban Giám đốc ---
    {
        "code": "asst.exec_tasks",
        "label": "Nhiệm vụ",
        "label_en": "Tasks",
        "group": "10. Hành chính",
        "group_en": "10. Administration",
        "route": "ops_asst_tasks",
        "sort": 240,
        "workflow": "Họp BGD → biên bản → nhiệm vụ → deadline → tiến độ",
    },
    {
        "code": "asst.calendar",
        "label": "Lịch tuần / lịch họp",
        "label_en": "Weekly calendar",
        "group": "10. Hành chính",
        "group_en": "10. Administration",
        "route": "ops_asst_calendar",
        "sort": 230,
        "workflow": "Lịch BGD / họp / sự kiện / giảng dạy / nghỉ phép",
    },
    {
        "code": "intl.partners",
        "label": "Trường đối tác",
        "label_en": "Partner universities",
        "group": "9. Quốc tế / Exchange",
        "group_en": "9. Exchange",
        "route": "ops_intl_partners",
        "sort": 204,
        "workflow": "Danh mục trường · mã viết tắt · import đối chiếu",
    },
    {
        "code": "intl.cooperation_programs",
        "label": "Chương trình hợp tác",
        "label_en": "Cooperation programs",
        "group": "9. Quốc tế / Exchange",
        "group_en": "9. Exchange",
        "route": "ops_intl_coop",
        "sort": 205,
        "workflow": "Liên kết đối tác · Incoming/Outgoing",
    },
    {
        "code": "intl.workflow_steps",
        "label": "Bước Incoming / Outgoing",
        "label_en": "Exchange workflow steps",
        "group": "9. Quốc tế / Exchange",
        "group_en": "9. Exchange",
        "route": "ops_intl_steps",
        "sort": 206,
        "workflow": "Danh mục bước + lịch sử minh chứng theo HV",
    },
    {
        "code": "intl.exchange_reports",
        "label": "Báo cáo trao đổi",
        "label_en": "Exchange reports",
        "group": "9. Quốc tế / Exchange",
        "group_en": "9. Exchange",
        "route": "ops_intl_reports",
        "sort": 207,
        "workflow": "Báo cáo theo trường đối tác / thời gian",
    },
    {
        "code": "asst.intl_faculty",
        "label": "Giảng viên quốc tế",
        "label_en": "International faculty",
        "group": "9. Quốc tế / Exchange",
        "group_en": "9. Exchange",
        "route": "ops_asst_intl_faculty",
        "sort": 220,
        "workflow": "Hộ chiếu → visa → vé → KS → đón tiễn → lịch giảng",
    },
    {
        "code": "asst.intl_students",
        "label": "Học viên quốc tế",
        "label_en": "International students",
        "group": "9. Quốc tế / Exchange",
        "group_en": "9. Exchange",
        "route": "ops_asst_intl_students",
        "sort": 210,
        "workflow": "HV trao đổi → visa → chuyến bay → onboarding",
    },
    {
        "code": "asst.director_fr",
        "label": "Hồ sơ GĐ Pháp",
        "label_en": "French Director dossiers",
        "group": "10. Hành chính",
        "group_en": "10. Administration",
        "route": "ops_asst_director_fr",
        "sort": 290,
        "workflow": "Visa / work permit / cư trú — cảnh báo hết hạn",
    },
    {
        "code": "asst.documents",
        "label": "Công văn & con dấu",
        "label_en": "Documents & seal",
        "group": "10. Hành chính",
        "group_en": "10. Administration",
        "route": "ops_asst_documents",
        "sort": 250,
        "workflow": "Công văn đến/đi → cấp số → ký → đóng dấu → phát hành",
    },
    {
        "code": "asst.procurement",
        "label": "Mua sắm",
        "label_en": "Procurement",
        "group": "10. Hành chính",
        "group_en": "10. Administration",
        "route": "ops_asst_procurement",
        "sort": 260,
        "workflow": "Đề xuất → duyệt → mua/đặt → hóa đơn → thanh toán",
    },
    {
        "code": "asst.payments",
        "label": "Chi phí / thanh toán",
        "label_en": "Expenses / payments",
        "group": "10. Hành chính",
        "group_en": "10. Administration",
        "route": "ops_asst_payments",
        "sort": 270,
        "workflow": "Vé máy bay / taxi / VP phẩm — theo dõi thanh toán tháng",
    },
    {
        "code": "asst.weekly_report",
        "label": "Báo cáo tuần NEU",
        "label_en": "Weekly NEU report",
        "group": "10. Hành chính",
        "group_en": "10. Administration",
        "route": "ops_asst_weekly_report",
        "sort": 285,
        "workflow": "Tổng hợp bộ phận → BGD duyệt → gửi NEU",
    },
    {
        "code": "asst.leave",
        "label": "Nghỉ phép",
        "label_en": "Leave",
        "group": "10. Hành chính",
        "group_en": "10. Administration",
        "route": "ops_asst_leave",
        "sort": 280,
        "workflow": "Đăng ký nghỉ → phê duyệt → lịch nghỉ → bàn giao",
    },
    # --- Canvas LMS (theo nhóm đối tượng) ---
    {
        "code": "canvas.coordinator",
        "label": "Canvas — Điều phối",
        "label_en": "Canvas — Coordinator",
        "group": "13. Cấu hình",
        "group_en": "13. Configuration",
        "route": "ops_canvas_coordinator",
        "sort": 400,
        "workflow": "Xuất lớp → Users/Courses/Enrollments SIS → Canvas",
    },
    {
        "code": "canvas.faculty",
        "label": "Canvas — Giảng viên",
        "label_en": "Canvas — Faculty",
        "group": "13. Cấu hình",
        "group_en": "13. Configuration",
        "route": "ops_canvas_faculty",
        "sort": 401,
        "workflow": "Lớp–môn trên Canvas · tài liệu · SpeedGrader",
    },
    {
        "code": "canvas.student",
        "label": "Canvas — Học viên",
        "label_en": "Canvas — Student",
        "group": "13. Cấu hình",
        "group_en": "13. Configuration",
        "route": "ops_canvas_student",
        "sort": 402,
        "workflow": "Trạng thái enroll · hướng dẫn đăng nhập Canvas",
    },
    {
        "code": "canvas.accounting",
        "label": "Canvas — Ghi danh",
        "label_en": "Canvas — Enrollment",
        "group": "13. Cấu hình",
        "group_en": "13. Configuration",
        "route": "ops_canvas_accounting",
        "sort": 403,
        "workflow": "Official list → xuất roster Users cho Canvas",
    },
    {
        "code": "canvas.it",
        "label": "Tích hợp Canvas",
        "label_en": "Canvas integration",
        "group": "13. Cấu hình",
        "group_en": "13. Configuration",
        "route": "ops_canvas_it",
        "sort": 404,
        "workflow": "Phân biệt đã xuất / đã gửi / Canvas chấp nhận · SIS map",
    },
    {
        "code": "students.support",
        "label": "Hỗ trợ học viên & UniBot",
        "label_en": "Student support & UniBot",
        "group": "3. Học viên",
        "group_en": "3. Students",
        "route": "ops_student_support",
        "sort": 449,
        "workflow": "Câu hỏi học viên UniBot chưa trả lời được → bộ phận chương trình trả lời trong khung chat; quản lý kho kiến thức học vụ",
    },
    # --- Học viên ---
    {
        "code": "student.profile",
        "label": "Hồ sơ của tôi",
        "label_en": "My profile",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_profile",
        "sort": 450,
        "workflow": "Cập nhật hồ sơ / minh chứng nộp phí",
    },
    {
        "code": "student.schedule",
        "label": "Lịch học / Lịch PV",
        "label_en": "My schedule",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_schedule",
        "sort": 451,
        "workflow": "Xem lịch PV và lịch học",
    },
    {
        "code": "student.results",
        "label": "Kết quả của tôi",
        "label_en": "My results",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_results",
        "sort": 452,
        "workflow": "Kết quả TS và điểm (khi mở)",
    },
    {
        "code": "student.progress",
        "label": "Bảng điểm & tiến độ",
        "label_en": "Transcript & progress",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_progress",
        "sort": 452,
        "workflow": "HV xem điểm từng môn, môn đã học / đang học / sắp học và in bảng điểm",
    },
    {
        "code": "student.library",
        "label": "Học liệu và Syllabus",
        "label_en": "Course materials",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_library",
        "sort": 453,
        "workflow": "Xem syllabus, buổi học, tìm và tải tài liệu đã release",
    },
    {
        "code": "student.lessons",
        "label": "Bài học và thảo luận",
        "label_en": "Lessons and discussion",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_lessons",
        "sort": 454,
        "workflow": "Xem preview bài học lớp, tải file, đặt câu hỏi/comment",
    },
    {
        "code": "student.study_plan",
        "label": "Cố vấn kế hoạch học",
        "label_en": "Study plan advisor",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_study_plan",
        "sort": 455,
        "workflow": "Đề xuất kế hoạch ôn tập theo mục tiêu và tiến độ cá nhân",
    },
    {
        "code": "student.time_to_learn",
        "label": "Thời gian hoàn thành chủ đề",
        "label_en": "Time-to-learn",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_time_to_learn",
        "sort": 456,
        "workflow": "Ước lượng phút còn lại theo mức độ xem bài / điểm",
    },
    {
        "code": "student.objective_recs",
        "label": "Đề xuất mục tiêu cá nhân",
        "label_en": "Objective recommender",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_objective_recs",
        "sort": 457,
        "workflow": "Gợi ý mục tiêu chưa đạt và cách hoàn thành",
    },
    {
        "code": "student.agenda",
        "label": "Lịch học cá nhân",
        "label_en": "Study agenda",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_agenda",
        "sort": 458,
        "workflow": "Xếp lịch ngày/tuần theo thời gian còn lại của từng chủ đề",
    },
    {
        "code": "student.return_meetings",
        "label": "Họp hỗ trợ trở lại",
        "label_en": "My return meetings",
        "group": "Cổng HV",
        "group_en": "Student portal",
        "route": "ops_student_return_meetings",
        "sort": 459,
        "workflow": "HV bảo lưu/nghỉ học xem lịch họp hỗ trợ trở lại lớp",
    },
    # --- Báo cáo & Admin ---
    {
        "code": "reports.dashboard",
        "label": "Dashboard",
        "label_en": "Dashboard",
        "group": "1. Dashboard",
        "group_en": "1. Dashboard",
        "route": "ops_reports",
        "sort": 5,
        "workflow": "Số liệu theo scope chương trình được giao",
    },
    {
        "code": "admin.users",
        "label": "Người dùng",
        "label_en": "Users",
        "group": "A. Tài khoản & phân quyền",
        "group_en": "A. Accounts & access",
        "route": "admin_users",
        "sort": 500,
        "workflow": "Khóa/mở, gán admin, reset mật khẩu",
    },
    {
        "code": "admin.departments",
        "label": "Bộ phận",
        "label_en": "Departments",
        "group": "A. Tài khoản & phân quyền",
        "group_en": "A. Accounts & access",
        "route": "admin_departments",
        "sort": 510,
        "workflow": "Danh sách bộ phận & thành viên",
    },
    {
        "code": "admin.permissions",
        "label": "Vai trò / phân quyền",
        "label_en": "Roles & permissions",
        "group": "A. Tài khoản & phân quyền",
        "group_en": "A. Accounts & access",
        "route": "admin_permissions",
        "sort": 520,
        "workflow": "Quyền theo bộ phận + scope CT theo user",
    },
    {
        "code": "admin.suggestions",
        "label": "Theo dõi đề xuất",
        "label_en": "Suggestion tracking",
        "group": "B. Theo dõi yêu cầu",
        "group_en": "B. Request tracking",
        "route": "admin_suggestions",
        "sort": 530,
        "workflow": "Lọc / phân trang / đánh dấu đã xử lý / xuất Excel",
    },
    {
        "code": "admin.status_catalog",
        "label": "Danh mục trạng thái",
        "label_en": "Status catalog",
        "group": "C. Danh mục trạng thái",
        "group_en": "C. Status catalogs",
        "route": "admin_status_catalog",
        "sort": 540,
        "workflow": "Hồ sơ, kết quả, lifecycle, phí, loại nghỉ phép…",
    },
    {
        "code": "admissions.doc_types",
        "label": "Phân loại tài liệu",
        "label_en": "Document types",
        "group": "2.TS.Tư vấn",
        "group_en": "2.TS.Consulting",
        "route": "ops_admissions_doc_types",
        "sort": 9,
        "workflow": "Khai báo danh mục loại tài liệu (quy chế cấp CT/phòng ban/trung tâm, thông báo, hội đồng, giấy phép, báo cáo, biên bản, minh chứng kiểm định)",
    },
    {
        "code": "admin.reports",
        "label": "Thống kê hệ thống",
        "label_en": "System reports",
        "group": "D. Thống kê báo cáo",
        "group_en": "D. Reports",
        "route": "admin_system_hub",
        "sort": 550,
        "workflow": "Tổng hợp số liệu Admin & liên kết báo cáo ops",
    },
    {
        "code": "admin.audit_logs",
        "label": "Nhật ký thao tác",
        "label_en": "Audit logs",
        "group": "D. Thống kê báo cáo",
        "group_en": "D. Reports",
        "route": "ops_admin_audit_logs",
        "sort": 552,
        "workflow": "Chỉ xem/xuất: điểm, phiếu thu, miễn, trạng thái, cấp mã, import",
    },
]

PROGRAMS = [
    ("MBA", "Chương trình MBA"),
    ("MMS", "Master in Marketing and Sales"),
    ("MSCM", "Master Supply Chain Management"),
]

# Workflow-aligned permissions per department
# (Tổng hợp chức năng — bàn giao giữa bộ phận)
DEPT_DEFAULT_PERMISSIONS: dict[str, list[str]] = {
    "ban_giam_doc": [
        "reports.dashboard",
        # Liên thông TS → phí → HV (đọc để giám sát / báo cáo)
        "admissions.rounds",
        "admissions.applications",
        "admissions.written_exams",
        "admissions.interviews",
        "admissions.results",
        "admissions.round_docs.view",
        "admissions.round_docs.download",
        "accounting.fees",
        "accounting.official_list",
        "students.manage",
        "students.academic",
        "programs.structure",
        "programs.courses",
        "classes.manage",
        "teaching.faculty",
        "teaching.assign",
        "teaching.schedule",
        "teaching.attendance",
        "teaching.grades",
        "teaching.exams",
        "teaching.thesis",
        "alumni.members",
        "alumni.events",
        # Trợ lý / điều hành chung
        "asst.exec_tasks",
        "asst.calendar",
        "asst.weekly_report",
        "asst.leave",
        "asst.intl_faculty",
        "asst.intl_students",
        "asst.documents",
        "asst.procurement",
        "asst.payments",
        "canvas.coordinator",
    ],
    "tro_ly_bgd": [
        "asst.exec_tasks",
        "asst.calendar",
        "asst.intl_faculty",
        "asst.intl_students",
        "asst.director_fr",
        "asst.documents",
        "asst.procurement",
        "asst.payments",
        "asst.weekly_report",
        "asst.leave",
        "reports.dashboard",
        # Đọc số liệu liên thông để tổng hợp báo cáo tuần / hỗ trợ BGD
        "admissions.rounds",
        "admissions.applications",
        "admissions.results",
        "accounting.fees",
        "accounting.official_list",
        "students.manage",
        "students.academic",
        "classes.manage",
        "programs.structure",
        "teaching.faculty",
        "teaching.schedule",
        "teaching.attendance",
        "teaching.exams",
        "alumni.events",
        "canvas.coordinator",
    ],
    "ke_toan": [
        "accounting.fees",
        "accounting.official_list",
        "accounting.charges",
        "accounting.benefits",
        "accounting.refunds",
        "accounting.billing_profiles",
        "accounting.tuition_tracker",
        "accounting.fee_alerts",
        "accounting.fee_types",
        "accounting.candidate_files",
        "accounting.receipts",
        "accounting.payment_methods",
        "accounting.round_fee_settings",
        "accounting.intake_plans",
        "accounting.payment_imports",
        "accounting.receipt_emails",
        "accounting.collection_report",
        "admissions.results",
        "admissions.applications",
        "admissions.rounds",
        "admissions.pre_enroll",
        "admissions.enrolled_files",
        "admissions.round_docs",
        "admissions.round_docs.view",
        "admissions.round_docs.download",
        "admissions.doc_types",
        "admissions.written_exams",
        "students.manage",
        "students.academic",
        "programs.structure",
        "programs.courses",
        "teaching.faculty",
        "reports.dashboard",
        "asst.payments",
        "asst.procurement",
        "asst.intl_students",
        "canvas.accounting",
        "admin.audit_logs",
        "marcom.campaigns",
        "marcom.events",
        "marcom.assets",
        "marcom.reports",
    ],
    "marcom": [
        "reports.dashboard",
        "marcom.leads",
        "marcom.campaigns",
        "marcom.events",
        "marcom.assets",
        "marcom.reports",
        "alumni.events",
        "admissions.rounds",
    ],
    "marcom_tuyen_sinh": [
        "admissions.rounds",
        "admissions.applications",
        "admissions.results",
        "admissions.pre_enroll",
        "admissions.round_docs.view",
        "admissions.crm_source",
        "admissions.crm_activities",
        "admissions.crm_reminders",
        "admissions.crm_reports",
        "marcom.leads",
        "reports.dashboard",
    ],
    "tuyen_sinh": [
        "admissions.rounds",
        "admissions.applications",
        "admissions.written_exams",
        "admissions.interviews",
        "admissions.results",
        "admissions.pre_enroll",
        "admissions.enrolled_files",
        "admissions.round_docs",
        "admissions.round_docs.view",
        "admissions.round_docs.download",
        "admissions.doc_types",
        "admissions.crm_source",
        "admissions.crm_activities",
        "admissions.crm_reminders",
        "admissions.crm_reports",
        "admissions.events",  # Info Day / Workshop: trước–trong–sau, không quản ngân sách Marcom
        "admissions.neu_prep",  # phối hợp gói NEU; Admin CT thực thi
        "admissions.mail",
        "accounting.fees",
        "accounting.official_list",  # theo dõi DS nhập học / xuất khảo thí
        "accounting.candidate_files",  # theo dõi nghĩa vụ phí — không mark-paid
        "marcom.leads",  # lead Marcom đổ về, TS nhập tiếp vào Enquiry
        "reports.dashboard",
    ],
    "mba": [
        "students.support",
        # Theo tên khách hàng đến khi nhập học xong — không tách phase Tư vấn/Thi/Xét duyệt.
        "admissions.crm_source",
        "admissions.crm_activities",
        "admissions.crm_reminders",
        "admissions.events",
        "accounting.benefits",  # xem chương trình ưu đãi; không duyệt chi
        "admissions.rounds",  # May/Aug intake — Điều phối lập timeline thi viết/PV
        "admissions.applications",
        "admissions.written_exams",
        "admissions.interviews",
        "admissions.results",
        "admissions.neu_prep",  # Admin CT thực thi gói Thanh tra / Khảo thí / HTQT
        "admissions.pre_enroll",
        "admissions.enrolled_files",
        "admissions.round_docs",
        "admissions.round_docs.view",
        "admissions.round_docs.download",
        "admissions.doc_types",
        "accounting.fees",
        "accounting.official_list",
        "programs.structure",
        "programs.courses",
        "classes.manage",
        "students.manage",
        "students.academic",
        "teaching.faculty",
        "teaching.assign",
        "teaching.schedule",
        "teaching.materials",
        "teaching.lessons",
        "teaching.online_lectures",
        "teaching.objectives",
        "teaching.instructor_intel",
        "teaching.student_tracker",
        "teaching.exam_integrity",
        "teaching.return_meetings",
        "teaching.groups",
        "teaching.attendance",
        "teaching.assignments",
        "teaching.grades",
        "teaching.exams",
        "teaching.evaluation",
        "teaching.thesis",
        "teaching.review_batches",
        "admissions.student_numbering",
        "intl.partners",
        "intl.cooperation_programs",
        "intl.workflow_steps",
        "intl.exchange_reports",
        "asst.intl_students",
        "asst.intl_faculty",  # vé/KS/BH GV nước ngoài — bàn giao Trợ lý
        "alumni.members",
        "alumni.events",
        "reports.dashboard",
        "admissions.crm_reports",
        "canvas.coordinator",
    ],
    "master_chuyen_nganh": [
        "students.support",
        "admissions.rounds",  # intake + timeline thi viết/PV (giống Điều phối MBA)
        "admissions.applications",
        "admissions.written_exams",
        "admissions.interviews",
        "admissions.results",
        "admissions.neu_prep",  # Admin CT thực thi gói Thanh tra / Khảo thí / HTQT
        "admissions.pre_enroll",
        "admissions.enrolled_files",
        "admissions.round_docs",
        "admissions.round_docs.view",
        "admissions.round_docs.download",
        "admissions.doc_types",
        "accounting.fees",
        "accounting.official_list",
        "programs.structure",
        "programs.courses",
        "classes.manage",
        "students.manage",
        "students.academic",
        "teaching.faculty",
        "teaching.assign",
        "teaching.schedule",
        "teaching.materials",
        "teaching.lessons",
        "teaching.online_lectures",
        "teaching.objectives",
        "teaching.instructor_intel",
        "teaching.student_tracker",
        "teaching.exam_integrity",
        "teaching.return_meetings",
        "student.library",
        "student.lessons",
        "student.study_plan",
        "student.time_to_learn",
        "student.objective_recs",
        "student.agenda",
        "student.return_meetings",
        "teaching.groups",
        "teaching.attendance",
        "teaching.assignments",
        "teaching.grades",
        "teaching.exams",
        "teaching.evaluation",
        "teaching.thesis",
        "teaching.review_batches",
        "admissions.student_numbering",
        "intl.partners",
        "intl.cooperation_programs",
        "intl.workflow_steps",
        "intl.exchange_reports",
        "asst.intl_students",
        "asst.intl_faculty",
        "alumni.members",
        "alumni.events",
        "reports.dashboard",
        "admissions.crm_reports",
        "canvas.coordinator",
    ],
    "giang_vien": [
        "teaching.assign",
        "teaching.schedule",
        "teaching.materials",
        "teaching.lessons",
        "teaching.online_lectures",
        "teaching.objectives",
        "teaching.instructor_intel",
        "teaching.student_tracker",
        "teaching.exam_integrity",
        "teaching.return_meetings",
        "teaching.groups",
        "teaching.attendance",
        "teaching.assignments",
        "teaching.exams",
        "teaching.grades",
        "teaching.evaluation",
        "teaching.thesis",
        "reports.dashboard",
        "canvas.faculty",
    ],
    "it": [
        # IT kỹ thuật Canvas / hạ tầng — không gồm danh mục hay toàn bộ bản ghi ops
        "canvas.it",
        "reports.dashboard",
    ],
    "admin_he_thong": [
        # Placeholder — bị ghi đè bởi ADMIN_DATA_RECORD_CODES bên dưới
        "reports.dashboard",
    ],
    "logistic": [
        "teaching.attendance",
        "teaching.schedule",
        "asst.procurement",
        "reports.dashboard",
        "asst.intl_faculty",  # đón tiễn / hậu cần GV quốc tế
        "asst.calendar",
        "asst.director_fr",
    ],
    "cuu_hoc_vien": [
        "alumni.portal",
    ],
    "hoc_vien": [
        "student.profile",
        "student.schedule",
        "student.results",
        "student.progress",
        "student.library",
        "student.lessons",
        "student.study_plan",
        "student.time_to_learn",
        "student.objective_recs",
        "student.agenda",
        "student.return_meetings",
        "accounting.my_fees",
        "canvas.student",
    ],
    "khao_thi": [
        "admissions.verification_queue",
        "admissions.neu_prep",
        "admissions.applications",
        "admissions.results",
        "admissions.rounds",
        "admissions.round_docs.view",
        "reports.dashboard",
    ],
    "thanh_tra": [
        "admissions.verification_queue",
        "admissions.neu_prep",
        "admissions.applications",
        "admissions.results",
        "admissions.rounds",
        "admissions.round_docs.view",
        "reports.dashboard",
    ],
}

# ---------------------------------------------------------------------------
# Chính sách tổ chức (override danh sách mặc định ở trên)
# - Giám đốc / Trợ lý: xem mọi báo cáo + dữ liệu chi tiết (ops)
# - NghiND: chỉ quản trị danh mục hệ thống
# - Admin: quản trị toàn bộ bản ghi dữ liệu nghiệp vụ (ops), không gồm cấu hình RBAC
# - ThaoP: toàn quyền (is_admin) — mọi dữ liệu + mọi báo cáo + cấu hình hệ thống
# ---------------------------------------------------------------------------
for _dept_codes in DEPT_DEFAULT_PERMISSIONS.values():
    if "admissions.crm_source" in _dept_codes and "admissions.chatbot" not in _dept_codes:
        _dept_codes.insert(_dept_codes.index("admissions.crm_source") + 1, "admissions.chatbot")
for _dept in ("ban_giam_doc", "tro_ly_bgd", "admin_he_thong"):
    if "admissions.chatbot_publish" not in DEPT_DEFAULT_PERMISSIONS.get(_dept, []):
        DEPT_DEFAULT_PERMISSIONS.setdefault(_dept, []).append("admissions.chatbot_publish")

ALL_MENU_CODES = [m["code"] for m in MENU_ITEMS]
OPS_VIEW_CODES = [c for c in ALL_MENU_CODES if not str(c).startswith("admin.")]

# NghiND — nhóm danh mục hệ thống (status, sách, khoản thu…)
ADMIN_CATALOG_CODES = [
    "admin.status_catalog",
    "accounting.fee_types",
    "admissions.doc_types",
]

# Tài khoản Admin — toàn bộ bản ghi dữ liệu ops (không admin.* cấu hình, không báo cáo tổng)
ADMIN_DATA_RECORD_CODES = [
    c for c in OPS_VIEW_CODES if c != "reports.dashboard"
]
if "admin.audit_logs" not in ADMIN_DATA_RECORD_CODES:
    ADMIN_DATA_RECORD_CODES.append("admin.audit_logs")
ADMIN_DATA_RECORD_CODES[:] = [
    c for c in ADMIN_DATA_RECORD_CODES if c != "teaching.grades.publish"
]

# ThaoP — siêu quản trị (dùng kèm is_admin=True)
ADMIN_SUPER_CODES = list(ALL_MENU_CODES)

# Tương thích tên cũ
ADMIN_MANAGE_CODES = list(ADMIN_SUPER_CODES)

DEPT_DEFAULT_PERMISSIONS["ban_giam_doc"] = [
    c for c in OPS_VIEW_CODES if c != "teaching.grades.publish"
]
DEPT_DEFAULT_PERMISSIONS["tro_ly_bgd"] = [
    c for c in OPS_VIEW_CODES if c != "teaching.grades.publish"
]
DEPT_DEFAULT_PERMISSIONS["admin_he_thong"] = [
    c for c in ADMIN_DATA_RECORD_CODES if c != "teaching.grades.publish"
]
for _coord in ("mba", "master_chuyen_nganh"):
    _perms = DEPT_DEFAULT_PERMISSIONS.get(_coord) or []
    if "teaching.grades" in _perms and "teaching.grades.publish" not in _perms:
        _perms.insert(_perms.index("teaching.grades") + 1, "teaching.grades.publish")
# Giám đốc / Trợ lý: theo dõi tài liệu (xem + tải), không CRUD
_DOC_MANAGE, _DOC_VIEW, _DOC_DL = (
    "admissions.round_docs",
    "admissions.round_docs.view",
    "admissions.round_docs.download",
)
for _exec in ("ban_giam_doc", "tro_ly_bgd"):
    _perms = [c for c in DEPT_DEFAULT_PERMISSIONS[_exec] if c != _DOC_MANAGE]
    for _extra in (_DOC_VIEW, _DOC_DL):
        if _extra not in _perms:
            _perms.append(_extra)
    DEPT_DEFAULT_PERMISSIONS[_exec] = _perms
# `it` giữ danh sách hẹp ở trên (canvas.it + dashboard)

# Seed sẽ REPLACE (không chỉ additive) quyền các BP này để gỡ bản ghi vượt quyền cũ
DEPT_PERMISSIONS_FORCE_SYNC = frozenset({
    "it",
    "admin_he_thong",
    "logistic",
    "hoc_vien",
    "giang_vien",
    "ke_toan",
    "marcom",
    "tuyen_sinh",
    "mba",
    "master_chuyen_nganh",
    "khao_thi",
    "thanh_tra",
})

DEPT_DEFAULT_PROGRAM_SCOPES: dict[str, list[str]] = {
    "ban_giam_doc": ["*"],
    "tro_ly_bgd": ["*"],
    "ke_toan": ["*"],  # Thủ quỹ / Kế toán: học phí xuyên suốt mọi CT
    "tuyen_sinh": ["*"],
    "marcom": ["*"],
    "marcom_tuyen_sinh": ["*"],
    "mba": ["MBA"],
    "master_chuyen_nganh": ["MMS", "MSCM"],
    "giang_vien": [],
    "it": ["*"],
    "admin_he_thong": ["*"],
    "logistic": ["*"],
    "hoc_vien": [],
    "cuu_hoc_vien": [],
    "khao_thi": ["*"],
    "thanh_tra": ["*"],
}

USER_PROGRAM_SCOPES: dict[str, list[str]] = {
    "AnhTT": ["*"],
    "NhuTV": ["*"],
    "LinhTHD": ["*"],
    "LoanBT": ["*"],
    # Thủ quỹ + ĐP MBA: tài chính dùng scopes_for_perm (*); đào tạo/thi chỉ MBA
    "HanhNT": ["MBA"],
    "TuanTA": ["*"],
    "NhungLH": ["*"],
    "GiaoNTQ": ["*"],
    "HaLP": ["MBA"],
    "DoanNTN": ["MBA"],
    "LinhTK": ["MMS"],
    "LinhLT": ["MMS"],
    "AnhPTX": ["MSCM"],
    "NghiND": ["*"],
    "TienNH": ["*"],
    "CuongNK": ["*"],
    "DupontJ": ["*"],
    "DupontPJ": ["*"],
    "ChuyenNV": ["*"],
}

# Campus được phân công. Không có dòng = chưa giới hạn campus trong phạm vi chương trình.
# HaLP/DoanNTN: cả HN và HCM vì hồ sơ MBA và danh sách exchange đang có cả hai campus.
# Đây là phân công tường minh, không phải quyền toàn CFVG.
USER_CAMPUS_SCOPES: dict[str, list[str]] = {
    "HaLP": ["HN", "HCM"],
    "DoanNTN": ["HN", "HCM"],
}


def menu_by_code() -> dict[str, dict]:
    return {m["code"]: m for m in MENU_ITEMS}


# Sắp lại thứ tự và nhóm hiển thị mà không đổi mã quyền.
# Tuyển sinh: tiếp nhận → xét duyệt → phỏng vấn → kết quả.
# Thu tiền: chọn khóa trước, rồi nghĩa vụ, phiếu thu, danh mục.
_MENU_NAV_PATCH = {
    "admissions.pre_enroll": {"sort": 20},
    "admissions.verification_queue": {"sort": 21},
    "admissions.neu_prep": {"sort": 22},
    "admissions.written_exams": {"sort": 30},
    "admissions.interviews": {"sort": 31},
    "admissions.results": {"group": "2.TS.Kết quả", "group_en": "2.TS.Results", "sort": 36},
    "admissions.student_numbering": {"group": "2.TS.Kết quả", "group_en": "2.TS.Results", "sort": 37},
    "accounting.intake_plans": {"group": "Thu.Kế hoạch", "group_en": "Fee.Plan", "sort": 50},
    "accounting.round_fee_settings": {"group": "Thu.Kế hoạch", "group_en": "Fee.Plan", "sort": 51},
    "accounting.fees": {"group": "Thu.Nghĩa vụ", "group_en": "Fee.Obligations", "sort": 54},
    "accounting.charges": {"group": "Thu.Nghĩa vụ", "group_en": "Fee.Obligations", "sort": 55},
    "accounting.candidate_files": {"group": "Thu.Nghĩa vụ", "group_en": "Fee.Obligations", "sort": 56},
    "accounting.tuition_tracker": {"group": "Thu.Nghĩa vụ", "group_en": "Fee.Obligations", "sort": 57},
    "accounting.fee_alerts": {"group": "Thu.Nghĩa vụ", "group_en": "Fee.Obligations", "sort": 58},
    "accounting.receipts": {"group": "Thu.Chứng từ", "group_en": "Fee.Receipts", "sort": 59},
    "accounting.payment_imports": {"group": "Thu.Chứng từ", "group_en": "Fee.Receipts", "sort": 60},
    "accounting.receipt_emails": {"group": "Thu.Chứng từ", "group_en": "Fee.Receipts", "sort": 61},
    "accounting.billing_profiles": {"group": "Thu.Chứng từ", "group_en": "Fee.Receipts", "sort": 62},
    "accounting.benefits": {"group": "Thu.Chứng từ", "group_en": "Fee.Receipts", "sort": 63},
    "accounting.refunds": {"group": "Thu.Chứng từ", "group_en": "Fee.Receipts", "sort": 64},
    "accounting.collection_report": {"group": "Thu.Chứng từ", "group_en": "Fee.Receipts", "sort": 64.5},
    "accounting.fee_types": {"group": "Thu.Danh mục", "group_en": "Fee.Catalog", "sort": 65},
    "accounting.payment_methods": {"group": "Thu.Danh mục", "group_en": "Fee.Catalog", "sort": 66},
}


# Gộp nhóm menu chi tiết → ít mục cấp 1 trên thanh nav (Trợ lý / Giám đốc / MBA…)
# key = group hoặc group_en gốc trong MENU_ITEMS
# value = (l1_vi, l1_en, section_vi|None, section_en|None, l1_order)
NAV_L1_FOLD: dict[str, tuple[str, str, str | None, str | None, int]] = {
    "1. Dashboard": ("1. Tổng quan", "1. Overview", None, None, 1),
    "2. Tuyển sinh": ("2. Tuyển sinh", "2. Admissions", None, None, 2),
    "2. Admissions": ("2. Tuyển sinh", "2. Admissions", None, None, 2),
    # Luồng ứng viên: tiếp nhận → xét duyệt hồ sơ → phỏng vấn → kết quả → bàn giao
    "2.TS.Tư vấn": ("2. Tuyển sinh", "2. Admissions", "Tiếp nhận hồ sơ", "Application intake", 2),
    "2.TS.Consulting": ("2. Tuyển sinh", "2. Admissions", "Tiếp nhận hồ sơ", "Application intake", 2),
    "2.TS.Xét duyệt": ("2. Tuyển sinh", "2. Admissions", "Xét duyệt hồ sơ", "File review", 2),
    "2.TS.Review": ("2. Tuyển sinh", "2. Admissions", "Xét duyệt hồ sơ", "File review", 2),
    "2.TS.Thi": ("2. Tuyển sinh", "2. Admissions", "Phỏng vấn", "Interview", 2),
    "2.TS.Exams": ("2. Tuyển sinh", "2. Admissions", "Phỏng vấn", "Interview", 2),
    "2.TS.Kết quả": ("2. Tuyển sinh", "2. Admissions", "Kết quả", "Results", 2),
    "2.TS.Results": ("2. Tuyển sinh", "2. Admissions", "Kết quả", "Results", 2),
    "2.TS.Email": ("2. Tuyển sinh", "2. Admissions", "Email tuyển sinh", "Admission email", 2),
    "2.TS.Bàn giao": ("2. Tuyển sinh", "2. Admissions", "Bàn giao nhập học", "Enrollment handoff", 2),
    "2.TS.Handoff": ("2. Tuyển sinh", "2. Admissions", "Bàn giao nhập học", "Enrollment handoff", 2),
    "Thu.Kế hoạch": ("Thu tiền", "Collections", "Kế hoạch theo khóa", "Intake plan", 4),
    "Fee.Plan": ("Thu tiền", "Collections", "Kế hoạch theo khóa", "Intake plan", 4),
    "Thu.Nghĩa vụ": ("Thu tiền", "Collections", "Nghĩa vụ theo khóa", "Obligations", 4),
    "Fee.Obligations": ("Thu tiền", "Collections", "Nghĩa vụ theo khóa", "Obligations", 4),
    "Thu.Chứng từ": ("Thu tiền", "Collections", "Phiếu thu", "Receipts", 4),
    "Fee.Receipts": ("Thu tiền", "Collections", "Phiếu thu", "Receipts", 4),
    "Thu.Danh mục": ("Thu tiền", "Collections", "Danh mục", "Catalogs", 4),
    "Fee.Catalog": ("Thu tiền", "Collections", "Danh mục", "Catalogs", 4),
    "2.TS.Sự kiện": ("2. Tuyển sinh", "2. Admissions", "Sự kiện tuyển sinh", "Admission events", 2),
    "2.TS.Events": ("2. Tuyển sinh", "2. Admissions", "Sự kiện tuyển sinh", "Admission events", 2),
    "2.TS.Báo cáo": ("2. Tuyển sinh", "2. Admissions", "Báo cáo", "Reports", 2),
    "2.TS.Reports": ("2. Tuyển sinh", "2. Admissions", "Báo cáo", "Reports", 2),
    "Thu tiền": ("Thu tiền", "Collections", None, None, 4),
    "Collections": ("Thu tiền", "Collections", None, None, 4),
    "3. Học viên": ("3. Đào tạo", "3. Academic", "Học viên", "Students", 3),
    "3. Students": ("3. Đào tạo", "3. Academic", "Học viên", "Students", 3),
    "4. Chương trình": ("3. Đào tạo", "3. Academic", "Chương trình", "Programme", 3),
    "4. Programme": ("3. Đào tạo", "3. Academic", "Chương trình", "Programme", 3),
    "5. Lớp học & Lịch học": ("3. Đào tạo", "3. Academic", "Lớp & lịch", "Classes & schedule", 3),
    "5. Classes & Schedule": ("3. Đào tạo", "3. Academic", "Lớp & lịch", "Classes & schedule", 3),
    "6. Giảng viên": ("3. Đào tạo", "3. Academic", "Giảng viên", "Lecturers", 3),
    "6. Lecturers": ("3. Đào tạo", "3. Academic", "Giảng viên", "Lecturers", 3),
    "7. Học vụ": ("3. Đào tạo", "3. Academic", "Học vụ", "Academic affairs", 3),
    "7. Academic Affairs": ("3. Đào tạo", "3. Academic", "Học vụ", "Academic affairs", 3),
    "7b. Học trực tuyến": ("3. Đào tạo", "3. Academic", "Học trực tuyến", "Online learning", 3),
    "7b. Online learning": ("3. Đào tạo", "3. Academic", "Học trực tuyến", "Online learning", 3),
    "8. Luận văn": ("3. Đào tạo", "3. Academic", "Luận văn", "Thesis", 3),
    "8. Thesis": ("3. Đào tạo", "3. Academic", "Luận văn", "Thesis", 3),
    "9. Quốc tế / Exchange": ("4. Quốc tế", "4. Exchange", None, None, 4),
    "9. Exchange": ("4. Quốc tế", "4. Exchange", None, None, 4),
    "10. Hành chính": ("5. Điều hành", "5. Executive ops", None, None, 5),
    "10. Administration": ("5. Điều hành", "5. Executive ops", None, None, 5),
    "11. Alumni": ("7. Alumni", "7. Alumni", None, None, 7),
    "12. Truyền thông": ("6. Truyền thông", "6. Marcom", None, None, 6),
    "12. Marcom": ("6. Truyền thông", "6. Marcom", None, None, 6),
    "Cổng HV": ("8. Cổng HV", "8. Student portal", None, None, 8),
    "Student portal": ("8. Cổng HV", "8. Student portal", None, None, 8),
    "13. Cấu hình": ("9. Hệ thống", "9. System", None, None, 9),
    "13. Configuration": ("9. Hệ thống", "9. System", None, None, 9),
    "A. Tài khoản & phân quyền": (
        "9. Hệ thống",
        "9. System",
        "Tài khoản & phân quyền",
        "Accounts & access",
        9,
    ),
    "A. Accounts & access": (
        "9. Hệ thống",
        "9. System",
        "Tài khoản & phân quyền",
        "Accounts & access",
        9,
    ),
    "B. Theo dõi yêu cầu": (
        "9. Hệ thống",
        "9. System",
        "Theo dõi yêu cầu",
        "Request tracking",
        9,
    ),
    "B. Request tracking": (
        "9. Hệ thống",
        "9. System",
        "Theo dõi yêu cầu",
        "Request tracking",
        9,
    ),
    "C. Danh mục trạng thái": (
        "9. Hệ thống",
        "9. System",
        "Danh mục trạng thái",
        "Status catalogs",
        9,
    ),
    "C. Status catalogs": (
        "9. Hệ thống",
        "9. System",
        "Danh mục trạng thái",
        "Status catalogs",
        9,
    ),
    "D. Thống kê báo cáo": (
        "9. Hệ thống",
        "9. System",
        "Thống kê báo cáo",
        "Reports",
        9,
    ),
    "D. Reports": (
        "9. Hệ thống",
        "9. System",
        "Thống kê báo cáo",
        "Reports",
        9,
    ),
}


def _fold_nav_group(raw_group: str, lang: str) -> tuple[str, str | None, int]:
    """Return (l1_label, section_label|None, order)."""
    meta = NAV_L1_FOLD.get(raw_group)
    if not meta:
        # Fallback: keep original, strip leading "N. "
        label = raw_group.split(". ", 1)[-1] if ". " in raw_group else raw_group
        return (label, None, 99)
    l1_vi, l1_en, sec_vi, sec_en, order = meta
    l1 = l1_en if lang == "en" else l1_vi
    sec = (sec_en if lang == "en" else sec_vi) if (sec_vi or sec_en) else None
    return (l1, sec, order)


def _dept_code_set(departments) -> set[str]:
    codes: set[str] = set()
    for d in departments or []:
        if isinstance(d, dict):
            code = str(d.get("code") or "").strip()
        else:
            code = str(d or "").strip()
        if code:
            codes.add(code)
    return codes


# Màn dùng chung. Bộ phận chủ quản giữ nguyên menu của họ.
# Tuyển sinh (không thuộc bộ phận chủ quản) thấy các màn này là mục con của Tuyển sinh.
_TS_DEPTS = frozenset({"tuyen_sinh", "marcom_tuyen_sinh"})
# code -> (group, group_en, sort, label_vi|None, label_en|None, owner_depts)
_TS_PULL = {
    "marcom.leads": (
        "2.TS.Tư vấn",
        "2.TS.Consulting",
        5.5,
        None,
        None,
        frozenset({"marcom"}),
    ),
    "marcom.events": (
        "2.TS.Sự kiện",
        "2.TS.Events",
        46,
        "Sự kiện tuyển sinh",
        "Admission events",
        frozenset({"marcom"}),
    ),
    "accounting.candidate_files": (
        "2.TS.Bàn giao",
        "2.TS.Handoff",
        40,
        None,
        None,
        frozenset({"ke_toan"}),
    ),
    "accounting.fees": (
        "2.TS.Bàn giao",
        "2.TS.Handoff",
        41,
        None,
        None,
        frozenset({"ke_toan"}),
    ),
}


# HaLP theo một khách hàng đến khi nhập học xong. Sáu nhóm đúng thứ tự team chốt.
# code -> (nhóm, mục con, thứ tự, nhãn hoặc None)
_MBA_MANAGER_NAV: dict[str, tuple[str, str | None, int, str | None]] = {
    "admissions.crm_source": ("Dữ liệu khách hàng", None, 1, "Dữ liệu khách hàng"),
    "admissions.crm_activities": ("Dữ liệu khách hàng", "Chăm sóc", 1, None),
    "admissions.crm_reminders": ("Dữ liệu khách hàng", "Chăm sóc", 1, None),
    "admissions.chatbot": ("Dữ liệu khách hàng", "Chăm sóc", 1, None),
    "admissions.applications": ("Quản lý hồ sơ ứng tuyển", None, 2, None),
    "admissions.rounds": ("Quản lý hồ sơ ứng tuyển", "Đợt", 2, None),
    "admissions.written_exams": ("Quản lý hồ sơ ứng tuyển", "Cùng hồ sơ", 2, None),
    "admissions.interviews": ("Quản lý hồ sơ ứng tuyển", "Cùng hồ sơ", 2, None),
    "admissions.results": ("Quản lý hồ sơ ứng tuyển", "Cùng hồ sơ", 2, None),
    "admissions.pre_enroll": ("Quản lý hồ sơ ứng tuyển", "Cùng hồ sơ", 2, None),
    "admissions.neu_prep": ("Quản lý hồ sơ ứng tuyển", "Cùng hồ sơ", 2, None),
    "admissions.round_docs": ("Quản lý hồ sơ ứng tuyển", "Tài liệu", 2, None),
    "admissions.doc_types": ("Quản lý hồ sơ ứng tuyển", "Tài liệu", 2, None),
    "admissions.enrolled_files": ("Quản lý nhập học", None, 3, None),
    "accounting.official_list": ("Quản lý nhập học", None, 3, None),
    "accounting.fees": ("Quản lý nhập học", "Theo dõi phí", 3, "Phí ghi danh (xem)"),
    "admissions.student_numbering": ("Quản lý nhập học", None, 3, None),
    "students.manage": ("Quản lý nhập học", "Đã nhập học", 3, None),
    "students.academic": ("Quản lý nhập học", "Đã nhập học", 3, None),
    "admissions.events": ("Sự kiện tuyển sinh", None, 4, "Sự kiện tuyển sinh"),
    "accounting.benefits": ("Chương trình ưu đãi", None, 5, "Chương trình ưu đãi"),
    "admissions.crm_reports": ("Báo cáo", None, 6, None),
    "intl.exchange_reports": ("Báo cáo", None, 6, None),
    "canvas.coordinator": ("Báo cáo", "Đồng bộ", 6, None),
    "alumni.members": ("Quản lý nhập học", "Sau nhập học", 3, None),
    "alumni.events": ("Quản lý nhập học", "Sau nhập học", 3, None),
    "teaching.student_tracker": ("Quản lý nhập học", "Đã nhập học", 3, None),
    "intl.partners": ("Đối tác", None, 7, None),
    "intl.cooperation_programs": ("Đối tác", None, 7, None),
    "intl.workflow_steps": ("Đối tác", None, 7, None),
    "asst.intl_students": ("Đối tác", None, 7, None),
    "programs.structure": ("Đào tạo", None, 8, None),
    "programs.courses": ("Đào tạo", None, 8, None),
    "classes.manage": ("Đào tạo", None, 8, None),
    "teaching.faculty": ("Đào tạo", None, 8, None),
    "teaching.assign": ("Đào tạo", None, 8, None),
    "teaching.schedule": ("Đào tạo", None, 8, None),
    "teaching.materials": ("Đào tạo", None, 8, None),
    "teaching.lessons": ("Đào tạo", None, 8, None),
    "teaching.online_lectures": ("Đào tạo", None, 8, None),
    "teaching.objectives": ("Đào tạo", None, 8, None),
    "teaching.instructor_intel": ("Đào tạo", None, 8, None),
    "teaching.groups": ("Đào tạo", None, 8, None),
    "asst.intl_faculty": ("Đào tạo", None, 8, None),
    "teaching.attendance": ("Đào tạo", "Học vụ", 8, None),
    "teaching.assignments": ("Đào tạo", "Học vụ", 8, None),
    "teaching.grades": ("Đào tạo", "Học vụ", 8, None),
    "teaching.grades.publish": ("Đào tạo", "Học vụ", 8, None),
    "teaching.exams": ("Đào tạo", "Học vụ", 8, None),
    "teaching.evaluation": ("Đào tạo", "Học vụ", 8, None),
    "teaching.thesis": ("Đào tạo", "Học vụ", 8, None),
    "teaching.review_batches": ("Đào tạo", "Học vụ", 8, None),
    "teaching.exam_integrity": ("Đào tạo", "Học vụ", 8, None),
    "teaching.return_meetings": ("Đào tạo", "Học vụ", 8, None),
}


def build_nav_from_permissions(
    permission_codes: list[str],
    lang: str = "vi",
    departments=None,
) -> list[dict]:
    """Group visible menu items into compact level-1 nav dropdowns (role / permission based)."""
    allowed = set(permission_codes)
    dept_codes = _dept_code_set(departments)
    mba_manager = dept_codes == {"mba"}
    pull_shared = bool(dept_codes & _TS_DEPTS) and not mba_manager
    # Dashboard → brand/home; admin.* → dropdown Admin riêng
    skip_nav = {"reports.dashboard"}
    items = []
    for src in MENU_ITEMS:
        visible = (
            (
                src["code"] in allowed
                or (
                    src["code"] == "admissions.round_docs"
                    and (
                        "admissions.round_docs.view" in allowed
                        or "admissions.round_docs.download" in allowed
                    )
                )
            )
            and src["code"] not in skip_nav
            and not str(src["code"]).startswith("admin.")
            and src.get("nav", True)
        )
        if not visible:
            continue
        row = dict(src)
        patch = _MENU_NAV_PATCH.get(row["code"])
        if patch:
            row.update(patch)
        spec = _TS_PULL.get(row["code"]) if pull_shared else None
        if spec and not (dept_codes & spec[5]):
            row["group"], row["group_en"], row["sort"] = spec[0], spec[1], spec[2]
            if spec[3]:
                row["label"] = spec[3]
            if spec[4]:
                row["label_en"] = spec[4]
        items.append(row)
    items.sort(key=lambda m: m["sort"])

    # l1_label -> {"order", "items": [...], "sections_seen"}
    buckets: dict[str, dict] = {}
    order_keys: list[str] = []

    for m in items:
        mapped = _MBA_MANAGER_NAV.get(m["code"]) if mba_manager else None
        if mapped:
            l1, section, l1_order, label_override = mapped
            label = label_override or m["label"]
        else:
            raw_g = m["group_en"] if lang == "en" else m["group"]
            l1, section, l1_order = _fold_nav_group(raw_g, lang)
            if l1_order == 99:
                alt = m["group"] if lang == "en" else m["group_en"]
                l1, section, l1_order = _fold_nav_group(alt, lang)
            label = m["label"] if mba_manager else (m["label_en"] if lang == "en" else m["label"])
        entry = {**m, "label": label, "group": l1, "section": section}

        if l1 not in buckets:
            buckets[l1] = {"order": l1_order, "items": [], "_sections": set()}
            order_keys.append(l1)
        buckets[l1]["items"].append(entry)
        if section:
            buckets[l1]["_sections"].add(section)

    # Stable sort by fold order, then first-seen
    ordered = sorted(order_keys, key=lambda k: (buckets[k]["order"], order_keys.index(k)))
    result = []
    for g in ordered:
        bucket = buckets[g]
        entries = bucket["items"]
        # Show L2 section headers whenever a fold merges source groups (e.g. Đào tạo)
        show_sections = len(bucket["_sections"]) > 1
        if show_sections:
            last_sec = object()
            for e in entries:
                e["show_section"] = bool(e.get("section") and e["section"] != last_sec)
                if e.get("section"):
                    last_sec = e["section"]
        else:
            for e in entries:
                e["show_section"] = False
                e["section"] = None
        result.append({"group": g, "items": entries})
    return result
