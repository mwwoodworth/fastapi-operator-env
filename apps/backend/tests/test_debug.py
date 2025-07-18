"""
Debug test to check table creation.
"""

import pytest
from sqlalchemy import inspect

from ..core.database import Base, engine


def test_show_registered_tables():
    """Show what tables are registered in Base.metadata."""
    print("\nRegistered tables in Base.metadata:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")
    
    # Check if any tables exist
    assert len(Base.metadata.tables) > 0, "No tables registered in Base.metadata!"


def test_create_tables_and_check():
    """Create tables and verify they exist."""
    # Drop all first to clean
    Base.metadata.drop_all(bind=engine)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Check what tables were created
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    print("\nActual tables in database:")
    for table in existing_tables:
        print(f"  - {table}")
    
    # Should have created some tables
    assert len(existing_tables) > 0, "No tables were created in the database!"
    
    # Check if users table exists
    assert "users" in existing_tables, "Users table was not created!"