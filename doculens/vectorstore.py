"""Vector and document chunk stores. Chroma is persistent; memory backend for tests."""

def source_filter(source_ids: list[str] | None):
    if not source_ids:
        return None
    if len(source_ids) == 1:
        return {"source_id": source_ids[0]}
    return {"source_id": {"$in": source_ids}}


class ChromaStore:
    def __init__(self, directory):
        import chromadb
        self.client = chromadb.PersistentClient(path=str(directory))
        self.collection = self.client.get_or_create_collection(
            "doculens_chunks", embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}})

    def add(self, chunks: list[dict], embeddings: list[list[float]]) -> None:
        for start in range(0, len(chunks), 100):
            rows, vectors = chunks[start:start+100], embeddings[start:start+100]
            self.collection.upsert(ids=[c["id"] for c in rows],
                                   documents=[c["text"] for c in rows],
                                   embeddings=vectors,
                                   metadatas=[{k:c[k] for k in ("source_id", "source_name", "page", "kind", "start", "end")}
                                              for c in rows])

    def search(self, embedding: list[float], n: int, source_ids: list[str] | None = None) -> list[dict]:
        if not self.collection.count():
            return []
        kwargs = {"query_embeddings": [embedding], "n_results": min(n, self.collection.count()),
                  "include": ["documents", "metadatas", "distances"]}
        if source_filter(source_ids):
            kwargs["where"] = source_filter(source_ids)
        result = self.collection.query(**kwargs)
        return [{"id": id_, "text": text, **metadata, "semantic_score": 1.0 - float(dist)}
                for id_,text,metadata,dist in zip(result["ids"][0], result["documents"][0],
                                                  result["metadatas"][0], result["distances"][0])]

    def all_chunks(self, source_ids: list[str] | None = None) -> list[dict]:
        kwargs = {"include": ["documents", "metadatas"]}
        if source_filter(source_ids):
            kwargs["where"] = source_filter(source_ids)
        result = self.collection.get(**kwargs)
        return [{"id": id_, "text": text, **metadata} for id_, text, metadata
                in zip(result["ids"], result["documents"], result["metadatas"])]

    def delete(self, source_id: str):
        self.collection.delete(where={"source_id": source_id})

    def count(self) -> int:
        return self.collection.count()


class MemoryStore:
    """Ephemeral backend used by offline tests and smoke checks."""
    def __init__(self):
        self.rows = {}

    def add(self, chunks, embeddings):
        for c,e in zip(chunks, embeddings):
            self.rows[c["id"]] = (c.copy(), e)

    def search(self, embedding, n, source_ids=None):
        import numpy as np
        q = np.array(embedding)
        rows = []
        for c,e in self.rows.values():
            if source_ids and c["source_id"] not in source_ids:
                continue
            vector = np.array(e)
            denom = float(np.linalg.norm(q) * np.linalg.norm(vector))
            score = float(np.dot(q, vector) / denom) if denom else 0.0
            rows.append({**c,"semantic_score":score})
        return sorted(rows, key=lambda r:r["semantic_score"], reverse=True)[:n]

    def all_chunks(self, source_ids=None):
        return [c.copy() for c,_ in self.rows.values() if not source_ids or c["source_id"] in source_ids]

    def delete(self, source_id):
        self.rows = {key:value for key,value in self.rows.items() if value[0]["source_id"] != source_id}

    def count(self):
        return len(self.rows)


class SQLiteVectorStore:
    """Zero-extra-dependency persistent cosine store for small/local collections.

    Unlike Chroma, search computes cosine similarities linearly; for large libraries use Chroma.
    """
    def __init__(self, directory):
        import sqlite3
        from pathlib import Path
        self.path = Path(directory) / "vectors.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("CREATE TABLE IF NOT EXISTS chunks (id TEXT PRIMARY KEY, source_id TEXT NOT NULL, "
                       "payload TEXT NOT NULL, embedding TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS ix_chunks_source ON chunks(source_id)")

    def connection(self):
        import sqlite3
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        return db

    def add(self, chunks, embeddings):
        import json
        if len(chunks) != len(embeddings):
            raise ValueError("Each chunk needs one embedding.")
        with self.connection() as db:
            db.executemany("INSERT OR REPLACE INTO chunks (id,source_id,payload,embedding) VALUES (?,?,?,?)",
                           [(c["id"],c["source_id"],json.dumps(c),json.dumps(e)) for c,e in zip(chunks,embeddings)])

    def _rows(self, source_ids):
        import json
        with self.connection() as db:
            if source_ids:
                placeholders = ",".join("?" for _ in source_ids)
                rows = db.execute(f"SELECT payload,embedding FROM chunks WHERE source_id IN ({placeholders})", source_ids)
            else:
                rows = db.execute("SELECT payload,embedding FROM chunks")
            return [(json.loads(r["payload"]),json.loads(r["embedding"])) for r in rows]

    def search(self, embedding, n, source_ids=None):
        import numpy as np
        query = np.asarray(embedding)
        query_norm = np.linalg.norm(query)
        hits = []
        for chunk,vector in self._rows(source_ids):
            vec = np.asarray(vector)
            if len(vec) != len(query):
                raise ValueError("Stored embedding dimensions differ; clear data after changing the embedding model.")
            denom = float(query_norm * np.linalg.norm(vec))
            score = float(np.dot(query,vec) / denom) if denom else 0.0
            hits.append({**chunk,"semantic_score":score})
        return sorted(hits, key=lambda c:c["semantic_score"], reverse=True)[:n]

    def all_chunks(self, source_ids=None):
        return [chunk for chunk,_ in self._rows(source_ids)]

    def delete(self, source_id):
        with self.connection() as db:
            db.execute("DELETE FROM chunks WHERE source_id=?",(source_id,))

    def count(self):
        with self.connection() as db:
            return db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
