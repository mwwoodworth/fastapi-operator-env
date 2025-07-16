"""Create a simple node in Tana."""

import httpx
import os
import logging
from codex.memory import memory_store

TASK_ID = "create_tana_node"
TASK_DESCRIPTION = "Create a node in Tana with provided content"
REQUIRED_FIELDS = ["content"]

TANA_API_KEY = os.getenv("TANA_API_KEY")


def run(context: dict):
    content = context.get("content", "").strip()
    if not TANA_API_KEY:
        logging.error("[❌] Missing TANA_API_KEY")
        return
    if not content:
        logging.error("[❌] No content provided")
        return

    headers = {
        "Authorization": f"Bearer {TANA_API_KEY}",
        "Content-Type": "application/json"
    }

    metadata = context.get("metadata")
    node = {"name": content}
    if isinstance(metadata, dict):
        tags = metadata.get("tags")
        if tags:
            node["supertags"] = tags
        node["description"] = metadata.get("source", "")
    payload = {"nodes": [node]}

    node_id = None
    try:
        response = httpx.post(
            "https://europe-west1.api.tana.inc/create/nodes",
            headers=headers,
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        logging.info(f"[✅] Node created in Tana: {data}")
        node_id = data.get("nodes", [{}])[0].get("id")
    except httpx.HTTPError as e:
        logging.error(f"[❌] HTTP error: {str(e)}")
        return

    if os.getenv("TRACE_FEEDBACK_ENABLED", "false").lower() == "true" and node_id:
        transcript = metadata.get("transcript_id") if isinstance(metadata, dict) else None
        model = metadata.get("model") if isinstance(metadata, dict) else None
        body = f"✅ Task posted successfully.\nTranscript: {transcript}\nModel: {model}"
        try:
            fb_payload = {"nodes": [{"name": body, "parent": node_id, "supertags": ["feedback", "trace-confirmed"]}]}
            httpx.post(
                "https://europe-west1.api.tana.inc/create/nodes",
                headers=headers,
                json=fb_payload,
                timeout=10,
            )
            memory_store.save_memory(
                {
                    "task": "tana_feedback",
                    "input": metadata,
                    "output": body,
                    "tags": ["feedback", "trace-confirmed"],
                    "metadata": {"parent_node": node_id, "transcript_id": transcript, "model": model},
                }
            )
        except Exception:  # noqa: BLE001
            logging.exception("Failed to post feedback node")
    return {"status": "created", "node_id": node_id}
