"""Send a prompt to Anthropic Claude and return the completion."""

import os
import httpx
import logging
from datetime import datetime, timezone
from pathlib import Path
from utils.text_helpers import clean_ai_response
from utils.template_loader import render_template
from utils.ai_logging import log_prompt

TASK_ID = "claude_prompt"
TASK_DESCRIPTION = "Send a prompt to Claude and return response"
REQUIRED_FIELDS = ["prompt"]

logger = logging.getLogger(__name__)

CLAUDE_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("CLAUDE_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"


def _append_log(prompt: str, completion: str) -> None:
    """Append raw Claude interaction to dated log file."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    fname = log_dir / f"claude_{datetime.now(timezone.utc).date()}.txt"
    with fname.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.now(timezone.utc).isoformat()}]\nPrompt: {prompt}\nResponse: {completion}\n\n")


def run(context: dict) -> dict:
    """Execute a Claude API call."""
    if "template" in context:
        prompt = render_template(context.get("template"), context.get("fields", {}))
    else:
        prompt = context.get("prompt", "")
    model = context.get("model", "claude-3-opus")
    temperature = context.get("temperature", 0.7)

    if not CLAUDE_API_KEY:
        logger.error("Missing Claude API key. Set OPENAI_API_KEY or CLAUDE_API_KEY")
        return {"error": "missing_api_key"}

    payload = {
        "model": model,
        "max_tokens": 1024,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        response = httpx.post(API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        completion_raw = response.json().get("content", [{}])[0].get("text", "")
        completion = clean_ai_response(completion_raw)
        _append_log(prompt, completion)
        log_prompt("claude", TASK_ID, prompt, completion)
        logger.info("Claude completion length %s", len(completion))
        return {"completion": completion, "executed_by": "claude"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Claude API call failed: %s", exc)
        return {"error": str(exc)}
