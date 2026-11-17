"""Chat composer attachment interaction contracts."""
from pathlib import Path
from fastapi.testclient import TestClient
from doculens.api import create_app

ROOT = Path(__file__).resolve().parents[1]

def test_chat_composer_has_attach_controls_and_pending_list(service):
    page = TestClient(create_app(service)).get("/").text
    assert 'id="chatAttachButton"' in page
    assert 'id="chatFiles"' in page
    assert 'id="chatAttachments"' in page
    assert 'accept=".pdf,.docx,.txt,.md,.markdown,.html,.htm,.csv,.json"' in page

def test_chat_composer_has_drop_and_paste_handlers(service):
    script = TestClient(create_app(service)).get("/app.js").text
    assert "chatComposerDrop" in script
    assert "chatComposerPaste" in script
    assert "uploadChatAttachments" in script
    assert "FormData()" in script

def test_existing_document_upload_api_accepts_pdf_without_chat_metadata(service):
    import fitz
    pdf = fitz.open()
    pdf.new_page().insert_text((60, 80), "Evidence from a dropped PDF file.")
    content = pdf.tobytes()
    pdf.close()
    client = TestClient(create_app(service))
    response = client.post("/api/documents/upload", files={"file":("chat.pdf", content, "application/pdf")})
    assert response.status_code == 201, response.text
    assert response.json()["pages"] == 1
