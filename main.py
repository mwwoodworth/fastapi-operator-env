"""BrainOps Operator FastAPI server."""

from __future__ import annotations

import logging
import sys
from loguru import logger
import asyncio
import json
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from pathlib import Path
import uuid
import httpx
from typing import Any, Dict, List
from utils.metrics import (
    REGISTRY,
    TASKS_EXECUTED,
    TASKS_SUCCEEDED,
    TASKS_FAILED,
    TASK_DURATION,
    OPENAI_API_CALLS,
    OPENAI_TOKENS,
    CLAUDE_API_CALLS,
    CLAUDE_TOKENS,
    MEMORY_ENTRIES,
    latest as metrics_latest,
)

from fastapi import FastAPI, HTTPException, Request, Header, UploadFile, File, Depends
from fastapi.responses import JSONResponse, StreamingResponse, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi_csrf_protect import CsrfProtect
from fastapi.staticfiles import StaticFiles
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
)
import jwt
from pydantic import BaseModel
from utils.slack import send_slack_message
from db.session import init_db
from core.settings import Settings

settings = Settings()
APP_START = datetime.now(timezone.utc)

# Prometheus metrics provided by utils.metrics

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
from codex.brainops_operator import stream_task
from celery_app import celery_app, long_task, execute_registered_task
from codex.memory import memory_store, agent_inbox
from codex.integrations.make_webhook import router as make_webhook_router
from codex.integrations.clickup import router as clickup_router
from codex.integrations.notion import router as notion_router
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
    CeleryTaskResponse,
    TaskStatusResponse,
    MemoryEntriesResponse,
    VoiceHistoryResponse,
    VoiceTraceResponse,
    VoiceStatusResponse,
    MemoryTraceResponse,
    TanaNodeCreateResponse,
    StatusResponse,
    ValueResponse,
    VoiceUploadResponse,
    KnowledgeDocUploadResponse,
    KnowledgeSearchResponse,
)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        level = (
            logger.level(record.levelname).name
            if record.levelname in logger._core.levels
            else record.levelno
        )
        logger.bind(module=record.module).opt(exception=record.exc_info).log(
            level, record.getMessage()
        )


logger.remove()
logger.add(sys.stdout, serialize=True)


def _slack_sink(message: "loguru.Message") -> None:
    send_slack_message(message.record["message"])


def _supabase_sink(message: "loguru.Message") -> None:
    async def _send() -> None:
        try:
            from supabase_client import supabase
        except Exception:
            return
        record = message.record
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record["level"].name,
            "message": record["message"],
            "function": record.get("function"),
            "module": record.get("module"),
        }
        try:
            supabase.table("logs").insert(entry).execute()
        except Exception:
            pass

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send())
    except RuntimeError:
        asyncio.run(_send())


logger.add(_slack_sink, level="ERROR")
logger.add(_supabase_sink, level="ERROR")
logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


class CsrfSettings(BaseModel):
    secret_key: str = settings.JWT_SECRET


@CsrfProtect.load_config
def get_csrf_config() -> CsrfSettings:
    return CsrfSettings()


limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
USERS: dict[str, str] = {}
ADMIN_USERS: set[str] = set()

if settings.AUTH_USERS:
    try:
        USERS = json.loads(settings.AUTH_USERS)
    except Exception:  # noqa: BLE001
        USERS = {}
ADMIN_USERS = set((settings.ADMIN_USERS or "").split(","))


def _create_token(data: dict, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=minutes)
    payload = data | {"exp": expire, "iat": int(now.timestamp())}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("JWT decode failed: %s", exc)
        raise HTTPException(status_code=401, detail="invalid_token") from exc


def get_current_user(
    request: Request, token: str | None = Depends(oauth2_scheme)
) -> str:
    if request.url.path.startswith("/auth/") or request.url.path.startswith(
        "/webhook/"
    ):
        return "anonymous"
    cookie_token = request.cookies.get("access_token")
    token = token or cookie_token
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = _decode_token(token)
    if payload.get("iat") and payload["iat"] < int(APP_START.timestamp()):
        raise HTTPException(status_code=401, detail="token_expired")
    username = payload.get("sub")
    if not username or username not in USERS:
        raise HTTPException(status_code=401, detail="invalid_user")
    return username


def require_admin(request: Request, token: str | None = Depends(oauth2_scheme)) -> str:
    token = token or request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = _decode_token(token)
    username = payload.get("sub")
    roles = payload.get("roles") or payload.get("role")
    if isinstance(roles, str):
        roles = [roles]
    roles = roles or []
    if username not in ADMIN_USERS and "admin" not in roles:
        raise HTTPException(status_code=403, detail="not authorized")
    return username


