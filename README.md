# SmartUni – Hệ thống quản lý đào tạo sau đại học

Sinh viên thực hiện: <Họ và tên> – <MSSV> – <Lớp>

## 1. Giới thiệu

SmartUni là hệ thống web hỗ trợ chuyển đổi số nghiệp vụ của một đơn vị đào tạo sau đại học (MBA, Thạc sĩ chuyên ngành MMS, MSCM). Hệ thống quản lý xuyên suốt vòng đời một người học: từ khách hàng tiềm năng, tuyển sinh, nhập học, học tập, đến cựu học viên, với phân quyền theo từng bộ phận.

Các phân hệ chính:

- Tuyển sinh và CRM: kho dữ liệu nguồn, đợt chăm sóc, đợt xét tuyển, hồ sơ thí sinh, chấm điểm phỏng vấn.
- Chatbot tư vấn tuyển sinh: trả lời người quan tâm 24/7 từ tài liệu chính thức, tự tạo hồ sơ nguồn CRM, chấm mức quan tâm, nhắc chuyên viên gọi lại (xem mục 10).
- Điều phối chương trình MBA / MMS / MSCM: danh sách học viên, lớp – môn, điểm, điểm danh, luận văn.
- Giảng dạy và eLearning: bài giảng theo buổi, tài liệu, bài tập thực hành, trắc nghiệm, điểm danh bằng QR.
- Thủ quỹ – Kế toán: kế hoạch thu, sổ thu và công nợ, hoàn phí, hồ sơ xuất hóa đơn.
- Marcom: sự kiện, danh sách đăng ký, báo cáo.
- Trợ lý Ban Giám đốc: điều phối học viên và giảng viên quốc tế.
- Thư viện học thuật: tải bài báo PDF, tìm kiếm và hỏi đáp bằng RAG (ChromaDB + LLM tương thích OpenAI API).
- Quản trị hệ thống: người dùng, bộ phận, phân quyền RBAC, danh mục trạng thái, nhập dữ liệu hàng loạt từ Excel, góp ý chức năng.

## 2. Công nghệ sử dụng

| Thành phần | Công nghệ |
|---|---|
| Backend API | Python 3.12, Flask, SQLite |
| Frontend | Python 3.12, Flask, Jinja2 templates, HTML/CSS |
| Tìm kiếm ngữ nghĩa | ChromaDB, PyMuPDF, OpenAI SDK |
| Xuất file | openpyxl, python-docx, python-pptx |
| Đóng gói, triển khai | Docker, Docker Compose, Nginx (reverse proxy) |
| CI | GitHub Actions (kiểm tra biên dịch Python và cấu hình Compose) |

Kiến trúc gồm 2 service tách biệt:

```
Trình duyệt ──> Frontend Flask (:8027) ──HTTP/JSON──> Backend Flask API (:8026) ──> SQLite / ChromaDB / uploads
```

## 3. Cấu trúc thư mục

```
Source/
├── backend/                 Backend API (Flask)
│   ├── main.py              Điểm khởi chạy, khai báo route API
│   ├── rbac.py              Phân quyền, menu theo bộ phận
│   ├── seed_org.py          Khởi tạo bộ phận, tài khoản, quyền mặc định
│   ├── ops_data.py          Lược đồ và truy vấn dữ liệu nghiệp vụ
│   ├── ops_crud.py          CRUD và xuất dữ liệu cho các phân hệ
│   ├── ops_bulk_import.py   Nhập dữ liệu hàng loạt từ Excel
│   ├── admission_ops.py     Đợt tuyển sinh, hồ sơ thí sinh
│   ├── crm_ops.py           CRM tuyển sinh
│   ├── admission_bot.py     Chatbot tư vấn: kho kiến thức, truy xuất BM25 + vector, trả lời, đẩy lead vào CRM
│   ├── import_admission_kb.py  Nạp cả thư mục tài liệu tuyển sinh vào kho kiến thức
│   ├── mba_ops.py           Điều phối MBA
│   ├── mms_program.py       Chương trình MMS
│   ├── mscm_coord.py        Điều phối MSCM
│   ├── coord_ops.py         Nghiệp vụ điều phối chung
│   ├── course_content.py    Chương trình, học phần, buổi học, tài liệu
│   ├── class_lessons.py     Bài giảng theo lớp – môn
│   ├── lesson_attendance.py Điểm danh theo buổi
│   ├── practice_homework.py Bài tập thực hành
│   ├── mc_quiz.py           Bài trắc nghiệm
│   ├── elearn_ops.py        eLearning
│   ├── treasury_ops.py      Thủ quỹ: sổ thu, công nợ
│   ├── treasury_finance.py  Kế hoạch thu, hoàn phí, hóa đơn
│   ├── marcom_ops.py        Marcom
│   ├── asst_ops.py          Trợ lý Ban Giám đốc
│   ├── person_profile.py    Hồ sơ cá nhân xuyên suốt
│   ├── learner_spine.py     Liên kết người học giữa các giai đoạn
│   ├── quality_ops.py       Rà soát chất lượng dữ liệu
│   ├── rag_service.py       Xử lý PDF, embedding, hỏi đáp RAG
│   ├── canvas_bridge.py     Kết nối Canvas LMS
│   ├── doc_preview.py       Xem trước tài liệu trong ứng dụng
│   ├── data/                PDF nhập hàng loạt; admission_kb/ là kho kiến thức khởi tạo của chatbot
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example         Mẫu biến môi trường
├── frontend/                Giao diện web (Flask + Jinja2)
│   ├── main.py              Điểm khởi chạy, route giao diện
│   ├── ops_modules.py       Cấu hình giao diện các phân hệ nghiệp vụ
│   ├── i18n.py              Chuỗi giao diện Việt / Anh
│   ├── guide_content.py     Nội dung trang hướng dẫn
│   ├── admission_bot_routes.py  Trang tư vấn công khai, widget nhúng, proxy API chatbot
│   ├── templates/           Giao diện HTML
│   ├── static/              CSS, hình ảnh
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── .github/workflows/ci.yml CI kiểm tra build
├── docker-compose.yml       Chạy đồng thời backend và frontend
└── .gitignore
```

