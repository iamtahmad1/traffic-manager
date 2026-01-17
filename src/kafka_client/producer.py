# src/kafka_client/producer.py
# This file handles publishing events to Kafka
# Kafka is a message queue system - think of it like a post office
# We send messages (events) to Kafka, and other services can read them later

import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

# Import Kafka client from kafka-python package
# This is the standard, simple import
from kafka import KafkaProducer
from kafka.errors import KafkaError

from logger import get_logger
from config import settings
from metrics import KAFKA_EVENTS_PUBLISHED_TOTAL, KAFKA_EVENTS_FAILED_TOTAL
from tracking.correlation import get_correlation_id

logger = get_logger(__name__)

# Kafka topic name where we publish route change events
# We get this from config, but also export it as a constant for convenience
ROUTE_EVENTS_TOPIC = settings.kafka.route_events_topic

# Global Kafka producer instance (singleton pattern)
# We create one producer and reuse it for all events
# This is more efficient than creating a new producer for each event
_kafka_producer: Optional[KafkaProducer] = None


def get_kafka_producer() -> KafkaProducer:
    """
    Get or create a Kafka producer client.
    
    This function implements the singleton pattern - it creates one producer
    and reuses it for all subsequent calls. This is more efficient than
    creating a new producer for each event.
    
    A producer is like a sender - it sends messages (events) to Kafka.
    We configure it to be reliable and idempotent for production use.
    
    Producer Configuration Explained:
    - bootstrap_servers: List of Kafka broker addresses (for redundancy)
    - value_serializer: Converts Python objects to bytes (JSON format)
    - acks='all': Wait for all replicas to confirm (most reliable, but slower)
    - retries: Automatically retry if sending fails (handles transient errors)
    - idempotent=True: Prevents duplicate messages if we retry (exactly-once semantics, best effort)
    - request_timeout_ms: How long to wait for Kafka to respond
    
    Returns:
        A KafkaProducer instance ready to send messages
    
    Note:
        The producer is thread-safe and can be used from multiple threads.
        It manages connections internally and handles reconnection automatically.
    """
    global _kafka_producer
    
    # If producer already exists, return it (singleton pattern)
    # This ensures we only have one producer for the entire application
    if _kafka_producer is not None:
        return _kafka_producer
    
    # Parse bootstrap servers from config
    # Config format: "host1:port1,host2:port2" (comma-separated)
    # We split by comma to get list of broker addresses
    bootstrap_servers = settings.kafka.bootstrap_servers.split(',')
    
    logger.info(
        f"Creating Kafka producer: "
        f"bootstrap_servers={bootstrap_servers}, "
        f"topic={settings.kafka.route_events_topic}, "
        f"acks={settings.kafka.acks}, "
        f"idempotent={settings.kafka.idempotent}"
    )
    
    try:
        # Create the producer with production-ready settings
        # These settings ensure reliability and prevent data loss
        _kafka_producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,  # List of Kafka broker addresses
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            # value_serializer converts Python dictionaries to JSON strings, then to bytes
            # This is how we send structured data over the network
            
            acks=settings.kafka.acks,  # Wait for all replicas to acknowledge
            # acks='all' means: wait for all in-sync replicas to confirm they received the message
            # This is the most reliable but slowest option
            # Alternatives: '0' (fire and forget), '1' (leader only)
            
            retries=settings.kafka.retries,  # Retry up to N times if sending fails
            # Retries handle transient failures like network hiccups
            # The producer automatically retries with exponential backoff
            
            enable_idempotence=settings.kafka.idempotent,  # Prevent duplicate messages
            # enable_idempotence=True ensures that if we retry, we don't send duplicate messages
            # This gives us "exactly-once" semantics (best effort)
            # Requires acks='all' and retries > 0
            
            request_timeout_ms=settings.kafka.request_timeout_ms,  # Request timeout
            # How long to wait for Kafka to respond before giving up
        )
        
        logger.info("Kafka producer created successfully")
        
    except Exception as e:
        logger.error(f"Failed to create Kafka producer: {e}")
        # In production, you might want to raise an error here
        # For now, we'll return None and handle it gracefully in calling code
        raise
    
    return _kafka_producer


