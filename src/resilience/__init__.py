# src/resilience/__init__.py
# Resilience patterns module
# Provides production-ready patterns for handling failures gracefully

from resilience.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitBreakerConfig
from resilience.retry_budget import RetryBudget, RetryBudgetExceeded, RetryBudgetConfig
from resilience.bulkhead import Bulkhead, BulkheadFullError, BulkheadConfig
from resilience.graceful_drain import GracefulDrainer, GracefulDrainConfig
from resilience.manager import get_resilience_manager, ResilienceManager

__all__ = [
    "CircuitBreaker",
    "CircuitOpenError",
    "CircuitBreakerConfig",
    "RetryBudget",
    "RetryBudgetExceeded",
    "RetryBudgetConfig",
    "Bulkhead",
    "BulkheadFullError",
    "BulkheadConfig",
    "GracefulDrainer",
    "GracefulDrainConfig",
    "get_resilience_manager",
    "ResilienceManager",
]
