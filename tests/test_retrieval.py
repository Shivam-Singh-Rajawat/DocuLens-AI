from doculens.retrieval import bm25_search,reciprocal_rank_fusion,HybridRetriever
from doculens.embeddings import HashEmbeddings
from doculens.vectorstore import MemoryStore


def test_bm25_finds_keyword_without_vectors():
    rows=[{"id":"first","text":"The network uses a transformer attention layer"},
          {"id":"second","text":"Database query execution plans and indexing"}]
    found=bm25_search("transformer attention",rows)
    assert found[0]["id"]=="first"
    assert found[0]["bm25_score"]>0


def test_rrf_combines_the_two_ranked_lists():
    semantic=[{"id":"a","text":"a"},{"id":"b","text":"b"}]
    bm25=[{"id":"b","text":"b"},{"id":"c","text":"c"}]
    combined=reciprocal_rank_fusion(semantic,bm25)
    assert combined[0]["id"]=="b"
    assert set(r["id"] for r in combined)=={"a","b","c"}


def test_optional_crossencoder_reorders_candidates(monkeypatch):
    from doculens import retrieval
    store=MemoryStore()
    emb=HashEmbeddings()
    rows=[{"id":"1","source_id":"a","source_name":"a","kind":"text","page":1,"start":0,"end":10,"text":"blue cats sleep"},
          {"id":"2","source_id":"b","source_name":"b","kind":"text","page":1,"start":0,"end":10,"text":"orange cats run"}]
    store.add(rows,emb.encode([c["text"] for c in rows]))
    class FakeCrossEncoder:
        def predict(self,pairs):
            return [1 if "orange" in passage else 0 for _,passage in pairs]
    monkeypatch.setattr(retrieval,"load_reranker",lambda _:FakeCrossEncoder())
    hits,warnings,reranked=HybridRetriever(emb,store,reranker_model="fake",enable_reranker=True).retrieve("cats",top_k=2)
    assert reranked and warnings==[]
    assert hits[0]["id"]=="2" and "rerank_score" in hits[0]
