# src/monitoring/middleware.py
# This file provides Flask middleware for monitoring API requests
# Middleware = code that runs before/after each request
# We use it to track metrics for all API requests automatically

import time
from flask import request, g
from prometheus_client import Counter, Histogram
from logger import get_logger

logger = get_logger(__name__)

# API request metrics
# These track all HTTP requests to our API

# Total API requests (all endpoints)
API_REQUESTS_TOTAL = Counter(
    "api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status_code"]  # Labels for grouping
)

# API request latency
# Measures how long each API request takes
API_REQUEST_DURATION_SECONDS = Histogram(
    "api_request_duration_seconds",
    "Duration of API requests in seconds",
    ["method", "endpoint"]  # Labels for grouping
)


def setup_request_monitoring(app):
    """
    Set up request monitoring middleware for Flask.
    
    This middleware automatically tracks:
    - Request count (total requests per endpoint)
    - Request latency (how long requests take)
    - HTTP status codes (success vs errors)
    
    How it works:
    1. Before request: Record start time
    2. After request: Calculate duration, increment counters
    3. Track by method (GET, POST) and endpoint
    
    This gives us visibility into:
    - Which endpoints are most used
    - Which endpoints are slow
    - Error rates per endpoint
    
    Args:
        app: Flask application instance
    """
    
    @app.before_request
    def before_request():
        """
        Called before each request is processed.
        
        We record the start time so we can calculate how long the request took.
        Flask's 'g' object is a request-local storage - each request gets its own 'g'.
        """
        # Record start time for this request
        # We'll use this later to calculate duration
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        """
        Called after each request is processed.
        
        We calculate metrics here:
        - How long the request took
        - What status code was returned
        - Which endpoint was called
        
        Args:
            response: Flask response object
        
        Returns:
            The response (unchanged, we just observe it)
        """
        # Calculate how long the request took
        # g.start_time was set in before_request()
        duration = time.time() - g.start_time
        
        # Get request information
        method = request.method  # GET, POST, etc.
        endpoint = request.endpoint or 'unknown'  # Function name handling the request
        status_code = response.status_code  # 200, 404, 500, etc.
        
        # Normalize endpoint name
        # request.endpoint might be None or have Flask internal names
        # We want a clean name for metrics
        if endpoint == 'unknown' or not endpoint:
            # Use the path as fallback
            endpoint = request.path
        
        # Increment request counter
        # Labels allow us to group by method, endpoint, and status code
        # Example: api_requests_total{method="GET", endpoint="resolve_route", status_code="200"}
        API_REQUESTS_TOTAL.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        
        # Record request duration
        # This creates a histogram entry for this request
        # Prometheus can then calculate percentiles (p50, p95, p99)
        API_REQUEST_DURATION_SECONDS.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
        
        # Log slow requests (optional, for debugging)
        # In production, you might want to alert on slow requests
        if duration > 1.0:  # Requests taking more than 1 second
            logger.warning(
                f"Slow request: {method} {request.path} took {duration:.2f}s"
            )
        
        # Return the response unchanged
        # Middleware should not modify the response, just observe
        return response
    
    logger.info("Request monitoring middleware enabled")
