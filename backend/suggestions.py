"""Feature suggestions / feedback from users per function."""
from __future__ import annotations

from datetime import datetime
from typing import Any


def ensure_suggestions_table(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS feature_suggestions ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "function_code TEXT NOT NULL, "
        "relative_path TEXT NOT NULL, "
        "title TEXT NOT NULL, "
        "body TEXT NOT NULL, "
        "user_id INTEGER, "
        "user_name TEXT NOT NULL, "
        "user_email TEXT, "
        "status TEXT NOT NULL DEFAULT 'open', "
        "created_at TEXT NOT NULL, "
        "updated_at TEXT, "
        "processed_at TEXT, "
        "processed_by TEXT)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_feat_sug_fn ON feature_suggestions(function_code)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_feat_sug_user ON feature_suggestions(user_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_feat_sug_created ON feature_suggestions(created_at)"
    )


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row(r) -> dict:
    if r is None:
        return {}
    keys = r.keys() if hasattr(r, "keys") else []
    if keys:
        return {k: r[k] for k in keys}
    return dict(r)


def create_suggestion(conn, data: dict) -> dict:
    cur = conn.cursor()
    ensure_suggestions_table(cur)
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    function_code = (data.get("function_code") or "").strip()
    relative_path = (data.get("relative_path") or "").strip() or "/"
    user_name = (data.get("user_name") or "").strip()
    if not title or not body:
        raise ValueError("Cần tiêu đề và nội dung đề xuất")
    if not function_code:
        raise ValueError("Thiếu mã chức năng")
    if not user_name:
        raise ValueError("Thiếu tên người đề xuất")
    # Soft length caps (TEXT columns; avoid accidental huge payloads)
    if len(title) > 500:
        title = title[:500]
    if len(body) > 20000:
        body = body[:20000]
    if len(function_code) > 200:
        function_code = function_code[:200]
    if len(relative_path) > 500:
        relative_path = relative_path[:500]
    now = _now()
    cur.execute(
        "INSERT INTO feature_suggestions "
        "(function_code, relative_path, title, body, user_id, user_name, user_email, "
        "status, created_at) VALUES (?,?,?,?,?,?,?,'open',?)",
        (
            function_code,
            relative_path,
            title,
            body,
            data.get("user_id"),
            user_name[:200],
            (data.get("user_email") or "").strip() or None,
            now,
        ),
    )
    conn.commit()
    sid = cur.lastrowid
    return get_suggestion(conn, sid)


def get_suggestion(conn, suggestion_id: int) -> dict | None:
    cur = conn.cursor()
    ensure_suggestions_table(cur)
    cur.execute("SELECT * FROM feature_suggestions WHERE id = ?", (suggestion_id,))
    row = cur.fetchone()
    return _row(row) if row else None


def list_suggestions(
    conn,
    *,
    user_id: int | None = None,
    function_code: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict]:
    cur = conn.cursor()
    ensure_suggestions_table(cur)
    sql = "SELECT * FROM feature_suggestions WHERE 1=1"
    params: list[Any] = []
    sql, params = _append_suggestion_filters(
        sql,
        params,
        user_id=user_id,
        function_code=function_code,
        status=status,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )
    sql += " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    params.extend([max(1, int(limit or 500)), max(0, int(offset or 0))])
    cur.execute(sql, params)
    return [_row(r) for r in cur.fetchall()]


def count_suggestions(
    conn,
    *,
    user_id: int | None = None,
    function_code: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
) -> int:
    cur = conn.cursor()
    ensure_suggestions_table(cur)
    sql = "SELECT COUNT(*) FROM feature_suggestions WHERE 1=1"
    params: list[Any] = []
    sql, params = _append_suggestion_filters(
        sql,
        params,
        user_id=user_id,
        function_code=function_code,
        status=status,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )
    return int(cur.execute(sql, params).fetchone()[0] or 0)


def _append_suggestion_filters(
    sql: str,
    params: list[Any],
    *,
    user_id: int | None = None,
    function_code: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
) -> tuple[str, list[Any]]:
    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    if function_code:
        sql += " AND function_code = ?"
        params.append(function_code)
    if status in ("open", "done"):
        sql += " AND status = ?"
        params.append(status)
    if date_from:
        sql += " AND date(created_at) >= date(?)"
        params.append(date_from)
    if date_to:
        sql += " AND date(created_at) <= date(?)"
        params.append(date_to)
    if q:
        sql += " AND (title LIKE ? OR body LIKE ? OR user_name LIKE ? OR function_code LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like, like])
    return sql, params


def set_suggestion_status(
    conn, suggestion_id: int, status: str, *, processed_by: str | None = None
) -> dict | None:
    if status not in ("open", "done"):
        raise ValueError("status must be open or done")
    cur = conn.cursor()
    ensure_suggestions_table(cur)
    now = _now()
    if status == "done":
        cur.execute(
            "UPDATE feature_suggestions SET status = ?, updated_at = ?, "
            "processed_at = ?, processed_by = ? WHERE id = ?",
            (status, now, now, processed_by, suggestion_id),
        )
    else:
        cur.execute(
            "UPDATE feature_suggestions SET status = ?, updated_at = ?, "
            "processed_at = NULL, processed_by = NULL WHERE id = ?",
            (status, now, suggestion_id),
        )
    conn.commit()
    return get_suggestion(conn, suggestion_id)


def bulk_set_suggestion_status(
    conn,
    suggestion_ids: list[int],
    status: str,
    *,
    processed_by: str | None = None,
) -> dict:
    if status not in ("open", "done"):
        raise ValueError("status must be open or done")
    ids: list[int] = []
    for raw in suggestion_ids or []:
        try:
            sid = int(raw)
        except (TypeError, ValueError):
            continue
        if sid > 0 and sid not in ids:
            ids.append(sid)
    if not ids:
        raise ValueError("Chưa chọn đề xuất nào")
    cur = conn.cursor()
    ensure_suggestions_table(cur)
    now = _now()
    updated = 0
    for sid in ids:
        if status == "done":
            cur.execute(
                "UPDATE feature_suggestions SET status = ?, updated_at = ?, "
                "processed_at = ?, processed_by = ? WHERE id = ?",
                (status, now, now, processed_by, sid),
            )
        else:
            cur.execute(
                "UPDATE feature_suggestions SET status = ?, updated_at = ?, "
                "processed_at = NULL, processed_by = NULL WHERE id = ?",
                (status, now, sid),
            )
        updated += cur.rowcount or 0
    conn.commit()
    return {"ok": True, "status": status, "requested": len(ids), "updated": updated}


def suggestion_stats(conn) -> dict:
    cur = conn.cursor()
    ensure_suggestions_table(cur)
    cur.execute("SELECT COUNT(*) FROM feature_suggestions")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM feature_suggestions WHERE status = 'open'")
    open_n = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM feature_suggestions WHERE status = 'done'")
    done_n = cur.fetchone()[0]
    cur.execute(
        "SELECT function_code, COUNT(*) AS n FROM feature_suggestions "
        "GROUP BY function_code ORDER BY n DESC LIMIT 20"
    )
    by_fn = [{"function_code": r[0], "count": r[1]} for r in cur.fetchall()]
    return {"total": total, "open": open_n, "done": done_n, "by_function": by_fn}
