"""Admission chatbot: knowledge base, hybrid retrieval, grounded answers, lead capture into CRM."""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import unicodedata
import uuid
from collections import Counter, defaultdict, deque
from datetime import date, datetime, timedelta
from pathlib import Path

SETTING_DEFAULTS = {
    "bot.name": "UniBot",
    "bot.org_name": "Trợ lý tuyển sinh sau đại học",
    "bot.site_name": "Trung tâm Đào tạo Sau đại học",
    "bot.greeting": (
        "Xin chào! Mình là UniBot, trợ lý tuyển sinh sau đại học. "
        "Bạn quan tâm chương trình nào (MBA, MMS, MSCM) hay cần hỏi về lịch tuyển sinh, "
        "quy trình xét tuyển, hồ sơ, học bổng?"
    ),
    "bot.hotline": "",
    "bot.contact_email": "",
    "bot.llm_enabled": "auto",
    "bot.ask_contact_after": "2",
    "bot.quick_replies": "Một năm có mấy đợt tuyển sinh MBA?|Quy trình xét tuyển gồm những bước nào?|Hồ sơ cần chuẩn bị gì?|Có học bổng không?|Sự kiện tư vấn sắp tới",
}

PROGRAM_KEYWORDS = {
    "MBA": ("mba", "quan tri kinh doanh", "business administration"),
    "MMS": ("mms", "marketing and sales", "marketing", "ban hang"),
    "MSCM": ("mscm", "chuoi cung ung", "supply chain", "logistics"),
}

CCCD_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")
PERSONAL_LIST_LIMIT = 15
SEED_VERSION = "2"

REQUEST_STATUSES = {
    "new": "Mới, chờ liên hệ",
    "contacted": "Đã liên hệ",
    "caring": "Đang chăm sóc",
    "converted": "Đã nộp hồ sơ",
    "closed": "Đóng",
}
OPEN_REQUEST_STATUSES = ("new", "contacted", "caring")
CONTACT_TIMES = {
    "office": "trong giờ hành chính",
    "morning": "vào buổi sáng",
    "afternoon": "vào buổi chiều",
    "evening": "vào buổi tối",
    "weekend": "vào cuối tuần",
}
REQUEST_SOURCES = {
    "website": "Form đăng ký trên trang giới thiệu",
    "chatbot": "Chatbot UniBot",
    "event": "Đăng ký sự kiện trên trang giới thiệu",
}
STATUS_TO_CARE = {"contacted": "interested", "caring": "consulting"}

INTENT_KEYWORDS = {
    "fee": ("hoc phi", "chi phi", "bao nhieu tien", "le phi", "tuition", "fee", "dong tien", "tra gop"),
    "deadline": ("han nop", "han chot", "deadline", "khi nao", "thoi han", "het han", "den ngay", "nop ho so", "dang ky"),
    "documents": ("ho so", "giay to", "chuan bi", "can nop", "cv", "bang diem"),
    "requirement": ("dieu kien", "yeu cau", "dau vao", "ielts", "toeic", "toefl", "tieng anh", "kinh nghiem", "bang dai hoc", "xet tuyen", "thi tuyen"),
    "scholarship": ("hoc bong", "uu dai", "giam hoc phi", "scholarship", "mien giam"),
    "schedule": ("lich hoc", "thoi gian hoc", "cuoi tuan", "buoi toi", "online", "bao lau", "may nam", "thoi gian dao tao", "khai giang"),
    "event": ("hoi thao", "su kien", "info day", "open day", "workshop", "buoi tu van"),
    "human": ("goi lai", "goi cho", "lien he voi toi", "lien he lai", "nguoi tu van", "tu van vien", "nhan vien", "gap truc tiep", "noi chuyen voi", "tu van truc tiep"),
}

INTENT_LABELS = {
    "fee": "học phí",
    "deadline": "hạn nộp/đăng ký",
    "documents": "hồ sơ",
    "requirement": "điều kiện đầu vào",
    "scholarship": "học bổng/ưu đãi",
    "schedule": "lịch học",
    "event": "sự kiện tư vấn",
    "human": "muốn gặp tư vấn viên",
}

INTENT_WEIGHTS = {
    "fee": 15,
    "deadline": 20,
    "documents": 15,
    "requirement": 10,
    "scholarship": 10,
    "schedule": 5,
    "event": 10,
    "human": 25,
}

LEVEL_RANK = {"low": 0, "medium": 1, "high": 2, "hot": 3}

GREETING_WORDS = {"xin chao", "chao", "hello", "hi", "alo", "chao ban", "chao em", "chao ad", "hey"}
THANKS_WORDS = ("cam on", "thank", "thanks", "tks")

STOPWORDS = set(
    "a ah ak ai anh ban bao ben bi biet bo cac cai can cho chi chua co con cua cung da dang day de den deu di do duoc em gi gio giup ha hay hoi hon khi khong la lai lam len ma minh mot muon nao nay nen neu nhe nhieu nhu nhung noi o oi ong qua ra rang roi sao se sau tai thay the thi tim toi trong tu va vao van ve voi vay vi vui long xem xin y"
    " the is are what how when where which who a an of to for and or in on at be do does can i you we my your please".split()
)

NO_INFO_MARK = "[CHUA_CO_THONG_TIN]"
EN_HINTS = {"what", "how", "when", "where", "fee", "fees", "tuition", "requirement", "requirements", "deadline", "program", "programme", "apply", "the"}

