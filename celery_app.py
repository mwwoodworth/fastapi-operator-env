from __future__ import annotations

from datetime import timedelta
from celery import Celery
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
