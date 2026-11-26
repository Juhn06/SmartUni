"""Export function catalog + accounts + activity descriptions to Excel."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

from main import get_db
from rbac import DEPT_DEFAULT_PERMISSIONS, MENU_ITEMS, NAV_L1_FOLD, USER_PROGRAM_SCOPES
from seed_org import TEMP_PASSWORD, seed_departments_and_users, get_user_access
from workflow_links import DEPT_APPLICATION_ACTIONS, STATUS_TRANSITIONS

OUT = BACKEND.parent / "nghiepvu" / "Danh_sach_chuc_nang_SmartUni.xlsx"
OUT_SIMPLE = BACKEND.parent / "nghiepvu" / "Danh_sach_chuc_nang.xlsx"

# Mô tả hoạt động chi tiết theo mã chức năng
ACTIVITY = {
    "teaching.lessons": "Import buổi từ syllabus vào lớp–môn; thêm/upload bài học; publish; HV preview và Q&A.",
    "teaching.online_lectures": "Tạo/phát bài giảng trực tuyến (file hoặc link) theo lịch; HV xem + hỏi đáp; thảo luận nhóm.",
    "teaching.objectives": "Phân tích syllabus/buổi học → mục tiêu + bước đạt mục tiêu.",
    "teaching.instructor_intel": "Theo dõi tiến độ lớp: phút xem, câu hỏi, HV rủi ro.",
    "teaching.student_tracker": "Phút học, tiến độ xem bài, cảnh báo HV chậm theo lớp–môn.",
    "teaching.exam_integrity": "Phiên thi: checklist CCCD / ảnh chân dung / cam kết — không so khớp khuôn mặt.",
    "teaching.return_meetings": "Họp trực tuyến cho HV bảo lưu/nghỉ học; lưu URL hỗ trợ trở lại.",
    "student.study_plan": "HV tạo kế hoạch ôn tập theo chủ đề còn lại.",
    "student.time_to_learn": "Ước lượng phút còn lại theo mức độ xem bài.",
    "student.objective_recs": "Đề xuất mục tiêu cá nhân và cách đạt.",
    "student.agenda": "Xếp lịch ngày/tuần theo thời gian còn lại.",
    "student.return_meetings": "HV xem lịch họp hỗ trợ trở lại lớp.",
    "student.lessons": "HV xem preview bài học lớp, tải file đã release, đặt câu hỏi/comment.",
    "student.library": "HV xem syllabus đã công bố, nội dung buổi học; tìm kiếm và tải tài liệu đã release.",
    "programs.structure": "Quản lý phiên bản khung CT; theo dõi số học phần theo phiên bản.",
    "programs.courses": "Syllabus, chuẩn đầu ra, đánh giá; cấu trúc buổi LT/TH; mở chi tiết nội dung.",
    "teaching.materials": "Upload tài liệu theo HP/buổi; release/thu hồi; tìm kiếm và tải file.",
    "canvas.coordinator": "Hub Điều phối: xuất gói lớp SIS (users/courses/enrollments) lên Canvas.",
    "canvas.faculty": "Hub GV: theo dõi lớp–môn Canvas, checklist tài liệu/SpeedGrader.",
    "canvas.student": "Hub HV: trạng thái enroll + hướng dẫn login x.instructure.com.",
    "canvas.accounting": "Hub Ghi danh: xuất roster HV official → Canvas People.",
    "canvas.it": "Hub IT: SIS map, nhật ký sync, đánh dấu đã đẩy Canvas.",
    "asst.exec_tasks": "Họp BGD → biên bản → giao nhiệm vụ → người phụ trách/hạn → theo dõi tiến độ; xuất báo cáo sau họp.",
    "asst.calendar": "Lịch tuần X (BGD, họp, sự kiện, giảng dạy, nghỉ phép); cảnh báo trùng; thông báo thay đổi.",
    "asst.intl_faculty": "Hồ sơ GV quốc tế: hộ chiếu, visa, vé, KS, BH, đón tiễn, lịch giảng; cảnh báo hết hạn.",
    "asst.intl_students": "Exchange In/Out (double degree / 1 HK); visa→Trợ lý, IAE→KT, môn→Điều phối; onboarding.",
    "asst.director_fr": "Visa, work permit, cư trú Giám đốc Pháp & gia đình; cảnh báo hết hạn giấy tờ.",
    "asst.documents": "Công văn đến/đi; cấp số; đóng dấu X; sổ văn thư.",
    "asst.procurement": "Mua VP phẩm, Lavie, taxi/đón tiễn; đề xuất → mua → hóa đơn.",
    "asst.payments": "Theo dõi hóa đơn vé máy bay/taxi/VP phẩm; trạng thái thanh toán tháng; phối hợp Kế toán.",
    "asst.weekly_report": "Tổng hợp hoạt động các bộ phận → BGD duyệt → báo cáo tuần gửi NEU.",
    "asst.leave": "Đăng ký/phê duyệt nghỉ phép; lịch nghỉ; người thay thế; đồng bộ lịch làm việc.",
    "admissions.rounds": "Tạo/đóng đợt TS; intake + timeline thi viết/PV; CT MBA/MMS/MSCM (MBA thường May & Aug).",
    "admissions.round_docs": "Tìm tài liệu theo đợt tuyển sinh; tải lên, xem trước, tải xuống. Kế toán (Hạnh) và Admin khai báo/đẩy file theo đợt.",
    "admissions.doc_types": "Khai báo danh mục loại tài liệu (quy chế, thông báo, hội đồng, giấy phép, báo cáo, biên bản, minh chứng). Kế toán và Admin dùng khi tải tài liệu đợt.",
    "admissions.applications": "Nhận hồ sơ; issue checklist X/Incompleted/Exempted/Not required; phản hồi chất lượng; hướng dẫn lịch thi/PV; duyệt TS (transferred_at/by).",
    "admissions.written_exams": "TS lập DS thi viết gửi Admin CT; Admin cập nhật không phản hồi sau deadline; ĐP gán SBD/điểm.",
    "admissions.interviews": "TS gửi DS và trực hỗ trợ PV; Admin CT cập nhật ngay no-show.",
    "admissions.results": "Admin gửi KQ đầu vào; TS nhắc chứng chỉ TA và xác nhận văn bằng trước khai giảng.",
    "admissions.events": "Sự kiện/workshop/campaign: TS chăm sóc trước–trong–sau; Marcom quảng bá; cập nhật mức quan tâm vào Enquiry.",
    "admissions.neu_prep": "Chuẩn bị xét duyệt NEU: hồ sơ Thanh tra Pháp chế, minh chứng TA Khảo thí, theo dõi văn bản NEU, nộp HTQT. Admin thực thi, TS phối hợp.",
    "admissions.mail": "Mẫu email tuyển sinh: tạo, sửa nội dung và gửi cho ứng viên theo chương trình.",
    "admissions.pre_enroll": "Hồ sơ tuyển sinh chưa thành học viên, cùng hồ sơ cá nhân, có bước xác nhận dự thi.",
    "admissions.enrolled_files": "Hồ sơ theo học sau quyết định có hiệu lực: mã học viên theo chương trình, cùng mã ứng viên.",
    "admissions.crm_source": "Sổ Enquiry 2022–2026 (chỉ phòng TS): PIC Giao/Nhung, Level, năm, kênh, nhắc lịch. Không dùng Application list. Nguồn campaign/web/sự kiện đổ về đây.",
    "admissions.crm_activities": "Đợt chăm sóc và sự kiện trên Enquiry: chọn hồ sơ nguồn, ghi chi tiết chăm sóc.",
    "admissions.crm_reminders": "Nhắc lịch Enquiry: in danh sách / email / gọi điện.",
    "admissions.crm_reports": "Báo cáo Enquiry: mức quan tâm (Hot/Warm/Cold/…) và phễu Apply/Candidate/Fail/Select/Quit/Postpone/Enroll theo chương trình.",
    "accounting.fees": "Theo dõi phí ghi danh sau passed; KT mark-paid (deposit); TS theo dõi tiến độ.",
    "accounting.official_list": "DS official; xuất Khảo thí NEU (TA/văn bằng); ĐP tạo lớp / Canvas.",
    "accounting.charges": "Sổ công nợ mọi CT. Thanh toán nhiều lần. Học bổng, giảm phí, hỗ trợ và hoàn lập thành đề nghị, người khác duyệt.",
    "accounting.benefits": "Một hồ sơ học bổng, giảm phí hoặc hỗ trợ: giảm nghĩa vụ hoặc chi ra tài khoản, không ghi cả hai.",
    "accounting.refunds": "Hồ sơ hoàn: số đề nghị, số duyệt, số đã chi. Thu nhầm thì đảo giao dịch và giữ nghĩa vụ.",
    "accounting.billing_profiles": "Thông tin người nhận hóa đơn, cá nhân hoặc doanh nghiệp. Bản mới không sửa bản đã lưu.",
    "accounting.intake_plans": "Kế hoạch thu theo chương trình và khóa, đơn vị VND. Chốt nhập học sinh khoản phải thu, bỏ qua đợt đã có.",
    "accounting.tuition_tracker": "Theo dõi tình trạng đóng học phí từng HV: đã nộp / một phần / sắp hạn / quá hạn.",
    "accounting.fee_alerts": "Cảnh báo tự động khi sắp hạn, quá hạn, hoặc HV có nhiều khoản trễ; Kế toán chỉnh ngưỡng tiêu chí.",
    "accounting.candidate_files": "Kế toán xem/cập nhật hồ sơ thí sinh: khoản thu, miễn giảm, hai bảng liên kết (xét tuyển / nhập học), khai báo loại tài liệu, tìm và tải tài liệu theo đợt.",
    "accounting.collection_report": "Báo cáo thu tiền: tổng đã thu (kể cả miễn phí), còn nợ, theo loại khoản thu và thời gian.",
    "accounting.fee_types": "Danh mục khoản thu (inscription, tuition, retake, resit, transcript…) — cấu hình Thủ quỹ.",
    "students.manage": "Lifecycle HV; học bổng (CFVG/partner/French gov/partial); IAE/reserve; → alumni khi tốt nghiệp.",
    "students.academic": "Học viên gốc nối hồ sơ ứng viên. Bảng chính thức chỉ điểm đã công bố; bảng theo dõi gồm sáu trạng thái tiến độ.",
    "student.progress": "Cổng HV: bảng chính thức đã công bố; tiến độ môn đã học / đang học / sắp học / chưa đạt.",
    "programs.structure": "Quản lý phiên bản khung CT; copy version; theo dõi số học phần.",
    "programs.courses": "Syllabus, chuẩn đầu ra, đánh giá; cấu trúc buổi LT/TH; mặc định 8 buổi (MBA).",
    "classes.manage": "Tạo lớp từ DS official (auto-enroll); Enroll official; gắn version CT; xuất DS.",
    "teaching.faculty": "Hồ sơ GV: lịch sử dạy CFVG, HĐ/TT, trả điểm, BH; vé/KS → asst.intl_faculty.",
    "teaching.schedule": "Lịch học lớp–môn theo buổi; phòng/ca; đồng bộ điểm danh.",
    "teaching.assign": "Phân GV LT + chuyên gia cho lớp–môn; tự sinh buổi giảng.",
    "teaching.groups": "Tạo nhóm SV theo môn; SV nhìn thấy nhóm của mình.",
    "teaching.attendance": "Điểm danh 2 lần/buổi. QR chỉ ghi nhận một lần, không phải bằng chứng có mặt. Sửa điểm danh đã có phải ghi lý do.",
    "teaching.assignments": "Theo dõi nộp bài tập cá nhân/nhóm; xuất điểm thành phần.",
    "teaching.grades": "Bảng điểm tổng hợp lớp–môn. Mỗi lần sửa giữ một lần thi trong course_grade_attempts. Khóa điểm không xóa điểm cũ.",
    "teaching.grades.publish": "Điều phối MBA/Master khóa và công bố điểm chính thức.",
    "teaching.exams": "Lịch thi; đề TL/TN; thi lại; hiển thị ineligible_count từ điểm danh.",
    "teaching.evaluation": "Form đánh giá; cổng 60% quản lý / 80% GV trước khi đóng.",
    "teaching.thesis": "Theo dõi đề án/luận văn: GVHD, Turnitin/AI%, hội đồng, lịch BV, điểm.",
    "alumni.members": "DS cựu HV theo khóa/CT/lớp; đồng bộ từ lifecycle=graduated; tìm kiếm; email.",
    "alumni.events": "Tạo sự kiện; lọc đối tượng; gửi lời mời; in/xuất DS.",
    "alumni.portal": "Cựu học viên sửa hồ sơ; xem sự kiện chung và sự kiện được mời.",
    "marcom.leads": "Người quan tâm trên hồ sơ cá nhân chung. Không bắt CCCD. Bàn giao tuyển sinh để tư vấn và nhận hồ sơ.",
    "marcom.campaigns": "Kế hoạch và ngân sách marketing. Kế toán rồi Ban Giám đốc duyệt trước khi triển khai. Chi phí lấy từ phân bổ đã xác nhận.",
    "marcom.events": "Sự kiện tuyển sinh, workshop, webinar, hội thảo, gặp khách hàng, Alumni. Diễn giả, khách mời, báo cáo sau sự kiện.",
    "marcom.assets": "Nội dung text/ảnh/video/thiết kế/ấn phẩm và lịch kênh. Thuê ngoài chỉ sau khi ngân sách được duyệt.",
    "marcom.reports": "Báo cáo tổng hợp tháng, quý, nửa năm, năm cho Ban Giám đốc. Không nhập lại số liệu.",
    "student.profile": "Thí sinh/HV cập nhật hồ sơ cá nhân và minh chứng nộp phí.",
    "student.schedule": "Xem lịch phỏng vấn / lịch học được thông báo.",
    "student.results": "Xem kết quả tuyển sinh và điểm (khi được mở).",
    "reports.dashboard": "Báo cáo tổng quan số liệu theo scope chương trình được giao.",
    "admin.users": "Khóa/mở, gán admin, reset MK; rà soát tên/login/bộ phận.",
    "admin.departments": "DS bộ phận + số thành viên; rà soát thiếu tên/TV.",
    "admin.permissions": "Gán quyền chức năng theo bộ phận; gán scope CT theo user (ThaoP).",
    "admin.suggestions": "Thu thập đề xuất; rà soát nội dung + người gửi.",
    "admin.status_catalog": "Danh mục trạng thái + sách; rà soát mã/nhãn.",
    "admin.reports": "Hub thống kê hệ thống & liên kết báo cáo (ThaoP).",
    "admin.audit_logs": "Nhật ký thao tác; rà soát thời gian + người thực hiện.",
}

HANDOFF = {
    "admissions.applications": "TS checklist + duyệt (approved_ts + transferred_at/by) → Admin/Điều phối CT; TS không gửi KQ đầu vào hộ Admin.",
    "admissions.written_exams": "TS gửi DS thi viết → Admin CT cập nhật không phản hồi; ĐP gán SBD/điểm.",
    "admissions.interviews": "TS trực hỗ trợ PV; Admin CT cập nhật no-show ngay cho TS.",
    "admissions.results": "Admin thông báo KQ đầu vào và trúng tuyển; TS nhắc giấy tờ trước khai giảng rồi bàn giao hồ sơ HV.",
    "admissions.events": "Marcom lập nội dung; TS mời/chăm sóc trước–trong–sau và ghi mức quan tâm về Enquiry.",
    "admissions.neu_prep": "TS phối hợp, Admin thực thi: Thanh tra Pháp chế + Khảo thí + văn bản NEU + nộp HTQT. Hội đồng xét duyệt do Admin lead (T8–T9).",
    "admissions.pre_enroll": "TS/ĐP quản lý hồ sơ xét tuyển; cùng mã UV với bảng đã nhập học khi Enroll official.",
    "admissions.enrolled_files": "Quyết định có hiệu lực → program_enrollments (mã học viên theo chương trình); liên thông class_students + applications.cfvg_app_no.",
    "admissions.crm_source": "TS làm việc trên file Enquiry → chăm sóc → chuyển ứng viên khi nhận hồ sơ. Application list ngưng dùng.",
    "admissions.crm_activities": "TS tạo đợt chăm sóc; chọn hồ sơ nguồn; ghi chú; nhắc trước đợt.",
    "admissions.crm_reminders": "TS in/email/gọi theo danh sách nhắc.",
    "admissions.crm_reports": "TS và lãnh đạo xem báo cáo mức quan tâm và phễu tuyển sinh theo chương trình.",
    "admissions.rounds": "TS/ĐP lập đợt + timeline; TS mở/đóng hồ sơ theo mùa.",
    "admissions.round_docs": "KT/Admin/TS tìm theo đợt; upload/preview/download; quyền xem và tải tách theo tài khoản.",
    "admissions.doc_types": "KT (Hạnh) / NghiND / Admin khai báo phân loại; đợt TS chọn loại khi tải tài liệu.",
    "accounting.candidate_files": "KT cập nhật hồ sơ + mức miễn; hai bảng liên kết; tài liệu đợt (phân loại / tìm theo đợt / tải lên).",
    "accounting.official_list": "official → xuất Khảo thí NEU (TS) → ĐP tạo lớp / enroll_official.",
    "accounting.charges": "Official → tuition charges; Thủ quỹ thu/điều chỉnh; liên thông students.manage (scholarship_type).",
    "accounting.tuition_tracker": "Kế toán theo dõi TT nộp học phí HV; KPI quá hạn trên Dashboard.",
    "accounting.fee_alerts": "Tiêu chí hạn nộp / số khoản trễ → cảnh báo live khi dữ liệu thay đổi.",
    "accounting.collection_report": "KT/BGD xem tổng thu gồm miễn phí; còn nợ; cảnh báo chậm trên fee_alerts.",
    "accounting.fee_types": "NghiND/ThaoP cấu hình danh mục; Thủ quỹ dùng khi tạo khoản thu.",
    "students.manage": "Coord cập nhật lifecycle + scholarship; graduated → promote_graduated_to_alumni.",
    "students.academic": "ĐP/HV xem cùng một hồ sơ cá nhân: ứng viên → người dự thi chính thức → học viên của chương trình.",
    "student.progress": "HV in bảng điểm và báo cáo tiến độ của chính mình.",
    "classes.manage": "Chỉ enroll app status=official (scope CT); sinh mã HV vào class_students.",
    "teaching.attendance": "Vắng (cả trước/sau giải lao) >30% → ineligible trên teaching.exams + email.",
    "teaching.exams": "Đọc eligibility từ điểm danh trước khi cho thi.",
    "teaching.faculty": "Coord cập nhật HĐ/trả điểm; logistics vé/KS → asst.intl_faculty (Trợ lý/Logistic).",
    "teaching.assign": "Điều phối theo 1 CT; Giám đốc học thuật (NhuTV) mọi CT.",
    "teaching.materials": "Điều phối/GV upload; học viên xem.",
    "teaching.online_lectures": "GV/ĐP phát bài; HV xem theo lịch; hỏi đáp trên bài giảng; nhóm học tập.",
    "teaching.objectives": "ĐP/GV tạo mục tiêu từ syllabus; HV dùng recommender trên cổng.",
    "teaching.instructor_intel": "GV xem tiến độ lớp từ thời gian xem + điểm danh/điểm.",
    "teaching.student_tracker": "GV/ĐP theo dõi HV; dữ liệu từ lesson_view_sessions.",
    "teaching.exam_integrity": "GV/ĐP tạo phiên từ lịch thi; xác minh checklist trước giờ thi.",
    "teaching.return_meetings": "ĐP/GV họp HV on_leave/reserved; HV xem lịch trên cổng.",
    "student.study_plan": "HV tạo kế hoạch từ bài chưa xem hết.",
    "student.time_to_learn": "HV tính phút còn lại; ĐP xem cùng quyền.",
    "student.objective_recs": "HV nhận gợi ý mục tiêu chưa đạt.",
    "student.agenda": "HV xếp lịch tuần; điều chỉnh khi tiến độ đổi (tạo lại).",
    "student.return_meetings": "HV bảo lưu/nghỉ xem URL họp hỗ trợ trở lại.",
    "asst.intl_students": "Visa→Trợ lý BGD; enrollment IAE→KT (Hạnh); courses→Điều phối (Đoan).",
    "asst.intl_faculty": "Coord bàn giao GV nước ngoài; Trợ lý/Logistic xử lý visa–vé–KS–đón tiễn.",
    "asst.payments": "Logistics theo dõi; Kế toán đối chiếu thanh toán.",
    "marcom.leads": "Marcom bàn giao → hồ sơ applications (submitted). Tuyển sinh xác nhận tiếp nhận và chăm sóc.",
    "marcom.events": "Marcom tổ chức; TS theo dõi ứng viên sau sự kiện; loại Alumni liên kết alumni_events.",
    "marcom.campaigns": "Marcom lập và theo dõi. Kế toán duyệt rồi xác nhận chi phí. Ban Giám đốc duyệt ngân sách và xem báo cáo.",
    "marcom.assets": "Marcom sản xuất. Thuê ngoài chờ duyệt ngân sách. Kế toán xác nhận chi phí thanh toán.",
    "marcom.reports": "Báo cáo gửi Ban Giám đốc CFVG, ghi kỳ và thời điểm chốt số liệu.",
    "admin.permissions": "IT / Admin hệ thống.",
}

# Dữ liệu nghiệp vụ gắn từng mã chức năng (xuất theo BP)
DATA_ENTITIES = {
    "admissions.rounds": "admission_rounds (mã đợt, intake, timeline thi/PV, CT)",
    "admissions.round_docs": "admission_round_docs + file uploads",
    "admissions.doc_types": "admission_doc_types (phân loại tài liệu)",
    "admissions.applications": "applications (hồ sơ, checklist, TA/VB, status, transferred_*, learner_id)",
    "admissions.written_exams": "điểm thi viết / SBD / phòng-ca; exam_registrations (lệ phí thi, danh sách hội đồng)",
    "admissions.interviews": "interview boards/slots, điểm PV, no-show",
    "admissions.results": "final_result, email KQ, giấy tờ trước KG",
    "admissions.pre_enroll": "applications chưa có program_enrollments — cùng person_profiles",
    "admissions.enrolled_files": "program_enrollments + mã học viên theo chương trình, cùng PersonId",
    "admissions.crm_source": "crm_source_profiles (Enquiry: PIC, level, intake, kênh, checklist, app_stage)",
    "admissions.events": "marcom_events (giai đoạn trước/trong/sau, admission_owner, người đăng ký)",
    "admissions.neu_prep": "applications đã đỗ: thanh_tra_status, khao_thi_status, neu_doc_status, htqt_status, checklist mục",
    "admissions.crm_activities": "crm_activities + crm_activity_participants",
    "admissions.crm_reminders": "crm_reminders",
    "admissions.crm_reports": "báo cáo mức quan tâm và phễu Apply/Candidate/Select/Enroll theo chương trình",
    "accounting.fees": "enrollment_fees (deposit pending/paid, proof)",
    "accounting.official_list": "applications status=official; neu_packet_ready",
    "accounting.charges": "student_charges, fee_payments, payment_allocations",
    "accounting.benefits": "financial_benefits — giảm nghĩa vụ hoặc chi ra tài khoản",
    "accounting.refunds": "refund_cases — đề nghị, duyệt, chi",
    "accounting.billing_profiles": "billing_profiles — cá nhân/doanh nghiệp, MST, CCCD, địa chỉ",
    "accounting.intake_plans": "fee_intake_plans theo chương trình và khóa",
    "accounting.tuition_tracker": "tổng hợp student_charges theo HV (còn phải thu, quá hạn, hạn gần nhất)",
    "accounting.fee_alerts": "fee_alert_criteria + cảnh báo live từ student_charges",
    "accounting.candidate_files": "nghĩa vụ phí hồ sơ đăng ký; miễn % hoặc số tiền; cam kết dự thi",
    "accounting.collection_report": "phải thu ban đầu / miễn / phải thu sau miễn / thực thu / còn phải thu",
    "accounting.receipts": "phiếu thu nhiều lần / một nghĩa vụ; mã GD chống trùng",
    "accounting.payment_methods": "danh mục hình thức nộp",
    "accounting.round_fee_settings": "đơn giá khoản thu theo đợt",
    "accounting.intake_plans": "Kế hoạch thu theo chương trình và khóa. Khi chốt nhập học, các đợt học phí sinh từ kế hoạch này.",
    "accounting.payment_imports": "import thu CCCD+đợt+mã khoản+mã GD",
    "accounting.receipt_emails": "email cảm ơn sau phiếu thu",
    "accounting.my_fees": "cổng HV xem nghĩa vụ phí; gửi minh chứng không tự xác nhận đã thu",
    "admissions.verification_queue": "hàng đợi khảo thí/thanh tra (chỉ xem/xuất)",
    "admissions.student_numbering": "cấp mã học viên theo chương trình sau quyết định có hiệu lực; không tạo thêm một người",
    "teaching.review_batches": "đợt xét + snapshot điểm + GPA tín chỉ",
    "intl.partners": "trường đối tác / mã viết tắt",
    "intl.cooperation_programs": "chương trình hợp tác Incoming/Outgoing",
    "intl.workflow_steps": "danh mục bước trao đổi",
    "intl.exchange_reports": "báo cáo theo trường đối tác",
    "admin.audit_logs": "nhật ký điểm/phiếu thu/miễn/cấp mã/import",
    "accounting.fee_types": "fee_type_catalog (danh mục khoản thu)",
    "students.manage": "class_students / lifecycle, scholarship_type, IAE, reserve",
    "students.academic": "learners + course_grades + course_grade_attempts. Bảng chính thức = điểm đã khóa.",
    "student.progress": "course_grades đã công bố, lesson_view_sessions, attendance_marks theo learners",
    "programs.structure": "program_versions",
    "programs.courses": "courses, course_sessions, syllabus",
    "classes.manage": "classes, class_students, mã HV",
    "teaching.faculty": "faculty (HĐ, trả điểm, CFVG payment)",
    "teaching.assign": "teaching_assignments, buổi giảng",
    "teaching.schedule": "lịch lớp–môn–phòng",
    "teaching.materials": "materials files + release status",
    "teaching.lessons": "class_lessons, comments Q&A",
    "teaching.online_lectures": "class_lessons (video_url, publish_at) + lesson_comments",
    "teaching.objectives": "elearn_objectives",
    "teaching.instructor_intel": "lesson_view_sessions + class_lessons stats",
    "teaching.student_tracker": "class_students + lesson_view_sessions",
    "teaching.exam_integrity": "elearn_exam_sittings + exam_schedules",
    "teaching.return_meetings": "elearn_return_meetings (HV on_leave/reserved)",
    "student.study_plan": "elearn_study_plans + elearn_plan_items",
    "student.time_to_learn": "tính remaining_min từ lesson_view_sessions",
    "student.objective_recs": "elearn_objective_recs",
    "student.agenda": "elearn_agenda",
    "student.return_meetings": "elearn_return_meetings (cổng HV)",
    "teaching.groups": "study_groups",
    "teaching.attendance": "attendance marks (trước/sau giải lao)",
    "teaching.assignments": "assignment submissions / điểm thành phần",
    "teaching.grades": "course_grades (tổng hợp) + course_grade_attempts (từng lần thi)",
    "teaching.grades.publish": "khóa course_grades và đánh dấu lần thi mới nhất đã công bố",
    "teaching.exams": "exams, eligibility từ điểm danh",
    "teaching.evaluation": "evaluations (cổng 60/80)",
    "teaching.thesis": "thesis_records",
    "alumni.members": "alumni_members",
    "alumni.events": "alumni_events, invitees",
    "alumni.portal": "alumni_members.user_id, alumni_events",
    "marcom.leads": "person_profiles, marcom_leads, candidate_interests, source_touchpoints",
    "marcom.campaigns": "marcom_campaigns, campaign_cost_allocations, asst_tasks",
    "marcom.events": "marcom_events, marcom_event_registrants, marcom_event_speakers",
    "marcom.assets": "marcom_assets (nội dung), content_publications",
    "marcom.reports": "tổng hợp từ chiến dịch, sự kiện, nội dung, hồ sơ — không bảng nhập riêng",
    "asst.exec_tasks": "asst_tasks / biên bản họp BGD",
    "asst.calendar": "asst_calendar",
    "asst.intl_faculty": "asst_intl_faculty (visa/vé/KS)",
    "asst.intl_students": "asst_intl_students (exchange handoff)",
    "asst.director_fr": "asst_director_fr",
    "asst.documents": "asst_documents (công văn)",
    "asst.procurement": "asst_procurement",
    "asst.payments": "asst_payments",
    "asst.weekly_report": "asst_weekly_reports",
    "asst.leave": "asst_leave",
    "student.profile": "hồ sơ portal HV/TS",
    "student.schedule": "lịch PV / lịch học portal",
    "student.results": "timeline / kết quả portal",
    "student.library": "syllabus + tài liệu released",
    "student.lessons": "preview bài học lớp",
    "canvas.coordinator": "canvas export packs (SIS)",
    "canvas.faculty": "canvas faculty hub",
    "canvas.student": "canvas student hub",
    "canvas.accounting": "canvas roster official",
    "canvas.it": "canvas sync log / SIS map",
    "reports.dashboard": "summary metrics theo scope",
    "admin.users": "user, departments, permissions",
    "admin.departments": "departments",
    "admin.permissions": "user_permissions, program scopes",
    "admin.suggestions": "suggestions / góp ý",
    "admin.status_catalog": "status_catalog, book categories",
    "admin.reports": "admin hub stats",
}

DEPT_LABELS = {
    "ban_giam_doc": "Ban Giám đốc",
    "tro_ly_bgd": "Trợ lý Ban Giám đốc",
    "ke_toan": "Kế toán / Thủ quỹ",
    "tuyen_sinh": "Tuyển sinh",
    "mba": "Điều phối MBA",
    "master_chuyen_nganh": "Điều phối Master (MMS/MSCM)",
    "giang_vien": "Giảng viên",
    "it": "IT",
    "admin_he_thong": "Admin hệ thống (bản ghi dữ liệu)",
    "logistic": "Logistics",
    "hoc_vien": "Học viên (portal)",
    "marcom": "Marcom / Truyền thông",
    "khao_thi": "Khảo thí",
    "thanh_tra": "Thanh tra",
}


def menu_path(item: dict) -> str:
    group = item.get("group") or ""
    fold = NAV_L1_FOLD.get(group) or NAV_L1_FOLD.get(item.get("group_en") or "")
    if fold:
        l1, _l1_en, section, _sec_en, _order = fold
        path = f"{l1} › {section}" if section else l1
    else:
        path = group
    if item.get("nav") is False:
        return f"{path} (quyền, không hiện trên menu)"
    return path


def function_rows(perm_users: dict[str, list[str]]) -> list[list]:
    rows = []
    for m in sorted(MENU_ITEMS, key=lambda x: (x.get("sort") or 0, x["code"])):
        code = m["code"]
        logins = sorted(set(perm_users.get(code, [])))
        desc = ACTIVITY.get(code) or m.get("workflow") or ""
        rows.append([m.get("label") or code, menu_path(m), ", ".join(logins), desc])
    return rows


def write_simple_sheet(ws, rows: list[list]) -> None:
    headers = ["Chức năng", "Menu", "Danh sách tài khoản có", "Mô tả"]
    ws.append(headers)
    for row in rows:
        ws.append(row)
    style_header(ws)
    wrap = Alignment(wrap_text=True, vertical="top")
    thin = Border(
        left=Side(style="thin", color="B0B0B0"),
        right=Side(style="thin", color="B0B0B0"),
        top=Side(style="thin", color="B0B0B0"),
        bottom=Side(style="thin", color="B0B0B0"),
    )
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=4):
        for cell in row:
            cell.alignment = wrap
            cell.border = thin
    ws.row_dimensions[1].height = 22
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 38
    ws.column_dimensions["C"].width = 56
    ws.column_dimensions["D"].width = 72
    ws.auto_filter.ref = f"A1:D{ws.max_row}"
    ws.freeze_panes = "A2"
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def style_header(ws, row=1):
    fill = PatternFill("solid", fgColor="085CA7")
    font = Font(color="FFFFFF", bold=True)
    thin = Border(
        left=Side(style="thin", color="B0B0B0"),
        right=Side(style="thin", color="B0B0B0"),
        top=Side(style="thin", color="B0B0B0"),
        bottom=Side(style="thin", color="B0B0B0"),
    )
    for cell in ws[row]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = thin


def autosize(ws, max_width=48):
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        width = 10
        for cell in col:
            val = "" if cell.value is None else str(cell.value)
            width = min(max(width, min(len(val) + 2, max_width)), max_width)
        ws.column_dimensions[letter].width = width


def main():
    with get_db() as conn:
        seed_departments_and_users(conn)
        cur = conn.cursor()
        users = []
        for r in cur.execute(
            "SELECT u.id, u.email, u.name, u.is_admin "
            "FROM user u WHERE u.email NOT LIKE '%@%' ORDER BY u.email"
        ):
            acc = get_user_access(conn, r[0])
            users.append(
                {
                    "id": r[0],
                    "login": r[1],
                    "name": r[2],
                    "is_admin": bool(r[3]),
                    "departments": acc["departments"],
                    "scopes": acc["program_scopes"],
                    "perms": acc["permission_codes"],
                    "theme": acc.get("theme", "courses"),
                    "lang": acc.get("lang", "vi"),
                }
            )

        # permission -> list of logins
        perm_users: dict[str, list[str]] = {m["code"]: [] for m in MENU_ITEMS}
        for u in users:
            for p in u["perms"]:
                perm_users.setdefault(p, []).append(u["login"])

    wb = Workbook()

    simple_rows = function_rows(perm_users)
    ws0 = wb.active
    ws0.title = "Danh_sach"
    write_simple_sheet(ws0, simple_rows)

    simple_wb = Workbook()
    simple_ws = simple_wb.active
    simple_ws.title = "Danh_sach"
    write_simple_sheet(simple_ws, simple_rows)

    # ---- Sheet: Chức năng (chi tiết) ----
    ws1 = wb.create_sheet("Chuc_nang")
    headers1 = [
        "STT",
        "Ma_chuc_nang",
        "Nhom_menu",
        "Ten_chuc_nang",
        "Ten_EN",
        "Thu_tu",
        "Mo_ta_hoat_dong",
        "Lien_ket_ban_giao",
        "Endpoint",
        "So_tai_khoan",
        "Danh_sach_tai_khoan",
    ]
    ws1.append(headers1)
    for i, m in enumerate(sorted(MENU_ITEMS, key=lambda x: x["sort"]), start=1):
        code = m["code"]
        logins = sorted(perm_users.get(code, []))
        ws1.append(
            [
                i,
                code,
                m["group"],
                m["label"],
                m.get("label_en", ""),
                m["sort"],
                ACTIVITY.get(code, m.get("workflow", "")),
                HANDOFF.get(code, m.get("workflow", "")),
                m["route"],
                len(logins),
                ", ".join(logins),
            ]
        )
    style_header(ws1)
    autosize(ws1)

    # ---- Sheet 2: Tai_khoan ----
    ws2 = wb.create_sheet("Tai_khoan")
    headers2 = [
        "STT",
        "Ten_dang_nhap",
        "Mat_khau_tam",
        "Ho_ten_vai_tro",
        "Bo_phan",
        "Ma_bo_phan",
        "Scope_chuong_trinh",
        "Theme",
        "Ngon_ngu",
        "Is_Admin",
        "So_chuc_nang",
        "Danh_sach_chuc_nang",
    ]
    ws2.append(headers2)
    for i, u in enumerate(users, start=1):
        dept_names = "; ".join(d["name"] for d in u["departments"])
        dept_codes = ", ".join(d["code"] for d in u["departments"])
        labels = []
        by_code = {m["code"]: m["label"] for m in MENU_ITEMS}
        for p in u["perms"]:
            labels.append(by_code.get(p, p))
        ws2.append(
            [
                i,
                u["login"],
                TEMP_PASSWORD,
                u["name"],
                dept_names,
                dept_codes,
                ", ".join(u["scopes"]) if u["scopes"] else "",
                u["theme"],
                u["lang"],
                "Yes" if u["is_admin"] else "No",
                len(u["perms"]),
                "; ".join(labels),
            ]
        )
    style_header(ws2)
    autosize(ws2, max_width=60)

    # ---- Sheet 3: Ma_tran (user x function) ----
    ws3 = wb.create_sheet("Ma_tran_User_ChucNang")
    codes = [m["code"] for m in sorted(MENU_ITEMS, key=lambda x: x["sort"])]
    ws3.append(["Ten_dang_nhap", "Bo_phan", "Scope"] + codes)
    for u in users:
        row = [
            u["login"],
            ", ".join(d["code"] for d in u["departments"]),
            ",".join(u["scopes"]),
        ]
        pset = set(u["perms"])
        for c in codes:
            row.append("X" if c in pset else "")
        ws3.append(row)
    style_header(ws3)
    autosize(ws3, max_width=22)

    # ---- Sheet 4: Bo_phan ----
    ws4 = wb.create_sheet("Bo_phan_Quyen")
    ws4.append(["Ma_bo_phan", "Danh_sach_ma_chuc_nang", "So_quyen"])
    for code, perms in DEPT_DEFAULT_PERMISSIONS.items():
        if code == "marcom_tuyen_sinh":
            continue
        ws4.append([code, "; ".join(perms), len(perms)])
    style_header(ws4)
    autosize(ws4, max_width=80)

    # ---- Sheet 5: Ban_giao_trang_thai ----
    ws5 = wb.create_sheet("Ban_giao_trang_thai")
    ws5.append(
        [
            "Trang_thai_hien_tai",
            "Duoc_chuyen_sang",
            "Bo_phan_duoc_phep",
            "Mo_ta_ban_giao",
        ]
    )
    for cur, rule in STATUS_TRANSITIONS.items():
        ws5.append(
            [
                cur,
                ", ".join(rule["to"]),
                ", ".join(rule["by_departments"]),
                rule["label"],
            ]
        )
    style_header(ws5)
    autosize(ws5, max_width=55)

    # ---- Sheet 6: Thao_tac_ho_so ----
    ws6 = wb.create_sheet("Thao_tac_ho_so_theo_BP")
    ws6.append(["Ma_bo_phan", "Nhan_thao_tac", "Trang_thai_dich"])
    for dept, actions in DEPT_APPLICATION_ACTIONS.items():
        for a in actions:
            ws6.append([dept, a["label"], a["status"]])
    style_header(ws6)
    autosize(ws6)

    # ---- Sheet 7: Chức năng theo bộ phận (1 dòng / quyền) ----
    by_code = {m["code"]: m for m in MENU_ITEMS}
    ws7 = wb.create_sheet("Bo_phan_Chuc_nang")
    ws7.append(
        [
            "Ma_bo_phan",
            "Ten_bo_phan",
            "Ma_chuc_nang",
            "Ten_chuc_nang",
            "Nhom_menu",
            "Mo_ta_hoat_dong",
            "Lien_ket_ban_giao",
            "Du_lieu_nghiep_vu",
            "Tai_khoan_mau",
        ]
    )
    # sample logins per dept from users
    dept_logins: dict[str, list[str]] = {}
    for u in users:
        for d in u["departments"]:
            dept_logins.setdefault(d["code"], []).append(u["login"])

    for dcode, perms in sorted(DEPT_DEFAULT_PERMISSIONS.items()):
        if dcode == "marcom_tuyen_sinh":
            continue
        dlabel = DEPT_LABELS.get(dcode, dcode)
        samples = ", ".join(sorted(set(dept_logins.get(dcode, [])))[:8])
        for p in perms:
            m = by_code.get(p) or {}
            ws7.append(
                [
                    dcode,
                    dlabel,
                    p,
                    m.get("label", p),
                    m.get("group", ""),
                    ACTIVITY.get(p, m.get("workflow", "")),
                    HANDOFF.get(p, ""),
                    DATA_ENTITIES.get(p, ""),
                    samples,
                ]
            )
    style_header(ws7)
    autosize(ws7, max_width=55)

    # ---- Sheet 8: Danh sách dữ liệu theo bộ phận (gom) ----
    ws8 = wb.create_sheet("Bo_phan_Du_lieu")
    ws8.append(
        [
            "Ma_bo_phan",
            "Ten_bo_phan",
            "Ma_chuc_nang",
            "Ten_chuc_nang",
            "Danh_sach_du_lieu",
            "Ghi_chu_lien_thong",
        ]
    )
    for dcode, perms in sorted(DEPT_DEFAULT_PERMISSIONS.items()):
        if dcode == "marcom_tuyen_sinh":
            continue
        dlabel = DEPT_LABELS.get(dcode, dcode)
        for p in perms:
            m = by_code.get(p) or {}
            data = DATA_ENTITIES.get(p, "")
            if not data:
                continue
            ws8.append(
                [
                    dcode,
                    dlabel,
                    p,
                    m.get("label", p),
                    data,
                    HANDOFF.get(p, ""),
                ]
            )
    style_header(ws8)
    autosize(ws8, max_width=60)

    # ---- Sheet 9: Tóm tắt BP (1 dòng / BP) ----
    ws9 = wb.create_sheet("Bo_phan_Tom_tat")
    ws9.append(
        [
            "Ma_bo_phan",
            "Ten_bo_phan",
            "So_chuc_nang",
            "Danh_sach_chuc_nang",
            "Danh_sach_du_lieu",
            "Tai_khoan_mau",
            "Scope_mac_dinh_user",
        ]
    )
    for dcode, perms in sorted(DEPT_DEFAULT_PERMISSIONS.items()):
        if dcode == "marcom_tuyen_sinh":
            continue
        labels = []
        data_bits = []
        for p in perms:
            m = by_code.get(p) or {}
            labels.append(m.get("label", p))
            if DATA_ENTITIES.get(p):
                data_bits.append(f"{p}: {DATA_ENTITIES[p]}")
        # scopes from users in this dept
        scopes = set()
        for u in users:
            if any(d["code"] == dcode for d in u["departments"]):
                scopes.update(u["scopes"] or [])
        ws9.append(
            [
                dcode,
                DEPT_LABELS.get(dcode, dcode),
                len(perms),
                "; ".join(labels),
                " | ".join(data_bits),
                ", ".join(sorted(set(dept_logins.get(dcode, [])))),
                ", ".join(sorted(scopes)) if scopes else "",
            ]
        )
    style_header(ws9)
    autosize(ws9, max_width=70)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    simple_wb.save(OUT_SIMPLE)
    print(f"Wrote {OUT}")
    print(f"Wrote {OUT_SIMPLE}")
    print(f"Functions={len(MENU_ITEMS)} Users={len(users)} Password={TEMP_PASSWORD}")
    print(
        "Sheets: Danh_sach, Chuc_nang, Tai_khoan, Ma_tran_User_ChucNang, Bo_phan_Quyen, "
        "Ban_giao_trang_thai, Thao_tac_ho_so_theo_BP, Bo_phan_Chuc_nang, "
        "Bo_phan_Du_lieu, Bo_phan_Tom_tat"
    )
    try:
        from export_functions_word import main as export_word

        export_word()
    except Exception as e:
        print(f"Word export skipped: {e}")


if __name__ == "__main__":
    main()
