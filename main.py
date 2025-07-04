"""BrainOps Operator FastAPI server."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from codex import get_registry, run_task
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