async def verify_csrf(request: Request, csrf_protect: CsrfProtect = Depends()) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if request.url.path.startswith("/auth/"):
        return
    if "access_token" in request.cookies:
        await csrf_protect.validate_csrf(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = ", ".join(get_registry().keys())
    logger.info("Available tasks: %s", tasks)
    init_db()
    app.state.settings = settings
    yield


app = FastAPI(
    lifespan=lifespan, dependencies=[Depends(get_current_user), Depends(verify_csrf)]
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.include_router(make_webhook_router)
app.include_router(clickup_router)
app.include_router(notion_router)
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


@app.post("/auth/token")
async def auth_token(
    form: OAuth2PasswordRequestForm = Depends(), csrf_protect: CsrfProtect = Depends()
) -> Response:
    if not USERS:
        raise HTTPException(status_code=401, detail="auth_disabled")
    pw = USERS.get(form.username)
    if not pw or pw != form.password:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    roles = ["admin"] if form.username in ADMIN_USERS else ["user"]
    payload = {"sub": form.username, "roles": roles}
    access_token = _create_token(payload, 15)
    refresh_token = _create_token(
        {"sub": form.username, "type": "refresh"}, 60 * 24 * 7
    )
    csrf_token, csrf_signed = csrf_protect.generate_csrf_tokens()
    resp = JSONResponse({"access_token": access_token, "csrf_token": csrf_token})
    resp.set_cookie("access_token", access_token, httponly=True, max_age=15 * 60)
    resp.set_cookie(
        "refresh_token", refresh_token, httponly=True, max_age=60 * 60 * 24 * 7
    )
    csrf_protect.set_csrf_cookie(csrf_signed, resp)
    return resp


@app.post("/auth/refresh")
async def refresh_access_token(
    request: Request, csrf_protect: CsrfProtect = Depends()
) -> Response:
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="missing_refresh")
    payload = _decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="invalid_token")
    username = payload.get("sub")
    if not username or username not in USERS:
        raise HTTPException(status_code=401, detail="invalid_user")
    roles = ["admin"] if username in ADMIN_USERS else ["user"]
    access_token = _create_token({"sub": username, "roles": roles}, 15)
    csrf_token, csrf_signed = csrf_protect.generate_csrf_tokens()
    resp = JSONResponse({"access_token": access_token, "csrf_token": csrf_token})
    resp.set_cookie("access_token", access_token, httponly=True, max_age=15 * 60)
    csrf_protect.set_csrf_cookie(csrf_signed, resp)
    return resp


@app.post("/auth/logout")
async def logout(csrf_protect: CsrfProtect = Depends()) -> Response:
    resp = JSONResponse({"status": "logged_out"})
    resp.delete_cookie("access_token")
    resp.delete_cookie("refresh_token")
    csrf_protect.unset_csrf_cookie(resp)
    return resp


class TanaRequest(BaseModel):
    content: str


class TaskRunRequest(BaseModel):
    task: str
    context: Dict[str, Any] | None = {}
    stream: bool | None = False


class NLDesignRequest(BaseModel):
    goal: str
    model: str | None = None


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    memory_scope: str | int | None = 5
    stream: bool | None = False
    session_id: str | None = None


class ChatToTaskRequest(BaseModel):
    message: str
    model: str | None = None
    memory_scope: str | int | None = 5
    session_id: str | None = None


class KnowledgeQueryRequest(BaseModel):
    query: str
    sources: list[str] | None = None
    model: str | None = None


class KnowledgeDocUploadRequest(BaseModel):
    content: str
    metadata: Dict[str, Any] | None = None


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


@app.post("/task/run", response_model=CeleryTaskResponse)
async def task_run(req: TaskRunRequest, request: Request):
    if req.stream:

        async def event_generator():
            gen = stream_task(req.task, req.context or {})
            try:
                async for token in gen:
                    yield f"data: {token}\n\n"
                    if await request.is_disconnected():
                        await gen.aclose()
                        break
            except asyncio.CancelledError:
                await gen.aclose()
                raise

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    try:
        result = execute_registered_task.delay(req.task, req.context or {})
        TASKS_EXECUTED.inc()
        return {"task_id": result.id}
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


class LongTaskRequest(BaseModel):
    duration: int = 5


@app.post("/tasks/long")
async def queue_long_task(req: LongTaskRequest) -> Dict[str, Any]:
    result = long_task.delay(req.duration)
    TASKS_EXECUTED.inc()
    return {"task_id": result.id}


