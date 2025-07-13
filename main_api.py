from loguru import logger
import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from codex import brainops_operator
from codex.integrations.make_webhook import router as make_webhook_router

load_dotenv()

LOG_PATH = Path("api.log")
logger.add(LOG_PATH, rotation=1_000_000, serialize=True)

app = FastAPI()
app.include_router(make_webhook_router)


class TanaCreateRequest(BaseModel):
    content: str
    tags: Optional[List[str]] = []
    fields: Optional[Dict[str, str]] = {}
    children: Optional[List[str]] = []


@app.post("/tana/create-node")
async def create_tana_node(req: TanaCreateRequest):
    context = {
        "content": req.content,
        "tags": req.tags,
        "fields": req.fields,
        "children": req.children,
    }
    brainops_operator.run_task("create_tana_node", context)
    return {"status": "submitted", "payload": context}


@app.post("/tana/from-assistant")
async def tana_from_assistant(req: Request):
    payload = await req.json()
    brainops_operator.run_task("create_tana_node", payload)
    return {"status": "assistant_note_received"}


@app.post("/run-task")
async def run_task_endpoint(payload: dict):
    task = payload.get("task")
    context = payload.get("context", {})
    if not task:
        raise HTTPException(status_code=400, detail="'task' is required")

    logger.info("Received task %s", task)
    try:
        result = brainops_operator.run_task(task, context)
        record = {"status": "success", "result": result}
        _log_history(task, context, record)
        return JSONResponse(record)
    except Exception as exc:
        logger.exception("Task execution failed")
        record = {"status": "error", "message": str(exc)}
        _log_history(task, context, record)
        raise HTTPException(status_code=500, detail=str(exc))


def _log_history(task: str, context: dict, result: dict):
    """Append execution info to ai_task_log.json (max 50 records)."""
    log_file = Path("ai_task_log.json")
    entry = {"task": task, "context": context, "result": result}
    history = []
    if log_file.exists():
        try:
            history = json.loads(log_file.read_text())
        except Exception:
            history = []
    history.append(entry)
    log_file.write_text(json.dumps(history[-50:], indent=2))
