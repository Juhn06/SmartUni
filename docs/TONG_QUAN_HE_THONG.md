# SmartUni: hệ thống quản lý đào tạo sau đại học tích hợp trợ lý UniBot

Tài liệu tổng hợp phục vụ báo cáo khóa luận. Hệ thống mô phỏng một trung tâm đào tạo sau đại học **giả định**. Tên tổ chức, trường và người trong dữ liệu mẫu đều là giả định.

Số liệu huấn luyện và kiểm thử chi tiết nằm ở `training/BAO_CAO_KET_QUA.md`.

---

## 1. Bài toán và mục tiêu

Một trung tâm đào tạo sau đại học quản lý ba chương trình: MBA, Master Marketing (MMS) và Master Supply Chain (MSCM). Có ba khó khăn chính:

- **Dữ liệu rời rạc theo phòng ban.** Tuyển sinh, điều phối, đào tạo, kế toán và luận văn mỗi bên giữ một bảng. Cùng một người học xuất hiện ở nhiều nơi, không nối với nhau.
- **Học viên hỏi lặp lại những câu giống nhau**: điểm, học phí, lịch thi, thủ tục. Cán bộ mất nhiều thời gian trả lời.
- **Khách quan tâm chưa được chăm sóc kịp.** Người hỏi về chương trình thường bị bỏ sót nếu không gọi điện.

Mục tiêu của đề tài:

1. Xây một hệ thống quản lý **xuyên suốt vòng đời người học**: từ khách tìm hiểu, ứng viên, học viên đến cựu học viên, trên **một hồ sơ duy nhất**.
2. Tích hợp **trợ lý UniBot** ở hai nơi:
   - Trang giới thiệu công khai, để tư vấn tuyển sinh.
   - Cổng học viên, để trả lời theo **dữ liệu riêng của từng người**.
3. Bot **không được bịa** học phí, ngày tháng hay con số. Câu nào không chắc thì chuyển cho cán bộ.
4. Chạy **miễn phí trên máy cá nhân**, dữ liệu học viên không gửi ra dịch vụ bên ngoài.

---

## 2. Kiến trúc tổng thể

```
Trình duyệt
   │
   ▼
Frontend  (Flask + Jinja2, cổng 8027)
   │  giao diện, phiên đăng nhập, chặn quyền lớp 1
   │  gọi API kèm định danh người dùng (X-User-Id)
   ▼
Backend API  (Flask, cổng 8026)
   │  nghiệp vụ, phân quyền lớp 2, UniBot
   ├──► SQLite  (backend/db/website.db)        dữ liệu nghiệp vụ, kho kiến thức, hội thoại
   ├──► ChromaDB (backend/chroma_db)           chỉ mục vector cho tìm kiếm ngữ nghĩa
   └──► Ollama  (http://localhost:11434)       mô hình ngôn ngữ chạy cục bộ
          • unibot-hv2-q4   bot học viên (Qwen2.5-3B đã huấn luyện LoRA, nén q4)
          • qwen2.5:3b      bot tuyển sinh
          • nomic-embed-text vector hóa văn bản
```

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Backend | Python, Flask, SQLite | API nghiệp vụ, phân quyền, UniBot |
| Frontend | Flask, Jinja2, HTML/CSS/JS | Trang công khai, cổng cán bộ, cổng học viên |
| Tìm kiếm | BM25 tiếng Việt không dấu kèm cặp từ, kết hợp vector ChromaDB | Truy xuất tài liệu và FAQ cho bot |
| Mô hình | Ollama, Qwen2.5-3B-Instruct, LoRA (Unsloth) | Sinh câu trả lời khi quy tắc không xử lý được |
| Hàng đợi email | Bảng `email_outbox` và tiến trình gửi SMTP | Gửi thông báo tài khoản |

---

## 3. Phân quyền

