# src/mongodb_client/client.py
# MongoDB client for audit store
# Handles connection management and audit event storage

from typing import Dict, Any, Optional
from datetime import datetime
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, PyMongoError

from logger import get_logger
from config import settings

logger = get_logger(__name__)

# Global MongoDB client instance (singleton pattern)
_mongodb_client: Optional[MongoClient] = None
_mongodb_db: Optional[Database] = None


def get_mongodb_client() -> MongoClient:
    """
    Get or create a MongoDB client instance.
    
    This function implements the singleton pattern - it creates one client
    and reuses it for all subsequent calls. This is more efficient than
    creating a new client for each operation.
    
    MongoDB Client Configuration:
    - Connection pooling: Automatically managed by pymongo
    - Authentication: Uses username/password from config
    - Timeouts: Configured for production reliability
    
    Returns:
        A MongoClient instance ready to use
    
    Raises:
        ConnectionFailure: If unable to connect to MongoDB
    """
    global _mongodb_client, _mongodb_db
    
    # If client already exists, return it (singleton pattern)
    if _mongodb_client is not None:
        return _mongodb_client
    
    # Build MongoDB connection URI
    # Format: mongodb://[username:password@]host[:port]/[database]?authSource=admin
    # When using root credentials (MONGO_INITDB_ROOT_USERNAME), we must authenticate
    # against the 'admin' database, not the target database
    if settings.mongodb.user and settings.mongodb.password:
        uri = (
            f"mongodb://{settings.mongodb.user}:{settings.mongodb.password}@"
            f"{settings.mongodb.host}:{settings.mongodb.port}/{settings.mongodb.name}"
            f"?authSource=admin"
        )
    else:
        # No authentication (for local development)
        uri = f"mongodb://{settings.mongodb.host}:{settings.mongodb.port}/{settings.mongodb.name}"
    
    logger.info(
        f"Connecting to MongoDB: host={settings.mongodb.host}, "
        f"port={settings.mongodb.port}, db={settings.mongodb.name}"
    )
    
    try:
        # Create MongoDB client with production-ready settings
        _mongodb_client = MongoClient(
            uri,
            connectTimeoutMS=settings.mongodb.connect_timeout_ms,
            serverSelectionTimeoutMS=settings.mongodb.server_selection_timeout_ms,
            # Connection pool settings (pymongo manages this automatically)
            maxPoolSize=50,  # Maximum connections in pool
            minPoolSize=2,  # Minimum connections to maintain
        )
        
        # Get database instance
        _mongodb_db = _mongodb_client[settings.mongodb.name]
        
        # Test connection by pinging the server
        _mongodb_client.admin.command('ping')
        
        # Create indexes for efficient querying
        _create_indexes(_mongodb_db)
        
        logger.info("MongoDB client connected successfully")
        
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        _mongodb_client = None
        _mongodb_db = None
        raise
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        _mongodb_client = None
        _mongodb_db = None
        raise
    
    return _mongodb_client


def _create_indexes(db: Database) -> None:
    """
    Create indexes on the audit collection for efficient querying.
    
    Indexes support common audit queries:
    - Who changed this route? (route fields)
    - When did it change? (occurred_at)
    - What was the previous value? (route + occurred_at for history)
    - History for last 30/90 days? (occurred_at)
    - Debug outages by config changes? (route + occurred_at + action)
    
    Args:
        db: MongoDB database instance
    """
    collection = db[settings.mongodb.audit_collection]
    
    try:
        # Compound index on route fields for route-specific queries
        # Supports: "Who changed this route?" and "What was the previous value?"
        collection.create_index([
            ("route.tenant", 1),
            ("route.service", 1),
            ("route.env", 1),
            ("route.version", 1),
            ("occurred_at", -1)  # Descending for recent-first queries
        ], name="route_occurred_at_idx")
        
        # Index on occurred_at for time-based queries
        # Supports: "History for last 30/90 days?"
        collection.create_index(
            [("occurred_at", -1)],
            name="occurred_at_idx"
        )
        
        # Index on action for filtering by action type
        # Supports: "Debug outages by config changes?" (filter by action)
        collection.create_index([
            ("action", 1),
            ("occurred_at", -1)
        ], name="action_occurred_at_idx")
        
        # Index on event_id for deduplication and lookups
        collection.create_index(
            [("event_id", 1)],
            name="event_id_idx",
            unique=True
        )
        
        logger.info("MongoDB indexes created successfully")
        
    except Exception as e:
        logger.warning(f"Failed to create MongoDB indexes (may already exist): {e}")


