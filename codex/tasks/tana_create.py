# codex/tasks/tana_create.py

import httpx
import os
import logging

TANA_API_KEY = os.getenv("TANA_API_KEY")

def run(context: dict):
    content = context.get("content", "").strip()

    if not TANA_API_KEY:
        logging.error("[❌] TANA_API_KEY is missing")
        return

    if not content:
        logging.error("[❌] No content provided to send to Tana")
        return

    headers = {
        "Authorization": f"Bearer {TANA_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "nodes": [
            {
                "name": content
            }
        ]
    }

    try:
        response = httpx.post(
            "https://europe-west1.api.tana.inc/create/nodes",
            headers=headers,
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        logging.info("[✅] Node created in Tana successfully")
        logging.info(f"↳ Response: {response.json()}")

    except httpx.HTTPError as e:
        logging.error(f"[❌] Tana API request failed: {str(e)}")

