import sqlite3
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

    @app.route("/")
    def index():
        try:
            count = db_execute("SELECT COUNT(*) FROM urls", fetchone=True)[0]
        except RuntimeError:
            count = -1
        return render_template("index.html", total_urls=count, port=app.config["PORT"])

    @app.route("/<code>")
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

    @app.route("/new")
    def create_short_url():
        code = request.args.get("code") or generate_code()
        url = request.args.get("url")
        templete_file = "message.html"

        if not url:
            return (
                render_template(
                    templete_file,
                    title="❌ Missing Parameters",
                    message="Use: <code>/new?code=your_code&url=https://example.com</code>",
                    link="/",
                ),
                400,
            )

        try:
            db_execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, url))
            short_url = f"http://localhost:{app.config['PORT']}/{code}"
            return render_template(
                templete_file,
                title="✨ Success!",
                message=f"Created short URL: <a href='{short_url}' target='_blank' rel='nofollow noopener'>{short_url}</a>",
                link="/",
            )
        except RuntimeError:
            return (
                render_template(
                    templete_file,
                    title="⚠️ Code Exists",
                    message=f"Code '{code}' is already taken!",
                    link="/",
                ),
                409,
            )

    @app.route("/list")
    def list_urls():
        try:
            rows = db_execute(
                "SELECT code, url, created_at FROM urls ORDER BY created_at DESC",
                fetch=True,
            )
        except RuntimeError:
            rows = []

        urls = []
        for code, url, created in rows:
            short_url = f"http://localhost:{app.config['PORT']}/{code}"
            display_url = (url[:50] + "...") if len(url) > 50 else url
            urls.append(
                {
                    "code": code,
                    "short_url": short_url,
                    "display_url": display_url,
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
