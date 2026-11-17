"""Private local diagnostic: report counts, not document text."""
import collections
import re
import requests
import fitz
base="http://127.0.0.1:8000"
docs=requests.get(base+"/api/documents",timeout=15).json()
for d in docs:
    print("DOC",d["name"],"kind",d["kind"],"pages",d["pages"],"chunks",d["chunks"])
    if d["name"].lower()=="case study.pdf":
        print("FILE_PRESENT",bool(d.get("file_path")))
        if d.get("file_path"):
            with fitz.open(d["file_path"]) as pdf:
                for i,p in enumerate(pdf,1):
                    t=p.get_text(sort=True)
                    print("PAGE",i,"chars",len(t),"images",len(p.get_images()),"word_the",len(re.findall(r"\\bthe\\b",t,re.I)))
        for q in ["find the word the in this","Summarize the main purpose of this case study"]:
            r=requests.post(base+"/api/search",json={"question":q,"source_ids":[d["id"]],"top_k":5,"rerank":False},timeout=60)
            print("SEARCH",q,"status",r.status_code)
            if r.ok:
                print([(h["page"],round(h.get("semantic_score",0),3),round(h.get("bm25_score",0),3)) for h in r.json()["hits"][:5]])
