"""Real Chrome browser smoke check for composer attachments; no LLM call needed."""
from pathlib import Path
from tempfile import TemporaryDirectory
import uuid
import requests
import fitz
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
created = []
before = {d["id"] for d in requests.get(BASE+"/api/documents",timeout=20).json()}
with TemporaryDirectory(prefix="doculens_attach_") as directory:
    doc = fitz.open()
    doc.new_page().insert_text((50,80), "This uploaded document contains a unique method named LANTERN.")
    filename = "chat-upload-"+uuid.uuid4().hex[:8]+".pdf"
    filepath = Path(directory)/filename
    filepath.write_bytes(doc.tobytes())
    doc.close()
    captured = []
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True, executable_path=CHROME, args=["--no-sandbox"])
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(BASE+"/",wait_until="networkidle",timeout=30000)
            page.locator("#chatAttachButton").wait_for()
            assert page.locator("#chatAttachments .chat-file-chip").count()==0
            assert page.locator("#chatAttachButton").is_visible()
            print("PASS chat Attach control visible")

            page.locator("#chatFiles").set_input_files(str(filepath))
            assert page.locator("#chatAttachments .chat-file-chip").count()==1
            assert filename in page.locator("#chatAttachments").inner_text()
            print("PASS file chooser stages PDF and shows removable chip")

            page.locator("#chatAttachments button[data-remove-chat-file]").click()
            assert page.locator("#chatAttachments .chat-file-chip").count()==0
            print("PASS attachment can be removed without indexing")

            paste_handled = page.evaluate("""() => {
                const transfer = new DataTransfer();
                transfer.items.add(new File(["dummy"],"clipboard-test.pdf",{type:"application/pdf"}));
                const event = new ClipboardEvent("paste",{bubbles:true,cancelable:true,clipboardData:transfer});
                document.querySelector("#question").dispatchEvent(event);
                return event.defaultPrevented;
            }""")
            assert paste_handled and page.locator("#chatAttachments .chat-file-chip").count()==1
            assert "clipboard-test.pdf" in page.locator("#chatAttachments").inner_text()
            print("PASS clipboard PDF file staged when browser exposes it")

            page.locator("#chatAttachments button[data-remove-chat-file]").click()
            drop_handled = page.evaluate("""() => {
                const transfer = new DataTransfer();
                transfer.items.add(new File(["dummy"],"dropped-test.pdf",{type:"application/pdf"}));
                const event = new DragEvent("drop",{bubbles:true,cancelable:true,dataTransfer:transfer});
                document.querySelector("#chatView").dispatchEvent(event);
                return event.defaultPrevented;
            }""")
            assert drop_handled and "dropped-test.pdf" in page.locator("#chatAttachments").inner_text()
            print("PASS PDF drag and drop stages file")
            page.locator("#chatAttachments button[data-remove-chat-file]").click()
            page.locator("#chatFiles").set_input_files(str(filepath))

            def intercept_chat(route):
                payload = route.request.post_data_json
                captured.append(payload)
                route.fulfill(status=200,content_type="application/json",json={
                    "session_id":"attachment_smoke_session",
                    "question":payload["question"],
                    "answer":"Document indexed and source attached [1].",
                    "provider":"evidence-only","sources":[],
                    "warnings":[],"reranked":False,"retrieval_ms":1.0
                })
            page.route("**/api/chat",intercept_chat)
            page.locator("#question").fill("What method does this PDF describe?")
            page.locator("#send").click()
            page.locator(".message.assistant").first.wait_for(timeout=180000)
            assert len(captured)==1
            assert len(captured[0]["source_ids"])==1
            assert captured[0]["question"]=="What method does this PDF describe?"
            indexed = requests.get(BASE+"/api/documents",timeout=30).json()
            new_docs = [d for d in indexed if d["id"] not in before]
            assert len(new_docs)==1,new_docs
            created.extend(d["id"] for d in new_docs)
            assert new_docs[0]["name"]==filename
            assert captured[0]["source_ids"]==[new_docs[0]["id"]],captured
            assert page.locator("#chatAttachments .chat-file-chip").count()==0
            assert not errors, errors
            print("PASS Send indexes real PDF and scopes chat to new document ID")
            browser.close()
    finally:
        current = requests.get(BASE+"/api/documents",timeout=30).json()
        for document in current:
            if document["id"] not in before:
                response = requests.delete(BASE+"/api/documents/"+document["id"],timeout=30)
                print("CLEANUP",document["name"],response.status_code)
