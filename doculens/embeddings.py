"""Production sentence embeddings and deterministic local test embedding alternative."""
import hashlib
import re
from functools import lru_cache
import numpy as np


class SentenceEmbeddings:
    def __init__(self, name: str):
        self.name = name

    @property
    def model(self):
        return _load_embedding_model(self.name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()


@lru_cache(maxsize=2)
def _load_embedding_model(name: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name)


class HashEmbeddings:
    """Offline deterministic demo/test backend, NOT a semantic embedding model."""
    def __init__(self, dimensions: int = 256):
        self.dimensions = dimensions

    def encode(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            vector = np.zeros(self.dimensions, dtype=np.float32)
            for word in re.findall(r"\w+", text.lower()):
                digest = hashlib.sha256(word.encode()).digest()
                slot = int.from_bytes(digest[:4], "big") % self.dimensions
                vector[slot] += 1
            length = np.linalg.norm(vector)
            if length:
                vector /= length
            results.append(vector.tolist())
        return results


@lru_cache(maxsize=2)
def load_reranker(name: str):
    from sentence_transformers import CrossEncoder
    return CrossEncoder(name)
