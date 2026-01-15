#!/usr/bin/env python3
"""
Run Kafka consumers for different use cases.

Usage:
  # Run a specific consumer
  python scripts/run_consumer.py cache_invalidation
  python scripts/run_consumer.py cache_warming
  python scripts/run_consumer.py audit_log
  
  # Run all consumers at once (in separate processes)
  python scripts/run_consumer.py --all
  python scripts/run_consumer.py all
"""

import sys
import os
import multiprocessing
import signal
import time

# Add src directory to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from kafka_client import run_consumer
from logger import get_logger

logger = get_logger(__name__)

# Supported consumer types
CONSUMER_TYPES = ["cache_invalidation", "cache_warming", "audit_log"]

# Global list to track running processes
running_processes = []


def run_consumer_process(consumer_type: str):
    """
    Run a consumer in a separate process.
    
    Args:
        consumer_type: Type of consumer to run
    """
    try:
        logger.info(f"Starting consumer process: {consumer_type}")
        run_consumer(consumer_type)
    except Exception as e:
        logger.error(f"Consumer {consumer_type} failed: {e}", exc_info=True)
        sys.exit(1)


def signal_handler(signum, frame):
    """
    Handle shutdown signals gracefully.
    """
    logger.info(f"Received signal {signum}, shutting down all consumers...")
    for process in running_processes:
        if process.is_alive():
            logger.info(f"Terminating consumer process: {process.name}")
            process.terminate()
    
    # Wait for processes to terminate
    for process in running_processes:
        process.join(timeout=5)
        if process.is_alive():
            logger.warning(f"Force killing consumer process: {process.name}")
            process.kill()
    
    sys.exit(0)


def run_all_consumers():
    """
    Run all consumers in separate processes.
    """
    logger.info("=" * 60)
    logger.info("Starting all Kafka consumers")
    logger.info("=" * 60)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start each consumer in a separate process
    for consumer_type in CONSUMER_TYPES:
        process = multiprocessing.Process(
            target=run_consumer_process,
            args=(consumer_type,),
            name=f"consumer-{consumer_type}"
        )
        process.start()
        running_processes.append(process)
        logger.info(f"✓ Started consumer: {consumer_type} (PID: {process.pid})")
        # Small delay between starts
        time.sleep(0.5)
    
    logger.info("")
    logger.info("All consumers started. Press Ctrl+C to stop all consumers.")
    logger.info("")
    
    # Wait for all processes
    try:
        while True:
            # Check if any process has died
            for process in running_processes:
                if not process.is_alive():
                    logger.error(f"Consumer process {process.name} has died!")
                    logger.info("Shutting down all consumers...")
                    signal_handler(None, None)
            
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nReceived keyboard interrupt")
        signal_handler(None, None)


def main():
    if len(sys.argv) < 2:
        logger.error("Usage: python scripts/run_consumer.py <consumer_type> | --all")
        logger.error("Valid types: cache_invalidation | cache_warming | audit_log")
        logger.error("Or use '--all' or 'all' to run all consumers")
        sys.exit(1)

    arg = sys.argv[1].strip().lower()
    
    # Check if user wants to run all consumers
    if arg == "--all" or arg == "all":
        run_all_consumers()
    else:
        # Run single consumer
        consumer_type = arg
        if consumer_type not in CONSUMER_TYPES:
            logger.error(f"Invalid consumer type: {consumer_type}")
            logger.error(f"Valid types: {', '.join(CONSUMER_TYPES)}")
            sys.exit(1)
        
        run_consumer(consumer_type)


if __name__ == "__main__":
    main()