PHONE_RE = re.compile(r"(?<![\d+])(?:\+?84|0)(?:[\s.\-]?\d){9}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
NAME_PREFIX_RE = re.compile(
    r"(?:tên\s+(?:của\s+)?(?:tôi|em|mình|tớ)\s+là|(?:tôi|em|mình|tớ)\s+tên\s+là|(?:tôi|em|mình|tớ)\s+tên|(?:tôi|em|mình|tớ)\s+là|my name is|i am|i'm)\s+",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"[a-z0-9]+")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+(?=[A-ZÀ-Ỹ0-9\-•*])|\n+")
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

_index_lock = threading.Lock()
_index_cache: dict = {"key": None, "index": None}
_rate_lock = threading.Lock()
_rate_buckets: dict[str, deque] = defaultdict(deque)
_vector_state = {"failed_at": 0.0}


def _now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def fold(text: str) -> str:
    text = (text or "").replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.lower()


def _words(text: str) -> list[str]:
    return [w for w in TOKEN_RE.findall(fold(text)) if w not in STOPWORDS]


def tokens(text: str) -> list[str]:
    words = _words(text)
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


def _has_phrase(folded: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", folded) is not None


def detect_intents(text: str) -> list[str]:
    folded = fold(text)
    return [name for name, keys in INTENT_KEYWORDS.items() if any(_has_phrase(folded, k) for k in keys)]


def detect_program(text: str) -> str:
    folded = fold(text)
    for code, keys in PROGRAM_KEYWORDS.items():
        if any(_has_phrase(folded, k) for k in keys):
            return code
    return ""


def is_english(text: str) -> bool:
    words = TOKEN_RE.findall((text or "").lower())
    if not words or fold(text) != (text or "").lower():
        return False
    return sum(1 for w in words if w in EN_HINTS) >= 1 and not any(w in {"la", "khong", "bao", "nhieu", "cho", "toi"} for w in words)


def extract_contact(text: str) -> dict:
    out: dict = {}
    m = EMAIL_RE.search(text or "")
    if m:
        out["email"] = m.group(0).strip().lower()
    for pm in PHONE_RE.finditer(text or ""):
        digits = re.sub(r"\D", "", pm.group(0))
        if digits.startswith("84"):
            digits = "0" + digits[2:]
        if len(digits) == 10 and digits.startswith("0"):
            out["phone"] = digits
            break
    nm = NAME_PREFIX_RE.search(text or "")
    if nm:
        rest = (text or "")[nm.end():]
        parts = []
        for word in re.split(r"\s+", rest.strip()):
            clean = word.strip(",.!?;:()\"'")
            if not clean or not clean[0].isupper() or not clean.replace("-", "").isalpha():
                break
            parts.append(clean)
            if len(parts) == 5 or clean != word:
                break
        if parts:
            out["name"] = " ".join(parts)
    return out


def rate_limited(key: str, limit: int = 15, window: float = 60.0) -> bool:
    now = time.time()
    with _rate_lock:
        bucket = _rate_buckets[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
        return False


def ensure_bot_tables(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS bot_kb_docs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "title TEXT NOT NULL, "
        "source_type TEXT DEFAULT 'text', "
        "program_code TEXT DEFAULT '', "
        "file_name TEXT, "
        "content TEXT, "
        "char_count INTEGER DEFAULT 0, "
        "chunk_count INTEGER DEFAULT 0, "
        "status TEXT DEFAULT 'active', "
        "created_by TEXT, "
        "created_at TEXT, "
        "updated_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS bot_kb_chunks ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "doc_id INTEGER NOT NULL, "
        "idx INTEGER NOT NULL, "
        "text TEXT NOT NULL, "
        "FOREIGN KEY (doc_id) REFERENCES bot_kb_docs(id) ON DELETE CASCADE)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS bot_faqs ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "question TEXT NOT NULL, "
        "answer TEXT NOT NULL, "
        "program_code TEXT DEFAULT '', "
        "status TEXT DEFAULT 'active', "
        "hits INTEGER DEFAULT 0, "
        "created_by TEXT, "
        "created_at TEXT, "
        "updated_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS bot_conversations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "session_key TEXT NOT NULL UNIQUE, "
        "channel TEXT DEFAULT 'web', "
        "status TEXT DEFAULT 'open', "
        "visitor_name TEXT, "
        "phone TEXT, "
        "email TEXT, "
        "program_interest TEXT, "
        "intents TEXT DEFAULT '[]', "
        "lead_score INTEGER DEFAULT 0, "
        "lead_level TEXT DEFAULT 'low', "
        "needs_human INTEGER DEFAULT 0, "
        "profile_id INTEGER, "
        "reminder_level TEXT DEFAULT '', "
        "contact_asked INTEGER DEFAULT 0, "
        "user_turns INTEGER DEFAULT 0, "
        "page_url TEXT, "
        "client_ip TEXT, "
        "summary TEXT, "
        "created_at TEXT, "
        "last_message_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS bot_messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "conversation_id INTEGER NOT NULL, "
        "role TEXT NOT NULL, "
        "content TEXT NOT NULL, "
        "sources TEXT, "
        "confidence REAL, "
        "answered INTEGER, "
        "mode TEXT, "
        "author TEXT, "
        "created_at TEXT, "
        "FOREIGN KEY (conversation_id) REFERENCES bot_conversations(id) ON DELETE CASCADE)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS bot_gaps ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "conversation_id INTEGER, "
        "message_id INTEGER, "
        "question TEXT NOT NULL, "
        "status TEXT DEFAULT 'open', "
        "faq_id INTEGER, "
        "resolved_by TEXT, "
        "created_at TEXT, "
        "resolved_at TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS consult_requests ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "profile_id INTEGER, "
        "conversation_id INTEGER, "
        "source TEXT NOT NULL, "
        "full_name TEXT NOT NULL, "
        "phone TEXT, "
        "email TEXT, "
        "program TEXT, "
        "company TEXT, "
        "job_title TEXT, "
        "intake TEXT, "
        "contact_time TEXT, "
        "event_id INTEGER, "
        "message TEXT, "
        "status TEXT DEFAULT 'new', "
        "assigned_user_id INTEGER, "
        "assigned_login TEXT, "
        "assigned_name TEXT, "
        "sla_due_at TEXT, "
        "first_contact_at TEXT, "
        "created_at TEXT, "
        "updated_at TEXT)"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_consult_status ON consult_requests(status, sla_due_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_consult_assignee ON consult_requests(assigned_user_id, status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bot_chunks_doc ON bot_kb_chunks(doc_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bot_msg_conv ON bot_messages(conversation_id, id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bot_conv_last ON bot_conversations(last_message_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bot_gaps_status ON bot_gaps(status)")


def get_settings(conn) -> dict:
    from app_settings import ensure_app_settings

    cur = conn.cursor()
    ensure_app_settings(cur)
    rows = cur.execute("SELECT key, value FROM app_settings WHERE key LIKE 'bot.%'").fetchall()
    out = dict(SETTING_DEFAULTS)
    for key, value in rows:
        if key in SETTING_DEFAULTS and value is not None:
            out[key] = str(value)
    return out


def save_settings(conn, data: dict) -> dict:
    from app_settings import set_setting

    for key in SETTING_DEFAULTS:
        short = key.split(".", 1)[1]
        if short in data:
            set_setting(conn, key, str(data.get(short) or "").strip())
    return public_settings(conn, include_private=True)


def llm_status(conn) -> dict:
    mode = (get_settings(conn).get("bot.llm_enabled") or "auto").lower()
    configured = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_BASE_URL"))
    enabled = mode == "on" or (mode == "auto" and configured)
    if mode == "off":
        enabled = False
    return {
        "mode": mode,
        "configured": configured,
        "enabled": enabled,
        "model": os.environ.get("CHAT_MODEL", "qwen3:8b"),
    }


def public_settings(conn, include_private: bool = False) -> dict:
    s = get_settings(conn)
    out = {
        "name": s["bot.name"],
        "org_name": s["bot.org_name"],
        "site_name": s["bot.site_name"],
        "greeting": s["bot.greeting"],
        "hotline": s["bot.hotline"],
        "contact_email": s["bot.contact_email"],
        "quick_replies": [q.strip() for q in (s["bot.quick_replies"] or "").split("|") if q.strip()],
        "programs": list(PROGRAM_KEYWORDS.keys()),
    }
    if include_private:
        out["llm_enabled"] = s["bot.llm_enabled"]
        out["ask_contact_after"] = s["bot.ask_contact_after"]
        out["quick_replies_raw"] = s["bot.quick_replies"]
        out["llm"] = llm_status(conn)
    return out


def _bump_kb_version(conn) -> None:
    from app_settings import set_setting

    set_setting(conn, "botkb.version", uuid.uuid4().hex[:12])
    _schedule_vector_sync()


def _kb_version(conn) -> str:
    from app_settings import get_setting

    return get_setting(conn, "botkb.version", "0")


HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")


def chunk_text(text: str, size: int = 900) -> list[str]:
    text = re.sub(r"[ \t]+", " ", (text or "").replace("\r", ""))
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[-•*#\d]+[.)]?\s)", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    heading = ""
    for para in paras:
        hm = HEADING_RE.match(para)
        if hm:
            if buf.strip() and buf.strip() != heading:
                chunks.append(buf.strip())
            heading = hm.group(1).strip()
            buf = heading
            continue
        if len(para) > size:
            sentences = [s.strip() for s in SENT_SPLIT_RE.split(para) if s.strip()]
        else:
            sentences = [para]
        for piece in sentences:
            if buf and buf != heading and len(buf) + len(piece) + 1 > size:
                chunks.append(buf.strip())
                buf = "\n".join(x for x in (heading, piece) if x)
            else:
                buf = f"{buf}\n{piece}" if buf else piece
    if buf.strip() and buf.strip() != heading:
        chunks.append(buf.strip())
    return [c for c in chunks if len(fold(c).strip()) > 3]


def extract_text_from_file(path: str, filename: str = "") -> str:
    ext = Path(filename or path).suffix.lower()
    if ext == ".pdf":
        import fitz

        with fitz.open(path) as doc:
            return "\n\n".join(page.get_text("text") for page in doc)
    if ext == ".docx":
        import docx

        d = docx.Document(path)
        parts = [p.text for p in d.paragraphs if p.text.strip()]
        for table in d.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(dict.fromkeys(cells)))
        return "\n\n".join(parts)
    if ext in (".xlsx", ".xlsm"):
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        parts = []
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            header = [str(c).strip() if c is not None else "" for c in rows[0]]
            parts.append(f"Bảng {ws.title}")
            for row in rows[1:]:
                cells = []
                for i, value in enumerate(row):
                    if value is None or str(value).strip() == "":
                        continue
                    label = header[i] if i < len(header) and header[i] else f"Cột {i + 1}"
                    cells.append(f"{label}: {value}")
                if cells:
                    parts.append("; ".join(cells))
        return "\n\n".join(parts)
    if ext in (".txt", ".md", ".csv"):
        raw = Path(path).read_bytes()
        for enc in ("utf-8-sig", "utf-16", "cp1258", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
    raise ValueError(f"Định dạng {ext or 'không rõ'} chưa được hỗ trợ (PDF, DOCX, XLSX, TXT, MD).")


SUPPORTED_EXTS = (".pdf", ".docx", ".xlsx", ".xlsm", ".txt", ".md", ".csv")


def redact_personal(text: str) -> tuple[str, int]:
    count = 0

    def mask(_m):
        nonlocal count
        count += 1
        return "[thông tin cá nhân đã ẩn]"

    text = EMAIL_RE.sub(mask, text or "")
    text = PHONE_RE.sub(mask, text)
    text = CCCD_RE.sub(mask, text)
    return text, count


def _clean_content(content: str) -> tuple[str, int]:
    content = (content or "").strip()
    if len(content) < 20:
        raise ValueError("Nội dung tài liệu quá ngắn hoặc không đọc được chữ.")
    cleaned, hidden = redact_personal(content)
    if hidden >= PERSONAL_LIST_LIMIT:
        raise ValueError(
            f"Tài liệu chứa {hidden} số điện thoại/email/số giấy tờ, có vẻ là danh sách cá nhân "
            "(học viên, ứng viên). Không nạp vào bot công khai để tránh lộ dữ liệu."
        )
    return cleaned, hidden


def add_document(conn, *, title: str, content: str, source_type: str = "text", program_code: str = "", file_name: str = "", created_by: str = "") -> dict:
    title = (title or "").strip() or (file_name or "Tài liệu")
    content, hidden = _clean_content(content)
    chunks = chunk_text(content)
    cur = conn.cursor()
    now = _now()
    cur.execute(
        "INSERT INTO bot_kb_docs (title, source_type, program_code, file_name, content, char_count, chunk_count, status, created_by, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (title, source_type, (program_code or "").upper(), file_name, content, len(content), len(chunks), "active", created_by, now, now),
    )
    doc_id = cur.lastrowid
    cur.executemany(
        "INSERT INTO bot_kb_chunks (doc_id, idx, text) VALUES (?,?,?)",
        [(doc_id, i, c) for i, c in enumerate(chunks)],
    )
    conn.commit()
    _bump_kb_version(conn)
    return {"id": doc_id, "title": title, "chunk_count": len(chunks), "char_count": len(content), "hidden_personal": hidden}


def import_file(conn, path: str, *, title: str = "", program_code: str = "", created_by: str = "", file_name: str = "") -> dict:
    name = file_name or Path(path).name
    text = extract_text_from_file(path, name)
    if not title and Path(name).suffix.lower() == ".md":
        first = next((ln for ln in text.splitlines() if ln.strip()), "")
        hm = HEADING_RE.match(first.strip())
        if hm:
            title = hm.group(1).strip()
    return add_document(
        conn,
        title=title or Path(name).stem,
        content=text,
        source_type="file",
        program_code=program_code or detect_program(name),
        file_name=name,
        created_by=created_by,
    )


def import_folder(conn, folder: str, created_by: str = "import") -> dict:
    root = Path(folder)
    if not root.is_dir():
        raise ValueError(f"Không tìm thấy thư mục {folder}")
    existing = {r[0] for r in conn.execute("SELECT file_name FROM bot_kb_docs WHERE file_name IS NOT NULL").fetchall()}
    done, skipped, failed = [], [], []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS or path.name.startswith("~$"):
            continue
        rel = str(path.relative_to(root))
        if rel in existing:
            skipped.append(rel)
            continue
        try:
            done.append(import_file(conn, str(path), created_by=created_by, file_name=rel))
        except Exception as e:
            failed.append({"file": rel, "error": str(e)})
    return {"imported": done, "skipped": skipped, "failed": failed}


def bootstrap(conn, data_dir) -> dict:
    from app_settings import get_setting, set_setting

    ensure_bot_tables(conn.cursor())
    conn.commit()
    out = {"docs": 0, "faqs": 0}
    seed = Path(data_dir) / "admission_kb"
    if not seed.is_dir() or get_setting(conn, "botkb.seed_version", "") == SEED_VERSION:
        return out
    seed_doc_ids = [r[0] for r in conn.execute("SELECT id FROM bot_kb_docs WHERE created_by = 'seed'").fetchall()]
    for doc_id in seed_doc_ids:
        conn.execute("DELETE FROM bot_kb_chunks WHERE doc_id = ?", (doc_id,))
        conn.execute("DELETE FROM bot_kb_docs WHERE id = ?", (doc_id,))
    conn.execute("UPDATE bot_gaps SET faq_id = NULL WHERE faq_id IN (SELECT id FROM bot_faqs WHERE created_by = 'seed')")
    conn.execute("DELETE FROM bot_faqs WHERE created_by = 'seed'")
    conn.commit()
    out["docs"] = len(import_folder(conn, str(seed), created_by="seed")["imported"])
    faq_file = seed / "faq.json"
    if faq_file.is_file():
        for item in json.loads(faq_file.read_text(encoding="utf-8")):
            save_faq(conn, item, actor="seed")
            out["faqs"] += 1
    set_setting(conn, "botkb.seed_version", SEED_VERSION)
    return out


def list_documents(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, title, source_type, program_code, file_name, char_count, chunk_count, status, created_by, created_at, updated_at "
        "FROM bot_kb_docs ORDER BY id DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_document(conn, doc_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM bot_kb_docs WHERE id = ?", (doc_id,)).fetchone()
    return dict(row) if row else None


def update_document(conn, doc_id: int, data: dict) -> dict:
    doc = get_document(conn, doc_id)
    if not doc:
        raise ValueError("Không tìm thấy tài liệu.")
    title = (data.get("title") if "title" in data else doc["title"]) or doc["title"]
    program = (data.get("program_code") if "program_code" in data else doc["program_code"]) or ""
    status = data.get("status") if data.get("status") in ("active", "inactive") else doc["status"]
    content = data.get("content") if "content" in data else None
    cur = conn.cursor()
    if content is not None and content.strip() != (doc["content"] or "").strip():
        content, _hidden = _clean_content(content)
        chunks = chunk_text(content)
        if not chunks:
            raise ValueError("Nội dung trống.")
        cur.execute("DELETE FROM bot_kb_chunks WHERE doc_id = ?", (doc_id,))
        cur.executemany(
            "INSERT INTO bot_kb_chunks (doc_id, idx, text) VALUES (?,?,?)",
            [(doc_id, i, c) for i, c in enumerate(chunks)],
        )
        cur.execute(
            "UPDATE bot_kb_docs SET content = ?, char_count = ?, chunk_count = ? WHERE id = ?",
            (content.strip(), len(content.strip()), len(chunks), doc_id),
        )
    cur.execute(
        "UPDATE bot_kb_docs SET title = ?, program_code = ?, status = ?, updated_at = ? WHERE id = ?",
        (title.strip(), program.upper(), status, _now(), doc_id),
    )
    conn.commit()
    _bump_kb_version(conn)
    return get_document(conn, doc_id)


def delete_document(conn, doc_id: int) -> None:
    conn.execute("DELETE FROM bot_kb_chunks WHERE doc_id = ?", (doc_id,))
    conn.execute("DELETE FROM bot_kb_docs WHERE id = ?", (doc_id,))
    conn.commit()
    _bump_kb_version(conn)


def list_faqs(conn) -> list[dict]:
    rows = conn.execute("SELECT * FROM bot_faqs ORDER BY status, hits DESC, id DESC").fetchall()
    return [dict(r) for r in rows]


def save_faq(conn, data: dict, faq_id: int | None = None, actor: str = "") -> dict:
    question = (data.get("question") or "").strip()
    answer = (data.get("answer") or "").strip()
    if not question or not answer:
        raise ValueError("Cần câu hỏi và câu trả lời.")
    program = (data.get("program_code") or detect_program(question)).upper()
    status = data.get("status") if data.get("status") in ("active", "inactive") else "active"
    now = _now()
    cur = conn.cursor()
    if faq_id:
        cur.execute(
            "UPDATE bot_faqs SET question = ?, answer = ?, program_code = ?, status = ?, updated_at = ? WHERE id = ?",
            (question, answer, program, status, now, faq_id),
        )
        if cur.rowcount == 0:
            raise ValueError("Không tìm thấy FAQ.")
    else:
        cur.execute(
            "INSERT INTO bot_faqs (question, answer, program_code, status, created_by, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (question, answer, program, status, actor, now, now),
        )
        faq_id = cur.lastrowid
    conn.commit()
    _bump_kb_version(conn)
    return dict(conn.execute("SELECT * FROM bot_faqs WHERE id = ?", (faq_id,)).fetchone())


def delete_faq(conn, faq_id: int) -> None:
    conn.execute("UPDATE bot_gaps SET faq_id = NULL WHERE faq_id = ?", (faq_id,))
    conn.execute("DELETE FROM bot_faqs WHERE id = ?", (faq_id,))
    conn.commit()
    _bump_kb_version(conn)


def _fmt_date(value) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s.replace("T", " ")[:19])
    except ValueError:
        return s
    if len(s) > 10 and (dt.hour or dt.minute):
        return dt.strftime("%H:%M %d/%m/%Y")
    return dt.strftime("%d/%m/%Y")


def live_units(conn) -> list[dict]:
    units: list[dict] = []
    try:
        rounds = conn.execute(
            "SELECT code, name, programs, intake, opened_at, closed_at, exam_timeline, interview_timeline "
            "FROM admission_rounds WHERE status = 'open' ORDER BY COALESCE(closed_at, '9999')"
        ).fetchall()
    except Exception:
        rounds = []
    for r in rounds:
        parts = [f"Đợt tuyển sinh {r['name'] or r['code']} (mã {r['code']}) đang mở nhận hồ sơ"]
        if r["programs"]:
            parts.append(f"cho chương trình {r['programs']}")
        if r["intake"]:
            parts.append(f"khóa nhập học {r['intake']}")
        if r["opened_at"]:
            parts.append(f"mở từ {_fmt_date(r['opened_at'])}")
        if r["closed_at"]:
            parts.append(f"hạn nộp hồ sơ đến {_fmt_date(r['closed_at'])}")
        if r["exam_timeline"]:
            parts.append(f"lịch thi viết: {r['exam_timeline']}")
        if r["interview_timeline"]:
            parts.append(f"lịch phỏng vấn: {r['interview_timeline']}")
        units.append({
            "key": f"live-round-{r['code']}",
            "kind": "live",
            "ref_id": None,
            "title": "Dữ liệu tuyển sinh hiện hành",
            "text": "; ".join(parts) + ". Hạn chót nộp hồ sơ, thời hạn đăng ký và lịch xét tuyển theo đợt này.",
            "program": "",
        })
    try:
        from crm_ops import ACTIVITY_TYPES

        type_labels = {c: vi for c, vi, _en in ACTIVITY_TYPES}
        acts = conn.execute(
            "SELECT title, activity_type, starts_at, location, program_codes FROM crm_activities "
            "WHERE status = 'planned' AND (starts_at IS NULL OR starts_at = '' OR substr(starts_at, 1, 10) >= ?) "
            "ORDER BY starts_at LIMIT 8",
            (date.today().isoformat(),),
        ).fetchall()
    except Exception:
        acts = []
        type_labels = {}
    for a in acts:
        parts = [f"Sự kiện tư vấn sắp tới: {a['title']}"]
        if a["activity_type"]:
            parts.append(f"hình thức {type_labels.get(a['activity_type'], a['activity_type'])}")
        if a["starts_at"]:
            parts.append(f"thời gian {_fmt_date(a['starts_at'])}")
        if a["location"]:
            parts.append(f"địa điểm {a['location']}")
        if a["program_codes"]:
            parts.append(f"dành cho chương trình {a['program_codes']}")
        units.append({
            "key": f"live-act-{a['title']}-{a['starts_at']}",
            "kind": "live",
            "ref_id": None,
            "title": "Lịch sự kiện tuyển sinh",
            "text": "; ".join(parts) + ". Hội thảo, info day, buổi tư vấn trực tiếp.",
            "program": "",
        })
    return units


def public_overview(conn) -> dict:
    rounds, events = [], []
    try:
        for r in conn.execute(
            "SELECT code, name, programs, intake, opened_at, closed_at, exam_timeline, interview_timeline "
            "FROM admission_rounds WHERE status = 'open' ORDER BY COALESCE(closed_at, '9999')"
        ).fetchall():
            rounds.append({
                "code": r["code"],
                "name": r["name"] or r["code"],
                "programs": [p.strip() for p in (r["programs"] or "").split(",") if p.strip()],
                "intake": r["intake"] or "",
                "opened_at": _fmt_date(r["opened_at"]),
                "closed_at": _fmt_date(r["closed_at"]),
                "exam_timeline": r["exam_timeline"] or "",
                "interview_timeline": r["interview_timeline"] or "",
            })
    except Exception:
        rounds = []
    try:
        from crm_ops import ACTIVITY_TYPES

        labels = {c: vi for c, vi, _en in ACTIVITY_TYPES}
        for a in conn.execute(
            "SELECT id, title, activity_type, starts_at, location, program_codes FROM crm_activities "
            "WHERE status = 'planned' AND starts_at IS NOT NULL AND starts_at != '' AND substr(starts_at, 1, 10) >= ? "
            "ORDER BY starts_at LIMIT 6",
            (date.today().isoformat(),),
        ).fetchall():
            events.append({
                "id": a["id"],
                "title": a["title"],
                "type": labels.get(a["activity_type"], a["activity_type"] or ""),
                "starts_at": _fmt_date(a["starts_at"]),
                "location": a["location"] or "",
                "programs": [p.strip() for p in (a["program_codes"] or "").split(",") if p.strip()],
            })
    except Exception:
        events = []
    faqs = []
    try:
        faqs = [
            {"question": f["question"], "answer": f["answer"], "program": f["program_code"] or ""}
            for f in conn.execute(
                "SELECT question, answer, program_code FROM bot_faqs WHERE status = 'active' ORDER BY hits DESC, id LIMIT 6"
            ).fetchall()
        ]
    except Exception:
        faqs = []
    deadline_days = None
    for r in rounds:
        try:
            closes = datetime.strptime(r["closed_at"], "%d/%m/%Y").date()
        except (TypeError, ValueError):
            continue
        days = (closes - date.today()).days
        if days >= 0 and (deadline_days is None or days < deadline_days):
            deadline_days = days
    return {"rounds": rounds, "events": events, "faqs": faqs, "deadline_days": deadline_days}


class Bm25Index:
    def __init__(self, units: list[dict], k1: float = 1.4, b: float = 0.72):
        self.units = units
        self.k1 = k1
        self.b = b
        self.tf = [Counter(tokens(f"{u['title']} {u.get('search_text') or u['text']}")) for u in units]
        self.lens = [sum(c.values()) or 1 for c in self.tf]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 1.0
        df: Counter = Counter()
        for c in self.tf:
            df.update(c.keys())
        n = len(units)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.by_key = {u["key"]: i for i, u in enumerate(units)}

    def search(self, query: str, k: int = 8, program: str = "", live_focus: bool = False) -> list[dict]:
        q_terms = tokens(query)
        q_words = set(_words(query))
        if not q_terms or not self.units:
            return []
        q_counts = Counter(q_terms)
        results = []
        for i, tf in enumerate(self.tf):
            score = 0.0
            for term, qf in q_counts.items():
                f = tf.get(term)
                if not f:
                    continue
                idf = self.idf.get(term, 0.0)
                weight = 1.6 if "_" in term else 1.0
                score += weight * qf * idf * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg))
            if score <= 0:
                continue
            unit = self.units[i]
            if unit["kind"] == "faq":
                score *= 1.4 if _faq_match(unit.get("question") or "", query, self.idf) >= 0.4 else 0.6
            elif unit["kind"] == "live":
                score *= 1.6 if live_focus else 0.5
            if program and unit.get("program") and unit["program"] != program:
                score *= 0.55
            elif program and unit.get("program") == program:
                score *= 1.15
            q_set = set(q_terms)
            covered = sum(1 for t in q_set if tf.get(t))
            coverage = covered / len(q_set) if q_set else 0.0
            results.append({**unit, "score": round(score, 4), "coverage": round(coverage, 3)})
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:k]


def _load_units(conn) -> list[dict]:
    units = []
    rows = conn.execute(
        "SELECT c.id, c.doc_id, c.idx, c.text, d.title, d.program_code FROM bot_kb_chunks c "
        "JOIN bot_kb_docs d ON d.id = c.doc_id WHERE d.status = 'active' ORDER BY c.doc_id, c.idx"
    ).fetchall()
    for r in rows:
        units.append({
            "key": f"c{r['id']}",
            "kind": "doc",
            "ref_id": r["doc_id"],
            "chunk_idx": r["idx"],
            "title": r["title"],
            "text": r["text"],
            "program": (r["program_code"] or "").upper(),
        })
    for r in conn.execute("SELECT id, question, answer, program_code FROM bot_faqs WHERE status = 'active'").fetchall():
        units.append({
            "key": f"f{r['id']}",
            "kind": "faq",
            "ref_id": r["id"],
            "title": r["question"],
            "question": r["question"],
            "text": r["answer"],
            "search_text": f"{r['question']} {r['question']} {r['answer']}",
            "program": (r["program_code"] or "").upper(),
        })
    return units


def get_index(conn) -> Bm25Index:
    live = live_units(conn)
    key = (_kb_version(conn), tuple(u["text"] for u in live))
    with _index_lock:
        if _index_cache["key"] != key:
            _index_cache["index"] = Bm25Index(_load_units(conn) + live)
            _index_cache["key"] = key
        return _index_cache["index"]


def _vector_enabled() -> bool:
    flag = (os.environ.get("BOT_VECTOR") or "auto").lower()
    if flag in ("0", "false", "off", "no"):
        return False
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_BASE_URL")):
        return False
    return time.time() - _vector_state["failed_at"] > 300


def _vector_collection(reset: bool = False):
    from rag_service import get_chroma_client

    client = get_chroma_client()
    if reset:
        try:
            client.delete_collection("admission_kb")
        except Exception:
            pass
    return client.get_or_create_collection(name="admission_kb", metadata={"hnsw:space": "cosine"})


def sync_vectors(db_path: str) -> dict:
    if not _vector_enabled():
        return {"ok": False, "reason": "disabled"}
    import sqlite3

    from rag_service import _embed_chunks

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        units = _load_units(conn)
        conn.close()
        col = _vector_collection(reset=True)
        batch = 64
        for i in range(0, len(units), batch):
            part = units[i:i + batch]
            docs = [f"{u['title']}\n{u['text']}" for u in part]
            col.add(ids=[u["key"] for u in part], documents=docs, embeddings=_embed_chunks(docs))
        return {"ok": True, "count": len(units)}
    except Exception as e:
        _vector_state["failed_at"] = time.time()
        print(f"[BOT] vector sync failed: {e}")
        return {"ok": False, "reason": str(e)}


_DB_PATH_HOLDER = {"path": ""}


def _schedule_vector_sync() -> None:
    path = _DB_PATH_HOLDER["path"]
    if path and _vector_enabled():
        threading.Thread(target=sync_vectors, args=(path,), daemon=True).start()


def _vector_search(question: str, k: int = 8) -> list[str]:
    if not _vector_enabled():
        return []
    try:
        from rag_service import _embed_chunks

        col = _vector_collection()
        if col.count() == 0:
            return []
        res = col.query(query_embeddings=_embed_chunks([question]), n_results=min(k, col.count()))
        return list((res.get("ids") or [[]])[0])
    except Exception as e:
        _vector_state["failed_at"] = time.time()
        print(f"[BOT] vector search failed: {e}")
        return []


SYNONYMS = {
    "lien ket": ("hop tac", "doi tac"),
    "hop tac": ("lien ket",),
    "chi phi": ("hoc phi",),
    "tien hoc": ("hoc phi",),
    "dieu kien": ("yeu cau",),
    "yeu cau": ("dieu kien",),
    "giay to": ("ho so",),
    "nghi hoc": ("vang",),
    "vang mat": ("vang",),
    "thoi gian hoc": ("lich hoc",),
    "lich hoc": ("thoi gian hoc",),
    "mot nam": ("moi nam",),
    "su kien": ("info day", "hoi thao"),
    "du hoc": ("trao doi",),
    "bang cap": ("van bang",),
}


def query_variants(question: str) -> list[str]:
    folded = fold(question)
    variants = [question]
    for phrase, alternatives in SYNONYMS.items():
        if _has_phrase(folded, phrase):
            for alt in alternatives:
                variants.append(re.sub(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", alt, folded))
    return variants[:6]


def _lexical_search(index: "Bm25Index", question: str, program: str, live_focus: bool) -> list[dict]:
    best: dict[str, dict] = {}
    for variant in query_variants(question):
        for hit in index.search(variant, k=12, program=program, live_focus=live_focus):
            cur = best.get(hit["key"])
            if not cur or (hit["coverage"], hit["score"]) > (cur["coverage"], cur["score"]):
                best[hit["key"]] = hit
    return sorted(best.values(), key=lambda h: h["score"], reverse=True)[:12]


def retrieve(conn, question: str, program: str = "", k: int = 6, intents: list[str] | None = None) -> list[dict]:
    index = get_index(conn)
    live_focus = bool(set(intents if intents is not None else detect_intents(question)) & {"deadline", "event"})
    lexical = _lexical_search(index, question, program, live_focus)
    vector_keys = _vector_search(question, k=10)
    if not vector_keys:
        return lexical[:k]
    fused: dict[str, float] = defaultdict(float)
    for rank, r in enumerate(lexical):
        fused[r["key"]] += 1.0 / (60 + rank)
    for rank, key in enumerate(vector_keys):
        fused[key] += 1.0 / (60 + rank)
    lex_by_key = {r["key"]: r for r in lexical}
    out = []
    for key, score in sorted(fused.items(), key=lambda kv: kv[1], reverse=True):
        if key in lex_by_key:
            item = dict(lex_by_key[key])
        elif key in index.by_key:
            item = {**index.units[index.by_key[key]], "score": 0.0, "coverage": 0.45}
        else:
            continue
        item["fused"] = round(score, 5)
        out.append(item)
        if len(out) >= k:
            break
    return out


def _source_label(unit: dict) -> dict:
    if unit["kind"] == "faq":
        return {"kind": "faq", "title": "Câu hỏi thường gặp", "detail": unit.get("question") or unit["title"], "id": unit["ref_id"]}
    if unit["kind"] == "live":
        return {"kind": "live", "title": unit["title"], "detail": "", "id": None}
    return {"kind": "doc", "title": unit["title"], "detail": "", "id": unit["ref_id"]}


def _dedupe_sources(units: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for u in units:
        label = _source_label(u)
        key = (label["kind"], label["title"], label["detail"])
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
    return out


def _confidence(hits: list[dict], question: str) -> float:
    if not hits:
        return 0.0
    top = hits[0]
    base = top.get("coverage", 0.0)
    if top["kind"] == "faq":
        base = max(base, _faq_match(top.get("question") or "", question))
    return round(min(1.0, base), 3)


def _faq_match(faq_question: str, question: str, idf: dict | None = None) -> float:
    a = set(_words(faq_question))
    b = set(_words(question))
    if not a or not b:
        return 0.0
    if idf is None:
        index = _index_cache.get("index")
        idf = index.idf if index else {}
    ceiling = max(idf.values()) if idf else 1.0

    def weight(words):
        return sum(idf.get(w, ceiling) for w in words)

    common = weight(a & b)
    if common <= 0:
        return 0.0
    return (common / weight(b)) * math.sqrt(common / weight(a))


def _is_title_line(line: str) -> bool:
    return len(line) < 80 and not re.search(r"[.!?:;,]", line)


def _split_lines(text: str) -> list[str]:
    out: list[str] = []
    lines = (text or "").splitlines()
    first = lines[0].strip() if lines else ""
    for piece in SENT_SPLIT_RE.split(text or ""):
        piece = piece.strip(" -•*\t")
        if not piece or HEADING_RE.match(piece) or (piece == first and _is_title_line(piece)):
            continue
        if out and out[-1].endswith(":"):
            out[-1] = f"{out[-1]} {piece}"
        else:
            out.append(piece)
    return [s for s in out if len(s) > 12]


def _line_score(line: str, q_words: set[str], q_bigrams: set[str]) -> float:
    toks = tokens(line)
    words = {t for t in toks if "_" not in t}
    bigrams = {t for t in toks if "_" in t}
    return len(words & q_words) + 2.0 * len(bigrams & q_bigrams)


def answer_offline(question: str, hits: list[dict], intents: list[str]) -> dict:
    if not hits:
        return {"answered": False}
    q_toks = [t for variant in query_variants(question) for t in tokens(variant)]
    q_words = {t for t in q_toks if "_" not in t}
    q_bigrams = {t for t in q_toks if "_" in t}
    top = hits[0]
    if top["kind"] == "faq" and _faq_match(top.get("question") or "", question) >= 0.4:
        return {"answered": True, "text": top["text"], "used": [top], "mode": "faq"}
    live_focus = bool(set(intents) & {"deadline", "event"})
    if top.get("coverage", 0) < 0.5 and not (top["kind"] == "live" and live_focus):
        return {"answered": False}
    candidates = []
    for rank, unit in enumerate(hits[:4]):
        if unit is not top and unit.get("coverage", 0) < 0.34:
            continue
        if unit["kind"] == "faq" and _faq_match(unit.get("question") or "", question) < 0.4:
            continue
        if unit["kind"] == "live" and not live_focus:
            continue
        lines = [unit["text"].split(". Hạn chót")[0].split(". Hội thảo")[0]] if unit["kind"] == "live" else _split_lines(unit["text"])
        first_line = (unit["text"].splitlines() or [""])[0].strip()
        heading_bonus = 0.6 * _line_score(first_line, q_words, q_bigrams) if unit["kind"] == "doc" and _is_title_line(first_line) else 0.0
        for pos, line in enumerate(lines):
            score = _line_score(line, q_words, q_bigrams)
            if score > 0:
                score += heading_bonus
            if unit["kind"] == "live":
                score += 1.5
            if line.rstrip().endswith("?"):
                score *= 0.3
            if score > 0:
                candidates.append((score - 0.15 * rank, rank, pos, line, unit))
    if not candidates:
        return {"answered": False}
    candidates.sort(key=lambda c: c[0], reverse=True)
    best = candidates[0][0]
    picked, used, seen = [], [], set()
    for score, rank, pos, line, unit in candidates:
        if score < best * 0.8 or len(picked) >= 3:
            break
        if line in seen:
            continue
        seen.add(line)
        picked.append((rank, pos, line))
        if unit not in used:
            used.append(unit)
    picked.sort()
    if "fee" in intents and not any(re.search(r"\d", line) for _r, _p, line in picked):
        return {"answered": False}
    body = "\n".join(f"- {line}" for _r, _p, line in picked)
    return {"answered": True, "text": f"Theo thông tin tuyển sinh hiện có:\n{body}", "used": used, "mode": "extractive"}


def _llm_answer(settings: dict, question: str, hits: list[dict], history: list[dict], english: bool) -> dict:
    from rag_service import _get_client

    context_lines = []
    for i, unit in enumerate(hits, 1):
        label = "Câu hỏi thường gặp: " + (unit.get("question") or "") if unit["kind"] == "faq" else unit["title"]
        context_lines.append(f"[{i}] {label}\n{unit['text']}")
    context = "\n\n".join(context_lines) or "(không có tài liệu phù hợp)"
    system = (
        f"Bạn là {settings['bot.name']} của {settings['bot.org_name']}, tư vấn tuyển sinh các chương trình sau đại học.\n"
        "Quy tắc bắt buộc:\n"
        "1. Chỉ trả lời dựa trên TÀI LIỆU được cung cấp. Không dùng kiến thức bên ngoài, không suy đoán.\n"
        "2. Học phí, ngày tháng, điều kiện, con số phải chép đúng như trong tài liệu.\n"
        f"3. Nếu tài liệu không có thông tin để trả lời, chỉ trả về đúng chuỗi {NO_INFO_MARK}.\n"
        "4. Nếu chỉ trả lời được một phần, trả lời phần có và nói rõ phần nào chưa có thông tin.\n"
        "5. Ngắn gọn, thân thiện, tối đa khoảng 120 từ; dùng gạch đầu dòng khi liệt kê.\n"
        "6. Ghi nguồn bằng ký hiệu [1], [2] tương ứng tài liệu đã dùng.\n"
        "7. Không hỏi thông tin cá nhân của người dùng.\n"
        "8. Từ chối lịch sự các chủ đề ngoài tuyển sinh và chương trình đào tạo.\n"
        + ("9. Người dùng viết tiếng Anh: trả lời bằng tiếng Anh.\n" if english else "9. Trả lời bằng tiếng Việt.\n")
    )
    messages = [{"role": "system", "content": system}]
    for m in history[-6:]:
        role = "user" if m["role"] == "user" else "assistant"
        messages.append({"role": role, "content": m["content"][:800]})
    messages.append({"role": "user", "content": f"TÀI LIỆU:\n{context}\n\nCÂU HỎI: {question}"})
    resp = _get_client().chat.completions.create(
        model=os.environ.get("CHAT_MODEL", "qwen3:8b"),
        messages=messages,
        temperature=0.2,
        max_tokens=600,
    )
    text = THINK_RE.sub("", resp.choices[0].message.content or "").strip()
    if not text or NO_INFO_MARK in text:
        return {"answered": False}
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", text) if n.isdigit()}
    used = [hits[i - 1] for i in sorted(cited) if 1 <= i <= len(hits)] or hits[:2]
    return {"answered": True, "text": text, "used": used, "mode": "llm"}


def compute_lead(conv: dict, intents_all: list[str]) -> tuple[int, str]:
    score = sum(INTENT_WEIGHTS.get(i, 0) for i in set(intents_all))
    if conv.get("phone"):
        score += 25
    if conv.get("email"):
        score += 15
    if conv.get("program_interest"):
        score += 10
    if int(conv.get("user_turns") or 0) >= 3:
        score += 10
    score = min(score, 100)
    level = "hot" if score >= 70 else "high" if score >= 45 else "medium" if score >= 20 else "low"
    return score, level


def _summary(conv: dict, intents_all: list[str], last_question: str) -> str:
    parts = []
    if conv.get("program_interest"):
        parts.append(f"Quan tâm {conv['program_interest']}")
    asked = [INTENT_LABELS[i] for i in INTENT_LABELS if i in intents_all]
    if asked:
        parts.append("hỏi về " + ", ".join(asked))
    if last_question:
        parts.append(f"câu gần nhất: \"{last_question[:160]}\"")
    return "; ".join(parts) or "Trao đổi với chatbot tuyển sinh"


def get_conversation(conn, conv_id: int | None = None, session_key: str = "") -> dict | None:
    if conv_id:
        row = conn.execute("SELECT * FROM bot_conversations WHERE id = ?", (conv_id,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM bot_conversations WHERE session_key = ?", (session_key,)).fetchone()
    if not row:
        return None
    conv = dict(row)
    try:
        conv["intents"] = json.loads(conv.get("intents") or "[]")
    except ValueError:
        conv["intents"] = []
    return conv


def _ensure_conversation(conn, session_key: str, page_url: str = "", client_ip: str = "", channel: str = "web") -> dict:
    session_key = (session_key or "").strip()[:64] or uuid.uuid4().hex
    conv = get_conversation(conn, session_key=session_key)
    if conv:
        return conv
    now = _now()
    conn.execute(
        "INSERT INTO bot_conversations (session_key, channel, page_url, client_ip, created_at, last_message_at) VALUES (?,?,?,?,?,?)",
        (session_key, channel, page_url[:300], client_ip[:64], now, now),
    )
    conn.commit()
    return get_conversation(conn, session_key=session_key)


def _add_message(conn, conv_id: int, role: str, content: str, **extra) -> int:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO bot_messages (conversation_id, role, content, sources, confidence, answered, mode, author, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            conv_id,
            role,
            content,
            json.dumps(extra.get("sources") or [], ensure_ascii=False),
            extra.get("confidence"),
            extra.get("answered"),
            extra.get("mode"),
            extra.get("author"),
            _now(),
        ),
    )
    conn.execute("UPDATE bot_conversations SET last_message_at = ? WHERE id = ?", (_now(), conv_id))
    conn.commit()
    return cur.lastrowid


def _update_conv(conn, conv_id: int, fields: dict) -> None:
    if not fields:
        return
    if "intents" in fields and not isinstance(fields["intents"], str):
        fields = {**fields, "intents": json.dumps(fields["intents"])}
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE bot_conversations SET {sets} WHERE id = ?", [*fields.values(), conv_id])
    conn.commit()


def _history(conn, conv_id: int, limit: int = 8) -> list[dict]:
    rows = conn.execute(
        "SELECT role, content FROM bot_messages WHERE conversation_id = ? AND role IN ('user','bot','staff') ORDER BY id DESC LIMIT ?",
        (conv_id, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def sync_lead(conn, conv: dict, force: bool = False) -> dict:
    from crm_ops import _find_profile, add_reminder, ensure_crm_tables, log_daily_update, upsert_source_profile

    out = {"profile_id": conv.get("profile_id"), "created": False, "reminder": False}
    if not (conv.get("phone") or conv.get("email")):
        return out
    cur = conn.cursor()
    ensure_crm_tables(cur)
    level = conv.get("lead_level") or "low"
    crm_level = level if level in LEVEL_RANK else "medium"
    if crm_level == "low":
        crm_level = "medium" if force else "low"
    name = (conv.get("visitor_name") or "").strip() or f"Khách chatbot {conv.get('phone') or conv.get('email')}"
    pid = conv.get("profile_id") or _find_profile(cur, email=conv.get("email") or "", phone=conv.get("phone") or "")
    today = date.today().isoformat()
    data = {
        "full_name": name,
        "phone": conv.get("phone") or "",
        "email": conv.get("email") or "",
        "latest_contact_at": today,
        "channel": "Chatbot website",
    }
    if conv.get("program_interest"):
        data["program_interest"] = conv["program_interest"]
    if pid:
        existing = conn.execute("SELECT interest_level, full_name FROM crm_source_profiles WHERE id = ?", (pid,)).fetchone()
        data["id"] = pid
        if existing:
            if not conv.get("visitor_name"):
                data["full_name"] = existing["full_name"]
            if LEVEL_RANK.get(crm_level, 0) > LEVEL_RANK.get(existing["interest_level"] or "medium", 1):
                data["interest_level"] = crm_level
    else:
        data.update({
            "source": "chatbot",
            "source_ref": f"bot:{conv['id']}",
            "source_1": "Chatbot",
            "enquiry_date": today,
            "care_status": "interested" if LEVEL_RANK.get(level, 0) >= 2 else "potential",
            "interest_level": crm_level if crm_level in LEVEL_RANK else "medium",
        })
    row = upsert_source_profile(conn, data)
    new_pid = row.get("id")
    created = not conv.get("profile_id")
    if created and new_pid:
        _update_conv(conn, conv["id"], {"profile_id": new_pid})
        try:
            log_daily_update(
                conn,
                new_pid,
                {"note": f"Chatbot: {conv.get('summary') or 'khách để lại liên hệ'}", "channel": "chatbot"},
                actor="chatbot",
            )
        except Exception as e:
            print(f"[BOT] care log failed: {e}")
    out.update({"profile_id": new_pid, "created": created and row.get("action") == "created", "linked": created})
    need_level = "hot" if (level == "hot" or conv.get("needs_human")) else ("high" if level == "high" else "")
    if need_level and LEVEL_RANK.get(need_level, 0) > LEVEL_RANK.get(conv.get("reminder_level") or "", -1) and new_pid:
        when = datetime.now() + timedelta(hours=1)
        if need_level == "high":
            when = (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        title = "Chatbot: khách cần gọi lại ngay" if need_level == "hot" else "Chatbot: khách quan tâm cao"
        body = conv.get("summary") or ""
        if conv.get("needs_human"):
            body = f"Khách yêu cầu gặp tư vấn viên. {body}"
        add_reminder(conn, {
            "profile_id": new_pid,
            "remind_at": when.strftime("%Y-%m-%d %H:%M:%S"),
            "channel": "phone" if conv.get("phone") else "email",
            "title": title,
            "body": body,
        })
        _update_conv(conn, conv["id"], {"reminder_level": need_level})
        out["reminder"] = True
    return out


def _contact_prompt(settings: dict, english: bool) -> str:
    if english:
        return "For a personal study plan, tuition details and scholarship options, register for a free consultation and an admissions advisor will contact you."
    return "Để được chuyên viên tư vấn riêng về lộ trình học, học phí và học bổng, bạn đăng ký nhận tư vấn ngay trong khung chat nhé. Chuyên viên tuyển sinh sẽ liên hệ trực tiếp với bạn."


def _fallback_text(settings: dict, english: bool, has_contact: bool, intents: list[str] | None = None) -> str:
    hotline = settings.get("bot.hotline") or ""
    mail = settings.get("bot.contact_email") or ""
    intents = intents or []
    if english:
        text = "That needs an admissions advisor to answer accurately, so I've passed your question on."
    elif "fee" in intents or "scholarship" in intents:
        text = "Học phí và chính sách học bổng được chuyên viên tuyển sinh tư vấn riêng theo từng chương trình và hồ sơ của bạn, nên mình không đưa con số chung để tránh sai lệch. Mình đã chuyển câu hỏi cho chuyên viên."
    else:
        text = "Câu này cần chuyên viên tuyển sinh tư vấn trực tiếp để chính xác, nên mình đã chuyển câu hỏi cho chuyên viên."
    contact_bits = [b for b in (f"hotline {hotline}" if hotline else "", f"email {mail}" if mail else "") if b]
    if contact_bits:
        text += (" You can also reach us via " if english else " Bạn cũng có thể liên hệ ") + " hoặc ".join(contact_bits) + "."
    if not has_contact:
        text += " " + (
            "Register for a consultation below and an advisor will get back to you."
            if english
            else "Bạn đăng ký nhận tư vấn ở form bên dưới, chuyên viên sẽ liên hệ lại với bạn."
        )
    return text


def generate_reply(conn, question: str, *, program: str = "", intents: list[str] | None = None, history: list[dict] | None = None, settings: dict | None = None) -> dict:
    settings = settings or get_settings(conn)
    intents = intents if intents is not None else detect_intents(question)
    english = is_english(question)
    hits = retrieve(conn, question, program=program, k=6, intents=intents)
    top_cov = hits[0]["coverage"] if hits else 0.0
    live_relevant = any(h["kind"] == "live" for h in hits) and bool(set(intents) & {"deadline", "event"})
    top_faq = hits[0] if hits and hits[0]["kind"] == "faq" else None
    if top_faq and _faq_match(top_faq.get("question") or "", question) >= 0.6:
        result = {"answered": True, "text": top_faq["text"], "used": [top_faq], "mode": "faq"}
    elif hits and (top_cov >= 0.25 or live_relevant or top_faq):
        result = None
        if llm_status(conn)["enabled"]:
            try:
                result = _llm_answer(settings, question, hits, history or [], english)
            except Exception as e:
                print(f"[BOT] LLM error, using extractive mode: {e}")
                result = None
        if result is None:
            result = answer_offline(question, hits, intents)
    else:
        result = {"answered": False}
    result["hits"] = hits
    result["confidence"] = _confidence(hits, question) if result.get("answered") else round(top_cov, 3)
    return result


def handle_message(conn, *, session_key: str, text: str, page_url: str = "", client_ip: str = "", channel: str = "web") -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Tin nhắn trống.")
    text = text[:1000]
    settings = get_settings(conn)
    conv = _ensure_conversation(conn, session_key, page_url, client_ip, channel)
    english = is_english(text)
    user_msg_id = _add_message(conn, conv["id"], "user", text)
    contact = extract_contact(text)
    program = detect_program(text)
    intents = detect_intents(text)
    folded = fold(text).strip(" !.?")
    intents_all = sorted(set(conv["intents"]) | set(intents))
    fields: dict = {"user_turns": int(conv.get("user_turns") or 0) + 1, "intents": intents_all}
    if contact.get("phone"):
        fields["phone"] = contact["phone"]
    if contact.get("email"):
        fields["email"] = contact["email"]
    if contact.get("name"):
        fields["visitor_name"] = contact["name"]
    if program:
        fields["program_interest"] = program
    conv.update(fields)
    conv["intents"] = intents_all
    if conv.get("status") == "human":
        _update_conv(conn, conv["id"], fields)
        return {"session": conv["session_key"], "reply": None, "status": "human", "message_id": user_msg_id}

    only_contact = bool(contact) and len(_words(EMAIL_RE.sub("", PHONE_RE.sub("", text)))) <= 6 and not intents
    is_greeting = folded in GREETING_WORDS or (
        len(folded) <= 24 and not intents and any(re.match(rf"{re.escape(g)}(?![a-z0-9])", folded) for g in GREETING_WORDS)
    )
    is_thanks = any(_has_phrase(folded, t) for t in THANKS_WORDS) and len(folded) <= 40 and not intents
    reply, sources, mode, answered, confidence = "", [], "", None, None
    needs_human = int(conv.get("needs_human") or 0)
    status = conv.get("status") or "open"

    if "human" in intents:
        needs_human, status = 1, "handoff"
        mode, answered = "handoff", None
        reply = (
            "I've notified our admissions team; an advisor will contact you shortly."
            if english
            else "Mình đã báo chuyên viên tuyển sinh, bạn sẽ được liên hệ sớm."
        )
        hotline = settings.get("bot.hotline")
        if hotline:
            reply += f" Hotline: {hotline}."
    elif only_contact:
        mode = "contact"
        name = conv.get("visitor_name") or ""
        reply = (
            f"Thanks{(' ' + name) if name else ''}! An advisor will reach out to you soon. Anything else I can help with?"
            if english
            else f"Cảm ơn {name or 'bạn'}! Mình đã ghi nhận thông tin, chuyên viên tuyển sinh sẽ liên hệ sớm. Bạn còn câu hỏi nào khác không?"
        )
    elif is_greeting:
        mode = "greeting"
        reply = settings["bot.greeting"]
    elif is_thanks:
        mode = "smalltalk"
        reply = "You're welcome! Feel free to ask anything else." if english else "Rất vui được hỗ trợ bạn! Bạn cần hỏi thêm gì cứ nhắn mình nhé."
    else:
        result = generate_reply(
            conn,
            text,
            program=conv.get("program_interest") or "",
            intents=intents,
            history=_history(conn, conv["id"])[:-1],
            settings=settings,
        )
        confidence = result.get("confidence")
        if result.get("answered"):
            answered, mode = 1, result["mode"]
            reply = result["text"]
            sources = _dedupe_sources(result.get("used") or [])
            for unit in result.get("used") or []:
                if unit["kind"] == "faq":
                    conn.execute("UPDATE bot_faqs SET hits = hits + 1 WHERE id = ?", (unit["ref_id"],))
            conn.commit()
        else:
            answered, mode = 0, "fallback"
            needs_human = 1
            reply = _fallback_text(settings, english, bool(conv.get("phone") or conv.get("email")), intents)

    ask_contact = False
    has_contact = bool(conv.get("phone") or conv.get("email"))
    threshold = int(settings.get("bot.ask_contact_after") or 2)
    if not has_contact and not conv.get("contact_asked") and mode not in ("greeting", "smalltalk", "fallback") and (
        fields["user_turns"] >= threshold or "human" in intents or set(intents) & {"fee", "deadline", "documents"}
    ):
        reply = f"{reply}\n\n{_contact_prompt(settings, english)}"
        fields["contact_asked"] = 1
        ask_contact = True
    elif not has_contact and mode in ("fallback", "handoff"):
        ask_contact = True

    conv["summary"] = _summary(conv, intents_all, text)
    score, level = compute_lead(conv, intents_all)
    fields.update({
        "lead_score": score,
        "lead_level": level,
        "needs_human": needs_human,
        "status": status,
        "summary": conv["summary"],
    })
    conv.update(fields)
    conv["intents"] = intents_all
    _update_conv(conn, conv["id"], fields)
    bot_msg_id = _add_message(
        conn, conv["id"], "bot", reply, sources=sources, confidence=confidence, answered=answered, mode=mode
    )
    if mode == "fallback":
        conn.execute(
            "INSERT INTO bot_gaps (conversation_id, message_id, question, status, created_at) VALUES (?,?,?,?,?)",
            (conv["id"], user_msg_id, text, "open", _now()),
        )
        conn.commit()
    crm = {}
    if has_contact:
        try:
            fresh = get_conversation(conn, conv["id"])
            if (contact or "human" in intents) and not _open_request(conn, fresh.get("phone") or "", fresh.get("email") or ""):
                created = create_request(
                    conn,
                    {
                        "full_name": fresh.get("visitor_name") or "",
                        "phone": fresh.get("phone") or "",
                        "email": fresh.get("email") or "",
                        "program": fresh.get("program_interest") or "",
                    },
                    source="chatbot",
                    session_key=fresh["session_key"],
                    require_consent=False,
                    announce=False,
                )
                crm = {"profile_id": created.get("profile_id")}
            else:
                crm = sync_lead(conn, fresh)
        except Exception as e:
            print(f"[BOT] CRM sync failed: {e}")
    return {
        "session": conv["session_key"],
        "message_id": bot_msg_id,
        "reply": reply,
        "sources": sources,
        "mode": mode,
        "ask_contact": ask_contact,
        "status": status,
        "lead_level": level,
        "crm_linked": bool(crm.get("profile_id")),
    }


def _validated_contact(data: dict, require_consent: bool) -> tuple[str, str, str]:
    name = re.sub(r"\s+", " ", (data.get("full_name") or data.get("name") or "")).strip()[:120]
    phone_raw = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip().lower()[:160]
    phone = ""
    if phone_raw:
        found = extract_contact(phone_raw).get("phone")
        if not found:
            raise ValueError("Số điện thoại chưa đúng định dạng (10 số, bắt đầu bằng 0).")
        phone = found
    if email and not EMAIL_RE.fullmatch(email):
        raise ValueError("Email chưa đúng định dạng.")
    if not (phone or email):
        raise ValueError("Vui lòng nhập số điện thoại hoặc email để chuyên viên liên hệ.")
    if require_consent and not name:
        raise ValueError("Vui lòng nhập họ tên.")
    if require_consent and not data.get("consent"):
        raise ValueError("Vui lòng đồng ý để trung tâm liên hệ tư vấn.")
    return name or f"Khách {phone or email}", phone, email


def _open_request(conn, phone: str, email: str):
    if not (phone or email):
        return None
    since = (datetime.now() - timedelta(days=30)).isoformat(sep=" ", timespec="seconds")
    clauses, params = [], []
    if phone:
        clauses.append("phone = ?")
        params.append(phone)
    if email:
        clauses.append("lower(email) = ?")
        params.append(email.lower())
    row = conn.execute(
        f"SELECT * FROM consult_requests WHERE ({' OR '.join(clauses)}) AND status IN ('new','contacted','caring') "
        "AND created_at >= ? ORDER BY id DESC LIMIT 1",
        [*params, since],
    ).fetchone()
    return dict(row) if row else None


def _consultants(conn) -> list[dict]:
    try:
        rows = conn.execute(
            "SELECT DISTINCT u.id, u.email AS login, u.name FROM user u "
            "JOIN user_departments ud ON ud.user_id = u.id "
            "JOIN departments d ON d.id = ud.department_id "
            "WHERE d.code = 'tuyen_sinh' AND IFNULL(u.is_locked, 0) = 0 ORDER BY u.id"
        ).fetchall()
    except Exception:
        return []
    return [{"id": r["id"], "login": r["login"], "name": (r["name"] or r["login"]).split(" — ")[0]} for r in rows]


def _pick_consultant(conn) -> dict | None:
    people = _consultants(conn)
    if not people:
        return None
    load = {
        r[0]: r[1]
        for r in conn.execute(
            "SELECT assigned_user_id, COUNT(*) FROM consult_requests WHERE status IN ('new','contacted','caring') GROUP BY assigned_user_id"
        ).fetchall()
    }
    return min(people, key=lambda p: (load.get(p["id"], 0), p["id"]))


def _sla_due(now: datetime) -> datetime:
    def next_workday(day: datetime) -> datetime:
        day = day + timedelta(days=1)
        while day.weekday() >= 5:
            day += timedelta(days=1)
        return day.replace(hour=10, minute=0, second=0, microsecond=0)

    if now.weekday() < 5 and 8 <= now.hour < 15:
        return (now + timedelta(hours=2)).replace(second=0, microsecond=0)
    if now.weekday() < 5 and now.hour < 8:
        return now.replace(hour=10, minute=0, second=0, microsecond=0)
    return next_workday(now)


def create_request(
    conn,
    data: dict,
    *,
    source: str = "website",
    session_key: str = "",
    client_ip: str = "",
    require_consent: bool = True,
    announce: bool = True,
) -> dict:
    from crm_ops import _find_profile, add_reminder, ensure_crm_tables, log_daily_update, upsert_source_profile

    ensure_bot_tables(conn.cursor())
    ensure_crm_tables(conn.cursor())
    name, phone, email = _validated_contact(data, require_consent)
    program = (data.get("program") or "").strip().upper()
    program = program if program in PROGRAM_KEYWORDS else ""
    company = (data.get("company") or "").strip()[:160]
    job_title = (data.get("job_title") or "").strip()[:120]
    intake = (data.get("intake") or "").strip()[:60]
    contact_time = data.get("contact_time") if data.get("contact_time") in CONTACT_TIMES else "office"
    message = (data.get("message") or "").strip()[:1000]
    event = None
    if str(data.get("event_id") or "").isdigit():
        event = conn.execute("SELECT id, title, starts_at FROM crm_activities WHERE id = ?", (int(data["event_id"]),)).fetchone()
    if event:
        source = "event"
    if source not in REQUEST_SOURCES:
        source = "website"

    conv = get_conversation(conn, session_key=session_key) if session_key else None
    if conv:
        fields = {"visitor_name": name, "contact_asked": 1, "needs_human": 1, "status": "handoff"}
        if phone:
            fields["phone"] = phone
        if email:
            fields["email"] = email
        if program:
            fields["program_interest"] = program
        conv.update(fields)
        conv["summary"] = _summary(conv, conv["intents"], "")
        score, level = compute_lead(conv, sorted(set(conv["intents"]) | {"human"}))
        fields.update({"lead_score": score, "lead_level": level, "summary": conv["summary"]})
        _update_conv(conn, conv["id"], fields)
        conv.update(fields)
    else:
        score, level = compute_lead({"phone": phone, "email": email, "program_interest": program, "user_turns": 0}, ["human"])

    existing = _open_request(conn, phone, email)
    consultant = None
    if existing and existing.get("assigned_user_id"):
        consultant = {"id": existing["assigned_user_id"], "login": existing["assigned_login"], "name": existing["assigned_name"]}
    else:
        consultant = _pick_consultant(conn)
    now = datetime.now()
    due = _sla_due(now)
    today = date.today().isoformat()
    cur = conn.cursor()
    pid = (existing or {}).get("profile_id") or (conv or {}).get("profile_id") or _find_profile(cur, email=email, phone=phone)
    crm_level = "hot" if level == "hot" else "high"
    crm = {
        "full_name": name,
        "phone": phone,
        "email": email,
        "latest_contact_at": today,
        "channel": "Chatbot website" if source == "chatbot" else "Website",
    }
    if program:
        crm["program_interest"] = program
    if company:
        crm["company"] = company
    if job_title:
        crm["occupation"] = job_title
    if intake:
        crm["intake"] = intake
    if event:
        crm["join_event"] = event["title"]
    if pid:
        prev = conn.execute("SELECT full_name, interest_level, pic FROM crm_source_profiles WHERE id = ?", (pid,)).fetchone()
        crm["id"] = pid
        if prev:
            if require_consent is False and not data.get("full_name"):
                crm["full_name"] = prev["full_name"]
            if LEVEL_RANK.get(crm_level, 0) > LEVEL_RANK.get(prev["interest_level"] or "medium", 1):
                crm["interest_level"] = crm_level
            if not (prev["pic"] or "").strip() and consultant:
                crm["pic"] = consultant["login"]
    else:
        crm.update({
            "source": "chatbot" if source == "chatbot" else "website",
            "source_ref": f"bot:{conv['id']}" if conv else "landing",
            "source_1": "Chatbot" if source == "chatbot" else "Website",
            "enquiry_date": today,
            "care_status": "potential",
            "person_status": "prospect",
            "prospect_level": "hot" if level == "hot" else "warm",
            "interest_level": crm_level,
        })
        if consultant:
            crm["pic"] = consultant["login"]
    profile = upsert_source_profile(conn, crm)
    pid = profile.get("id")

    if event and pid:
        conn.execute(
            "INSERT OR IGNORE INTO crm_activity_participants (activity_id, profile_id, interest_level, care_note) VALUES (?,?,?,?)",
            (event["id"], pid, crm_level, "Đăng ký tham dự qua trang giới thiệu"),
        )
        conn.commit()

    stamp = _now()
    if existing:
        req_id = existing["id"]
        merged = "\n".join(x for x in (existing.get("message") or "", message) if x)
        conn.execute(
            "UPDATE consult_requests SET profile_id = ?, conversation_id = COALESCE(?, conversation_id), program = COALESCE(NULLIF(?, ''), program), "
            "company = COALESCE(NULLIF(?, ''), company), job_title = COALESCE(NULLIF(?, ''), job_title), intake = COALESCE(NULLIF(?, ''), intake), "
            "contact_time = ?, event_id = COALESCE(?, event_id), message = ?, updated_at = ? WHERE id = ?",
            (pid, conv["id"] if conv else None, program, company, job_title, intake, contact_time, event["id"] if event else None, merged, stamp, req_id),
        )
    else:
        cur.execute(
            "INSERT INTO consult_requests (profile_id, conversation_id, source, full_name, phone, email, program, company, job_title, intake, "
            "contact_time, event_id, message, status, assigned_user_id, assigned_login, assigned_name, sla_due_at, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'new',?,?,?,?,?,?)",
            (
                pid, conv["id"] if conv else None, source, name, phone, email, program, company, job_title, intake,
                contact_time, event["id"] if event else None, message,
                consultant["id"] if consultant else None, consultant["login"] if consultant else None,
                consultant["name"] if consultant else None, due.isoformat(sep=" ", timespec="minutes"), stamp, stamp,
            ),
        )
        req_id = cur.lastrowid
    conn.commit()

    parts = [f"{REQUEST_SOURCES[source]}: đăng ký nhận tư vấn"]
    if program:
        parts.append(f"chương trình {program}")
    parts.append(f"muốn được liên hệ {CONTACT_TIMES[contact_time]}")
    if event:
        parts.append(f"đăng ký sự kiện {event['title']}")
    if message:
        parts.append(f"lời nhắn: {message[:200]}")
    if conv and conv.get("intents"):
        parts.append("đã hỏi UniBot về " + ", ".join(INTENT_LABELS[i] for i in INTENT_LABELS if i in conv["intents"] and i != "human"))
    note = "; ".join(p for p in parts if p and not p.endswith("về ")) + "."
    if pid:
        try:
            log_daily_update(
                conn,
                pid,
                {"note": note, "channel": crm["channel"], "follow_up_date": due.date().isoformat(), **({"pic": consultant["login"]} if consultant and not existing else {})},
                actor="website",
            )
        except Exception as e:
            print(f"[BOT] care log failed: {e}")
        if not existing:
            add_reminder(conn, {
                "profile_id": pid,
                "remind_at": due.strftime("%Y-%m-%d %H:%M:%S"),
                "channel": "phone" if phone else "email",
                "title": f"Yêu cầu tư vấn mới: {name}" + (f" ({consultant['name']})" if consultant else ""),
                "body": note,
            })

    if conv:
        _update_conv(conn, conv["id"], {"profile_id": pid, "reminder_level": "hot"})
        handler = consultant["name"] if consultant else "bộ phận tuyển sinh"
        _add_message(conn, conv["id"], "system", f"Khách đăng ký nhận tư vấn, đã chuyển cho chuyên viên {handler}.", mode="request")

    when = CONTACT_TIMES[contact_time]
    reach = phone or email
    reply = (
        f"Cảm ơn {name}! Yêu cầu tư vấn của bạn đã được chuyển tới chuyên viên tuyển sinh. "
        f"Chuyên viên sẽ liên hệ qua {reach} {when} để tư vấn riêng về lộ trình học, học phí và học bổng. "
        "Trong lúc chờ, bạn vẫn có thể hỏi mình các thông tin chung về chương trình."
    )
    if conv and announce:
        _add_message(conn, conv["id"], "bot", reply, mode="request")
    return {
        "ok": True,
        "request_id": req_id,
        "profile_id": pid,
        "reply": reply,
        "assigned": bool(consultant),
        "session": conv["session_key"] if conv else "",
        "duplicate": bool(existing),
    }


def submit_contact(conn, *, session_key: str, data: dict, client_ip: str = "") -> dict:
    session_key = (session_key or "").strip()[:64]
    if session_key:
        _ensure_conversation(conn, session_key, client_ip=client_ip)
    return create_request(conn, data, source="chatbot", session_key=session_key, client_ip=client_ip)


def list_requests(conn, *, status: str = "", assignee: int | None = None, q: str = "", overdue: bool = False, req_id: int | None = None) -> list[dict]:
    sql = (
        "SELECT r.*, a.title AS event_title, c.lead_level, c.lead_score, "
        "(SELECT COUNT(*) FROM bot_messages m WHERE m.conversation_id = r.conversation_id AND m.role = 'user') AS bot_questions, "
        "p.care_status FROM consult_requests r "
        "LEFT JOIN crm_activities a ON a.id = r.event_id "
        "LEFT JOIN bot_conversations c ON c.id = r.conversation_id "
        "LEFT JOIN crm_source_profiles p ON p.id = r.profile_id WHERE 1 = 1"
    )
    params: list = []
    if req_id:
        sql += " AND r.id = ?"
        params.append(req_id)
    if status == "open":
        sql += " AND r.status IN ('new','contacted','caring')"
    elif status:
        sql += " AND r.status = ?"
        params.append(status)
    if assignee:
        sql += " AND r.assigned_user_id = ?"
        params.append(assignee)
    if overdue:
        sql += " AND r.status = 'new' AND r.sla_due_at < ?"
        params.append(datetime.now().isoformat(sep=" ", timespec="minutes"))
    if q:
        like = f"%{q.strip()}%"
        sql += " AND (r.full_name LIKE ? OR r.phone LIKE ? OR r.email LIKE ? OR r.company LIKE ?)"
        params += [like, like, like, like]
    sql += " ORDER BY CASE r.status WHEN 'new' THEN 0 WHEN 'contacted' THEN 1 WHEN 'caring' THEN 2 ELSE 3 END, r.sla_due_at, r.id DESC LIMIT 300"
    now = datetime.now().isoformat(sep=" ", timespec="minutes")
    out = []
    for r in conn.execute(sql, params).fetchall():
        item = dict(r)
        item["status_label"] = REQUEST_STATUSES.get(item["status"], item["status"])
        item["source_label"] = REQUEST_SOURCES.get(item["source"], item["source"])
        item["contact_time_label"] = CONTACT_TIMES.get(item["contact_time"] or "office", "")
        item["overdue"] = item["status"] == "new" and bool(item["sla_due_at"]) and item["sla_due_at"] < now
        out.append(item)
    return out


def request_detail(conn, req_id: int) -> dict | None:
    rows = list_requests(conn, req_id=req_id)
    if not rows:
        return None
    item = rows[0]
    item["messages"] = []
    if item.get("conversation_id"):
        item["messages"] = [
            dict(m)
            for m in conn.execute(
                "SELECT role, content, mode, created_at FROM bot_messages WHERE conversation_id = ? ORDER BY id",
                (item["conversation_id"],),
            ).fetchall()
        ]
    item["care_log"] = []
    item["profile"] = None
    if item.get("profile_id"):
        try:
            from crm_ops import get_source_profile, list_care_log

            item["profile"] = get_source_profile(conn, item["profile_id"])
            item["care_log"] = list_care_log(conn, item["profile_id"])
        except Exception:
            pass
    item["consultants"] = _consultants(conn)
    return item


def update_request(conn, req_id: int, data: dict, actor: dict) -> dict:
    from crm_ops import log_daily_update, upsert_source_profile

    row = conn.execute("SELECT * FROM consult_requests WHERE id = ?", (req_id,)).fetchone()
    if not row:
        raise ValueError("Không tìm thấy yêu cầu tư vấn.")
    req = dict(row)
    fields: dict = {"updated_at": _now()}
    if data.get("claim"):
        fields.update({"assigned_user_id": actor.get("user_id"), "assigned_login": actor.get("login"), "assigned_name": actor.get("name")})
    if data.get("assign_to"):
        person = next((p for p in _consultants(conn) if str(p["id"]) == str(data["assign_to"])), None)
        if not person:
            raise ValueError("Không tìm thấy chuyên viên.")
        fields.update({"assigned_user_id": person["id"], "assigned_login": person["login"], "assigned_name": person["name"]})
    status = data.get("status") or ""
    if status:
        if status not in REQUEST_STATUSES:
            raise ValueError("Trạng thái không hợp lệ.")
        fields["status"] = status
        if status != "new" and not req.get("first_contact_at"):
            fields["first_contact_at"] = _now()
    note = (data.get("note") or "").strip()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE consult_requests SET {sets} WHERE id = ?", [*fields.values(), req_id])
    conn.commit()
    pid = req.get("profile_id")
    login = actor.get("login") or "staff"
    if pid:
        if "assigned_login" in fields:
            prof = conn.execute("SELECT full_name FROM crm_source_profiles WHERE id = ?", (pid,)).fetchone()
            if prof:
                upsert_source_profile(conn, {"id": pid, "full_name": prof["full_name"], "pic": fields["assigned_login"]})
        care = STATUS_TO_CARE.get(status)
        if note or care:
            label = REQUEST_STATUSES.get(status, "")
            text = note or f"Cập nhật yêu cầu tư vấn: {label}"
            payload = {"note": text, "channel": data.get("channel") or "phone"}
            if care:
                payload["care_status"] = care
            if data.get("follow_up_date"):
                payload["follow_up_date"] = data["follow_up_date"]
            log_daily_update(conn, pid, payload, actor=login)
    if req.get("conversation_id") and status in ("contacted", "caring", "converted", "closed"):
        _update_conv(conn, req["conversation_id"], {"needs_human": 0})
    return request_detail(conn, req_id)


def poll_messages(conn, session_key: str, after_id: int = 0) -> dict:
    conv = get_conversation(conn, session_key=session_key)
    if not conv:
        return {"messages": [], "status": "new"}
    rows = conn.execute(
        "SELECT id, role, content, created_at FROM bot_messages WHERE conversation_id = ? AND id > ? AND role IN ('user','bot','staff') ORDER BY id",
        (conv["id"], after_id),
    ).fetchall()
    return {"messages": [dict(r) for r in rows], "status": conv["status"]}


def list_conversations(conn, *, q: str = "", status: str = "", level: str = "", needs_human: str = "", limit: int = 200) -> list[dict]:
    sql = (
        "SELECT c.*, (SELECT COUNT(*) FROM bot_messages m WHERE m.conversation_id = c.id AND m.role = 'user') AS user_messages, "
        "(SELECT content FROM bot_messages m WHERE m.conversation_id = c.id AND m.role = 'user' ORDER BY m.id DESC LIMIT 1) AS last_question "
        "FROM bot_conversations c WHERE c.channel != 'test'"
    )
    params: list = []
    if status:
        sql += " AND c.status = ?"
        params.append(status)
    if level:
        sql += " AND c.lead_level = ?"
        params.append(level)
    if needs_human in ("1", "true"):
        sql += " AND c.needs_human = 1 AND c.status != 'closed'"
    if q:
        like = f"%{q.strip()}%"
        sql += " AND (c.visitor_name LIKE ? OR c.phone LIKE ? OR c.email LIKE ? OR c.summary LIKE ?)"
        params += [like, like, like, like]
    sql += " ORDER BY c.last_message_at DESC LIMIT ?"
    params.append(limit)
    out = []
    for r in conn.execute(sql, params).fetchall():
        item = dict(r)
        try:
            item["intents"] = json.loads(item.get("intents") or "[]")
        except ValueError:
            item["intents"] = []
        item["intent_labels"] = [INTENT_LABELS.get(i, i) for i in item["intents"]]
        out.append(item)
    return out


def conversation_detail(conn, conv_id: int) -> dict | None:
    conv = get_conversation(conn, conv_id)
    if not conv:
        return None
    rows = conn.execute(
        "SELECT id, role, content, sources, confidence, answered, mode, author, created_at FROM bot_messages WHERE conversation_id = ? ORDER BY id",
        (conv_id,),
    ).fetchall()
    msgs = []
    for r in rows:
        m = dict(r)
        try:
            m["sources"] = json.loads(m.get("sources") or "[]")
        except ValueError:
            m["sources"] = []
        msgs.append(m)
    conv["messages"] = msgs
    conv["intent_labels"] = [INTENT_LABELS.get(i, i) for i in conv["intents"]]
    if conv.get("profile_id"):
        p = conn.execute(
            "SELECT id, full_name, care_status, interest_level, program_interest FROM crm_source_profiles WHERE id = ?",
            (conv["profile_id"],),
        ).fetchone()
        conv["profile"] = dict(p) if p else None
    return conv


def staff_reply(conn, conv_id: int, text: str, author: str, takeover: bool = True) -> dict:
    text = (text or "").strip()
    if not text:
        raise ValueError("Nội dung trả lời trống.")
    conv = get_conversation(conn, conv_id)
    if not conv:
        raise ValueError("Không tìm thấy hội thoại.")
    mid = _add_message(conn, conv_id, "staff", text[:2000], author=author)
    fields = {"needs_human": 0}
    if takeover:
        fields["status"] = "human"
    _update_conv(conn, conv_id, fields)
    if conv.get("profile_id"):
        try:
            from crm_ops import log_daily_update

            log_daily_update(conn, conv["profile_id"], {"note": f"Trả lời qua chatbot: {text[:300]}", "channel": "chatbot"}, actor=author)
        except Exception as e:
            print(f"[BOT] care log failed: {e}")
    return {"id": mid, "status": fields.get("status", conv["status"])}


def set_conversation_status(conn, conv_id: int, status: str) -> dict:
    if status not in ("open", "human", "handoff", "closed"):
        raise ValueError("Trạng thái không hợp lệ.")
    fields = {"status": status}
    if status in ("open", "closed"):
        fields["needs_human"] = 0
    _update_conv(conn, conv_id, fields)
    return {"id": conv_id, "status": status}


def list_gaps(conn, status: str = "open") -> list[dict]:
    sql = (
        "SELECT g.*, c.visitor_name, c.program_interest, f.question AS faq_question FROM bot_gaps g "
        "LEFT JOIN bot_conversations c ON c.id = g.conversation_id "
        "LEFT JOIN bot_faqs f ON f.id = g.faq_id"
    )
    params: list = []
    if status:
        sql += " WHERE g.status = ?"
        params.append(status)
    sql += " ORDER BY g.id DESC LIMIT 300"
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def resolve_gap(conn, gap_id: int, data: dict, actor: str = "") -> dict:
    gap = conn.execute("SELECT * FROM bot_gaps WHERE id = ?", (gap_id,)).fetchone()
    if not gap:
        raise ValueError("Không tìm thấy câu hỏi.")
    faq_id = None
    if data.get("dismiss"):
        status = "dismissed"
    else:
        faq = save_faq(
            conn,
            {
                "question": data.get("question") or gap["question"],
                "answer": data.get("answer") or "",
                "program_code": data.get("program_code") or "",
            },
            actor=actor,
        )
        faq_id = faq["id"]
        status = "resolved"
        similar = conn.execute("SELECT id, question FROM bot_gaps WHERE status = 'open' AND id != ?", (gap_id,)).fetchall()
        for other in similar:
            if _faq_match(faq["question"], other["question"]) >= 0.6:
                conn.execute(
                    "UPDATE bot_gaps SET status = 'resolved', faq_id = ?, resolved_by = ?, resolved_at = ? WHERE id = ?",
                    (faq_id, actor, _now(), other["id"]),
                )
    conn.execute(
        "UPDATE bot_gaps SET status = ?, faq_id = ?, resolved_by = ?, resolved_at = ? WHERE id = ?",
        (status, faq_id, actor, _now(), gap_id),
    )
    conn.commit()
    return {"id": gap_id, "status": status, "faq_id": faq_id}


def stats(conn) -> dict:
    today = date.today().isoformat()
    week = (date.today() - timedelta(days=6)).isoformat()

    def one(sql, params=()):
        row = conn.execute(sql, params).fetchone()
        return row[0] if row and row[0] is not None else 0

    base = "FROM bot_conversations WHERE channel != 'test'"
    answered_total = one(
        "SELECT COUNT(*) FROM bot_messages m JOIN bot_conversations c ON c.id = m.conversation_id "
        "WHERE c.channel != 'test' AND m.role = 'bot' AND m.mode IN ('llm','extractive','faq','fallback')"
    )
    answered_ok = one(
        "SELECT COUNT(*) FROM bot_messages m JOIN bot_conversations c ON c.id = m.conversation_id "
        "WHERE c.channel != 'test' AND m.role = 'bot' AND m.mode IN ('llm','extractive','faq')"
    )
    intent_counter: Counter = Counter()
    program_counter: Counter = Counter()
    for r in conn.execute(f"SELECT intents, program_interest {base}").fetchall():
        try:
            intent_counter.update(json.loads(r[0] or "[]"))
        except ValueError:
            pass
        if r[1]:
            program_counter[r[1]] += 1
    daily = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        daily.append({
            "date": d,
            "conversations": one(f"SELECT COUNT(*) {base} AND substr(created_at,1,10) = ?", (d,)),
            "leads": one(f"SELECT COUNT(*) {base} AND profile_id IS NOT NULL AND substr(created_at,1,10) = ?", (d,)),
        })
    return {
        "conversations_total": one(f"SELECT COUNT(*) {base}"),
        "conversations_today": one(f"SELECT COUNT(*) {base} AND substr(created_at,1,10) = ?", (today,)),
        "conversations_week": one(f"SELECT COUNT(*) {base} AND substr(created_at,1,10) >= ?", (week,)),
        "leads_total": one(f"SELECT COUNT(*) {base} AND profile_id IS NOT NULL"),
        "leads_hot": one(f"SELECT COUNT(*) {base} AND lead_level IN ('hot','high')"),
        "waiting_human": one(f"SELECT COUNT(*) {base} AND needs_human = 1 AND status != 'closed'"),
        "answer_rate": round(100.0 * answered_ok / answered_total, 1) if answered_total else None,
        "questions_answered": answered_ok,
        "questions_total": answered_total,
        "gaps_open": one("SELECT COUNT(*) FROM bot_gaps WHERE status = 'open'"),
        "kb_docs": one("SELECT COUNT(*) FROM bot_kb_docs WHERE status = 'active'"),
        "kb_chunks": one("SELECT COUNT(*) FROM bot_kb_chunks c JOIN bot_kb_docs d ON d.id = c.doc_id WHERE d.status = 'active'"),
        "faqs": one("SELECT COUNT(*) FROM bot_faqs WHERE status = 'active'"),
        "requests_new": one("SELECT COUNT(*) FROM consult_requests WHERE status = 'new'"),
        "requests_open": one("SELECT COUNT(*) FROM consult_requests WHERE status IN ('new','contacted','caring')"),
        "requests_overdue": one(
            "SELECT COUNT(*) FROM consult_requests WHERE status = 'new' AND sla_due_at < ?",
            (datetime.now().isoformat(sep=" ", timespec="minutes"),),
        ),
        "requests_today": one("SELECT COUNT(*) FROM consult_requests WHERE substr(created_at,1,10) = ?", (today,)),
        "requests_week": one("SELECT COUNT(*) FROM consult_requests WHERE substr(created_at,1,10) >= ?", (week,)),
        "intents": [{"code": k, "label": INTENT_LABELS.get(k, k), "count": v} for k, v in intent_counter.most_common()],
        "programs": [{"code": k, "count": v} for k, v in program_counter.most_common()],
        "daily": daily,
        "llm": llm_status(conn),
    }


def test_question(conn, question: str, program: str = "") -> dict:
    intents = detect_intents(question)
    result = generate_reply(conn, question, program=program or detect_program(question), intents=intents)
    hits = [
        {
            "kind": h["kind"],
            "title": h["title"],
            "score": h.get("score"),
            "coverage": h.get("coverage"),
            "fused": h.get("fused"),
            "text": h["text"][:400],
        }
        for h in result.get("hits") or []
    ]
    return {
        "answered": bool(result.get("answered")),
        "reply": result.get("text") if result.get("answered") else _fallback_text(get_settings(conn), is_english(question), True),
        "mode": result.get("mode") or "fallback",
        "confidence": result.get("confidence"),
        "intents": [INTENT_LABELS.get(i, i) for i in intents],
        "program": program or detect_program(question),
        "hits": hits,
        "sources": _dedupe_sources(result.get("used") or []),
    }


def register_routes(app, get_db, auth_fn, uploads_dir: Path, db_path: str) -> None:
    from flask import jsonify, request

    _DB_PATH_HOLDER["path"] = db_path
    _schedule_vector_sync()

    def err(message, status=400):
        return jsonify({"error": message}), status

    def client_ip():
        return (request.headers.get("X-Client-IP") or request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()

    def staff(conn):
        actor, problem = auth_fn(conn, "admissions.chatbot", "admissions.crm_source")
        if problem:
            return None, err(problem, 403)
        try:
            row = conn.execute("SELECT email, name FROM user WHERE id = ?", (actor.get("user_id"),)).fetchone()
            actor["login"] = row[0] if row else ""
            actor["name"] = (row[1] or row[0]).split(" — ")[0] if row else ""
        except Exception:
            actor["login"] = ""
            actor["name"] = ""
        return actor, None

    def actor_name(actor):
        return str(actor.get("login") or actor.get("user_id") or "staff")

    @app.route("/bot/public/config", methods=["GET"])
    def bot_public_config():
        with get_db() as conn:
            return jsonify(public_settings(conn))

    @app.route("/bot/public/overview", methods=["GET"])
    def bot_public_overview():
        with get_db() as conn:
            return jsonify(public_overview(conn))

    @app.route("/bot/public/chat", methods=["POST"])
    def bot_public_chat():
        data = request.get_json(silent=True) or {}
        ip = client_ip()
        session_key = str(data.get("session") or "")[:64]
        if rate_limited(f"ip:{ip}", limit=40) or (session_key and rate_limited(f"s:{session_key}", limit=12)):
            return err("Bạn gửi hơi nhanh, vui lòng đợi một chút rồi hỏi tiếp nhé.", 429)
        with get_db() as conn:
            try:
                return jsonify(handle_message(
                    conn,
                    session_key=session_key,
                    text=str(data.get("message") or ""),
                    page_url=str(data.get("page_url") or ""),
                    client_ip=ip,
                    channel="test" if data.get("test") else "web",
                ))
            except ValueError as e:
                return err(str(e))

    @app.route("/bot/public/contact", methods=["POST"])
    def bot_public_contact():
        data = request.get_json(silent=True) or {}
        ip = client_ip()
        if rate_limited(f"contact:{ip}", limit=6):
            return err("Vui lòng thử lại sau ít phút.", 429)
        with get_db() as conn:
            try:
                return jsonify(submit_contact(conn, session_key=str(data.get("session") or ""), data=data, client_ip=ip))
            except ValueError as e:
                return err(str(e))

    @app.route("/bot/public/register", methods=["POST"])
    def bot_public_register():
        data = request.get_json(silent=True) or {}
        ip = client_ip()
        if rate_limited(f"register:{ip}", limit=6):
            return err("Bạn đã gửi nhiều yêu cầu, vui lòng thử lại sau ít phút.", 429)
        with get_db() as conn:
            try:
                return jsonify(create_request(
                    conn,
                    data,
                    source="event" if data.get("event_id") else "website",
                    session_key=str(data.get("session") or "")[:64],
                    client_ip=ip,
                ))
            except ValueError as e:
                return err(str(e))

    @app.route("/ops/chatbot/requests", methods=["GET"])
    def bot_requests():
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            mine = request.args.get("mine") in ("1", "true")
            return jsonify(list_requests(
                conn,
                status=request.args.get("status") or "",
                assignee=actor.get("user_id") if mine else None,
                q=request.args.get("q") or "",
                overdue=request.args.get("overdue") in ("1", "true"),
            ))

    @app.route("/ops/chatbot/requests/<int:req_id>", methods=["GET", "POST"])
    def bot_request(req_id):
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            if request.method == "POST":
                try:
                    return jsonify(update_request(conn, req_id, request.get_json(silent=True) or {}, actor))
                except ValueError as e:
                    return err(str(e))
            item = request_detail(conn, req_id)
            if not item:
                return err("Không tìm thấy yêu cầu tư vấn.", 404)
            item["me"] = {"user_id": actor.get("user_id"), "login": actor.get("login"), "name": actor.get("name")}
            return jsonify(item)

    @app.route("/bot/public/messages", methods=["GET"])
    def bot_public_messages():
        session_key = (request.args.get("session") or "").strip()[:64]
        if not session_key:
            return jsonify({"messages": [], "status": "new"})
        with get_db() as conn:
            return jsonify(poll_messages(conn, session_key, request.args.get("after", 0, type=int)))

    @app.route("/ops/chatbot/stats", methods=["GET"])
    def bot_stats():
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            return jsonify(stats(conn))

    @app.route("/ops/chatbot/conversations", methods=["GET"])
    def bot_conversations():
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            return jsonify(list_conversations(
                conn,
                q=request.args.get("q") or "",
                status=request.args.get("status") or "",
                level=request.args.get("level") or "",
                needs_human=request.args.get("needs_human") or "",
            ))

    @app.route("/ops/chatbot/conversations/<int:conv_id>", methods=["GET"])
    def bot_conversation(conv_id):
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            conv = conversation_detail(conn, conv_id)
            return jsonify(conv) if conv else err("Không tìm thấy hội thoại.", 404)

    @app.route("/ops/chatbot/conversations/<int:conv_id>/reply", methods=["POST"])
    def bot_conversation_reply(conv_id):
        data = request.get_json(silent=True) or {}
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            try:
                return jsonify(staff_reply(conn, conv_id, data.get("text") or "", actor_name(actor), bool(data.get("takeover", True))))
            except ValueError as e:
                return err(str(e))

    @app.route("/ops/chatbot/conversations/<int:conv_id>/status", methods=["POST"])
    def bot_conversation_status(conv_id):
        data = request.get_json(silent=True) or {}
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            try:
                return jsonify(set_conversation_status(conn, conv_id, data.get("status") or ""))
            except ValueError as e:
                return err(str(e))

    @app.route("/ops/chatbot/conversations/<int:conv_id>/sync-crm", methods=["POST"])
    def bot_conversation_sync(conv_id):
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            conv = get_conversation(conn, conv_id)
            if not conv:
                return err("Không tìm thấy hội thoại.", 404)
            if not (conv.get("phone") or conv.get("email")):
                return err("Hội thoại chưa có số điện thoại hoặc email.")
            return jsonify(sync_lead(conn, conv, force=True))

    @app.route("/ops/chatbot/gaps", methods=["GET"])
    def bot_gaps():
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            return jsonify(list_gaps(conn, request.args.get("status", "open")))

    @app.route("/ops/chatbot/gaps/<int:gap_id>/resolve", methods=["POST"])
    def bot_gap_resolve(gap_id):
        data = request.get_json(silent=True) or {}
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            try:
                return jsonify(resolve_gap(conn, gap_id, data, actor_name(actor)))
            except ValueError as e:
                return err(str(e))

    @app.route("/ops/chatbot/faqs", methods=["GET", "POST"])
    def bot_faqs():
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            if request.method == "POST":
                try:
                    return jsonify(save_faq(conn, request.get_json(silent=True) or {}, actor=actor_name(actor))), 201
                except ValueError as e:
                    return err(str(e))
            return jsonify(list_faqs(conn))

    @app.route("/ops/chatbot/faqs/<int:faq_id>", methods=["PUT", "DELETE"])
    def bot_faq(faq_id):
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            if request.method == "DELETE":
                delete_faq(conn, faq_id)
                return jsonify({"ok": True})
            try:
                return jsonify(save_faq(conn, request.get_json(silent=True) or {}, faq_id=faq_id, actor=actor_name(actor)))
            except ValueError as e:
                return err(str(e))

    @app.route("/ops/chatbot/docs", methods=["GET", "POST"])
    def bot_docs():
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            if request.method == "POST":
                data = request.get_json(silent=True) or {}
                try:
                    return jsonify(add_document(
                        conn,
                        title=data.get("title") or "",
                        content=data.get("content") or "",
                        source_type="text",
                        program_code=data.get("program_code") or "",
                        created_by=actor_name(actor),
                    )), 201
                except ValueError as e:
                    return err(str(e))
            return jsonify(list_documents(conn))

    @app.route("/ops/chatbot/docs/upload", methods=["POST"])
    def bot_docs_upload():
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            files = request.files.getlist("files") or ([request.files["file"]] if "file" in request.files else [])
            if not files:
                return err("Chưa chọn tệp.")
            target = uploads_dir / "admission_kb"
            target.mkdir(parents=True, exist_ok=True)
            done, failed = [], []
            for f in files:
                name = Path(f.filename or "").name
                if not name or Path(name).suffix.lower() not in SUPPORTED_EXTS:
                    failed.append({"file": name, "error": "Định dạng chưa hỗ trợ (PDF, DOCX, XLSX, TXT, MD)."})
                    continue
                dest = target / f"{uuid.uuid4().hex[:10]}_{name}"
                f.save(str(dest))
                try:
                    done.append(import_file(
                        conn,
                        str(dest),
                        title=request.form.get("title") if len(files) == 1 and request.form.get("title") else "",
                        program_code=request.form.get("program_code") or "",
                        created_by=actor_name(actor),
                        file_name=name,
                    ))
                except Exception as e:
                    failed.append({"file": name, "error": str(e)})
                    try:
                        dest.unlink()
                    except OSError:
                        pass
            return jsonify({"imported": done, "failed": failed}), (201 if done else 400)

    @app.route("/ops/chatbot/docs/<int:doc_id>", methods=["GET", "PUT", "DELETE"])
    def bot_doc(doc_id):
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            if request.method == "DELETE":
                delete_document(conn, doc_id)
                return jsonify({"ok": True})
            if request.method == "PUT":
                try:
                    return jsonify(update_document(conn, doc_id, request.get_json(silent=True) or {}))
                except ValueError as e:
                    return err(str(e))
            doc = get_document(conn, doc_id)
            return jsonify(doc) if doc else err("Không tìm thấy tài liệu.", 404)

    @app.route("/ops/chatbot/settings", methods=["GET", "PUT"])
    def bot_settings():
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            if request.method == "PUT":
                return jsonify(save_settings(conn, request.get_json(silent=True) or {}))
            return jsonify(public_settings(conn, include_private=True))

    @app.route("/ops/chatbot/test", methods=["POST"])
    def bot_test():
        data = request.get_json(silent=True) or {}
        with get_db() as conn:
            actor, problem = staff(conn)
            if problem:
                return problem
            question = (data.get("question") or "").strip()
            if not question:
                return err("Nhập câu hỏi để thử.")
            return jsonify(test_question(conn, question, (data.get("program_code") or "").upper()))
