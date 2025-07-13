from __future__ import annotations

from logging.config import fileConfig
from configparser import ConfigParser
from sqlalchemy import engine_from_config, pool
from alembic import context
import os

import db.models  # noqa: F401

config = context.config
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Configure logging only if the config has logging sections
parser = ConfigParser()
parser.read(config.config_file_name)
if parser.has_section("loggers"):
    fileConfig(config.config_file_name)

target_metadata = db.models.Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
