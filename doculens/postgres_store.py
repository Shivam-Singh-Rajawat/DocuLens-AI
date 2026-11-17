"""PostgreSQL document and conversation persistence.

Chroma still owns vector chunks. PostgreSQL only stores document metadata and
chat messages. The interface matches DocumentDB for seamless backend selection.
"""
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from doculens.database import utcnow


class PostgresDocumentDB:
    def __init__(self, database_url: str):
        if not database_url:
            raise ValueError("DATABASE_URL is required when METADATA_BACKEND=postgres")
        self.database_url = database_url
        with self.connection() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL, kind TEXT NOT NULL,
                    digest TEXT NOT NULL, origin TEXT,
                    pages INTEGER NOT NULL, chunks INTEGER NOT NULL,
                    file_path TEXT, created_at TEXT NOT NULL,
                    UNIQUE(digest, kind)
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            db.execute("""
                CREATE INDEX IF NOT EXISTS ix_messages_session
                ON messages (session_id, created_at, id)
            """)

    def connection(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def add_document(self, entry: dict) -> dict:
        with self.connection() as db:
            db.execute("""
                INSERT INTO documents
                    (id,name,kind,digest,origin,pages,chunks,file_path,created_at)
                VALUES
                    (%(id)s,%(name)s,%(kind)s,%(digest)s,%(origin)s,
                     %(pages)s,%(chunks)s,%(file_path)s,%(created_at)s)
                ON CONFLICT (id) DO NOTHING
            """, entry)
        return entry

    def duplicate(self, digest: str, kind: str) -> dict | None:
        with self.connection() as db:
            return db.execute(
                "SELECT * FROM documents WHERE digest=%s AND kind=%s",
                (digest,kind)
            ).fetchone()

    def documents(self) -> list[dict]:
        with self.connection() as db:
            return db.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()

    def document(self, document_id: str) -> dict | None:
        with self.connection() as db:
            return db.execute(
                "SELECT * FROM documents WHERE id=%s", (document_id,)
            ).fetchone()

    def remove_document(self, document_id: str) -> None:
        with self.connection() as db:
            db.execute("DELETE FROM documents WHERE id=%s", (document_id,))

    def message(self, session_id: str, role: str, content: str):
        with self.connection() as db:
            db.execute(
                "INSERT INTO messages (id,session_id,role,content,created_at) VALUES (%s,%s,%s,%s,%s)",
                (uuid4().hex,session_id,role,content,utcnow())
            )

    def history(self, session_id: str, limit: int = 40) -> list[dict]:
        with self.connection() as db:
            rows=db.execute("""
                SELECT role,content,created_at FROM messages WHERE session_id=%s
                ORDER BY created_at DESC,id DESC LIMIT %s
            """,(session_id,limit)).fetchall()
            return list(reversed(rows))

    def clear_history(self, session_id: str):
        with self.connection() as db:
            db.execute("DELETE FROM messages WHERE session_id=%s",(session_id,))

    def import_message(self, row: dict):
        """Idempotently migrate messages, keeping their original IDs/timestamps."""
        with self.connection() as db:
            db.execute("""
                INSERT INTO messages (id,session_id,role,content,created_at)
                VALUES (%(id)s,%(session_id)s,%(role)s,%(content)s,%(created_at)s)
                ON CONFLICT (id) DO NOTHING
            """,row)