- **Bộ phận → quyền → menu** (`backend/rbac.py`). Mỗi tài khoản thuộc một hoặc nhiều bộ phận: tuyển sinh, chương trình MBA, Master Chuyên ngành, kế toán, Ban giám đốc, học viên, cựu học viên… Mỗi bộ phận có một bộ quyền mặc định, và menu chỉ hiện chức năng mà tài khoản được phép dùng.
- **Phạm vi chương trình.** Cán bộ chỉ thấy dữ liệu của chương trình mình phụ trách. Học viên chỉ thấy dữ liệu của chính mình.
- **Kiểm quyền hai lớp.** Frontend chặn ở giao diện, và backend kiểm tra lại bằng định danh người dùng cho các thao tác nhạy cảm: đưa hồ sơ vào lớp, tạo lớp, đổi trạng thái học viên, đặt lại mật khẩu, duyệt tài liệu. Ai gọi thẳng API mà bỏ qua giao diện vẫn bị chặn.

---

## 4. Luồng nghiệp vụ xuyên suốt vòng đời người học

```
Khách ──► UniBot tuyển sinh ──► Đăng ký tư vấn ──► Chuyên viên tuyển sinh (CRM)
                                                          │
                                                          ▼
          Hồ sơ ứng tuyển ──► Thi viết ──► Phỏng vấn ──► Kết quả ──► Phí ghi danh ──► Official
                                                                                     │
                                                                                     ▼
          Xếp lớp: mã học viên, sổ học phí, tài khoản cổng học viên, email báo tài khoản
                                                                                     │
                                                                                     ▼
          Học tập: phân công giảng dạy, buổi học, điểm danh, lịch thi, điểm, miễn môn
          Tài chính: các đợt học phí, học bổng và miễn giảm, nhắc hạn, quá hạn
          Trạng thái: đang học, bảo lưu, tạm nghỉ, thôi học (khóa tài khoản)
                                                                                     │
                                                                                     ▼
          Luận văn ──► Bảo vệ ──► Xét tốt nghiệp ──► Cựu học viên (Alumni)

          UniBot học viên đọc trực tiếp mọi dữ liệu trên của đúng người đang đăng nhập.
```

### 4.1. Tư vấn và chăm sóc khách hàng tiềm năng

1. Khách vào trang giới thiệu công khai (`/`) và hỏi **UniBot tuyển sinh**. Bot chỉ trả lời thông tin chung về chương trình, lấy từ kho kiến thức tuyển sinh.
2. Khách đăng ký tư vấn theo một trong ba cách: form trên trang, form trong khung chat, hoặc để lại số điện thoại khi đang chat.
3. Hệ thống tạo **yêu cầu tư vấn** và giao cho chuyên viên bộ phận tuyển sinh. Yêu cầu đi kèm toàn bộ lịch sử khách đã hỏi bot.
4. Hệ thống tự tạo **hồ sơ nguồn CRM** ở trạng thái "tiềm năng", kèm lịch nhắc liên hệ và nhật ký chăm sóc.
5. Chuyên viên xử lý và đổi trạng thái theo các bước: mới → đã liên hệ → đang chăm sóc → chuyển đổi → đóng.
6. Câu khách hỏi mà bot không trả lời được sẽ vào danh sách **câu chưa trả lời** để bổ sung kho kiến thức.

UniBot tuyển sinh dùng hai cách trả lời. Câu khớp FAQ được trả lời ngay. Các câu còn lại dùng Hybrid RAG: BM25 kết hợp vector, trộn kết quả bằng RRF, rồi `qwen2.5:3b` viết câu trả lời chỉ dựa trên tài liệu. Kho gồm 5 tài liệu và 27 FAQ về chương trình, điều kiện, hồ sơ, quy trình, hình thức học và học bổng. Bot không đưa con số học phí hay mức điểm tiếng Anh vì trung tâm chưa có tài liệu chính thức; gặp các câu này, bot mời người hỏi đăng ký tư vấn. Bot trả lời được cả câu hỏi tiếng Anh.

### 4.2. Tuyển sinh

Hồ sơ ứng tuyển đi qua các bước theo thứ tự:

1. Tiếp nhận hồ sơ và kiểm tra checklist văn bằng, chứng chỉ tiếng Anh.
2. Thi viết.
3. Phỏng vấn, chấm theo hội đồng.
4. Có kết quả trúng tuyển, hệ thống sinh khoản **phí ghi danh**.
5. Đóng phí ghi danh xong, hồ sơ chuyển trạng thái **official**.

