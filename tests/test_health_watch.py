"""Health watch logs meaningful failures and only restarts an unavailable service."""
import json
from scripts import health_watch


def test_healthy_rag_does_not_restart_and_records_quality(tmp_path):
    restarts=[]
    result=health_watch.run_check(
        probe=lambda:{"status":"ok","documents":5,"chunks":50,"metadata_backend":"postgres","vector_backend":"chroma"},
        recover=lambda:restarts.append(True),
        quality=lambda:"ok",
        log_file=tmp_path/"watch.jsonl")
    assert result["status"]=="healthy"
    assert result["quality"]=="ok"
    assert not restarts
    log=json.loads((tmp_path/"watch.jsonl").read_text().splitlines()[-1])
    assert log["documents"]==5


def test_watch_recovers_offline_service_and_logs_recovery(tmp_path):
    calls=[]
    def probe():
        calls.append("probe")
        if len(calls)==1: raise ConnectionError("not listening")
        return {"status":"ok","documents":2,"chunks":9}
    result=health_watch.run_check(probe=probe,recover=lambda:calls.append("recover"),
                                  quality=lambda:"ok",log_file=tmp_path/"watch.jsonl")
    assert result["status"]=="recovered"
    assert calls==["probe","recover","probe"]


def test_watch_does_not_restart_running_service_for_degraded_quality(tmp_path):
    restarts=[]
    result=health_watch.run_check(
        probe=lambda:{"status":"ok","documents":1,"chunks":2},
        recover=lambda:restarts.append(True),
        quality=lambda:"degraded",
        log_file=tmp_path/"watch.jsonl")
    assert result["status"]=="degraded"
    assert not restarts


def test_watch_reports_unrecoverable_failure_without_secrets(tmp_path):
    sensitive="DO-NOT-COPY-SECRET-ABCDEF"
    result=health_watch.run_check(
        probe=lambda: (_ for _ in ()).throw(RuntimeError(sensitive)),
        recover=lambda:None,quality=lambda:"skipped",
        log_file=tmp_path/"watch.jsonl")
    assert result["status"]=="offline"
    assert sensitive not in (tmp_path/"watch.jsonl").read_text()


def test_retrieval_watch_retries_a_slow_cold_model_load(monkeypatch):
    from requests.exceptions import Timeout
    class Result:
        def __init__(self,payload):self.payload=payload
        def raise_for_status(self):pass
        def json(self):return self.payload
    counts=[]
    monkeypatch.setattr(health_watch.requests,"get",
                        lambda *a,**kw:Result([{"id":"sample-id","name":"paper_b.md"}]))
    def post(*a,**kwargs):
        counts.append(True)
        if len(counts)==1:
            raise Timeout("cold model loading")
        return Result({"hits":[{"source_id":"sample-id"}]})
    monkeypatch.setattr(health_watch.requests,"post",post)
    assert health_watch.check_retrieval()=="ok"
    assert len(counts)==2


def test_recover_uses_safe_restart_for_stalled_owned_server(monkeypatch):
    calls=[]
    class Result: returncode=0
    def fake_run(args,**kwargs):
        calls.append(args)
        return Result()
    monkeypatch.setattr(health_watch.subprocess,"run",fake_run)
    health_watch.recover_local()
    assert len(calls)==1
    assert "Restart_DocuLens.ps1" in " ".join(calls[0])
