"""
Alembic environment configuration for BrainOps database migrations.

This module configures the Alembic migration environment, connecting to
the Supabase PostgreSQL database and managing schema versioning.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys
from pathlib import Path

# Add the backend directory to Python path for imports
sys.path.append(str(Path(__file__).parents[3]))

from apps.backend.core.settings import settings
from apps.backend.db.models import Base  # Import all models

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for autogenerate support
target_metadata = Base.metadata

def get_database_url():
    """
    Construct database URL from settings.
    
    Handles both local development and production Supabase connections.
    """
    # Use the Supabase connection string from settings
    return settings.SUPABASE_DB_URL

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.
    """
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    
    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    # Override the sqlalchemy.url in alembic.ini with our settings
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_database_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

# Determine which mode to run migrations
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()