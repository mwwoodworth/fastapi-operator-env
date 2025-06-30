# BrainOps Operator Environment

This repository contains a lightweight task runner and API server used by the BrainOps automation system. Tasks can be executed via CLI, HTTP API or Make.com webhooks.

## Usage

### CLI
```bash
python main.py <task_name> --key value
```

### API
Start the server:
```bash
uvicorn main_api:app --host 0.0.0.0 --port 8000
```
Then POST to `/run-task` with JSON body:
```json
{"task": "deploy_vercel", "context": {"project_path": "."}}
```

## Environment
Copy `.env.example` to `.env` and fill in the required keys.

## Tasks
Tasks live in `codex/tasks/` and each implements a `run(context)` function returning structured results.
