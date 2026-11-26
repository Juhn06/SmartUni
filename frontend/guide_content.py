"""Slide guide: one person, from prospect to learner, in the order each account may write."""

from __future__ import annotations


def T(vi: str, en: str) -> dict:
    return {"vi": vi, "en": en}


# Bộ phận → các chương trong trình tự mà tài khoản đó được thao tác.
DEPT_CHAPTERS = {
    "admin_he_thong": ["cau-hinh"],
    "it": ["cau-hinh"],
    "marcom": ["tiem-nang"],
    "marcom_tuyen_sinh": ["tiem-nang", "ho-so"],
    "tuyen_sinh": ["tiem-nang", "dot-ts", "ho-so", "thi-pv", "trung-tuyen", "nhap-hoc"],
    "mba": ["dot-ts", "thi-pv", "trung-tuyen", "nhap-hoc"],
    "master_chuyen_nganh": ["dot-ts", "thi-pv", "trung-tuyen", "nhap-hoc"],
    "ke_toan": ["thu-phi", "nhap-hoc"],
    "khao_thi": ["nhap-hoc"],
    "thanh_tra": ["ho-so", "trung-tuyen"],
    "hoc_vien": ["nhap-hoc"],
}

LOGIN_CHAPTERS = {
    "ThaoP": ["cau-hinh"],
    "NghiND": ["danh-muc"],
    "Admin": ["cau-hinh"],
}


def audience_ids_for_user(user: dict | None) -> list[str]:
    """Chapters this account is allowed to operate. The deck still opens at the start."""
    user = user or {}
    ids: list[str] = []
    for dept in user.get("departments") or []:
        code = dept.get("code") if isinstance(dept, dict) else ""
        for aid in DEPT_CHAPTERS.get(code or "", []):
            if aid not in ids:
                ids.append(aid)
    login = (user.get("email") or "").strip()
    for aid in LOGIN_CHAPTERS.get(login, []):
        if aid not in ids:
            ids.append(aid)
    if user.get("is_admin") and "cau-hinh" not in ids:
        ids.append("cau-hinh")
    return ids


def _cover(kicker, title, accent, lead, meta):
    return {
        "type": "cover",
        "kicker": kicker,
        "title": title,
        "accent": accent,
        "lead": lead,
        "meta": meta,
    }


def _cards(kicker, title, cards, chips):
    return {"type": "cards", "kicker": kicker, "title": title, "cards": cards, "chips": chips}


def _card(n, title, body, items=None):
    return {"n": n, "title": title, "body": body, "items": items or []}


def _steps(kicker, title, lead, steps):
    return {"type": "steps", "kicker": kicker, "title": title, "lead": lead, "steps": steps}


def _step(n, title, body, menu, endpoint=""):
    return {"n": n, "title": title, "body": body, "menu": menu, "endpoint": endpoint}


def _aud(aid, section, title, slides):
    return {"id": aid, "section": section, "title": title, "slides": slides}


SECTIONS = [
    {"id": "mo", "title": T("Mở đầu", "Start")},
    {"id": "cau-hinh", "title": T("1. Cấu hình", "1. Setup")},
    {"id": "nguon", "title": T("2. Ứng viên tiềm năng", "2. Prospects")},
    {"id": "dot", "title": T("3. Đợt và hồ sơ", "3. Round and files")},
    {"id": "thi", "title": T("4. Thi và trúng tuyển", "4. Exams and offers")},
    {"id": "nhap", "title": T("5. Thu phí và nhập học", "5. Fees and enrollment")},
]


