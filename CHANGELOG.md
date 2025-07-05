# Changelog

## [Unreleased]
- Migrated startup events to FastAPI lifespan.
- Enforced Supabase credentials in production via `ENVIRONMENT` variable.
- Replaced deprecated `datetime.utcnow()` usage with timezone-aware timestamps.
- Documented deployment steps and environment requirements.
