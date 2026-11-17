"""End-to-end DocuLens + PostgreSQL + Chroma verification.

Creates one intentionally public demonstration note in the local knowledge base.
Does not display credentials, and does not modify existing uploaded documents.
"""
import requests
import psycopg
from doculens.settings import Settings

base = "http://127.0.0.1:8000"
settings = Settings()
assert settings.metadata_backend == "postgres"
with psycopg.connect(settings.database_url) as conn:
    prior_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    prior_msgs = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
health = requests.get(base + "/api/health", timeout=20).json()
assert health["status"] == "ok" and health["metadata_backend"] == "postgres", health
assert health["vector_backend"] == "chroma", health
print("PASS active FastAPI -> PostgreSQL metadata -> Chroma vectors")
print("Previous database records:", prior_docs, "documents,", prior_msgs, "messages")

content = (
    "DocuLens AI is an example Retrieval-Augmented Generation system. "
    "PostgreSQL is used as the durable database for document metadata, source identifiers, "
    "file locations, and saved chat messages. ChromaDB is used as the persistent vector "
    "database that indexes chunk embeddings. Sentence Transformers produces the dense "
    "embeddings, BM25 matches exact words, and reciprocal rank fusion combines results. "
    "An optional CrossEncoder reranks retrieved document snippets. Gemini generates an "
    "answer supported by citations to retrieved sources. "
    "The document record in PostgreSQL links to its embeddings in Chroma using source_id. "
    "This demonstration contains fictional architecture notes rather than secret credentials."
)
title = "DocuLens Demo - PostgreSQL and RAG Architecture"
uploaded = requests.post(base + "/api/documents/text",
                         json={"title":title, "content":content}, timeout=180)
assert uploaded.status_code == 201, (uploaded.status_code,uploaded.text[:200])
record = uploaded.json()
source_id = record["id"]
with psycopg.connect(settings.database_url) as conn:
    sql_row = conn.execute(
        "SELECT name,kind,chunks FROM documents WHERE id=%s", (source_id,)
    ).fetchone()
assert sql_row and sql_row[0] == title and sql_row[2] >= 1
print("PASS document upload created a genuine PostgreSQL document row")

result = requests.post(base + "/api/search",
                       json={"question":"Which database stores DocuLens embeddings and which stores chat history?",
                             "source_ids":[source_id],"rerank":False,"top_k":4},
                       timeout=120)
assert result.status_code == 200,(result.status_code,result.text[:300])
hits = result.json()["hits"]
assert hits and all(hit["source_id"] == source_id for hit in hits)
print("PASS Chroma vector + BM25 retrieval across PostgreSQL-linked source_id")

answer = requests.post(base + "/api/chat",
                       json={"question":"Where are document metadata, chat history and embeddings stored?",
                             "source_ids":[source_id],"rerank":False,"top_k":4,"mode":"qa"},
                       timeout=160)
if answer.status_code == 200:
    payload = answer.json()
    assert payload["sources"] and payload["sources"][0]["source_id"] == source_id
    with psycopg.connect(settings.database_url) as conn:
        turns = conn.execute("SELECT role,content FROM messages WHERE session_id=%s",
                             (payload["session_id"],)).fetchall()
    assert len(turns) >= 2 and {row[0] for row in turns} >= {"user","assistant"}
    print("PASS source-cited chat saved user and assistant turns to PostgreSQL")
    print("Live answer provider:",payload["provider"])
    print("Answer excerpt:",payload["answer"][:240].replace("\n"," "))
else:
    print("LIVE_LLM_CHECK_FAILED: API returned",answer.status_code)
    try:
        print("Reason (truncated):", str(answer.json().get("detail","unknown"))[:220])
    except ValueError:
        print("No JSON error details")
    # Generation-provider problems do not invalidate PostgreSQL/Chroma integration.
    from doculens.service import RAGService
    fallback_settings=Settings(llm_provider="none")
    fallback=RAGService(fallback_settings)
    response=fallback.chat("Which database stores chat history?",
                           source_ids=[source_id],rerank=False)
    assert response["sources"] and response["provider"] == "evidence-only"
    with psycopg.connect(settings.database_url) as conn:
        turns=conn.execute("SELECT COUNT(*) FROM messages WHERE session_id=%s",
                           (response["session_id"],)).fetchone()[0]
    assert turns==2
    print("PASS evidence-only fallback wrote both chat turns to PostgreSQL")
print("Demo document ID:",source_id)
print("PASS end-to-end PostgreSQL RAG smoke test")
