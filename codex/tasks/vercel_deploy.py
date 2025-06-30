import os
import subprocess

def run(context: dict):
    print("[🚀] Deploying to Vercel...")
    project_path = context.get("project_path", ".")
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        raise EnvironmentError("VERCEL_TOKEN not set in environment.")

    subprocess.run(["npx", "vercel", "--prod", "--token", token, "--confirm"], cwd=project_path)
    print("[✅] Deployment triggered.")
