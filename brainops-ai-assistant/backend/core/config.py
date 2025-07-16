"""Configuration settings for BrainOps AI Assistant."""

from typing import List, Optional
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # Application
    APP_NAME: str = "BrainOps AI Assistant"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    PORT: int = 8000
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Get async database URL."""
        if self.DATABASE_URL.startswith("sqlite"):
            return self.DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
        elif self.DATABASE_URL.startswith("postgresql"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        return self.DATABASE_URL
    
    # AI Services
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str
    GOOGLE_AI_API_KEY: Optional[str] = None
    
    # Voice Services
    ELEVENLABS_API_KEY: Optional[str] = None
    WHISPER_MODEL: str = "base"
    
    # File System
    OPS_ROOT_DIR: Path = Path("/home/brainops/operations")
    ALLOWED_FILE_EXTENSIONS: List[str] = [
        ".txt", ".md", ".json", ".yaml", ".yml", 
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".html", ".css", ".scss", ".sql",
        ".sh", ".bash", ".zsh",
        ".env", ".config", ".conf",
        ".log", ".csv", ".xlsx", ".pdf"
    ]
    MAX_FILE_SIZE_MB: int = 100
    
    # Command Execution
    ALLOWED_COMMANDS: List[str] = [
        "ls", "cd", "pwd", "cat", "grep", "find",
        "git", "npm", "yarn", "python", "pip",
        "docker", "kubectl", "make", "curl", "wget"
    ]
    COMMAND_TIMEOUT_SECONDS: int = 300
    REQUIRE_CONFIRMATION: bool = True
    
    # Task Management
    TASK_QUEUE_NAME: str = "brainops_tasks"
    MAX_CONCURRENT_TASKS: int = 10
    
    # Workflow Automation
    MAKE_WEBHOOK_URL: Optional[str] = None
    CLICKUP_API_TOKEN: Optional[str] = None
    NOTION_API_KEY: Optional[str] = None
    
    # Memory & Knowledge
    MEMORY_COLLECTION_NAME: str = "assistant_memory"
    MAX_MEMORY_ENTRIES: int = 10000
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://brainops.ai",
        "https://assistant.brainops.ai"
    ]
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"
    
    # Voice Configuration
    VOICE_ACTIVATION_KEYWORD: str = "hey brain"
    VOICE_LANGUAGE: str = "en-US"
    VOICE_CONFIDENCE_THRESHOLD: float = 0.5
    
    # Audit & Security
    AUDIT_LOG_RETENTION_DAYS: int = 90
    MAX_LOGIN_ATTEMPTS: int = 5
    ENABLE_2FA: bool = True
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    def get_ops_path(self, subpath: str = "") -> Path:
        """Get a path within the operations directory."""
        path = self.OPS_ROOT_DIR / subpath
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()