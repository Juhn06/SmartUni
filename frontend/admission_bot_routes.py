import calendar
from datetime import date

import requests
from flask import Response, jsonify, redirect, render_template, request, session, url_for

PUBLIC_ENDPOINTS = (
    "index",
    "admission_public",
    "admission_widget",
    "admission_embed_js",
    "admission_api_config",
    "admission_api_chat",
    "admission_api_contact",
    "admission_api_register",
    "admission_api_messages",
)

DEFAULT_CONFIG = {
    "name": "UniBot",
    "org_name": "Trợ lý tuyển sinh sau đại học",
    "site_name": "Trung tâm Đào tạo Sau đại học",
    "greeting": "Xin chào! Mình có thể giúp gì cho bạn về tuyển sinh sau đại học?",
    "hotline": "",
    "contact_email": "",
    "quick_replies": [],
    "programs": ["MBA", "MMS", "MSCM"],
}


def load_config(api_base: str) -> dict:
    try:
        resp = requests.get(f"{api_base}/bot/public/config", timeout=5)
        if resp.status_code == 200:
            return {**DEFAULT_CONFIG, **resp.json()}
    except requests.RequestException:
        pass
    return dict(DEFAULT_CONFIG)


def admission_cycle(today: date) -> tuple[list[dict], dict]:
    start_year = today.year if today.month >= 10 else today.year - 1
    months = []
    for i in range(12):
        month = (10 + i - 1) % 12 + 1
        year = start_year if month >= 10 else start_year + 1
        marked = i == 0 or month == 1
        months.append({"num": month, "year": year, "marked": marked, "label": f"Th {month}/{year}" if marked else f"Th {month}"})
    index = next(i for i, m in enumerate(months) if m["num"] == today.month)
    days = calendar.monthrange(today.year, today.month)[1]
    position = (index + (today.day - 0.5) / days) / 12
    if today.month in (10, 11, 12, 1, 2):
        phase = "Đang là giai đoạn tư vấn và đăng ký quan tâm cho năm tuyển sinh tới."
        phase_short = "Tư vấn, đăng ký quan tâm"
    elif today.month == 3:
        phase = "Đang chuyển từ giai đoạn tư vấn sang nhận hồ sơ dự tuyển."
        phase_short = "Bắt đầu nhận hồ sơ"
    elif today.month in (4, 5, 6, 7):
        phase = "Đang nhận hồ sơ, tổ chức thi viết và phỏng vấn."
        phase_short = "Nhận hồ sơ, thi và phỏng vấn"
    else:
        phase = "Đang nhận hồ sơ đợt cuối và xét duyệt trúng tuyển."
        phase_short = "Xét duyệt trúng tuyển"
    if today.month < 5:
        next_mba = f"5/{today.year}"
    elif today.month < 8:
        next_mba = f"8/{today.year}"
    else:
        next_mba = f"5/{today.year + 1}"
    now = {
        "month": today.month,
        "year": today.year,
        "position": position,
        "phase": phase,
        "phase_short": phase_short,
        "next_mba": next_mba,
        "next_year": start_year + 1,
    }
    return months, now


def _stroke_icon(path: str, color: str = "#00528c", width: str = "2") -> str:
    return (
        f'<svg viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="{path}"/></svg>'
    )


ICONS = {
    "check": _stroke_icon("M5 12.5l4.5 4.5L19 7.5", "#f2b705", "3"),
    "globe": _stroke_icon("M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"),
    "award": _stroke_icon("M12 3a6 6 0 1 0 0 12a6 6 0 1 0 0-12zM8.5 13.5 7 21l5-2.5 5 2.5-1.5-7.5"),
    "people": _stroke_icon("M9 11a3 3 0 1 0 0-6a3 3 0 0 0 0 6zM17 11a3 3 0 1 0 0-6M3 20c0-3 2.7-5 6-5s6 2 6 5M15 15c3.3 0 6 2 6 5"),
    "net": _stroke_icon("M12 3a2.5 2.5 0 1 0 0 5a2.5 2.5 0 0 0 0-5zM5 16a2.5 2.5 0 1 0 0 5a2.5 2.5 0 0 0 0-5zM19 16a2.5 2.5 0 1 0 0 5a2.5 2.5 0 0 0 0-5zM11 8l-5 8M13 8l5 8M7.5 18.5h9"),
    "chevron": _stroke_icon("M6 9l6 6 6-6", "#00528c", "2.4"),
}


def event_date_parts(value: str) -> dict:
    parts = (value or "").split()
    day_part = parts[-1] if parts else ""
    time_part = parts[0] if len(parts) > 1 else ""
    bits = day_part.split("/")
    if len(bits) != 3:
        return {"day": "", "month": "", "time": time_part}
    return {"day": bits[0], "month": f"Th {int(bits[1])}", "time": time_part}


