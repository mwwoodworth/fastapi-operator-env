Executive Summary
The backend already delivers a solid task‑runner architecture, memory store, chat assistant, basic RAG, voice → task automation, Make.com & GitHub webhooks, and a minimal PWA dashboard.
To reach production‑grade parity with BrainOps’ AI‑native vision we must:

add streaming AI responses & richer inference orchestration;

finish RAG (vector search, Notion/Tana/ClickUp ingestion, auto‑RAG in chat);

implement missing vertical integrations (ClickUp, Stripe, Slack inbound, roofing agents);

harden auth/security, deployable background workers, testing, CI/CD, observability;

generate a typed TS SDK & full docs;

supply a structured sprint plan so Codex can iterate safely with human‑approved guardrails.

1  Current State Recap
Area	Implemented Highlights	Status
Task engine	Dynamic registry, retry queue, Supabase persistence	✅ Mature
Chat/Copilot	/chat, task suggestions, memory context	⚠️ Blocking: no SSE streaming
Memory & RAG	JSON/Supabase memory, basic doc index, unified RAG agent	⚠️ Basic substring search only
Voice	Whisper transcription → chat‑to‑task → inbox	✅ Prototype
Integrations	Make.com webhook, GitHub webhook, Slack outbound	⚠️ Many inbound APIs missing
Dashboard UI	Static Next.js export served by FastAPI	⚠️ Needs streaming support & richer metrics
Auth/Security	Global HTTP Basic, admin check	⚠️ No JWT, no role/tenant separation
Deployment	Render YAML, Supabase, migrations checklist	⚠️ No background worker, limited file persistence
Tests/CI	Initial pytest folder, no coverage gates	⚠️ Sparse

## 2  Gap Analysis & Completion Requirements

2.1 AI Inference Pipeline
Implement token‑streaming for Claude & GPT models via StreamingResponse or SSE. 
Medium
GitHub

Add async generator helpers; ensure frontend consumes EventSource / fetch stream. 
Medium

Introduce retry / fallback model logic for transient API errors.

Support interrupt / cancel (client abort closes generator).

Build progress events for multi‑step tasks (e.g., voice pipeline).

### 2.2 Retrieval‑Augmented Generation

Replace JSON doc index with pgvector‑backed semantic search in Supabase. 
Supabase
Swizec

Create /rag/documents CRUD endpoints that embed & persist docs.

Finish Notion adapter: implement search & page snippet retrieval with official API. 
Notion Developers
pynotion.com

Build ClickUp search adapter for docs/tasks. 
ClickUp Developer Docs
ClickUp Developer Docs

Integrate auto‑RAG path in /chat: detect knowledge questions, run RAG, inject answer + citations.

### 2.3 Vertical‑Specific Integrations

Vertical	Required Features
Project/PM	Two‑way ClickUp sync (create/update tasks, pull statuses).
Passive Income	Stripe webhook endpoint (signature‑verified) for sale events → sync_sale. 
Stripe Docs
Stripe Docs
Automation	Slack Slash‑command & Events API receiver so operators can query/approve via Slack. 
Slack API
Stack Overflow
Roofing	Initial “Roof AI” task: parse EagleView JSON → quantity take‑off, plus cost‑template generator.

### 2.4 Auth & Security

Replace basic auth with JWT Bearer (FastAPI tutorial pattern). 
FastAPI
TestDriven.io

Support session‑scoped chat (session_id) & role‑based admin check.

CSRF & webhook secrets already partially implemented—extend to all inbound webhooks.

### 2.5 Background & Scheduling

Add Celery/Redis worker (or Baseten/Reflex) for long‑running tasks; expose /tasks/status/{id}. 
TestDriven.io
TestDriven.io

Migrate existing retry queue to Celery beat schedule where appropriate.

Containerize worker in docker-compose.dev.yml & Render background service.

### 2.6 Observability & Ops

Structured JSON logging; export to Render logs & Supabase table.

/metrics Prometheus endpoint; optional Grafana dashboard.

Slack alert improvements: route errors & criticals; weekly digest task.

### 2.7 Testing & CI/CD

Expand pytest to cover ≥ 90 % endpoints; include streaming tests (async TestClient).

Add integration tests for each external API via VCR‑py or mocks.

Add GitHub Actions: lint (black, ruff), type‑check (mypy), test, build Docker; block merges on failure.

### 2.8 Docs & SDK

Annotate every endpoint with Pydantic in/out models for full OpenAPI.

Generate TypeScript client via openapi-typescript-codegen. 
npm

