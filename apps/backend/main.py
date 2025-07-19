"""
Main application entry point with full error handling and route loading.
"""

import os
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .core.settings import settings
from .core.database import engine, Base
from .core.logging import setup_logging, get_logger
from .middleware.security import SecurityMiddleware
from .middleware.logging import LoggingMiddleware

# Initialize logging first
setup_logging()
logger = get_logger(__name__)

# Track route loading for diagnostics
route_loading_status = {
    "timestamp": datetime.utcnow().isoformat(),
    "routes_loaded": [],
    "routes_failed": [],
    "import_errors": []
}

# Import routes with comprehensive error tracking
try:
    logger.info("Starting route imports...")
    from .routes import (
        auth, users, tasks, analytics, settings as settings_router,
        ai_agents, crm, reporting, integrations, automations, 
        notifications, webhooks, admin, communications, marketplace,
        erp_job_management, erp_estimating, erp_scheduling, erp_inventory,
        erp_financial, erp_task_management, erp_crm, erp_field_capture,
        langgraph, weathercraft_features
    )
    logger.info("Successfully imported all routes")
    route_loading_status["routes_loaded"] = [
        "auth", "users", "tasks", "analytics", "settings", "ai_agents",
        "crm", "reporting", "integrations", "automations", "notifications",
        "webhooks", "admin", "communications", "marketplace",
        "erp_job_management", "erp_estimating", "erp_scheduling",
        "erp_inventory", "erp_financial", "erp_task_management",
        "erp_crm", "erp_field_capture", "langgraph", "weathercraft_features"
    ]
except Exception as e:
    logger.error(f"Failed to import routes: {str(e)}", exc_info=True)
    route_loading_status["import_errors"].append({
        "error": str(e),
        "type": type(e).__name__
    })
    # Set all routes to None if import fails
    auth = users = tasks = analytics = settings_router = None
    ai_agents = crm = reporting = integrations = automations = None
    notifications = webhooks = admin = communications = marketplace = None
    erp_job_management = erp_estimating = erp_scheduling = erp_inventory = None
    erp_financial = erp_task_management = erp_crm = erp_field_capture = None
    langgraph = weathercraft_features = None
    route_loading_status["routes_failed"] = ["all routes failed to import"]

# Special marketplace import handling
marketplace_router = None
try:
    from .routes.marketplace import router as marketplace_router
    route_loading_status["routes_loaded"].append("marketplace_router")
except ImportError:
    logger.warning("Marketplace router not available!")
    route_loading_status["routes_failed"].append("marketplace_router")