Toàn bộ thông tin đầu vào được lưu trên hồ sơ và về sau UniBot dùng lại: loại và điểm chứng chỉ tiếng Anh, ngày cấp, trạng thái xác minh, ngành, xếp loại và trường cấp bằng đại học, điểm thi viết, điểm phỏng vấn.

### 4.3. Xếp lớp và tạo tài khoản học viên tự động

Cán bộ chương trình (quyền `classes.manage`) bấm **"Đưa hồ sơ official vào lớp"**. Chỉ một thao tác, hệ thống tự làm cùng lúc:

1. Tạo học viên trong lớp và cấp **mã học viên** theo chương trình.
2. Nối vào **hồ sơ người học thống nhất** (learner spine): cùng một người xuyên suốt từ tuyển sinh tới lớp, điểm và học phí.
3. Mở **sổ học phí**: phí ghi danh và các đợt học phí.
4. Tạo **tài khoản cổng học viên**:
   - Tên đăng nhập là mã học viên.
   - Mật khẩu tạm ngẫu nhiên. Lần đăng nhập đầu, học viên bị **bắt buộc đổi mật khẩu**, chưa đổi thì không vào được trang nào khác.
   - Email báo tên đăng nhập và mật khẩu tạm được xếp vào hàng đợi, tiến trình nền gửi qua SMTP.
   - Nếu bấm xếp lớp lại, hệ thống không ghi đè mật khẩu học viên đã tự đổi.

### 4.4. Đào tạo

- **Phân công giảng dạy** từng môn cho lớp, xếp **buổi học** và **lịch thi**, gồm thi cuối kỳ và thi lại.
- **Điểm danh** theo buổi, từ đó tính tỷ lệ chuyên cần của từng môn.
- **Điểm** gồm điểm quá trình, điểm thi và điểm tổng kết. Học viên chỉ thấy điểm khi điểm đã được khóa và công bố. Ngưỡng đạt là 10/20.
- **Trạng thái môn** được hệ thống suy ra tự động:
  - Đã học xong hoặc chưa đạt: theo điểm đã công bố.
  - Đang học: đã phân công giảng dạy nhưng chưa có điểm.
  - Sắp học: có buổi học trong tương lai.
  - Miễn và công nhận tín chỉ: theo ghi chú công nhận.

### 4.5. Tài chính

- Các đợt học phí có hạn đóng. Mỗi khoản có các trạng thái: chưa đóng, đóng một phần, đã đóng, sắp đến hạn, quá hạn.
- **Học bổng và miễn giảm:**
  - Loại học bổng ghi ở hồ sơ học viên.
  - Số tiền được giảm ghi trên từng khoản phí ở module kế toán.
  - Bot đọc cả hai nguồn và giải thích được "học phí gốc, được giảm bao nhiêu phần trăm, còn phải đóng bao nhiêu".
- Học viên xem khoản phí của mình và gửi minh chứng chuyển khoản ở mục "Nghĩa vụ phí của tôi". Học viên không tự xác nhận đã thu được.

### 4.6. Trạng thái học tập gắn với tài khoản

| Trạng thái do cán bộ cập nhật | Tài khoản cổng học viên | UniBot |
|---|---|---|
| Đang học | Hoạt động | Trả lời bình thường |
| Bảo lưu hoặc tạm nghỉ | Vẫn đăng nhập | Nói rõ đang bảo lưu, kèm ghi chú quyết định |
| Thôi học | **Tự khóa**. Quay lại học thì tự mở | Không truy cập được |
| Tốt nghiệp | Thêm vai trò cựu học viên, chuyển sang danh sách Alumni | Trả lời như người đã tốt nghiệp |

### 4.7. Luận văn, tốt nghiệp, cựu học viên

Luận văn đi qua các bước: đăng ký đề tài, phân công người hướng dẫn, xếp lịch bảo vệ (ngày, giờ, phòng, hội đồng), bảo vệ, có điểm. Sau đó học viên qua xét tốt nghiệp và được chuyển vào danh sách cựu học viên.

