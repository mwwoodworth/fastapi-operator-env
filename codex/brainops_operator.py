# codex/brainops_operator.py
from codex.tasks import (
    vercel_deploy,
    fastapi_sync,
    seo_optimize,
    site_audit,
    generate_roadmap,
    run_tests,
    backup_site,
    refresh_content,
)


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
        case "generate_roadmap":
            generate_roadmap.run(context)
        case "run_tests":
            run_tests.run(context)
        case "backup_site":
            backup_site.run(context)
        case "refresh_content":
            refresh_content.run(context)
        case _:
            print(f"[❌] Unknown task: {task}")
