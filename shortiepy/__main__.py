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
def create_flask_app():
    from .app import create_app

    return create_app(DB_PATH, config.port)


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
    app = create_flask_app()
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
from shortiepy.__main__ import create_flask_app, DB_PATH
from waitress import serve

app = create_flask_app()
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
