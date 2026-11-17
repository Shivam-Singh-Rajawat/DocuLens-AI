from fastapi.testclient import TestClient
from doculens.api import create_app

def test_chat_composer_has_general_conversation_mode(service):
    page=TestClient(create_app(service)).get("/").text
    assert '<option value="chat">' in page

def test_chat_composer_can_bypass_document_selection_in_general_mode(service):
    script=TestClient(create_app(service)).get("/app.js").text
    assert "const isGeneral" in script
    assert "sourceIds=isGeneral?[]" in script
