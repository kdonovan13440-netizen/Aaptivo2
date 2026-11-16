from groq import Groq
from .config import settings
from .verticals import system_prompt

def answer(message: str) -> str:
    if not settings.groq_api_key:
        return "AI is not configured yet. Add GROQ_API_KEY to the server environment."
    client = Groq(api_key=settings.groq_api_key)
    result = client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role":"system","content":system_prompt()},{"role":"user","content":message}],
        temperature=0.3,
    )
    return result.choices[0].message.content or ""
