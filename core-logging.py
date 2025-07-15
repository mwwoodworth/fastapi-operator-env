"""
Logging configuration module for BrainOps.

Structured logging system that captures critical events, errors, and operational
metrics. Built to provide clear visibility into system behavior under pressure
while protecting sensitive data from exposure.
"""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar
from pythonjsonlogger import jsonlogger
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

from ..core.settings import settings


# Context variables for request tracking across async operations
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)


class SecurityFilter(logging.Filter):
    """
    Filter to redact sensitive information from logs.
    
    Prevents accidental exposure of API keys, passwords, and personal data
    in log files. Critical for maintaining security in production systems.
    """
    
    SENSITIVE_FIELDS = {
        "password", "api_key", "token", "secret", "authorization",
        "credit_card", "ssn", "email", "phone", "address",
        "stripe_key", "openai_key", "anthropic_key"
    }
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive fields from log records."""
        # Handle log messages
        if hasattr(record, 'msg'):
            record.msg = self._redact_message(str(record.msg))
        
        # Handle structured log data
        if hasattr(record, 'data'):
            record.data = self._redact_dict(record.data)
        
        return True
    
    def _redact_message(self, message: str) -> str:
        """Redact sensitive patterns from text messages."""
        # Redact API keys and tokens (basic pattern matching)
        import re
        
        # Pattern for API key-like strings
        api_key_pattern = r'([a-zA-Z0-9_-]{20,})'
        message = re.sub(api_key_pattern, '[REDACTED]', message)
        
        # Pattern for email addresses
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        message = re.sub(email_pattern, '[EMAIL_REDACTED]', message)
        
        return message
    
    def _redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively redact sensitive fields from dictionaries."""
        redacted = {}
        
        for key, value in data.items():
            # Check if field name suggests sensitive data
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_FIELDS):
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [
                    self._redact_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                redacted[key] = value
        
        return redacted


class StructuredFormatter(jsonlogger.JsonFormatter):
    """
    JSON formatter with consistent structure and context injection.
    
    Ensures all logs have predictable format for parsing and analysis,
    with automatic inclusion of request context for tracing.
    """
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        """Add standard fields to every log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add context from context variables
        log_record['request_id'] = request_id_var.get()
        log_record['user_id'] = user_id_var.get()
        
        # Add application metadata
        log_record['app'] = settings.APP_NAME
        log_record['environment'] = settings.ENVIRONMENT
        log_record['version'] = settings.APP_VERSION
        
        # Ensure level name is included
        log_record['level'] = record.levelname
        
        # Add error details if present
        if record.exc_info:
            log_record['error_type'] = record.exc_info[0].__name__
            log_record['error_message'] = str(record.exc_info[1])


class AlertHandler(logging.Handler):
    """
    Send critical alerts to Slack for immediate attention.
    
    Ensures team is notified of system failures or critical errors
    that require immediate intervention.
    """
    
    def __init__(self, webhook_url: str):
        super().__init__()
        self.webhook_url = webhook_url
        self.setLevel(logging.ERROR)  # Only alert on errors and above
    
    def emit(self, record: logging.LogRecord):
        """Send formatted alert to Slack webhook."""
        try:
            import httpx
            
            # Format alert message with context
            alert_data = {
                "text": f"🚨 *{record.levelname}* in {settings.ENVIRONMENT}",
                "attachments": [{
                    "color": "danger" if record.levelname == "ERROR" else "warning",
                    "fields": [
                        {"title": "Message", "value": record.getMessage(), "short": False},
                        {"title": "Logger", "value": record.name, "short": True},
                        {"title": "Time", "value": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), "short": True},
                        {"title": "Request ID", "value": request_id_var.get() or "N/A", "short": True},
                        {"title": "User ID", "value": user_id_var.get() or "N/A", "short": True}
                    ]
                }]
            }
            
            # Add error details if present
            if record.exc_info:
                alert_data["attachments"][0]["fields"].append({
                    "title": "Exception",
                    "value": f"{record.exc_info[0].__name__}: {record.exc_info[1]}",
                    "short": False
                })
            
            # Send alert (fire and forget)
            with httpx.Client(timeout=5.0) as client:
                client.post(self.webhook_url, json=alert_data)
                
        except Exception:
            # Never let alert failures break the application
            pass


def configure_logging():
    """
    Configure comprehensive logging for production systems.
    
    Sets up structured JSON logging, security filtering, and alert mechanisms
    to provide operational visibility while maintaining security.
    """
    # Determine log level from settings
    log_level = getattr(logging, settings.LOG_LEVEL.upper())
    
    # Create root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    root_logger.handlers = []
    
    # Console handler with structured JSON output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Use JSON formatter for structured logs
    if settings.LOG_FORMAT == "json":
        formatter = StructuredFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            json_ensure_ascii=False
        )
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    
    # Add security filter to all handlers
    security_filter = SecurityFilter()
    console_handler.addFilter(security_filter)
    
    root_logger.addHandler(console_handler)
    
    # Add Slack alerts for critical errors
    if settings.SLACK_ALERTS_WEBHOOK and settings.ENVIRONMENT == "production":
        alert_handler = AlertHandler(settings.SLACK_ALERTS_WEBHOOK)
        alert_handler.addFilter(security_filter)
        root_logger.addHandler(alert_handler)
    
    # Configure Sentry for error tracking
    if settings.SENTRY_DSN:
        sentry_logging = LoggingIntegration(
            level=logging.INFO,  # Capture info and above
            event_level=logging.ERROR  # Send errors as events
        )
        
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[sentry_logging],
            traces_sample_rate=0.1,  # Sample 10% of transactions
            environment=settings.ENVIRONMENT,
            release=settings.APP_VERSION
        )
    
    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "log_level": settings.LOG_LEVEL,
            "log_format": settings.LOG_FORMAT,
            "sentry_enabled": bool(settings.SENTRY_DSN),
            "slack_alerts_enabled": bool(settings.SLACK_ALERTS_WEBHOOK)
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with consistent configuration.
    
    Ensures all application loggers inherit security filtering
    and structured formatting for operational consistency.
    """
    return logging.getLogger(name)


class LogContext:
    """
    Context manager for adding request/user context to logs.
    
    Usage:
        with LogContext(request_id="abc123", user_id="user456"):
            logger.info("Processing request")  # Will include context
    """
    
    def __init__(self, request_id: Optional[str] = None, user_id: Optional[str] = None):
        self.request_id = request_id
        self.user_id = user_id
        self._tokens = []
    
    def __enter__(self):
        """Set context variables on entry."""
        if self.request_id:
            self._tokens.append(request_id_var.set(self.request_id))
        if self.user_id:
            self._tokens.append(user_id_var.set(self.user_id))
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Reset context variables on exit."""
        for token in self._tokens:
            token.var.reset(token)


# Convenience functions for structured logging
def log_task_execution(task_id: str, status: str, duration_ms: int, **kwargs):
    """Log task execution with consistent structure."""
    logger = get_logger("task_execution")
    logger.info(
        "Task executed",
        extra={
            "task_id": task_id,
            "status": status,
            "duration_ms": duration_ms,
            **kwargs
        }
    )


def log_ai_call(provider: str, model: str, tokens: int, cost: float, **kwargs):
    """Log AI provider API calls for cost tracking."""
    logger = get_logger("ai_usage")
    logger.info(
        "AI API call",
        extra={
            "provider": provider,
            "model": model,
            "tokens": tokens,
            "cost": cost,
            **kwargs
        }
    )


def log_integration_event(integration: str, event_type: str, success: bool, **kwargs):
    """Log external integration events for monitoring."""
    logger = get_logger("integration")
    level = logging.INFO if success else logging.WARNING
    logger.log(
        level,
        f"Integration event: {integration}",
        extra={
            "integration": integration,
            "event_type": event_type,
            "success": success,
            **kwargs
        }
    )