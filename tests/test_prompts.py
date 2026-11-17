from types import SimpleNamespace
from doculens.llm import make_prompt, generate, SYSTEM_PROMPT, PROMPT_MODES


def test_llm_prompt_uses_numbered_evidence_and_untrusted_instructions():
    hit={"page":2,"kind":"pdf","source_name":"study.pdf","source_id":"docx","text":"Accuracy of 93 percent"}
    prompt=make_prompt("What is the accuracy?",[hit],[],"extract","Use one short sentence.")
    assert "[SOURCE 1] study.pdf (page 2)" in prompt
    assert "Accuracy of 93 percent" in prompt
    assert "Use one short sentence" in prompt
    assert "UNTRUSTED DATA" in SYSTEM_PROMPT
    assert "outside knowledge" in SYSTEM_PROMPT
    assert len(PROMPT_MODES)>=6


def test_missing_gemini_key_uses_evidence_only_mode():
    settings=SimpleNamespace(llm_provider="gemini",gemini_key="")
    answer,provider=generate("What?",[{"text":"a factual passage"}],[],settings=settings,mode="qa",custom_instructions="")
    assert provider=="evidence-only"
    assert "API key not set" in answer
