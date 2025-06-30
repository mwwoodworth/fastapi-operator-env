"""Backup a site directory into /backups."""

import logging
import shutil
from datetime import datetime
from pathlib import Path


logger = logging.getLogger(__name__)


def run(context: dict) -> dict:
    """Zip a directory and place it in /backups with timestamp."""

    site_dir = Path(context.get("site_dir", "public"))
    if not site_dir.exists():
        error = f"Site directory not found: {site_dir}"
        logger.error(error)
        return {"status": "error", "message": error}

    backup_root = Path("/backups")
    backup_root.mkdir(exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    backup_name = context.get("backup_name", f"site_backup_{timestamp}")
    archive_path = backup_root / backup_name

    logger.info("Creating backup %s.zip from %s", archive_path, site_dir)
    try:
        shutil.make_archive(str(archive_path), "zip", str(site_dir))
        message = f"Backup created at {archive_path}.zip"
        logger.info(message)
        return {
            "status": "success",
            "message": message,
            "archive": f"{archive_path}.zip",
        }
    except Exception as exc:
        logger.error("Backup failed: %s", exc)
        return {"status": "error", "message": str(exc)}
