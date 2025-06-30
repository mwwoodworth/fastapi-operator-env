import os


def run(context: dict):
    print("[🛣️] Generating project roadmap...")
    project = context.get("project_name", "MyProject")
    output_file = context.get("output", "ROADMAP.md")
    content = f"# {project} Roadmap\n\n- Placeholder milestones\n"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[✅] Roadmap saved to {output_file}")
