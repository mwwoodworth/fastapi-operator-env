"""BrainOps Operator FastAPI server."""

from __future__ import annotations

import logging
import os
import json
from datetime import datetime
from pathlib import Path
import uuid
import httpx
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request, Header, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from codex.tasks import (
    secrets as secrets_task,
    claude_summarize,
    claude_agent,
    github_push_trigger,
    tana_node_executor,
    claude_prompt,
    gemini_prompt,
)

from codex import get_registry, run_task
from codex.memory import memory_store
from codex.integrations.make_webhook import router as make_webhook_router
from utils.ai_router import get_ai_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brainops.api")

app = FastAPI()
app.include_router(make_webhook_router)


class TanaRequest(BaseModel):
    content: str


class TaskRunRequest(BaseModel):
    task: str
    context: Dict[str, Any] | None = {}


class NLDesignRequest(BaseModel):
    goal: str
    model: str | None = None


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    memory_scope: str | int | None = 5
    stream: bool | None = False


class ChatToTaskRequest(BaseModel):
    message: str
    model: str | None = None
    memory_scope: str | int | None = 5


def _resolve_scope(scope: str | int | None) -> int:
    """Parse memory scope value like 'last_5' into an integer."""
    if scope is None:
        return 5
    if isinstance(scope, int):
        return scope
    if isinstance(scope, str) and scope.startswith("last_"):
        try:
            return int(scope.split("_", 1)[1])
        except Exception:  # noqa: BLE001
            return 5
    try:
        return int(scope)
    except Exception:  # noqa: BLE001
        return 5


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


@app.post("/task/nl-design")
async def nl_design(req: NLDesignRequest) -> Dict[str, Any]:
    context = {"goal": req.goal}
    if req.model:
        context["model"] = req.model
    return run_task("nl_task_designer", context)


@app.post("/chat")
async def chat_endpoint(req: ChatRequest) -> Dict[str, Any]:
    model = req.model or get_ai_model(task="chat")
    scope = _resolve_scope(req.memory_scope)
    mem_text = memory_store.load_recent(scope)
    system_prompt = os.getenv(
        "CHAT_SYSTEM_PROMPT",
        "You are BrainOps Operator, a fast, reliable assistant for project execution.",
    )
    prompt = f"{system_prompt}\n\nRecent memory:\n{mem_text}\nUser: {req.message}\nAssistant:"
    ai_result = (
        claude_prompt.run({"prompt": prompt}) if model == "claude" else gemini_prompt.run({"prompt": prompt})
    )
    completion = ai_result.get("completion", "")

    task_suggestions = run_task(
        "chat_to_prompt",
        {"message": req.message, "model": "claude", "memory_scope": scope},
    )
    suggested = task_suggestions.get("tasks") or task_suggestions.get("generated")

    entry_id = str(uuid.uuid4())
    memory_entry = {
        "id": entry_id,
        "type": "chat",
        "source": "chat",
        "model": model,
        "input": req.message,
        "output": completion,
        "tags": ["chat", "interactive"],
        "timestamp": datetime.utcnow().isoformat(),
    }
    memory_store.save_memory(memory_entry)

    log_path = Path(f"logs/chat_{model}.json")
    history: list[dict[str, Any]] = []
    if log_path.exists():
        try:
            history = json.loads(log_path.read_text())
        except Exception:  # noqa: BLE001
            history = []
    history.append(
        {
            "prompt": prompt,
            "memory": mem_text,
            "result": completion,
            "timestamp": memory_entry["timestamp"],
            "suggested": suggested,
        }
    )
    log_path.write_text(json.dumps(history[-200:], indent=2))

    return {
        "response": completion,
        "model": model,
        "suggested_tasks": suggested,
        "memory_id": entry_id,
    }


@app.post("/chat/to-task")
async def chat_to_task(req: ChatToTaskRequest) -> Dict[str, Any]:
    context = {
        "message": req.message,
        "model": req.model,
        "memory_scope": req.memory_scope,
    }
    return run_task("chat_to_prompt", context)


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


@app.get("/memory/query")
async def memory_query(tags: str = "", limit: int = 10) -> Dict[str, Any]:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    entries = memory_store.query(tag_list, limit=limit)
    return {"entries": entries}


@app.get("/memory/trace/{task_id}")
async def memory_trace(task_id: str) -> Dict[str, Any]:
    entry = memory_store.fetch_one(task_id)
    if not entry:
        return {"error": "not_found"}
    meta = entry.get("metadata") or {}
    return {
        "task": entry.get("task"),
        "triggered_by": meta.get("source"),
        "linked_transcript": meta.get("linked_transcript_id"),
        "linked_node": meta.get("node_id"),
        "executed_by": meta.get("model") or entry.get("output", {}).get("executed_by"),
        "output": entry.get("output"),
    }


@app.get("/chat/history")
async def chat_history(limit: int = 20, model: str | None = None, tags: str = "") -> Dict[str, Any]:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    tag_list.append("chat")
    records = memory_store.query(tag_list, limit=limit)
    if model:
        records = [r for r in records if r.get("model") == model]
    return {"entries": records}