Học viên theo dõi toàn bộ chặng đường của mình ở mục "Kết quả của tôi". Từ các dữ liệu trên, hệ thống dựng lại 14 giai đoạn của học viên, mỗi giai đoạn có trạng thái đã xong hay đang chờ.

---

## 5. Module đặc biệt: UniBot học viên

### 5.1. Kiến trúc trả lời ba lớp

| Lớp | Cách làm | Dùng cho | Thời gian |
|---|---|---|---|
| 1. Quy tắc | Code đọc thẳng dữ liệu của học viên đang đăng nhập rồi điền vào mẫu câu | Điểm, môn học, chuyên cần, học phí, học bổng, lịch, luận văn, trạng thái, hồ sơ đầu vào | Dưới 0,2 giây |
| 2. FAQ | So khớp câu hỏi với kho câu hỏi thường gặp, mỗi câu có nhiều cách hỏi | Thủ tục phổ biến | Dưới 0,1 giây |
| 3. Mô hình ngôn ngữ | Mô hình đọc "phiếu dữ liệu" của học viên và tài liệu học vụ liên quan | Câu tự do, so sánh, câu nằm ngoài quy tắc | Khoảng 5–10 giây |

Lớp quy tắc chỉ trả lời khi hiểu **toàn bộ** câu hỏi: mọi từ trong câu đều phải giải thích được bằng chủ đề, tên môn hay tên khoản phí. Còn sót từ nào chưa hiểu thì câu được chuyển xuống lớp dưới. Nhờ vậy bot không trả lời nhầm trọng tâm.

### 5.2. Chống bịa thông tin

- **Định danh lấy từ phiên đăng nhập.** Bot chỉ đọc dữ liệu của người đang đăng nhập, học viên A không thể xem dữ liệu của học viên B.
- Mọi **con số** trong câu trả lời của mô hình phải có trong dữ liệu đầu vào. Không khớp thì câu trả lời bị loại.
- Nếu mô hình trả lời "không có thông tin", bị lẫn chữ nước ngoài, hoặc dùng nhầm dữ liệu học viên mẫu trong ví dụ, câu được **chuyển cho cán bộ** thay vì trả lời.
- Không có dữ liệu thì bot nói thật. Ví dụ: "người hướng dẫn: chưa phân công", "điểm thi lại chưa có".
- Quyết định riêng của từng học viên (bảo lưu, học bổng, miễn môn, điểm) **không đưa vào kho tài liệu**. Bot đọc trực tiếp từ module nghiệp vụ, nên chỉ người có quyết định đó nhìn thấy.

### 5.3. Hiểu tình huống của người học

- **Chủ động nhắc việc.** Mục "Cần chú ý" tự hiện các việc sắp tới mà không cần học viên hỏi: học phí sắp đến hạn hoặc đã quá hạn, lịch thi trong 7 ngày, buổi học hôm nay hoặc ngày mai, lịch bảo vệ luận văn trong 14 ngày. Việc gấp còn hiện số đỏ trên biểu tượng bot.
- **Hiểu câu hỏi nối tiếp.** Ví dụ học viên hỏi "điểm kỳ 1" rồi hỏi tiếp "còn kỳ 2 thì sao".
- **Hiểu ngày tương đối**: hôm nay, ngày mai, tuần này, tuần sau, kỳ này, kỳ trước.
- **Trả lời đúng trọng tâm**: hỏi một môn thì chỉ trả lời môn đó; hỏi khoản phải đóng tiếp theo thì ưu tiên khoản đã quá hạn.
- **Nhận ra học viên đang lo lắng**, trấn an trước khi đưa thông tin, và gợi ý gặp cán bộ.
- **Câu giả định** như "nếu tôi dừng học thì…" được hiểu là câu hỏi quy chế. Bot tra tài liệu thay vì suy diễn từ hồ sơ cá nhân.

### 5.4. Song ngữ Việt và Anh

