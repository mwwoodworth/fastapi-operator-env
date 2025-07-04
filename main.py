"""BrainOps Operator FastAPI server."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from codex.tasks import (
    secrets as secrets_task,
    claude_summarize,
    claude_agent,
    github_push_trigger,
    tana_node_executor,
)

from codex import get_registry, run_task
from codex.memory import memory_store
from codex.integrations.make_webhook import router as make_webhook_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brainops.api")

app = FastAPI()
app.include_router(make_webhook_router)


class TanaRequest(BaseModel):
    content: str


class TaskRunRequest(BaseModel):
    task: str
    context: Dict[str, Any] | None = {}


@app.on_event("startup")
async def startup_event() -> None:
    required = [
        "TANA_API_KEY",
        "SUPABASE_SERVICE_KEY",
        "VERCEL_TOKEN",
        "OPENAI_API_KEY",
        "STRIPE_SECRET_KEY",
    ]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        logger.warning("Missing env vars: %s", ", ".join(missing))
    tasks = ", ".join(get_registry().keys())
    logger.info("Available tasks: %s", tasks)


@app.post("/tana/create-node")
async def create_tana_node(req: TanaRequest) -> Dict[str, Any]:
    run_task("create_tana_node", {"content": req.content})
    return {"status": "submitted", "content": req.content}


@app.post("/task/run")
async def task_run(req: TaskRunRequest) -> JSONResponse:
    try:
        result = run_task(req.task, req.context or {})
        return JSONResponse({"status": "success", "result": result})
    except Exception as exc:  # noqa: BLE001
        logger.exception("Task execution failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/task/generate")
async def generate_task(req: dict) -> Dict[str, Any]:
    return claude_agent.run(req)


@app.post("/task/webhook")
async def webhook_trigger(req: dict) -> Dict[str, Any]:
    task = req.get("task")
    context = req.get("context", {})
    result = run_task(task, context)
    return {"status": "success", "result": result}


@app.post("/webhook/github")
async def github_webhook(request: Request, x_hub_signature_256: str | None = Header(default=None)) -> Dict[str, Any]:
    payload = await request.json()
    raw = await request.body()
    result = github_push_trigger.run({"payload": payload, "signature": x_hub_signature_256, "raw_body": raw})
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/task/inspect/{task_id}")
async def inspect_task(task_id: str) -> Dict[str, Any]:
    entry = memory_store.fetch_one(task_id)
    log_entry = None
    try:
        from pathlib import Path
        import json

        log_file = Path("logs/task_log.json")
        if log_file.exists():
            history = json.loads(log_file.read_text())
            for item in history:
                if item.get("id") == task_id:
                    log_entry = item
                    break
    except Exception:  # noqa: BLE001
        log_entry = None
    if not entry and not log_entry:
        raise HTTPException(status_code=404, detail="task not found")
    return {"memory": entry, "log": log_entry}


@app.get("/docs/registry")
async def docs_registry() -> Dict[str, Any]:
    registry = {
        key: {
            "description": value.description,
            "required_fields": value.required_fields,
        }
        for key, value in get_registry().items()
    }
    return registry


@app.post("/secrets/store")
async def store_secret_api(req: dict):
    secrets_task.store_secret(req["name"], req["value"])
    return {"status": "stored"}


@app.get("/secrets/retrieve/{name}")
async def retrieve_secret_api(name: str):
    val = secrets_task.retrieve_secret(name)
    return {"value": val}


@app.delete("/secrets/delete/{name}")
async def delete_secret_api(name: str):
    secrets_task.delete_secret(name)
    return {"status": "deleted"}


@app.get("/secrets/list")
async def list_secrets_api():
    return {"secrets": secrets_task.list_secrets()}


@app.get("/memory/summary")
async def memory_summary() -> Dict[str, Any]:
    return claude_summarize.run({})


@app.get("/dashboard/status")
async def dashboard_status() -> Dict[str, Any]:
    tasks_count = len(get_registry())
    memory_count = memory_store.count_entries()
    pending = 0
    last_success = None
    try:
        from supabase_client import supabase

        res = supabase.table("retry_queue").select("id").eq("status", "pending").execute()
        pending = len(res.data or [])
    except Exception:  # noqa: BLE001
        pending = 0
    try:
        from pathlib import Path
        import json

        log_file = Path("logs/task_log.json")
        if log_file.exists():
            history = json.loads(log_file.read_text())
            for item in reversed(history):
                if not isinstance(item.get("result"), dict) or not item["result"].get("error"):
                    last_success = item.get("timestamp")
                    break
    except Exception:  # noqa: BLE001
        last_success = None
    return {
        "tasks_registered": tasks_count,
        "memory_entries": memory_count,
        "pending_retries": pending,
        "last_successful_task": last_success,
    }


@app.get("/diagnostics/state")
async def diagnostics_state() -> Dict[str, Any]:
    active_tasks = 0
    retry_queue = 0
    last_summary = None
    last_tana_push = None
    try:
        from supabase_client import supabase

        res = supabase.table("task_queue").select("id").eq("status", "pending").execute()
        active_tasks = len(res.data or [])
        rq = supabase.table("retry_queue").select("id").eq("status", "pending").execute()
        retry_queue = len(rq.data or [])
    except Exception:  # noqa: BLE001
        active_tasks = 0
        retry_queue = 0
    for item in reversed(memory_store.fetch_all(limit=20)):
        if item.get("task") == "claude_memory_agent" or item.get("task") == "gemini_memory_agent":
            last_summary = item.get("timestamp")
            break
    for item in reversed(memory_store.fetch_all(limit=50)):
        if item.get("task") == "create_tana_node":
            last_tana_push = item.get("timestamp")
            break
    secrets_loaded = [s for s in ["CLAUDE_API_KEY", "TANA_API_KEY"] if os.getenv(s)]
    return {
        "active_tasks": active_tasks,
        "last_memory_summary": last_summary,
        "retry_queue": retry_queue,
        "secrets_loaded": secrets_loaded,
        "last_successful_tana_push": last_tana_push,
    }


@app.get("/tana/scan")
async def tana_scan() -> Dict[str, Any]:
    return tana_node_executor.run({})


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


def _parse_cli() -> tuple[str, Dict[str, Any]]:
    import sys

    if len(sys.argv) < 2:
        return "", {}
    task = sys.argv[1]
    if task == "task" and len(sys.argv) >= 4 and sys.argv[2] == "run":
        import json as _json

        try:
            payload = _json.loads(sys.argv[3])
        except Exception:  # noqa: BLE001
            return "", {}
        return payload.get("task", ""), payload.get("context", {})
    if task == "memory" and len(sys.argv) > 2:
        sub = sys.argv[2]
        if sub == "view":
            return "memory_view", {}
        if sub == "summarize":
            return "claude_memory_agent", {}
    if task == "retry" and len(sys.argv) > 2 and sys.argv[2] == "queue":
        return "retry_queue", {}
    if task == "secrets" and len(sys.argv) > 2:
        action = sys.argv[2]
        if action == "store" and len(sys.argv) >= 5:
            return "secrets", {
                "action": "store",
                "name": sys.argv[3],
                "value": sys.argv[4],
            }
        if action in {"retrieve", "delete"} and len(sys.argv) >= 4:
            return "secrets", {"action": action, "name": sys.argv[3]}
        if action == "list":
            return "secrets", {"action": "list"}
    context: Dict[str, Any] = {}
    args = sys.argv[2:]
    key = None
    for arg in args:
        if arg.startswith("--"):
            key = arg[2:]
            context[key] = ""
        elif key:
            context[key] = arg
            key = None
    return task, context


if __name__ == "__main__":
    cmd, ctx = _parse_cli()
    if cmd == "memory_view":
        import json

        entries = memory_store.fetch_all()
        print(json.dumps(entries, indent=2))
    elif cmd:
        if cmd == "retry_queue":
            from scripts.runner import check_retry_queue

            check_retry_queue()
            print("retry queue processed")
        else:
            result = run_task(cmd, ctx)
            import json

            print(json.dumps(result, indent=2))
