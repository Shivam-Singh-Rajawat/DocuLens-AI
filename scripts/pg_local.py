"""Install an isolated PostgreSQL 18 cluster for DocuLens on Windows.

Usage: python -m scripts.pg_local setup|start|status
No passwords are printed. The existing system PostgreSQL service is untouched.
"""
import json
import os
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CLUSTER = DATA / "postgres18"
PRIVATE = DATA / "private"
SECRETS = PRIVATE / "postgres-admin.json"
PG = Path(r"C:\Program Files\PostgreSQL\18\bin")
PORT = 5433
ADMIN = "doculens_admin"
USER = "doculens_app"
DATABASE = "doculens_rag"


def executable(name):
    path = PG / name
    if not path.exists():
        raise RuntimeError("PostgreSQL 18 binaries were not found on this computer")
    return str(path)


def run(*arguments, env=None):
    proc = subprocess.run(arguments, text=True, capture_output=True, env=env, timeout=90)
    if proc.returncode:
        raise RuntimeError(f"PostgreSQL command failed: {Path(arguments[0]).name}. "
                           + (proc.stderr or proc.stdout)[-1000:])
    return proc.stdout


def secrets_store():
    if SECRETS.exists():
        return json.loads(SECRETS.read_text(encoding="utf-8"))
    PRIVATE.mkdir(parents=True, exist_ok=True)
    record = {"admin_password": secrets.token_urlsafe(30),
              "app_password": secrets.token_urlsafe(30)}
    SECRETS.write_text(json.dumps(record), encoding="utf-8")
    try:
        SECRETS.chmod(0o600)
    except OSError:
        pass
    return record


def init_cluster():
    if (CLUSTER / "PG_VERSION").exists():
        return
    if CLUSTER.exists() and any(CLUSTER.iterdir()):
        raise RuntimeError("PostgreSQL cluster directory exists but isn't initialized; "
                           "inspect it manually before proceeding.")
    creds = secrets_store()
    CLUSTER.parent.mkdir(parents=True, exist_ok=True)
    password_file = PRIVATE / "initdb-password.tmp"
    password_file.write_text(creds["admin_password"] + "\n", encoding="utf-8")
    try:
        result = run(executable("initdb.exe"), "-D", str(CLUSTER),
                     "-U", ADMIN, "-E", "UTF8",
                     "--auth-host=scram-sha-256",
                     "--auth-local=scram-sha-256",
                     f"--pwfile={password_file}")
    finally:
        password_file.unlink(missing_ok=True)
    print("Created isolated PostgreSQL 18 cluster with password authentication.")


def is_listening():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.6):
            return True
    except OSError:
        return False


def start():
    if not (CLUSTER / "PG_VERSION").exists():
        raise RuntimeError("Cluster not initialized. Run: python -m scripts.pg_local setup")
    creds = secrets_store()
    if not is_listening():
        logs = DATA / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        # The Windows postgres child inherits stdout handles; avoid PIPE deadlocks.
        proc = subprocess.run(
            [executable("pg_ctl.exe"), "-D", str(CLUSTER), "-l",
             str(logs / "postgres18.log"), "-o",
             f"-h 127.0.0.1 -p {PORT}", "-w", "-t", "40", "start"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
        if proc.returncode:
            raise RuntimeError("PostgreSQL failed to start; see data/logs/postgres18.log")
    # Connection check prevents mistakenly trusting another service bound to port 5433.
    with psycopg.connect(host="127.0.0.1", port=PORT, dbname="postgres",
                         user=ADMIN, password=creds["admin_password"],
                         connect_timeout=5) as conn:
        version = conn.execute("SHOW server_version").fetchone()[0]
    print(f"PostgreSQL {version} available on 127.0.0.1:{PORT}.")


def create_database():
    creds = secrets_store()
    with psycopg.connect(host="127.0.0.1", port=PORT, dbname="postgres",
                         user=ADMIN, password=creds["admin_password"],
                         connect_timeout=5, autocommit=True) as conn:
        role = conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (USER,)).fetchone()
        if not role:
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(USER), sql.Literal(creds["app_password"])))
        database = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (DATABASE,)
        ).fetchone()
        if not database:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(DATABASE), sql.Identifier(USER)))
    print("Database doculens_rag and restricted login doculens_app are available.")


def app_url():
    password = quote(secrets_store()["app_password"], safe="")
    return f"postgresql://{USER}:{password}@127.0.0.1:{PORT}/{DATABASE}?connect_timeout=5"


def migrate():
    from doculens.postgres_store import PostgresDocumentDB
    dest = PostgresDocumentDB(app_url())
    sqlite_path = DATA / "metadata.sqlite3"
    if not sqlite_path.exists():
        print("No legacy SQLite metadata to migrate.")
        return
    # Preserve SQLite backup, uploads and Chroma. Never delete or rewrite the original.
    backup_path = DATA / "metadata.before-postgres.sqlite3"
    if not backup_path.exists():
        shutil.copy2(sqlite_path, backup_path)
    with sqlite3.connect(sqlite_path) as source:
        source.row_factory = sqlite3.Row
        documents = [dict(row) for row in source.execute(
            "SELECT * FROM documents ORDER BY created_at")]
        messages = [dict(row) for row in source.execute(
            "SELECT id,session_id,role,content,created_at FROM messages ORDER BY rowid")]
    for document in documents:
        dest.add_document(document)
    for message in messages:
        dest.import_message(message)
    with dest.connection() as conn:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()["count"]
        message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()["count"]
    if doc_count < len(documents) or message_count < len(messages):
        raise RuntimeError("Migration counts are smaller than the original SQLite database.")
    print(f"Copied {len(documents)} original document rows and {len(messages)} messages; "
          f"PostgreSQL now has {doc_count} documents and {message_count} messages.")


def configure_env():
    path = ROOT / ".env"
    if not path.exists():
        raise RuntimeError("DocuLens .env is missing; setup will not overwrite other settings.")
    content = path.read_text(encoding="utf-8-sig")
    lines = [line for line in content.splitlines()
             if not line.startswith("METADATA_BACKEND=")
             and not line.startswith("DATABASE_URL=")]
    lines += ["METADATA_BACKEND=postgres", "DATABASE_URL=" + app_url()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Updated only METADATA_BACKEND and DATABASE_URL in the local .env file.")


def setup():
    init_cluster()
    start()
    create_database()
    migrate()
    configure_env()
    print("PostgreSQL setup, metadata migration, and environment switch completed.")


def status():
    if not (CLUSTER / "PG_VERSION").exists():
        print("DocuLens PostgreSQL cluster not yet initialized.")
        return 1
    try:
        start()
        with psycopg.connect(app_url()) as conn:
            documents = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        print(f"Database: {DATABASE}; documents: {documents}; messages: {messages}")
        return 0
    except (psycopg.Error,RuntimeError) as e:
        print(f"Database unavailable: {type(e).__name__}")
        return 1


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv)>1 else "status"
    if action=="setup":
        setup()
    elif action=="start":
        start()
    elif action=="status":
        raise SystemExit(status())
    else:
        raise SystemExit("Use: python -m scripts.pg_local setup|start|status")
