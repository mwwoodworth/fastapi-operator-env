"""Core task dispatcher for BrainOps Operator."""

from __future__ import annotations

import datetime
import importlib
import json
import logging
import pkgutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any, Dict, List

logger = logging.getLogger(__name__)

_LOG_FILE = Path("logs/task_log.json")


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
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "task": task,
        "context": context,
        "result": result,
    }
    history: List[dict] = []
    if _LOG_FILE.exists():
        try:
            history = json.loads(_LOG_FILE.read_text())
        except Exception:  # noqa: BLE001
            history = []
    history.append(entry)
    _LOG_FILE.write_text(json.dumps(history[-100:], indent=2))


def run_task(task_id: str, context: Dict[str, Any]) -> Any:
    """Execute a registered task and persist a log entry."""

    registry = get_registry()
    task_def = registry.get(task_id)
    if not task_def:
        raise ValueError(f"Unknown task: {task_id}")
    result = task_def.func(context)
    _log_task(task_id, context, result)
    return result


# Load tasks on import so startup displays them quickly
_load_tasks()