- Bot trả lời **đúng ngôn ngữ của câu hỏi**, dù giao diện đang để tiếng Việt hay tiếng Anh.
- Với câu tiếng Anh, câu hỏi được đổi sang từ khóa tiếng Việt để đi qua lớp quy tắc, rồi câu trả lời được chuyển sang tiếng Anh bằng bảng mẫu câu cố định. Vì vậy câu tiếng Anh vẫn trả lời tức thì và không có nguy cơ bịa số.
- Chỉ những câu bảng mẫu chưa bao quát mới cần mô hình dịch.

### 5.5. Chuyển cán bộ và học từ cán bộ

1. Bot chuyển câu hỏi cho cán bộ trong hai trường hợp: học viên nhắn "gặp cán bộ", hoặc bot không trả lời được. Yêu cầu được chuyển **đúng chương trình** của học viên: MBA về bộ phận MBA, MMS và MSCM về Master Chuyên ngành.
2. Cán bộ thấy câu hỏi kèm toàn bộ hội thoại, và trả lời ngay trong khung chat của học viên.
3. Cán bộ có thể **lưu câu trả lời thành FAQ**. Sau khi được duyệt, bot tự trả lời câu đó cho các học viên sau.
4. Hệ thống tự gợi ý FAQ từ các câu được hỏi nhiều.

### 5.6. Quản trị kho kiến thức có duyệt

| Bước | Ai làm | Quy định |
|---|---|---|
| Tải tài liệu, thêm FAQ | Cán bộ chương trình | Chỉ cho chương trình mình phụ trách hoặc tài liệu "Chung". Bộ lọc tự ẩn số điện thoại, email, số giấy tờ và từ chối tệp dạng danh sách cá nhân |
| Duyệt hoặc trả lại | Ban giám đốc, Trợ lý BGĐ, Admin | Trả lại phải ghi lý do. Cán bộ chương trình không tự duyệt được |
| Hiệu lực | Ghi trên từng tài liệu | Bot chỉ dùng tài liệu đã duyệt và đang trong khoảng ngày hiệu lực. Tới ngày thì tự bật, hết hạn thì tự tắt |
| Sửa nội dung hoặc ngày hiệu lực | Cán bộ chương trình | Tài liệu quay về trạng thái chờ duyệt |

Tài liệu được duyệt là bot dùng ngay, không phải khởi động lại hệ thống.

UniBot tuyển sinh dùng cùng quy trình: cán bộ tuyển sinh soạn hoặc tải lên, nội dung chờ duyệt; người có quyền "Duyệt nội dung UniBot tuyển sinh" công bố theo thời gian hiệu lực của từng đợt tuyển sinh; hết đợt thì bot tự gỡ. Quyền duyệt mặc định thuộc Ban giám đốc, Trợ lý BGĐ và Admin, và có thể cấp thêm cho trưởng phòng tuyển sinh. Câu trả lời cán bộ soạn cho câu hỏi bot chưa trả lời được cũng phải qua duyệt.

### 5.7. Hồ sơ đầu vào

Bot trả lời được về chứng chỉ tiếng Anh (loại, điểm, ngày cấp, trạng thái xác minh), bằng đại học (ngành, xếp loại, trường, năm), điểm thi viết, điểm phỏng vấn và kết quả xét tuyển. Các thông tin này lấy trực tiếp từ hồ sơ tuyển sinh của chính học viên.

---

## 6. Huấn luyện mô hình

| Giai đoạn | Đúng hướng xử lý (41 câu) | Đúng nội dung (18 câu) | Ghi chú |
|---|---|---|---|
| Mô hình gốc qwen2.5:3b | 40 | 14 | Hay đọc sai phiếu dữ liệu, có lần tự cộng ra tổng học phí không có thật |
| LoRA vòng 1 (1.500 mẫu, rank 16) | 39 | 14 | Chưa ổn định |
| LoRA vòng 2 (2.000 mẫu, 2 lượt, rank 32, q8) | 40 | 16 | Ổn định, trung vị 21,3 giây |
| LoRA vòng 2 nén q4_k_m (đang dùng) | 40 | 16 | Trung vị 10,4 giây, nhẹ hơn 42% |