Các thư mục `backend/db/`, `backend/uploads/`, `backend/chroma_db/` không được kèm theo. Hệ thống tự tạo chúng khi khởi động lần đầu.

## 4. Yêu cầu môi trường

- Python 3.12 (đã kiểm thử với 3.12; tối thiểu 3.10), pip
- Hoặc Docker Desktop / Docker Engine kèm Docker Compose v2
- Tùy chọn: API key của dịch vụ LLM tương thích OpenAI (OpenAI, Ollama, vLLM...) để dùng chức năng hỏi đáp RAG

## 5. Cài đặt và chạy trên máy cá nhân

### Cách 1: Chạy bằng Docker (khuyến nghị)

```bash
cd Source
docker compose up -d --build
```

- Giao diện: http://localhost:8027
- Backend API: http://localhost:8026

Dừng hệ thống: `docker compose down`. Xem log: `docker compose logs -f`.

### Cách 2: Chạy trực tiếp bằng Python

Mở 2 cửa sổ terminal.

Terminal 1 – Backend:

```bash
cd Source/backend
python -m venv .venv
# Windows: .venv\Scripts\activate    |  Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env               # Linux/macOS: cp .env.example .env
python main.py
```

Terminal 2 – Frontend:

```bash
cd Source/frontend
python -m venv .venv
# Windows: .venv\Scripts\activate    |  Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env               # Linux/macOS: cp .env.example .env
python main.py
```

Truy cập http://localhost:8027.

Ở lần khởi động đầu, backend tự tạo cơ sở dữ liệu SQLite, các bộ phận, quyền và tài khoản mặc định.

## 6. Tài khoản mặc định

Mật khẩu mặc định của mọi tài khoản khởi tạo: `123!`

| Tên đăng nhập | Vai trò |
|---|---|
| Admin | Quản trị bản ghi dữ liệu nghiệp vụ |
| NghiND | Quản trị danh mục hệ thống |

Danh sách đầy đủ (super admin và tài khoản nhân sự theo từng bộ phận) được khai báo trong `backend/seed_org.py` (`ADMIN_ACCOUNTS`, `STAFF`). Khi `RESET_STAFF_PASSWORDS=true`, mật khẩu nhân sự được đặt lại về giá trị mặc định mỗi lần backend khởi động.

## 7. Biến môi trường

