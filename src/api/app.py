# src/api/app.py
# This file creates the Flask application and sets up the API
# Flask is a web framework for Python - it lets us create REST API endpoints
# REST API = way to interact with our service over HTTP (like a website, but for programs)

from flask import Flask, request, jsonify
from logger import get_logger
from config import settings

# Import resilience patterns for graceful draining and protection
from resilience import (
    get_resilience_manager,
    CircuitOpenError,
    BulkheadFullError,
)

# Import our service functions
from service import (
    resolve_endpoint,
    RouteNotFoundError,
    create_route,
    activate_route,
    deactivate_route,
)
from service.audit import (
    get_route_history,
    get_recent_events,
    get_events_by_action,
    get_events_in_time_range,
)

# Import database pool for health checks
from db.pool import get_connection, get_pool_status

# Import monitoring utilities
from monitoring import (
    setup_metrics_endpoint,
    start_metrics_collector,
    setup_request_monitoring,
)

# Import tracking middleware for correlation IDs
from tracking.middleware import setup_correlation_tracking

logger = get_logger(__name__)


def create_app():
    """
    Create and configure the Flask application.
    
    This is a factory function - it creates the app with all its configuration.
    Factory pattern is useful because:
    - Can create multiple app instances (for testing)
    - Configuration is centralized
    - Easy to set up different environments
    
    Returns:
        Configured Flask application instance
    """
    # Create Flask application
    # __name__ tells Flask where to find templates, static files, etc.
    app = Flask(__name__)
    
    # Configure Flask settings
    # These affect how Flask behaves
    app.config['DEBUG'] = settings.app.debug  # Enable debug mode (dev only!)
    app.config['JSON_SORT_KEYS'] = False  # Don't sort JSON keys (preserve order)
    
    # Register API routes
    # Routes are the endpoints (URLs) that clients can call
    register_routes(app)
    
    # Register error handlers
    # These handle errors and return proper HTTP responses
    register_error_handlers(app)
    
    # Register monitoring endpoints
    # This sets up the /metrics endpoint for Prometheus
    setup_metrics_endpoint(app)
    
    # Set up correlation ID tracking middleware
    # This extracts or generates correlation IDs for end-to-end request tracking
    setup_correlation_tracking(app)
    
    # Set up request monitoring middleware
    # This automatically tracks all API requests (count, latency, status codes)
    setup_request_monitoring(app)
    
    # Start background metrics collector
    # This periodically updates system metrics (connection pool, cache status, etc.)
    start_metrics_collector(interval=30)  # Collect every 30 seconds
    
    logger.info(f"Flask application created: debug={settings.app.debug}")
    logger.info("Monitoring enabled: /metrics endpoint available for Prometheus")
    logger.info("Correlation ID tracking enabled: X-Correlation-ID header supported")
    
    return app


