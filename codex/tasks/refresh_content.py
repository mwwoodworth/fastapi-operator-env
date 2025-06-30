import subprocess


def run(context: dict):
    print("[🔄] Refreshing site content...")
    content_dir = context.get("content_dir", "content")
    subprocess.run(["git", "pull"], cwd=content_dir)
    print("[✅] Content refreshed.")
