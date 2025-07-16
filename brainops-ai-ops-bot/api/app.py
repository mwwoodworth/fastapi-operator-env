"""
FastAPI application for BrainOps AI Ops Bot
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from config.settings import Settings
from core.monitor import HealthMonitor
from core.alerts import AlertManager
from core.scheduler import JobScheduler
from connectors import get_connector, list_available_connectors


logger = logging.getLogger(__name__)


# Pydantic models for requests/responses
class HealthCheckRequest(BaseModel):
    services: Optional[List[str]] = None
    parallel: bool = True


class DeploymentRequest(BaseModel):
    service: str
    app: str
    branch: str = 'main'


class AlertRequest(BaseModel):
    service: str
    severity: str
    message: str
    details: Optional[Dict[str, Any]] = None


class JobRequest(BaseModel):
    func_name: str
    interval_minutes: Optional[int] = None
    cron_expression: Optional[str] = None
    job_id: Optional[str] = None


class ResourceListRequest(BaseModel):
    service: str
    resource_type: str


def create_app(settings: Settings) -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="BrainOps AI Ops Bot API",
        description="DevOps automation and monitoring API",
        version="1.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure based on your needs
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize components
    monitor = HealthMonitor(settings)
    alert_manager = AlertManager(settings)
    scheduler = JobScheduler(settings)
    
    # Start scheduler
    try:
        scheduler.start()
        logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
        # Continue without scheduler for now, but create a new instance to avoid issues
        scheduler = None
    
    @app.on_event("shutdown")
    def shutdown_event():
        """Clean up on shutdown"""
        try:
            if scheduler:
                scheduler.stop()
        except Exception as e:
            logger.error(f"Error during scheduler shutdown: {e}")
    
    # Routes
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "name": "BrainOps AI Ops Bot",
            "version": "1.0.0",
            "status": "operational",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/health")
    async def health():
        """API health check"""
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.post("/health/check")
    async def check_health(request: HealthCheckRequest):
        """Check health of specified services"""
        if request.services:
            results = {}
            for service in request.services:
                results[service] = monitor.check_service(service)
        else:
            results = monitor.check_all_services(parallel=request.parallel)
        
        return {
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/health/summary")
    async def health_summary():
        """Get overall health summary"""
        return monitor.get_summary()
    
    @app.get("/health/unhealthy")
    async def unhealthy_services():
        """Get list of unhealthy services"""
        return {
            "unhealthy_services": monitor.get_unhealthy_services(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.post("/deploy")
    async def deploy(request: DeploymentRequest, background_tasks: BackgroundTasks):
        """Trigger deployment for a service"""
        try:
            connector = get_connector(request.service, settings)
            
            # Run deployment in background
            def run_deployment():
                result = connector.deploy(request.app, request.branch)
                if not result['success']:
                    alert_manager.send_alert(
                        service=request.service,
                        severity='error',
                        message=f"Deployment failed for {request.app}",
                        details=result
                    )
            
            background_tasks.add_task(run_deployment)
            
            return {
                "message": "Deployment triggered",
                "service": request.service,
                "app": request.app,
                "branch": request.branch
            }
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @app.post("/alerts/send")
    async def send_alert(request: AlertRequest):
        """Send an alert"""
        success = alert_manager.send_alert(
            service=request.service,
            severity=request.severity,
            message=request.message,
            details=request.details
        )
        
        return {
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/alerts/history")
    async def alert_history(service: Optional[str] = None, hours: int = 24):
        """Get alert history"""
        return {
            "history": alert_manager.get_alert_history(service, hours),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.post("/alerts/test")
    async def test_alerts():
        """Test alert channels"""
        results = {}
        
        if settings.enable_slack_alerts:
            results['slack'] = alert_manager.test_slack_alert()
        
        if settings.enable_email_alerts:
            results['email'] = alert_manager.test_email_alert()
        
        return {
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/jobs")
    async def list_jobs():
        """List all scheduled jobs"""
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not available")
        return {
            "jobs": scheduler.get_jobs(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        """Get details for a specific job"""
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not available")
        job = scheduler.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return job
    
    @app.post("/jobs")
    async def create_job(request: JobRequest):
        """Create a new scheduled job"""
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not available")
        
        # This is simplified - in production you'd want more security
        # around what functions can be scheduled
        
        if request.func_name == "health_check":
            job_id = scheduler.add_health_check_job(
                services=settings.get_enabled_services(),
                interval_minutes=request.interval_minutes or 5
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown function: {request.func_name}"
            )
        
        return {
            "job_id": job_id,
            "message": "Job created successfully"
        }
    
    @app.delete("/jobs/{job_id}")
    async def delete_job(job_id: str):
        """Delete a scheduled job"""
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not available")
        
        success = scheduler.remove_job(job_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {"message": "Job deleted successfully"}
    
    @app.post("/jobs/{job_id}/run")
    async def run_job_now(job_id: str):
        """Run a job immediately"""
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not available")
        
        success = scheduler.run_job_now(job_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {"message": "Job triggered successfully"}
    
    @app.post("/jobs/{job_id}/pause")
    async def pause_job(job_id: str):
        """Pause a scheduled job"""
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not available")
        
        success = scheduler.pause_job(job_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {"message": "Job paused successfully"}
    
    @app.post("/jobs/{job_id}/resume")
    async def resume_job(job_id: str):
        """Resume a paused job"""
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not available")
        
        success = scheduler.resume_job(job_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return {"message": "Job resumed successfully"}
    
    @app.post("/resources/list")
    async def list_resources(request: ResourceListRequest):
        """List resources from a service"""
        try:
            connector = get_connector(request.service, settings)
            resources = connector.list_resources(request.resource_type)
            
            return {
                "service": request.service,
                "resource_type": request.resource_type,
                "resources": resources,
                "count": len(resources),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @app.get("/services")
    async def list_services():
        """List available services"""
        return {
            "available": list_available_connectors(),
            "enabled": settings.get_enabled_services(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.get("/config")
    async def get_config():
        """Get current configuration (masked)"""
        return {
            "config": settings.mask_secrets(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        """Global exception handler"""
        logger.error(f"Unhandled exception: {exc}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(exc) if settings.debug_mode else "An error occurred",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    return app