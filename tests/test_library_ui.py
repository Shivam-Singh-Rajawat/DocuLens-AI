"""Source selection and grounded question shortcuts should be visible."""
from fastapi.testclient import TestClient
from doculens.api import create_app

def test_chat_has_library_shortcuts(service):
    html=TestClient(create_app(service)).get("/").text
    assert 'data-question="Which PDFs are in my sources?"' in html
    assert 'data-question="What do these documents have in common?"' in html
    assert 'id="selectionSummary"' in html

def test_client_updates_selection_summary(service):
    app=TestClient(create_app(service)).get("/app.js").text
    assert "updateSelectionSummary" in app
    assert "selected.size" in app
