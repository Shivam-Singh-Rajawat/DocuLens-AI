"""Retrieved evidence is always navigable even if the model skips citations."""
from doculens import service as service_module

def test_missing_gemini_citations_are_exposed_as_unverified_retrieval_references(service, monkeypatch):
    doc=service.ingest_text("Citation evidence","The orbital library uses a queue for job scheduling.")
    monkeypatch.setattr(service_module,"generate",lambda *args,**kwargs: ("The library uses a queue.", "gemini"))
    response=service.chat("What does the orbital library use for scheduling?",source_ids=[doc["id"]],rerank=False)
    assert response["provider"]=="gemini"
    assert response["sources"][0]["source_id"]==doc["id"]
    assert "Retrieved source excerpts" in response["answer"]
    assert "not independently verified" in response["answer"]
    assert "[1]" in response["answer"]

def test_correct_inline_citation_does_not_get_duplicate_footer(service,monkeypatch):
    doc=service.ingest_text("Citation evidence","The orbital library uses a queue for job scheduling.")
    monkeypatch.setattr(service_module,"generate",lambda *args,**kwargs: ("The library uses a queue [1].", "gemini"))
    response=service.chat("What does the orbital library use for scheduling?",source_ids=[doc["id"]],rerank=False)
    assert "Retrieved source excerpts" not in response["answer"]
    assert "[1]" in response["answer"]
