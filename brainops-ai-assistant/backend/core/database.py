"""Database connection and session management."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
try:
    from sqlalchemy.ext.asyncio import async_sessionmaker
except ImportError:
    # Fallback for SQLAlchemy 1.4
    async_sessionmaker = sessionmaker
from sqlalchemy.pool import StaticPool
from loguru import logger

from core.config import settings
from models.db import Base


class DatabaseManager:
    """Database manager for async SQLAlchemy operations."""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize database connection and create tables."""
        if self._initialized:
            return
        
        try:
            # Create async engine
            database_url = str(settings.ASYNC_DATABASE_URL)
            
            if "sqlite" in database_url:
                self.engine = create_async_engine(
                    database_url,
                    echo=settings.DEBUG,
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False}
                )
            else:
                self.engine = create_async_engine(
                    database_url,
                    echo=settings.DEBUG,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    max_overflow=20,
                    pool_size=10
                )
            
            # Create session factory
            try:
                # SQLAlchemy 2.0+ style
                self.session_factory = async_sessionmaker(
                    bind=self.engine,
                    class_=AsyncSession,
                    expire_on_commit=False
                )
            except TypeError:
                # SQLAlchemy 1.4 style
                self.session_factory = sessionmaker(
                    bind=self.engine,
                    class_=AsyncSession,
                    expire_on_commit=False
                )
            
            # Create tables
            await self.create_tables()
            
            self._initialized = True
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def create_tables(self):
        """Create database tables."""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    async def drop_tables(self):
        """Drop all database tables."""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise
    
    async def get_session(self) -> AsyncSession:
        """Get a database session."""
        if not self._initialized:
            await self.initialize()
        return self.session_factory()
    
    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")


# Global database manager instance
db_manager = DatabaseManager()


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    session = await db_manager.get_session()
    try:
        yield session
    except Exception as e:
        await session.rollback()
        logger.error(f"Database transaction rolled back: {e}")
        raise
    finally:
        await session.close()


async def get_db_session() -> AsyncSession:
    """Get database session for dependency injection."""
    return await db_manager.get_session()


async def init_db():
    """Initialize database - called at startup."""
    await db_manager.initialize()


async def close_db():
    """Close database connections - called at shutdown."""
    await db_manager.close()


# Database health check
async def check_database_health() -> dict:
    """Check database connection health."""
    try:
        async with get_db() as db:
            # Simple query to test connection
            result = await db.execute("SELECT 1")
            result.scalar()
            
            return {
                "status": "healthy",
                "database_url": str(settings.ASYNC_DATABASE_URL).split("@")[0] + "@***",
                "connection_pool": {
                    "size": db.bind.pool.size(),
                    "checked_out": db.bind.pool.checkedout(),
                    "checked_in": db.bind.pool.checkedin(),
                    "overflow": db.bind.pool.overflow()
                } if hasattr(db.bind, "pool") else None
            }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Migration utilities
async def run_migrations():
    """Run database migrations."""
    try:
        # In a real application, you'd use Alembic here
        # For now, we'll just create/update tables
        await db_manager.create_tables()
        logger.info("Database migrations completed")
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise


async def seed_database():
    """Seed database with initial data."""
    try:
        async with get_db() as db:
            # Check if we already have data
            from models.db import User
            from sqlalchemy import select
            
            result = await db.execute(select(User).limit(1))
            if result.scalar():
                logger.info("Database already seeded")
                return
            
            # Create admin user
            from services.auth import AuthService
            auth_service = AuthService()
            
            admin_user = await auth_service.create_user(
                email="admin@brainops.ai",
                username="admin",
                password="changeme123!",
                full_name="BrainOps Administrator",
                is_superuser=True
            )
            
            logger.info(f"Created admin user: {admin_user.email}")
            
            # Create system configuration entries
            from models.db import SystemConfigDB
            import uuid
            
            system_configs = [
                {
                    "key": "assistant.default_model",
                    "value": "gpt-4-turbo-preview",
                    "description": "Default AI model for assistant responses"
                },
                {
                    "key": "assistant.max_tokens",
                    "value": 4000,
                    "description": "Maximum tokens for assistant responses"
                },
                {
                    "key": "security.max_failed_logins",
                    "value": 5,
                    "description": "Maximum failed login attempts before lockout"
                },
                {
                    "key": "files.max_size_mb",
                    "value": 50,
                    "description": "Maximum file size in MB"
                },
                {
                    "key": "commands.timeout_seconds",
                    "value": 300,
                    "description": "Command execution timeout in seconds"
                }
            ]
            
            for config in system_configs:
                db_config = SystemConfigDB(
                    id=str(uuid.uuid4()),
                    key=config["key"],
                    value=config["value"],
                    description=config["description"],
                    updated_by=admin_user.id
                )
                db.add(db_config)
            
            await db.commit()
            logger.info("Database seeded successfully")
            
    except Exception as e:
        logger.error(f"Database seeding failed: {e}")
        raise


# Context manager for transactions
@asynccontextmanager
async def db_transaction():
    """Context manager for database transactions."""
    async with get_db() as db:
        try:
            yield db
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(f"Transaction rolled back: {e}")
            raise