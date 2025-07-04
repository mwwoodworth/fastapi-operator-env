"""Send a prompt to Google Gemini and return the completion."""

import os
import httpx
import logging
from datetime import datetime
from pathlib import Path
from utils.text_helpers import clean_ai_response
from utils.template_loader import render_template

TASK_ID = "gemini_prompt"
TASK_DESCRIPTION = "Send a prompt to Gemini and return response"
REQUIRED_FIELDS = ["prompt"]

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _append_log(prompt: str, completion: str) -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    fname = log_dir / f"gemini_{datetime.utcnow().date()}.txt"
    with fname.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.utcnow().isoformat()}]\nPrompt: {prompt}\nResponse: {completion}\n\n")


def run(context: dict) -> dict:
    if "template" in context:
        prompt = render_template(context.get("template"), context.get("fields", {}))
    else:
        prompt = context.get("prompt", "")
    model = context.get("model", "gemini-1.5-pro")

    if not GEMINI_API_KEY:
        logger.error("Missing GEMINI_API_KEY env var")
        return {"error": "missing_api_key"}

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    url = f"{API_URL_TEMPLATE.format(model=model)}?key={GEMINI_API_KEY}"
    try:
        response = httpx.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        completion_raw = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        completion = clean_ai_response(completion_raw)
        _append_log(prompt, completion)
        logger.info("Gemini completion length %s", len(completion))
        return {"completion": completion}
    except Exception as exc:  # noqa: BLE001
        logger.error("Gemini API call failed: %s", exc)
        return {"error": str(exc)}
