"""Evaluate DocuLens retrieval against the indexed sample papers.

The educational paper metrics are fictional. These checks measure retrieval
coverage only, not general model accuracy, hallucination rate or faithfulness.
"""
import requests

BASE="http://127.0.0.1:8000"
def request(method,path,**kw):
    r=requests.request(method,BASE+path,timeout=120,**kw)
    r.raise_for_status()
    return r.json()

health=request("GET","/api/health")
print("Server:",health["status"],"| metadata:",health.get("metadata_backend"),
      "| vectors:",health["vector_backend"],"| chunks:",health["chunks"])
docs=request("GET","/api/documents")
by_name={d["name"]:d["id"] for d in docs}
definitions=[
    ("paper_a.md","Which paper used 800-character chunks with a 100-character overlap?"),
    ("paper_b.md","Which paper used reciprocal rank fusion with rank constant 60?"),
]
cases=[{"question":question,"expected_source_ids":[by_name[name]]}
       for name,question in definitions if name in by_name]
if not cases:
    raise SystemExit("No sample paper documents indexed; add sample_data/paper_a.md and paper_b.md.")
results=request("POST","/api/evaluate",json={"cases":cases,"top_k":5,"rerank":False})
print("Evaluation cases:",len(cases))
for case in results["cases"]:
    print(" -",case["question"])
    print("   recall@5:",case["recall_at_k"],"reciprocal rank:",case["reciprocal_rank"])
print("Mean Recall@5:",results["recall_at_k"],"MRR:",results["mrr"],
      "mean retrieval ms:",results["mean_latency_ms"])
print("Note: tiny illustrative test set; not an external benchmark.")
