# src/db/pool.py
# This file implements database connection pooling
# Connection pooling is a production pattern that reuses database connections
# instead of creating a new one for each request

# Why connection pooling?
# - Creating connections is expensive (network handshake, authentication)
# - Databases have connection limits (can't have unlimited connections)
# - Pooling improves performance and resource usage
# - Better than creating/destroying connections repeatedly

import psycopg2
from psycopg2 import pool, extensions
from contextlib import contextmanager
from typing import Generator, Optional
from logger import get_logger
from config import settings
from metrics import DB_CONNECTION_ERRORS_TOTAL

logger = get_logger(__name__)

# Global connection pool
# This is a singleton - one pool for the entire application
# The pool manages a collection of reusable database connections
_connection_pool: Optional[pool.ThreadedConnectionPool] = None


def initialize_pool():
    """
    Initialize the database connection pool.
    
    This function creates a pool of database connections that can be reused.
    The pool is created once when the application starts, not for each request.
    
    How it works:
    1. Pool starts with min_connections connections
    2. When you need a connection, pool gives you one from the pool
    3. When you're done, you return it to the pool (don't close it!)
    4. Pool can grow up to max_connections if needed
    5. Connections are reused, saving time and resources
    
    This should be called once at application startup.
    """
    global _connection_pool
    
    if _connection_pool is not None:
        logger.warning("Connection pool already initialized")
        return
    
    logger.info(
        f"Initializing database connection pool: "
        f"min={settings.db.min_connections}, max={settings.db.max_connections}"
    )
    
    try:
        # ThreadedConnectionPool creates a pool that's safe to use from multiple threads
        # This is important for web servers that handle multiple requests concurrently
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=settings.db.min_connections,  # Minimum connections to keep
            maxconn=settings.db.max_connections,  # Maximum connections allowed
            host=settings.db.host,
            port=settings.db.port,
            dbname=settings.db.name,
            user=settings.db.user,
            password=settings.db.password,
        )
        
        logger.info("Database connection pool initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise


def close_pool():
    """
    Close the database connection pool.
    
    This should be called when the application shuts down.
    It closes all connections in the pool and cleans up resources.
    """
    global _connection_pool
    
    if _connection_pool is not None:
        logger.info("Closing database connection pool")
        _connection_pool.closeall()  # Close all connections in the pool
        _connection_pool = None
        logger.info("Database connection pool closed")


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Get a database connection from the pool.
    
    This is a context manager - use it with 'with' statement.
    The connection is automatically returned to the pool when done.
    
    Example:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            result = cursor.fetchall()
        # Connection automatically returned to pool here
    
    Why context manager?
    - Ensures connection is always returned to pool (even if error occurs)
    - Cleaner code (no need to remember to return connection)
    - Exception-safe (connection returned even if exception raised)
    
    Yields:
        A database connection from the pool
    
    Raises:
        RuntimeError: If pool is not initialized
        pool.PoolError: If no connections available (pool exhausted)
    """
    global _connection_pool
    
    if _connection_pool is None:
        raise RuntimeError("Connection pool not initialized. Call initialize_pool() first.")
    
    # Get a connection from the pool
    # This might wait if all connections are in use
    # If pool is exhausted and timeout expires, this raises PoolError
    conn = None
    try:
        conn = _connection_pool.getconn()  # Get connection from pool
        logger.debug("Got connection from pool")
        
        # Yield the connection - this is where your code uses it
        # After the 'with' block, execution continues here
        yield conn
        
        # Check if transaction is still open (not committed or rolled back)
        # Service functions may commit/rollback themselves, so we check first
        # This prevents trying to commit an already-committed transaction
        if conn.status == extensions.STATUS_IN_TRANSACTION:
            # Transaction is still open - commit it
            # This handles cases where service function didn't commit
            conn.commit()
            logger.debug("Committed transaction, returning connection to pool")
        else:
            # Transaction already committed or rolled back by service function
            # This is fine - service functions handle their own transactions
            logger.debug("Transaction already handled by service, returning connection to pool")
    except pool.PoolError as e:
        # Pool is exhausted - no connections available
        # This is a critical error - we can't serve requests
        DB_CONNECTION_ERRORS_TOTAL.inc()
        logger.error(f"Failed to get connection from pool: {e}")
        raise
        
    except Exception as e:
        # If an error occurred, rollback any changes
        if conn:
            conn.rollback()
            logger.debug("Rolled back transaction due to error")
        raise  # Re-raise the exception
        
    finally:
        # Always return connection to pool, even if error occurred
        # This is why we use a context manager - ensures cleanup happens
        if conn:
            _connection_pool.putconn(conn)  # Return connection to pool
            logger.debug("Returned connection to pool")


def get_pool_status():
    """
    Get status information about the connection pool.
    
    This is useful for monitoring and debugging.
    Shows how many connections are in use, available, etc.
    
    Returns:
        Dictionary with pool status information
    """
    global _connection_pool
    
    if _connection_pool is None:
        return {
            "initialized": False,
            "min_connections": settings.db.min_connections,
            "max_connections": settings.db.max_connections,
        }
    
    # Get pool statistics
    # These are internal attributes of the pool object
    # _used is a dict of in-use connections; count it with len()
    used_connections = len(_connection_pool._used)
    return {
        "initialized": True,
        "min_connections": settings.db.min_connections,
        "max_connections": settings.db.max_connections,
        "current_connections": used_connections,  # How many are in use
        "available_connections": _connection_pool.maxconn - used_connections,  # How many available
    }
