#!/usr/bin/env python3
"""
Run a Kafka consumer for a specific use case.

Usage:
  python scripts/run_consumer.py cache_invalidation
  python scripts/run_consumer.py cache_warming
  python scripts/run_consumer.py audit_log
"""

import sys
import os

# Add src directory to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kafka_client import run_consumer
from logger import get_logger

logger = get_logger(__name__)


def main():
    if len(sys.argv) != 2:
        logger.error("Usage: python scripts/run_consumer.py <consumer_type>")
        logger.error("Valid types: cache_invalidation | cache_warming | audit_log")
        sys.exit(1)

    consumer_type = sys.argv[1].strip().lower()
    run_consumer(consumer_type)


if __name__ == "__main__":
    main()
