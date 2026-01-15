# Failure Handling and Resilience

This document explains how to design systems that handle failures gracefully and remain available.

## Table of Contents

1. [Failure is Inevitable](#failure-is-inevitable)
2. [Failure Modes](#failure-modes)
3. [Resilience Patterns](#resilience-patterns)
4. [Circuit Breaker Pattern](#circuit-breaker-pattern)
5. [Retry Strategies](#retry-strategies)
6. [Timeout and Backoff](#timeout-and-backoff)
7. [Graceful Degradation](#graceful-degradation)
8. [Failure Isolation](#failure-isolation)
9. [Traffic Manager's Failure Handling](#traffic-managers-failure-handling)

---

## Failure is Inevitable

**Failures will happen** - design for them.

### Types of Failures

1. **Hardware failures**: Disk, CPU, memory
2. **Network failures**: Timeouts, partitions
3. **Software failures**: Bugs, crashes
4. **Human errors**: Misconfiguration, mistakes
5. **Load failures**: Overwhelmed by traffic

### Failure Statistics

- **Hardware**: ~3% annual failure rate
- **Network**: ~0.1% packet loss
- **Software**: Bugs in all complex systems
- **Human**: 70% of outages caused by humans

**Conclusion**: Must design for failures.

---

## Failure Modes

### 1. Complete Failure

**Service is completely down.**

```
Service → [DOWN] → No response
```

**Impact**: All requests fail

**Handling**: Failover to backup, return error

### 2. Partial Failure

**Service is partially working.**

```
Service → [SLOW] → Some requests timeout
```

**Impact**: Some requests fail, some succeed

**Handling**: Timeout, retry, circuit breaker

### 3. Degraded Performance

**Service is slow but working.**

```
Service → [SLOW] → 5 second response time
```

**Impact**: Slow responses, timeouts

**Handling**: Timeout, fallback, cache

### 4. Data Corruption

**Data is incorrect.**

```
Database → [CORRUPT] → Wrong data returned
```

**Impact**: Incorrect results

**Handling**: Validation, checksums, backups

---

## Resilience Patterns

### 1. Failover

**Switch to backup when primary fails.**

```
Primary → [FAIL] → Backup (takes over)
```

**Example**: Database master fails → replica becomes master

### 2. Redundancy

**Multiple copies of everything.**

```
Service 1
Service 2  → Load balancer → Clients
Service 3
```

**Example**: Multiple service instances

### 3. Timeout

**Don't wait forever.**

```python
try:
    result = service.call(timeout=5)  # Max 5 seconds
except TimeoutError:
    # Handle timeout
    return fallback()
```

### 4. Retry

**Try again on failure.**

```python
for attempt in range(3):
    try:
        return service.call()
    except Exception:
        if attempt == 2:
            raise
        time.sleep(2 ** attempt)  # Exponential backoff
```

### 5. Circuit Breaker

**Stop calling failing service.**

```python
if circuit_breaker.is_open():
    return fallback()  # Don't call service

try:
    result = service.call()
    circuit_breaker.record_success()
except Exception:
    circuit_breaker.record_failure()
    return fallback()
```

---

## Circuit Breaker Pattern

**Circuit breaker** = stop calling failing service to prevent cascading failures.

### States

1. **Closed**: Normal operation (calling service)
2. **Open**: Service failing (not calling, using fallback)
3. **Half-Open**: Testing if service recovered

### State Transitions

```
Closed → [Too many failures] → Open
Open → [Timeout] → Half-Open
Half-Open → [Success] → Closed
Half-Open → [Failure] → Open
```

### Implementation

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.state = 'closed'
        self.last_failure_time = None
    
    def call(self, func):
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'half-open'
            else:
                raise CircuitOpenError()
        
        try:
            result = func()
            if self.state == 'half-open':
                self.state = 'closed'
                self.failure_count = 0
            return result
        except Exception:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
            raise
```

### Benefits

- ✅ **Prevents cascading failures**: Stop calling failing service
- ✅ **Fast failure**: Immediate fallback
- ✅ **Auto-recovery**: Tests if service recovered

---

## Retry Strategies

### 1. No Retry

**Fail immediately.**

```python
result = service.call()  # Fails → raise exception
```

**Use case**: Non-idempotent operations

### 2. Fixed Retry

**Retry fixed number of times.**

```python
for i in range(3):
    try:
        return service.call()
    except Exception:
        if i == 2:
            raise
        time.sleep(1)
```

**Use case**: Transient failures

### 3. Exponential Backoff

**Wait longer between retries.**

```python
for i in range(3):
    try:
        return service.call()
    except Exception:
        if i == 2:
            raise
        time.sleep(2 ** i)  # 1s, 2s, 4s
```

**Use case**: Overloaded services

### 4. Jittered Backoff

**Add randomness to backoff.**

```python
import random
backoff = (2 ** i) + random.uniform(0, 1)
time.sleep(backoff)
```

**Use case**: Prevent thundering herd

### Traffic Manager's Retries

**Kafka producer**: Exponential backoff with jitter
- Retries up to 3 times
- Exponential backoff
- Idempotent (safe to retry)

---

## Timeout and Backoff

### Timeout

**Don't wait forever for response.**

```python
# Set timeout
response = requests.get(url, timeout=5)  # Max 5 seconds

# Or with socket timeout
socket.setdefaulttimeout(5)
```

**Why important?**
- Prevents hanging requests
- Frees resources quickly
- Better user experience

### Backoff Strategies

1. **Fixed**: Wait same time between retries
2. **Exponential**: Wait 2^n seconds (1s, 2s, 4s, 8s)
3. **Linear**: Wait n seconds (1s, 2s, 3s, 4s)
4. **Jittered**: Add randomness

### Traffic Manager's Timeouts

**Kafka producer**: 10 second timeout
- Don't wait forever for Kafka
- Fail fast if Kafka is down
- Log error, continue (non-critical)

---

## Graceful Degradation

**Graceful degradation** = system works with reduced functionality when components fail.

### Example: Cache Failure

```
Normal: Request → Cache → Database → Response
Degraded: Request → Database → Response (slower, but works)
```

### Strategies

1. **Fallback to slower path**: Cache fails → use database
2. **Return cached data**: Database fails → use stale cache
3. **Return default**: Service fails → return default value
4. **Queue for later**: Service fails → queue request

### Traffic Manager's Degradation

**Cache failure**:
- Fallback to database (slower, but works)
- System remains functional

**Kafka failure**:
- Write succeeds (database is source of truth)
- Events delayed (non-critical)
- Cache TTL ensures eventual correctness

---

## Failure Isolation

**Failure isolation** = prevent failures from cascading.

### Bulkhead Pattern

**Isolate resources** (like ship bulkheads).

```
Service A → [Isolated] → Resource Pool A
Service B → [Isolated] → Resource Pool B
```

**If Service A fails, Service B still works.**

### Traffic Manager's Isolation

**Component isolation**:
- Redis failure → doesn't affect writes
- Kafka failure → doesn't affect writes
- Database failure → affects writes (expected)

**Read path isolation**:
- Cache failure → fallback to DB
- DB failure → return error (expected)

---

## Traffic Manager's Failure Handling

### Read Path Failures

| Failure | Impact | Handling |
|---------|--------|----------|
| Redis unavailable | Cache misses | Fallback to database |
| Database unavailable | Cache misses fail | Return error (expected) |
| Cache stale | Stale data | Bounded by TTL (60s) |

### Write Path Failures

| Failure | Impact | Handling |
|---------|--------|----------|
| Database failure | Write fails | Transaction rollback, return error |
| Kafka failure | Event not published | Write succeeds, log warning |
| Consumer failure | Side effects delayed | Events replayed on recovery |

### Design Principles

1. **Database is source of truth**: Always correct
2. **Cache is optimization**: Failure doesn't break system
3. **Kafka is best-effort**: Failure doesn't break writes
4. **Fail fast**: Timeouts prevent hanging
5. **Graceful degradation**: System works with reduced functionality

---

## Key Takeaways

1. **Failures are inevitable**: Design for them
2. **Circuit breaker**: Stop calling failing services (✅ IMPLEMENTED)
3. **Retry with backoff**: Handle transient failures
4. **Retry budget**: Prevent retry storms (✅ IMPLEMENTED)
5. **Timeouts**: Don't wait forever
6. **Graceful degradation**: Work with reduced functionality
7. **Bulkhead**: Isolate resources (✅ IMPLEMENTED)
8. **Failure isolation**: Prevent cascading failures
9. **Graceful draining**: Zero-downtime deployments (✅ IMPLEMENTED)
10. **Fail fast**: Detect failures quickly
11. **Idempotency**: Safe to retry

Understanding failure handling helps you:
- Design resilient systems
- Prevent cascading failures
- Maintain availability
- Handle errors gracefully
- Pass senior engineer interviews

## Implementation Status

All four resilience patterns are **fully implemented** in Traffic Manager:

- ✅ **Circuit Breaker**: `src/resilience/circuit_breaker.py`
- ✅ **Retry Budget**: `src/resilience/retry_budget.py`
- ✅ **Bulkhead**: `src/resilience/bulkhead.py`
- ✅ **Graceful Draining**: `src/resilience/graceful_drain.py`

See `docs/13-resilience-patterns.md` for complete documentation and interview preparation guide.