def close_kafka_producer():
    """
    Close the Kafka producer and clean up resources.
    
    This should be called when the application shuts down.
    It flushes any pending messages and closes connections.
    """
    global _kafka_producer
    
    if _kafka_producer is not None:
        logger.info("Closing Kafka producer")
        _kafka_producer.flush(timeout=10)  # Wait up to 10 seconds for pending messages
        _kafka_producer.close()  # Close all connections
        _kafka_producer = None
        logger.info("Kafka producer closed")


def publish_route_event(
    producer: Optional[KafkaProducer],
    action: str,
    tenant: str,
    service: str,
    env: str,
    version: str,
    url: str
):
    """
    Publish a route change event to Kafka.
    
    This function creates an event message and sends it to Kafka.
    Other services can listen to these events and react (like invalidating cache).
    
    Args:
        producer: The Kafka producer to use
        action: What happened - "created", "activated", or "deactivated"
        tenant: Tenant name
        service: Service name
        env: Environment name
        version: Version name
        url: The endpoint URL
    
    Returns:
        True if published successfully, False otherwise
    """
    # Create a unique ID for this event
    # UUID (Universally Unique Identifier) ensures every event has a unique ID
    event_id = str(uuid.uuid4())
    
    # Get current timestamp in RFC3339 format (standard format for timestamps)
    # Example: "2024-01-14T17:30:00Z"
    occurred_at = datetime.utcnow().isoformat() + "Z"
    
    # Get correlation ID from current request context
    # This allows tracing events back to the original request
    correlation_id = get_correlation_id()
    
    # Build the event payload (the data we're sending)
    # This matches the format described in write_path.md
    event = {
        "event_id": event_id,
        "event_type": "route_changed",
        "action": action,
        "tenant": tenant,
        "service": service,
        "env": env,
        "version": version,
        "url": url,
        "occurred_at": occurred_at,
        "correlation_id": correlation_id  # Add correlation ID for end-to-end tracking
    }
    
    # Create partition key from route identifiers
    # Partition key ensures all events for the same route go to the same partition
    # This guarantees ordering - events for the same route are processed in order
    partition_key = f"{tenant}:{service}:{env}:{version}".encode('utf-8')
    
    if producer is None:
        logger.warning("Kafka producer is None, cannot publish event")
        return False
    
    try:
        logger.info(f"Publishing route event: {action} for {tenant}/{service}/{env}/{version}")
        
        # Send the event to Kafka
        # send() is asynchronous - it returns immediately, doesn't wait for confirmation
        # This is good for performance - we don't block waiting for Kafka
        # We use get() to wait for the result (or timeout)
        future = producer.send(
            settings.kafka.route_events_topic,  # Topic name from config
            value=event,  # The event data (JSON)
            key=partition_key  # Partition key for ordering
        )
        
        # Wait for the message to be sent (with timeout from config)
        # This ensures we know if it succeeded or failed
        # The timeout is in milliseconds, so we convert to seconds
        timeout_seconds = settings.kafka.request_timeout_ms / 1000
        record_metadata = future.get(timeout=timeout_seconds)
        
        logger.info(
            f"Route event published successfully: "
            f"topic={record_metadata.topic}, "
            f"partition={record_metadata.partition}, "
            f"offset={record_metadata.offset}"
        )
        
        # Track successful event publication
        # This metric helps us monitor Kafka health
        KAFKA_EVENTS_PUBLISHED_TOTAL.labels(action=action).inc()
        
        return True
        
    except KafkaError as e:
        # If Kafka fails, log the error but don't crash
        # The write path document says: "Kafka failure does NOT fail write request"
        # The database is the source of truth, Kafka is just for side effects
        logger.error(f"Failed to publish route event to Kafka: {e}")
        
        # Track failed event publication
        # This metric helps us detect Kafka issues
        KAFKA_EVENTS_FAILED_TOTAL.labels(action=action).inc()
        
        return False
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error publishing route event: {e}")
        
        # Track failed event publication
        KAFKA_EVENTS_FAILED_TOTAL.labels(action=action).inc()
        
        return False