- Dữ liệu huấn luyện do `training/gen_dataset.py` tự sinh. Mỗi mẫu gồm hồ sơ học viên giả định, câu hỏi nhiều kiểu (có dấu, không dấu, tiếng Anh, câu bẫy) và đáp án do code tính, nên đáp án luôn đúng. Các câu giống bộ đánh giá đã bị loại để chấm cho công bằng.
- Mô hình được huấn luyện trên Google Colab bằng Unsloth, xuất ra GGUF và chạy cục bộ bằng Ollama.

---

## 7. Kiểm thử

### 7.1. Dữ liệu kiểm thử: ba hồ sơ học viên khác nhau trên mọi mặt

Dữ liệu cấu hình trong `backend/e2e_personas.py`. Ngày tháng tính tương đối theo ngày chạy, và dữ liệu tự làm mới mỗi ngày.

| Tài khoản | Tình trạng | Học tập | Lịch | Học phí | Hồ sơ đầu vào | Luận văn |
|---|---|---|---|---|---|---|
| E2eMba | Đã tốt nghiệp | 3 môn đạt, trung bình 15,97 | Không còn lịch | Kỳ 2 còn 40 triệu, hạn sau 20 ngày | IELTS 7.0, bằng Giỏi | Đã bảo vệ, 16 điểm |
| E2eMms | Đang học kỳ 2 | 1 môn đạt, 1 môn miễn, 1 môn đang học | Học ngày mai, thi sau 5 ngày | Học bổng 50%, đã đóng đủ | TOEIC 820, bằng Khá | Chưa bắt đầu |
| E2eMscm | Đang học, học lực yếu | 1 môn chưa đạt, 1 môn miễn, chuyên cần 40–50% | Học hôm nay, thi lại sau 2 ngày | Học bổng 50%, kỳ 1 quá hạn 12 ngày, nợ 30 triệu | IELTS 5.5, bằng Trung bình khá | Đang làm, chưa có người hướng dẫn |

### 7.2. Kết quả

| Bộ kiểm thử | Số câu hoặc bước | Kết quả |
|---|---|---|
| Bộ câu hỏi chung (quy chế, thủ tục, câu khó) | 41 | 41/41 đạt; đúng nội dung 18/18 |
| Bộ tình huống theo tài khoản (14 nhóm tình huống) | 99 | 99/99 đạt; đúng nội dung 96/96 |
| UniBot tuyển sinh: bộ câu hỏi (10 nhóm) | 44 | 44/44 đạt; đúng nội dung 40/40 |
| UniBot tuyển sinh: kịch bản chuyển khách tiềm năng | 15 bước | 15/15 đạt |
| UniBot tuyển sinh: luồng xuất bản nội dung (soạn, duyệt, hiệu lực) | 16 bước | 16/16 đạt |
| Kịch bản luồng nghiệp vụ đầu-cuối | 34 bước | 34/34 đạt |

- Bộ tình huống chia thành 14 nhóm: điểm, môn học, chuyên cần, học phí, học bổng, lịch, luận văn, trạng thái, hồ sơ, hồ sơ đầu vào, tiếng Anh, học viên lo lắng, câu bẫy, gặp cán bộ.
- Kịch bản luồng nghiệp vụ kiểm tra:
  - Phân quyền ở backend.
  - Khóa và mở tài khoản theo trạng thái học tập.
  - Duyệt tài liệu và ngày hiệu lực.
  - FAQ cần duyệt và phạm vi chương trình.
  - Mật khẩu tạm, bắt đổi mật khẩu ở lần đăng nhập đầu, email báo tài khoản.
- **Phân bố cách trả lời** trên 140 câu:

  | Cách trả lời | Số câu | Thời gian trung bình |
  |---|---|---|
  | Quy tắc | 112 | 0,2 giây |
  | Mô hình | 15 | 10,7 giây |
  | Chuyển cán bộ vì chưa có thông tin | 5 | |
  | Theo yêu cầu gặp cán bộ | 4 | |
  | FAQ | 4 | |

