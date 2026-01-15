# Resilience Patterns - Interview Preparation Guide

This guide helps you prepare for senior/principal engineer interviews by explaining resilience patterns in detail, with real-world examples and interview questions.

**Target Audience**: Junior engineers preparing for senior/principal engineer interviews.

---

## Table of Contents

1. [Why These Patterns Matter](#why-these-patterns-matter)
2. [Circuit Breaker Deep Dive](#circuit-breaker-deep-dive)
3. [Retry Budget Deep Dive](#retry-budget-deep-dive)
4. [Bulkhead Deep Dive](#bulkhead-deep-dive)
5. [Graceful Draining Deep Dive](#graceful-draining-deep-dive)
6. [Common Interview Questions](#common-interview-questions)
7. [System Design Scenarios](#system-design-scenarios)

---

## Why These Patterns Matter

### The Problem They Solve

In production systems, you face:
- **Cascading failures**: One service failure brings down everything
- **Retry storms**: Retries amplify failures instead of helping
- **Resource exhaustion**: One slow operation blocks everything
- **Deployment downtime**: Users see errors during deployments

### The Solution

Resilience patterns provide:
- **Fault isolation**: Failures don't cascade
- **Controlled retries**: Prevent retry amplification
- **Resource protection**: Isolate resources per operation type
- **Zero-downtime**: Finish requests before shutdown

### Interview Context

When interviewers ask about resilience, they want to know:
1. Do you understand failure modes?
2. Can you design for failures?
3. Do you know production patterns?
4. Can you explain trade-offs?

---

## Circuit Breaker Deep Dive

### The Problem

**Scenario**: Your service calls a payment API that's slow (5 second response time).

**Without Circuit Breaker**:
```
Request 1: Wait 5s → timeout → fail
Request 2: Wait 5s → timeout → fail
Request 3: Wait 5s → timeout → fail
... (all requests wait and fail)
Result: Poor user experience, wasted resources
```

**With Circuit Breaker**:
```
Request 1-5: Wait → timeout → fail (circuit learning)
Request 6+: Circuit OPEN → fail immediately (no wait!)
After 60s: Try one request (HALF_OPEN)
If success: Circuit CLOSED → normal operation
Result: Fast failure, better UX, resources saved
```

### How to Explain It

**Simple explanation**:
"A circuit breaker is like a fuse in your house. When too many failures happen, it trips and stops calling the failing service. This prevents wasting time waiting for timeouts and gives better user experience."

**Technical explanation**:
"Circuit breakers have three states: closed (normal), open (tripped), and half-open (testing). We track failures in a time window. When failures exceed a threshold, we open the circuit and fail fast. After a timeout, we test recovery in half-open state. If the test succeeds, we close the circuit; if it fails, we open it again."

### Interview Questions

**Q: "When would you use a circuit breaker?"**

**Answer**:
"I'd use a circuit breaker when calling external services that might fail or be slow. For example, when calling a payment API, database, or third-party service. The circuit breaker detects when the service is failing and fails fast instead of waiting for timeouts. This improves user experience and prevents resource exhaustion."

**Q: "How do you configure a circuit breaker?"**

**Answer**:
"Key parameters are:
- Failure threshold: How many failures before opening (e.g., 5 failures)
- Timeout: How long to stay open before testing recovery (e.g., 60 seconds)
- Time window: How long to track failures (e.g., last 60 seconds)
- Min calls: Minimum calls before opening (prevents opening on just a few failures)

I'd tune these based on:
- Service reliability (more reliable = higher threshold)
- Recovery time (faster recovery = shorter timeout)
- Traffic patterns (high traffic = larger window)"

**Q: "What happens when a circuit breaker is open?"**

**Answer**:
"When open, the circuit breaker immediately raises an exception without calling the service. The application should handle this by:
1. Returning cached data (if available)
2. Returning a default value
3. Returning a 503 Service Unavailable error
4. Queuing the request for later

The key is failing fast - don't wait for timeouts."

---

## Retry Budget Deep Dive

### The Problem

**Scenario**: Database is slow (500ms response time). 1000 requests come in, each retries 3 times.

**Without Retry Budget**:
```
1000 requests × 3 retries = 3000 total requests
Database gets overwhelmed
Response time becomes 5 seconds
More retries → worse performance → death spiral
```

**With Retry Budget (100 retries/minute)**:
```
1000 requests come in
First 100 get retries, rest fail fast
Database load manageable
Response time stays reasonable
```

### How to Explain It

**Simple explanation**:
"A retry budget is like a spending limit. You have a limited amount of 'retry money' per time period. Once you spend it, you can't retry anymore until the budget resets. This prevents retry storms that make problems worse."

**Technical explanation**:
"We track retry attempts in a sliding time window. Each retry consumes budget. When budget is exhausted, we fail fast instead of retrying. This prevents retry amplification - when everyone retries, it creates more load on the failing service, making it worse."

### Interview Questions

**Q: "Why do we need retry budgets? Can't we just retry?"**

**Answer**:
"Retries are good for transient failures, but they can amplify problems. If a service is slow, everyone retries, creating more load, making it slower, causing more retries - a death spiral. Retry budgets limit total retries across all requests, preventing this amplification. We still retry, but in a controlled way."

**Q: "How do you size a retry budget?"**

**Answer**:
"I'd size it based on:
- Expected failure rate (higher failures = more budget needed)
- Service capacity (can service handle retry load?)
- Time window (how long to track retries)
- Cost of retries (database retries are expensive, cache retries are cheap)

For example:
- Database: 100 retries per minute (expensive, critical)
- Cache: 200 retries per minute (cheap, less critical)
- External API: 50 retries per minute (rate limits, costs)

I'd monitor budget usage and adjust based on actual patterns."

---

## Bulkhead Deep Dive

### The Problem

**Scenario**: You have 20 database connections shared by reads, writes, and admin operations.

**Without Bulkhead**:
```
Admin operation uses all 20 connections
Read operations wait → slow
Write operations wait → slow
User experience degrades
```

**With Bulkhead**:
```
Read pool: 15 connections (isolated)
Write pool: 4 connections (isolated)
Admin pool: 1 connection (isolated)

Admin operation uses 1 connection
Read operations still work (15 available)
Write operations still work (4 available)
User experience maintained
```

### How to Explain It

**Simple explanation**:
"Bulkheads are like watertight compartments in a ship. If one compartment floods, others stay dry. In software, we isolate resources so if one operation type uses all resources, other operations still work."

**Technical explanation**:
"We create separate resource pools for different operation types. Each pool has a maximum concurrency limit. Operations acquire a slot from their pool before executing. If a pool is full, operations wait or fail fast. This provides fault isolation - one slow operation type can't block others."

### Interview Questions

**Q: "How do bulkheads prevent cascading failures?"**

**Answer**:
"Bulkheads isolate resources so failures in one area don't affect others. For example, if admin operations are slow and use all their connections, read and write operations in their separate pools continue normally. This prevents one problem from cascading to everything. It's like having separate lanes on a highway - if one lane is blocked, others keep moving."

**Q: "How do you size bulkhead pools?"**

**Answer**:
"I'd size pools based on:
- Operation frequency (reads are frequent, admin is rare)
- Operation latency (reads are fast, writes are slow)
- Resource cost (database connections are expensive)
- Business priority (reads are critical, admin is less critical)

Example:
- Read pool: 20 connections (high frequency, fast, critical)
- Write pool: 5 connections (low frequency, slow, critical)
- Admin pool: 2 connections (rare, very slow, less critical)

I'd monitor pool utilization and adjust based on actual usage patterns."

---

## Graceful Draining Deep Dive

### The Problem

**Scenario**: You need to deploy a new version. Old server receives shutdown signal.

**Without Graceful Draining**:
```
Server receives SIGTERM → immediately stops
In-flight requests killed mid-processing
Users get errors
Load balancer sends requests to dead server
Downtime!
```

**With Graceful Draining**:
```
Server receives SIGTERM → start draining
Stop accepting new requests
Finish in-flight requests
Load balancer removes from rotation
Shutdown cleanly
Zero downtime!
```

### How to Explain It

**Simple explanation**:
"Graceful draining is like closing a restaurant. You stop seating new customers, but let existing customers finish their meals. In software, we stop accepting new requests but finish processing in-flight requests before shutting down."

**Technical explanation**:
"We track in-flight requests with a counter. When draining starts, we set a flag. New requests check this flag and reject if draining. We wait for the counter to reach zero (all requests complete) or timeout. This enables zero-downtime deployments - new server starts, old server drains, no user-visible downtime."

### Interview Questions

**Q: "How does graceful draining work in Kubernetes?"**

**Answer**:
"Kubernetes sends SIGTERM to the pod when it wants to terminate it. Our application:
1. Receives SIGTERM → start draining
2. Readiness probe starts failing (we're not ready)
3. Kubernetes stops sending new requests
4. We finish in-flight requests
5. Kubernetes sends SIGKILL after grace period
6. Pod terminates cleanly

The key is coordinating with Kubernetes:
- Readiness probe: Returns 503 when draining
- Grace period: Time to finish requests (e.g., 30 seconds)
- Load balancer: Removes pod from rotation when not ready"

**Q: "What if requests take too long to finish?"**

**Answer**:
"We set a drain timeout (e.g., 30 seconds). If requests don't finish in time:
1. Log a warning
2. Force shutdown (requests may be killed)
3. Monitor for issues

In practice:
- Most requests finish quickly (< 1 second)
- Long-running requests are rare
- Timeout is a safety net

For very long operations, we might:
- Make them asynchronous (queue for later)
- Add checkpoints (can resume after restart)
- Use separate workers (don't block HTTP requests)"

---

## Common Interview Questions

### General Questions

**Q: "Explain the difference between circuit breaker and retry budget."**

**Answer**:
"Circuit breaker detects when a service is failing and stops calling it. Retry budget limits how many retries you can do. They work together:
- Circuit breaker: 'This service is down, don't call it'
- Retry budget: 'You've retried too much, stop retrying'

Circuit breaker is per-service (is payment API down?). Retry budget is global (how many total retries across all requests?). Both prevent wasting resources on failing operations."

**Q: "When would you use bulkheads vs circuit breakers?"**

**Answer**:
"Use circuit breakers when calling external services that might fail. Use bulkheads to isolate resources within your application. They solve different problems:
- Circuit breaker: Service is failing → don't call it
- Bulkhead: Too many operations → limit concurrency

You'd use both:
- Circuit breaker protects database calls
- Bulkhead limits concurrent database operations
- Together: Don't call failing service AND don't overwhelm it"

**Q: "How do these patterns work together?"**

**Answer**:
"They work in layers:
1. Graceful draining: Reject new requests during shutdown
2. Bulkhead: Limit concurrent operations (if not draining)
3. Circuit breaker: Fail fast if service is down (if got slot)
4. Retry budget: Limit retries (if circuit allows call)

Example flow:
- Request comes in → check draining (reject if draining)
- Acquire bulkhead slot → check circuit breaker (fail fast if open)
- Make call → if fails, check retry budget (retry if budget available)
- Retry → check circuit breaker again (might have opened)"

### System Design Questions

**Q: "Design a resilient payment service."**

**Answer**:
"I'd use all four patterns:

1. **Circuit Breaker**: Protect calls to payment processor
   - If processor is down, fail fast
   - Return cached payment status if available

2. **Retry Budget**: Limit retries for payment calls
   - Payments are expensive (fees)
   - Limit to 10 retries per minute
   - Fail fast when budget exhausted

3. **Bulkhead**: Isolate payment operations
   - Payment processing: 5 concurrent
   - Payment queries: 20 concurrent
   - Admin operations: 2 concurrent

4. **Graceful Draining**: Zero-downtime deployments
   - Finish in-flight payments before shutdown
   - Critical for financial operations

This ensures:
- Fast failure when processor is down
- Controlled retries (don't waste money)
- Isolation (admin doesn't block payments)
- Zero downtime (no payment loss during deploy)"

---

## System Design Scenarios

### Scenario 1: E-commerce Checkout

**Problem**: Checkout service calls payment API, inventory service, and shipping service.

**Solution**:
```
Checkout Service
├─ Circuit Breaker (payment API)
│  └─ If payment API down → return error immediately
├─ Circuit Breaker (inventory service)
│  └─ If inventory down → use cached inventory
├─ Circuit Breaker (shipping service)
│  └─ If shipping down → queue for later
├─ Retry Budget (all services)
│  └─ Max 50 retries per minute total
├─ Bulkhead (checkout operations)
│  └─ Max 10 concurrent checkouts
└─ Graceful Draining
   └─ Finish in-flight checkouts before shutdown
```

### Scenario 2: API Gateway

**Problem**: Gateway routes requests to 100+ backend services.

**Solution**:
```
API Gateway
├─ Circuit Breaker (per backend service)
│  └─ Each service has its own circuit breaker
├─ Retry Budget (per service type)
│  └─ Critical services: 100 retries/min
│  └─ Non-critical: 20 retries/min
├─ Bulkhead (per route)
│  └─ /api/payments: 10 concurrent
│  └─ /api/search: 50 concurrent
│  └─ /api/admin: 2 concurrent
└─ Graceful Draining
   └─ Stop accepting new requests, finish routing
```

---

## Key Takeaways for Interviews

1. **Understand the problem**: Why do we need each pattern?
2. **Know the solution**: How does each pattern work?
3. **Explain simply**: Use analogies (circuit breaker = fuse)
4. **Know trade-offs**: When to use what, and why
5. **Think in layers**: Patterns work together
6. **Consider metrics**: How to monitor and tune

### What Interviewers Want to Hear

✅ "I understand failure modes and design for them"
✅ "I know production patterns and when to use them"
✅ "I can explain trade-offs and make decisions"
✅ "I think about system behavior under stress"
✅ "I design for zero-downtime deployments"

### Red Flags to Avoid

❌ "I don't know what a circuit breaker is"
❌ "We just retry everything 10 times"
❌ "We don't need graceful shutdown"
❌ "One connection pool for everything is fine"

---

## Practice Exercises

1. **Explain circuit breaker** to a non-technical person
2. **Design resilience** for a chat application
3. **Tune parameters** for a high-traffic API
4. **Debug a scenario** where circuit breaker keeps opening
5. **Design graceful draining** for a long-running job processor

---

## Resources

- **Code**: `src/resilience/` - Full implementations with comments
- **Documentation**: `docs/13-resilience-patterns.md` - Complete guide
- **Architecture**: `architecture/overview.md` - System design
- **Metrics**: `GET /health/resilience` - See patterns in action

---

Good luck with your interviews! 🚀

Remember: Understanding these patterns shows you can design production-ready systems that handle failures gracefully.
