"""Webhook handler for Gemini Sheets data."""

from __future__ import annotations

import os
import httpx
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class GeminiRowInput(BaseModel):
    values: list[str]


@router.post("/gemini/webhook")
async def gemini_webhook(payload: GeminiRowInput) -> dict:
    """Parse sheet row and forward to memory service."""
    api_base = os.getenv("API_BASE", "http://localhost:10000")
    title = payload.values[0] if payload.values else "gemini"
    content = "\n".join(payload.values)
    data = {
        "project_id": "gemini_sheet",
        "title": title,
        "content": content,
        "author_id": "gemini",
    }
    async with httpx.AsyncClient() as client:
        await client.post(f"{api_base}/memory/write", json=data, timeout=10)
    return {"status": "ok"}