AUDIENCES = [
    _aud(
        "mo-dau",
        "mo",
        T("Trình tự", "Sequence"),
        [
            _cover(
                T("Hướng dẫn", "Guide"),
                T("Một người, một hồ sơ", "One person, one file"),
                T("từ ứng viên đến học viên", "from applicant to learner"),
                T(
                    "Đọc từ đầu. Vai trò đổi trên cùng hồ sơ cá nhân: Ứng viên, rồi Người dự thi chính thức, rồi Học viên. Không tạo thêm một người và không có giai đoạn Sinh viên. Mỗi bước ghi tài khoản được phép ghi. Tài khoản khác cùng màn hình chỉ xem hoặc làm việc phụ.",
                    "Read from the start. The role changes on the same personal file: Applicant, then Official examinee, then Learner. The system does not create a second person and there is no Student stage. Each step names the account allowed to write. Other accounts on the same screen only view or assist.",
                ),
                [
                    T("ThaoP cấu hình chức năng · NghiND khai danh mục", "ThaoP sets functions · NghiND sets catalogs"),
                    T("Phím ← → để đi tiếp. Mục lục nhảy tới bước của bạn.", "Use ← → to continue. Contents jumps to your step."),
                ],
            ),
            _steps(
                T("Đúng thứ tự", "In order"),
                T("Cùng một người, vai trò đổi dần", "The same person, the role changes"),
                T(
                    "Bỏ qua một khâu thì khâu sau không có dữ liệu. Chưa xác nhận dự thi thì chưa cấp số báo danh. Chưa Đỗ thì chưa có phí ghi danh. Chưa chính thức thì chưa có hồ sơ theo học.",
                    "Skip a stage and the next one has no data. An unconfirmed examinee gets no exam number. A file that is not passed has no enrollment fee. A file that is not official has no programme record.",
                ),
                [
                    _step("1", T("Cấu hình chức năng", "Configure functions"), T("ThaoP gán menu cho từng tài khoản. NghiND khai trạng thái, khoản thu và loại giấy tờ.", "ThaoP grants menus. NghiND sets statuses, fee types and document types."), T("ThaoP · NghiND", "ThaoP · NghiND")),
                    _step("2", T("Ứng viên", "Applicant"), T("TuanTA ghi người quan tâm. NhungLH và GiaoNTQ chăm sóc, rồi mở hồ sơ khi đợt đang mở. Lúc này người đó vẫn là ứng viên.", "TuanTA records leads. NhungLH and GiaoNTQ follow up, then open a file while a round is open. The person is still an applicant."), T("TuanTA · NhungLH", "TuanTA · NhungLH")),
                    _step("3", T("Người dự thi chính thức", "Official examinee"), T("NhungLH xác nhận dự thi và ghi căn cứ trên cùng hồ sơ. Nếu đợt yêu cầu, LoanBT xác nhận lệ phí thi trước khi HaLP cấp số báo danh.", "NhungLH confirms the examinee and writes the basis on the same file. If the round requires it, LoanBT confirms the exam fee before HaLP assigns an exam number."), T("NhungLH · LoanBT · HaLP", "NhungLH · LoanBT · HaLP")),
                    _step("4", T("Đỗ hoặc Trượt", "Pass or fail"), T("HaLP, LinhTK hoặc AnhPTX chốt trong chương trình của mình. NhungLH gửi cả thư đỗ và thư trượt. Hồ sơ Đỗ sinh phí ghi danh đang chờ.", "HaLP, LinhTK or AnhPTX decides inside their own programme. NhungLH sends both the pass and the fail letter. A passed file creates an enrollment fee that is waiting."), T("HaLP · NhungLH", "HaLP · NhungLH")),
                    _step("5", T("Học viên", "Learner"), T("LoanBT xác nhận đã thu rồi chốt chính thức. Cùng người trở thành học viên, trạng thái Chờ xếp lớp. HaLP cấp mã theo chương trình rồi xếp lớp.", "LoanBT confirms payment then marks the file official. The same person becomes a learner, waiting for a class. HaLP assigns the programme code and then places the class."), T("LoanBT · HaLP", "LoanBT · HaLP")),
                ],
            ),
        ],
    ),
    _aud(
        "cau-hinh",
        "cau-hinh",
        T("Cấu hình chức năng", "Configure functions"),
        [
            _cover(
                T("Bước 1 · ThaoP", "Step 1 · ThaoP"),
                T("Gán đúng chức năng", "Grant the right functions"),
                T("trước khi ai nhập liệu", "before anyone enters data"),
                T(
                    "ThaoP tạo tài khoản, gắn bộ phận và chọn menu. Người được cấp phải đăng nhập lại thì menu mới đổi. Admin sửa bản ghi nghiệp vụ, không phân quyền. IT không nhận mọi menu.",
                    "ThaoP creates the account, attaches a department and picks menus. The person must sign in again before the menu changes. Admin edits operational records and does not set permissions. IT does not receive every menu.",
                ),
                [
                    T("Đăng nhập: ThaoP", "Sign in: ThaoP"),
                    T("MBA chỉ thấy MBA. MMS chỉ thấy MMS. MSCM chỉ thấy MSCM.", "MBA sees only MBA. MMS only MMS. MSCM only MSCM."),
                ],
            ),
            _steps(
                T("ThaoP thao tác", "What ThaoP does"),
                T("Ba màn hình cấu hình, theo thứ tự", "Three setup screens, in order"),
                T("Làm xong bước này rồi mới tới danh mục và dữ liệu ứng viên.", "Finish this step before catalogs and prospect data."),
                [
                    _step("1", T("Bộ phận", "Departments"), T("Mỗi người thuộc đúng bộ phận: Tuyển sinh, Marcom, MBA, Kế toán, Học viên…", "Each person belongs to the right department: Admissions, Marcom, MBA, Accounting, Students…"), T("Quản trị → Bộ phận", "Admin → Departments"), "admin_departments"),
                    _step("2", T("Người dùng", "Users"), T("Tạo tài khoản đăng nhập và gắn bộ phận.", "Create the login and attach the department."), T("Quản trị → Người dùng", "Admin → Users"), "admin_users"),
                    _step("3", T("Phân quyền", "Permissions"), T("Chọn từng chức năng được mở. Không tick toàn bộ menu cho một bộ phận.", "Pick each function to open. Do not tick every menu for one department."), T("Quản trị → Phân quyền", "Admin → Permissions"), "admin_permissions"),
                    _step("4", T("Đăng nhập lại", "Sign in again"), T("Người vừa được cấp thoát ra và vào lại. Menu cũ còn nằm trong phiên làm việc.", "The person who was just granted access signs out and back in. The old menu stays in the session."), T("Tài khoản vừa cấp", "The account just granted")),
                ],
            ),
        ],
    ),
    _aud(
        "danh-muc",
        "cau-hinh",
        T("Danh mục dùng chung", "Shared catalogs"),
        [
            _cover(
                T("Bước 1 · NghiND", "Step 1 · NghiND"),
                T("Khai danh mục", "Set the catalogs"),
                T("mà các form phía sau sẽ chọn", "later forms will pick from"),
                T(
                    "NghiND không sửa hồ sơ ứng viên và không thu tiền. Ba danh mục này phải có trước: trạng thái trên form, khoản thu, loại giấy tờ của đợt.",
                    "NghiND does not edit applicant files and does not collect money. These three catalogs must exist first: form statuses, fee types, and round document types.",
                ),
                [T("Đăng nhập: NghiND", "Sign in: NghiND")],
            ),
            _steps(
                T("NghiND thao tác", "What NghiND does"),
                T("Khai một lần, các bộ phận dùng lại", "Set them once; departments reuse them"),
                T("", ""),
                [
                    _step("1", T("Loại trạng thái", "Status types"), T("Giá trị trong ô chọn của hồ sơ, đợt, phí. Không gõ trạng thái tự do trên form.", "Values in the dropdowns for files, rounds and fees. Forms do not take a free-typed status."), T("Quản trị → Loại trạng thái", "Admin → Status types"), "admin_status_catalog"),
                    _step("2", T("Danh mục khoản thu", "Fee types"), T("Lệ phí thi, phí ghi danh và học phí. Các màn thu phía sau chỉ chọn trong danh mục này.", "Exam fee, enrollment fee and tuition. Later collection screens only pick from this catalog."), T("Thu tiền → Danh mục khoản thu", "Collections → Fee types"), "ops_accounting_fee_types"),
                    _step("3", T("Phân loại tài liệu", "Document types"), T("Loại giấy tờ của đợt tuyển sinh: quy chế, thông báo, hội đồng, minh chứng.", "Document kinds for an admissions round: rules, notices, board, evidence."), T("Tuyển sinh → Phân loại tài liệu", "Admissions → Document types"), "ops_admissions_doc_types"),
                ],
            ),
        ],
    ),
    _aud(
        "tiem-nang",
        "nguon",
        T("Ứng viên tiềm năng", "Prospects"),
        [
            _cover(
                T("Bước 2 · TuanTA rồi NhungLH", "Step 2 · TuanTA then NhungLH"),
                T("Lập danh sách", "Build the list"),
                T("người quan tâm, rồi chăm sóc", "of interested people, then follow up"),
                T(
                    "TuanTA ghi lead từ kênh truyền thông. NhungLH và GiaoNTQ nhận sang Dữ liệu nguồn, chăm sóc, và chỉ chuyển thành ứng viên khi đợt đang mở.",
                    "TuanTA records leads from communications channels. NhungLH and GiaoNTQ take them into Source data, follow up, and turn them into applicants only while a round is open.",
                ),
                [
                    T("TuanTA: Truyền thông. NhungLH, GiaoNTQ: Tuyển sinh.", "TuanTA: Marcom. NhungLH, GiaoNTQ: Admissions."),
                    T("Chưa có hồ sơ ứng viên ở bước này. Hồ sơ cá nhân bắt đầu từ đây và được bổ sung dần.", "There is no applicant file at this step yet. The personal file starts here and is filled in over time."),
                ],
            ),
            _cards(
                T("Hai sổ, hai tài khoản", "Two registers, two accounts"),
                T("Lead chưa phải hồ sơ dự tuyển", "A lead is not yet an application"),
                [
                    _card("01", T("TuanTA ghi lead", "TuanTA writes the lead"), T("Người quan tâm từ Facebook, Zalo, cuộc gọi, sự kiện.", "Someone interested via Facebook, Zalo, a call, or an event."), [T("Có thể chuyển sang Tuyển sinh", "Can be handed to Admissions")]),
                    _card("02", T("NhungLH chăm sóc", "NhungLH follows up"), T("Dữ liệu nguồn: người phụ trách, mức quan tâm, cờ, ghi chú.", "Source data: owner, interest level, flags, notes."), [T("Thiếu tên, email hoặc điện thoại là còn thiếu", "A missing name, email or phone is still a gap")]),
                    _card("03", T("Đợt chăm sóc", "Care round"), T("Tư vấn, hội thảo, Info Day. Nhắc trước mỗi đợt.", "Advice, workshop, Info Day. A reminder before each round."), []),
                    _card("04", T("Chuyển ứng viên", "Become an applicant"), T("Chỉ khi đợt tuyển sinh đang mở. CCCD không bắt buộc lúc này. Cùng một người, chưa phải người dự thi.", "Only while an admissions round is open. An ID number is not required yet. It is the same person, and not yet an examinee."), []),
                ],
                [
                    T("TuanTA không phê duyệt hồ sơ", "TuanTA does not approve applications"),
                    T("NhungLH không đánh dấu đã thu phí", "NhungLH does not mark a fee paid"),
                ],
            ),
            _steps(
                T("Thứ tự ghi", "Order of entry"),
                T("Từ người quan tâm đến ứng viên của đợt", "From an interested person to a round applicant"),
                T("", ""),
                [
                    _step("1", T("Người quan tâm", "Leads"), T("TuanTA thêm lead. Khi đủ thông tin thì chuyển Tuyển sinh.", "TuanTA adds the lead. When the details are enough, hand it to Admissions."), T("TuanTA · Truyền thông → Người quan tâm", "TuanTA · Marcom → Leads"), "ops_marcom_leads"),
                    _step("2", T("Sự kiện", "Events"), T("TuanTA lập sự kiện. Người đăng ký có thể thành lead.", "TuanTA creates the event. A registrant can become a lead."), T("TuanTA · Truyền thông → Sự kiện", "TuanTA · Marcom → Events"), "ops_marcom_events"),
                    _step("3", T("Dữ liệu nguồn", "Source data"), T("NhungLH hoặc GiaoNTQ cập nhật chăm sóc mỗi ngày và chuyển ứng viên vào đợt đang mở.", "NhungLH or GiaoNTQ update the daily follow-up and move the person into the open round."), T("NhungLH · Tuyển sinh → Dữ liệu nguồn", "NhungLH · Admissions → Source data"), "ops_admissions_crm_source"),
                    _step("4", T("Đợt chăm sóc", "Care rounds"), T("Chọn loại hoạt động, chọn hồ sơ nguồn, ghi nội dung chăm sóc.", "Pick the activity type, pick source records, write the follow-up."), T("NhungLH · Tuyển sinh → Đợt chăm sóc", "NhungLH · Admissions → Care rounds"), "ops_admissions_crm_activities"),
                    _step("5", T("Nhắc nhở", "Reminders"), T("In danh sách, gửi email hoặc đánh dấu đã gọi trước đợt chăm sóc.", "Print the list, send email, or mark the call before the care round."), T("NhungLH · Tuyển sinh → Nhắc nhở", "NhungLH · Admissions → Reminders"), "ops_admissions_crm_reminders"),
                ],
            ),
        ],
    ),
    _aud(
        "dot-ts",
        "dot",
        T("Đợt tuyển sinh", "Admissions round"),
        [
            _cover(
                T("Bước 3 · Điều phối rồi Tuyển sinh", "Step 3 · Coordination then Admissions"),
                T("Lập đợt", "Create the round"),
                T("rồi mới mở nhận hồ sơ", "then open it for applications"),
                T(
                    "HaLP và DoanNTN lập timeline MBA (May, August). LinhTK, LinhLT làm vậy cho MMS. AnhPTX cho MSCM. Mỗi người chỉ thấy chương trình của mình. NhungLH và GiaoNTQ mở hoặc đóng nhận hồ sơ trên đợt đó.",
                    "HaLP and DoanNTN set the MBA timeline (May, August). LinhTK and LinhLT do the same for MMS. AnhPTX for MSCM. Each person only sees their own programme. NhungLH and GiaoNTQ open or close applications on that round.",
                ),
                [
                    T("Chưa mở đợt thì Dữ liệu nguồn chưa chuyển được thành hồ sơ.", "Until the round is open, Source data cannot become an application."),
                    T("Đợt có thể yêu cầu thu lệ phí thi trước khi cấp số báo danh.", "A round can require the exam fee before an exam number is assigned."),
                ],
            ),
            _steps(
                T("Trên cùng một màn hình", "On the same screen"),
                T("Điều phối lập lịch. Tuyển sinh mở cổng.", "Coordination sets the dates. Admissions opens the gate."),
                T("", ""),
                [
                    _step("1", T("Tạo đợt", "Create the round"), T("HaLP (MBA), LinhTK (MMS) hoặc AnhPTX (MSCM) tạo đợt theo intake và timeline thi viết, phỏng vấn.", "HaLP (MBA), LinhTK (MMS) or AnhPTX (MSCM) creates the round with the intake and the written-exam and interview timeline."), T("Điều phối · Tuyển sinh → Đợt tuyển sinh", "Coordination · Admissions → Rounds"), "ops_admissions_rounds"),
                    _step("2", T("Mở nhận hồ sơ", "Open applications"), T("NhungLH hoặc GiaoNTQ chuyển đợt sang đang mở. Hết hạn thì đóng.", "NhungLH or GiaoNTQ set the round to open. They close it when the window ends."), T("NhungLH · Tuyển sinh → Đợt tuyển sinh", "NhungLH · Admissions → Rounds"), "ops_admissions_rounds"),
                    _step("3", T("Tài liệu đợt", "Round documents"), T("Gắn giấy tờ của đợt theo phân loại NghiND đã khai. Đây không phải sổ nghĩa vụ phí của thí sinh.", "Attach the round documents using the types NghiND already set. This is not the candidate fee ledger."), T("Tuyển sinh → Tìm kiếm tài liệu", "Admissions → Find documents"), "ops_admissions_round_docs"),
                ],
            ),
        ],
    ),
    _aud(
        "ho-so",
        "dot",
        T("Hồ sơ và bàn giao", "Files and handoff"),
        [
            _cover(
                T("Bước 4 · NhungLH, GiaoNTQ", "Step 4 · NhungLH, GiaoNTQ"),
                T("Nhận hồ sơ,", "Take the file,"),
                T("phê duyệt, rồi xác nhận dự thi", "approve it, then confirm the examinee"),
                T(
                    "Tuyển sinh chỉ có hai thao tác trạng thái: Phê duyệt hồ sơ hoặc Rút hồ sơ. Xác nhận dự thi là một nút riêng: ghi căn cứ, đổi vai trò thành Người dự thi chính thức trên cùng hồ sơ, và chưa mở lệ phí. HaLP thấy hồ sơ đã duyệt trong phạm vi MBA. Tuyển sinh không chốt Đỗ, không gán số báo danh, không lập hội đồng.",
                    "Admissions has two status actions: Approve the file or Withdraw it. Confirm examinee is a separate button: write the basis, change the role to Official examinee on the same file, and do not open a fee. HaLP sees approved files inside MBA. Admissions does not set Pass, does not assign an exam number, and does not create a board.",
                ),
                [T("Đăng nhập thao tác: NhungLH hoặc GiaoNTQ", "The account that writes: NhungLH or GiaoNTQ")],
            ),
            _steps(
                T("NhungLH thao tác", "What NhungLH does"),
                T("Checklist xong thì mới phê duyệt, rồi mới xác nhận dự thi", "Finish the checklist, then approve, then confirm the examinee"),
                T("Thiếu bằng, chứng chỉ ngoại ngữ hoặc thư giới thiệu thì gửi email chương trình và lịch, chưa duyệt. Hồ sơ đã rút thì không xác nhận dự thi.", "If the degree, language certificate or reference is missing, email the programme and the schedule. Do not approve yet. A withdrawn file cannot be confirmed as an examinee."),
                [
                    _step("1", T("Hồ sơ ứng viên", "Applications"), T("Tiếp nhận hồ sơ của đợt đang mở. Đối chiếu checklist giấy tờ. Mở Hồ sơ xuyên suốt khi cần xem cùng một người.", "Take applications for the open round. Check the document list. Open the continuous profile when you need to see the same person."), T("NhungLH · 2.TS.Tư vấn → Hồ sơ ứng viên", "NhungLH · Admissions → Applications"), "ops_admissions_applications"),
                    _step("2", T("Phê duyệt hồ sơ", "Approve the file"), T("Bấm Phê duyệt hồ sơ. Hồ sơ sang trạng thái đã duyệt và Điều phối nhận tiếp.", "Choose Approve. The file becomes admissions-approved and coordination takes it."), T("Cùng màn Hồ sơ ứng viên", "Same Applications screen"), "ops_admissions_applications"),
                    _step("3", T("Rút hồ sơ", "Withdraw"), T("Chỉ khi ứng viên rút. Không dùng ô này để ghi đỗ hay trượt.", "Only when the applicant withdraws. Do not use this to record pass or fail."), T("Cùng màn Hồ sơ ứng viên", "Same Applications screen"), "ops_admissions_applications"),
                    _step("4", T("Xác nhận dự thi", "Confirm the examinee"), T("Bấm Xác nhận dự thi và ghi căn cứ. Vai trò thành Người dự thi chính thức. Rồi Đăng ký nội dung thi. Chưa mở lệ phí và không tạo hồ sơ cá nhân mới.", "Choose Confirm examinee and write the basis. The role becomes Official examinee. Then register the exam content. This does not open a fee and does not create a new personal file."), T("NhungLH · Hồ sơ ứng viên hoặc Hồ sơ xét tuyển", "NhungLH · Applications or Pre-enrollment files"), "ops_admissions_pre_enroll"),
                    _step("5", T("Hồ sơ xét tuyển", "Pre-enrollment files"), T("Danh sách người chưa thành học viên. Dùng màn này để đối chiếu tư cách dự thi trước khi vào thi.", "The list of people who are not learners yet. Use this screen to check examinee status before the exam."), T("2.TS.Xét duyệt → Hồ sơ xét tuyển", "Admissions review → Pre-enrollment files"), "ops_admissions_pre_enroll"),
                    _step("6", T("Xuất danh sách gửi Điều phối", "Export the list for coordination"), T("Danh sách hồ sơ đã duyệt để HaLP tổ chức thi và phỏng vấn.", "The approved list so HaLP can run the exam and the interview."), T("NhungLH · xuất từ Hồ sơ hoặc Thi viết", "NhungLH · export from Applications or Written exam"), "ops_admissions_written_exams"),
                ],
            ),
        ],
    ),
    _aud(
        "thi-pv",
        "thi",
        T("Tổ chức thi", "Run the exams"),
        [
            _cover(
                T("Bước 5 · HaLP, NhungLH hỗ trợ", "Step 5 · HaLP, NhungLH assists"),
                T("Lập danh sách thi", "Build the exam list"),
                T("và hội đồng phỏng vấn", "and the interview boards"),
                T(
                    "HaLP và DoanNTN chỉ cấp số báo danh khi hồ sơ đã là người dự thi chính thức. Nếu đợt yêu cầu lệ phí thi, LoanBT phải xác nhận đã thu trước. LinhTK làm vậy cho MMS, AnhPTX cho MSCM. NhungLH gửi lịch, thư mời và theo dõi vắng mặt, không sửa điểm và không xác nhận lệ phí.",
                    "HaLP and DoanNTN assign an exam number only after the file is an official examinee. If the round requires an exam fee, LoanBT must confirm it first. LinhTK does the same for MMS, AnhPTX for MSCM. NhungLH sends the schedule and invitations and tracks no-shows, and does not edit scores or confirm the exam fee.",
                ),
                [T("Điều phối còn bấm Chuyển phỏng vấn trên hồ sơ đã đủ điều kiện.", "Coordination also sets Move to interview on eligible files.")],
            ),
            _steps(
                T("Thứ tự tổ chức", "Order of the exam"),
                T("Đủ điều kiện trước, danh sách sau, rồi mới mời phỏng vấn", "Eligibility first, then the list, then the interview invite"),
                T("Hồ sơ đã rút không vào danh sách thi.", "A withdrawn file does not enter the exam list."),
                [
                    _step("1", T("Lệ phí thi, nếu đợt yêu cầu", "Exam fee, if the round requires it"), T("LoanBT hoặc HanhNT bấm Xác nhận lệ phí thi. Việc này không đổi phí ghi danh. NhungLH không có nút này.", "LoanBT or HanhNT confirms the exam fee. This does not change the enrollment fee. NhungLH does not have this button."), T("LoanBT · 2.TS.Thi → Thi viết", "LoanBT · Admissions exams → Written exam"), "ops_admissions_written_exams"),
                    _step("2", T("Thi viết", "Written exam"), T("HaLP gán số báo danh, phòng, ca và nhập điểm khi đã xác nhận dự thi và đã đủ lệ phí. NhungLH chỉ xem và xuất danh sách.", "HaLP assigns the exam number, room, session and enters scores once the examinee is confirmed and the fee is satisfied. NhungLH only views and exports the list."), T("HaLP · 2.TS.Thi → Thi viết", "HaLP · Admissions exams → Written exam"), "ops_admissions_written_exams"),
                    _step("3", T("Gửi lịch thi", "Send the exam notice"), T("NhungLH gửi thông báo lịch cho thí sinh.", "NhungLH sends the schedule notice to candidates."), T("NhungLH · trên màn Thi viết", "NhungLH · on the Written exam screen"), "ops_admissions_written_exams"),
                    _step("4", T("Tạo lịch phỏng vấn", "Create the interview schedule"), T("HaLP lọc theo đợt, chọn thí sinh, tạo hội đồng từ danh sách đã chọn.", "HaLP filters by round, selects candidates, and creates boards from the selected list."), T("HaLP · 2.TS.Thi → Phỏng vấn", "HaLP · Admissions exams → Interview"), "ops_admissions_interviews"),
                    _step("5", T("Thư mời phỏng vấn", "Interview invitation"), T("NhungLH gửi thư mời và ghi nhận không đến.", "NhungLH sends the invitation and records no-shows."), T("NhungLH · 2.TS.Thi → Phỏng vấn", "NhungLH · Admissions exams → Interview"), "ops_admissions_interviews"),
                    _step("6", T("Chuyển phỏng vấn", "Move to interview"), T("HaLP đặt trạng thái Chuyển phỏng vấn trên hồ sơ đủ điều kiện. NhungLH không có nút này.", "HaLP sets Move to interview on eligible files. NhungLH does not have this button."), T("HaLP · Hồ sơ ứng viên", "HaLP · Applications"), "ops_admissions_applications"),
                ],
            ),
        ],
    ),
    _aud(
        "trung-tuyen",
        "thi",
        T("Công bố trúng tuyển", "Announce offers"),
        [
            _cover(
                T("Bước 6 · HaLP chốt, NhungLH gửi", "Step 6 · HaLP decides, NhungLH sends"),
                T("Chốt Đỗ hoặc Trượt", "Set pass or fail"),
                T("rồi thông báo cho thí sinh", "then notify the candidate"),
                T(
                    "Chỉ Điều phối bấm Đỗ hoặc Trượt, trong phạm vi chương trình. Hồ sơ Đỗ vẫn là người dự thi cho đến khi nhập học chính thức, và tự sinh phí ghi danh đang chờ. NhungLH gửi cả email đỗ và email trượt, nhắc giấy tờ còn thiếu, rồi gửi thông báo trúng tuyển. Tuyển sinh không được bấm xác nhận đã thu.",
                    "Only coordination presses Pass or Fail, inside the programme. A passed file stays an examinee until official enrollment, and it creates a pending enrollment fee. NhungLH sends both the pass email and the fail email, reminds about missing documents, then sends the offer. Admissions cannot press confirm-paid.",
                ),
                [T("Chưa Đỗ thì Kế toán chưa có phí ghi danh để thu. Lệ phí thi là khoản khác, thu trước lúc thi.", "Until the file is passed, Accounting has no enrollment fee to collect. The exam fee is a different charge, collected before the exam.")],
            ),
            _steps(
                T("Hai tài khoản, nối tiếp", "Two accounts, one after the other"),
                T("Chốt kết quả trước, gửi thư sau", "Decide first, send the letter second"),
                T("", ""),
                [
                    _step("1", T("Đỗ hoặc Trượt", "Pass or fail"), T("HaLP (MBA), LinhTK (MMS) hoặc AnhPTX (MSCM) bấm Đỗ hoặc Trượt trên hồ sơ trong phạm vi chương trình.", "HaLP (MBA), LinhTK (MMS) or AnhPTX (MSCM) presses Pass or Fail on a file inside their programme."), T("Điều phối · Tuyển sinh → Hồ sơ ứng viên", "Coordination · Admissions → Applications"), "ops_admissions_applications"),
                    _step("2", T("Kết quả tuyển sinh", "Admissions results"), T("Danh sách điểm viết, phỏng vấn, trung bình. Đây là sổ để đối chiếu trước khi gửi thư.", "The list of written, interview and average scores. Check it before sending letters."), T("Tuyển sinh → Kết quả tuyển sinh", "Admissions → Results"), "ops_admissions_results"),
                    _step("3", T("Email đỗ và trượt", "Pass and fail email"), T("NhungLH gửi cả hai. Không chỉ gửi cho người đỗ.", "NhungLH sends both. Do not send only to those who passed."), T("NhungLH · Kết quả tuyển sinh", "NhungLH · Results"), "ops_admissions_results"),
                    _step("4", T("Thông báo trúng tuyển", "Offer notice"), T("NhungLH gửi thông báo trúng tuyển và học phí. Khoản phí ghi danh đã nằm ở trạng thái chờ thu.", "NhungLH sends the offer and the tuition notice. The enrollment fee is already waiting to be collected."), T("NhungLH · Kết quả tuyển sinh", "NhungLH · Results"), "ops_admissions_results"),
                    _step("5", T("Giấy tờ và bàn giao xác minh", "Documents and the verification handoff"), T("NhungLH nhắc bổ sung giấy tờ, rồi xuất hồ sơ Thanh tra và hồ sơ HTQT. Khảo thí và Thanh tra chỉ xem danh sách cần xác minh, không sửa hồ sơ.", "NhungLH reminds about missing documents, then exports the inspection pack and the international-office pack. The exam office and Inspection only view the verification queue and do not edit the file."), T("NhungLH · Kết quả tuyển sinh · Khảo thí xem Danh sách cần xác minh", "NhungLH · Results · Exam office views the verification queue"), "ops_admissions_verification"),
                ],
            ),
        ],
    ),
    _aud(
        "thu-phi",
        "nhap",
        T("Thu phí ghi danh", "Collect the enrollment fee"),
        [
            _cover(
                T("Bước 7 · LoanBT, HanhNT", "Step 7 · LoanBT, HanhNT"),
                T("Xác nhận đã thu", "Confirm the payment"),
                T("đúng khoản, đúng lúc", "the right charge, at the right time"),
                T(
                    "Có hai khoản trước khi thành học viên. Lệ phí thi thu trước lúc cấp số báo danh, nếu đợt yêu cầu. Phí ghi danh chỉ sinh sau khi Đỗ. LoanBT và HanhNT là người bấm xác nhận đã thu. NhungLH chỉ theo dõi. Người nộp gửi minh chứng trên cổng của mình và không tự ghi là đã nộp.",
                    "There are two charges before someone becomes a learner. The exam fee is collected before an exam number, if the round requires it. The enrollment fee appears only after a pass. LoanBT and HanhNT are the ones who confirm payment. NhungLH only watches. The payer submits proof on their own portal and cannot mark it paid.",
                ),
                [T("HạnhNT vừa thủ quỹ vừa điều phối MBA: thu phí trên mọi chương trình, việc lớp chỉ trong MBA.", "HanhNT is both cashier and MBA coordinator: fees on every programme, class work only inside MBA.")],
            ),
            _steps(
                T("LoanBT thao tác", "What LoanBT does"),
                T("Lệ phí thi trước, phí ghi danh sau khi Đỗ", "Exam fee first, enrollment fee after a pass"),
                T("Chưa thu phí ghi danh thì chưa được chốt nhập học chính thức. Xác nhận lệ phí thi không làm hồ sơ thành đã nộp phí ghi danh.", "An unpaid enrollment fee is not marked official. Confirming the exam fee does not mark the enrollment fee paid."),
                [
                    _step("1", T("Nghĩa vụ phí thí sinh", "Candidate fee obligations"), T("Xem lệ phí thi, miễn và số còn nợ. Bấm xác nhận lệ phí thi khi tiền về. Tuyển sinh mở cùng màn để xem, không có nút xác nhận.", "See the exam fee, any waiver and the balance. Confirm the exam fee when the money arrives. Admissions opens the same screen to look, and has no confirm button."), T("LoanBT · Thu tiền → Nghĩa vụ phí thí sinh", "LoanBT · Collections → Candidate fee obligations"), "ops_accounting_candidate_files"),
                    _step("2", T("Phí ghi danh", "Enrollment fees"), T("Chỉ có sau khi Đỗ. Lọc khoản chờ. Bấm xác nhận đã thu khi tiền về. Hồ sơ chuyển đã nộp phí.", "This exists only after a pass. Filter pending charges. Confirm paid when the money arrives. The file becomes paid."), T("LoanBT · Thu tiền → Phí ghi danh", "LoanBT · Collections → Enrollment fees"), "ops_accounting_fees"),
                    _step("3", T("Phiếu thu", "Receipts"), T("Lập phiếu thu cho khoản vừa xác nhận. Một khoản có thể có nhiều phiếu. Không nhập trùng mã giao dịch.", "Issue a receipt for the charge just confirmed. One charge can have several receipts. Do not enter the same transaction code twice."), T("LoanBT · Thu tiền → Phiếu thu", "LoanBT · Collections → Receipts"), "ops_accounting_receipts"),
                    _step("4", T("Email cảm ơn", "Thank-you email"), T("Gửi email sau khi đã thu.", "Send the email after payment is confirmed."), T("LoanBT · Thu tiền → Email cảm ơn", "LoanBT · Collections → Thank-you email"), "ops_accounting_receipt_emails"),
                    _step("5", T("Theo dõi, không thu", "Watch, do not collect"), T("NhungLH mở Nghĩa vụ phí thí sinh và Phí ghi danh để xem tiến độ. Không có nút xác nhận đã thu.", "NhungLH opens Candidate fee obligations and Enrollment fees to see progress. There is no confirm-paid button."), T("NhungLH · Thu tiền → Phí ghi danh", "NhungLH · Collections → Enrollment fees"), "ops_accounting_fees"),
                ],
            ),
        ],
    ),
    _aud(
        "nhap-hoc",
        "nhap",
        T("Nhập học", "Enrollment"),
        [
            _cover(
                T("Bước 8 · LoanBT rồi HaLP", "Step 8 · LoanBT then HaLP"),
                T("Chốt chính thức,", "Mark official,"),
                T("mở hồ sơ theo học, rồi xếp lớp", "open the programme file, then place the class"),
                T(
                    "LoanBT chốt nhập học chính thức sau khi đã thu phí ghi danh. Cùng một người trở thành học viên, trạng thái Chờ xếp lớp, vẫn giữ mã ứng viên. NhungLH xuất hồ sơ gửi Khảo thí. HaLP cấp mã học viên trên hồ sơ theo học của chương trình rồi xếp lớp. Xếp lớp mở tài khoản cổng. MMS và MSCM làm cùng các thao tác trong chương trình của mình. Sổ học phí chỉ mở sau bước chính thức.",
                    "LoanBT marks the file official after the enrollment fee is paid. The same person becomes a learner, waiting for a class, and keeps the candidate code. NhungLH exports the pack for the exam office. HaLP assigns the learner code on that programme file and then places the class. Placing the class opens the portal account. MMS and MSCM do the same steps inside their own programme. The tuition ledger opens only after the official step.",
                ),
                [T("Học viên đăng nhập cổng để xem hồ sơ và nghĩa vụ phí, không sửa sổ thu.", "The learner signs in to the portal to see the file and fees, and cannot edit the cash book.")],
            ),
            _cards(
                T("Ba việc khác nhau", "Three different jobs"),
                T("Chính thức, mã, rồi mới vào lớp", "Official, then the code, then the class"),
                [
                    _card("01", T("Chốt chính thức", "Mark official"), T("LoanBT làm sau khi phí ghi danh đã thu. Hồ sơ theo học được mở, trạng thái Chờ xếp lớp.", "LoanBT does this after the enrollment fee is paid. The programme file opens, waiting for a class."), [T("Chưa chính thức thì chưa vào lớp", "A file that is not official does not enter a class")]),
                    _card("02", T("Cấp mã học viên", "Assign the learner code"), T("HaLP, LinhTK hoặc AnhPTX xem trước rồi cấp mã theo chương trình. Không tạo thêm một người.", "HaLP, LinhTK or AnhPTX previews and then assigns the programme code. This does not create another person."), [T("Tuyển sinh và Kế toán không cấp mã", "Admissions and Accounting do not assign the code")]),
                    _card("03", T("Xếp lớp", "Place the class"), T("Điều phối đưa học viên chính thức vào lớp. Trạng thái theo học chuyển sang đang học và cổng được mở.", "Coordination places the official learner in a class. The study status becomes in study and the portal opens."), [T("Sổ học phí nằm ở Công nợ", "The tuition ledger is in Charges")]),
                    _card("04", T("Hồ sơ đã nhập học", "Enrolled files"), T("Xem mã học viên cạnh mã ứng viên. Người vừa chính thức mà chưa có lớp vẫn nằm ở đây.", "See the learner code next to the candidate code. Someone just made official and not yet in a class still appears here."), []),
                ],
                [
                    T("Khảo thí và Thanh tra chỉ xem, không sửa hồ sơ", "The exam office and Inspection only view, and do not edit the file"),
                    T("Một người học hai chương trình là hai hồ sơ theo học", "One person in two programmes has two programme files"),
                ],
            ),
            _steps(
                T("Đến khi có lớp", "Until there is a class"),
                T("Chính thức trước, mã và lớp sau", "Official first, then the code and the class"),
                T("Người chưa xếp lớp là học viên trạng thái Chờ xếp lớp, không phải một loại hồ sơ khác.", "Someone not yet placed is a learner waiting for a class, not a different kind of file."),
                [
                    _step("1", T("Nhập học chính thức", "Official enrollment"), T("LoanBT chốt hồ sơ đã thu phí ghi danh. Hồ sơ sang chính thức và mở hồ sơ theo học.", "LoanBT closes the file whose enrollment fee is paid. The file becomes official and the programme file opens."), T("LoanBT · 2.TS.Bàn giao → Nhập học chính thức", "LoanBT · Admissions handoff → Official enrollment"), "ops_accounting_official"),
                    _step("2", T("Hồ sơ đã nhập học", "Enrolled files"), T("Đối chiếu mã ứng viên, mã học viên và trạng thái theo học. Chờ xếp lớp là đúng khi chưa có lớp.", "Check the candidate code, the learner code and the study status. Waiting for a class is correct when there is no class yet."), T("2.TS.Bàn giao → Hồ sơ đã nhập học", "Admissions handoff → Enrolled files"), "ops_admissions_enrolled_files"),
                    _step("3", T("Gửi Khảo thí", "Send to the exam office"), T("NhungLH bấm Gửi khảo thí trên danh sách chính thức. Khảo thí và Thanh tra mở Danh sách cần xác minh để xem minh chứng. Không dùng các nút này để thu tiền hay sửa hồ sơ.", "NhungLH chooses Send to the exam office on the official list. The exam office and Inspection open the verification queue to see the evidence. These buttons do not collect money and do not edit the file."), T("NhungLH · Nhập học chính thức · Khảo thí xem Danh sách cần xác minh", "NhungLH · Official enrollment · Exam office views the verification queue"), "ops_admissions_verification"),
                    _step("4", T("Cấp mã học viên", "Assign the learner code"), T("HaLP xem trước rồi cấp mã MBA. LinhTK cấp mã MMS, AnhPTX cấp mã MSCM. Mã nằm trên hồ sơ theo học của chương trình đó.", "HaLP previews and then assigns the MBA code. LinhTK assigns the MMS code, AnhPTX the MSCM code. The code sits on that programme file."), T("Điều phối · 2.TS.Xét duyệt → Cấp mã học viên", "Coordination · Admissions review → Learner codes"), "ops_admissions_student_numbering"),
                    _step("5", T("Đưa vào lớp", "Place in a class"), T("HaLP tạo lớp hoặc ghi danh học viên chính thức. Hệ thống cấp tài khoản cổng. Trạng thái theo học hết Chờ xếp lớp.", "HaLP creates the class or enrolls the official learner. The system creates the portal account. The study status leaves Waiting for a class."), T("HaLP · 5. Lớp học & Lịch học → Danh sách lớp", "HaLP · Classes → Class list"), "ops_classes"),
                    _step("6", T("Sổ học phí và cổng học viên", "Tuition ledger and the learner portal"), T("Sau khi chính thức, LoanBT theo dõi Công nợ, Theo dõi học phí và Cảnh báo học phí. Học viên mở Hồ sơ của tôi và Nghĩa vụ phí của tôi, gửi minh chứng nếu được hỏi, không tự xác nhận đã nộp.", "After the official step, LoanBT follows Charges, the tuition tracker and tuition alerts. The learner opens My profile and My fees, sends proof if asked, and does not confirm payment."), T("LoanBT · Thu tiền → Công nợ / học phí · Học viên · Cổng HV", "LoanBT · Collections → Charges · Learner · Portal"), "ops_accounting_charges"),
                ],
            ),
        ],
    ),
]


