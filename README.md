# BrainOps Operator Environment

This repository contains a lightweight task runner and API server used by the BrainOps automation system. Tasks can be executed via CLI, HTTP API or Make.com webhooks.

## Getting Started

1. Install dependencies and create a local environment file:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   ```
   Fill in the required API keys inside `.env`.

2. (Optional) Enable HTTP Basic Auth by defining users:
   ```bash
   export BASIC_AUTH_USERS='{"admin": "secret"}'
   export ADMIN_USERS=admin
   ```
   All routes will then require authentication.

3. Launch the server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 10000
   ```

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
Set `SLACK_WEBHOOK_URL` to a Slack incoming webhook to get notified when tasks succeed or fail.

## Tasks
Tasks live in `codex/tasks/` and each implements a `run(context)` function returning structured results.

### Demo Data

Sample helpers in the `mock/` folder can be used to generate example events or tasks during onboarding:

```bash
python main.py task run '{"task": "claude_prompt", "context": {"prompt": "demo"}}'
```

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
- `/dashboard/ui` - live dashboard interface.
- `/memory/search` - search memories with filters.
- `/logs/errors` - recent error entries.
- `/mobile/task` - quick mobile task capture.
- `/agent/forecast/weekly` - generate a 7-day forecast plan.
- `/dashboard/forecast` - view the rolling task timeline.
- `/agent/strategy/weekly` - run the weekly strategy agent.
- `/task/dependency-map` - create a dependency map for tasks.
- `/feedback/report` - submit bug reports or suggestions.

## Deployment
Use `uvicorn main:app` locally. For cloud deploy, create a Render or Vercel service using the provided `render.yaml` and ensure all environment variables from `.env` are set.
The dashboard at `/dashboard/ui` includes a PWA manifest. Open the page in a modern mobile browser and choose **Add to Home Screen** to install it like a native app.

## Dashboard UI

A production-ready dashboard is located in `dashboard_ui/` built with Next.js, Tailwind CSS and shadcn/ui components. It can be deployed statically or embedded via `<iframe>`.

### Build & Export

```bash
cd dashboard_ui
npm install
npm run build && npm run export
```

The export step outputs static files to `static/dashboard/` which FastAPI serves at `/dashboard/ui`.

### Deploy

- **Vercel/Netlify:** deploy `dashboard_ui` as a static site.
- **FastAPI static:** copy the exported files to `static/dashboard/` on your server.

### Embed

Include the dashboard in another site using:

```html
<iframe src="/dashboard/ui" width="100%" height="600" style="border:0;"></iframe>
```

### Customization

- API endpoint base URL and auth can be set via `NEXT_PUBLIC_API_BASE` and TODO auth headers in `dashboard_ui` components.
- Branding and styling can be tweaked in `dashboard_ui/styles` and React components.

