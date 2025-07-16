"""
Logging configuration for BrainOps Backend.

Provides structured logging with context tracking, performance monitoring,
and integration with external logging services.
"""

import logging
import sys
from typing import Optional, Dict, Any
from datetime import datetime
import structlog
from pythonjsonlogger import jsonlogger

from .settings import settings


class LogContext:
    """Context manager for adding contextual information to logs."""
    
    def __init__(self, **kwargs):
        self.context = kwargs
    
    def __enter__(self):
        for key, value in self.context.items():
            structlog.contextvars.bind_contextvars(**{key: value})
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        for key in self.context:
            structlog.contextvars.unbind_contextvars(key)


def configure_logging():
    """
    Configure logging for the application.
    
    Sets up structured logging with JSON output for production
    and human-readable output for development.
    """
    # Determine log level from settings
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    
    if settings.ENVIRONMENT == "production":
        # Production: JSON logs
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Development: Human-readable logs
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure uvicorn access logs
    uvicorn_logger = logging.getLogger("uvicorn.access")
    uvicorn_logger.handlers.clear()
    
    # Suppress noisy loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return structlog.get_logger(name)


# Convenience logger for module-level use
logger = get_logger(__name__)