def register_routes(app: Flask):
    """
    Register all API routes with the Flask application.
    
    Routes define what URLs clients can call and what functions handle them.
    This is like mapping URLs to functions.
    
    Args:
        app: Flask application instance
    """
    
    # ============================================
    # Health Check Endpoints
    # ============================================
    # Health checks are used by:
    # - Load balancers (to know if server is healthy)
    # - Monitoring systems (to alert if service is down)
    # - Kubernetes (for liveness/readiness probes)
    # - DevOps tools (for automated health monitoring)
    
    @app.route('/health', methods=['GET'])
    def health():
        """
        Basic health check endpoint.
        
        Returns 200 if the service is running.
        This is the simplest health check - just confirms the API is responding.
        
        Returns:
            JSON response with status
        """
        return jsonify({
            "status": "healthy",
            "service": "traffic-manager"
        }), 200
    
    @app.route('/health/ready', methods=['GET'])
    def readiness():
        """
        Readiness probe endpoint.
        
        Readiness means the service is ready to accept traffic.
        This checks if all dependencies (database, cache, kafka) are available.
        
        IMPORTANT: This endpoint also checks if the server is draining.
        If draining, we return 503 (not ready) so load balancers stop sending traffic.
        
        Kubernetes uses this to know when to start sending traffic.
        If this fails, Kubernetes won't send requests to this instance.
        
        Returns:
            JSON response with readiness status and dependency checks
        """
        # Get resilience manager to check draining status
        manager = get_resilience_manager()
        
        # Check if server is draining
        # If draining, we're not ready to accept new traffic
        is_draining = manager.drainer.is_draining()
        
        checks = {
            "database": check_database(),
            "cache": check_cache(),
            "kafka": check_kafka(),
            "mongodb": check_mongodb(),
            "draining": {
                "status": "draining" if is_draining else "not_draining",
                "in_flight_requests": manager.drainer.get_in_flight_count(),
                "message": "Server is draining and not accepting new requests" if is_draining else "Server is ready"
            }
        }
        
        # Service is ready if:
        # 1. All critical dependencies are healthy
        # 2. Server is NOT draining
        # Database is critical (can't work without it)
        # Cache, Kafka, and MongoDB are non-critical (can degrade gracefully)
        all_ready = (
            checks["database"]["status"] == "healthy" and
            not is_draining
        )
        
        status_code = 200 if all_ready else 503  # 503 = Service Unavailable
        
        return jsonify({
            "status": "ready" if all_ready else "not_ready",
            "checks": checks
        }), status_code
    
    @app.route('/health/live', methods=['GET'])
    def liveness():
        """
        Liveness probe endpoint.
        
        Liveness means the service process is alive and running.
        This is simpler than readiness - just checks if the process is working.
        
        Kubernetes uses this to know if it should restart the container.
        If this fails, Kubernetes will kill and restart the container.
        
        Returns:
            JSON response with liveness status
        """
        # For liveness, we just check if the application is running
        # We don't check dependencies because:
        # - If database is down, we might still be able to recover
        # - We don't want Kubernetes to restart us just because DB is temporarily down
        return jsonify({
            "status": "alive",
            "service": "traffic-manager"
        }), 200
    
    @app.route('/health/resilience', methods=['GET'])
    def resilience_metrics():
        """
        Resilience patterns metrics endpoint.
        
        This endpoint exposes metrics from all resilience patterns:
        - Circuit breaker states and failure rates
        - Retry budget usage
        - Bulkhead utilization
        - Graceful draining status
        
        This is useful for:
        - Monitoring resilience pattern health
        - Debugging why requests are failing
        - Understanding system behavior under load
        - Interview preparation (seeing patterns in action)
        
        Returns:
            JSON response with resilience metrics
        
        Example:
            GET /health/resilience
        
        Response includes:
        - circuit_breakers: State, failure rates, total calls
        - retry_budgets: Current usage, budget remaining
        - bulkheads: Current usage, utilization percentage
        - graceful_draining: Draining status, in-flight requests
        """
        try:
            manager = get_resilience_manager()
            metrics = manager.get_all_metrics()
            
            return jsonify(metrics), 200
            
        except Exception as e:
            logger.error(f"Error retrieving resilience metrics: {e}", exc_info=True)
            return jsonify({
                "error": "Internal server error",
                "message": "An unexpected error occurred"
            }), 500
    
    # ============================================
    # Read Path Endpoints
    # ============================================
    # These endpoints handle reading/resolving routes
    
    @app.route('/api/v1/routes/resolve', methods=['GET'])
    def resolve_route():
        """
        Resolve an endpoint URL for a given route.
        
        This is the read path - it finds the URL for a route.
        It uses caching for performance (fast path).
        
        This endpoint is protected by:
        - Graceful draining: Rejects requests during shutdown
        - Bulkhead: Limits concurrent read operations
        - Circuit breaker: Fails fast if database is down
        
        Query Parameters:
            tenant: Tenant name (required)
            service: Service name (required)
            env: Environment name (required)
            version: Version name (required)
        
        Returns:
            JSON response with the resolved URL
        
        Example:
            GET /api/v1/routes/resolve?tenant=team-a&service=payments&env=prod&version=v2
        """
        # Get resilience manager for graceful draining and bulkhead
        manager = get_resilience_manager()
        
        # Step 1: Check if server is draining (graceful draining)
        # If draining, reject new requests immediately
        try:
            with manager.drainer.process_request():
                # Step 2: Acquire bulkhead slot (resource isolation)
                # This limits concurrent read operations
                # If too many reads are running, wait (up to timeout)
                with manager.read_bulkhead.acquire():
                    # Get query parameters from the request
                    # Query parameters are in the URL: ?tenant=team-a&service=payments
                    tenant = request.args.get('tenant')
                    service = request.args.get('service')
                    env = request.args.get('env')
                    version = request.args.get('version')
                    
                    # Validate that all required parameters are provided
                    # Input validation is important for security and user experience
                    if not all([tenant, service, env, version]):
                        return jsonify({
                            "error": "Missing required parameters",
                            "required": ["tenant", "service", "env", "version"]
                        }), 400  # 400 = Bad Request
                    
                    try:
                        # Step 3: Use circuit breaker to protect database call
                        # If database is failing, circuit breaker fails fast
                        # This prevents waiting for timeouts
                        from db.pool import get_connection
                        
                        def _resolve():
                            with get_connection() as conn:
                                return resolve_endpoint(conn, tenant, service, env, version)
                        
                        # Call with circuit breaker protection
                        # If circuit is open, this raises CircuitOpenError immediately
                        url = manager.db_circuit.call(_resolve)
                        
                        # Return success response with the URL
                        # 200 = OK (success)
                        return jsonify({
                            "tenant": tenant,
                            "service": service,
                            "env": env,
                            "version": version,
                            "url": url
                        }), 200
                        
                    except CircuitOpenError:
                        # Circuit breaker is open - database is failing
                        # Try to return cached data as fallback
                        logger.warning(
                            f"Database circuit breaker is OPEN, attempting cache fallback"
                        )
                        try:
                            from cache import get_redis_client
                            redis_client = get_redis_client()
                            cache_key = f"route:{tenant}:{service}:{env}:{version}"
                            cached_url = redis_client.get(cache_key)
                            
                            if cached_url and cached_url != "__NOT_FOUND__":
                                logger.info("Returning cached data (circuit breaker fallback)")
                                return jsonify({
                                    "tenant": tenant,
                                    "service": service,
                                    "env": env,
                                    "version": version,
                                    "url": cached_url,
                                    "source": "cache_fallback"
                                }), 200
                        except Exception:
                            pass  # Cache also failed, continue to error
                        
                        # No cache fallback available, return error
                        return jsonify({
                            "error": "Service temporarily unavailable",
                            "message": "Database is currently unavailable. Please try again later."
                        }), 503  # 503 = Service Unavailable
                        
                    except RouteNotFoundError as e:
                        # Route doesn't exist - return 404 Not Found
                        # This is the correct HTTP status code for "resource not found"
                        return jsonify({
                            "error": "Route not found",
                            "message": str(e),
                            "tenant": tenant,
                            "service": service,
                            "env": env,
                            "version": version
                        }), 404
                        
                    except Exception as e:
                        # Unexpected error - log it and return 500 Internal Server Error
                        # 500 means something went wrong on our side (not the client's fault)
                        logger.error(f"Error resolving route: {e}", exc_info=True)
                        return jsonify({
                            "error": "Internal server error",
                            "message": "An unexpected error occurred"
                        }), 500
                        
        except RuntimeError:
            # Server is draining, reject request
            return jsonify({
                "error": "Service is shutting down",
                "message": "Server is draining and not accepting new requests"
            }), 503  # 503 = Service Unavailable
        
        except BulkheadFullError:
            # Bulkhead is full, too many concurrent operations
            return jsonify({
                "error": "Service overloaded",
                "message": "Too many concurrent requests. Please try again later."
            }), 503  # 503 = Service Unavailable
    
    # ============================================
    # Write Path Endpoints
    # ============================================
    # These endpoints handle creating/updating routes
    
    @app.route('/api/v1/routes', methods=['POST'])
    def create_route_endpoint():
        """
        Create a new route.
        
        This is the write path - it creates a new route in the database.
        It uses database transactions for atomicity (all or nothing).
        After successful creation, it publishes a Kafka event.
        
        This endpoint is protected by:
        - Graceful draining: Rejects requests during shutdown
        - Bulkhead: Limits concurrent write operations
        - Circuit breaker: Fails fast if database is down
        
        Request Body (JSON):
            {
                "tenant": "team-a",
                "service": "payments",
                "env": "prod",
                "version": "v2",
                "url": "https://payments.example.com/v2"
            }
        
        Returns:
            JSON response with created route information
        
        Example:
            POST /api/v1/routes
            {
                "tenant": "team-a",
                "service": "payments",
                "env": "prod",
                "version": "v2",
                "url": "https://payments.example.com/v2"
            }
        """
        # Get resilience manager for graceful draining and bulkhead
        manager = get_resilience_manager()
        
        # Step 1: Check if server is draining (graceful draining)
        try:
            with manager.drainer.process_request():
                # Step 2: Acquire write bulkhead slot (resource isolation)
                # Writes are slower, so we limit concurrent writes separately
                with manager.write_bulkhead.acquire():
                    # Get JSON data from request body
                    # request.json automatically parses JSON and converts to Python dict
                    data = request.get_json()
                    
                    if not data:
                        return jsonify({
                            "error": "Request body must be JSON"
                        }), 400
                    
                    # Extract parameters from request body
                    # Using .get() with defaults is safer than direct access (won't crash if missing)
                    tenant = data.get('tenant')
                    service = data.get('service')
                    env = data.get('env')
                    version = data.get('version')
                    url = data.get('url')
                    
                    # Validate required fields
                    if not all([tenant, service, env, version, url]):
                        return jsonify({
                            "error": "Missing required fields",
                            "required": ["tenant", "service", "env", "version", "url"]
                        }), 400
                    
                    try:
                        # Step 3: Use circuit breaker to protect database call
                        from db.pool import get_connection
                        
                        def _create():
                            with get_connection() as conn:
                                return create_route(conn, tenant, service, env, version, url)
                        
                        # Call with circuit breaker protection
                        route = manager.db_circuit.call(_create)
                        
                        # Return success response with created route
                        # 201 = Created (successful creation)
                        return jsonify(route), 201
                        
                    except CircuitOpenError:
                        # Circuit breaker is open - database is failing
                        logger.error("Database circuit breaker is OPEN, cannot create route")
                        return jsonify({
                            "error": "Service temporarily unavailable",
                            "message": "Database is currently unavailable. Please try again later."
                        }), 503  # 503 = Service Unavailable
                        
                    except ValueError as e:
                        # Validation error - client sent invalid data
                        return jsonify({
                            "error": "Validation error",
                            "message": str(e)
                        }), 400
                        
                    except Exception as e:
                        # Unexpected error
                        logger.error(f"Error creating route: {e}", exc_info=True)
                        return jsonify({
                            "error": "Internal server error",
                            "message": "An unexpected error occurred"
                        }), 500
                        
        except RuntimeError:
            # Server is draining, reject request
            return jsonify({
                "error": "Service is shutting down",
                "message": "Server is draining and not accepting new requests"
            }), 503
        
        except BulkheadFullError:
            # Bulkhead is full, too many concurrent writes
            return jsonify({
                "error": "Service overloaded",
                "message": "Too many concurrent write operations. Please try again later."
            }), 503
    
    @app.route('/api/v1/routes/activate', methods=['POST'])
    def activate_route_endpoint():
        """
        Activate a route (set is_active = true).
        
        This makes a route visible to the read path again.
        It's a write operation, so it uses database transactions.
        
        Request Body (JSON):
            {
                "tenant": "team-a",
                "service": "payments",
                "env": "prod",
                "version": "v2"
            }
        
        Returns:
            JSON response with activated route information
        """
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        tenant = data.get('tenant')
        service = data.get('service')
        env = data.get('env')
        version = data.get('version')
        
        if not all([tenant, service, env, version]):
            return jsonify({
                "error": "Missing required fields",
                "required": ["tenant", "service", "env", "version"]
            }), 400
        
        try:
            with get_connection() as conn:
                route = activate_route(conn, tenant, service, env, version)
            
            return jsonify(route), 200
            
        except ValueError as e:
            return jsonify({
                "error": "Validation error",
                "message": str(e)
            }), 404  # 404 because route not found
            
        except Exception as e:
            logger.error(f"Error activating route: {e}", exc_info=True)
            return jsonify({
                "error": "Internal server error",
                "message": "An unexpected error occurred"
            }), 500
    
    @app.route('/api/v1/routes/deactivate', methods=['POST'])
    def deactivate_route_endpoint():
        """
        Deactivate a route (set is_active = false).
        
        This makes a route invisible to the read path (soft delete).
        The route still exists in the database, just marked as inactive.
        
        Request Body (JSON):
            {
                "tenant": "team-a",
                "service": "payments",
                "env": "prod",
                "version": "v2"
            }
        
        Returns:
            JSON response with deactivated route information
        """
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        tenant = data.get('tenant')
        service = data.get('service')
        env = data.get('env')
        version = data.get('version')
        
        if not all([tenant, service, env, version]):
            return jsonify({
                "error": "Missing required fields",
                "required": ["tenant", "service", "env", "version"]
            }), 400
        
        try:
            with get_connection() as conn:
                route = deactivate_route(conn, tenant, service, env, version)
            
            return jsonify(route), 200
            
        except ValueError as e:
            return jsonify({
                "error": "Validation error",
                "message": str(e)
            }), 404
            
        except Exception as e:
            logger.error(f"Error deactivating route: {e}", exc_info=True)
            return jsonify({
                "error": "Internal server error",
                "message": "An unexpected error occurred"
            }), 500
    
    # ============================================
    # Audit Log Endpoints
    # ============================================
    # These endpoints provide access to route change history from MongoDB
    
    @app.route('/api/v1/audit/route', methods=['GET'])
    def get_route_audit_history():
        """
        Get audit history for a specific route.
        
        Answers: "Who changed this route?" and "When did it change?"
        
        Query Parameters:
            tenant: Tenant name (required)
            service: Service name (required)
            env: Environment name (required)
            version: Version name (required)
            limit: Maximum number of events to return (default: 100, max: 1000)
        
        Returns:
            JSON response with list of audit events
        
        Example:
            GET /api/v1/audit/route?tenant=team-a&service=payments&env=prod&version=v2&limit=50
        """
        # Get query parameters
        tenant = request.args.get('tenant')
        service = request.args.get('service')
        env = request.args.get('env')
        version = request.args.get('version')
        limit = request.args.get('limit', default=100, type=int)
        
        # Validate required parameters
        if not all([tenant, service, env, version]):
            return jsonify({
                "error": "Missing required parameters",
                "required": ["tenant", "service", "env", "version"]
            }), 400
        
        # Validate limit
        if limit < 1 or limit > 1000:
            return jsonify({
                "error": "Invalid limit",
                "message": "Limit must be between 1 and 1000"
            }), 400
        
        try:
            events = get_route_history(tenant, service, env, version, limit)
            
            return jsonify({
                "route": {
                    "tenant": tenant,
                    "service": service,
                    "env": env,
                    "version": version
                },
                "count": len(events),
                "events": events
            }), 200
            
        except Exception as e:
            logger.error(f"Error retrieving route audit history: {e}", exc_info=True)
            return jsonify({
                "error": "Internal server error",
                "message": "An unexpected error occurred"
            }), 500
    
    @app.route('/api/v1/audit/recent', methods=['GET'])
    def get_recent_audit_events():
        """
        Get audit events from the last N days.
        
        Answers: "Can we see history for last 30/90 days?"
        
        Query Parameters:
            days: Number of days to look back (default: 30, max: 365)
            tenant: Optional tenant filter
            service: Optional service filter
            env: Optional environment filter
            limit: Maximum number of events to return (default: 100, max: 1000)
        
        Returns:
            JSON response with list of audit events
        
        Example:
            GET /api/v1/audit/recent?days=90&limit=200
            GET /api/v1/audit/recent?days=30&tenant=team-a&service=payments
        """
        # Get query parameters
        days = request.args.get('days', default=30, type=int)
        tenant = request.args.get('tenant')
        service = request.args.get('service')
        env = request.args.get('env')
        limit = request.args.get('limit', default=100, type=int)
        
        # Validate parameters
        if days < 1 or days > 365:
            return jsonify({
                "error": "Invalid days",
                "message": "Days must be between 1 and 365"
            }), 400
        
        if limit < 1 or limit > 1000:
            return jsonify({
                "error": "Invalid limit",
                "message": "Limit must be between 1 and 1000"
            }), 400
        
        try:
            events = get_recent_events(days, tenant, service, env, limit)
            
            return jsonify({
                "days": days,
                "count": len(events),
                "events": events
            }), 200
            
        except Exception as e:
            logger.error(f"Error retrieving recent audit events: {e}", exc_info=True)
            return jsonify({
                "error": "Internal server error",
                "message": "An unexpected error occurred"
            }), 500
    
    @app.route('/api/v1/audit/action', methods=['GET'])
    def get_audit_events_by_action():
        """
        Get audit events filtered by action type.
        
        Answers: "Can we debug an outage caused by a config change?"
        Useful for finding deactivations or other critical actions.
        
        Query Parameters:
            action: Action type - created, activated, or deactivated (required)
            hours: Optional number of hours to look back
            tenant: Optional tenant filter
            service: Optional service filter
            env: Optional environment filter
            limit: Maximum number of events to return (default: 100, max: 1000)
        
        Returns:
            JSON response with list of audit events
        
        Example:
            GET /api/v1/audit/action?action=deactivated&hours=1
            GET /api/v1/audit/action?action=created&tenant=team-a&service=payments
        """
        # Get query parameters
        action = request.args.get('action')
        hours = request.args.get('hours', type=int)
        tenant = request.args.get('tenant')
        service = request.args.get('service')
        env = request.args.get('env')
        limit = request.args.get('limit', default=100, type=int)
        
        # Validate required parameters
        if not action:
            return jsonify({
                "error": "Missing required parameter",
                "required": ["action"],
                "valid_actions": ["created", "activated", "deactivated"]
            }), 400
        
        if action not in ["created", "activated", "deactivated"]:
            return jsonify({
                "error": "Invalid action",
                "valid_actions": ["created", "activated", "deactivated"]
            }), 400
        
        if limit < 1 or limit > 1000:
            return jsonify({
                "error": "Invalid limit",
                "message": "Limit must be between 1 and 1000"
            }), 400
        
        try:
            events = get_events_by_action(action, hours, tenant, service, env, limit)
            
            return jsonify({
                "action": action,
                "hours": hours,
                "count": len(events),
                "events": events
            }), 200
            
        except Exception as e:
            logger.error(f"Error retrieving audit events by action: {e}", exc_info=True)
            return jsonify({
                "error": "Internal server error",
                "message": "An unexpected error occurred"
            }), 500
    
    @app.route('/api/v1/audit/time-range', methods=['GET'])
    def get_audit_events_in_time_range():
        """
        Get audit events within a specific time range.
        
        Useful for debugging outages by looking at changes in a specific time window.
        
        Query Parameters:
            start_time: Start of time range in ISO 8601 format (required)
            end_time: End of time range in ISO 8601 format (required)
            tenant: Optional tenant filter
            service: Optional service filter
            env: Optional environment filter
            action: Optional action filter (created, activated, deactivated)
            limit: Maximum number of events to return (default: 100, max: 1000)
        
        Returns:
            JSON response with list of audit events
        
        Example:
            GET /api/v1/audit/time-range?start_time=2024-01-14T17:00:00Z&end_time=2024-01-14T18:00:00Z
        """
        # Get query parameters
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')
        tenant = request.args.get('tenant')
        service = request.args.get('service')
        env = request.args.get('env')
        action = request.args.get('action')
        limit = request.args.get('limit', default=100, type=int)
        
        # Validate required parameters
        if not start_time_str or not end_time_str:
            return jsonify({
                "error": "Missing required parameters",
                "required": ["start_time", "end_time"],
                "format": "ISO 8601 (e.g., 2024-01-14T17:00:00Z)"
            }), 400
        
        # Parse timestamps
        try:
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            
            # Convert to UTC (remove timezone for MongoDB)
            if start_time.tzinfo:
                start_time = start_time.astimezone().replace(tzinfo=None)
            if end_time.tzinfo:
                end_time = end_time.astimezone().replace(tzinfo=None)
            
        except ValueError as e:
            return jsonify({
                "error": "Invalid timestamp format",
                "message": str(e),
                "format": "ISO 8601 (e.g., 2024-01-14T17:00:00Z)"
            }), 400
        
        # Validate time range
        if start_time >= end_time:
            return jsonify({
                "error": "Invalid time range",
                "message": "start_time must be before end_time"
            }), 400
        
        if limit < 1 or limit > 1000:
            return jsonify({
                "error": "Invalid limit",
                "message": "Limit must be between 1 and 1000"
            }), 400
        
        if action and action not in ["created", "activated", "deactivated"]:
            return jsonify({
                "error": "Invalid action",
                "valid_actions": ["created", "activated", "deactivated"]
            }), 400
        
        try:
            events = get_events_in_time_range(
                start_time, end_time, tenant, service, env, action, limit
            )
            
            return jsonify({
                "start_time": start_time_str,
                "end_time": end_time_str,
                "count": len(events),
                "events": events
            }), 200
            
        except Exception as e:
            logger.error(f"Error retrieving audit events in time range: {e}", exc_info=True)
            return jsonify({
                "error": "Internal server error",
                "message": "An unexpected error occurred"
            }), 500


