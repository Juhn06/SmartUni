# UniBot học viên và UniBot tuyển sinh: quá trình xây dựng, huấn luyện và kết quả thực nghiệm

Built with Qwen. Mô hình gốc Qwen2.5-3B-Instruct dùng Qwen Research License, chỉ dùng cho mục đích phi thương mại (đồ án).

## 1. Bài toán

Học viên hỏi bot trong cổng học viên về hai nhóm nội dung:

- Dữ liệu riêng của chính mình: điểm từng môn, học phí còn nợ, lịch thi, tiến trình học tập, luận văn.
- Quy chế, thủ tục học vụ chung.

Yêu cầu bắt buộc:

- Trả lời đúng dữ liệu của tài khoản đang đăng nhập, không lẫn sang tài khoản khác.
- Không bịa học phí, ngày tháng, con số.
- Câu không trả lời được thì chuyển cho cán bộ chương trình.
- Chạy miễn phí trên máy cá nhân, không gọi API trả phí.

## 2. Kiến trúc trả lời ba lớp

| Lớp | Cách làm | Dùng cho | Thời gian |
|---|---|---|---|
| 1. Quy tắc | Code đọc thẳng dữ liệu học viên rồi điền vào mẫu câu | Câu hỏi rõ ràng về điểm, học phí, lịch, tiến trình | Dưới 0,1 giây |
| 2. FAQ | So khớp câu hỏi với kho câu hỏi thường gặp (25 câu, 84 cách hỏi khác nhau) | Câu thủ tục phổ biến | Dưới 0,1 giây |
| 3. Mô hình ngôn ngữ | Mô hình đọc "phiếu dữ liệu" của học viên và tài liệu học vụ để trả lời | Câu hỏi tự do, so sánh, câu khó | Khoảng 10 giây |

Các câu trả lời do mô hình sinh ra đi qua bốn bước kiểm tra trước khi gửi cho học viên:

- Mọi con số trong câu trả lời phải có trong dữ liệu đầu vào.
- Không được lộ dữ liệu của học viên mẫu.
- Không được lẫn chữ nước ngoài.
- Nếu mô hình báo "không có thông tin", câu hỏi được chuyển cho cán bộ.

## 3. Phương pháp đánh giá

- Bộ 41 câu hỏi kiểm thử viết tay, tách riêng với dữ liệu huấn luyện.
- Mỗi câu được chấm hai tiêu chí:
  - **Đúng hướng xử lý:** bot chọn đúng cách trả lời (tự trả lời hay chuyển cán bộ), áp dụng cho cả 41 câu.
  - **Đúng nội dung:** câu trả lời có đủ thông tin bắt buộc và không chứa thông tin sai, áp dụng cho 18 câu có đáp án kiểm tra.
- Khi chấm, mô hình chạy với temperature 0 và không gửi kèm lịch sử hội thoại, để kết quả lặp lại giống nhau giữa các lần chạy.
- Công cụ chấm: `backend/eval_student_bot.py`.

## 4. Các giai đoạn và kết quả

### Giai đoạn 0: chọn mô hình nền

- Thử qwen3:4b: mô hình luôn bật chế độ "suy nghĩ" và không tắt được, nên trả lời rất chậm. Đã loại.
- Chọn qwen2.5:3b chạy bằng Ollama trên laptop (CPU i7 thế hệ 11, RAM 20 GB, không có GPU rời).

### Giai đoạn 1: mô hình gốc kết hợp phiếu dữ liệu và kiểm soát

- Mô hình gốc thường đọc sai phiếu dữ liệu: đếm nhầm số môn, bỏ sót khoản phí, có lần tự cộng ra tổng học phí 120 triệu không có thật.
- Cách khắc phục khi chưa huấn luyện:
  - Đưa các câu hỏi về điểm, học phí, lịch sang lớp quy tắc.
  - Thêm bước kiểm tra con số, đặt temperature về 0.
  - Thử cách học từ ví dụ: đưa vài câu hỏi mẫu kèm đáp án vào lời nhắc. Cách này đã được gỡ bỏ khi chuyển sang mô hình đã huấn luyện, vì LoRA thay thế hoàn toàn.
- **Kết quả: 40/41 đúng hướng xử lý, 14/18 đúng nội dung.**

### Giai đoạn 2: huấn luyện LoRA vòng 1

