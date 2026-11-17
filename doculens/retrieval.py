"""BM25 + vector retrieval, reciprocal-rank fusion, optional CrossEncoder reranking."""
import re
import math
from collections import Counter
from doculens.embeddings import load_reranker


STOPWORDS = {"the", "a", "an", "is", "are", "was", "were", "what", "which", "why", "how",
             "when", "where", "who", "do", "does", "did", "can", "could", "of", "to", "for",
             "and", "or", "in", "on", "by", "with", "it", "this", "that", "my", "your",
             "their", "from", "about", "please", "me", "as", "at", "be", "i", "you"}

def tokenize(text: str) -> list[str]:
    return [word for word in re.findall(r"\w+", text.casefold()) if word not in STOPWORDS]


def bm25_search(query: str, corpus: list[dict], n: int = 20) -> list[dict]:
    if not corpus:
        return []
    terms = tokenize(query)
    if not terms:
        return []
    tokenized = [tokenize(chunk["text"]) for chunk in corpus]
    n_docs = len(tokenized)
    avg_length = sum(map(len, tokenized)) / n_docs or 1
    frequencies = Counter(term for doc in tokenized for term in set(doc))
    query_terms = set(terms)
    scores = []
    for words in tokenized:
        counts = Counter(words)
        score = 0.0
        for term in query_terms:
            freq = counts.get(term, 0)
            if not freq:
                continue
            idf = math.log(1 + (n_docs - frequencies[term] + 0.5) / (frequencies[term] + 0.5))
            score += idf * (freq * 2.5) / (freq + 1.5 * (0.25 + 0.75 * len(words) / avg_length))
        scores.append(score)
    rows = []
    for chunk, words, raw in zip(corpus, tokenized, scores):
        matches = len(set(words) & query_terms)
        if matches:
            # Stable lexical overlap improves short/single-document behavior.
            rows.append({**chunk, "bm25_score": float(raw), "lexical_overlap": matches})
    return sorted(rows, key=lambda hit: (hit["bm25_score"],hit["lexical_overlap"]), reverse=True)[:n]


def reciprocal_rank_fusion(vector_hits: list[dict], keyword_hits: list[dict], *, k: int = 60) -> list[dict]:
    merged = {}
    for group, source in [(vector_hits,"vector"), (keyword_hits,"bm25")]:
        for rank, chunk in enumerate(group, 1):
            key = chunk["id"]
            if key not in merged:
                merged[key] = {**chunk, "rrf_score":0.0,
                               "semantic_score":chunk.get("semantic_score",0.0),
                               "bm25_score":chunk.get("bm25_score",0.0)}
            merged[key].update({a:b for a,b in chunk.items() if a in {"bm25_score","semantic_score","lexical_overlap"}})
            merged[key]["rrf_score"] += 1 / (k + rank)
    return sorted(merged.values(), key=lambda row:row["rrf_score"], reverse=True)


class HybridRetriever:
    def __init__(self, embedder, store, *, reranker_model: str, enable_reranker: bool = True):
        self.embedder = embedder
        self.store = store
        self.reranker_model = reranker_model
        self.enable_reranker = enable_reranker

    def retrieve(self, question: str, *, source_ids: list[str] | None = None,
                 top_k: int = 5, rerank: bool = True) -> tuple[list[dict], list[str], bool]:
        if not question.strip():
            raise ValueError("Question cannot be empty.")
        top_k = min(max(int(top_k),1),20)
        limit = max(top_k * 4, 20)
        vector = self.embedder.encode([question])[0]
        vector_hits = self.store.search(vector, limit, source_ids)
        keyword_hits = bm25_search(question, self.store.all_chunks(source_ids), limit)
        candidates = reciprocal_rank_fusion(vector_hits, keyword_hits)[:limit]
        warnings = []
        reranked = False
        if rerank and self.enable_reranker and candidates:
            try:
                model = load_reranker(self.reranker_model)
                scores = model.predict([(question, c["text"]) for c in candidates])
                for c, score in zip(candidates, scores):
                    c["rerank_score"] = float(score)
                candidates.sort(key=lambda row:row["rerank_score"], reverse=True)
                reranked = True
            except Exception:
                warnings.append("CrossEncoder unavailable; used hybrid RRF ranking instead.")
        elif rerank and not self.enable_reranker:
            warnings.append("CrossEncoder disabled in server settings; used hybrid RRF ranking.")
        return candidates[:top_k], warnings, reranked
