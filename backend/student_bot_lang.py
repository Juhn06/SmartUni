"""Language layer for the student assistant: Vietnamese and English, routing English through the Vietnamese rule engine."""

from __future__ import annotations

import hashlib
import re

VI_ANY_RE = re.compile(r"[ăâđêôơưàáạảãấầẩẫậắằẳẵặèéẹẻẽếềểễệìíỉĩịòóọỏõốồổỗộớờởỡợùúụủũứừửữựỳýỵỷỹ]", re.IGNORECASE)
LANGS = ("vi", "en")
EN_WORDS = set(
    "what which when where who why how my i am me do does did is are was were have has had much many owe still "
    "show tell please can could will would about this next last current upcoming any all the my your of for to in on "
    "grade grades score scores mark marks gpa fee fees tuition paid pay payment payments overdue due exam exams test "
    "schedule course courses subject subjects module modules semester term thesis progress graduate graduation status "
    "highest lowest average total remaining left unpaid outstanding class classes lesson lessons interview hi hello "
    "thanks thank you want need help staff human person".split()
)
VI_WORDS = set(
    "toi cua khong mon diem hoc phi bao nhieu ky lich nao gi minh em chua roi duoc nhung cac xem dau sao vay "
    "thi luan van tot nghiep tien trinh dong han con no ban oi nhe a".split()
)