- Dữ liệu: 1.500 mẫu do `gen_dataset.py` tự sinh. Mỗi mẫu gồm hồ sơ học viên giả định, câu hỏi nhiều kiểu (có dấu, không dấu, tiếng Anh, câu bẫy, câu ngoài phạm vi) và đáp án do code tính nên luôn đúng.
- Cấu hình: 1 lượt huấn luyện, rank 16, xuất bản nén q4_k_m.
- **Kết quả: 39/41, 14/18.** Không tốt hơn mô hình gốc, và chưa ổn định giữa các lần chạy.
- Nguyên nhân: mô hình chọn chữ ngẫu nhiên, lịch sử hội thoại cũ làm nhiễu câu trả lời mới.
- Khắc phục: đặt temperature 0, không gửi lịch sử hội thoại cho mô hình.

### Giai đoạn 3: huấn luyện LoRA vòng 2

- Dữ liệu: 2.000 mẫu huấn luyện và 150 mẫu kiểm tra. Đã loại các câu giống bộ đánh giá (độ giống từ 0,6 trở lên) để chấm cho công bằng.
- Cấu hình: Qwen2.5-3B-Instruct, Unsloth, Google Colab GPU L4.
  - 2 lượt, LoRA rank 32, alpha 32.
  - Learning rate 2e-4, batch 2 × tích lũy 4.
  - bf16, xuất bản nén q8_0.
- **Kết quả: 40/41, 16/18.** Nội dung đúng tăng từ 14 lên 16 câu, ổn định giữa các lần chạy.

### Giai đoạn 4: nén mô hình để tăng tốc

- Xuất lại LoRA vòng 2 sang bản nén q4_k_m, không huấn luyện lại.
- Đo trên cùng 41 câu, cùng điều kiện máy cắm sạc. Thời gian tính trên 12 câu phải qua mô hình:

| | q8_0 | q4_k_m (đang dùng) |
|---|---|---|
| Dung lượng | 3,3 GB | 1,9 GB |
| Đúng hướng xử lý | 40/41 | 40/41 |
| Đúng nội dung | 16/18 | 16/18 |
| Thời gian trung vị | 21,3 giây | 10,4 giây |
| Thời gian trung bình | 30,9 giây | 16,2 giây |

- **Kết luận:** bản q4 giữ nguyên độ chính xác, nhanh gấp khoảng 2 lần và nhẹ hơn 42% RAM.

### Giai đoạn 5: tối ưu thời gian phản hồi

- Nạp sẵn mô hình khi backend khởi động và giữ trong RAM 30 phút, nên câu hỏi đầu tiên không phải chờ nạp mô hình.
- Câu hỏi về dữ liệu cá nhân bỏ qua bước tìm tài liệu, nhanh hơn khoảng 2,5 giây.
- Lưu sẵn câu trả lời: hỏi lại đúng câu cũ thì trả lời ngay.
- Đã thử rút gọn phiếu dữ liệu gửi cho mô hình: không nhanh hơn (10,9 giây so với 11,1 giây) mà còn làm sai một câu, nên bỏ.
- Phát hiện: khi laptop chạy pin, cùng một câu có thể mất 26–90 giây vì Windows hạ hiệu năng CPU. Khi trình diễn nên cắm sạc.

### Giai đoạn 6: song ngữ Việt – Anh

- Bot trả lời đúng ngôn ngữ của câu hỏi, không phụ thuộc giao diện đang để tiếng gì.
- Câu tiếng Anh được đổi sang từ khóa tiếng Việt để đi qua lớp quy tắc. Câu trả lời được chuyển sang tiếng Anh bằng bảng mẫu câu cố định.
- Nhờ vậy câu tiếng Anh về điểm, học phí, lịch cũng trả lời dưới 0,1 giây và không có nguy cơ bịa số.

## 5. Kiểm thử theo tình huống học viên

Ba tài khoản mẫu được dựng với hoàn cảnh khác nhau trên mọi mặt dữ liệu. Cấu hình nằm trong `backend/e2e_personas.py`, ngày tháng tính tương đối theo ngày chạy.

| Tài khoản | Tình trạng | Điểm và môn học | Lịch | Học phí | Luận văn |
|---|---|---|---|---|---|
| E2eMba | Đã tốt nghiệp | 3 môn đạt, trung bình 15,97 | Không còn lịch | Kỳ 2 còn 40 triệu, hạn sau 20 ngày | Đã bảo vệ, 16 điểm, có hội đồng |
| E2eMms | Đang học kỳ 2 | 1 môn đạt, 1 môn được miễn, 1 môn đang học (chuyên cần 75%) | Học ngày mai, thi sau 5 ngày | Học bổng 50%, đã đóng đủ | Chưa bắt đầu |
| E2eMscm | Đang học, học lực yếu | 1 môn chưa đạt (9,7), chuyên cần 40–50% | Học hôm nay, thi lại sau 2 ngày | Kỳ 1 quá hạn 12 ngày, còn nợ 60 triệu | Đang làm, chưa có người hướng dẫn |

