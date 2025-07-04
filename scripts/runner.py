"""Simple background runner to execute queued tasks."""

from __future__ import annotations

import asyncio
import logging

from codex import run_task
from codex.tasks import secrets
from supabase_client import supabase
import json

logger = logging.getLogger(__name__)
INTERVAL = 900  # 15 minutes


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
        await asyncio.sleep(INTERVAL)


if __name__ == "__main__":
    asyncio.run(poll_and_run())
