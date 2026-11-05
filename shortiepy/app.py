import re
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request

from .__main__ import __version__, db_execute, generate_code


def create_app(config_port):
    app = Flask(
        __name__,
        template_folder=Path(__file__).parent / "templates",
        static_folder=Path(__file__).parent / "static",
    )

    app.config["PORT"] = config_port

    @app.context_processor
    def inject_version():
        return {"version": __version__}

    @app.route("/", methods=["GET"])
    def index():
        try:
            count = db_execute("SELECT COUNT(*) FROM urls", fetchone=True)[0]
        except RuntimeError:
            count = -1
        return render_template("index.html", total_urls=count, port=app.config["PORT"])

    @app.route("/<code>", methods=["GET"])
    def redirect_url(code):
        try:
            row = db_execute(
                "SELECT url FROM urls WHERE code = ?", (code,), fetchone=True
            )
        except RuntimeError:
            abort(404)
        if not row:
            abort(404)
        return redirect(row[0])

    @app.route("/new", methods=["GET"])
    def create_short_url():
        code = request.args.get("code") or generate_code()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", code):
            return "Invalid short code. Use 1–32 letters, numbers, '_' or '-'.", 400

        url = request.args.get("url")
        template_file = "message.html"

        if not url:
            return (
                render_template(
                    template_file,
                    title="❌ Missing Parameters",
                ),
                400,
            )

        try:
            db_execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, url))
            short_url = f"http://localhost:{app.config['PORT']}/{code}"
            return render_template(
                template_file,
                title="✨ Success!",
                short_url=short_url,
            )
        except RuntimeError:
            return (
                render_template(
                    template_file,
                    title="⚠️ Code Exists",
                    code=code,
                ),
                409,
            )

    @app.route("/list", methods=["GET"])
    def list_urls():
        try:
            rows = db_execute(
                "SELECT code, url, datetime(created_at, 'localtime') FROM urls ORDER BY created_at DESC",
                fetch=True,
            )
        except RuntimeError:
            rows = []

        urls = []
        for code, url, created in rows:
            short_url = f"http://localhost:{app.config['PORT']}/{code}"
            display_url = url
            urls.append(
                {
                    "code": code,
                    "short_url": short_url,
                    "display_url": (display_url[:30] + "...")
                    if len(display_url) > 30
                    else display_url,
                    "display_url_full": display_url,
                    "created": created,
                }
            )
        return render_template("list.html", urls=urls, port=app.config["PORT"])

    @app.route("/delete/<code>", methods=["POST"])
    def delete_url(code):
        try:
            db_execute("DELETE FROM urls WHERE code = ?", (code,))
        except RuntimeError:
            return {"success": False, "message": "Failed to delete URL."}, 500
        return {"success": True}

    return app
