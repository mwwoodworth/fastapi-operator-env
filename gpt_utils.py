# gpt_utils.py
import httpx
from loguru import logger
from utils.metrics import OPENAI_API_CALLS, OPENAI_TOKENS

from core.settings import Settings

settings = Settings()

OPENAI_API_KEY = settings.OPENAI_API_KEY
OPENAI_MODEL = "gpt-4o"

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not set in environment.")

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
}


async def run_gpt(prompt: str) -> str:
    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=HEADERS,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        OPENAI_API_CALLS.inc()
        OPENAI_TOKENS.inc(data.get("usage", {}).get("total_tokens", 0))
        return data["choices"][0]["message"]["content"]


async def stream_gpt(prompt: str):
    """Yield GPT tokens using OpenAI streaming API."""
    import openai

    client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
    OPENAI_API_CALLS.inc()
    stream = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1024,
        stream=True,
    )
    async for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            OPENAI_TOKENS.inc(len(token.split()))
            yield token
