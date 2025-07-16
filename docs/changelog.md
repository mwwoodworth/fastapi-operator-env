# Changelog

## [Unreleased]
- Migrated startup events to FastAPI lifespan.
- Enforced Supabase credentials in production via `ENVIRONMENT` variable.
- Replaced deprecated `datetime.utcnow()` usage with timezone-aware timestamps.
- Documented deployment steps and environment requirements.
- Added `/dashboard/metrics` endpoint for quick log summaries.
- Added `/dashboard/ui` static dashboard with live charts.
- Implemented `/memory/search` and `/logs/errors` endpoints.
- Optional BasicAuth via `BASIC_AUTH_USERS` env var.
- Slack notifications via `SLACK_WEBHOOK_URL`.
- Added PWA `manifest.json` for installable dashboard.