Có hai bộ kiểm thử, chạy bằng lệnh `python backend/eval_student_bot.py`:

- **Bộ câu hỏi chung** (`eval_questions.json`, 41 câu): quy chế, thủ tục, câu khó, chạy trên tài khoản E2eMba.
- **Bộ tình huống theo tài khoản** (`eval_scenarios.json`, 87 câu): mỗi tài khoản 27–32 câu, chia 13 nhóm. Các nhóm gồm điểm, môn học, chuyên cần, học phí, học bổng, lịch, luận văn, trạng thái học tập, hồ sơ, tiếng Anh, học viên lo lắng, câu bẫy dễ bịa và yêu cầu gặp cán bộ. Đáp án mong đợi lấy đúng theo dữ liệu riêng của từng người. Công cụ chấm trên đúng câu trả lời mà học viên nhìn thấy.

Bộ tình huống đã tìm ra các lỗi bị che khi các tài khoản dùng chung một bộ dữ liệu. Tất cả đã được sửa:

- Hỏi "khoản tiếp theo phải đóng" lại rơi xuống mô hình, và mô hình trả lời kỳ 2 trong khi kỳ 1 đang quá hạn.
- Hỏi thẳng tên môn đang được miễn thì bot trả lời là "chưa công bố điểm".
- Hỏi chuyên cần của môn đang học thì không thấy tỷ lệ chuyên cần.
- "So sánh điểm kỳ 1 với kỳ 2" chỉ trả về điểm kỳ 1.
- Câu hỏi về hội đồng luận văn bị chuyển cán bộ dù dữ liệu đã có.

Kết quả cuối:

| Bộ kiểm thử | Đạt hoàn toàn | Đúng hướng xử lý | Đúng nội dung |
|---|---|---|---|
| Bộ câu hỏi chung | 41/41 | 41/41 | 18/18 |
| Bộ tình huống theo tài khoản | 87/87 | 87/87 | 84/84 |

Trong 128 câu, 98 câu được trả lời bằng quy tắc (dưới 0,1 giây). 17 câu phải qua mô hình, khoảng 5–10 giây mỗi câu. Các câu còn lại trả lời bằng FAQ hoặc được chuyển cán bộ.

Cùng một câu hỏi, mỗi tài khoản nhận được câu trả lời theo đúng dữ liệu của mình. Số liệu bot đưa ra khớp với trang "Nghĩa vụ phí của tôi" của chính tài khoản đó.

## 6. Tổng hợp

| Giai đoạn | Đúng hướng (41) | Đúng nội dung (18) | Ghi chú |
|---|---|---|---|
| Mô hình gốc qwen2.5:3b | 40 | 14 | Hay đọc sai phiếu dữ liệu |
| LoRA vòng 1 | 39 | 14 | Chưa ổn định |
| LoRA vòng 2 (q8_0) | 40 | 16 | Ổn định, trung vị 21,3 giây |
| LoRA vòng 2 (q4_k_m) | 40 | 16 | Trung vị 10,4 giây, bản đang dùng |

## 7. Luồng nghiệp vụ gắn với bot

- **Tài khoản học viên** được tạo tự động khi cán bộ chương trình đưa hồ sơ official vào lớp. Tài khoản có mật khẩu tạm ngẫu nhiên, học viên bị bắt đổi ở lần đăng nhập đầu, và email báo tài khoản được xếp vào hàng đợi. Email được gửi khi máy chủ SMTP đã cấu hình.
- **Trạng thái học tập** đồng bộ với tài khoản: thôi học thì khóa tài khoản, quay lại học thì mở khóa, tốt nghiệp thì chuyển sang cựu học viên, bảo lưu thì bot nói rõ là đang bảo lưu.
- **Tài liệu và FAQ cho bot**: cán bộ chương trình chỉ đưa lên cho chương trình mình phụ trách. Bot chỉ dùng sau khi Ban giám đốc, Trợ lý BGĐ hoặc Admin duyệt, và chỉ trong khoảng ngày hiệu lực. Quyết định riêng của từng học viên nhập ở module nghiệp vụ, bot đọc trực tiếp.
- **Kiểm tra quyền ở backend** cho các thao tác trong luồng này, không chỉ dựa vào giao diện.
- Kịch bản kiểm thử đầu-cuối có 34 bước, đạt 34/34.

