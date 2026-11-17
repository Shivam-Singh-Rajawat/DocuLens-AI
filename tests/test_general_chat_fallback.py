"""Explicit general chat retries a secondary model on transient provider failures."""
from types import SimpleNamespace
from google import genai
from google.genai import errors
from doculens.llm import generate_general

def test_general_chat_tries_another_model_on_transient_outage(monkeypatch):
    used=[]
    class Client:
        def __init__(self,api_key):
            assert api_key=="dummy-key"
            self.models=self
        def generate_content(self,model,**kwargs):
            used.append(model)
            if len(used)==1:
                raise errors.ServerError(503,{"error":{"code":503,"message":"service temporarily unavailable"}})
            return SimpleNamespace(text="RAG retrieves evidence; fine-tuning changes model parameters.")
        def close(self): pass
    monkeypatch.setattr(genai,"Client",Client)
    cfg=SimpleNamespace(llm_provider="gemini",gemini_model="gemini-3.5-flash-lite",gemini_key="dummy-key")
    response,provider=generate_general("RAG vs fine-tuning?",[],cfg)
    assert provider=="gemini"
    assert "RAG" in response
    assert len(set(used))==2
