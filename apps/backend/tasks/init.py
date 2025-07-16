"""
Task Registry Initialization

This module automatically discovers and registers all task implementations
in the tasks directory. Each task must define a TASK_ID and inherit from
the base Task class to be registered.
"""

import os
import importlib
import inspect
from typing import Dict, Type, Any, List
import logging

from .agents.base import ExecutionContext, AgentResponse


logger = logging.getLogger(__name__)


class BaseTask:
    """
    Base class for all task implementations.
    
    All tasks must inherit from this class and implement the required
    methods for registration and execution.
    """
    
    # Task metadata - must be overridden in subclasses
    TASK_ID: str = None
    TASK_NAME: str = None
    TASK_DESCRIPTION: str = None
    TASK_CATEGORY: str = None
    
    @classmethod
    def validate_parameters(cls, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize task parameters.
        
        Must be implemented by subclasses to define parameter requirements.
        """
        raise NotImplementedError("Subclasses must implement validate_parameters")
    
    @classmethod
    def estimate_tokens(cls, parameters: Dict[str, Any]) -> int:
        """Estimate token usage for the task."""
        # Default estimation - override for more accuracy
        return 1000
    
    @classmethod
    def estimate_duration(cls, parameters: Dict[str, Any]) -> int:
        """Estimate execution duration in seconds."""
        # Default estimation - override for more accuracy
        return 30
    
    @classmethod
    def get_required_approvals(cls, parameters: Dict[str, Any]) -> List[str]:
        """Get list of required approvals for this task."""
        return []
    
    @classmethod
    def describe(cls, parameters: Dict[str, Any]) -> str:
        """Generate human-readable description of the task."""
        return cls.TASK_DESCRIPTION or f"Execute {cls.TASK_NAME}"
    
    @classmethod
    async def run(cls, context: ExecutionContext) -> Dict[str, Any]:
        """
        Execute the task with the given context.
        
        Must be implemented by subclasses to define task logic.
        """
        raise NotImplementedError("Subclasses must implement run method")
    
    @classmethod
    async def stream(cls, context: ExecutionContext):
        """
        Optional streaming execution for real-time updates.
        
        Yields server-sent events for streaming responses.
        """
        # Default implementation calls run() and yields result
        result = await cls.run(context)
        yield f"data: {{'type': 'complete', 'result': {result}}}\n\n"


# Global task registry
task_registry: Dict[str, Type[BaseTask]] = {}


def register_task(task_class: Type[BaseTask]):
    """Register a task class in the global registry."""
    if not task_class.TASK_ID:
        logger.warning(f"Task {task_class.__name__} has no TASK_ID, skipping registration")
        return
    
    if task_class.TASK_ID in task_registry:
        logger.warning(f"Task {task_class.TASK_ID} already registered, overwriting")
    
    task_registry[task_class.TASK_ID] = task_class
    logger.info(f"Registered task: {task_class.TASK_ID} ({task_class.TASK_NAME})")


def auto_discover_tasks():
    """
    Automatically discover and register all tasks in the tasks directory.
    
    Scans for Python files that define classes inheriting from BaseTask
    and registers them in the global task registry.
    """
    tasks_dir = os.path.dirname(__file__)
    
    # Scan all Python files in the tasks directory
    for filename in os.listdir(tasks_dir):
        if filename.endswith('.py') and not filename.startswith('_'):
            module_name = filename[:-3]  # Remove .py extension
            
            try:
                # Import the module
                module_path = f"apps.backend.tasks.{module_name}"
                module = importlib.import_module(module_path)
                
                # Find all classes that inherit from BaseTask
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseTask) and obj != BaseTask:
                        # Check if it's defined in this module (not imported)
                        if obj.__module__ == module_path:
                            register_task(obj)
                            
            except Exception as e:
                logger.error(f"Failed to import task module {module_name}: {e}")


# Auto-discover tasks on module import
auto_discover_tasks()


# Export commonly used task categories
TASK_CATEGORIES = {
    "content": "Content Generation",
    "automation": "Automation & Integration",
    "analysis": "Analysis & Research",
    "roofing": "Roofing Industry",
    "documentation": "Documentation",
    "data": "Data Processing"
}


def get_task_by_category(category: str) -> List[Type[BaseTask]]:
    """Get all tasks in a specific category."""
    return [
        task for task in task_registry.values()
        if task.TASK_CATEGORY == category
    ]


def get_task_metadata() -> Dict[str, Dict[str, Any]]:
    """Get metadata for all registered tasks."""
    metadata = {}
    
    for task_id, task_class in task_registry.items():
        metadata[task_id] = {
            "id": task_class.TASK_ID,
            "name": task_class.TASK_NAME,
            "description": task_class.TASK_DESCRIPTION,
            "category": task_class.TASK_CATEGORY,
            "class": task_class.__name__
        }
    
    return metadata