except Exception as e:
    logger.error(f"Error importing marketplace router: {e}")
    route_loading_status["routes_failed"].append(f"marketplace_router: {str(e)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    # Startup
    logger.info("Starting BrainOps Backend...")
    
    # Create database tables
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    
    # Log configuration
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database URL configured: {'Yes' if settings.DATABASE_URL else 'No'}")
    logger.info(f"CORS Origins: {settings.CORS_ORIGINS}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down BrainOps Backend...")


# Initialize FastAPI app
app = FastAPI(
    title="BrainOps Backend",
    description="AI-Powered Business Operations Platform",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# Add session middleware (required for OAuth)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="brainops_session",
    max_age=86400,  # 24 hours
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Process-Time"],
)

# Add custom middleware
app.add_middleware(SecurityMiddleware)
app.add_middleware(LoggingMiddleware)


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with consistent format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "request_id": request.state.request_id if hasattr(request.state, 'request_id') else None
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed feedback."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation error",
            "errors": exc.errors(),
            "request_id": request.state.request_id if hasattr(request.state, 'request_id') else None
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Internal server error",
            "request_id": request.state.request_id if hasattr(request.state, 'request_id') else None
        }
    )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service information."""
    return {
        "service": "BrainOps Operator Service",
        "version": "1.0.0",
        "documentation": "/docs" if settings.ENVIRONMENT != "production" else "Contact support for API documentation",
        "health": "/health",
        "status": "operational"
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


# Diagnostic endpoint for route loading status
@app.get("/api/v1/diagnostics/routes", tags=["Diagnostics"])
async def get_route_diagnostics():
    """Get diagnostic information about route loading."""
    return {
        "status": "diagnostic",
        "route_loading": route_loading_status,
        "api_prefix": settings.API_V1_PREFIX,
        "environment": settings.ENVIRONMENT,
        "routes_registered": len(route_loading_status["routes_loaded"]),
        "routes_failed": len(route_loading_status["routes_failed"]),
        "has_errors": len(route_loading_status["import_errors"]) > 0
    }


# Include routers with error handling and logging
def include_router_safe(router, prefix: str, tags: list, router_name: str):
    """Safely include a router with error handling."""
    if router is not None:
        try:
            app.include_router(router, prefix=prefix, tags=tags)
            logger.info(f"Successfully mounted router: {router_name} at {prefix}")
            route_loading_status["routes_loaded"].append(f"mounted_{router_name}")
        except Exception as e:
            logger.error(f"Failed to mount router {router_name}: {str(e)}")
            route_loading_status["routes_failed"].append(f"mount_{router_name}: {str(e)}")
    else:
        logger.warning(f"Router {router_name} is None, skipping mount")
        route_loading_status["routes_failed"].append(f"mount_{router_name}: router is None")


# Core routes
if auth:
    include_router_safe(auth.router, f"{settings.API_V1_PREFIX}/auth", ["Authentication"], "auth")

if users:
    include_router_safe(users.router, f"{settings.API_V1_PREFIX}/users", ["Users"], "users")

if tasks:
    include_router_safe(tasks.router, f"{settings.API_V1_PREFIX}/tasks", ["Tasks"], "tasks")

if analytics:
    include_router_safe(analytics.router, f"{settings.API_V1_PREFIX}/analytics", ["Analytics"], "analytics")

if settings_router:
    include_router_safe(settings_router.router, f"{settings.API_V1_PREFIX}/settings", ["Settings"], "settings")

# AI and automation routes
if ai_agents:
    include_router_safe(ai_agents.router, f"{settings.API_V1_PREFIX}/ai-agents", ["AI Agents"], "ai_agents")

if automations:
    include_router_safe(automations.router, f"{settings.API_V1_PREFIX}/automations", ["Automations"], "automations")

if langgraph:
    include_router_safe(langgraph.router, f"{settings.API_V1_PREFIX}/langgraph", ["LangGraph"], "langgraph")

# Business routes
if crm:
    include_router_safe(crm.router, f"{settings.API_V1_PREFIX}/crm", ["CRM"], "crm")

if reporting:
    include_router_safe(reporting.router, f"{settings.API_V1_PREFIX}/reporting", ["Reporting"], "reporting")

# Integration routes
if integrations:
    include_router_safe(integrations.router, f"{settings.API_V1_PREFIX}/integrations", ["Integrations"], "integrations")

if webhooks:
    include_router_safe(webhooks.router, f"{settings.API_V1_PREFIX}/webhooks", ["Webhooks"], "webhooks")

if notifications:
    include_router_safe(notifications.router, f"{settings.API_V1_PREFIX}/notifications", ["Notifications"], "notifications")

if communications:
    include_router_safe(communications.router, f"{settings.API_V1_PREFIX}/communications", ["Communications"], "communications")

# ERP routes
if erp_job_management:
    include_router_safe(erp_job_management.router, f"{settings.API_V1_PREFIX}/erp/jobs", ["ERP - Jobs"], "erp_job_management")

if erp_estimating:
    include_router_safe(erp_estimating.router, f"{settings.API_V1_PREFIX}/erp/estimates", ["ERP - Estimating"], "erp_estimating")

if erp_scheduling:
    include_router_safe(erp_scheduling.router, f"{settings.API_V1_PREFIX}/erp/scheduling", ["ERP - Scheduling"], "erp_scheduling")

if erp_inventory:
    include_router_safe(erp_inventory.router, f"{settings.API_V1_PREFIX}/erp/inventory", ["ERP - Inventory"], "erp_inventory")

if erp_financial:
    include_router_safe(erp_financial.router, f"{settings.API_V1_PREFIX}/erp/financial", ["ERP - Financial"], "erp_financial")

if erp_task_management:
    include_router_safe(erp_task_management.router, f"{settings.API_V1_PREFIX}/erp/tasks", ["ERP - Tasks"], "erp_task_management")

if erp_crm:
    include_router_safe(erp_crm.router, f"{settings.API_V1_PREFIX}/erp/crm", ["ERP - CRM"], "erp_crm")

if erp_field_capture:
    include_router_safe(erp_field_capture.router, f"{settings.API_V1_PREFIX}/erp/field", ["ERP - Field Capture"], "erp_field_capture")

# Feature routes
if weathercraft_features:
    include_router_safe(weathercraft_features.router, f"{settings.API_V1_PREFIX}/features", ["Features"], "weathercraft_features")

# Marketplace route (special handling)
if marketplace_router:
    include_router_safe(marketplace_router, f"{settings.API_V1_PREFIX}/marketplace", ["Marketplace"], "marketplace")

# Admin routes (last to override if needed)
if admin:
    include_router_safe(admin.router, f"{settings.API_V1_PREFIX}/admin", ["Admin"], "admin")


# Log final route status
total_routes = len(app.routes)
logger.info(f"Application initialized with {total_routes} routes")
logger.info(f"Routes loaded: {len(route_loading_status['routes_loaded'])}")
logger.info(f"Routes failed: {len(route_loading_status['routes_failed'])}")

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "apps.backend.main:app",
        host="0.0.0.0",
        port=port,
        reload=settings.ENVIRONMENT == "development",
        log_level="info"
    )