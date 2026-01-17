# src/tracking/correlation.py
# This file implements correlation ID management for end-to-end request tracking
# A correlation ID is a unique identifier that follows a request through all components
# This enables distributed tracing and makes debugging much easier

import uuid
import threading
from typing import Optional, ContextManager
from contextvars import ContextVar

# Context variable for storing correlation ID per request context
# ContextVar is thread-safe and works with async code
# Each request gets its own context, so correlation IDs don't leak between requests
_correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID.
    
    Uses UUID4 for uniqueness. Format: "req-{uuid}"
    The "req-" prefix makes it easy to identify in logs.
    
    Returns:
        A unique correlation ID string
    """
    return f"req-{uuid.uuid4().hex[:16]}"


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID from the request context.
    
    Returns:
        The correlation ID if set, None otherwise
    """
    return _correlation_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current request context.
    
    Args:
        correlation_id: The correlation ID to set
    """
    _correlation_id.set(correlation_id)


def clear_correlation_id() -> None:
    """
    Clear the correlation ID from the current request context.
    
    Useful for cleanup after request processing.
    """
    _correlation_id.set(None)


def correlation_context(correlation_id: Optional[str] = None) -> ContextManager[Optional[str]]:
    """
    Context manager for setting correlation ID within a scope.
    
    This ensures the correlation ID is automatically cleared when exiting the context.
    Useful for background tasks or async operations.
    
    Args:
        correlation_id: Optional correlation ID. If None, generates a new one.
    
    Returns:
        Context manager that sets and clears correlation ID
    
    Example:
        with correlation_context("req-abc123"):
            # All code here has correlation_id="req-abc123"
            do_something()
        # Correlation ID is automatically cleared here
    """
    class CorrelationContext:
        def __init__(self, cid: Optional[str]):
            self.correlation_id = cid or generate_correlation_id()
            self.old_correlation_id: Optional[str] = None
        
        def __enter__(self) -> Optional[str]:
            self.old_correlation_id = get_correlation_id()
            set_correlation_id(self.correlation_id)
            return self.correlation_id
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.old_correlation_id:
                set_correlation_id(self.old_correlation_id)
            else:
                clear_correlation_id()
    
    return CorrelationContext(correlation_id)
