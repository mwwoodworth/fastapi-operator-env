"""
Task registration and management for BrainOps Backend.

This module handles the registration of all background tasks,
scheduled jobs, and async workers.
"""

from typing import Dict, Any, Callable
import logging

from apps.backend.core.scheduler import scheduler
from apps.backend.core.logging import get_logger

# Import all task modules
# from . import (
#     autopublish,
#     customer_onboarding,
#     sync_database,
#     weekly_report,
# )

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


def register_all_tasks() -> int:
    """
    Register all available tasks.
    
    This function is called during application startup to ensure
    all tasks are available for execution.
    
    Returns:
        Number of tasks registered
    """
    logger.info("Registering all tasks")
    
    # TODO: Import and register actual task modules when they are available
    # For now, just return 0 to indicate no tasks registered
    
    logger.info(f"Registered {len(task_registry)} tasks")
    return len(task_registry)


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


# Re-added by Codex for import fix
def get_task_registry() -> Dict[str, Callable]:
    return task_registry


async def execute_task(task_name: str, **kwargs) -> Any:
    """
    Execute a task by name.
    
    Args:
        task_name: Name of the task to execute
        **kwargs: Arguments to pass to the task
        
    Returns:
        Task result
        
    Raises:
        KeyError: If task not found
    """
    task = get_task(task_name)
    
    # Check if task is async
    import asyncio
    if asyncio.iscoroutinefunction(task):
        return await task(**kwargs)
    else:
        return task(**kwargs)
