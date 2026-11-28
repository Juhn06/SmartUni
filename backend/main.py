"""
Flask API for user CRUD operations and ReadArticles (admin PDF upload, RAG Q&A).
"""
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file

# Load .env before reading config (for local runs; Docker uses env_file)
load_dotenv(Path(__file__).resolve().parent / ".env")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# backend/db/website.db (set DB_PATH env to override)
BACKEND_DIR = Path(__file__).resolve().parent
DB_DIR = BACKEND_DIR / "db"
DB_DIR.mkdir(parents=True, exist_ok=True)
_raw_db = os.environ.get("DB_PATH", str(DB_DIR / "website.db"))
_db_candidate = Path(_raw_db)
# Relative DB_PATH is resolved against backend/, not process cwd
if not _db_candidate.is_absolute():
    _db_candidate = BACKEND_DIR / _db_candidate
DB_PATH = _db_candidate.resolve()
# Prefer website.db when default empty legacy DB would hide staff accounts
if DB_PATH.name == "readarticles.db":
    _website = (DB_DIR / "website.db").resolve()
    if _website.is_file():
        DB_PATH = _website
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_PATH_STR = str(DB_PATH)
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", str(BACKEND_DIR / "uploads")))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
# Data folder for bulk import: user-provided folder name is relative to this
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BACKEND_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PORT = 8026

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


@contextmanager
def get_db():
    """Context manager for database connections (uses string path for sqlite3)."""
    conn = sqlite3.connect(DB_PATH_STR)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
    finally:
        conn.close()


def row_to_user(row: sqlite3.Row, include_password: bool = False) -> dict:
    """Convert a DB row to a user dict (passwords excluded by default)."""
    keys = row.keys() if hasattr(row, "keys") else []
    user = {"id": row["id"], "name": row["name"], "email": row["email"]}
    user["is_admin"] = bool(row["is_admin"]) if "is_admin" in keys else False
    user["is_locked"] = bool(row["is_locked"]) if "is_locked" in keys else False
    if "gender" in keys:
        user["gender"] = (row["gender"] or "").strip() or None
    if "birth_year" in keys:
        user["birth_year"] = row["birth_year"]
    if "avatar_path" in keys:
        user["avatar_path"] = row["avatar_path"]
    if "theme" in keys and row["theme"]:
        user["theme"] = row["theme"]
    if "theme_manual" in keys:
        user["theme_manual"] = bool(row["theme_manual"])
    if "departments" in keys:
        user["departments"] = row["departments"] or []
    if include_password:
        user["password"] = row["password"]
    return user


def _user_departments_map(conn) -> dict[int, list[dict]]:
    """Map user_id -> list of {id, code, name}."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ud.user_id, d.id, d.code, d.name "
            "FROM user_departments ud "
            "JOIN departments d ON d.id = ud.department_id "
            "ORDER BY d.sort_order, d.name"
        )
    except sqlite3.OperationalError:
        return {}
    out: dict[int, list[dict]] = {}
    for r in cur.fetchall():
        out.setdefault(r["user_id"], []).append(
            {"id": r["id"], "code": r["code"], "name": r["name"]}
        )
    return out


def json_error(message: str, status: int) -> tuple:
    """Return a consistent JSON error response."""
    return jsonify({"error": message}), status


def row_to_storage(row: sqlite3.Row) -> dict:
    """Convert a DB row to a storage dict (id as int)."""
    try:
        sid = int(row["id"])
    except (TypeError, ValueError):
        sid = row["id"]
    return {
        "id": sid,
        "product": row["product"] or "",
        "brand": row["brand"] or "",
        "rating": row["rating"] or "",
        "model": row["model"] or "",
        "picture": row["picture"] or "",
        "price": row["price"] or "",
        "RAM": row["RAM"] or "",
        "details": row["details"] or "",
    }


def row_to_article(row: sqlite3.Row) -> dict:
    """Convert a DB row to an article dict."""
    return {
        "id": row["id"],
        "title": row["title"] or "",
        "source_url": row["source_url"] or "",
        "file_path": row["file_path"] or "",
        "summary": row["summary"] or "",
        "created_at": row["created_at"] or "",
    }


def _is_header_row(row: dict) -> bool:
    """True if row looks like a header row (values = column names)."""
    return (
        str(row.get("id", "")).lower() == "id"
        or str(row.get("product", "")).lower() == "product"
    )


def init_db():
    """Create tables if they do not exist."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS user ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL, email TEXT NOT NULL, password TEXT NOT NULL)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS storages ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "product TEXT, brand TEXT, rating TEXT, model TEXT, "
            "picture TEXT, price TEXT, RAM TEXT, details TEXT)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS articles ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, source_url TEXT, file_path TEXT, "
            "summary TEXT, full_text TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS chat_history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "article_id INTEGER NOT NULL, "
            "question TEXT NOT NULL, answer TEXT NOT NULL, "
            "model TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS theses ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, source_url TEXT, file_path TEXT, "
            "summary TEXT, analysis TEXT, full_text TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS thesis_chat_history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "thesis_id INTEGER NOT NULL, "
            "question TEXT NOT NULL, answer TEXT NOT NULL, "
            "model TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY (thesis_id) REFERENCES theses(id) ON DELETE CASCADE)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS book_categories ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL UNIQUE, "
            "sort_order INTEGER DEFAULT 0, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS books ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, source_url TEXT, file_path TEXT, "
            "summary TEXT, full_text TEXT, category_id INTEGER, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY (category_id) REFERENCES book_categories(id) ON DELETE SET NULL)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS book_chat_history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "book_id INTEGER NOT NULL, "
            "question TEXT NOT NULL, answer TEXT NOT NULL, "
            "model TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS book_notes ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "book_id INTEGER NOT NULL, user_id INTEGER NOT NULL, "
            "content TEXT NOT NULL, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE, "
            "FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS article_notes ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "article_id INTEGER NOT NULL, user_id INTEGER NOT NULL, "
            "content TEXT NOT NULL, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE, "
            "FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS projects ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "title TEXT NOT NULL, description TEXT, "
            "combined_summary TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS project_files ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "project_id INTEGER NOT NULL, "
            "title TEXT NOT NULL, file_path TEXT, "
            "file_hash TEXT, summary TEXT, full_text TEXT, "
            "status TEXT DEFAULT 'pending', "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS project_chat_history ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "project_id INTEGER NOT NULL, "
            "question TEXT NOT NULL, answer TEXT NOT NULL, "
            "model TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE)"
        )
        cur.execute(
            "CREATE TABLE IF NOT EXISTS project_articles ("
            "project_id INTEGER NOT NULL, article_id INTEGER NOT NULL, "
            "PRIMARY KEY (project_id, article_id), "
            "FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE, "
            "FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE)"
        )

        # --- Migrations: add aims, instructions to projects ---
        for col in ("aims", "instructions"):
            try:
                cur.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass

        # --- Migration: add user_id to projects (for per-user project visibility) ---
        try:
            cur.execute("ALTER TABLE projects ADD COLUMN user_id INTEGER REFERENCES user(id)")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # --- Migration: project_shares (share projects with other users by email) ---
        cur.execute(
            "CREATE TABLE IF NOT EXISTS project_shares ("
            "project_id INTEGER NOT NULL, "
            "user_id INTEGER NOT NULL, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY (project_id, user_id), "
            "FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE, "
            "FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_shares_user "
            "ON project_shares(user_id)"
        )
        conn.commit()

        # --- Migration: add category_id to books ---
        try:
            cur.execute("ALTER TABLE books ADD COLUMN category_id INTEGER REFERENCES book_categories(id)")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        # --- Seed default book categories ---
        cur.execute("SELECT COUNT(*) FROM book_categories")
        if cur.fetchone()[0] == 0:
            for i, name in enumerate(["English Book", "Programming Book", "Computer Science Book", "Other Fields"]):
                cur.execute(
                    "INSERT INTO book_categories (name, sort_order) VALUES (?, ?)",
                    (name, i),
                )
            conn.commit()

        # --- Indexes for query performance ---

        # chat_history: lookups by article_id, sorting by created_at
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_history_article "
            "ON chat_history(article_id, created_at DESC)"
        )

        # thesis_chat_history: lookups by thesis_id, sorting by created_at
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_thesis_chat_history_thesis "
            "ON thesis_chat_history(thesis_id, created_at DESC)"
        )

        # project_files: lookups by project_id, filtering by status
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_files_project "
            "ON project_files(project_id, status)"
        )

        # project_chat_history: lookups by project_id, sorting by created_at
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_chat_project "
            "ON project_chat_history(project_id, created_at DESC)"
        )
        # project_articles: lookups by project_id
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_project_articles_project "
            "ON project_articles(project_id)"
        )

        # articles: ORDER BY created_at DESC on list page
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_created "
            "ON articles(created_at DESC)"
        )

        # theses: ORDER BY created_at DESC on list page
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_theses_created "
            "ON theses(created_at DESC)"
        )

        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_books_created "
            "ON books(created_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_books_category "
            "ON books(category_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_book_chat_history_book "
            "ON book_chat_history(book_id, created_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_book_notes_book_user "
            "ON book_notes(book_id, user_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_article_notes_article_user "
            "ON article_notes(article_id, user_id)"
        )

        # projects: ORDER BY updated_at DESC on list page
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_updated "
            "ON projects(updated_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_projects_user "
            "ON projects(user_id)"
        )

        # user: email lookups for login
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_email "
            "ON user(email)"
        )

        # --- Migrations: add model column to existing chat tables ---
        for tbl in ("chat_history", "thesis_chat_history", "project_chat_history", "book_chat_history"):
            try:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN model TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists

        # --- Migrations: add feedback column (like/dislike) to chat tables ---
        for tbl in ("chat_history", "thesis_chat_history", "project_chat_history", "book_chat_history"):
            try:
                cur.execute(f"ALTER TABLE {tbl} ADD COLUMN feedback TEXT")
            except sqlite3.OperationalError:
                pass  # column already exists

        # --- Migration: add summary_feedback to articles ---
        try:
            cur.execute("ALTER TABLE articles ADD COLUMN summary_feedback TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

        # --- Migration: add analysis to articles ---
        try:
            cur.execute("ALTER TABLE articles ADD COLUMN analysis TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists

        # --- Migration: add is_admin, is_locked to user ---
        for col in ("is_admin", "is_locked"):
            try:
                cur.execute(f"ALTER TABLE user ADD COLUMN {col} INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
        # Profile: gender, birth_year, avatar, theme preference
        for col, decl in (
            ("gender", "TEXT"),
            ("birth_year", "INTEGER"),
            ("avatar_path", "TEXT"),
            ("theme", "TEXT"),
            ("theme_manual", "INTEGER DEFAULT 0"),
        ):
            try:
                cur.execute(f"ALTER TABLE user ADD COLUMN {col} {decl}")
                conn.commit()
            except sqlite3.OperationalError:
                pass
        try:
            cur.execute(
                "UPDATE user SET is_admin = 1 WHERE email = ?",
                ("thaofami@gmail.com",),
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass

        cur.execute(
            "CREATE TABLE IF NOT EXISTS bulk_import_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "folder TEXT NOT NULL, "
            "filename TEXT NOT NULL, "
            "article_id INTEGER, "
            "status TEXT NOT NULL, "
            "error_message TEXT, "
            "created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
            "UNIQUE(folder, filename), "
            "FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL)"
        )

        # --- FTS5 full-text search for articles (title, summary) ---
        cur.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5("
            "title, summary, content='articles', content_rowid='id')"
        )
        try:
            cur.execute(
                "CREATE TRIGGER IF NOT EXISTS articles_fts_ai AFTER INSERT ON articles BEGIN "
                "INSERT INTO articles_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary); END"
            )
            cur.execute(
                "CREATE TRIGGER IF NOT EXISTS articles_fts_ad AFTER DELETE ON articles BEGIN "
                "INSERT INTO articles_fts(articles_fts, rowid) VALUES ('delete', old.id); END"
            )
            cur.execute(
                "CREATE TRIGGER IF NOT EXISTS articles_fts_au AFTER UPDATE ON articles BEGIN "
                "INSERT INTO articles_fts(articles_fts, rowid) VALUES ('delete', old.id); "
                "INSERT INTO articles_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary); END"
            )
        except sqlite3.OperationalError:
            pass  # triggers may already exist
        # Initial population if articles exist and FTS is empty
        try:
            cur.execute("SELECT COUNT(*) FROM articles_fts")
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "INSERT INTO articles_fts(rowid, title, summary) "
                    "SELECT id, title, COALESCE(summary, '') FROM articles"
                )
        except sqlite3.OperationalError:
            pass

        # --- Departments + staff seed (nghiepvu) ---
        try:
            from seed_org import seed_departments_and_users

            seed_departments_and_users(conn)
        except Exception as e:
            print(f"Warning: org seed failed: {e}")

        # --- Operational draft data ---
        try:
            from ops_data import seed_ops_draft_data

            seed_ops_draft_data(conn)
        except Exception as e:
            print(f"Warning: ops seed failed: {e}")

        # --- Thủ quỹ / treasury ledger (khớp luồng phí ghi danh) ---
        try:
            from treasury_ops import backfill_from_enrollment_fees, ensure_treasury_tables

            cur = conn.cursor()
            ensure_treasury_tables(cur)
            try:
                from nv2026_ops import ensure_nv2026_tables

                ensure_nv2026_tables(cur)
                conn.commit()
            except Exception:
                pass
            conn.commit()
            backfill_from_enrollment_fees(conn)
        except Exception as e:
            print(f"Warning: treasury seed failed: {e}")

        try:
            from learner_spine import align_flow_records

            align_flow_records(conn)
        except Exception as e:
            print(f"Warning: flow align failed: {e}")

        # --- Trợ lý Ban Giám đốc modules ---
        try:
            from asst_ops import seed_asst_draft_data

            seed_asst_draft_data(conn)
        except Exception as e:
            print(f"Warning: asst seed failed: {e}")

        # --- Marcom (Trần Anh Tuấn) ---
        try:
            from marcom_ops import seed_marcom_draft_data

            seed_marcom_draft_data(conn)
        except Exception as e:
            print(f"Warning: marcom seed failed: {e}")

        # --- Canvas LMS bridge ---
        try:
            from canvas_bridge import seed_canvas_draft_data

            seed_canvas_draft_data(conn)
        except Exception as e:
            print(f"Warning: canvas seed failed: {e}")

        # --- Course content / syllabus / materials ---
        try:
            from course_content import seed_course_content

            seed_course_content(conn)
        except Exception as e:
            print(f"Warning: course content seed failed: {e}")

        # --- Class lessons (per lớp–môn) ---
        try:
            from class_lessons import seed_class_lessons

            seed_class_lessons(conn)
        except Exception as e:
            print(f"Warning: class lessons seed failed: {e}")

        try:
            from elearn_ops import ensure_elearn_tables

            ensure_elearn_tables(conn.cursor())
            conn.commit()
        except Exception as e:
            print(f"Warning: elearn tables failed: {e}")

        # --- Coordinator fields (thí sinh / PV / điểm / LV) ---
        try:
            from coord_ops import seed_coord_enrichment

            seed_coord_enrichment(conn)
        except Exception as e:
            print(f"Warning: coord enrichment seed failed: {e}")

        try:
            from ops_crud import seed_extra_ops

            seed_extra_ops(conn)
        except Exception as e:
            print(f"Warning: ops crud seed failed: {e}")

        try:
            from suggestions import ensure_suggestions_table

            ensure_suggestions_table(conn.cursor())
        except Exception as e:
            print(f"Warning: suggestions table failed: {e}")

        try:
            from status_catalog import seed_status_catalog

            n = seed_status_catalog(conn)
            if n:
                print(f"Seeded {n} status catalog rows")
        except Exception as e:
            print(f"Warning: status catalog seed failed: {e}")

        try:
            from crm_ops import ensure_crm_tables

            ensure_crm_tables(conn.cursor())
        except Exception as e:
            print(f"Warning: CRM tables failed: {e}")

        try:
            from admission_bot import bootstrap as bootstrap_admission_bot

            seeded = bootstrap_admission_bot(conn, DATA_DIR)
            if seeded["docs"] or seeded["faqs"]:
                print(f"Seeded admission bot: {seeded['docs']} docs, {seeded['faqs']} FAQ")
        except Exception as e:
            print(f"Warning: admission bot tables failed: {e}")

        try:
            from student_bot import bootstrap as bootstrap_student_bot

            seeded = bootstrap_student_bot(conn, DATA_DIR)
            if seeded["docs"] or seeded["faqs"]:
                print(f"Seeded student bot: {seeded['docs']} docs, {seeded['faqs']} FAQ")
        except Exception as e:
            print(f"Warning: student bot tables failed: {e}")

        conn.commit()


init_db()

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/models", methods=["GET"])
def list_models():
    """Return the list of available chat models."""
    try:
        from rag_service import get_available_models
        return jsonify(get_available_models())
    except Exception:
        return jsonify([os.environ.get("CHAT_MODEL", "qwen3:8b")])


@app.route("/api/metadata", methods=["GET"])
def api_metadata():
    """
    Return metadata for external discovery (e.g., Agent integration).
    Describes capabilities, data types, supported models, and sample prompts.
    """
    try:
        from rag_service import get_available_models
        model_ids = get_available_models()
    except Exception:
        model_ids = [os.environ.get("CHAT_MODEL", "qwen3:8b")]

    supported_models = [
        {
            "model_id": m,
            "name": m.split("/")[-1] if "/" in m else m,
            "description": f"Model for RAG Q&A and summarization",
        }
        for m in (model_ids or ["qwen3:8b"])
    ]

    metadata = {
        "name": "ReadArticles",
        "description": (
            "Upload PDFs to search, summarize, and chat with your documents. "
            "Semantic search over existing articles, or upload a PDF for instant analysis."
        ),
        "capabilities": ["search"],
        "contact": os.environ.get("METADATA_CONTACT", ""),
        "developer": os.environ.get("METADATA_DEVELOPER", "ReadArticles Team"),
        "version": "1.0.0",
        "status": "active",
        "provided_data_types": [
            {"type": "documents", "description": "List and summary of articles, theses, and books stored in the system"},
        ],
        "sample_prompts": [
            "Search/Find related articles with",
            "What is the main contribution of this paper?",
            "Summarize the methodology section",
            "What are the limitations mentioned?",
        ],
        "supported_models": supported_models,
    }
    return jsonify(metadata)


@app.route("/api/articles/<int:article_id>/file", methods=["GET"])
def api_article_file(article_id):
    """Serve article PDF for external API (attachments)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path, source_url FROM articles WHERE id = ?", (article_id,))
        row = cur.fetchone()
    if not row:
        return json_error("Article not found", 404)
    fp = Path(row["file_path"]) if row["file_path"] else None
    if fp and fp.exists():
        return send_file(str(fp), mimetype="application/pdf", as_attachment=False)
    return json_error("File not found", 404)


def _build_article_file_url(article_id: int) -> str:
    """Build full URL to article PDF (for API attachments)."""
    base = (request.url_root or "").rstrip("/")
    return f"{base}/api/articles/{article_id}/file"


def _extract_notification_email(data: dict) -> str | None:
    """
    Extract email for completion notification.
    Uses 'email' field if present, else 'user' if it looks like an email (contains @).
    """
    email = (data.get("email") or "").strip()
    if email and "@" in email:
        return email
    user = (data.get("user") or "").strip()
    if user and "@" in user:
        return user
    return None


def _send_ask_completion_email(to_email: str, prompt: str, mode: str, content_preview: str) -> None:
    """
    Send completion notification to user. Uses thaop@neu.edu.vn as sender.
    Config: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD (EMAIL_FROM default: thaop@neu.edu.vn)
    Fails silently if SMTP not configured.
    """
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    if not smtp_host or not smtp_password:
        return
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    from_addr = os.environ.get("EMAIL_FROM", "thaop@neu.edu.vn")
    smtp_user = os.environ.get("SMTP_USER", from_addr)
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    use_tls = smtp_port in (587, 25)

    subject = f"ReadArticles: Processing complete — {prompt[:50]}{'...' if len(prompt) > 50 else ''}"
    body = f"""Your ReadArticles request has been processed successfully.

Mode: {mode}
Query: {prompt}

Preview of results:
{content_preview[:800]}{'...' if len(content_preview) > 800 else ''}

—
Sent from ReadArticles (thaop@neu.edu.vn)
"""
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.sendmail(from_addr, [to_email], msg.as_string())
        print(f"[API] completion email sent to {to_email}")
    except Exception as e:
        print(f"[API] email send failed: {e}")


@app.route("/api/ask", methods=["POST"])
def api_ask():
    """
    Two modes:
    1) Without PDF: Semantic search over existing articles (top 15 matching results).
    2) With PDF: Upload file, process like Articles (extract text, summary, analysis),
       then answer the prompt and return answer + summary + analysis.
    Input (JSON): {"session_id", "model_id", "user", "prompt"}
    Input (multipart with PDF): form field "file" or "pdf" + "prompt" (and other fields)
    If "user" or "email" contains an email address, a completion notification is sent
    from thaop@neu.edu.vn after processing (requires SMTP_* env vars).
    """
    import time as _time
    t0 = _time.perf_counter()

    # Parse input: support both JSON and multipart/form-data
    pdf_file = request.files.get("file") or request.files.get("pdf")
    if request.is_json:
        data = request.get_json(silent=True) or {}
    elif pdf_file:
        data = dict(request.form) if request.form else {}
    else:
        data = request.get_json(silent=True) or {}
    session_id = data.get("session_id") or ""
    model_id = data.get("model_id") or os.environ.get("CHAT_MODEL", "qwen3:8b")
    user = data.get("user") or ""
    prompt = (data.get("prompt") or "").strip()

    if not prompt:
        return jsonify({
            "status": "error",
            "content_markdown": "Prompt is required.",
            "session_id": session_id,
            "attachments": [],
            "meta": {"model": model_id, "response_time_ms": 0, "tokens_used": 0},
        }), 400

    try:
        from rag_service import (
            query_articles,
            query_articles_fast,
            generate_chat_answer,
            is_llm_configured,
            extract_text_from_pdf,
            add_article_to_rag,
            generate_summary_three_pass,
            generate_article_analysis,
        )
        if not is_llm_configured():
            return jsonify({
                "status": "error",
                "content_markdown": "LLM not configured for search.",
                "session_id": session_id,
                "attachments": [],
                "meta": {"model": model_id, "response_time_ms": 0, "tokens_used": 0},
            }), 503

        # ---- Case: With PDF - upload, process, answer ----
        if pdf_file and pdf_file.filename and pdf_file.filename.lower().endswith(".pdf"):
            file_path = UPLOADS_DIR / f"{uuid.uuid4().hex}_{pdf_file.filename}"
            pdf_file.save(str(file_path))
            try:
                full_text = extract_text_from_pdf(str(file_path))
                if not full_text.strip():
                    file_path.unlink(missing_ok=True)
                    return jsonify({
                        "status": "error",
                        "content_markdown": "Could not extract text from PDF.",
                        "session_id": session_id,
                        "attachments": [],
                        "meta": {"model": model_id, "response_time_ms": 0, "tokens_used": 0},
                    }), 400

                title = pdf_file.filename[:-4] if pdf_file.filename.endswith(".pdf") else pdf_file.filename
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                    fut_summary = ex.submit(generate_summary_three_pass, full_text)
                    fut_analysis = ex.submit(generate_article_analysis, full_text)
                    summary_data = fut_summary.result()
                    analysis = fut_analysis.result()
                summary = summary_data.get("full", "")

                with get_db() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "INSERT INTO articles (title, source_url, file_path, summary, analysis, full_text) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (title, "", str(file_path), summary, analysis, full_text),
                    )
                    conn.commit()
                    article_id = cur.lastrowid
                add_article_to_rag(article_id, title, full_text)

                context = query_articles(prompt, article_ids=[article_id], top_k=5)
                answer = generate_chat_answer(
                    prompt, context,
                    source_type="article", source_id=article_id,
                    model=model_id or None,
                )
                used_model = model_id or os.environ.get("CHAT_MODEL", "qwen3:8b")
                url = _build_article_file_url(article_id)

                content_parts = [
                    f"## Answer to your question\n\n{answer}",
                    f"## Summary\n\n{summary}" if summary else "",
                    f"## Analysis\n\n{analysis}" if analysis else "",
                ]
                content_markdown = "\n\n".join(p for p in content_parts if p)
                response_time_ms = (_time.perf_counter() - t0) * 1000
                tokens_used = len(content_markdown) // 4

                notify_email = _extract_notification_email(data)
                if notify_email:
                    import threading
                    threading.Thread(
                        target=_send_ask_completion_email,
                        args=(notify_email, prompt, "PDF upload & analysis", content_markdown),
                        daemon=True,
                    ).start()

                return jsonify({
                    "status": "success",
                    "session_id": session_id,
                    "content_markdown": content_markdown,
                    "attachments": [{"type": "pdf", "url": url}],
                    "meta": {"model": used_model, "response_time_ms": response_time_ms, "tokens_used": tokens_used},
                })
            except Exception as e:
                file_path.unlink(missing_ok=True)
                raise

        # ---- Case: Without PDF - fast semantic search (no Query Transform/HyDE) ----
        chunks = query_articles_fast(prompt, article_ids=None, top_k=15)
    except Exception as e:
        return jsonify({
            "status": "error",
            "content_markdown": str(e),
            "session_id": session_id,
            "attachments": [],
            "meta": {"model": model_id, "response_time_ms": 0, "tokens_used": 0},
        }), 500

    article_ids_seen = set()
    attachments = []
    ids_for_attachments = []
    parts = []

    for i, c in enumerate(chunks, 1):
        aid = c.get("article_id")
        title = c.get("title") or "Untitled"
        section = c.get("section") or ""
        content = c.get("content") or ""
        score = c.get("relevance_score")

        if aid and aid not in article_ids_seen:
            article_ids_seen.add(aid)
            ids_for_attachments.append(aid)

        header = f"### {i}. {title}"
        if section:
            header += f" ({section})"
        if score is not None:
            header += f" — relevance: {score}"
        parts.append(f"{header}\n\n{content}")

    if ids_for_attachments:
        placeholders = ",".join("?" * len(ids_for_attachments))
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT id, source_url FROM articles WHERE id IN ({placeholders})",
                ids_for_attachments,
            )
            url_by_id = {r["id"]: (r["source_url"] or "").strip() for r in cur.fetchall()}
        for aid in ids_for_attachments:
            url = url_by_id.get(aid, "")
            if url.startswith("http"):
                attachments.append({"type": "pdf", "url": url})
            else:
                attachments.append({"type": "pdf", "url": _build_article_file_url(aid)})

    content_markdown = "\n\n---\n\n".join(parts) if parts else "No matching articles found."
    response_time_ms = (_time.perf_counter() - t0) * 1000
    tokens_used = len(content_markdown) // 4

    notify_email = _extract_notification_email(data)
    if notify_email:
        import threading
        threading.Thread(
            target=_send_ask_completion_email,
            args=(notify_email, prompt, "Semantic search", content_markdown),
            daemon=True,
        ).start()

    return jsonify({
        "status": "success",
        "session_id": session_id,
        "content_markdown": content_markdown,
        "attachments": attachments,
        "meta": {
            "model": model_id,
            "response_time_ms": response_time_ms,
            "tokens_used": tokens_used,
        },
    })


@app.route("/users/login", methods=["POST"])
def login_user():
    """Validate login id and password; return user + access (menus, scopes)."""
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return json_error("Email and password are required", 400)

    with get_db() as conn:
        cur = conn.cursor()
        # Case-insensitive login id (Admin / admin / AnhTT)
        cur.execute(
            "SELECT id, name, email, password, is_admin, is_locked, "
            "gender, birth_year, avatar_path, theme, theme_manual "
            "FROM user WHERE lower(trim(email)) = lower(trim(?))",
            (email,),
        )
        row = cur.fetchone()
        if not row:
            aliases = {
                "dupontpj": "DupontJ",
                "prof.jeandupont": "DupontJ",
                "jean.dupont": "DupontJ",
            }
            alt = aliases.get(email.lower().replace(" ", ""))
            if alt:
                cur.execute(
                    "SELECT id, name, email, password, is_admin, is_locked, "
                    "gender, birth_year, avatar_path, theme, theme_manual "
                    "FROM user WHERE lower(trim(email)) = lower(trim(?))",
                    (alt,),
                )
                row = cur.fetchone()
        if not row:
            return json_error("Invalid email or password", 401)
        stored = (row["password"] or "").strip()
        if stored != password:
            return json_error("Invalid email or password", 401)
        is_locked = row["is_locked"] if "is_locked" in row.keys() else 0
        if is_locked:
            return json_error("Account is locked", 403)
        from seed_org import get_user_access
        from rbac import build_nav_from_permissions
        from student_accounts import must_change

        access = get_user_access(conn, row["id"])
        force_change = must_change(conn, row["id"])
    user = row_to_user(row, include_password=False)
    user["must_change_password"] = force_change
    user["departments"] = access["departments"]
    user["permissions"] = access["permission_codes"]
    user["program_scopes"] = access["program_scopes"]
    user["lang"] = access.get("lang", "vi")
    user["theme"] = access.get("theme", "courses")
    user["theme_manual"] = bool(access.get("theme_manual"))
    user["gender"] = access.get("gender") or user.get("gender")
    user["birth_year"] = access.get("birth_year") if access.get("birth_year") is not None else user.get("birth_year")
    user["avatar_path"] = access.get("avatar_path") or user.get("avatar_path")
    user["nav"] = build_nav_from_permissions(
        access["permission_codes"],
        lang=access.get("lang", "vi"),
        departments=access.get("departments"),
    )
    return jsonify(user)


@app.route("/users/<int:user_id>/password", methods=["POST"])
def change_user_password(user_id):
    """Self-service password change: require current password, then set new one."""
    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password") or ""
    new_password = data.get("new_password") or ""

    if not current_password or not new_password:
        return json_error("Current password and new password are required", 400)
    if len(new_password) < 4:
        return json_error("New password must be at least 4 characters", 400)
    if new_password == current_password:
        return json_error("New password must be different from current password", 400)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, password, is_locked FROM user WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return json_error("User not found", 404)
        is_locked = row["is_locked"] if "is_locked" in row.keys() else 0
        if is_locked:
            return json_error("Account is locked", 403)
        if row["password"] != current_password:
            return json_error("Current password is incorrect", 401)
        cur.execute(
            "UPDATE user SET password = ? WHERE id = ?",
            (new_password, user_id),
        )
        conn.commit()
        from student_accounts import set_must_change

        set_must_change(conn, user_id, False)
    return jsonify({"ok": True, "message": "Password updated"})


def _theme_for_gender(gender: str | None) -> str:
    """Toàn bộ chức năng dùng theme xanh NEU AI."""
    return "courses"


@app.route("/users/<int:user_id>/profile", methods=["GET", "PATCH"])
def user_profile(user_id):
    """Self-service profile: gender, birth year, theme, avatar meta."""
    with get_db() as conn:
        from seed_org import get_user_access

        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, email, is_admin, is_locked, gender, birth_year, "
            "avatar_path, theme, theme_manual FROM user WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            return json_error("User not found", 404)
        if request.method == "GET":
            access = get_user_access(conn, user_id)
            user = row_to_user(row)
            user["theme"] = access.get("theme") or user.get("theme") or "courses"
            user["theme_manual"] = bool(access.get("theme_manual"))
            return jsonify(user)

        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        gender_raw = data.get("gender")
        gender = (gender_raw or "").strip().upper() if gender_raw is not None else None
        if gender in ("FEMALE", "NỮ", "NU", "Nữ"):
            gender = "F"
        elif gender in ("MALE", "NAM", "Nam"):
            gender = "M"
        elif gender not in (None, "", "F", "M"):
            return json_error("Giới tính không hợp lệ (F/M).", 400)

        birth_year = data.get("birth_year")
        if birth_year is not None and birth_year != "":
            try:
                birth_year = int(birth_year)
            except (TypeError, ValueError):
                return json_error("Năm sinh không hợp lệ.", 400)
            from datetime import date

            year_now = date.today().year
            if birth_year < 1940 or birth_year > year_now - 14:
                return json_error(f"Năm sinh phải trong khoảng 1940–{year_now - 14}.", 400)
        else:
            birth_year = None

        theme_raw = data.get("theme")
        theme_set = "theme" in data
        theme = (theme_raw or "").strip() if theme_raw is not None else None
        if theme_set and theme not in ("courses", "admin", "auto", ""):
            return json_error(
                "Theme phải là courses (xanh NEU AI) hoặc auto.",
                400,
            )

        keys = row.keys()
        cur_manual = int(row["theme_manual"] or 0) if "theme_manual" in keys else 0

        updates = []
        params: list = []
        if name:
            updates.append("name = ?")
            params.append(name[:200])
        if gender is not None:
            updates.append("gender = ?")
            params.append(gender or None)
        if "birth_year" in data:
            updates.append("birth_year = ?")
            params.append(birth_year)

        # Toàn bộ chức năng: luôn theme xanh NEU AI
        if theme_set or gender is not None or name or "birth_year" in data:
            updates.append("theme = ?")
            params.append("courses")
            updates.append("theme_manual = 0")
            cur_manual = 0

        if not updates:
            return json_error("Không có thay đổi.", 400)
        params.append(user_id)
        cur.execute(f"UPDATE user SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        access = get_user_access(conn, user_id)
        cur.execute(
            "SELECT id, name, email, is_admin, is_locked, gender, birth_year, "
            "avatar_path, theme, theme_manual FROM user WHERE id = ?",
            (user_id,),
        )
        updated = row_to_user(cur.fetchone())
        updated["theme"] = access.get("theme") or updated.get("theme") or "courses"
        updated["theme_manual"] = bool(access.get("theme_manual"))
    return jsonify(updated)


@app.route("/users/<int:user_id>/avatar", methods=["POST", "DELETE"])
def user_avatar(user_id):
    """Upload or remove profile avatar image."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, avatar_path FROM user WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return json_error("User not found", 404)

        avatar_dir = UPLOADS_DIR / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)

        def _avatar_file(rel: str) -> Path:
            safe = str(rel or "").replace("\\", "/").lstrip("/")
            if ".." in safe.split("/"):
                return avatar_dir / "_invalid_"
            if not safe.startswith("avatars/"):
                safe = f"avatars/{Path(safe).name}"
            return UPLOADS_DIR / safe

        if request.method == "DELETE":
            old = row["avatar_path"] if "avatar_path" in row.keys() else None
            if old:
                try:
                    p = _avatar_file(old)
                    if p.exists() and p.is_file():
                        p.unlink()
                except OSError:
                    pass
            cur.execute("UPDATE user SET avatar_path = NULL WHERE id = ?", (user_id,))
            conn.commit()
            return jsonify({"ok": True, "avatar_path": None, "avatar_url": None})

        f = request.files.get("avatar") or request.files.get("file")
        if not f or not f.filename:
            return json_error("Cần chọn file ảnh avatar.", 400)
        ext = Path(f.filename).suffix.lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            return json_error("Chỉ nhận ảnh JPG, PNG, WEBP, GIF.", 400)
        old = row["avatar_path"] if "avatar_path" in row.keys() else None
        if old:
            try:
                op = _avatar_file(old)
                if op.exists() and op.is_file():
                    op.unlink()
            except OSError:
                pass
        import uuid as _uuid

        safe = f"{user_id}_{_uuid.uuid4().hex[:12]}{ext}"
        rel = f"avatars/{safe}"
        dest = avatar_dir / safe
        f.save(str(dest))
        cur.execute("UPDATE user SET avatar_path = ? WHERE id = ?", (rel, user_id))
        conn.commit()
    return jsonify({"ok": True, "avatar_path": rel, "avatar_url": f"/api/uploads/{rel}"})


@app.route("/uploads/<path:relpath>", methods=["GET"])
def serve_upload(relpath):
    """Serve files under uploads/ (avatars, materials…)."""
    from flask import send_from_directory

    safe = Path(relpath).as_posix()
    if ".." in safe.split("/"):
        return json_error("Invalid path", 400)
    full = UPLOADS_DIR / safe
    if not full.exists() or not full.is_file():
        return json_error("Not found", 404)
    return send_from_directory(full.parent, full.name)


@app.route("/users", methods=["GET"])
def get_users():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, is_admin, is_locked FROM user ORDER BY name")
        rows = cur.fetchall()
        dept_map = _user_departments_map(conn)
        scope_map: dict[int, list[str]] = {}
        try:
            for r in cur.execute(
                "SELECT user_id, program_code FROM user_program_scopes ORDER BY program_code"
            ):
                scope_map.setdefault(r[0], []).append(r[1])
        except sqlite3.OperationalError:
            pass
        result = []
        for r in rows:
            u = row_to_user(r)
            u["departments"] = dept_map.get(r["id"], [])
            u["program_scopes"] = scope_map.get(r["id"], [])
            result.append(u)
        return jsonify(apply_qa_rows("user", result))


@app.route("/users/<int:user_id>/access", methods=["GET"])
def get_user_access_api(user_id):
    """Return departments, permissions, program scopes + nav groups for one user."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, is_admin, is_locked FROM user WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return json_error("User not found", 404)
        from seed_org import get_user_access
        from rbac import build_nav_from_permissions

        access = get_user_access(conn, user_id)
    user = row_to_user(row)
    user.update(access)
    lang = (request.args.get("lang") or access.get("lang") or "vi").strip().lower()
    if lang not in ("vi", "en"):
        lang = "vi"
    dept_only = {d.get("code") for d in (access.get("departments") or []) if d.get("code")}
    if dept_only == {"mba"}:
        lang = "en"
    user["nav"] = build_nav_from_permissions(
        access["permission_codes"],
        lang=lang,
        departments=access.get("departments"),
    )
    user["nav_lang"] = lang
    return jsonify(user)


@app.route("/users/<int:user_id>/scopes", methods=["PUT"])
def put_user_scopes(user_id):
    """Replace program scopes for a user. Body: {scopes: ['MBA','MMS'] or ['*']}."""
    data = request.get_json(silent=True) or {}
    scopes = data.get("scopes")
    if not isinstance(scopes, list):
        return json_error("scopes must be a list", 400)
    scopes = [str(s).strip() for s in scopes if str(s).strip()]
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM user WHERE id = ?", (user_id,))
        if not cur.fetchone():
            return json_error("User not found", 404)
        cur.execute("DELETE FROM user_program_scopes WHERE user_id = ?", (user_id,))
        for sc in scopes:
            cur.execute(
                "INSERT INTO user_program_scopes (user_id, program_code) VALUES (?, ?)",
                (user_id, sc),
            )
        conn.commit()
    return jsonify({"ok": True, "scopes": scopes})


@app.route("/users/<int:user_id>/admin-reset-password", methods=["POST"])
def admin_reset_user_password(user_id):
    """Admin sets a new password for another user (no current-password check)."""
    data = request.get_json(silent=True) or {}
    new_password = data.get("new_password") or ""
    if not new_password:
        return json_error("new_password is required", 400)
    if len(new_password) < 4:
        return json_error("New password must be at least 4 characters", 400)
    with get_db() as conn:
        denied = _deny_unless(conn, "admin.users")
        if denied:
            return denied
        cur = conn.cursor()
        cur.execute("SELECT id FROM user WHERE id = ?", (user_id,))
        if not cur.fetchone():
            return json_error("User not found", 404)
        cur.execute("UPDATE user SET password = ? WHERE id = ?", (new_password, user_id))
        conn.commit()
        from student_accounts import set_must_change

        set_must_change(conn, user_id, True)
    return jsonify({"ok": True, "message": "Password reset", "must_change_password": True})


@app.route("/users/<int:user_id>/departments", methods=["PUT"])
def put_user_departments(user_id):
    """Replace user department memberships. Body: {department_ids: [1,2,...]}."""
    data = request.get_json(silent=True) or {}
    dept_ids = data.get("department_ids")
    if not isinstance(dept_ids, list):
        return json_error("department_ids must be a list", 400)
    clean_ids = []
    for d in dept_ids:
        try:
            clean_ids.append(int(d))
        except (TypeError, ValueError):
            continue
    with get_db() as conn:
        cur = conn.cursor()
        from seed_org import ensure_rbac_tables

        ensure_rbac_tables(cur)
        cur.execute("SELECT id FROM user WHERE id = ?", (user_id,))
        if not cur.fetchone():
            return json_error("User not found", 404)
        if clean_ids:
            placeholders = ",".join("?" * len(clean_ids))
            cur.execute(
                f"SELECT id FROM departments WHERE id IN ({placeholders})",
                clean_ids,
            )
            valid = {r[0] for r in cur.fetchall()}
            clean_ids = [i for i in clean_ids if i in valid]
        cur.execute("DELETE FROM user_departments WHERE user_id = ?", (user_id,))
        for did in clean_ids:
            cur.execute(
                "INSERT OR IGNORE INTO user_departments (user_id, department_id) VALUES (?, ?)",
                (user_id, did),
            )
        conn.commit()
    return jsonify({"ok": True, "department_ids": clean_ids})


@app.route("/users/<int:user_id>/permissions", methods=["GET"])
def get_user_permissions(user_id):
    """Catalog + direct grants + effective permissions for one user."""
    with get_db() as conn:
        cur = conn.cursor()
        from seed_org import ensure_rbac_tables, get_user_access

        ensure_rbac_tables(cur)
        cur.execute("SELECT id, name, email, is_admin, is_locked FROM user WHERE id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return json_error("User not found", 404)
        access = get_user_access(conn, user_id)
        direct = set(access.get("direct_permission_codes") or [])
        effective = set(access.get("permission_codes") or [])
        cur.execute(
            "SELECT code, label, group_name, route, sort_order FROM permissions ORDER BY sort_order"
        )
        catalog = [
            {
                "code": r[0],
                "label": r[1],
                "group": r[2],
                "route": r[3],
                "sort": r[4],
                "direct": r[0] in direct,
                "effective": r[0] in effective,
            }
            for r in cur.fetchall()
        ]
    return jsonify(
        {
            "user": row_to_user(row),
            "direct_permission_codes": list(direct),
            "permission_codes": list(effective),
            "catalog": catalog,
            "departments": access.get("departments") or [],
        }
    )


@app.route("/users/<int:user_id>/permissions", methods=["PUT"])
def put_user_permissions(user_id):
    """Replace direct user permission grants. Body: {permissions: ['code', ...]}."""
    data = request.get_json(silent=True) or {}
    perms = data.get("permissions")
    if not isinstance(perms, list):
        return json_error("permissions must be a list", 400)
    perms = [str(p).strip() for p in perms if str(p).strip()]
    with get_db() as conn:
        cur = conn.cursor()
        from seed_org import ensure_rbac_tables

        ensure_rbac_tables(cur)
        cur.execute("SELECT id FROM user WHERE id = ?", (user_id,))
        if not cur.fetchone():
            return json_error("User not found", 404)
        cur.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
        for code in perms:
            cur.execute(
                "INSERT OR IGNORE INTO user_permissions (user_id, permission_code) VALUES (?, ?)",
                (user_id, code),
            )
        conn.commit()
    return jsonify({"ok": True, "permissions": perms})


@app.route("/departments", methods=["GET"])
def get_departments():
    """List departments with member counts."""
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT d.id, d.code, d.name, d.sort_order, "
                "COUNT(ud.user_id) AS member_count "
                "FROM departments d "
                "LEFT JOIN user_departments ud ON ud.department_id = d.id "
                "GROUP BY d.id "
                "ORDER BY d.sort_order, d.name"
            )
            rows = cur.fetchall()
        except sqlite3.OperationalError:
            return jsonify([])
    return jsonify(
        apply_qa_rows(
            "department",
            [
                {
                    "id": r["id"],
                    "code": r["code"],
                    "name": r["name"],
                    "sort_order": r["sort_order"],
                    "member_count": r["member_count"],
                }
                for r in rows
            ],
        )
    )


@app.route("/departments", methods=["POST"])
def create_department():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip().lower().replace(" ", "_")
    name = (data.get("name") or "").strip()
    if not code or not name:
        return json_error("Cần mã và tên bộ phận.", 400)
    try:
        sort_order = int(data.get("sort_order") or 100)
    except (TypeError, ValueError):
        sort_order = 100
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not actor["is_admin"] and "admin.departments" not in actor.get("permission_codes", []):
            return json_error("Bạn không có quyền admin.departments.", 403)
        cur = conn.cursor()
        exists = cur.execute("SELECT id FROM departments WHERE code = ?", (code,)).fetchone()
        if exists:
            return json_error("Mã bộ phận đã tồn tại.", 400)
        cur.execute(
            "INSERT INTO departments (code, name, sort_order) VALUES (?, ?, ?)",
            (code, name, sort_order),
        )
        conn.commit()
        dept_id = cur.lastrowid
    return jsonify(
        {"id": dept_id, "code": code, "name": name, "sort_order": sort_order, "member_count": 0}
    ), 201


@app.route("/departments/<int:dept_id>/users", methods=["GET"])
def get_department_users(dept_id):
    """List users in a department."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, code, name FROM departments WHERE id = ?", (dept_id,))
        dept = cur.fetchone()
        if not dept:
            return json_error("Department not found", 404)
        cur.execute(
            "SELECT u.id, u.name, u.email, u.is_admin, u.is_locked "
            "FROM user u "
            "JOIN user_departments ud ON ud.user_id = u.id "
            "WHERE ud.department_id = ? "
            "ORDER BY u.name",
            (dept_id,),
        )
        rows = cur.fetchall()
    return jsonify(
        {
            "department": {"id": dept["id"], "code": dept["code"], "name": dept["name"]},
            "users": [row_to_user(r) for r in rows],
        }
    )


@app.route("/departments/<int:dept_id>/permissions", methods=["GET"])
def get_department_permissions(dept_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, code, name FROM departments WHERE id = ?", (dept_id,))
        dept = cur.fetchone()
        if not dept:
            return json_error("Department not found", 404)
        cur.execute(
            "SELECT permission_code FROM department_permissions WHERE department_id = ?",
            (dept_id,),
        )
        codes = [r[0] for r in cur.fetchall()]
        cur.execute(
            "SELECT code, label, group_name, route, sort_order FROM permissions ORDER BY sort_order"
        )
        catalog = [
            {
                "code": r[0],
                "label": r[1],
                "group": r[2],
                "route": r[3],
                "sort": r[4],
                "granted": r[0] in codes,
            }
            for r in cur.fetchall()
        ]
    return jsonify(
        {
            "department": {"id": dept["id"], "code": dept["code"], "name": dept["name"]},
            "permission_codes": codes,
            "catalog": catalog,
        }
    )


@app.route("/departments/<int:dept_id>/permissions", methods=["PUT"])
def put_department_permissions(dept_id):
    """Replace department permissions. Body: {permissions: ['code', ...]}."""
    data = request.get_json(silent=True) or {}
    perms = data.get("permissions")
    if not isinstance(perms, list):
        return json_error("permissions must be a list", 400)
    perms = [str(p).strip() for p in perms if str(p).strip()]
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM departments WHERE id = ?", (dept_id,))
        if not cur.fetchone():
            return json_error("Department not found", 404)
        cur.execute("DELETE FROM department_permissions WHERE department_id = ?", (dept_id,))
        for code in perms:
            cur.execute(
                "INSERT OR IGNORE INTO department_permissions (department_id, permission_code) "
                "VALUES (?, ?)",
                (dept_id, code),
            )
        conn.commit()
    return jsonify({"ok": True, "permissions": perms})


@app.route("/permissions", methods=["GET"])
def list_permissions():
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT code, label, group_name, route, sort_order FROM permissions ORDER BY sort_order"
            )
            rows = cur.fetchall()
        except sqlite3.OperationalError:
            return jsonify([])
    return jsonify(
        [
            {
                "code": r[0],
                "label": r[1],
                "group": r[2],
                "route": r[3],
                "sort": r[4],
            }
            for r in rows
        ]
    )


@app.route("/programs", methods=["GET"])
def list_programs():
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute("SELECT code, name FROM programs ORDER BY code")
            rows = cur.fetchall()
        except sqlite3.OperationalError:
            return jsonify([])
    return jsonify([{"code": r[0], "name": r[1]} for r in rows])


def _parse_scopes_from_request() -> list[str] | None:
    raw = request.args.get("scopes") or request.headers.get("X-Program-Scopes") or ""
    if not raw or raw.strip() == "*":
        return ["*"]
    return [s.strip() for s in raw.split(",") if s.strip()]


def _scopes_for_accounting(actor: dict | None = None) -> list[str]:
    """Kế toán / Thủ quỹ: luôn toàn bộ chương trình (không bị scope CT của vai trò kèm)."""
    from workflow_links import scopes_for_accounting

    if actor and actor.get("ok"):
        return scopes_for_accounting(
            actor.get("dept_codes"),
            actor.get("program_scopes"),
            is_admin=bool(actor.get("is_admin")),
        )
    return _parse_scopes_from_request() or ["*"]


def _resolve_ops_actor(conn) -> dict:
    """
    Resolve departments / scopes / permissions from authenticated user id.
    Prefer X-User-Id (from frontend session); never trust client-supplied dept lists alone.
    """
    from seed_org import get_user_access

    uid_raw = request.headers.get("X-User-Id") or request.args.get("user_id") or ""
    try:
        user_id = int(uid_raw)
    except (TypeError, ValueError):
        user_id = None
    if not user_id:
        return {
            "user_id": None,
            "dept_codes": [],
            "program_scopes": [],
            "permission_codes": [],
            "is_admin": False,
            "ok": False,
            "error": "Thiếu định danh người dùng (X-User-Id).",
        }
    access = get_user_access(conn, user_id)
    dept_codes = [d.get("code") for d in (access.get("departments") or []) if d.get("code")]
    if access.get("is_admin") and "admin_he_thong" not in dept_codes:
        dept_codes = list({*dept_codes, "admin_he_thong"})
    return {
        "user_id": user_id,
        "dept_codes": dept_codes,
        "program_scopes": access.get("program_scopes") or [],
        "permission_codes": access.get("permission_codes") or [],
        "is_admin": bool(access.get("is_admin")),
        "ok": True,
        "error": None,
    }


def _round_doc_actor_caps(conn) -> tuple[dict, dict]:
    actor = _resolve_ops_actor(conn)
    from admission_ops import round_doc_caps

    return actor, round_doc_caps(actor if actor.get("ok") else None)


def _actor_owns_application(conn, actor: dict, application_id: int) -> bool:
    if not actor or not actor.get("ok") or not actor.get("user_id") or not application_id:
        return False
    from e2e_pipeline import resolve_student_identity

    ident = resolve_student_identity(conn, user_id=actor["user_id"])
    app = (ident or {}).get("application") or {}
    return int(app.get("id") or 0) == int(application_id)


def _app_doc_actor_caps(conn, application_id: int | None = None) -> tuple[dict, dict]:
    actor = _resolve_ops_actor(conn)
    owns = False
    if application_id and actor.get("ok"):
        owns = _actor_owns_application(conn, actor, application_id)
    from admission_ops import app_doc_caps

    return actor, app_doc_caps(actor if actor.get("ok") else None, owns=owns)


@app.route("/ops/summary", methods=["GET"])
def ops_summary():
    """Dashboard counts + cross-dept pipeline for BGD / Trợ lý / Admin."""
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        cur = conn.cursor()
        from ops_data import _scopes_sql

        frag_a, params_a = _scopes_sql(scopes, "program_code")
        frag_ef, params_ef = _scopes_sql(scopes, "a.program_code")

        def safe_count(sql, params=None):
            try:
                return cur.execute(sql, params or []).fetchone()[0]
            except sqlite3.OperationalError:
                return 0

        def safe_rows(sql, params=None):
            try:
                return cur.execute(sql, params or []).fetchall()
            except sqlite3.OperationalError:
                return []

        faculty_count = safe_count("SELECT COUNT(*) FROM faculty")
        applications = safe_count(
            f"SELECT COUNT(*) FROM applications WHERE {frag_a}", params_a
        )
        fees_pending = safe_count(
            "SELECT COUNT(*) FROM enrollment_fees ef "
            "JOIN applications a ON a.id = ef.application_id "
            f"WHERE ef.status = 'pending' AND {frag_ef}",
            params_ef,
        )
        fees_paid = safe_count(
            "SELECT COUNT(*) FROM enrollment_fees ef "
            "JOIN applications a ON a.id = ef.application_id "
            f"WHERE ef.status IN ('paid','verified','Da thanh toan') AND {frag_ef}",
            params_ef,
        )
        classes = safe_count(
            f"SELECT COUNT(*) FROM class_groups WHERE {frag_a}", params_a
        )
        alumni = safe_count(
            f"SELECT COUNT(*) FROM alumni_members WHERE {frag_a}", params_a
        )
        frag_cg, params_cg = _scopes_sql(scopes, "cg.program_code")
        students_active = safe_count(
            "SELECT COUNT(*) FROM class_students cs "
            "JOIN class_groups cg ON cg.id = cs.class_id "
            f"WHERE COALESCE(cs.lifecycle_status,'active') IN ('active','') AND {frag_cg}",
            params_cg,
        )
        students_total = safe_count(
            "SELECT COUNT(*) FROM class_students cs "
            "JOIN class_groups cg ON cg.id = cs.class_id "
            f"WHERE {frag_cg}",
            params_cg,
        )

        # Application pipeline by status (liên thông TS → ĐP → KT)
        status_rows = safe_rows(
            f"SELECT COALESCE(status,''), COUNT(*) FROM applications "
            f"WHERE {frag_a} GROUP BY COALESCE(status,'')",
            params_a,
        )
        by_status = {str(r[0] or "unknown"): int(r[1]) for r in status_rows}

        pipeline_order = [
            ("submitted", "Đã nộp"),
            ("approved_ts", "TS duyệt"),
            ("interview", "Phỏng vấn"),
            ("passed", "Đỗ"),
            ("failed", "Trượt"),
            ("paid", "Đã nộp phí"),
            ("official", "Nhập học"),
            ("withdrawn", "Rút HS"),
        ]
        pipeline = [
            {"code": code, "label": label, "count": int(by_status.get(code, 0))}
            for code, label in pipeline_order
        ]
        # Include any other statuses present
        known = {c for c, _ in pipeline_order}
        for code, cnt in sorted(by_status.items()):
            if code not in known and code:
                pipeline.append({"code": code, "label": code, "count": int(cnt)})

        # By program breakdown
        prog_apps = {
            str(r[0]): int(r[1])
            for r in safe_rows(
                f"SELECT COALESCE(program_code,''), COUNT(*) FROM applications "
                f"WHERE {frag_a} GROUP BY COALESCE(program_code,'')",
                params_a,
            )
        }
        prog_students = {
            str(r[0]): int(r[1])
            for r in safe_rows(
                "SELECT COALESCE(cg.program_code,''), COUNT(*) FROM class_students cs "
                "JOIN class_groups cg ON cg.id = cs.class_id "
                f"WHERE {frag_cg} GROUP BY COALESCE(cg.program_code,'')",
                params_cg,
            )
        }
        prog_codes = sorted(set(prog_apps) | set(prog_students) | {"MBA", "MMS", "MSCM"})
        by_program = [
            {
                "program_code": p,
                "applications": prog_apps.get(p, 0),
                "students": prog_students.get(p, 0),
            }
            for p in prog_codes
            if p
        ]

        # Assistant / shared management signals
        tasks_open = safe_count(
            "SELECT COUNT(*) FROM asst_tasks WHERE COALESCE(status,'open') "
            "IN ('open','doing','overdue','pending')"
        )
        leave_pending = safe_count(
            "SELECT COUNT(*) FROM asst_leave WHERE COALESCE(status,'pending')='pending'"
        )
        intl_faculty_prep = safe_count(
            "SELECT COUNT(*) FROM asst_intl_faculty WHERE COALESCE(status,'preparing') "
            "IN ('preparing','pending','open')"
        )

        treasury_kpis = {
            "overdue_count": 0,
            "due_soon_count": 0,
            "unpaid_count": 0,
            "overdue_students": 0,
            "alert_count": 0,
            "amount_remaining": 0,
        }
        try:
            from treasury_ops import treasury_summary

            treasury_kpis = treasury_summary(conn, scopes)
        except Exception:
            pass

        return jsonify(
            {
                "applications": applications,
                "fees_pending": fees_pending,
                "fees_paid": fees_paid,
                "classes": classes,
                "faculty": faculty_count,
                "alumni": alumni,
                "students_active": students_active,
                "students_total": students_total,
                "by_status": by_status,
                "pipeline": pipeline,
                "by_program": by_program,
                "asst": {
                    "tasks_open": tasks_open,
                    "leave_pending": leave_pending,
                    "intl_faculty_prep": intl_faculty_prep,
                },
                "fees_overdue": treasury_kpis.get("overdue_count") or 0,
                "fees_due_soon": treasury_kpis.get("due_soon_count") or 0,
                "fees_unpaid": treasury_kpis.get("unpaid_count") or 0,
                "overdue_students": treasury_kpis.get("overdue_students") or 0,
                "fee_alerts": treasury_kpis.get("alert_count") or 0,
                "tuition_remaining": treasury_kpis.get("amount_remaining") or 0,
                "scopes": scopes,
            }
        )


@app.route("/ops/admission-rounds", methods=["GET"])
def ops_admission_rounds():
    q = (request.args.get("q") or "").strip()
    program_code = (request.args.get("program_code") or "").strip()
    from status_catalog import drop_watch_or_qa_status

    status = drop_watch_or_qa_status(request.args.get("status") or "")
    year = (request.args.get("year") or "").strip()
    intake = (request.args.get("intake") or "").strip()
    with get_db() as conn:
        from admission_ops import list_admission_rounds

        return jsonify(
            apply_qa_rows(
                "round",
                list_admission_rounds(
                    conn,
                    q=q,
                    program_code=program_code,
                    status=status,
                    year=year or None,
                    intake=intake,
                ),
            )
        )


@app.route("/ops/candidate-pre-enroll", methods=["GET"])
def ops_candidate_pre_enroll():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        codes = set(actor.get("permission_codes") or [])
        if not actor["is_admin"] and "admissions.pre_enroll" not in codes:
            return json_error("Bạn không có quyền admissions.pre_enroll.", 403)
        from admission_ops import list_pre_enroll_files

        rows = list_pre_enroll_files(conn, actor.get("program_scopes") or scopes, q=q)
        program_code = (request.args.get("program_code") or "").strip().upper()
        if program_code:
            rows = [r for r in rows if (r.get("program_code") or "").upper() == program_code]
        return jsonify(rows)


@app.route("/ops/candidate-enrolled", methods=["GET"])
def ops_candidate_enrolled():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        codes = set(actor.get("permission_codes") or [])
        if not actor["is_admin"] and "admissions.enrolled_files" not in codes:
            return json_error("Bạn không có quyền admissions.enrolled_files.", 403)
        from admission_ops import list_enrolled_files

        rows = list_enrolled_files(conn, actor.get("program_scopes") or scopes, q=q)
        program_code = (request.args.get("program_code") or "").strip().upper()
        if program_code:
            rows = [r for r in rows if (r.get("program_code") or "").upper() == program_code]
        return jsonify(rows)


@app.route("/ops/applications", methods=["GET", "POST"])
def ops_applications():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        with get_db() as conn:
            actor = _resolve_ops_actor(conn)
            if not actor["ok"]:
                return json_error(actor["error"] or "Unauthorized", 401)
            if not actor["is_admin"] and "admissions.applications" not in actor["permission_codes"]:
                return json_error("Bạn không có quyền admissions.applications.", 403)
            from admission_ops import create_candidate_applications

            try:
                result = create_candidate_applications(conn, data)
            except ValueError as e:
                return json_error(str(e), 400)
        return jsonify(result), 201

    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    from status_catalog import drop_watch_or_qa_status

    status = drop_watch_or_qa_status(request.args.get("status") or "")
    role_mode = (request.args.get("role_mode") or request.headers.get("X-Role-Mode") or "all").strip()
    decision = (request.args.get("decision") or "").strip() in ("1", "true", "yes")
    round_id = request.args.get("round_id", type=int)
    intake_session = (request.args.get("intake_session") or "").strip()
    with get_db() as conn:
        from coord_ops import list_applications_enriched, seed_coord_enrichment

        seed_coord_enrichment(conn)
        neu_prep = (request.args.get("neu_prep") or "").strip() in ("1", "true", "yes")
        actor = _resolve_ops_actor(conn)
        campuses = actor.get("campus_scopes") if actor.get("ok") else None
        rows = list_applications_enriched(
            conn, scopes, q=q, status=status, role_mode=role_mode, decision=decision,
            round_id=round_id, intake_session=intake_session, neu_prep=neu_prep,
            campuses=campuses,
            dossier_status=(request.args.get("dossier_status") or "").strip(),
            selection_status=(request.args.get("selection_status") or "").strip(),
        )
        try:
            from learner_spine import annotate_applications, refresh_learner_stages

            refresh_learner_stages(conn, [int(r["id"]) for r in rows if r.get("id")])
            rows = annotate_applications(conn, rows)
        except Exception:
            pass
        from quality_ops import apply_qa

        rows = apply_qa("application", rows, qa=(request.args.get("qa") or ""))
    return jsonify(rows)


@app.route("/ops/applications/<int:app_id>", methods=["PATCH"])
def ops_application_patch(app_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not actor["is_admin"] and "admissions.applications" not in actor["permission_codes"]:
            return json_error("Bạn không có quyền admissions.applications.", 403)
        from ops_policy import can_write_perm, deny_write_message, scopes_for_perm

        if not can_write_perm(actor, "admissions.applications"):
            return json_error(deny_write_message("admissions.applications"), 403)

        cur = conn.cursor()
        cur.execute("SELECT status, program_code FROM applications WHERE id = ?", (app_id,))
        row = cur.fetchone()
        if not row:
            return json_error("Application not found", 404)
        current_status, program_code = row[0], row[1]

        from workflow_links import actor_may_mutate_program, actor_may_transition

        ok_scope, scope_msg = actor_may_mutate_program(
            scopes_for_perm(actor, "admissions.applications"), program_code
        )
        if not ok_scope:
            return json_error(scope_msg, 403)

        new_status = (data.get("status") or "").strip()
        if new_status and new_status != current_status:
            ok, msg = actor_may_transition(actor["dept_codes"], current_status, new_status)
            if not ok:
                return json_error(msg, 403)
            if new_status == "withdrawn" and not (data.get("notes") or "").strip():
                return json_error("Rút hồ sơ cần ghi chú (lý do).", 400)

        from coord_ops import update_application_profile

        if new_status and new_status != current_status and new_status == "approved_ts":
            actor_label = f"user:{actor.get('user_id')}"
            if actor.get("dept_codes"):
                actor_label += "/" + ",".join(actor["dept_codes"][:3])
            data = dict(data)
            data["_actor_label"] = actor_label

        try:
            updated = update_application_profile(conn, app_id, data)
        except ValueError as e:
            return json_error(str(e), 400)
        if not updated:
            return json_error("Application not found", 404)
    return jsonify(updated)


@app.route("/ops/applications/import", methods=["POST"])
def ops_applications_import():
    """Import candidates from JSON rows or uploaded .xlsx."""
    round_id = None
    rows = []
    if request.files.get("file"):
        f = request.files["file"]
        name = (f.filename or "").lower()
        if not name.endswith((".xlsx", ".xlsm")):
            return json_error("Chỉ nhận file Excel .xlsx", 400)
        from ops_crud import parse_applications_xlsx

        try:
            rows = parse_applications_xlsx(f.read())
        except Exception as e:
            return json_error(f"Không đọc được Excel: {e}", 400)
        round_id = request.form.get("round_id", type=int)
    else:
        data = request.get_json(silent=True) or {}
        rows = data.get("rows") or []
        round_id = data.get("round_id")
    if not isinstance(rows, list) or not rows:
        return json_error("Không có dòng dữ liệu để import", 400)
    with get_db() as conn:
        from coord_ops import import_candidates

        try:
            result = import_candidates(conn, rows, round_id=round_id)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/applications/import/template", methods=["GET"])
def ops_applications_import_template():
    from flask import Response
    from ops_crud import build_applications_import_template

    data = build_applications_import_template()
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=mau_import_ho_so_tuyen_sinh.xlsx"
        },
    )


@app.route("/ops/bulk-import/<entity>/template", methods=["GET"])
def ops_bulk_import_template(entity):
    """Download blank Excel template for a list module."""
    from flask import Response
    from ops_bulk_import import build_import_template

    try:
        data = build_import_template(entity)
    except ValueError as e:
        return json_error(str(e), 404)
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=mau_import_{entity}.xlsx"
        },
    )


@app.route("/ops/bulk-import/<entity>", methods=["POST"])
def ops_bulk_import(entity):
    """
    Import .xlsx; validate each row; return annotated workbook with Ket_qua_import column.
    Headers: X-Import-Created / Updated / Errors / Total.
    """
    from flask import Response
    from ops_bulk_import import run_import_xlsx

    f = request.files.get("file")
    if not f:
        return json_error("Thiếu file Excel (.xlsx)", 400)
    raw = f.read()
    if not raw:
        return json_error("File trống", 400)
    round_id = request.form.get("round_id", type=int) or None
    with get_db() as conn:
        try:
            out_bytes, stats = run_import_xlsx(conn, entity, raw, round_id=round_id)
        except ValueError as e:
            return json_error(str(e), 400)
        except Exception as e:
            return json_error(str(e), 400)
    return Response(
        out_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=ket_qua_import_{entity}.xlsx",
            "X-Import-Created": str(stats.get("created", 0)),
            "X-Import-Updated": str(stats.get("updated", 0)),
            "X-Import-Errors": str(stats.get("errors", 0)),
            "X-Import-Total": str(stats.get("total", 0)),
            "Access-Control-Expose-Headers": (
                "X-Import-Created, X-Import-Updated, X-Import-Errors, X-Import-Total, Content-Disposition"
            ),
        },
    )


@app.route("/ops/bulk-delete", methods=["POST"])
def ops_bulk_delete():
    """Delete multiple rows: {delete_path: 'asst/tasks'|..., ids: [1,2,3]}."""
    data = request.get_json(silent=True) or {}
    delete_path = (data.get("delete_path") or data.get("path") or "").strip()
    ids = data.get("ids") or []
    if not delete_path:
        return json_error("Thiếu delete_path", 400)
    if not isinstance(ids, list) or not ids:
        return json_error("Thiếu danh sách ids", 400)
    with get_db() as conn:
        from ops_bulk_import import bulk_delete_rows

        try:
            result = bulk_delete_rows(conn, delete_path, ids)
        except Exception as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/mba/written-exam/assign-numbers", methods=["POST"])
def ops_mba_assign_written_exam_numbers():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from mba_ops import assign_written_exam_numbers

        try:
            result = assign_written_exam_numbers(
                conn,
                round_id=data.get("round_id"),
                program_code=(data.get("program_code") or "MBA").strip() or "MBA",
                prefix=(data.get("prefix") or "").strip() or None,
                start=int(data.get("start") or 1),
                preview=bool(data.get("preview")),
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/mba/scores/import", methods=["POST"])
def ops_mba_import_scores():
    """Import written / interview conclusion scores (JSON rows or Excel)."""
    program_code = "MBA"
    rows = []
    if request.files.get("file"):
        f = request.files["file"]
        name = (f.filename or "").lower()
        if not name.endswith((".xlsx", ".xlsm", ".csv")):
            return json_error("Accept .xlsx or .csv", 400)
        program_code = (request.form.get("program_code") or "MBA").strip() or "MBA"
        if name.endswith(".csv"):
            import csv
            import io

            text = f.read().decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            rows = [dict(r) for r in reader]
        else:
            from ops_crud import parse_applications_xlsx

            try:
                rows = parse_applications_xlsx(f.read())
            except Exception as e:
                return json_error(f"Cannot read Excel: {e}", 400)
    else:
        data = request.get_json(silent=True) or {}
        rows = data.get("rows") or []
        program_code = (data.get("program_code") or "MBA").strip() or "MBA"
    if not isinstance(rows, list) or not rows:
        return json_error("No rows to import", 400)
    with get_db() as conn:
        from mba_ops import import_round_scores

        try:
            result = import_round_scores(conn, rows, program_code=program_code)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/mba/interview-boards", methods=["POST"])
def ops_mba_create_interview_boards():
    data = request.get_json(silent=True) or {}
    round_id = data.get("round_id")
    if not round_id:
        return json_error("round_id required", 400)
    raw_ids = data.get("application_ids") or []
    if isinstance(raw_ids, str):
        raw_ids = [x for x in raw_ids.replace(";", ",").split(",") if x.strip()]
    application_ids = []
    for x in raw_ids:
        try:
            application_ids.append(int(str(x).strip()))
        except (TypeError, ValueError):
            continue
    with get_db() as conn:
        from mba_ops import create_interview_boards, interview_board_defaults

        program_code = (data.get("program_code") or "MBA").strip() or "MBA"
        defaults = interview_board_defaults(program_code)
        board_count = data.get("board_count")
        max_per_board = data.get("max_per_board")
        try:
            result = create_interview_boards(
                conn,
                round_id=int(round_id),
                program_code=program_code,
                board_count=int(board_count) if board_count not in (None, "") else defaults["board_count"],
                room_prefix=(data.get("room_prefix") or "Room").strip() or "Room",
                starts_at=data.get("starts_at"),
                slot_minutes=int(data.get("slot_minutes") or 20),
                max_per_board=int(max_per_board) if max_per_board not in (None, "") else defaults["max_per_board"],
                queue_confirm_emails=str(
                    data.get("queue_confirm_emails", "1")
                ).lower()
                not in ("0", "false", "no", "off"),
                application_ids=application_ids or None,
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/mba/attendance/notify-ineligible", methods=["POST"])
def ops_mba_notify_ineligible():
    scopes = _parse_scopes_from_request()
    data = request.get_json(silent=True) or {}
    max_pct = float(data.get("max_absent_pct") or request.args.get("max_absent_pct") or 30)
    with get_db() as conn:
        from mba_ops import notify_ineligible_students

        result = notify_ineligible_students(conn, scopes, max_absent_pct=max_pct)
    return jsonify(result)


@app.route("/ops/mba/written-exam/roster", methods=["GET"])
@app.route("/ops/written-exams", methods=["GET"])
def ops_mba_written_exam_roster():
    scopes = _parse_scopes_from_request()
    round_id = request.args.get("round_id", type=int)
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        from mba_ops import list_written_exam_roster

        rows = list_written_exam_roster(conn, scopes, round_id=round_id, q=q)
        try:
            from learner_spine import annotate_applications, refresh_learner_stages

            refresh_learner_stages(conn, [int(r["id"]) for r in rows if r.get("id")])
            rows = annotate_applications(conn, rows)
        except Exception:
            pass
        from quality_ops import apply_qa

        rows = apply_qa("written_exam", rows, qa=(request.args.get("qa") or ""))
    return jsonify(rows)


@app.route("/ops/students/assign-class", methods=["POST"])
def ops_students_assign_class():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "students.manage"):
            return json_error(deny_write_message("students.manage"), 403)
        from mba_ops import assign_students_to_class

        try:
            class_id = int(data.get("class_id") or 0)
        except (TypeError, ValueError):
            return json_error("Chọn lớp học", 400)
        try:
            return jsonify(assign_students_to_class(conn, data.get("ids") or [], class_id))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/students", methods=["GET"])
def ops_students_lifecycle():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        from mba_ops import list_students_lifecycle

        actor = _resolve_ops_actor(conn)
        campuses = actor.get("campus_scopes") if actor.get("ok") else None
        rows = list_students_lifecycle(
            conn,
            scopes,
            q=q,
            campuses=campuses,
            cohort=(request.args.get("cohort") or "").strip(),
            mobility=(request.args.get("mobility") or "").strip(),
        )
        try:
            from learner_spine import annotate_class_students, refresh_from_class_students

            refresh_from_class_students(conn, [int(r["id"]) for r in rows if r.get("id")])
            rows = annotate_class_students(conn, rows)
        except Exception:
            pass
        return jsonify(rows)


@app.route("/ops/teaching-schedule/import", methods=["POST"])
def ops_teaching_schedule_import():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.schedule"):
            return json_error(deny_write_message("teaching.schedule"), 403)
        upload = request.files.get("file")
        if not upload:
            return json_error("Chọn file Excel", 400)
        from openpyxl import load_workbook
        from mba_ops import import_schedule_rooms

        wb = load_workbook(upload, data_only=True, read_only=True)
        ws = wb.active
        header = []
        parsed = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            values = ["" if c is None else str(c).strip() for c in row]
            if i == 0:
                header = values
                continue
            if not any(values):
                continue
            parsed.append(dict(zip(header, values)))
        return jsonify(import_schedule_rooms(conn, parsed))


@app.route("/ops/teaching-schedule", methods=["GET"])
def ops_teaching_schedule_api():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        from mba_ops import list_teaching_schedule

        return jsonify(list_teaching_schedule(
            conn,
            scopes,
            session_date=(request.args.get("session_date") or "").strip(),
            course_code=(request.args.get("course_code") or request.args.get("subject") or "").strip(),
            chapter=(request.args.get("chapter") or "").strip(),
        ))


@app.route("/ops/mba/attendance/eligibility", methods=["GET"])
def ops_mba_attendance_eligibility():
    scopes = _parse_scopes_from_request()
    max_pct = request.args.get("max_absent_pct", type=float) or 30.0
    only_ineligible = (request.args.get("only_ineligible") or "").lower() in ("1", "true", "yes")
    with get_db() as conn:
        from mba_ops import attendance_eligibility

        rows = attendance_eligibility(conn, scopes, max_absent_pct=max_pct)
        if only_ineligible:
            rows = [r for r in rows if not r.get("exam_eligible")]
    return jsonify(rows)


@app.route("/ops/program-versions/<int:version_id>/copy", methods=["POST"])
def ops_program_version_copy(version_id):
    data = request.get_json(silent=True) or {}
    copy_courses = data.get("copy_courses", True)
    if isinstance(copy_courses, str):
        copy_courses = copy_courses.strip().lower() not in ("0", "false", "no", "")
    with get_db() as conn:
        from mba_ops import copy_program_version

        try:
            result = copy_program_version(
                conn,
                version_id,
                new_version_code=(data.get("new_version_code") or "").strip(),
                new_name=data.get("new_name"),
                copy_courses=bool(copy_courses),
                keep_course_ids=data.get("keep_course_ids") or data.get("keep_ids"),
                drop_course_ids=data.get("drop_course_ids") or data.get("drop_ids"),
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result), 201


@app.route("/ops/program-versions/<int:version_id>/transfer-courses", methods=["POST"])
def ops_program_version_transfer_courses(version_id):
    """Copy course set into an existing version (no new program version)."""
    data = request.get_json(silent=True) or {}
    target_id = data.get("target_version_id")
    try:
        target_id = int(target_id)
    except (TypeError, ValueError):
        return json_error("target_version_id required", 400)
    replace = data.get("replace", True)
    if isinstance(replace, str):
        replace = replace.strip().lower() not in ("0", "false", "no", "")
    with get_db() as conn:
        from mba_ops import transfer_program_version_courses

        try:
            result = transfer_program_version_courses(
                conn,
                version_id,
                target_id,
                replace=bool(replace),
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/program-versions/<int:version_id>/study-status", methods=["GET"])
def ops_program_version_study_status(version_id):
    with get_db() as conn:
        from mba_ops import version_has_active_study

        return jsonify(version_has_active_study(conn, version_id))


@app.route("/ops/evaluations/<int:eval_id>/send", methods=["POST"])
def ops_evaluation_send(eval_id):
    data = request.get_json(silent=True) or {}
    target = (data.get("target") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.evaluation"):
            return json_error(deny_write_message("teaching.evaluation"), 403)
        from mba_ops import mark_evaluation_sent

        try:
            result = mark_evaluation_sent(conn, eval_id, target)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/evaluations/<int:eval_id>/close", methods=["POST"])
def ops_evaluation_close(eval_id):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.evaluation"):
            return json_error(deny_write_message("teaching.evaluation"), 403)
        from mba_ops import mark_evaluation_closed

        try:
            result = mark_evaluation_closed(conn, eval_id)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/suggestions", methods=["GET", "POST"])
def ops_suggestions():
    """List (admin/filters) or create a feature suggestion."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        with get_db() as conn:
            from suggestions import create_suggestion

            try:
                row = create_suggestion(conn, data)
            except ValueError as e:
                return json_error(str(e), 400)
        return jsonify(row), 201

    user_id = request.args.get("user_id", type=int)
    function_code = (request.args.get("function_code") or "").strip() or None
    status = (request.args.get("status") or "").strip() or None
    date_from = (request.args.get("from") or "").strip() or None
    date_to = (request.args.get("to") or "").strip() or None
    q = (request.args.get("q") or "").strip() or None
    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or 20
    if per_page not in (10, 20, 50, 100, 200):
        per_page = 20
    with get_db() as conn:
        from suggestions import count_suggestions, list_suggestions, suggestion_stats

        total = count_suggestions(
            conn,
            user_id=user_id,
            function_code=function_code,
            status=status,
            date_from=date_from,
            date_to=date_to,
            q=q,
        )
        items = list_suggestions(
            conn,
            user_id=user_id,
            function_code=function_code,
            status=status,
            date_from=date_from,
            date_to=date_to,
            q=q,
            limit=per_page,
            offset=(page - 1) * per_page,
        )
        stats = suggestion_stats(conn)
    return jsonify(
        {
            "items": apply_qa_rows("suggestion", items),
            "stats": stats,
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    )


@app.route("/ops/suggestions/<int:suggestion_id>", methods=["PATCH"])
def ops_suggestion_patch(suggestion_id):
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip()
    processed_by = (data.get("processed_by") or "").strip() or None
    with get_db() as conn:
        from suggestions import set_suggestion_status

        try:
            row = set_suggestion_status(
                conn, suggestion_id, status, processed_by=processed_by
            )
        except ValueError as e:
            return json_error(str(e), 400)
    if not row:
        return json_error("Not found", 404)
    return jsonify(row)


@app.route("/ops/suggestions/bulk-status", methods=["POST"])
def ops_suggestions_bulk_status():
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip()
    processed_by = (data.get("processed_by") or "").strip() or None
    ids = data.get("ids") or data.get("suggestion_ids") or []
    with get_db() as conn:
        from suggestions import bulk_set_suggestion_status

        try:
            result = bulk_set_suggestion_status(
                conn, ids, status, processed_by=processed_by
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/suggestions/export", methods=["GET"])
def ops_suggestions_export():
    """Export filtered suggestions to Excel (.xlsx)."""
    from io import BytesIO

    from flask import Response
    from suggestions import list_suggestions

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        import subprocess
        import sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill

    function_code = (request.args.get("function_code") or "").strip() or None
    status = (request.args.get("status") or "").strip() or None
    date_from = (request.args.get("from") or "").strip() or None
    date_to = (request.args.get("to") or "").strip() or None
    q = (request.args.get("q") or "").strip() or None
    with get_db() as conn:
        items = list_suggestions(
            conn,
            function_code=function_code,
            status=status,
            date_from=date_from,
            date_to=date_to,
            q=q,
            limit=5000,
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "De_xuat"
    headers = [
        ("id", "ID"),
        ("created_at", "Thời gian"),
        ("user_name", "Người đề xuất"),
        ("user_email", "Email"),
        ("function_code", "Mã chức năng"),
        ("relative_path", "Đường dẫn"),
        ("title", "Tiêu đề"),
        ("body", "Nội dung"),
        ("status", "Trạng thái"),
        ("processed_at", "Xử lý lúc"),
        ("processed_by", "Người xử lý"),
    ]
    ws.append([h[1] for h in headers])
    header_fill = PatternFill("solid", fgColor="085CA7")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(wrap_text=True, vertical="center")

    status_label = {"open": "Chờ xử lý", "done": "Đã xử lý"}
    for it in items:
        row = []
        for key, _ in headers:
            val = it.get(key)
            if key == "status":
                val = status_label.get(val, val)
            row.append("" if val is None else val)
        ws.append(row)

    for col in ws.columns:
        letter = col[0].column_letter
        width = 12
        for cell in col[:80]:
            width = min(max(width, len(str(cell.value or "")) + 2), 48)
        ws.column_dimensions[letter].width = width
    ws.freeze_panes = "A2"

    buf = BytesIO()
    wb.save(buf)
    data = buf.getvalue()
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=de_xuat_gop_y.xlsx",
        },
    )



@app.route("/ops/applications/<int:app_id>/status", methods=["POST"])
def ops_application_status(app_id):
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip()
    notes = (data.get("notes") or "").strip()

    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not actor["is_admin"] and "admissions.applications" not in actor["permission_codes"]:
            return json_error("Bạn không có quyền admissions.applications.", 403)

        try:
            from status_catalog import allowed_codes

            allowed_statuses = allowed_codes(conn, "application_status")
        except Exception:
            allowed_statuses = set()
        if not allowed_statuses:
            allowed_statuses = {
                "submitted", "approved_ts", "interview", "passed", "failed",
                "paid", "official", "withdrawn",
            }
        from status_catalog import WATCH_OR_QA_CODES

        if status in WATCH_OR_QA_CODES or status not in allowed_statuses:
            return json_error("Invalid status", 400)

        cur = conn.cursor()
        cur.execute("SELECT status, program_code FROM applications WHERE id = ?", (app_id,))
        row = cur.fetchone()
        if not row:
            return json_error("Application not found", 404)
        current, program_code = row[0], row[1]

        from workflow_links import actor_may_mutate_program, actor_may_transition

        ok_scope, scope_msg = actor_may_mutate_program(actor["program_scopes"], program_code)
        if not ok_scope:
            return json_error(scope_msg, 403)

        ok, msg = actor_may_transition(actor["dept_codes"], current, status)
        if not ok:
            return json_error(msg, 403)
        withdraw_reason = (data.get("withdraw_reason") or "").strip()
        if status == "withdrawn":
            from coord_ops import WITHDRAW_REASONS, ensure_coord_tables

            ensure_coord_tables(cur)
            if withdraw_reason not in WITHDRAW_REASONS:
                return json_error(
                    "Chọn lý do rút hồ sơ: không xác nhận văn bằng, hoặc có kế hoạch khác.",
                    400,
                )
            if not notes:
                return json_error("Rút hồ sơ cần ghi chú kèm lý do.", 400)
        if status == "paid":
            return json_error(
                "Xác nhận đã thu phí ghi danh trên màn Phí ghi danh (Kế toán). "
                "Không đổi trạng thái paid trực tiếp trên hồ sơ.",
                400,
            )

        from mba_ops import ensure_mba_tables
        from datetime import datetime
        from admission_ops import apply_board_decision_fields, assert_can_mark_official

        ensure_mba_tables(cur)
        if status in ("passed", "official", "paid"):
            cur.execute(
                "SELECT status, program_code, exam_eligible_flag, exam_format, "
                "written_score, interview_score, board_decision, admitted_program, final_result "
                "FROM applications WHERE id = ?",
                (app_id,),
            )
            prow = cur.fetchone()
            if prow:
                rowd = {
                    "status": prow[0], "program_code": prow[1],
                    "exam_eligible_flag": prow[2], "exam_format": prow[3],
                    "written_score": prow[4], "interview_score": prow[5],
                    "board_decision": prow[6], "admitted_program": prow[7],
                    "final_result": prow[8],
                }
                try:
                    if status == "passed":
                        apply_board_decision_fields(rowd, {"status": "passed"})
                    else:
                        assert_can_mark_official(rowd)
                except ValueError as e:
                    return json_error(str(e), 400)

        from coord_ops import ensure_coord_tables

        ensure_coord_tables(cur)
        cur.execute(
            "UPDATE applications SET status = ?, notes = COALESCE(NULLIF(?, ''), notes), "
            "withdraw_reason = CASE WHEN ? = 'withdrawn' THEN ? ELSE withdraw_reason END "
            "WHERE id = ?",
            (status, notes, status, withdraw_reason, app_id),
        )
        # TS → Điều phối: ghi nhận bàn giao
        if status == "approved_ts" and current != "approved_ts":
            actor_label = f"user:{actor.get('user_id')}"
            if actor.get("dept_codes"):
                actor_label += "/" + ",".join(actor["dept_codes"][:3])
            cur.execute(
                "UPDATE applications SET transferred_at = ?, transferred_by = ? WHERE id = ?",
                (datetime.now().isoformat(sep=" ", timespec="seconds"), actor_label, app_id),
            )
        if status == "passed":
            from treasury_ops import ensure_inscription_charge
            from admission_ops import apply_board_decision_fields

            cur.execute(
                "SELECT status, program_code, exam_eligible_flag, exam_format, "
                "written_score, interview_score, board_decision, admitted_program, final_result "
                "FROM applications WHERE id = ?",
                (app_id,),
            )
            prow = cur.fetchone()
            if prow:
                rowd = {
                    "status": prow[0], "program_code": prow[1],
                    "exam_eligible_flag": prow[2], "exam_format": prow[3],
                    "written_score": prow[4], "interview_score": prow[5],
                    "board_decision": prow[6], "admitted_program": prow[7],
                    "final_result": prow[8],
                }
                extra = apply_board_decision_fields(rowd, {"status": "passed"})
                cur.execute(
                    "UPDATE applications SET admitted_program = ?, "
                    "final_result = COALESCE(NULLIF(?, ''), final_result), "
                    "board_decision = COALESCE(NULLIF(board_decision,''), 'Trúng tuyển') "
                    "WHERE id = ?",
                    (extra.get("admitted_program") or prow[1], extra.get("final_result") or "Admitted", app_id),
                )
            ensure_inscription_charge(conn, app_id)
        if status == "failed":
            cur.execute(
                "UPDATE applications SET admitted_program = '', "
                "final_result = COALESCE(NULLIF(final_result,''), 'Non-Admitted') WHERE id = ?",
                (app_id,),
            )
        if status == "official":
            from treasury_ops import inscription_is_paid, open_tuition_plan_after_official

            if not inscription_is_paid(cur, app_id):
                return json_error(
                    "Cần Kế toán xác nhận đã thu phí ghi danh trước khi chốt nhập học.",
                    400,
                )
            open_tuition_plan_after_official(conn, app_id)
        conn.commit()
        try:
            from crm_ops import sync_profile_from_application

            sync_profile_from_application(conn, app_id)
        except Exception:
            pass
        try:
            from learner_spine import upsert_learner_for_application

            upsert_learner_for_application(conn, app_id)
            conn.commit()
        except Exception:
            pass
    return jsonify({
        "ok": True,
        "status": status,
        "handoff": msg,
        "actor_user_id": actor["user_id"],
        "actor_departments": actor["dept_codes"],
    })


def _actor_can(actor: dict, *codes: str) -> bool:
    if actor.get("is_admin"):
        return True
    granted = set(actor.get("permission_codes") or [])
    return any(code in granted for code in codes)


def _deny_unless(conn, *codes: str):
    """Server-side permission gate: the backend never trusts that the frontend already checked."""
    actor = _resolve_ops_actor(conn)
    if not actor.get("user_id"):
        return json_error(actor.get("error") or "Unauthorized", 401)
    if not _actor_can(actor, *codes):
        return json_error("Bạn không có quyền thực hiện thao tác này.", 403)
    return None


@app.route("/ops/applications/<int:app_id>/register-exam", methods=["POST"])
def ops_application_register_exam(app_id):
    """Ứng viên đăng ký thành thí sinh của đợt thi và mở lệ phí thi."""
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not _actor_can(actor, "admissions.applications", "admissions.written_exams"):
            return json_error("Bạn không có quyền đăng ký thí sinh.", 403)
        from learner_spine import register_examinee

        amount = data.get("amount")
        try:
            amount = float(amount) if amount not in (None, "") else None
        except (TypeError, ValueError):
            amount = None
        try:
            result = register_examinee(
                conn, app_id, actor=f"user:{actor.get('user_id')}",
                amount=amount, exam_board=(data.get("exam_board") or ""),
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/applications/<int:app_id>/confirm-examinee", methods=["POST"])
def ops_application_confirm_examinee(app_id):
    """Xác nhận người dự thi chính thức. Không tạo hồ sơ cá nhân mới."""
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not _actor_can(actor, "admissions.applications", "admissions.written_exams"):
            return json_error("Bạn không có quyền xác nhận người dự thi.", 403)
        from person_profile import confirm_official_examinee
        from learner_spine import upsert_learner_for_application

        try:
            result = confirm_official_examinee(
                conn,
                app_id,
                actor=f"user:{actor.get('user_id')}",
                basis=(data.get("basis") or ""),
            )
            spine = upsert_learner_for_application(conn, app_id)
            conn.commit()
        except ValueError as e:
            return json_error(str(e), 400)
    result["stage"] = spine.get("stage")
    result["stage_label"] = spine.get("stage_label")
    result["person_id"] = spine.get("person_id") or result.get("person_id")
    return jsonify(result)


@app.route("/ops/persons/<int:person_id>", methods=["GET"])
def ops_person_dossier(person_id):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from person_profile import build_dossier

        try:
            return jsonify(build_dossier(conn, person_id, actor))
        except ValueError as e:
            return json_error(str(e), 403)


@app.route("/ops/persons/by-application/<int:app_id>", methods=["GET"])
def ops_person_dossier_by_application(app_id):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from person_profile import dossier_for_application

        try:
            return jsonify(dossier_for_application(conn, app_id, actor))
        except ValueError as e:
            return json_error(str(e), 403)


@app.route("/ops/applications/<int:app_id>/exam-fee", methods=["POST"])
def ops_application_exam_fee(app_id):
    """Kế toán / điều phối xác nhận lệ phí thi. Không đổi phí ghi danh."""
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not {"ke_toan", "admin_he_thong", "it"}.intersection(actor["dept_codes"]) and not actor.get("is_admin"):
            return json_error(
                "Chỉ Kế toán xác nhận lệ phí thi. Tuyển sinh xác nhận dự thi và đăng ký nội dung thi.",
                403,
            )
        from learner_spine import mark_exam_fee_paid

        amount = data.get("amount")
        try:
            amount = float(amount) if amount not in (None, "") else None
        except (TypeError, ValueError):
            amount = None
        try:
            result = mark_exam_fee_paid(
                conn, app_id, actor=f"user:{actor.get('user_id')}", amount=amount,
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/applications/<int:app_id>/exam-board", methods=["POST"])
def ops_application_exam_board(app_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not _actor_can(actor, "admissions.written_exams", "admissions.interviews"):
            return json_error("Bạn không có quyền lập danh sách hội đồng.", 403)
        from learner_spine import list_on_exam_board

        try:
            result = list_on_exam_board(
                conn, app_id,
                exam_board=(data.get("exam_board") or ""),
                actor=f"user:{actor.get('user_id')}",
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


def _academic_allowed(actor: dict) -> bool:
    return _actor_can(
        actor, "students.academic", "students.manage", "teaching.grades", "student.progress",
    )


@app.route("/ops/academic-records", methods=["GET"])
def ops_academic_records():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not _actor_can(actor, "students.academic", "students.manage", "teaching.grades"):
            return json_error("Bạn không có quyền xem kết quả học tập.", 403)
        from learner_spine import list_academic_records
        from ops_policy import scopes_for_perm

        scopes = scopes_for_perm(actor, "students.academic") or actor.get("program_scopes") or ["*"]
        q = (request.args.get("q") or "").strip()
        semester = (request.args.get("semester") or "").strip()
        return jsonify(list_academic_records(conn, scopes, q=q, semester=semester))


@app.route("/ops/academic-records/<int:learner_id>", methods=["GET"])
def ops_academic_record_one(learner_id):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from learner_spine import academic_record, learner_id_for_user

        own = learner_id_for_user(conn, actor["user_id"]) if actor.get("user_id") else None
        if own != int(learner_id) and not _actor_can(
            actor, "students.academic", "students.manage", "teaching.grades"
        ):
            return json_error("Bạn không có quyền xem bảng điểm này.", 403)
        edition = (request.args.get("edition") or "tracking").strip() or "tracking"
        if edition not in ("official", "tracking"):
            edition = "tracking"
        try:
            doc = academic_record(
                conn,
                learner_id,
                edition=edition,
                mask_unpublished=request.args.get("mask") == "1",
            )
        except ValueError as e:
            return json_error(str(e), 404)
        if own != int(learner_id):
            from workflow_links import actor_may_mutate_program

            ok, msg = actor_may_mutate_program(
                actor.get("program_scopes") or ["*"],
                (doc.get("learner") or {}).get("program_code"),
            )
            if not ok and not actor.get("is_admin"):
                return json_error(msg, 403)
    return jsonify(doc)


@app.route("/ops/student/me/progress", methods=["GET"])
def ops_student_me_progress():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not _academic_allowed(actor) and "hoc_vien" not in (actor.get("dept_codes") or []):
            return json_error("Bạn không có quyền xem tiến độ học tập.", 403)
        from learner_spine import academic_record, learner_id_for_user

        lid = learner_id_for_user(conn, actor["user_id"])
        if not lid:
            return jsonify({"learner": None, "courses": [], "summary": {}})
        edition = (request.args.get("edition") or "tracking").strip() or "tracking"
        if edition not in ("official", "tracking"):
            edition = "tracking"
        return jsonify(academic_record(
            conn, lid, edition=edition, mask_unpublished=edition != "official",
        ))


@app.route("/ops/student/me/progress-courses", methods=["GET"])
def ops_student_me_progress_courses():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from learner_spine import academic_record, learner_id_for_user

        lid = learner_id_for_user(conn, actor["user_id"])
        if not lid:
            return jsonify([])
        doc = academic_record(conn, lid, edition="tracking", mask_unpublished=True)
        person = doc.get("learner") or {}
        summary = doc.get("summary") or {}
        rows = []
        for course in doc.get("courses") or []:
            course["id"] = course.get("course_id") or person.get("id")
            course["full_name"] = person.get("full_name")
            course["student_code"] = person.get("student_code")
            course["program_code"] = person.get("program_code")
            course["gpa_to_date"] = "" if summary.get("gpa") is None else summary.get("gpa")
            rows.append(course)
        return jsonify(rows)


@app.route("/ops/interviews", methods=["GET"])
def ops_interviews():
    scopes = _parse_scopes_from_request()
    round_id = request.args.get("round_id", type=int)
    program_code = (request.args.get("program_code") or "").strip()
    with get_db() as conn:
        cur = conn.cursor()
        from ops_data import _scopes_sql
        from coord_ops import seed_coord_enrichment

        seed_coord_enrichment(conn)
        frag, params = _scopes_sql(scopes, "s.program_code")
        extra = ""
        if round_id:
            extra += " AND s.round_id = ?"
            params.append(round_id)
        if program_code:
            extra += " AND s.program_code = ?"
            params.append(program_code)
        from ops_data import ensure_ops_tables

        ensure_ops_tables(cur)
        rows = cur.execute(
            "SELECT s.id, s.program_code, s.title, s.room, s.starts_at, s.slot_minutes, "
            "r.code, COUNT(sl.id) AS slot_count, IFNULL(s.owner,'') "
            "FROM interview_sessions s "
            "JOIN admission_rounds r ON r.id = s.round_id "
            "LEFT JOIN interview_slots sl ON sl.session_id = s.id "
            f"WHERE {frag}{extra} "
            "GROUP BY s.id ORDER BY s.starts_at",
            params,
        ).fetchall()
    return jsonify(
        apply_qa_rows(
            "interview",
            [
                {
                    "id": r[0],
                    "program_code": r[1],
                    "title": r[2],
                    "room": r[3],
                    "starts_at": r[4],
                    "slot_minutes": r[5],
                    "round_code": r[6],
                    "slot_count": r[7],
                    "owner": r[8] if len(r) > 8 else "",
                }
                for r in rows
            ],
        )
    )


@app.route("/ops/interviews/<int:session_id>", methods=["GET"])
def ops_interview_detail(session_id):
    with get_db() as conn:
        from coord_ops import get_interview_session_detail, seed_coord_enrichment

        seed_coord_enrichment(conn)
        detail = get_interview_session_detail(conn, session_id)
        if not detail:
            return json_error("Interview session not found", 404)
    return jsonify(detail)


@app.route("/ops/interview-slots/<int:slot_id>/scores", methods=["POST"])
def ops_interview_slot_scores(slot_id):
    data = request.get_json(silent=True) or {}
    scores = data.get("scores") or {}
    if not isinstance(scores, dict):
        return json_error("scores must be an object {jury_name: score}", 400)
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        coord_depts = {"mba", "master_chuyen_nganh", "admin_he_thong", "it"}
        if not coord_depts.intersection(actor["dept_codes"]):
            return json_error(
                "Chỉ Điều phối chương trình được nhập điểm / kết luận phỏng vấn.",
                403,
            )

        cur = conn.cursor()
        cur.execute(
            "SELECT s.application_id, a.status, a.program_code FROM interview_slots s "
            "JOIN applications a ON a.id = s.application_id WHERE s.id = ?",
            (slot_id,),
        )
        row = cur.fetchone()
        if not row:
            return json_error("Slot not found", 404)
        app_id, app_status, program_code = row[0], row[1], row[2]
        from workflow_links import actor_may_mutate_program, actor_may_transition

        ok_scope, scope_msg = actor_may_mutate_program(actor["program_scopes"], program_code)
        if not ok_scope:
            return json_error(scope_msg, 403)

        result = (data.get("result") or "").strip().lower()
        if result in ("passed", "failed"):
            ok, msg = actor_may_transition(actor["dept_codes"], app_status, result)
            if not ok:
                return json_error(msg, 403)

        from coord_ops import save_interview_slot_scores

        try:
            detail = save_interview_slot_scores(
                conn,
                slot_id,
                scores=scores,
                result=data.get("result"),
                score_conclusion=data.get("score_conclusion"),
                notes=data.get("notes"),
            )
        except Exception as e:
            return json_error(str(e), 400)
        if not detail:
            return json_error("Slot not found", 404)
    return jsonify(detail)


@app.route("/ops/classes/<int:class_id>/grades", methods=["GET"])
def ops_class_grades(class_id):
    with get_db() as conn:
        from coord_ops import get_class_gradebook, seed_coord_enrichment

        seed_coord_enrichment(conn)
        book = get_class_gradebook(conn, class_id)
        if not book:
            return json_error("Class not found", 404)
    return jsonify(book)


@app.route("/ops/classes/<int:class_id>/grades", methods=["POST"])
def ops_class_grades_upsert(class_id):
    data = request.get_json(silent=True) or {}
    try:
        student_id = int(data["student_id"])
        course_id = int(data["course_id"])
    except (KeyError, TypeError, ValueError):
        return json_error("student_id and course_id required", 400)
    score = data.get("score")
    if score is not None and score != "":
        try:
            score = float(score)
        except (TypeError, ValueError):
            return json_error("Invalid score", 400)
    else:
        score = None

    def _opt_float(key):
        v = data.get(key)
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid {key}")

    try:
        group_assignment = _opt_float("group_assignment")
        final_exam = _opt_float("final_exam")
        component_score = _opt_float("component_score")
    except ValueError as e:
        return json_error(str(e), 400)
    component_id = None
    if data.get("component_id") not in (None, ""):
        try:
            component_id = int(data["component_id"])
        except (TypeError, ValueError):
            return json_error("Invalid component_id", 400)

    with get_db() as conn:
        from coord_ops import upsert_grade

        try:
            book = upsert_grade(
                conn,
                class_id,
                student_id,
                course_id,
                score=score,
                locked=data.get("locked"),
                observations=data.get("observations"),
                group_assignment=group_assignment,
                final_exam=final_exam,
                anonymous_no=data.get("anonymous_no"),
                remarks=data.get("remarks"),
                retake=bool(data.get("retake")),
                actor=str(request.headers.get("X-User-Id") or ""),
                component_id=component_id,
                component_score=component_score,
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(book)


@app.route("/ops/classes/<int:class_id>/grades/lock", methods=["POST"])
def ops_class_grades_lock(class_id):
    data = request.get_json(silent=True) or {}
    locked = data.get("locked", True)
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        depts = set(actor.get("dept_codes") or [])
        codes = set(actor.get("permission_codes") or [])
        coord = bool(depts & {"mba", "master_chuyen_nganh"})
        if not actor.get("is_admin") and not (
            coord and "teaching.grades.publish" in codes
        ):
            from rbac import DEPT_DEFAULT_PERMISSIONS
            granted = any(
                "teaching.grades.publish" in (DEPT_DEFAULT_PERMISSIONS.get(d) or [])
                for d in depts & {"mba", "master_chuyen_nganh"}
            )
            if not actor.get("is_admin") and not (coord and granted):
                return json_error("Bạn không có quyền công bố điểm.", 403)
        from coord_ops import lock_class_grades

        book = lock_class_grades(
            conn, class_id, locked=bool(locked), actor=str(actor.get("user_id") or ""),
        )
        if not book:
            return json_error("Class not found", 404)
    return jsonify(book)


@app.route("/ops/class-students/<int:student_id>", methods=["PATCH"])
def ops_class_student_patch(student_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        denied = _deny_unless(conn, "classes.manage", "teaching.grades", "students.manage")
        if denied:
            return denied
        from coord_ops import update_student_grade_meta

        try:
            update_student_grade_meta(conn, student_id, data)
        except ValueError as e:
            return json_error(str(e), 400)
        try:
            from learner_spine import refresh_from_class_students

            refresh_from_class_students(conn, [student_id])
        except Exception:
            pass
        account = {}
        if "lifecycle_status" in data:
            from student_accounts import sync_with_lifecycle

            account = sync_with_lifecycle(conn, student_id)
    return jsonify({"ok": True, "account": account})


@app.route("/ops/thesis-records", methods=["GET"])
def ops_thesis_records():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        from coord_ops import list_thesis_records, seed_coord_enrichment

        seed_coord_enrichment(conn)
        rows = list_thesis_records(conn, scopes, q=q)
    return jsonify(rows)


@app.route("/ops/thesis-records", methods=["POST"])
def ops_thesis_records_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from coord_ops import upsert_thesis_record

        try:
            row = upsert_thesis_record(conn, data)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/thesis-records/<int:thesis_id>", methods=["GET", "PATCH"])
def ops_thesis_record_one(thesis_id):
    with get_db() as conn:
        from coord_ops import get_thesis_record, upsert_thesis_record

        if request.method == "GET":
            row = get_thesis_record(conn, thesis_id)
            if not row:
                return json_error("Not found", 404)
            return jsonify(row)
        data = request.get_json(silent=True) or {}
        try:
            row = upsert_thesis_record(conn, data, thesis_id=thesis_id)
        except ValueError as e:
            return json_error(str(e), 400)
        if not row:
            return json_error("Not found", 404)
    return jsonify(row)


@app.route("/ops/fees", methods=["GET"])
def ops_fees():
    q = (request.args.get("q") or "").strip()
    from status_catalog import drop_watch_or_qa_status

    status = drop_watch_or_qa_status(request.args.get("status") or "")
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        scopes = _scopes_for_accounting(actor if actor.get("ok") else None)
        cur = conn.cursor()
        from ops_data import _scopes_sql

        frag, params = _scopes_sql(scopes, "a.program_code")
        sql = (
            "SELECT ef.id, a.id, a.full_name, a.program_code, a.status, "
            "ef.amount, ef.status, ef.paid_at, ef.proof_note, "
            "a.cfvg_app_no, a.student_code_mba "
            "FROM enrollment_fees ef "
            "JOIN applications a ON a.id = ef.application_id "
            f"WHERE {frag}"
        )
        if status:
            # unpaid alias → pending
            if status == "unpaid":
                sql += " AND ef.status IN ('pending','unpaid')"
            else:
                sql += " AND ef.status = ?"
                params.append(status)
        if q:
            like = f"%{q}%"
            sql += (
                " AND (a.full_name LIKE ? OR a.program_code LIKE ? OR COALESCE(ef.proof_note,'') LIKE ?"
                " OR COALESCE(a.cfvg_app_no,'') LIKE ? OR COALESCE(a.student_code_mba,'') LIKE ?)"
            )
            params.extend([like, like, like, like, like])
        sql += " ORDER BY ef.id DESC"
        rows = cur.execute(sql, params).fetchall()
    mapped = [
        {
            "id": r[0],
            "application_id": r[1],
            "full_name": r[2],
            "program_code": r[3],
            "application_status": r[4],
            "amount": r[5],
            "amount_due": r[5],
            "status": r[6],
            "paid_at": r[7],
            "proof_note": r[8],
            "student_proof_note": r[8],
            "cfvg_app_no": r[9],
            "student_code": r[10] or r[9],
        }
        for r in rows
    ]
    return jsonify(apply_qa_rows("charge", mapped))


@app.route("/ops/fees/<int:fee_id>/mark-paid", methods=["POST"])
def ops_fee_mark_paid(fee_id):
    data = request.get_json(silent=True) or {}
    proof = (data.get("proof_note") or "").strip() or "Kế toán xác nhận"
    method = (data.get("method") or "bank_transfer").strip() or "bank_transfer"
    bank_ref = (data.get("bank_ref") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        allowed_fee = {"ke_toan", "admin_he_thong", "it"}
        if not allowed_fee.intersection(actor["dept_codes"]):
            return json_error(
                "Chỉ Kế toán được xác nhận nộp phí ghi danh (theo bàn giao bộ phận).",
                403,
            )
        cur = conn.cursor()
        cur.execute(
            "SELECT ef.id, ef.application_id, a.program_code FROM enrollment_fees ef "
            "JOIN applications a ON a.id = ef.application_id WHERE ef.id = ?",
            (fee_id,),
        )
        row = cur.fetchone()
        if not row:
            return json_error("Fee record not found", 404)
        _, app_id, program_code = row[0], row[1], row[2]
        from workflow_links import actor_may_mutate_program, scopes_for_accounting

        ok_scope, scope_msg = actor_may_mutate_program(
            scopes_for_accounting(
                actor["dept_codes"],
                actor["program_scopes"],
                is_admin=bool(actor.get("is_admin")),
            ),
            program_code,
        )
        if not ok_scope:
            return json_error(scope_msg, 403)
        from treasury_ops import record_inscription_payment

        result = record_inscription_payment(
            conn,
            fee_id,
            proof_note=proof,
            method=method,
            bank_ref=bank_ref,
            created_by=f"user:{actor.get('user_id')}",
        )
        try:
            from learner_spine import upsert_learner_for_application

            upsert_learner_for_application(conn, app_id)
            conn.commit()
        except Exception:
            pass
        result["actor_user_id"] = actor["user_id"]
        result["actor_departments"] = actor["dept_codes"]
    return jsonify(result)


@app.route("/ops/fees/<int:fee_id>/mark-official", methods=["POST"])
def ops_fee_mark_official(fee_id):
    """Deposit Verified → Officially Enrolled (Kế toán) + mở Payment Plan học phí."""
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not {"ke_toan", "admin_he_thong", "it"}.intersection(actor["dept_codes"]):
            return json_error("Chỉ Kế toán được chốt nhập học chính thức.", 403)
        cur = conn.cursor()
        cur.execute(
            "SELECT ef.id, ef.application_id, ef.status, a.program_code, a.status "
            "FROM enrollment_fees ef JOIN applications a ON a.id = ef.application_id "
            "WHERE ef.id = ?",
            (fee_id,),
        )
        row = cur.fetchone()
        if not row:
            return json_error("Fee record not found", 404)
        _, app_id, fee_status, program_code, app_status = row
        from workflow_links import actor_may_mutate_program, scopes_for_accounting
        from admission_ops import assert_can_mark_official

        ok_scope, scope_msg = actor_may_mutate_program(
            scopes_for_accounting(
                actor["dept_codes"],
                actor["program_scopes"],
                is_admin=bool(actor.get("is_admin")),
            ),
            program_code,
        )
        if not ok_scope:
            return json_error(scope_msg, 403)
        if fee_status != "paid":
            return json_error("Cần xác nhận nộp phí ghi danh (Deposit Verified) trước khi chốt nhập học.", 400)
        cur.execute(
            "SELECT status, program_code, exam_eligible_flag, exam_format, "
            "written_score, interview_score, board_decision, admitted_program, final_result "
            "FROM applications WHERE id = ?",
            (app_id,),
        )
        prow = cur.fetchone()
        if prow:
            try:
                assert_can_mark_official({
                    "status": prow[0], "program_code": prow[1],
                    "exam_eligible_flag": prow[2], "exam_format": prow[3],
                    "written_score": prow[4], "interview_score": prow[5],
                    "board_decision": prow[6], "admitted_program": prow[7],
                    "final_result": prow[8],
                })
            except ValueError as e:
                return json_error(str(e), 400)
        if app_status != "official":
            cur.execute(
                "UPDATE applications SET status = 'official', "
                "admitted_program = COALESCE(NULLIF(admitted_program,''), program_code), "
                "final_result = COALESCE(NULLIF(final_result,''), 'Admitted') WHERE id = ?",
                (app_id,),
            )
            conn.commit()
        from treasury_ops import ensure_inscription_charge, open_tuition_plan_after_official

        ensure_inscription_charge(conn, app_id)
        plan = open_tuition_plan_after_official(conn, app_id)
        try:
            from learner_spine import upsert_learner_for_application

            upsert_learner_for_application(conn, app_id)
            conn.commit()
        except Exception:
            pass
    return jsonify({
        "ok": True,
        "status": "official",
        "application_id": app_id,
        "tuition_plan": plan,
        "handoff": "Đã chốt nhập học chính thức. Hồ sơ theo học mở ở trạng thái Chờ xếp lớp. Điều phối cấp mã và xếp lớp. Sổ học phí đã mở.",
    })


@app.route("/ops/treasury/charges", methods=["GET"])
def ops_treasury_charges():
    q = (request.args.get("q") or "").strip()
    fee_type = (request.args.get("fee_type") or "").strip()
    status = (request.args.get("status") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        scopes = _scopes_for_accounting(actor if actor.get("ok") else None)
        from treasury_ops import list_student_charges

        rows = list_student_charges(
            conn,
            scopes,
            q=q,
            fee_type=fee_type,
            status=status,
            cohort=(request.args.get("cohort") or "").strip(),
            study_year=(request.args.get("study_year") or "").strip(),
            require_cohort=True,
        )
        return jsonify(apply_qa_rows("charge", rows))


@app.route("/ops/treasury/tuition-tracker", methods=["GET"])
def ops_treasury_tuition_tracker():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        scopes = _scopes_for_accounting(actor if actor.get("ok") else None)
        from treasury_ops import list_tuition_tracker

        return jsonify(list_tuition_tracker(
            conn,
            scopes,
            q=q,
            status=status,
            cohort=(request.args.get("cohort") or "").strip(),
            study_year=(request.args.get("study_year") or "").strip(),
        ))


@app.route("/ops/treasury/alerts", methods=["GET"])
def ops_treasury_alerts():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        scopes = _scopes_for_accounting(actor if actor.get("ok") else None)
        from treasury_ops import list_fee_alerts

        return jsonify(list_fee_alerts(conn, scopes, q=q, status=status))


@app.route("/ops/treasury/alert-criteria", methods=["GET"])
def ops_treasury_alert_criteria():
    with get_db() as conn:
        from treasury_ops import list_alert_criteria

        return jsonify(list_alert_criteria(conn))


@app.route("/ops/treasury/alert-criteria/<code>", methods=["PATCH"])
def ops_treasury_alert_criteria_patch(code):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        depts = set(actor.get("dept_codes") or [])
        if not (
            actor.get("is_admin")
            or {"ke_toan", "admin_he_thong"}.intersection(depts)
        ):
            return json_error("Bạn không có quyền sửa tiêu chí cảnh báo học phí.", 403)
        from treasury_ops import update_alert_criterion

        try:
            return jsonify(update_alert_criterion(conn, code, data))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/summary", methods=["GET"])
def ops_treasury_summary():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        scopes = _scopes_for_accounting(actor if actor.get("ok") else None)
        from treasury_ops import treasury_summary

        return jsonify(treasury_summary(conn, scopes))


@app.route("/ops/treasury/fee-types", methods=["GET", "POST"])
def ops_treasury_fee_types():
    with get_db() as conn:
        if request.method == "GET":
            from treasury_ops import list_fee_types

            return jsonify(list_fee_types(conn, include_inactive=True))
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not actor.get("is_admin") and not {"ke_toan", "admin_he_thong", "it"}.intersection(
            actor.get("dept_codes") or []
        ):
            return json_error("Chỉ Kế toán được khai báo danh mục khoản thu.", 403)
        from treasury_ops import upsert_fee_type

        try:
            return jsonify(upsert_fee_type(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/fee-types/<code>", methods=["PATCH"])
def ops_treasury_fee_type_patch(code):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not actor.get("is_admin") and not {"ke_toan", "admin_he_thong", "it"}.intersection(
            actor.get("dept_codes") or []
        ):
            return json_error("Chỉ Kế toán được khai báo danh mục khoản thu.", 403)
        data = dict(request.get_json(silent=True) or {})
        data["code"] = code
        from treasury_ops import upsert_fee_type

        try:
            return jsonify(upsert_fee_type(conn, data))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/candidate-files", methods=["GET"])
def ops_treasury_candidate_files():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        scopes = _scopes_for_accounting(actor if actor.get("ok") else None)
        from treasury_ops import list_candidate_fee_files

        return jsonify(list_candidate_fee_files(conn, scopes, q=q, status=status))


@app.route("/ops/treasury/candidate-files/<int:charge_id>", methods=["PATCH"])
def ops_treasury_candidate_file_patch(charge_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not {"ke_toan", "admin_he_thong", "it"}.intersection(actor["dept_codes"]) and not actor.get("is_admin"):
            return json_error("Chỉ Kế toán được cập nhật hồ sơ thí sinh trên sổ thu.", 403)
        from treasury_ops import update_candidate_fee_file

        try:
            result = update_candidate_fee_file(
                conn,
                charge_id,
                full_name=(data.get("full_name") or "").strip(),
                email=(data.get("email") or "").strip(),
                phone=(data.get("phone") or "").strip(),
                notes=(data.get("notes") or "").strip(),
                fee_type=(data.get("fee_type") or "").strip(),
                waiver_pct=data.get("waiver_pct") if data.get("waiver_pct") is not None else data.get("waiver"),
                waiver_amount=data.get("waiver_amount") if data.get("waiver_amount") is not None else data.get("waiver_amt"),
                due_date=(data.get("due_date") or "").strip(),
                created_by=f"user:{actor.get('user_id')}",
            )
        except ValueError as e:
            return json_error(str(e), 400)
    result["message"] = "Đã cập nhật hồ sơ thí sinh"
    return jsonify(result)


@app.route("/ops/treasury/collection-report", methods=["GET"])
def ops_treasury_collection_report():
    q = (request.args.get("q") or "").strip()
    fee_type = (request.args.get("fee_type") or "").strip()
    status = (request.args.get("status") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        scopes = _scopes_for_accounting(actor if actor.get("ok") else None)
        from treasury_ops import collection_report

        return jsonify(collection_report(conn, scopes, q=q, fee_type=fee_type, status=status))


def _nv_actor_or_401():
    from flask import g
    return None


@app.route("/ops/treasury/receipts", methods=["GET", "POST"])
def ops_nv_receipts():
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_receipts, create_receipt

        if request.method == "GET":
            return jsonify(list_receipts(conn, q=q, round_id=request.args.get("round_id", type=int)))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.receipts"):
            return json_error(deny_write_message("accounting.receipts"), 403)
        try:
            return jsonify(create_receipt(
                conn, request.get_json(silent=True) or {},
                actor=f"user:{actor.get('user_id')}", user_id=actor.get("user_id"),
            )), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/payment-methods", methods=["GET", "POST"])
def ops_nv_payment_methods():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_payment_methods, upsert_payment_method

        if request.method == "GET":
            return jsonify(list_payment_methods(conn))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.payment_methods"):
            return json_error(deny_write_message("accounting.payment_methods"), 403)
        try:
            return jsonify(upsert_payment_method(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/round-fee-settings", methods=["GET", "POST"])
def ops_nv_round_fees():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_round_fee_settings, upsert_round_fee_setting

        if request.method == "GET":
            year_raw = (request.args.get("year") or "").strip()
            try:
                year = int(year_raw) if year_raw else None
            except ValueError:
                year = None
            return jsonify(list_round_fee_settings(
                conn,
                round_id=request.args.get("round_id", type=int),
                year=year,
            ))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.round_fee_settings"):
            return json_error(deny_write_message("accounting.round_fee_settings"), 403)
        try:
            return jsonify(upsert_round_fee_setting(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


def _finance_actor(conn):
    actor = _resolve_ops_actor(conn)
    if not actor["ok"]:
        return actor, json_error(actor["error"] or "Unauthorized", 401)
    return actor, None


@app.route("/ops/treasury/payment-plans", methods=["GET", "POST"])
def ops_treasury_payment_plans():
    with get_db() as conn:
        actor, err = _finance_actor(conn)
        if err:
            return err
        from treasury_finance import create_payment_plan, list_payment_plans

        if request.method == "GET":
            return jsonify(list_payment_plans(conn, _scopes_for_accounting(actor)))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.payment_plans"):
            return json_error(deny_write_message("accounting.payment_plans"), 403)
        try:
            return jsonify(create_payment_plan(
                conn, request.get_json(silent=True) or {}, actor=f"user:{actor.get('user_id')}",
            )), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/payment-plans/<int:plan_id>/lines", methods=["POST"])
def ops_treasury_payment_plan_line(plan_id):
    with get_db() as conn:
        actor, err = _finance_actor(conn)
        if err:
            return err
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.payment_plans"):
            return json_error(deny_write_message("accounting.payment_plans"), 403)
        from treasury_finance import add_plan_line

        try:
            return jsonify(add_plan_line(
                conn, plan_id, request.get_json(silent=True) or {}, actor=f"user:{actor.get('user_id')}",
            )), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/payment-plans/<int:plan_id>/approve", methods=["POST"])
def ops_treasury_payment_plan_approve(plan_id):
    with get_db() as conn:
        actor, err = _finance_actor(conn)
        if err:
            return err
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.payment_plans"):
            return json_error(deny_write_message("accounting.payment_plans"), 403)
        from treasury_finance import approve_payment_plan

        try:
            return jsonify(approve_payment_plan(conn, plan_id, actor=f"user:{actor.get('user_id')}"))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/payment-plans/<int:plan_id>/apply", methods=["POST"])
def ops_treasury_payment_plan_apply(plan_id):
    with get_db() as conn:
        actor, err = _finance_actor(conn)
        if err:
            return err
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.payment_plans"):
            return json_error(deny_write_message("accounting.payment_plans"), 403)
        from treasury_finance import apply_intake_plan

        try:
            result = apply_intake_plan(conn, plan_id=plan_id)
        except ValueError as e:
            return json_error(str(e), 400)
        if not result.get("matched"):
            return json_error("Không có học viên chính thức khớp chương trình và Intake.", 400)
        result["message"] = f"Đã sinh {result.get('created') or 0} khoản phải thu. Đợt đã có được giữ nguyên."
        return jsonify(result)


@app.route("/ops/treasury/benefits", methods=["GET", "POST"])
def ops_treasury_benefits():
    with get_db() as conn:
        actor, err = _finance_actor(conn)
        if err:
            return err
        from treasury_finance import create_benefit, list_benefits

        if request.method == "GET":
            rows = list_benefits(conn, _scopes_for_accounting(actor))
            depts = set(actor.get("dept_codes") or [])
            if not actor.get("is_admin") and "ke_toan" not in depts:
                for row in rows:
                    row["beneficiary_account"] = ""
                    row["beneficiary_bank"] = ""
            return jsonify(rows)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.benefits"):
            return json_error(deny_write_message("accounting.benefits"), 403)
        try:
            return jsonify(create_benefit(
                conn, request.get_json(silent=True) or {}, actor=f"user:{actor.get('user_id')}",
            )), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/benefits/<int:benefit_id>/<action>", methods=["POST"])
def ops_treasury_benefit_action(benefit_id, action):
    with get_db() as conn:
        actor, err = _finance_actor(conn)
        if err:
            return err
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.benefits"):
            return json_error(deny_write_message("accounting.benefits"), 403)
        from treasury_finance import apply_benefit, approve_benefit, disburse_benefit

        fn = {"approve": approve_benefit, "apply": apply_benefit, "disburse": disburse_benefit}.get(action)
        if not fn:
            return json_error("Thao tác không hợp lệ", 404)
        try:
            return jsonify(fn(conn, benefit_id, actor=f"user:{actor.get('user_id')}"))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/refunds", methods=["GET", "POST"])
def ops_treasury_refunds():
    with get_db() as conn:
        actor, err = _finance_actor(conn)
        if err:
            return err
        from treasury_finance import create_refund, list_refunds

        if request.method == "GET":
            return jsonify(list_refunds(conn, _scopes_for_accounting(actor)))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.refunds"):
            return json_error(deny_write_message("accounting.refunds"), 403)
        try:
            return jsonify(create_refund(
                conn, request.get_json(silent=True) or {}, actor=f"user:{actor.get('user_id')}",
            )), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/refunds/<int:refund_id>/<action>", methods=["POST"])
def ops_treasury_refund_action(refund_id, action):
    with get_db() as conn:
        actor, err = _finance_actor(conn)
        if err:
            return err
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.refunds"):
            return json_error(deny_write_message("accounting.refunds"), 403)
        from treasury_finance import approve_refund, disburse_refund

        fn = {"approve": approve_refund, "disburse": disburse_refund}.get(action)
        if not fn:
            return json_error("Thao tác không hợp lệ", 404)
        try:
            return jsonify(fn(conn, refund_id, actor=f"user:{actor.get('user_id')}"))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/billing-profiles", methods=["GET", "POST"])
def ops_treasury_billing_profiles():
    with get_db() as conn:
        actor, err = _finance_actor(conn)
        if err:
            return err
        from treasury_finance import create_billing_profile, list_billing_profiles

        if request.method == "GET":
            return jsonify(list_billing_profiles(conn, _scopes_for_accounting(actor)))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.billing_profiles"):
            return json_error(deny_write_message("accounting.billing_profiles"), 403)
        try:
            return jsonify(create_billing_profile(
                conn, request.get_json(silent=True) or {}, actor=f"user:{actor.get('user_id')}",
            )), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/intake-plans", methods=["GET", "POST"])
def ops_treasury_intake_plans():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from treasury_finance import list_intake_plans, upsert_intake_plan

        if request.method == "GET":
            return jsonify(list_intake_plans(
                conn,
                cohort=(request.args.get("cohort") or "").strip(),
                study_year=(request.args.get("study_year") or "").strip(),
            ))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.intake_plans"):
            return json_error(deny_write_message("accounting.intake_plans"), 403)
        try:
            return jsonify(upsert_intake_plan(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/payment-imports", methods=["GET", "POST"])
def ops_nv_payment_imports():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import import_payments

        if request.method == "GET":
            from treasury_finance import list_bank_lines

            return jsonify(list_bank_lines(conn, q=(request.args.get("q") or "").strip()))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.payment_imports"):
            return json_error(deny_write_message("accounting.payment_imports"), 403)
        rows = (request.get_json(silent=True) or {}).get("rows") or []
        return jsonify(import_payments(conn, rows, actor=f"user:{actor.get('user_id')}", user_id=actor.get("user_id")))


@app.route("/ops/treasury/receipt-emails", methods=["GET", "POST"])
def ops_nv_receipt_emails():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_receipt_emails, bulk_receipt_emails, mark_receipt_email

        if request.method == "GET":
            return jsonify(list_receipt_emails(conn, q=(request.args.get("q") or "").strip()))
        data = request.get_json(silent=True) or {}
        if data.get("receipt_id"):
            return jsonify(mark_receipt_email(conn, int(data["receipt_id"]), actor=f"user:{actor.get('user_id')}"))
        return jsonify(bulk_receipt_emails(conn, round_id=data.get("round_id"), actor=f"user:{actor.get('user_id')}"))


@app.route("/ops/treasury/commitments", methods=["GET", "POST"])
def ops_nv_commitments():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_commitments, create_commitment

        if request.method == "GET":
            return jsonify(list_commitments(conn, q=(request.args.get("q") or "").strip()))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "accounting.candidate_files"):
            return json_error(deny_write_message("accounting.candidate_files"), 403)
        try:
            return jsonify(create_commitment(
                conn, request.get_json(silent=True) or {},
                actor=f"user:{actor.get('user_id')}", user_id=actor.get("user_id"),
            )), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/treasury/commitments/<int:cid>/approve", methods=["POST"])
def ops_nv_commitment_approve(cid):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import approve_commitment

        try:
            return jsonify(approve_commitment(conn, cid, actor=f"user:{actor.get('user_id')}", user_id=actor.get("user_id")))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/verification-queue", methods=["GET"])
def ops_nv_verification_queue():
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        codes = set(actor.get("permission_codes") or [])
        if not actor["is_admin"] and "admissions.verification_queue" not in codes:
            return json_error("Bạn không có quyền admissions.verification_queue.", 403)
        from nv2026_ops import list_verification_queue

        return jsonify(list_verification_queue(conn, actor.get("program_scopes"), q=q))


@app.route("/ops/applications/bulk-flag", methods=["POST"])
def ops_nv_bulk_flag():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "admissions.applications"):
            return json_error(deny_write_message("admissions.applications"), 403)
        from nv2026_ops import bulk_flag_applications

        ids = [int(x) for x in (data.get("ids") or []) if str(x).strip()]
        try:
            return jsonify(bulk_flag_applications(
                conn, ids, (data.get("field") or "").strip(), str(data.get("value") or "1"),
                actor=f"user:{actor.get('user_id')}",
            ))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/student-numbering", methods=["GET", "POST"])
def ops_nv_student_numbering():
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_student_numbering, assign_student_codes
        from ops_policy import scopes_for_perm, can_write_perm, deny_write_message

        if request.method == "GET":
            return jsonify(list_student_numbering(conn, scopes_for_perm(actor, "admissions.student_numbering"), q=q))
        if not can_write_perm(actor, "admissions.student_numbering"):
            return json_error(deny_write_message("admissions.student_numbering"), 403)
        data = request.get_json(silent=True) or {}
        try:
            return jsonify(assign_student_codes(
                conn,
                prefix=(data.get("prefix") or "HV").strip(),
                start=int(data.get("start") or 1),
                application_ids=data.get("application_ids") or data.get("ids"),
                round_id=data.get("round_id"),
                preview=bool(data.get("preview")),
                actor=f"user:{actor.get('user_id')}",
            ))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/applications/<int:app_id>/confirm-enrollment", methods=["POST"])
def ops_nv_confirm_enrollment(app_id):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message
        from nv2026_ops import confirm_enrollment

        if not can_write_perm(actor, "admissions.enrolled_files"):
            return json_error(deny_write_message("admissions.enrolled_files"), 403)
        try:
            return jsonify(confirm_enrollment(conn, app_id, actor=f"user:{actor.get('user_id')}"))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/review-batches", methods=["GET", "POST"])
def ops_nv_review_batches():
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_review_batches, create_review_batch
        from ops_policy import can_write_perm, deny_write_message

        if request.method == "GET":
            return jsonify(list_review_batches(conn, q=q))
        if not can_write_perm(actor, "teaching.review_batches"):
            return json_error(deny_write_message("teaching.review_batches"), 403)
        try:
            return jsonify(create_review_batch(conn, request.get_json(silent=True) or {}, actor=f"user:{actor.get('user_id')}")), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/review-batches/<int:bid>/lock", methods=["POST"])
def ops_nv_review_batch_lock(bid):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import lock_review_batch
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.review_batches"):
            return json_error(deny_write_message("teaching.review_batches"), 403)
        try:
            return jsonify(lock_review_batch(conn, bid, actor=f"user:{actor.get('user_id')}"))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/intl/partners", methods=["GET", "POST"])
def ops_nv_partners():
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_partners, upsert_partner, import_partners
        from ops_policy import can_write_perm, deny_write_message

        if request.method == "GET":
            return jsonify(list_partners(conn, q=q))
        if not can_write_perm(actor, "intl.partners"):
            return json_error(deny_write_message("intl.partners"), 403)
        data = request.get_json(silent=True) or {}
        if data.get("rows"):
            return jsonify(import_partners(conn, data["rows"]))
        try:
            return jsonify(upsert_partner(conn, data)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/intl/coop-programs", methods=["GET", "POST"])
def ops_nv_coop():
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_coop_programs, create_coop_program
        from ops_policy import can_write_perm, deny_write_message

        if request.method == "GET":
            return jsonify(list_coop_programs(conn, q=q))
        if not can_write_perm(actor, "intl.cooperation_programs"):
            return json_error(deny_write_message("intl.cooperation_programs"), 403)
        try:
            return jsonify(create_coop_program(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/intl/workflow-steps", methods=["GET"])
def ops_nv_steps():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_workflow_steps

        return jsonify(list_workflow_steps(conn, q=(request.args.get("q") or "").strip()))


@app.route("/ops/intl/workflow-steps", methods=["POST"])
def ops_nv_steps_create():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "intl.workflow_steps"):
            return json_error(deny_write_message("intl.workflow_steps"), 403)
        from nv2026_ops import create_workflow_step

        try:
            return jsonify(create_workflow_step(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/intl/exchange-reports", methods=["GET"])
def ops_nv_exchange_reports():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from nv2026_ops import list_exchange_reports

        return jsonify(list_exchange_reports(conn, q=(request.args.get("q") or "").strip()))


@app.route("/ops/audit-logs", methods=["GET"])
def ops_nv_audit_logs():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        codes = set(actor.get("permission_codes") or [])
        if not actor["is_admin"] and "admin.audit_logs" not in codes:
            return json_error("Bạn không có quyền admin.audit_logs.", 403)
        from nv2026_ops import list_audit_logs

        return jsonify(
            apply_qa_rows("audit", list_audit_logs(conn, q=(request.args.get("q") or "").strip()))
        )


@app.route("/ops/canvas/accept/<int:class_id>", methods=["POST"])
def ops_nv_canvas_accept(class_id):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from canvas_bridge import mark_canvas_accepted

        try:
            return jsonify(mark_canvas_accepted(conn, class_id, actor=f"user:{actor.get('user_id')}"))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/grades/import", methods=["POST"])
def ops_nv_grades_import():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message
        from nv2026_ops import import_course_grades

        if not can_write_perm(actor, "teaching.grades"):
            return json_error(deny_write_message("teaching.grades"), 403)
        return jsonify(import_course_grades(conn, data.get("rows") or [], actor=f"user:{actor.get('user_id')}"))


@app.route("/ops/treasury/charges/<int:charge_id>/waiver", methods=["POST", "PATCH"])
def ops_treasury_charge_waiver(charge_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not {"ke_toan", "admin_he_thong", "it"}.intersection(actor["dept_codes"]) and not actor.get("is_admin"):
            return json_error("Chỉ Kế toán được ghi nhận mức miễn phí.", 403)
        from treasury_ops import set_charge_waiver

        try:
            result = set_charge_waiver(
                conn,
                charge_id,
                waiver_pct=data.get("waiver_pct") if data.get("waiver_pct") is not None else data.get("waiver"),
                waiver_amount=data.get("waiver_amount") if data.get("waiver_amount") is not None else data.get("waiver_amt"),
                due_date=(data.get("due_date") or "").strip(),
                decision_note=(data.get("decision_note") or data.get("note") or "").strip(),
                created_by=f"user:{actor.get('user_id')}",
            )
        except ValueError as e:
            return json_error(str(e), 400)
    result["message"] = "Đã ghi nhận mức miễn và tính lại số tiền thực tế"
    return jsonify(result)


@app.route("/ops/treasury/charges/<int:charge_id>/pay", methods=["POST"])
def ops_treasury_charge_pay(charge_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not {"ke_toan", "admin_he_thong", "it"}.intersection(actor["dept_codes"]):
            return json_error("Chỉ Thủ quỹ / Kế toán được ghi nhận thanh toán.", 403)
        from treasury_ops import record_charge_payment

        try:
            result = record_charge_payment(
                conn,
                charge_id,
                amount=float(data.get("amount") or 0),
                proof_note=(data.get("proof_note") or data.get("note") or "").strip(),
                method=(data.get("method") or "bank_transfer").strip(),
                bank_ref=(data.get("bank_ref") or "").strip(),
                paid_at=(data.get("paid_at") or data.get("paid_date") or "").strip(),
                created_by=f"user:{actor.get('user_id')}",
            )
        except ValueError as e:
            return json_error(str(e), 400)
    result["message"] = "Đã ghi nhận thanh toán"
    return jsonify(result)


@app.route("/ops/treasury/charges/<int:charge_id>/adjust", methods=["POST"])
def ops_treasury_charge_adjust(charge_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not {"ke_toan", "admin_he_thong", "it"}.intersection(actor["dept_codes"]):
            return json_error("Chỉ Thủ quỹ / Kế toán được điều chỉnh học bổng / giảm / hỗ trợ / hoàn.", 403)
        kind = (data.get("adj_type") or data.get("kind") or "").strip().lower()
        actor_ref = f"user:{actor.get('user_id')}"
        try:
            if kind == "refund":
                from treasury_finance import create_refund

                payload = dict(data)
                payload["charge_id"] = charge_id
                result = create_refund(conn, payload, actor=actor_ref)
                result["message"] = "Đã lập hồ sơ hoàn. Người khác duyệt trước khi chi."
            elif kind in ("scholarship", "discount", "aid"):
                from treasury_finance import create_benefit

                payload = dict(data)
                payload["charge_id"] = charge_id
                payload["benefit_type"] = kind
                if (data.get("effect") or "").strip().lower() in ("payout", "disburse"):
                    payload["effect"] = "disburse"
                    payload["beneficiary_account"] = data.get("beneficiary_account") or data.get("payout_account") or ""
                    payload["beneficiary_bank"] = data.get("beneficiary_bank") or data.get("payout_bank") or ""
                result = create_benefit(conn, payload, actor=actor_ref)
                result["message"] = "Đã lập đề nghị. Người lập không tự duyệt."
            else:
                from treasury_ops import apply_adjustment

                result = apply_adjustment(
                    conn,
                    charge_id,
                    adj_type=kind,
                    amount=float(data.get("amount") or 0),
                    decision_note=(data.get("decision_note") or data.get("note") or "").strip(),
                    created_by=actor_ref,
                )
                result["message"] = "Đã ghi nhận điều chỉnh"
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/program-versions", methods=["GET"])
def ops_program_versions():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    program_code = (request.args.get("program_code") or "").strip()
    version_code = (request.args.get("version_code") or "").strip()
    with get_db() as conn:
        from course_content import list_program_versions, seed_course_content

        seed_course_content(conn)
        conn.commit()
        return jsonify(
            list_program_versions(
                conn,
                scopes,
                q=q,
                program_code=program_code,
                version_code=version_code,
                cohort=(request.args.get("cohort") or "").strip(),
            )
        )


@app.route("/ops/program-versions", methods=["POST"])
def ops_program_versions_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "programs.structure"):
            return json_error(deny_write_message("programs.structure"), 403)
        from ops_crud import create_program_version_row

        try:
            row = create_program_version_row(conn, data)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/courses", methods=["GET"])
def ops_courses():
    scopes = _parse_scopes_from_request()
    version_id = request.args.get("version_id", type=int)
    q = (request.args.get("q") or "").strip()
    program_code = (request.args.get("program_code") or "").strip()
    version_code = (request.args.get("version_code") or "").strip()
    with get_db() as conn:
        from course_content import list_courses, seed_course_content

        seed_course_content(conn)
        conn.commit()
        return jsonify(
            list_courses(
                conn,
                scopes,
                version_id=version_id,
                q=q,
                program_code=program_code,
                version_code=version_code,
                cohort=(request.args.get("cohort") or "").strip(),
            )
        )


@app.route("/ops/courses", methods=["POST"])
def ops_courses_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "programs.courses"):
            return json_error(deny_write_message("programs.courses"), 403)
        from ops_crud import create_course_row

        try:
            row = create_course_row(conn, data)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/courses/<int:course_id>", methods=["GET"])
def ops_course_detail(course_id):
    with get_db() as conn:
        from course_content import get_course_detail, seed_course_content

        seed_course_content(conn)
        conn.commit()
        detail = get_course_detail(conn, course_id)
    if not detail:
        return json_error("Course not found", 404)
    return jsonify(detail)


@app.route("/ops/courses/<int:course_id>", methods=["PATCH"])
def ops_course_update(course_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from course_content import update_course_syllabus

        detail = update_course_syllabus(conn, course_id, data)
    if not detail:
        return json_error("Course not found", 404)
    return jsonify(detail)


@app.route("/ops/course-sessions/<int:session_id>", methods=["PATCH"])
def ops_course_session_update(session_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from course_content import update_session

        row = update_session(conn, session_id, data)
    if not row:
        return json_error("Session not found", 404)
    return jsonify(row)


@app.route("/ops/courses/<int:course_id>/sessions/reorder", methods=["POST"])
def ops_course_sessions_reorder(course_id):
    data = request.get_json(silent=True) or {}
    session_ids = data.get("session_ids") or data.get("order") or []
    with get_db() as conn:
        from course_content import reorder_course_sessions

        try:
            result = reorder_course_sessions(conn, course_id, session_ids)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/materials", methods=["GET"])
def ops_materials_list():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    from status_catalog import drop_watch_or_qa_status

    status = drop_watch_or_qa_status(request.args.get("status") or "")
    if status not in ("", "draft", "released", "archived"):
        status = ""
    with get_db() as conn:
        from course_content import list_materials_admin, seed_course_content

        seed_course_content(conn)
        conn.commit()
        return jsonify(list_materials_admin(conn, scopes, q=q, release_status=status))


@app.route("/ops/materials/upload", methods=["POST"])
def ops_materials_upload():
    course_id = request.form.get("course_id", type=int)
    if not course_id:
        return json_error("course_id required", 400)
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    material_type = (request.form.get("material_type") or "slide").strip()
    session_id = request.form.get("session_id", type=int)
    class_id = request.form.get("class_id", type=int)
    release_status = (request.form.get("release_status") or "draft").strip()
    if release_status not in ("draft", "released"):
        release_status = "draft"
    uploaded_by = (request.form.get("uploaded_by") or request.headers.get("X-Actor") or "").strip()
    f = request.files.get("file")

    from course_content import add_material, allowed_material_filename

    file_path = None
    stored_name = None
    original_filename = None
    mime_type = None
    file_size = 0
    if f and f.filename:
        if not allowed_material_filename(f.filename):
            return json_error(
                f"File type not allowed. Use: {', '.join(sorted(__import__('course_content').MATERIAL_EXTS))}",
                400,
            )
        original_filename = f.filename
        stored_name = f"{uuid.uuid4().hex}_{f.filename}"
        dest = UPLOADS_DIR / "course_materials"
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / stored_name
        f.save(str(path))
        file_path = str(path)
        mime_type = f.mimetype
        file_size = path.stat().st_size
        if not title:
            title = Path(original_filename).stem
    if not title:
        return json_error("title or file required", 400)

    with get_db() as conn:
        try:
            row = add_material(
                conn,
                course_id=course_id,
                title=title,
                description=description,
                material_type=material_type,
                session_id=session_id,
                class_id=class_id,
                original_filename=original_filename,
                stored_name=stored_name,
                file_path=file_path,
                mime_type=mime_type,
                file_size=file_size,
                uploaded_by=uploaded_by,
                release_status=release_status,
            )
        except Exception as e:
            if file_path:
                Path(file_path).unlink(missing_ok=True)
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/materials/<int:material_id>/release", methods=["POST"])
def ops_materials_release(material_id):
    data = request.get_json(silent=True) or {}
    status = (data.get("release_status") or data.get("status") or "").strip()
    with get_db() as conn:
        from course_content import set_material_release

        try:
            row = set_material_release(conn, material_id, status)
        except ValueError as e:
            return json_error(str(e), 400)
    if not row:
        return json_error("Material not found", 404)
    return jsonify(row)


@app.route("/ops/materials/<int:material_id>/file", methods=["GET"])
def ops_materials_file(material_id):
    """Download/view material file. Students only if released. ?inline=1 for preview."""
    student_mode = (request.args.get("as_student") or request.headers.get("X-As-Student") or "") in (
        "1",
        "true",
        "yes",
    )
    inline = (request.args.get("inline") or "") in ("1", "true", "yes")
    with get_db() as conn:
        from course_content import get_material_file, safe_download_name

        meta = get_material_file(conn, material_id)
    if not meta:
        return json_error("Material not found", 404)
    if student_mode and meta["release_status"] != "released":
        return json_error("File chưa được release tới học viên", 403)
    fp = meta.get("file_path")
    if not fp or not Path(fp).is_file():
        return json_error(
            "Chưa có file đính kèm (metadata only). Hãy upload file thật từ Điều phối.",
            404,
        )
    download_name = safe_download_name(meta.get("original_filename"), "material.bin")
    mime = meta.get("mime_type") or "application/octet-stream"
    # Force correct mime for common preview types
    ext = Path(download_name).suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    if ext in mime_map:
        mime = mime_map[ext]
    return send_file(
        fp,
        as_attachment=not inline,
        download_name=download_name,
        mimetype=mime,
    )


@app.route("/ops/materials/<int:material_id>/preview", methods=["GET"])
def ops_materials_preview(material_id):
    """JSON preview payload for office/PDF/image files."""
    student_mode = (request.args.get("as_student") or "") in ("1", "true", "yes")
    with get_db() as conn:
        from course_content import get_material_file

        meta = get_material_file(conn, material_id)
    if not meta:
        return json_error("Material not found", 404)
    if student_mode and meta["release_status"] != "released":
        return json_error("File chưa được release tới học viên", 403)
    fp = meta.get("file_path")
    if not fp or not Path(fp).is_file():
        return json_error("Chưa có file đính kèm để xem trước.", 404)
    from doc_preview import preview_payload

    payload = preview_payload(fp, meta.get("original_filename") or "file")
    payload["material_id"] = material_id
    payload["release_status"] = meta.get("release_status")
    payload["lesson_id"] = meta.get("lesson_id")
    payload["material_title"] = meta.get("title") or payload.get("title")
    return jsonify(payload)


@app.route("/ops/student/library", methods=["GET"])
def ops_student_library():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    course_id = request.args.get("course_id", type=int)
    email = (request.args.get("email") or request.headers.get("X-Student-Email") or "").strip()
    with get_db() as conn:
        from course_content import list_student_library, seed_course_content

        seed_course_content(conn)
        conn.commit()
        # Prefer portal identity from X-User-Id
        if not email:
            actor = _resolve_ops_actor(conn)
            if actor.get("ok") and actor.get("user_id"):
                from e2e_pipeline import resolve_student_identity

                ident = resolve_student_identity(conn, user_id=int(actor["user_id"]))
                if ident and ident.get("application"):
                    email = ident["application"].get("email") or ""
                elif ident and ident.get("student"):
                    email = ident["student"].get("email") or ""
        data = list_student_library(
            conn, q=q, scopes=scopes, student_email=email or None, course_id=course_id
        )
        qa = (request.args.get("qa") or "")
        from quality_ops import apply_qa

        data = dict(data)
        data["courses"] = apply_qa("material", data.get("courses") or [], qa=qa)
        data["materials"] = apply_qa("material", data.get("materials") or [], qa=qa)
        return jsonify(data)


@app.route("/ops/student/me", methods=["GET"])
def ops_student_me():
    """Portal profile for the logged-in hoc_vien."""
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from e2e_pipeline import get_student_timeline, resolve_student_identity

        ident = resolve_student_identity(conn, user_id=actor["user_id"])
        if not ident:
            return jsonify([])
        profile = (get_student_timeline(conn, user_id=actor["user_id"]).get("profile") or {})
        app = ident.get("application") or {}
        app_id = app.get("id")
        doc_summary = {}
        if app_id:
            from admission_ops import attach_application_doc_summary

            doc_summary = attach_application_doc_summary(conn, [{"id": app_id}])[0]
        row = {
            "id": app_id or (ident.get("student") or {}).get("id") or actor["user_id"],
            "application_id": app_id,
            "full_name": profile.get("full_name") or app.get("full_name"),
            "program_code": profile.get("program_code") or app.get("program_code"),
            "status": profile.get("application_status") or profile.get("lifecycle_status") or app.get("status"),
            "email": profile.get("email") or app.get("email"),
            "student_code": profile.get("student_code"),
            "class_name": profile.get("class_name"),
            "lifecycle_status": profile.get("lifecycle_status"),
            "login": profile.get("login"),
            "cfvg_app_no": app.get("cfvg_app_no"),
            "written_score": app.get("written_score"),
            "interview_score": app.get("interview_score"),
            "avg_score": app.get("avg_score"),
            "english_file": doc_summary.get("english_file") or "",
            "degree_file": doc_summary.get("degree_file") or "",
            "other_file": doc_summary.get("other_file") or "",
            "doc_count": doc_summary.get("doc_count") or 0,
            "dob": app.get("dob") or profile.get("dob") or "",
            "phone": profile.get("phone") or app.get("phone") or "",
        }
        return jsonify(apply_qa_rows("student_profile", [row]))


@app.route("/ops/student/me", methods=["PATCH"])
def ops_student_me_patch():
    """HV cập nhật hồ sơ liên hệ — không tự xác nhận phí."""
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from e2e_pipeline import resolve_student_identity

        ident = resolve_student_identity(conn, user_id=actor["user_id"])
        app = (ident or {}).get("application") or {}
        app_id = app.get("id")
        if not app_id:
            return json_error("Không gắn hồ sơ thí sinh với tài khoản này.", 400)
        allowed = {}
        for key in ("email", "phone", "dob"):
            if key in data and data.get(key) is not None:
                allowed[key] = str(data.get(key) or "").strip()
        if not allowed:
            return json_error("Không có trường được phép cập nhật (email, phone, dob).", 400)
        from quality_ops import attach, _email_ok

        flags = []
        if "email" in allowed and allowed["email"] and not _email_ok(allowed["email"]):
            flags.append("Email không hợp lệ — kiểm tra lại.")
        sets = ", ".join(f"{k} = ?" for k in allowed)
        conn.cursor().execute(
            f"UPDATE applications SET {sets} WHERE id = ?",
            [*allowed.values(), app_id],
        )
        conn.commit()
        row = dict(app)
        row.update(allowed)
        out = attach("student_profile", row)
        out["qa_precheck"] = flags
        return jsonify(out)


@app.route("/ops/student/me/charges", methods=["GET"])
def ops_student_me_charges():
    """HV xem công nợ của mình — không lộ khoản của người khác."""
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from e2e_pipeline import resolve_student_identity
        from treasury_ops import list_student_charges

        ident = resolve_student_identity(conn, user_id=actor["user_id"])
        app = (ident or {}).get("application") or {}
        app_id = app.get("id")
        if not app_id:
            return jsonify([])
        rows = [
            r
            for r in list_student_charges(conn, ["*"])
            if int(r.get("application_id") or 0) == int(app_id)
        ]
        return jsonify(apply_qa_rows("charge", rows))


@app.route("/ops/student/me/charges/<int:charge_id>/proof", methods=["POST"])
def ops_student_me_charge_proof(charge_id):
    """HV gửi minh chứng — không tự xác nhận đã thu."""
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from e2e_pipeline import resolve_student_identity
        from treasury_ops import record_student_proof

        ident = resolve_student_identity(conn, user_id=actor["user_id"])
        app = (ident or {}).get("application") or {}
        app_id = app.get("id")
        if not app_id:
            return json_error("Không gắn hồ sơ thí sinh với tài khoản này.", 400)
        try:
            return jsonify(
                record_student_proof(
                    conn,
                    charge_id,
                    note=(data.get("proof_note") or data.get("note") or data.get("student_proof_note") or ""),
                    application_id=int(app_id),
                    created_by=f"user:{actor.get('user_id')}",
                )
            )
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/student/me/timeline", methods=["GET"])
def ops_student_me_timeline():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from e2e_pipeline import student_timeline_rows

        return jsonify(apply_qa_rows("student_result", student_timeline_rows(conn, user_id=actor["user_id"])))


@app.route("/ops/student/me/schedule", methods=["GET"])
def ops_student_me_schedule():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from e2e_pipeline import student_schedule_rows

        return jsonify(apply_qa_rows("event", student_schedule_rows(conn, user_id=actor["user_id"])))


@app.route("/ops/student/me/dossier", methods=["GET"])
def ops_student_me_dossier():
    """Full timeline JSON (for print / detail)."""
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from e2e_pipeline import get_student_timeline

        return jsonify(get_student_timeline(conn, user_id=actor["user_id"]))


# ---------------------------------------------------------------------------
# eLearning (bài giảng trực tuyến, mục tiêu, tracker, phiên thi, lịch HV)
# ---------------------------------------------------------------------------
_ELEARN_PERM = {
    "lectures": "teaching.online_lectures",
    "objectives": "teaching.objectives",
    "instructor-intel": "teaching.instructor_intel",
    "tracker": "teaching.student_tracker",
    "sittings": "teaching.exam_integrity",
    "meetings": "teaching.return_meetings",
    "plans": "student.study_plan",
    "ttl": "student.time_to_learn",
    "recs": "student.objective_recs",
    "agenda": "student.agenda",
    "my-meetings": "student.return_meetings",
}


def _elearn_actor(conn, *perm_codes: str):
    actor = _resolve_ops_actor(conn)
    if not actor["ok"]:
        return actor, (json_error(actor["error"] or "Unauthorized", 401),)
    codes = set(actor.get("permission_codes") or [])
    if actor.get("is_admin"):
        return actor, None
    if perm_codes and not any(p in codes for p in perm_codes):
        return actor, (json_error(f"Bạn không có quyền {perm_codes[0]}.", 403),)
    return actor, None


@app.route("/ops/elearn/lectures", methods=["GET", "POST"])
def ops_elearn_lectures():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "teaching.online_lectures", "student.lessons")
        if err:
            return err[0]
        from elearn_ops import create_online_lecture, list_online_lectures

        depts = set(actor.get("dept_codes") or [])
        as_student = (not actor.get("is_admin")) and ("hoc_vien" in depts) and "teaching.online_lectures" not in set(actor.get("permission_codes") or [])
        if request.method == "GET":
            return jsonify(list_online_lectures(conn, actor.get("program_scopes") or scopes, q=q, as_student=as_student))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.online_lectures"):
            return json_error(deny_write_message("teaching.online_lectures"), 403)
        try:
            return jsonify(create_online_lecture(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/elearn/objectives", methods=["GET", "POST"])
def ops_elearn_objectives_api():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "teaching.objectives")
        if err:
            return err[0]
        from elearn_ops import generate_objectives_from_syllabus, list_objectives

        if request.method == "GET":
            return jsonify(list_objectives(conn, actor.get("program_scopes") or scopes, q=q))
        try:
            return jsonify(generate_objectives_from_syllabus(conn, actor.get("program_scopes") or scopes)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/elearn/instructor-intel", methods=["GET"])
def ops_elearn_instructor_intel():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "teaching.instructor_intel")
        if err:
            return err[0]
        from elearn_ops import list_instructor_intel

        return jsonify(list_instructor_intel(conn, actor.get("program_scopes") or scopes, q=q))


@app.route("/ops/elearn/tracker", methods=["GET"])
def ops_elearn_tracker():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "teaching.student_tracker")
        if err:
            return err[0]
        from elearn_ops import list_student_tracker

        return jsonify(list_student_tracker(conn, actor.get("program_scopes") or scopes, q=q))


@app.route("/ops/elearn/ttl", methods=["GET", "POST"])
def ops_elearn_ttl():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "student.time_to_learn", "teaching.student_tracker")
        if err:
            return err[0]
        from elearn_ops import generate_time_to_learn, list_time_to_learn

        if request.method == "GET":
            return jsonify(list_time_to_learn(conn, actor, actor.get("program_scopes") or scopes, q=q))
        return jsonify(generate_time_to_learn(conn, actor, actor.get("program_scopes") or scopes))


@app.route("/ops/elearn/plans", methods=["GET", "POST"])
def ops_elearn_plans():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "student.study_plan", "teaching.objectives")
        if err:
            return err[0]
        from elearn_ops import generate_study_plan, list_study_plans

        if request.method == "GET":
            return jsonify(list_study_plans(conn, actor, actor.get("program_scopes") or scopes, q=q))
        try:
            return jsonify(generate_study_plan(conn, actor, actor.get("program_scopes") or scopes)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/elearn/recs", methods=["GET", "POST"])
def ops_elearn_recs():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "student.objective_recs", "teaching.objectives")
        if err:
            return err[0]
        from elearn_ops import generate_objective_recs, list_objective_recs

        if request.method == "GET":
            return jsonify(list_objective_recs(conn, actor, actor.get("program_scopes") or scopes, q=q))
        try:
            return jsonify(generate_objective_recs(conn, actor, actor.get("program_scopes") or scopes)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/elearn/agenda", methods=["GET", "POST"])
def ops_elearn_agenda():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "student.agenda", "teaching.student_tracker")
        if err:
            return err[0]
        from elearn_ops import generate_agenda, list_agenda

        if request.method == "GET":
            return jsonify(list_agenda(conn, actor, actor.get("program_scopes") or scopes, q=q))
        try:
            return jsonify(generate_agenda(conn, actor, actor.get("program_scopes") or scopes)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/elearn/sittings", methods=["GET", "POST"])
def ops_elearn_sittings():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "teaching.exam_integrity")
        if err:
            return err[0]
        from elearn_ops import create_exam_sitting, generate_exam_sittings, list_exam_sittings

        if request.method == "GET":
            return jsonify(list_exam_sittings(conn, actor.get("program_scopes") or scopes, q=q))
        data = request.get_json(silent=True) or {}
        try:
            if data.get("generate"):
                return jsonify(generate_exam_sittings(conn, actor.get("program_scopes") or scopes)), 201
            return jsonify(create_exam_sitting(conn, data, actor.get("program_scopes") or scopes)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/elearn/sittings/<int:sitting_id>/verify", methods=["POST"])
def ops_elearn_sitting_verify(sitting_id):
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "teaching.exam_integrity")
        if err:
            return err[0]
        from elearn_ops import verify_exam_sitting

        try:
            return jsonify(verify_exam_sitting(conn, sitting_id, request.get_json(silent=True) or {}))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/elearn/sittings/<int:sitting_id>/selfie", methods=["POST"])
def ops_elearn_sitting_selfie(sitting_id):
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "teaching.exam_integrity")
        if err:
            return err[0]
        f = request.files.get("file")
        if not f:
            return json_error("Cần file ảnh selfie.", 400)
        from elearn_ops import save_exam_selfie

        try:
            return jsonify(save_exam_selfie(conn, sitting_id, f))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/elearn/meetings", methods=["GET", "POST"])
def ops_elearn_meetings():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "teaching.return_meetings", "student.return_meetings")
        if err:
            return err[0]
        from elearn_ops import _student_ident, create_return_meeting, list_return_meetings

        codes = set(actor.get("permission_codes") or [])
        email = ""
        if "teaching.return_meetings" not in codes and not actor.get("is_admin"):
            email = (_student_ident(conn, actor).get("student_email") or "")
        if request.method == "GET":
            return jsonify(list_return_meetings(conn, actor.get("program_scopes") or scopes, q=q, student_email=email))
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.return_meetings"):
            return json_error(deny_write_message("teaching.return_meetings"), 403)
        try:
            return jsonify(create_return_meeting(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/elearn/paused-students", methods=["GET"])
def ops_elearn_paused_students():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        actor, err = _elearn_actor(conn, "teaching.return_meetings")
        if err:
            return err[0]
        from elearn_ops import list_paused_students

        return jsonify(list_paused_students(conn, actor.get("program_scopes") or scopes))


# ---------------------------------------------------------------------------
# Class lessons (bài giảng theo lớp–môn)
# ---------------------------------------------------------------------------
@app.route("/ops/class-lesson-offerings", methods=["GET"])
def ops_class_lesson_offerings():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        from class_lessons import list_assignments_for_lessons, seed_class_lessons

        seed_class_lessons(conn)
        conn.commit()
        return jsonify(list_assignments_for_lessons(conn, scopes))


@app.route("/ops/teaching-assignments/<int:assignment_id>/lessons", methods=["GET"])
def ops_assignment_lessons(assignment_id):
    published_only = (request.args.get("published_only") or "") in ("1", "true", "yes")
    with get_db() as conn:
        from class_lessons import list_class_lessons, seed_class_lessons

        seed_class_lessons(conn)
        conn.commit()
        try:
            return jsonify(list_class_lessons(conn, assignment_id, published_only=published_only))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/teaching-assignments/<int:assignment_id>/lessons/import", methods=["POST"])
def ops_assignment_lessons_import(assignment_id):
    data = request.get_json(silent=True) or {}
    publish = bool(data.get("publish"))
    replace = bool(data.get("replace"))
    with get_db() as conn:
        from class_lessons import import_lessons_from_syllabus

        try:
            result = import_lessons_from_syllabus(
                conn, assignment_id, publish=publish, replace=replace
            )
        except ValueError as e:
            return json_error(str(e), 404)
    return jsonify(result), 201


@app.route("/ops/teaching-assignments/<int:assignment_id>/lessons", methods=["POST"])
def ops_assignment_lessons_create(assignment_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from class_lessons import add_class_lesson

        try:
            lesson = add_class_lesson(conn, assignment_id, data)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(lesson), 201


@app.route("/ops/class-lessons/<int:lesson_id>", methods=["GET"])
def ops_class_lesson_detail(lesson_id):
    as_student = (request.args.get("as_student") or "") in ("1", "true", "yes")
    email = (
        request.headers.get("X-Student-Email")
        or request.args.get("email")
        or ""
    ).strip()
    with get_db() as conn:
        from class_lessons import attach_chapter_work, get_class_lesson, seed_class_lessons

        seed_class_lessons(conn)
        conn.commit()
        detail = get_class_lesson(conn, lesson_id, as_student=as_student)
        if detail:
            attach_chapter_work(conn, detail, student_email=email)
    if not detail:
        return json_error("Lesson not found or not published", 404)
    return jsonify(detail)


@app.route("/ops/class-lessons/<int:lesson_id>", methods=["PATCH"])
def ops_class_lesson_update(lesson_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from class_lessons import update_class_lesson

        detail = update_class_lesson(conn, lesson_id, data)
    if not detail:
        return json_error("Lesson not found", 404)
    return jsonify(detail)


@app.route("/ops/class-lessons/<int:lesson_id>/upload", methods=["POST"])
def ops_class_lesson_upload(lesson_id):
    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    material_type = (request.form.get("material_type") or "slide").strip()
    release_status = (request.form.get("release_status") or "draft").strip()
    if release_status not in ("draft", "released"):
        release_status = "draft"
    uploaded_by = (request.form.get("uploaded_by") or request.headers.get("X-Actor") or "").strip()
    f = request.files.get("file")
    from course_content import allowed_material_filename
    from class_lessons import attach_file_to_lesson
    import uuid as _uuid

    file_path = None
    stored_name = None
    original_filename = None
    mime_type = None
    file_size = 0
    if f and f.filename:
        if not allowed_material_filename(f.filename):
            return json_error("File type not allowed", 400)
        original_filename = f.filename
        stored_name = f"{_uuid.uuid4().hex}_{f.filename}"
        dest = UPLOADS_DIR / "course_materials"
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / stored_name
        f.save(str(path))
        file_path = str(path)
        mime_type = f.mimetype
        file_size = path.stat().st_size
        if not title:
            title = Path(original_filename).stem
    if not title:
        return json_error("title or file required", 400)
    with get_db() as conn:
        try:
            row = attach_file_to_lesson(
                conn,
                lesson_id,
                title=title,
                description=description,
                material_type=material_type,
                original_filename=original_filename,
                stored_name=stored_name,
                file_path=file_path,
                mime_type=mime_type,
                file_size=file_size,
                uploaded_by=uploaded_by,
                release_status=release_status,
            )
        except ValueError as e:
            if file_path:
                Path(file_path).unlink(missing_ok=True)
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/class-lessons/<int:lesson_id>/comments", methods=["GET"])
def ops_class_lesson_comments(lesson_id):
    with get_db() as conn:
        from class_lessons import list_lesson_comments

        return jsonify(list_lesson_comments(conn, lesson_id))


@app.route("/ops/class-lessons/<int:lesson_id>/comments", methods=["POST"])
def ops_class_lesson_comments_add(lesson_id):
    data = request.get_json(silent=True) or {}
    actor = request.headers.get("X-User-Id") or ""
    with get_db() as conn:
        from class_lessons import add_lesson_comment

        try:
            row = add_lesson_comment(
                conn,
                lesson_id,
                body=data.get("body") or "",
                author_name=data.get("author_name") or actor or "",
                author_email=data.get("author_email")
                or request.headers.get("X-Student-Email")
                or "",
                author_role=data.get("author_role") or "student",
                is_question=bool(data.get("is_question")),
                comment_type=data.get("comment_type"),
                parent_id=data.get("parent_id"),
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/class-lessons/<int:lesson_id>/views/open", methods=["POST"])
def ops_lesson_view_open(lesson_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from class_lessons import open_view_session

        try:
            mid = data.get("material_id")
            row = open_view_session(
                conn,
                lesson_id=lesson_id,
                material_id=int(mid) if mid not in (None, "") else None,
                student_email=data.get("student_email")
                or request.headers.get("X-Student-Email")
                or "",
                student_name=data.get("student_name") or "",
                user_id=None,
                user_agent=request.headers.get("User-Agent") or "",
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/lesson-views/<int:session_id>/heartbeat", methods=["POST"])
def ops_lesson_view_heartbeat(session_id):
    with get_db() as conn:
        from class_lessons import heartbeat_view_session

        try:
            return jsonify(heartbeat_view_session(conn, session_id))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/lesson-views/<int:session_id>/close", methods=["POST"])
def ops_lesson_view_close(session_id):
    with get_db() as conn:
        from class_lessons import close_view_session

        try:
            return jsonify(close_view_session(conn, session_id))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/class-lessons/<int:lesson_id>/learning-stats", methods=["GET"])
def ops_lesson_learning_stats(lesson_id):
    with get_db() as conn:
        from class_lessons import learning_stats_for_lesson

        try:
            return jsonify(learning_stats_for_lesson(conn, lesson_id))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route(
    "/ops/teaching-assignments/<int:assignment_id>/learning-stats",
    methods=["GET"],
)
def ops_assignment_learning_stats(assignment_id):
    with get_db() as conn:
        from class_lessons import learning_stats_for_assignment

        try:
            return jsonify(learning_stats_for_assignment(conn, assignment_id))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/lesson-comments", methods=["GET"])
def ops_lesson_comments_inbox():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        from class_lessons import list_comments_inbox, list_comment_filter_options

        items = list_comments_inbox(
            conn,
            scopes=scopes,
            course_id=request.args.get("course_id", type=int),
            class_id=request.args.get("class_id", type=int),
            lesson_no=request.args.get("lesson_no", type=int),
            assignment_id=request.args.get("assignment_id", type=int),
            comment_type=(request.args.get("comment_type") or "").strip() or None,
            q=(request.args.get("q") or "").strip(),
        )
        return jsonify(
            {
                "items": items,
                "filters": list_comment_filter_options(conn, scopes),
            }
        )


@app.route("/ops/student/lessons", methods=["GET"])
def ops_student_lessons():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    email = (request.args.get("email") or request.headers.get("X-Student-Email") or "").strip()
    with get_db() as conn:
        from class_lessons import list_student_lessons, seed_class_lessons

        seed_class_lessons(conn)
        conn.commit()
        return jsonify(
            apply_qa_rows(
                "material",
                list_student_lessons(
                    conn, scopes=scopes, student_email=email or None, q=q
                ),
            )
        )


@app.route("/ops/cohort-options", methods=["GET"])
def ops_cohort_options():
    with get_db() as conn:
        from ops_data import ensure_ops_tables, format_cohort_label

        cur = conn.cursor()
        ensure_ops_tables(cur)
        options = []
        seen = set()

        def add(value, label):
            value = str(value or "").strip()
            if not value or value in seen:
                return
            seen.add(value)
            options.append({"value": value, "label": label or value})

        for no, ys, ye, year in cur.execute(
            "SELECT IFNULL(cohort_no,''), IFNULL(year_start,''), IFNULL(year_end,''), "
            "IFNULL(cohort_year,'') FROM class_groups"
        ).fetchall():
            label = format_cohort_label(no, ys, ye, year)
            add(no or year, label)
        try:
            for code in cur.execute(
                "SELECT DISTINCT intake_code FROM fee_intake_plans WHERE IFNULL(intake_code,'') != ''"
            ).fetchall():
                add(code[0], f"Khóa {code[0]}")
        except Exception:
            pass
    return jsonify(options)


@app.route("/ops/scholarship-basis", methods=["GET", "POST"])
def ops_scholarship_basis():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from coord_ops import ensure_coord_tables

        cur = conn.cursor()
        ensure_coord_tables(cur)
        prog = (request.args.get("program_code") or (request.get_json(silent=True) or {}).get("program_code") or "").strip().upper()
        if request.method == "GET":
            rows = cur.execute(
                "SELECT c.id, c.code, c.name, c.semester, "
                "CASE WHEN b.id IS NULL THEN 0 ELSE 1 END "
                "FROM courses c "
                "JOIN program_versions v ON v.id = c.program_version_id "
                "LEFT JOIN scholarship_basis b ON b.course_id = c.id AND b.program_code = v.program_code "
                "WHERE c.semester = 1 AND (? = '' OR v.program_code = ?) "
                "ORDER BY v.program_code, c.sort_order, c.code",
                (prog, prog),
            ).fetchall()
            return jsonify([
                {"id": r[0], "code": r[1], "name": r[2], "semester": r[3], "selected": bool(r[4])}
                for r in rows
            ])
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.grades") and not can_write_perm(actor, "programs.courses"):
            return json_error(deny_write_message("teaching.grades"), 403)
        data = request.get_json(silent=True) or {}
        prog = (data.get("program_code") or "").strip().upper()
        ids = []
        for raw in data.get("course_ids") or []:
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        ids = ids[:5]
        if not prog:
            return json_error("Chọn chương trình", 400)
        cur.execute("DELETE FROM scholarship_basis WHERE program_code = ?", (prog,))
        for cid in ids:
            ok = cur.execute(
                "SELECT 1 FROM courses c JOIN program_versions v ON v.id = c.program_version_id "
                "WHERE c.id = ? AND v.program_code = ? AND c.semester = 1",
                (cid, prog),
            ).fetchone()
            if ok:
                cur.execute(
                    "INSERT OR IGNORE INTO scholarship_basis (program_code, course_id) VALUES (?, ?)",
                    (prog, cid),
                )
        conn.commit()
    return jsonify({"program_code": prog, "course_ids": ids})


@app.route("/ops/classes", methods=["GET"])
def ops_classes():
    scopes = _parse_scopes_from_request()
    cohort = (request.args.get("cohort") or "").strip()
    with get_db() as conn:
        cur = conn.cursor()
        from ops_data import _scopes_sql, ensure_ops_tables, format_cohort_label

        ensure_ops_tables(cur)
        frag, params = _scopes_sql(scopes, "cg.program_code")
        sql = (
            "SELECT cg.id, cg.program_code, cg.name, cg.cohort_year, cg.status, "
            "v.version_code, COUNT(DISTINCT cs.id) AS student_count, "
            "IFNULL(cg.cohort_no,''), IFNULL(cg.year_start,''), IFNULL(cg.year_end,'') "
            "FROM class_groups cg "
            "LEFT JOIN program_versions v ON v.id = cg.program_version_id "
            "LEFT JOIN class_students cs ON cs.class_id = cg.id "
            f"WHERE {frag} "
        )
        if cohort:
            sql += " AND (CAST(IFNULL(cg.cohort_year,'') AS TEXT) = ? OR IFNULL(cg.cohort_no,'') = ?) "
            params.extend([cohort, cohort])
        sql += "GROUP BY cg.id ORDER BY cg.program_code, cg.name"
        rows = cur.execute(sql, params).fetchall()
    return jsonify(
        [
            {
                "id": r[0],
                "program_code": r[1],
                "name": r[2],
                "cohort_year": r[3],
                "status": r[4],
                "version_code": r[5],
                "student_count": r[6],
                "cohort_label": format_cohort_label(r[7], r[8], r[9], r[3]),
            }
            for r in rows
        ]
    )


@app.route("/ops/faculty", methods=["GET"])
def ops_faculty():
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        from mba_ops import ensure_mba_tables

        cur = conn.cursor()
        ensure_mba_tables(cur)
        sql = (
            "SELECT id, full_name, role_type, degree, title, organization, specialty, "
            "teachable_courses, email, phone, nationality, passport_no, bank_account, cv_note, "
            "teaching_history_note, contract_status, contract_no, grade_return_date, "
            "cfvg_payment_status, insurance_note "
            "FROM faculty WHERE 1=1"
        )
        params: list = []
        if q:
            sql += " AND (full_name LIKE ? OR specialty LIKE ? OR organization LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        sql += " ORDER BY role_type, full_name"
        rows = cur.execute(sql, params).fetchall()
        actor = _resolve_ops_actor(conn)
        show_sensitive = bool(actor.get("ok") and (
            actor.get("is_admin")
            or "teaching.faculty.sensitive" in (actor.get("permission_codes") or [])
        ))
    return jsonify(
        [
            {
                "id": r[0],
                "full_name": r[1],
                "role_type": r[2],
                "degree": r[3],
                "title": r[4],
                "organization": r[5],
                "specialty": r[6],
                "teachable_courses": r[7],
                "email": r[8],
                "phone": r[9] or "",
                "nationality": r[10] or "",
                "passport_no": (r[11] or "") if show_sensitive else "",
                "bank_account": (r[12] or "") if show_sensitive else "",
                "cv_note": r[13] or "",
                "teaching_history_note": r[14] or "",
                "contract_status": r[15] or "",
                "contract_no": r[16] or "",
                "grade_return_date": r[17] or "",
                "cfvg_payment_status": r[18] or "",
                "insurance_note": r[19] or "",
            }
            for r in rows
        ]
    )


@app.route("/ops/teaching-assignments", methods=["GET"])
def ops_teaching_assignments():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        cur = conn.cursor()
        from ops_data import _scopes_sql, ensure_ops_tables, format_cohort_label

        ensure_ops_tables(cur)
        frag, params = _scopes_sql(scopes, "cg.program_code")
        cohort = (request.args.get("cohort") or "").strip()
        sql = (
            "SELECT ta.id, cg.name, cg.program_code, c.code, c.name, "
            "fl.full_name, fe.full_name, ta.status, "
            "IFNULL(cg.cohort_no,''), IFNULL(cg.year_start,''), IFNULL(cg.year_end,''), "
            "IFNULL(cg.cohort_year,'') "
            "FROM teaching_assignments ta "
            "JOIN class_groups cg ON cg.id = ta.class_id "
            "JOIN courses c ON c.id = ta.course_id "
            "LEFT JOIN faculty fl ON fl.id = ta.lecturer_id "
            "LEFT JOIN faculty fe ON fe.id = ta.expert_id "
            f"WHERE {frag} "
        )
        if cohort:
            sql += " AND (CAST(IFNULL(cg.cohort_year,'') AS TEXT) = ? OR IFNULL(cg.cohort_no,'') = ?) "
            params.extend([cohort, cohort])
        sql += "ORDER BY cg.program_code, c.code, cg.name"
        rows = cur.execute(sql, params).fetchall()
    return jsonify(
        [
            {
                "id": r[0],
                "class_name": r[1],
                "program_code": r[2],
                "course_code": r[3],
                "course_name": r[4],
                "lecturer": r[5] or "—",
                "expert": r[6] or "—",
                "status": r[7],
                "cohort_label": format_cohort_label(r[8], r[9], r[10], r[11]),
            }
            for r in rows
        ]
    )


@app.route("/ops/teaching-assignments", methods=["POST"])
def ops_teaching_assignments_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.assign"):
            return json_error(deny_write_message("teaching.assign"), 403)
        from ops_crud import create_teaching_assignment_row

        try:
            row = create_teaching_assignment_row(conn, data)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/teaching-assignments/<int:assignment_id>/stamp-sessions", methods=["POST"])
def ops_teaching_assignment_stamp(assignment_id):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.assign"):
            return json_error(deny_write_message("teaching.assign"), 403)
        from class_lessons import stamp_faculty_sessions

        try:
            return jsonify(stamp_faculty_sessions(conn, assignment_id))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/classes/<int:class_id>/welcome-email", methods=["POST"])
def ops_class_welcome_email(class_id):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "classes.manage"):
            return json_error(deny_write_message("classes.manage"), 403)
        from mscm_coord import queue_class_welcome

        try:
            return jsonify(queue_class_welcome(conn, class_id))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/classes/<int:class_id>/grade-scheme", methods=["POST"])
def ops_class_grade_scheme(class_id):
    data = request.get_json(silent=True) or {}
    try:
        course_id = int(data["course_id"])
    except (KeyError, TypeError, ValueError):
        return json_error("course_id required", 400)
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.grades"):
            return json_error(deny_write_message("teaching.grades"), 403)
        from coord_ops import set_grade_scheme

        try:
            return jsonify(set_grade_scheme(conn, class_id, course_id, (data.get("scheme") or "").strip()))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/email-templates", methods=["GET", "POST"])
def ops_email_templates():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from mscm_coord import get_mail_template, list_mail_templates, save_mail_template

        if request.method == "GET" and request.args.get("catalog") == "1":
            return jsonify(list_mail_templates(conn))
        if request.method == "GET":
            prog = (request.args.get("program_code") or "MSCM").strip()
            return jsonify({
                "program_code": prog,
                "pass": get_mail_template(conn, prog, "pass"),
                "fail": get_mail_template(conn, prog, "fail"),
                "welcome": get_mail_template(conn, prog, "welcome"),
            })
        data = request.get_json(silent=True) or {}
        from ops_policy import can_write_perm, deny_write_message

        if not (
            can_write_perm(actor, "admissions.results")
            or can_write_perm(actor, "admissions.mail")
        ):
            return json_error(deny_write_message("admissions.mail"), 403)
        prog = (data.get("program_code") or "").strip()
        try:
            if (data.get("kind") or "").strip():
                saved = save_mail_template(
                    conn,
                    prog,
                    (data.get("kind") or "").strip(),
                    data.get("subject") or "",
                    data.get("body") or "",
                )
            else:
                saved = {
                    "pass": save_mail_template(conn, prog, "pass", data.get("pass_subject") or "", data.get("pass_body") or ""),
                    "fail": save_mail_template(conn, prog, "fail", data.get("fail_subject") or "", data.get("fail_body") or ""),
                }
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(saved)


@app.route("/ops/email-templates/send", methods=["POST"])
def ops_email_templates_send():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not (
            can_write_perm(actor, "admissions.mail")
            or can_write_perm(actor, "admissions.results")
        ):
            return json_error(deny_write_message("admissions.mail"), 403)
        from mscm_coord import render_mail, save_mail_template
        from ops_crud import queue_email
        from ops_data import _scopes_sql

        prog = (data.get("program_code") or "").strip().upper()
        kind = (data.get("kind") or "").strip()
        try:
            save_mail_template(conn, prog, kind, data.get("subject") or "", data.get("body") or "")
        except ValueError as e:
            return json_error(str(e), 400)
        status_for = {
            "pass": ("passed", "paid", "official"),
            "fail": ("failed",),
            "interview": ("interview",),
            "missing_docs": ("passed", "paid", "official"),
            "welcome": ("official",),
        }.get(kind, ())
        if not status_for:
            return json_error("Mẫu này chưa gắn nhóm ứng viên để gửi.", 400)
        cur = conn.cursor()
        frag, params = _scopes_sql(actor.get("program_scopes"), "a.program_code")
        ph = ",".join("?" * len(status_for))
        params = [prog, *status_for, *params]
        people = cur.execute(
            "SELECT full_name, email, program_code FROM applications a "
            f"WHERE a.program_code = ? AND a.status IN ({ph}) AND IFNULL(a.email,'') != '' AND {frag}",
            params,
        ).fetchall()
        sent = 0
        for name, email, program in people:
            subject, body = render_mail(conn, program, kind, name=name or "", program=program or prog)
            queue_email(conn, kind=kind, recipient=email, subject=subject, body=body)
            sent += 1
    return jsonify({"sent": sent, "program_code": prog, "kind": kind})


@app.route("/ops/alumni/<int:alumni_id>/portal-account", methods=["POST"])
def ops_alumni_portal_account(alumni_id):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "alumni.members"):
            return json_error(deny_write_message("alumni.members"), 403)
        from mscm_coord import provision_alumni_portal

        try:
            return jsonify(provision_alumni_portal(conn, alumni_id))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/alumni/me", methods=["GET", "PATCH"])
def ops_alumni_me():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from mscm_coord import alumni_portal_for_user, update_alumni_self

        if request.method == "GET":
            row = alumni_portal_for_user(conn, int(actor["user_id"]))
            if not row:
                return json_error("Tài khoản chưa gắn hồ sơ cựu học viên.", 404)
            return jsonify(row)
        try:
            return jsonify(update_alumni_self(conn, int(actor["user_id"]), request.get_json(silent=True) or {}))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/attendance-sessions", methods=["POST"])
def ops_attendance_sessions_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "teaching.schedule"):
            return json_error(deny_write_message("teaching.schedule"), 403)
        from ops_crud import create_attendance_session_row

        try:
            row = create_attendance_session_row(conn, data)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row), 201


# —— Practice homework (bài thực hành online theo mẫu Word/Excel) ——

@app.route("/ops/practice/teaching-assignments", methods=["GET"])
def ops_practice_ta_list():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        from practice_homework import list_teaching_assignments_with_practice
        from mc_quiz import enrich_ta_list_with_mc

        rows = list_teaching_assignments_with_practice(conn, scopes)
        return jsonify(enrich_ta_list_with_mc(conn, rows))


@app.route("/ops/practice/template.xlsx", methods=["GET"])
def ops_practice_template_xlsx():
    from flask import Response
    from practice_homework import export_template_xlsx_bytes

    data = export_template_xlsx_bytes()
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=Mau_Thuc_hanh.xlsx"
        },
    )


@app.route(
    "/ops/practice/teaching-assignments/<int:ta_id>/homeworks",
    methods=["GET"],
)
def ops_practice_homeworks_list(ta_id):
    with get_db() as conn:
        from practice_homework import list_homeworks_for_ta, _ta_meta

        meta = _ta_meta(conn, ta_id)
        if not meta:
            return json_error("Teaching assignment not found", 404)
        return jsonify({"meta": meta, "items": list_homeworks_for_ta(conn, ta_id)})


@app.route(
    "/ops/practice/teaching-assignments/<int:ta_id>/homeworks/import",
    methods=["POST"],
)
def ops_practice_homework_import(ta_id):
    f = request.files.get("file")
    if not f or not f.filename:
        return json_error("Cần file mẫu (.doc/.docx/.xlsx)", 400)
    title = (request.form.get("title") or "").strip()
    publish = (request.form.get("publish") or "").lower() in ("1", "true", "yes")
    raw = f.read()
    actor = request.headers.get("X-User-Id") or ""
    with get_db() as conn:
        from practice_homework import import_homework_from_file

        try:
            hw = import_homework_from_file(
                conn,
                ta_id,
                filename=f.filename,
                raw=raw,
                title=title,
                created_by=str(actor),
                publish=publish,
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(hw), 201


@app.route("/ops/practice/homeworks/<int:hw_id>", methods=["GET"])
def ops_practice_homework_get(hw_id):
    with get_db() as conn:
        from practice_homework import get_homework

        try:
            return jsonify(get_homework(conn, hw_id))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/practice/homeworks/<int:hw_id>/status", methods=["POST"])
def ops_practice_homework_status(hw_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from practice_homework import set_homework_status

        try:
            return jsonify(set_homework_status(conn, hw_id, data.get("status") or ""))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/practice/homeworks/<int:hw_id>/submissions", methods=["GET"])
def ops_practice_homework_submissions(hw_id):
    with get_db() as conn:
        from practice_homework import list_submissions, get_homework

        try:
            get_homework(conn, hw_id, include_questions=False)
        except ValueError as e:
            return json_error(str(e), 404)
        return jsonify(list_submissions(conn, hw_id))


@app.route("/ops/practice/student/homeworks", methods=["GET"])
def ops_practice_student_homeworks():
    email = (request.headers.get("X-Student-Email") or request.args.get("email") or "").strip()
    with get_db() as conn:
        from practice_homework import list_published_for_student
        from mc_quiz import list_published_for_student as list_mc_for_student

        practice = list_published_for_student(conn, student_email=email)
        for p in practice:
            p["kind"] = "practice"
        mc = list_mc_for_student(conn, student_email=email)
        # Merge: practice keeps own ids; MC ids remain mc quiz ids with kind
        merged = practice + mc
        merged.sort(key=lambda x: (x.get("due_at") or "", x.get("id") or 0), reverse=True)
        return jsonify(merged)


@app.route("/ops/practice/homeworks/<int:hw_id>/start", methods=["POST"])
def ops_practice_start(hw_id):
    data = request.get_json(silent=True) or {}
    email = (
        (request.headers.get("X-Student-Email") or data.get("student_email") or "")
        .strip()
    )
    with get_db() as conn:
        from practice_homework import start_or_get_submission

        try:
            return jsonify(
                start_or_get_submission(
                    conn,
                    hw_id,
                    student_email=email,
                    student_name=data.get("student_name") or "",
                    student_code=data.get("student_code") or "",
                )
            )
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/practice/submissions/<int:sub_id>", methods=["GET"])
def ops_practice_submission_get(sub_id):
    with get_db() as conn:
        from practice_homework import get_submission

        try:
            return jsonify(get_submission(conn, sub_id))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/practice/submissions/<int:sub_id>/answers", methods=["POST"])
def ops_practice_submission_answers(sub_id):
    data = request.get_json(silent=True) or {}
    answers = data.get("answers") or {}
    submit = bool(data.get("submit"))
    with get_db() as conn:
        from practice_homework import save_answers

        try:
            return jsonify(save_answers(conn, sub_id, answers, submit=submit))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/practice/submissions/<int:sub_id>/grade", methods=["POST"])
def ops_practice_submission_grade(sub_id):
    data = request.get_json(silent=True) or {}
    score = data.get("score")
    try:
        score_f = float(score) if score is not None and score != "" else None
    except Exception:
        return json_error("Điểm không hợp lệ", 400)
    with get_db() as conn:
        from practice_homework import grade_submission

        try:
            return jsonify(
                grade_submission(
                    conn, sub_id, score=score_f, note=data.get("note") or ""
                )
            )
        except ValueError as e:
            return json_error(str(e), 400)


# —— Multiple-choice quizzes ——

@app.route("/ops/mc/template.xlsx", methods=["GET"])
def ops_mc_template_xlsx():
    from flask import Response
    from mc_quiz import export_template_xlsx_bytes

    data = export_template_xlsx_bytes()
    return Response(
        data,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=Template_MultipleChoice.xlsx"
        },
    )


@app.route("/ops/mc/teaching-assignments/<int:ta_id>/quizzes", methods=["GET"])
def ops_mc_quizzes_list(ta_id):
    with get_db() as conn:
        from mc_quiz import list_quizzes_for_ta, _ta_meta

        meta = _ta_meta(conn, ta_id)
        if not meta:
            return json_error("Teaching assignment not found", 404)
        return jsonify({"meta": meta, "items": list_quizzes_for_ta(conn, ta_id)})


@app.route(
    "/ops/mc/teaching-assignments/<int:ta_id>/quizzes/import",
    methods=["POST"],
)
def ops_mc_quiz_import(ta_id):
    f = request.files.get("file")
    if not f or not f.filename:
        return json_error("Cần file mẫu (.xlsx)", 400)
    title = (request.form.get("title") or "").strip()
    publish = (request.form.get("publish") or "").lower() in ("1", "true", "yes")
    raw = f.read()
    actor = request.headers.get("X-User-Id") or ""
    with get_db() as conn:
        from mc_quiz import import_quiz_from_file

        try:
            quiz = import_quiz_from_file(
                conn,
                ta_id,
                filename=f.filename,
                raw=raw,
                title=title,
                created_by=str(actor),
                publish=publish,
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(quiz), 201


@app.route("/ops/mc/quizzes/<int:quiz_id>", methods=["GET"])
def ops_mc_quiz_get(quiz_id):
    with get_db() as conn:
        from mc_quiz import get_quiz

        try:
            return jsonify(get_quiz(conn, quiz_id))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/mc/quizzes/<int:quiz_id>/status", methods=["POST"])
def ops_mc_quiz_status(quiz_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from mc_quiz import set_quiz_status

        try:
            return jsonify(set_quiz_status(conn, quiz_id, data.get("status") or ""))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/mc/quizzes/<int:quiz_id>/submissions", methods=["GET"])
def ops_mc_quiz_submissions(quiz_id):
    with get_db() as conn:
        from mc_quiz import list_submissions, get_quiz

        try:
            get_quiz(conn, quiz_id, include_questions=False)
        except ValueError as e:
            return json_error(str(e), 404)
        return jsonify(list_submissions(conn, quiz_id))


@app.route("/ops/mc/quizzes/<int:quiz_id>/start", methods=["POST"])
def ops_mc_start(quiz_id):
    data = request.get_json(silent=True) or {}
    email = (
        (request.headers.get("X-Student-Email") or data.get("student_email") or "")
        .strip()
    )
    with get_db() as conn:
        from mc_quiz import start_or_get_submission

        try:
            return jsonify(
                start_or_get_submission(
                    conn,
                    quiz_id,
                    student_email=email,
                    student_name=data.get("student_name") or "",
                    student_code=data.get("student_code") or "",
                )
            )
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/mc/submissions/<int:sub_id>", methods=["GET"])
def ops_mc_submission_get(sub_id):
    with get_db() as conn:
        from mc_quiz import get_submission

        try:
            return jsonify(get_submission(conn, sub_id, for_student=False))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/mc/submissions/<int:sub_id>/answers", methods=["POST"])
def ops_mc_submission_answers(sub_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from mc_quiz import save_answers

        try:
            return jsonify(
                save_answers(
                    conn,
                    sub_id,
                    data.get("answers") or {},
                    submit=bool(data.get("submit")),
                )
            )
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/attendance", methods=["GET"])
def ops_attendance():
    scopes = _parse_scopes_from_request()
    student_id = request.args.get("student_id", type=int)
    with get_db() as conn:
        if student_id:
            from lesson_attendance import list_student_attendance

            return jsonify(list_student_attendance(conn, student_id, scopes))
        from lesson_attendance import list_sessions_enriched

        return jsonify(list_sessions_enriched(conn, scopes))


@app.route("/ops/attendance/sessions/<int:session_id>", methods=["GET"])
def ops_attendance_session_get(session_id):
    with get_db() as conn:
        from lesson_attendance import get_roster

        try:
            return jsonify(get_roster(conn, session_id))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/attendance/lessons/<int:lesson_id>/session", methods=["POST"])
def ops_attendance_ensure_lesson(lesson_id):
    with get_db() as conn:
        from lesson_attendance import ensure_session_for_lesson, get_roster

        try:
            sess = ensure_session_for_lesson(conn, lesson_id)
            return jsonify(get_roster(conn, sess["id"]))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/attendance/sessions/<int:session_id>/rounds", methods=["POST"])
def ops_attendance_set_round(session_id):
    data = request.get_json(silent=True) or {}
    try:
        round_no = int(data.get("round") or 0)
    except Exception:
        return json_error("round không hợp lệ", 400)
    open_ = bool(data.get("open"))
    with get_db() as conn:
        from lesson_attendance import set_round_open, get_roster

        try:
            set_round_open(conn, session_id, round_no, open_)
            return jsonify(get_roster(conn, session_id))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/attendance/sessions/<int:session_id>/marks", methods=["PUT"])
def ops_attendance_save_marks(session_id):
    data = request.get_json(silent=True) or {}
    marks = data.get("marks") or []
    with get_db() as conn:
        from lesson_attendance import save_marks

        try:
            return jsonify(save_marks(
                conn,
                session_id,
                marks,
                source="faculty",
                reason=str(data.get("reason") or ""),
                actor=str(request.headers.get("X-User-Id") or ""),
            ))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/attendance/sessions/<int:session_id>/qr/rotate", methods=["POST"])
def ops_attendance_qr_rotate(session_id):
    data = request.get_json(silent=True) or {}
    try:
        round_no = int(data.get("round") or 0)
    except Exception:
        return json_error("round không hợp lệ", 400)
    public_base = (data.get("public_base") or request.host_url or "").rstrip("/")
    # Prefer frontend URL if provided by client
    actor = request.headers.get("X-User-Id") or ""
    with get_db() as conn:
        from lesson_attendance import rotate_qr_token

        try:
            return jsonify(
                rotate_qr_token(
                    conn,
                    session_id,
                    round_no,
                    created_by=str(actor),
                    public_base=public_base,
                )
            )
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/attendance/scan", methods=["POST"])
def ops_attendance_scan():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from lesson_attendance import scan_qr_checkin

        actor = _resolve_ops_actor(conn)
        try:
            return jsonify(
                scan_qr_checkin(
                    conn,
                    token=data.get("token") or "",
                    user_id=actor.get("user_id"),
                    student_name=data.get("student_name") or "",
                )
            )
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/alumni", methods=["GET"])
def ops_alumni():
    scopes = _parse_scopes_from_request()
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        cur = conn.cursor()
        from ops_data import _scopes_sql, ensure_ops_tables

        ensure_ops_tables(cur)
        frag, params = _scopes_sql(scopes, "program_code")
        sql = (
            "SELECT id, full_name, program_code, cohort, class_name, email, phone, company, "
            "COALESCE(activity_keywords,''), COALESCE(cccd,''), COALESCE(portal_login,'') "
            f"FROM alumni_members WHERE {frag}"
        )
        if q:
            like = f"%{q}%"
            sql += (
                " AND (full_name LIKE ? OR email LIKE ? OR company LIKE ? "
                "OR COALESCE(activity_keywords,'') LIKE ? OR program_code LIKE ? "
                "OR COALESCE(cccd,'') LIKE ?)"
            )
            params.extend([like, like, like, like, like, like])
        sql += " ORDER BY program_code, full_name"
        rows = cur.execute(sql, params).fetchall()
    return jsonify(
        apply_qa_rows(
            "alumni",
            [
                {
                    "id": r[0],
                    "full_name": r[1],
                    "program_code": r[2],
                    "cohort": r[3],
                    "class_name": r[4],
                    "email": r[5],
                    "phone": r[6],
                    "company": r[7],
                    "activity_keywords": r[8],
                    "cccd": r[9] if len(r) > 9 else "",
                    "portal_login": r[10] if len(r) > 10 else "",
                }
                for r in rows
            ],
        )
    )


@app.route("/ops/alumni-events", methods=["GET"])
def ops_alumni_events():
    q = (request.args.get("q") or "").strip()
    with get_db() as conn:
        cur = conn.cursor()
        from ops_data import ensure_ops_tables

        ensure_ops_tables(cur)
        sql = (
            "SELECT e.id, e.title, e.event_date, e.location, e.program_filter, e.status, e.description, "
            "(SELECT COUNT(*) FROM alumni_event_invitees i WHERE i.event_id = e.id) "
            "FROM alumni_events e WHERE 1=1"
        )
        params: list = []
        if q:
            like = f"%{q}%"
            sql += " AND (e.title LIKE ? OR e.location LIKE ? OR COALESCE(e.description,'') LIKE ?)"
            params.extend([like, like, like])
        sql += " ORDER BY e.event_date"
        rows = cur.execute(sql, params).fetchall()
    return jsonify(
        apply_qa_rows(
            "alumni_event",
            [
                {
                    "id": r[0],
                    "title": r[1],
                    "event_date": r[2],
                    "location": r[3],
                    "program_filter": r[4],
                    "status": r[5],
                    "description": r[6],
                    "invitee_count": r[7] or 0,
                }
                for r in rows
            ],
        )
    )


@app.route("/ops/alumni-events/<int:event_id>/invitees", methods=["GET", "POST"])
def ops_alumni_event_invitees(event_id):
    with get_db() as conn:
        from ops_crud import queue_alumni_event_emails, set_alumni_event_invitees
        from ops_data import ensure_ops_tables

        cur = conn.cursor()
        ensure_ops_tables(cur)
        if request.method == "GET":
            rows = cur.execute(
                "SELECT i.alumni_id, m.full_name, m.email, m.program_code, m.activity_keywords, "
                "i.email_status "
                "FROM alumni_event_invitees i "
                "JOIN alumni_members m ON m.id = i.alumni_id "
                "WHERE i.event_id = ? ORDER BY m.full_name",
                (event_id,),
            ).fetchall()
            return jsonify(
                [
                    {
                        "alumni_id": r[0],
                        "full_name": r[1],
                        "email": r[2],
                        "program_code": r[3],
                        "activity_keywords": r[4],
                        "email_status": r[5],
                    }
                    for r in rows
                ]
            )
        data = request.get_json(silent=True) or {}
        ids = data.get("alumni_ids") or data.get("invitee_ids") or []
        try:
            result = set_alumni_event_invitees(conn, event_id, ids)
            if data.get("send_email"):
                result["email"] = queue_alumni_event_emails(conn, event_id)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/alumni-events/<int:event_id>/send-invites", methods=["POST"])
def ops_alumni_event_send_invites(event_id):
    with get_db() as conn:
        from ops_crud import queue_alumni_event_emails

        try:
            return jsonify(queue_alumni_event_emails(conn, event_id))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/admission-rounds", methods=["POST"])
def ops_admission_rounds_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not actor["is_admin"] and "admissions.rounds" not in actor["permission_codes"]:
            return json_error("Bạn không có quyền admissions.rounds.", 403)
        from ops_crud import create_admission_round
        try:
            row = create_admission_round(conn, data)
        except ValueError as e:
            return json_error(str(e), 400)
        except Exception as e:
            if "unique" in str(e).lower():
                return json_error("Mã đợt bị trùng, vui lòng nhập đợt khác", 400)
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/admission-rounds/<int:round_id>", methods=["GET", "PATCH"])
def ops_admission_round_one(round_id):
    with get_db() as conn:
        from admission_ops import get_admission_round, update_admission_round

        if request.method == "GET":
            row = get_admission_round(conn, round_id)
            if not row:
                return json_error("Không tìm thấy đợt tuyển sinh", 404)
            return jsonify(row)
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not actor["is_admin"] and "admissions.rounds" not in actor["permission_codes"]:
            return json_error("Bạn không có quyền admissions.rounds.", 403)
        try:
            row = update_admission_round(conn, round_id, request.get_json(silent=True) or {})
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row)


@app.route("/ops/admission-doc-types", methods=["GET", "POST"])
def ops_admission_doc_types():
    with get_db() as conn:
        actor, caps = _round_doc_actor_caps(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        codes = set(actor.get("permission_codes") or [])
        catalog = actor["is_admin"] or "admissions.doc_types" in codes or "admin.status_catalog" in codes
        if request.method == "GET":
            if not caps["view"] and not catalog:
                return json_error("Bạn không có quyền xem phân loại tài liệu.", 403)
            from admission_ops import list_doc_types

            return jsonify(list_doc_types(conn, include_inactive=catalog or caps["manage"]))
        if not catalog and not caps["manage"]:
            return json_error("Bạn không có quyền khai báo loại tài liệu.", 403)
        from admission_ops import create_doc_type

        try:
            row = create_doc_type(conn, request.get_json(silent=True) or {})
        except ValueError as e:
            return json_error(str(e), 400)
        return jsonify(row), 201


@app.route("/ops/admission-round-docs", methods=["GET"])
def ops_admission_round_docs_search():
    q = (request.args.get("q") or "").strip()
    round_id = request.args.get("round_id", type=int)
    program_code = (request.args.get("program_code") or "").strip()
    with get_db() as conn:
        actor, caps = _round_doc_actor_caps(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not caps["view"]:
            return json_error("Bạn không có quyền xem tài liệu đợt tuyển sinh.", 403)
        from admission_ops import list_round_docs

        year_raw = (request.args.get("year") or "").strip()
        try:
            year = int(year_raw) if year_raw else None
        except ValueError:
            year = None
        rows = list_round_docs(
            conn,
            round_id=round_id,
            q=q,
            program_code=program_code,
            scopes=actor.get("program_scopes"),
            year=year,
            doc_scope=(request.args.get("doc_scope") or "").strip(),
            require_year=True,
        )
        for r in rows:
            r.pop("file_path", None)
            r["can_download"] = caps["download"]
            r["can_manage"] = caps["manage"]
        return jsonify(rows)


@app.route("/ops/admission-rounds/<int:round_id>/docs", methods=["GET", "POST"])
def ops_admission_round_docs(round_id):
    if request.method == "GET":
        q = (request.args.get("q") or "").strip()
        program_code = (request.args.get("program_code") or "").strip()
        with get_db() as conn:
            actor, caps = _round_doc_actor_caps(conn)
            if not actor["ok"]:
                return json_error(actor["error"] or "Unauthorized", 401)
            if not caps["view"]:
                return json_error("Bạn không có quyền xem tài liệu đợt tuyển sinh.", 403)
            from admission_ops import list_round_docs

            rows = list_round_docs(
                conn,
                round_id=round_id,
                q=q,
                program_code=program_code,
                scopes=actor.get("program_scopes"),
            )
            for r in rows:
                r.pop("file_path", None)
                r["can_download"] = caps["download"]
                r["can_manage"] = caps["manage"]
            return jsonify(rows)
    with get_db() as conn:
        actor, caps = _round_doc_actor_caps(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not caps["manage"]:
            return json_error("Bạn không có quyền thêm/sửa tài liệu đợt tuyển sinh.", 403)
        from admission_ops import add_round_doc, save_round_doc_file

        title = (request.form.get("title") or "").strip()
        notes = (request.form.get("notes") or "").strip()
        program_codes = (request.form.get("program_codes") or "").strip()
        share_scope = (request.form.get("share_scope") or "").strip()
        cohort_code = (request.form.get("cohort_code") or "").strip()
        doc_type_id = request.form.get("doc_type_id", type=int)
        f = request.files.get("file")
        original = stored = path = mime = None
        size = 0
        try:
            if f and f.filename:
                original, stored, path, mime, size = save_round_doc_file(f)
            actor_label = f"user:{actor.get('user_id')}"
            row = add_round_doc(
                conn,
                round_id=round_id,
                title=title,
                doc_type_id=doc_type_id,
                notes=notes,
                program_codes=program_codes,
                share_scope=share_scope,
                cohort_code=cohort_code,
                original_filename=original,
                stored_name=stored,
                file_path=path,
                mime=mime,
                size_bytes=size,
                uploaded_by=actor_label,
            )
        except ValueError as e:
            if path:
                Path(path).unlink(missing_ok=True)
            return json_error(str(e), 400)
        row.pop("file_path", None)
        row["can_download"] = True
        row["can_manage"] = True
    return jsonify(row), 201


@app.route("/ops/admission-round-docs/<int:doc_id>", methods=["PATCH", "DELETE"])
def ops_admission_round_doc_one(doc_id):
    with get_db() as conn:
        actor, caps = _round_doc_actor_caps(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not caps["manage"]:
            return json_error("Bạn không có quyền cập nhật/xóa tài liệu đợt tuyển sinh.", 403)
        from admission_ops import delete_round_doc, save_round_doc_file, update_round_doc

        if request.method == "DELETE":
            ok = delete_round_doc(conn, doc_id)
            if not ok:
                return json_error("Không tìm thấy tài liệu", 404)
            return jsonify({"ok": True})
        title = (request.form.get("title") or (request.json or {}).get("title") if request.is_json else request.form.get("title"))
        if request.is_json:
            data = request.get_json(silent=True) or {}
            try:
                row = update_round_doc(
                    conn,
                    doc_id,
                    title=data.get("title"),
                    doc_type_id=data.get("doc_type_id"),
                    notes=data.get("notes"),
                    program_codes=data.get("program_codes"),
                    uploaded_by=f"user:{actor.get('user_id')}",
                )
            except ValueError as e:
                return json_error(str(e), 400)
        else:
            f = request.files.get("file")
            original = stored = path = mime = None
            size = None
            try:
                if f and f.filename:
                    original, stored, path, mime, size = save_round_doc_file(f)
                row = update_round_doc(
                    conn,
                    doc_id,
                    title=request.form.get("title"),
                    doc_type_id=request.form.get("doc_type_id", type=int),
                    notes=request.form.get("notes"),
                    program_codes=request.form.get("program_codes"),
                    original_filename=original,
                    stored_name=stored,
                    file_path=path,
                    mime=mime,
                    size_bytes=size,
                    uploaded_by=f"user:{actor.get('user_id')}",
                )
            except ValueError as e:
                if path:
                    Path(path).unlink(missing_ok=True)
                return json_error(str(e), 400)
        row.pop("file_path", None)
        row["can_download"] = True
        row["can_manage"] = True
        return jsonify(row)


@app.route("/ops/admission-round-docs/<int:doc_id>/file", methods=["GET"])
def ops_admission_round_doc_file(doc_id):
    inline = (request.args.get("inline") or "") in ("1", "true", "yes")
    with get_db() as conn:
        actor, caps = _round_doc_actor_caps(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if inline:
            if not caps["view"]:
                return json_error("Bạn không có quyền xem tài liệu này.", 403)
        elif not caps["download"]:
            return json_error("Bạn chỉ được xem, không được tải xuống tài liệu này.", 403)
        from admission_ops import get_round_doc

        meta = get_round_doc(conn, doc_id)
    if not meta:
        return json_error("Không tìm thấy tài liệu", 404)
    fp = meta.get("file_path")
    if not fp or not Path(fp).is_file():
        return json_error("Chưa có file đính kèm.", 404)
    download_name = meta.get("original_name") or "document.bin"
    mime = meta.get("mime") or "application/octet-stream"
    ext = Path(download_name).suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    if ext in mime_map:
        mime = mime_map[ext]
    return send_file(
        fp,
        as_attachment=not inline,
        download_name=download_name,
        mimetype=mime,
    )


@app.route("/ops/admission-round-docs/<int:doc_id>/preview", methods=["GET"])
def ops_admission_round_doc_preview(doc_id):
    with get_db() as conn:
        actor, caps = _round_doc_actor_caps(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not caps["view"]:
            return json_error("Bạn không có quyền xem tài liệu này.", 403)
        from admission_ops import get_round_doc
        from doc_preview import preview_payload

        meta = get_round_doc(conn, doc_id)
    if not meta:
        return json_error("Không tìm thấy tài liệu", 404)
    fp = meta.get("file_path")
    if not fp or not Path(fp).is_file():
        return json_error("Chưa có file đính kèm.", 404)
    payload = preview_payload(fp, meta.get("original_name") or meta.get("title") or "document")
    payload["material_title"] = meta.get("title") or payload.get("title")
    payload["round_id"] = meta.get("round_id")
    payload["doc_id"] = doc_id
    payload["can_download"] = caps["download"]
    return jsonify(payload)


@app.route("/ops/applications/<int:app_id>/docs", methods=["GET", "POST"])
def ops_application_docs(app_id):
    if request.method == "GET":
        with get_db() as conn:
            actor, caps = _app_doc_actor_caps(conn, app_id)
            if not actor["ok"]:
                return json_error(actor["error"] or "Unauthorized", 401)
            if not caps["view"]:
                return json_error("Bạn không có quyền xem tài liệu hồ sơ thí sinh.", 403)
            from admission_ops import (
                app_doc_type_catalog,
                get_application_brief,
                list_application_docs,
            )

            brief = get_application_brief(conn, app_id)
            if not brief:
                return json_error("Không tìm thấy hồ sơ thí sinh.", 404)
            rows = list_application_docs(conn, app_id)
            for r in rows:
                r.pop("file_path", None)
                r["can_download"] = caps["download"]
                r["can_manage"] = caps["manage"]
            return jsonify(
                {
                    "application": brief,
                    "items": rows,
                    "types": app_doc_type_catalog(),
                    "can_manage": caps["manage"],
                    "can_download": caps["download"],
                }
            )
    with get_db() as conn:
        actor, caps = _app_doc_actor_caps(conn, app_id)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not caps["manage"]:
            return json_error("Bạn không có quyền upload tài liệu hồ sơ thí sinh.", 403)
        from admission_ops import add_application_doc, save_application_doc_file

        f = request.files.get("file")
        if not f or not f.filename:
            return json_error("Cần chọn file PDF (hoặc ảnh cho chứng chỉ / bằng).", 400)
        doc_type = (request.form.get("doc_type") or "").strip()
        title = (request.form.get("title") or "").strip()
        notes = (request.form.get("notes") or "").strip()
        path = None
        try:
            original, stored, path, mime, size = save_application_doc_file(f, doc_type)
            row = add_application_doc(
                conn,
                application_id=app_id,
                doc_type=doc_type,
                title=title,
                original_filename=original,
                stored_name=stored,
                file_path=path,
                mime=mime,
                size_bytes=size,
                notes=notes,
                uploaded_by=f"user:{actor.get('user_id')}",
            )
        except ValueError as e:
            if path:
                Path(path).unlink(missing_ok=True)
            return json_error(str(e), 400)
        row.pop("file_path", None)
        row["can_download"] = True
        row["can_manage"] = True
    return jsonify(row), 201


@app.route("/ops/application-docs/<int:doc_id>", methods=["DELETE"])
def ops_application_doc_delete(doc_id):
    with get_db() as conn:
        from admission_ops import delete_application_doc, get_application_doc

        meta = get_application_doc(conn, doc_id)
        if not meta:
            return json_error("Không tìm thấy tài liệu", 404)
        actor, caps = _app_doc_actor_caps(conn, meta.get("application_id"))
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if not caps["manage"]:
            return json_error("Bạn không có quyền xóa tài liệu hồ sơ thí sinh.", 403)
        ok = delete_application_doc(conn, doc_id)
        if not ok:
            return json_error("Không tìm thấy tài liệu", 404)
        return jsonify({"ok": True})


@app.route("/ops/application-docs/<int:doc_id>/file", methods=["GET"])
def ops_application_doc_file(doc_id):
    inline = (request.args.get("inline") or "") in ("1", "true", "yes")
    with get_db() as conn:
        from admission_ops import get_application_doc

        meta = get_application_doc(conn, doc_id)
        if not meta:
            return json_error("Không tìm thấy tài liệu", 404)
        actor, caps = _app_doc_actor_caps(conn, meta.get("application_id"))
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        if inline:
            if not caps["view"]:
                return json_error("Bạn không có quyền xem tài liệu này.", 403)
        elif not caps["download"]:
            return json_error("Bạn không có quyền tải xuống tài liệu này.", 403)
    fp = meta.get("file_path")
    if not fp or not Path(fp).is_file():
        return json_error("Chưa có file đính kèm.", 404)
    download_name = meta.get("original_name") or "document.bin"
    mime = meta.get("mime") or "application/octet-stream"
    ext = Path(download_name).suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    if ext in mime_map:
        mime = mime_map[ext]
    return send_file(
        fp,
        as_attachment=not inline,
        download_name=download_name,
        mimetype=mime,
    )


@app.route("/ops/official/convert-bulk", methods=["POST"])
def ops_official_convert_bulk():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        denied = _deny_unless(conn, "classes.manage")
        if denied:
            return denied
        from ops_crud import convert_all_official

        try:
            result = convert_all_official(conn, scopes)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/classes", methods=["POST"])
def ops_classes_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        denied = _deny_unless(conn, "classes.manage")
        if denied:
            return denied
        from ops_crud import create_class_group
        try:
            row = create_class_group(conn, data)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/classes/<int:class_id>/enroll-official", methods=["POST"])
def ops_class_enroll_official(class_id):
    """Enroll Officially Enrolled applicants into an existing class."""
    with get_db() as conn:
        denied = _deny_unless(conn, "classes.manage")
        if denied:
            return denied
        from ops_crud import enroll_official_into_class

        try:
            result = enroll_official_into_class(conn, class_id)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/classes/<int:class_id>/students", methods=["GET"])
def ops_class_students(class_id):
    with get_db() as conn:
        from ops_crud import list_class_students
        try:
            return jsonify(list_class_students(conn, class_id))
        except ValueError as e:
            return json_error(str(e), 404)


@app.route("/ops/faculty", methods=["POST"])
def ops_faculty_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from ops_crud import create_faculty
        try:
            return jsonify(create_faculty(conn, data)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/faculty/<int:faculty_id>", methods=["PATCH"])
def ops_faculty_patch(faculty_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from ops_crud import update_faculty
        try:
            return jsonify(update_faculty(conn, faculty_id, data))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/alumni", methods=["POST"])
def ops_alumni_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from ops_crud import create_alumni
        try:
            return jsonify(create_alumni(conn, data)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/alumni-events", methods=["POST"])
def ops_alumni_events_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from ops_crud import create_alumni_event
        try:
            return jsonify(create_alumni_event(conn, data)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/study-groups", methods=["GET", "POST"])
def ops_study_groups():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        from ops_crud import create_study_group, list_study_groups, seed_extra_ops
        seed_extra_ops(conn)
        if request.method == "GET":
            return jsonify(list_study_groups(conn, scopes))
        try:
            return jsonify(create_study_group(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/exams-schedule", methods=["GET", "POST"])
def ops_exams_schedule_api():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        from ops_crud import create_exam, list_exams, seed_extra_ops
        seed_extra_ops(conn)
        if request.method == "GET":
            return jsonify(list_exams(conn, scopes))
        try:
            return jsonify(create_exam(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/evaluations", methods=["GET", "POST"])
def ops_evaluations_api():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        from ops_crud import create_evaluation, list_evaluations, seed_extra_ops
        seed_extra_ops(conn)
        if request.method == "GET":
            return jsonify(list_evaluations(conn, scopes))
        try:
            return jsonify(create_evaluation(conn, request.get_json(silent=True) or {})), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/actions/notify-results", methods=["POST"])
def ops_notify_results():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "admissions.results"):
            return json_error(deny_write_message("admissions.results"), 403)
        from ops_crud import notify_passed_applicants
        return jsonify(notify_passed_applicants(conn, scopes))


@app.route("/ops/actions/notify-missing-docs", methods=["POST"])
def ops_notify_missing_docs():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "admissions.results"):
            return json_error(deny_write_message("admissions.results"), 403)
        from ops_crud import notify_missing_docs
        return jsonify(notify_missing_docs(conn, scopes))


@app.route("/ops/actions/send-timeline", methods=["POST"])
def ops_send_timeline():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not (
            can_write_perm(actor, "admissions.applications")
            or can_write_perm(actor, "admissions.crm_source")
        ):
            return json_error(deny_write_message("admissions.applications"), 403)
        from quality_ops import send_timeline_emails

        return jsonify(send_timeline_emails(conn, scopes))


@app.route("/ops/actions/issue-checklists", methods=["POST"])
def ops_issue_checklists():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "admissions.applications"):
            return json_error(deny_write_message("admissions.applications"), 403)
        from quality_ops import issue_checklists

        return jsonify(issue_checklists(conn, scopes))


@app.route("/ops/actions/notify-exam-schedule", methods=["POST"])
def ops_notify_exam_schedule():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not (
            can_write_perm(actor, "admissions.written_exams")
            or can_write_perm(actor, "admissions.applications")
        ):
            return json_error(deny_write_message("admissions.written_exams"), 403)
        from quality_ops import notify_exam_schedule

        return jsonify(notify_exam_schedule(conn, scopes))


@app.route("/ops/actions/notify-interview-invites", methods=["POST"])
def ops_notify_interview_invites():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not (
            can_write_perm(actor, "admissions.interviews")
            or can_write_perm(actor, "admissions.applications")
        ):
            return json_error(deny_write_message("admissions.interviews"), 403)
        from quality_ops import notify_interview_invites

        return jsonify(notify_interview_invites(conn, scopes))


@app.route("/ops/actions/notify-admission-pack", methods=["POST"])
def ops_notify_admission_pack():
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "admissions.results"):
            return json_error(deny_write_message("admissions.results"), 403)
        from quality_ops import notify_admission_pack

        return jsonify(notify_admission_pack(conn, scopes))


@app.route("/ops/export/<entity>", methods=["GET"])
def ops_export_entity(entity):
    scopes = _parse_scopes_from_request()
    from flask import Response
    from ops_crud import export_rows_csv, list_study_groups, list_exams, list_evaluations, seed_extra_ops

    with get_db() as conn:
        seed_extra_ops(conn)
        cur = conn.cursor()
        rows = []
        fields = None
        if entity == "official":
            from coord_ops import list_applications_enriched
            rows = list_applications_enriched(conn, scopes, status="official")
            fields = [
                "cfvg_app_no", "full_name", "program_code", "email", "campus",
                "english_cert", "degree_verified", "english_verified", "neu_packet_ready",
                "final_result", "status", "notes",
            ]
        elif entity == "thanh-tra":
            from coord_ops import list_applications_enriched
            rows = list_applications_enriched(conn, scopes)
            rows = [
                r for r in rows
                if str(r.get("inspect_thanh_tra") or "").lower() in ("1", "yes", "true")
                or str(r.get("neu_packet_ready") or "").lower() in ("yes", "1", "ready")
                or (r.get("status") or "") in ("passed", "paid", "official")
            ]
            fields = [
                "cfvg_app_no", "full_name", "program_code", "gender", "dob", "email", "phone",
                "university", "degree_major", "degree_grade", "english_cert",
                "degree_file", "english_file", "degree_verified", "english_verified",
                "inspect_thanh_tra", "neu_packet_ready", "campus", "status",
            ]
        elif entity == "htqt":
            from coord_ops import list_applications_enriched
            rows = [
                r for r in list_applications_enriched(conn, scopes)
                if (r.get("status") or "") in ("passed", "paid", "official")
            ]
            fields = [
                "cfvg_app_no", "full_name", "program_code", "gender", "dob", "email", "phone",
                "university", "degree_major", "degree_grade", "english_cert",
                "degree_file", "english_file", "other_file", "doc_count",
                "board_decision", "final_result", "neu_packet_ready", "campus", "status",
            ]
        elif entity == "khao-thi":
            # Xuất danh sách trúng tuyển chính thức gửi phòng Khảo thí / TT Pháp chế NEU
            from coord_ops import list_applications_enriched
            rows = list_applications_enriched(conn, scopes, status="official")
            fields = [
                "cfvg_app_no", "full_name", "program_code", "gender", "dob", "email", "phone",
                "university", "degree_major", "degree_grade", "english_cert",
                "degree_verified", "english_verified", "neu_packet_ready", "campus", "status",
            ]
        elif entity == "applications":
            from coord_ops import list_applications_enriched
            rows = list_applications_enriched(conn, scopes)
            fields = [
                "intake_session", "student_code_mba", "cfvg_app_no", "full_name", "gender", "dob",
                "program_code", "campus", "email", "phone",
                "university", "degree_major", "eco_background", "master_level",
                "bachelor_start_year", "bachelor_grad_year", "study_duration", "credit_hours",
                "degree_grade", "other_achievements", "company", "job_title",
                "experience_years", "management_years", "english_cert", "english_note",
                "naric_status", "naric_note", "exam_eligible_flag",
                "avg_score", "interview_score", "interview_jury1", "interview_jury2",
                "interview_jury3", "written_score", "written_gk", "written_mle",
                "english_file", "degree_file", "other_file", "doc_count",
                "confirmation_status", "board_decision",
                "lead_source", "checklist_status", "degree_verified", "english_verified",
                "status", "final_result", "transferred_at", "transferred_by",
            ]
        elif entity == "students":
            from mba_ops import list_students_lifecycle
            rows = list_students_lifecycle(conn, scopes)
            fields = [
                "student_code", "full_name", "intake_session", "program_code", "class_name",
                "gender", "dob", "place_of_birth", "email", "phone", "company", "job_title",
                "management_years", "lifecycle_status", "scholarship_type",
                "partner_enrollment", "exchange_flag", "reserve_note",
            ]
        elif entity == "coord-handoff":
            # DS đã phê duyệt TS — gửi Điều phối tổ chức thi/PV
            from coord_ops import list_applications_enriched
            rows = [
                r for r in list_applications_enriched(conn, scopes)
                if r.get("status") in (
                    "approved_ts", "interview", "passed", "failed", "paid", "official"
                )
            ]
            fields = [
                "cfvg_app_no", "full_name", "program_code", "dob", "degree_major", "degree_grade",
                "campus", "email", "phone",
                "english_cert", "checklist_status", "degree_verified", "english_verified",
                "status", "transferred_at", "transferred_by",
            ]
        elif entity == "alumni":
            from ops_data import _scopes_sql
            frag, params = _scopes_sql(scopes, "program_code")
            raw = cur.execute(
                f"SELECT full_name, program_code, cohort, class_name, email, phone, company "
                f"FROM alumni_members WHERE {frag} ORDER BY full_name",
                params,
            ).fetchall()
            fields = ["full_name", "program_code", "cohort", "class_name", "email", "phone", "company"]
            rows = [dict(zip(fields, r)) for r in raw]
        elif entity == "attendance":
            from ops_data import _scopes_sql
            frag, params = _scopes_sql(scopes, "cg.program_code")
            raw = cur.execute(
                "SELECT cg.name, c.code, a.session_no, a.session_label, a.session_date, "
                "a.present_count, a.absent_count "
                "FROM attendance_sessions a "
                "JOIN teaching_assignments ta ON ta.id = a.assignment_id "
                "JOIN class_groups cg ON cg.id = ta.class_id "
                "JOIN courses c ON c.id = ta.course_id "
                f"WHERE {frag} ORDER BY a.session_date",
                params,
            ).fetchall()
            fields = ["class_name", "course_code", "session_no", "session_label", "session_date", "present", "absent"]
            rows = [
                {
                    "class_name": r[0], "course_code": r[1], "session_no": r[2],
                    "session_label": r[3], "session_date": r[4], "present": r[5], "absent": r[6],
                }
                for r in raw
            ]
        elif entity == "assignments":
            raw = cur.execute(
                "SELECT course_code, student_name, title, score, submitted_at, status "
                "FROM assignment_submissions ORDER BY id DESC"
            ).fetchall()
            fields = ["course_code", "student_name", "title", "score", "submitted_at", "status"]
            rows = [dict(zip(fields, r)) for r in raw]
        elif entity == "groups":
            rows = list_study_groups(conn, scopes)
            fields = ["name", "class_name", "program_code", "member_names", "status"]
        elif entity == "exams":
            rows = list_exams(conn, scopes)
            fields = ["title", "class_name", "program_code", "exam_date", "exam_type", "room", "status"]
        elif entity == "evaluations":
            rows = list_evaluations(conn, scopes)
            fields = [
                "title", "name", "program_code", "response_pct", "status",
                "ready_mgmt", "ready_faculty", "report_status",
            ]
        elif entity == "written-exam":
            from mba_ops import list_written_exam_roster

            rows = list_written_exam_roster(conn, scopes)
            fields = [
                "written_exam_no", "full_name", "program_code", "email", "phone",
                "written_score", "written_exam_date", "status", "cfvg_app_no", "round_code",
            ]
        elif entity == "exam-eligibility":
            from mba_ops import attendance_eligibility, list_students_lifecycle

            rows = attendance_eligibility(conn, scopes, max_absent_pct=30.0)
            if not rows:
                rows = []
                for st in list_students_lifecycle(conn, scopes):
                    rows.append(
                        {
                            "full_name": st.get("full_name"),
                            "email": st.get("email"),
                            "class_name": st.get("class_name"),
                            "program_code": st.get("program_code"),
                            "course_code": "",
                            "course_name": "",
                            "sessions_marked": 0,
                            "absent_count": 0,
                            "absent_pct": 0,
                            "exam_eligible": True,
                            "max_absent_pct": 30.0,
                            "student_code": st.get("student_code"),
                        }
                    )
            fields = [
                "full_name", "email", "class_name", "program_code", "course_code",
                "course_name", "sessions_marked", "absent_count", "absent_pct",
                "exam_eligible", "max_absent_pct",
            ]
        elif entity == "attendance-matrix":
            from mba_ops import attendance_matrix_rows

            class_id = request.args.get("class_id", type=int)
            rows = attendance_matrix_rows(conn, scopes, class_id=class_id)
            fields = [
                "student_code", "full_name", "gender", "dob", "place_of_birth",
                "email", "phone", "company", "job_title", "class_name", "program_code",
                "course_code", "course_name", "session_date", "check_in", "check_out",
                "day_total",
            ]
        elif entity == "grade-synthesis":
            from mba_ops import grade_synthesis_rows

            class_id = request.args.get("class_id", type=int)
            rows = grade_synthesis_rows(conn, scopes, class_id=class_id)
            fields = sorted({k for r in rows for k in r.keys()}) if rows else [
                "class_name", "program_code", "student_code", "full_name", "total"
            ]
        elif entity == "fees":
            from ops_data import _scopes_sql

            frag, params = _scopes_sql(scopes, "a.program_code")
            raw = cur.execute(
                "SELECT a.cfvg_app_no, a.full_name, a.program_code, a.email, "
                "ef.amount, ef.status, ef.paid_at, ef.proof_note, a.status AS app_status "
                "FROM enrollment_fees ef JOIN applications a ON a.id = ef.application_id "
                f"WHERE {frag} ORDER BY ef.id DESC",
                params,
            ).fetchall()
            rows = [
                {
                    "cfvg_app_no": r[0], "full_name": r[1], "program_code": r[2], "email": r[3],
                    "amount": r[4], "fee_status": r[5], "paid_at": r[6], "proof_note": r[7],
                    "app_status": r[8],
                }
                for r in raw
            ]
            fields = [
                "cfvg_app_no", "full_name", "program_code", "email",
                "amount", "fee_status", "paid_at", "proof_note", "app_status",
            ]
        elif entity == "thesis":
            from coord_ops import list_thesis_records

            rows = list_thesis_records(conn, scopes)
            fields = [
                "full_name", "program_code", "cp_number", "title", "tutor",
                "status", "total_grade", "defense_date", "defense_time", "room", "class_name",
            ]
        elif entity == "student-timeline":
            from e2e_pipeline import student_timeline_rows

            actor = _resolve_ops_actor(conn)
            uid = actor.get("user_id") if actor.get("ok") else None
            # Staff may pass application email or student login
            email = (request.args.get("email") or "").strip()
            user_id = request.args.get("user_id", type=int) or uid
            rows = student_timeline_rows(conn, user_id=user_id, email=email)
            fields = [
                "stage_no", "code", "title", "status", "detail",
                "full_name", "program_code", "student_code", "print_entity",
            ]
        elif entity == "interview-slot":
            from ops_data import _scopes_sql

            frag, params = _scopes_sql(scopes, "s.program_code")
            raw = cur.execute(
                "SELECT a.cfvg_app_no, a.full_name, a.program_code, s.title, s.room, "
                "sl.scheduled_at, sl.result, sl.score_conclusion, sl.notes "
                "FROM interview_slots sl "
                "JOIN interview_sessions s ON s.id = sl.session_id "
                "JOIN applications a ON a.id = sl.application_id "
                f"WHERE {frag} ORDER BY sl.scheduled_at",
                params,
            ).fetchall()
            rows = [
                {
                    "cfvg_app_no": r[0], "full_name": r[1], "program_code": r[2],
                    "title": r[3], "room": r[4], "scheduled_at": r[5],
                    "result": r[6], "score_conclusion": r[7], "notes": r[8],
                }
                for r in raw
            ]
            fields = [
                "cfvg_app_no", "full_name", "program_code", "title", "room",
                "scheduled_at", "result", "score_conclusion", "notes",
            ]
        elif entity == "event-registrants":
            from marcom_ops import export_event_registrants, seed_marcom_draft_data

            seed_marcom_draft_data(conn)
            event_id = request.args.get("event_id", type=int)
            rows = export_event_registrants(conn, event_id=event_id)
            fields = [
                "event_title", "event_type", "event_date", "location", "program_codes",
                "event_status", "full_name", "email", "phone", "company", "occupation",
                "program_interest", "interest_level", "attendance_status",
                "followup_status", "contact_note", "notes", "lead_id", "updated_at",
            ]
        elif entity == "event-followup":
            from marcom_ops import export_event_followup, seed_marcom_draft_data

            seed_marcom_draft_data(conn)
            event_id = request.args.get("event_id", type=int)
            rows = export_event_followup(conn, event_id=event_id)
            fields = [
                "event_title", "event_date", "full_name", "email", "phone", "company",
                "program_interest", "interest_level", "attendance_status",
                "followup_status", "contact_note", "updated_at",
            ]
        elif entity in ("crm-source", "crm-activities", "crm-reminders", "crm-report"):
            from crm_ops import export_crm_rows, ensure_crm_tables

            ensure_crm_tables(cur)
            kind_map = {
                "crm-source": "source",
                "crm-activities": "activities",
                "crm-reminders": "reminders",
                "crm-report": "report",
            }
            rows, fields = export_crm_rows(conn, kind=kind_map[entity])
        else:
            return json_error("Unknown export", 404)
        fmt = (request.args.get("format") or "xlsx").strip().lower()
        safe_name = re.sub(r"[^\w\-]+", "_", entity)[:80] or "export"
        if fmt == "csv":
            csv_text = export_rows_csv(rows, fields)
            return Response(
                "\ufeff" + csv_text,
                mimetype="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": f"attachment; filename={safe_name}.csv"
                },
            )
        from ops_crud import export_rows_xlsx

        xlsx_bytes = export_rows_xlsx(rows, fields, sheet_name=entity[:31])
        return Response(
            xlsx_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={safe_name}.xlsx"
            },
        )


@app.route("/ops/export-table", methods=["POST"])
def ops_export_table():
    """Build .xlsx from arbitrary table payload (current list / client-side exports)."""
    from flask import Response

    data = request.get_json(silent=True) or {}
    headers = data.get("headers") or data.get("fields") or []
    keys = data.get("keys") or headers
    raw_rows = data.get("rows") or []
    if not isinstance(headers, list) or not headers:
        return json_error("Cần headers", 400)
    if not isinstance(keys, list) or len(keys) != len(headers):
        keys = list(headers)
    filename = re.sub(
        r"[^\w\-]+", "_", str(data.get("filename") or "danh_sach")
    )[:80] or "danh_sach"
    sheet = str(data.get("sheet") or "Data")[:31]
    mapped = []
    for r in raw_rows:
        if not isinstance(r, dict):
            continue
        mapped.append({headers[i]: r.get(keys[i], "") for i in range(len(headers))})
    from ops_crud import export_rows_xlsx

    xlsx_bytes = export_rows_xlsx(mapped, list(headers), sheet_name=sheet)
    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}.xlsx"
        },
    )


@app.route("/ops/asst/<entity>", methods=["POST"])
def ops_asst_create(entity):
    data = dict(request.get_json(silent=True) or {})
    table_map = {
        "tasks": ("asst_tasks", ["title"], "asst.exec_tasks"),
        "calendar": ("asst_calendar", ["title"], "asst.calendar"),
        "intl-faculty": ("asst_intl_faculty", ["full_name"], "asst.intl_faculty"),
        "intl-students": ("asst_intl_students", ["full_name", "cccd"], "asst.intl_students"),
        "director-fr": ("asst_director_fr", ["full_name"], "asst.director_fr"),
        "documents": ("asst_documents", ["subject"], "asst.documents"),
        "procurement": ("asst_procurement", ["item_name"], "asst.procurement"),
        "payments": ("asst_payments", ["beneficiary"], "asst.payments"),
        "weekly-reports": ("asst_weekly_reports", ["week_label"], "asst.weekly_report"),
        "leave": ("asst_leave", ["employee_name"], "asst.leave"),
    }
    if entity not in table_map:
        return json_error("Unknown asst entity", 404)
    table, required, perm = table_map[entity]
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, perm):
            return json_error(deny_write_message(perm), 403)
        if entity == "documents" and not data.get("subject"):
            data["subject"] = data.get("title") or data.get("doc_no") or "Công văn"
        if entity == "procurement" and not data.get("item_name"):
            data["item_name"] = data.get("title") or "Đề xuất"
        for key in required:
            if not data.get(key):
                return json_error(f"Thiếu trường {key}", 400)
        from ops_crud import asst_insert, seed_extra_ops

        seed_extra_ops(conn)
        try:
            row = asst_insert(conn, table, data, required)
        except Exception as e:
            return json_error(str(e), 400)
        if entity == "calendar":
            from asst_ops import calendar_conflict_titles

            row["conflicts"] = calendar_conflict_titles(conn, row)
    return jsonify(row), 201


@app.route("/ops/asst/<entity>/<int:row_id>", methods=["PATCH", "DELETE"])
def ops_asst_row(entity, row_id):
    table_map = {
        "tasks": ("asst_tasks", "asst.exec_tasks"),
        "calendar": ("asst_calendar", "asst.calendar"),
        "intl-faculty": ("asst_intl_faculty", "asst.intl_faculty"),
        "intl-students": ("asst_intl_students", "asst.intl_students"),
        "director-fr": ("asst_director_fr", "asst.director_fr"),
        "documents": ("asst_documents", "asst.documents"),
        "procurement": ("asst_procurement", "asst.procurement"),
        "payments": ("asst_payments", "asst.payments"),
        "weekly-reports": ("asst_weekly_reports", "asst.weekly_report"),
        "leave": ("asst_leave", "asst.leave"),
    }
    spec = table_map.get(entity)
    if not spec:
        return json_error("Unknown asst entity", 404)
    table, perm = spec
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, perm):
            return json_error(deny_write_message(perm), 403)
        if request.method == "PATCH":
            from ops_crud import generic_row_update

            try:
                return jsonify(generic_row_update(conn, table, row_id, request.get_json(silent=True) or {}))
            except ValueError as e:
                return json_error(str(e), 400)
        from ops_crud import delete_ops_row

        try:
            ok = delete_ops_row(conn, table, row_id)
        except ValueError as e:
            return json_error(str(e), 400)
    if not ok:
        return json_error("Not found", 404)
    return jsonify({"ok": True})


@app.route("/ops/rows/<table>/<int:row_id>", methods=["PATCH", "DELETE"])
def ops_generic_row(table, row_id):
    """Patch or delete a row from allowlisted ops tables."""
    alias = {
        "faculty": "faculty",
        "alumni": "alumni_members",
        "alumni-events": "alumni_events",
        "study-groups": "study_groups",
        "exams": "exam_schedules",
        "evaluations": "course_evaluations",
        "classes": "class_groups",
        "rounds": "admission_rounds",
        "applications": "applications",
        "teaching-assignments": "teaching_assignments",
        "teaching-schedule": "teaching_schedule",
        "attendance-sessions": "attendance_sessions",
        "program-versions": "program_versions",
        "courses": "courses",
        "interviews": "interview_sessions",
        "thesis-records": "thesis_records",
        "marcom-campaigns": "marcom_campaigns",
        "marcom-assets": "marcom_assets",
        "marcom-leads": "marcom_leads",
        "marcom-events": "marcom_events",
        "crm-source": "crm_source_profiles",
        "crm-activities": "crm_activities",
        "crm-reminders": "crm_reminders",
        "candidate-pre-enroll": "candidate-pre-enroll",
        "candidate-enrolled": "candidate-enrolled",
        "admission-doc-types": "admission_doc_types",
        "elearn-lectures": "class_lessons",
        "elearn-objectives": "elearn_objectives",
        "elearn-recs": "elearn_objective_recs",
        "elearn-plans": "elearn_study_plans",
        "elearn-agenda": "elearn_agenda",
        "elearn-sittings": "elearn_exam_sittings",
        "elearn-meetings": "elearn_return_meetings",
    }
    real = alias.get(table, table)
    if request.method == "PATCH":
        with get_db() as conn:
            actor = _resolve_ops_actor(conn)
            if not actor["ok"]:
                return json_error(actor["error"] or "Unauthorized", 401)
            if real == "candidate-pre-enroll":
                if not actor["is_admin"] and "admissions.pre_enroll" not in (actor.get("permission_codes") or []):
                    return json_error("Bạn không có quyền admissions.pre_enroll.", 403)
                from admission_ops import update_pre_enroll_file

                try:
                    return jsonify(update_pre_enroll_file(conn, row_id, request.get_json(silent=True) or {}))
                except ValueError as e:
                    return json_error(str(e), 400)
            if real == "candidate-enrolled":
                if not actor["is_admin"] and "admissions.enrolled_files" not in (actor.get("permission_codes") or []):
                    return json_error("Bạn không có quyền admissions.enrolled_files.", 403)
                from admission_ops import update_enrolled_file

                try:
                    return jsonify(update_enrolled_file(conn, row_id, request.get_json(silent=True) or {}))
                except ValueError as e:
                    return json_error(str(e), 400)
            if real == "admission_doc_types":
                codes = set(actor.get("permission_codes") or [])
                if not actor["is_admin"] and "admissions.doc_types" not in codes and "admissions.round_docs" not in codes and "admin.status_catalog" not in codes:
                    return json_error("Bạn không có quyền khai báo loại tài liệu.", 403)
                from admission_ops import update_doc_type

                try:
                    return jsonify(update_doc_type(conn, row_id, request.get_json(silent=True) or {}))
                except ValueError as e:
                    return json_error(str(e), 400)
            from ops_crud import generic_row_update

            try:
                return jsonify(generic_row_update(conn, real, row_id, request.get_json(silent=True) or {}))
            except ValueError as e:
                return json_error(str(e), 400)
    if real in ("candidate-pre-enroll", "candidate-enrolled"):
        return json_error(
            "Không xóa từ bảng liên kết. Dùng hồ sơ thí sinh hoặc danh sách lớp.",
            400,
        )
    return ops_generic_delete_impl(real, row_id)


def ops_generic_delete_impl(real, row_id):
    with get_db() as conn:
        from ops_crud import delete_ops_row

        try:
            ok = delete_ops_row(conn, real, row_id)
        except ValueError as e:
            return json_error(str(e), 400)
    if not ok:
        return json_error("Not found", 404)
    return jsonify({"ok": True})


def apply_qa_rows(kind: str, rows: list) -> list:
    from quality_ops import apply_qa

    return apply_qa(kind, rows, qa=(request.args.get("qa") or ""))


def _asst_list(sql: str, mapper, *, expiry_fields: list[str] | None = None, calendar: bool = False, qa_kind: str | None = None):
    q = (request.args.get("q") or "").strip()
    expiry = (request.args.get("expiry") or "").strip().lower()
    with get_db() as conn:
        cur = conn.cursor()
        try:
            from asst_ops import ensure_asst_tables
            from mba_ops import ensure_mba_tables

            ensure_asst_tables(cur)
            ensure_mba_tables(cur)  # exchange extras on asst_intl_students
            conn.commit()
        except Exception:
            pass
        rows = cur.execute(sql).fetchall()
    items = [mapper(r) for r in rows]
    if calendar:
        from asst_ops import annotate_calendar_conflicts

        annotate_calendar_conflicts(items)
    if expiry in ("soon", "1", "true", "yes") and expiry_fields:
        from asst_ops import is_expiring_soon

        items = [
            it
            for it in items
            if any(is_expiring_soon(str(it.get(f) or "")) for f in expiry_fields)
        ]
    if q:
        ql = q.lower()
        items = [
            it
            for it in items
            if any(ql in str(v).lower() for v in it.values() if v is not None)
        ]
    if qa_kind:
        items = apply_qa_rows(qa_kind, items)
    return jsonify(items)


@app.route("/ops/asst/tasks", methods=["GET"])
def ops_asst_tasks():
    return _asst_list(
        "SELECT t.id, t.title, t.assignee, t.department, t.due_date, t.status, t.notes, "
        "m.title AS meeting_title "
        "FROM asst_tasks t LEFT JOIN asst_meetings m ON m.id = t.meeting_id "
        "ORDER BY t.due_date",
        lambda r: {
            "id": r[0],
            "title": r[1],
            "assignee": r[2],
            "department": r[3],
            "due_date": r[4],
            "status": r[5],
            "notes": r[6],
            "meeting_title": r[7] or "—",
        },
        qa_kind="task",
    )


@app.route("/ops/asst/calendar", methods=["GET"])
def ops_asst_calendar():
    return _asst_list(
        "SELECT id, title, cal_type, starts_at, ends_at, location, owner, status, notes "
        "FROM asst_calendar ORDER BY starts_at",
        lambda r: {
            "id": r[0],
            "title": r[1],
            "cal_type": r[2],
            "starts_at": r[3],
            "ends_at": r[4],
            "location": r[5],
            "owner": r[6],
            "status": r[7],
            "notes": r[8],
        },
        calendar=True,
        qa_kind="calendar",
    )


@app.route("/ops/asst/calendar/notify-changes", methods=["POST"])
def ops_asst_calendar_notify():
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor["ok"]:
            return json_error(actor["error"] or "Unauthorized", 401)
        from ops_policy import can_write_perm, deny_write_message

        if not can_write_perm(actor, "asst.calendar"):
            return json_error(deny_write_message("asst.calendar"), 403)
        from asst_ops import notify_calendar_changes

        data = request.get_json(silent=True) or {}
        return jsonify(
            notify_calendar_changes(
                conn,
                actor=f"user:{actor.get('user_id')}",
                recipient=(data.get("recipient") or "").strip(),
            )
        )


@app.route("/ops/asst/intl-faculty", methods=["GET"])
def ops_asst_intl_faculty():
    return _asst_list(
        "SELECT id, full_name, nationality, organization, passport_no, passport_expiry, "
        "visa_type, visa_status, visa_expiry, arrival_date, arrival_flight, departure_date, "
        "hotel_name, program_code, course_name, status, partner_university, partner_code "
        "FROM asst_intl_faculty ORDER BY arrival_date",
        lambda r: {
            "id": r[0],
            "full_name": r[1],
            "nationality": r[2],
            "organization": r[3],
            "passport_no": r[4],
            "passport_expiry": r[5],
            "visa_type": r[6],
            "visa_status": r[7],
            "visa_expiry": r[8],
            "arrival_date": r[9],
            "arrival_flight": r[10],
            "departure_date": r[11],
            "hotel_name": r[12],
            "program_code": r[13],
            "course_name": r[14],
            "status": r[15],
            "partner_university": r[16] or r[3],
            "partner_code": r[17],
        },
        expiry_fields=["passport_expiry", "visa_expiry"],
    )


@app.route("/ops/asst/intl-students", methods=["GET"])
def ops_asst_intl_students():
    return _asst_list(
        "SELECT id, full_name, nationality, program_code, cohort, student_type, "
        "home_university, visa_status, arrival_date, onboarding_status, email, "
        "direction, semester, exchange_kind, partner_university, "
        "handoff_visa_by, handoff_iae_by, handoff_courses_by, accounting_note, cccd "
        "FROM asst_intl_students ORDER BY arrival_date",
        lambda r: {
            "id": r[0],
            "full_name": r[1],
            "nationality": r[2],
            "program_code": r[3],
            "cohort": r[4],
            "student_type": r[5],
            "home_university": r[6],
            "visa_status": r[7],
            "arrival_date": r[8],
            "onboarding_status": r[9],
            "email": r[10],
            "direction": r[11] or "",
            "semester": r[12] or "",
            "exchange_kind": r[13] or "",
            "partner_university": r[14] or "",
            "handoff_visa_by": r[15] or "",
            "handoff_iae_by": r[16] or "",
            "handoff_courses_by": r[17] or "",
            "accounting_note": r[18] or "",
            "cccd": r[19] if len(r) > 19 else "",
        },
    )


@app.route("/ops/asst/director-fr", methods=["GET"])
def ops_asst_director_fr():
    return _asst_list(
        "SELECT id, full_name, relation, nationality, passport_no, passport_expiry, "
        "visa_info, work_permit, residence_reg, doc_expiry, status "
        "FROM asst_director_fr ORDER BY id",
        lambda r: {
            "id": r[0],
            "full_name": r[1],
            "relation": r[2],
            "nationality": r[3],
            "passport_no": r[4],
            "passport_expiry": r[5],
            "visa_info": r[6],
            "work_permit": r[7],
            "residence_reg": r[8],
            "doc_expiry": r[9],
            "status": r[10],
        },
        expiry_fields=["passport_expiry", "doc_expiry"],
        qa_kind="director_fr",
    )


@app.route("/ops/asst/documents", methods=["GET"])
def ops_asst_documents():
    return _asst_list(
        "SELECT id, doc_direction, doc_no, doc_date, sender_or_receiver, subject, "
        "handler, due_date, status, seal_used "
        "FROM asst_documents ORDER BY id DESC",
        lambda r: {
            "id": r[0],
            "doc_direction": r[1],
            "doc_no": r[2],
            "doc_date": r[3],
            "sender_or_receiver": r[4],
            "subject": r[5],
            "handler": r[6],
            "due_date": r[7],
            "status": r[8],
            "seal_used": "Có" if r[9] else "Không",
        },
        qa_kind="document",
    )


@app.route("/ops/asst/procurement", methods=["GET"])
def ops_asst_procurement():
    return _asst_list(
        "SELECT id, category, item_name, quantity, unit_price, amount, requester, "
        "supplier, request_date, status, invoice_no "
        "FROM asst_procurement ORDER BY id DESC",
        lambda r: {
            "id": r[0],
            "category": r[1],
            "item_name": r[2],
            "quantity": r[3],
            "unit_price": r[4],
            "amount": r[5],
            "requester": r[6],
            "supplier": r[7],
            "request_date": r[8],
            "status": r[9],
            "invoice_no": r[10],
        },
        qa_kind="procurement",
    )


@app.route("/ops/asst/payments", methods=["GET"])
def ops_asst_payments():
    return _asst_list(
        "SELECT id, cost_type, beneficiary, program_code, supplier, amount, "
        "invoice_no, invoice_date, payment_status, payment_date, month_key "
        "FROM asst_payments ORDER BY month_key DESC, id DESC",
        lambda r: {
            "id": r[0],
            "cost_type": r[1],
            "beneficiary": r[2],
            "program_code": r[3],
            "supplier": r[4],
            "amount": r[5],
            "invoice_no": r[6],
            "invoice_date": r[7],
            "payment_status": r[8],
            "payment_date": r[9],
            "month_key": r[10],
        },
        qa_kind="payment",
    )


@app.route("/ops/asst/weekly-reports", methods=["GET"])
def ops_asst_weekly_reports():
    return _asst_list(
        "SELECT id, week_label, week_start, done_summary, ongoing_summary, "
        "next_week_plan, issues, status, sent_at "
        "FROM asst_weekly_reports ORDER BY week_start DESC",
        lambda r: {
            "id": r[0],
            "week_label": r[1],
            "week_start": r[2],
            "done_summary": r[3],
            "ongoing_summary": r[4],
            "next_week_plan": r[5],
            "issues": r[6],
            "status": r[7],
            "sent_at": r[8],
        },
        qa_kind="weekly",
    )


@app.route("/ops/asst/weekly-reports/<int:row_id>/submit", methods=["POST"])
def ops_asst_weekly_submit(row_id):
    with get_db() as conn:
        from datetime import datetime

        from asst_ops import ensure_asst_tables

        cur = conn.cursor()
        ensure_asst_tables(cur)
        row = cur.execute(
            "SELECT id FROM asst_weekly_reports WHERE id=?", (row_id,)
        ).fetchone()
        if not row:
            return json_error("Không tìm thấy báo cáo tuần", 404)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "UPDATE asst_weekly_reports SET status='submitted_bgd', sent_at=? WHERE id=?",
            (now, row_id),
        )
        conn.commit()
        return jsonify({"id": row_id, "status": "submitted_bgd", "sent_at": now})


@app.route("/ops/asst/leave", methods=["GET"])
def ops_asst_leave():
    return _asst_list(
        "SELECT id, employee_name, department, leave_type, start_date, end_date, "
        "days, reason, substitute, status, approver "
        "FROM asst_leave ORDER BY start_date DESC",
        lambda r: {
            "id": r[0],
            "employee_name": r[1],
            "department": r[2],
            "leave_type": r[3],
            "start_date": r[4],
            "end_date": r[5],
            "days": r[6],
            "reason": r[7],
            "substitute": r[8],
            "status": r[9],
            "approver": r[10],
        },
        qa_kind="leave",
    )


@app.route("/ops/asst/leave/<int:leave_id>/status", methods=["POST"])
def ops_asst_leave_status(leave_id):
    data = request.get_json(silent=True) or {}
    status = (data.get("status") or "").strip()
    if status not in ("pending", "approved", "rejected"):
        return json_error("status must be pending|approved|rejected", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE asst_leave SET status = ? WHERE id = ?", (status, leave_id))
        if cur.rowcount == 0:
            return json_error("Leave request not found", 404)
        conn.commit()
    return jsonify({"ok": True, "status": status})


# ---------------------------------------------------------------------------
# Marcom — Marketing / truyền thông / sự kiện (TuanTA)
# ---------------------------------------------------------------------------
_MARCOM_ENTITY = {
    "leads": ("marcom_leads", ["full_name"]),
    "campaigns": ("marcom_campaigns", ["title"]),
    "events": ("marcom_events", ["title"]),
    "assets": ("marcom_assets", ["title"]),
}


def _marcom_list(sql: str, mapper, *, qa_kind: str | None = None):
    q = (request.args.get("q") or "").strip().lower()
    with get_db() as conn:
        cur = conn.cursor()
        from marcom_ops import ensure_marcom_tables

        ensure_marcom_tables(cur)
        rows = cur.execute(sql).fetchall()
    out = [mapper(r) for r in rows]
    if q:
        out = [
            r
            for r in out
            if q in " ".join(str(v or "") for v in r.values()).lower()
        ]
    if qa_kind:
        out = apply_qa_rows(qa_kind, out)
    return jsonify(out)


@app.route("/ops/marcom/leads", methods=["GET"])
def ops_marcom_leads_list():
    q = (request.args.get("q") or "").strip().lower()
    with get_db() as conn:
        from marcom_ops import list_marcom_leads

        out = list_marcom_leads(conn)
    if q:
        out = [r for r in out if q in " ".join(str(v or "") for v in r.values()).lower()]
    return jsonify(apply_qa_rows("lead", out))


@app.route("/ops/marcom/campaigns", methods=["GET"])
def ops_marcom_campaigns_list():
    q = (request.args.get("q") or "").strip().lower()
    with get_db() as conn:
        from marcom_ops import list_marcom_campaigns

        out = list_marcom_campaigns(conn)
    if q:
        out = [r for r in out if q in " ".join(str(v or "") for v in r.values()).lower()]
    return jsonify(apply_qa_rows("campaign", out))


@app.route("/ops/marcom/events", methods=["GET"])
def ops_marcom_events_list():
    q = (request.args.get("q") or "").strip()
    event_type = (request.args.get("event_type") or "").strip()
    with get_db() as conn:
        from marcom_ops import list_marcom_events, seed_marcom_draft_data

        seed_marcom_draft_data(conn)
        return jsonify(apply_qa_rows("event", list_marcom_events(conn, q=q, event_type=event_type)))


@app.route("/ops/marcom/events/<int:event_id>", methods=["GET", "PATCH"])
def ops_marcom_event_detail(event_id):
    with get_db() as conn:
        from marcom_ops import (
            ensure_marcom_tables,
            get_marcom_event,
            list_event_registrants,
            seed_marcom_draft_data,
        )

        seed_marcom_draft_data(conn)
        if request.method == "PATCH":
            data = request.get_json(silent=True) or {}
            allowed = {
                "title", "event_type", "event_date", "location", "program_codes",
                "content", "speakers", "guest_list", "status", "post_event_report",
                "budget", "comms_plan", "co_org_notes", "admission_owner",
                "phase_before_notes", "phase_during_notes", "phase_after_notes",
                "objective", "online_url", "host_unit", "co_units", "campaign_id",
                "supplier_notes", "voucher_note", "acceptance_note",
            }
            fields, params = [], []
            for k, v in data.items():
                if k not in allowed:
                    continue
                fields.append(f"{k} = ?")
                params.append(v)
            if not fields:
                return json_error("No fields", 400)
            cur = conn.cursor()
            ensure_marcom_tables(cur)
            if "status" in data:
                from marcom_ops import guard_event_phase

                try:
                    guard_event_phase(cur, event_id, str(data.get("status") or ""))
                except ValueError as e:
                    return json_error(str(e), 400)
            params.append(event_id)
            cur.execute(
                f"UPDATE marcom_events SET {', '.join(fields)} WHERE id = ?", params
            )
            if cur.rowcount == 0:
                return json_error("Sự kiện không tồn tại", 404)
            conn.commit()
        ev = get_marcom_event(conn, event_id)
        if not ev:
            return json_error("Sự kiện không tồn tại", 404)
        if request.method == "GET":
            ev["registrants"] = list_event_registrants(conn, event_id)
    return jsonify(ev)


@app.route("/ops/marcom/events/<int:event_id>/registrants", methods=["GET", "POST"])
def ops_marcom_event_registrants(event_id):
    with get_db() as conn:
        from marcom_ops import (
            get_marcom_event,
            list_event_registrants,
            seed_marcom_draft_data,
            upsert_event_registrant,
        )

        seed_marcom_draft_data(conn)
        if not get_marcom_event(conn, event_id):
            return json_error("Sự kiện không tồn tại", 404)
        if request.method == "GET":
            q = (request.args.get("q") or "").strip()
            return jsonify(list_event_registrants(conn, event_id, q=q))
        data = request.get_json(silent=True) or {}
        try:
            row = upsert_event_registrant(conn, event_id, data)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route(
    "/ops/marcom/events/<int:event_id>/registrants/<int:reg_id>",
    methods=["PATCH"],
)
def ops_marcom_event_registrant_patch(event_id, reg_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from marcom_ops import upsert_event_registrant

        try:
            row = upsert_event_registrant(
                conn, event_id, data, registrant_id=reg_id
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(row)


@app.route(
    "/ops/marcom/events/registrants/<int:reg_id>/to-lead",
    methods=["POST"],
)
def ops_marcom_registrant_to_lead(reg_id):
    with get_db() as conn:
        from marcom_ops import registrant_to_lead

        try:
            result = registrant_to_lead(conn, reg_id)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route(
    "/ops/marcom/events/registrants/<int:reg_id>/hand-to-ts",
    methods=["POST"],
)
def ops_marcom_registrant_hand_to_ts(reg_id):
    """Event registrant → lead (nếu cần) → tạo hồ sơ TS (Nhận hồ sơ)."""
    data = request.get_json(silent=True) or {}
    round_id = data.get("round_id")
    with get_db() as conn:
        from marcom_ops import registrant_hand_to_ts

        try:
            result = registrant_hand_to_ts(
                conn, reg_id, round_id=int(round_id) if round_id else None
            )
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(result)


@app.route("/ops/marcom/assets", methods=["GET"])
def ops_marcom_assets_list():
    q = (request.args.get("q") or "").strip().lower()
    with get_db() as conn:
        from marcom_ops import list_marcom_assets

        out = list_marcom_assets(conn)
    if q:
        out = [r for r in out if q in " ".join(str(v or "") for v in r.values()).lower()]
    return jsonify(out)


@app.route("/ops/marcom/<entity>", methods=["POST"])
def ops_marcom_create(entity):
    if entity not in _MARCOM_ENTITY:
        return json_error("Unknown marcom entity", 404)
    table, required = _MARCOM_ENTITY[entity]
    data = dict(request.get_json(silent=True) or {})
    for key in required:
        if not data.get(key):
            return json_error(f"Thiếu trường {key}", 400)
    with get_db() as conn:
        if entity == "leads":
            from marcom_ops import intake_interest

            try:
                return jsonify(intake_interest(conn, data)), 201
            except ValueError as e:
                return json_error(str(e), 400)
        if entity == "campaigns":
            data.pop("budget_spent", None)
            data.pop("budget_actual", None)
            if (data.get("status") or "planned") not in ("planned", "budget_submitted"):
                data["status"] = "planned"
        if entity == "events":
            data["budget_status"] = "planned"
            if (data.get("status") or "planned") not in ("planned", "cancelled"):
                data["status"] = "planned"
        if entity == "assets":
            data.pop("budget_actual", None)
            if (data.get("budget_status") or "planned") not in ("planned", "budget_submitted"):
                data["budget_status"] = "planned"
        from ops_crud import asst_insert

        try:
            row = asst_insert(conn, table, data, required)
        except Exception as e:
            return json_error(str(e), 400)
    return jsonify(row), 201


@app.route("/ops/marcom/<entity>/<int:row_id>", methods=["PATCH", "DELETE"])
def ops_marcom_row(entity, row_id):
    if entity not in _MARCOM_ENTITY:
        return json_error("Unknown marcom entity", 404)
    table = _MARCOM_ENTITY[entity][0]
    if request.method == "PATCH":
        payload = dict(request.get_json(silent=True) or {})
        with get_db() as conn:
            from marcom_ops import ensure_marcom_tables, guard_content_status
            from ops_crud import generic_row_update

            cur = conn.cursor()
            ensure_marcom_tables(cur)
            actor = _resolve_ops_actor(conn)
            try:
                if entity == "campaigns":
                    payload.pop("budget_spent", None)
                    payload.pop("budget_actual", None)
                    payload.pop("approved_kt_by", None)
                    payload.pop("approved_bgd_by", None)
                    if payload.get("status"):
                        from marcom_ops import advance_campaign

                        advance_campaign(
                            cur,
                            row_id,
                            str(payload.get("status") or ""),
                            set(actor.get("dept_codes") or []),
                            bool(actor.get("is_admin")),
                        )
                if entity == "events":
                    payload.pop("budget_status", None)
                    payload.pop("approved_kt_by", None)
                    payload.pop("approved_bgd_by", None)
                    if payload.get("status"):
                        from marcom_ops import guard_event_phase

                        guard_event_phase(cur, row_id, str(payload.get("status") or ""))
                if entity == "assets":
                    payload.pop("budget_actual", None)
                    payload.pop("budget_status", None)
                    payload.pop("approved_kt_by", None)
                    payload.pop("approved_bgd_by", None)
                    if payload.get("content_status"):
                        guard_content_status(cur, row_id, str(payload.get("content_status") or ""))
                return jsonify(generic_row_update(conn, table, row_id, payload))
            except ValueError as e:
                return json_error(str(e), 400)
    with get_db() as conn:
        from ops_crud import delete_ops_row

        try:
            ok = delete_ops_row(conn, table, row_id)
        except ValueError as e:
            return json_error(str(e), 400)
    if not ok:
        return json_error("Not found", 404)
    return jsonify({"ok": True})


@app.route("/ops/marcom/leads/<int:lead_id>/hand-to-ts", methods=["POST"])
def ops_marcom_hand_lead(lead_id):
    data = request.get_json(silent=True) or {}
    round_id = data.get("round_id")
    try:
        round_id = int(round_id) if round_id not in (None, "") else None
    except (TypeError, ValueError):
        return json_error("round_id không hợp lệ", 400)
    with get_db() as conn:
        from marcom_ops import hand_lead_to_ts

        try:
            result = hand_lead_to_ts(conn, lead_id, round_id=round_id)
        except ValueError as e:
            return json_error(str(e), 404)
    return jsonify(result)


@app.route("/ops/marcom/leads/<int:lead_id>/accept", methods=["POST"])
def ops_marcom_accept_lead(lead_id):
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor.get("ok"):
            return json_error(actor.get("error") or "Unauthorized", 401)
        depts = set(actor.get("dept_codes") or [])
        if not actor.get("is_admin") and not (depts & {"tuyen_sinh", "marcom_tuyen_sinh"}):
            return json_error("Tuyển sinh xác nhận tiếp nhận.", 403)
        from marcom_ops import accept_lead

        label = ""
        user = conn.cursor().execute(
            "SELECT name FROM user WHERE id = ?", (actor.get("user_id"),)
        ).fetchone()
        if user:
            label = user[0] or ""
        try:
            return jsonify(accept_lead(conn, lead_id, label))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/marcom/<entity>/<int:row_id>/budget-decision", methods=["POST"])
def ops_marcom_budget_decision(entity, row_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor.get("ok"):
            return json_error(actor.get("error") or "Unauthorized", 401)
        from marcom_ops import decide_budget

        try:
            return jsonify(
                decide_budget(
                    conn,
                    entity,
                    row_id,
                    data.get("decision") or "",
                    actor,
                    note=(data.get("note") or "").strip(),
                )
            )
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/marcom/costs", methods=["POST"])
def ops_marcom_propose_cost():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor.get("ok"):
            return json_error(actor.get("error") or "Unauthorized", 401)
        depts = set(actor.get("dept_codes") or [])
        if not actor.get("is_admin") and "marcom" not in depts:
            return json_error("Marcom đề xuất phân bổ chi phí.", 403)
        from marcom_ops import propose_cost

        try:
            return jsonify(propose_cost(conn, data)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/marcom/costs/confirm", methods=["POST"])
def ops_marcom_confirm_cost():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor.get("ok"):
            return json_error(actor.get("error") or "Unauthorized", 401)
        from marcom_ops import confirm_costs

        try:
            return jsonify(confirm_costs(conn, data, actor))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/marcom/campaigns/<int:campaign_id>/activities", methods=["POST"])
def ops_marcom_campaign_activity(campaign_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from marcom_ops import add_campaign_activity

        try:
            return jsonify(add_campaign_activity(conn, campaign_id, data)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/marcom/assets/<int:asset_id>/publications", methods=["POST"])
def ops_marcom_publication(asset_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from marcom_ops import add_publication

        try:
            return jsonify(add_publication(conn, asset_id, data)), 201
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/marcom/events/registrants/<int:reg_id>/check-in", methods=["POST"])
def ops_marcom_check_in(reg_id):
    with get_db() as conn:
        from marcom_ops import check_in_registrant

        try:
            return jsonify(check_in_registrant(conn, reg_id))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/marcom/reports", methods=["GET"])
def ops_marcom_reports():
    period = (request.args.get("period") or "month").strip()
    as_of = (request.args.get("as_of") or "").strip()
    attribution = (request.args.get("attribution") or "first").strip()
    with get_db() as conn:
        actor = _resolve_ops_actor(conn)
        if not actor.get("ok"):
            return json_error(actor.get("error") or "Unauthorized", 401)
        if not actor.get("is_admin") and not _actor_can(
            actor, "marcom.reports", "marcom.campaigns", "reports.dashboard"
        ):
            return json_error("Không có quyền báo cáo Marcom.", 403)
        from marcom_ops import build_marcom_report

        return jsonify(build_marcom_report(conn, period=period, as_of=as_of, attribution=attribution))


@app.route("/ops/marcom/events/<int:event_id>/sync-alumni", methods=["POST"])
def ops_marcom_sync_alumni(event_id):
    with get_db() as conn:
        from marcom_ops import sync_event_to_alumni

        try:
            result = sync_event_to_alumni(conn, event_id)
        except ValueError as e:
            return json_error(str(e), 404)
    return jsonify(result)


@app.route("/ops/marcom/assets/<int:asset_id>/upload", methods=["POST"])
def ops_marcom_asset_upload(asset_id):
    f = request.files.get("file") or request.files.get("asset")
    if not f or not f.filename:
        return json_error("Cần chọn file", 400)
    with get_db() as conn:
        from marcom_ops import ensure_marcom_tables

        cur = conn.cursor()
        ensure_marcom_tables(cur)
        cur.execute("SELECT id, file_path FROM marcom_assets WHERE id = ?", (asset_id,))
        row = cur.fetchone()
        if not row:
            return json_error("Asset not found", 404)
        dest_dir = UPLOADS_DIR / "marcom_assets"
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(f.filename).suffix.lower() or ".bin"
        safe = f"{asset_id}_{uuid.uuid4().hex[:10]}{ext}"
        rel = f"marcom_assets/{safe}"
        f.save(str(dest_dir / safe))
        old = row[1]
        if old:
            try:
                op = UPLOADS_DIR / str(old).replace("\\", "/")
                if op.exists():
                    op.unlink()
            except OSError:
                pass
        cur.execute("UPDATE marcom_assets SET file_path = ? WHERE id = ?", (rel, asset_id))
        conn.commit()
    return jsonify({"ok": True, "file_path": rel, "avatar_url": f"/api/uploads/{rel}"})


# ---------------------------------------------------------------------------
# CRM tuyển sinh — Dữ liệu Nguồn / đợt chăm sóc / nhắc / báo cáo
# ---------------------------------------------------------------------------
_CRM_PERMS = {
    "source": "admissions.crm_source",
    "activities": "admissions.crm_activities",
    "reminders": "admissions.crm_reminders",
    "reports": "admissions.crm_reports",
}


def _crm_actor_ok(conn, *codes: str) -> tuple[dict, str | None]:
    actor = _resolve_ops_actor(conn)
    if not actor.get("ok"):
        return actor, actor.get("error") or "Unauthorized"
    if actor.get("is_admin"):
        return actor, None
    perms = set(actor.get("permission_codes") or [])
    if any(c in perms for c in codes):
        return actor, None
    return actor, "Không có quyền CRM tuyển sinh."


@app.route("/ops/crm/source", methods=["GET", "POST"])
def ops_crm_source():
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_source", "admissions.crm_reports")
        if err:
            return json_error(err, 403)
        from crm_ops import (
            ensure_crm_tables,
            list_source_profiles,
            sync_source_warehouse,
            upsert_source_profile,
        )

        ensure_crm_tables(conn.cursor())
        if request.method == "POST":
            data = dict(request.get_json(silent=True) or {})
            try:
                row = upsert_source_profile(conn, data)
            except ValueError as e:
                return json_error(str(e), 400)
            return jsonify(row), 201
        if (request.args.get("sync") or "") in ("1", "true", "yes"):
            sync_source_warehouse(conn)
        from status_catalog import drop_watch_or_qa_status

        rows = list_source_profiles(
            conn,
            q=(request.args.get("q") or "").strip(),
            care_status=drop_watch_or_qa_status(
                request.args.get("status") or request.args.get("care_status") or ""
            ),
            program_code=(request.args.get("program_code") or "").strip(),
            source=(request.args.get("source") or "").strip(),
            converted=(request.args.get("converted") or "").strip(),
            pic=(request.args.get("pic") or "").strip(),
            intake=(request.args.get("intake") or "").strip(),
            prospect_level=(request.args.get("prospect_level") or request.args.get("level") or "").strip(),
        )
        rows = apply_qa_rows("crm", rows)
    return jsonify(rows)


@app.route("/ops/crm/source/sync", methods=["POST"])
def ops_crm_source_sync():
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_source")
        if err:
            return json_error(err, 403)
        from crm_ops import sync_source_warehouse

        return jsonify(sync_source_warehouse(conn))


@app.route("/ops/crm/source/open-programs", methods=["GET"])
def ops_crm_open_programs():
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_source")
        if err:
            return json_error(err, 403)
        from crm_ops import list_open_program_options

        return jsonify(list_open_program_options(conn))


@app.route("/ops/crm/source/convert", methods=["POST"])
def ops_crm_source_convert():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_source")
        if err:
            return json_error(err, 403)
        from crm_ops import convert_potential_to_applicant

        ids = data.get("profile_ids") or data.get("ids") or []
        if data.get("profile_id") and not ids:
            ids = [data.get("profile_id")]
        try:
            result = convert_potential_to_applicant(
                conn,
                ids,
                round_id=data.get("round_id"),
                program_code=data.get("program_code") or "",
                actor=f"user:{actor.get('user_id')}",
            )
        except ValueError as e:
            return json_error(str(e), 400)
        if result.get("errors") and not result.get("count"):
            return json_error("; ".join(result["errors"]), 400)
        return jsonify(result)


@app.route("/ops/crm/source/<int:profile_id>/inline", methods=["POST", "PATCH"])
def ops_crm_source_inline(profile_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_source")
        if err:
            return json_error(err, 403)
        from crm_ops import patch_source_inline

        try:
            return jsonify(patch_source_inline(
                conn, profile_id, (data.get("field") or "").strip(), data.get("value") or "",
            ))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/crm/source/<int:profile_id>/status", methods=["POST", "PATCH"])
def ops_crm_source_status(profile_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_source")
        if err:
            return json_error(err, 403)
        from crm_ops import set_care_status

        try:
            row = set_care_status(
                conn,
                profile_id,
                (data.get("care_status") or data.get("status") or "").strip(),
                notes=data.get("notes"),
            )
        except ValueError as e:
            return json_error(str(e), 400)
        return jsonify(row)


@app.route("/ops/crm/source/<int:profile_id>/daily", methods=["GET", "POST"])
def ops_crm_source_daily(profile_id):
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_source")
        if err:
            return json_error(err, 403)
        from crm_ops import list_care_log, log_daily_update

        if request.method == "GET":
            return jsonify(list_care_log(conn, profile_id))
        data = dict(request.get_json(silent=True) or {})
        try:
            row = log_daily_update(
                conn, profile_id, data, actor=f"user:{actor.get('user_id')}"
            )
        except ValueError as e:
            return json_error(str(e), 400)
        return jsonify(row), 201


@app.route("/ops/crm/source/<int:profile_id>/consult", methods=["POST"])
def ops_crm_private_consult(profile_id):
    data = dict(request.get_json(silent=True) or {})
    data["profile_id"] = profile_id
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_source", "admissions.crm_activities")
        if err:
            return json_error(err, 403)
        from crm_ops import create_private_consult

        try:
            row = create_private_consult(
                conn, data, created_by=f"user:{actor.get('user_id')}"
            )
        except ValueError as e:
            return json_error(str(e), 400)
        return jsonify(row), 201


@app.route("/ops/crm/source/<int:profile_id>/reminders", methods=["GET"])
def ops_crm_profile_reminders(profile_id):
    with get_db() as conn:
        actor, err = _crm_actor_ok(
            conn, "admissions.crm_source", "admissions.crm_reminders"
        )
        if err:
            return json_error(err, 403)
        from crm_ops import list_reminders

        return jsonify(list_reminders(conn, profile_id=profile_id))


@app.route("/ops/crm/activities", methods=["GET", "POST"])
def ops_crm_activities():
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_activities", "admissions.crm_reports")
        if err:
            return json_error(err, 403)
        from crm_ops import create_activity, ensure_crm_tables, list_activities
        from status_catalog import drop_watch_or_qa_status

        ensure_crm_tables(conn.cursor())
        if request.method == "POST":
            try:
                row = create_activity(
                    conn,
                    request.get_json(silent=True) or {},
                    created_by=f"user:{actor.get('user_id')}",
                )
            except ValueError as e:
                return json_error(str(e), 400)
            return jsonify(row), 201
        return jsonify(
            apply_qa_rows(
                "crm_activity",
                list_activities(
                    conn,
                    q=(request.args.get("q") or "").strip(),
                    activity_type=(request.args.get("activity_type") or request.args.get("event_type") or "").strip(),
                    status=drop_watch_or_qa_status(request.args.get("status") or ""),
                ),
            )
        )


@app.route("/ops/crm/activities/<int:activity_id>", methods=["GET"])
def ops_crm_activity_detail(activity_id):
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_activities", "admissions.crm_reports")
        if err:
            return json_error(err, 403)
        from crm_ops import get_activity

        act = get_activity(conn, activity_id)
        if not act:
            return json_error("Không tìm thấy đợt hoạt động.", 404)
        return jsonify(act)


@app.route("/ops/crm/activities/<int:activity_id>/participants", methods=["GET", "POST"])
def ops_crm_activity_participants(activity_id):
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_activities")
        if err:
            return json_error(err, 403)
        from crm_ops import add_participants, list_participants

        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            ids = data.get("profile_ids") or data.get("ids") or []
            try:
                return jsonify(add_participants(conn, activity_id, ids))
            except ValueError as e:
                return json_error(str(e), 400)
        return jsonify(list_participants(conn, activity_id))


@app.route("/ops/crm/participants/<int:participant_id>", methods=["PATCH"])
def ops_crm_participant_update(participant_id):
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_activities")
        if err:
            return json_error(err, 403)
        from crm_ops import update_participant

        try:
            return jsonify(update_participant(conn, participant_id, request.get_json(silent=True) or {}))
        except ValueError as e:
            return json_error(str(e), 400)


@app.route("/ops/crm/reminders", methods=["GET", "POST"])
def ops_crm_reminders():
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_reminders", "admissions.crm_source")
        if err:
            return json_error(err, 403)
        from crm_ops import add_reminder, ensure_crm_tables, list_reminders
        from status_catalog import drop_watch_or_qa_status

        ensure_crm_tables(conn.cursor())
        if request.method == "POST":
            try:
                return jsonify(add_reminder(conn, request.get_json(silent=True) or {})), 201
            except ValueError as e:
                return json_error(str(e), 400)
        return jsonify(
            list_reminders(
                conn,
                q=(request.args.get("q") or "").strip(),
                status=drop_watch_or_qa_status(request.args.get("status") or ""),
                profile_id=request.args.get("profile_id", type=int),
                upcoming_only=(request.args.get("upcoming") or "") in ("1", "true"),
            )
        )


@app.route("/ops/crm/reminders/dispatch", methods=["POST"])
def ops_crm_reminders_dispatch():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_reminders")
        if err:
            return json_error(err, 403)
        from crm_ops import dispatch_reminders

        ids = data.get("ids") or data.get("reminder_ids") or []
        channel = (data.get("channel") or "print").strip() or "print"
        return jsonify(dispatch_reminders(conn, ids, channel=channel))


@app.route("/ops/crm/reports", methods=["GET"])
def ops_crm_reports():
    with get_db() as conn:
        actor, err = _crm_actor_ok(conn, "admissions.crm_reports", "admissions.crm_source")
        if err:
            return json_error(err, 403)
        from crm_ops import crm_report

        return jsonify(
            crm_report(
                conn,
                level=(request.args.get("level") or "overview").strip() or "overview",
                activity_id=request.args.get("activity_id", type=int),
            )
        )


# ---------------------------------------------------------------------------
# Canvas LMS bridge
# ---------------------------------------------------------------------------
@app.route("/ops/canvas/hub/<audience>", methods=["GET"])
def ops_canvas_hub(audience):
    if audience not in ("coordinator", "faculty", "student", "accounting", "it"):
        return json_error("Invalid audience", 400)
    scopes = _parse_scopes_from_request()
    with get_db() as conn:
        from canvas_bridge import hub_for_audience, seed_canvas_draft_data

        seed_canvas_draft_data(conn)
        conn.commit()
        try:
            data = hub_for_audience(conn, audience, scopes)
        except ValueError as e:
            return json_error(str(e), 400)
        if isinstance(data, dict) and data.get("rows"):
            data = dict(data)
            data["rows"] = apply_qa_rows("canvas", data.get("rows") or [])
    return jsonify(data)


@app.route("/ops/canvas/exports", methods=["GET"])
def ops_canvas_exports():
    with get_db() as conn:
        from canvas_bridge import list_exports

        return jsonify(list_exports(conn))


@app.route("/ops/canvas/exports/<int:export_id>", methods=["GET"])
def ops_canvas_export_detail(export_id):
    with get_db() as conn:
        from canvas_bridge import get_export

        data = get_export(conn, export_id)
    if not data:
        return json_error("Export not found", 404)
    return jsonify(data)


@app.route("/ops/canvas/export/roster", methods=["POST"])
def ops_canvas_export_roster():
    scopes = _parse_scopes_from_request()
    data = request.get_json(silent=True) or {}
    actor = (data.get("actor") or request.headers.get("X-Actor") or "").strip()
    with get_db() as conn:
        from canvas_bridge import build_roster_package

        payload = build_roster_package(conn, scopes, actor=actor)
    return jsonify(payload), 201


@app.route("/ops/canvas/export/class/<int:class_id>", methods=["POST"])
def ops_canvas_export_class(class_id):
    data = request.get_json(silent=True) or {}
    actor = (data.get("actor") or request.headers.get("X-Actor") or "").strip()
    with get_db() as conn:
        from canvas_bridge import build_class_package

        try:
            payload = build_class_package(conn, class_id, actor=actor)
        except ValueError as e:
            return json_error(str(e), 404)
    return jsonify(payload), 201


@app.route("/ops/canvas/exports/<int:export_id>/mark-pushed", methods=["POST"])
def ops_canvas_mark_pushed(export_id):
    data = request.get_json(silent=True) or {}
    actor = (data.get("actor") or request.headers.get("X-Actor") or "").strip()
    with get_db() as conn:
        from canvas_bridge import mark_export_pushed

        try:
            result = mark_export_pushed(conn, export_id, actor=actor)
        except ValueError as e:
            return json_error(str(e), 404)
    return jsonify(result)


@app.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM user WHERE id = ?", (user_id,))
        row = cur.fetchone()
    if not row:
        return json_error("User not found", 404)
    return jsonify(row_to_user(row, include_password=True))


@app.route("/users", methods=["POST"])
def add_user():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not all([name, email, password]):
        return json_error("Name, email, and password are required", 400)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM user WHERE email = ?", (email,))
        if cur.fetchone():
            return json_error("An account with this email already exists", 400)
        cur.execute(
            "INSERT INTO user (name, email, password, is_admin, is_locked) VALUES (?, ?, ?, 0, 0)",
            (name, email, password),
        )
        conn.commit()
        user_id = cur.lastrowid
    return jsonify({"id": user_id}), 201


@app.route("/users/<int:user_id>", methods=["PATCH"])
def patch_user(user_id):
    """Update is_admin and/or is_locked for admin user management."""
    data = request.get_json(silent=True) or {}
    updates = []
    params = []
    if "is_admin" in data:
        updates.append("is_admin = ?")
        params.append(1 if data["is_admin"] else 0)
    if "is_locked" in data:
        updates.append("is_locked = ?")
        params.append(1 if data["is_locked"] else 0)
    if not updates:
        return json_error("No fields to update", 400)
    params.append(user_id)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE user SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        updated = cur.rowcount
    if updated == 0:
        return json_error("User not found", 404)
    return jsonify({"ok": True})


@app.route("/users/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not all([name, email, password]):
        return json_error("Name, email, and password are required", 400)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE user SET name = ?, email = ?, password = ? WHERE id = ?",
            (name, email, password, user_id),
        )
        conn.commit()
        updated = cur.rowcount
    if updated == 0:
        return json_error("User not found", 404)
    return jsonify({"message": "User updated successfully"})


@app.route("/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM user WHERE id = ?", (user_id,))
        conn.commit()
        deleted = cur.rowcount
    if deleted == 0:
        return json_error("User not found", 404)
    return jsonify({"message": "User deleted successfully"})


# ---------------------------------------------------------------------------
# Storages routes
# ---------------------------------------------------------------------------
@app.route("/storages", methods=["GET"])
def get_storages():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, product, brand, rating, model, picture, price, RAM, details "
            "FROM storages"
        )
        rows = cur.fetchall()
    storages = [row_to_storage(r) for r in rows]
    storages = [s for s in storages if not _is_header_row(s)]
    return jsonify(storages)


@app.route("/storages/<int:storage_id>", methods=["GET"])
def get_storage(storage_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM storages WHERE id = ?", (storage_id,))
        row = cur.fetchone()
    if not row:
        return json_error("Storage not found", 404)
    return jsonify(row_to_storage(row))


@app.route("/storages", methods=["POST"])
def add_storage():
    data = request.get_json(silent=True) or {}
    product = data.get("product", "").strip()
    brand = data.get("brand", "").strip()
    rating = data.get("rating", "")
    model = data.get("model", "").strip()
    picture = data.get("picture", "").strip()
    price = data.get("price", "").strip()
    ram = data.get("RAM", "").strip()
    details = data.get("details", "").strip()

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO storages (product, brand, rating, model, picture, price, RAM, details) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (product, brand, rating, model, picture, price, ram, details),
        )
        conn.commit()
        storage_id = cur.lastrowid
    return jsonify({"id": storage_id}), 201


@app.route("/storages/<int:storage_id>", methods=["PUT"])
def update_storage(storage_id):
    data = request.get_json(silent=True) or {}
    product = data.get("product", "").strip()
    brand = data.get("brand", "").strip()
    rating = data.get("rating", "")
    model = data.get("model", "").strip()
    picture = data.get("picture", "").strip()
    price = data.get("price", "").strip()
    ram = data.get("RAM", "").strip()
    details = data.get("details", "").strip()

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE storages SET product=?, brand=?, rating=?, model=?, "
            "picture=?, price=?, RAM=?, details=? WHERE id=?",
            (product, brand, rating, model, picture, price, ram, details, storage_id),
        )
        conn.commit()
        updated = cur.rowcount
    if updated == 0:
        return json_error("Storage not found", 404)
    return jsonify({"message": "Storage updated successfully"})


@app.route("/storages/<int:storage_id>", methods=["DELETE"])
def delete_storage(storage_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM storages WHERE id = ?", (storage_id,))
        conn.commit()
        deleted = cur.rowcount
    if deleted == 0:
        return json_error("Storage not found", 404)
    return jsonify({"message": "Storage deleted successfully"})


# ---------------------------------------------------------------------------
# Articles (admin upload, RAG Q&A)
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {"pdf"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _parse_pagination():
    """Parse page and per_page from request. per_page limited to 12, 14, 48, 100."""
    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or 12
    if per_page not in (12, 14, 48, 100):
        per_page = 12
    return page, per_page


def _fts5_escape(q: str) -> str | None:
    """Escape query for FTS5 MATCH. Returns None if invalid."""
    q = (q or "").strip()
    if not q:
        return None
    # Escape FTS5 special chars: " - ( ) and use phrase for safety
    escaped = q.replace('"', '""').replace("'", "''")
    return f'"{escaped}"'


@app.route("/articles", methods=["GET"])
def get_articles():
    """List all articles with chat count. Optional ?q= search (FTS5). Supports ?page=&per_page= (10,25,100)."""
    q = (request.args.get("q") or "").strip()
    page, per_page = _parse_pagination()
    offset = (page - 1) * per_page
    base_sql = (
        "SELECT a.id, a.title, a.source_url, a.file_path, a.summary, a.created_at, "
        "COALESCE(c.cnt, 0) AS chat_count "
        "FROM articles a "
        "LEFT JOIN (SELECT article_id, COUNT(*) AS cnt FROM chat_history GROUP BY article_id) c "
        "ON a.id = c.article_id "
    )
    fts_term = _fts5_escape(q) if q else None
    use_fts = fts_term is not None
    if use_fts:
        # Use FTS5 for fast full-text search
        where_sql = "WHERE a.id IN (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?) "
        order_limit = "ORDER BY a.created_at DESC LIMIT ? OFFSET ?"
        params = (fts_term, per_page, offset)
        count_params = (fts_term,)
    else:
        where_sql = ""
        order_limit = "ORDER BY a.created_at DESC LIMIT ? OFFSET ?"
        params = (per_page, offset)
        count_params = ()
    with get_db() as conn:
        cur = conn.cursor()
        try:
            if use_fts:
                cur.execute(
                    "SELECT COUNT(*) FROM articles a "
                    "WHERE a.id IN (SELECT rowid FROM articles_fts WHERE articles_fts MATCH ?)",
                    count_params,
                )
            else:
                cur.execute("SELECT COUNT(*) FROM articles a", count_params)
            total = cur.fetchone()[0]
            cur.execute(base_sql + where_sql + order_limit, params)
            rows = cur.fetchall()
        except sqlite3.OperationalError as e:
            if "syntax error" in str(e).lower() and use_fts:
                # Fallback to LIKE if FTS query fails (e.g. malformed input)
                where_sql = "WHERE a.title LIKE ? OR (a.summary IS NOT NULL AND a.summary LIKE ?) "
                order_limit = "ORDER BY a.created_at DESC LIMIT ? OFFSET ?"
                params = (f"%{q}%", f"%{q}%", per_page, offset)
                count_params = (f"%{q}%", f"%{q}%")
                cur.execute("SELECT COUNT(*) FROM articles a " + where_sql, count_params)
                total = cur.fetchone()[0]
                cur.execute(base_sql + where_sql + order_limit, params)
                rows = cur.fetchall()
            else:
                raise
    result = []
    for r in rows:
        d = row_to_article(r)
        d["chat_count"] = r["chat_count"]
        result.append(d)
    return jsonify({"items": result, "total": total, "page": page, "per_page": per_page})


@app.route("/articles/<int:article_id>", methods=["GET"])
def get_article(article_id):
    """Get single article with summary."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, source_url, file_path, summary, analysis, full_text, created_at, summary_feedback FROM articles WHERE id = ?",
            (article_id,),
        )
        row = cur.fetchone()
    if not row:
        return json_error("Article not found", 404)
    d = row_to_article(row)
    d["full_text"] = row["full_text"] or ""
    d["analysis"] = dict(row).get("analysis") or ""
    d["summary_feedback"] = dict(row).get("summary_feedback") or ""
    return jsonify(d)


@app.route("/articles/<int:article_id>/summary/feedback", methods=["POST"])
def set_article_summary_feedback(article_id):
    """Set like/dislike feedback for article summary."""
    data = request.get_json(silent=True) or {}
    feedback_val = (data.get("feedback") or "").strip().lower()
    if feedback_val not in ("like", "dislike"):
        return json_error("feedback must be 'like' or 'dislike'", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE articles SET summary_feedback = ? WHERE id = ?",
            (feedback_val, article_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Article not found", 404)
    return jsonify({"ok": True, "feedback": feedback_val})


@app.route("/articles/<int:article_id>/summary/pptx", methods=["GET"])
def get_article_summary_pptx(article_id):
    """Generate PPTX from article summary."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT title, summary FROM articles WHERE id = ?",
            (article_id,),
        )
        row = cur.fetchone()
    if not row or not (row["summary"] or "").strip():
        return json_error("Article not found or has no summary", 404)
    try:
        from pptx_generator import build_pptx

        pptx_bytes = build_pptx(
            title=row["title"] or "Untitled",
            content=row["summary"] or "",
            source_type="Article Summary",
        )
    except Exception as e:
        return json_error(str(e), 500)
    from io import BytesIO

    safe_title = re.sub(r"[^\w\s-]", "", (row["title"] or "article")[:50])
    filename = f"{safe_title}.pptx"
    return send_file(
        BytesIO(pptx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/articles/<int:article_id>/analysis/pptx", methods=["GET"])
def get_article_analysis_pptx(article_id):
    """Generate PPTX from article analysis (Ratio, Gap, Discussion, Limitation, Future Direction)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT title, analysis FROM articles WHERE id = ?",
            (article_id,),
        )
        row = cur.fetchone()
    if not row or not (row["analysis"] or "").strip():
        return json_error("Article not found or has no analysis", 404)
    try:
        from pptx_generator import build_pptx

        pptx_bytes = build_pptx(
            title=(row["title"] or "Untitled") + " - Analysis",
            content=row["analysis"] or "",
            source_type="Article Analysis",
        )
    except Exception as e:
        return json_error(str(e), 500)
    from io import BytesIO

    safe_title = re.sub(r"[^\w\s-]", "", (row["title"] or "article")[:50])
    filename = f"{safe_title}_analysis.pptx"
    return send_file(
        BytesIO(pptx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/articles/<int:article_id>/chats", methods=["GET"])
def get_article_chats(article_id):
    """Get chat history for an article."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, question, answer, model, created_at, feedback FROM chat_history "
            "WHERE article_id = ? ORDER BY created_at DESC",
            (article_id,),
        )
        rows = cur.fetchall()
    return jsonify([
        {"id": r["id"], "question": r["question"], "answer": r["answer"],
         "model": r["model"] or "", "created_at": r["created_at"], "feedback": dict(r).get("feedback") or ""}
        for r in rows
    ])


@app.route("/articles/<int:article_id>/chats/<int:chat_id>", methods=["DELETE"])
def delete_article_chat(article_id, chat_id):
    """Delete a single chat from article history."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM chat_history WHERE id = ? AND article_id = ?", (chat_id, article_id))
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Chat not found", 404)
    return jsonify({"ok": True})


@app.route("/articles/<int:article_id>/chats/<int:chat_id>/feedback", methods=["POST"])
def set_article_chat_feedback(article_id, chat_id):
    """Set like/dislike feedback for a chat message."""
    data = request.get_json(silent=True) or {}
    feedback = (data.get("feedback") or "").strip().lower()
    if feedback not in ("like", "dislike"):
        return json_error("feedback must be 'like' or 'dislike'", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE chat_history SET feedback = ? WHERE id = ? AND article_id = ?",
            (feedback, chat_id, article_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Chat not found", 404)
    return jsonify({"ok": True, "feedback": feedback})


@app.route("/articles/<int:article_id>/notes", methods=["GET"])
def get_article_notes(article_id):
    """Get notes for an article. Requires user_id query param."""
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return json_error("user_id is required", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, content, created_at, updated_at FROM article_notes "
            "WHERE article_id = ? AND user_id = ? ORDER BY updated_at DESC",
            (article_id, user_id),
        )
        rows = cur.fetchall()
    return jsonify([
        {"id": r["id"], "content": r["content"], "created_at": r["created_at"], "updated_at": r["updated_at"]}
        for r in rows
    ])


@app.route("/articles/<int:article_id>/notes", methods=["POST"])
def create_article_note(article_id):
    """Create or update a note. Requires user_id in body."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if user_id is None:
        return json_error("user_id is required", 400)
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return json_error("user_id must be an integer", 400)
    content = (data.get("content") or "").strip()
    if not content:
        return json_error("content is required", 400)
    note_id = data.get("id")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM articles WHERE id = ?", (article_id,))
        if not cur.fetchone():
            return json_error("Article not found", 404)
        if note_id:
            cur.execute(
                "UPDATE article_notes SET content = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND article_id = ? AND user_id = ?",
                (content, note_id, article_id, user_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return json_error("Note not found", 404)
            return jsonify({"ok": True, "id": note_id, "updated": True})
        cur.execute(
            "INSERT INTO article_notes (article_id, user_id, content) VALUES (?, ?, ?)",
            (article_id, user_id, content),
        )
        conn.commit()
        return jsonify({"ok": True, "id": cur.lastrowid}), 201


@app.route("/articles/<int:article_id>/notes/<int:note_id>", methods=["DELETE"])
def delete_article_note(article_id, note_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or request.args.get("user_id", type=int)
    if not user_id:
        return json_error("user_id is required", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM article_notes WHERE id = ? AND article_id = ? AND user_id = ?",
            (note_id, article_id, int(user_id)),
        )
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Note not found", 404)
    return jsonify({"ok": True})


@app.route("/articles/<int:article_id>/notes/export", methods=["GET"])
def export_article_notes(article_id):
    """Export notes to Excel or Word. Format: excel|word. Requires user_id."""
    fmt = request.args.get("format", "excel").lower()
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return json_error("user_id is required", 400)
    if fmt not in ("excel", "word"):
        return json_error("format must be excel or word", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT title FROM articles WHERE id = ?", (article_id,))
        row = cur.fetchone()
        if not row:
            return json_error("Article not found", 404)
        article_title = row["title"] or "Article"
        cur.execute(
            "SELECT id, content, created_at, updated_at FROM article_notes "
            "WHERE article_id = ? AND user_id = ? ORDER BY updated_at DESC",
            (article_id, user_id),
        )
        notes = cur.fetchall()
    safe_title = re.sub(r"[^\w\s-]", "", article_title[:40])
    if fmt == "excel":
        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = "Notes"
        ws.append(["#", "Note", "Created", "Updated"])
        for c in ws[1]:
            c.font = Font(bold=True)
        for i, n in enumerate(notes, 1):
            ws.append([i, n["content"] or "", n["created_at"] or "", n["updated_at"] or ""])
        ws.column_dimensions["B"].width = 60
        buf = __import__("io").BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"{safe_title}_notes.xlsx",
        )
    from docx import Document

    doc = Document()
    doc.add_heading(f"Notes: {article_title}", 0)
    for i, n in enumerate(notes, 1):
        p = doc.add_paragraph()
        p.add_run(f"Note {i}").bold = True
        p.add_run(f" ({n['created_at'] or ''})")
        doc.add_paragraph(n["content"] or "")
    buf = __import__("io").BytesIO()
    doc.save(buf)
    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"{safe_title}_notes.docx",
    )


def _parse_search_pagination():
    """Parse page and per_page for search. per_page in (10, 25, 50)."""
    page = max(1, request.args.get("page", type=int) or 1)
    per_page = request.args.get("per_page", type=int) or 10
    if per_page not in (10, 25, 50):
        per_page = 10
    return page, per_page


@app.route("/admin/search", methods=["GET"])
def admin_search():
    """Search across all articles using RAG. Supports ?page=&per_page= (10,25,50)."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"results": [], "items": [], "total": 0, "page": 1, "per_page": 10, "query": ""})
    try:
        from rag_service import query_articles, is_llm_configured

        if not is_llm_configured():
            return jsonify({"results": [], "error": "LLM not configured for embeddings"})
        page, per_page = _parse_search_pagination()
        # Fetch enough for pagination (up to 100 results)
        all_chunks = query_articles(q, article_ids=None, top_k=100, for_search=True)
        total = len(all_chunks)
        offset = (page - 1) * per_page
        chunks = all_chunks[offset : offset + per_page]
        return jsonify({
            "results": chunks,
            "items": chunks,
            "total": total,
            "page": page,
            "per_page": per_page,
            "query": q,
        })
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"results": [], "error": str(e)}), 500


@app.route("/admin/settings", methods=["GET", "PUT"])
def admin_settings():
    """System settings: deployment_mode (development|production)."""
    from app_settings import (
        get_all_settings,
        get_deployment_mode,
        is_production,
        set_deployment_mode,
    )

    if request.method == "GET":
        with get_db() as conn:
            settings = get_all_settings(conn)
            mode = get_deployment_mode(conn)
            show_hints = not is_production(conn)
        return jsonify(
            {
                "settings": settings,
                "deployment_mode": mode,
                "show_workflow_hints": show_hints,
            }
        )

    data = request.get_json(silent=True) or {}
    mode = (data.get("deployment_mode") or "").strip().lower()
    if not mode:
        return json_error("deployment_mode required", 400)
    with get_db() as conn:
        try:
            saved = set_deployment_mode(conn, mode)
        except ValueError as e:
            return json_error(str(e), 400)
    return jsonify(
        {
            "ok": True,
            "deployment_mode": saved,
            "show_workflow_hints": saved != "production",
        }
    )


@app.route("/admin/stats", methods=["GET"])
def admin_stats():
    """Return dashboard stats: counts of articles, projects, theses, chats, likes, dislikes."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM articles")
        articles_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM projects")
        projects_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM theses")
        theses_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM books")
        books_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM chat_history")
        article_chats_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM thesis_chat_history")
        thesis_chats_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM project_chat_history")
        project_chats_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM book_chat_history")
        book_chats_count = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM chat_history WHERE feedback = ?", ("like",)
        )
        article_likes = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM chat_history WHERE feedback = ?", ("dislike",)
        )
        article_dislikes = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM thesis_chat_history WHERE feedback = ?", ("like",)
        )
        thesis_likes = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM thesis_chat_history WHERE feedback = ?", ("dislike",)
        )
        thesis_dislikes = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM project_chat_history WHERE feedback = ?", ("like",)
        )
        project_likes = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM project_chat_history WHERE feedback = ?", ("dislike",)
        )
        project_dislikes = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM book_chat_history WHERE feedback = ?", ("like",)
        )
        book_likes = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM book_chat_history WHERE feedback = ?", ("dislike",)
        )
        book_dislikes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM user")
        users_count = cur.fetchone()[0]
        try:
            cur.execute("SELECT COUNT(*) FROM applications")
            applications_count = cur.fetchone()[0]
        except sqlite3.OperationalError:
            applications_count = 0
    from quality_ops import attach

    payload = {
        "articles_count": articles_count,
        "projects_count": projects_count,
        "theses_count": theses_count,
        "books_count": books_count,
        "article_chats_count": article_chats_count,
        "thesis_chats_count": thesis_chats_count,
        "project_chats_count": project_chats_count,
        "book_chats_count": book_chats_count,
        "article_likes": article_likes,
        "article_dislikes": article_dislikes,
        "thesis_likes": thesis_likes,
        "thesis_dislikes": thesis_dislikes,
        "project_likes": project_likes,
        "project_dislikes": project_dislikes,
        "book_likes": book_likes,
        "book_dislikes": book_dislikes,
        "likes_total": article_likes + thesis_likes + project_likes + book_likes,
        "dislikes_total": article_dislikes + thesis_dislikes + project_dislikes + book_dislikes,
        "users_count": users_count,
        "applications_count": applications_count,
    }
    qa = attach(
        "admin_stat",
        {"users_count": users_count, "applications_count": applications_count},
    )
    payload["qa_status"] = qa.get("qa_status")
    payload["qa_label"] = qa.get("qa_label")
    payload["qa_flags"] = qa.get("qa_flags")
    payload["qa_suggestions"] = qa.get("qa_suggestions")
    return jsonify(payload)


# ---------------------------------------------------------------------------
# Bulk Import (Add Multiple Articles from Data Folder)
# ---------------------------------------------------------------------------
def _get_bulk_folder_path(folder_name: str) -> Path | None:
    """Resolve folder path. Accepts:
    - Relative path: resolved under DATA_DIR (default behavior).
    - Absolute path: used as-is for mounted folders (e.g. /mnt/network/papers or D:\\mounted).
    Returns None if invalid."""
    raw = (folder_name or "").strip()
    if not raw:
        return None
    path_obj = Path(raw)
    if path_obj.is_absolute():
        path = path_obj.resolve()
        if not path.exists() or not path.is_dir():
            return None
        return path
    folder_name = raw.replace("\\", "/").strip("/")
    if not folder_name or ".." in folder_name:
        return None
    data_dir = DATA_DIR.resolve()
    path = (DATA_DIR / folder_name).resolve()
    if not path.exists() or not path.is_dir():
        return None
    base_str = os.path.normpath(str(data_dir))
    path_str = os.path.normpath(str(path))
    if not (path_str == base_str or path_str.startswith(base_str + os.sep)):
        return None
    return path


@app.route("/admin/bulk-import/scan", methods=["GET"])
def admin_bulk_import_scan():
    """Scan a folder for PDFs. Accepts relative path (under DATA_DIR) or absolute path (mounted)."""
    raw = (request.args.get("folder") or "").strip()
    folder_name = raw if Path(raw).is_absolute() else raw.replace("\\", "/").strip("/")
    if not folder_name:
        return jsonify({"error": "folder is required", "files": [], "counts": {}})
    path = _get_bulk_folder_path(folder_name)
    if not path:
        data_hint = os.path.normpath(str(DATA_DIR.resolve()))
        return json_error(
            f"Folder not found or not accessible. For relative paths, ensure it exists under: {data_hint}. "
            f"For absolute paths (mounted folders), ensure the path exists.",
            400,
        )

    pdfs = sorted(
        f.name for f in path.iterdir()
        if f.is_file() and f.suffix.lower() == ".pdf"
    )
    if not pdfs:
        return jsonify({
            "folder": folder_name,
            "base_path": str(path),
            "files": [],
            "counts": {"new": 0, "done": 0, "error": 0},
        })

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT filename, status, article_id, error_message FROM bulk_import_log WHERE folder = ?",
            (folder_name,),
        )
        log = {r["filename"]: r for r in cur.fetchall()}

    files = []
    counts = {"new": 0, "done": 0, "error": 0}
    for fn in pdfs:
        row = log.get(fn)
        if not row:
            files.append({"filename": fn, "status": "new", "article_id": None, "error": None})
            counts["new"] += 1
        elif row["status"] == "success":
            files.append({"filename": fn, "status": "done", "article_id": row["article_id"], "error": None})
            counts["done"] += 1
        else:
            files.append({"filename": fn, "status": "error", "article_id": None, "error": row["error_message"] or "Unknown error"})
            counts["error"] += 1

    return jsonify({
        "folder": folder_name,
        "base_path": str(path),
        "files": files,
        "counts": counts,
    })


def _process_single_pdf_to_article(
    pdf_path: Path,
    title: str | None = None,
) -> tuple[int, str]:
    """Process a PDF file into an article. Returns (article_id, title). Raises on error."""
    from rag_service import (
        extract_text_from_pdf,
        add_article_to_rag,
        generate_summary_three_pass,
        generate_article_analysis,
    )
    title = (title or "").strip() or pdf_path.stem
    full_text = extract_text_from_pdf(str(pdf_path))
    if not full_text.strip():
        raise ValueError("Could not extract text from PDF")
    summary_data = generate_summary_three_pass(full_text)
    summary = summary_data.get("full", "")
    analysis = generate_article_analysis(full_text)
    safe_name = f"{uuid.uuid4().hex}_{pdf_path.name}"
    dest_path = UPLOADS_DIR / safe_name
    import shutil
    shutil.copy2(str(pdf_path), str(dest_path))
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO articles (title, source_url, file_path, summary, analysis, full_text) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, "", str(dest_path), summary, analysis, full_text),
        )
        conn.commit()
        article_id = cur.lastrowid
    add_article_to_rag(article_id, title, full_text)
    return article_id, title


@app.route("/admin/bulk-import/process", methods=["POST"])
def admin_bulk_import_process():
    """Process PDFs from a folder. Optionally specify filenames (default: all new)."""
    import time as _time
    data = request.get_json(silent=True) or {}
    raw = (data.get("folder") or "").strip()
    folder_name = raw if Path(raw).is_absolute() else raw.replace("\\", "/").strip("/")
    filenames = data.get("filenames") or []
    retry_errors = data.get("retry_errors", False)

    if not folder_name:
        return json_error("folder is required", 400)
    path = _get_bulk_folder_path(folder_name)
    if not path:
        data_hint = os.path.normpath(str(DATA_DIR.resolve()))
        return json_error(
            f"Folder not found or not accessible. For relative paths, ensure it exists under: {data_hint}. "
            f"For absolute paths (mounted folders), ensure the path exists.",
            400,
        )

    # Determine which files to process
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT filename, status, error_message FROM bulk_import_log WHERE folder = ?",
            (folder_name,),
        )
        log = {r["filename"]: r for r in cur.fetchall()}

    if filenames:
        to_process = [f for f in filenames if (path / f).is_file() and f.lower().endswith(".pdf")]
    elif retry_errors:
        to_process = [r["filename"] for r in log.values() if r["status"] == "error"]
        to_process = [f for f in to_process if (path / f).is_file()]
    else:
        pdfs = [f.name for f in path.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"]
        to_process = [f for f in pdfs if log.get(f, {}).get("status") != "success"]

    if not to_process:
        return jsonify({
            "processed": 0,
            "succeeded": 0,
            "errors": [],
            "message": "No files to process" if not retry_errors else "No error files to retry",
        })

    from rag_service import is_llm_configured
    if not is_llm_configured():
        return json_error("LLM not configured", 503)

    succeeded = []
    errors = []
    t0 = _time.time()

    for fn in to_process:
        fp = path / fn
        if not fp.is_file():
            continue
        try:
            article_id, title = _process_single_pdf_to_article(fp)
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT OR REPLACE INTO bulk_import_log (folder, filename, article_id, status, error_message) VALUES (?, ?, ?, 'success', NULL)",
                    (folder_name, fn, article_id),
                )
                conn.commit()
            succeeded.append({"filename": fn, "article_id": article_id, "title": title})
        except Exception as e:
            err_msg = str(e)
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT OR REPLACE INTO bulk_import_log (folder, filename, article_id, status, error_message) VALUES (?, ?, NULL, 'error', ?)",
                    (folder_name, fn, err_msg),
                )
                conn.commit()
            errors.append({"filename": fn, "error": err_msg})

    print(f"[BACKEND] bulk-import process: {len(succeeded)} ok, {len(errors)} errors (+{_time.time()-t0:.2f}s)")
    return jsonify({
        "processed": len(to_process),
        "succeeded": len(succeeded),
        "errors": errors,
        "succeeded_items": succeeded,
    })


@app.route("/admin/articles/upload", methods=["POST"])
def admin_upload_article():
    """Admin: Upload PDF and ingest into RAG."""
    import time as _time
    t0 = _time.time()

    print(f"\n[BACKEND] ========== UPLOAD START {_time.strftime('%H:%M:%S')} ==========")
    print(f"[BACKEND] request.files: {list(request.files.keys())}")
    print(f"[BACKEND] request.form: {dict(request.form)}")

    if "file" not in request.files:
        return json_error("No file in request", 400)
    file = request.files["file"]
    if not file or file.filename == "":
        return json_error("No file selected", 400)
    if not _allowed_file(file.filename):
        return json_error("Only PDF files are allowed", 400)

    title = (request.form.get("title") or "").strip() or file.filename.rsplit(".", 1)[0]
    source_url = (request.form.get("source_url") or "").strip()
    print(f"[BACKEND] title={title!r} filename={file.filename!r} (+{_time.time()-t0:.2f}s)")

    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = UPLOADS_DIR / safe_name
    file.save(str(file_path))
    print(f"[BACKEND] file saved: {file_path} (+{_time.time()-t0:.2f}s)")

    try:
        print(f"[BACKEND] importing rag_service... (+{_time.time()-t0:.2f}s)")
        from rag_service import (
            extract_text_from_pdf,
            add_article_to_rag,
            generate_summary_three_pass,
            generate_article_analysis,
            is_llm_configured,
        )
        print(f"[BACKEND] rag_service imported OK (+{_time.time()-t0:.2f}s)")

        print(f"[BACKEND] OPENAI_API_KEY: {'set (' + os.environ.get('OPENAI_API_KEY','')[:8] + '...)' if os.environ.get('OPENAI_API_KEY') else '(NOT SET)'}")
        print(f"[BACKEND] OPENAI_BASE_URL: {os.environ.get('OPENAI_BASE_URL', '(NOT SET)')}")
        print(f"[BACKEND] CHAT_MODEL: {os.environ.get('CHAT_MODEL', '(default)')}")
        print(f"[BACKEND] EMBED_MODEL: {os.environ.get('EMBED_MODEL', '(default)')}")
        print(f"[BACKEND] is_llm_configured: {is_llm_configured()}")

        if not is_llm_configured():
            return json_error(
                "LLM not configured. Set OPENAI_API_KEY or OPENAI_BASE_URL.", 503
            )

        print(f"[BACKEND] extracting text from PDF... (+{_time.time()-t0:.2f}s)")
        full_text = extract_text_from_pdf(str(file_path))
        print(f"[BACKEND] text extracted: {len(full_text)} chars (+{_time.time()-t0:.2f}s)")
        if not full_text.strip():
            file_path.unlink(missing_ok=True)
            return json_error("Could not extract text from PDF", 400)

        print(f"[BACKEND] generating three-pass summary... (+{_time.time()-t0:.2f}s)")
        summary_data = generate_summary_three_pass(full_text)
        summary = summary_data.get("full", "")
        print(f"[BACKEND] summary generated: {len(summary)} chars (+{_time.time()-t0:.2f}s)")

        print(f"[BACKEND] generating article analysis... (+{_time.time()-t0:.2f}s)")
        analysis = generate_article_analysis(full_text)
        print(f"[BACKEND] analysis generated: {len(analysis)} chars (+{_time.time()-t0:.2f}s)")

        print(f"[BACKEND] saving to DB... (+{_time.time()-t0:.2f}s)")
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO articles (title, source_url, file_path, summary, analysis, full_text) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (title, source_url, str(file_path), summary, analysis, full_text),
            )
            conn.commit()
            article_id = cur.lastrowid
        print(f"[BACKEND] saved to DB, article_id={article_id} (+{_time.time()-t0:.2f}s)")

        print(f"[BACKEND] adding to RAG index... (+{_time.time()-t0:.2f}s)")
        add_article_to_rag(article_id, title, full_text)
        print(f"[BACKEND] RAG index done (+{_time.time()-t0:.2f}s)")

        print(f"[BACKEND] ========== UPLOAD SUCCESS total={_time.time()-t0:.2f}s ==========\n")
        return jsonify({"id": article_id, "title": title, "summary": summary}), 201

    except Exception as e:
        import traceback
        print(f"[BACKEND] ========== UPLOAD FAILED after {_time.time()-t0:.2f}s ==========")
        traceback.print_exc()
        file_path.unlink(missing_ok=True)
        return json_error(str(e), 500)


@app.route("/articles/<int:article_id>", methods=["DELETE"])
def delete_article(article_id):
    """Admin: Delete article and remove from RAG."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM articles WHERE id = ?", (article_id,))
        row = cur.fetchone()
    if not row:
        return json_error("Article not found", 404)

    file_path = Path(row["file_path"]) if row["file_path"] else None
    if file_path and file_path.exists():
        try:
            file_path.unlink()
        except OSError:
            pass

    try:
        from rag_service import get_chroma_client

        client = get_chroma_client()
        collection = client.get_collection("articles")
        results = collection.get(where={"article_id": article_id}, include=[])
        if results and results["ids"]:
            collection.delete(ids=results["ids"])
    except Exception:
        pass

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM articles WHERE id = ?", (article_id,))
        conn.commit()
    return jsonify({"message": "Article deleted"})


@app.route("/articles/rerun", methods=["POST"])
def rerun_articles():
    """Re-process selected articles: re-extract text, regenerate summary, rebuild RAG index."""
    import time as _time
    t0 = _time.time()
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return json_error("ids is required", 400)

    try:
        from rag_service import (
            extract_text_from_pdf,
            add_article_to_rag,
            generate_summary_three_pass,
            generate_article_analysis,
            is_llm_configured,
        )
        if not is_llm_configured():
            return json_error("LLM not configured.", 503)
    except Exception as e:
        return json_error(str(e), 500)

    results = {"updated": [], "errors": []}
    for aid in ids:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, title, file_path FROM articles WHERE id = ?", (aid,))
                row = cur.fetchone()
            if not row:
                results["errors"].append({"id": aid, "error": "Not found"})
                continue

            fp = row["file_path"]
            if not fp or not Path(fp).exists():
                results["errors"].append({"id": aid, "error": "PDF file missing"})
                continue

            full_text = extract_text_from_pdf(fp)
            if not full_text.strip():
                results["errors"].append({"id": aid, "error": "Could not extract text"})
                continue

            summary_data = generate_summary_three_pass(full_text)
            summary = summary_data.get("full", "")
            analysis = generate_article_analysis(full_text)

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE articles SET summary = ?, analysis = ?, full_text = ? WHERE id = ?",
                    (summary, analysis, full_text, aid),
                )
                conn.commit()

            add_article_to_rag(aid, row["title"], full_text)
            results["updated"].append(aid)
            print(f"[BACKEND] rerun article {aid} OK (+{_time.time()-t0:.2f}s)")

        except Exception as exc:
            results["errors"].append({"id": aid, "error": str(exc)})

    return jsonify(results)


@app.route("/articles/batch-delete", methods=["POST"])
def batch_delete_articles():
    """Delete multiple articles at once."""
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return json_error("ids is required", 400)

    deleted = []
    errors = []
    for aid in ids:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT file_path FROM articles WHERE id = ?", (aid,))
                row = cur.fetchone()
            if not row:
                errors.append({"id": aid, "error": "Not found"})
                continue

            file_path = Path(row["file_path"]) if row["file_path"] else None
            if file_path and file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass

            try:
                from rag_service import get_chroma_client
                client = get_chroma_client()
                collection = client.get_collection("articles")
                results = collection.get(where={"article_id": aid}, include=[])
                if results and results["ids"]:
                    collection.delete(ids=results["ids"])
            except Exception:
                pass

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM articles WHERE id = ?", (aid,))
                conn.commit()
            deleted.append(aid)

        except Exception as exc:
            errors.append({"id": aid, "error": str(exc)})

    return jsonify({"deleted": deleted, "errors": errors})


@app.route("/articles/chat", methods=["POST"])
def chat_with_articles():
    """User: Ask a question about articles (RAG). Supports model selection and compare mode."""
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    article_ids = data.get("article_ids")
    chosen_model = (data.get("model") or "").strip() or None
    compare = data.get("compare", False)

    if not question:
        return json_error("question is required", 400)

    try:
        from rag_service import (
            query_articles,
            generate_chat_answer,
            is_llm_configured,
            store_memory,
            get_available_models,
        )

        if not is_llm_configured():
            return json_error(
                "LLM not configured. Set OPENAI_API_KEY or OPENAI_BASE_URL.", 503
            )

        aid = article_ids[0] if article_ids and len(article_ids) == 1 else None
        context = query_articles(question, article_ids=article_ids, top_k=5)

        if compare:
            models = get_available_models()
            results = {}
            for m in models:
                try:
                    results[m] = generate_chat_answer(
                        question, context, source_type="article", source_id=aid, model=m,
                    )
                except Exception as exc:
                    results[m] = f"[Error from {m}]: {exc}"
                if aid:
                    with get_db() as conn:
                        conn.cursor().execute(
                            "INSERT INTO chat_history (article_id, question, answer, model) VALUES (?, ?, ?, ?)",
                            (aid, question, results[m], m),
                        )
                        conn.commit()
                    try:
                        store_memory(question, results[m], "article", aid)
                    except Exception:
                        pass
            return jsonify({"compare": results, "sources": [c.get("title") for c in context]})

        answer = generate_chat_answer(
            question, context, source_type="article", source_id=aid, model=chosen_model,
        )
        used_model = chosen_model or os.environ.get("CHAT_MODEL", "qwen3:8b")

        chat_id = None
        if aid:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO chat_history (article_id, question, answer, model) VALUES (?, ?, ?, ?)",
                    (aid, question, answer, used_model),
                )
                chat_id = cur.lastrowid
                conn.commit()
            try:
                store_memory(question, answer, "article", aid)
            except Exception:
                pass

        return jsonify({"answer": answer, "model": used_model, "chat_id": chat_id, "sources": [c.get("title") for c in context]})

    except Exception as e:
        return json_error(str(e), 500)


@app.route("/articles/health", methods=["GET"])
def articles_health():
    """Check if RAG/LLM is configured."""
    try:
        from rag_service import is_llm_configured
        ok = is_llm_configured()
        return jsonify({"llm_configured": ok})
    except Exception:
        return jsonify({"llm_configured": False})


# ---------------------------------------------------------------------------
# Theses (mirror of articles with thesis-specific analysis)
# ---------------------------------------------------------------------------
def row_to_thesis(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"] or "",
        "source_url": row["source_url"] or "",
        "file_path": row["file_path"] or "",
        "summary": row["summary"] or "",
        "analysis": row["analysis"] or "",
        "created_at": row["created_at"] or "",
    }


@app.route("/theses", methods=["GET"])
def get_theses():
    """List theses with pagination. Optional ?q= search (title, summary). Supports ?page=&per_page= (10,25,100)."""
    q = (request.args.get("q") or "").strip()
    page, per_page = _parse_pagination()
    offset = (page - 1) * per_page
    if q:
        like_term = f"%{q}%"
        where_sql = "WHERE t.title LIKE ? OR (t.summary IS NOT NULL AND t.summary LIKE ?)"
        count_params = (like_term, like_term)
        list_params = (like_term, like_term, per_page, offset)
    else:
        where_sql = ""
        count_params = ()
        list_params = (per_page, offset)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM theses t " + where_sql,
            count_params,
        )
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT t.id, t.title, t.source_url, t.file_path, t.summary, t.analysis, t.created_at, "
            "COALESCE(c.cnt, 0) AS chat_count "
            "FROM theses t "
            "LEFT JOIN (SELECT thesis_id, COUNT(*) AS cnt FROM thesis_chat_history GROUP BY thesis_id) c "
            "ON t.id = c.thesis_id "
            + where_sql + " ORDER BY t.created_at DESC LIMIT ? OFFSET ?",
            list_params,
        )
        rows = cur.fetchall()
    result = []
    for r in rows:
        d = row_to_thesis(r)
        d["chat_count"] = r["chat_count"]
        result.append(d)
    return jsonify({"items": result, "total": total, "page": page, "per_page": per_page})


@app.route("/theses/<int:thesis_id>", methods=["GET"])
def get_thesis(thesis_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, source_url, file_path, summary, analysis, full_text, created_at "
            "FROM theses WHERE id = ?",
            (thesis_id,),
        )
        row = cur.fetchone()
    if not row:
        return json_error("Thesis not found", 404)
    d = row_to_thesis(row)
    d["full_text"] = row["full_text"] or ""
    return jsonify(d)


@app.route("/theses/<int:thesis_id>/chats", methods=["GET"])
def get_thesis_chats(thesis_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, question, answer, model, created_at, feedback FROM thesis_chat_history "
            "WHERE thesis_id = ? ORDER BY created_at DESC",
            (thesis_id,),
        )
        rows = cur.fetchall()
    return jsonify([
        {"id": r["id"], "question": r["question"], "answer": r["answer"],
         "model": r["model"] or "", "created_at": r["created_at"], "feedback": dict(r).get("feedback") or ""}
        for r in rows
    ])


@app.route("/theses/<int:thesis_id>/chats/<int:chat_id>", methods=["DELETE"])
def delete_thesis_chat(thesis_id, chat_id):
    """Delete a single chat from thesis history."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM thesis_chat_history WHERE id = ? AND thesis_id = ?", (chat_id, thesis_id))
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Chat not found", 404)
    return jsonify({"ok": True})


@app.route("/theses/<int:thesis_id>/chats/<int:chat_id>/feedback", methods=["POST"])
def set_thesis_chat_feedback(thesis_id, chat_id):
    """Set like/dislike feedback for a thesis chat message."""
    data = request.get_json(silent=True) or {}
    feedback = (data.get("feedback") or "").strip().lower()
    if feedback not in ("like", "dislike"):
        return json_error("feedback must be 'like' or 'dislike'", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE thesis_chat_history SET feedback = ? WHERE id = ? AND thesis_id = ?",
            (feedback, chat_id, thesis_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Chat not found", 404)
    return jsonify({"ok": True, "feedback": feedback})


@app.route("/theses/<int:thesis_id>/summary/pptx", methods=["GET"])
def get_thesis_summary_pptx(thesis_id):
    """Generate PPTX from thesis summary (or analysis)."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT title, summary, analysis FROM theses WHERE id = ?",
            (thesis_id,),
        )
        row = cur.fetchone()
    if not row:
        return json_error("Thesis not found", 404)
    content = (row["summary"] or "").strip() or (row["analysis"] or "").strip()
    if not content:
        return json_error("Thesis has no summary or analysis", 404)
    try:
        from pptx_generator import build_pptx

        pptx_bytes = build_pptx(
            title=row["title"] or "Untitled",
            content=content,
            source_type="Thesis Summary",
        )
    except Exception as e:
        return json_error(str(e), 500)
    from io import BytesIO

    safe_title = re.sub(r"[^\w\s-]", "", (row["title"] or "thesis")[:50])
    filename = f"{safe_title}.pptx"
    return send_file(
        BytesIO(pptx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/admin/theses/upload", methods=["POST"])
def admin_upload_thesis():
    """Admin: Upload thesis PDF and run structured analysis."""
    import time as _time
    t0 = _time.time()

    print(f"\n[BACKEND] ========== THESIS UPLOAD START {_time.strftime('%H:%M:%S')} ==========")

    if "file" not in request.files:
        return json_error("No file in request", 400)
    file = request.files["file"]
    if not file or file.filename == "":
        return json_error("No file selected", 400)
    if not _allowed_file(file.filename):
        return json_error("Only PDF files are allowed", 400)

    title = (request.form.get("title") or "").strip() or file.filename.rsplit(".", 1)[0]
    source_url = (request.form.get("source_url") or "").strip()

    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = UPLOADS_DIR / safe_name
    file.save(str(file_path))
    print(f"[BACKEND] thesis saved: {file_path} (+{_time.time()-t0:.2f}s)")

    try:
        from rag_service import (
            extract_text_from_pdf,
            add_thesis_to_rag,
            generate_thesis_analysis,
            generate_summary_three_pass,
            is_llm_configured,
        )

        if not is_llm_configured():
            return json_error("LLM not configured.", 503)

        full_text = extract_text_from_pdf(str(file_path))
        if not full_text.strip():
            file_path.unlink(missing_ok=True)
            return json_error("Could not extract text from PDF", 400)

        print(f"[BACKEND] thesis text: {len(full_text)} chars (+{_time.time()-t0:.2f}s)")

        print(f"[BACKEND] generating three-pass summary... (+{_time.time()-t0:.2f}s)")
        summary_data = generate_summary_three_pass(full_text)
        summary = summary_data.get("full", "")
        print(f"[BACKEND] summary done (+{_time.time()-t0:.2f}s)")

        print(f"[BACKEND] generating thesis analysis... (+{_time.time()-t0:.2f}s)")
        analysis = generate_thesis_analysis(full_text)
        print(f"[BACKEND] analysis done (+{_time.time()-t0:.2f}s)")

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO theses (title, source_url, file_path, summary, analysis, full_text) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (title, source_url, str(file_path), summary, analysis, full_text),
            )
            conn.commit()
            thesis_id = cur.lastrowid

        print(f"[BACKEND] adding to RAG... (+{_time.time()-t0:.2f}s)")
        add_thesis_to_rag(thesis_id, title, full_text)
        print(f"[BACKEND] ========== THESIS UPLOAD SUCCESS total={_time.time()-t0:.2f}s ==========\n")

        return jsonify({"id": thesis_id, "title": title, "summary": summary}), 201

    except Exception as e:
        import traceback
        print(f"[BACKEND] ========== THESIS UPLOAD FAILED after {_time.time()-t0:.2f}s ==========")
        traceback.print_exc()
        file_path.unlink(missing_ok=True)
        return json_error(str(e), 500)


@app.route("/theses/<int:thesis_id>", methods=["DELETE"])
def delete_thesis(thesis_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM theses WHERE id = ?", (thesis_id,))
        row = cur.fetchone()
    if not row:
        return json_error("Thesis not found", 404)

    fp = Path(row["file_path"]) if row["file_path"] else None
    if fp and fp.exists():
        try:
            fp.unlink()
        except OSError:
            pass

    try:
        from rag_service import get_chroma_client
        client = get_chroma_client()
        collection = client.get_collection("theses")
        results = collection.get(where={"thesis_id": thesis_id}, include=[])
        if results and results["ids"]:
            collection.delete(ids=results["ids"])
    except Exception:
        pass

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM theses WHERE id = ?", (thesis_id,))
        conn.commit()
    return jsonify({"message": "Thesis deleted"})


@app.route("/theses/rerun", methods=["POST"])
def rerun_theses():
    """Re-process selected theses: re-extract text, regenerate summary + analysis, rebuild RAG."""
    import time as _time
    t0 = _time.time()
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return json_error("ids is required", 400)

    try:
        from rag_service import (
            extract_text_from_pdf,
            add_thesis_to_rag,
            generate_thesis_analysis,
            generate_summary_three_pass,
            is_llm_configured,
        )
        if not is_llm_configured():
            return json_error("LLM not configured.", 503)
    except Exception as e:
        return json_error(str(e), 500)

    results = {"updated": [], "errors": []}
    for tid in ids:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, title, file_path FROM theses WHERE id = ?", (tid,))
                row = cur.fetchone()
            if not row:
                results["errors"].append({"id": tid, "error": "Not found"})
                continue

            fp = row["file_path"]
            if not fp or not Path(fp).exists():
                results["errors"].append({"id": tid, "error": "PDF file missing"})
                continue

            full_text = extract_text_from_pdf(fp)
            if not full_text.strip():
                results["errors"].append({"id": tid, "error": "Could not extract text"})
                continue

            summary_data = generate_summary_three_pass(full_text)
            summary = summary_data.get("full", "")
            analysis = generate_thesis_analysis(full_text)

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE theses SET summary = ?, analysis = ?, full_text = ? WHERE id = ?",
                    (summary, analysis, full_text, tid),
                )
                conn.commit()

            add_thesis_to_rag(tid, row["title"], full_text)
            results["updated"].append(tid)
            print(f"[BACKEND] rerun thesis {tid} OK (+{_time.time()-t0:.2f}s)")

        except Exception as exc:
            results["errors"].append({"id": tid, "error": str(exc)})

    return jsonify(results)


@app.route("/theses/batch-delete", methods=["POST"])
def batch_delete_theses():
    """Delete multiple theses at once."""
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return json_error("ids is required", 400)

    deleted = []
    errors = []
    for tid in ids:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT file_path FROM theses WHERE id = ?", (tid,))
                row = cur.fetchone()
            if not row:
                errors.append({"id": tid, "error": "Not found"})
                continue

            fp = Path(row["file_path"]) if row["file_path"] else None
            if fp and fp.exists():
                try:
                    fp.unlink()
                except OSError:
                    pass

            try:
                from rag_service import get_chroma_client
                client = get_chroma_client()
                collection = client.get_collection("theses")
                res = collection.get(where={"thesis_id": tid}, include=[])
                if res and res["ids"]:
                    collection.delete(ids=res["ids"])
            except Exception:
                pass

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM theses WHERE id = ?", (tid,))
                conn.commit()
            deleted.append(tid)

        except Exception as exc:
            errors.append({"id": tid, "error": str(exc)})

    return jsonify({"deleted": deleted, "errors": errors})


@app.route("/theses/chat", methods=["POST"])
def chat_with_theses():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    thesis_ids = data.get("thesis_ids")
    chosen_model = (data.get("model") or "").strip() or None
    compare = data.get("compare", False)

    if not question:
        return json_error("question is required", 400)

    try:
        from rag_service import query_theses, generate_chat_answer, is_llm_configured, store_memory, get_available_models

        if not is_llm_configured():
            return json_error("LLM not configured.", 503)

        tid = thesis_ids[0] if thesis_ids and len(thesis_ids) == 1 else None
        context = query_theses(question, thesis_ids=thesis_ids, top_k=5)

        if compare:
            models = get_available_models()
            results = {}
            for m in models:
                try:
                    results[m] = generate_chat_answer(
                        question, context, source_type="thesis", source_id=tid, model=m,
                    )
                except Exception as exc:
                    results[m] = f"[Error from {m}]: {exc}"
                if tid:
                    with get_db() as conn:
                        conn.cursor().execute(
                            "INSERT INTO thesis_chat_history (thesis_id, question, answer, model) VALUES (?, ?, ?, ?)",
                            (tid, question, results[m], m),
                        )
                        conn.commit()
                    try:
                        store_memory(question, results[m], "thesis", tid)
                    except Exception:
                        pass
            return jsonify({"compare": results, "sources": [c.get("title") for c in context]})

        answer = generate_chat_answer(
            question, context, source_type="thesis", source_id=tid, model=chosen_model,
        )
        used_model = chosen_model or os.environ.get("CHAT_MODEL", "qwen3:8b")

        chat_id = None
        if tid:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO thesis_chat_history (thesis_id, question, answer, model) VALUES (?, ?, ?, ?)",
                    (tid, question, answer, used_model),
                )
                chat_id = cur.lastrowid
                conn.commit()
            try:
                store_memory(question, answer, "thesis", tid)
            except Exception:
                pass

        return jsonify({"answer": answer, "model": used_model, "chat_id": chat_id, "sources": [c.get("title") for c in context]})

    except Exception as e:
        return json_error(str(e), 500)


# ---------------------------------------------------------------------------
# Book Categories (Admin managed)
# ---------------------------------------------------------------------------
@app.route("/admin/book-categories", methods=["GET"])
def get_book_categories():
    """List all book categories."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, sort_order, created_at FROM book_categories ORDER BY sort_order ASC, name ASC"
        )
        rows = cur.fetchall()
    return jsonify([
        {"id": r["id"], "name": r["name"], "sort_order": r["sort_order"] or 0, "created_at": r["created_at"] or ""}
        for r in rows
    ])


@app.route("/admin/book-categories", methods=["POST"])
def create_book_category():
    """Create a new book category."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("name is required", 400)
    sort_order = data.get("sort_order", 0)
    try:
        sort_order = int(sort_order)
    except (TypeError, ValueError):
        sort_order = 0
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO book_categories (name, sort_order) VALUES (?, ?)",
                (name, sort_order),
            )
            conn.commit()
            return jsonify({"id": cur.lastrowid, "name": name, "sort_order": sort_order}), 201
        except sqlite3.IntegrityError:
            return json_error("Category name already exists", 400)


@app.route("/admin/book-categories/<int:cat_id>", methods=["PUT"])
def update_book_category(cat_id):
    """Update a book category."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("name is required", 400)
    sort_order = data.get("sort_order")
    with get_db() as conn:
        cur = conn.cursor()
        if sort_order is not None:
            try:
                cur.execute(
                    "UPDATE book_categories SET name = ?, sort_order = ? WHERE id = ?",
                    (name, int(sort_order), cat_id),
                )
            except (TypeError, ValueError):
                cur.execute("UPDATE book_categories SET name = ? WHERE id = ?", (name, cat_id))
        else:
            cur.execute("UPDATE book_categories SET name = ? WHERE id = ?", (name, cat_id))
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Category not found", 404)
    return jsonify({"ok": True, "id": cat_id, "name": name})


@app.route("/admin/book-categories/<int:cat_id>", methods=["DELETE"])
def delete_book_category(cat_id):
    """Delete a book category. Books in this category get category_id set to NULL."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM book_categories WHERE id = ?", (cat_id,))
        if not cur.fetchone():
            return json_error("Category not found", 404)
        cur.execute("UPDATE books SET category_id = NULL WHERE category_id = ?", (cat_id,))
        cur.execute("DELETE FROM book_categories WHERE id = ?", (cat_id,))
        conn.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Status catalog (Admin configurable application / lifecycle / fee statuses)
# ---------------------------------------------------------------------------
@app.route("/ops/status-options", methods=["GET"])
def ops_status_options():
    """Active status options by category (for ops selects)."""
    lang = (request.args.get("lang") or "vi").strip().lower()
    if lang not in ("vi", "en"):
        lang = "vi"
    with get_db() as conn:
        from status_catalog import CATEGORY_LABELS, status_label_map, status_options_map

        options = status_options_map(conn, lang=lang, active_only=True)
        labels = status_label_map(conn, lang=lang)
        categories = [
            {
                "code": code,
                "label": (labels_pair[1] if lang == "en" else labels_pair[0]),
            }
            for code, labels_pair in CATEGORY_LABELS.items()
        ]
    return jsonify({"options": options, "labels": labels, "categories": categories})


@app.route("/admin/status-catalog", methods=["GET"])
def admin_status_catalog_list():
    """List status catalog rows (admin)."""
    category = (request.args.get("category") or "").strip() or None
    lang = (request.args.get("lang") or "vi").strip().lower()
    if lang not in ("vi", "en"):
        lang = "vi"
    active_only = (request.args.get("active_only") or "").strip() in ("1", "true", "True")
    with get_db() as conn:
        from status_catalog import CATEGORY_LABELS, list_status_catalog

        items = list_status_catalog(
            conn, category=category, active_only=active_only, lang=lang
        )
        items = apply_qa_rows("status_item", items)
        categories = [
            {
                "code": code,
                "label_vi": pair[0],
                "label_en": pair[1],
                "label": pair[1] if lang == "en" else pair[0],
            }
            for code, pair in CATEGORY_LABELS.items()
        ]
    return jsonify({"items": items, "categories": categories})


@app.route("/admin/status-catalog", methods=["POST"])
def admin_status_catalog_create():
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from status_catalog import create_status_item

        try:
            item = create_status_item(conn, data)
        except ValueError as e:
            return json_error(str(e), 400)
        except sqlite3.IntegrityError:
            return json_error("Mã trạng thái đã tồn tại trong loại này", 400)
    return jsonify(item), 201


@app.route("/admin/status-catalog/<int:item_id>", methods=["PUT"])
def admin_status_catalog_update(item_id):
    data = request.get_json(silent=True) or {}
    with get_db() as conn:
        from status_catalog import update_status_item

        try:
            item = update_status_item(conn, item_id, data)
        except ValueError as e:
            return json_error(str(e), 400)
        except sqlite3.IntegrityError:
            return json_error("Mã trạng thái đã tồn tại trong loại này", 400)
    if not item:
        return json_error("Not found", 404)
    return jsonify({"ok": True, **item})


@app.route("/admin/status-catalog/<int:item_id>", methods=["DELETE"])
def admin_status_catalog_delete(item_id):
    with get_db() as conn:
        from status_catalog import delete_status_item

        ok, msg = delete_status_item(conn, item_id)
    if not ok:
        code = 404 if msg == "Not found" else 400
        return json_error(msg, code)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Books (long-form reading with RAG, learner notes, export)
# ---------------------------------------------------------------------------
def row_to_book(row: sqlite3.Row) -> dict:
    keys = row.keys() if hasattr(row, "keys") else []
    d = {
        "id": row["id"],
        "title": row["title"] or "",
        "source_url": row["source_url"] or "",
        "file_path": row["file_path"] or "",
        "summary": row["summary"] or "",
        "full_text": row["full_text"] or "",
        "created_at": row["created_at"] or "",
    }
    if "category_id" in keys and row["category_id"] is not None:
        d["category_id"] = row["category_id"]
    if "category_name" in keys and row["category_name"]:
        d["category_name"] = row["category_name"]
    return d


@app.route("/books", methods=["GET"])
def get_books():
    """List books. Optional ?q= search (title, summary). ?category_id= filter. ?page=&per_page= for pagination."""
    category_id = request.args.get("category_id", type=int)
    q = (request.args.get("q") or "").strip()
    page, per_page = _parse_pagination()
    offset = (page - 1) * per_page
    conditions = []
    params = []
    if category_id is not None:
        conditions.append("b.category_id = ?")
        params.append(category_id)
    if q:
        conditions.append("(b.title LIKE ? OR (b.summary IS NOT NULL AND b.summary LIKE ?))")
        params.extend((f"%{q}%", f"%{q}%"))
    where_sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    count_params = tuple(params)
    list_params = tuple(params) + (per_page, offset)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM books b " + where_sql,
            count_params,
        )
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT b.*, bc.name AS category_name, COALESCE(chat_cnt.cnt, 0) AS chat_count "
            "FROM books b "
            "LEFT JOIN book_categories bc ON b.category_id = bc.id "
            "LEFT JOIN (SELECT book_id, COUNT(*) AS cnt FROM book_chat_history GROUP BY book_id) chat_cnt "
            "ON b.id = chat_cnt.book_id "
            + where_sql + " ORDER BY b.created_at DESC LIMIT ? OFFSET ?",
            list_params,
        )
        rows = cur.fetchall()
    result = []
    for r in rows:
        d = row_to_book(r)
        d["chat_count"] = r["chat_count"]
        result.append(d)
    return jsonify({"items": result, "total": total, "page": page, "per_page": per_page})


@app.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT b.*, bc.name AS category_name FROM books b "
            "LEFT JOIN book_categories bc ON b.category_id = bc.id "
            "WHERE b.id = ?",
            (book_id,),
        )
        row = cur.fetchone()
    if not row:
        return json_error("Book not found", 404)
    d = row_to_book(row)
    d["full_text"] = row["full_text"] or ""
    return jsonify(d)


@app.route("/books/<int:book_id>", methods=["PATCH"])
def update_book(book_id):
    """Update book fields (e.g. category_id)."""
    data = request.get_json(silent=True) or {}
    updates = []
    params = []
    if "category_id" in data:
        cat_id = data["category_id"]
        params.append(cat_id if cat_id is not None else None)
        updates.append("category_id = ?")
    if not updates:
        return json_error("No fields to update", 400)
    params.append(book_id)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE books SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Book not found", 404)
    return jsonify({"ok": True})


@app.route("/books/<int:book_id>/chats", methods=["GET"])
def get_book_chats(book_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, question, answer, model, created_at, feedback FROM book_chat_history "
            "WHERE book_id = ? ORDER BY created_at DESC",
            (book_id,),
        )
        rows = cur.fetchall()
    return jsonify([
        {"id": r["id"], "question": r["question"], "answer": r["answer"],
         "model": r["model"] or "", "created_at": r["created_at"], "feedback": dict(r).get("feedback") or ""}
        for r in rows
    ])


@app.route("/books/<int:book_id>/chats/<int:chat_id>", methods=["DELETE"])
def delete_book_chat(book_id, chat_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM book_chat_history WHERE id = ? AND book_id = ?", (chat_id, book_id))
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Chat not found", 404)
    return jsonify({"ok": True})


@app.route("/books/<int:book_id>/chats/<int:chat_id>/feedback", methods=["POST"])
def set_book_chat_feedback(book_id, chat_id):
    data = request.get_json(silent=True) or {}
    feedback = (data.get("feedback") or "").strip().lower()
    if feedback not in ("like", "dislike"):
        return json_error("feedback must be 'like' or 'dislike'", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE book_chat_history SET feedback = ? WHERE id = ? AND book_id = ?",
            (feedback, chat_id, book_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Chat not found", 404)
    return jsonify({"ok": True, "feedback": feedback})


@app.route("/books/<int:book_id>/notes", methods=["GET"])
def get_book_notes(book_id):
    """Get notes for a book. Requires user_id query param (current learner)."""
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return json_error("user_id is required", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, content, created_at, updated_at FROM book_notes "
            "WHERE book_id = ? AND user_id = ? ORDER BY updated_at DESC",
            (book_id, user_id),
        )
        rows = cur.fetchall()
    return jsonify([
        {"id": r["id"], "content": r["content"], "created_at": r["created_at"], "updated_at": r["updated_at"]}
        for r in rows
    ])


@app.route("/books/<int:book_id>/notes", methods=["POST"])
def create_book_note(book_id):
    """Create or update a note. Requires user_id in body."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    if user_id is None:
        return json_error("user_id is required", 400)
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return json_error("user_id must be an integer", 400)
    content = (data.get("content") or "").strip()
    if not content:
        return json_error("content is required", 400)
    note_id = data.get("id")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM books WHERE id = ?", (book_id,))
        if not cur.fetchone():
            return json_error("Book not found", 404)
        if note_id:
            cur.execute(
                "UPDATE book_notes SET content = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND book_id = ? AND user_id = ?",
                (content, note_id, book_id, user_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return json_error("Note not found", 404)
            return jsonify({"ok": True, "id": note_id, "updated": True})
        cur.execute(
            "INSERT INTO book_notes (book_id, user_id, content) VALUES (?, ?, ?)",
            (book_id, user_id, content),
        )
        conn.commit()
        return jsonify({"ok": True, "id": cur.lastrowid}), 201


@app.route("/books/<int:book_id>/notes/<int:note_id>", methods=["DELETE"])
def delete_book_note(book_id, note_id):
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id") or request.args.get("user_id", type=int)
    if not user_id:
        return json_error("user_id is required", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM book_notes WHERE id = ? AND book_id = ? AND user_id = ?",
            (note_id, book_id, int(user_id)),
        )
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Note not found", 404)
    return jsonify({"ok": True})


@app.route("/books/<int:book_id>/notes/export", methods=["GET"])
def export_book_notes(book_id):
    """Export notes to Excel or Word. Format: excel|word. Requires user_id."""
    fmt = request.args.get("format", "excel").lower()
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return json_error("user_id is required", 400)
    if fmt not in ("excel", "word"):
        return json_error("format must be excel or word", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT title FROM books WHERE id = ?", (book_id,))
        row = cur.fetchone()
        if not row:
            return json_error("Book not found", 404)
        book_title = row["title"] or "Book"
        cur.execute(
            "SELECT id, content, created_at, updated_at FROM book_notes "
            "WHERE book_id = ? AND user_id = ? ORDER BY updated_at DESC",
            (book_id, user_id),
        )
        notes = cur.fetchall()
    safe_title = re.sub(r"[^\w\s-]", "", book_title[:40])
    if fmt == "excel":
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment
        wb = Workbook()
        ws = wb.active
        ws.title = "Notes"
        ws.append(["#", "Note", "Created", "Updated"])
        for c in ws[1]:
            c.font = Font(bold=True)
        for i, n in enumerate(notes, 1):
            ws.append([i, n["content"] or "", n["created_at"] or "", n["updated_at"] or ""])
        ws.column_dimensions["B"].width = 60
        buf = __import__("io").BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        as_attachment=True, download_name=f"{safe_title}_notes.xlsx")
    from docx import Document
    from docx.shared import Inches, Pt
    doc = Document()
    doc.add_heading(f"Notes: {book_title}", 0)
    for i, n in enumerate(notes, 1):
        p = doc.add_paragraph()
        p.add_run(f"Note {i}").bold = True
        p.add_run(f" ({n['created_at'] or ''})")
        doc.add_paragraph(n["content"] or "")
    buf = __import__("io").BytesIO()
    doc.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    as_attachment=True, download_name=f"{safe_title}_notes.docx")


@app.route("/books/<int:book_id>/summary/pptx", methods=["GET"])
def get_book_summary_pptx(book_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT title, summary FROM books WHERE id = ?", (book_id,))
        row = cur.fetchone()
    if not row or not (row["summary"] or "").strip():
        return json_error("Book not found or has no summary", 404)
    try:
        from pptx_generator import build_pptx
        pptx_bytes = build_pptx(
            title=row["title"] or "Untitled",
            content=row["summary"] or "",
            source_type="Book Summary",
        )
    except Exception as e:
        return json_error(str(e), 500)
    safe_title = re.sub(r"[^\w\s-]", "", (row["title"] or "book")[:50])
    return send_file(
        __import__("io").BytesIO(pptx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True,
        download_name=f"{safe_title}.pptx",
    )


@app.route("/admin/books/upload", methods=["POST"])
def admin_upload_book():
    """Upload book PDF. Optimized for long books: summary + full RAG indexing."""
    import time as _time
    t0 = _time.time()
    if "file" not in request.files:
        return json_error("No file in request", 400)
    file = request.files["file"]
    if not file or file.filename == "":
        return json_error("No file selected", 400)
    if not _allowed_file(file.filename):
        return json_error("Only PDF files are allowed", 400)
    title = (request.form.get("title") or "").strip() or file.filename.rsplit(".", 1)[0]
    source_url = (request.form.get("source_url") or "").strip()
    category_id = request.form.get("category_id", type=int) or None
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = UPLOADS_DIR / safe_name
    file.save(str(file_path))
    try:
        from rag_service import (
            extract_text_from_pdf,
            add_book_to_rag,
            generate_summary_three_pass,
            is_llm_configured,
        )
        if not is_llm_configured():
            return json_error("LLM not configured.", 503)
        full_text = extract_text_from_pdf(str(file_path))
        if not full_text.strip():
            file_path.unlink(missing_ok=True)
            return json_error("Could not extract text from PDF", 400)
        summary_data = generate_summary_three_pass(full_text)
        summary = summary_data.get("full", "")
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO books (title, source_url, file_path, summary, full_text, category_id) VALUES (?, ?, ?, ?, ?, ?)",
                (title, source_url, str(file_path), summary, full_text, category_id),
            )
            conn.commit()
            book_id = cur.lastrowid
        add_book_to_rag(book_id, title, full_text)
        return jsonify({"id": book_id, "title": title, "summary": summary}), 201
    except Exception as e:
        import traceback
        traceback.print_exc()
        file_path.unlink(missing_ok=True)
        return json_error(str(e), 500)


@app.route("/books/rerun", methods=["POST"])
def rerun_books():
    """Re-process selected books: re-extract text, regenerate summary, rebuild RAG index."""
    import time as _time
    t0 = _time.time()
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return json_error("ids is required", 400)

    try:
        from rag_service import (
            extract_text_from_pdf,
            add_book_to_rag,
            generate_summary_three_pass,
            is_llm_configured,
        )
        if not is_llm_configured():
            return json_error("LLM not configured.", 503)
    except Exception as e:
        return json_error(str(e), 500)

    results = {"updated": [], "errors": []}
    for bid in ids:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, title, file_path FROM books WHERE id = ?", (bid,))
                row = cur.fetchone()
            if not row:
                results["errors"].append({"id": bid, "error": "Not found"})
                continue

            fp = row["file_path"]
            if not fp or not Path(fp).exists():
                results["errors"].append({"id": bid, "error": "PDF file missing"})
                continue

            full_text = extract_text_from_pdf(fp)
            if not full_text.strip():
                results["errors"].append({"id": bid, "error": "Could not extract text"})
                continue

            summary_data = generate_summary_three_pass(full_text)
            summary = summary_data.get("full", "")

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE books SET summary = ?, full_text = ? WHERE id = ?",
                    (summary, full_text, bid),
                )
                conn.commit()

            add_book_to_rag(bid, row["title"], full_text)
            results["updated"].append(bid)
            print(f"[BACKEND] rerun book {bid} OK (+{_time.time()-t0:.2f}s)")

        except Exception as exc:
            results["errors"].append({"id": bid, "error": str(exc)})

    return jsonify(results)


@app.route("/books/batch-delete", methods=["POST"])
def batch_delete_books():
    """Delete multiple books at once."""
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return json_error("ids is required", 400)

    deleted = []
    errors = []
    for bid in ids:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT file_path FROM books WHERE id = ?", (bid,))
                row = cur.fetchone()
            if not row:
                errors.append({"id": bid, "error": "Not found"})
                continue

            file_path = Path(row["file_path"]) if row["file_path"] else None
            if file_path and file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass

            try:
                from rag_service import get_chroma_client
                client = get_chroma_client()
                collection = client.get_collection("books")
                results = collection.get(where={"book_id": bid}, include=[])
                if results and results["ids"]:
                    collection.delete(ids=results["ids"])
            except Exception:
                pass

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM books WHERE id = ?", (bid,))
                conn.commit()
            deleted.append(bid)

        except Exception as exc:
            errors.append({"id": bid, "error": str(exc)})

    return jsonify({"deleted": deleted, "errors": errors})


@app.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM books WHERE id = ?", (book_id,))
        row = cur.fetchone()
    if not row:
        return json_error("Book not found", 404)
    fp = Path(row["file_path"]) if row["file_path"] else None
    if fp and fp.exists():
        try:
            fp.unlink()
        except OSError:
            pass
    try:
        from rag_service import get_chroma_client
        client = get_chroma_client()
        collection = client.get_collection("books")
        results = collection.get(where={"book_id": book_id}, include=[])
        if results and results["ids"]:
            collection.delete(ids=results["ids"])
    except Exception:
        pass
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()
    return jsonify({"message": "Book deleted"})


@app.route("/books/chat", methods=["POST"])
def chat_with_books():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    book_ids = data.get("book_ids")
    chosen_model = (data.get("model") or "").strip() or None
    compare = data.get("compare", False)
    if not question:
        return json_error("question is required", 400)
    try:
        from rag_service import query_books, generate_chat_answer, is_llm_configured, store_memory, get_available_models
        if not is_llm_configured():
            return json_error("LLM not configured.", 503)
        bid = book_ids[0] if book_ids and len(book_ids) == 1 else None
        context = query_books(question, book_ids=book_ids, top_k=8)
        if compare:
            models = get_available_models()
            results = {}
            for m in models:
                try:
                    results[m] = generate_chat_answer(question, context, source_type="book", source_id=bid, model=m)
                except Exception as exc:
                    results[m] = f"[Error from {m}]: {exc}"
                if bid:
                    with get_db() as conn:
                        conn.cursor().execute(
                            "INSERT INTO book_chat_history (book_id, question, answer, model) VALUES (?, ?, ?, ?)",
                            (bid, question, results[m], m),
                        )
                        conn.commit()
            return jsonify({"compare": results, "sources": [c.get("title") for c in context]})
        answer = generate_chat_answer(question, context, source_type="book", source_id=bid, model=chosen_model)
        used_model = chosen_model or os.environ.get("CHAT_MODEL", "qwen3:8b")
        chat_id = None
        if bid:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO book_chat_history (book_id, question, answer, model) VALUES (?, ?, ?, ?)",
                    (bid, question, answer, used_model),
                )
                chat_id = cur.lastrowid
                conn.commit()
            try:
                store_memory(question, answer, "book", bid)
            except Exception:
                pass
        return jsonify({"answer": answer, "model": used_model, "chat_id": chat_id, "sources": [c.get("title") for c in context]})
    except Exception as e:
        return json_error(str(e), 500)


# ---------------------------------------------------------------------------
# Research Projects
# ---------------------------------------------------------------------------
def row_to_project(row: sqlite3.Row) -> dict:
    keys = row.keys() if hasattr(row, "keys") else []
    def _get(k, default=""):
        val = row[k] if k in keys else default
        return val or default
    d = {
        "id": row["id"],
        "title": row["title"] or "",
        "description": row["description"] or "",
        "aims": _get("aims"),
        "instructions": _get("instructions"),
        "combined_summary": row["combined_summary"] or "",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }
    if "user_id" in keys and row["user_id"] is not None:
        d["user_id"] = row["user_id"]
    return d


def row_to_project_file(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "title": row["title"] or "",
        "file_path": row["file_path"] or "",
        "file_hash": row["file_hash"] or "",
        "summary": row["summary"] or "",
        "status": row["status"] or "pending",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


def _projects_base_sql():
    return (
        "SELECT p.id, p.title, p.description, p.combined_summary, p.created_at, p.updated_at, p.user_id, "
        "COALESCE(f.cnt, 0) AS file_count, "
        "COALESCE(pa.cnt, 0) AS article_count, "
        "COALESCE(c.cnt, 0) AS chat_count, "
        "u.name AS owner_name "
        "FROM projects p "
        "LEFT JOIN user u ON p.user_id = u.id "
        "LEFT JOIN (SELECT project_id, COUNT(*) AS cnt FROM project_files GROUP BY project_id) f ON p.id = f.project_id "
        "LEFT JOIN (SELECT project_id, COUNT(*) AS cnt FROM project_articles GROUP BY project_id) pa ON p.id = pa.project_id "
        "LEFT JOIN (SELECT project_id, COUNT(*) AS cnt FROM project_chat_history GROUP BY project_id) c ON p.id = c.project_id "
    )


@app.route("/projects", methods=["GET"])
def get_projects():
    """List projects with pagination. Optional ?user_id=, ?q= search (title, description). Supports ?page=&per_page= (10,25,100).
    When user_id given: returns owned projects + shared-with-me projects. Shared projects include shared_by (owner name)."""
    user_id = request.args.get("user_id", type=int)
    q = (request.args.get("q") or "").strip()
    page, per_page = _parse_pagination()
    offset = (page - 1) * per_page
    conditions = []
    params = []
    if user_id is not None:
        conditions.append("(p.user_id = ? OR p.id IN (SELECT project_id FROM project_shares WHERE user_id = ?))")
        params.extend((user_id, user_id))
    if q:
        conditions.append("(p.title LIKE ? OR (p.description IS NOT NULL AND p.description LIKE ?))")
        params.extend((f"%{q}%", f"%{q}%"))
    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    count_params = tuple(params)
    list_params = tuple(params) + (per_page, offset)
    order_limit = " ORDER BY p.updated_at DESC LIMIT ? OFFSET ?"

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM projects p " + where_clause,
                count_params,
            )
            total = cur.fetchone()[0]
            cur.execute(
                _projects_base_sql() + where_clause + order_limit,
                list_params,
            )
            rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        print(f"[BACKEND] get_projects fallback: {e}")
        # Fallback: if project_shares fails, use owned-only filter so we don't 500
        if user_id is not None:
            simple_conditions = ["p.user_id = ?"]
            simple_params = [user_id]
            if q:
                simple_conditions.append("(p.title LIKE ? OR (p.description IS NOT NULL AND p.description LIKE ?))")
                simple_params.extend((f"%{q}%", f"%{q}%"))
            simple_where = "WHERE " + " AND ".join(simple_conditions)
            simple_count_params = tuple(simple_params)
            simple_list_params = tuple(simple_params) + (per_page, offset)
        else:
            simple_where = where_clause
            simple_count_params = count_params
            simple_list_params = list_params
            if not simple_where:
                simple_where = "WHERE 1=1"
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT COUNT(*) FROM projects p " + simple_where,
                    simple_count_params,
                )
                total = cur.fetchone()[0]
                fallback_sql = (
                    "SELECT p.id, p.title, p.description, p.combined_summary, p.created_at, p.updated_at, p.user_id, "
                    "COALESCE(f.cnt, 0) AS file_count, 0 AS article_count, "
                    "COALESCE(c.cnt, 0) AS chat_count, u.name AS owner_name "
                    "FROM projects p "
                    "LEFT JOIN user u ON p.user_id = u.id "
                    "LEFT JOIN (SELECT project_id, COUNT(*) AS cnt FROM project_files GROUP BY project_id) f ON p.id = f.project_id "
                    "LEFT JOIN (SELECT project_id, COUNT(*) AS cnt FROM project_chat_history GROUP BY project_id) c ON p.id = c.project_id "
                    + simple_where + order_limit
                )
                cur.execute(fallback_sql, simple_list_params)
                rows = cur.fetchall()
        except sqlite3.OperationalError as e2:
            print(f"[BACKEND] get_projects fallback2 failed: {e2}")
            total, rows = 0, []

    result = []
    has_owner_name = bool(rows) and "owner_name" in (rows[0].keys() if hasattr(rows[0], "keys") else [])
    for r in rows:
        d = row_to_project(r)
        rkeys = r.keys() if hasattr(r, "keys") else []
        d["file_count"] = r["file_count"] if "file_count" in rkeys else 0
        d["article_count"] = r["article_count"] if "article_count" in rkeys else 0
        d["chat_count"] = r["chat_count"] if "chat_count" in rkeys else 0
        proj_uid = r["user_id"] if "user_id" in rkeys else None
        if user_id is not None and proj_uid != user_id and has_owner_name and r.get("owner_name"):
            d["shared_by"] = r["owner_name"] or ""
        elif user_id is not None and proj_uid != user_id:
            owner_name = ""
            try:
                with get_db() as conn2:
                    c2 = conn2.cursor()
                    c2.execute("SELECT name FROM user WHERE id = ?", (proj_uid,))
                    ow = c2.fetchone()
                    owner_name = ow["name"] or "" if ow else ""
            except Exception:
                pass
            d["shared_by"] = owner_name
        result.append(d)
    return jsonify({"items": result, "total": total, "page": page, "per_page": per_page})


@app.route("/projects", methods=["POST"])
def create_project():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    aims = (data.get("aims") or "").strip()
    instructions = (data.get("instructions") or "").strip()
    article_ids = data.get("article_ids") or []
    user_id = data.get("user_id")

    if not title:
        return json_error("Title is required", 400)

    with get_db() as conn:
        cur = conn.cursor()
        if user_id is not None:
            cur.execute(
                "INSERT INTO projects (title, description, aims, instructions, user_id) VALUES (?, ?, ?, ?, ?)",
                (title, description, aims, instructions, int(user_id)),
            )
        else:
            cur.execute(
                "INSERT INTO projects (title, description, aims, instructions) VALUES (?, ?, ?, ?)",
                (title, description, aims, instructions),
            )
        conn.commit()
        project_id = cur.lastrowid

        if article_ids:
            for aid in article_ids:
                try:
                    cur.execute(
                        "INSERT INTO project_articles (project_id, article_id) VALUES (?, ?)",
                        (project_id, int(aid)),
                    )
                except (ValueError, sqlite3.IntegrityError):
                    pass
            conn.commit()
            _regenerate_project_summary(project_id)

    return jsonify({"id": project_id, "title": title}), 201


def _request_user_id():
    """Get user_id from request (query param, JSON body, or form)."""
    uid = request.args.get("user_id", type=int)
    if uid is not None:
        return uid
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    if uid is not None:
        return int(uid) if uid else None
    return request.form.get("user_id", type=int)


def _check_project_access(project_id: int, user_id: int | None) -> sqlite3.Row | None:
    """Return project row if exists and user has access (owner or shared). None if not found, 'forbidden' if no access."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cur.fetchone()
    if not row:
        return None
    proj_user_id = row["user_id"] if "user_id" in (row.keys() if hasattr(row, "keys") else []) else None
    if user_id is None:
        return row
    if proj_user_id == user_id:
        return row
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM project_shares WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        )
        if cur.fetchone():
            return row
    return "forbidden"


@app.route("/projects/<int:project_id>", methods=["GET"])
def get_project(project_id):
    user_id = _request_user_id()
    row = _check_project_access(project_id, user_id)
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    d = row_to_project(row)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM project_files WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,),
        )
        files = [row_to_project_file(r) for r in cur.fetchall()]
    d["files"] = files

    # Linked articles (from Articles list)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT a.id, a.title, a.summary, a.source_url, a.created_at FROM articles a "
            "JOIN project_articles pa ON a.id = pa.article_id WHERE pa.project_id = ?",
            (project_id,),
        )
        d["articles"] = [
            {
                "id": r["id"],
                "title": r["title"],
                "summary": r["summary"] or "",
                "summary_short": ((r["summary"] or "")[:200]),
                "source_url": r["source_url"] or "",
                "created_at": r["created_at"] or "",
            }
            for r in cur.fetchall()
        ]

    return jsonify(d)


@app.route("/projects/<int:project_id>/summary/pptx", methods=["GET"])
def get_project_summary_pptx(project_id):
    """Generate PPTX from project combined summary."""
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    content = (row["combined_summary"] or "").strip()
    if not content:
        return json_error("Project has no combined summary yet", 404)
    try:
        from pptx_generator import build_pptx

        pptx_bytes = build_pptx(
            title=row["title"] or "Untitled Project",
            content=content,
            source_type="Project Summary",
        )
    except Exception as e:
        return json_error(str(e), 500)
    from io import BytesIO

    safe_title = re.sub(r"[^\w\s-]", "", (row["title"] or "project")[:50])
    filename = f"{safe_title}.pptx"
    return send_file(
        BytesIO(pptx_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/projects/<int:project_id>/draft/export", methods=["POST"])
def export_project_draft(project_id):
    """Export publication draft to Word. Body: {draft: {...}, outline_items: [...]}."""
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    data = request.get_json(silent=True) or {}
    draft = data.get("draft") or {}
    outline_items = data.get("outline_items") or []
    project_title = row["title"] or "Untitled Project"

    from docx import Document

    doc = Document()
    doc.add_heading(f"Publication Draft: {project_title}", 0)

    for item in outline_items:
        oid = item.get("id") or item.get("label", "")
        label = item.get("label") or oid
        entries = draft.get(oid) or draft.get(label) or []
        if not entries:
            continue
        doc.add_heading(label, level=1)
        for i, ent in enumerate(entries):
            q = (ent.get("question") or "").strip()
            answers = ent.get("answers") or []
            if q:
                p = doc.add_paragraph()
                p.add_run("Q: ").bold = True
                p.add_run(q)
            for j, ans in enumerate(answers):
                if ans and str(ans).strip():
                    p = doc.add_paragraph()
                    run_label = f"A{j + 1}: " if len(answers) > 1 else "A: "
                    p.add_run(run_label).bold = True
                    p.add_run(str(ans).strip())
        doc.add_paragraph()

    buf = __import__("io").BytesIO()
    doc.save(buf)
    buf.seek(0)
    safe_title = re.sub(r"[^\w\s-]", "", project_title[:40])
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"{safe_title}_draft.docx",
    )


@app.route("/projects/<int:project_id>", methods=["PATCH"])
def update_project(project_id):
    """Update project title, description, aims, instructions."""
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    data = request.get_json(silent=True) or {}
    updates = []
    vals = []
    for key in ("title", "description", "aims", "instructions"):
        if key in data:
            updates.append(f"{key} = ?")
            vals.append((data[key] or "").strip())
    if not updates:
        return json_error("No fields to update", 400)
    vals.append(project_id)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
        if not cur.fetchone():
            return json_error("Project not found", 404)
        cur.execute(
            f"UPDATE projects SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            vals,
        )
        conn.commit()
    return jsonify({"message": "Updated"})


@app.route("/projects/<int:project_id>/articles", methods=["POST"])
def add_project_articles(project_id):
    """Link articles to a project. Body: {article_ids: [1, 2, 3]}."""
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    data = request.get_json(silent=True) or {}
    article_ids = data.get("article_ids") or []

    with get_db() as conn:
        cur = conn.cursor()

        added = 0
        for aid in article_ids:
            try:
                cur.execute(
                    "INSERT INTO project_articles (project_id, article_id) VALUES (?, ?)",
                    (project_id, int(aid)),
                )
                added += 1
            except (ValueError, sqlite3.IntegrityError):
                pass
        conn.commit()

    if added:
        import threading
        def _bg_summary():
            try:
                _regenerate_project_summary(project_id)
            except Exception as e:
                print(f"[BACKEND] bg _regenerate_project_summary error: {e}")
        threading.Thread(target=_bg_summary, daemon=True).start()
    return jsonify({"added": added, "article_ids": article_ids}), 201


@app.route("/projects/<int:project_id>/articles/<int:article_id>", methods=["DELETE"])
def remove_project_article(project_id, article_id):
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM project_articles WHERE project_id = ? AND article_id = ?",
            (project_id, article_id),
        )
        conn.commit()
        n = cur.rowcount
    if n == 0:
        return json_error("Article not linked to this project", 404)
    return jsonify({"message": "Article removed"})


def _create_article_from_file(file_storage, title="", source_url="") -> tuple[int | None, str | None]:
    """Process uploaded PDF into an Article. Returns (article_id, error)."""
    if not file_storage or file_storage.filename == "":
        return None, "No file selected"
    if not _allowed_file(file_storage.filename):
        return None, "Only PDF files are allowed"
    title = (title or "").strip() or file_storage.filename.rsplit(".", 1)[0]
    source_url = (source_url or "").strip()
    safe_name = f"{uuid.uuid4().hex}_{file_storage.filename}"
    file_path = UPLOADS_DIR / safe_name
    file_storage.save(str(file_path))
    try:
        from rag_service import (
            extract_text_from_pdf,
            add_article_to_rag,
            generate_summary_three_pass,
            is_llm_configured,
        )
        if not is_llm_configured():
            file_path.unlink(missing_ok=True)
            return None, "LLM not configured"
        full_text = extract_text_from_pdf(str(file_path))
        if not full_text.strip():
            file_path.unlink(missing_ok=True)
            return None, "Could not extract text from PDF"
        summary_data = generate_summary_three_pass(full_text)
        summary = summary_data.get("full", "")
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO articles (title, source_url, file_path, summary, full_text) "
                "VALUES (?, ?, ?, ?, ?)",
                (title, source_url, str(file_path), summary, full_text),
            )
            conn.commit()
            article_id = cur.lastrowid
        add_article_to_rag(article_id, title, full_text)
        return article_id, None
    except Exception as e:
        file_path.unlink(missing_ok=True)
        return None, str(e)


@app.route("/projects/<int:project_id>/articles/upload", methods=["POST"])
def upload_article_to_project(project_id):
    """Upload a PDF, create an Article (stored in Articles), and link it to the project."""
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    if "file" not in request.files:
        return json_error("No file in request", 400)
    file = request.files["file"]

    title = (request.form.get("title") or "").strip()
    source_url = (request.form.get("source_url") or "").strip()
    article_id, err = _create_article_from_file(file, title=title, source_url=source_url)
    if err:
        return json_error(err, 400)

    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO project_articles (project_id, article_id) VALUES (?, ?)",
                (project_id, article_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass

    _regenerate_project_summary(project_id)
    return jsonify({"id": article_id, "project_id": project_id}), 201


@app.route("/projects/<int:project_id>/shares", methods=["GET"])
def get_project_shares(project_id):
    """List users this project is shared with. Owner only."""
    user_id = _request_user_id()
    row = _check_project_access(project_id, user_id)
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    proj_uid = row["user_id"] if "user_id" in (row.keys() if hasattr(row, "keys") else []) else None
    if proj_uid != user_id:
        return json_error("Only the project owner can view shares", 403)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT u.id, u.name, u.email FROM user u "
            "JOIN project_shares ps ON u.id = ps.user_id WHERE ps.project_id = ?",
            (project_id,),
        )
        rows = cur.fetchall()
    return jsonify([{"id": r["id"], "name": r["name"] or "", "email": r["email"] or ""} for r in rows])


@app.route("/projects/<int:project_id>/shares", methods=["POST"])
def add_project_share(project_id):
    """Add a user to project shares by email. Owner only."""
    user_id = _request_user_id()
    row = _check_project_access(project_id, user_id)
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    proj_uid = row["user_id"] if "user_id" in (row.keys() if hasattr(row, "keys") else []) else None
    if proj_uid != user_id:
        return json_error("Only the project owner can add shares", 403)
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return json_error("email is required", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM user WHERE LOWER(email) = ?", (email,))
        target = cur.fetchone()
    if not target:
        return json_error("This email does not exist in the system. The user must sign up first.", 404)
    target_id = int(target["id"])
    if target_id == proj_uid:
        return json_error("Cannot share with yourself", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM project_shares WHERE project_id = ? AND user_id = ?",
            (project_id, target_id),
        )
        if cur.fetchone():
            return json_error("This user is already in the share list.", 400)
        cur.execute(
            "INSERT INTO project_shares (project_id, user_id) VALUES (?, ?)",
            (project_id, target_id),
        )
        conn.commit()
    return jsonify({"ok": True, "user_id": target_id})


@app.route("/projects/<int:project_id>/shares/<int:shared_user_id>", methods=["DELETE"])
def remove_project_share(project_id, shared_user_id):
    """Remove a user from project shares. Owner only."""
    user_id = _request_user_id()
    row = _check_project_access(project_id, user_id)
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    proj_uid = row["user_id"] if "user_id" in (row.keys() if hasattr(row, "keys") else []) else None
    if proj_uid != user_id:
        return json_error("Only the project owner can remove shares", 403)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM project_shares WHERE project_id = ? AND user_id = ?",
            (project_id, shared_user_id),
        )
        conn.commit()
        n = cur.rowcount
    if n == 0:
        return json_error("Share not found", 404)
    return jsonify({"ok": True})


@app.route("/projects/<int:project_id>", methods=["DELETE"])
def delete_project(project_id):
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    user_id = _request_user_id()
    proj_uid = row["user_id"] if "user_id" in (row.keys() if hasattr(row, "keys") else []) else None
    if user_id != proj_uid:
        return json_error("Only the project owner can delete the project", 403)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, file_path FROM project_files WHERE project_id = ?", (project_id,))
        file_rows = cur.fetchall()

    for fr in file_rows:
        fp = Path(fr["file_path"]) if fr["file_path"] else None
        if fp and fp.exists():
            try:
                fp.unlink()
            except OSError:
                pass
        try:
            from rag_service import remove_project_file_from_rag
            remove_project_file_from_rag(fr["id"])
        except Exception:
            pass

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM project_articles WHERE project_id = ?", (project_id,))
        cur.execute("DELETE FROM project_files WHERE project_id = ?", (project_id,))
        cur.execute("DELETE FROM project_chat_history WHERE project_id = ?", (project_id,))
        cur.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
    return jsonify({"message": "Project deleted"})


def _process_project_file(project_id: int, file_storage) -> dict:
    """Save, extract, summarize, and index a single project file. Returns file info dict."""
    import hashlib
    import time as _time

    from rag_service import (
        extract_text_from_pdf,
        generate_summary_three_pass,
        add_project_file_to_rag,
        is_llm_configured,
    )

    t0 = _time.time()
    filename = file_storage.filename
    title = filename.rsplit(".", 1)[0] if "." in filename else filename
    safe_name = f"{uuid.uuid4().hex}_{filename}"
    file_path = UPLOADS_DIR / safe_name

    file_bytes = file_storage.read()
    file_hash = hashlib.md5(file_bytes).hexdigest()
    with open(str(file_path), "wb") as fp:
        fp.write(file_bytes)

    print(f"[BACKEND] project file saved: {file_path} ({len(file_bytes)} bytes, +{_time.time()-t0:.2f}s)")

    full_text = extract_text_from_pdf(str(file_path))
    if not full_text.strip():
        file_path.unlink(missing_ok=True)
        return {"error": f"Could not extract text from {filename}", "title": title}

    summary = ""
    if is_llm_configured():
        try:
            summary_data = generate_summary_three_pass(full_text)
            summary = summary_data.get("full", "")
        except Exception as e:
            print(f"[BACKEND] summary failed for {filename}: {e}")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO project_files (project_id, title, file_path, file_hash, summary, full_text, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'ready')",
            (project_id, title, str(file_path), file_hash, summary, full_text),
        )
        conn.commit()
        pf_id = cur.lastrowid

    try:
        add_project_file_to_rag(pf_id, title, full_text)
    except Exception as e:
        print(f"[BACKEND] RAG index failed for {filename}: {e}")

    print(f"[BACKEND] project file processed: {title} (pf_id={pf_id}, +{_time.time()-t0:.2f}s)")
    return {"id": pf_id, "title": title, "status": "ready"}


@app.route("/projects/<int:project_id>/files", methods=["POST"])
def upload_project_files(project_id):
    """Upload one or more PDFs to a project."""
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    import time as _time
    t0 = _time.time()

    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return json_error("No files provided", 400)

    results = []
    errors = []
    for f in files:
        if not f or f.filename == "" or not _allowed_file(f.filename):
            errors.append(f"Skipped {f.filename}: not a PDF")
            continue
        try:
            info = _process_project_file(project_id, f)
            if "error" in info:
                errors.append(info["error"])
            else:
                results.append(info)
        except Exception as e:
            import traceback
            traceback.print_exc()
            errors.append(f"Failed to process {f.filename}: {e}")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,),
        )
        conn.commit()

    # Regenerate combined summary if we have ready files
    _regenerate_project_summary(project_id)

    print(f"[BACKEND] project files upload done: {len(results)} ok, {len(errors)} errors (+{_time.time()-t0:.2f}s)")
    return jsonify({"processed": results, "errors": errors}), 201


def _regenerate_project_summary(project_id: int):
    """Regenerate the combined project summary from files and/or linked articles."""
    try:
        from rag_service import generate_project_summary, is_llm_configured
        if not is_llm_configured():
            return

        file_summaries = []
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT title, summary FROM project_files "
                "WHERE project_id = ? AND status = 'ready' AND summary != ''",
                (project_id,),
            )
            file_summaries = [{"title": r["title"], "summary": r["summary"]} for r in cur.fetchall()]
            if not file_summaries:
                cur.execute(
                    "SELECT a.title, a.summary FROM articles a "
                    "JOIN project_articles pa ON a.id = pa.article_id "
                    "WHERE pa.project_id = ? AND a.summary IS NOT NULL AND a.summary != ''",
                    (project_id,),
                )
                file_summaries = [{"title": r["title"], "summary": r["summary"]} for r in cur.fetchall()]

        if not file_summaries:
            return

        combined = generate_project_summary(file_summaries)

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE projects SET combined_summary = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (combined, project_id),
            )
            conn.commit()
    except Exception as e:
        print(f"[BACKEND] combined summary failed: {e}")


@app.route("/projects/<int:project_id>/files/<int:file_id>", methods=["DELETE"])
def delete_project_file(project_id, file_id):
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT file_path FROM project_files WHERE id = ? AND project_id = ?",
            (file_id, project_id),
        )
        row = cur.fetchone()
    if not row:
        return json_error("File not found", 404)

    fp = Path(row["file_path"]) if row["file_path"] else None
    if fp and fp.exists():
        try:
            fp.unlink()
        except OSError:
            pass

    try:
        from rag_service import remove_project_file_from_rag
        remove_project_file_from_rag(file_id)
    except Exception:
        pass

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM project_files WHERE id = ?", (file_id,))
        conn.commit()

    _regenerate_project_summary(project_id)
    return jsonify({"message": "File removed"})


@app.route("/projects/<int:project_id>/rerun", methods=["POST"])
def rerun_project(project_id):
    """Re-process changed/new files by comparing MD5 hashes."""
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    import hashlib
    import time as _time
    t0 = _time.time()

    from rag_service import (
        extract_text_from_pdf,
        generate_summary_three_pass,
        add_project_file_to_rag,
        is_llm_configured,
    )

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM project_files WHERE project_id = ?", (project_id,))
        file_rows = cur.fetchall()

    updated = []
    unchanged = []
    errors = []

    for fr in file_rows:
        fp = Path(fr["file_path"]) if fr["file_path"] else None
        if not fp or not fp.exists():
            errors.append({"id": fr["id"], "title": fr["title"], "reason": "File missing"})
            continue

        with open(str(fp), "rb") as f:
            current_hash = hashlib.md5(f.read()).hexdigest()

        if current_hash == fr["file_hash"]:
            unchanged.append({"id": fr["id"], "title": fr["title"]})
            continue

        try:
            full_text = extract_text_from_pdf(str(fp))
            summary = ""
            if is_llm_configured():
                try:
                    sd = generate_summary_three_pass(full_text)
                    summary = sd.get("full", "")
                except Exception:
                    pass

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE project_files SET file_hash=?, summary=?, full_text=?, "
                    "status='ready', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (current_hash, summary, full_text, fr["id"]),
                )
                conn.commit()

            add_project_file_to_rag(fr["id"], fr["title"], full_text)
            updated.append({"id": fr["id"], "title": fr["title"]})
        except Exception as e:
            errors.append({"id": fr["id"], "title": fr["title"], "reason": str(e)})

    if updated:
        _regenerate_project_summary(project_id)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,),
        )
        conn.commit()

    print(f"[BACKEND] rerun done: {len(updated)} updated, {len(unchanged)} unchanged, {len(errors)} errors (+{_time.time()-t0:.2f}s)")
    return jsonify({"updated": updated, "unchanged": unchanged, "errors": errors})


@app.route("/projects/batch-rerun", methods=["POST"])
def batch_rerun_projects():
    """Re-process all files in selected projects."""
    import hashlib
    import time as _time
    t0 = _time.time()
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return json_error("ids is required", 400)

    from rag_service import (
        extract_text_from_pdf,
        generate_summary_three_pass,
        add_project_file_to_rag,
        is_llm_configured,
    )

    results = {"updated": [], "errors": []}

    for pid in ids:
        try:
            row = _check_project_access(pid, user_id)
            if row is None:
                results["errors"].append({"id": pid, "error": "Not found"})
                continue
            if row == "forbidden":
                results["errors"].append({"id": pid, "error": "Access denied"})
                continue
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM project_files WHERE project_id = ?", (pid,))
                file_rows = cur.fetchall()

            any_updated = False
            for fr in file_rows:
                fp = Path(fr["file_path"]) if fr["file_path"] else None
                if not fp or not fp.exists():
                    continue
                try:
                    full_text = extract_text_from_pdf(str(fp))
                    summary = ""
                    if is_llm_configured():
                        try:
                            sd = generate_summary_three_pass(full_text)
                            summary = sd.get("full", "")
                        except Exception:
                            pass

                    with open(str(fp), "rb") as f:
                        current_hash = hashlib.md5(f.read()).hexdigest()

                    with get_db() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE project_files SET file_hash=?, summary=?, full_text=?, "
                            "status='ready', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            (current_hash, summary, full_text, fr["id"]),
                        )
                        conn.commit()

                    add_project_file_to_rag(fr["id"], fr["title"], full_text)
                    any_updated = True
                except Exception as e:
                    print(f"[BACKEND] rerun project file {fr['id']} failed: {e}")

            if any_updated:
                _regenerate_project_summary(pid)

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (pid,))
                conn.commit()

            results["updated"].append(pid)
            print(f"[BACKEND] rerun project {pid} OK (+{_time.time()-t0:.2f}s)")

        except Exception as exc:
            results["errors"].append({"id": pid, "error": str(exc)})

    return jsonify(results)


@app.route("/projects/batch-delete", methods=["POST"])
def batch_delete_projects():
    """Delete multiple projects at once."""
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return json_error("ids is required", 400)
    user_id = _request_user_id()

    deleted = []
    errors = []
    for pid in ids:
        try:
            row = _check_project_access(pid, user_id)
            if row is None:
                errors.append({"id": pid, "error": "Not found"})
                continue
            if row == "forbidden":
                errors.append({"id": pid, "error": "Access denied"})
                continue
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, file_path FROM project_files WHERE project_id = ?", (pid,))
                file_rows = cur.fetchall()

            for fr in file_rows:
                fp = Path(fr["file_path"]) if fr["file_path"] else None
                if fp and fp.exists():
                    try:
                        fp.unlink()
                    except OSError:
                        pass
                try:
                    from rag_service import remove_project_file_from_rag
                    remove_project_file_from_rag(fr["id"])
                except Exception:
                    pass

            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM project_files WHERE project_id = ?", (pid,))
                cur.execute("DELETE FROM project_chat_history WHERE project_id = ?", (pid,))
                cur.execute("DELETE FROM projects WHERE id = ?", (pid,))
                conn.commit()
            deleted.append(pid)

        except Exception as exc:
            errors.append({"id": pid, "error": str(exc)})

    return jsonify({"deleted": deleted, "errors": errors})


@app.route("/projects/<int:project_id>/chat", methods=["POST"])
def chat_with_project(project_id):
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    chosen_model = (data.get("model") or "").strip() or None
    compare = data.get("compare", False)
    scope_article_ids = data.get("scope_article_ids")
    scope_project_file_ids = data.get("scope_project_file_ids")

    if not question:
        return json_error("question is required", 400)

    try:
        from rag_service import query_project, query_articles, generate_chat_answer, is_llm_configured, store_memory, get_available_models
        if not is_llm_configured():
            return json_error("LLM not configured.", 503)

        # Use scope params if provided (for per-item ask); otherwise use all linked articles + project files
        article_ids = []
        pf_ids = []
        if scope_article_ids is not None or scope_project_file_ids is not None:
            article_ids = list(scope_article_ids) if scope_article_ids else []
            pf_ids = [int(x) for x in scope_project_file_ids] if scope_project_file_ids else []
        else:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT article_id FROM project_articles WHERE project_id = ?", (project_id,))
                article_ids = [r["article_id"] for r in cur.fetchall()]
                cur.execute(
                    "SELECT id FROM project_files WHERE project_id = ? AND status = 'ready'",
                    (project_id,),
                )
                pf_ids = [r["id"] for r in cur.fetchall()]

        if not article_ids and not pf_ids:
            return json_error("No articles or files in this project yet. Add articles from Select Articles or upload files in Add Resource.", 400)

        context_parts = []
        if article_ids:
            context_parts.extend(query_articles(question, article_ids=article_ids, top_k=5))
        if pf_ids:
            context_parts.extend(query_project(question, pf_ids, top_k=5))
        context = context_parts[:12]

        if compare:
            models = get_available_models()
            results = {}
            for m in models:
                try:
                    results[m] = generate_chat_answer(
                        question, context, source_type="project", source_id=project_id, model=m,
                    )
                except Exception as exc:
                    results[m] = f"[Error from {m}]: {exc}"
                with get_db() as conn:
                    conn.cursor().execute(
                        "INSERT INTO project_chat_history (project_id, question, answer, model) VALUES (?, ?, ?, ?)",
                        (project_id, question, results[m], m),
                    )
                    conn.commit()
                try:
                    store_memory(question, results[m], "project", project_id)
                except Exception:
                    pass
            return jsonify({"compare": results, "sources": [c.get("title") for c in context]})

        answer = generate_chat_answer(
            question, context, source_type="project", source_id=project_id, model=chosen_model,
        )
        used_model = chosen_model or os.environ.get("CHAT_MODEL", "qwen3:8b")

        chat_id = None
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO project_chat_history (project_id, question, answer, model) VALUES (?, ?, ?, ?)",
                (project_id, question, answer, used_model),
            )
            chat_id = cur.lastrowid
            conn.commit()

        try:
            store_memory(question, answer, "project", project_id)
        except Exception:
            pass

        return jsonify({"answer": answer, "model": used_model, "chat_id": chat_id, "sources": [c.get("title") for c in context]})

    except Exception as e:
        return json_error(str(e), 500)


@app.route("/projects/<int:project_id>/chats", methods=["GET"])
def get_project_chats(project_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, question, answer, model, created_at, feedback FROM project_chat_history "
            "WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        )
        rows = cur.fetchall()
    return jsonify([
        {"id": r["id"], "question": r["question"], "answer": r["answer"],
         "model": r["model"] or "", "created_at": r["created_at"], "feedback": dict(r).get("feedback") or ""}
        for r in rows
    ])


@app.route("/projects/<int:project_id>/chats/<int:chat_id>", methods=["DELETE"])
def delete_project_chat(project_id, chat_id):
    """Delete a single chat from project history."""
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM project_chat_history WHERE id = ? AND project_id = ?", (chat_id, project_id))
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Chat not found", 404)
    return jsonify({"ok": True})


@app.route("/projects/<int:project_id>/chats/<int:chat_id>/feedback", methods=["POST"])
def set_project_chat_feedback(project_id, chat_id):
    """Set like/dislike feedback for a project chat message."""
    row = _check_project_access(project_id, _request_user_id())
    if row is None:
        return json_error("Project not found", 404)
    if row == "forbidden":
        return json_error("Access denied", 403)
    data = request.get_json(silent=True) or {}
    feedback = (data.get("feedback") or "").strip().lower()
    if feedback not in ("like", "dislike"):
        return json_error("feedback must be 'like' or 'dislike'", 400)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE project_chat_history SET feedback = ? WHERE id = ? AND project_id = ?",
            (feedback, chat_id, project_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return json_error("Chat not found", 404)
    return jsonify({"ok": True, "feedback": feedback})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
from admission_bot import register_routes as _register_admission_bot

_register_admission_bot(app, get_db, _crm_actor_ok, UPLOADS_DIR, DB_PATH_STR)

from student_bot import register_routes as _register_student_bot

_register_student_bot(app, get_db, UPLOADS_DIR)

if os.environ.get("FLASK_DEBUG", "false").lower() != "true" or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
    from email_outbox import start_worker as _start_email_worker

    _start_email_worker(get_db)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    print(f"[BACKEND] DB_PATH={DB_PATH_STR}")
    try:
        with get_db() as conn:
            n = conn.execute("SELECT COUNT(*) FROM user").fetchone()[0]
            print(f"[BACKEND] users_in_db={n}")
    except Exception as e:
        print(f"[BACKEND] users_in_db=? ({e})")
    app.run(host="0.0.0.0", port=port, debug=debug)
