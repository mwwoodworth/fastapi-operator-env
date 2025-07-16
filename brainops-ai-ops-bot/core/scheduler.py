"""
Job scheduling module for automated tasks
"""

import logging
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import pytz

from config.settings import Settings


logger = logging.getLogger(__name__)


class JobScheduler:
    """Manage scheduled jobs and tasks"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self._scheduler = None
        self._job_handlers = {}
        self._init_scheduler()
    
    def _init_scheduler(self):
        """Initialize the scheduler with configuration"""
        try:
            # Use memory store for simplicity in initial deployment
            # TODO: Switch to SQLAlchemy when database is properly configured
            from apscheduler.jobstores.memory import MemoryJobStore
            
            jobstores = {
                'default': MemoryJobStore()
            }
            
            # Configure executors
            from apscheduler.executors.pool import ProcessPoolExecutor
            
            executors = {
                'default': ThreadPoolExecutor(20),
                'processpool': ProcessPoolExecutor(5)
            }
            
            # Configure job defaults
            job_defaults = {
            'coalesce': False,
            'max_instances': 3,
            'misfire_grace_time': 30
        }
        
            # Create scheduler
            self._scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=pytz.timezone(self.settings.timezone)
            )
            
            # Add listeners with proper event mask handling
            # EVENT_JOB_ERROR and EVENT_JOB_EXECUTED are integer constants
            # Ensure they are integers to avoid TypeError
            logger.debug(f"EVENT_JOB_ERROR type: {type(EVENT_JOB_ERROR)}, value: {EVENT_JOB_ERROR}")
            logger.debug(f"EVENT_JOB_EXECUTED type: {type(EVENT_JOB_EXECUTED)}, value: {EVENT_JOB_EXECUTED}")
            
            # Add listeners with explicit integer event codes
            self._scheduler.add_listener(
                self._job_error_listener,
                int(EVENT_JOB_ERROR) if not isinstance(EVENT_JOB_ERROR, int) else EVENT_JOB_ERROR
            )
            
            self._scheduler.add_listener(
                self._job_executed_listener,
                int(EVENT_JOB_EXECUTED) if not isinstance(EVENT_JOB_EXECUTED, int) else EVENT_JOB_EXECUTED
            )
            
            logger.info("Scheduler initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            # Create a minimal scheduler without advanced features
            self._scheduler = BackgroundScheduler()
            logger.warning("Using minimal scheduler configuration")
    
    def _job_error_listener(self, event):
        """Handle job errors"""
        logger.error(
            f"Job {event.job_id} crashed with exception: {event.exception}"
        )
        
        # Could send alert here
        if hasattr(self, 'alert_manager'):
            self.alert_manager.send_alert(
                service='scheduler',
                severity='error',
                message=f"Scheduled job {event.job_id} failed",
                details={'exception': str(event.exception)}
            )
    
    def _job_executed_listener(self, event):
        """Handle successful job execution"""
        logger.debug(f"Job {event.job_id} executed successfully")
    
    def start(self):
        """Start the scheduler"""
        try:
            if not self._scheduler.running:
                self._scheduler.start()
                logger.info("Job scheduler started")
            else:
                logger.info("Job scheduler is already running")
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    def stop(self):
        """Stop the scheduler"""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=True)
            logger.info("Job scheduler stopped")
    
    def add_job(self, func: Callable, interval_minutes: Optional[int] = None,
                cron_expression: Optional[str] = None, job_id: Optional[str] = None,
                **kwargs) -> str:
        """
        Add a job to the scheduler
        
        Args:
            func: Function to execute
            interval_minutes: Run every N minutes
            cron_expression: Cron expression for scheduling
            job_id: Unique job identifier
            **kwargs: Additional arguments for the job
            
        Returns:
            str: Job ID
        """
        if not interval_minutes and not cron_expression:
            raise ValueError("Either interval_minutes or cron_expression must be provided")
        
        # Generate job ID if not provided
        if not job_id:
            job_id = f"{func.__name__}_{datetime.utcnow().timestamp()}"
        
        # Store handler
        self._job_handlers[job_id] = func
        
        # Create trigger
        if interval_minutes:
            trigger = IntervalTrigger(minutes=interval_minutes)
        else:
            trigger = CronTrigger.from_crontab(cron_expression)
        
        # Add job
        job = self._scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            **kwargs
        )
        
        logger.info(f"Added job {job_id} with trigger {trigger}")
        return job.id
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the scheduler"""
        try:
            self._scheduler.remove_job(job_id)
            if job_id in self._job_handlers:
                del self._job_handlers[job_id]
            logger.info(f"Removed job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a scheduled job"""
        try:
            self._scheduler.pause_job(job_id)
            logger.info(f"Paused job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause job {job_id}: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        try:
            self._scheduler.resume_job(job_id)
            logger.info(f"Resumed job {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to resume job {job_id}: {e}")
            return False
    
    def get_jobs(self) -> List[Dict[str, Any]]:
        """Get list of all scheduled jobs"""
        jobs = []
        
        for job in self._scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'trigger': str(job.trigger),
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'pending': job.pending,
                'func': job.func.__name__ if hasattr(job.func, '__name__') else str(job.func)
            })
        
        return jobs
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific job"""
        job = self._scheduler.get_job(job_id)
        
        if not job:
            return None
        
        return {
            'id': job.id,
            'name': job.name,
            'trigger': str(job.trigger),
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'pending': job.pending,
            'func': job.func.__name__ if hasattr(job.func, '__name__') else str(job.func),
            'args': job.args,
            'kwargs': job.kwargs
        }
    
    def reschedule_job(self, job_id: str, interval_minutes: Optional[int] = None,
                      cron_expression: Optional[str] = None) -> bool:
        """Reschedule an existing job"""
        try:
            if interval_minutes:
                trigger = IntervalTrigger(minutes=interval_minutes)
            elif cron_expression:
                trigger = CronTrigger.from_crontab(cron_expression)
            else:
                raise ValueError("Either interval_minutes or cron_expression must be provided")
            
            self._scheduler.reschedule_job(job_id, trigger=trigger)
            logger.info(f"Rescheduled job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reschedule job {job_id}: {e}")
            return False
    
    def run_job_now(self, job_id: str) -> bool:
        """Run a job immediately"""
        try:
            job = self._scheduler.get_job(job_id)
            if job:
                self._scheduler.modify_job(
                    job_id,
                    next_run_time=datetime.now(pytz.timezone(self.settings.timezone))
                )
                logger.info(f"Triggered immediate run of job {job_id}")
                return True
            else:
                logger.error(f"Job {job_id} not found")
                return False
                
        except Exception as e:
            logger.error(f"Failed to run job {job_id}: {e}")
            return False
    
    def add_health_check_job(self, services: List[str], interval_minutes: int = 5):
        """Add a health check job for specified services"""
        from core.monitor import HealthMonitor
        from core.alerts import AlertManager
        
        monitor = HealthMonitor(self.settings)
        alert_manager = AlertManager(self.settings)
        
        def health_check_job():
            logger.info(f"Running health check for {len(services)} services")
            
            for service in services:
                try:
                    result = monitor.check_service(service)
                    
                    if not result['healthy']:
                        alert_manager.send_alert(
                            service=service,
                            severity='error',
                            message=f"Health check failed: {result.get('message', 'Unknown error')}",
                            details={
                                'response_time': result.get('response_time', 0),
                                'checked_at': result.get('checked_at')
                            }
                        )
                except Exception as e:
                    logger.error(f"Error checking {service}: {e}")
                    alert_manager.send_alert(
                        service=service,
                        severity='critical',
                        message=f"Health check error: {str(e)}"
                    )
        
        return self.add_job(
            func=health_check_job,
            interval_minutes=interval_minutes,
            job_id='health_check_job'
        )
    
    def add_deployment_job(self, service: str, cron_expression: str):
        """Add a scheduled deployment job"""
        from connectors import get_connector
        
        def deployment_job():
            logger.info(f"Running scheduled deployment for {service}")
            
            try:
                connector = get_connector(service, self.settings)
                result = connector.deploy('main', branch='main')
                
                if result['success']:
                    logger.info(f"Deployment triggered successfully: {result}")
                else:
                    logger.error(f"Deployment failed: {result}")
                    
            except Exception as e:
                logger.error(f"Deployment error: {e}")
        
        return self.add_job(
            func=deployment_job,
            cron_expression=cron_expression,
            job_id=f'deployment_{service}'
        )