# src/mongodb_client/__init__.py
# MongoDB client module for audit store
# Provides connection management and audit logging functionality

from mongodb_client.client import (
    get_mongodb_client,
    close_mongodb_client,
    insert_audit_event,
    get_audit_collection,
)

__all__ = [
    "get_mongodb_client",
    "close_mongodb_client",
    "insert_audit_event",
    "get_audit_collection",
]
