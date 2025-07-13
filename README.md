# BrainOps Operator Environment

[![CI](https://github.com/brain-stack-studio/fastapi-operator-env/actions/workflows/ci.yml/badge.svg)](https://github.com/brain-stack-studio/fastapi-operator-env/actions/workflows/ci.yml)

This repository contains a lightweight task runner and API server used by the BrainOps automation system. Tasks can be executed via CLI, HTTP API or Make.com webhooks.

Continuous integration runs linting, type checks and tests with coverage to ensure code quality.

## Getting Started

1. Install dependencies and create a local environment file:
   ```bash
   pip install -r requirements.txt
   cp .env.example .env
   ```
   Fill in the required API keys inside `.env`.

2. Enable JWT auth by defining users:
   ```bash
   export AUTH_USERS='{"admin": "secret"}'
   export ADMIN_USERS=admin
   ```
   Obtain a token via `/auth/token` and include `Authorization: Bearer <token>` on requests.

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
The endpoint queues the task on Celery and returns a `task_id`. Use
`/task/status/{id}` to query the result.

## Environment
Copy `.env.example` to `.env` and fill in the required keys. Configuration is
loaded via `core/settings.py` using Pydantic's `BaseSettings`, which reads the
`.env` file automatically. Set `ENVIRONMENT=production` when deploying so missing
required variables raise an error. Supabase credentials are required in
production for persistent memory storage. Set `SLACK_WEBHOOK_URL` to a Slack
incoming webhook to get notified when tasks succeed or fail.

### Slack commands
Register a `/brainops` slash command in your Slack workspace pointing to
`/webhook/slack/command`. Set `SLACK_SIGNING_SECRET` so requests can be
verified. Commands include:

* `approve <id>` – run and mark an inbox task approved
* `reject <id>` – mark a task rejected
* `status <id>` – view the stored status
* `query <text>` – search recent memory for information

Slack Events can be sent to `/webhook/slack/event` if you want to store
messages from channels.

### Database migrations
Before running the server in production, apply the Alembic migrations to ensure
the database schema and extensions are up to date:

```bash
alembic upgrade head
```

`DATABASE_URL` must point to your Supabase Postgres instance for the migrations
to run successfully.

## Tasks
Tasks live in `codex/tasks/` and each implements a `run(context)` function returning structured results.

### Demo Data

Sample helpers in the `mock/` folder can be used to generate example events or tasks during onboarding:

```bash
python main.py task run '{"task": "claude_prompt", "context": {"prompt": "demo"}}'
```

New automation tasks power BrainStackStudio's publishing workflow:

- `autopublish_content` – publish an article to the site, trigger Make.com marketplace uploads and optionally send a newsletter.
- `sync_sale` – notify Make.com of a new sale to start onboarding and CRM sync.
- `generate_product_docs` – create product docs with Claude and push them to your documentation site.
- `parse_eagleview_report` – convert EagleView JSON into a CSV quantity take‑off.
- `generate_roof_estimate` – calculate material and labor costs from roof quantities.

See `docs/production_checklist.md` for a go-live checklist.

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
- `/metrics` - Prometheus metrics for monitoring.
- `/dashboard/ui` - live dashboard interface.
- `/dashboard/copilot-v2` - memory-assisted Copilot v2.
- `/dashboard/pipeline` - Claude category pipelines.
- `/dashboard/products` - marketplace-ready documents.
- `/dashboard/export` - export markdown system.
- `/memory/search` - search memories with filters.
- `/knowledge/doc/upload` - add a new knowledge document with vector embedding.
- `/knowledge/search` - semantic search across uploaded documents.
- `/logs/errors` - recent error entries.
- `/mobile/task` - quick mobile task capture.
- `/agent/forecast/weekly` - generate a 7-day forecast plan.
- `/dashboard/forecast` - view the rolling task timeline.
- `/agent/strategy/weekly` - run the weekly strategy agent.
- `/task/dependency-map` - create a dependency map for tasks.
- `/feedback/report` - submit bug reports or suggestions.
- `docs/production_checklist.md` - production readiness guide.

## Deployment
Use `uvicorn main:app` locally. For cloud deploy, create a Render or Vercel service using the provided `render.yaml` and ensure all environment variables from `.env` are set.
The dashboard at `/dashboard/ui` includes a PWA manifest. Open the page in a modern mobile browser and choose **Add to Home Screen** to install it like a native app.

## Dashboard UI

A production-ready dashboard is located in `dashboard_ui/` built with Next.js, Tailwind CSS and shadcn/ui components. It can be deployed statically or embedded via `<iframe>`.

## Marketing Site

The same Next.js project also hosts a lightweight marketing site for BrainStack Studio. Visit `/`, `/products`, `/services`, `/about`, `/contact`, `/newsletter` or `/blog` for the public pages. The contact form submits to `/api/contact` and forwards data to the `MAKE_WEBHOOK_URL` if set. Newsletter signups are sent to `/api/newsletter/subscribe` using the provider configured in `.env`.

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
The same snippet works in Tana, Google Sites or any platform that allows iframes.

### Customization

- API endpoint base URL is configured with `NEXT_PUBLIC_API_BASE`.
- JWT tokens are read from `localStorage.token` when available. You can set `NEXT_PUBLIC_AUTH_HEADER` to force a static header value.
- Optional `MAKE_WEBHOOK_URL` is used by the contact form to forward submissions.
- Branding and styling can be tweaked in `dashboard_ui/styles` and React components.

### BrainOps AI Assistant

The dashboard includes a persistent chat widget that proxies to the FastAPI `/chat` endpoint via `/api/assistant/chat`.
Use it to summarize memory or trigger tasks. Conversations are saved to Supabase for later review.

## Documentation

The full documentation site is published via [MkDocs](https://brain-stack-studio.github.io/fastapi-operator-env/). To run it locally:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

An OpenAPI schema is available at `/openapi.json` and the repository includes a pre-generated TypeScript SDK under `sdk/`.
To regenerate it manually run:

```bash
curl http://localhost:10000/openapi.json -o openapi.json
npx openapi-typescript-codegen --input openapi.json --output sdk --useOptions --exportSchemas true
```

If you are working inside `dashboard_ui` simply run `npm run generate:sdk` to update the bundled client library.

### Icon Assets
Icon files such as `favicon.svg` are not stored in this repository. After merging any changes, upload the required `.svg` and `.ico` assets manually on GitHub.
