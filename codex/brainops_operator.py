# codex/brainops_operator.py
"""BrainOps task dispatcher."""

import logging
from typing import Callable, Dict

from codex.tasks import (
    backup_site,
    fastapi_sync,
    generate_roadmap,
    refresh_content,
    run_tests,
    seo_optimize,
    site_audit,
    vercel_deploy,
)


logger = logging.getLogger(__name__)

TASK_MAP: Dict[str, Callable[[dict], dict]] = {
    "deploy_vercel": vercel_deploy.run,
    "sync_fastapi": fastapi_sync.run,
    "optimize_seo": seo_optimize.run,
    "site_audit": site_audit.run,
    "generate_roadmap": generate_roadmap.run,
    "run_tests": run_tests.run,
    "backup_site": backup_site.run,
    "refresh_content": refresh_content.run,
}


def run_task(task: str, context: dict) -> dict:
    """Dispatch a task to the correct handler.

    Parameters
    ----------
    task : str
        Name of the task.
    context : dict
        Parameters for the task.
    """

    func = TASK_MAP.get(task)
    if not func:
        error = f"Unknown task: {task}"
        logger.error(error)
        raise ValueError(error)

    logger.info("Running task %s with context %s", task, context)
    return func(context)
