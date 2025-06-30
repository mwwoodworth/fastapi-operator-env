# utils.py
import datetime
import json
from pathlib import Path

LOG_FILE = Path("ai_task_log.json")

async def log_task(task_type, input_data, result_data):
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "task": task_type,
        "input": input_data,
        "result": result_data
    }
    history = []
    if LOG_FILE.exists():
        try:
            history = json.loads(LOG_FILE.read_text())
        except Exception:
            pass
    history.append(entry)
    LOG_FILE.write_text(json.dumps(history[-50:], indent=2))  # Keep only last 50 logs