- Lệnh chạy lại toàn bộ: `python backend/eval_student_bot.py` (bot học viên) và `python backend/eval_admission_bot.py` (bot tuyển sinh).
- UniBot tuyển sinh có 16 câu trả lời bằng FAQ (trung bình 0,6 giây) và 20 câu qua mô hình (trung bình 8,9 giây). Bộ đánh giá bao gồm các câu bẫy về học phí, mức điểm tiếng Anh và dữ liệu cá nhân của người khác. Chi tiết ở `training/BAO_CAO_KET_QUA.md`, mục 8.

Bộ kiểm thử đã phát hiện nhiều lỗi mà dữ liệu mẫu giống nhau từng che mất, và các lỗi đó đã được sửa:

- Khoản phải đóng tiếp theo bị trả nhầm kỳ 2, trong khi kỳ 1 đang quá hạn.
- So sánh điểm hai học kỳ chỉ trả về một kỳ.
- Môn được miễn bị báo là chưa công bố điểm.
- Hỏi chuyên cần của môn đang học thì không thấy tỷ lệ.
- Câu về hội đồng luận văn bị chuyển cán bộ dù dữ liệu đã có.

---

## 8. Các module tiêu biểu để trình diễn

Thứ tự đề xuất, khoảng 12–15 phút:

1. **Trang giới thiệu và UniBot tuyển sinh** (2 phút). Hỏi bot rồi đăng ký tư vấn ngay trong khung chat. Đăng nhập chuyên viên tuyển sinh để thấy yêu cầu đã được giao, kèm lịch sử hỏi bot và hồ sơ CRM.
2. **Tạo tài khoản học viên tự động** (1–2 phút). Kể luồng từ xếp lớp tới mã học viên, sổ học phí, tài khoản, email; demo đăng nhập lần đầu bị bắt đổi mật khẩu.
3. **UniBot học viên trên một tài khoản E2eMscm** (6 phút), theo kịch bản bên dưới.
4. **Quản trị kho kiến thức** (2 phút). Cán bộ chương trình tải tài liệu lên, tài liệu ở trạng thái "Chờ duyệt", bot chưa dùng. Ban giám đốc bấm Duyệt, bot trả lời được ngay.
5. **Kết bằng số liệu** (2 phút): bảng huấn luyện ở mục 6 và bảng kiểm thử ở mục 7.

**Kịch bản hỏi trên E2eMscm.** Mở khung chat, mục "Cần chú ý" tự hiện 3 việc: học phí quá hạn, thi lại sau 2 ngày, buổi học hôm nay.

| # | Câu hỏi | Điểm thể hiện |
|---|---|---|
| 1 | Điểm các môn của tôi | Dữ liệu riêng: môn chưa đạt, môn miễn, môn đang học |
| 2 | Tôi có môn nào bị trượt không? | Trả lời đúng trọng tâm, kèm lịch thi lại |
| 3 | Tôi được miễn môn nào? | Đọc dữ liệu công nhận tín chỉ |
| 4 | Chuyên cần môn Logistics của tôi | Nhận ra tên môn dù chỉ gõ một chữ |
| 5 | Hôm nay tôi có buổi học nào không? | Hiểu ngày tương đối |
| 6 | Tôi có khoản nào quá hạn không? | Số tiền và số ngày quá hạn |
| 7 | Tôi có học bổng không? | Học phí gốc, phần được giảm, phần còn phải đóng |
| 8 | Điểm IELTS của tôi bao nhiêu? | Hồ sơ đầu vào |
| 9 | Ai hướng dẫn luận văn của tôi? | Chưa có dữ liệu thì nói thật |
| 10 | Did I fail any course? | Song ngữ, vẫn tức thì |
| 11 | Tôi sợ trượt lần nữa, khi nào thi lại? | Trấn an, rồi đưa đúng thông tin |
| 12 | Điểm thi lại của tôi là bao nhiêu? | Chưa thi thì không bịa điểm |
| 13 | Nếu tôi trượt thi lại thì có bị đuổi học không? | Câu quy chế chưa có tài liệu: chuyển cán bộ, không phán bừa |
| 14 | Cho tôi gặp cán bộ | Chuyển đúng bộ phận; cán bộ trả lời ngay trong khung chat |

---

## 9. Bảo mật và toàn vẹn dữ liệu