## 8. UniBot tuyển sinh: kết quả đánh giá

UniBot tuyển sinh là icon nổi trên trang giới thiệu công khai. Bot trả lời người quan tâm về chương trình, điều kiện, hồ sơ, quy trình xét tuyển và học bổng, rồi chuyển khách tiềm năng sang chuyên viên tuyển sinh.

### 8.1. Cách trả lời

- **FAQ:** câu hỏi khớp FAQ thì trả lời ngay bằng câu trả lời đã soạn sẵn.
- **Mô hình:** các câu còn lại dùng Hybrid RAG. Hệ thống tìm đoạn liên quan bằng BM25 kết hợp vector, trộn kết quả bằng RRF, rồi mô hình `qwen2.5:3b` viết câu trả lời chỉ dựa trên các đoạn tìm được (temperature 0).
- **Không có thông tin:** bot nói rõ là chưa có, chuyển câu hỏi cho chuyên viên và đưa câu đó vào danh sách "câu chưa trả lời" để bổ sung kho kiến thức.
- **Học phí và học bổng:** bot không đưa con số chung, chỉ mời người hỏi đăng ký tư vấn.
- **Câu tiếng Anh:** từ khóa được đổi sang tiếng Việt để tìm kiếm, và bot trả lời bằng tiếng Anh.

### 8.2. Kho kiến thức

Kho gồm 5 tài liệu và 27 FAQ, mỗi FAQ có nhiều cách hỏi. Nội dung bao quát:

- Ba chương trình và cách chọn chương trình phù hợp.
- Đối tượng dự tuyển, điều kiện tiếng Anh, danh mục hồ sơ.
- Lịch tuyển sinh, thi viết, phỏng vấn, kết quả.
- Thời lượng, hình thức học, ngôn ngữ giảng dạy, văn bằng.
- Học phí và học bổng (chỉ mô tả chính sách chung, không có con số), trao đổi quốc tế.

Theo quy ước của dự án, **không có con số học phí hay mức điểm tiếng Anh cụ thể** vì trung tâm chưa có tài liệu chính thức. Bộ lọc tự ẩn số điện thoại, email và số giấy tờ trong tài liệu công khai.

### 8.3. Kết quả

Lệnh chạy: `python backend/eval_admission_bot.py`. Bộ đánh giá chạy qua đúng luồng xử lý thật rồi tự xóa dữ liệu thử.

| Bộ kiểm thử | Kết quả |
|---|---|
| Bộ câu hỏi (44 câu, 10 nhóm) | **44/44** đạt; đúng hướng xử lý 44/44; đúng nội dung 40/40 |
| Kịch bản chuyển khách tiềm năng | **15/15** bước đạt |

Kết quả giống nhau qua hai lần chạy liên tiếp.

Các nhóm câu hỏi: chương trình, điều kiện, hồ sơ, quy trình, học tập, học phí và học bổng (không được bịa số), tiếng Anh, ngoài phạm vi, riêng tư (hỏi số điện thoại hay điểm của người khác), giao tiếp.

| Cách trả lời | Số câu | Thời gian trung bình |
|---|---|---|
| FAQ | 16 | 0,6 giây |
| Mô hình (Hybrid RAG) | 20 | 8,9 giây |
| Chuyển chuyên viên vì chưa có thông tin | 4 | 4,5 giây |
| Chào hỏi, cảm ơn, gặp tư vấn viên, để lại liên hệ | 4 | Tức thì |

Kịch bản chuyển khách tiềm năng kiểm tra các bước sau:

- Hỏi học phí thì bot mời để lại liên hệ, không đưa con số.
- Khách để lại số điện thoại trong khung chat thì hệ thống tạo yêu cầu tư vấn gắn với hội thoại, giao cho chuyên viên tuyển sinh, ghi đúng chương trình quan tâm.
- Chuyên viên xem được toàn bộ lịch sử khách đã hỏi bot.
- Hệ thống tự tạo hồ sơ CRM, lịch nhắc liên hệ và chấm mức độ quan tâm.
- Form đăng ký thiếu xác nhận đồng ý thì bị từ chối; đăng ký lại cùng số điện thoại không tạo yêu cầu trùng.
- Khách đòi gặp tư vấn viên thì được chuyển ngay.
- Câu bot không trả lời được vào danh sách cần bổ sung.
- Kho kiến thức công khai tự ẩn dữ liệu cá nhân.

