"""Application settings; API keys are never included in API responses."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def boolean(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(ROOT / "data"))).resolve())
    embedding_backend: str = field(default_factory=lambda: os.getenv("EMBEDDING_BACKEND", "sentence-transformers"))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    vector_backend: str = field(default_factory=lambda: os.getenv("VECTOR_BACKEND", "chroma"))
    metadata_backend: str = field(default_factory=lambda: os.getenv("METADATA_BACKEND", "sqlite"))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    enable_reranker: bool = field(default_factory=lambda: boolean("ENABLE_RERANKER", True))
    reranker_model: str = field(default_factory=lambda: os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"))
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini"))
    gemini_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2:3b"))
    app_token: str = field(default_factory=lambda: os.getenv("APP_ACCESS_TOKEN", ""))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "20")))
    chunk_size: int = field(default_factory=lambda: int(os.getenv("CHUNK_SIZE", "900")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "150")))
    top_k: int = field(default_factory=lambda: int(os.getenv("TOP_K", "5")))
    min_similarity: float = field(default_factory=lambda: float(os.getenv("MIN_SIMILARITY", "0.22")))
    enable_ocr: bool = field(default_factory=lambda: boolean("ENABLE_OCR", False))
    def __post_init__(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
