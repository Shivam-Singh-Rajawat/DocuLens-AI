import fitz
import pytest
from doculens.service import RAGService


def seed(service):
    first=service.ingest_text("Transformer paper", "The transformer attention mechanism processes sequences using self attention. Accuracy is 91 percent.")
    second=service.ingest_text("Vector search notes", "Dense embeddings support semantic document retrieval. BM25 provides lexical search. Fusion combines the results.")
    return first,second


def test_text_ingestion_dedup_and_persistence(service):
    first,second=seed(service)
    assert len(service.list_documents())==2
    assert service.ingest_text("Different title", "The transformer attention mechanism processes sequences using self attention. Accuracy is 91 percent.")["duplicate"]
    assert len(service.list_documents())==2
    again=RAGService(service.settings)
    assert again.store.count()==service.store.count()
    assert again.db.document(first["id"])["name"]=="Transformer paper"
    assert again.delete_document(second["id"])
    assert not again.db.document(second["id"])
    assert not again.delete_document(second["id"])


def test_search_filters_and_bm25(service):
    a,b=seed(service)
    results=service.search("What does BM25 provide?",rerank=False)
    assert results["hits"]
    assert results["hits"][0]["source_id"]==b["id"]
    selected=service.search("attention",source_ids=[a["id"]],rerank=False)
    assert all(hit["source_id"]==a["id"] for hit in selected["hits"])
    with pytest.raises(ValueError,match="Unknown"):
        service.search("attention",source_ids=["bad-id"])


def test_chat_cites_real_sources_and_remembers_session(service):
    a,_=seed(service)
    answer=service.chat("What is the transformer accuracy?",source_ids=[a["id"]],rerank=False)
    assert "91" in answer["answer"]
    assert answer["sources"][0]["source_id"]==a["id"]
    assert "[1]" in answer["answer"]
    session=service.db.history(answer["session_id"])
    assert [row["role"] for row in session]==["user","assistant"]
    follow=service.chat("Why is that important?",session_id=answer["session_id"],rerank=False)
    assert follow["session_id"]==answer["session_id"]
    assert len(service.db.history(answer["session_id"]))==4


def test_chat_abstains_on_empty_collection(service):
    answer=service.chat("What is the conclusion?",rerank=False)
    assert "couldn't find" in answer["answer"]
    assert answer["sources"]==[]


def test_evaluation_calculates_retrieval_metrics(service):
    _,b=seed(service)
    result=service.evaluate([{"question":"What is BM25 used for?", "expected_source_ids":[b["id"]]}],rerank=False)
    assert result["recall_at_k"]==1
    assert result["mrr"]>0


def test_pdf_document_page_reference(service):
    pdf=fitz.open()
    pdf.new_page().insert_text((60,80),"Birds have hollow bones")
    pdf.new_page().insert_text((60,80),"Marine mammals breathe air with lungs")
    item=service.ingest_file("facts.pdf",pdf.tobytes())
    pdf.close()
    result=service.chat("How do marine mammals breathe?",source_ids=[item["id"]],rerank=False)
    assert any(s["page"]==2 for s in result["sources"])
