"""Google Drive Claude log synchronizer."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials


def _get_service() -> "drive":
    creds_info = os.getenv("GOOGLE_API_SERVICE_ACCOUNT")
    if not creds_info:
        raise RuntimeError("GOOGLE_API_SERVICE_ACCOUNT not configured")
    if Path(creds_info).exists():
        creds = Credentials.from_service_account_file(creds_info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    else:
        creds = Credentials.from_service_account_info(json.loads(creds_info), scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return build("drive", "v3", credentials=creds)


def sync_claude_logs() -> dict:
    """Pull markdown logs from Drive and store them via the memory API."""
    folder_id = os.getenv("CLAUDE_LOG_FOLDER_ID")
    api_base = os.getenv("API_BASE", "http://localhost:10000")
    if not folder_id:
        return {"error": "missing_folder"}
    service = _get_service()
    files = (
        service.files()
        .list(q=f"'{folder_id}' in parents and mimeType contains 'text/plain'", fields="files(id,name)")
        .execute()
        .get("files", [])
    )
    count = 0
    for f in files:
        data = service.files().get_media(fileId=f["id"]).execute().decode()
        payload = {
            "project_id": "claude_logs",
            "title": f["name"],
            "content": data,
            "author_id": "claude",
        }
        try:
            httpx.post(f"{api_base}/memory/write", json=payload, timeout=10)
            count += 1
        except Exception:  # noqa: BLE001
            pass
    return {"synced": count}
