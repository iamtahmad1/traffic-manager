# src/db/__init__.py
# This file makes the db folder a Python package
# It exports both direct connections and connection pooling

from .connection import get_db_connection
from .pool import (
    initialize_pool,
    close_pool,
    get_connection,
    get_pool_status,
)

__all__ = [
    "get_db_connection",  # Direct connection (for backward compatibility)
    "initialize_pool",     # Initialize connection pool (call at startup)
    "close_pool",          # Close connection pool (call at shutdown)
    "get_connection",      # Get connection from pool (preferred for production)
    "get_pool_status",     # Get pool status (for monitoring)
]
