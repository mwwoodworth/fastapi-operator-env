# Task Development Guide

Automation tasks live in `codex/tasks`. Each task exposes a `run(context)` function returning JSON serialisable data.

To add a new task:
1. Create a file in `codex/tasks/` and implement `run(context)`.
2. Register the task in `codex/__init__.py` using `brainops_operator.register_task`.
3. Include a description and required fields for documentation.
4. Write tests to cover the new behaviour.
