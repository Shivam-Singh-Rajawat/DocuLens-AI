"""Higher-level document questions must not accidentally retrieve unrelated snippets."""
import fitz
from doculens import service as service_module


def pdf_source(service, name="case.pdf", text="Machine learning helps classify customer requests."):
    document = fitz.open()
    document.new_page().insert_text((55, 90), text)
    result = service.ingest_file(name, document.tobytes())
    document.close()
    return result


def test_informal_ppt_inventory_does_not_make_up_a_presentation(service, monkeypatch):
    pdf = pdf_source(service)
    notes = service.ingest_text("RAG notes", "Retrieval augmented generation combines evidence and AI.")
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Library inventory should not request semantic generation")
    monkeypatch.setattr(service_module, "generate", fail_if_called)
    result = service.chat(
        "what ppt in in the our source and is the common in it",
        source_ids=[pdf["id"], notes["id"]], rerank=False,
    )
    assert result["provider"] == "library"
    assert "no powerpoint" in result["answer"].lower()
    assert "case.pdf" in result["answer"]
    assert "rag notes" in result["answer"].lower()
    assert result["sources"] == []


def test_list_pdfs_only_and_respect_selected_sources(service):
    case = pdf_source(service)
    other = service.ingest_text("Some notes", "This is unrelated.")
    result = service.chat("Which PDFs are in my sources?", source_ids=[case["id"], other["id"]], rerank=False)
    assert "case.pdf" in result["answer"]
    assert "Some notes" not in result["answer"]
    only_text = service.chat("Which PDFs are in my sources?", source_ids=[other["id"]], rerank=False)
    assert "no pdf" in only_text["answer"].lower()


def test_list_all_uploaded_sources(service):
    pdf_source(service)
    service.ingest_text("Alpha notes", "Textual content.")
    result=service.chat("list my uploaded files",rerank=False)
    assert result["provider"]=="library"
    assert "case.pdf" in result["answer"]
    assert "Alpha notes" in result["answer"]


def test_ask_commonality_uses_evidence_from_each_selected_document(service,monkeypatch):
    a=service.ingest_text("Dense retrieval", "Embedding models map sentences into vectors for retrieval.")
    b=service.ingest_text("Hybrid search", "Hybrid RAG combines BM25 ranking and embedding similarity.")
    c=service.ingest_text("RAG overview", "RAG retrieves supporting sources before generating responses.")
    captured=[]
    def fake_generate(question,hits,history,**kwargs):
        captured.extend(hits)
        return "These documents all discuss retrieval systems [1] [2] [3].", "gemini"
    monkeypatch.setattr(service_module,"generate",fake_generate)
    result=service.chat("what is common across these documents?",source_ids=[a["id"],b["id"],c["id"]],rerank=False)
    assert set(hit["source_id"] for hit in captured)=={a["id"],b["id"],c["id"]}
    assert len(result["sources"])==3
    assert all(s["selection_method"] == "document-overview" for s in result["sources"])


def test_model_abstention_not_followed_by_random_citation_footer(service,monkeypatch):
    service.ingest_text("Bayes notes", "Bayesian reasoning updates prior probabilities with observations.")
    monkeypatch.setattr(service_module,"generate",
                        lambda *args,**kwargs: ("I couldn't find that information in the selected sources.", "gemini"))
    result=service.chat("What is Bayesian reasoning?",rerank=False)
    assert "Retrieved source excerpts" not in result["answer"]
    assert not result["sources"]
