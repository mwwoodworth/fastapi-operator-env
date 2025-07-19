"""
Settings management with secure credential handling
"""

import json
from typing import Dict, List, Any, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def mask_secret(secret: str, show_chars: int = 4) -> str:
    """Mask sensitive data, showing only first and last N characters"""
    if not secret or len(secret) <= show_chars * 2:
        return "***"
    return f"{secret[:show_chars]}...{secret[-show_chars:]}"


class Settings(BaseSettings):
    """Application settings with validation"""

    # Application Info
    APP_NAME: str = Field(default="BrainOps Backend", env="APP_NAME")
    APP_VERSION: str = Field(default="1.0.0", env="APP_VERSION")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    API_V1_PREFIX: str = Field(default="/api/v1", env="API_V1_PREFIX")

    # General Configuration
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    debug_mode: bool = Field(default=False, env="DEBUG_MODE")
    timezone: str = Field(default="UTC", env="TIMEZONE")

    # Security
    SECRET_KEY: str = Field(
        default="change-me-in-production", env="SECRET_KEY"
    )
    API_KEYS: str = Field(default="", env="API_KEYS")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")
    JWT_SECRET: str = Field(default="change-me-in-production", env="JWT_SECRET")
    JWT_ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    JWT_EXPIRATION_HOURS: int = Field(default=24, env="JWT_EXPIRATION_HOURS")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    
    # Frontend
    FRONTEND_URL: str = Field(default="http://localhost:3000", env="FRONTEND_URL")
    
    # API Limits
    MAX_API_KEYS_PER_USER: int = Field(default=5, env="MAX_API_KEYS_PER_USER")
    
    # ClickUp
    CLICKUP_API_KEY: Optional[str] = Field(default=None, env="CLICKUP_API_KEY")
    CLICKUP_WORKSPACE_ID: Optional[str] = Field(default=None, env="CLICKUP_WORKSPACE_ID")
    CLICKUP_DEFAULT_LIST_ID: Optional[str] = Field(default=None, env="CLICKUP_DEFAULT_LIST_ID")
    CLICKUP_ESTIMATE_LIST_ID: Optional[str] = Field(default=None, env="CLICKUP_ESTIMATE_LIST_ID")
    clickup_api_token: Optional[str] = Field(default=None, env="CLICKUP_API_TOKEN")
    clickup_workspace_id: Optional[str] = Field(default=None, env="CLICKUP_WORKSPACE_ID")
    clickup_folder_ids: Optional[Dict[str, str]] = Field(default=None, env="CLICKUP_FOLDER_IDS")
    CLICKUP_WEBHOOK_SECRET: Optional[str] = Field(default=None, env="CLICKUP_WEBHOOK_SECRET")
    
    # Notion
    NOTION_API_KEY: Optional[str] = Field(default=None, env="NOTION_API_KEY")
    NOTION_TASKS_DB_ID: Optional[str] = Field(default=None, env="NOTION_TASKS_DB_ID")
    NOTION_KNOWLEDGE_DB_ID: Optional[str] = Field(default=None, env="NOTION_KNOWLEDGE_DB_ID")
    NOTION_ESTIMATES_DB_ID: Optional[str] = Field(default=None, env="NOTION_ESTIMATES_DB_ID")
    notion_api_token: Optional[str] = Field(default=None, env="NOTION_API_TOKEN")
    notion_database_ids: Optional[Dict[str, str]] = Field(default=None, env="NOTION_DATABASE_IDS")

    # GitHub
    github_token: Optional[str] = Field(default=None, env="GITHUB_TOKEN")
    github_repos: Optional[List[str]] = Field(
        default=None, env="GITHUB_REPOS"
    )

    # Slack
    SLACK_BOT_TOKEN: Optional[str] = Field(default=None, env="SLACK_BOT_TOKEN")
    SLACK_SIGNING_SECRET: Optional[str] = Field(default=None, env="SLACK_SIGNING_SECRET")
    SLACK_DEFAULT_CHANNEL: str = Field(default="#general", env="SLACK_DEFAULT_CHANNEL")
    SLACK_APPROVAL_CHANNEL: Optional[str] = Field(default=None, env="SLACK_APPROVAL_CHANNEL")
    slack_webhook_url: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")
    slack_alert_channel: str = Field(default="#alerts", env="SLACK_ALERT_CHANNEL")
    
    # Supabase
    SUPABASE_URL: Optional[str] = Field(default=None, env="SUPABASE_URL")
    SUPABASE_ANON_KEY: Optional[str] = Field(
        default=None, env="SUPABASE_ANON_KEY"
    )
    SUPABASE_DB_URL: Optional[str] = Field(
        default=None, env="SUPABASE_DB_URL"
    )
    supabase_service_key: Optional[str] = Field(
        default=None, env="SUPABASE_SERVICE_KEY"
    )
    supabase_db_password: Optional[str] = Field(
        default=None, env="SUPABASE_DB_PASSWORD"
    )

    # Airtable
    airtable_api_key: Optional[str] = Field(
        default=None, env="AIRTABLE_API_KEY"
    )
    airtable_base_ids: Optional[Dict[str, str]] = Field(
        default=None, env="AIRTABLE_BASE_IDS"
    )

    # Stripe
    stripe_api_key_live: Optional[str] = Field(default=None, env="STRIPE_API_KEY_LIVE")
    stripe_api_key_test: Optional[str] = Field(default=None, env="STRIPE_API_KEY_TEST")
    stripe_webhook_secret: Optional[str] = Field(default=None, env="STRIPE_WEBHOOK_SECRET")
    STRIPE_SECRET_KEY: Optional[str] = Field(default=None, env="STRIPE_SECRET_KEY")

    make_webhook_secret: Optional[str] = Field(default=None, env="MAKE_WEBHOOK_SECRET")
    make_webhook_base_url: Optional[str] = Field(default=None, env="MAKE_WEBHOOK_BASE_URL")
    MAKE_WEBHOOK_SECRETS: Optional[Dict[str, str]] = Field(default=None, env="MAKE_WEBHOOK_SECRETS")
    GENERIC_WEBHOOK_INTEGRATIONS: Optional[Dict[str, Any]] = Field(default=None, env="GENERIC_WEBHOOK_INTEGRATIONS")
    
    # Render
    render_api_key: Optional[str] = Field(
        default=None, env="RENDER_API_KEY"
    )
    render_service_ids: Optional[Dict[str, str]] = Field(
        default=None, env="RENDER_SERVICE_IDS"
    )

    # Vercel
    vercel_token: Optional[str] = Field(default=None, env="VERCEL_TOKEN")
    vercel_team_id: Optional[str] = Field(
        default=None, env="VERCEL_TEAM_ID"
    )

    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")

    GOOGLE_AI_API_KEY: Optional[str] = Field(default=None, env="GOOGLE_AI_API_KEY")
    EMBEDDING_MODEL: str = Field(default="text-embedding-3-small", env="EMBEDDING_MODEL")

    # Claude/Anthropic
    claude_api_key: Optional[str] = Field(default=None, env="CLAUDE_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    
    # Gemini
    GEMINI_API_KEY: Optional[str] = Field(default=None, env="GEMINI_API_KEY")

    COST_THRESHOLD_USD: float = Field(default=100.0, env="COST_THRESHOLD_USD")
    
    # Email
    resend_api_key: Optional[str] = Field(
        default=None, env="RESEND_API_KEY"
    )
    email_alert_recipients: Optional[List[str]] = Field(
        default=None, env="EMAIL_ALERT_RECIPIENTS"
    )
    # Email settings (using both conventions for compatibility)
    EMAIL_HOST: str = Field(default="smtp.gmail.com", env="EMAIL_HOST")
    EMAIL_PORT: int = Field(default=587, env="EMAIL_PORT")
    EMAIL_USERNAME: Optional[str] = Field(default=None, env="EMAIL_USERNAME")
    EMAIL_PASSWORD: Optional[str] = Field(default=None, env="EMAIL_PASSWORD")
    EMAIL_FROM: str = Field(default="noreply@brainops.com", env="EMAIL_FROM")
    EMAIL_USE_TLS: bool = Field(default=True, env="EMAIL_USE_TLS")
    
    # SMTP settings (for notification service compatibility)
    SMTP_HOST: str = Field(default="smtp.gmail.com", env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = Field(default="noreply@brainops.com", env="SMTP_FROM_EMAIL")
    SMTP_USE_TLS: bool = Field(default=True, env="SMTP_USE_TLS")
    
    # SendGrid and AWS SES
    SENDGRID_API_KEY: Optional[str] = Field(default=None, env="SENDGRID_API_KEY")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")

    # Monitoring
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")

    # Webhooks
    make_webhook_url: Optional[str] = Field(
        default=None, env="MAKE_WEBHOOK_URL"
    )

    # Security
    fernet_secret: Optional[str] = Field(default=None, env="FERNET_SECRET")
    jwt_secret: Optional[str] = Field(default=None, env="JWT_SECRET")

    # Alert Configuration
    alert_cooldown_minutes: int = Field(
        default=15, env="ALERT_COOLDOWN_MINUTES"
    )
    error_threshold: int = Field(default=5, env="ERROR_THRESHOLD")
    response_time_threshold_ms: int = Field(
        default=5000, env="RESPONSE_TIME_THRESHOLD_MS"
    )
    error_window_minutes: int = Field(
        default=5, env="ERROR_WINDOW_MINUTES"
    )
    max_webhook_retries: int = Field(
        default=3, env="MAX_WEBHOOK_RETRIES"
    )

    # Feature Flags
    enable_slack_alerts: bool = Field(
        default=True, env="ENABLE_SLACK_ALERTS"
    )
    enable_email_alerts: bool = Field(
        default=True, env="ENABLE_EMAIL_ALERTS"
    )
    enable_health_checks: bool = Field(
        default=True, env="ENABLE_HEALTH_CHECKS"
    )
    enable_auto_deploy: bool = Field(
        default=False, env="ENABLE_AUTO_DEPLOY"
    )
    enable_webhook_alerts: bool = Field(
        default=True, env="ENABLE_WEBHOOK_ALERTS"
    )
    enable_performance_monitoring: bool = Field(
        default=True, env="ENABLE_PERFORMANCE_MONITORING"
    )
    enable_ai_monitoring: bool = Field(
        default=True, env="ENABLE_AI_MONITORING"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///brainops_bot.db", env="DATABASE_URL"
    )

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"  # Allow extra fields

    @validator(
        "clickup_folder_ids", "notion_database_ids",
        "airtable_base_ids", "render_service_ids", pre=True
    )
    def parse_json_field(cls, v):
        """Parse JSON string fields"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    @validator("github_repos", "email_alert_recipients", pre=True)
    def parse_list_field(cls, v):
        """Parse comma-separated or JSON list fields"""
        if isinstance(v, str):
            if v.startswith('['):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return []
            else:
                return [x.strip() for x in v.split(',') if x.strip()]
        return v

    def get_enabled_services(self) -> List[str]:
        """Return list of services that have credentials configured"""
        services = []

        if self.clickup_api_token:
            services.append('clickup')
        if self.notion_api_token:
            services.append('notion')
        if self.github_token:
            services.append('github')
        if self.SLACK_BOT_TOKEN:
            services.append('slack')
        if self.airtable_api_key:
            services.append('airtable')
        if self.SUPABASE_URL and self.SUPABASE_ANON_KEY:
            services.append('supabase')
        if self.stripe_api_key_live or self.stripe_api_key_test:
            services.append('stripe')
        if self.render_api_key:
            services.append('render')
        if self.vercel_token:
            services.append('vercel')
        if self.openai_api_key:
            services.append('openai')
        if self.claude_api_key:
            services.append('claude')

        return services

    def get_service_config(self, service: str) -> Dict[str, Any]:
        """Get configuration for a specific service"""
        configs = {
            'clickup': {
                'api_token': self.clickup_api_token,
                'workspace_id': self.clickup_workspace_id,
                'folder_ids': self.clickup_folder_ids,
            },
            'notion': {
                'api_token': self.notion_api_token,
                'database_ids': self.notion_database_ids,
            },
            'github': {
                'token': self.github_token,
                'repos': self.github_repos,
            },
            'slack': {
                'bot_token': self.SLACK_BOT_TOKEN,
                'signing_secret': self.SLACK_SIGNING_SECRET,
                'webhook_url': self.slack_webhook_url,
                'alert_channel': self.slack_alert_channel,
                'default_channel': self.SLACK_DEFAULT_CHANNEL,
                'approval_channel': self.SLACK_APPROVAL_CHANNEL,
            },
            'airtable': {
                'api_key': self.airtable_api_key,
                'base_ids': self.airtable_base_ids,
            },
            'supabase': {
                'url': self.SUPABASE_URL,
                'anon_key': self.SUPABASE_ANON_KEY,
                'db_url': self.SUPABASE_DB_URL,
            },
            'stripe': {
                'api_key_live': self.stripe_api_key_live,
                'api_key_test': self.stripe_api_key_test,
                'webhook_secret': self.stripe_webhook_secret,
            },
            'render': {
                'api_key': self.render_api_key,
                'service_ids': self.render_service_ids,
            },
            'vercel': {
                'token': self.vercel_token,
                'team_id': self.vercel_team_id,
            },
            'openai': {
                'api_key': self.openai_api_key,
            },
            'claude': {
                'api_key': self.claude_api_key,
            },
        }

        return configs.get(service, {})

    def mask_secrets(self) -> Dict[str, str]:
        """Return configuration with masked secrets for logging"""
        masked = {}

        for field_name, field_value in self.dict().items():
            if field_value is None:
                continue

            if any(secret_word in field_name.lower()
                   for secret_word in ['token', 'key', 'secret', 'password']):
                if isinstance(field_value, str):
                    masked[field_name] = mask_secret(field_value)
                else:
                    masked[field_name] = str(field_value)
            else:
                masked[field_name] = str(field_value)

        return masked
    
    def validate_required_integrations(self) -> Dict[str, bool]:
        """Check which integrations are configured"""
        return {
            'clickup': bool(self.CLICKUP_API_KEY),
            'notion': bool(self.NOTION_API_KEY),
            'slack': bool(self.SLACK_BOT_TOKEN),
            'supabase': bool(self.SUPABASE_URL and self.SUPABASE_ANON_KEY),
            'openai': bool(self.openai_api_key),
            'claude': bool(self.claude_api_key),
            'github': bool(self.github_token),
            'stripe': bool(self.stripe_api_key_live or self.stripe_api_key_test),
            'render': bool(self.render_api_key),
            'vercel': bool(self.vercel_token),
        }
    
    def get_ai_limits(self) -> Dict[str, Any]:
        """Get AI service limits and configuration"""
        return {
            'openai': {
                'max_tokens': 4096,
                'model': 'gpt-4-turbo-preview',
                'temperature': 0.7
            },
            'claude': {
                'max_tokens': 4096,
                'model': 'claude-3-opus-20240229',
                'temperature': 0.7
            }
        }

    def validate_required_integrations(self) -> Dict[str, str]:
        """Validate and return status of required integrations."""
        integrations = {}

        # Check each integration
        if self.clickup_api_token:
            integrations["clickup"] = "configured"
        else:
            integrations["clickup"] = "not configured"

        if self.notion_api_token:
            integrations["notion"] = "configured"
        else:
            integrations["notion"] = "not configured"

        if self.SLACK_BOT_TOKEN:
            integrations["slack"] = "configured"
        else:
            integrations["slack"] = "not configured"

        if self.SUPABASE_URL and self.SUPABASE_ANON_KEY:
            integrations["supabase"] = "configured"
        else:
            integrations["supabase"] = "not configured"

        return integrations

    def get_ai_limits(self) -> Dict[str, Any]:
        """Get AI service limits and configuration."""
        return {
            "openai": {
                "configured": bool(self.openai_api_key),
                "model": "gpt-4",
                "max_tokens": 4000
            },
            "claude": {
                "configured": bool(
                    self.claude_api_key or self.ANTHROPIC_API_KEY
                ),
                "model": "claude-3-sonnet",
                "max_tokens": 4000
            },
            "google": {
                "configured": bool(self.GOOGLE_AI_API_KEY),
                "model": "gemini-pro",
                "max_tokens": 4000
            }
        }

    def ensure_critical_settings(self) -> None:
        """Validate presence of essential runtime configuration."""
        missing = []

        if not self.SECRET_KEY or self.SECRET_KEY == "change-me-in-production":
            missing.append("SECRET_KEY")
        if not self.database_url:
            missing.append("DATABASE_URL")
        if not (self.SUPABASE_URL and self.SUPABASE_ANON_KEY):
            missing.append("SUPABASE_URL/SUPABASE_ANON_KEY")

        if missing:
            raise ValueError(
                f"Missing required settings: {', '.join(missing)}"
            )


# Create global settings instance
settings = Settings()
