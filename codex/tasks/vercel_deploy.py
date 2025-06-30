"""Vercel deployment task."""

import logging
import os
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)


def run(context: dict) -> dict:
    """Deploy a project using the Vercel CLI.

    Parameters
    ----------
    context : dict
        Expected keys:
        - ``project_path``: directory of the project (default ``'.'``)

    Returns
    -------
    dict
        Structured result with ``status`` and ``message``.
    """

    project_path = Path(context.get("project_path", "."))
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        error = "VERCEL_TOKEN not set in environment"
        logger.error(error)
        return {"status": "error", "message": error}
    if not project_path.exists():
        error = f"Project path not found: {project_path}"
        logger.error(error)
        return {"status": "error", "message": error}

    logger.info("Deploying %s to Vercel", project_path)
    try:
        subprocess.run(
            ["npx", "vercel", "--prod", "--token", token, "--confirm"],
            cwd=str(project_path),
            check=True,
            capture_output=True,
        )
        message = "[✅] Deployment triggered."
        logger.info(message)
        return {"status": "success", "message": message}
    except subprocess.CalledProcessError as exc:
        error = exc.stderr.decode() if exc.stderr else str(exc)
        logger.error("Deployment failed: %s", error)
        return {"status": "error", "message": error}
