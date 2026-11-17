"""Gemini API failures must not leak keys or appear as unhelpful HTTP 500s."""
from types import SimpleNamespace
import pytest
from google import genai
from google.genai import errors
from doculens.llm import generate

def test_unavailable_gemini_model_has_clear_runtime_error(monkeypatch):
    closed=[]
    class FakeClient:
        def __init__(self, api_key):
            assert api_key=="dummy-secret"
            self.models=self
        def generate_content(self, **kwargs):
            raise errors.ClientError(404,{"error":{"code":404,"message":"model unavailable","status":"NOT_FOUND"}})
        def close(self):
            closed.append(True)
    monkeypatch.setattr(genai,"Client",FakeClient)
    settings=SimpleNamespace(llm_provider="gemini",gemini_key="dummy-secret",gemini_model="obsolete-model")
    hit={"source_name":"demo.txt","source_id":"123","text":"The study uses PostgreSQL.","kind":"txt","page":1}
    with pytest.raises(RuntimeError,match="unavailable") as error:
        generate("Where is the data stored?",[hit],[],settings=settings,mode="qa",custom_instructions="")
    assert "dummy-secret" not in str(error.value)
    assert closed
