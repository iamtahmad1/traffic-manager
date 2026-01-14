# src/cache/redis_client.py
# This file handles connecting to Redis, which is our cache
# A cache is like a fast memory that stores frequently used data
# Think of it like a notepad where you write down things you look up often
# Instead of asking the database every time, we check the cache first (much faster!)

# Import our centralized logging configuration
from logger import get_logger
# Import centralized configuration
from config import settings
# redis is a library that lets Python talk to Redis
import redis

# Create a logger for this file
logger = get_logger(__name__)

# Global Redis connection pool
# Connection pooling for Redis works similarly to database pooling
# It reuses connections instead of creating new ones each time
# This improves performance and reduces connection overhead
_redis_pool: redis.ConnectionPool = None
_redis_client: redis.Redis = None


def get_redis_client():
    """
    Get or create a Redis client with connection pooling.
    
    This function uses a connection pool to reuse Redis connections.
    Connection pooling is a production pattern that:
    - Reuses connections (faster than creating new ones)
    - Manages connection limits
    - Handles connection failures gracefully
    - Improves performance under load
    
    The first call creates the pool and client.
    Subsequent calls return the same client (singleton pattern).
    
    Returns:
        A Redis client object that we can use to interact with Redis
    
    Note:
        The client uses connection pooling internally, so you don't need to
        manage connections yourself - just use the client methods.
    """
    global _redis_pool, _redis_client
    
    # If client already exists, return it (singleton pattern)
    # This ensures we only have one Redis client for the entire application
    if _redis_client is not None:
        return _redis_client
    
    logger.info(
        f"Creating Redis client with connection pooling: "
        f"host={settings.redis.host}, port={settings.redis.port}, db={settings.redis.db}"
    )
    
    # Create a connection pool for Redis
    # The pool manages a collection of reusable connections
    # max_connections limits how many connections we can have open at once
    _redis_pool = redis.ConnectionPool(
        host=settings.redis.host,           # Redis server address (from config)
        port=settings.redis.port,           # Redis server port (from config)
        db=settings.redis.db,               # Redis database number (from config)
        max_connections=settings.redis.max_connections,  # Maximum connections in pool
        socket_timeout=settings.redis.socket_timeout,    # Connection timeout
        decode_responses=True  # Return strings instead of bytes
        # decode_responses=True means Redis returns normal strings (like 'hello')
        # Without this, Redis returns bytes (like b'hello'), which is harder to work with
    )
    
    # Create Redis client that uses the connection pool
    # The client automatically gets connections from the pool when needed
    # and returns them when done
    _redis_client = redis.Redis(connection_pool=_redis_pool)
    
    # Test the connection to make sure Redis is accessible
    try:
        _redis_client.ping()  # PING is a simple Redis command to test connectivity
        logger.info("Redis connection established and tested successfully")
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        # In production, you might want to raise an error here
        # For now, we'll continue - the application can work without Redis (falls back to DB)
    
    return _redis_client


def close_redis_client():
    """
    Close the Redis connection pool.
    
    This should be called when the application shuts down.
    It closes all connections in the pool and cleans up resources.
    """
    global _redis_pool, _redis_client
    
    if _redis_pool is not None:
        logger.info("Closing Redis connection pool")
        _redis_pool.disconnect()  # Close all connections in the pool
        _redis_pool = None
        _redis_client = None
        logger.info("Redis connection pool closed")