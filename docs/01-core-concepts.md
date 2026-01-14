# Core Concepts and Terminology

This document explains the fundamental concepts and terms used in the Traffic Manager system. Understanding these concepts is essential for designing distributed systems.

## Table of Contents

1. [Control Plane vs Data Plane](#control-plane-vs-data-plane)
2. [Multi-Tenancy](#multi-tenancy)
3. [Source of Truth](#source-of-truth)
4. [Idempotency](#idempotency)
5. [ACID Transactions](#acid-transactions)
6. [Eventual Consistency](#eventual-consistency)
7. [Bounded Staleness](#bounded-staleness)
8. [Cache-Aside Pattern](#cache-aside-pattern)
9. [Negative Caching](#negative-caching)
10. [Soft Deletion](#soft-deletion)

---

## Control Plane vs Data Plane

### Control Plane
The **control plane** is responsible for configuration and management operations. In Traffic Manager:
- **Write operations**: Creating, activating, deactivating routes
- **Low frequency**: Operations happen infrequently (minutes/hours, not milliseconds)
- **Strong consistency required**: Configuration must be correct
- **Example**: Kubernetes API Server, network routers' control plane

### Data Plane
The **data plane** handles actual request processing. In Traffic Manager:
- **Read operations**: Resolving endpoint URLs for incoming requests
- **High frequency**: Thousands to millions of requests per second
- **Performance critical**: Must be fast
- **Example**: Load balancers forwarding traffic, API gateways routing requests

### Why Separate Them?
- **Different requirements**: Control plane needs correctness, data plane needs speed
- **Different scaling**: Control plane scales with configuration changes, data plane scales with traffic
- **Different consistency**: Control plane = strong, data plane = eventual

---

## Multi-Tenancy

**Multi-tenancy** means a single system serves multiple isolated customers (tenants).

### In Traffic Manager
- Each **tenant** (e.g., "team-a", "team-b") has isolated routing configuration
- Tenants cannot see or modify each other's routes
- Same infrastructure serves all tenants (cost-effective)

### Isolation Levels
1. **Logical isolation**: Data separated by tenant_id (what we use)
2. **Physical isolation**: Separate databases per tenant (more expensive)
3. **Hybrid**: Logical for small tenants, physical for large ones

### Benefits
- **Cost efficiency**: Share infrastructure
- **Easier management**: One system to maintain
- **Resource utilization**: Better hardware usage

### Challenges
- **Data isolation**: Must prevent cross-tenant access
- **Performance isolation**: One tenant shouldn't impact others
- **Compliance**: Some regulations require physical separation

---

## Source of Truth

The **source of truth** is the authoritative data store that defines correctness.

### In Traffic Manager
- **PostgreSQL is the source of truth** for routing data
- All writes go to PostgreSQL first
- Cache (Redis) is a derivative, not authoritative
- If cache and database disagree, database wins

### Why This Matters
- **Correctness**: Always know what's right
- **Recovery**: Can rebuild cache from database
- **Debugging**: Single place to check actual state

### Anti-Pattern: Cache as Source of Truth
- ❌ Bad: Writing to cache first, syncing to DB later
- ✅ Good: Writing to DB first, cache is read-only replica

---

## Idempotency

An **idempotent operation** produces the same result regardless of how many times it's executed.

### Example
```python
# Idempotent: Calling this 1 time or 100 times gives same result
create_route(tenant="team-a", service="payments", env="prod", version="v2", url="https://...")
```

### Why Important?
- **Network retries**: If request fails, safe to retry
- **Duplicate requests**: Client sends same request twice? No problem
- **Recovery**: Can replay operations without side effects

### How We Achieve It
1. **Unique constraints**: Database prevents duplicates
2. **Deterministic operations**: Same input = same output
3. **Upsert patterns**: INSERT ... ON CONFLICT DO UPDATE

### Non-Idempotent Example
```python
# NOT idempotent: Each call increments counter
counter += 1  # Call 3 times = counter = 3
```

---

## ACID Transactions

**ACID** stands for Atomicity, Consistency, Isolation, Durability - properties of database transactions.

### Atomicity
"All or nothing" - transaction either fully completes or fully fails.

**Example**:
```sql
BEGIN;
  INSERT INTO tenants (name) VALUES ('team-a');
  INSERT INTO services (tenant_id, name) VALUES (1, 'payments');
  INSERT INTO endpoints (environment_id, version, url) VALUES (1, 'v2', 'https://...');
COMMIT;
```
If any step fails, all changes are rolled back.

### Consistency
Database remains in valid state - constraints are never violated.

**Example**: Foreign key constraints ensure `services.tenant_id` always references valid tenant.

### Isolation
Concurrent transactions don't interfere with each other.

**Example**: Two writes to same route are serialized (one completes before other starts).

### Durability
Committed changes survive system failures.

**Example**: After COMMIT, data is written to disk and won't be lost if server crashes.

### Why We Use Transactions
- **Correctness**: Ensures data integrity
- **Error handling**: Easy rollback on failure
- **Concurrency**: Prevents race conditions

---

## Eventual Consistency

**Eventual consistency** means system will become consistent over time, but not immediately.

### In Traffic Manager
- **Database**: Strongly consistent (immediate)
- **Cache**: Eventually consistent (may be stale for up to 60 seconds)
- **Downstream systems**: Eventually consistent (via Kafka events)

### Timeline Example
```
T=0s:  Write route to database (strongly consistent)
T=0s:  Publish Kafka event
T=1s:  Consumer processes event
T=1s:  Cache invalidated
T=2s:  Next read gets fresh data from database
```

### Why Acceptable?
- **Routing data changes infrequently**: Minutes/hours, not seconds
- **Bounded staleness**: Maximum 60 seconds old
- **Performance benefit**: Fast reads from cache

### When NOT Acceptable
- **Financial transactions**: Must be immediately consistent
- **Inventory systems**: Can't oversell products
- **Real-time bidding**: Milliseconds matter

---

## Bounded Staleness

**Bounded staleness** means data can be stale, but only for a known maximum time.

### In Traffic Manager
- **Positive cache TTL**: 60 seconds maximum staleness
- **Negative cache TTL**: 10 seconds maximum staleness
- **Kafka consumer lag**: Typically < 1 second

### Why This Matters
- **Predictable behavior**: Know worst-case staleness
- **SLA definition**: Can promise "data is at most X seconds old"
- **Debugging**: Understand why data might be stale

### Trade-offs
- **Shorter TTL**: Fresher data, more database load
- **Longer TTL**: Staler data, less database load

---

## Cache-Aside Pattern

**Cache-aside** (also called "lazy loading") means application manages cache explicitly.

### Flow
1. Application checks cache
2. If miss, application queries database
3. Application writes result to cache
4. Application returns data

### In Traffic Manager
```python
# 1. Check cache
cached_url = redis.get(cache_key)

# 2. If miss, query database
if not cached_url:
    url = query_database(...)
    # 3. Write to cache
    redis.setex(cache_key, ttl, url)
    # 4. Return
    return url
```

### Alternative: Write-Through
- Application writes to cache, cache writes to database
- More complex, but ensures cache and DB always match

### Why Cache-Aside?
- **Simplicity**: Easy to understand and debug
- **Flexibility**: Can invalidate cache independently
- **Failure isolation**: Cache failure doesn't break writes

---

## Negative Caching

**Negative caching** means caching "not found" results.

### In Traffic Manager
- Route doesn't exist → Cache `__NOT_FOUND__` for 10 seconds
- Next request for same route → Return immediately (no DB query)

### Why Useful?
- **Performance**: Avoids repeated database queries for non-existent routes
- **Database protection**: Prevents thundering herd on missing routes
- **Cost**: Reduces database load

### Example
```
Request 1: GET /route/team-a/payments/prod/v99
  → DB query → Not found → Cache "__NOT_FOUND__" (10s TTL)

Request 2-100 (within 10s): GET /route/team-a/payments/prod/v99
  → Cache hit → Return 404 immediately (no DB query)
```

### Shorter TTL
- Negative cache uses 10s TTL (vs 60s for positive)
- Allows quick recovery if route is created
- Trade-off: More cache misses, but acceptable

---

## Soft Deletion

**Soft deletion** means marking records as deleted instead of actually deleting them.

### In Traffic Manager
- Deactivate route: Set `is_active = false`
- Record remains in database
- Read path filters out inactive routes

### Why Not Hard Delete?
- **Audit trail**: Can see what routes existed
- **Recovery**: Can reactivate if needed
- **Referential integrity**: No orphaned records
- **Analytics**: Can analyze historical data

### Implementation
```sql
-- Soft delete
UPDATE endpoints SET is_active = false WHERE id = 123;

-- Read path filters
SELECT * FROM endpoints WHERE is_active = true;
```

### When to Hard Delete?
- **GDPR compliance**: Must delete personal data
- **Storage costs**: Old data too expensive to keep
- **After retention period**: Archive then delete

---

## Key Takeaways

1. **Control plane** = configuration (slow, correct), **Data plane** = requests (fast, eventually consistent)
2. **Source of truth** = single authoritative store (database)
3. **Idempotency** = safe to retry operations
4. **ACID transactions** = correctness guarantees
5. **Eventual consistency** = acceptable trade-off for performance
6. **Bounded staleness** = predictable maximum age
7. **Cache-aside** = application manages cache
8. **Negative caching** = cache "not found" results
9. **Soft deletion** = mark as deleted, don't remove

These concepts form the foundation of distributed systems design. Understanding them helps you make informed decisions about consistency, performance, and reliability.
