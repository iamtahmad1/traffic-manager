# src/resilience/circuit_breaker.py
# Circuit Breaker Pattern Implementation
#
# WHAT IS A CIRCUIT BREAKER?
# ===========================
# A circuit breaker is like an electrical circuit breaker in your house.
# When too many failures happen, it "opens" (trips) to prevent damage.
# In software, it stops calling a failing service to prevent cascading failures.
#
# WHY DO WE NEED IT?
# ===================
# Imagine your service calls a database that's slow or failing:
# - Without circuit breaker: Every request waits, times out, fails
# - With circuit breaker: After detecting failures, immediately return error
#   (fast failure) instead of waiting for timeout
#
# This prevents:
# 1. Cascading failures (one service failure doesn't bring down everything)
# 2. Resource exhaustion (threads waiting on slow services)
# 3. User experience degradation (fast errors vs slow timeouts)
#
# HOW IT WORKS:
# =============
# Circuit breaker has 3 states:
# 1. CLOSED (normal): Calling the service, tracking failures
# 2. OPEN (tripped): Not calling service, immediately failing
# 3. HALF-OPEN (testing): Trying one request to see if service recovered
#
# State transitions:
# CLOSED → [too many failures] → OPEN
# OPEN → [timeout period] → HALF-OPEN
# HALF-OPEN → [success] → CLOSED
# HALF-OPEN → [failure] → OPEN
#
# INTERVIEW TALKING POINTS:
# =========================
# - "We use circuit breakers to prevent cascading failures"
# - "Fast failure is better than slow failure for user experience"
# - "Circuit breakers auto-recover when services come back"
# - "We track failure rates and trip when threshold is exceeded"

import time
import threading
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass, field

from logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """
    Circuit breaker states.
    
    Think of this like a light switch:
    - CLOSED: Switch is ON, current flows (calling service)
    - OPEN: Switch is OFF, no current (not calling service)
    - HALF_OPEN: Switch is flickering, testing if it works
    """
    CLOSED = "closed"      # Normal operation, calling service
    OPEN = "open"          # Tripped, not calling service
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for circuit breaker behavior.
    
    These settings control when the circuit trips and how it recovers.
    """
    # How many failures before opening the circuit
    # Example: If failure_threshold=5, circuit opens after 5 failures
    failure_threshold: int = 5
    
    # How long (in seconds) to stay OPEN before trying HALF_OPEN
    # Example: If timeout_seconds=60, wait 60 seconds before testing recovery
    timeout_seconds: int = 60
    
    # Time window (in seconds) for counting failures
    # Example: If window_seconds=60, only count failures in last 60 seconds
    # This prevents old failures from keeping circuit open
    window_seconds: int = 60
    
    # Minimum number of calls before circuit can open
    # Example: If min_calls=10, need at least 10 calls before opening
    # This prevents opening on just a few failures
    min_calls: int = 10


class CircuitOpenError(Exception):
    """
    Exception raised when circuit breaker is OPEN.
    
    This means the service is known to be failing, so we're not even trying
    to call it. We fail fast instead of waiting for a timeout.
    """
    pass


class CircuitBreaker:
    """
    Circuit Breaker Pattern Implementation.
    
    This class implements the circuit breaker pattern to prevent cascading
    failures when calling external services (database, cache, APIs, etc.).
    
    HOW TO USE:
    ===========
    
    # Create a circuit breaker for database calls
    db_circuit = CircuitBreaker(
        name="database",
        config=CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=60
        )
    )
    
    # Use it to protect a function call
    try:
        result = db_circuit.call(lambda: database.query("SELECT ..."))
    except CircuitOpenError:
        # Circuit is open, service is failing
        # Return cached data or error immediately
        return fallback_data
    
    REAL-WORLD EXAMPLE:
    ===================
    Imagine you're calling a payment service:
    
    Without circuit breaker:
    - Request 1: Wait 30s, timeout, fail
    - Request 2: Wait 30s, timeout, fail
    - Request 3: Wait 30s, timeout, fail
    - ... (all requests wait and fail)
    
    With circuit breaker:
    - Request 1-5: Wait, timeout, fail (circuit learning)
    - Request 6+: Circuit OPEN, fail immediately (no wait!)
    - After 60s: Try one request (HALF_OPEN)
    - If success: Circuit CLOSED, normal operation
    - If failure: Circuit OPEN again
    
    INTERVIEW EXPLANATION:
    ======================
    "We use circuit breakers to protect against cascading failures. When
    a downstream service starts failing, the circuit breaker detects this
    pattern and 'opens' the circuit. Once open, we fail fast instead of
    waiting for timeouts, which improves user experience and prevents
    resource exhaustion. The circuit automatically tests recovery by
    entering a half-open state periodically."
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Create a new circuit breaker.
        
        Args:
            name: Name of this circuit breaker (for logging)
                Example: "database", "redis", "payment-api"
            config: Configuration for circuit behavior
                If None, uses default configuration
        
        Example:
            # Circuit breaker for database calls
            db_circuit = CircuitBreaker("database")
            
            # Circuit breaker with custom config
            api_circuit = CircuitBreaker(
                "payment-api",
                config=CircuitBreakerConfig(
                    failure_threshold=10,
                    timeout_seconds=30
                )
            )
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # Current state of the circuit
        # Starts CLOSED (normal operation)
        self.state = CircuitState.CLOSED
        
        # Track failures and successes
        # We use a list of timestamps to track failures in the time window
        self.failure_timestamps: list[float] = []
        self.success_count = 0
        self.total_calls = 0
        
        # When did we last open the circuit?
        # Used to determine when to try HALF_OPEN
        self.last_open_time: Optional[float] = None
        
        # Thread lock to make this thread-safe
        # Multiple threads can use the same circuit breaker safely
        self._lock = threading.Lock()
        
        logger.info(
            f"Circuit breaker '{name}' created: "
            f"failure_threshold={self.config.failure_threshold}, "
            f"timeout={self.config.timeout_seconds}s"
        )
    
    def call(self, func: Callable[[], Any]) -> Any:
        """
        Execute a function with circuit breaker protection.
        
        This is the main method you use. It wraps your function call
        with circuit breaker logic:
        1. Check if circuit is open (fail fast if so)
        2. Try calling the function
        3. Track success/failure
        4. Update circuit state based on results
        
        Args:
            func: Function to call (must take no arguments)
                Example: lambda: database.query("SELECT ...")
        
        Returns:
            Result from the function call
        
        Raises:
            CircuitOpenError: If circuit is OPEN (service is failing)
            Exception: Any exception raised by the function
        
        Example:
            # Protect a database query
            try:
                result = db_circuit.call(lambda: conn.execute("SELECT ..."))
            except CircuitOpenError:
                # Circuit is open, use fallback
                return cached_data
            except DatabaseError as e:
                # Database error, but circuit might still be closed
                raise
        """
        with self._lock:
            # Check current state and update if needed
            self._update_state()
            
            # If circuit is OPEN, fail fast
            # Don't even try to call the service
            if self.state == CircuitState.OPEN:
                logger.warning(
                    f"Circuit breaker '{self.name}' is OPEN, failing fast. "
                    f"Last opened: {time.time() - (self.last_open_time or 0):.1f}s ago"
                )
                raise CircuitOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service is failing, not attempting call."
                )
            
            # If circuit is HALF_OPEN, we're testing recovery
            # This is a test call to see if service recovered
            if self.state == CircuitState.HALF_OPEN:
                logger.info(
                    f"Circuit breaker '{self.name}' is HALF_OPEN, "
                    f"testing if service recovered"
                )
        
        # Try calling the function
        # We do this outside the lock to avoid blocking other threads
        try:
            result = func()
            
            # Success! Record it and update state
            with self._lock:
                self._record_success()
            
            return result
            
        except Exception as e:
            # Failure! Record it and update state
            with self._lock:
                self._record_failure()
            
            # Re-raise the original exception
            # The caller can handle it appropriately
            raise
    
    def _update_state(self) -> None:
        """
        Update circuit breaker state based on current conditions.
        
        This is called before each operation to check if we should:
        - Stay in current state
        - Transition from OPEN to HALF_OPEN (timeout expired)
        - Transition from HALF_OPEN to CLOSED (service recovered)
        
        State transitions:
        - OPEN → HALF_OPEN: If timeout period has passed
        - HALF_OPEN → CLOSED: If we just had a success (handled in _record_success)
        - HALF_OPEN → OPEN: If we just had a failure (handled in _record_failure)
        """
        now = time.time()
        
        # Clean up old failures outside the time window
        # Only count failures in the last window_seconds
        cutoff = now - self.config.window_seconds
        self.failure_timestamps = [
            ts for ts in self.failure_timestamps if ts > cutoff
        ]
        
        # If circuit is OPEN, check if timeout has passed
        # If so, transition to HALF_OPEN to test recovery
        if self.state == CircuitState.OPEN:
            if self.last_open_time and (now - self.last_open_time) >= self.config.timeout_seconds:
                logger.info(
                    f"Circuit breaker '{self.name}': OPEN → HALF_OPEN "
                    f"(timeout expired, testing recovery)"
                )
                self.state = CircuitState.HALF_OPEN
                # Reset counters for half-open test
                self.success_count = 0
                self.failure_timestamps = []
    
    def _record_success(self) -> None:
        """
        Record a successful call and update circuit state.
        
        When a call succeeds:
        - If HALF_OPEN: Transition to CLOSED (service recovered!)
        - If CLOSED: Just increment success count
        - Clear failure history (success resets failure tracking)
        """
        self.total_calls += 1
        self.success_count += 1
        
        # If we're in HALF_OPEN and got a success, service recovered!
        # Transition back to CLOSED (normal operation)
        if self.state == CircuitState.HALF_OPEN:
            logger.info(
                f"Circuit breaker '{self.name}': HALF_OPEN → CLOSED "
                f"(service recovered!)"
            )
            self.state = CircuitState.CLOSED
            self.failure_timestamps = []  # Clear failure history
            self.last_open_time = None
        
        # If we're in CLOSED, success clears recent failures
        # This helps the circuit recover from transient failures
        elif self.state == CircuitState.CLOSED:
            # Clear failures older than window
            # Recent success means service is working
            pass  # Already cleaned in _update_state
    
    def _record_failure(self) -> None:
        """
        Record a failed call and update circuit state.
        
        When a call fails:
        - Record the failure timestamp
        - If CLOSED: Check if we should open (too many failures)
        - If HALF_OPEN: Open immediately (service still failing)
        """
        now = time.time()
        self.total_calls += 1
        
        # Record this failure
        self.failure_timestamps.append(now)
        
        # If we're in HALF_OPEN and got a failure, service is still down
        # Transition back to OPEN immediately
        if self.state == CircuitState.HALF_OPEN:
            logger.warning(
                f"Circuit breaker '{self.name}': HALF_OPEN → OPEN "
                f"(service still failing)"
            )
            self.state = CircuitState.OPEN
            self.last_open_time = now
        
        # If we're in CLOSED, check if we should open
        elif self.state == CircuitState.CLOSED:
            # Only open if we have enough calls and enough failures
            # This prevents opening on just a few failures
            if (self.total_calls >= self.config.min_calls and
                len(self.failure_timestamps) >= self.config.failure_threshold):
                
                logger.warning(
                    f"Circuit breaker '{self.name}': CLOSED → OPEN "
                    f"({len(self.failure_timestamps)} failures in last "
                    f"{self.config.window_seconds}s, threshold={self.config.failure_threshold})"
                )
                self.state = CircuitState.OPEN
                self.last_open_time = now
    
    def get_state(self) -> CircuitState:
        """
        Get the current state of the circuit breaker.
        
        Returns:
            Current state (CLOSED, OPEN, or HALF_OPEN)
        
        Example:
            state = db_circuit.get_state()
            if state == CircuitState.OPEN:
                print("Database is failing, using cache")
        """
        with self._lock:
            self._update_state()
            return self.state
    
    def get_metrics(self) -> dict:
        """
        Get metrics about circuit breaker performance.
        
        Useful for monitoring and debugging.
        
        Returns:
            Dictionary with metrics:
            - state: Current state
            - total_calls: Total number of calls
            - failure_count: Number of failures in window
            - success_count: Number of successes
            - failure_rate: Percentage of failures
            - last_open_time: When circuit last opened (or None)
        
        Example:
            metrics = db_circuit.get_metrics()
            print(f"Failure rate: {metrics['failure_rate']:.1f}%")
        """
        with self._lock:
            self._update_state()
            
            failure_count = len(self.failure_timestamps)
            failure_rate = (
                (failure_count / self.total_calls * 100)
                if self.total_calls > 0 else 0
            )
            
            return {
                "name": self.name,
                "state": self.state.value,
                "total_calls": self.total_calls,
                "failure_count": failure_count,
                "success_count": self.success_count,
                "failure_rate": failure_rate,
                "last_open_time": self.last_open_time,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "timeout_seconds": self.config.timeout_seconds,
                    "window_seconds": self.config.window_seconds,
                    "min_calls": self.config.min_calls,
                }
            }
    
    def reset(self) -> None:
        """
        Manually reset the circuit breaker to CLOSED state.
        
        This is useful for:
        - Testing
        - Manual recovery after fixing a service
        - Administrative operations
        
        WARNING: Only use this if you're sure the service is fixed!
        Normally, the circuit breaker should auto-recover.
        
        Example:
            # After fixing the database, manually reset
            db_circuit.reset()
        """
        with self._lock:
            logger.info(f"Circuit breaker '{self.name}' manually reset to CLOSED")
            self.state = CircuitState.CLOSED
            self.failure_timestamps = []
            self.success_count = 0
            self.last_open_time = None
