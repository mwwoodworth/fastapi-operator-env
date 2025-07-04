# codex/tasks/tana_create.py

import httpx
import os
import logging

TANA_API_KEY = os.getenv("TANA_API_KEY")


def run(context: dict):
    if not TANA_API_KEY:
        logging.error("[❌] TANA_API_KEY is missing")
        return

    name = context.get("content", "Untitled Node")
    supertags = context.get("tags", [])
    fields = context.get("fields", {})
    children = context.get("children", [])

    payload = {
        "nodes": [
            {
                "name": name,
                "supertags": supertags,
                "fields": fields,
                "children": [{"name": c} for c in children],
            }
        ]
    }

    try:
        response = httpx.post(
            "https://europe-west1.api.tana.inc/create/nodes",
            headers={
                "Authorization": f"Bearer {TANA_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        logging.info(f"[✅] Node created in Tana: {name}")
        logging.debug(f"[🔁] Response: {response.json()}")
    except httpx.HTTPError as e:
        logging.error(f"[❌] Tana API error: {str(e)}")

