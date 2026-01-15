# src/resilience/graceful_drain.py
# Graceful Draining Pattern Implementation
#
# WHAT IS GRACEFUL DRAINING?
# ==========================
# Graceful draining means stopping new requests while finishing in-flight
# requests before shutting down. It's like closing a restaurant: you stop
# seating new customers, but let existing customers finish their meals.
#
# WHY DO WE NEED IT?
# ===================
# Without graceful draining:
# - Server receives shutdown signal → immediately stops
# - In-flight requests are killed mid-processing
# - Users get errors, data might be corrupted
# - Load balancer sends requests to dead server
#
# With graceful draining:
# - Server receives shutdown signal → stops accepting new requests
# - In-flight requests complete normally
# - Load balancer removes server from rotation
# - Server shuts down cleanly after all requests finish
#
# DEPLOYMENT SCENARIO:
# ===================
# When deploying a new version:
# 1. New server starts up
# 2. Old server stops accepting new requests (draining starts)
# 3. Load balancer routes new requests to new server
# 4. Old server finishes in-flight requests
# 5. Old server shuts down cleanly
# 6. Zero downtime deployment!
#
# INTERVIEW TALKING POINTS:
# =========================
# - "Graceful draining ensures zero-downtime deployments"
# - "We track in-flight requests and wait for them to complete"
# - "During draining, we stop accepting new requests but finish existing ones"
# - "This prevents request failures during deployments"

import time
import threading
import signal
from dataclasses import dataclass
from typing import Optional, Callable
from contextlib import contextmanager

from logger import get_logger

logger = get_logger(__name__)


@dataclass
class GracefulDrainConfig:
    """
    Configuration for graceful draining behavior.
    
    These settings control how draining works.
    """
    # Maximum time to wait for in-flight requests to complete (in seconds)
    # Example: If drain_timeout=30, wait up to 30 seconds for requests to finish
    # After timeout, force shutdown
    drain_timeout: float = 30.0
    
    # How often to check if draining is complete (in seconds)
    # Example: If check_interval=1, check every 1 second
    check_interval: float = 1.0


