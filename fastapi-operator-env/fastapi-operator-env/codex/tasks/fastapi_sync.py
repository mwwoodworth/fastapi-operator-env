"""Utilities for reloading the FastAPI server."""

import logging
import subprocess


logger = logging.getLogger(__name__)


def run(context: dict) -> dict:
    """Reload the running FastAPI server.

    Tries to send a HUP signal to any running Uvicorn process. This call does
    not block waiting for the server to restart.
    """

    logger.info("Sending reload signal to FastAPI server")
    try:
        subprocess.run(["pkill", "-HUP", "-f", "uvicorn"], check=True, capture_output=True)
        message = "[✅] FastAPI server reload signal sent."
        logger.info(message)
        return {"status": "success", "message": message}
    except subprocess.CalledProcessError as exc:
        error = exc.stderr.decode() if exc.stderr else str(exc)
        logger.error("Failed to reload FastAPI: %s", error)
        return {"status": "error", "message": error}