### 8.4. Quy trình xuất bản nội dung cho bot

Quy trình mô phỏng cách các trường công bố thông tin tuyển sinh:

1. **Soạn:** cán bộ tuyển sinh tải thông báo, quy định lên hoặc soạn FAQ, kèm khoảng thời gian hiệu lực của đợt tuyển sinh. Nội dung ở trạng thái **Chờ duyệt**.
2. **Duyệt:** người có quyền "Duyệt nội dung UniBot tuyển sinh" duyệt để công bố, hoặc trả lại kèm lý do. Mặc định quyền này thuộc Ban giám đốc, Trợ lý BGĐ và Admin, và có thể cấp thêm cho trưởng phòng tuyển sinh qua trang phân quyền.
3. **Công bố:** UniBot dùng nội dung ngay sau khi duyệt, chỉ trong thời gian hiệu lực. Hết đợt tuyển sinh thì bot tự gỡ.
4. **Sửa sau khi công bố:** sửa nội dung hoặc thời gian hiệu lực thì nội dung quay về Chờ duyệt. Câu trả lời cán bộ soạn cho "câu bot chưa trả lời được" cũng phải qua duyệt.

Kịch bản kiểm thử luồng xuất bản đạt **16/16** bước. Kho học vụ cho bot học viên dùng cùng quy trình này.

### 8.5. Lỗi phát hiện nhờ bộ đánh giá

- **Bot trả lời "cần IELTS 6.0".** Bot không bịa: nó trích đúng một FAQ do cán bộ tạo khi thử tính năng, nhưng FAQ này mâu thuẫn với tài liệu chính. Đã xóa FAQ đó. Trường hợp này cho thấy giá trị của bộ đánh giá trong việc kiểm soát chất lượng kho kiến thức.
- **Câu hỏi tiếng Anh không tìm được tài liệu**, vì bước tìm kiếm chỉ hiểu tiếng Việt. Đã thêm bước đổi từ khóa tiếng Anh sang tiếng Việt.
- **Câu hỏi tiếng Anh khớp FAQ nhận câu trả lời tiếng Việt.** Đã chuyển các câu này qua mô hình để trả lời bằng tiếng Anh.
- **Hỏi "có những chương trình nào" bằng tiếng Anh thì bot liệt kê thiếu MBA.** Đã bổ sung FAQ liệt kê đủ ba chương trình.
- **Câu trả lời của mô hình thay đổi giữa các lần hỏi.** Đã đặt temperature về 0 cho ổn định.
- **Tài liệu vừa duyệt có thể bị đẩy khỏi kết quả tìm kiếm trong vài giây**, khi chỉ mục vector chưa kịp cập nhật. Khi trộn hai danh sách bằng RRF, đoạn mới chỉ có trong danh sách BM25 nên thua các đoạn cũ có mặt ở cả hai danh sách. Đã sửa: đoạn khớp từ khóa tốt nhất luôn được giữ trong kết quả.

## 9. Hạn chế

- Thời gian trả lời các câu phải qua mô hình phụ thuộc máy chạy: khoảng 5–10 giây khi cắm sạc, chậm hơn khi chạy pin.
- Các API khác của hệ thống, ngoài luồng học viên và bot, vẫn dựa vào kiểm tra quyền ở frontend.

Hướng phát triển:

- Huấn luyện vòng 3 với thêm dữ liệu về luận văn và các tình huống dừng học.
- Dùng máy có GPU để giảm thời gian các câu phải qua mô hình xuống dưới 3 giây.

## 10. Tệp liên quan

- `training/gen_dataset.py`: sinh dữ liệu huấn luyện.
- `training/train_unibot_lora.ipynb`: notebook huấn luyện trên Colab.
- `training/export_q4.ipynb`: notebook xuất bản nén q4.
- `training/unibot-lora-v2.zip`: trọng số LoRA vòng 2, dùng để tạo lại mô hình khi cần.
- `backend/eval_student_bot.py` và `backend/data/student_kb/eval_questions.json`: công cụ và bộ câu hỏi đánh giá.
- `backend/student_bot.py`: bot học viên.
- `backend/student_bot_lang.py`: lớp song ngữ.
- `backend/eval_admission_bot.py`, `backend/data/admission_kb/eval_questions.json`: bộ đánh giá UniBot tuyển sinh.
- `backend/data/admission_kb/`: kho kiến thức tuyển sinh.
