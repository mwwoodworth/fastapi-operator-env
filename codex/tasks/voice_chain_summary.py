"""Summarize the task chain triggered by a voice transcript."""

from __future__ import annotations

import logging
from typing import Any, Dict

from codex.memory import memory_store
from . import claude_prompt

TASK_ID = "voice_chain_summary"
TASK_DESCRIPTION = "Summarize transcript-triggered task chain"
REQUIRED_FIELDS = ["transcript_id"]

logger = logging.getLogger(__name__)


def _gather(transcript_id: str) -> tuple[str, list[dict]]:
    records = memory_store.fetch_all(limit=100)
    transcript = ""
    related: list[dict] = []
    for r in records:
        meta = r.get("metadata") or {}
        if meta.get("transcript_id") == transcript_id and r.get("task") == "voice_upload":
            transcript = r.get("output", {}).get("transcription", "")
        if meta.get("linked_transcript_id") == transcript_id:
            related.append(r)
    return transcript, related


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    tid = context.get("transcript_id")
    if not tid:
        return {"error": "missing_transcript_id"}

    transcript, linked = _gather(tid)
    if not transcript:
        return {"error": "not_found"}

    summary_input = f"Transcript:\n{transcript}\n\nEntries:\n" + "\n".join(
        f"{r.get('task')}: {r.get('output')}" for r in linked
    )
    ai = claude_prompt.run({"prompt": f"Summarize this chain:\n{summary_input}"})
    summary = ai.get("completion", "")

    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": {"transcript_id": tid},
            "output": {
                "summary": summary,
                "linked_tasks": [r.get("task") for r in linked],
            },
            "tags": ["voice-trace", "chain-summary"],
        },
        origin={"linked_transcript_id": tid, "model": ai.get("executed_by", "claude")},
    )
    return {"summary": summary, "linked_tasks": [r.get("task") for r in linked]}
