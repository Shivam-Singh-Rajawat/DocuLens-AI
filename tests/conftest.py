import pytest
from doculens.service import RAGService
from doculens.settings import Settings


@pytest.fixture
def service(tmp_path):
    settings = Settings(data_dir=tmp_path, embedding_backend="hash", vector_backend="sqlite",
                        metadata_backend="sqlite", database_url="",
                        llm_provider="none", enable_reranker=False,
                        chunk_size=160, chunk_overlap=30, min_similarity=0.15)
    return RAGService(settings)
