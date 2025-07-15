"""
Background task scheduler module for BrainOps.

Manages recurring tasks, delayed executions, and background job processing
with reliability guarantees. Built to ensure critical automations run on schedule
even under system pressure.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union
from functools import wraps
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from ..core.settings import settings
from ..core.logging import get_logger
from ..memory.memory_store import save_task_execution


logger = get_logger(__name__)


class TaskScheduler:
    """
    Reliable background task scheduler with persistence and monitoring.
    
    Handles recurring automations, delayed task execution, and system maintenance
    jobs. Built to survive restarts and maintain execution guarantees.
    """
    
    def __init__(self):
        # Configure job persistence to survive restarts
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=settings.DATABASE_URL.get_secret_value(),
                tablename='scheduled_jobs'
            )
        }
        
        # Configure execution with proper concurrency limits
        executors = {
            'default': AsyncIOExecutor(),
        }
        
        # Job defaults to prevent runaway executions
        job_defaults = {
            'coalesce': True,  # Skip missed executions rather than catching up
            'max_instances': 3,  # Prevent job pile-up
            'misfire_grace_time': 300  # 5 minute grace period for delayed starts
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        # Track active jobs for monitoring
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
    
    async def start(self):
        """
        Start the scheduler and restore persisted jobs.
        
        Called during application startup to resume scheduled operations
        after deployments or crashes.
        """
        self.scheduler.start()
        logger.info("Task scheduler started, restored %d persisted jobs", 
                   len(self.scheduler.get_jobs()))
        
        # Schedule system maintenance tasks
        await self._schedule_system_tasks()
    
    async def shutdown(self):
        """
        Gracefully shutdown scheduler, allowing running jobs to complete.
        
        Ensures clean shutdown during deployments without losing work.
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("Task scheduler shutdown complete")
    
    def schedule_recurring(
        self,
        func: Callable,
        trigger: Union[str, Dict[str, Any]],
        job_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Schedule a recurring task with cron or interval trigger.
        
        Supports both cron expressions and interval specifications for
        maximum flexibility in automation scheduling.
        
        Examples:
            # Daily at 2 AM
            schedule_recurring(backup_func, "0 2 * * *")
            
            # Every 30 minutes
            schedule_recurring(sync_func, {"minutes": 30})
        """
        job_id = job_id or f"recurring_{func.__name__}_{uuid.uuid4().hex[:8]}"
        
        # Parse trigger specification
        if isinstance(trigger, str):
            # Assume cron expression
            trigger_obj = CronTrigger.from_crontab(trigger)
        elif isinstance(trigger, dict):
            # Interval trigger
            trigger_obj = IntervalTrigger(**trigger)
        else:
            raise ValueError(f"Invalid trigger type: {type(trigger)}")
        
        # Wrap function with execution tracking
        wrapped_func = self._wrap_with_tracking(func, job_id)
        
        # Schedule the job
        job = self.scheduler.add_job(
            wrapped_func,
            trigger=trigger_obj,
            id=job_id,
            replace_existing=True,
            kwargs=kwargs
        )
        
        logger.info(f"Scheduled recurring job: {job_id} with trigger: {trigger}")
        return job_id
    
    def schedule_once(
        self,
        func: Callable,
        run_time: Union[datetime, int],
        job_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Schedule a one-time task execution at specific time or after delay.
        
        Perfect for delayed onboarding sequences, follow-ups, or time-sensitive
        automations that need precise timing control.
        
        Args:
            func: Async function to execute
            run_time: datetime object or seconds from now
            job_id: Optional unique identifier for the job
            kwargs: Arguments to pass to the function
        """
        job_id = job_id or f"once_{func.__name__}_{uuid.uuid4().hex[:8]}"
        
        # Handle both datetime and delay in seconds
        if isinstance(run_time, int):
            run_time = datetime.utcnow() + timedelta(seconds=run_time)
        
        # Wrap function with execution tracking
        wrapped_func = self._wrap_with_tracking(func, job_id)
        
        # Schedule the job
        job = self.scheduler.add_job(
            wrapped_func,
            trigger=DateTrigger(run_date=run_time),
            id=job_id,
            replace_existing=True,
            kwargs=kwargs
        )
        
        logger.info(f"Scheduled one-time job: {job_id} at {run_time}")
        return job_id
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a scheduled job by ID.
        
        Allows dynamic cancellation of automations when business logic changes
        or user actions make them unnecessary.
        """
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Cancelled job: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Failed to cancel job {job_id}: {str(e)}")
            return False
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status and next run time for a scheduled job.
        
        Provides visibility into automation scheduling for monitoring
        and debugging purposes.
        """
        job = self.scheduler.get_job(job_id)
        if not job:
            return None
        
        return {
            "job_id": job_id,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "active": job_id in self.active_jobs,
            "pending": job.pending,
            "trigger": str(job.trigger),
            "kwargs": job.kwargs
        }
    
    def list_jobs(self, job_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all scheduled jobs with optional filtering.
        
        Provides system-wide visibility into scheduled automations for
        operations monitoring and debugging.
        """
        jobs = self.scheduler.get_jobs()
        
        # Filter by job type if specified
        if job_type:
            jobs = [j for j in jobs if j.id.startswith(job_type)]
        
        return [
            {
                "job_id": job.id,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "active": job.id in self.active_jobs
            }
            for job in jobs
        ]
    
    def _wrap_with_tracking(self, func: Callable, job_id: str) -> Callable:
        """
        Wrap scheduled function with execution tracking and error handling.
        
        Ensures all scheduled tasks are monitored, logged, and recorded
        for operational visibility and debugging.
        """
        @wraps(func)
        async def wrapped(*args, **kwargs):
            start_time = datetime.utcnow()
            self.active_jobs[job_id] = {"start_time": start_time}
            
            try:
                # Execute the actual function
                result = await func(*args, **kwargs)
                
                # Record successful execution
                await save_task_execution({
                    "job_id": job_id,
                    "status": "success",
                    "start_time": start_time,
                    "end_time": datetime.utcnow(),
                    "result": str(result) if result else None
                })
                
                logger.info(f"Job {job_id} completed successfully")
                return result
                
            except Exception as e:
                # Record failed execution
                await save_task_execution({
                    "job_id": job_id,
                    "status": "failed",
                    "start_time": start_time,
                    "end_time": datetime.utcnow(),
                    "error": str(e)
                })
                
                logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)
                raise
                
            finally:
                # Clean up active job tracking
                self.active_jobs.pop(job_id, None)
        
        return wrapped
    
    async def _schedule_system_tasks(self):
        """
        Schedule built-in system maintenance tasks.
        
        Ensures BrainOps system health through automated maintenance,
        cleanup, and monitoring tasks.
        """
        # Daily memory optimization at 3 AM UTC
        self.schedule_recurring(
            self._optimize_memory_store,
            "0 3 * * *",
            job_id="system_memory_optimization"
        )
        
        # Hourly health check
        self.schedule_recurring(
            self._system_health_check,
            {"hours": 1},
            job_id="system_health_check"
        )
        
        # Weekly analytics aggregation
        self.schedule_recurring(
            self._aggregate_analytics,
            "0 2 * * 0",  # Sunday at 2 AM UTC
            job_id="system_analytics_aggregation"
        )
    
    async def _optimize_memory_store(self):
        """Optimize vector database and clean old memory entries."""
        # Implementation would include:
        # - Reindexing vectors for search performance
        # - Archiving old memory entries
        # - Compacting storage
        logger.info("Running memory store optimization")
    
    async def _system_health_check(self):
        """Check system health and alert on issues."""
        # Implementation would include:
        # - API availability checks
        # - Database connection health
        # - Integration status verification
        # - Alert sending if issues found
        logger.info("Running system health check")
    
    async def _aggregate_analytics(self):
        """Aggregate weekly analytics for reporting."""
        # Implementation would include:
        # - Task execution statistics
        # - AI token usage summaries
        # - Error rate calculations
        # - Performance metrics aggregation
        logger.info("Running analytics aggregation")


# Global scheduler instance
scheduler = TaskScheduler()


# Convenience decorators for route handlers
def schedule_after(delay_seconds: int):
    """
    Decorator to schedule a function to run after a delay.
    
    Usage:
        @schedule_after(300)  # Run after 5 minutes
        async def send_follow_up(user_id: str):
            # Send follow-up message
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            job_id = scheduler.schedule_once(
                func,
                delay_seconds,
                **dict(zip(func.__code__.co_varnames, args), **kwargs)
            )
            return {"scheduled": True, "job_id": job_id}
        return wrapper
    return decorator