def register_error_handlers(app: Flask):
    """
    Register error handlers for the Flask application.
    
    Error handlers catch exceptions and return proper HTTP responses.
    This ensures clients always get a valid JSON response, even on errors.
    
    Args:
        app: Flask application instance
    """
    
    @app.errorhandler(404)
    def not_found(error):
        """
        Handle 404 Not Found errors.
        
        This is called when a URL doesn't match any route.
        For example: GET /api/v1/nonexistent
        
        Returns:
            JSON error response
        """
        return jsonify({
            "error": "Not found",
            "message": "The requested endpoint does not exist"
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        """
        Handle 405 Method Not Allowed errors.
        
        This is called when a route exists but the HTTP method is wrong.
        For example: POST /health (health only accepts GET)
        
        Returns:
            JSON error response
        """
        return jsonify({
            "error": "Method not allowed",
            "message": "The HTTP method is not allowed for this endpoint"
        }), 405
    
    @app.errorhandler(500)
    def internal_error(error):
        """
        Handle 500 Internal Server Error.
        
        This is called when an unhandled exception occurs.
        In production, you might want to log this to an error tracking service.
        
        Returns:
            JSON error response
        """
        logger.error(f"Internal server error: {error}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "An unexpected error occurred"
        }), 500


# Health check helper functions
# These check if dependencies are available

def check_database():
    """
    Check if database is accessible.
    
    This tries to get a connection from the pool and execute a simple query.
    If it succeeds, database is healthy.
    
    Returns:
        Dictionary with check status and details
    """
    try:
        # Try to get a connection from the pool
        # This will fail if database is down or pool is exhausted
        with get_connection() as conn:
            # Execute a simple query to test connectivity
            # SELECT 1 is the simplest possible query - just returns 1
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()  # Fetch the result
        
        # Get pool status for additional information
        pool_status = get_pool_status()
        
        return {
            "status": "healthy",
            "message": "Database is accessible",
            "pool": pool_status
        }
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "message": f"Database is not accessible: {str(e)}"
        }


