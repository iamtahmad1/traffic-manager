# src/tracking/middleware.py
# Flask middleware for correlation ID management
# This middleware extracts correlation IDs from HTTP headers or generates new ones
# It ensures every request has a correlation ID that flows through all components

from flask import request, g, has_request_context
from tracking.correlation import (
    get_correlation_id,
    set_correlation_id,
    generate_correlation_id,
)
from logger import get_logger

# Import metrics - handle import error gracefully for testing
try:
    from metrics import CORRELATION_IDS_GENERATED_TOTAL, CORRELATION_IDS_PROVIDED_TOTAL
except ImportError:
    # Fallback for testing or if metrics not available
    CORRELATION_IDS_GENERATED_TOTAL = None
    CORRELATION_IDS_PROVIDED_TOTAL = None

logger = get_logger(__name__)

# Standard HTTP header name for correlation IDs
# Clients can send this header to trace their requests
CORRELATION_ID_HEADER = "X-Correlation-ID"
RESPONSE_CORRELATION_ID_HEADER = "X-Correlation-ID"


def setup_correlation_tracking(app):
    """
    Set up correlation ID tracking middleware for Flask.
    
    This middleware:
    1. Extracts correlation ID from X-Correlation-ID header (if provided by client)
    2. Generates a new correlation ID if not provided
    3. Stores it in Flask's 'g' object for request-scoped access
    4. Sets it in the context variable for use throughout the request
    5. Adds it to response headers so clients can track their requests
    
    Args:
        app: Flask application instance
    """
    
    @app.before_request
    def before_request():
        """
        Called before each request is processed.
        
        Extracts or generates correlation ID and stores it for the request.
        """
        # Try to get correlation ID from request header
        # Clients can send X-Correlation-ID to trace their requests across services
        correlation_id = request.headers.get(CORRELATION_ID_HEADER)
        
        if not correlation_id:
            # No header provided, generate a new correlation ID
            correlation_id = generate_correlation_id()
            if CORRELATION_IDS_GENERATED_TOTAL:
                CORRELATION_IDS_GENERATED_TOTAL.inc()
            logger.debug(f"Generated new correlation ID: {correlation_id}")
        else:
            if CORRELATION_IDS_PROVIDED_TOTAL:
                CORRELATION_IDS_PROVIDED_TOTAL.inc()
            logger.debug(f"Using correlation ID from header: {correlation_id}")
        
        # Store in Flask's 'g' object (request-scoped storage)
        g.correlation_id = correlation_id
        
        # Set in context variable for use throughout the request
        set_correlation_id(correlation_id)
    
    @app.after_request
    def after_request(response):
        """
        Called after each request is processed.
        
        Adds correlation ID to response headers so clients can track their requests.
        """
        if has_request_context():
            correlation_id = getattr(g, 'correlation_id', None)
            if correlation_id:
                # Add correlation ID to response headers
                # This allows clients to see the correlation ID used for their request
                response.headers[RESPONSE_CORRELATION_ID_HEADER] = correlation_id
        
        return response
    
    logger.info("Correlation ID tracking middleware enabled")
