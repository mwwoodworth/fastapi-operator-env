import subprocess

def run(context: dict):
    print("[🔄] Syncing FastAPI changes...")
    result = subprocess.run(["uvicorn", "main:app", "--reload"], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[❌] Error syncing: {result.stderr}")
    else:
        print("[✅] FastAPI app restarted with live reload.")
