import requests
from flask import jsonify, redirect, render_template, request, session, url_for


SUPPORT_DEPARTMENTS = {"mba", "master_chuyen_nganh", "ban_giam_doc", "tro_ly_bgd", "admin_he_thong"}


def session_departments() -> set:
    depts = (session.get("user") or {}).get("departments") or []
    return {d.get("code") for d in depts if isinstance(d, dict) and d.get("code")}


def is_student_session() -> bool:
    return "hoc_vien" in session_departments()


def register_student_bot(app, api_base: str, api_proxy, user_has_perm, is_exec_viewer, scopes_header):
    @app.context_processor
    def student_bot_context():
        return {
            "student_bot_enabled": bool(session.get("user")) and is_student_session() and not session.get("must_change_password")
        }

    def body():
        if request.method in ("POST", "PUT"):
            return request.get_json(silent=True) or {}
        return None

    @app.route("/api/student-bot/<path:sub>", methods=["GET", "POST"])
    def api_student_bot(sub):
        if not session.get("user"):
            return jsonify({"error": "Bạn cần đăng nhập."}), 401
        return api_proxy(request.method.lower(), f"/student/bot/{sub}", body(), timeout=180, params=request.args if request.method == "GET" else None)

    def staff_allowed():
        return (
            user_has_perm("students.support")
            or is_exec_viewer()
            or bool(session_departments() & SUPPORT_DEPARTMENTS)
        )

    @app.route("/ops/hoc-vien/ho-tro")
    def ops_student_support():
        if not staff_allowed():
            return redirect(url_for("ops_home"))
        return render_template("ops/student_support.html")

    @app.route("/api/ops/student-support/docs/upload", methods=["POST"])
    def api_student_support_upload():
        if not session.get("user"):
            return jsonify({"error": "Unauthorized"}), 401
        files = [
            ("files", (f.filename, f.stream, f.mimetype or "application/octet-stream"))
            for f in request.files.getlist("files")
        ]
        try:
            resp = requests.post(
                f"{api_base}/ops/student-support/docs/upload",
                files=files,
                data=dict(request.form.items()),
                headers=scopes_header(),
                timeout=180,
            )
            return jsonify(resp.json()), resp.status_code
        except requests.RequestException as e:
            return jsonify({"error": str(e)}), 503
        except ValueError:
            return jsonify({"error": "Phản hồi không hợp lệ."}), 502

    @app.route("/api/ops/student-support/<path:sub>", methods=["GET", "POST", "PUT", "DELETE"])
    def api_student_support(sub):
        if not session.get("user"):
            return jsonify({"error": "Unauthorized"}), 401
        return api_proxy(request.method.lower(), f"/ops/student-support/{sub}", body(), timeout=60, params=request.args if request.method == "GET" else None)
