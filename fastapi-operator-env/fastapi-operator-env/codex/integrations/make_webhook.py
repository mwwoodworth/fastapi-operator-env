from fastapi import APIRouter, Header, HTTPException
import os
from codex.brainops_operator import run_task

router = APIRouter(prefix="/webhook/make")

@router.post("")
async def handle_webhook(payload: dict, x_make_secret: str | None = Header(default=None)):
    secret_required = os.getenv("MAKE_WEBHOOK_SECRET")
    if secret_required and secret_required != x_make_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")

    task = payload.get("task")
    context = payload.get("context", {})
    if isinstance(context, dict):
        context.setdefault("source", "make-webhook")
    if not task:
        raise HTTPException(status_code=400, detail="'task' is required")

    try:
        result = run_task(task, context)
        return {"status": "success", "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
