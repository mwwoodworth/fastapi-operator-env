"""Background scheduler for periodic inbox checks and summaries."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from codex import run_task
from codex.memory import agent_inbox, memory_store
from codex.integrations import push_notify

logger = logging.getLogger(__name__)
CHECK_INTERVAL = 1800  # 30 minutes


async def scheduled_loop() -> None:
    while True:
        try:
            pending = agent_inbox.get_pending_tasks(20)
            if pending:
                run_task("claude_summarize", {})
                oldest = pending[0]
                ts = oldest.get("timestamp")
                if ts:
                    try:
                        dt = datetime.fromisoformat(ts)
                        if datetime.utcnow() - dt > timedelta(hours=2):
                            push_notify.send_push(
                                "Tasks awaiting approval",
                                f"{len(pending)} items need attention",
                                url="/agent/inbox",
                            )
                    except Exception:  # noqa: BLE001
                        pass
        except Exception as exc:  # noqa: BLE001
            logger.error("Scheduler error: %s", exc)
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(scheduled_loop())
