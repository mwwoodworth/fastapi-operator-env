"""Bridge feedback between Claude and Gemini."""

from __future__ import annotations

from typing import Any, Dict

from core.settings import Settings

settings = Settings()

from codex.tasks import claude_prompt, gemini_prompt


def maybe_chain_feedback(
    output: str, context: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Optionally route Claude output through Gemini for feedback and back."""
    context = context or {}
    if not (context.get("feedback_chain") or settings.AI_FEEDBACK_CHAIN == "true"):
        return {"output": output}

    gem_res = gemini_prompt.run(
        {"prompt": f"Provide feedback on the following Claude output:\n{output}"}
    )
    suggestion = gem_res.get("completion", "")
    if not suggestion:
        return {"output": output, "feedback": None}

    claude_res = claude_prompt.run(
        {"prompt": f"Apply this feedback: {suggestion}\nOriginal: {output}"}
    )
    final_out = claude_res.get("completion", output)
    return {"output": final_out, "feedback": suggestion}
