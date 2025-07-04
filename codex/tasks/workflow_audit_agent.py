"""Audit recent workflows and propose repairs."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from codex.memory import memory_store
from . import claude_prompt, gemini_prompt

TASK_ID = "workflow_audit_agent"
TASK_DESCRIPTION = "Audit workflow health and suggest repairs"
REQUIRED_FIELDS: list[str] = []

logger = logging.getLogger(__name__)


def _gather_logs(limit: int = 20) -> List[Dict[str, Any]]:
    return memory_store.fetch_all(limit=limit)


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    records = _gather_logs(50)
    incomplete = [r for r in records if isinstance(r.get("result"), dict) and r["result"].get("error")]
    summary_prompt = (
        "Summarize the main issues found in the following failed task logs:\n"
        + "\n".join(str(r.get("result")) for r in incomplete)
    )
    claude_res = claude_prompt.run({"prompt": summary_prompt})
    issues = claude_res.get("completion", "")

    patch_prompt = (
        f"Given these issues: {issues}\nPropose concise repair actions in bullet form."
    )
    gem_res = gemini_prompt.run({"prompt": patch_prompt})
    patches = gem_res.get("completion", "")

    memory_store.save_memory(
        {
            "task": TASK_ID,
            "input": issues,
            "output": patches,
            "tags": ["repair_suggestion"],
        },
        origin={"model": gem_res.get("executed_by", "gemini")},
    )

    return {"issues": issues, "patches": patches}
