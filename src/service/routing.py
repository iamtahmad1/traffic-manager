# src/service/routing.py
# This file contains the core logic for finding (resolving) endpoint URLs
# An endpoint is like an address - it tells us where to send requests

import time  # We use this to measure how long things take
# Import our centralized logging configuration
from logger import get_logger
from psycopg2.extras import RealDictCursor  # A special cursor that returns results as dictionaries
from cache.redis_client import get_redis_client  # Function to get Redis connection
from metrics import (  # Import our metrics (counters and timers)
    RESOLVE_REQUESTS_TOTAL,
    CACHE_HIT_TOTAL,
    CACHE_MISS_TOTAL,
    NEGATIVE_CACHE_HIT_TOTAL,
    RESOLVE_LATENCY_SECONDS,
    DB_QUERIES_TOTAL,  # Track database queries
)

# Create a logger for this file
logger = get_logger(__name__)

# This is a custom exception class
# Exceptions are Python's way of saying "something went wrong"
# We create a custom one so we can catch it specifically
# It's like creating a special type of error message
class RouteNotFoundError(Exception):
    # 'pass' means "do nothing" - we're just creating the class
    # It inherits from Exception, so it works like any other error
    pass


# This is a SQL query - a question we ask the database
# SQL (Structured Query Language) is how we talk to databases
# This query finds a URL by joining multiple tables together
SQL_RESOLVE_ENDPOINT = """
SELECT e.url
FROM tenants t
JOIN services s ON s.tenant_id = t.id
JOIN environments env ON env.service_id = s.id
JOIN endpoints e ON e.environment_id = env.id
WHERE t.name = %(tenant)s
  AND s.name = %(service)s
  AND env.name = %(env)s
  AND e.version = %(version)s
  AND e.is_active = true
LIMIT 1;
"""
# What this query does:
# - SELECT e.url: Get the URL from the endpoints table
# - FROM tenants t: Start from the tenants table (we call it 't')
# - JOIN: Connect related tables together (like linking spreadsheets)
# - WHERE: Filter to find the exact match we want
# - %(tenant)s: This is a placeholder - we'll fill it in with actual values
# - LIMIT 1: Only get one result (even if there are multiple matches)

# Import centralized configuration
from config import settings

# Constants - values that don't change
# These are like settings we use throughout the code
NEGATIVE_CACHE_VALUE = "__NOT_FOUND__"  # Special value we store when route doesn't exist

# Cache TTL values from configuration
# TTL = Time To Live (how long to keep in cache, in seconds)
# We get these from centralized config instead of hardcoding
POSITIVE_CACHE_TTL = settings.app.positive_cache_ttl  # How long to cache existing routes
NEGATIVE_CACHE_TTL = settings.app.negative_cache_ttl  # How long to cache "not found" results (shorter)

def _cache_key(tenant, service, env, version):
    """
    Helper function to create a unique key for the cache.
    
    A cache key is like a label on a box - it helps us find stored data quickly.
    We combine all the parameters into one string.
    
    Example: "route:team-a:payments:prod:v2"
    """
    # f-string lets us insert variables into a string
    # The 'f' before the quotes makes it a formatted string
    return f"route:{tenant}:{service}:{env}:{version}"

