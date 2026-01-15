#!/usr/bin/env python3

import secrets
import sqlite3

import click
import pyperclip
from flask import Flask, abort, redirect, request
from tabulate import tabulate
from waitress import serve as run

DB_PATH = "shortie.db"
PORT = 9876


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
        "shortie": "your local URL shortner ( ˶˘ ³˘)♡",
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
        return f"http://localhost:{PORT}/{code}", 200
    except sqlite3.IntegrityError:
        return f"Code '{code}' exists", 409


# --- CLI Commands ---
@click.group()
def cli():
    """shortie: your local URL shortner ( ˶˘ ³˘)♡"""
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
        short_url = f"http://localhost:{PORT}/{code}"
        pyperclip.copy(short_url)
        click.echo(f"Copied to clipboard: {short_url}")
    except sqlite3.IntegrityError:
        # Very rare, but handle duplicate codes
        click.echo("Oops! Try again - code collision (unlikely!) ~ (ᵕ—ᴗ—)")
        return add(url)  # retry


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
        click.echo("(;´༎ຶД༎ຶ`) No links yet! Add one with `shortie add <URL>`")
        return

    # Prepare data
    table_data = []
    for code, url, created in rows:
        short_url = f"http://localhost:{PORT}/{code}"
        # Truncate long URLs for readability
        display_url = (url[:40] + "...") if len(url) > 40 else url
        table_data.append((short_url, display_url, created))

    headers = ["Short URL", "Original URL", "Created At"]
    output = tabulate(table_data, headers=headers, tablefmt="fancy_grid")
    click.echo(output)


@cli.command()
@click.option("--port", default=PORT, help="Port to run shortie on")
def serve(port):
    """Start the local redirect server"""
    click.echo(f"Running shortie server on `http://localhost:{port}`")
    run(app=app, host="localhost", port=port)


if __name__ == "__main__":
    cli()
