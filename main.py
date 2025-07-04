"""BrainOps Operator FastAPI server."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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


@app.get("/task/inspect/{task_id}")
async def inspect_task(task_id: str) -> Dict[str, Any]:
    entry = memory_store.fetch_one(task_id)
    if not entry:
        raise HTTPException(status_code=404, detail="task not found")
    return entry


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


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


def _parse_cli() -> tuple[str, Dict[str, Any]]:
    import sys

    if len(sys.argv) < 2:
        return "", {}
    task = sys.argv[1]
    if task == "memory" and len(sys.argv) > 2 and sys.argv[2] == "view":
        return "memory_view", {}
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
        result = run_task(cmd, ctx)
        import json

        print(json.dumps(result, indent=2))
