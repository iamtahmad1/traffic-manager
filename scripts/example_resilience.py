#!/usr/bin/env python3
"""
Example script demonstrating resilience patterns usage.

This script shows how to use circuit breakers, retry budgets, bulkheads,
and graceful draining in practice.

Usage:
    python scripts/example_resilience.py
"""

import sys
import os
import time

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from resilience import (
    CircuitBreaker,
    CircuitBreakerConfig,
    RetryBudget,
    RetryBudgetConfig,
    Bulkhead,
    BulkheadConfig,
    GracefulDrainer,
    GracefulDrainConfig,
    get_resilience_manager,
)
from logger import get_logger

logger = get_logger(__name__)


def example_circuit_breaker():
    """
    Example: Using Circuit Breaker
    
    This shows how circuit breaker protects against failing services.
    """
    print("\n" + "="*70)
    print("EXAMPLE 1: Circuit Breaker")
    print("="*70)
    
    # Create a circuit breaker
    circuit = CircuitBreaker(
        name="example_service",
        config=CircuitBreakerConfig(
            failure_threshold=3,      # Open after 3 failures
            timeout_seconds=10,       # Wait 10s before testing recovery
            window_seconds=60,
            min_calls=5
        )
    )
    
    # Simulate a failing service
    def failing_service():
        raise Exception("Service is down!")
    
    # Simulate a working service
    def working_service():
        return "Success!"
    
    print("\n1. Calling failing service (circuit will open)...")
    for i in range(5):
        try:
            result = circuit.call(failing_service)
            print(f"   Call {i+1}: {result}")
        except Exception as e:
            print(f"   Call {i+1}: Failed - {e}")
            print(f"   Circuit state: {circuit.get_state().value}")
    
    print("\n2. Circuit is now OPEN - calls fail fast:")
    try:
        circuit.call(failing_service)
    except Exception as e:
        print(f"   {e}")
        print(f"   Circuit state: {circuit.get_state().value}")
    
    print("\n3. After timeout, circuit tests recovery (HALF_OPEN):")
    time.sleep(11)  # Wait for timeout
    print(f"   Circuit state: {circuit.get_state().value}")
    
    print("\n4. If service recovers, circuit closes:")
    try:
        result = circuit.call(working_service)
        print(f"   Call succeeded: {result}")
        print(f"   Circuit state: {circuit.get_state().value}")
    except Exception as e:
        print(f"   Call failed: {e}")
    
    print("\n5. Metrics:")
    metrics = circuit.get_metrics()
    print(f"   State: {metrics['state']}")
    print(f"   Total calls: {metrics['total_calls']}")
    print(f"   Failure rate: {metrics['failure_rate']:.1f}%")


def example_retry_budget():
    """
    Example: Using Retry Budget
    
    This shows how retry budget prevents retry storms.
    """
    print("\n" + "="*70)
    print("EXAMPLE 2: Retry Budget")
    print("="*70)
    
    # Create a retry budget
    budget = RetryBudget(
        name="example_service",
        config=RetryBudgetConfig(
            max_retries=5,           # Max 5 retries
            window_seconds=60,       # Per 60 seconds
            min_retry_interval=0.1
        )
    )
    
    print("\n1. Retrying with budget (first 5 succeed):")
    for i in range(7):
        if budget.can_retry():
            budget.record_retry()
            print(f"   Retry {i+1}: Allowed (budget available)")
        else:
            print(f"   Retry {i+1}: DENIED (budget exhausted)")
            break
    
    print("\n2. Metrics:")
    metrics = budget.get_metrics()
    print(f"   Current retries: {metrics['current_retries']}")
    print(f"   Max retries: {metrics['max_retries']}")
    print(f"   Budget used: {metrics['budget_used']:.1f}%")
    print(f"   Budget remaining: {metrics['budget_remaining']}")


def example_bulkhead():
    """
    Example: Using Bulkhead
    
    This shows how bulkhead limits concurrent operations.
    """
    print("\n" + "="*70)
    print("EXAMPLE 3: Bulkhead")
    print("="*70)
    
    # Create a bulkhead
    bulkhead = Bulkhead(
        name="example_operations",
        config=BulkheadConfig(
            max_concurrent=3,        # Max 3 concurrent operations
            max_wait_time=5.0
        )
    )
    
    print("\n1. Acquiring bulkhead slots:")
    operations = []
    for i in range(5):
        try:
            with bulkhead.acquire():
                print(f"   Operation {i+1}: Started (slot acquired)")
                operations.append(i)
                # Simulate work
                time.sleep(0.5)
                print(f"   Operation {i+1}: Completed")
        except Exception as e:
            print(f"   Operation {i+1}: DENIED - {e}")
    
    print("\n2. Metrics:")
    metrics = bulkhead.get_metrics()
    print(f"   Current usage: {metrics['current_usage']}")
    print(f"   Max concurrent: {metrics['max_concurrent']}")
    print(f"   Utilization: {metrics['utilization']:.1f}%")


