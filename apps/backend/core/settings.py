"""
Settings management with secure credential handling
"""

import os
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
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
    
    # General Configuration
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    debug_mode: bool = Field(default=False, env="DEBUG_MODE")
    timezone: str = Field(default="UTC", env="TIMEZONE")
    
    # Security
    SECRET_KEY: str = Field(default="change-me-in-production", env="SECRET_KEY")
    API_KEYS: str = Field(default="", env="API_KEYS")
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000", "http://localhost:8000"], env="CORS_ORIGINS")
    
    # ClickUp
    clickup_api_token: Optional[str] = Field(default=None, env="CLICKUP_API_TOKEN")
    clickup_workspace_id: Optional[str] = Field(default=None, env="CLICKUP_WORKSPACE_ID")
    clickup_folder_ids: Optional[Dict[str, str]] = Field(default=None, env="CLICKUP_FOLDER_IDS")
    
    # Notion
    notion_api_token: Optional[str] = Field(default=None, env="NOTION_API_TOKEN")
    notion_database_ids: Optional[Dict[str, str]] = Field(default=None, env="NOTION_DATABASE_IDS")
    
    # GitHub
    github_token: Optional[str] = Field(default=None, env="GITHUB_TOKEN")
    github_repos: Optional[List[str]] = Field(default=None, env="GITHUB_REPOS")
    
    # Slack
    slack_bot_token: Optional[str] = Field(default=None, env="SLACK_BOT_TOKEN")
    slack_webhook_url: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")
    slack_alert_channel: str = Field(default="#alerts", env="SLACK_ALERT_CHANNEL")
    
    # Supabase
    SUPABASE_URL: Optional[str] = Field(default=None, env="SUPABASE_URL")
    SUPABASE_ANON_KEY: Optional[str] = Field(default=None, env="SUPABASE_ANON_KEY")
    SUPABASE_DB_URL: Optional[str] = Field(default=None, env="SUPABASE_DB_URL")
    
    # Airtable
    airtable_api_key: Optional[str] = Field(default=None, env="AIRTABLE_API_KEY")
    airtable_base_ids: Optional[Dict[str, str]] = Field(default=None, env="AIRTABLE_BASE_IDS")
    
    # Stripe
    stripe_api_key_live: Optional[str] = Field(default=None, env="STRIPE_API_KEY_LIVE")
    stripe_api_key_test: Optional[str] = Field(default=None, env="STRIPE_API_KEY_TEST")
    stripe_webhook_secret: Optional[str] = Field(default=None, env="STRIPE_WEBHOOK_SECRET")
    
    # Render
    render_api_key: Optional[str] = Field(default=None, env="RENDER_API_KEY")
    render_service_ids: Optional[Dict[str, str]] = Field(default=None, env="RENDER_SERVICE_IDS")
    
    # Vercel
    vercel_token: Optional[str] = Field(default=None, env="VERCEL_TOKEN")
    vercel_team_id: Optional[str] = Field(default=None, env="VERCEL_TEAM_ID")
    
    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    
    # Claude
    claude_api_key: Optional[str] = Field(default=None, env="CLAUDE_API_KEY")
    
    # Email
    resend_api_key: Optional[str] = Field(default=None, env="RESEND_API_KEY")
    email_alert_recipients: Optional[List[str]] = Field(default=None, env="EMAIL_ALERT_RECIPIENTS")
    
    # Security
    fernet_secret: Optional[str] = Field(default=None, env="FERNET_SECRET")
    jwt_secret: Optional[str] = Field(default=None, env="JWT_SECRET")
    
    # Alert Configuration
    alert_cooldown_minutes: int = Field(default=15, env="ALERT_COOLDOWN_MINUTES")
    error_threshold: int = Field(default=5, env="ERROR_THRESHOLD")
    response_time_threshold_ms: int = Field(default=5000, env="RESPONSE_TIME_THRESHOLD_MS")
    
    # Feature Flags
    enable_slack_alerts: bool = Field(default=True, env="ENABLE_SLACK_ALERTS")
    enable_email_alerts: bool = Field(default=True, env="ENABLE_EMAIL_ALERTS")
    enable_health_checks: bool = Field(default=True, env="ENABLE_HEALTH_CHECKS")
    enable_auto_deploy: bool = Field(default=False, env="ENABLE_AUTO_DEPLOY")
    
    # Database
    database_url: str = Field(default="sqlite:///brainops_bot.db", env="DATABASE_URL")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        
    @validator("clickup_folder_ids", "notion_database_ids", "airtable_base_ids", "render_service_ids", pre=True)
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
        if self.slack_bot_token:
            services.append('slack')
        if self.airtable_api_key:
            services.append('airtable')
        if self.supabase_url and self.supabase_anon_key:
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
                'bot_token': self.slack_bot_token,
                'webhook_url': self.slack_webhook_url,
                'alert_channel': self.slack_alert_channel,
            },
            'airtable': {
                'api_key': self.airtable_api_key,
                'base_ids': self.airtable_base_ids,
            },
            'supabase': {
                'url': self.supabase_url,
                'anon_key': self.supabase_anon_key,
                'service_key': self.supabase_service_key,
                'db_password': self.supabase_db_password,
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
                
            if any(secret_word in field_name.lower() for secret_word in ['token', 'key', 'secret', 'password']):
                if isinstance(field_value, str):
                    masked[field_name] = mask_secret(field_value)
                else:
                    masked[field_name] = str(field_value)
            else:
                masked[field_name] = str(field_value)
                
        return masked


# Create global settings instance
settings = Settings()