"""Read-only inspect of DocuLens PostgreSQL tables; credentials remain private."""
import psycopg
from doculens.settings import Settings

cfg=Settings()
if cfg.metadata_backend!="postgres" or not cfg.database_url:
    raise SystemExit("DocuLens is not configured to use PostgreSQL.")
with psycopg.connect(cfg.database_url) as conn:
    print("PostgreSQL database: doculens_rag")
    print("Tables:")
    for (name,) in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    ).fetchall():
        print(" -",name)
    docs=conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    messages=conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    sessions=conn.execute("SELECT COUNT(DISTINCT session_id) FROM messages").fetchone()[0]
    print(f"Records: {docs} documents, {messages} messages, {sessions} conversations")
    print("Sample document records:")
    for name,kind,pages,chunks in conn.execute(
        "SELECT name,kind,pages,chunks FROM documents ORDER BY created_at DESC LIMIT 6"
    ).fetchall():
        print(f" - {name} ({kind}; {pages} page(s), {chunks} chunk(s))")
print("Vector chunks are stored separately in ChromaDB.")
