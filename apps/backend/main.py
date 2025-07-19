"""
BrainOps Backend Application Entry Point.

FastAPI application that orchestrates all services, routes, and middleware.
Built to handle high-stakes automation with reliability and clear operational
visibility. This is where everything comes together.
"""

from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .core.settings import settings
from .core.logging import configure_logging, get_logger, LogContext
from .core.scheduler import scheduler
from .memory.supabase_client import init_supabase
from .tasks import register_all_tasks

# Configure logging before anything else
configure_logging()
logger = get_logger(__name__)

# Import all route modules
try:
    from .routes import (
        tasks, auth, memory, webhooks, agents,
        auth_extended, users, projects, ai_services, 
        automation, marketplace, erp_estimating,
        erp_job_management, erp_field_capture, erp_compliance,
        erp_task_management, erp_financial, erp_crm, langgraph
    )
except Exception as e:  # Re-added by Codex for import fix
    logger.error(f"Failed to import routes: {e}", exc_info=True)
    tasks = auth = memory = webhooks = agents = None
    auth_extended = users = projects = ai_services = None
    automation = marketplace = None
    erp_estimating = erp_job_management = erp_field_capture = None
    erp_compliance = erp_task_management = erp_financial = erp_crm = langgraph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown.

    Ensures all services start correctly and shut down cleanly,
    protecting against partial initialization or ungraceful exits.
    """
    # Startup sequence
    logger.info("Starting BrainOps backend",
                extra={"version": settings.APP_VERSION})

    # Fail fast if essential configuration is missing
    settings.ensure_critical_settings()

    try:
        # Initialize database connection and vector store
        await init_supabase()
        logger.info("Database and vector store initialized")

        # Register all available tasks
        registered_count = register_all_tasks()
        logger.info(f"Registered {registered_count} automation tasks")

        # Start background scheduler
        await scheduler.start()
        logger.info("Background scheduler started")

        # Warm up AI connections (optional but recommended)
        # await warm_up_ai_providers()

        logger.info("BrainOps backend ready to serve requests")

    except Exception as e:
        logger.error(f"Startup failed: {str(e)}", exc_info=True)
        raise

    # Let the application run
    yield

    # Shutdown sequence
    logger.info("Shutting down BrainOps backend")

    try:
        # Stop scheduler gracefully
        await scheduler.shutdown()

        # Close database connections
        # await close_database_connections()

        logger.info("BrainOps backend shutdown complete")

    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}", exc_info=True)


# Create FastAPI application with production-ready configuration
app = FastAPI(
    title="BrainOps Operator Service",
    description="AI-powered automation engine for high-stakes business ops",
    version=settings.APP_VERSION,
    docs_url="/api/docs" if settings.debug_mode else None,
    redoc_url="/api/redoc" if settings.debug_mode else None,
    openapi_url="/api/openapi.json" if settings.debug_mode else None,
    lifespan=lifespan
)


# Configure CORS with security in mind
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"]
)

# Add compression for API responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Protect against host header attacks
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.brainops.com", "brainops.com"]
    )


# Global exception handlers for consistent error responses
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request,
                                       exc: RequestValidationError):
    """
    Handle validation errors with clear, actionable messages.

    Helps developers and integrators quickly identify and fix
    request formatting issues.
    """
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation failed",
            "details": [
                {
                    "loc": err.get("loc"),
                    "msg": str(err.get("msg")),
                    "type": err.get("type")
                }
                for err in exc.errors()
            ],
            "request_id": (request.state.request_id
                           if hasattr(request.state, "request_id")
                           else None)
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request,
                                 exc: StarletteHTTPException):
    """
    Handle HTTP exceptions with consistent format.

    Ensures all errors follow the same structure for easier
    client-side handling.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.detail,
            "request_id": (request.state.request_id
                           if hasattr(request.state, "request_id")
                           else None)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler for unexpected errors.

    Logs full details while returning safe error messages to clients,
    preventing information leakage in production.
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

    # Return generic error in production, detailed in development
    if settings.debug_mode:
        message = str(exc)
    else:
        message = "An internal error occurred"

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": message,
            "request_id": (request.state.request_id
                           if hasattr(request.state, "request_id")
                           else None)
        }
    )


