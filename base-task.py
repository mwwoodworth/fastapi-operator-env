"""
Base task class for all BrainOps automation tasks.
Provides common functionality for task execution, logging, and error handling.
"""

import logging
import traceback
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, AsyncIterator
from datetime import datetime
from dataclasses import dataclass, field
import uuid

from ..memory.memory_store import MemoryStore
from ..core.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """
    Standardized result object for task execution.
    
    Attributes:
        success: Whether the task completed successfully
        data: Result data from the task execution
        error: Error message if the task failed
        message: Human-readable status message
        metadata: Additional execution metadata
    """
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTask(ABC):
    """
    Abstract base class for all BrainOps automation tasks.
    
    This class provides:
    - Common task execution framework
    - Automatic logging and error handling
    - Memory storage integration
    - Streaming support for real-time updates
    - Context validation
    """
    
    def __init__(self, task_id: str):
        """
        Initialize the base task.
        
        Args:
            task_id: Unique identifier for the task type
        """
        self.task_id = task_id
        self.execution_id = None
        self.memory_store = MemoryStore()
        self.logger = logging.getLogger(f"{__name__}.{task_id}")
        
    @abstractmethod
    async def run(self, context: Dict[str, Any]) -> TaskResult:
        """
        Execute the task with the given context.
        
        This method must be implemented by all task subclasses.
        
        Args:
            context: Task-specific input parameters and data
            
        Returns:
            TaskResult containing execution outcome and data
        """
        pass
    
    async def stream(self, context: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream task execution updates in real-time.
        
        Override this method to provide streaming updates during execution.
        Default implementation yields a single update with the final result.
        
        Args:
            context: Task-specific input parameters
            
        Yields:
            Status updates during task execution
        """
        # Default implementation - just run and yield result
        result = await self.run(context)
        yield {
            "stage": "completed",
            "result": result.data if result.success else None,
            "error": result.error,
            "message": result.message
        }
    
    async def execute_async(self, context: Dict[str, Any]) -> TaskResult:
        """
        Execute the task with full lifecycle management.
        
        This method handles:
        - Execution tracking
        - Error handling
        - Logging
        - Memory storage
        
        Args:
            context: Task-specific input parameters
            
        Returns:
            TaskResult with execution outcome
        """
        # Generate unique execution ID
        self.execution_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        # Log task start
        await self._log_execution_start(context)
        
        try:
            # Validate context before execution
            self._validate_base_context(context)
            
            # Execute the task
            result = await self.run(context)
            
            # Calculate execution time
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            result.metadata['execution_time_seconds'] = execution_time
            result.metadata['execution_id'] = self.execution_id
            
            # Log successful completion
            await self._log_execution_complete(result, execution_time)
            
            return result
            
        except Exception as e:
            # Calculate execution time even for failures
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create error result
            error_message = str(e)
            stack_trace = traceback.format_exc()
            
            result = TaskResult(
                success=False,
                error=error_message,
                message=f"Task {self.task_id} failed: {error_message}",
                metadata={
                    'execution_time_seconds': execution_time,
                    'execution_id': self.execution_id,
                    'stack_trace': stack_trace
                }
            )
            
            # Log failure
            await self._log_execution_failure(error_message, stack_trace, execution_time)
            
            return result
    
    def _validate_base_context(self, context: Dict[str, Any]) -> None:
        """
        Validate basic context requirements.
        
        Override this method to add task-specific validation.
        
        Args:
            context: Context to validate
            
        Raises:
            ValueError: If context is invalid
        """
        if not isinstance(context, dict):
            raise ValueError("Context must be a dictionary")
    
    async def _log_execution_start(self, context: Dict[str, Any]) -> None:
        """Log the start of task execution to memory."""
        log_entry = {
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "status": "started",
            "context": self._sanitize_context_for_logging(context),
            "started_at": datetime.utcnow().isoformat()
        }
        
        await self.memory_store.save_memory_entry(
            namespace="task_executions",
            key=f"{self.task_id}_{self.execution_id}_start",
            content=log_entry
        )
        
        self.logger.info(
            f"Task execution started",
            extra={"task_id": self.task_id, "execution_id": self.execution_id}
        )
    
    async def _log_execution_complete(
        self, 
        result: TaskResult, 
        execution_time: float
    ) -> None:
        """Log successful task completion."""
        log_entry = {
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "status": "completed",
            "execution_time_seconds": execution_time,
            "result_summary": self._summarize_result(result),
            "completed_at": datetime.utcnow().isoformat()
        }
        
        await self.memory_store.save_memory_entry(
            namespace="task_executions",
            key=f"{self.task_id}_{self.execution_id}_complete",
            content=log_entry
        )
        
        self.logger.info(
            f"Task execution completed successfully",
            extra={
                "task_id": self.task_id,
                "execution_id": self.execution_id,
                "execution_time": execution_time
            }
        )
    
    async def _log_execution_failure(
        self,
        error_message: str,
        stack_trace: str,
        execution_time: float
    ) -> None:
        """Log task execution failure."""
        log_entry = {
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "status": "failed",
            "error": error_message,
            "stack_trace": stack_trace,
            "execution_time_seconds": execution_time,
            "failed_at": datetime.utcnow().isoformat()
        }
        
        await self.memory_store.save_memory_entry(
            namespace="task_executions",
            key=f"{self.task_id}_{self.execution_id}_failure",
            content=log_entry
        )
        
        self.logger.error(
            f"Task execution failed",
            extra={
                "task_id": self.task_id,
                "execution_id": self.execution_id,
                "error": error_message,
                "execution_time": execution_time
            }
        )
    
    def _sanitize_context_for_logging(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive data from context before logging.
        
        Override this method to implement task-specific sanitization.
        
        Args:
            context: Original context
            
        Returns:
            Sanitized context safe for logging
        """
        # Default implementation - remove common sensitive keys
        sensitive_keys = ['password', 'api_key', 'token', 'secret', 'credit_card']
        
        sanitized = {}
        for key, value in context.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = self._sanitize_context_for_logging(value)
            else:
                sanitized[key] = value
                
        return sanitized
    
    def _summarize_result(self, result: TaskResult) -> Dict[str, Any]:
        """
        Create a summary of the task result for logging.
        
        Override this method for task-specific summarization.
        
        Args:
            result: Task execution result
            
        Returns:
            Summary safe for logging
        """
        summary = {
            "success": result.success,
            "message": result.message
        }
        
        if result.data:
            # Include data keys but not full content
            summary["data_keys"] = list(result.data.keys())
            
        if result.metadata:
            summary["metadata"] = result.metadata
            
        return summary
    
    async def get_execution_history(
        self,
        limit: int = 10
    ) -> list[Dict[str, Any]]:
        """
        Retrieve execution history for this task type.
        
        Args:
            limit: Maximum number of executions to retrieve
            
        Returns:
            List of execution records
        """
        # Query memory store for task execution history
        executions = await self.memory_store.query_by_namespace(
            namespace="task_executions",
            key_prefix=f"{self.task_id}_",
            limit=limit
        )
        
        return executions
    
    async def retry_failed_execution(
        self,
        execution_id: str,
        modified_context: Optional[Dict[str, Any]] = None
    ) -> TaskResult:
        """
        Retry a previously failed task execution.
        
        Args:
            execution_id: ID of the failed execution to retry
            modified_context: Optional modified context for retry
            
        Returns:
            Result of the retry attempt
        """
        # Retrieve original execution context
        original_execution = await self.memory_store.get_memory_entry(
            namespace="task_executions",
            key=f"{self.task_id}_{execution_id}_start"
        )
        
        if not original_execution:
            return TaskResult(
                success=False,
                error="Original execution not found",
                message=f"Could not find execution {execution_id} to retry"
            )
        
        # Use modified context if provided, otherwise use original
        context = modified_context or original_execution.get('context', {})
        
        # Add retry metadata
        context['_retry_of'] = execution_id
        context['_retry_attempt'] = context.get('_retry_attempt', 0) + 1
        
        # Execute with retry context
        return await self.execute_async(context)