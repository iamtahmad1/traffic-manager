# src/resilience/bulkhead.py
# Bulkhead Pattern Implementation
#
# WHAT IS A BULKHEAD?
# ====================
# A bulkhead is like the watertight compartments in a ship. If one compartment
# floods, the others stay dry. In software, bulkheads isolate resources so
# if one part fails, other parts keep working.
#
# WHY DO WE NEED IT?
# ===================
# Without bulkheads, one failing operation can consume all resources:
# - Database query is slow → uses all connection pool → other queries wait
# - One tenant's requests are slow → blocks all other tenants
# - One API endpoint is slow → blocks all other endpoints
#
# With bulkheads:
# - Each operation type has its own resource pool
# - If one pool is exhausted, others still work
# - Failures are isolated and don't cascade
#
# REAL-WORLD EXAMPLE:
# ===================
# Imagine you have:
# - Read operations (fast, frequent)
# - Write operations (slow, infrequent)
# - Admin operations (very slow, rare)
#
# Without bulkhead:
# - Admin operation uses all connections
# - Read operations wait → user experience degrades
# - Write operations wait → system appears frozen
#
# With bulkhead:
# - Read pool: 20 connections (for fast reads)
# - Write pool: 5 connections (for writes)
# - Admin pool: 2 connections (for admin)
# - Admin operation can't block reads or writes!
#
# INTERVIEW TALKING POINTS:
# =========================
# - "Bulkheads isolate resources to prevent cascading failures"
# - "Each operation type has its own resource pool"
# - "If one pool is exhausted, other operations continue normally"
# - "This provides fault isolation and predictable performance"

import threading
import time
from dataclasses import dataclass
from typing import Optional, Callable, Any
from contextlib import contextmanager

from logger import get_logger

logger = get_logger(__name__)


@dataclass
class BulkheadConfig:
    """
    Configuration for bulkhead behavior.
    
    These settings control resource isolation.
    """
    # Maximum number of concurrent operations allowed
    # Example: If max_concurrent=10, only 10 operations can run at once
    max_concurrent: int = 10
    
    # Maximum time to wait for a slot (in seconds)
    # Example: If max_wait_time=5, wait up to 5 seconds for a slot
    # If timeout, raise BulkheadFullError
    max_wait_time: float = 5.0


class BulkheadFullError(Exception):
    """
    Exception raised when bulkhead is full (no slots available).
    
    This means all resource slots are in use and we can't start a new
    operation. We should fail fast instead of waiting indefinitely.
    """
    pass


