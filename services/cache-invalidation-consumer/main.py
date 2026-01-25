#!/usr/bin/env python3
"""
Cache Invalidation Consumer Service

This service:
- Consumes route change events from Kafka
- Invalidates Redis cache keys when routes change

Runs as a long-lived consumer process.
"""

import sys
import os

# Add parent directory to path to import shared code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from logger import get_logger
from kafka_client.consumer import run_consumer

logger = get_logger(__name__)

def main():
    """Main entry point for Cache Invalidation Consumer."""
    logger.info("=" * 60)
    logger.info("Starting Cache Invalidation Consumer")
    logger.info("=" * 60)
    
    try:
        run_consumer("cache_invalidation")
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise
    finally:
        logger.info("Cache Invalidation Consumer shutdown complete")

if __name__ == "__main__":
    main()
