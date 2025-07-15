"""Generate a dependency map and execution order for a set of tasks."""

from __future__ import annotations

from typing import Any, Dict, List

TASK_ID = "gemini_dependency_map"
TASK_DESCRIPTION = "Identify task dependencies and suggested order"
REQUIRED_FIELDS = ["tasks"]


def run(context: Dict[str, Any]) -> Dict[str, Any]:
    tasks = context.get("tasks") or []
    name_map = {t.get("task"): t for t in tasks if t.get("task")}
    order: List[str] = []
    visited: set[str] = set()

    def add(name: str) -> None:
        if name in visited:
            return
        item = name_map.get(name)
        if not item:
            return
        dep = item.get("depends_on")
        if dep:
            add(dep)
        order.append(name)
        visited.add(name)

    for t in tasks:
        add(t.get("task"))

    dep_map = [
        {"task": name, "depends_on": name_map.get(name, {}).get("depends_on")}
        for name in order
    ]
    return {"dependency_order": order, "map": dep_map}
