import argparse
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description="Nạp tài liệu tuyển sinh vào kho kiến thức chatbot.")
    parser.add_argument("folder", help="Thư mục chứa PDF, DOCX, XLSX, TXT, MD")
    parser.add_argument("--db", default="", help="Đường dẫn website.db (mặc định theo DB_PATH)")
    args = parser.parse_args()

    if args.db:
        db_path = args.db
    else:
        import os

        raw = Path(os.environ.get("DB_PATH", str(BACKEND_DIR / "db" / "website.db")))
        db_path = str(raw if raw.is_absolute() else (BACKEND_DIR / raw).resolve())

    sys.path.insert(0, str(BACKEND_DIR))
    from admission_bot import _DB_PATH_HOLDER, ensure_bot_tables, import_folder, sync_vectors

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_bot_tables(conn.cursor())
    conn.commit()
    _DB_PATH_HOLDER["path"] = ""
    result = import_folder(conn, args.folder)
    conn.close()

    for item in result["imported"]:
        print(f"Đã nạp: {item['title']} ({item['chunk_count']} đoạn)")
    for name in result["skipped"]:
        print(f"Bỏ qua (đã có): {name}")
    for item in result["failed"]:
        print(f"Lỗi: {item['file']} - {item['error']}")
    print(f"Tổng: {len(result['imported'])} nạp mới, {len(result['skipped'])} bỏ qua, {len(result['failed'])} lỗi")
    vec = sync_vectors(db_path)
    if vec.get("ok"):
        print(f"Đã tạo chỉ mục vector cho {vec['count']} đoạn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
