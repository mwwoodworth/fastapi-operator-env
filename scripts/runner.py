"""Simple background runner to execute queued tasks."""

from __future__ import annotations

import asyncio
import logging

from codex import run_task
from codex.tasks import secrets
from supabase_client import supabase
import json
from pathlib import Path
import datetime

logger = logging.getLogger(__name__)
INTERVAL = 900  # 15 minutes


def check_retry_queue() -> None:
    try:
        res = supabase.table("retry_queue").select("*").eq("status", "pending").execute()
        entries = res.data or []
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch retry queue: %s", exc)
        return
    for entry in entries:
        ctx = entry.get("context") or {}
        task_id = entry.get("task")
        retry = entry.get("retry", 1)
        try:
            result = run_task(task_id, {**ctx, "retry": retry})
            supabase.table("retry_queue").update({"status": "complete", "result": json.dumps(result)}).eq("id", entry["id"]).execute()
        except Exception as exc:  # noqa: BLE001
            logger.error("Retry task failed: %s", exc)
            status = "failed" if retry >= 3 else "pending"
            supabase.table("retry_queue").update({"status": status, "retry": retry + 1, "error": str(exc)}).eq("id", entry["id"]).execute()


LAST_SUMMARY_FILE = Path("logs/last_memory_summary.txt")


def auto_memory_summarizer() -> None:
    last = None
    if LAST_SUMMARY_FILE.exists():
        try:
            last = datetime.datetime.fromisoformat(LAST_SUMMARY_FILE.read_text().strip())
        except Exception:  # noqa: BLE001
            last = None
    if not last or (datetime.datetime.now(datetime.timezone.utc) - last).total_seconds() > 86400:
        try:
            run_task("claude_memory_agent", {})
            LAST_SUMMARY_FILE.write_text(datetime.datetime.now(datetime.timezone.utc).isoformat())
        except Exception as exc:  # noqa: BLE001
            logger.error("Auto memory summarizer failed: %s", exc)


async def poll_and_run() -> None:
    while True:
        try:
            res = (
                supabase.table("task_queue")
                .select("*")
                .eq("status", "pending")
                .execute()
            )
            entries = res.data or []
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to fetch queue: %s", exc)
            await asyncio.sleep(INTERVAL)
            continue

        for entry in entries:
            ctx = entry.get("context") or {}
            task_id = entry.get("task")
            try:
                result = run_task(task_id, ctx)
                supabase.table("task_queue").update(
                    {"status": "complete", "result": json.dumps(result)}
                ).eq("id", entry["id"]).execute()
            except Exception as exc:  # noqa: BLE001
                logger.error("Queue task failed: %s", exc)
                supabase.table("task_queue").update(
                    {"status": "error", "result": str(exc)}
                ).eq("id", entry["id"]).execute()
        try:
            secrets.expire_old()
        except Exception as exc:  # noqa: BLE001
            logger.error("Secret expiration failed: %s", exc)
        try:
            check_retry_queue()
        except Exception as exc:  # noqa: BLE001
            logger.error("Retry queue check failed: %s", exc)
        try:
            auto_memory_summarizer()
        except Exception as exc:  # noqa: BLE001
            logger.error("Memory summarizer error: %s", exc)
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(poll_and_run())
