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
from mongodb_client import get_mongodb_client, close_mongodb_client, insert_audit_event
from tracking.correlation import correlation_context

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
    
    This function processes route change events from Kafka and stores them in MongoDB
    for audit trail and compliance purposes. It's called automatically by the Kafka
    consumer whenever a route change event is received.
    
    What this function does:
    1. Validates the event has all required fields (action, tenant, service, env, version)
    2. Calls insert_audit_event() to store the event in MongoDB
    3. Logs success or failure for monitoring
    
    MongoDB audit store supports queries like:
    - Who changed this route? (changed_by field)
    - When did it change? (occurred_at timestamp)
    - What was the previous value? (previous_url, previous_state)
    - Can we see history for last 30/90 days? (indexed by occurred_at)
    - Can we debug an outage caused by a config change? (full event context)
    
    Args:
        event: Dictionary containing route change event from Kafka
            Required fields: action, tenant, service, env, version
            Optional fields: event_id, url, occurred_at, changed_by, etc.
    """
    # Extract required fields from the event
    # These fields identify which route was changed
    action = event.get("action")
    tenant = event.get("tenant")
    service = event.get("service")
    env = event.get("env")
    version = event.get("version")

    # Validate that all required fields are present
    # If any are missing, we can't create a valid audit record
    if not all([action, tenant, service, env, version]):
        logger.warning(
            f"Invalid event for audit log - missing required fields: {event}. "
            f"Required: action, tenant, service, env, version"
        )
        return

    try:
        # Insert audit event into MongoDB
        # The insert_audit_event function:
        # - Builds a structured document with all event data
        # - Handles timestamp parsing and conversion
        # - Inserts into the route_events collection
        # - Returns True on success, False on failure
        success = insert_audit_event(event)
        
        if success:
            # Log successful insertion for monitoring and debugging
            logger.info(
                f"✓ Audit log saved to MongoDB: {tenant}/{service}/{env}/{version} "
                f"action={action}, event_id={event.get('event_id')}"
            )
        else:
            # Log failure - this is important for debugging
            # The insert_audit_event function already logged the specific error
            logger.error(
                f"✗ Failed to save audit log to MongoDB: {tenant}/{service}/{env}/{version} "
                f"action={action}, event_id={event.get('event_id')}. "
                f"Check MongoDB connection and permissions."
            )
    except Exception as e:
        # Catch any unexpected errors during insertion
        # This should rarely happen since insert_audit_event handles most errors
        logger.error(
            f"✗ Audit log insert failed with exception: {e}. "
            f"Event: {event}",
            exc_info=True  # Include full stack trace for debugging
        )


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
    
    # Cache warming needs database
    if consumer_type == "cache_warming":
        logger.info("Initializing database connection pool...")
        initialize_pool()
        logger.info("✓ Database connection pool initialized")
    
    # Audit log needs MongoDB
    if consumer_type == "audit_log":
        logger.info("Initializing MongoDB client for audit logging...")
        get_mongodb_client()  # Initialize MongoDB client
        logger.info("✓ MongoDB client initialized")
    
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
        # This loop continuously polls Kafka for new messages
        # When messages arrive, they are processed by the appropriate handler
        message_count = 0
        while not shutdown_requested:
            # Poll Kafka for new messages
            # timeout_ms: How long to wait for messages (returns empty if no messages)
            records = consumer.poll(timeout_ms=settings.kafka.consumer_poll_timeout_ms)
            
            # Process all messages received in this poll
            for topic_partition, messages in records.items():
                for message in messages:
                    message_count += 1
                    try:
                        # Extract event data from Kafka message
                        # message.value is already deserialized from JSON (see _build_consumer)
                        event = message.value
                        
                        # Extract correlation ID from event (if present)
                        # This allows tracing consumer processing back to the original request
                        correlation_id = event.get('correlation_id')
                        
                        # Set correlation ID in context for this event processing
                        # This ensures all logs during event processing include the correlation ID
                        with correlation_context(correlation_id):
                            # Log that we received an event (helpful for debugging)
                            if consumer_type == "audit_log":
                                logger.debug(
                                    f"Received audit event #{message_count}: "
                                    f"action={event.get('action')}, "
                                    f"route={event.get('tenant')}/{event.get('service')}/"
                                    f"{event.get('env')}/{event.get('version')}, "
                                    f"event_id={event.get('event_id')}, "
                                    f"correlation_id={correlation_id or 'N/A'}"
                                )
                            
                            # Call the appropriate handler for this consumer type
                            # Each handler processes the event differently:
                            # - cache_invalidation: Deletes Redis cache keys
                            # - cache_warming: Pre-loads cache from database
                            # - audit_log: Stores event in MongoDB
                            handlers[consumer_type](event)
                    except Exception as e:
                        # Log errors but don't crash the consumer
                        # This allows the consumer to continue processing other messages
                        logger.error(
                            f"Error processing message #{message_count} in {consumer_type} consumer: {e}. "
                            f"Message: {message.value if hasattr(message, 'value') else 'N/A'}",
                            exc_info=True  # Include full stack trace for debugging
                        )
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
        if consumer_type == "cache_warming":
            close_pool()
            logger.info("✓ Database connection pool closed")
        
        # Close MongoDB client if it was initialized
        if consumer_type == "audit_log":
            close_mongodb_client()
            logger.info("✓ MongoDB client closed")
        
        # Close Redis client if it was initialized
        if consumer_type == "cache_invalidation":
            close_redis_client()
            logger.info("✓ Redis client closed")
        
        logger.info("Consumer shutdown complete")
