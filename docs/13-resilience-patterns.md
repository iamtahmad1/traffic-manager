# Resilience Patterns - Complete Guide for Junior Engineers

This document explains advanced resilience patterns used in production systems. These patterns are essential for building systems that handle failures gracefully and remain available under stress.

**Target Audience**: Junior engineers preparing for senior/principal engineer interviews.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Circuit Breaker Pattern](#circuit-breaker-pattern)
3. [Retry Budget Pattern](#retry-budget-pattern)
4. [Bulkhead Pattern](#bulkhead-pattern)
5. [Graceful Draining Pattern](#graceful-draining-pattern)
6. [How They Work Together](#how-they-work-together)
7. [Interview Preparation](#interview-preparation)

---

## Introduction

### What Are Resilience Patterns?

**Resilience patterns** are design techniques that help systems handle failures gracefully. They prevent small failures from becoming big problems.

### Why Do We Need Them?

In production systems, failures are **inevitable**:
- Services go down
- Networks have latency spikes
- Databases get overloaded
- Deployments happen

Without resilience patterns:
- One failure can cascade to everything
- Retries can amplify problems
- Resources get exhausted
- Deployments cause downtime

With resilience patterns:
- Failures are isolated
- Retries are controlled
- Resources are protected
- Deployments are zero-downtime

### The Four Patterns

1. **Circuit Breaker**: Stop calling failing services
2. **Retry Budget**: Limit total retries
3. **Bulkhead**: Isolate resources
4. **Graceful Draining**: Finish requests before shutdown

---

## Circuit Breaker Pattern

### What Is It?

A **circuit breaker** is like an electrical circuit breaker. When too many failures happen, it "opens" (trips) to prevent damage.

**Real-world analogy**: Your house's circuit breaker trips when there's an electrical problem, preventing fires.

### Why Do We Need It?

**Problem**: When a service is failing, every request:
1. Waits for timeout (slow)
2. Fails after timeout
3. Wastes resources (threads, connections)
4. Degrades user experience

**Solution**: Circuit breaker detects failures and "opens" the circuit:
1. Immediately fails (fast failure)
2. Doesn't waste resources
3. Better user experience
4. Prevents cascading failures

### How It Works

Circuit breaker has **3 states**:

```
CLOSED (normal) → [too many failures] → OPEN (tripped)
OPEN → [timeout] → HALF_OPEN (testing)
HALF_OPEN → [success] → CLOSED
HALF_OPEN → [failure] → OPEN
```

**State Transitions**:

1. **CLOSED**: Normal operation
   - Calling the service
   - Tracking failures
   - If failures exceed threshold → OPEN

2. **OPEN**: Circuit tripped
   - NOT calling the service
   - Failing fast immediately
   - After timeout → HALF_OPEN

3. **HALF_OPEN**: Testing recovery
   - Trying one request
   - If success → CLOSED (recovered!)
   - If failure → OPEN (still failing)

### Example Scenario

**Without Circuit Breaker**:
```
Request 1: Wait 30s → timeout → fail
Request 2: Wait 30s → timeout → fail
Request 3: Wait 30s → timeout → fail
... (all requests wait and fail)
```

**With Circuit Breaker**:
```
Request 1-5: Wait → timeout → fail (circuit learning)
Request 6+: Circuit OPEN → fail immediately (no wait!)
After 60s: Try one request (HALF_OPEN)
If success: Circuit CLOSED → normal operation
If failure: Circuit OPEN again
```

### Code Example

```python
from resilience import CircuitBreaker, CircuitBreakerConfig

# Create circuit breaker for database calls
db_circuit = CircuitBreaker(
    name="database",
    config=CircuitBreakerConfig(
        failure_threshold=5,      # Open after 5 failures
        timeout_seconds=60,       # Wait 60s before testing recovery
        window_seconds=60,        # Count failures in last 60s
        min_calls=10              # Need 10 calls before opening
    )
)

# Use it to protect database calls
try:
    result = db_circuit.call(lambda: database.query("SELECT ..."))
except CircuitOpenError:
    # Circuit is open, service is failing
    # Return cached data or error immediately
    return get_cached_data()
```

### Interview Talking Points

**What to say**:
- "We use circuit breakers to prevent cascading failures"
- "When a downstream service starts failing, the circuit opens"
- "Once open, we fail fast instead of waiting for timeouts"
- "The circuit automatically tests recovery periodically"
- "This improves user experience and prevents resource exhaustion"

**Key Metrics**:
- Failure threshold: How many failures before opening
- Timeout: How long to stay open before testing
- Success rate: Track recovery attempts

---

## Retry Budget Pattern

### What Is It?

A **retry budget** limits how many retries you can do in a time period. Think of it like a spending budget - you have limited "retry money".

**Real-world analogy**: You have $100 to spend. Once you spend it, you can't buy more until next month.

### Why Do We Need It?

**Problem**: Retries can amplify failures:
- Service is slow → everyone retries → more load → service gets slower
- This creates a "retry storm" that makes problems worse

**Example**:
```
1000 requests come in
Each retries 3 times = 3000 total requests
Service gets overwhelmed
Response time becomes 5 seconds
Everyone retries more → death spiral
```

**Solution**: Retry budget limits total retries:
- Track retries in a time window
- Limit total retries allowed
- When budget exhausted → fail fast

### How It Works

1. **Track retries**: Record each retry attempt with timestamp
2. **Time window**: Only count retries in last N seconds
3. **Budget limit**: Maximum retries allowed in window
4. **Check before retry**: If budget available → allow retry
5. **If exhausted**: Fail fast instead of retrying

### Example Scenario

**Without Retry Budget**:
```
1000 requests → each retries 3 times = 3000 requests
Service overwhelmed → response time 5 seconds
More retries → worse performance → death spiral
```

**With Retry Budget (100 retries/minute)**:
```
1000 requests come in
First 100 get retries, rest fail fast
Service load manageable
Response time stays reasonable
```

### Code Example

```python
from resilience import RetryBudget, RetryBudgetConfig

# Create retry budget
retry_budget = RetryBudget(
    name="database",
    config=RetryBudgetConfig(
        max_retries=100,          # Max 100 retries
        window_seconds=60,        # Per 60 seconds
        min_retry_interval=0.1   # Wait 0.1s between retries
    )
)

# Use it to limit retries
for attempt in range(max_attempts):
    try:
        result = database.query("SELECT ...")
        break
    except DatabaseError:
        # Check if we have budget for a retry
        if not retry_budget.can_retry():
            raise RetryBudgetExceeded("Retry budget exhausted")
        
        # Record retry
        retry_budget.record_retry()
        
        # Wait before retrying
        time.sleep(backoff_time)
```

### Interview Talking Points

**What to say**:
- "Retry budgets prevent retry storms that amplify failures"
- "We track retry attempts in a time window and limit total retries"
- "When budget is exhausted, we fail fast instead of retrying"
- "This prevents cascading failures from retry amplification"
- "We use sliding windows to track retries over time"

**Key Metrics**:
- Max retries: Maximum allowed in window
- Window size: Time period for tracking
- Current usage: How much budget is used

---

## Bulkhead Pattern

### What Is It?

A **bulkhead** isolates resources so if one part fails, other parts keep working. Like watertight compartments in a ship.

**Real-world analogy**: Ship has bulkheads. If one compartment floods, others stay dry.

### Why Do We Need It?

**Problem**: One failing operation can consume all resources:
- Database query is slow → uses all connections → other queries wait
- One tenant's requests are slow → blocks all other tenants
- One API endpoint is slow → blocks all other endpoints

**Example**:
```
Admin operation uses all 20 database connections
Read operations wait → user experience degrades
Write operations wait → system appears frozen
```

**Solution**: Bulkhead isolates resources:
- Each operation type has its own resource pool
- If one pool is exhausted, others still work
- Failures are isolated and don't cascade

### How It Works

1. **Separate pools**: Each operation type has its own resource pool
2. **Limit concurrency**: Maximum concurrent operations per pool
3. **Acquire slot**: Before operation, acquire a slot from pool
4. **If full**: Wait (with timeout) or fail fast
5. **Release slot**: After operation completes, release slot

### Example Scenario

**Without Bulkhead**:
```
Read pool: 20 connections
Write pool: 20 connections (shared!)
Admin pool: 20 connections (shared!)

Admin operation uses all 20 connections
Read operations wait → slow
Write operations wait → slow
```

**With Bulkhead**:
```
Read pool: 20 connections (isolated)
Write pool: 5 connections (isolated)
Admin pool: 2 connections (isolated)

Admin operation uses 2 connections
Read operations still work (20 available)
Write operations still work (5 available)
```

### Code Example

```python
from resilience import Bulkhead, BulkheadConfig

# Create bulkheads for different operation types
read_bulkhead = Bulkhead(
    name="read_operations",
    config=BulkheadConfig(max_concurrent=20)
)

write_bulkhead = Bulkhead(
    name="write_operations",
    config=BulkheadConfig(max_concurrent=5)
)

# Use bulkhead to limit concurrency
with read_bulkhead.acquire():
    # Only 20 read operations can run at once
    result = database.query("SELECT ...")

# Or use as decorator
@read_bulkhead.protect
def read_from_database():
    return database.query("SELECT ...")
```

### Interview Talking Points

**What to say**:
- "Bulkheads isolate resources to prevent cascading failures"
- "Each operation type has its own resource pool"
- "If one pool is exhausted, other operations continue normally"
- "This provides fault isolation and predictable performance"
- "We use semaphores to implement concurrency limits"

**Key Metrics**:
- Max concurrent: Maximum operations per pool
- Current usage: How many operations running
- Utilization: Percentage of capacity used

---

## Graceful Draining Pattern

### What Is It?

**Graceful draining** means stopping new requests while finishing in-flight requests before shutting down.

**Real-world analogy**: Closing a restaurant - stop seating new customers, but let existing customers finish their meals.

### Why Do We Need It?

**Problem**: Without graceful draining:
- Server receives shutdown signal → immediately stops
- In-flight requests are killed mid-processing
- Users get errors, data might be corrupted
- Load balancer sends requests to dead server

**Solution**: Graceful draining:
- Stop accepting new requests
- Finish in-flight requests
- Load balancer removes server from rotation
- Shutdown cleanly after all requests finish

### Deployment Scenario

**Zero-Downtime Deployment**:

```
1. New server starts up
2. Old server stops accepting new requests (draining starts)
3. Load balancer routes new requests to new server
4. Old server finishes in-flight requests
5. Old server shuts down cleanly
6. Zero downtime!
```

### How It Works

1. **Track requests**: Count in-flight requests
2. **Start draining**: On shutdown signal, set draining flag
3. **Reject new**: New requests check flag, reject if draining
4. **Wait for completion**: Wait for in-flight requests to finish
5. **Shutdown**: After all complete (or timeout), shutdown

### Code Example

```python
from resilience import GracefulDrainer, GracefulDrainConfig

# Create graceful drainer
drainer = GracefulDrainer(
    name="api_server",
    config=GracefulDrainConfig(
        drain_timeout=30.0,      # Wait up to 30s
        check_interval=1.0       # Check every 1s
    )
)

# In request handler, wrap with drainer
@app.route('/api/v1/routes/resolve')
def resolve_route():
    try:
        with drainer.process_request():
            # Your request handling code
            return resolve_endpoint(...)
    except RuntimeError:
        # Draining, reject request
        return jsonify({"error": "Server shutting down"}), 503

# On shutdown signal
def shutdown_handler():
    logger.info("Received shutdown signal")
    drainer.start_draining()
    
    if drainer.wait_for_drain():
        logger.info("All requests completed, safe to shutdown")
    else:
        logger.warning("Timeout waiting for requests, forcing shutdown")
    
    # Now safe to shutdown
    shutdown_server()
```

### Interview Talking Points

**What to say**:
- "Graceful draining enables zero-downtime deployments"
- "We track in-flight requests and wait for them to complete"
- "During draining, we stop accepting new requests but finish existing ones"
- "This prevents request failures during deployments"
- "We coordinate with load balancers to remove servers from rotation"

**Key Metrics**:
- In-flight requests: Currently processing
- Draining status: Whether draining is active
- Drain timeout: Maximum wait time

---

## How They Work Together

These patterns work together to create a resilient system:

### Example: Database Call with All Patterns

```python
# Setup
db_circuit = CircuitBreaker("database")
retry_budget = RetryBudget("database")
read_bulkhead = Bulkhead("read_operations")
drainer = GracefulDrainer("api_server")

# Protected database call
@app.route('/api/v1/routes/resolve')
def resolve_route():
    # 1. Check if draining (graceful draining)
    try:
        with drainer.process_request():
            # 2. Acquire bulkhead slot (resource isolation)
            with read_bulkhead.acquire():
                # 3. Retry with budget (controlled retries)
                for attempt in range(max_attempts):
                    try:
                        # 4. Call with circuit breaker (failure detection)
                        result = db_circuit.call(
                            lambda: database.query("SELECT ...")
                        )
                        return result
                    except CircuitOpenError:
                        # Circuit open, use cache
                        return get_cached_data()
                    except DatabaseError:
                        # Check retry budget
                        if not retry_budget.can_retry():
                            raise RetryBudgetExceeded()
                        retry_budget.record_retry()
                        time.sleep(backoff_time)
    except RuntimeError:
        # Draining, reject request
        return jsonify({"error": "Server shutting down"}), 503
```

### Pattern Interactions

1. **Graceful Draining** → Rejects new requests first
2. **Bulkhead** → Limits concurrent operations
3. **Retry Budget** → Limits retry attempts
4. **Circuit Breaker** → Fails fast when service is down

---

## Interview Preparation

### Common Interview Questions

#### Q: "Explain circuit breaker pattern"

**Answer**:
"A circuit breaker is a pattern that prevents cascading failures. It has three states: closed (normal), open (tripped), and half-open (testing). When failures exceed a threshold, the circuit opens and we fail fast instead of waiting for timeouts. After a timeout period, we test recovery by entering half-open state. If the test succeeds, we close the circuit; if it fails, we open it again."

#### Q: "What's the difference between retry and retry budget?"

**Answer**:
"Retry is trying again after a failure. Retry budget limits how many retries you can do in a time window. Without a budget, retries can amplify failures - if a service is slow, everyone retries, creating more load. Retry budgets prevent this by limiting total retries across all requests."

#### Q: "How do bulkheads prevent cascading failures?"

**Answer**:
"Bulkheads isolate resources into separate pools. If one pool is exhausted, other pools continue working. For example, if admin operations use all connections in their pool, read and write operations in their pools are unaffected. This provides fault isolation."

#### Q: "How does graceful draining work in deployments?"

**Answer**:
"Graceful draining enables zero-downtime deployments. When we receive a shutdown signal, we stop accepting new requests but continue processing in-flight requests. We track the number of active requests and wait for them to complete before shutting down. Meanwhile, the load balancer routes new requests to the new server instance."

### Key Concepts to Remember

1. **Circuit Breaker**: Fast failure when service is down
2. **Retry Budget**: Prevent retry storms
3. **Bulkhead**: Isolate resources
4. **Graceful Draining**: Zero-downtime deployments

### Metrics to Track

- **Circuit Breaker**: Failure rate, state transitions, recovery time
- **Retry Budget**: Retry count, budget utilization, exhaustion events
- **Bulkhead**: Current usage, utilization, rejected operations
- **Graceful Draining**: In-flight requests, drain time, timeout events

---

## Summary

These four resilience patterns work together to create production-ready systems:

1. **Circuit Breaker**: Detects failures and fails fast
2. **Retry Budget**: Prevents retry amplification
3. **Bulkhead**: Isolates resources
4. **Graceful Draining**: Enables zero-downtime deployments

Understanding these patterns is essential for:
- Building resilient systems
- Passing senior engineer interviews
- Handling production failures
- Designing scalable architectures

---

## Next Steps

1. **Read the code**: Study the implementations in `src/resilience/`
2. **Try examples**: Run the example code
3. **Practice explaining**: Explain each pattern in your own words
4. **Think of scenarios**: When would you use each pattern?
5. **Interview prep**: Practice answering common questions

Good luck with your interviews! 🚀
