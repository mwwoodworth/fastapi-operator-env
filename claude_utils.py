# claude_utils.py
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_MODEL = "claude-3-opus-20240229"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

if not CLAUDE_API_KEY:
    raise ValueError("CLAUDE_API_KEY not set in environment.")

HEADERS = {
    "x-api-key": CLAUDE_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json"
}

async def run_claude(prompt: str) -> str:
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1024,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}]
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(ANTHROPIC_API_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        return response.json()["content"][0]["text"]
