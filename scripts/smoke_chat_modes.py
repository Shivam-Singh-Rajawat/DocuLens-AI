"""Local end-to-end RAG dialogue regression without printing document content."""
import requests
base="http://127.0.0.1:8000"
docs=requests.get(base+"/api/documents",timeout=10).json()
case=next(d for d in docs if d["name"].casefold()=="case study.pdf")
sessions=[]
def ask(question,mode="qa",source_ids=None,session_id=None):
    payload={"question":question,"mode":mode,"source_ids":source_ids,
             "session_id":session_id,"rerank":False,"top_k":5}
    resp=requests.post(base+"/api/chat",json=payload,timeout=130)
    assert resp.status_code==200,(resp.status_code,resp.text[:300])
    value=resp.json()
    sessions.append(value["session_id"])
    return value
try:
    exact=ask("find the word the in this",source_ids=[case["id"]])
    assert exact["provider"]=="document-search" and "occurrences" in exact["answer"]
    assert len(exact["sources"])>0
    print("PASS exact term search on 7-page Case Study PDF, linked pages:",
          len(exact["sources"]),"answer:",exact["answer"].splitlines()[0])
    summary=ask("what is this pdf about?",source_ids=[case["id"]])
    assert summary["sources"] and summary["provider"]=="gemini",(summary["provider"],summary["answer"][:250])
    print("PASS grounded document summary with",len(summary["sources"]),"references")
    chat=ask("What is the difference between RAG and fine-tuning? Give 2 short points.",mode="chat",source_ids=[])
    assert chat["provider"]=="gemini" and not chat["sources"], chat
    print("PASS general chatbot, no document citations")
    follow=ask("And which one is usually cheaper to update?",mode="chat",source_ids=[],session_id=chat["session_id"])
    assert follow["provider"]=="gemini" and follow["session_id"]==chat["session_id"]
    print("PASS follow-up conversation shares session ID")
finally:
    for sid in set(sessions):
        requests.delete(base+"/api/sessions/"+sid,timeout=10)
