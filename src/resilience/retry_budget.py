# src/resilience/retry_budget.py
# Retry Budget Pattern Implementation
#
# WHAT IS A RETRY BUDGET?
# ========================
# A retry budget limits how many retries you can do in a time period.
# Think of it like a spending budget - you have a limited amount of "retry money"
# and once you spend it, you can't retry anymore until the budget resets.
#
# WHY DO WE NEED IT?
# ===================
# Without retry budgets, retries can make problems worse:
# - Service is slow → everyone retries → more load → service gets slower
# - This creates a "retry storm" that amplifies the problem
#
# With retry budgets:
# - Limit total retries across all requests
# - Prevent retry storms
# - Fail fast when budget is exhausted
#
# REAL-WORLD EXAMPLE:
# ===================
# Imagine a payment service is slow (500ms response time):
#
# Without retry budget:
# - 1000 requests come in
# - Each retries 3 times = 3000 total requests
# - Service gets overwhelmed, response time becomes 5 seconds
# - Everyone retries more → death spiral
#
# With retry budget (100 retries per minute):
# - 1000 requests come in
# - First 100 get retries, rest fail fast
# - Service load is manageable
# - Response time stays reasonable
#
# INTERVIEW TALKING POINTS:
# =========================
# - "Retry budgets prevent retry storms that amplify failures"
# - "We track retry attempts in a time window and limit total retries"
# - "When budget is exhausted, we fail fast instead of retrying"
# - "This prevents cascading failures from retry amplification"

import time
import threading
from dataclasses import dataclass, field
from typing import Optional
from collections import deque

from logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetryBudgetConfig:
    """
    Configuration for retry budget behavior.
    
    These settings control how many retries are allowed.
    """
    # Maximum number of retries allowed in the time window
    # Example: If max_retries=100, allow up to 100 retries per window
    max_retries: int = 100
    
    # Time window in seconds for tracking retries
    # Example: If window_seconds=60, track retries in last 60 seconds
    window_seconds: int = 60
    
    # Minimum time between retries (in seconds)
    # Example: If min_retry_interval=0.1, wait at least 0.1s between retries
    # This prevents rapid-fire retries
    min_retry_interval: float = 0.1


class RetryBudgetExceeded(Exception):
    """
    Exception raised when retry budget is exhausted.
    
    This means we've used up all our retry "budget" and should fail fast
    instead of retrying more.
    """
    pass


