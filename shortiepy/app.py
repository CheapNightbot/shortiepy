import sqlite3
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request

from .__main__ import __version__, generate_code


def create_app(db_path, config_port):
    app = Flask(
        __name__,
        template_folder=Path(__file__).parent / "templates",
        static_folder=Path(__file__).parent / "static",
    )

    app.config["DB_PATH"] = db_path
    app.config["PORT"] = config_port

    @app.context_processor
    def inject_version():
        return dict(version=__version__)

    def get_db_connection():
        return sqlite3.connect(app.config["DB_PATH"])

    @app.route("/")
    def index():
        with get_db_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
        return render_template("index.html", total_urls=count, port=app.config["PORT"])

    @app.route("/<code>")
    def redirect_url(code):
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT url FROM urls WHERE code = ?", (code,))
            row = cur.fetchone()
        if not row:
            abort(404)
        return redirect(row[0])

    @app.route("/new")
    def create_short_url():
        code = request.args.get("code") or generate_code()
        url = request.args.get("url")

        if not url:
            return (
                render_template(
                    "message.html",
                    title="❌ Missing Parameters",
                    message="Use: <code>/new?code=your_code&url=https://example.com</code>",
                    link="/",
                ),
                400,
            )

        try:
            with get_db_connection() as conn:
                conn.execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, url))
            short_url = f"http://localhost:{app.config['PORT']}/{code}"
            return render_template(
                "message.html",
                title="✨ Success!",
                message=f"Created short URL: <a href='{short_url}'>{short_url}</a>",
                link="/",
            )
        except sqlite3.IntegrityError:
            return (
                render_template(
                    "message.html",
                    title="⚠️ Code Exists",
                    message=f"Code '{code}' is already taken!",
                    link="/",
                ),
                409,
            )

    @app.route("/list")
    def list_urls():
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT code, url, created_at FROM urls ORDER BY created_at DESC"
            )
            rows = cur.fetchall()

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

    return app
