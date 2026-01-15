# src/service/audit.py
# Audit service for querying route change history from MongoDB
# Provides functions to answer common audit questions

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pymongo.errors import PyMongoError

from logger import get_logger
from mongodb_client import get_audit_collection

logger = get_logger(__name__)


def get_route_history(
    tenant: str,
    service: str,
    env: str,
    version: str,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get audit history for a specific route.
    
    This function queries MongoDB to find all audit events for a specific route.
    It's used by the API endpoint /api/v1/audit/route to answer questions like:
    - "Who changed this route?"
    - "When did it change?"
    - "What was the previous value?"
    
    How it works:
    1. Builds a query to find all events for the specified route
    2. Uses a compound index for fast lookup (route fields + occurred_at)
    3. Sorts results by occurred_at descending (most recent first)
    4. Limits results to the specified number
    5. Converts MongoDB documents to Python dictionaries
    6. Formats timestamps as ISO 8601 strings for JSON response
    
    Args:
        tenant: Tenant name (e.g., "team-a")
        service: Service name (e.g., "payments")
        env: Environment name (e.g., "prod")
        version: Version name (e.g., "v2")
        limit: Maximum number of events to return (default: 100, max recommended: 1000)
    
    Returns:
        List of audit event dictionaries, sorted by occurred_at (most recent first).
        Each event contains:
        - event_id: Unique event identifier
        - action: Action type (created, activated, deactivated)
        - url: Current URL
        - previous_url: Previous URL (if available)
        - previous_state: Previous state (if available)
        - changed_by: User who made the change (if available)
        - occurred_at: When the change happened (ISO 8601 string)
        - processed_at: When we processed the event (ISO 8601 string)
    
    Raises:
        PyMongoError: If MongoDB query fails (connection, permission, etc.)
        Exception: For any other unexpected errors
    
    Example:
        events = get_route_history("team-a", "payments", "prod", "v2", limit=50)
        # Returns list of up to 50 most recent events for that route
    """
    try:
        # Get the MongoDB collection where audit events are stored
        collection = get_audit_collection()
        
        # Build query to find all events for this specific route
        # This query uses the compound index (route.tenant, route.service, route.env, route.version, occurred_at)
        # for efficient lookup - MongoDB can find matching documents very quickly
        query = {
            "route.tenant": tenant,
            "route.service": service,
            "route.env": env,
            "route.version": version,
        }
        
        # Execute query with sorting and limit
        # - find(query): Find all documents matching the query
        # - sort("occurred_at", -1): Sort by occurred_at descending (most recent first)
        # - limit(limit): Only return up to 'limit' documents
        cursor = collection.find(query).sort("occurred_at", -1).limit(limit)
        
        # Convert MongoDB documents to Python dictionaries
        # MongoDB returns documents as dict-like objects, but we want plain dicts
        events = []
        for doc in cursor:
            # Convert MongoDB document to dict and format for API response
            # We extract only the fields we need and format timestamps as ISO strings
            event = {
                "event_id": doc.get("event_id"),
                "action": doc.get("action"),
                "url": doc.get("url"),
                "previous_url": doc.get("previous_url"),
                "previous_state": doc.get("previous_state"),
                "changed_by": doc.get("changed_by"),
                # Convert datetime objects to ISO 8601 strings for JSON serialization
                "occurred_at": doc.get("occurred_at").isoformat() if doc.get("occurred_at") else None,
                "processed_at": doc.get("processed_at").isoformat() if doc.get("processed_at") else None,
            }
            events.append(event)
        
        # Log the query result for monitoring and debugging
        logger.info(
            f"Retrieved {len(events)} audit events for route: "
            f"{tenant}/{service}/{env}/{version}"
        )
        
        return events
        
    except PyMongoError as e:
        # MongoDB-specific errors (connection, permission, query syntax, etc.)
        logger.error(
            f"Failed to query route history from MongoDB: {e}. "
            f"Query: tenant={tenant}, service={service}, env={env}, version={version}"
        )
        raise
    except Exception as e:
        # Any other unexpected errors
        logger.error(
            f"Unexpected error querying route history: {e}. "
            f"Query: tenant={tenant}, service={service}, env={env}, version={version}",
            exc_info=True
        )
        raise


def get_recent_events(
    days: int = 30,
    tenant: Optional[str] = None,
    service: Optional[str] = None,
    env: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get audit events from the last N days.
    
    Answers: "Can we see history for last 30/90 days?"
    
    Args:
        days: Number of days to look back (default: 30)
        tenant: Optional tenant filter
        service: Optional service filter
        env: Optional environment filter
        limit: Maximum number of events to return (default: 100)
    
    Returns:
        List of audit events, sorted by occurred_at (most recent first)
    
    Raises:
        Exception: If MongoDB query fails
    """
    try:
        collection = get_audit_collection()
        
        # Calculate cutoff date
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Build query
        query = {
            "occurred_at": {"$gte": cutoff_date}
        }
        
        # Add optional filters
        if tenant:
            query["route.tenant"] = tenant
        if service:
            query["route.service"] = service
        if env:
            query["route.env"] = env
        
        # Find events, sort by occurred_at descending
        cursor = collection.find(query).sort("occurred_at", -1).limit(limit)
        
        events = []
        for doc in cursor:
            event = {
                "event_id": doc.get("event_id"),
                "action": doc.get("action"),
                "route": doc.get("route", {}),
                "url": doc.get("url"),
                "previous_url": doc.get("previous_url"),
                "previous_state": doc.get("previous_state"),
                "changed_by": doc.get("changed_by"),
                "occurred_at": doc.get("occurred_at").isoformat() if doc.get("occurred_at") else None,
                "processed_at": doc.get("processed_at").isoformat() if doc.get("processed_at") else None,
            }
            events.append(event)
        
        logger.info(f"Retrieved {len(events)} audit events from last {days} days")
        
        return events
        
    except PyMongoError as e:
        logger.error(f"Failed to query recent events from MongoDB: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error querying recent events: {e}")
        raise


def get_events_by_action(
    action: str,
    hours: Optional[int] = None,
    tenant: Optional[str] = None,
    service: Optional[str] = None,
    env: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get audit events filtered by action type, optionally within a time window.
    
    Answers: "Can we debug an outage caused by a config change?"
    Useful for finding deactivations or other critical actions.
    
    Args:
        action: Action type (created, activated, deactivated)
        hours: Optional number of hours to look back
        tenant: Optional tenant filter
        service: Optional service filter
        env: Optional environment filter
        limit: Maximum number of events to return (default: 100)
    
    Returns:
        List of audit events, sorted by occurred_at (most recent first)
    
    Raises:
        Exception: If MongoDB query fails
    """
    try:
        collection = get_audit_collection()
        
        # Build query
        query = {
            "action": action
        }
        
        # Add time filter if specified
        if hours:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            query["occurred_at"] = {"$gte": cutoff_time}
        
        # Add optional filters
        if tenant:
            query["route.tenant"] = tenant
        if service:
            query["route.service"] = service
        if env:
            query["route.env"] = env
        
        # Find events, sort by occurred_at descending
        cursor = collection.find(query).sort("occurred_at", -1).limit(limit)
        
        events = []
        for doc in cursor:
            event = {
                "event_id": doc.get("event_id"),
                "action": doc.get("action"),
                "route": doc.get("route", {}),
                "url": doc.get("url"),
                "previous_url": doc.get("previous_url"),
                "previous_state": doc.get("previous_state"),
                "changed_by": doc.get("changed_by"),
                "occurred_at": doc.get("occurred_at").isoformat() if doc.get("occurred_at") else None,
                "processed_at": doc.get("processed_at").isoformat() if doc.get("processed_at") else None,
            }
            events.append(event)
        
        logger.info(
            f"Retrieved {len(events)} audit events for action={action}"
            + (f" in last {hours} hours" if hours else "")
        )
        
        return events
        
    except PyMongoError as e:
        logger.error(f"Failed to query events by action from MongoDB: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error querying events by action: {e}")
        raise


def get_events_in_time_range(
    start_time: datetime,
    end_time: datetime,
    tenant: Optional[str] = None,
    service: Optional[str] = None,
    env: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get audit events within a specific time range.
    
    Useful for debugging outages by looking at changes in a specific time window.
    
    Args:
        start_time: Start of time range (UTC)
        end_time: End of time range (UTC)
        tenant: Optional tenant filter
        service: Optional service filter
        env: Optional environment filter
        action: Optional action filter
        limit: Maximum number of events to return (default: 100)
    
    Returns:
        List of audit events, sorted by occurred_at (most recent first)
    
    Raises:
        Exception: If MongoDB query fails
    """
    try:
        collection = get_audit_collection()
        
        # Build query
        query = {
            "occurred_at": {
                "$gte": start_time,
                "$lte": end_time
            }
        }
        
        # Add optional filters
        if tenant:
            query["route.tenant"] = tenant
        if service:
            query["route.service"] = service
        if env:
            query["route.env"] = env
        if action:
            query["action"] = action
        
        # Find events, sort by occurred_at descending
        cursor = collection.find(query).sort("occurred_at", -1).limit(limit)
        
        events = []
        for doc in cursor:
            event = {
                "event_id": doc.get("event_id"),
                "action": doc.get("action"),
                "route": doc.get("route", {}),
                "url": doc.get("url"),
                "previous_url": doc.get("previous_url"),
                "previous_state": doc.get("previous_state"),
                "changed_by": doc.get("changed_by"),
                "occurred_at": doc.get("occurred_at").isoformat() if doc.get("occurred_at") else None,
                "processed_at": doc.get("processed_at").isoformat() if doc.get("processed_at") else None,
            }
            events.append(event)
        
        logger.info(
            f"Retrieved {len(events)} audit events between "
            f"{start_time.isoformat()} and {end_time.isoformat()}"
        )
        
        return events
        
    except PyMongoError as e:
        logger.error(f"Failed to query events in time range from MongoDB: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error querying events in time range: {e}")
        raise
