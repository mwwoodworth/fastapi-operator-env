# codex/brainops_operator.py
from codex.tasks import vercel_deploy, fastapi_sync, seo_optimize, site_audit

def run_task(task: str, context: dict):
    match task:
        case "deploy_vercel":
            vercel_deploy.run(context)
        case "sync_fastapi":
            fastapi_sync.run(context)
        case "optimize_seo":
            seo_optimize.run(context)
        case "site_audit":
            site_audit.run(context)
        case _:
            print(f"[❌] Unknown task: {task}")
