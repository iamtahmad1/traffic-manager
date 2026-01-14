# src/main.py
# This is the entry point of our application - the main file that gets executed
# In production, this file:
# 1. Initializes all infrastructure (database pool, cache, kafka)
# 2. Creates the Flask API application
# 3. Starts the web server
# 4. Handles graceful shutdown

# Import our centralized logging configuration
# This gives us a configured logger that's ready to use
from logger import get_logger

# Import centralized configuration
from config import settings

# Import database connection pool
# Connection pooling is a production pattern for reusing database connections
from db.pool import initialize_pool, close_pool

# Import cache and kafka cleanup functions
from cache import close_redis_client
from kafka_client import close_kafka_producer

# Import Flask application factory
# Factory pattern lets us create the app with proper configuration
from api import create_app

# Create a logger object for this file
# __name__ is a special variable that contains the name of the current module
# This helps us know which file the log message came from
logger = get_logger(__name__)


def initialize_services():
    """
    Initialize all infrastructure services.
    
    This function sets up:
    - Database connection pool (reusable connections)
    - Redis cache client (with connection pooling)
    - Kafka producer (for event publishing)
    
    This should be called once at application startup.
    All services are initialized before the API starts accepting requests.
    """
    logger.info("Initializing services...")
    
    try:
        # Initialize database connection pool
        # The pool manages a collection of reusable database connections
        # This is much more efficient than creating a new connection for each request
        initialize_pool()
        logger.info("✓ Database connection pool initialized")
        
        # Redis and Kafka clients are created lazily (on first use)
        # This is fine because they handle their own initialization
        # We don't need to initialize them here
        
        logger.info("✓ All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}", exc_info=True)
        raise


def cleanup_services():
    """
    Clean up all infrastructure services.
    
    This function:
    - Closes database connection pool
    - Closes Redis connections
    - Closes Kafka producer
    
    This should be called when the application shuts down.
    It ensures all resources are properly released.
    """
    logger.info("Cleaning up services...")
    
    try:
        # Close database connection pool
        # This closes all connections in the pool
        close_pool()
        logger.info("✓ Database connection pool closed")
        
        # Close Redis client
        # This closes the connection pool
        close_redis_client()
        logger.info("✓ Redis client closed")
        
        # Close Kafka producer
        # This flushes pending messages and closes connections
        close_kafka_producer()
        logger.info("✓ Kafka producer closed")
        
        logger.info("✓ All services cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)


def main():
    """
    Main function - this is where our program starts running.
    
    This function:
    1. Initializes all services (database, cache, kafka)
    2. Creates the Flask API application
    3. Starts the web server
    4. Handles graceful shutdown on exit
    
    In production, this would typically be run by a process manager
    like systemd, supervisord, or a container orchestrator (Kubernetes).
    """
    logger.info("=" * 60)
    logger.info("Starting Traffic Manager Application")
    logger.info(f"Environment: {settings.app.environment}")
    logger.info(f"Debug mode: {settings.app.debug}")
    logger.info("=" * 60)
    
    try:
        # Step 1: Initialize all infrastructure services
        # This must happen before the API starts accepting requests
        # If initialization fails, we want to know immediately (not after server starts)
        initialize_services()
        
        # Step 2: Create Flask application
        # The factory function creates the app with all routes and error handlers
        app = create_app()
        
        # Step 3: Start the web server
        # Flask's development server (for development only!)
        # In production, use a production WSGI server like gunicorn or uwsgi
        logger.info(f"Starting API server on {settings.app.api_host}:{settings.app.api_port}")
        logger.info(f"API endpoints available at: http://{settings.app.api_host}:{settings.app.api_port}")
        logger.info("Health check: http://{}:{}/health".format(settings.app.api_host, settings.app.api_port))
        
        # Run the Flask development server
        # In production, you would use:
        #   gunicorn -w 4 -b 0.0.0.0:8000 'src.main:app'
        # This runs the app using gunicorn (production WSGI server)
        app.run(
            host=settings.app.api_host,  # Listen on this interface
            port=settings.app.api_port,   # Listen on this port
            debug=settings.app.debug,     # Debug mode (dev only!)
            # In production, debug should always be False
        )
        
    except KeyboardInterrupt:
        # User pressed Ctrl+C - graceful shutdown
        logger.info("Received shutdown signal (Ctrl+C)")
        
    except Exception as e:
        # Unexpected error during startup or runtime
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
        
    finally:
        # Always clean up, even if there was an error
        # This ensures resources are released properly
        cleanup_services()
        logger.info("Application shutdown complete")


# This is a special Python pattern
# It means: "only run main() if this file is being executed directly"
# If someone imports this file, main() won't run automatically
# This is useful when you want to reuse code from this file in other projects
if __name__ == "__main__":
    main()
