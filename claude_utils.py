import os
import httpx
from dotenv import load_dotenv

# Load from .env file
load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

if not CLAUDE_API_KEY:
    raise ValueError("CLAUDE_API_KEY is not set. Please check your .env file.")

HEADERS = {
    "x-api-key": CLAUDE_API_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json"
}

async def run_claude(prompt: str) -> str:
    payload = {
        "model": "claude-3-opus-20240229",
        "max_tokens": 1024,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:  # <-- added timeout here
            response = await client.post(ANTHROPIC_API_URL, headers=HEADERS, json=payload)
            response.raise_for_status()
            data = response.json()
            print("🧠 Claude Raw Response:", data)

            if "content" in data and isinstance(data["content"], list):
                return data["content"][0]["text"]
            elif "completion" in data:
                return data["completion"]
            else:
                raise ValueError(f"Unexpected Claude response: {data}")

    except httpx.ReadTimeout:
        return "❌ Claude API timed out. Please try again later or reduce prompt length."