class RetryBudget:
    """
    Retry Budget Pattern Implementation.
    
    This class implements the retry budget pattern to prevent retry storms
    that can amplify failures and overwhelm services.
    
    HOW IT WORKS:
    =============
    1. Track all retry attempts in a time window
    2. Count retries and compare to budget
    3. If budget available: Allow retry
    4. If budget exhausted: Fail fast
    
    HOW TO USE:
    ===========
    
    # Create a retry budget
    retry_budget = RetryBudget(
        name="database",
        config=RetryBudgetConfig(
            max_retries=100,
            window_seconds=60
        )
    )
    
    # Before retrying, check budget
    for attempt in range(max_attempts):
        try:
            result = database.query("SELECT ...")
            break
        except DatabaseError:
            # Check if we have budget for a retry
            if not retry_budget.can_retry():
                raise RetryBudgetExceeded("Retry budget exhausted")
            
            # Record that we're retrying
            retry_budget.record_retry()
            
            # Wait before retrying
            time.sleep(backoff_time)
    
    INTERVIEW EXPLANATION:
    ======================
    "We use retry budgets to prevent retry storms. When a service starts
    failing, every request retries multiple times, which multiplies the
    load on the failing service. Retry budgets limit the total number of
    retries across all requests in a time window. Once the budget is
    exhausted, we fail fast instead of retrying, which prevents amplifying
    the failure."
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[RetryBudgetConfig] = None
    ):
        """
        Create a new retry budget.
        
        Args:
            name: Name of this retry budget (for logging)
                Example: "database", "payment-api"
            config: Configuration for retry budget behavior
                If None, uses default configuration
        
        Example:
            # Retry budget for database calls
            db_budget = RetryBudget("database")
            
            # Retry budget with custom config
            api_budget = RetryBudget(
                "payment-api",
                config=RetryBudgetConfig(
                    max_retries=50,
                    window_seconds=30
                )
            )
        """
        self.name = name
        self.config = config or RetryBudgetConfig()
        
        # Track retry attempts with timestamps
        # We use a deque (double-ended queue) for efficient time-window tracking
        # Each entry is a timestamp of when a retry happened
        self.retry_timestamps: deque = deque()
        
        # Total retries ever recorded (for metrics)
        self.total_retries = 0
        
        # Thread lock for thread-safety
        # Multiple threads can use the same retry budget safely
        self._lock = threading.Lock()
        
        logger.info(
            f"Retry budget '{name}' created: "
            f"max_retries={self.config.max_retries}, "
            f"window={self.config.window_seconds}s"
        )
    
    def can_retry(self) -> bool:
        """
        Check if we have budget available for a retry.
        
        This method checks:
        1. Clean up old retries outside the time window
        2. Count current retries in the window
        3. Compare to max_retries budget
        4. Return True if budget available, False if exhausted
        
        Returns:
            True if retry is allowed, False if budget is exhausted
        
        Example:
            if retry_budget.can_retry():
                retry_budget.record_retry()
                # Do retry
            else:
                # Budget exhausted, fail fast
                raise RetryBudgetExceeded()
        """
        with self._lock:
            now = time.time()
            cutoff = now - self.config.window_seconds
            
            # Remove retries outside the time window
            # Only count retries in the last window_seconds
            while self.retry_timestamps and self.retry_timestamps[0] < cutoff:
                self.retry_timestamps.popleft()
            
            # Check if we're under budget
            current_retries = len(self.retry_timestamps)
            can_retry = current_retries < self.config.max_retries
            
            if not can_retry:
                logger.warning(
                    f"Retry budget '{self.name}' exhausted: "
                    f"{current_retries}/{self.config.max_retries} retries "
                    f"in last {self.config.window_seconds}s"
                )
            
            return can_retry
    
    def record_retry(self) -> None:
        """
        Record that a retry is being attempted.
        
        Call this BEFORE doing a retry to track it in the budget.
        This increments the retry count for the current time window.
        
        Raises:
            RetryBudgetExceeded: If budget is already exhausted
        
        Example:
            try:
                result = service.call()
            except ServiceError:
                if not retry_budget.can_retry():
                    raise RetryBudgetExceeded()
                
                retry_budget.record_retry()  # Record before retrying
                result = service.call()  # Retry
        """
        with self._lock:
            # Check budget again (might have changed since can_retry())
            if not self.can_retry():
                raise RetryBudgetExceeded(
                    f"Retry budget '{self.name}' exhausted. "
                    f"Max {self.config.max_retries} retries per "
                    f"{self.config.window_seconds}s window."
                )
            
            # Record this retry
            now = time.time()
            self.retry_timestamps.append(now)
            self.total_retries += 1
            
            logger.debug(
                f"Retry budget '{self.name}': Recorded retry "
                f"({len(self.retry_timestamps)}/{self.config.max_retries} in window)"
            )
    
    def get_metrics(self) -> dict:
        """
        Get metrics about retry budget usage.
        
        Useful for monitoring and debugging.
        
        Returns:
            Dictionary with metrics:
            - name: Budget name
            - current_retries: Retries in current window
            - max_retries: Maximum allowed retries
            - budget_used: Percentage of budget used
            - total_retries: Total retries ever recorded
            - window_seconds: Time window size
        
        Example:
            metrics = retry_budget.get_metrics()
            if metrics['budget_used'] > 80:
                alert("Retry budget almost exhausted!")
        """
        with self._lock:
            now = time.time()
            cutoff = now - self.config.window_seconds
            
            # Clean up old retries
            while self.retry_timestamps and self.retry_timestamps[0] < cutoff:
                self.retry_timestamps.popleft()
            
            current_retries = len(self.retry_timestamps)
            budget_used = (
                (current_retries / self.config.max_retries * 100)
                if self.config.max_retries > 0 else 0
            )
            
            return {
                "name": self.name,
                "current_retries": current_retries,
                "max_retries": self.config.max_retries,
                "budget_used": budget_used,
                "total_retries": self.total_retries,
                "window_seconds": self.config.window_seconds,
                "budget_remaining": self.config.max_retries - current_retries,
            }
    
    def reset(self) -> None:
        """
        Manually reset the retry budget.
        
        Clears all retry history. Useful for testing or manual recovery.
        
        Example:
            # After fixing a service, reset the budget
            retry_budget.reset()
        """
        with self._lock:
            logger.info(f"Retry budget '{self.name}' manually reset")
            self.retry_timestamps.clear()
            self.total_retries = 0
