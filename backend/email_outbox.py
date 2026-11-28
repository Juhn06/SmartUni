"""Deliver queued emails from email_outbox over SMTP when it is configured; otherwise keep them queued."""

from __future__ import annotations

import os
import smtplib
import threading
import time
from datetime import datetime
from email.mime.text import MIMEText

_started = False


def ensure_outbox_columns(cur) -> None:
    for column in ("sent_at TEXT", "attempts INTEGER DEFAULT 0", "last_error TEXT"):
        try:
            cur.execute(f"ALTER TABLE email_outbox ADD COLUMN {column}")
        except Exception:
            pass


def smtp_ready() -> bool:
    return bool(os.environ.get("SMTP_HOST") and os.environ.get("EMAIL_FROM"))


def _send(recipient: str, subject: str, body: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT") or 587)
    sender = os.environ["EMAIL_FROM"]
    user = os.environ.get("SMTP_USER") or sender
    password = os.environ.get("SMTP_PASSWORD") or ""
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"], msg["To"], msg["Subject"] = sender, recipient, subject
    with smtplib.SMTP(host, port, timeout=20) as server:
        if port in (587, 25):
            server.starttls()
        if password:
            server.login(user, password)
        server.sendmail(sender, [recipient], msg.as_string())


def send_pending(conn, limit: int = 20, max_attempts: int = 5) -> dict:
    from ops_crud import ensure_extra_ops_tables

    cur = conn.cursor()
    ensure_extra_ops_tables(cur)
    ensure_outbox_columns(cur)
    conn.commit()
    if not smtp_ready():
        return {"sent": 0, "failed": 0, "skipped": "smtp_not_configured"}
    rows = cur.execute(
        "SELECT id, recipient, subject, body FROM email_outbox "
        "WHERE status IN ('queued', 'retry') AND COALESCE(attempts, 0) < ? ORDER BY id LIMIT ?",
        (max_attempts, limit),
    ).fetchall()
    sent = failed = 0
    for row_id, recipient, subject, body in rows:
        try:
            _send(recipient, subject or "", body or "")
            cur.execute(
                "UPDATE email_outbox SET status = 'sent', sent_at = ?, attempts = COALESCE(attempts, 0) + 1, last_error = NULL WHERE id = ?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row_id),
            )
            sent += 1
        except Exception as e:
            cur.execute(
                "UPDATE email_outbox SET status = CASE WHEN COALESCE(attempts, 0) + 1 >= ? THEN 'failed' ELSE 'retry' END, "
                "attempts = COALESCE(attempts, 0) + 1, last_error = ? WHERE id = ?",
                (max_attempts, str(e)[:300], row_id),
            )
            failed += 1
        conn.commit()
    return {"sent": sent, "failed": failed}


def start_worker(get_db, interval: int = 60) -> None:
    global _started
    if _started:
        return
    _started = True

    def loop() -> None:
        while True:
            try:
                with get_db() as conn:
                    result = send_pending(conn)
                if result.get("sent") or result.get("failed"):
                    print(f"[EMAIL] đã gửi {result['sent']}, lỗi {result['failed']}")
            except Exception as e:
                print(f"[EMAIL] lỗi hàng đợi: {e}")
            time.sleep(interval)

    threading.Thread(target=loop, name="email-outbox", daemon=True).start()
