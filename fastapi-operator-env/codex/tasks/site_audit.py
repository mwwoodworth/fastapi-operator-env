"""Site audit task using Lighthouse."""

import logging
import subprocess


logger = logging.getLogger(__name__)


def run(context: dict) -> dict:
    """Run a basic Lighthouse audit on a live site."""

    url = context.get("site_url")
    if not url:
        error = "'site_url' is required for site_audit task"
        logger.error(error)
        return {"status": "error", "message": error}

    report_path = context.get("report_path", "lighthouse-report.html")
    logger.info("Running lighthouse for %s", url)
    try:
        subprocess.run(
            [
                "npx",
                "lighthouse",
                url,
                "--output",
                "html",
                "--output-path",
                report_path,
                "--quiet",
            ],
            check=True,
            capture_output=True,
        )
        message = f"Audit complete. Report saved to {report_path}"
        logger.info(message)
        return {"status": "success", "message": message, "report": report_path}
    except subprocess.CalledProcessError as exc:
        error = exc.stderr.decode() if exc.stderr else str(exc)
        logger.error("Audit failed: %s", error)
        return {"status": "error", "message": error}
