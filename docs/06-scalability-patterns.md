# Scalability Patterns

This document explains scalability patterns, horizontal vs vertical scaling, and how to design systems that can grow.

## Table of Contents

1. [What is Scalability?](#what-is-scalability)
2. [Vertical vs Horizontal Scaling](#vertical-vs-horizontal-scaling)
3. [Stateless vs Stateful Services](#stateless-vs-stateful-services)
4. [Load Balancing](#load-balancing)
5. [Database Scaling](#database-scaling)
6. [Caching for Scale](#caching-for-scale)
7. [Async Processing](#async-processing)
8. [Partitioning and Sharding](#partitioning-and-sharding)
9. [Traffic Manager's Scalability](#traffic-managers-scalability)

---

## What is Scalability?

**Scalability** = system's ability to handle increased load by adding resources.

### Types of Scalability

1. **Scale Up (Vertical)**: Bigger machines
2. **Scale Out (Horizontal)**: More machines
3. **Scale Both**: Hybrid approach

### Scalability Dimensions

- **Load**: Requests per second
- **Data**: Amount of data stored
- **Users**: Number of concurrent users
- **Geographic**: Multiple regions

---

## Vertical vs Horizontal Scaling

### Vertical Scaling (Scale Up)

**Add more resources to existing machine.**

```
Before: 4 CPU, 8GB RAM
After:  16 CPU, 64GB RAM
```

**Pros:**
- ✅ Simple (no code changes)
- ✅ No distributed system complexity
- ✅ Lower latency (no network)

**Cons:**
- ❌ Limited by hardware
- ❌ Expensive (bigger machines cost more)
- ❌ Single point of failure

### Horizontal Scaling (Scale Out)

**Add more machines.**

```
Before: 1 server
After:  10 servers
```

**Pros:**
- ✅ Unlimited scale (add more machines)
- ✅ Cost-effective (commodity hardware)
- ✅ Fault tolerant (one fails, others work)

**Cons:**
- ❌ Complex (distributed system)
- ❌ Network latency
- ❌ Coordination needed

### Traffic Manager's Approach

**Horizontal scaling**:
- Stateless services (can add more instances)
- Database can scale (read replicas)
- Cache can scale (Redis cluster)
- Kafka consumers scale horizontally

---

## Stateless vs Stateful Services

### Stateless Services

**No server-side state** - each request is independent.

```python
# Stateless: No memory between requests
def resolve_endpoint(tenant, service, env, version):
    # Uses external state (database, cache)
    return query_database(...)
```

**Benefits:**
- ✅ Easy to scale (add more instances)
- ✅ Load balancing simple
- ✅ Fault tolerant (any instance can handle request)

### Stateful Services

**Maintains state** between requests.

```python
# Stateful: Maintains state
class Service:
    def __init__(self):
        self.cache = {}  # In-memory state
    
    def get_data(self, key):
        return self.cache.get(key)
```

**Problems:**
- ❌ Hard to scale (state must be shared)
- ❌ Load balancing complex (sticky sessions)
- ❌ Fault intolerant (state lost on crash)

### Traffic Manager's Approach

**Stateless services**:
- No in-memory state
- All state in database/cache
- Easy to scale horizontally

---

## Load Balancing

**Load balancing** = distributing requests across multiple servers.

### Strategies

#### 1. Round Robin

**Distribute requests evenly.**

```
Request 1 → Server 1
Request 2 → Server 2
Request 3 → Server 3
Request 4 → Server 1 (repeat)
```

#### 2. Least Connections

**Send to server with fewest active connections.**

#### 3. Weighted Round Robin

**Distribute based on server capacity.**

```
Server 1 (weight 3): Gets 3 requests
Server 2 (weight 1): Gets 1 request
```

#### 4. IP Hash

**Same IP always goes to same server** (sticky sessions).

### Traffic Manager's Load Balancing

**Stateless services** can use any strategy:
- Round robin (simple)
- Least connections (efficient)
- Health-based (skip unhealthy servers)

---

## Database Scaling

### Read Replicas

**Multiple copies for reads, one master for writes.**

```
Master (writes) → Replica 1 (reads)
               → Replica 2 (reads)
               → Replica 3 (reads)
```

**Benefits:**
- ✅ Scale reads (add more replicas)
- ✅ Fault tolerance (replica can become master)
- ✅ Geographic distribution

**Traffic Manager**: Can use read replicas for read path.

### Sharding

**Split data across multiple databases.**

```
Shard 1: tenants 1-1000
Shard 2: tenants 1001-2000
Shard 3: tenants 2001-3000
```

**Benefits:**
- ✅ Scale writes (distribute load)
- ✅ Scale storage (each shard smaller)

**Challenges:**
- ❌ Complex queries (cross-shard)
- ❌ Rebalancing (when shards grow)

**Traffic Manager**: Not sharded (single database sufficient).

### Connection Pooling

**Reuse database connections.**

```python
# Without pooling: Create connection per request
conn = connect()  # Slow
query(conn)
close(conn)

# With pooling: Reuse connections
conn = pool.get_connection()  # Fast (reused)
query(conn)
pool.return_connection(conn)
```

**Benefits:**
- ✅ Faster (reuse connections)
- ✅ Efficient (limited connections)
- ✅ Scalable (handle more requests)

---

## Caching for Scale

**Cache reduces database load** (scales reads).

### Cache Hit Rate

**Higher hit rate = less database load.**

```
1000 requests/second
- 90% cache hits = 100 DB queries/second
- 10% cache hits = 900 DB queries/second
```

### Cache Strategies for Scale

1. **Distributed cache**: Redis cluster (multiple nodes)
2. **Cache warming**: Pre-populate hot data
3. **Cache hierarchy**: L1 (local) + L2 (distributed)

### Traffic Manager's Caching

**Redis cache**:
- 80-95% hit rate (typical)
- Reduces DB load by 80-95%
- Can scale Redis cluster if needed

---

## Async Processing

**Async processing** = don't wait for slow operations.

### Synchronous (Blocking)

```python
# Blocks until complete
result = slow_operation()  # Waits 5 seconds
return result
```

**Problem**: Can't handle more requests while waiting.

### Asynchronous (Non-blocking)

```python
# Returns immediately
queue.put(slow_operation)  # Returns immediately
# Process in background
```

**Benefit**: Can handle more requests.

### Traffic Manager's Async

**Kafka events**:
- Write path doesn't wait for side effects
- Consumers process asynchronously
- Scales independently

---

## Partitioning and Sharding

### Partitioning (Kafka)

**Split topic into partitions** for parallelism.

```
Topic: route-events
  Partition 0: [event1, event2, event3]
  Partition 1: [event4, event5, event6]
  Partition 2: [event7, event8, event9]

Consumers:
  Consumer 1 → Partition 0
  Consumer 2 → Partition 1
  Consumer 3 → Partition 2
```

**Benefits:**
- ✅ Parallel processing
- ✅ Scalable (add more partitions)
- ✅ Ordered within partition

### Sharding (Database)

**Split data across databases.**

```
Database 1: tenant_id % 3 = 0
Database 2: tenant_id % 3 = 1
Database 3: tenant_id % 3 = 2
```

**Benefits:**
- ✅ Scale writes
- ✅ Scale storage

**Traffic Manager**: Not sharded (single DB sufficient).

---

## Traffic Manager's Scalability

### Read Path Scalability

**Horizontal scaling**:
- Stateless services (add more instances)
- Redis cache (handles 100K+ req/s)
- Database read replicas (if needed)

**Bottleneck**: Database (on cache misses)

**Solution**: High cache hit rate (80-95%)

### Write Path Scalability

**Limited by database**:
- Writes are infrequent (minutes/hours)
- Database can handle write load
- Can add read replicas for reads

**Bottleneck**: Database transactions

**Solution**: Writes are rare, acceptable

### Event Processing Scalability

**Horizontal scaling**:
- Kafka consumers scale independently
- Add more consumers = more parallelism
- Partition by route (parallel processing)

**Bottleneck**: Kafka throughput

**Solution**: Kafka handles high throughput

### Overall Scalability

**Read path**: Highly scalable (cache + stateless)
**Write path**: Limited by DB (acceptable for control plane)
**Events**: Highly scalable (Kafka + consumers)

---

## Key Takeaways

1. **Horizontal scaling** = add more machines (preferred)
2. **Stateless services** = easy to scale
3. **Load balancing** = distribute requests
4. **Read replicas** = scale database reads
5. **Caching** = scale reads (reduce DB load)
6. **Async processing** = don't block on slow operations
7. **Partitioning** = parallel processing
8. **Identify bottlenecks** = scale what's limiting you

Understanding scalability helps you:
- Design systems that can grow
- Identify bottlenecks
- Choose right scaling strategy
- Plan for growth
