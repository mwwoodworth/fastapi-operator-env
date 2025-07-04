from __future__ import annotations

"""Utilities for linking tasks back to their origin."""

from typing import Any, Dict

from . import memory_store


def link_task_to_origin(task_id: str, origin_type: str, metadata: Dict[str, Any]) -> None:
    """Persist lineage information relating a task back to its trigger."""
    entry = {
        "task": "task_origin_link",
        "input": {"task_id": task_id, "origin_type": origin_type},
        "output": metadata,
        "tags": ["lineage", origin_type],
        "metadata": {**metadata, "linked_task_id": task_id},
    }
    try:
        memory_store.save_memory(entry)
    except Exception:  # noqa: BLE001
        pass