EN_TO_VI = [
    (r"\b(talk|speak|chat) (to|with) (a )?(staff|human|person|someone|officer|advisor)\b", " gap can bo "),
    (r"\b(real person|human agent|contact staff)\b", " gap can bo "),
    (r"\bthank(s| you)?\b", " cam on "),
    (r"\b(hi|hello|hey|good (morning|afternoon|evening))\b", " xin chao "),
    (r"\b(worried|anxious|stressed|afraid|scared|nervous)\b", " lo lang "),
    (r"\b(english|language) (certificate|certification|test score)s?\b", " chung chi tieng anh "),
    (r"\b(written|entrance) exam scores?\b", " diem thi viet "),
    (r"\binterview scores?\b", " diem phong van "),
    (r"\b(admission|entrance) (scores?|results?|record)\b", " diem dau vao "),
    (r"\b(bachelor'?s?( degree)?|undergraduate degree|university degree|diploma|degree)\b", " bang dai hoc "),
    (r"\btoday\b", " hom nay "),
    (r"\btomorrow\b", " ngay mai "),
    (r"\bthis week\b", " tuan nay "),
    (r"\bnext week\b", " tuan sau "),
    (r"\b(retakes?|resits?|re-?exams?)\b", " thi lai "),
    (r"\b(fail|failed|failing)\b", " truot "),
    (r"\b(pass|passed)\b", " qua mon "),
    (r"\b(committee|jury|panel)\b", " hoi dong "),
    (r"\b(scholarships?|tuition (reduction|discount)s?|discounts?)\b", " hoc bong "),
    (r"\b(exempt(ed|ion)?|recogni[sz]ed credits?)\b", " duoc mien "),
    (r"\b(defer(ral|red|ment)?|deferring)\b", " bao luu "),
    (r"\bon leave\b", " tam nghi "),
    (r"\b(withdrawn|withdrawal|withdraw)\b", " thoi hoc "),
    (r"\b(inscription|enrollment|enrolment|registration) fees?\b", " phi ghi danh "),
    (r"\btuition( fees?)?\b", " hoc phi "),
    (r"\b(how much|what) do i (still )?owe\b", " toi con no bao nhieu "),
    (r"\b(still )?ow(e|es|ed|ing)\b", " con no "),
    (r"\b(outstanding|unpaid|not (yet )?paid|haven'?t paid)\b", " chua dong "),
    (r"\b(overdue|late|past due)\b", " qua han "),
    (r"\bnext (fee|payment|installment|due)( to pay)?\b", " khoan phi tiep theo "),
    (r"\b(compare|compared|versus|vs)\b", " so voi "),
    (r"\bhow (high|good|well|bad|low) (are|is|were|was)\b", " "),
    (r"\bhow am i doing\b", " "),
    (r"\b(course |study |learning )?materials?\b", " hoc lieu "),
    (r"\b(can|could|may|should) i\b", " "),
    (r"\b(due date|deadline)s?\b", " han dong "),
    (r"\b(already )?paid\b", " da dong tien "),
    (r"\bpay\b", " dong tien "),
    (r"\bpayments?\b", " thanh toan "),
    (r"\bfees?\b", " khoan phi "),
    (r"\b(in total|total|altogether|whole program)\b", " tong "),
    (r"\b(this|current) (semester|term)\b", " ky nay "),
    (r"\b(last|previous) (semester|term)\b", " ky truoc "),
    (r"\bnext (semester|term)\b", " ky sau "),
    (r"\b(first|1st) (semester|term)\b", " ky 1 "),
    (r"\b(second|2nd) (semester|term)\b", " ky 2 "),
    (r"\b(third|3rd) (semester|term)\b", " ky 3 "),
    (r"\b(semester|term) (\d{1,2})\b", r" ky \2 "),
    (r"\bhow many (courses|subjects|modules)\b", " bao nhieu mon "),
    (r"\b(completed|finished|done with)\b", " hoc xong "),
    (r"\b(am i taking|am taking|currently taking|studying)\b", " dang hoc "),
    (r"\b(not yet taken|remaining|left to take)\b", " con lai "),
    (r"\b(courses|subjects|modules)\b", " cac mon "),
    (r"\b(course|subject|module)\b", " mon "),
    (r"\b(grades?|scores?|marks?|results?) (in|for|of) (the )?(course |subject |module )?", " diem mon "),
    (r"\b(transcript|grades|grade|scores|score|marks|mark|results)\b", " diem "),
    (r"\b(highest|best|top)\b", " cao nhat "),
    (r"\b(lowest|worst)\b", " thap nhat "),
    (r"\baverage\b", " trung binh "),
    (r"\battendance\b", " chuyen can "),
    (r"\bnext (exam|test)s?\b", " lich thi sap toi "),
    (r"\bnext (class|lesson)(es|s)?\b", " lich hoc sap toi "),
    (r"\bnext interviews?\b", " phong van sap toi "),
    (r"\b(exam schedule|exams|exam|tests|test)\b", " lich thi "),
    (r"\b(class schedule|timetable|lessons|lesson|classes)\b", " lich hoc "),
    (r"\binterviews?\b", " phong van "),
    (r"\b(upcoming|coming up|soon)\b", " sap toi "),
    (r"\bwhen\b", " khi nao "),
    (r"\b(thesis|dissertation)\b", " luan van "),
    (r"\b(defen[cs]e|defend)\b", " bao ve "),
    (r"\b(supervisor|advisor|adviser)\b", " huong dan "),
    (r"\b(graduated|graduation|graduate)\b", " tot nghiep "),
    (r"\bstudent (id|code|number)\b", " ma hoc vien "),
    (r"\b(which|what) class am i in\b", " lop cua toi "),
    (r"\bmy class\b(?! (schedule|tomorrow|today))", " lop cua toi "),
    (r"\bclass\b", " lich hoc "),
    (r"\b(progress|status|study path)\b", " tien trinh "),
    (r"\b(how to|how do|how can|how does)\b", " lam sao "),
    (r"\b(regulations?|rules?|polic(y|ies)|procedures?)\b", " quy dinh "),
    (r"\b(requirements?|conditions?)\b", " dieu kien "),
    (r"\bwhere\b", " o dau "),
    (r"\bwhy\b", " vi sao "),
    (r"\bnext\b", " tiep theo "),
    (r"\b(my|mine|me|i)\b", " toi "),
]
EN_FILLER = set(
    "what which is are was were the a an do does did have has had am please show tell can could you list of for in on "
    "to about give any there still so far yet currently right now at moment with be been get see know want would like "
    "need let check how much many s m it its and or find study studies than more who whom whose any anything have has got".split()
)

VI_FIXED = {
    "Tôi có khoản nào quá hạn không?": "Do I have any overdue fees?",
    "Khoản tiếp theo tôi phải đóng là gì?": "What is my next fee to pay?",
    "Lịch thi sắp tới của tôi": "My upcoming exams",
    "Lịch phỏng vấn của tôi": "My interview schedule",
    "Lịch học sắp tới của tôi": "My upcoming classes",
    "Ngày bảo vệ luận văn của tôi": "My thesis defense date",
    "Điểm các môn của tôi": "My course grades",
    "Môn nào tôi có điểm cao nhất?": "Which course has my highest grade?",
    "Tôi còn khoản phí nào chưa đóng?": "Do I have any unpaid fees?",
    "Tiến trình học tập của tôi": "My study progress",
    "Xem học liệu ở đâu?": "Where can I find course materials?",
}