- **Mật khẩu.** Mật khẩu tạm ngẫu nhiên, bắt buộc đổi ở lần đăng nhập đầu. Khi admin đặt lại mật khẩu, người dùng cũng phải đổi lại.
- **Kiểm quyền.** Frontend và backend cùng kiểm tra cho các thao tác nhạy cảm.
- **Học viên chỉ thấy dữ liệu của mình**, và điều này có kiểm thử riêng.
- **Thôi học** thì tài khoản tự khóa.
- **Kho kiến thức công khai** tự ẩn dữ liệu cá nhân. Nội dung cho bot phải qua duyệt và có ngày hiệu lực.
- **Mô hình chạy cục bộ**, dữ liệu học viên không gửi ra dịch vụ bên ngoài.

---

## 10. Hạn chế và hướng phát triển

**Hạn chế:**

- Câu phải qua mô hình mất khoảng 5–10 giây trên laptop không có GPU, và chậm hơn khi máy chạy pin.
- Email chỉ gửi đi được khi máy chủ SMTP đã cấu hình trong `backend/.env`. Khi chưa cấu hình, email nằm chờ trong hàng đợi.
- Mới rà quyền ở backend cho các API thuộc luồng học viên và bot. Các API khác vẫn chủ yếu được chặn ở frontend.

**Hướng phát triển:**

- Chạy mô hình trên máy có GPU để đưa thời gian trả lời xuống dưới 3 giây.
- Huấn luyện vòng 3 với nhiều tình huống quy chế hơn.
- Rà kiểm quyền backend cho toàn hệ thống.
- Thêm kênh thông báo đẩy (email, tin nhắn) cho mục "Cần chú ý".

---

## 11. Phụ lục

### Tài khoản thử (mật khẩu `123!`)

| Tài khoản | Vai trò |
|---|---|
| E2eMscm | Học viên, dùng cho demo chính |
| E2eMms | Học viên đang học, có học bổng và môn miễn |
| E2eMba | Học viên đã tốt nghiệp |
| NhungLH | Chuyên viên tuyển sinh |
| HaLP | Cán bộ chương trình MBA |
| LinhTK | Cán bộ chương trình Master Chuyên ngành |
| AnhTT | Ban giám đốc, người duyệt tài liệu |
| Admin | Quản trị hệ thống |

### Chạy hệ thống

```
.venv\Scripts\activate
cd backend && python main.py          (cổng 8026)
cd frontend && python main.py         (cổng 8027)
python backend/eval_student_bot.py    (kiểm thử bot, làm mới dữ liệu mẫu theo ngày)
```

Ollama cần có ba mô hình `unibot-hv2-q4`, `qwen2.5:3b` và `nomic-embed-text`.

### Tệp chính

| Tệp | Nội dung |
|---|---|
| `backend/main.py`, `frontend/main.py` | Điểm vào backend và frontend |
| `backend/rbac.py`, `backend/seed_org.py` | Phân quyền, tài khoản mặc định |
| `backend/ops_crud.py` | Xếp lớp, tạo học viên và tài khoản |
| `backend/treasury_ops.py` | Học phí, miễn giảm, khoản thu |
| `backend/learner_spine.py` | Hồ sơ người học thống nhất, bảng điểm |
| `backend/student_accounts.py` | Vòng đời tài khoản học viên |
| `backend/email_outbox.py` | Hàng đợi và gửi email |
| `backend/admission_bot.py` | UniBot tuyển sinh, kho kiến thức, tìm kiếm |
| `backend/eval_admission_bot.py` và `backend/data/admission_kb/` | Bộ đánh giá và kho kiến thức tuyển sinh |
| `backend/student_bot.py` | UniBot học viên |
| `backend/student_bot_lang.py` | Lớp song ngữ |
| `backend/e2e_personas.py` | Dữ liệu ba học viên mẫu |
| `backend/eval_student_bot.py` và `backend/data/student_kb/` | Bộ kiểm thử và kho kiến thức học vụ |
| `training/` | Sinh dữ liệu, notebook huấn luyện và xuất mô hình, báo cáo kết quả |
