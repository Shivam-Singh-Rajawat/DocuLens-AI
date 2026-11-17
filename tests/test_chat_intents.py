"""Chat intent tests: exact document search, greetings, and deliberate general chat."""
import fitz
from doculens import service as service_module

def _pdf(service):
    pdf=fitz.open()
    pdf.new_page().insert_text((50,70),"The theory is useful. There is a key point: the theory.")
    pdf.new_page().insert_text((50,70),"The takeaway is that the data matters.")
    doc=service.ingest_file("example.pdf",pdf.tobytes())
    pdf.close()
    return doc

def test_exact_word_search_counts_across_pages_not_substrings(service):
    doc=_pdf(service)
    result=service.chat("find the word the in this",source_ids=[doc["id"]],rerank=False)
    assert result["provider"]=="document-search"
    assert "4 occurrences" in result["answer"]
    assert "Page 1" in result["answer"] and "Page 2" in result["answer"]
    assert {s["page"] for s in result["sources"]}=={1,2}
    assert not any("There" in line and "occurrence" in line for line in result["answer"].splitlines())

def test_exact_word_search_respects_document_selection(service):
    first=_pdf(service)
    second=service.ingest_text("Other notes","The other one.")
    r=service.chat("count the word theory",source_ids=[second["id"]],rerank=False)
    assert "0 occurrences" in r["answer"]
    assert first["id"] not in {s["source_id"] for s in r["sources"]}

def test_greeting_is_answered_without_documents(service):
    r=service.chat("hey",rerank=False)
    assert r["provider"]=="assistant"
    assert "upload" in r["answer"].lower() or "attach" in r["answer"].lower()

def test_unrestricted_chat_mode_works_without_documents(service,monkeypatch):
    calls=[]
    def fake(question,history,settings,custom_instructions):
        calls.append(question)
        return "Hi! I'm ready for general questions.", "gemini"
    monkeypatch.setattr(service_module,"generate_general",fake,raising=False)
    r=service.chat("Explain the difference between RAG and fine-tuning.",mode="chat",rerank=False)
    assert r["answer"].startswith("Hi!")
    assert r["sources"]==[] and r["provider"]=="gemini"
    assert calls == ["Explain the difference between RAG and fine-tuning."]

def test_vague_reference_to_attached_pdf_rewrites_query(service,monkeypatch):
    doc=_pdf(service)
    queries=[]
    original=service.retriever.retrieve
    def intercepted(question,**kw):
        queries.append(question)
        return original(question,**kw)
    monkeypatch.setattr(service.retriever,"retrieve",intercepted)
    service.chat("what is this pdf about?",source_ids=[doc["id"]],rerank=False)
    assert "main topic" in queries[0].lower()
