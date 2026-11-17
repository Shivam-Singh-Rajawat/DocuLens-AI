"""SQLite metadata and lightweight conversation persistence."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocumentDB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL,
                    digest TEXT NOT NULL, origin TEXT, pages INTEGER NOT NULL,
                    chunks INTEGER NOT NULL, file_path TEXT, created_at TEXT NOT NULL,
                    UNIQUE(digest, kind)
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY, session_id TEXT NOT NULL, role TEXT NOT NULL,
                    content TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_messages_session ON messages(session_id, created_at);
            """)

    def connection(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        return db

    def add_document(self, entry: dict) -> dict:
        with self.connection() as db:
            db.execute("INSERT INTO documents (id,name,kind,digest,origin,pages,chunks,file_path,created_at) "
                       "VALUES (:id,:name,:kind,:digest,:origin,:pages,:chunks,:file_path,:created_at)", entry)
        return entry

    def duplicate(self, digest: str, kind: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM documents WHERE digest=? AND kind=?", (digest,kind)).fetchone()
            return dict(row) if row else None

    def documents(self) -> list[dict]:
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM documents ORDER BY created_at DESC")]

    def document(self, document_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
            return dict(row) if row else None

    def remove_document(self, document_id: str) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM documents WHERE id=?", (document_id,))

    def message(self, session_id: str, role: str, content: str):
        with self.connection() as db:
            db.execute("INSERT INTO messages VALUES (?,?,?,?,?)", (uuid4().hex, session_id, role, content, utcnow()))

    def history(self, session_id: str, limit: int = 40) -> list[dict]:
        with self.connection() as db:
            rows = db.execute("SELECT role,content,created_at FROM messages WHERE session_id=? "
                              "ORDER BY created_at DESC, rowid DESC LIMIT ?", (session_id,limit)).fetchall()
            return [dict(row) for row in reversed(rows)]

    def clear_history(self, session_id: str):
        with self.connection() as db:
            db.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
