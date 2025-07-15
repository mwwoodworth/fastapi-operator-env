"""Generate basic product documentation and push to docs site."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

from . import claude_prompt

TASK_ID = "generate_product_docs"
TASK_DESCRIPTION = "Create product docs using Claude and upload"
REQUIRED_FIELDS = ["product_name", "description"]

logger = logging.getLogger(__name__)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    name = context.get("product_name")
    desc = context.get("description")
    if not name or not desc:
        return {"error": "missing_fields"}

    prompt = (
        "Write concise documentation for a product.\n"
        f"Name: {name}\nDescription: {desc}\n"
        "Include usage instructions and key features."
    )
    ai = claude_prompt.run({"prompt": prompt})
    docs = ai.get("completion", "")

    url = os.getenv("DOCS_WEBHOOK_URL")
    if url:
        try:  # pragma: no cover - external network
            httpx.post(
                url,
                json={"title": name, "content": docs},
                timeout=10,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Upload failed: %s", exc)
            return {"docs": docs, "upload": "error", "error": str(exc)}
    return {"docs": docs, "upload": "success" if url else "disabled"}