Publish README → docs site (MkDocs Material) with how‑tos.

## 3  Step‑by‑Step Completion Road‑Map

Each numbered step belongs to a sprint (see §4).
Check ☑ as you merge PRs; keep changelog in /misc/CHANGELOG_Agent.md.

### Step 0 — Foundational Cleanup

 Run Alembic migrations on Supabase; ensure pgvector enabled. 
Supabase

 Refactor settings loader; centralise env validation.

 Convert remaining ad‑hoc dict responses to Pydantic models.

### Step 1 — Streaming Chat

 Refactor /chat to /chat/stream using SSE (text/event-stream). 
GitHub

 Update Claude & GPT wrappers to yield tokens.

 Patch dashboard React hook to consume EventSource stream.

### Step 2 — Vector RAG Core

 Create documents table (id, content, metadata, embedding vector).

 Write embed_and_store() helper; use OpenAI ADA‑002.

 Add /knowledge/doc/upload & /knowledge/search vector routes.

### Step 3 — External Integrations

 Notion: adapter functions search_notion_pages, get_page_snippet. 
Notion Developers

 ClickUp: create_task, search_tasks; secret via vault. 
ClickUp Developer Docs

 Slack Inbound: /webhook/slack/command, verify signing secret. 
Slack API

 Stripe: /webhook/stripe, verify signature, enqueue sync_sale. 
Stripe Docs

### Step 4 — Auth & Security

 Implement OAuth2‑Password + JWT per FastAPI docs. 
FastAPI

 Protect secrets endpoints with role admin.

 Migrate dashboard login to JWT flow.

### Step 5 — Background Processing

 Add Celery worker (Redis broker) with example long_task. 
TestDriven.io

 Convert existing recurring scheduler to Celery beat.

 Deploy worker on Render background service.

### Step 6 — Observability & CI

 Add structured logging (loguru).

 /metrics endpoint with Prometheus client.

 GitHub Actions pipeline (lint, type, test, build).

### Step 7 — Docs & SDK

 Finish Pydantic schemas; generate client/brainops-sdk via openapi-typescript-codegen. 
npm

 Publish MkDocs site to GitHub Pages; link in README.

### Step 8 — Roofing Vertical MVP

 Write parse_eagleview_report task → CSV quantities.

 Write generate_roof_estimate that feeds template & pricing sheet.

 Add tests and sample fixtures.

## 4  Codex Sprint Matrix

Create one file per sprint under /sprints/, named sprint‑N‑<slug>.md.
Each file should:

Copy its tasks from the table below (checklist markdown).

Link back to /misc/brainops‑backend‑master‑guide.md.

End with “### Definition of Done” (acceptance criteria).

Sprint	Focus	File	Tasks
0	Foundations & schemas	sprint‑0‑foundation.md	Step 0
1	Streaming chat	sprint‑1‑streaming-chat.md	Step 1
2	Vector RAG	sprint‑2‑vector-rag.md	Step 2
3	Integrations I	sprint‑3‑integrations.md	Step 3
4	Auth & Security	sprint‑4‑auth-security.md	Step 4
5	Background / Worker	sprint‑5‑background.md	Step 5
6	Observability & CI	sprint‑6‑observability.md	Step 6
7	Docs & SDK	sprint‑7‑docs-sdk.md	Step 7
8	Roofing MVP	sprint‑8‑roofing-mvp.md	Step 8

## 5  Development Guard‑Rails for Codex

Prompt Codex with tight specs – excerpt the relevant step task verbatim.

One PR per task; enforce passing CI suite.

Run make lint test locally before committing.

Never store secrets in code – use /secrets/store.

Comment every network call with endpoint & expected status codes.

Write/expand tests alongside implementation; ≥ 90 % coverage gate.

Respect style (black, ruff, types).

After merge, codex must update the sprint file checkboxes and push.

## 6  Resource Pointers & References

FastAPI SSE streaming examples 
Medium
GitHub

Notion search API 
Notion Developers
 & Python tutorial 
pynotion.com

ClickUp task endpoints 
ClickUp Developer Docs
ClickUp Developer Docs

FastAPI JWT/OAuth2 patterns 
FastAPI
TestDriven.io

Supabase pgvector docs 
Supabase
 & similarity tutorial 
Swizec

Stripe webhook signature verification 
Stripe Docs
Stripe Docs

Slack slash command/events guide 
Slack API
Stack Overflow

OpenAPI → TypeScript codegen 
npm

Celery + FastAPI background task patterns 
TestDriven.io
TestDriven.io

Use these sources when Codex requests examples or clarification.
