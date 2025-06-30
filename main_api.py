import logging
from logging.handlers import RotatingFileHandler
import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from codex.brainops_operator import run_task
from codex.integrations.make_webhook import router as make_webhook_router

load_dotenv()

LOG_PATH = Path("api.log")
handler = RotatingFileHandler(LOG_PATH, maxBytes=1000000, backupCount=3)
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("brainops.api")

app = FastAPI()
app.include_router(make_webhook_router)

@app.post("/run-task")
async def run_task_endpoint(payload: dict):
    task = payload.get("task")
    context = payload.get("context", {})
    if not task:
        raise HTTPException(status_code=400, detail="'task' is required")

    logger.info("Received task %s", task)
    try:
        result = run_task(task, context)
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

