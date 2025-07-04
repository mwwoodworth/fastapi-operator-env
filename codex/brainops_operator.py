"""Core task dispatcher for BrainOps Operator."""

from __future__ import annotations

import datetime
from datetime import timezone
import importlib
import json
import logging
import traceback
import pkgutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any, Dict, List

from .memory import memory_store, link_task_to_origin
from utils.slack import send_slack_message

logger = logging.getLogger(__name__)

_LOG_FILE = Path("logs/task_log.json")
_ERROR_LOG_FILE = Path("logs/error_log.json")


@dataclass
class TaskDefinition:
    """Metadata about a registered task."""

    id: str
    func: Callable[[dict], Any]
    description: str = ""
    required_fields: List[str] = field(default_factory=list)


_TASK_REGISTRY: Dict[str, TaskDefinition] = {}


def register_task(
    task_id: str,
    func: Callable[[dict], Any],
    description: str = "",
    required_fields: List[str] | None = None,
) -> None:
    """Register a task implementation."""

    _TASK_REGISTRY[task_id] = TaskDefinition(
        task_id, func, description, required_fields or []
    )
    logger.debug("Registered task %s", task_id)


def _load_tasks() -> None:
    """Import task modules under ``codex.tasks`` and register them."""

    from . import tasks as tasks_pkg

    for module_info in pkgutil.iter_modules(tasks_pkg.__path__):
        module_name = module_info.name
        module = importlib.import_module(f"codex.tasks.{module_name}")
        func = getattr(module, "run", None)
        if func is None:
            continue
        task_id = getattr(module, "TASK_ID", module_name)
        description = getattr(module, "TASK_DESCRIPTION", "") or (
            module.__doc__ or ""
        ).strip()
        required = getattr(module, "REQUIRED_FIELDS", [])
        register_task(task_id, func, description, required)


def get_registry() -> Dict[str, TaskDefinition]:
    """Return all discovered tasks."""

    if not _TASK_REGISTRY:
        _load_tasks()
    return _TASK_REGISTRY


def _log_task(task: str, context: dict, result: Any) -> None:
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry_id = str(uuid.uuid4())
    entry = {
        "id": entry_id,
        "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
        "task": task,
        "context": context,
        "result": result,
        "retry": context.get("retry", 0),
    }
    history: List[dict] = []
    if _LOG_FILE.exists():
        try:
            history = json.loads(_LOG_FILE.read_text())
        except Exception:  # noqa: BLE001
            history = []
    history.append(entry)
    _LOG_FILE.write_text(json.dumps(history[-100:], indent=2))
    return entry_id


def run_task(task_id: str, context: Dict[str, Any]) -> Any:
    """Execute a registered task and persist a log entry."""

    registry = get_registry()
    task_def = registry.get(task_id)
    if not task_def:
        raise ValueError(f"Unknown task: {task_id}")
    retry = int(context.get("retry", 0))
    try:
        result = task_def.func(context)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Task %s failed", task_id)
        tb = traceback.format_exc()
        result = {"error": str(exc), "stack": tb}
        if retry < 3:
            try:
                from supabase_client import supabase

                supabase.table("retry_queue").insert(
                    {
                        "task": task_id,
                        "context": context,
                        "retry": retry + 1,
                        "status": "pending",
                    }
                ).execute()
            except Exception as e:  # noqa: BLE001
                logger.error("Failed to queue retry: %s", e)
    log_entry_id = _log_task(task_id, context, result)
    status = "success"
    if isinstance(result, dict) and result.get("error"):
        status = "failed"
        _ERROR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        history = []
        if _ERROR_LOG_FILE.exists():
            try:
                history = json.loads(_ERROR_LOG_FILE.read_text())
            except Exception:  # noqa: BLE001
                history = []
        history.append(
            {
                "id": log_entry_id,
                "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
                "task": task_id,
                "context": context,
                "error": result.get("error"),
                "stack": result.get("stack"),
            }
        )
        _ERROR_LOG_FILE.write_text(json.dumps(history[-100:], indent=2))
        send_slack_message(f"Task {task_id} failed: {result.get('error')}")
    try:
        origin_meta = {}
        for key in [
            "linked_transcript_id",
            "model",
            "source",
            "node_id",
            "task_generated_by",
        ]:
            if key in context:
                origin_meta[key] = context[key]
        if context.get("input_origin") == "transcription":
            origin_meta.setdefault("source", "voice")
            origin_meta.setdefault("tags", ["auto-generated", "from-transcript"])
        memory_store.save_memory(
            {
                "id": log_entry_id,
                "task": task_id,
                "input": context,
                "output": result,
                "user": context.get("user", "default"),
                "tags": context.get("tags", []),
                "status": status,
            },
            origin=origin_meta or None,
        )
    except Exception:  # noqa: BLE001
        pass
    if status == "success":
        try:
            link_task_to_origin(
                log_entry_id,
                context.get("input_origin") or context.get("source") or "manual",
                origin_meta,
            )
        except Exception:  # noqa: BLE001
            pass
        send_slack_message(f"Task {task_id} completed")
    return result


# Load tasks on import so startup displays them quickly
_load_tasks()
