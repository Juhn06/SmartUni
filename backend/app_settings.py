"""System-wide key/value settings (Admin configuration)."""

from __future__ import annotations

DEPLOYMENT_MODE_KEY = "deployment_mode"
DEPLOYMENT_DEVELOPMENT = "development"
DEPLOYMENT_PRODUCTION = "production"
VALID_DEPLOYMENT_MODES = (DEPLOYMENT_DEVELOPMENT, DEPLOYMENT_PRODUCTION)

DEFAULTS = {
    DEPLOYMENT_MODE_KEY: DEPLOYMENT_DEVELOPMENT,
}


def ensure_app_settings(cur) -> None:
    cur.execute(
        "CREATE TABLE IF NOT EXISTS app_settings ("
        "key TEXT PRIMARY KEY, "
        "value TEXT NOT NULL, "
        "updated_at TEXT)"
    )


def get_setting(conn, key: str, default: str | None = None) -> str:
    cur = conn.cursor()
    ensure_app_settings(cur)
    row = cur.execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)
    ).fetchone()
    if row and row[0] is not None and str(row[0]).strip() != "":
        return str(row[0]).strip()
    if default is not None:
        return default
    return DEFAULTS.get(key, "")


def set_setting(conn, key: str, value: str) -> str:
    from datetime import datetime, timezone

    cur = conn.cursor()
    ensure_app_settings(cur)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO app_settings (key, value, updated_at) VALUES (?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
        "updated_at = excluded.updated_at",
        (key, value, now),
    )
    conn.commit()
    return value


def get_deployment_mode(conn) -> str:
    mode = (get_setting(conn, DEPLOYMENT_MODE_KEY) or DEPLOYMENT_DEVELOPMENT).lower()
    if mode not in VALID_DEPLOYMENT_MODES:
        return DEPLOYMENT_DEVELOPMENT
    return mode


def set_deployment_mode(conn, mode: str) -> str:
    mode = (mode or "").strip().lower()
    if mode not in VALID_DEPLOYMENT_MODES:
        raise ValueError(
            f"deployment_mode must be one of: {', '.join(VALID_DEPLOYMENT_MODES)}"
        )
    return set_setting(conn, DEPLOYMENT_MODE_KEY, mode)


def is_production(conn) -> bool:
    return get_deployment_mode(conn) == DEPLOYMENT_PRODUCTION


def get_all_settings(conn) -> dict:
    cur = conn.cursor()
    ensure_app_settings(cur)
    rows = cur.execute("SELECT key, value, updated_at FROM app_settings").fetchall()
    stored = {r[0]: {"value": r[1], "updated_at": r[2] or ""} for r in rows}
    out = {}
    for key, default in DEFAULTS.items():
        if key in stored:
            out[key] = stored[key]
        else:
            out[key] = {"value": default, "updated_at": ""}
    for key, meta in stored.items():
        if key not in out:
            out[key] = meta
    out["deployment_mode"] = {
        "value": get_deployment_mode(conn),
        "updated_at": (stored.get(DEPLOYMENT_MODE_KEY) or {}).get("updated_at", ""),
    }
    return out