| Biến | Service | Mặc định | Ý nghĩa |
|---|---|---|---|
| `PORT` | cả hai | 8026 / 8027 | Cổng chạy |
| `API_BASE_URL` | frontend | `http://127.0.0.1:8026` | Địa chỉ backend (trong Docker: `http://backend:8026`) |
| `SECRET_KEY` | frontend | `dev-secret-key` | Khóa ký session, bắt buộc đổi khi triển khai thật |
| `FLASK_DEBUG` | cả hai | `false` | Chế độ debug |
| `DB_PATH` | backend | `./db/website.db` | Đường dẫn SQLite |
| `UPLOADS_DIR` | backend | `./uploads` | Thư mục lưu file tải lên |
| `RESET_STAFF_PASSWORDS` | backend | `true` | Đặt lại mật khẩu nhân sự khi khởi động |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | backend | trống | Kết nối LLM cho RAG |
| `CHAT_MODEL`, `EMBED_MODEL` | backend | `qwen3:8b`, `text-embedding-3-small` | Mô hình hội thoại và embedding |
| `RAG_*` | backend | xem `backend/RAG_CONFIG.md` | Tùy chỉnh pipeline RAG |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM` | backend | trống | Gửi email thông báo |

## 8. Triển khai lên máy chủ

1. Cài Docker và Docker Compose trên máy chủ Linux.
2. Sao chép thư mục `Source` lên máy chủ, tạo `backend/.env` từ `.env.example` và điền khóa cần thiết.
3. Đặt `SECRET_KEY` mạnh, `RESET_STAFF_PASSWORDS=false`, `SESSION_COOKIE_SECURE=true`, `PREFERRED_URL_SCHEME=https`.
4. Chạy `docker compose up -d --build`.
5. Cấu hình Nginx làm reverse proxy cho tên miền về `127.0.0.1:8027` và cài chứng chỉ SSL:

```nginx
server {
    listen 443 ssl;
    server_name your-domain.example;
    client_max_body_size 100M;
    location / {
        proxy_pass http://127.0.0.1:8027;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

6. Kiểm tra: `http://127.0.0.1:8027/login` và `http://127.0.0.1:8026/api/metadata` trả về mã 200.

Dữ liệu SQLite, file tải lên và chỉ mục ChromaDB được lưu trong Docker volume (`backend_db`, `backend_uploads`, `backend_chroma`), không mất khi build lại image.

## 9. Lưu ý

- Mã nguồn nộp kèm không chứa dữ liệu thật của đơn vị (danh sách học viên, điểm, cơ sở dữ liệu vận hành) để bảo vệ thông tin cá nhân.
- Chức năng hỏi đáp RAG cần cấu hình LLM; các phân hệ nghiệp vụ khác hoạt động độc lập không cần LLM.

## 10. Chatbot tư vấn tuyển sinh

### Bài toán

Ở bước chăm sóc người quan tâm, câu hỏi về học phí, điều kiện, hồ sơ, lịch thi đến liên tục và ngoài giờ hành chính. Trả lời chậm làm mất ứng viên; trả lời bằng chatbot thông thường thì không biết ai là người tiềm năng. Chatbot của SmartUni gắn thẳng vào quy trình CRM tuyển sinh sẵn có.

### Luồng xử lý

```
Người quan tâm hỏi trên web (/tu-van hoặc widget nhúng)
  -> Nhận diện chương trình (MBA/MMS/MSCM) và ý định (học phí, hạn nộp, hồ sơ, điều kiện, học bổng, lịch học, sự kiện)
  -> Truy xuất lai: BM25 tiếng Việt không dấu + bigram, kết hợp vector ChromaDB (Reciprocal Rank Fusion) khi có API embedding
     Nguồn: tài liệu tuyển sinh, FAQ do chuyên viên duyệt, dữ liệu sống từ hệ thống (đợt tuyển sinh đang mở, sự kiện sắp tới)
  -> Trả lời có ghi nguồn
     Có LLM: LLM chỉ được diễn đạt lại từ tài liệu, không có thông tin thì trả về mã [CHUA_CO_THONG_TIN]
     Không có LLM: trích câu liên quan nhất từ tài liệu
     Độ khớp thấp: không đoán, chuyển chuyên viên và ghi vào danh sách câu chưa trả lời
  -> Thu liên hệ (form trong khung chat hoặc tự nhận diện SĐT, email, họ tên trong tin nhắn)
  -> Chấm điểm quan tâm 0-100 -> tạo/cập nhật Hồ sơ nguồn CRM (nguồn chatbot), ghi nhật ký chăm sóc
  -> Mức cao/rất nóng hoặc khách đòi gặp người -> tạo Nhắc nhở CRM gọi lại
  -> Chuyên viên trả lời trực tiếp trong cùng khung chat (tiếp nhận / trả lại cho bot)
  -> Câu chưa trả lời -> chuyên viên nhập câu trả lời chuẩn -> thành FAQ, các câu tương tự tự đóng
```

### Sử dụng

- Trang giới thiệu tuyển sinh công khai tại `http://localhost:8027/` (người chưa đăng nhập): chương trình, lịch tuyển sinh trong năm có đánh dấu tháng hiện tại, đợt đang mở và sự kiện lấy trực tiếp từ hệ thống, quy trình xét tuyển, học bổng, nút Đăng nhập cho học viên và cán bộ.
- Biểu tượng UniBot nổi ở góc phải trang giới thiệu; bấm vào để mở khung chat, không cần đăng nhập. Nút Đăng ký nhận tư vấn trên trang mở form để lại liên hệ trong khung chat của bot. Link `http://localhost:8027/tu-van` mở trang giới thiệu với khung chat bật sẵn (dùng cho mã QR).
- Nhúng vào website trung tâm: thêm `<script src="http://<domain>/tu-van/embed.js" async></script>` vào cuối thẻ body, biểu tượng bot sẽ xuất hiện ở góc phải.
- Kho kiến thức ban đầu nằm ở `backend/data/admission_kb/` (tổng hợp từ tài liệu nghiệp vụ tuyển sinh, nạp tự động khi cơ sở dữ liệu chưa có tài liệu). Bộ phận Tuyển sinh bổ sung thông báo tuyển sinh chính thức (học phí, điều kiện tiếng Anh) tại tab Kho kiến thức.
- Khi tải tài liệu lên, hệ thống tự ẩn số điện thoại, email, số CCCD và từ chối tệp có dạng danh sách cá nhân (danh sách học viên, ứng viên) để bot công khai không làm lộ dữ liệu.
- Màn hình quản lý: menu Tuyển sinh -> Chatbot tư vấn (`/ops/tuyen-sinh/chatbot`), dành cho bộ phận Tuyển sinh, Marcom tuyển sinh, Điều phối MBA, Ban giám đốc. Gồm: tổng quan, hội thoại, câu chưa trả lời, kho kiến thức, FAQ, chat thử (xem đoạn tài liệu được truy xuất và điểm), cấu hình.
- Nạp cả thư mục tài liệu: `cd backend && python import_admission_kb.py <thư mục>` (PDF, DOCX, XLSX, TXT, MD; tệp đã nạp sẽ được bỏ qua).

### Đăng ký nhận tư vấn và giao chuyên viên

Bot chỉ trả lời thông tin chung; việc tư vấn chi tiết (lộ trình, học phí, học bổng, hồ sơ) do chuyên viên tuyển sinh thực hiện. Khi người quan tâm đăng ký nhận tư vấn (form trên trang giới thiệu, đăng ký sự kiện, form trong khung chat, hoặc để lại số điện thoại khi chat):

1. Tạo hoặc cập nhật Hồ sơ nguồn CRM ở trạng thái Tiềm năng, mức quan tâm theo điểm bot chấm, nguồn Website hoặc Chatbot.
2. Tạo Yêu cầu tư vấn, tự giao cho chuyên viên bộ phận Tuyển sinh đang ít việc nhất (cột PIC của hồ sơ nguồn).
3. Đặt hạn liên hệ (2 giờ làm việc, ngoài giờ thì 10:00 ngày làm việc kế tiếp) và tạo Nhắc nhở CRM cho chuyên viên.
4. Ghi nhật ký chăm sóc kèm nội dung khách đã hỏi bot; nếu đăng ký sự kiện thì thêm khách vào danh sách tham dự của đợt chăm sóc.
5. Chuyên viên vào Tuyển sinh, Yêu cầu tư vấn & chatbot, tab Yêu cầu tư vấn: tiếp nhận, xem lịch sử hỏi bot, ghi chú cuộc gọi (vào nhật ký CRM), chuyển trạng thái Đã liên hệ, Đang chăm sóc, Đã nộp hồ sơ.

Trung tâm trong hệ thống là trung tâm đào tạo sau đại học giả định; tên hiển thị đổi được ở tab Cấu hình.

### Cấu hình mô hình

| Biến | Ý nghĩa |
|---|---|
| `OPENAI_API_KEY` | Bật LLM và vector search qua OpenAI |
| `OPENAI_BASE_URL` | Dùng máy chủ tương thích OpenAI khác, ví dụ Ollama `http://localhost:11434/v1` |
| `CHAT_MODEL`, `EMBED_MODEL` | Mô hình hội thoại và embedding |
| `BOT_VECTOR` | `off` để chỉ dùng BM25 |

Không cấu hình gì, bot vẫn hoạt động ở chế độ trích xuất từ tài liệu và FAQ.

### Bảo vệ

- Giới hạn tần suất theo IP và phiên chat; tin nhắn tối đa 1000 ký tự.
- Chỉ lưu liên hệ khi người dùng đồng ý; không bịa học phí, ngày tháng (bắt buộc trích từ tài liệu).

