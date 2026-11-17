-- DocuLens AI PostgreSQL 18 demonstration.
-- Connect to the local database doculens_rag on 127.0.0.1:5433 as doculens_app.
-- Source content and embeddings remain in ChromaDB, not in these tables.

SELECT COUNT(*) AS documents FROM public.documents;
SELECT COUNT(*) AS chat_messages FROM public.messages;

SELECT name, kind, pages, chunks, created_at
FROM public.documents
ORDER BY created_at DESC
LIMIT 10;

SELECT session_id, role, created_at
FROM public.messages
ORDER BY created_at DESC
LIMIT 15;

SELECT kind, COUNT(*) AS document_count, SUM(chunks) AS indexed_chunks
FROM public.documents
GROUP BY kind
ORDER BY document_count DESC;
