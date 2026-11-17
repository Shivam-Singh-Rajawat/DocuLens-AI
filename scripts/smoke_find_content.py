"""Verify grounded passage finding on the existing Case Study PDF without showing its text."""
import requests

BASE="http://127.0.0.1:8000"
docs=requests.get(BASE+"/api/documents",timeout=12).json()
target=next((d for d in docs if d["name"]=="Case Study.pdf"),None)
if target is None:
    raise SystemExit("Case Study.pdf not available; use your own uploaded PDF.")
session=None
try:
    response=requests.post(BASE+"/api/chat",json={
        "question":"find the passage about customer satisfaction",
        "mode":"find","source_ids":[target["id"]],
        "top_k":5,"rerank":False,
    },timeout=90)
    response.raise_for_status()
    result=response.json()
    session=result["session_id"]
    assert result["provider"]=="passage-search",result["provider"]
    assert result["sources"],"The uploaded PDF had no matching evidence"
    assert all(s["source_id"]==target["id"] for s in result["sources"])
    assert any("customer satisfaction" in s["excerpt"].lower()
               for s in result["sources"]),"No literal topic evidence returned"
    assert "[1]" in result["answer"]
    print("PASS original Case Study PDF passage retrieval")
    print("Result count:",len(result["sources"]))
    print("Pages:",sorted({s["page"] for s in result["sources"] if s["page"]}))
    print("No LLM generation required; original PDF evidence only.")
finally:
    if session:
        requests.delete(BASE+"/api/sessions/"+session,timeout=12)
