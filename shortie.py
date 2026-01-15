#!/usr/bin/env python3

import json
import os
import platform
import secrets
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import click
import pyperclip
from colorama import init as colorama_init
from flask import Flask, abort, redirect, request
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


# --- Flask App (for server) ---
app = Flask(__name__)


# placeholder for now so that we don't get 404 meow ~
@app.route("/")
def index():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM urls").fetchone()
    conn.close()
    return {
        "shortiepy": "your local URL shortner ( ˶˘ ³˘)♡",
        "total_urls": count[0],
    }


@app.route("/<code>")
def redirect_url(code):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT url FROM urls WHERE code = ?", (code,))
    row = cur.fetchone()
    conn.close()

    if not row:
        abort(404)
    return redirect(row[0])


@app.route("/new")
def create_short_url():
    code = request.args.get("code")
    url = request.args.get("url")

    if not code or not url:
        return "Error: Missing 'code' or 'url'", 400

    init_db()
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, url))
        conn.commit()
        conn.close()
        return f"http://localhost:{config.port}/{code}", 200
    except sqlite3.IntegrityError:
        return f"Code '{code}' exists", 409


# --- CLI Commands ---
@click.group()
def cli():
    """shortiepy: your local URL shortner ( ˶˘ ³˘)♡"""
    pass


@cli.command()
@click.argument("url")
def add(url):
    """Add a new URL and copy short link to clipboard"""
    init_db()
    code = generate_code()

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT INTO urls (code, url) VALUES (?, ?)", (code, url))
        conn.commit()
        conn.close()
        short_url = f"http://localhost:{config.port}/{code}"
        pyperclip.copy(short_url)
        cute_echo(success(f"Copied to clipboard: {short_url}"))
    except sqlite3.IntegrityError:
        # Very rare, but handle duplicate codes
        cute_echo(warn("Oops! Code collision (unlikely!) ~ (ᵕ—ᴗ—)"))
        return add(url)  # retry


@cli.command()
@click.argument("code")
def delete(code):
    """Delete a short URL by code"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM urls WHERE code = ?", (code,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if deleted:
        cute_echo(success(f"Deleted: http://localhost:{config.port}/{code}"))
    else:
        cute_echo(error(f"Code '{code}' not found! (；′⌒`)"))


@cli.command()
def list():
    """List all shortened URLs"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT code, url, created_at FROM urls ORDER BY created_at DESC")
    rows = cur.fetchall()
    conn.close()

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
            return
        except OSError:
            LOCK_FILE.unlink()

    # Start in background
    proc = subprocess.Popen(
        ["python3", __file__, "serve", "--port", str(port)],
        stdout=open(LOG_FILE, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    with open(LOCK_FILE, "w") as f:
        f.write(str(proc.pid))

    cute_echo(success(f"Started server (PID: {proc.pid})"))
    cute_echo(info(f"Logs: {LOG_FILE}"))


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


if __name__ == "__main__":
    cli()