def get_audit_collection() -> Collection:
    """
    Get the MongoDB collection for storing audit events.
    
    This function returns the collection object that we use to store and query
    route change events. The collection name comes from settings (default: "route_events").
    
    How it works:
    1. Checks if MongoDB client is initialized
    2. If not, initializes it automatically (lazy initialization)
    3. Returns the collection object for the audit collection
    
    The collection is where all audit events are stored. You can use it to:
    - Insert new events: collection.insert_one(document)
    - Query events: collection.find(query)
    - Create indexes: collection.create_index(...)
    
    Returns:
        MongoDB Collection object for the audit events collection
    
    Raises:
        RuntimeError: If MongoDB client cannot be initialized
        ConnectionFailure: If unable to connect to MongoDB
    
    Example:
        collection = get_audit_collection()
        result = collection.insert_one({"event_id": "123", "action": "created"})
    """
    global _mongodb_db
    
    # If database instance doesn't exist, initialize the client
    # This is lazy initialization - we only connect when we need to
    if _mongodb_db is None:
        # This will create the client and database connection
        # It also creates indexes automatically on first connection
        get_mongodb_client()
    
    # Double-check that initialization succeeded
    if _mongodb_db is None:
        raise RuntimeError(
            "MongoDB client not initialized. "
            "Check MongoDB connection settings and ensure MongoDB is running."
        )
    
    # Return the collection object
    # The collection name comes from settings.mongodb.audit_collection
    # Default is "route_events"
    return _mongodb_db[settings.mongodb.audit_collection]


def insert_audit_event(event: Dict[str, Any]) -> bool:
    """
    Insert an audit event into MongoDB.
    
    This function is the main entry point for storing route change events in MongoDB.
    It's called by the Kafka consumer whenever a route change event is received.
    
    What this function does:
    1. Gets the MongoDB collection (route_events)
    2. Builds a structured document from the event data
    3. Parses and converts timestamps to proper datetime objects
    4. Inserts the document into MongoDB
    5. Returns True on success, False on failure
    
    The stored document supports audit queries like:
    - Who changed this route? (changed_by field, if available)
    - When did it change? (occurred_at timestamp)
    - What was the previous value? (previous_url, previous_state)
    - Can we see history? (indexed by occurred_at)
    - Can we debug outages? (full event context with action, route, timestamps)
    
    Args:
        event: Event dictionary from Kafka containing:
            - event_id: Unique event identifier (UUID string)
            - event_type: Type of event (e.g., "route_changed")
            - action: Action performed (created, activated, deactivated)
            - tenant, service, env, version: Route identifiers (required)
            - url: Current URL after the change
            - occurred_at: Timestamp when event occurred (ISO 8601 format)
            - Optional: previous_url, previous_state, changed_by, metadata
    
    Returns:
        True if inserted successfully, False otherwise (check logs for error details)
    
    Example:
        event = {
            "event_id": "123e4567-e89b-12d3-a456-426614174000",
            "action": "created",
            "tenant": "team-a",
            "service": "payments",
            "env": "prod",
            "version": "v2",
            "url": "https://payments.example.com/v2",
            "occurred_at": "2024-01-14T17:30:00Z"
        }
        success = insert_audit_event(event)  # Returns True if successful
    """
    try:
        # Get the MongoDB collection where we store audit events
        # This function handles connection initialization if needed
        collection = get_audit_collection()
        
        # Build audit document with structured data for efficient querying
        # We structure the data in a way that makes queries fast and intuitive
        audit_doc = {
            # Unique identifier for this event (from Kafka event)
            "event_id": event.get("event_id"),
            
            # Type of event (usually "route_changed")
            "event_type": event.get("event_type", "route_changed"),
            
            # What action was performed (created, activated, deactivated)
            "action": event.get("action"),
            
            # Route identifiers grouped together for easy querying
            # This structure allows queries like: route.tenant = "team-a"
            "route": {
                "tenant": event.get("tenant"),
                "service": event.get("service"),
                "env": event.get("env"),
                "version": event.get("version"),
            },
            
            # Current URL after the change
            "url": event.get("url"),
            
            # Previous values (if available in event)
            # These help answer "what was the previous value?" queries
            "previous_url": event.get("previous_url"),
            "previous_state": event.get("previous_state"),
            
            # Who made the change (if available in event)
            # This helps answer "who changed this route?" queries
            "changed_by": event.get("changed_by"),
            
            # Timestamps
            # occurred_at: When the change actually happened (from Kafka event)
            # processed_at: When we processed and stored it (now)
            "occurred_at": _parse_timestamp(event.get("occurred_at")),
            "processed_at": datetime.utcnow(),
            
            # Additional metadata for future extensibility
            # Can store any extra information that might be useful later
            "metadata": event.get("metadata", {}),
        }
        
        # Insert document into MongoDB
        # insert_one() is atomic - either fully succeeds or fully fails
        # Returns a result object with inserted_id if successful
        result = collection.insert_one(audit_doc)
        
        # Log successful insertion with key details
        # This helps with debugging and monitoring
        logger.info(
            f"✓ Audit event saved to MongoDB: event_id={audit_doc['event_id']}, "
            f"route={audit_doc['route']['tenant']}/{audit_doc['route']['service']}/"
            f"{audit_doc['route']['env']}/{audit_doc['route']['version']}, "
            f"action={audit_doc['action']}, inserted_id={result.inserted_id}"
        )
        
        return True
        
    except PyMongoError as e:
        # PyMongoError covers all MongoDB-specific errors
        # Examples: connection failures, write errors, authentication failures
        logger.error(
            f"✗ MongoDB error inserting audit event: {e}. "
            f"Event: {event}. "
            f"Check MongoDB connection, permissions, and collection access."
        )
        return False
    except Exception as e:
        # Catch any other unexpected errors
        # This should rarely happen, but we want to handle it gracefully
        logger.error(
            f"✗ Unexpected error inserting audit event: {e}. "
            f"Event: {event}",
            exc_info=True  # Include full stack trace for debugging
        )
        return False


