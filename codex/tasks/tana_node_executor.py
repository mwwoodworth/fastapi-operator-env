"""Execute tasks defined in Tana nodes with auto_execute=true."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

from codex.brainops_operator import run_task
from codex.memory import memory_store
from . import tana_create

TASK_ID = "tana_node_executor"
TASK_DESCRIPTION = "Run tasks pulled from Tana nodes"
REQUIRED_FIELDS: list[str] = []

logger = logging.getLogger(__name__)

TANA_API_KEY = os.getenv("TANA_API_KEY")
TANA_AUTO_TAG = os.getenv("TANA_AUTO_TAG", "auto_execute")

BASE_URL = "https://europe-west1.api.tana.inc"


def _get_nodes() -> list[dict]:
    if not TANA_API_KEY:
        return []
    headers = {"Authorization": f"Bearer {TANA_API_KEY}"}
    try:
        resp = httpx.get(
            f"{BASE_URL}/get/nodes?tag={TANA_AUTO_TAG}", headers=headers, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("nodes", [])
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch nodes: %s", exc)
        return []


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    nodes = _get_nodes()
    results = []
    for node in nodes:
        try:
            payload = node.get("content") or {}
            if isinstance(payload, str):
                import json as _json

                try:
                    payload = _json.loads(payload)
                except Exception:
                    continue
            if payload.get("feedback"):
                try:
                    memory_store.save_memory(
                        {
                            "task": TASK_ID,
                            "input": payload,
                            "output": payload.get("content"),
                            "tags": ["feedback"],
                            "metadata": {
                                "source": "tana-feedback",
                                "node_id": node.get("id"),
                            },
                        }
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to record feedback")
            task_id = payload.get("task")
            task_ctx = payload.get("context", {})
            if task_id:
                result = run_task(task_id, task_ctx)
                results.append(result)
            if node.get("id"):
                try:
                    tana_create.run(
                        {
                            "content": str(result),
                            "metadata": {"parent": node["id"]},
                        }
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to post result to Tana")
        except Exception as exc:  # noqa: BLE001
            logger.error("Node execution failed: %s", exc)
    return {"executed": len(results), "results": results}
