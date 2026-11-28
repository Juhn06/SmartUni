# Huấn luyện LoRA cho UniBot học viên

Built with Qwen. Mô hình gốc Qwen2.5-3B-Instruct dùng Qwen Research License, chỉ cho mục đích phi thương mại.

## Ý tưởng

UniBot gửi cho mô hình một phiếu dữ liệu của học viên (môn học, điểm, học phí, lịch, tiến trình) kèm tài liệu học vụ và câu hỏi. Mô hình 3B gốc hay đọc sai phiếu: đếm nhầm số môn, bỏ sót khoản phí, bịa số buổi học. LoRA dạy mô hình đọc đúng phiếu này.

Dữ liệu huấn luyện do `gen_dataset.py` sinh tự động: hồ sơ học viên giả định ngẫu nhiên, câu hỏi nhiều kiểu (có dấu, không dấu, tiếng Anh, câu bẫy dễ bịa, câu ngoài phạm vi), đáp án do code tính nên luôn đúng. Phiếu dữ liệu dùng chung hàm `format_sheet` với bot thật nên định dạng khớp hoàn toàn. Câu trùng bộ đánh giá `backend/data/student_kb/eval_questions.json` bị loại để đánh giá công bằng.

## Các bước

1. Sinh dữ liệu (đã có sẵn trong `training/data`, chạy lại nếu sửa định dạng phiếu):
   ```
   .venv\Scripts\python training\gen_dataset.py
   ```
2. Mở https://colab.research.google.com, chọn *File → Upload notebook*, tải `training/train_unibot_lora.ipynb`.
3. *Runtime → Change runtime type → T4 GPU*, rồi chạy lần lượt từng ô. Ở ô tải dữ liệu, chọn `training/data/train.jsonl` và `training/data/val.jsonl`.
4. Ô cuối tải về file `.gguf` (khoảng 2 GB). Đổi tên thành `unibot-q4.gguf`, đặt vào thư mục `training/`.
5. Nạp vào Ollama:
   ```
   cd training
   ollama create unibot-hv2-q4 -f Modelfile
   ```
6. Sửa `backend/.env`: `STUDENT_CHAT_MODEL=unibot-hv2-q4`, rồi khởi động lại backend. Bot tuyển sinh vẫn dùng `CHAT_MODEL`.
7. Đo lại:
   ```
   cd backend
   python eval_student_bot.py E2eMba
   ```
   Kết quả đo (tắt ví dụ, temperature 0, không gửi lịch sử, kết quả lặp lại ổn định giữa các lần):
   - Mô hình gốc qwen2.5:3b: 40/41 đúng hướng, 14/18 đúng nội dung, khoảng 11 giây mỗi câu qua mô hình.
   - Vòng 1 (1.500 mẫu, 1 lượt, rank 16, q4_k_m): 39/41, 14/18, khoảng 14 giây.
   - Vòng 2 (2.000 mẫu, 2 lượt, rank 32, bf16, q8_0): 40/41, 16/18, khoảng 18 giây.

Muốn quay lại mô hình gốc cho bot học viên: xóa giá trị `STUDENT_CHAT_MODEL` trong `backend/.env`.
