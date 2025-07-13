# claude_utils.py
import httpx
from loguru import logger
from utils.metrics import CLAUDE_API_CALLS, CLAUDE_TOKENS

from core.settings import Settings

settings = Settings()

CLAUDE_API_KEY = settings.CLAUDE_API_KEY
CLAUDE_MODEL = "claude-3-opus-20240229"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

if not CLAUDE_API_KEY:
    raise ValueError("CLAUDE_API_KEY not set in environment.")

HEADERS = {
    "x-api-key": CLAUDE_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}


async def run_claude(prompt: str) -> str:
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1024,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(ANTHROPIC_API_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        data = response.json()
        CLAUDE_API_CALLS.inc()
        usage = data.get("usage", {})
        CLAUDE_TOKENS.inc(usage.get("output_tokens", 0) + usage.get("input_tokens", 0))
        return data["content"][0]["text"]


async def stream_claude(prompt: str):
    """Yield Claude tokens using Anthropic streaming API."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)
    CLAUDE_API_CALLS.inc()
    async with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for event in stream:
            if event.type == "content_block_delta":
                CLAUDE_TOKENS.inc(len(event.delta.text.split()))
                yield event.delta.text
