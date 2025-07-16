"""Transcribe audio files using OpenAI Whisper API."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import openai

TASK_ID = "whisper_transcribe"
TASK_DESCRIPTION = "Transcribe an audio file with Whisper"
REQUIRED_FIELDS = ["audio_path"]

logger = logging.getLogger(__name__)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    """Transcribe the given audio file and return the text."""
    audio_path = context.get("audio_path")
    if not audio_path:
        return {"error": "missing_audio_path"}

    path = Path(audio_path)
    if not path.exists():
        return {"error": "file_not_found"}

    try:
        with path.open("rb") as f:
            resp = openai.Audio.transcribe("whisper-1", f)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Whisper transcription failed")
        return {"error": str(exc)}

    text = resp.get("text", "").strip()
    language = resp.get("language", "en")
    tokens = len(text.split())
    return {"text": text, "tokens": tokens, "language": language}