def _pick(value, lang: str):
    if isinstance(value, dict) and ("vi" in value or "en" in value):
        return value.get(lang) or value.get("vi") or ""
    return value


def build_guide(lang: str, mine_ids: list[str], default_id: str, link_for) -> dict:
    """Localized deck for the slide page. link_for(endpoint) -> url or ''."""
    lang = "en" if lang == "en" else "vi"
    mine = set(mine_ids or [])
    sections = [{"id": s["id"], "title": _pick(s["title"], lang)} for s in SECTIONS]
    audiences = []
    for aud in AUDIENCES:
        slides = []
        for raw in aud["slides"]:
            slide = {
                "type": raw["type"],
                "kicker": _pick(raw.get("kicker"), lang),
                "title": _pick(raw.get("title"), lang),
            }
            if raw["type"] == "cover":
                slide["accent"] = _pick(raw.get("accent"), lang)
                slide["lead"] = _pick(raw.get("lead"), lang)
                slide["meta"] = [_pick(x, lang) for x in raw.get("meta") or []]
            elif raw["type"] == "cards":
                slide["chips"] = [_pick(x, lang) for x in raw.get("chips") or []]
                slide["cards"] = [
                    {
                        "n": c["n"],
                        "title": _pick(c["title"], lang),
                        "body": _pick(c["body"], lang),
                        "items": [_pick(x, lang) for x in c.get("items") or []],
                    }
                    for c in raw.get("cards") or []
                ]
            elif raw["type"] == "steps":
                slide["lead"] = _pick(raw.get("lead"), lang)
                steps = []
                for s in raw.get("steps") or []:
                    endpoint = s.get("endpoint") or ""
                    href = ""
                    if endpoint:
                        try:
                            href = link_for(endpoint) or ""
                        except Exception:
                            href = ""
                    steps.append(
                        {
                            "n": s["n"],
                            "title": _pick(s["title"], lang),
                            "body": _pick(s["body"], lang),
                            "menu": _pick(s.get("menu"), lang),
                            "href": href,
                        }
                    )
                slide["steps"] = steps
            slides.append(slide)
        audiences.append(
            {
                "id": aud["id"],
                "section": aud["section"],
                "title": _pick(aud["title"], lang),
                "mine": aud["id"] in mine,
                "slides": slides,
            }
        )
    if default_id not in {a["id"] for a in audiences}:
        default_id = audiences[0]["id"]
    return {
        "default_id": default_id,
        "sections": sections,
        "audiences": audiences,
        "ui": {
            "contents": _pick(T("Mục lục", "Contents"), lang),
            "close": _pick(T("Đóng", "Close"), lang),
            "back": _pick(T("Về Tổng quan", "Back to dashboard"), lang),
            "prev": _pick(T("Trang trước", "Previous"), lang),
            "next": _pick(T("Trang sau", "Next"), lang),
            "yours": _pick(T("Của bạn", "Yours"), lang),
            "open": _pick(T("Mở màn hình", "Open screen"), lang),
            "guide": _pick(T("Hướng dẫn SmartUni", "SmartUni guide"), lang),
        },
    }
