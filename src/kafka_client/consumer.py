# src/kafka_client/consumer.py
# This file provides simple Kafka consumers for common use cases
# Each consumer reads route events and performs a specific action

import json
import signal
from typing import Dict, Any, Callable

from kafka import KafkaConsumer

from logger import get_logger
from config import settings
from cache import get_redis_client, close_redis_client
from db.pool import get_connection, initialize_pool, close_pool
from service.routing import resolve_endpoint, RouteNotFoundError

logger = get_logger(__name__)

# Supported consumer types (simple, scalable pattern)
CONSUMER_TYPES = {
    "cache_invalidation",
    "cache_warming",
    "audit_log",
}


def _consumer_group_id(consumer_type: str) -> str:
    """
    Build a consumer group id using a shared prefix.
    This allows each use case to scale independently.
    """
    return f"{settings.kafka.consumer_group_prefix}-{consumer_type}"


def _build_consumer(consumer_type: str) -> KafkaConsumer:
    """
    Create a Kafka consumer with config from settings.
    """
    return KafkaConsumer(
        settings.kafka.route_events_topic,
        bootstrap_servers=settings.kafka.bootstrap_servers.split(","),
        group_id=_consumer_group_id(consumer_type),
        auto_offset_reset=settings.kafka.consumer_auto_offset_reset,
        enable_auto_commit=settings.kafka.consumer_enable_auto_commit,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )


def _cache_key(tenant: str, service: str, env: str, version: str) -> str:
    """
    Build the Redis cache key for a route.
    This matches the read-path cache key format.
    """
    return f"route:{tenant}:{service}:{env}:{version}"


def _handle_cache_invalidation(event: Dict[str, Any]) -> None:
    """
    Cache Invalidation Consumer (MOST IMPORTANT)
    Removes cached data when a route changes.
    """
    tenant = event.get("tenant")
    service = event.get("service")
    env = event.get("env")
    version = event.get("version")

    if not all([tenant, service, env, version]):
        logger.warning(f"Invalid event for cache invalidation: {event}")
        return

    client = get_redis_client()
    key = _cache_key(tenant, service, env, version)
    client.delete(key)
    logger.info(f"Cache invalidated: {key}")


def _handle_cache_warming(event: Dict[str, Any]) -> None:
    """
    Cache Warming Consumer (VERY COMMON)
    Pre-loads cache after a route change so reads are fast.
    """
    tenant = event.get("tenant")
    service = event.get("service")
    env = event.get("env")
    version = event.get("version")

    if not all([tenant, service, env, version]):
        logger.warning(f"Invalid event for cache warming: {event}")
        return

    # Resolve from DB and store in cache by reusing the read-path logic
    try:
        with get_connection() as conn:
            resolve_endpoint(conn, tenant, service, env, version)
            logger.info(
                f"Cache warmed: {tenant}/{service}/{env}/{version}"
            )
    except RouteNotFoundError:
        # If the route doesn't exist, we don't warm cache
        logger.info(
            f"Cache warming skipped (route not found): "
            f"{tenant}/{service}/{env}/{version}"
        )
    except Exception as e:
        logger.warning(f"Cache warming failed: {e}")


def _handle_audit_log(event: Dict[str, Any]) -> None:
    """
    Audit / Change Log Consumer (EXTREMELY COMMON)
    Stores events in the database for traceability.
    """
    action = event.get("action")
    tenant = event.get("tenant")
    service = event.get("service")
    env = event.get("env")
    version = event.get("version")

    if not all([action, tenant, service, env, version]):
        logger.warning(f"Invalid event for audit log: {event}")
        return

    sql = """
    INSERT INTO route_events (tenant, service, env, version, action)
    VALUES (%(tenant)s, %(service)s, %(env)s, %(version)s, %(action)s);
    """

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql,
                    {
                        "tenant": tenant,
                        "service": service,
                        "env": env,
                        "version": version,
                        "action": action,
                    },
                )
        logger.info(
            f"Audit log saved: {tenant}/{service}/{env}/{version} action={action}"
        )
    except Exception as e:
        logger.warning(f"Audit log insert failed: {e}")


def run_consumer(consumer_type: str) -> None:
    """
    Run a consumer for one specific use case.

    This function:
    1. Initializes required services (DB pool, Redis client) based on consumer type
    2. Sets up signal handlers for graceful shutdown
    3. Starts consuming messages from Kafka
    4. Cleans up resources on shutdown

    Usage examples:
    - run_consumer("cache_invalidation")
    - run_consumer("cache_warming")
    - run_consumer("audit_log")
    """
    if consumer_type not in CONSUMER_TYPES:
        raise ValueError(
            f"Unknown consumer type: {consumer_type}. "
            f"Valid types: {sorted(CONSUMER_TYPES)}"
        )

    # Initialize services based on consumer type
    logger.info(f"Initializing services for consumer: {consumer_type}")
    
    # Cache invalidation needs Redis
    if consumer_type == "cache_invalidation":
        logger.info("Initializing Redis client for cache invalidation...")
        get_redis_client()  # Initialize Redis client
        logger.info("✓ Redis client initialized")
    
    # Cache warming and audit log need database
    if consumer_type in ["cache_warming", "audit_log"]:
        logger.info("Initializing database connection pool...")
        initialize_pool()
        logger.info("✓ Database connection pool initialized")
    
    # Set up signal handlers for graceful shutdown
    shutdown_requested = False
    
    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        shutdown_requested = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {
        "cache_invalidation": _handle_cache_invalidation,
        "cache_warming": _handle_cache_warming,
        "audit_log": _handle_audit_log,
    }

    consumer = None
    try:
        consumer = _build_consumer(consumer_type)
        logger.info(
            f"Starting Kafka consumer: type={consumer_type}, "
            f"group_id={_consumer_group_id(consumer_type)}"
        )

        # Main loop: read messages and process
        while not shutdown_requested:
            records = consumer.poll(timeout_ms=settings.kafka.consumer_poll_timeout_ms)
            for _, messages in records.items():
                for message in messages:
                    try:
                        event = message.value
                        handlers[consumer_type](event)
                    except Exception as e:
                        logger.warning(f"Consumer error: {e}")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error in consumer: {e}", exc_info=True)
        raise
    finally:
        # Cleanup: close consumer and services
        logger.info("Cleaning up resources...")
        if consumer is not None:
            consumer.close()
            logger.info("✓ Kafka consumer closed")
        
        # Close database pool if it was initialized
        if consumer_type in ["cache_warming", "audit_log"]:
            close_pool()
            logger.info("✓ Database connection pool closed")
        
        # Close Redis client if it was initialized
        if consumer_type == "cache_invalidation":
            close_redis_client()
            logger.info("✓ Redis client closed")
        
        logger.info("Consumer shutdown complete")
