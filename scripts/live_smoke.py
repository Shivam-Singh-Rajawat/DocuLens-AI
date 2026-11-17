"""HTTP end-to-end check using local offline backend; exits nonzero on failure."""
import os
import subprocess
import sys
import tempfile
import time

import fitz
import requests

with tempfile.TemporaryDirectory(prefix="doculens_smoke_") as directory:
    env = os.environ.copy()
    env.update({"DATA_DIR":directory,"VECTOR_BACKEND":"sqlite", "EMBEDDING_BACKEND":"hash",
                "ENABLE_RERANKER":"false","LLM_PROVIDER":"none","APP_ACCESS_TOKEN":""})
    server = subprocess.Popen([sys.executable,"-m","uvicorn","doculens.api:app",
                                "--host","127.0.0.1","--port","8897"],env=env,
                               stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    base="http://127.0.0.1:8897"
    try:
        for i in range(45):
            try:
                resp=requests.get(base+"/api/health",timeout=1)
                if resp.status_code==200:
                    break
            except requests.RequestException:
                time.sleep(.2)
        else:
            server.terminate()
            raise RuntimeError("Backend failed to launch for live test. " + server.communicate(timeout=5)[0].decode()[-1600:])
        homepage=requests.get(base+"/",timeout=5)
        assert homepage.status_code==200 and "DocuLens AI" in homepage.text
        js=requests.get(base+"/app.js",timeout=5)
        assert js.status_code==200 and "custom_instructions" in js.text
        print("PASS homepage and Javascript served")
        doc=fitz.open()
        doc.new_page().insert_text((55,80),"RAG pages preserve evidence and source references")
        data=doc.tobytes()
        doc.close()
        upload=requests.post(base+"/api/documents/upload",data=data,
                             headers={"X-Filename":"live-smoke.pdf","Content-Type":"application/pdf"},timeout=8)
        assert upload.status_code==201,upload.text
        source_id=upload.json()["id"]
        print("PASS PDF indexed",source_id)
        answer=requests.post(base+"/api/chat",json={"question":"What do RAG pages preserve?","rerank":False},timeout=8)
        assert answer.status_code==200,answer.text
        body=answer.json()
        assert body["sources"][0]["source_id"]==source_id and body["sources"][0]["page"]==1,body
        print("PASS chat grounded in PDF page 1")
        answer2=requests.get(base+"/api/documents/"+source_id+"/file",timeout=5)
        assert answer2.status_code==200 and answer2.content.startswith(b"%PDF")
        print("PASS original PDF downloadable")
        deleted=requests.delete(base+"/api/documents/"+source_id,timeout=8)
        assert deleted.status_code==200 and deleted.json()["deleted"]
        print("PASS document deletion")
    finally:
        server.terminate()
        try:server.communicate(timeout=5)
        except subprocess.TimeoutExpired:server.kill();server.communicate()
