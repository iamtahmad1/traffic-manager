# src/db/connection.py
# This file provides database connection functionality
# 
# IMPORTANT: For production, use connection pooling (db/pool.py) instead of this!
# This file is kept for backward compatibility and direct connection needs.
# 
# Connection pooling is preferred because:
# - Reuses connections (faster)
# - Better resource management
# - Handles connection limits
# - Production best practice

import psycopg2
from logger import get_logger
from config import settings

logger = get_logger(__name__)


def get_db_connection():
    """
    Create a direct database connection (not from pool).
    
    WARNING: This creates a new connection each time, which is expensive.
    For production use, prefer get_connection() from db.pool instead.
    
    This function is kept for:
    - Backward compatibility
    - One-off scripts
    - Migration scripts
    - Testing
    
    For regular application code, use:
        from db.pool import get_connection
        with get_connection() as conn:
            # use conn
    
    Returns:
        A database connection object
    
    Note:
        You must close this connection when done: conn.close()
        Or use context manager: with get_db_connection() as conn:
    """
    logger.info("Creating direct database connection (not from pool)")
    
    # psycopg2.connect() creates a new connection to PostgreSQL
    # This is slower than getting one from the pool because:
    # 1. Network handshake (TCP connection)
    # 2. Authentication (username/password check)
    # 3. Database initialization
    
    # We use settings from centralized config instead of os.getenv()
    # This is cleaner and easier to manage
    conn = psycopg2.connect(
        host=settings.db.host,      # Where is the database? (from config)
        port=settings.db.port,      # Which port? (from config)
        dbname=settings.db.name,    # Which database? (from config)
        user=settings.db.user,      # Username (from config)
        password=settings.db.password,  # Password (from config)
    )
    
    logger.info("Direct database connection established")
    
    # Return the connection
    # IMPORTANT: Caller must close this connection!
    return conn