STAGE_TITLES = {
    "Nộp / tiếp nhận hồ sơ tuyển sinh": "Application submitted / received",
    "TS phê duyệt → chuyển Điều phối": "Admissions approval → coordination",
    "Checklist / văn bằng / TA": "Checklist / degrees / English",
    "Lịch & kết quả phỏng vấn": "Interview schedule & result",
    "Kết quả trúng tuyển": "Admission result",
    "Thanh toán phí ghi danh": "Inscription fee payment",
    "Nhập học chính thức (Official)": "Official enrollment",
    "Hồ sơ tuyển sinh": "Admission file",
    "Xếp lớp / danh sách học viên": "Class assignment",
    "Điểm từng môn học": "Course grades",
    "Điểm danh các buổi học": "Class attendance",
    "Lịch / hoàn thành bài thi": "Exams scheduled / completed",
    "Chuyên đề / luận văn tốt nghiệp": "Graduation thesis",
    "Xét tốt nghiệp": "Graduation review",
    "Chuyển Alumni": "Alumni transfer",
    "Thi viết": "Written exam",
    "Xếp lớp": "Class assignment",
    "Chương trình Master Chuyên ngành": "the Specialized Master Program",
    "Chương trình MBA": "the MBA Program",
    "bộ phận chương trình": "the program office",
}

PROGRESS_EN = {
    "đã học xong": "completed",
    "đang học": "in progress",
    "chưa học": "not started",
    "chưa đạt": "not passed",
    "sắp học": "upcoming",
    "miễn / công nhận": "exempted / recognized",
}


def _what_en(text: str) -> str:
    out = text.lower()
    for a, b in (
        ("lịch thi, lịch học hay phỏng vấn", "exams, classes or interviews"),
        ("lịch phỏng vấn", "interviews"),
        ("lịch thi", "exams"),
        ("lịch học", "classes"),
        (" và ", " and "),
    ):
        out = out.replace(a, b)
    return out


def _courses_word(n: str) -> str:
    return "course" if n == "1" else "courses"


