"""PostgreSQL document registry must be a drop-in replacement for SQLite."""
from doculens.settings import Settings
from doculens.embeddings import HashEmbeddings
from doculens.vectorstore import MemoryStore
from doculens.service import RAGService

def test_settings_allow_separate_postgres_metadata_backend(tmp_path):
    settings=Settings(data_dir=tmp_path, embedding_backend="hash",
                      vector_backend="memory", llm_provider="none",
                      metadata_backend="postgres",
                      database_url="postgresql://demo_user@127.0.0.1:5433/doculens_rag")
    assert settings.metadata_backend=="postgres"
    assert settings.database_url.startswith("postgresql://")

def test_service_selects_postgres_db_without_changing_vector_store(tmp_path, monkeypatch):
    from doculens import service
    calls=[]
    monkeypatch.setattr(service,"PostgresDocumentDB",lambda url: calls.append(url) or "postgres-marker")
    settings=Settings(data_dir=tmp_path, embedding_backend="hash",vector_backend="memory",
                      llm_provider="none",metadata_backend="postgres",
                      database_url="postgresql://demo_user@127.0.0.1:5433/doculens_rag")
    rag=RAGService(settings,embedder=HashEmbeddings(),store=MemoryStore())
    assert rag.db=="postgres-marker"
    assert calls==[settings.database_url]
    assert rag.store.count()==0
