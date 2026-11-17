"""List models advertised to the user's configured Gemini API key (names only)."""
from doculens.settings import Settings
from google import genai

s=Settings()
if not s.gemini_key:
    print("NO_KEY")
else:
    client=genai.Client(api_key=s.gemini_key)
    try:
        count=0
        for model in client.models.list():
            name=model.name or ""
            actions=getattr(model,"supported_actions",[]) or []
            if "flash" in name.lower() and (not actions or any("generate" in str(a).lower() for a in actions)):
                print(name)
                count+=1
                if count>=20:break
        print("FLASH_MODELS_LISTED",count)
    except Exception as exc:
        print("MODEL_LIST_UNAVAILABLE",type(exc).__name__,getattr(exc,"code","?"))
    finally:
        client.close()
