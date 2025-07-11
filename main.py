"""BrainOps Operator FastAPI server."""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
import uuid
import httpx
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request, Header, UploadFile, File, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets as pysecrets
from pydantic import BaseModel
from utils.slack import send_slack_message
from db.session import init_db
from core.settings import Settings

settings = Settings()

from codex.tasks import (
    secrets as secrets_task,
    claude_summarize,
    claude_agent,
    github_push_trigger,
    tana_node_executor,
    claude_prompt,
    gemini_prompt,
    recurring_task_engine,
    task_rescheduler,
    weekly_priority_review,
)

from codex import get_registry, run_task
from codex.memory import memory_store, agent_inbox
from codex.integrations.make_webhook import router as make_webhook_router
from codex.memory.memory_api import router as memory_api_router
from codex.ai.gemini_webhook import router as gemini_webhook_router
from chat_task_api import router as chat_task_router
import codex.ai.claude_sync as claude_sync
from utils.ai_router import get_ai_model
from claude_utils import stream_claude
from gpt_utils import stream_gpt
from response_models import (
    ChatResponse,
    TaskRunResponse,
    MemoryEntriesResponse,
    VoiceHistoryResponse,
    VoiceTraceResponse,
    VoiceStatusResponse,
    MemoryTraceResponse,
    TanaNodeCreateResponse,
    StatusResponse,
    ValueResponse,
    VoiceUploadResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("brainops.api")

security = HTTPBasic(auto_error=False)
USERS = {}
ADMIN_USERS: set[str] = set()

if settings.BASIC_AUTH_USERS:
    try:
        USERS = json.loads(settings.BASIC_AUTH_USERS)
    except Exception:  # noqa: BLE001
        USERS = {}
ADMIN_USERS = set((settings.ADMIN_USERS or "").split(","))


def get_current_user(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    if not USERS:
        return "anonymous"
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    correct_password = USERS.get(credentials.username)
    if not correct_password or not pysecrets.compare_digest(
        credentials.password, correct_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def require_admin(user: str = Depends(get_current_user)) -> str:
    if USERS and user not in ADMIN_USERS:
        raise HTTPException(status_code=403, detail="not authorized")
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = ", ".join(get_registry().keys())
    logger.info("Available tasks: %s", tasks)
    init_db()
    app.state.settings = settings
    yield


app = FastAPI(lifespan=lifespan, dependencies=[Depends(get_current_user)])
app.include_router(make_webhook_router)
app.include_router(memory_api_router)
app.include_router(gemini_webhook_router)
app.include_router(chat_task_router)

# Serve dashboard with authentication
dashboard_app = FastAPI(dependencies=[Depends(get_current_user)])
dashboard_app.mount(
    "/", StaticFiles(directory="static/dashboard", html=True), name="dashboard"
)
app.mount("/dashboard/ui", dashboard_app)

# Expose static assets like manifest and icons
app.mount("/static", StaticFiles(directory="static"), name="static")


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


class KnowledgeQueryRequest(BaseModel):
    query: str
    sources: list[str] | None = None
    model: str | None = None


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


@app.post("/tana/create-node", response_model=TanaNodeCreateResponse)
async def create_tana_node(req: TanaRequest) -> TanaNodeCreateResponse:
    """Create a note in Tana from the provided content."""
    run_task("create_tana_node", {"content": req.content})
    return TanaNodeCreateResponse(status="submitted", content=req.content)


@app.post("/task/run", response_model=TaskRunResponse)
async def task_run(req: TaskRunRequest) -> TaskRunResponse:
    try:
        result = run_task(req.task, req.context or {})
        return TaskRunResponse(status="success", result=result)
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


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    model = req.model or get_ai_model(task="chat")
    scope = _resolve_scope(req.memory_scope)
    mem_text = memory_store.load_recent(scope)
    system_prompt = settings.CHAT_SYSTEM_PROMPT
    prompt = f"{system_prompt}\n\nRecent memory:\n{mem_text}\nUser: {req.message}\nAssistant:"

    if req.stream:
        async def event_generator():
            """Async generator yielding SSE tokens."""
            full = ""
            try:
                gen = stream_claude(prompt) if model == "claude" else stream_gpt(prompt)
                async for token in gen:
                    full += token
                    # Send each token as a SSE data chunk
                    yield f"data: {token}\n\n"
            finally:
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
                    "output": full,
                    "tags": ["chat", "interactive"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
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
                        "result": full,
                        "timestamp": memory_entry["timestamp"],
                        "suggested": suggested,
                    }
                )
                log_path.write_text(json.dumps(history[-200:], indent=2))

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    ai_result = (
        claude_prompt.run({"prompt": prompt})
        if model == "claude"
        else gemini_prompt.run({"prompt": prompt})
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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

    return ChatResponse(
        response=completion,
        model=model,
        suggested_tasks=suggested,
        memory_id=entry_id,
    )


@app.post("/chat/to-task")
async def chat_to_task(req: ChatToTaskRequest) -> Dict[str, Any]:
    context = {
        "message": req.message,
        "model": req.model,
        "memory_scope": req.memory_scope,
    }
    return run_task("chat_to_prompt", context)


@app.post("/task/webhook", response_model=TaskRunResponse)
async def webhook_trigger(req: dict) -> TaskRunResponse:
    task = req.get("task")
    context = req.get("context", {})
    result = run_task(task, context)
    return TaskRunResponse(status="success", result=result)


@app.post("/webhook/github")
async def github_webhook(
    request: Request, x_hub_signature_256: str | None = Header(default=None)
) -> Dict[str, Any]:
    payload = await request.json()
    raw = await request.body()
    result = github_push_trigger.run(
        {"payload": payload, "signature": x_hub_signature_256, "raw_body": raw}
    )
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


@app.post("/secrets/store", response_model=StatusResponse)
async def store_secret_api(req: dict, _: str = Depends(require_admin)) -> StatusResponse:
    secrets_task.store_secret(req["name"], req["value"])
    return StatusResponse(status="stored")


@app.get("/secrets/retrieve/{name}", response_model=ValueResponse)
async def retrieve_secret_api(name: str, _: str = Depends(require_admin)) -> ValueResponse:
    val = secrets_task.retrieve_secret(name)
    return ValueResponse(value=val)


@app.delete("/secrets/delete/{name}", response_model=StatusResponse)
async def delete_secret_api(name: str, _: str = Depends(require_admin)) -> StatusResponse:
    secrets_task.delete_secret(name)
    return StatusResponse(status="deleted")


@app.get("/secrets/list")
async def list_secrets_api(_: str = Depends(require_admin)):
    return {"secrets": secrets_task.list_secrets()}


@app.get("/memory/summary")
async def memory_summary() -> Dict[str, Any]:
    return claude_summarize.run({})


@app.get("/memory/query", response_model=MemoryEntriesResponse)
async def memory_query(tags: str = "", limit: int = 10) -> MemoryEntriesResponse:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    entries = memory_store.query(tag_list, limit=limit)
    return MemoryEntriesResponse(entries=entries)


@app.get("/memory/search", response_model=MemoryEntriesResponse)
async def memory_search(
    q: str = "",
    tags: str = "",
    start: str | None = None,
    end: str | None = None,
    user: str | None = None,
    limit: int = 20,
) -> MemoryEntriesResponse:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    results = memory_store.search(q, tag_list, start, end, user, limit)
    return MemoryEntriesResponse(entries=results)


@app.post("/knowledge/index")
async def knowledge_index() -> Dict[str, Any]:
    from codex.memory import doc_indexer

    docs = doc_indexer.index_documents()
    return {"indexed": len(docs)}


@app.post("/knowledge/query")
async def knowledge_query(req: KnowledgeQueryRequest) -> Dict[str, Any]:
    context = {
        "query": req.query,
        "sources": req.sources,
        "model": req.model,
    }
    return run_task("unified_rag_agent", context)


@app.get("/knowledge/sources")
async def knowledge_sources() -> Dict[str, Any]:
    from codex.memory import doc_indexer

    return {"docs": doc_indexer.list_sources()}


@app.get("/logs/rag", response_model=MemoryEntriesResponse)
async def rag_logs(limit: int = 20) -> MemoryEntriesResponse:
    from utils import rag_logger

    return MemoryEntriesResponse(entries=rag_logger.load_logs(limit))


@app.get("/logs/errors", response_model=MemoryEntriesResponse)
async def error_logs(limit: int = 50) -> MemoryEntriesResponse:
    """Return recent error log entries."""
    error_file = Path("logs/error_log.json")
    entries: List[Dict[str, Any]] = []
    if error_file.exists():
        try:
            entries = json.loads(error_file.read_text())[-limit:]
        except Exception:  # noqa: BLE001
            entries = []
    return MemoryEntriesResponse(entries=entries)


class FeedbackReport(BaseModel):
    message: str
    page: str | None = None


@app.post("/feedback/report", response_model=StatusResponse)
async def feedback_report(
    req: FeedbackReport, user: str = Depends(get_current_user)
) -> StatusResponse:
    entry = {
        "task": "user_feedback",
        "input": {"message": req.message, "page": req.page},
        "user": user,
        "tags": ["feedback"],
    }
    memory_store.save_memory(entry)
    send_slack_message(f"Feedback from {user}: {req.message}")
    return StatusResponse(status="received")


@app.get("/memory/trace/{task_id}", response_model=MemoryTraceResponse)
async def memory_trace(task_id: str) -> MemoryTraceResponse:
    entry = memory_store.fetch_one(task_id)
    if not entry:
        return MemoryTraceResponse()
    meta = entry.get("metadata") or {}
    return MemoryTraceResponse(
        task=entry.get("task"),
        triggered_by=meta.get("source"),
        linked_transcript=meta.get("linked_transcript_id"),
        linked_node=meta.get("node_id"),
        executed_by=meta.get("model") or entry.get("output", {}).get("executed_by"),
        output=entry.get("output"),
    )


@app.get("/chat/history", response_model=MemoryEntriesResponse)
async def chat_history(
    limit: int = 20, model: str | None = None, tags: str = ""
) -> MemoryEntriesResponse:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    tag_list.append("chat")
    records = memory_store.query(tag_list, limit=limit)
    if model:
        records = [r for r in records if r.get("model") == model]
    return MemoryEntriesResponse(entries=records)


@app.post("/voice/upload", response_model=VoiceUploadResponse)
async def voice_upload(file: UploadFile = File(...)) -> VoiceUploadResponse:
    """Upload an audio file and process it into tasks."""
    upload_dir = Path(settings.VOICE_UPLOAD_DIR)
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
        from codex.memory import agent_inbox

        for task in tasks_list:
            agent_inbox.add_to_inbox(task.get("task"), task.get("context", {}), "voice")

    entry_id = str(uuid.uuid4())
    transcript_id = dest.stem
    memory_store.save_memory(
        {
            "id": entry_id,
            "task": "voice_upload",
            "input": str(dest),
            "output": {
                "transcription": text,
                "tasks": tasks_list,
                "run_result": run_result,
            },
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

    return VoiceUploadResponse(transcription=text, tasks=tasks_list, id=entry_id)


@app.get("/voice/history", response_model=VoiceHistoryResponse)
async def voice_history(limit: int = 20) -> VoiceHistoryResponse:
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
    return VoiceHistoryResponse(entries=history)


@app.get("/voice/trace/{transcript_id}", response_model=VoiceTraceResponse)
async def voice_trace(transcript_id: str) -> VoiceTraceResponse:
    limit = settings.TRACE_VIEW_LIMIT
    records = memory_store.fetch_all(limit=1000)
    transcript = ""
    tasks = []
    outputs = []
    executed_by = None
    for r in records:
        meta = r.get("metadata") or {}
        if (
            meta.get("transcript_id") == transcript_id
            and r.get("task") == "voice_upload"
        ):
            transcript = r.get("output", {}).get("transcription", "")
            executed_by = meta.get("processed_by")
        if meta.get("linked_transcript_id") == transcript_id:
            tasks.append(r.get("task"))
            outputs.append(r)
    outputs = outputs[:limit]
    return VoiceTraceResponse(
        transcript=transcript,
        tasks_triggered=tasks,
        memory_outputs=outputs,
        executed_by=executed_by,
    )


@app.get("/voice/status", response_model=VoiceStatusResponse)
async def voice_status() -> VoiceStatusResponse:
    records = memory_store.query(["voice"], limit=1)
    if not records:
        return VoiceStatusResponse(
            latest_transcript="",
            task_executed=False,
            memory_link=None,
            execution_status="none",
            processed_by=None,
        )
    r = records[-1]
    transcript = r.get("output", {}).get("transcription", "")
    executed = bool(r.get("output", {}).get("run_result"))
    status = "success"
    result = r.get("output", {}).get("run_result")
    if isinstance(result, dict) and result.get("error"):
        status = "error"
    processed = r.get("metadata", {}).get("processed_by", "Claude")
    return VoiceStatusResponse(
        latest_transcript=transcript,
        task_executed=executed,
        memory_link=r.get("id"),
        execution_status=status,
        processed_by=processed,
    )


class StatusUpdate(BaseModel):
    task_id: str
    status: str
    message: str
    timestamp: str | None = None


@app.post("/webhook/status-update", response_model=StatusResponse)
async def status_update(req: StatusUpdate) -> StatusResponse:
    entry = req.dict()
    entry["tags"] = ["status_update"]
    memory_store.save_memory(entry)

    try:
        orig = memory_store.fetch_one(req.task_id)
        node_id = orig.get("metadata", {}).get("node_id") if orig else None
        if node_id and settings.TANA_NODE_CALLBACK:
            headers = {}
            if settings.TANA_API_KEY:
                headers["Authorization"] = f"Bearer {settings.TANA_API_KEY}"
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

    return StatusResponse(status="logged")


class InboxDecision(BaseModel):
    task_id: str
    decision: str
    notes: str | None = ""
    edit_context: Dict[str, Any] | None = None


class DelayRequest(BaseModel):
    task_id: str
    delay_until: str
    note: str | None = ""
    fallback: str | None = "notify"


@app.get("/agent/inbox")
async def agent_inbox_view(limit: int = 10) -> List[Dict[str, Any]]:
    return agent_inbox.get_pending_tasks(limit)


@app.post("/agent/inbox/approve", response_model=TaskRunResponse)
async def agent_inbox_approve(req: InboxDecision) -> TaskRunResponse:
    item = agent_inbox.get_task(req.task_id)
    if not item:
        raise HTTPException(status_code=404, detail="not_found")
    if req.decision == "approve":
        context = req.edit_context or item.get("context", {})
        result = run_task(item["task_id"], context)
        agent_inbox.mark_as_resolved(req.task_id, "approved", req.notes or "")
        return TaskRunResponse(status="approved", result=result)
    if req.decision == "reject":
        agent_inbox.mark_as_resolved(req.task_id, "rejected", req.notes or "")
        return TaskRunResponse(status="rejected", result=None)
    if req.decision == "edit":
        context = req.edit_context or item.get("context", {})
        result = run_task(item["task_id"], context)
        agent_inbox.mark_as_resolved(req.task_id, "edited", req.notes or "")
        return TaskRunResponse(status="edited", result=result)
    raise HTTPException(status_code=400, detail="invalid_decision")


@app.post("/agent/inbox/delay", response_model=StatusResponse)
async def agent_inbox_delay(req: DelayRequest) -> StatusResponse:
    item = agent_inbox.get_task(req.task_id)
    if not item:
        raise HTTPException(status_code=404, detail="not_found")
    task_rescheduler.record_delay(req.task_id, req.delay_until, req.note, req.fallback)
    return StatusResponse(status="delayed")


@app.get("/agent/inbox/summary")
async def agent_inbox_summary() -> Dict[str, Any]:
    return agent_inbox.get_summary()


@app.post("/agent/plan/daily")
async def agent_daily_plan() -> Dict[str, Any]:
    return run_task("claude_calendar_planner", {})


@app.post("/agent/inbox/prioritize")
async def agent_inbox_prioritize() -> Dict[str, Any]:
    return run_task("inbox_prioritizer", {})


@app.get("/agent/inbox/mobile")
async def agent_inbox_mobile() -> Dict[str, Any]:
    tasks = agent_inbox.get_pending_tasks(10)
    counts: Dict[str, int] = {}
    for t in tasks:
        origin = t.get("origin", "other")
        counts[origin] = counts.get(origin, 0) + 1
    summary_parts = [f"{v} {k}" for k, v in counts.items()]
    summary = f"{len(tasks)} items pending. " + ", ".join(summary_parts)
    top = tasks[0] if tasks else {}
    return {
        "summary": summary,
        "top_task": {
            "task_id": top.get("task_id"),
            "summary": (top.get("summary") or {}).get("summary"),
        },
    }


@app.post("/optimize/flow")
async def optimize_flow(req: dict) -> Dict[str, Any]:
    history = req.get("history")
    result = run_task("gemini_optimize_taskflow", {"history": history})
    return result


@app.post("/memory/sync/agents")
async def memory_sync_agents() -> Dict[str, Any]:
    return run_task("memory_sync_agent", {})


class MemoryDiffRequest(BaseModel):
    task_id: str


@app.post("/memory/audit/diff")
async def memory_audit_diff(req: MemoryDiffRequest) -> Dict[str, Any]:
    return run_task("memory_diff_checker", req.dict())


class CoAuthorRequest(BaseModel):
    intent: str


@app.post("/task/ai-coauthor")
async def task_ai_coauthor(req: CoAuthorRequest) -> Dict[str, Any]:
    return run_task("ai_coauthored_composer", req.dict())


@app.post("/agent/workflows/audit")
async def workflows_audit() -> Dict[str, Any]:
    return run_task("workflow_audit_agent", {})


@app.post("/agent/forecast/weekly")
async def agent_forecast_weekly(req: dict | None = None) -> Dict[str, Any]:
    context = req or {"goal": "Optimize AI pipeline delivery over the next 7 days"}
    return run_task("strategy_forecaster", context)


@app.get("/dashboard/forecast")
async def dashboard_forecast() -> Dict[str, Any]:
    return run_task("timeline_builder", {})


@app.post("/agent/strategy/weekly")
async def agent_strategy_weekly() -> Dict[str, Any]:
    return run_task("claude_strategy_agent", {})


class DependencyMapRequest(BaseModel):
    tasks: List[Dict[str, Any]]


@app.post("/task/dependency-map")
async def task_dependency_map(req: DependencyMapRequest) -> Dict[str, Any]:
    return run_task("gemini_dependency_map", {"tasks": req.tasks})


class MobileTask(BaseModel):
    voice_message: str


class RecurringTask(BaseModel):
    task: str
    context: Dict[str, Any] | None = {}
    frequency: str
    day: str | None = None
    time: str
    enabled: bool | None = True


@app.post("/mobile/task")
async def mobile_task(req: MobileTask) -> Dict[str, Any]:
    message = req.voice_message
    prompt_result = run_task(
        "chat_to_prompt",
        {"message": message, "model": "claude", "memory_scope": 5},
    )
    tasks = prompt_result.get("tasks") or []
    queued: List[Dict[str, Any]] = []
    for t in tasks:
        queued.append(
            agent_inbox.add_to_inbox(t.get("task"), t.get("context", {}), "mobile")
        )
    return {
        "task_id": [q.get("task_id") for q in queued],
        "summary": [q.get("summary") for q in queued],
    }


@app.get("/agent/recurring")
async def get_recurring() -> List[Dict[str, Any]]:
    return recurring_task_engine.get_recurring_tasks()


@app.post("/agent/recurring/add")
async def add_recurring(req: RecurringTask) -> Dict[str, Any]:
    entry = recurring_task_engine.add_recurring_task(req.dict())
    return {"added": entry}


@app.get("/dashboard/status")
async def dashboard_status() -> Dict[str, Any]:
    tasks_count = len(get_registry())
    memory_count = memory_store.count_entries()
    pending = 0
    last_success = None
    try:
        from supabase_client import supabase

        res = (
            supabase.table("retry_queue").select("id").eq("status", "pending").execute()
        )
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
                if not isinstance(item.get("result"), dict) or not item["result"].get(
                    "error"
                ):
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


@app.get("/dashboard/tasks")
async def dashboard_tasks() -> Dict[str, Any]:
    pending = len(agent_inbox.get_pending_tasks(100))
    recurring_enabled = len(
        [
            t
            for t in recurring_task_engine.get_recurring_tasks()
            if t.get("enabled", True)
        ]
    )
    delayed = len(
        [t for t in agent_inbox.get_pending_tasks(100) if t.get("delay_until")]
    )
    last_review = weekly_priority_review.get_last_review_time()
    return {
        "pending": pending,
        "recurring_enabled": recurring_enabled,
        "delayed_tasks": delayed,
        "last_priority_review": last_review,
    }


@app.get("/dashboard/full")
async def dashboard_full() -> Dict[str, Any]:
    base = dashboard_status()
    inbox = agent_inbox.get_summary()
    supabase_status = bool(settings.SUPABASE_URL)
    last_entry = memory_store.fetch_all(limit=1)
    last_model = None
    if last_entry:
        last_model = last_entry[0].get("metadata", {}).get("model")
    base.update(
        {
            "inbox": inbox,
            "last_model": last_model,
            "supabase": supabase_status,
        }
    )
    return base


@app.get("/dashboard/metrics")
async def dashboard_metrics() -> Dict[str, Any]:
    """Return basic counts from log files."""
    log_file = Path("logs/task_log.json")
    tasks_logged = 0
    unique_tasks = 0
    last_task = None
    if log_file.exists():
        try:
            data = json.loads(log_file.read_text())
            tasks_logged = len(data)
            unique_tasks = len({d.get("task") for d in data})
            if data:
                last_task = data[-1].get("timestamp")
        except Exception:  # noqa: BLE001
            pass
    error_file = Path("logs/error_log.json")
    errors = 0
    if error_file.exists():
        try:
            errors = len(json.loads(error_file.read_text()))
        except Exception:  # noqa: BLE001
            errors = 0
    mem_count = memory_store.count_entries()
    last_mem_time = None
    records = memory_store.fetch_all(limit=1)
    if records:
        last_mem_time = records[0].get("timestamp")
    return {
        "tasks_logged": tasks_logged,
        "unique_tasks": unique_tasks,
        "errors_logged": errors,
        "memory_entries": mem_count,
        "last_task_time": last_task,
        "last_memory_time": last_mem_time,
    }


@app.get("/dashboard/sync")
async def dashboard_sync() -> Dict[str, Any]:
    records = memory_store.fetch_all(limit=200)
    syncs = len([r for r in records if r.get("task") == "memory_sync_agent"])
    coauthored = len([r for r in records if r.get("task") == "ai_coauthored_composer"])
    discrepancy_time = None
    for r in reversed(records):
        if (
            r.get("task") == "memory_diff_checker"
            and r.get("output")
            and isinstance(r.get("output"), dict)
            and r["output"].get("discrepancy")
        ):
            discrepancy_time = r.get("timestamp")
            break
    repairs = len([r for r in records if r.get("task") == "workflow_audit_agent"])
    return {
        "claude_gemini_syncs": syncs,
        "coauthored_tasks": coauthored,
        "last_discrepancy": discrepancy_time,
        "repair_suggestions": repairs,
    }


@app.get("/dashboard/ops")
async def dashboard_ops() -> Dict[str, Any]:
    """Combined operations metrics including sales and signups."""
    metrics = await dashboard_metrics()
    tasks = await dashboard_tasks()
    status = await dashboard_status()
    data_file = Path("data/ops_data.json")
    extra: Dict[str, Any] = {}
    if data_file.exists():
        try:
            extra = json.loads(data_file.read_text())
        except Exception:  # noqa: BLE001
            extra = {}
    result = {**status, **metrics, **tasks, **extra}
    return result


@app.get("/diagnostics/state")
async def diagnostics_state() -> Dict[str, Any]:
    active_tasks = 0
    retry_queue = 0
    last_summary = None
    last_tana_push = None
    try:
        from supabase_client import supabase

        res = (
            supabase.table("task_queue").select("id").eq("status", "pending").execute()
        )
        active_tasks = len(res.data or [])
        rq = (
            supabase.table("retry_queue").select("id").eq("status", "pending").execute()
        )
        retry_queue = len(rq.data or [])
    except Exception:  # noqa: BLE001
        active_tasks = 0
        retry_queue = 0
    for item in reversed(memory_store.fetch_all(limit=20)):
        if (
            item.get("task") == "claude_memory_agent"
            or item.get("task") == "gemini_memory_agent"
        ):
            last_summary = item.get("timestamp")
            break
    for item in reversed(memory_store.fetch_all(limit=50)):
        if item.get("task") == "create_tana_node":
            last_tana_push = item.get("timestamp")
            break
    secrets_loaded = [
        s for s in ["CLAUDE_API_KEY", "TANA_API_KEY"] if getattr(settings, s, None)
    ]
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
    """Basic health check endpoint used by monitoring services."""
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
