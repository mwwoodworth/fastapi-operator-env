"""
Database module initialization.

Provides database connection management and migration utilities.
Built to ensure reliable data persistence for high-stakes operations.
"""

from ..core.logging import get_logger

logger = get_logger(__name__)

# Database module version for migration tracking
__version__ = "1.0.0"

# Module initialization
logger.info("Database module initialized", extra={"version": __version__})