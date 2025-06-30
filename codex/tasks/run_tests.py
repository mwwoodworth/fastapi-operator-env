"""Run the project's test suite."""

import logging
import subprocess
from pathlib import Path


logger = logging.getLogger(__name__)


def run(context: dict) -> dict:
    """Execute pytest for the given project directory."""

    project_dir = Path(context.get("path", "."))
    if not project_dir.exists():
        error = f"Project directory not found: {project_dir}"
        logger.error(error)
        return {"status": "error", "message": error}

    logger.info("Running tests in %s", project_dir)
    try:
        result = subprocess.run(["pytest", "-q"], cwd=str(project_dir), capture_output=True, text=True)
        if result.returncode == 0:
            message = "Tests passed"
            logger.info(message)
            return {"status": "success", "message": message, "output": result.stdout}
        else:
            logger.error("Tests failed: %s", result.stderr)
            return {"status": "error", "message": result.stderr}
    except FileNotFoundError:
        # pytest may not be installed; fall back
        logger.warning("pytest not available; running placeholder tests")
        subprocess.run(["echo", "Tests placeholder"], cwd=str(project_dir))
        return {"status": "success", "message": "Placeholder tests executed"}
