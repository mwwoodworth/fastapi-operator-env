"""Core task dispatcher for BrainOps Operator."""

from __future__ import annotations

import datetime
from datetime import timezone
import importlib
from loguru import logger
import os
import traceback
import pkgutil
import uuid
from dataclasses import dataclass, field
from typing import Callable, Any, Dict, List

from .memory import memory_store, link_task_to_origin
from utils.slack import send_slack_message
from .integrations.clickup_adapter import create_clickup_task, update_clickup_task
from utils.metrics import (
    TASKS_EXECUTED,
    TASKS_SUCCEEDED,
    TASKS_FAILED,
    TASK_DURATION,
)


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
        description = (
            getattr(module, "TASK_DESCRIPTION", "") or (module.__doc__ or "").strip()
        )
        required = getattr(module, "REQUIRED_FIELDS", [])
        register_task(task_id, func, description, required)


def get_registry() -> Dict[str, TaskDefinition]:
    """Return all discovered tasks."""

    if not _TASK_REGISTRY:
        _load_tasks()
    return _TASK_REGISTRY


def _log_task(task: str, context: dict, result: Any, level: str = "info") -> str:
    """Persist a task log entry to Supabase."""
    entry_id = str(uuid.uuid4())
    entry = {
        "id": entry_id,
        "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
        "task": task,
        "context": context,
        "result": result,
        "retry": context.get("retry", 0),
        "level": level,
    }
    try:
        from supabase_client import supabase

        supabase.table("task_log").insert(entry).execute()
    except Exception:  # noqa: BLE001
        logger.error("Failed to log task entry")
    return entry_id


def _maybe_sync_clickup(task_id: str, context: Dict[str, Any], result: Any) -> None:
    """Create or update a mirrored ClickUp task if context specifies one."""
    list_id = context.get("clickup_list_id")
    if not list_id:
        return
    token = context.get("clickup_token") or os.getenv("CLICKUP_API_TOKEN")
    if not token:
        logger.warning("ClickUp sync skipped: missing token")
        return
    cu_task_id = context.get("clickup_task_id")
    title = context.get("title") or task_id
    description = context.get("description") or ""
    try:
        if cu_task_id:
            update_clickup_task(
                cu_task_id, {"name": title, "description": description, "token": token}
            )
        else:
            res = create_clickup_task(
                {
                    "list_id": list_id,
                    "title": title,
                    "description": description,
                    "token": token,
                }
            )
            if isinstance(res, dict) and res.get("id"):
                context["clickup_task_id"] = res["id"]
    except Exception:  # noqa: BLE001
        logger.exception("ClickUp sync failed")


def run_task(task_id: str, context: Dict[str, Any]) -> Any:
    """Execute a registered task and persist a log entry."""

    registry = get_registry()
    task_def = registry.get(task_id)
    if not task_def:
        raise ValueError(f"Unknown task: {task_id}")
    TASKS_EXECUTED.inc()
    start = datetime.datetime.now(timezone.utc)
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
    duration = (datetime.datetime.now(timezone.utc) - start).total_seconds()
    TASK_DURATION.observe(duration)
    level = "info"
    if isinstance(result, dict) and result.get("error"):
        level = "error"
        TASKS_FAILED.inc()
        send_slack_message(f"Task {task_id} failed: {result.get('error')}")
    log_entry_id = _log_task(task_id, context, result, level=level)
    status = "failed" if level == "error" else "success"
    if status == "success":
        TASKS_SUCCEEDED.inc()
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
        try:
            _maybe_sync_clickup(task_id, context, result)
        except Exception:  # noqa: BLE001
            logger.exception("ClickUp sync hook failed")
        send_slack_message(f"Task {task_id} completed")
    return result


# Load tasks on import so startup displays them quickly
_load_tasks()


async def stream_task(task_id: str, context: Dict[str, Any]):
    """Async generator that streams task output tokens if supported."""
    registry = get_registry()
    task_def = registry.get(task_id)
    if not task_def:
        raise ValueError(f"Unknown task: {task_id}")

    TASKS_EXECUTED.inc()
    start = datetime.datetime.now(timezone.utc)

    module = importlib.import_module(f"codex.tasks.{task_id}")
    stream_func = getattr(module, "stream", None)
    if not stream_func:
        # Fall back to normal execution
        result = run_task(task_id, context)
        yield str(result)
        return

    full = ""
    try:
        async for token in stream_func(context):
            full += token
            yield token
        result: Any = {"output": full}
        level = "info"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Streaming task %s failed", task_id)
        tb = traceback.format_exc()
        result = {"error": str(exc), "stack": tb}
        level = "error"

    duration = (datetime.datetime.now(timezone.utc) - start).total_seconds()
    TASK_DURATION.observe(duration)
    log_entry_id = _log_task(task_id, context, result, level=level)
    status = "failed" if level == "error" else "success"
    if status == "success":
        TASKS_SUCCEEDED.inc()
    else:
        TASKS_FAILED.inc()
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
            _maybe_sync_clickup(task_id, context, result)
        except Exception:  # noqa: BLE001
            logger.exception("ClickUp sync hook failed")
        send_slack_message(f"Task {task_id} completed")
