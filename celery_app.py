from __future__ import annotations

from datetime import timedelta
from celery import Celery
from celery.schedules import crontab
from core.settings import Settings

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
            hour=int(settings.CLAUDE_WEEKLY_PRIORITY_TIME.split(":" )[0]),
            minute=int(settings.CLAUDE_WEEKLY_PRIORITY_TIME.split(":" )[1]),
        ),
        "args": ("weekly_priority_review", {}),
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
