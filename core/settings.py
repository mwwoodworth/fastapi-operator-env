from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env."""

    ENVIRONMENT: str = "development"

    OPENAI_API_KEY: str | None = None
    CLAUDE_API_KEY: str | None = None
    CHATGPT_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    API_BASE: str | None = None

    FERNET_SECRET: str

    VERCEL_TOKEN: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_URL: str
    STRIPE_SECRET_KEY: str
    REDIS_URL: str = "redis://localhost:6379/0"

    MAKE_WEBHOOK_SECRET: str | None = None
    BRAINSTACK_API_URL: str | None = None
    BRAINSTACK_API_KEY: str | None = None
    MAKE_PUBLISH_WEBHOOK: str | None = None
    MAKE_SALE_WEBHOOK: str | None = None
    NEWSLETTER_API_URL: str | None = None
    NEWSLETTER_API_KEY: str | None = None
    DOCS_WEBHOOK_URL: str | None = None

    GITHUB_SECRET: str | None = None
    GOOGLE_API_SERVICE_ACCOUNT: str | None = None
    TANA_API_KEY: str
    NOTION_API_KEY: str | None = None
    NOTION_DB_ID: str | None = None
    RAG_INDEX_ENABLED: bool = True
    KNOWLEDGE_DOC_DIR: str = "data/docs/"

    TANA_AUTO_TAG: str = "auto_execute"
    SUMMARY_TAG: str = "summary_candidate"

    GITHUB_DEPLOY_HASH_KEY: str | None = None
    TANA_NODE_CALLBACK: bool = False
    VOICE_UPLOAD_RETENTION_DAYS: int = 30

    DEBUG_MODE: bool = False
    AI_FEEDBACK_CHAIN: str | None = None

    AI_ROUTER_MODE: str = "auto"
    WHISPER_MODEL_SIZE: str = "base"
    VOICE_UPLOAD_DIR: str = "uploads"
    CHAT_SYSTEM_PROMPT: str = (
        "You are BrainOps Operator, a fast, reliable assistant for project execution."
    )
    TRACE_FEEDBACK_ENABLED: bool = True
    TRACE_VIEW_LIMIT: int = 50

    INBOX_SUPABASE_TABLE: str = "agent_inbox"
    INBOX_SUMMARIZER_MODEL: str = "claude"
    PUSH_WEBHOOK_URL: str | None = None
    PUSH_DEVICE_ID: str | None = None
    DAILY_PLAN_TIME: str = "07:00"
    INBOX_ALERT_THRESHOLD: int = 3
    RECURRING_TASK_CHECK_INTERVAL: int = 30
    RETRY_FAILURE_LIMIT: int = 3
    CLAUDE_WEEKLY_PRIORITY_DAY: str = "Sunday"
    CLAUDE_WEEKLY_PRIORITY_TIME: str = "16:00"
    FORECAST_PLANNER_ENABLED: bool = True
    WEEKLY_STRATEGY_DAY: str = "Sunday"
    DAILY_PLANNER_MODEL: str = "claude"
    ESCALATION_CHECK_INTERVAL: int = 1800
    CLAUDE_LOG_FOLDER_ID: str | None = None

    AUTH_USERS: str | None = None
    ADMIN_USERS: str | None = None
    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    TASK_WEBHOOK_SECRET: str | None = None
    STATUS_UPDATE_SECRET: str | None = None
    GEMINI_WEBHOOK_SECRET: str | None = None
    SLACK_WEBHOOK_URL: str | None = None
    SLACK_SIGNING_SECRET: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    CLICKUP_API_TOKEN: str | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