def render_landing(api_base: str):
    overview = {"rounds": [], "events": [], "faqs": [], "deadline_days": None}
    try:
        resp = requests.get(f"{api_base}/bot/public/overview", timeout=5)
        if resp.status_code == 200:
            overview = {**overview, **resp.json()}
    except requests.RequestException:
        pass
    for event in overview.get("events") or []:
        event.update(event_date_parts(event.get("starts_at", "")))
    months, now = admission_cycle(date.today())
    return render_template(
        "public/landing.html",
        config=load_config(api_base),
        overview=overview,
        months=months,
        now=now,
        icons=ICONS,
    )


def register_admission_bot(app, api_base: str, api_proxy, user_has_perm, is_exec_viewer, scopes_header):
    def client_headers():
        ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
        return {"X-Client-IP": ip}

    def forward(method: str, path: str, json_body=None, params=None):
        try:
            resp = requests.request(
                method,
                f"{api_base}{path}",
                json=json_body,
                params=params,
                headers=client_headers(),
                timeout=90,
            )
        except requests.RequestException:
            return jsonify({"error": "Hệ thống đang bận, vui lòng thử lại sau."}), 503
        try:
            return jsonify(resp.json()), resp.status_code
        except ValueError:
            return jsonify({"error": "Phản hồi không hợp lệ."}), 502

    def config():
        return load_config(api_base)

    @app.after_request
    def admission_cors(resp):
        if request.endpoint == "admission_embed_js":
            resp.headers["Access-Control-Allow-Origin"] = "*"
        if request.endpoint == "admission_widget":
            resp.headers.pop("X-Frame-Options", None)
        return resp

    @app.route("/tu-van")
    def admission_public():
        return redirect(url_for("index", chat=1))

    @app.route("/tu-van/widget")
    def admission_widget():
        return render_template(
            "public/admission_widget.html",
            config=config(),
            api_base=url_for("admission_public") + "/api",
        )

    @app.route("/tu-van/embed.js")
    def admission_embed_js():
        cfg = config()
        body = render_template(
            "public/embed.js",
            config=cfg,
            widget_url=url_for("admission_widget", _external=True),
            teaser=f"Bạn cần tư vấn về chương trình, lịch tuyển sinh hay hồ sơ? Hỏi {cfg['name']} nhé!",
            mascot=render_template("public/_mascot.svg"),
        )
        return Response(body, mimetype="application/javascript", headers={"Cache-Control": "public, max-age=300"})

    @app.route("/tu-van/api/config", methods=["GET"])
    def admission_api_config():
        return jsonify(config())

    @app.route("/tu-van/api/chat", methods=["POST"])
    def admission_api_chat():
        return forward("POST", "/bot/public/chat", request.get_json(silent=True) or {})

    @app.route("/tu-van/api/contact", methods=["POST"])
    def admission_api_contact():
        return forward("POST", "/bot/public/contact", request.get_json(silent=True) or {})

    @app.route("/tu-van/api/register", methods=["POST"])
    def admission_api_register():
        return forward("POST", "/bot/public/register", request.get_json(silent=True) or {})

    @app.route("/tu-van/api/messages", methods=["GET"])
    def admission_api_messages():
        return forward("GET", "/bot/public/messages", params=dict(request.args))

    def allowed():
        return user_has_perm("admissions.chatbot") or user_has_perm("admissions.crm_source") or is_exec_viewer()

    @app.route("/ops/tuyen-sinh/chatbot")
    def ops_admissions_chatbot():
        if not allowed():
            return redirect(url_for("ops_home"))
        return render_template("ops/chatbot.html")

    @app.route("/api/ops/chatbot/docs/upload", methods=["POST"])
    def api_ops_chatbot_upload():
        if not session.get("user"):
            return jsonify({"error": "Unauthorized"}), 401
        files = [
            ("files", (f.filename, f.stream, f.mimetype or "application/octet-stream"))
            for f in request.files.getlist("files")
        ]
        try:
            resp = requests.post(
                f"{api_base}/ops/chatbot/docs/upload",
                files=files,
                data={k: v for k, v in request.form.items()},
                headers=scopes_header(),
                timeout=180,
            )
            return jsonify(resp.json()), resp.status_code
        except requests.RequestException as e:
            return jsonify({"error": str(e)}), 503
        except ValueError:
            return jsonify({"error": "Phản hồi không hợp lệ."}), 502

    @app.route("/api/ops/chatbot/<path:sub>", methods=["GET", "POST", "PUT", "DELETE"])
    def api_ops_chatbot(sub):
        if not session.get("user"):
            return jsonify({"error": "Unauthorized"}), 401
        method = request.method.lower()
        body = request.get_json(silent=True) if method in ("post", "put") else None
        if method in ("post", "put") and body is None:
            body = {}
        return api_proxy(method, f"/ops/chatbot/{sub}", body, timeout=90, params=request.args if method == "get" else None)
