"""Generate simple usage metrics from log files."""

from __future__ import annotations

import json
from pathlib import Path


def compute_metrics() -> dict:
    log_file = Path("logs/task_log.json")
    error_file = Path("logs/error_log.json")
    metrics = {
        "tasks_logged": 0,
        "unique_tasks": 0,
        "errors_logged": 0,
        "last_task_time": None,
    }
    if log_file.exists():
        try:
            data = json.loads(log_file.read_text())
            metrics["tasks_logged"] = len(data)
            metrics["unique_tasks"] = len({d.get("task") for d in data})
            if data:
                metrics["last_task_time"] = data[-1].get("timestamp")
        except Exception:
            pass
    if error_file.exists():
        try:
            metrics["errors_logged"] = len(json.loads(error_file.read_text()))
        except Exception:
            pass
    return metrics


if __name__ == "__main__":
    print(json.dumps(compute_metrics(), indent=2))
