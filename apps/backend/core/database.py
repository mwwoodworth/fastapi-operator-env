"""
Database configuration and session management for BrainOps backend.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
import logging

from .settings import settings

logger = logging.getLogger(__name__)

# Create database engine
if settings.database_url.startswith("sqlite"):
    # SQLite specific settings
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=NullPool
    )
else:
    # PostgreSQL/MySQL settings
    # Use default pool settings if not defined
    pool_size = getattr(settings, 'DB_POOL_SIZE', 20)
    max_overflow = getattr(settings, 'DB_MAX_OVERFLOW', 40)
    pool_timeout = getattr(settings, 'DB_POOL_TIMEOUT', 30)
    
    engine = create_engine(
        settings.database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True  # Verify connections before using
    )

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()


def get_db() -> Session:
    """
    Dependency to get database session.
    
    Usage:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def init_database():
    """Initialize database tables."""
    try:
        # Import all models to register them with Base
        from ..db.models import (
            TaskExecution, AgentExecution, MemoryEntry,
            WebhookEvent, SystemConfig
        )
        from ..db.business_models import (
            User, Team, Project, ProjectTask, TaskComment,
            Product, Purchase, Subscription, APIKey, UserSession,
            Document, Notification, Inspection, InspectionPhoto,
            Estimate, Integration, Workflow, WorkflowRun
        )
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database tables initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise


async def check_database_health() -> bool:
    """Check if database is accessible."""
    try:
        db = SessionLocal()
        # Execute simple query
        db.execute("SELECT 1")
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False


async def close_database_connections():
    """Close all database connections."""
    try:
        engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error closing database connections: {str(e)}")


# Database utilities
class DatabaseTransaction:
    """Context manager for database transactions."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def __enter__(self):
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.db.rollback()
        else:
            self.db.commit()


def bulk_insert(db: Session, objects: list):
    """Efficiently insert multiple objects."""
    try:
        db.bulk_save_objects(objects)
        db.commit()
    except Exception as e:
        db.rollback()
        raise


def bulk_update(db: Session, mappings: list):
    """Efficiently update multiple objects."""
    try:
        db.bulk_update_mappings(mappings)
        db.commit()
    except Exception as e:
        db.rollback()
        raise