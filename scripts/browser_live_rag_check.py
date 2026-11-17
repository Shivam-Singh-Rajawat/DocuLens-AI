"""Real browser PDF -> Chroma -> Gemini -> PostgreSQL integration check.

Uses a unique synthetic PDF; deletes only the test source and test session.
Does not print or access credentials explicitly. Run from project root.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import uuid
import fitz
import psycopg
import requests
from playwright.sync_api import sync_playwright
from doculens.settings import Settings

BASE = "http://127.0.0.1:8000"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
TOKEN = "LIMESTONE" + uuid.uuid4().hex[:9].upper()
filename = "doculens-live-qa-" + uuid.uuid4().hex[:8] + ".pdf"
q = f"What is the verification codename in the attached PDF? Cite the page."
settings = Settings()
session_id = None
test_doc_id = None
before = {row["id"] for row in requests.get(BASE + "/api/documents", timeout=20).json()}

try:
    with TemporaryDirectory(prefix="doculens_live_rag_") as tmp:
        pdf = fitz.open()
        p1 = pdf.new_page()
        p1.insert_text((50, 85), "DocuLens verification research notes.")
        p1.insert_text((50, 115), "This local test uses a research evidence pipeline.")
        p2 = pdf.new_page()
        p2.insert_text((50, 85), f"The verification codename is {TOKEN}.")
        p2.insert_text((50, 115), "PostgreSQL retains document metadata and chat turns.")
        p2.insert_text((50, 145), "ChromaDB retrieves relevant passage embeddings.")
        path = Path(tmp) / filename
        path.write_bytes(pdf.tobytes())
        pdf.close()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=CHROME)
            page = browser.new_page()
            errors = []
            page.on("pageerror",lambda e: errors.append(str(e)))
            page.goto(BASE, wait_until="networkidle", timeout=30000)
            assert page.locator("#chatAttachButton").is_visible()
            page.locator("#newChat").click()
            page.locator("#chatFiles").set_input_files(str(path))
            assert filename in page.locator("#chatAttachments").inner_text()
            page.locator("#question").fill(q)
            # Keep this test fast while exercising real embeddings and real Gemini.
            page.locator("#rerank").uncheck()
            page.locator("#send").click()
            page.locator(".message.assistant .message-text").first.wait_for(timeout=180000)
            session_id = page.evaluate("sessionStorage.getItem('doculens_session')")
            answer = page.locator(".message.assistant .message-text").first.inner_text(timeout=15000)
            assert TOKEN in answer, "Generated answer did not retrieve unique page-2 evidence: " + answer[:400]
            assert "[1]" in answer or "[2]" in answer, "Answer lacks a source citation."
            source = page.locator(".message.assistant .source-summary")
            assert source.count() == 1, "No expandable citation source excerpts"
            source.locator("summary").click()
            assert "Page 2" in source.inner_text()
            assert TOKEN in source.inner_text()
            assert not errors, errors
            print("PASS Chrome upload, real Gemini answer, citation and PDF page 2")
            session_id = page.evaluate("sessionStorage.getItem('doculens_session')")
            assert session_id, "Session was not saved to sessionStorage"
            # Reopen tab: recover persisted chat.
            page.reload(wait_until="networkidle", timeout=30000)
            page.locator(".message.assistant .message-text").first.wait_for(timeout=30000)
            restored = page.locator(".message.assistant .message-text").first.inner_text()
            assert TOKEN in restored, "Reload did not restore PostgreSQL chat history"
            print("PASS browser chat restored from saved session after refresh")
            browser.close()
        after = requests.get(BASE + "/api/documents",timeout=20).json()
        new = [d for d in after if d["id"] not in before and d["name"] == filename]
        assert len(new)==1,new
        test_doc_id=new[0]["id"]
        assert new[0]["pages"]==2
        with psycopg.connect(settings.database_url) as conn:
            rec = conn.execute("SELECT COUNT(*) FROM documents WHERE id=%s",(test_doc_id,)).fetchone()[0]
            turns = conn.execute("SELECT role FROM messages WHERE session_id=%s",(session_id,)).fetchall()
        assert rec==1 and {t[0] for t in turns} >= {"user","assistant"}, (rec,turns)
        print("PASS source metadata and full chat stored in PostgreSQL")
        result = requests.post(BASE + "/api/search",
            json={"question":f"What is the verification codename {TOKEN}?",
                  "source_ids":[test_doc_id], "top_k":5,"rerank":True},timeout=180)
        assert result.status_code==200,result.text[:500]
        data=result.json()
        assert data["reranked"] and any(h["page"]==2 for h in data["hits"])
        print("PASS live Chroma + BM25 + CrossEncoder rerank returns PDF page 2")
except Exception:
    # Print full exception, but no credentials; user-created sample contains none.
    raise
finally:
    if session_id:
        r=requests.delete(BASE + "/api/sessions/" + session_id,timeout=30)
        print("CLEANUP test chat",r.status_code)
    for d in requests.get(BASE + "/api/documents",timeout=20).json():
        if d["id"] not in before and d["name"]==filename:
            r=requests.delete(BASE + "/api/documents/" + d["id"],timeout=60)
            print("CLEANUP test document",r.status_code)
