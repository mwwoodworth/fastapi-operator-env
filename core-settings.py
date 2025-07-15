"""
Core settings module for BrainOps backend.

Centralized configuration management using Pydantic BaseSettings for type safety,
environment variable validation, and secure secret handling. Built to prevent
configuration errors and protect sensitive credentials.
"""

from typing import Optional, List, Dict, Any
from functools import lru_cache

from pydantic import BaseSettings, Field, validator, SecretStr


class Settings(BaseSettings):
    """
    Application settings with comprehensive validation and security.
    
    Loads configuration from environment variables with sensible defaults,
    type validation, and secret protection. Designed to fail fast on
    misconfiguration rather than runtime errors.
    """
    
    # Application Core
    APP_NAME: str = Field("BrainOps", description="Application identifier")
    APP_VERSION: str = Field("1.0.0", description="Current version for tracking")
    DEBUG: bool = Field(False, description="Debug mode - NEVER true in production")
    ENVIRONMENT: str = Field("production", regex="^(development|staging|production)$")
    
    # API Configuration
    API_V1_PREFIX: str = Field("/api/v1", description="API version prefix")
    CORS_ORIGINS: List[str] = Field(
        ["http://localhost:3000"],
        description="Allowed CORS origins - restrict in production"
    )
    
    # Security & Authentication
    SECRET_KEY: SecretStr = Field(..., description="JWT signing key - MUST be unique")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, ge=5, le=1440)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(7, ge=1, le=30)
    ALGORITHM: str = Field("HS256", description="JWT signing algorithm")
    
    # Database (Supabase/PostgreSQL)
    DATABASE_URL: SecretStr = Field(
        ...,
        description="PostgreSQL connection string with pgvector extension"
    )
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_KEY: SecretStr = Field(..., description="Supabase service key")
    SUPABASE_JWT_SECRET: SecretStr = Field(..., description="Supabase JWT secret")
    
    # AI Provider Keys (all required for multi-agent system)
    OPENAI_API_KEY: SecretStr = Field(..., description="OpenAI GPT-4 access")
    ANTHROPIC_API_KEY: SecretStr = Field(..., description="Claude access")
    GOOGLE_AI_API_KEY: SecretStr = Field(..., description="Gemini access")
    PERPLEXITY_API_KEY: Optional[SecretStr] = Field(None, description="Perplexity search")
    
    # Integration Webhooks & APIs
    SLACK_BOT_TOKEN: Optional[SecretStr] = Field(None, description="Slack bot OAuth token")
    SLACK_SIGNING_SECRET: Optional[SecretStr] = Field(None, description="Slack webhook verification")
    CLICKUP_API_KEY: Optional[SecretStr] = Field(None, description="ClickUp integration")
    NOTION_API_KEY: Optional[SecretStr] = Field(None, description="Notion integration")
    MAKE_WEBHOOK_SECRET: SecretStr = Field(..., description="Make.com webhook security")
    STRIPE_API_KEY: SecretStr = Field(..., description="Stripe payment processing")
    STRIPE_WEBHOOK_SECRET: SecretStr = Field(..., description="Stripe webhook security")
    
    # Task Queue & Scheduling
    REDIS_URL: Optional[str] = Field("redis://localhost:6379", description="Redis for task queue")
    TASK_TIMEOUT_SECONDS: int = Field(300, ge=30, le=3600, description="Max task runtime")
    MAX_CONCURRENT_TASKS: int = Field(10, ge=1, le=100, description="Concurrent task limit")
    
    # Logging & Monitoring
    LOG_LEVEL: str = Field("INFO", regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    LOG_FORMAT: str = Field("json", regex="^(json|text)$")
    SENTRY_DSN: Optional[str] = Field(None, description="Sentry error tracking")
    SLACK_ALERTS_WEBHOOK: Optional[str] = Field(None, description="Critical alert channel")
    
    # AI Model Configuration
    CLAUDE_MODEL: str = Field("claude-3-opus-20240229", description="Claude model version")
    GPT_MODEL: str = Field("gpt-4-turbo-preview", description="OpenAI model version")
    GEMINI_MODEL: str = Field("gemini-pro", description="Google model version")
    EMBEDDING_MODEL: str = Field("text-embedding-3-small", description="OpenAI embedding model")
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = Field(100, ge=10, le=1000, description="Requests per minute")
    RATE_LIMIT_TOKENS: int = Field(100000, ge=1000, description="AI tokens per hour")
    
    # File Storage
    MAX_UPLOAD_SIZE_MB: int = Field(50, ge=1, le=500, description="Max file upload size")
    ALLOWED_UPLOAD_EXTENSIONS: List[str] = Field(
        [".pdf", ".xlsx", ".csv", ".txt", ".md", ".json"],
        description="Permitted file types"
    )
    
    @validator("SECRET_KEY", pre=True)
    def validate_secret_key(cls, v):
        """Ensure SECRET_KEY is sufficiently complex for production."""
        if isinstance(v, str) and len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters for security")
        return v
    
    @validator("ENVIRONMENT")
    def validate_debug_production(cls, v, values):
        """Prevent DEBUG=True in production environment."""
        if v == "production" and values.get("DEBUG"):
            raise ValueError("DEBUG cannot be True in production environment")
        return v
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    def get_database_settings(self) -> Dict[str, Any]:
        """
        Get database connection settings with pgvector configuration.
        
        Ensures proper vector search setup for RAG memory system.
        """
        return {
            "url": self.DATABASE_URL.get_secret_value(),
            "pool_size": 20 if self.ENVIRONMENT == "production" else 5,
            "max_overflow": 10,
            "pool_pre_ping": True,
            "echo": self.DEBUG,
            "connect_args": {
                "server_settings": {
                    "jit": "off"  # Recommended for pgvector performance
                }
            }
        }
    
    def get_ai_limits(self) -> Dict[str, int]:
        """
        Get AI token and request limits based on environment.
        
        Protects against runaway costs while ensuring adequate capacity
        for production workloads.
        """
        if self.ENVIRONMENT == "development":
            return {
                "max_tokens_per_request": 4000,
                "max_requests_per_minute": 20,
                "max_cost_per_hour": 10  # dollars
            }
        else:
            return {
                "max_tokens_per_request": 8000,
                "max_requests_per_minute": 60,
                "max_cost_per_hour": 100  # dollars
            }
    
    def validate_required_integrations(self) -> List[str]:
        """
        Check which integrations are properly configured.
        
        Returns list of configured integrations for feature flagging.
        """
        integrations = []
        
        if self.SLACK_BOT_TOKEN and self.SLACK_SIGNING_SECRET:
            integrations.append("slack")
        if self.CLICKUP_API_KEY:
            integrations.append("clickup")
        if self.NOTION_API_KEY:
            integrations.append("notion")
        
        return integrations
    
    class Config:
        """Pydantic configuration for environment loading."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        # Prevent secrets from being logged
        json_encoders = {
            SecretStr: lambda v: "***REDACTED***" if v else None
        }


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses function-level caching to ensure settings are loaded only once,
    preventing repeated environment variable parsing and validation.
    """
    return Settings()


# Global settings instance
settings = get_settings()


# Validate critical settings on import
if settings.ENVIRONMENT == "production":
    # Ensure all production-critical settings are configured
    required_prod_settings = [
        "SECRET_KEY",
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_AI_API_KEY",
        "STRIPE_API_KEY",
        "STRIPE_WEBHOOK_SECRET"
    ]
    
    for setting in required_prod_settings:
        if not getattr(settings, setting, None):
            raise ValueError(f"Production requires {setting} to be configured")