"""Run a chain of tasks sequentially."""

import logging
from typing import Any, Dict, List

from codex.brainops_operator import run_task
from codex.memory import memory_store

TASK_ID = "multi_task"
TASK_DESCRIPTION = "Run a chain of tasks in order"
REQUIRED_FIELDS = ["tasks"]

logger = logging.getLogger(__name__)


def _resolve_context(ctx: Dict[str, Any], results: List[Dict[str, Any]]) -> Dict[str, Any]:
    ctx = ctx.copy()
    def _token_val(val: Any) -> Any:
        if isinstance(val, str) and val.startswith("{{") and val.endswith("}}"): 
            token = val[2:-2]
            if token.startswith("output_from:"):
                try:
                    idx = int(token.split(":", 1)[1])
                    if 0 <= idx < len(results):
                        prev = results[idx]
                        return (
                            prev.get("completion")
                            or prev.get("result")
                            or str(prev)
                        )
                except Exception:  # noqa: BLE001
                    return val
            if token.startswith("memory:"):
                arg = token.split(":", 1)[1]
                try:
                    limit = 1 if arg == "recent" else int(arg)
                except Exception:
                    limit = 1
                mem = memory_store.fetch_all(limit=limit)
                return "\n".join(
                    str(m.get("output") or m) for m in mem
                )
        return val

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

    fields = ctx.get("fields")
    if isinstance(fields, dict):
        for k, v in list(fields.items()):
            fields[k] = _token_val(v)
        ctx["fields"] = fields

    for k, v in list(ctx.items()):
        if k not in {"fields"}:
            ctx[k] = _token_val(v)
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