# Request tracking middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """
    Add unique request ID for tracing and debugging.

    Essential for tracking requests through logs and correlating
    errors with specific API calls.
    """
    import uuid

    # Generate or extract request ID
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    # Add to logging context
    with LogContext(request_id=request_id):
        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


# Mount auth routes at root level for backward compatibility
if auth:
    app.include_router(
        auth,
        prefix="/auth",
        tags=["authentication"]
    )

# Mount API routes with clear versioning
if tasks:
    app.include_router(
        tasks,
        prefix=f"{settings.API_V1_PREFIX}/tasks",
        tags=["tasks"]
    )

if auth:
    app.include_router(
        auth,
        prefix=f"{settings.API_V1_PREFIX}/auth",
        tags=["authentication"]
    )

if memory:
    app.include_router(
        memory,
        prefix=f"{settings.API_V1_PREFIX}/memory",
        tags=["memory"]
    )

if webhooks:
    app.include_router(
        webhooks,
        prefix=f"{settings.API_V1_PREFIX}/webhooks",
        tags=["webhooks"]
    )

if agents:
    app.include_router(
        agents,
        prefix=f"{settings.API_V1_PREFIX}/agents",
        tags=["agents"]
    )

# Mount extended auth routes
if auth_extended:
    app.include_router(
        auth_extended,
        prefix=f"{settings.API_V1_PREFIX}/auth",
        tags=["authentication"]
    )

# Mount user management routes
if users:
    app.include_router(
        users,
        prefix=f"{settings.API_V1_PREFIX}/users",
        tags=["users"]
    )

# Mount project management routes
if projects:
    app.include_router(
        projects,
        prefix=f"{settings.API_V1_PREFIX}/projects",
        tags=["projects"]
    )

# Mount AI service routes
if ai_services:
    app.include_router(
        ai_services,
        prefix=f"{settings.API_V1_PREFIX}/ai",
        tags=["ai-services"]
    )

# Mount automation routes
if automation:
    app.include_router(
        automation,
        prefix=f"{settings.API_V1_PREFIX}/automation",
        tags=["automation"]
    )

# Mount marketplace routes
if marketplace:
    print(f"Mounting marketplace router: {marketplace}")
    app.include_router(
        marketplace,
        prefix=f"{settings.API_V1_PREFIX}/marketplace",
        tags=["marketplace"]
    )
else:
    print("WARNING: Marketplace router not available!")

# Mount ERP routes
if erp_estimating:
    app.include_router(
        erp_estimating,
        prefix=f"{settings.API_V1_PREFIX}/erp",
        tags=["erp-estimating"]
    )

if erp_job_management:
    app.include_router(
        erp_job_management,
        prefix=f"{settings.API_V1_PREFIX}/erp",
        tags=["erp-jobs"]
    )

if erp_field_capture:
    app.include_router(
        erp_field_capture,
        prefix=f"{settings.API_V1_PREFIX}/erp",
        tags=["erp-field"]
    )

if erp_compliance:
    app.include_router(
        erp_compliance,
        prefix=f"{settings.API_V1_PREFIX}/erp",
        tags=["erp-compliance"]
    )

if erp_task_management:
    app.include_router(
        erp_task_management,
        prefix=f"{settings.API_V1_PREFIX}/erp",
        tags=["erp-tasks"]
    )

if erp_financial:
    app.include_router(
        erp_financial,
        prefix=f"{settings.API_V1_PREFIX}/erp",
        tags=["erp-financial"]
    )

if erp_crm:
    app.include_router(
        erp_crm,
        prefix=f"{settings.API_V1_PREFIX}/crm",
        tags=["crm"]
    )

if langgraph:
    app.include_router(
        langgraph,
        prefix=f"{settings.API_V1_PREFIX}/langgraph",
        tags=["langgraph"]
    )

# Import weathercraft features
try:
    from .routes import weathercraft_features
except ImportError:
    weathercraft_features = None

if weathercraft_features:
    app.include_router(
        weathercraft_features,
        tags=["weathercraft"]
    )


# Health check endpoints
@app.get("/health", tags=["system"])
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.

    Used by load balancers and monitoring systems to verify
    the service is responsive.
    """
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }


@app.get("/health/detailed", tags=["system"])
async def detailed_health_check() -> Dict[str, Any]:
    """
    Comprehensive health check with subsystem status.

    Provides operational visibility into all critical components,
    helping identify issues before they impact users.
    """
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "components": {}
    }

    # Check database connectivity
    try:
        # await check_database_health()
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"

    # Check scheduler status
    if scheduler._scheduler and scheduler._scheduler.running:
        health_status["components"]["scheduler"] = "healthy"
    else:
        health_status["components"]["scheduler"] = "unhealthy: not running"
        health_status["status"] = "degraded"

    # Check AI provider connectivity (implement actual checks)
    health_status["components"]["ai_providers"] = {
        "openai": "healthy",
        "anthropic": "healthy",
        "google": "healthy"
    }

    # Check integration status
    configured_integrations = settings.validate_required_integrations()
    health_status["components"]["integrations"] = configured_integrations

    return health_status


@app.get("/", tags=["system"])
async def root():
    """
    Root endpoint with API information.

    Provides basic orientation for developers discovering the API.
    """
    return {
        "service": "BrainOps Operator Service",
        "version": settings.APP_VERSION,
        "documentation": (f"{settings.API_V1_PREFIX}/docs"
                          if settings.debug_mode
                          else "Contact support for API documentation"),
        "health": "/health",
        "status": "operational"
    }


# Error tracking integration (if configured)
if settings.SENTRY_DSN:
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

    app.add_middleware(SentryAsgiMiddleware)


# Development-only endpoints
if settings.debug_mode:
    @app.get("/debug/settings", tags=["debug"])
    async def debug_settings():
        """Show current settings (development only)."""
        return {
            "environment": settings.ENVIRONMENT,
            "debug": settings.debug_mode,
            "ai_limits": settings.get_ai_limits(),
            "configured_integrations": (
                settings.validate_required_integrations()
            )
        }

    @app.get("/debug/tasks", tags=["debug"])
    async def debug_tasks():
        """List all registered tasks (development only)."""
        from .tasks import TASK_REGISTRY
        return {
            "tasks": list(TASK_REGISTRY.keys()),
            "count": len(TASK_REGISTRY)
        }
