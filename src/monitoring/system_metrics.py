# src/monitoring/system_metrics.py
# This file collects system-level metrics for monitoring
# System metrics track the health and status of infrastructure components
# These are different from business metrics (like request counts)

import time
from prometheus_client import Gauge
from logger import get_logger

logger = get_logger(__name__)

# Gauge metrics track a value that can go up or down
# Unlike counters (which only go up), gauges can increase or decrease
# Examples: temperature, memory usage, number of active connections

# Database connection pool metrics
# These track the state of our connection pool
DB_POOL_SIZE = Gauge(
    "db_pool_size",
    "Current number of connections in the database pool",
)

DB_POOL_AVAILABLE = Gauge(
    "db_pool_available",
    "Number of available connections in the database pool",
)

DB_POOL_IN_USE = Gauge(
    "db_pool_in_use",
    "Number of connections currently in use",
)

# Cache metrics
# These track Redis cache status
CACHE_CONNECTED = Gauge(
    "cache_connected",
    "Whether Redis cache is connected (1) or not (0)",
)

# Kafka metrics
# These track Kafka producer status
KAFKA_PRODUCER_READY = Gauge(
    "kafka_producer_ready",
    "Whether Kafka producer is ready (1) or not (0)",
)

# Application uptime
# Tracks how long the application has been running
APPLICATION_UPTIME_SECONDS = Gauge(
    "application_uptime_seconds",
    "Number of seconds the application has been running",
)

# Track when the application started
# This is used to calculate uptime
_start_time = time.time()


def collect_system_metrics():
    """
    Collect and update system-level metrics.
    
    This function should be called periodically (e.g., every 10-30 seconds)
    to update system metrics. These metrics track infrastructure health,
    not business metrics (those are updated automatically).
    
    System metrics include:
    - Database connection pool status
    - Cache connectivity
    - Kafka producer status
    - Application uptime
    
    In production, you might call this from a background thread or
    use a library that does it automatically.
    """
    try:
        # Update database pool metrics
        # These show the state of our connection pool
        from db.pool import get_pool_status
        pool_status = get_pool_status()
        
        if pool_status.get("initialized"):
            # Pool is initialized - update metrics
            DB_POOL_SIZE.set(pool_status.get("max_connections", 0))
            DB_POOL_AVAILABLE.set(pool_status.get("available_connections", 0))
            DB_POOL_IN_USE.set(pool_status.get("current_connections", 0))
        else:
            # Pool not initialized - set to 0
            DB_POOL_SIZE.set(0)
            DB_POOL_AVAILABLE.set(0)
            DB_POOL_IN_USE.set(0)
        
        # Update cache connectivity
        # Check if Redis is accessible
        try:
            from cache import get_redis_client
            client = get_redis_client()
            client.ping()  # Test connection
            CACHE_CONNECTED.set(1)  # Connected
        except Exception:
            CACHE_CONNECTED.set(0)  # Not connected
        
        # Update Kafka producer status
        # Check if Kafka producer is ready
        try:
            from kafka_client import get_kafka_producer
            producer = get_kafka_producer()
            # Producer exists and is ready
            KAFKA_PRODUCER_READY.set(1)
        except Exception:
            KAFKA_PRODUCER_READY.set(0)
        
        # Update application uptime
        # Calculate how long the application has been running
        uptime = time.time() - _start_time
        APPLICATION_UPTIME_SECONDS.set(uptime)
        
        logger.debug("System metrics updated successfully")
        
    except Exception as e:
        # If collecting metrics fails, log it but don't crash
        # Monitoring should never break the application
        logger.warning(f"Error collecting system metrics: {e}")


def start_metrics_collector(interval=30):
    """
    Start a background thread that periodically collects system metrics.
    
    This function starts a thread that calls collect_system_metrics()
    every 'interval' seconds. This keeps system metrics up to date.
    
    Args:
        interval: How often to collect metrics (in seconds)
                 Default: 30 seconds
    
    Note:
        In production, you might use a more sophisticated approach
        like a scheduled task or a monitoring agent.
    """
    import threading
    
    def collect_loop():
        """Background loop that collects metrics periodically."""
        while True:
            try:
                collect_system_metrics()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"Error in metrics collector loop: {e}")
                time.sleep(interval)  # Continue even if error
    
    # Start the background thread
    # daemon=True means the thread will stop when main program exits
    collector_thread = threading.Thread(target=collect_loop, daemon=True)
    collector_thread.start()
    
    logger.info(f"System metrics collector started (interval={interval}s)")