VI_TO_EN = [
    (r"Mình chưa tìm thấy hồ sơ tuyển sinh gắn với tài khoản của bạn\.", "I couldn't find an admission record linked to your account."),
    (r"Hồ sơ đầu vào của bạn:", "Your admission record:"),
    (r"Bạn được miễn (\d+) môn, đã công nhận tín chỉ:", lambda m: f"You are exempted from {m.group(1)} {_courses_word(m.group(1))}, credits recognized:"),
    (r"Trong (.+?), bạn không được miễn môn nào\.", r"In \1, you are not exempted from any course."),
    (r"học phần khác: (\d+) môn", lambda m: f"other modules: {m.group(1)} {_courses_word(m.group(1))}"),
    (r"- Chứng chỉ tiếng Anh: hồ sơ chưa ghi nhận\.", "- English certificate: not recorded."),
    (r"- Bằng đại học: hồ sơ chưa ghi nhận\.", "- Bachelor's degree: not recorded."),
    (r"- Chứng chỉ tiếng Anh: ", "- English certificate: "),
    (r", cấp ngày ", ", issued "),
    (r", số ([A-Z0-9-]+)", r", no. \1"),
    (r", đã được xác minh", ", verified"),
    (r", chưa xác minh", ", not yet verified"),
    (r"- Bằng đại học: ngành ", "- Bachelor's degree: "),
    (r", xếp loại Giỏi", ", classification Very good"),
    (r", xếp loại Trung bình khá", ", classification Fairly good"),
    (r", xếp loại Khá", ", classification Good"),
    (r", xếp loại Trung bình", ", classification Average"),
    (r", xếp loại Xuất sắc", ", classification Excellent"),
    (r"Trường Đại học ([^,\n]+)", r"\1 University"),
    (r", năm (\d{4})", r", \1"),
    (r"Tài chính ngân hàng", "Banking and Finance"),
    (r"Logistics và quản lý chuỗi cung ứng", "Logistics and Supply Chain Management"),
    (r"Quản trị kinh doanh", "Business Administration"),
    (r"- Điểm thi viết: ", "- Written exam score: "),
    (r"; điểm phỏng vấn: ", "; interview score: "),
    (r"; điểm trung bình xét tuyển: ", "; admission average: "),
    (r"; kết quả: không trúng tuyển", "; result: not admitted"),
    (r"; kết quả: trúng tuyển", "; result: admitted"),
    (r"Bạn không có môn nào chưa đạt\.", "You have not failed any course."),
    (r" Còn (\d+) môn chưa có điểm\.", lambda m: f" {m.group(1)} {_courses_word(m.group(1))} still without a grade."),
    (r"Bạn có (\d+) môn chưa đạt:", lambda m: f"You have {m.group(1)} failed {_courses_word(m.group(1))}:"),
    (r", thi lại (\S+), phòng (\S+)", r", retake on \1, room \2"),
    (r", thi lại (\S+)", r", retake on \1"),
    (r"Lịch của bạn (hôm nay|ngày mai|trong 7 ngày tới|tuần sau):", lambda m: "Your schedule " + {
        "hôm nay": "today", "ngày mai": "tomorrow", "trong 7 ngày tới": "for the next 7 days", "tuần sau": "next week"}[m.group(1)] + ":"),
    (r"Bạn không có (.+?) nào (hôm nay|ngày mai|trong 7 ngày tới|tuần sau)\.", lambda m: f"You have no {_what_en(m.group(1))} " + {
        "hôm nay": "today", "ngày mai": "tomorrow", "trong 7 ngày tới": "in the next 7 days", "tuần sau": "next week"}[m.group(2)] + "."),
    (r"Gần nhất sắp tới:", "Next one:"),
    (r"Bạn đã tốt nghiệp, hồ sơ không có quyết định bảo lưu, tạm nghỉ hay thôi học\.",
     "You have graduated; your record has no deferral, leave or withdrawal decision."),
    (r"Bạn chưa được xếp lớp nên chưa có môn nào đang học\.", "You have not been assigned to a class yet, so you have no courses in progress."),
    (r"Bạn chưa được xếp lớp nên chưa có điểm môn nào\.", "You have not been assigned to a class yet, so you have no grades yet."),
    (r" Chương trình (\S+) gồm (\d+) môn: (.+?)\.(?= Lớp|$)", r" The \1 program has \2 courses: \3."),
    (r" Lớp và lịch học sẽ hiện trong cổng học viên khi bạn được xếp lớp\.",
     " Your class and schedule will appear in the portal once you are assigned."),
    (r": môn này được miễn học, công nhận tín chỉ\.", ": this course is exempted and its credits are recognized."),
    (r": môn này chưa có điểm vì bạn đang học\.", ": no grade yet because you are still taking it."),
    (r": môn này chưa có điểm vì bạn chưa học\.", ": no grade yet because you have not started it."),
    (r"miễn học, được công nhận tín chỉ", "exempted, credits recognized"),
    (r"chưa có điểm", "no grade yet"),
    (r"học phí gốc (.+?), được giảm (.+?), ", r"original tuition \1, reduced by \2, "),
    (r"Bạn đang hưởng (.+?), số phải đóng ở trên đã trừ phần được giảm\.",
     r"You have \1; the amounts due above already include the reduction."),
    (r"Bạn đang hưởng (.+?), tổng được giảm (.+?):", r"You have \1, with a total reduction of \2:"),
    (r"Hồ sơ của bạn hiện không có học bổng hay khoản miễn giảm học phí nào\.",
     "Your record has no scholarship or tuition reduction."),
    (r"Bạn đang hưởng (.+?)\.", r"You have \1."),
    (r"học bổng một phần học phí", "a partial tuition scholarship"),
    (r"học bổng đối tác", "a partner scholarship"),
    (r"học bổng Chính phủ Pháp", "a French government scholarship"),
    (r"học bổng CFVG", "a CFVG scholarship"),
    (r"học bổng khác", "a scholarship"),
    (r"Bạn đang học bình thường, hồ sơ không có quyết định bảo lưu, tạm nghỉ hay thôi học\.",
     "You are studying normally; your record has no deferral, leave or withdrawal decision."),
    (r"Trạng thái học tập: bạn ", "Study status: you are "),
    (r"Hồ sơ của bạn chưa có thông tin về (.+?)\.", lambda m: "Your record has no information about " + ", ".join(
        {"luận văn": "the thesis", "xét tốt nghiệp": "graduation review", "nhập học chính thức": "official enrollment",
         "xếp lớp": "class assignment", "điểm danh": "attendance", "cựu học viên": "alumni status"}.get(x.strip(), x.strip())
        for x in m.group(1).split(",")) + " yet."),
    (r"Bạn đã trúng tuyển chương trình (\S+), hiện chưa được xếp lớp\.",
     r"You have been admitted to the \1 program and have not been assigned to a class yet."),
    (r"\bđang thực hiện\b", "in progress"),
    (r"\bđã xếp lịch bảo vệ\b", "defense scheduled"),
    (r"\bđang bảo lưu\b", "on deferral"),
    (r"\bđang tạm nghỉ\b", "on leave"),
    (r"\bđã thôi học\b", "withdrawn"),
    (r"Chào bạn! Bạn cần hỏi gì về học tập, học phí, lịch thi hay thủ tục học vụ\?",
     "Hi! What would you like to ask about your studies, fees, exams or academic procedures?"),
    (r"Rất vui được hỗ trợ bạn! Cần gì cứ nhắn mình nhé\.", "Happy to help! Message me anytime."),
    (r"Mình đã chuyển yêu cầu của bạn tới (.+?)\. Cán bộ sẽ trả lời ngay trong khung chat này\.",
     r"I've forwarded your request to \1. Staff will reply right here in this chat."),
    (r"Câu này mình chưa có trong hồ sơ của bạn và tài liệu học vụ nên không trả lời để tránh sai\. "
     r"Mình đã chuyển câu hỏi tới (.+?), cán bộ sẽ trả lời ngay trong khung chat này\.",
     r"I don't have this in your records or the academic documents, so I won't guess. "
     r"I've forwarded your question to \1; staff will reply right here in this chat."),
    (r"Mình hiểu bạn đang lo, mình cùng xem cụ thể nhé\.", "I understand you're worried, let's look at it together."),
    (r"Nếu cần trao đổi trực tiếp, bạn nhắn \"gặp cán bộ\", mình sẽ chuyển ngay cho cán bộ chương trình hỗ trợ bạn\.",
     "If you'd like to talk to someone directly, type \"talk to staff\" and I'll connect you with program staff right away."),
    (r"Hiện chưa có môn học nào được ghi nhận cho bạn\.", "No courses have been recorded for you yet."),
    (r"Bạn không có môn nào trong (.+?)\. Các môn của bạn thuộc học kỳ ([\d, ]+)\.",
     r"You have no courses in \1. Your courses are in semester \2."),
    (r"Bạn không có môn nào trong (.+?)\.", r"You have no courses in \1."),
    (r"Trong (.+?), bạn không có môn nào (đã học xong|đang học|chưa học)\.",
     lambda m: f"In {m.group(1)}, you have no " + {
         "đã học xong": "completed courses", "đang học": "courses in progress", "chưa học": "courses left to take",
     }[m.group(2)] + "."),
    (r" Tất cả (\d+) môn đều đã học xong: (.+?)\.$", r" All courses there are completed: \2."),
    (r"Trong (.+?), bạn có (\d+) môn (đã học xong|đang học|chưa học):",
     lambda m: f"In {m.group(1)}, you have {m.group(2)} {PROGRESS_EN[m.group(3)]} {_courses_word(m.group(2))}:"),
    (r"Trong (.+?), bạn có (\d+) môn", lambda m: f"In {m.group(1)}, you have {m.group(2)} {_courses_word(m.group(2))}"),
    (r"Bạn đã học xong tất cả các môn\. Học kỳ gần nhất là học kỳ (\d+), có (\d+) môn",
     lambda m: f"You have completed all your courses. Your most recent semester is semester {m.group(1)}, with {m.group(2)} {_courses_word(m.group(2))}"),
    (r"học kỳ (\d+): (\d+) môn", lambda m: f"semester {m.group(1)}: {m.group(2)} {_courses_word(m.group(2))}"),
    (r"Hiện chưa có điểm môn học nào được ghi nhận cho bạn\. Điểm sẽ hiện ở mục Bảng điểm & tiến độ khi giảng viên công bố\.",
     "No course grades have been recorded for you yet. Grades will appear under Transcript & progress once lecturers publish them."),
    (r"Điểm tổng kết các môn của bạn \((\d+) môn\):", lambda m: f"Your final grades ({m.group(1)} {_courses_word(m.group(1))}):"),
    (r"Điểm (.+?) của bạn \((\d+) môn\):", lambda m: f"Your grades for {m.group(1)} ({m.group(2)} {_courses_word(m.group(2))}):"),
    (r"- (.+?): tổng kết (\S+) \(quá trình (\S+), thi (\S+)\)", r"- \1: final \2 (coursework \3, exam \4)"),
    (r"Điểm trung bình các môn đã có điểm trong (.+?): ([\d.]+)\.", r"Average of graded courses in \1: \2."),
    (r"Điểm trung bình (.+?) \(([\d.]+)\) cao hơn (.+?) \(([\d.]+)\) ([\d.]+) điểm\.",
     r"Your average in \1 (\2) is \5 points higher than in \3 (\4)."),
    (r"Điểm trung bình (.+?) và (.+?) bằng nhau \(([\d.]+)\)\.", r"Your averages in \1 and \2 are equal (\3)."),
    (r"Cả (\d+) môn đã có điểm của bạn đều bằng nhau, cùng điểm tổng kết ([\d.]+)\.",
     r"All \1 of your graded courses have the same final grade, \2."),
    (r"Điểm tổng kết (cao nhất|thấp nhất) của bạn là ([\d.]+), đồng điểm ở (\d+) môn: (.+?)\.",
     lambda m: f"Your {'highest' if m.group(1) == 'cao nhất' else 'lowest'} final grade is {m.group(2)}, shared by {m.group(3)} courses: {m.group(4)}."),
    (r"Điểm tổng kết (cao nhất|thấp nhất) của bạn là ([\d.]+), ở môn (.+?)\.(?=\s|$)",
     lambda m: f"Your {'highest' if m.group(1) == 'cao nhất' else 'lowest'} final grade is {m.group(2)}, in {m.group(3)}."),
    (r"Điểm các môn khác xem ở mục Bảng điểm & tiến độ\.", "Grades for other courses are under Transcript & progress."),
    (r"Mình không thấy môn \"(.+?)\" trong bảng điểm của bạn\. Các môn hiện có: (.+?)\. Bạn hỏi lại đúng tên môn nhé\.",
     lambda m: f'I can\'t find the course "{m.group(1)}" in your transcript. Your courses are: {m.group(2)}. Please ask again with the exact course name.'),
    (r"(?m)^Môn ", "Course "),
    (r": điểm môn này chưa được công bố\.", ": grades for this course have not been published yet."),
    (r"- Điểm quá trình:", "- Coursework:"),
    (r"- Điểm thi:", "- Exam:"),
    (r"- Điểm tổng kết:", "- Final grade:"),
    (r"- Chuyên cần:", "- Attendance:"),
    (r"Điểm trung bình tích lũy hiện tại: ([\d.]+)\.", r"Current cumulative GPA: \1."),
    (r"Muốn xem điểm quá trình, điểm thi của một môn, bạn hỏi kèm tên môn, ví dụ \"điểm môn (.+?)\"\.",
     r'To see coursework and exam scores for a course, ask with its name, for example "grades for \1".'),
    (r"Mình chưa tìm thấy hồ sơ phí gắn với tài khoản của bạn\. Bạn xem mục Nghĩa vụ phí của tôi hoặc nhắn \"gặp cán bộ\" nhé\.",
     "I couldn't find a fee record linked to your account. Please check My fee obligations or type \"talk to staff\"."),
    (r"Hiện chưa có khoản phí nào được ghi nhận cho bạn\.", "No fees have been recorded for you yet."),
    (r"Minh chứng chuyển khoản bạn tải ở mục Nghĩa vụ phí của tôi\.", "You can upload transfer receipts under My fee obligations."),
    (r"Bạn không có khoản phí nào quá hạn\.", "You have no overdue fees."),
    (r" Khoản sắp đến hạn gần nhất: (.+?), hạn (\S+)\.", r" Your next upcoming fee: \1, due \2."),
    (r"Các khoản đã quá hạn:", "Overdue fees:"),
    (r"Tổng (\d+) khoản phí của bạn: phải đóng (.+?), đã đóng (.+?), còn (.+?)\.",
     r"Your \1 fees in total: due \2, paid \3, remaining \4."),
    (r"Bạn đã đóng tổng cộng (.+?)\.", r"You have paid \1 in total."),
    (r" Chưa có khoản nào được đóng đủ\.", " No fee has been paid in full yet."),
    (r"Các khoản đã đóng đủ \((\d+)\):", r"Fees paid in full (\1):"),
    (r"Khoản cần đóng tiếp theo:", "Your next fee to pay:"),
    (r"Sau đó còn (\d+) khoản chưa đóng\.", r"After that, \1 more unpaid fee(s)."),
    (r"Bạn đã đóng đủ (\d+) khoản phí đã ghi nhận, hiện không còn khoản nào chưa đóng\.",
     r"You have paid all \1 recorded fees; nothing is outstanding."),
    (r"Bạn còn (\d+) khoản chưa đóng, tổng (.+?):", r"You have \1 unpaid fee(s), totaling \2:"),
    (r"Đã đóng đủ (\d+) khoản khác\.", r"\1 other fee(s) paid in full."),
    (r"\(đã đóng đủ\): ", "(paid in full): "),
    (r"\(chưa đóng đủ\): ", "(not fully paid): "),
    (r"phải đóng ", "due "),
    (r", đã quá hạn (\d+) ngày", r", \1 days overdue"),
    (r", còn (\d+) ngày", r", \1 days left"),
    (r"đã đóng ", "paid "),
    (r", còn ", ", remaining "),
    (r", hạn ", ", due date "),
    (r"Học phí kỳ (\d+)", r"Tuition semester \1"),
    (r"Phí ghi danh \(Inscription Fee\)", "Inscription fee"),
    (r"Phí ghi danh", "Inscription fee"),
    (r"Khoản phí", "Fee"),
    (r"Buổi học (\S+) ", r"Class \1 "),
    (r"\bThi (\w+):", r"Exam \1:"),
    (r"\(sắp tới\)", "(upcoming)"),
    (r"\(đã diễn ra\)", "(past)"),
    (r", phòng ", ", room "),
    (r"Lịch đầy đủ xem ở mục Lịch học / Lịch PV\.", "The full schedule is under Class schedule / Interview schedule."),
    (r"(?m)^(.+?) sắp tới của bạn:", lambda m: f"Your upcoming {_what_en(m.group(1))}:"),
    (r"Hiện chưa có (.+?) nào sắp tới\. Gần nhất:", lambda m: f"You have no upcoming {_what_en(m.group(1))}. Most recent:"),
    (r"Lịch mới sẽ hiện ở mục Lịch học / Lịch PV khi được xếp\.",
     "New schedules will appear under Class schedule / Interview schedule once arranged."),
    (r"Hiện chưa có (.+?) nào được xếp cho bạn\.", lambda m: f"No {_what_en(m.group(1))} have been scheduled for you yet."),
    (r"Mình chưa tìm thấy hồ sơ học tập gắn với tài khoản của bạn\.", "I couldn't find a study record linked to your account."),
    (r"Toàn bộ lộ trình xem ở mục Kết quả của tôi\.", "Your full study path is under My results."),
    (r"Bạn là học viên( \w+)?", lambda m: f"You are {'an' if (m.group(1) or '').strip()[:1] in 'AEIOUM' and m.group(1) else 'a'}{m.group(1) or ''} student"),
    (r", mã học viên ", ", student ID "),
    (r", lớp ", ", class "),
    (r"Bạn đã hoàn thành (\d+)/(\d+) giai đoạn\. Giai đoạn tiếp theo: (.+?)\.",
     r"You have completed \1/\2 stages. Next stage: \3."),
    (r"Các giai đoạn còn lại: ", "Remaining stages: "),
    (r"Bạn đã hoàn thành tất cả (\d+) giai đoạn, từ hồ sơ tuyển sinh đến tốt nghiệp\.",
     r"You have completed all \1 stages, from admission to graduation."),
    (r"Hỏi riêng từng giai đoạn được, ví dụ \"luận văn của tôi\" hay \"tôi tốt nghiệp chưa\"\.",
     "You can ask about each stage, for example \"my thesis\" or \"have I graduated\"."),
    (r": đã xong", ": done"),
    (r": đang chờ", ": pending"),
    (r": chưa áp dụng", ": not applicable"),
    (r"Luận văn: ", "Thesis: "),
    (r"đề tài ", "topic "),
    (r"người hướng dẫn: chưa phân công", "supervisor: not assigned"),
    (r"người hướng dẫn: ", "supervisor: "),
    (r"[Tt]rạng thái: ", "status: "),
    (r"trạng thái ", "status "),
    (r"ngày bảo vệ: ", "defense date: "),
    (r" lúc ", " at "),
    (r"; phòng ", "; room "),
    (r"; điểm ", "; grade "),
    (r"hội đồng: chưa có thông tin", "committee: no information yet"),
    (r"hội đồng: ", "committee: "),
    (r"Điểm viết: ", "Written score: "),
    (r"KQ: ", "Result: "),
    (r"TB: ", "Avg: "),
    (r"Mã HV: ", "Student ID: "),
    (r"Lớp: ", "Class: "),
    (r"Chưa liên kết hồ sơ", "No linked file"),
    (r"Chưa có bản ghi class_students", "No class record"),
    (r"(.+?) đã quá hạn (\d+) ngày, remaining (.+?) chưa đóng\.", r"\1 is \2 days overdue, \3 still unpaid."),
    (r"(.+?) đã quá hạn (\d+) ngày, còn (.+?) chưa đóng\.", r"\1 is \2 days overdue, \3 still unpaid."),
    (r"(.+?) đến hạn (\S+) \(hôm nay\), cần đóng (.+?)\.", r"\1 is due today (\2), amount \3."),
    (r"(.+?) đến hạn (\S+) \(remaining (\d+) ngày\), cần đóng (.+?)\.", r"\1 is due \2 (in \3 days), amount \4."),
    (r"(.+?) đến hạn (\S+) \(còn (\d+) ngày\), cần đóng (.+?)\.", r"\1 is due \2 (in \3 days), amount \4."),
    (r"Bạn có lịch phỏng vấn (.+?)\.", r"You have an interview \1."),
    (r"Bạn bảo vệ luận văn (.+?)\.", r"Your thesis defense is \1."),
    (r"(?m)^(Hôm nay|Ngày mai|Ngày \S+) bạn có (.+?)\.$", r"\1 you have \2."),
    (r"Bạn có (.+?)\.$", r"You have \1."),
    (r"\b[Hh]ôm nay\b", "today"),
    (r"\b[Nn]gày mai\b", "tomorrow"),
    (r"\b[Nn]gày (\d{2}/\d{2}/\d{4})", r"on \1"),
    (r"toàn khóa", "the whole program"),
    (r"học kỳ này \(học kỳ (\d+)\)", r"this semester (semester \1)"),
    (r"học kỳ trước \(học kỳ (\d+)\)", r"last semester (semester \1)"),
    (r"học kỳ sau \(học kỳ (\d+)\)", r"next semester (semester \1)"),
    (r"học kỳ (\d+)", r"semester \1"),
    (r"\b(đã tốt nghiệp)\b", "graduated"),
    (r"\b(đã bảo vệ)\b", "defended"),
    (r"\bchính thức\b", "official"),
    (r"\bđã hoàn thành\b", "completed"),
    (r"\bchưa đạt\b", "not passed"),
    (r"\bkhông đạt\b", "not passed"),
    (r"\bđạt\b", "passed"),
    (r"chưa công bố", "not published"),
    (r" · điểm ", " · grade "),
    (r"\bđã học xong\b", "completed"),
    (r"\bđang học\b", "in progress"),
    (r"\bchưa học\b", "not started"),
    (r"\bchưa đạt\b", "not passed"),
    (r"\bsắp học\b", "upcoming"),
    (r"\bbảo vệ\b", "defense"),
]
VI_TO_EN = [(re.compile(p), r) for p, r in VI_TO_EN]
_PROGRESS_RE = re.compile(r"\((" + "|".join(re.escape(k) for k in PROGRESS_EN) + r")\)", re.IGNORECASE)
_STAGE_RE = re.compile("|".join(re.escape(k) for k in sorted(STAGE_TITLES, key=len, reverse=True)))
_TRANSLATE_CACHE: dict[str, str] = {}


