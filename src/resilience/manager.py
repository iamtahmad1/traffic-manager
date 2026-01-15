# src/resilience/manager.py
# Resilience Patterns Manager
#
# This module provides a centralized way to initialize and access all resilience
# patterns. It creates circuit breakers, retry budgets, bulkheads, and graceful
# drainers for different parts of the system.
#
# HOW TO USE:
# ===========
# from resilience.manager import get_resilience_manager
#
# manager = get_resilience_manager()
# 
# # Use circuit breaker for database
# result = manager.db_circuit.call(lambda: database.query(...))
#
# # Use bulkhead for read operations
# with manager.read_bulkhead.acquire():
#     result = database.query(...)
#
# # Use graceful drainer in request handlers
# with manager.drainer.process_request():
#     return handle_request()

from typing import Optional

from logger import get_logger
from resilience.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from resilience.retry_budget import RetryBudget, RetryBudgetConfig
from resilience.bulkhead import Bulkhead, BulkheadConfig
from resilience.graceful_drain import GracefulDrainer, GracefulDrainConfig

logger = get_logger(__name__)

# Global resilience manager instance (singleton)
_resilience_manager: Optional['ResilienceManager'] = None


class ResilienceManager:
    """
    Centralized manager for all resilience patterns.
    
    This class creates and manages circuit breakers, retry budgets, bulkheads,
    and graceful drainers for the entire application. It provides a single
    place to access all resilience patterns.
    
    WHY A MANAGER?
    ==============
    Instead of creating patterns everywhere, we centralize them here:
    - Single place to configure all patterns
    - Easy to access from anywhere
    - Consistent configuration across the app
    - Better for monitoring and metrics
    
    Example:
        manager = ResilienceManager()
        
        # Use circuit breaker for database
        result = manager.db_circuit.call(lambda: db.query(...))
        
        # Use bulkhead for reads
        with manager.read_bulkhead.acquire():
            result = db.query(...)
    """
    
    def __init__(self):
        """
        Initialize all resilience patterns.
        
        This creates circuit breakers, retry budgets, bulkheads, and graceful
        drainers for different parts of the system.
        """
        logger.info("Initializing resilience patterns...")
        
        # Circuit Breakers
        # These detect failures and fail fast when services are down
        self.db_circuit = CircuitBreaker(
            name="database",
            config=CircuitBreakerConfig(
                failure_threshold=5,      # Open after 5 failures
                timeout_seconds=60,       # Wait 60s before testing recovery
                window_seconds=60,        # Count failures in last 60s
                min_calls=10              # Need 10 calls before opening
            )
        )
        
        self.redis_circuit = CircuitBreaker(
            name="redis",
            config=CircuitBreakerConfig(
                failure_threshold=10,     # Redis is less critical, higher threshold
                timeout_seconds=30,       # Faster recovery test
                window_seconds=60,
                min_calls=20
            )
        )
        
        self.mongodb_circuit = CircuitBreaker(
            name="mongodb",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout_seconds=60,
                window_seconds=60,
                min_calls=10
            )
        )
        
        # Retry Budgets
        # These limit total retries to prevent retry storms
        self.db_retry_budget = RetryBudget(
            name="database",
            config=RetryBudgetConfig(
                max_retries=100,          # Max 100 retries
                window_seconds=60,        # Per 60 seconds
                min_retry_interval=0.1    # Wait 0.1s between retries
            )
        )
        
        self.redis_retry_budget = RetryBudget(
            name="redis",
            config=RetryBudgetConfig(
                max_retries=200,          # More retries for cache (less critical)
                window_seconds=60,
                min_retry_interval=0.05
            )
        )
        
        # Bulkheads
        # These isolate resources for different operation types
        self.read_bulkhead = Bulkhead(
            name="read_operations",
            config=BulkheadConfig(
                max_concurrent=20,        # Allow 20 concurrent reads
                max_wait_time=5.0         # Wait up to 5s for a slot
            )
        )
        
        self.write_bulkhead = Bulkhead(
            name="write_operations",
            config=BulkheadConfig(
                max_concurrent=5,         # Writes are slower, fewer concurrent
                max_wait_time=10.0        # Longer wait for writes
            )
        )
        
        self.audit_bulkhead = Bulkhead(
            name="audit_operations",
            config=BulkheadConfig(
                max_concurrent=10,        # Audit operations
                max_wait_time=5.0
            )
        )
        
        # Graceful Draining
        # This enables zero-downtime deployments
        self.drainer = GracefulDrainer(
            name="api_server",
            config=GracefulDrainConfig(
                drain_timeout=30.0,        # Wait up to 30s for requests to finish
                check_interval=1.0        # Check every 1 second
            )
        )
        
        logger.info("✓ All resilience patterns initialized")
    
    def get_all_metrics(self) -> dict:
        """
        Get metrics from all resilience patterns.
        
        This is useful for monitoring and debugging. It collects metrics
        from all circuit breakers, retry budgets, bulkheads, and the drainer.
        
        Returns:
            Dictionary with metrics from all patterns
        
        Example:
            metrics = manager.get_all_metrics()
            print(f"DB circuit state: {metrics['circuit_breakers']['database']['state']}")
        """
        return {
            "circuit_breakers": {
                "database": self.db_circuit.get_metrics(),
                "redis": self.redis_circuit.get_metrics(),
                "mongodb": self.mongodb_circuit.get_metrics(),
            },
            "retry_budgets": {
                "database": self.db_retry_budget.get_metrics(),
                "redis": self.redis_retry_budget.get_metrics(),
            },
            "bulkheads": {
                "read_operations": self.read_bulkhead.get_metrics(),
                "write_operations": self.write_bulkhead.get_metrics(),
                "audit_operations": self.audit_bulkhead.get_metrics(),
            },
            "graceful_draining": self.drainer.get_metrics(),
        }


def get_resilience_manager() -> ResilienceManager:
    """
    Get or create the global resilience manager instance.
    
    This implements the singleton pattern - there's only one resilience
    manager for the entire application. All resilience patterns are created
    once and reused.
    
    Returns:
        ResilienceManager instance with all patterns initialized
    
    Example:
        manager = get_resilience_manager()
        result = manager.db_circuit.call(lambda: database.query(...))
    """
    global _resilience_manager
    
    if _resilience_manager is None:
        _resilience_manager = ResilienceManager()
    
    return _resilience_manager


def reset_resilience_manager() -> None:
    """
    Reset the resilience manager (for testing).
    
    This clears the global instance. Useful for testing when you want
    to create a fresh manager.
    """
    global _resilience_manager
    _resilience_manager = None
