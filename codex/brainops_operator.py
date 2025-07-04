from codex.tasks import tana_create


def run_task(task: str, context: dict):
    match task:
        case "create_tana_node":
            tana_create.run(context)
        case _:
            print(f"[❌] Unknown task: {task}")
