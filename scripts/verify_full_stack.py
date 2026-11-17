"""Verify the active production-mode server without storing API secrets."""
import requests
import fitz

BASE = "http://127.0.0.1:8000"
created_ids = []

def check(response, expected=200):
    assert response.status_code == expected, f"{response.status_code}: {response.text[:600]}"
    return response.json()

try:
    health = check(requests.get(BASE + "/api/health", timeout=15))
    assert health["embedding_backend"] == "sentence-transformers", health
    assert health["vector_backend"] == "chroma", health
    page = requests.get(BASE + "/", timeout=15)
    assert page.status_code == 200 and "DocuLens AI" in page.text
    assert requests.get(BASE + "/app.js", timeout=15).status_code == 200
    print("PASS production server and dashboard")

    pdf = fitz.open()
    pdf.new_page().insert_text((50, 90), "The cassava study uses Ridge regression to estimate beta carotene.")
    pdf.new_page().insert_text((50, 90), "The cassava study limitation is only ninety-three samples, creating overfitting risk.")
    raw_pdf = pdf.tobytes()
    pdf.close()
    upload = check(requests.post(BASE + "/api/documents/upload", data=raw_pdf,
        headers={"X-Filename": "doculens-verified-two-pages.pdf",
                 "Content-Type": "application/pdf"}, timeout=180), 201)
    pdf_id = upload["id"]
    created_ids.append(pdf_id)
    assert upload["pages"] == 2, upload
    print("PASS two-page PDF ingestion with real embeddings and Chroma")

    text = check(requests.post(BASE + "/api/documents/text", json={
        "title": "DocuLens live text validation",
        "content": "Knowledge marker KAPPA739: hybrid retrieval combines BM25 and dense embeddings."
    }, timeout=180), 201)
    created_ids.append(text["id"])
    print("PASS pasted text ingestion")

    results = check(requests.post(BASE + "/api/search", json={
        "question": "What is the cassava study limitation?",
        "source_ids": [pdf_id], "top_k": 5, "rerank": False
    }, timeout=180))
    assert any(hit.get("page") == 2 for hit in results["hits"]), results
    assert all(hit["source_id"] == pdf_id for hit in results["hits"]), results
    print("PASS page-specific document-filtered retrieval")

    answer = check(requests.post(BASE + "/api/chat", json={
        "question": "Describe the cassava study limitation.",
        "source_ids": [pdf_id], "mode": "summarize", "rerank": False
    }, timeout=180))
    assert answer["sources"] and any(s["page"] == 2 for s in answer["sources"]), answer
    assert answer["provider"] == "evidence-only", answer
    print("PASS cited chat and no-key evidence-only fallback")

    prompts = check(requests.get(BASE + "/api/prompts", timeout=15))
    assert all(mode in prompts for mode in ["qa", "compare", "summarize", "extract", "study", "quiz"])
    original = requests.get(BASE + "/api/documents/" + pdf_id + "/file", timeout=15)
    assert original.status_code == 200 and original.content.startswith(b"%PDF")
    print("PASS prompt modes and original PDF download")
finally:
    for source_id in created_ids:
        response = requests.delete(BASE + "/api/documents/" + source_id, timeout=30)
        print("CLEANUP", source_id[:8], response.status_code)
