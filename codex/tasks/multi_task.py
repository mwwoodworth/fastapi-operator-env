"""Run a chain of tasks sequentially."""

import logging
from typing import Any, Dict, List

from codex.brainops_operator import run_task

TASK_ID = "multi_task"
TASK_DESCRIPTION = "Run a chain of tasks in order"
REQUIRED_FIELDS = ["tasks"]

logger = logging.getLogger(__name__)


def _resolve_context(ctx: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    ctx = ctx.copy()
    if "content_from" in ctx:
        idx = ctx.pop("content_from")
        if 0 <= idx < len(results):
            prev = results[idx]
            value = (
                prev.get("completion")
                or prev.get("result")
                or str(prev)
            )
            ctx["content"] = value
    if "output_from" in ctx:
        idx = ctx.pop("output_from")
        if 0 <= idx < len(results):
            ctx["output"] = results[idx]
    return ctx


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    tasks = context.get("tasks") or []
    if not isinstance(tasks, list) or not tasks:
        return {"error": "tasks must be a non-empty list"}

    results: List[Any] = []
    for task_def in tasks:
        task_id = task_def.get("task")
        task_ctx = task_def.get("context", {})
        task_ctx = _resolve_context(task_ctx, results)
        result = run_task(task_id, task_ctx)
        results.append(result)
    return {"results": results}
