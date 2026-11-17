"""Grounded, targeted passage-finding rather than generic unrelated generation."""
import fitz
from fastapi.testclient import TestClient
from doculens.api import create_app
from doculens import service as service_module

def make_case(service):
    pdf=fitz.open()
    pdf.new_page().insert_text((55,85),"The budget covers monthly maintenance costs and overhead.")
    pdf.new_page().insert_text((55,85),"Customer satisfaction was the highest among the service representatives.")
    pdf.new_page().insert_text((55,85),"Training was delayed due to scheduling constraints.")
    result=service.ingest_file("case.pdf",pdf.tobytes())
    pdf.close()
    return result

def test_find_content_returns_relevant_pdf_passage_and_page(service,monkeypatch):
    src=make_case(service)
    def no_model(*a,**kw):raise AssertionError("Find content must not call LLM")
    monkeypatch.setattr(service_module,"generate",no_model)
    answer=service.chat("find the passage about customer satisfaction",
                        mode="find",source_ids=[src["id"]],rerank=False)
    assert answer["provider"]=="passage-search"
    assert "Customer satisfaction was the highest" in answer["answer"]
    assert "Page 2" in answer["answer"]
    assert answer["sources"][0]["page"]==2
    assert "[1]" in answer["answer"]

def test_find_content_obeys_source_selection_and_abstains_cleanly(service):
    src=make_case(service)
    other=service.ingest_text("Meeting notes","The assigned meeting room was changed.")
    answer=service.chat("find content about customer satisfaction",mode="find",
                        source_ids=[other["id"]],rerank=False)
    assert answer["sources"]==[]
    assert "no matching passage" in answer["answer"].lower()
    assert "Customer satisfaction" not in answer["answer"]

def test_find_content_is_detected_from_regular_question_mode(service):
    src=make_case(service)
    answer=service.chat("show me the passage about customer satisfaction",
                        mode="qa",source_ids=[src["id"]],rerank=False)
    assert answer["provider"]=="passage-search"
    assert "Page 2" in answer["answer"]

def test_find_content_mode_available_over_api_and_dashboard(service):
    client=TestClient(create_app(service))
    assert '<option value="find">' in client.get("/").text
    assert '"find"' in client.get("/openapi.json").text


def test_find_content_snippet_starts_near_requested_topic(service):
    content=("General operations details are routine and largely unrelated. "
             "Customer satisfaction rose significantly after training.")
    src=service.ingest_text("long-notes",content)
    result=service.chat("find the passage about customer satisfaction",
                        mode="find",source_ids=[src["id"]],rerank=False)
    assert result["sources"]
    snippet=result["sources"][0]["excerpt"]
    assert "Customer satisfaction rose" in snippet
    assert not snippet.startswith("General operations details")
