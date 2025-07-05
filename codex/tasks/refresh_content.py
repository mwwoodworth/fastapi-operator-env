"""Refresh remote content."""

import logging
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)


def run(context: dict) -> dict:
    """Pull latest content from git and run AI updates if configured."""

    content_dir = Path(context.get("content_dir", "content"))
    if not content_dir.exists():
        error = f"Content directory not found: {content_dir}"
        logger.error(error)
        return {"status": "error", "message": error}

    logger.info("Pulling latest content in %s", content_dir)
    try:
        subprocess.run(["git", "pull"], cwd=str(content_dir), check=True, capture_output=True)
        # Placeholder for future AI-based content refresh
        message = "Content refreshed"
        logger.info(message)
        return {"status": "success", "message": message}
    except subprocess.CalledProcessError as exc:
        error = exc.stderr.decode() if exc.stderr else str(exc)
        logger.error("Content refresh failed: %s", error)
        return {"status": "error", "message": error}
