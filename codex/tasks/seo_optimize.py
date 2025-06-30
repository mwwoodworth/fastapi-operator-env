"""SEO optimization task."""

import logging
import os
from pathlib import Path
import httpx


logger = logging.getLogger(__name__)


def run(context: dict) -> dict:
    """Perform a simple SEO audit or injection of meta tags.

    Parameters
    ----------
    context : dict
        ``site_dir`` for local HTML files or ``site_url`` for a live site.

    Returns
    -------
    dict
        Result information.
    """

    site_dir = context.get("site_dir")
    site_url = context.get("site_url")
    if not site_dir and not site_url:
        error = "Either 'site_dir' or 'site_url' must be provided"
        logger.error(error)
        return {"status": "error", "message": error}

    if site_url:
        try:
            response = httpx.get(site_url, timeout=10)
            response.raise_for_status()
            has_description = "<meta name=\"description\"" in response.text
            message = (
                "Description tag present" if has_description else "Missing description tag"
            )
            logger.info("Checked %s: %s", site_url, message)
            return {"status": "success", "message": message}
        except Exception as exc:  # broad
            logger.error("SEO check failed: %s", exc)
            return {"status": "error", "message": str(exc)}

    site_path = Path(site_dir)
    if not site_path.exists():
        error = f"Site directory not found: {site_dir}"
        logger.error(error)
        return {"status": "error", "message": error}

    injected = []
    for file in site_path.glob("*.html"):
        content = file.read_text(encoding="utf-8")
        if "<meta name=\"description\"" not in content:
            content = content.replace(
                "<head>",
                "<head>\n<meta name=\"description\" content=\"SEO optimized page\">",
            )
            file.write_text(content, encoding="utf-8")
            injected.append(file.name)

    message = f"SEO tags injected into {len(injected)} files."
    logger.info(message)
    return {"status": "success", "message": message, "files": injected}