@app.post("/voice/upload")
async def voice_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload an audio file and process it into tasks."""
    upload_dir = Path(os.getenv("VOICE_UPLOAD_DIR", "uploads"))
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename
    with dest.open("wb") as f:
        f.write(await file.read())

    transcribed = run_task("whisper_transcribe", {"audio_path": str(dest)})
    text = transcribed.get("text", "")

    prompt_tasks = run_task(
        "chat_to_prompt",
        {"message": text, "model": "claude", "memory_scope": 5},
    )
    tasks_list = prompt_tasks.get("tasks", [])
    run_result = None
    if tasks_list:
        run_result = run_task(
            "multi_task",
            {
                "tasks": tasks_list,
                "linked_audio": str(dest),
                "linked_transcript_id": dest.stem,
                "model": "claude",
                "source": "voice",
                "input_origin": "transcription",
            },
        )

    entry_id = str(uuid.uuid4())
    transcript_id = dest.stem
    memory_store.save_memory(
        {
            "id": entry_id,
            "task": "voice_upload",
            "input": str(dest),
            "output": {"transcription": text, "tasks": tasks_list, "run_result": run_result},
            "tags": ["voice", "transcription", "mobile"],
            "metadata": {"transcript_id": transcript_id, "processed_by": "Claude"},
        },
        origin={"model": "claude", "source": "voice"},
    )

    try:
        run_task(
            "create_tana_node",
            {
                "content": text,
                "metadata": {
                    "source": "brainops-voice",
                    "transcript_id": transcript_id,
                    "linked_memory_id": entry_id,
                },
            },
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to sync to Tana")

    return {"transcription": text, "tasks": tasks_list, "id": entry_id}


@app.get("/voice/history")
async def voice_history(limit: int = 20) -> Dict[str, Any]:
    records = memory_store.query(["voice"], limit=limit)
    history = []
    for r in records:
        history.append(
            {
                "id": r.get("metadata", {}).get("transcript_id") or r.get("id"),
                "filename": Path(r.get("input", "")).name,
                "transcript": r.get("output", {}).get("transcription", ""),
                "timestamp": r.get("timestamp"),
            }
        )
    return {"entries": history}


@app.get("/voice/trace/{transcript_id}")
async def voice_trace(transcript_id: str) -> Dict[str, Any]:
    limit = int(os.getenv("TRACE_VIEW_LIMIT", 50))
    records = memory_store.fetch_all(limit=1000)
    transcript = ""
    tasks = []
    outputs = []
    executed_by = None
    for r in records:
        meta = r.get("metadata") or {}
        if meta.get("transcript_id") == transcript_id and r.get("task") == "voice_upload":
            transcript = r.get("output", {}).get("transcription", "")
            executed_by = meta.get("processed_by")
        if meta.get("linked_transcript_id") == transcript_id:
            tasks.append(r.get("task"))
            outputs.append(r)
    outputs = outputs[:limit]
    return {
        "transcript": transcript,
        "tasks_triggered": tasks,
        "memory_outputs": outputs,
        "executed_by": executed_by,
    }


@app.get("/voice/status")
async def voice_status() -> Dict[str, Any]:
    records = memory_store.query(["voice"], limit=1)
    if not records:
        return {
            "latest_transcript": "",
            "task_executed": False,
            "memory_link": None,
            "execution_status": "none",
            "processed_by": None,
        }
    r = records[-1]
    transcript = r.get("output", {}).get("transcription", "")
    executed = bool(r.get("output", {}).get("run_result"))
    status = "success"
    result = r.get("output", {}).get("run_result")
    if isinstance(result, dict) and result.get("error"):
        status = "error"
    processed = r.get("metadata", {}).get("processed_by", "Claude")
    return {
        "latest_transcript": transcript,
        "task_executed": executed,
        "memory_link": r.get("id"),
        "execution_status": status,
        "processed_by": processed,
    }


class StatusUpdate(BaseModel):
    task_id: str
    status: str
    message: str
    timestamp: str | None = None


@app.post("/webhook/status-update")
async def status_update(req: StatusUpdate) -> Dict[str, Any]:
    entry = req.dict()
    entry["tags"] = ["status_update"]
    memory_store.save_memory(entry)

    try:
        orig = memory_store.fetch_one(req.task_id)
        node_id = orig.get("metadata", {}).get("node_id") if orig else None
        if node_id and os.getenv("TANA_NODE_CALLBACK"):
            headers = {}
            if os.getenv("TANA_API_KEY"):
                headers["Authorization"] = f"Bearer {os.getenv('TANA_API_KEY')}"
            httpx.post(
                "https://europe-west1.api.tana.inc/update/node",
                json={"id": node_id, "content": req.message},
                headers=headers,
                timeout=10,
            )
            memory_store.save_memory(
                {
                    "task": "tana_callback",
                    "input": entry,
                    "output": {"node_id": node_id},
                    "tags": ["feedback-returned"],
                    "metadata": {"source": "tana-exec-sync", "node_id": node_id},
                }
            )
    except Exception:  # noqa: BLE001
        logger.exception("Tana callback failed")

    return {"status": "logged"}


@app.post("/optimize/flow")
async def optimize_flow(req: dict) -> Dict[str, Any]:
    history = req.get("history")
    result = run_task("gemini_optimize_taskflow", {"history": history})
    return result


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