def _parse_timestamp(timestamp_str: Optional[str]) -> datetime:
    """
    Parse timestamp string to datetime object.
    
    This helper function converts timestamp strings from Kafka events (which are in
    ISO 8601 format) into Python datetime objects that MongoDB can store.
    
    Why we need this:
    - Kafka events send timestamps as strings (e.g., "2024-01-14T17:30:00Z")
    - MongoDB stores timestamps as datetime objects
    - We need to convert between these formats
    
    Supports ISO 8601 format (RFC3339) with or without timezone:
    - "2024-01-14T17:30:00Z" (UTC with Z suffix)
    - "2024-01-14T17:30:00+00:00" (UTC with timezone offset)
    - "2024-01-14T17:30:00" (no timezone, assumed UTC)
    
    Args:
        timestamp_str: Timestamp string in ISO 8601 format, or None
    
    Returns:
        datetime object in UTC (timezone-naive, as MongoDB expects)
    
    Example:
        timestamp_str = "2024-01-14T17:30:00Z"
        dt = _parse_timestamp(timestamp_str)  # Returns datetime(2024, 1, 14, 17, 30, 0)
    """
    # If no timestamp provided, use current time
    # This shouldn't happen in normal operation, but we handle it gracefully
    if timestamp_str is None:
        logger.warning("No timestamp in event, using current UTC time")
        return datetime.utcnow()
    
    try:
        # Handle 'Z' suffix (Z means UTC timezone)
        # Python's fromisoformat() doesn't handle 'Z' directly, so we convert it
        if timestamp_str.endswith('Z'):
            # Replace 'Z' with '+00:00' which Python understands
            timestamp_str = timestamp_str[:-1] + '+00:00'
        
        # Parse ISO 8601 format string to datetime object
        # fromisoformat() handles most ISO 8601 formats including timezones
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # Convert to UTC and make timezone-naive
        # MongoDB stores datetimes as UTC without timezone info
        if dt.tzinfo is not None:
            # Convert to UTC timezone, then remove timezone info
            dt = dt.astimezone().replace(tzinfo=None)
        
        return dt
    except (ValueError, AttributeError) as e:
        # If parsing fails, log a warning and use current time
        # This ensures we still store the event, even if timestamp parsing fails
        logger.warning(
            f"Failed to parse timestamp '{timestamp_str}', using current UTC time. "
            f"Error: {e}"
        )
        return datetime.utcnow()


def close_mongodb_client() -> None:
    """
    Close the MongoDB client and clean up resources.
    
    This should be called when the application shuts down.
    """
    global _mongodb_client, _mongodb_db
    
    if _mongodb_client is not None:
        logger.info("Closing MongoDB client")
        _mongodb_client.close()
        _mongodb_client = None
        _mongodb_db = None
        logger.info("MongoDB client closed")
