#!/usr/bin/env python3

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("shortiepy")
except PackageNotFoundError:
    __version__ = "unknown"

import json
import os
import platform
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path

import click
import pyperclip
from colorama import init as colorama_init
from flask import Flask, abort, redirect, request
from markupsafe import escape
from tabulate import tabulate
from waitress import serve

# --- Kaomoji & Color Helpers ---
colorama_init()  # Required for Windows


def cute_echo(text, fg="bright_magenta"):
    """Echo with pastel colors and sparkles"""
    click.echo(click.style(text, fg=fg))


def success(text):
    return click.style(f"🌸 {text}", fg="bright_magenta")


def error(text):
    return click.style(f"❌ {text}", fg="bright_red")


def info(text):
    return click.style(f"ℹ️  {text}", fg="bright_blue")


def warn(text):
    return click.style(f"⚠️  {text}", fg="bright_yellow")


class Config:
    def __init__(self, config_path: Path, default_port):
        self.config_path = config_path
        self.default_port = default_port
        self._port = None  # Lazy-loaded

    @property
    def port(self):
        if self._port is None:
            self._port = self._load()
        return self._port

    def _load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    return json.load(f).get("port", self.default_port)
            except (json.JSONDecodeError, KeyError):
                pass
        return self.default_port

    def save(self, port):
        """Save new port and update cache"""
        with open(self.config_path, "w") as f:
            json.dump({"port": port}, f)
        self._port = port  # Update cache


# Determine OS-specific data directory
def get_data_dir():
    home = Path.home()
    system = platform.system()
    if system == "Windows":
        return home / "AppData" / "Roaming" / "shortiepy"
    elif system == "Darwin":  # macOS
        return home / "Library" / "Application Support" / "shortiepy"
    else:  # Linux and others
        return home / ".local" / "share" / "shortiepy"


# Paths
DATA_DIR = get_data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)  # Create if missing
DB_PATH = DATA_DIR / "shortiepy.db"
LOCK_FILE = Path(tempfile.gettempdir()) / "shortiepy.lock"
LOG_FILE = Path(tempfile.gettempdir()) / "shortiepy.log"

# Config
CONFIG_PATH = DATA_DIR / "config.json"
DEFAULT_PORT = 9876
config = Config(CONFIG_PATH, DEFAULT_PORT)