def resolve_endpoint(conn, tenant, service, env, version):
    """
    This is the main function that finds an endpoint URL.
    
    It uses a two-step strategy:
    1. First, check the cache (Redis) - very fast!
    2. If not in cache, ask the database - slower but more reliable
    
    Args:
        conn: Database connection object
        tenant: Which team/organization (e.g., "team-a")
        service: Which service (e.g., "payments")
        env: Which environment (e.g., "prod" for production)
        version: Which version (e.g., "v2")
    
    Returns:
        The URL string for the endpoint
    
    Raises:
        RouteNotFoundError: If the route doesn't exist
    """
    # Record the start time so we can measure how long this takes
    # time.time() returns the current time as a number (seconds since 1970)
    start_time = time.time()
    
    # Create a unique key for this request
    # This key will be used to store/retrieve data from the cache
    cache_key = _cache_key(tenant, service, env, version)
    
    logger.info(f"Resolving endpoint: {tenant}/{service}/{env}/{version}")
    
    # Increment the counter - track that we got a request
    # .inc() means "increment" (add 1 to the counter)
    RESOLVE_REQUESTS_TOTAL.inc()

    # Step 1: Try Redis cache first (this is fast!)
    # We use try/except because Redis might be down or have errors
    # If Redis fails, we don't want the whole app to crash
    try:
        # Get a Redis client (like getting a remote control for Redis)
        redis_client = get_redis_client()
        
        # Try to get the URL from cache
        # .get() asks Redis: "Do you have data for this key?"
        # If yes, it returns the value. If no, it returns None.
        cached_url = redis_client.get(cache_key)

        if cached_url:
            # We found something in the cache!
            
            # Check if it's a negative cache entry (meaning "not found")
            # Negative caching: we remember when something doesn't exist
            # This prevents us from asking the database repeatedly for non-existent routes
            if cached_url == NEGATIVE_CACHE_VALUE:
                logger.info("Negative cache hit")
                # Track that we found a "not found" in cache
                NEGATIVE_CACHE_HIT_TOTAL.inc()
                
                # Calculate how long this took
                duration = time.time() - start_time
                # Record the timing in our metrics
                RESOLVE_LATENCY_SECONDS.observe(duration)
                
                # Raise an error - the route doesn't exist
                raise RouteNotFoundError(
                    f"No active route found for "
                    f"{tenant}/{service}/{env}/{version}"
                )
            
            # It's a real URL! We found it in cache (cache hit)
            logger.info("Cache hit")
            CACHE_HIT_TOTAL.inc()
            
            # Calculate how long this took
            duration = time.time() - start_time
            # Record the timing
            RESOLVE_LATENCY_SECONDS.observe(duration)
            
            # Return the URL immediately - we're done!
            return cached_url
        
        # Cache miss - the data wasn't in Redis
        logger.debug("Cache miss")
        CACHE_MISS_TOTAL.inc()

    except RouteNotFoundError:
        # If we raised RouteNotFoundError above, re-raise it
        # This lets the calling code know the route wasn't found
        raise
    except Exception as e:
        # If Redis had any other error (connection failed, etc.)
        # Log it but don't crash - we'll try the database instead
        logger.warning(f"Redis error: {e}")
        # Redis failure must NOT break DB path
        # This means: if Redis is broken, we can still use the database
        pass  # 'pass' means "do nothing, continue with the code"

    # Step 2: Cache miss or Redis error - query the database
    logger.info("Querying database")
    
    # Track that we're executing a database query
    # This metric helps us monitor database load
    DB_QUERIES_TOTAL.inc()
    
    # Create a cursor - this is like a pointer that lets us execute queries
    # RealDictCursor makes results come back as dictionaries (easier to work with)
    # 'with' statement automatically closes the cursor when done (good practice!)
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        # Execute the SQL query we defined earlier
        # We pass the parameters as a dictionary
        cursor.execute(
            SQL_RESOLVE_ENDPOINT,
            {
                "tenant": tenant,
                "service": service,
                "env": env,
                "version": version,
            },
        )
        
        # fetchone() gets one row from the results
        # If there are results, row will be a dictionary like {"url": "https://..."}
        # If no results, row will be None
        row = cursor.fetchone()

        if row is None:
            # The route doesn't exist in the database
            logger.warning("Route not found in database")
            
            # Cache the negative result (remember that it doesn't exist)
            # This is called "negative caching"
            # We store a special value for a short time (10 seconds)
            # So if someone asks for the same route again soon, we don't query the DB
            try:
                # setex = "set with expiration"
                # It stores the value for a specific amount of time
                redis_client.setex(cache_key, NEGATIVE_CACHE_TTL, NEGATIVE_CACHE_VALUE)
                logger.debug("Cached negative result")
            except Exception as e:
                # If caching fails, log it but don't crash
                logger.warning(f"Failed to cache negative result: {e}")
            
            # Record how long this took
            duration = time.time() - start_time
            RESOLVE_LATENCY_SECONDS.observe(duration)
            
            # Raise an error - the route doesn't exist
            raise RouteNotFoundError(
                f"No active route found for "
                f"{tenant}/{service}/{env}/{version}"
            )
        
        # We found it! Extract the URL from the database result
        # row is a dictionary, so we use ["url"] to get the URL value
        url = row["url"]
    
    # Step 3: Store the result in cache for next time
    # This way, future requests will be faster (cache hit instead of database query)
    try:
        # Store the URL in Redis for 60 seconds
        # After 60 seconds, Redis will automatically delete it
        redis_client.setex(cache_key, POSITIVE_CACHE_TTL, url)
        logger.debug("Cached endpoint")
    except Exception as e:
        # If caching fails, log it but don't crash
        # The request still succeeded, we just couldn't cache it
        logger.warning(f"Failed to cache: {e}")

    # Record how long the entire operation took
    duration = time.time() - start_time
    RESOLVE_LATENCY_SECONDS.observe(duration)
    
    # Return the URL we found
    return url