def example_graceful_draining():
    """
    Example: Using Graceful Draining
    
    This shows how graceful draining works.
    """
    print("\n" + "="*70)
    print("EXAMPLE 4: Graceful Draining")
    print("="*70)
    
    # Create a graceful drainer
    drainer = GracefulDrainer(
        name="example_server",
        config=GracefulDrainConfig(
            drain_timeout=10.0,
            check_interval=1.0
        )
    )
    
    print("\n1. Processing requests (normal operation):")
    def process_request(request_id):
        try:
            with drainer.process_request():
                print(f"   Request {request_id}: Processing...")
                time.sleep(0.5)  # Simulate work
                print(f"   Request {request_id}: Completed")
        except RuntimeError as e:
            print(f"   Request {request_id}: REJECTED - {e}")
    
    # Process some requests
    import threading
    threads = []
    for i in range(3):
        t = threading.Thread(target=process_request, args=(i+1,))
        t.start()
        threads.append(t)
        time.sleep(0.1)
    
    # Start draining
    print("\n2. Starting graceful draining...")
    drainer.start_draining()
    print(f"   Draining status: {drainer.is_draining()}")
    print(f"   In-flight requests: {drainer.get_in_flight_count()}")
    
    # Try to process new request (should be rejected)
    print("\n3. New request during draining (should be rejected):")
    try:
        with drainer.process_request():
            print("   This shouldn't print")
    except RuntimeError as e:
        print(f"   Request rejected: {e}")
    
    # Wait for in-flight requests
    print("\n4. Waiting for in-flight requests to complete...")
    for t in threads:
        t.join()
    
    if drainer.wait_for_drain():
        print("   ✓ All requests completed")
    else:
        print("   ⚠ Timeout waiting for requests")
    
    print("\n5. Metrics:")
    metrics = drainer.get_metrics()
    print(f"   Is draining: {metrics['is_draining']}")
    print(f"   In-flight requests: {metrics['in_flight_requests']}")


def example_resilience_manager():
    """
    Example: Using Resilience Manager
    
    This shows how to use the centralized resilience manager.
    """
    print("\n" + "="*70)
    print("EXAMPLE 5: Resilience Manager")
    print("="*70)
    
    # Get resilience manager (creates all patterns)
    manager = get_resilience_manager()
    
    print("\n1. Using circuit breaker for database:")
    def db_query():
        # Simulate database query
        return "query result"
    
    try:
        result = manager.db_circuit.call(db_query)
        print(f"   Result: {result}")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n2. Using bulkhead for read operations:")
    try:
        with manager.read_bulkhead.acquire():
            print("   Read operation executing...")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n3. All resilience metrics:")
    metrics = manager.get_all_metrics()
    print(f"   Database circuit: {metrics['circuit_breakers']['database']['state']}")
    print(f"   Read bulkhead usage: {metrics['bulkheads']['read_operations']['current_usage']}")
    print(f"   Draining status: {metrics['graceful_draining']['is_draining']}")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("RESILIENCE PATTERNS - USAGE EXAMPLES")
    print("="*70)
    print("\nThis script demonstrates how to use:")
    print("1. Circuit Breaker - Fail fast when services are down")
    print("2. Retry Budget - Prevent retry storms")
    print("3. Bulkhead - Isolate resources")
    print("4. Graceful Draining - Zero-downtime deployments")
    print("5. Resilience Manager - Centralized access")
    
    try:
        example_circuit_breaker()
        example_retry_budget()
        example_bulkhead()
        example_graceful_draining()
        example_resilience_manager()
        
        print("\n" + "="*70)
        print("All examples completed!")
        print("="*70)
        print("\nFor more information, see:")
        print("- docs/13-resilience-patterns.md - Complete guide")
        print("- docs/14-resilience-patterns-interview.md - Interview prep")
        print("- src/resilience/ - Implementation code")
        
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user")
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)


if __name__ == "__main__":
    main()
