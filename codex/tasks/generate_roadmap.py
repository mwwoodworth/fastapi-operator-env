"""Generate a project roadmap markdown file."""

import logging
from pathlib import Path


logger = logging.getLogger(__name__)


def run(context: dict) -> dict:
    """Create a simple ROADMAP.md stub.

    TODO: Integrate Gemini or GPT for automatic content generation.
    """

    project = context.get("project_name", "MyProject")
    output_file = Path(context.get("output", "ROADMAP.md"))

    content = f"# {project} Roadmap\n\n- Placeholder milestones\n"
    try:
        output_file.write_text(content, encoding="utf-8")
        message = f"Roadmap saved to {output_file}"
        logger.info(message)
        return {"status": "success", "message": message, "file": str(output_file)}
    except Exception as exc:  # broad file errors
        logger.error("Failed to write roadmap: %s", exc)
        return {"status": "error", "message": str(exc)}
