"""
BrainOps Operator Service - Main FastAPI Application Entry Point

This module initializes the FastAPI application, mounts all routers, configures
middleware, and handles startup/shutdown events for the BrainStack Studio backend.
It serves as the central orchestrator for all API endpoints and background services.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging

from apps.backend.routes import tasks, auth, memory, webhooks, agents
from apps.backend.core.settings import settings
from apps.backend.core.scheduler import scheduler
from apps.backend.core.logging import configure_logging
from apps.backend.memory.supabase_client import init_supabase_connection
from apps.backend.agents.base import initialize_agent_graph


# Configure structured logging for production-ready observability
configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle events for proper initialization and cleanup.
    Ensures all connections and background services start/stop gracefully.
    """
    # Startup: Initialize core services
    logger.info("Starting BrainOps Operator Service...")
    
    # Initialize Supabase connection pool for pgvector operations
    await init_supabase_connection()
    
    # Load and validate the agent graph configuration
    await initialize_agent_graph()
    
    # Start the background task scheduler for recurring operations
    scheduler.start()
    logger.info("Background scheduler started")
    
    yield
    
    # Shutdown: Cleanup resources
    logger.info("Shutting down BrainOps Operator Service...")
    scheduler.shutdown(wait=True)
    logger.info("Service shutdown complete")


# Initialize FastAPI with production-ready configuration
app = FastAPI(
    title="BrainOps Operator Service",
    description="AI-powered task automation and knowledge management for BrainStack Studio",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/api/redoc" if settings.ENABLE_DOCS else None,
)

# Configure CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security middleware for production deployments
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS
    )

# Mount feature-specific routers with URL prefixes
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint for monitoring and load balancer configuration.
    Returns service status and basic diagnostics.
    """
    return {
        "status": "healthy",
        "service": "brainops-operator",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


@app.get("/")
async def root():
    """Root endpoint redirect to API documentation."""
    return {"message": "BrainOps Operator Service", "docs": "/api/docs"}