# --- Helper Functions ---
def generate_code(length=5):
    return secrets.token_urlsafe(length)[:length]


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS urls (
            code TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.close()


def db_execute(query, params=(), fetch=False):
    """Execute DB query safely with automatic connection handling"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
            return cur.rowcount
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            raise RuntimeError("Database busy! Try again later. (；′⌒`)")
        raise


# --- Flask App (for server) ---
app = Flask(__name__)


@app.route("/")
def index():
    init_db()
    count = db_execute("SELECT COUNT(*) FROM urls", fetch=True)[0][0]

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>shortiepy 🌸</title>
        <style>
            body {{
                font-family: 'Segoe UI', system-ui, sans-serif;
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
                background: #fff9fb;
                color: #5a3a5e;
                line-height: 1.6rem;
            }}
            h1 {{
                color: #ff69b4;
                text-align: center;
                margin-bottom: 30px;
            }}
            h2, h3 {{
                color: #d47ab8;
                margin-top: 24px;
            }}
            .header {{
                text-align: center;
                margin-bottom: 30px;
            }}
            .stats {{
                background: #f8e9f1;
                padding: 15px;
                border-radius: 12px;
                margin: 20px 0;
                text-align: center;
            }}
            .card {{
                background: white;
                border-radius: 12px;
                padding: 20px;
                margin: 20px 0;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            code {{
                background: #f0e6f5;
                padding: 2px 6px;
                border-radius: 4px;
                font-family: monospace;
            }}
            .option {{
                color: #a07cb2;
                font-style: italic;
                font-size: 0.9em;
            }}
            pre {{
                background: #f8e9f1;
                padding: 12px;
                border-radius: 8px;
                overflow-x: auto;
                margin: 12px 0;
            }}
            pre code {{
                background: transparent;
                padding: 0;
                font-size: 0.95em;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>✨ shortiepy 🌸</h1>
            <p>Your local URL shortener ( ˶˘ ³˘)♡</p>
        </div>

        <div class="stats">
            <strong>Total URLs:</strong> {count}
        </div>

        <div class="card">
            <h2>🌐 Web API</h2>
            <p>Create short URLs directly from your browser:</p>
            <code>/new?code=your_code&url=https://example.com</code>
            <p>Example: </p>
            <ul>
                <li><a href="/new?code=meow&url=https://example.com">/new?code=meow&url=https://example.com</a></li>
                <li><a href="/new?url=https://example.org">/new?code=url=https://example.org</a></li>
            </ul>
        </div>

        <div class="card">
            <h2>💻 CLI Commands</h2>

            <h3>🔗 URL Management</h3>
            <ul>
                <li><code>shortiepy add &lt;URL&gt;</code> → Create short URL</li>
                <li><code>shortiepy list</code> → Show all links</li>
                <li><code>shortiepy delete &lt;code&gt;</code> → Remove link</li>
            </ul>

            <h3>🖥️ Server Control</h3>
            <ul>
                <li><code>shortiepy serve</code> → Start server (foreground)
                    <ul class="option">
                        <li>Optional: <code>--port PORT</code></li>
                    </ul>
                </li>
                <li><code>shortiepy start</code> → Start server (background)
                    <ul class="option">
                        <li>Optional: <code>--port PORT</code></li>
                    </ul>
                </li>
                <li><code>shortiepy stop</code> → Stop background server</li>
                <li><code>shortiepy status</code> → Check server status</li>
            </ul>

            <h3>ℹ️ Information</h3>
            <ul>
                <li><code>shortiepy config</code> → Show configuration</li>
                <li><code>shortiepy docs</code> → Open this documentation</li>
                <li><code>shortiepy --version</code> → Show version</li>
            </ul>
        </div>

        <div class="card">
            <h2>📝 Examples</h2>

            <h3>✨ Basic Workflow</h3>
            <pre><code>&gt;&gt;&gt; shortiepy add https://example.com/very/long/url
🌸 Copied to clipboard: http://localhost:9876/x9f2k</code></pre>

            <pre><code>&gt;&gt;&gt; shortiepy list
ℹ️  Your shortiepy links:
╭────────┬─────────────────────────────┬───────────────────────────────────┬─────────────────────╮
│ Code   │ Short URL                   │ Original URL                      │ Created At          │
├────────┼─────────────────────────────┼───────────────────────────────────┼─────────────────────┤
│ x9f2k  │ http://localhost:9876/x9f2k │ https://example.com/very/long/url │ YYYY-MM-DD hh:mm:ss │
╰────────┴─────────────────────────────┴───────────────────────────────────┴─────────────────────╯
</code></pre>

            <pre><code>&gt;&gt;&gt; shortiepy delete x9f2k
🌸 Deleted: http://localhost:9876/x9f2k</code></pre>

            <h3>⚙️ Custom Port</h3>
            <pre><code>&gt;&gt;&gt; shortiepy start --port 8080
🌸 Started server (PID: 12345)
ℹ️  Logs: /tmp/shortiepy.log</code></pre>

            <pre><code>&gt;&gt;&gt; shortiepy add https://example.com
🌸 Copied to clipboard: http://localhost:8080/y3k9m</code></pre>
        </div>

        <div class="card">
            <h2>🎀 Features</h2>
            <ul>
                <li>🔒 100% offline - no data leaves your machine</li>
                <li>🌸 Cross-platform (Linux/macOS/Windows)</li>
                <li>📋 Auto-copies short URLs to clipboard</li>
                <li>🎨 Pastel colors & kaomojis everywhere!</li>
            </ul>
        </div>

        <div style="text-align: center; margin-top: 40px; color: #a07cb2;">
            <p>Made with 🩷 by ポテト ^. .^₎ฅ | v{__version__}</p>
        </div>
    </body>
    </html>
    """


@app.route("/<code>")
def redirect_url(code):
    with sqlite3.connect(DB_PATH) as conn:
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

    if not code or not url:
        return (
            f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>shortiepy 🌸</title>
            <style>
                body {{
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    max-width: 800px;
                    margin: 40px auto;
                    padding: 20px;
                    background: #fff9fb;
                    color: #5a3a5e;
                    line-height: 1.6rem;
                }}
                h2, h3 {{
                    color: #d47ab8;
                    margin-top: 24px;
                }}
                .card {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    margin: 20px 0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .btn {{
                    color: #ff69b4;
                    background: #ffdfef;
                    padding: 0.6rem;
                    border-radius: 0.5rem;
                    text-decoration: none;
                    display: inline-block;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>❌ Missing Parameters</h2>
                <p>Use: <code>/new?code=your_code&url=https://example.com</code></p>
                <a href="/" class="btn">← Back to homepage</a>
            </div>
        </body>
        </html>
        """,
            400,
        )

    init_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, url))
        short_url = f"http://localhost:{config.port}/{code}"
        return (
            f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>shortiepy 🌸</title>
            <style>
                body {{
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    max-width: 800px;
                    margin: 40px auto;
                    padding: 20px;
                    background: #fff9fb;
                    color: #5a3a5e;
                    line-height: 1.6rem;
                }}
                h2, h3 {{
                    color: #d47ab8;
                    margin-top: 24px;
                }}
                .card {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    margin: 20px 0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .btn {{
                    color: #ff69b4;
                    background: #ffdfef;
                    padding: 0.6rem;
                    border-radius: 0.5rem;
                    text-decoration: none;
                    display: inline-block;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>✨ Success!</h2>
                <p>Created short URL:</p>
                <p><a href="{escape(short_url)}" style="color: #ff69b4; font-size: 1.2em;">{escape(short_url)}</a></p>
                <a href="/" class="btn">← Back to homepage</a>
            </div>
        </body>
        </html>
        """,
            200,
        )
    except sqlite3.IntegrityError:
        return (
            f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>shortiepy 🌸</title>
            <style>
                body {{
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    max-width: 800px;
                    margin: 40px auto;
                    padding: 20px;
                    background: #fff9fb;
                    color: #5a3a5e;
                    line-height: 1.6rem;
                }}
                h2, h3 {{
                    color: #d47ab8;
                    margin-top: 24px;
                }}
                .card {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    margin: 20px 0;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .btn {{
                    color: #ff69b4;
                    background: #ffdfef;
                    padding: 0.6rem;
                    border-radius: 0.5rem;
                    text-decoration: none;
                    display: inline-block;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>⚠️ Code Exists</h2>
                <p>Code '{escape(code)}' is already taken!</p>
                <a href="/" class="btn">← Back to homepage</a>
            </div>
        </body>
        </html>
        """,
            409,
        )


# --- CLI Commands ---
@click.group()
@click.version_option(version=__version__, prog_name="shortiepy")
def cli():
    """shortiepy: your local URL shortner ( ˶˘ ³˘)♡"""
    pass


@cli.command()
@click.argument("action", required=False, default="install")
def completion(action):
    """Manage shell completions"""
    if action != "install":
        cute_echo(warn("Only 'install' is supported"))
        return

    # Detect shell
    shell = os.environ.get("SHELL", "").split("/")[-1]
    home = Path.home()

    if shell == "bash":
        dest_dir = home / ".local" / "share" / "bash-completion" / "completions"
        dest_file = dest_dir / "shortiepy"
        src_file = Path(__file__).parent / "completions" / "shortiepy.bash"

    elif shell == "zsh":
        dest_dir = home / ".zsh" / "completions"
        dest_file = dest_dir / "_shortiepy"
        src_file = Path(__file__).parent / "completions" / "shortiepy.zsh"

    elif shell == "fish":
        dest_dir = home / ".config" / "fish" / "completions"
        dest_file = dest_dir / "shortiepy.fish"
        src_file = Path(__file__).parent / "completions" / "shortiepy.fish"

    else:
        cute_echo(error(f"Unsupported shell: {shell}"))
        cute_echo(info("Supported: bash, zsh, fish"))
        return

    # Create directory
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Copy file
    try:
        shutil.copy(src_file, dest_file)
        cute_echo(success(f"Installed completion for {shell}!"))
        if shell == "bash":
            cute_echo(
                info(
                    """Restart your shell or run:
    source ~/.bashrc"""
                )
            )
        elif shell == "zsh":
            cute_echo(
                info(
                    """Restart your shell or run:
    source ~/.zshrc"""
                )
            )
        # Fish loads automatically /ᐠ •⩊•マ

    except Exception as e:
        cute_echo(error(f"Failed to install: {e}"))


@cli.command()
@click.argument("url")
def add(url):
    """Add a new URL and copy short link to clipboard"""
    init_db()
    code = generate_code()

    try:
        db_execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, url))
        short_url = f"http://localhost:{config.port}/{code}"
        pyperclip.copy(short_url)
        cute_echo(success(f"Copied to clipboard: {short_url}"))
    except sqlite3.IntegrityError:
        # Very rare, but handle duplicate codes
        cute_echo(warn("Oops! Code collision (unlikely!) ~ (ᵕ—ᴗ—)"))
        return add(url)  # retry
    except RuntimeError as e:
        cute_echo(error(str(e)))


@cli.command()
@click.argument("code")
def delete(code):
    """Delete a short URL by code"""
    try:
        deleted = db_execute("DELETE FROM urls WHERE code = ?", (code,))
    except RuntimeError as e:
        cute_echo(error(str(e)))

    if deleted:
        cute_echo(success(f"Deleted: http://localhost:{config.port}/{code}"))
    else:
        cute_echo(error(f"Code '{code}' not found! (；′⌒`)"))


@cli.command()
def docs():
    """Open documentation in browser"""
    # Check if server is running
    if not LOCK_FILE.exists():
        cute_echo(error("Server not running! (；′⌒`)"))
        cute_echo(
            info(
                """Please start the server first:
    shortiepy serve    →  Foreground server
    shortiepy start    →  Background server"""
            )
        )
        return

    url = f"http://localhost:{config.port}"
    try:
        cute_echo(info(f"Opening docs: {url}"))
        webbrowser.open(url)
    except Exception as e:
        cute_echo(error(f"Failed to open browser: {str(e)}"))
        cute_echo(info(f"Visit manually: {url}"))


@cli.command()
def list():
    """List all shortened URLs"""
    init_db()

    try:
        rows = db_execute(
            "SELECT code, url, created_at FROM urls ORDER BY created_at DESC",
            fetch=True,
        )
    except RuntimeError as e:
        cute_echo(error(str(e)))

    if not rows:
        cute_echo(warn("(;´༎ຶД༎ຶ`) No links yet! Add one with `shortiepy add <URL>`"))
        return

    # Prepare data
    table_data = []
    for code, url, created in rows:
        short_url = f"http://localhost:{config.port}/{code}"
        # Truncate long URLs for readability
        display_url = (url[:40] + "...") if len(url) > 40 else url
        table_data.append((code, short_url, display_url, created))

    headers = ["Code", "Short URL", "Original URL", "Created At"]
    output = tabulate(table_data, headers=headers, tablefmt="rounded_grid")
    cute_echo(info("Your shortiepy links:"))
    click.echo(output)


@cli.command(name="serve")
@click.option("--port", default=DEFAULT_PORT, help="Port to run shortiepy on")
def run(port):
    """Start the local redirect server"""
    config.save(port)
    cute_echo(info(f"Running shortiepy server on http://localhost:{config.port}"))
    cute_echo(warn("Press CTRL + C to stop the server. (๑•̀ㅂ•́)و✧"))
    serve(app=app, host="localhost", port=config.port)


@cli.command(name="config")
def show_config():
    """Show shortiepy configurations"""
    config_data = [
        ("Version", __version__),
        ("Port", str(config.port)),
        ("Host", "localhost"),
        ("Data Directory", str(DATA_DIR)),
        ("Database", str(DB_PATH)),
        ("Config File", str(CONFIG_PATH)),
        ("Log File", str(LOG_FILE)),
        ("Lock File", str(LOCK_FILE)),
    ]

    click.echo(tabulate(config_data, tablefmt="rounded_grid"))


@cli.command()
@click.option("--port", default=DEFAULT_PORT, help="Port to run shortiepy on")
def start(port):
    """Start shortiepy server in the background"""
    config.save(port)

    if LOCK_FILE.exists():
        with open(LOCK_FILE) as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, 0)
            cute_echo(info(f"Server already running (PID: {pid})"))
            cute_echo(info(f"URL: http://localhost:{config.port}"))
            return
        except OSError:
            LOCK_FILE.unlink()

    package_dir = Path(__file__).parent.resolve()
    if not (package_dir / "__main__.py").exists():
        raise RuntimeError("Cannot find shortiepy package")

    # Create a minimal script to start the server
    server_script = f"""
import sys
sys.path.insert(0, {repr(str(package_dir))})
from shortiepy.__main__ import app
from waitress import serve
serve(app=app, host="localhost", port={port})
"""

    # Start in background
    proc = subprocess.Popen(
        [sys.executable, "-c", server_script],
        stdout=open(LOG_FILE, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    with open(LOCK_FILE, "w") as f:
        f.write(str(proc.pid))

    cute_echo(success(f"Started server (PID: {proc.pid})"))
    cute_echo(info(f"Logs: {LOG_FILE}"))
    cute_echo(info(f"URL: http://localhost:{config.port}"))


@cli.command()
def stop():
    """Stop the background server"""
    if not os.path.exists(LOCK_FILE):
        cute_echo(warn("No background server running („• ֊ •„)"))
        return

    with open(LOCK_FILE) as f:
        pid = int(f.read().strip())

    try:
        os.kill(pid, 15)  # SIGTERM
        os.remove(LOCK_FILE)
        cute_echo(success(f"Stopped server (PID: {pid}) ദ്ദി◝ ⩊ ◜.ᐟ"))
    except ProcessLookupError:
        cute_echo(error("Server not found. Cleaning up lock file."))
        os.remove(LOCK_FILE)


@cli.command()
def status():
    """Show server status and stats"""
    if LOCK_FILE.exists():
        with open(LOCK_FILE) as f:
            try:
                pid = int(f.read().strip())
                os.kill(pid, 0)  # Check if running
                cute_echo(success(f"Server: Running (PID: {pid}) (˶˃ ᵕ ˂˶) .ᐟ.ᐟ"))
            except (OSError, ValueError):
                cute_echo(warn("Server: Stopped (stale lock)"))
                LOCK_FILE.unlink()
    else:
        cute_echo(warn("Server: Stopped (•˕ •マ.ᐟ"))

    # Show DB stats
    init_db()
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
    conn.close()
    cute_echo(info(f"Total URLs: {count}"))
