"""
Core module initialization for BrainOps backend.

Provides centralized access to core functionality including settings,
security, logging, and scheduling. Built to ensure consistent initialization
across all backend components.
"""

from .settings import settings, get_settings
from .security import (
    security_manager,
    get_current_user,
    require_permissions,
    sanitize_filename
)
from .logging import (
    configure_logging,
    get_logger,
    LogContext,
    log_task_execution,
    log_ai_call,
    log_integration_event
)
from .scheduler import scheduler, schedule_after

__all__ = [
    # Settings
    "settings",
    "get_settings",
    
    # Security
    "security_manager",
    "get_current_user",
    "require_permissions",
    "sanitize_filename",
    
    # Logging
    "configure_logging",
    "get_logger",
    "LogContext",
    "log_task_execution",
    "log_ai_call",
    "log_integration_event",
    
    # Scheduling
    "scheduler",
    "schedule_after"
]

# Module initialization log
logger = get_logger(__name__)
logger.info("Core module initialized", extra={
    "environment": settings.ENVIRONMENT,
    "debug_mode": settings.DEBUG
})