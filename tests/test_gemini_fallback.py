"""Gemini fallback behaviour when provider gives transient HTTP failures."""
from types import SimpleNamespace
from google import genai
from google.genai import errors
from doculens.llm import generate

HIT={"source_name":"notes.txt","source_id":"1","text":"Retrieved useful evidence.","kind":"text","page":1}

def _settings():
    return SimpleNamespace(llm_provider="gemini",gemini_key="dummy-secret",
                           gemini_model="gemini-3.5-flash-lite")

def test_gemini_tries_alternate_model_when_primary_temporarily_unavailable(monkeypatch):
    calls=[]
    class FakeClient:
        def __init__(self,api_key): self.models=self
        def generate_content(self,model,**kwargs):
            calls.append(model)
            if model=="gemini-3.5-flash-lite":
                raise errors.ServerError(503,{"error":{"code":503,"message":"temporarily unavailable"}})
            return SimpleNamespace(text="Here is the evidence [1].")
        def close(self):pass
    monkeypatch.setattr(genai,"Client",FakeClient)
    answer,provider=generate("What does the document say?",[HIT],[],settings=_settings(),mode="qa",custom_instructions="")
    assert provider=="gemini"
    assert "[1]" in answer
    assert len(set(calls))>=2

def test_gemini_returns_cited_evidence_when_models_unavailable(monkeypatch):
    class FakeClient:
        def __init__(self,api_key):self.models=self
        def generate_content(self,**kwargs):
            raise errors.ServerError(503,{"error":{"code":503,"message":"temporarily unavailable"}})
        def close(self): pass
    monkeypatch.setattr(genai,"Client",FakeClient)
    answer,provider=generate("What does the document say?",[HIT],[],settings=_settings(),mode="qa",custom_instructions="")
    assert provider=="evidence-only"
    assert "[1]" in answer
    assert "temporarily unavailable" in answer.lower()
