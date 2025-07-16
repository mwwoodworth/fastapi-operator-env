"""
Task registration and management for BrainOps Backend.

This module handles the registration of all background tasks,
scheduled jobs, and async workers.
"""

from typing import Dict, Any, Callable
import logging

from ..core.scheduler import scheduler
from ..core.logging import get_logger

# Import all task modules
from . import (
    autopublish,
    customer_onboarding,
    sync_database,
    weekly_report,
)

logger = get_logger(__name__)

# Global task registry
task_registry: Dict[str, Callable] = {}


def register_task(name: str, func: Callable) -> None:
    """
    Register a task in the global registry.
    
    Args:
        name: Unique task name
        func: Task function
    """
    if name in task_registry:
        logger.warning(f"Task {name} already registered, overwriting")
    
    task_registry[name] = func
    logger.info(f"Registered task: {name}")


def register_all_tasks() -> None:
    """
    Register all available tasks.
    
    This function is called during application startup to ensure
    all tasks are available for execution.
    """
    logger.info("Registering all tasks")
    
    # Register individual tasks
    register_task("autopublish_content", autopublish.autopublish_content)
    register_task("onboard_customer", customer_onboarding.onboard_customer)
    register_task("sync_database", sync_database.sync_database_task)
    register_task("generate_weekly_report", weekly_report.generate_weekly_report)
    
    # Register scheduled tasks
    if scheduler:
        # Weekly report every Monday at 9 AM
        scheduler.add_job(
            weekly_report.generate_weekly_report,
            'cron',
            day_of_week='mon',
            hour=9,
            minute=0,
            id='weekly_report',
            replace_existing=True
        )
        
        # Database sync every 6 hours
        scheduler.add_job(
            sync_database.sync_database_task,
            'interval',
            hours=6,
            id='database_sync',
            replace_existing=True
        )
    
    logger.info(f"Registered {len(task_registry)} tasks")


def get_task(name: str) -> Callable:
    """
    Get a task by name.
    
    Args:
        name: Task name
        
    Returns:
        Task function
        
    Raises:
        KeyError: If task not found
    """
    if name not in task_registry:
        raise KeyError(f"Task {name} not found")
    
    return task_registry[name]


def list_tasks() -> Dict[str, str]:
    """
    List all registered tasks.
    
    Returns:
        Dictionary of task names and descriptions
    """
    return {
        name: func.__doc__.strip() if func.__doc__ else "No description"
        for name, func in task_registry.items()
    }