def detect_lang(text: str) -> str | None:
    raw = text or ""
    if VI_ANY_RE.search(raw):
        return "vi"
    words = re.findall(r"[a-z']+", raw.lower())
    en = sum(1 for w in words if w in EN_WORDS)
    vi = sum(1 for w in words if w in VI_WORDS)
    if en > vi:
        return "en"
    if vi > en:
        return "vi"
    return None


def to_vi_query(text: str) -> str:
    out = " " + (text or "").lower().replace("’", "'") + " "
    for pattern, repl in EN_TO_VI:
        out = re.sub(pattern, lambda m, r=repl: " <" + "_".join(m.expand(r).split()) + "> ", out)
    words = []
    for tok in re.findall(r"<[^>]+>|[a-z0-9&]+", out):
        if tok.startswith("<"):
            if len(tok) > 2:
                words.append(tok[1:-1].replace("_", " "))
        elif tok not in EN_FILLER:
            words.append(tok)
    return " ".join(words)


def has_vietnamese(text: str) -> bool:
    return bool(VI_ANY_RE.search(text or ""))


def to_english(text: str) -> str:
    out = (text or "").strip()
    if out in VI_FIXED:
        return VI_FIXED[out]
    out = _STAGE_RE.sub(lambda m: STAGE_TITLES[m.group(0)], out)
    for rx, repl in VI_TO_EN:
        out = rx.sub(repl, out)
    out = _PROGRESS_RE.sub(lambda m: f"({PROGRESS_EN[m.group(1).lower()]})", out)
    return out


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "").replace(".", "") for n in re.findall(r"\d+(?:[.,]\d+)*", text or "")}


def llm_translate(text: str, model: str) -> str | None:
    key = hashlib.sha256(f"{model}|{text}".encode("utf-8")).hexdigest()
    if key in _TRANSLATE_CACHE:
        return _TRANSLATE_CACHE[key]
    try:
        from rag_service import _get_client

        resp = _get_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You translate Vietnamese text into English. Reply in English only."},
                {
                    "role": "user",
                    "content": "Translate into English. Keep numbers, dates, amounts, course codes and line breaks unchanged. "
                    f"Output only the translation:\n\n{text}",
                },
            ],
            temperature=0,
            max_tokens=500,
        )
        out = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[STUDENT BOT] translate error: {e}")
        return None
    if not out or not _numbers(out) <= _numbers(text):
        return None
    if len(_TRANSLATE_CACHE) >= 300:
        _TRANSLATE_CACHE.pop(next(iter(_TRANSLATE_CACHE)))
    _TRANSLATE_CACHE[key] = out
    return out


def localize(text: str, lang: str, model: str) -> str:
    if not text or lang != "en":
        return text
    english = to_english(text)
    if not has_vietnamese(english):
        return english
    return llm_translate(english, model) or english
