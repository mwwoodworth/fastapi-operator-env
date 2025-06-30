import subprocess


def run(context: dict):
    print("[🧪] Running test suite...")
    project = context.get("project_name", "MyProject")
    subprocess.run(["echo", f"Simulated tests for {project}"])
    print("[✅] Tests completed.")