@app.get("/tasks/status/{task_id}", response_model=TaskStatusResponse)
@app.get("/task/status/{task_id}", response_model=TaskStatusResponse)
async def task_status(task_id: str) -> TaskStatusResponse:
    res = celery_app.AsyncResult(task_id)
    if res.successful():
        return TaskStatusResponse(status=res.state, result=res.result)
    return TaskStatusResponse(status=res.state, result=None)


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    model = req.model or get_ai_model(task="chat")
    scope = _resolve_scope(req.memory_scope)
    mem_text = memory_store.load_recent(scope, req.session_id)
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
                    {
                        "message": req.message,
                        "model": "claude",
                        "memory_scope": scope,
                        "session_id": req.session_id,
                    },
                )
                suggested = task_suggestions.get("tasks") or task_suggestions.get(
                    "generated"
                )
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
                    "session_id": req.session_id,
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
        {
            "message": req.message,
            "model": "claude",
            "memory_scope": scope,
            "session_id": req.session_id,
        },
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
        "session_id": req.session_id,
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
        "session_id": req.session_id,
    }
    return run_task("chat_to_prompt", context)


@app.post("/task/webhook", response_model=TaskRunResponse)
async def webhook_trigger(
    req: dict, x_webhook_secret: str | None = Header(default=None)
) -> TaskRunResponse:
    secret = settings.TASK_WEBHOOK_SECRET
    if secret and secret != x_webhook_secret:
        raise HTTPException(status_code=401, detail="invalid_signature")
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


def _verify_stripe(payload: bytes, sig_header: str | None) -> bool:
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret or not sig_header:
        return True
    import hmac
    import hashlib

    try:
        parts = {s.split("=", 1)[0]: s.split("=", 1)[1] for s in sig_header.split(",")}
        timestamp = parts.get("t")
        signature = parts.get("v1")
        if not timestamp or not signature:
            return False
        msg = f"{timestamp}.{payload.decode()}".encode()
        digest = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
        expected = digest
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


_EVENT_FILE = Path("logs/stripe_events.json")


def _load_event_ids() -> list[str]:
    if _EVENT_FILE.exists():
        try:
            return json.loads(_EVENT_FILE.read_text())
        except Exception:  # noqa: BLE001
            return []
    return []


def _save_event_ids(ids: list[str]) -> None:
    _EVENT_FILE.parent.mkdir(exist_ok=True)
    _EVENT_FILE.write_text(json.dumps(ids[-200:], indent=2))


@app.post("/webhook/stripe", dependencies=[])
async def stripe_webhook(request: Request) -> Dict[str, Any]:
    """Handle Stripe sale events and enqueue ``sync_sale`` task."""
    raw = await request.body()
    sig = request.headers.get("Stripe-Signature")
    if not _verify_stripe(raw, sig):
        raise HTTPException(status_code=401, detail="invalid_signature")

    try:
        payload = json.loads(raw.decode())
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="invalid_payload")
    event_id = payload.get("id")
    if not event_id:
        raise HTTPException(status_code=400, detail="missing_event_id")
    processed = _load_event_ids()
    if event_id in processed:
        return {"status": "duplicate"}

    event_type = payload.get("type")
    obj = payload.get("data", {}).get("object", {})
    relevant = {"checkout.session.completed", "payment_intent.succeeded"}
    if event_type in relevant:
        context = {
            "email": obj.get("customer_email")
            or obj.get("customer_details", {}).get("email")
            or obj.get("receipt_email"),
            "product": obj.get("description")
            or obj.get("metadata", {}).get("product")
            or event_type,
            "amount": obj.get("amount_total")
            or obj.get("amount_received")
            or obj.get("amount"),
            "metadata": obj.get("metadata"),
            "transaction_id": obj.get("payment_intent") or obj.get("id"),
        }
        run_task("sync_sale", context)

    processed.append(event_id)
    _save_event_ids(processed)
    return {"status": "processed"}


def _verify_slack(timestamp: str | None, sig: str | None, body: bytes) -> bool:
    """Validate Slack webhook signature and timestamp."""
    secret = settings.SLACK_SIGNING_SECRET
    if not secret or not sig or not timestamp:
        return True
    import hmac
    import hashlib
    import time

    try:
        ts = int(timestamp)
    except Exception:
        return False
    if abs(time.time() - ts) > 60 * 5:
        return False

    basestring = f"v0:{timestamp}:{body.decode()}".encode()
    digest = hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, sig)


