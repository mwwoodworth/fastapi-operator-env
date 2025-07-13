"""Assign tasks to Claude or Gemini based on simple heuristics."""

from __future__ import annotations

from typing import Dict, List


def assign_routes(tasks: List[Dict[str, str]]) -> List[Dict[str, str]]:
    routes: List[Dict[str, str]] = []
    for t in tasks:
        name = str(t.get("task", "")).lower()
        model = "claude"
        if any(k in name for k in ["code", "dependency", "map"]):
            model = "gemini"
        routes.append({"task": str(t.get("task")), "model": model})
    return routes
