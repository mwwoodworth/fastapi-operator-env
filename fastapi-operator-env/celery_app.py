from __future__ import annotations

from datetime import datetime, timedelta
from celery import Celery
from celery.schedules import crontab
from core.settings import Settings
from utils.slack import send_slack_message

settings = Settings()

celery_app = Celery(
    "brainops",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.timezone = "UTC"

celery_app.conf.beat_schedule = {
    "run-recurring-tasks": {
        "task": "run_recurring_tasks",
        "schedule": timedelta(seconds=settings.RECURRING_TASK_CHECK_INTERVAL),
    },
    "run-task-rescheduler": {
        "task": "run_task_rescheduler",
        "schedule": timedelta(seconds=settings.ESCALATION_CHECK_INTERVAL),
    },
    "weekly-strategy-agent": {
        "task": "execute_registered_task",
        "schedule": crontab(
            day_of_week=settings.WEEKLY_STRATEGY_DAY.lower(), hour=16, minute=0
        ),
        "args": ("claude_strategy_agent", {}),
    },
    "weekly-priority-review": {
        "task": "execute_registered_task",
        "schedule": crontab(
            day_of_week=settings.CLAUDE_WEEKLY_PRIORITY_DAY.lower(),
            hour=int(settings.CLAUDE_WEEKLY_PRIORITY_TIME.split(":")[0]),
            minute=int(settings.CLAUDE_WEEKLY_PRIORITY_TIME.split(":")[1]),
        ),
        "args": ("weekly_priority_review", {}),
    },
    "weekly-digest-report": {
        "task": "weekly_digest_report",
        "schedule": crontab(day_of_week="monday", hour=9, minute=0),
    },
}


@celery_app.task(name="long_task")
def long_task(duration: int = 5) -> dict:
    """Sample long running task."""
    import time

    for _ in range(duration):
        time.sleep(1)
    return {"duration": duration}


@celery_app.task(name="run_task_rescheduler")
def run_task_rescheduler() -> dict:
    from codex.tasks import task_rescheduler

    return task_rescheduler.run({})


@celery_app.task(name="run_recurring_tasks")
def run_recurring_tasks() -> dict:
    from codex.tasks import recurring_task_engine

    return recurring_task_engine.run({})


@celery_app.task(name="execute_registered_task")
def execute_registered_task(task_id: str, context: dict | None = None) -> dict:
    """Run a registered task via Celery."""
    from codex import run_task

    return run_task(task_id, context or {})


@celery_app.task(name="weekly_digest_report")
def weekly_digest_report() -> dict:
    """Compile simple stats and send to Slack."""
    try:
        from supabase_client import supabase
    except Exception:
        return {"status": "supabase_unavailable"}

    one_week = datetime.utcnow() - timedelta(days=7)
    res = supabase.table("logs").select("*").execute()
    entries = [
        e
        for e in (res.data or [])
        if e.get("timestamp") and e["timestamp"] > one_week.isoformat()
    ]
    errors = len([e for e in entries if e.get("level") == "ERROR"])
    docs_res = supabase.table("documents").select("id", count="exact").execute()
    docs = int(docs_res.count or 0)
    message = (
        f"Weekly digest: {len(entries)} log entries, {errors} errors, {docs} documents."
    )
    send_slack_message(message)
    return {"entries": len(entries), "errors": errors, "documents": docs}