class GracefulDrainer:
    """
    Graceful Draining Pattern Implementation.
    
    This class implements graceful draining to enable zero-downtime deployments.
    It tracks in-flight requests and ensures they complete before shutdown.
    
    HOW IT WORKS:
    =============
    1. Track number of in-flight requests
    2. When draining starts: Stop accepting new requests
    3. Wait for in-flight requests to complete
    4. Shutdown after all requests finish (or timeout)
    
    HOW TO USE:
    ===========
    
    # Create a graceful drainer
    drainer = GracefulDrainer(
        name="api_server",
        config=GracefulDrainConfig(drain_timeout=30.0)
    )
    
    # In your request handler, wrap with drainer
    @app.route('/api/v1/routes/resolve')
    def resolve_route():
        with drainer.process_request():
            # Your request handling code
            return resolve_endpoint(...)
    
    # On shutdown signal, start draining
    def shutdown_handler():
        drainer.start_draining()
        drainer.wait_for_drain()
        # Now safe to shutdown
    
    INTERVIEW EXPLANATION:
    ======================
    "We use graceful draining for zero-downtime deployments. When we receive
    a shutdown signal, we stop accepting new requests but continue processing
    in-flight requests. We track the number of active requests and wait for
    them to complete before shutting down. This ensures users don't experience
    errors during deployments."
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[GracefulDrainConfig] = None
    ):
        """
        Create a new graceful drainer.
        
        Args:
            name: Name of this drainer (for logging)
                Example: "api_server", "worker_process"
            config: Configuration for draining behavior
                If None, uses default configuration
        
        Example:
            # Graceful drainer for API server
            drainer = GracefulDrainer("api_server")
            
            # Graceful drainer with custom config
            drainer = GracefulDrainer(
                "api_server",
                config=GracefulDrainConfig(
                    drain_timeout=60.0,
                    check_interval=2.0
                )
            )
        """
        self.name = name
        self.config = config or GracefulDrainConfig()
        
        # Track draining state
        self._draining = False
        self._draining_started_at: Optional[float] = None
        
        # Track in-flight requests
        # This counter tracks how many requests are currently being processed
        self._in_flight_requests = 0
        
        # Thread lock for thread-safety
        self._lock = threading.Lock()
        
        # Event to signal when draining is complete
        # Other threads can wait on this event
        self._drain_complete = threading.Event()
        
        logger.info(
            f"Graceful drainer '{name}' created: "
            f"drain_timeout={self.config.drain_timeout}s"
        )
    
    def is_draining(self) -> bool:
        """
        Check if draining has started.
        
        When draining is active, new requests should be rejected.
        
        Returns:
            True if draining has started, False otherwise
        
        Example:
            if drainer.is_draining():
                return jsonify({"error": "Server is shutting down"}), 503
        """
        with self._lock:
            return self._draining
    
    def start_draining(self) -> None:
        """
        Start graceful draining process.
        
        This should be called when you receive a shutdown signal.
        After calling this:
        - is_draining() returns True
        - New requests should be rejected
        - In-flight requests continue processing
        - Call wait_for_drain() to wait for completion
        
        Example:
            def signal_handler(signum, frame):
                logger.info("Received shutdown signal")
                drainer.start_draining()
                drainer.wait_for_drain()
                # Now safe to shutdown
        """
        with self._lock:
            if self._draining:
                logger.warning(f"Graceful drainer '{self.name}' already draining")
                return
            
            self._draining = True
            self._draining_started_at = time.time()
            self._drain_complete.clear()
        
        logger.info(
            f"Graceful drainer '{self.name}': Draining started. "
            f"In-flight requests: {self._in_flight_requests}"
        )
    
    @contextmanager
    def process_request(self):
        """
        Context manager to track a request being processed.
        
        Use this to wrap your request handling code. It:
        1. Checks if draining (rejects if draining)
        2. Increments in-flight counter
        3. Processes request
        4. Decrements in-flight counter
        
        Usage:
            with drainer.process_request():
                # Your request handling code
                return handle_request()
        
        Raises:
            RuntimeError: If draining and trying to process new request
        
        Example:
            @app.route('/api/v1/routes/resolve')
            def resolve_route():
                try:
                    with drainer.process_request():
                        return resolve_endpoint(...)
                except RuntimeError as e:
                    # Draining, reject request
                    return jsonify({"error": "Server shutting down"}), 503
        """
        # Check if we're draining
        # If draining, reject new requests immediately
        if self.is_draining():
            logger.warning(
                f"Graceful drainer '{self.name}': Rejecting new request "
                f"(draining in progress, {self._in_flight_requests} in-flight)"
            )
            raise RuntimeError(
                f"Server '{self.name}' is draining and not accepting new requests"
            )
        
        # Increment in-flight counter
        with self._lock:
            self._in_flight_requests += 1
        
        logger.debug(
            f"Graceful drainer '{self.name}': Request started "
            f"({self._in_flight_requests} in-flight)"
        )
        
        try:
            # Process the request
            yield
            
        finally:
            # Always decrement counter when done
            # This happens even if request fails
            with self._lock:
                self._in_flight_requests -= 1
                
                # If draining and no more in-flight requests, signal completion
                if self._draining and self._in_flight_requests == 0:
                    self._drain_complete.set()
                    logger.info(
                        f"Graceful drainer '{self.name}': All requests completed, "
                        f"draining finished"
                    )
            
            logger.debug(
                f"Graceful drainer '{self.name}': Request completed "
                f"({self._in_flight_requests} in-flight)"
            )
    
    def wait_for_drain(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all in-flight requests to complete.
        
        This blocks until:
        - All in-flight requests complete, OR
        - Timeout is reached
        
        Call this after start_draining() to wait for completion.
        
        Args:
            timeout: Maximum time to wait (in seconds)
                If None, uses config.drain_timeout
        
        Returns:
            True if all requests completed, False if timeout
        
        Example:
            drainer.start_draining()
            if drainer.wait_for_drain():
                logger.info("All requests completed, safe to shutdown")
            else:
                logger.warning("Timeout waiting for requests, forcing shutdown")
        """
        timeout = timeout or self.config.drain_timeout
        
        if not self._draining:
            logger.warning(
                f"Graceful drainer '{self.name}': wait_for_drain() called "
                f"but not draining"
            )
            return True
        
        logger.info(
            f"Graceful drainer '{self.name}': Waiting for {self._in_flight_requests} "
            f"in-flight requests to complete (timeout: {timeout}s)"
        )
        
        start_time = time.time()
        
        # Wait for drain to complete, checking periodically
        while True:
            # Check if all requests completed
            with self._lock:
                if self._in_flight_requests == 0:
                    elapsed = time.time() - start_time
                    logger.info(
                        f"Graceful drainer '{self.name}': All requests completed "
                        f"in {elapsed:.2f}s"
                    )
                    return True
            
            # Check if timeout exceeded
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                with self._lock:
                    remaining = self._in_flight_requests
                
                logger.warning(
                    f"Graceful drainer '{self.name}': Timeout ({timeout}s) exceeded. "
                    f"{remaining} requests still in-flight. Forcing shutdown."
                )
                return False
            
            # Wait a bit before checking again
            time.sleep(self.config.check_interval)
    
    def get_metrics(self) -> dict:
        """
        Get metrics about graceful draining status.
        
        Useful for monitoring and debugging.
        
        Returns:
            Dictionary with metrics:
            - name: Drainer name
            - is_draining: Whether draining is active
            - in_flight_requests: Number of requests currently processing
            - draining_started_at: When draining started (or None)
            - drain_timeout: Maximum time to wait
        
        Example:
            metrics = drainer.get_metrics()
            if metrics['is_draining']:
                print(f"Draining: {metrics['in_flight_requests']} requests remaining")
        """
        with self._lock:
            draining_elapsed = None
            if self._draining and self._draining_started_at:
                draining_elapsed = time.time() - self._draining_started_at
            
            return {
                "name": self.name,
                "is_draining": self._draining,
                "in_flight_requests": self._in_flight_requests,
                "draining_started_at": self._draining_started_at,
                "draining_elapsed_seconds": draining_elapsed,
                "drain_timeout": self.config.drain_timeout,
            }
    
    def get_in_flight_count(self) -> int:
        """
        Get current number of in-flight requests.
        
        Returns:
            Number of requests currently being processed
        
        Example:
            if drainer.get_in_flight_count() > 100:
                logger.warning("High number of in-flight requests")
        """
        with self._lock:
            return self._in_flight_requests