def check_cache():
    """
    Check if Redis cache is accessible.
    
    This tries to ping Redis. If it succeeds, cache is healthy.
    Cache is non-critical - service can work without it (just slower).
    
    Returns:
        Dictionary with check status
    """
    try:
        from cache import get_redis_client
        client = get_redis_client()
        client.ping()  # PING is a simple Redis command to test connectivity
        return {
            "status": "healthy",
            "message": "Cache is accessible"
        }
    except Exception as e:
        logger.warning(f"Cache health check failed: {e}")
        return {
            "status": "degraded",  # Degraded, not unhealthy (service can work without cache)
            "message": f"Cache is not accessible: {str(e)}"
        }


def check_kafka():
    """
    Check if Kafka is accessible.
    
    This tries to create a producer and get metadata.
    Kafka is non-critical - write path can work without it (events just delayed).
    
    Returns:
        Dictionary with check status
    """
    try:
        from kafka_client import get_kafka_producer
        producer = get_kafka_producer()
        # Try to get metadata - this tests connectivity to Kafka
        # list_topics() requires connecting to Kafka brokers
        producer.list_topics(timeout=5)
        return {
            "status": "healthy",
            "message": "Kafka is accessible"
        }
    except Exception as e:
        logger.warning(f"Kafka health check failed: {e}")
        return {
            "status": "degraded",  # Degraded, not unhealthy (service can work without Kafka)
            "message": f"Kafka is not accessible: {str(e)}"
        }


def check_mongodb():
    """
    Check if MongoDB is accessible.
    
    This tries to connect to MongoDB and ping the server.
    MongoDB is non-critical - audit logging can be delayed if it's down.
    
    Returns:
        Dictionary with check status
    """
    try:
        from mongodb_client import get_mongodb_client
        client = get_mongodb_client()
        # Ping the server to test connectivity
        client.admin.command('ping')
        return {
            "status": "healthy",
            "message": "MongoDB is accessible"
        }
    except Exception as e:
        logger.warning(f"MongoDB health check failed: {e}")
        return {
            "status": "degraded",  # Degraded, not unhealthy (service can work without MongoDB)
            "message": f"MongoDB is not accessible: {str(e)}"
        }
