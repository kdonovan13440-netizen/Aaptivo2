from groq import Groq
from .config import settings

SYSTEM = """You are Aptivo, a careful personal assistant. Be transparent about capabilities.
Never claim an action happened unless a connected tool confirms it. Ask for confirmation
before calls, messages, bookings, purchases, deletion, or device changes. Do not expose secrets."""

def answer(message: str) -> str:
    if not settings.groq_api_key:
        return "AI is not configured yet. Add GROQ_API_KEY to the server environment."
    client = Groq(api_key=settings.groq_api_key)
    result = client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role":"system","content":SYSTEM},{"role":"user","content":message}],
        temperature=0.3,
    )
    return result.choices[0].message.content or ""