@app.post("/webhook/slack/command")
async def slack_command(request: Request) -> Dict[str, Any]:
    """Process Slack slash-command approvals for inbox tasks."""
    raw = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    sig = request.headers.get("X-Slack-Signature")
    if not _verify_slack(timestamp, sig, raw):
        raise HTTPException(status_code=401, detail="invalid_signature")
    form = await request.form()
    text = form.get("text", "")
    parts = text.split()
    if len(parts) < 2:
        return {"response_type": "ephemeral", "text": "Usage: approve|reject <id>"}
    action, task_id = parts[0], parts[1]
    item = agent_inbox.get_task(task_id)
    if not item:
        return {"response_type": "ephemeral", "text": "Task not found"}
    if action == "approve":
        result = run_task(item["task_id"], item.get("context", {}))
        agent_inbox.mark_as_resolved(task_id, "approved", "via slack")
        _ = result
        return {"response_type": "in_channel", "text": f"Task {task_id} approved"}
    if action == "reject":
        agent_inbox.mark_as_resolved(task_id, "rejected", "via slack")
        return {"response_type": "in_channel", "text": f"Task {task_id} rejected"}
    if action == "status":
        return {
            "response_type": "ephemeral",
            "text": f"Task {task_id}: {item.get('status')}",
        }
    if action == "query":
        query = " ".join(parts[1:])
        results = memory_store.search(query, limit=3)
        if results:
            lines = [str(r.get("output") or r)[:80] for r in results]
            resp = "\n".join(lines)
        else:
            resp = "No results"
        return {"response_type": "in_channel", "text": resp}
    return {"response_type": "ephemeral", "text": "Unknown command"}


@app.post("/webhook/slack/event")
async def slack_event(request: Request) -> Dict[str, Any]:
    """Handle generic Slack Events API payloads."""
    raw = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    sig = request.headers.get("X-Slack-Signature")
    if not _verify_slack(timestamp, sig, raw):
        raise HTTPException(status_code=401, detail="invalid_signature")
    payload = await request.json()
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    event = payload.get("event", {})
    if event.get("type") == "message" and event.get("text"):
        memory_store.save_memory(
            {"input": event.get("text"), "output": "", "user": event.get("user")},
            origin={"source": "slack"},
        )
    return {"status": "received"}


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
async def store_secret_api(
    req: dict, _: str = Depends(require_admin)
) -> StatusResponse:
    secrets_task.store_secret(req["name"], req["value"])
    return StatusResponse(status="stored")


@app.get("/secrets/retrieve/{name}", response_model=ValueResponse)
async def retrieve_secret_api(
    name: str, _: str = Depends(require_admin)
) -> ValueResponse:
    val = secrets_task.retrieve_secret(name)
    return ValueResponse(value=val)


@app.delete("/secrets/delete/{name}", response_model=StatusResponse)
async def delete_secret_api(
    name: str, _: str = Depends(require_admin)
) -> StatusResponse:
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


@app.post("/knowledge/doc/upload", response_model=KnowledgeDocUploadResponse)
async def knowledge_doc_upload(
    req: KnowledgeDocUploadRequest,
) -> KnowledgeDocUploadResponse:
    from codex.memory.memory_utils import embed_chunks

    try:
        from supabase_client import supabase
    except Exception:  # pragma: no cover - missing deps
        supabase = None

    vector = embed_chunks([req.content])[0]
    doc_id: int | None = None
    if supabase:
        try:  # pragma: no cover - network
            res = (
                supabase.table("documents")
                .insert(
                    {
                        "content": req.content,
                        "metadata": req.metadata or {},
                        "embedding": vector,
                    }
                )
                .execute()
            )
            if res.data:
                doc_id = res.data[0].get("id")
        except Exception:  # noqa: BLE001
            doc_id = None
    return KnowledgeDocUploadResponse(id=doc_id)


@app.get("/knowledge/search", response_model=KnowledgeSearchResponse)
async def knowledge_search(q: str, limit: int = 5) -> KnowledgeSearchResponse:
    from codex.memory import doc_indexer

    results = doc_indexer.search(q, limit)
    return KnowledgeSearchResponse(results=results)


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
    limit: int = 20,
    model: str | None = None,
    tags: str = "",
    session_id: str | None = None,
) -> MemoryEntriesResponse:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    tag_list.append("chat")
    records = memory_store.query(tag_list, limit=limit * 5)
    if session_id:
        records = [r for r in records if r.get("session_id") == session_id]
    records = records[-limit:]
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
async def status_update(
    req: StatusUpdate, x_webhook_secret: str | None = Header(default=None)
) -> StatusResponse:
    secret = settings.STATUS_UPDATE_SECRET
    if secret and secret != x_webhook_secret:
        raise HTTPException(status_code=401, detail="invalid_signature")
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


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint."""
    MEMORY_ENTRIES.set(memory_store.count_entries())
    data = metrics_latest()
    return Response(data, media_type="text/plain; version=0.0.4")


@app.get("/health")
async def health() -> Dict[str, str]:
    """Basic health check endpoint used by monitoring services."""
    return {"status": "ok"}


@app.post("/protected-test")
async def protected_test() -> Dict[str, str]:
    return {"status": "protected"}


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
        logger.info(json.dumps(entries, indent=2))
    elif cmd:
        if cmd == "retry_queue":
            from scripts.runner import check_retry_queue

            check_retry_queue()
            logger.info("retry queue processed")
        else:
            result = run_task(cmd, ctx)
            import json

            logger.info(json.dumps(result, indent=2))
