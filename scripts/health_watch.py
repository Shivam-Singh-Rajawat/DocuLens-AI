"""DocuLens local health watchdog.

Safe for frequent Windows Task Scheduler runs:
- Probes localhost only; never calls a billable LLM.
- Restarts only if HTTP health is unavailable.
- Logs status and counts, never contents, passwords, API keys, or exception messages.
- Does not auto-modify source code or uploaded documents.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import requests

ROOT=Path(__file__).resolve().parents[1]
BASE="http://127.0.0.1:8000"
LOG=ROOT/"data"/"logs"/"health-watch.jsonl"


def probe_http():
    response=requests.get(BASE+"/api/health", timeout=8)
    response.raise_for_status()
    health=response.json()
    if health.get("status")!="ok" or "documents" not in health:
        raise RuntimeError("unhealthy API")
    return health


def check_retrieval():
    """Cheap unbilled audit of known demo-document lexical retrieval, if present."""
    response=requests.get(BASE+"/api/documents",timeout=8)
    response.raise_for_status()
    documents=response.json()
    sample=next((d for d in documents if d["name"]=="paper_b.md"),None)
    if sample is None:
        return "skipped"  # User may have intentionally removed demo data.
    # The first retrieval after a reboot loads transformer weights lazily and
    # can legitimately exceed 25 seconds. Don't flag that cold start as failure.
    for attempt in range(2):
        try:
            response=requests.post(BASE+"/api/search",json={
                "question":"Which study used reciprocal rank fusion with rank constant 60?",
                "top_k":5,"rerank":False},timeout=70)
            response.raise_for_status()
            break
        except requests.Timeout:
            if attempt == 1:
                raise
    hits=response.json().get("hits",[])
    return "ok" if any(hit["source_id"]==sample["id"] for hit in hits) else "degraded"


def recover_local():
    script=ROOT/"Restart_DocuLens.ps1"
    process=subprocess.run(
        ["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass",
         "-File",str(script),"-NoBrowser"],
        cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=110)
    if process.returncode:
        raise RuntimeError("local launcher failed")


def write_record(record:dict,log_file:Path):
    log_file.parent.mkdir(parents=True,exist_ok=True)
    if log_file.exists() and log_file.stat().st_size>1_500_000:
        old=log_file.with_suffix(".previous.jsonl")
        log_file.replace(old)
    with log_file.open("a",encoding="utf-8") as out:
        out.write(json.dumps(record,ensure_ascii=True)+"\n")


def run_check(*,probe,recover,quality,log_file:Path):
    record={
        "timestamp_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status":"offline","quality":"skipped", "documents":0,"chunks":0,
    }
    try:
        try:
            health=probe()
            recovered=False
        except Exception:
            # A previously healthy server might simply be down after reboot.
            # A single recovery attempt is allowed; no infinite restart loop.
            recover()
            health=probe()
            recovered=True
        if health.get("status")!="ok":
            raise RuntimeError("server health not ok")
        record["documents"]=int(health.get("documents",0))
        record["chunks"]=int(health.get("chunks",0))
        record["status"]="recovered" if recovered else "healthy"
        try:
            result=quality()
            record["quality"]=result if result in ("ok","degraded","skipped") else "degraded"
        except Exception:
            record["quality"]="degraded"
        if record["quality"]=="degraded":
            record["status"]="degraded"
    except Exception as exc:
        record["status"]="offline"
        # Never retain exception text: it can contain credentials or file paths.
        record["failure_type"]=type(exc).__name__
    write_record(record,log_file)
    return record


def main():
    result=run_check(probe=probe_http,recover=recover_local,
                     quality=check_retrieval,log_file=LOG)
    print(
        f"DocuLens watch: {result['status']}; retrieval={result['quality']}; "
        f"documents={result['documents']}; chunks={result['chunks']}"
    )
    return 0 if result["status"] in ("healthy","recovered") else 1


if __name__=="__main__":
    raise SystemExit(main())