class Bulkhead:
    """
    Bulkhead Pattern Implementation.
    
    This class implements the bulkhead pattern to isolate resources
    and prevent one type of operation from consuming all resources.
    
    HOW IT WORKS:
    =============
    1. Track how many operations are currently running
    2. Before starting an operation, acquire a "slot"
    3. If no slots available, wait (up to max_wait_time)
    4. After operation completes, release the slot
    5. This limits concurrent operations and isolates failures
    
    HOW TO USE:
    ===========
    
    # Create a bulkhead for read operations
    read_bulkhead = Bulkhead(
        name="read_operations",
        config=BulkheadConfig(max_concurrent=20)
    )
    
    # Use it to limit concurrent operations
    with read_bulkhead.acquire():
        # This code runs with bulkhead protection
        # Only max_concurrent operations can run at once
        result = database.query("SELECT ...")
    
    # Or use as a decorator
    @read_bulkhead.protect
    def read_from_db():
        return database.query("SELECT ...")
    
    INTERVIEW EXPLANATION:
    ======================
    "We use bulkheads to isolate resources and prevent cascading failures.
    Each operation type (reads, writes, admin) has its own resource pool
    with a maximum concurrency limit. If one pool is exhausted, other
    operations continue normally. This provides fault isolation and ensures
    that one slow operation type doesn't block others."
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[BulkheadConfig] = None
    ):
        """
        Create a new bulkhead.
        
        Args:
            name: Name of this bulkhead (for logging)
                Example: "read_operations", "write_operations", "admin_operations"
            config: Configuration for bulkhead behavior
                If None, uses default configuration
        
        Example:
            # Bulkhead for read operations
            read_bulkhead = Bulkhead("read_operations")
            
            # Bulkhead with custom config
            write_bulkhead = Bulkhead(
                "write_operations",
                config=BulkheadConfig(
                    max_concurrent=5,
                    max_wait_time=10.0
                )
            )
        """
        self.name = name
        self.config = config or BulkheadConfig()
        
        # Semaphore to track available slots
        # Semaphore is like a counter: acquire() decrements, release() increments
        # If counter is 0, acquire() blocks until someone releases
        self._semaphore = threading.Semaphore(self.config.max_concurrent)
        
        # Track current usage for metrics
        self._current_usage = 0
        self._total_operations = 0
        self._rejected_operations = 0
        
        # Thread lock for thread-safety
        self._lock = threading.Lock()
        
        logger.info(
            f"Bulkhead '{name}' created: "
            f"max_concurrent={self.config.max_concurrent}, "
            f"max_wait_time={self.config.max_wait_time}s"
        )
    
    @contextmanager
    def acquire(self):
        """
        Acquire a slot in the bulkhead (context manager).
        
        This is the main way to use a bulkhead. It ensures only
        max_concurrent operations run at once.
        
        Usage:
            with bulkhead.acquire():
                # Your operation here
                result = expensive_operation()
        
        Raises:
            BulkheadFullError: If no slot available and wait timeout exceeded
        
        Example:
            # Limit concurrent database queries
            with db_bulkhead.acquire():
                result = database.query("SELECT ...")
        """
        # Try to acquire a slot (with timeout)
        acquired = self._semaphore.acquire(timeout=self.config.max_wait_time)
        
        if not acquired:
            # Timeout - no slot available
            with self._lock:
                self._rejected_operations += 1
            
            logger.warning(
                f"Bulkhead '{self.name}' full: "
                f"waited {self.config.max_wait_time}s, no slot available. "
                f"Current usage: {self._current_usage}/{self.config.max_concurrent}"
            )
            raise BulkheadFullError(
                f"Bulkhead '{self.name}' is full. "
                f"Max {self.config.max_concurrent} concurrent operations allowed. "
                f"Wait timeout {self.config.max_wait_time}s exceeded."
            )
        
        # Got a slot! Track usage
        with self._lock:
            self._current_usage += 1
            self._total_operations += 1
        
        logger.debug(
            f"Bulkhead '{self.name}': Acquired slot "
            f"({self._current_usage}/{self.config.max_concurrent} in use)"
        )
        
        try:
            # Execute the operation
            yield
            
        finally:
            # Always release the slot when done
            # This happens even if the operation fails
            self._semaphore.release()
            
            with self._lock:
                self._current_usage -= 1
            
            logger.debug(
                f"Bulkhead '{self.name}': Released slot "
                f"({self._current_usage}/{self.config.max_concurrent} in use)"
            )
    
    def protect(self, func: Callable[[], Any]) -> Callable[[], Any]:
        """
        Decorator to protect a function with bulkhead.
        
        This is a convenience method to use bulkhead as a decorator.
        
        Usage:
            @bulkhead.protect
            def my_function():
                return expensive_operation()
        
        Example:
            @read_bulkhead.protect
            def read_from_database():
                return database.query("SELECT ...")
        """
        def wrapper(*args, **kwargs):
            with self.acquire():
                return func(*args, **kwargs)
        
        return wrapper
    
    def get_metrics(self) -> dict:
        """
        Get metrics about bulkhead usage.
        
        Useful for monitoring and debugging.
        
        Returns:
            Dictionary with metrics:
            - name: Bulkhead name
            - current_usage: Currently running operations
            - max_concurrent: Maximum allowed concurrent operations
            - utilization: Percentage of capacity used
            - total_operations: Total operations ever executed
            - rejected_operations: Operations rejected (timeout)
        
        Example:
            metrics = bulkhead.get_metrics()
            if metrics['utilization'] > 80:
                alert("Bulkhead almost full!")
        """
        with self._lock:
            utilization = (
                (self._current_usage / self.config.max_concurrent * 100)
                if self.config.max_concurrent > 0 else 0
            )
            
            return {
                "name": self.name,
                "current_usage": self._current_usage,
                "max_concurrent": self.config.max_concurrent,
                "utilization": utilization,
                "total_operations": self._total_operations,
                "rejected_operations": self._rejected_operations,
                "available_slots": self.config.max_concurrent - self._current_usage,
            }
    
    def get_current_usage(self) -> int:
        """
        Get current number of operations using the bulkhead.
        
        Returns:
            Number of operations currently running
        
        Example:
            if bulkhead.get_current_usage() > 10:
                logger.warning("High bulkhead usage")
        """
        with self._lock:
            return self._current_usage
