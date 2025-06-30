# gpt_utils.py
import os
import httpx
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = "gpt-4o"

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not set in environment.")

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json"
}

async def run_gpt(prompt: str) -> str:
    payload = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 1024
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post("https://api.openai.com/v1/chat/completions", headers=HEADERS, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
