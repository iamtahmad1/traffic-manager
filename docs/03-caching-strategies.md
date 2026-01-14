# Caching Strategies and Patterns

This document explains different caching strategies, when to use them, and how they're implemented in Traffic Manager.

## Table of Contents

1. [Why Cache?](#why-cache)
2. [Cache-Aside Pattern](#cache-aside-pattern)
3. [Write-Through Pattern](#write-through-pattern)
4. [Write-Behind Pattern](#write-behind-pattern)
5. [Refresh-Ahead Pattern](#refresh-ahead-pattern)
6. [Cache Invalidation Strategies](#cache-invalidation-strategies)
7. [Negative Caching](#negative-caching)
8. [Cache Warming](#cache-warming)
9. [Cache Coherency](#cache-coherency)
10. [Traffic Manager's Approach](#traffic-managers-approach)

---

## Why Cache?

**Caching** stores frequently accessed data in fast storage to improve performance.

### Benefits

- **Performance**: 10-1000x faster than database
- **Reduced load**: Protects database from high traffic
- **Cost**: Cheaper than scaling database
- **Availability**: Can serve requests even if DB is slow

### Costs

- **Complexity**: More moving parts
- **Staleness**: May serve old data
- **Memory**: Requires RAM
- **Consistency**: Must manage cache invalidation

### When to Cache

✅ **Good candidates:**
- Read-heavy workloads
- Data that changes infrequently
- Expensive computations
- Frequently accessed data

❌ **Bad candidates:**
- Write-heavy workloads
- Data that changes frequently
- Data that must be real-time
- Rarely accessed data

---

## Cache-Aside Pattern

**Cache-aside** (also called "lazy loading") means the application manages the cache.

### Flow

```
1. Application receives request
2. Check cache
   ├─ Hit → Return cached data
   └─ Miss → Query database → Write to cache → Return data
```

### Implementation

```python
def get_data(key):
    # 1. Check cache
    cached = cache.get(key)
    if cached:
        return cached
    
    # 2. Cache miss - query database
    data = database.query(key)
    
    # 3. Write to cache
    cache.set(key, data, ttl=60)
    
    # 4. Return
    return data
```

### Pros

- ✅ **Simple**: Easy to understand
- ✅ **Flexible**: Can invalidate cache independently
- ✅ **Failure isolation**: Cache failure doesn't break application
- ✅ **No cache dependency**: Works without cache

### Cons

- ❌ **Cache miss penalty**: Two round trips (cache + DB)
- ❌ **Staleness**: Data may be old until TTL expires
- ❌ **Thundering herd**: Multiple requests for same miss

### Use Case

Traffic Manager uses cache-aside for read path:
- Simple to implement
- Cache failure doesn't break system
- Can invalidate via Kafka events

---

## Write-Through Pattern

**Write-through** means writes go to both cache and database simultaneously.

### Flow

```
1. Application writes data
2. Write to cache
3. Write to database
4. Return success (only after both complete)
```

### Implementation

```python
def write_data(key, value):
    # Write to both cache and database
    cache.set(key, value)
    database.update(key, value)
    # Both must succeed
```

### Pros

- ✅ **Consistency**: Cache and DB always match
- ✅ **Durability**: Data persisted immediately
- ✅ **No stale data**: Cache always fresh

### Cons

- ❌ **Slower writes**: Must wait for both
- ❌ **Cache dependency**: Requires cache to be available
- ❌ **Complexity**: Must handle failures in both

### Use Case

Good for:
- Data that must be immediately consistent
- When cache availability is guaranteed
- Write-heavy workloads with frequent reads

---

## Write-Behind Pattern

**Write-behind** (also called "write-back") means writes go to cache first, then asynchronously to database.

### Flow

```
1. Application writes data
2. Write to cache (immediate)
3. Queue write to database (async)
4. Return success immediately
5. Background process writes to database
```

### Implementation

```python
def write_data(key, value):
    # 1. Write to cache immediately
    cache.set(key, value)
    
    # 2. Queue database write (async)
    queue.put(('write', key, value))
    
    # 3. Return immediately
    return success

# Background worker
def worker():
    while True:
        operation, key, value = queue.get()
        database.update(key, value)
```

### Pros

- ✅ **Fast writes**: Immediate response
- ✅ **High throughput**: Can batch database writes
- ✅ **Resilient**: Can retry failed writes

### Cons

- ❌ **Data loss risk**: Cache failure loses data
- ❌ **Complexity**: Must handle failures, retries
- ❌ **Consistency**: Cache and DB may differ temporarily

### Use Case

Good for:
- Write-heavy workloads
- When some data loss is acceptable
- High-performance requirements

**Not used in Traffic Manager** - we need strong consistency.

---

## Refresh-Ahead Pattern

**Refresh-ahead** means cache refreshes data before it expires.

### Flow

```
1. Data accessed from cache
2. Check TTL remaining
   ├─ > 20% remaining → Return cached data
   └─ < 20% remaining → Return cached data + trigger refresh
3. Background refresh updates cache
```

### Implementation

```python
def get_data(key):
    cached, ttl_remaining = cache.get_with_ttl(key)
    
    if cached:
        # If TTL < 20%, refresh in background
        if ttl_remaining < 0.2 * TTL:
            async_refresh(key)
        return cached
    
    # Cache miss - normal flow
    return fetch_from_db(key)
```

### Pros

- ✅ **Always fresh**: Data refreshed before expiry
- ✅ **No stale reads**: Users never see expired data
- ✅ **Smooth experience**: No cache miss delays

### Cons

- ❌ **Complexity**: Must track TTL and trigger refreshes
- ❌ **Waste**: May refresh data that's never accessed
- ❌ **Load**: More database queries

### Use Case

Good for:
- Critical data that must be fresh
- When cache misses are expensive
- Predictable access patterns

---

## Cache Invalidation Strategies

### 1. TTL (Time-To-Live)

**Simple**: Data expires after fixed time.

```python
cache.set(key, value, ttl=60)  # Expires in 60 seconds
```

**Pros**: Simple, automatic
**Cons**: May serve stale data, unnecessary refreshes

### 2. Event-Based Invalidation

**Smart**: Invalidate on data changes.

```python
# On write
database.update(key, value)
cache.delete(key)  # Invalidate immediately
```

**Pros**: Always fresh, efficient
**Cons**: Requires event system, more complex

### 3. Version-Based

**Optimistic**: Check version before using.

```python
# Store version with data
cache.set(key, (value, version=5))

# On read, check version
cached_value, cached_version = cache.get(key)
if cached_version < database_version:
    # Stale, refresh
    refresh(key)
```

**Pros**: Can detect staleness
**Cons**: Requires version tracking

### 4. Tag-Based Invalidation

**Grouped**: Invalidate by tags.

```python
# Cache with tags
cache.set(key, value, tags=['user:123', 'product:456'])

# Invalidate all with tag
cache.invalidate_tag('user:123')  # Removes all user:123 data
```

**Pros**: Efficient bulk invalidation
**Cons**: Requires tag system

### Traffic Manager's Approach

**Hybrid**: TTL + Event-based
- TTL as safety net (60s for positive, 10s for negative)
- Kafka events for immediate invalidation
- Best of both worlds

---

## Negative Caching

**Negative caching** means caching "not found" results.

### Why?

- **Performance**: Avoids repeated DB queries for missing data
- **Protection**: Prevents thundering herd on 404s
- **Cost**: Reduces database load

### Implementation

```python
def get_data(key):
    cached = cache.get(key)
    
    if cached == "__NOT_FOUND__":
        # Negative cache hit
        raise NotFoundError()
    
    if cached:
        return cached
    
    # Cache miss - query DB
    data = database.query(key)
    
    if data:
        cache.set(key, data, ttl=60)  # Positive cache
    else:
        cache.set(key, "__NOT_FOUND__", ttl=10)  # Negative cache (shorter TTL)
        raise NotFoundError()
```

### TTL Strategy

- **Positive cache**: Longer TTL (60s) - data exists, unlikely to change
- **Negative cache**: Shorter TTL (10s) - data might be created soon

### Use Cases

- API endpoints: Cache 404s
- Database queries: Cache missing records
- File systems: Cache missing files

---

## Cache Warming

**Cache warming** means pre-populating cache with likely-needed data.

### Strategies

1. **On startup**: Load hot data
2. **Predictive**: Load data likely to be accessed
3. **Scheduled**: Refresh at intervals
4. **Event-driven**: Warm on write events

### Implementation

```python
def warm_cache():
    # Get hot routes
    hot_routes = database.query("""
        SELECT * FROM endpoints 
        WHERE access_count > 1000 
        ORDER BY access_count DESC 
        LIMIT 100
    """)
    
    # Pre-populate cache
    for route in hot_routes:
        key = f"route:{route.tenant}:{route.service}:{route.env}:{route.version}"
        cache.set(key, route.url, ttl=60)
```

### Pros

- ✅ **Better hit rate**: More data in cache
- ✅ **Faster responses**: No cache misses for hot data
- ✅ **Predictable load**: Spreads DB load

### Cons

- ❌ **Memory usage**: More cache space needed
- ❌ **Complexity**: Must identify hot data
- ❌ **Waste**: May warm unused data

---

## Cache Coherency

**Cache coherency** means keeping cache consistent with source of truth.

### Problems

1. **Stale reads**: Cache has old data
2. **Inconsistent updates**: Cache and DB differ
3. **Race conditions**: Concurrent updates

### Solutions

1. **TTL**: Automatic expiration (simple but may be stale)
2. **Invalidation**: Delete on update (fresh but complex)
3. **Versioning**: Check versions (detect staleness)
4. **Write-through**: Always write both (consistent but slow)

### Traffic Manager's Approach

**Multi-layered**:
1. TTL as safety net (bounded staleness)
2. Kafka events for invalidation (eventual consistency)
3. Database as source of truth (always correct)

---

## Traffic Manager's Approach

### Read Path: Cache-Aside with Negative Caching

```python
def resolve_endpoint(...):
    # 1. Check cache
    cached = redis.get(cache_key)
    
    # 2. Negative cache hit
    if cached == "__NOT_FOUND__":
        raise RouteNotFoundError()
    
    # 3. Positive cache hit
    if cached:
        return cached
    
    # 4. Cache miss - query DB
    url = query_database(...)
    
    # 5. Cache result
    if url:
        redis.setex(cache_key, 60, url)  # Positive: 60s
    else:
        redis.setex(cache_key, 10, "__NOT_FOUND__")  # Negative: 10s
    
    return url
```

### Write Path: Event-Based Invalidation

```python
def create_route(...):
    # 1. Write to database (strong consistency)
    with transaction:
        database.insert(...)
    
    # 2. Publish Kafka event (best effort)
    kafka.publish({
        'action': 'created',
        'route': {...}
    })
    
    # 3. Consumer invalidates cache
    # (happens asynchronously)
```

### Why This Works

1. **Cache-aside**: Simple, flexible, resilient
2. **Negative caching**: Protects DB from 404 storms
3. **TTL safety net**: Ensures eventual correctness
4. **Event invalidation**: Speeds up cache refresh
5. **Database as source of truth**: Always know what's correct

---

## Key Takeaways

1. **Cache-aside** = application manages cache (simple, flexible)
2. **Write-through** = write to both cache and DB (consistent, slower)
3. **Write-behind** = write cache first, DB later (fast, risky)
4. **TTL** = automatic expiration (simple, may be stale)
5. **Event invalidation** = delete on update (fresh, complex)
6. **Negative caching** = cache "not found" (protects DB)
7. **Cache warming** = pre-populate (better hit rate)
8. **Multi-layered approach** = TTL + events + DB (best of all worlds)

Understanding caching strategies helps you:
- Choose the right pattern for your use case
- Balance performance and consistency
- Design scalable systems
- Optimize for your workload
