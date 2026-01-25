#!/usr/bin/env python3
"""
Route Management Service - Write Path Microservice

This service handles:
- Route creation
- Route activation/deactivation
- Write operations with transactions

Port: 8002 (configurable via API_PORT)
Uses shared code from src/ directory
"""

import sys
import os

# Add src directory to path to import shared code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

# Import from existing shared code
from logger import get_logger
from config import settings
from db.pool import initialize_pool, close_pool
from kafka_client import close_kafka_producer
from resilience import get_resilience_manager
from api import create_app

logger = get_logger(__name__)

def initialize_services():
    """Initialize services needed for route management."""
    logger.info("Initializing Route Management Service...")
    try:
        initialize_pool()
        logger.info("✓ Database connection pool initialized")
        logger.info("✓ Route Management Service initialized")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}", exc_info=True)
        raise

def cleanup_services():
    """Clean up services."""
    logger.info("Cleaning up Route Management Service...")
    try:
        close_pool()
        close_kafka_producer()
        logger.info("✓ Services cleaned up")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)

def main():
    """Main entry point for Route Management Service."""
    logger.info("=" * 60)
    logger.info("Starting Route Management Service")
    logger.info(f"Environment: {settings.app.environment}")
    logger.info("=" * 60)
    
    resilience_manager = get_resilience_manager()
    
    try:
        initialize_services()
        # Use existing create_app() - it will handle all routes
        app = create_app()
        
        port = int(os.getenv('API_PORT', '8002'))
        logger.info(f"Starting Route Management Service on 0.0.0.0:{port}")
        logger.info(f"Health check: http://0.0.0.0:{port}/health")
        
        app.run(host='0.0.0.0', port=port, debug=False)
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        resilience_manager.drainer.start_draining()
        if resilience_manager.drainer.wait_for_drain():
            logger.info("✓ All requests completed")
        else:
            logger.warning("⚠ Timeout waiting for requests")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        cleanup_services()
        logger.info("Route Management Service shutdown complete")

if __name__ == "__main__":
    main()
