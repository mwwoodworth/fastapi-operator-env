# BrainOps Operator Environment

This repository contains a lightweight task runner and API server used by the BrainOps automation system. Tasks can be executed via CLI, HTTP API or Make.com webhooks.

## Usage

### CLI
Run tasks locally using either key/value flags or the JSON wrapper:
```bash
python main.py task run '{"task": "create_tana_node", "context": {"content": "CLI test"}}'
```

### API
Start the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 10000
```
Then POST to `/task/run` with JSON body:
```json
{"task": "deploy_vercel", "context": {"project_path": "."}}
```

## Environment
Copy `.env.example` to `.env` and fill in the required keys. Set `ENVIRONMENT=production`
when deploying to Render or Vercel so the server fails fast if mandatory secrets
are missing. Supabase credentials are required in production for persistent
memory storage.

## Tasks
Tasks live in `codex/tasks/` and each implements a `run(context)` function returning structured results.

### Secrets Vault

The API exposes endpoints under `/secrets` for storing and retrieving encrypted credentials. Example:

```bash
curl -X POST http://localhost:10000/secrets/store -H "Content-Type: application/json" -d '{"name":"CLAUDE_API_KEY","value":"sk-xyz"}'
```

You can view available tasks by calling the `/docs/registry` endpoint once the server is running.

Additional helpful endpoints:

- `/webhook/make` - trigger tasks from Make.com.
- `/diagnostics/state` - view operator status snapshot.
- `/voice/status` - latest voice transcript processing info.
- `/voice/history` - recent transcription records.
- `/agent/inbox` - pending task queue.
- `/agent/inbox/approve` - approve or reject tasks.
- `/agent/inbox/summary` - inbox counts overview.
- `/dashboard/full` - extended operator metrics.
- `/dashboard/metrics` - summary counts of tasks and memory logs.
- `/mobile/task` - quick mobile task capture.
- `/agent/forecast/weekly` - generate a 7-day forecast plan.
- `/dashboard/forecast` - view the rolling task timeline.
- `/agent/strategy/weekly` - run the weekly strategy agent.
- `/task/dependency-map` - create a dependency map for tasks.

## Deployment
Use `uvicorn main:app` locally. For cloud deploy, create a Render or Vercel service using the provided `render.yaml` and ensure all environment variables from `.env` are set.
