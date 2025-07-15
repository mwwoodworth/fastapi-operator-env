"""
Task registry and auto-registration system for BrainOps tasks.
Automatically discovers and registers all task implementations.
"""

import os
import importlib
import logging
from typing import Dict, Type, Any
from pathlib import Path

from .base_task import BaseTask

logger = logging.getLogger(__name__)

# Global task registry
task_registry: Dict[str, Type[BaseTask]] = {}


def register_task(task_id: str, task_class: Type[BaseTask]) -> None:
    """
    Register a task class in the global registry.
    
    Args:
        task_id: Unique identifier for the task
        task_class: Task class implementing BaseTask
    """
    if task_id in task_registry:
        logger.warning(f"Task {task_id} is already registered, overwriting...")
    
    task_registry[task_id] = task_class
    logger.info(f"Registered task: {task_id}")


def auto_discover_tasks() -> None:
    """
    Automatically discover and register all task implementations.
    
    Scans the tasks directory for Python files and imports any that
    define a TASK_ID constant and a class inheriting from BaseTask.
    """
    # Get the tasks directory path
    tasks_dir = Path(__file__).parent
    
    # Iterate through all Python files in the tasks directory
    for file_path in tasks_dir.glob("*.py"):
        # Skip special files
        if file_path.name.startswith("_") or file_path.name == "base_task.py":
            continue
            
        # Extract module name
        module_name = file_path.stem
        
        try:
            # Import the module
            module = importlib.import_module(f".{module_name}", package=__name__)
            
            # Check if module has TASK_ID constant
            if hasattr(module, "TASK_ID"):
                task_id = getattr(module, "TASK_ID")
                
                # Find the task class (subclass of BaseTask)
                task_class = None
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BaseTask) and 
                        attr is not BaseTask):
                        task_class = attr
                        break
                
                if task_class:
                    register_task(task_id, task_class)
                else:
                    logger.warning(
                        f"Module {module_name} has TASK_ID but no BaseTask subclass"
                    )
                    
        except Exception as e:
            logger.error(f"Failed to import task module {module_name}: {e}")


# Auto-discover tasks on module import
auto_discover_tasks()


def get_task(task_id: str) -> Type[BaseTask]:
    """
    Retrieve a task class from the registry.
    
    Args:
        task_id: Task identifier
        
    Returns:
        Task class or None if not found
    """
    return task_registry.get(task_id)


def list_tasks() -> list[str]:
    """
    List all registered task IDs.
    
    Returns:
        List of registered task identifiers
    """
    return list(task_registry.keys())


def create_task_instance(task_id: str) -> BaseTask:
    """
    Create an instance of a registered task.
    
    Args:
        task_id: Task identifier
        
    Returns:
        Task instance
        
    Raises:
        ValueError: If task_id is not registered
    """
    task_class = get_task(task_id)
    if not task_class:
        raise ValueError(f"Unknown task ID: {task_id}")
    
    return task_class()


def get_task_metadata(task_id: str) -> Dict[str, Any]:
    """
    Get metadata about a registered task.
    
    Args:
        task_id: Task identifier
        
    Returns:
        Dictionary containing task metadata
    """
    task_class = get_task(task_id)
    if not task_class:
        return {}
    
    # Extract metadata from docstring and class attributes
    metadata = {
        "id": task_id,
        "name": task_class.__name__,
        "description": task_class.__doc__ or "No description available",
        "module": task_class.__module__
    }
    
    # Add any custom metadata attributes
    if hasattr(task_class, "METADATA"):
        metadata.update(task_class.METADATA)
    
    return metadata


# Export commonly used items
__all__ = [
    "task_registry",
    "register_task",
    "get_task",
    "list_tasks",
    "create_task_instance",
    "get_task_metadata",
    "BaseTask",
    "TaskResult"
]