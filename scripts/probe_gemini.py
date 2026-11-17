"""Tiny credential-safe Gemini generation probe."""
from doculens.settings import Settings
from google import genai
from google.genai import types
s=Settings()
client=genai.Client(api_key=s.gemini_key,http_options=types.HttpOptions(timeout=30000))
model="gemini-3.5-flash-lite"
try:
    response=client.models.generate_content(
        model=model, contents="Say only: READY",
        config=types.GenerateContentConfig(max_output_tokens=50,temperature=0))
    print("PROBE_MODEL",model)
    print("PROBE_OK",bool(response.text and "READY" in response.text))
    if response.text:print("RESPONSE",response.text[:60])
except Exception as exc:
    print("PROBE_FAILED",type(exc).__name__,getattr(exc,"code","unknown"))
finally:
    client.close()
