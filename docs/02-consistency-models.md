# Consistency Models in Distributed Systems

This document explains different consistency models, when to use them, and the trade-offs involved. Understanding consistency is crucial for designing distributed systems.

## Table of Contents

1. [What is Consistency?](#what-is-consistency)
2. [Strong Consistency](#strong-consistency)
3. [Eventual Consistency](#eventual-consistency)
4. [CAP Theorem](#cap-theorem)
5. [Consistency Levels](#consistency-levels)
6. [Choosing the Right Model](#choosing-the-right-model)
7. [Trade-offs in Traffic Manager](#trade-offs-in-traffic-manager)

---

## What is Consistency?

**Consistency** means all nodes in a distributed system see the same data at the same time (or within acceptable bounds).

### The Consistency Spectrum

```
Strong Consistency          Eventual Consistency
     (Immediate)              (Eventually)
        |                          |
        |                          |
    Always correct          Eventually correct
    Slower, expensive       Faster, cheaper
```

### Real-World Analogy

- **Strong consistency**: Everyone sees the same clock time (synchronized)
- **Eventual consistency**: Different clocks, but they'll sync eventually

---

## Strong Consistency

**Strong consistency** (also called "immediate consistency" or "linearizability") means:
- All reads see the most recent write
- All nodes agree on the order of operations
- No stale data visible

### Characteristics

- ✅ **Correctness**: Always see latest data
- ❌ **Latency**: Must wait for all nodes to agree
- ❌ **Availability**: System may be unavailable during partitions
- ❌ **Cost**: More expensive (synchronous replication)

### When to Use

- **Financial transactions**: Money must be accurate
- **Configuration**: System config must be correct
- **Critical operations**: Where correctness > performance
- **Write path**: Creating/updating routes (our use case)

### Example: Database Transaction

```sql
BEGIN;
  UPDATE accounts SET balance = balance - 100 WHERE id = 1;
  UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;
```

After COMMIT, all reads see the updated balances immediately.

### Implementation in Traffic Manager

```python
# Write path: Strong consistency
def create_route(...):
    with transaction:
        # All changes are atomic
        create_tenant(...)
        create_service(...)
        create_endpoint(...)
    # After commit, all reads see new route
```

---

## Eventual Consistency

**Eventual consistency** means:
- System will become consistent over time
- Different nodes may see different data temporarily
- No guarantee of when consistency is achieved

### Characteristics

- ✅ **Performance**: Fast reads (no waiting)
- ✅ **Availability**: System stays available during partitions
- ✅ **Scalability**: Can scale horizontally easily
- ❌ **Staleness**: May read old data
- ❌ **Complexity**: Must handle conflicts

### When to Use

- **Read-heavy workloads**: Performance matters more
- **Non-critical data**: Staleness is acceptable
- **High availability required**: System must stay up
- **Read path**: Resolving routes (our use case)

### Example: DNS

DNS uses eventual consistency:
- Update DNS record → propagates globally over minutes/hours
- Different users may see different IPs temporarily
- Eventually all see the same IP

### Implementation in Traffic Manager

```python
# Read path: Eventual consistency
def resolve_endpoint(...):
    # Check cache (may be stale up to 60 seconds)
    cached = redis.get(key)
    if cached:
        return cached  # Fast, but might be stale
    
    # Fallback to database (strongly consistent)
    return query_database(...)
```

---

## CAP Theorem

The **CAP Theorem** states that a distributed system can guarantee at most 2 of 3 properties:

### C - Consistency
All nodes see the same data simultaneously.

### A - Availability
System remains operational (responds to requests).

### P - Partition Tolerance
System continues working despite network failures.

### The Triangle

```
        Consistency
            /\
           /  \
          /    \
         /      \
        /        \
Availability --- Partition Tolerance
```

**You can only pick 2!**

### Real-World Choices

1. **CP (Consistency + Partition Tolerance)**
   - Example: PostgreSQL, MongoDB (with strong consistency)
   - Trade-off: May be unavailable during partitions
   - Use: When correctness is critical

2. **AP (Availability + Partition Tolerance)**
   - Example: DNS, CDN, Cassandra
   - Trade-off: May serve stale data
   - Use: When availability is critical

3. **CA (Consistency + Availability)**
   - Not possible in distributed systems (partitions always happen)
   - Only works in single-node systems

### Traffic Manager's Approach

- **Write path**: CP (Consistency + Partition Tolerance)
  - Database must be consistent
  - May be unavailable if database is partitioned

- **Read path**: AP (Availability + Partition Tolerance)
  - Cache provides availability
  - May serve stale data (bounded by TTL)

---

## Consistency Levels

Different systems offer different consistency guarantees:

### 1. Strong Consistency (Linearizability)
- All operations appear to execute atomically
- All nodes see operations in same order
- **Example**: PostgreSQL transactions, etcd

### 2. Sequential Consistency
- All nodes see operations in same order
- But operations may not be atomic
- **Example**: Some distributed databases

### 3. Causal Consistency
- Causally related operations seen in order
- Unrelated operations may be seen in different order
- **Example**: Some NoSQL databases

### 4. Eventual Consistency
- System will become consistent eventually
- No guarantees about when
- **Example**: DNS, CDN, most caches

### 5. Weak Consistency
- No guarantees about order or timing
- **Example**: Some distributed caches

---

## Choosing the Right Model

### Decision Framework

Ask these questions:

1. **How critical is correctness?**
   - Critical → Strong consistency
   - Acceptable staleness → Eventual consistency

2. **How often does data change?**
   - Frequent → Strong consistency or short TTL
   - Rare → Eventual consistency acceptable

3. **What's the read/write ratio?**
   - Read-heavy → Optimize reads (eventual consistency)
   - Write-heavy → Optimize writes (strong consistency)

4. **What's the cost of stale data?**
   - High cost (money, safety) → Strong consistency
   - Low cost (routing, recommendations) → Eventual consistency

5. **What's the availability requirement?**
   - Must stay up → Eventual consistency
   - Can tolerate downtime → Strong consistency

### Examples

| Use Case | Consistency Model | Why |
|----------|------------------|-----|
| Bank account balance | Strong | Money must be accurate |
| Route resolution | Eventual | Staleness acceptable, performance critical |
| User profile | Eventual | Can show slightly old data |
| Inventory count | Strong | Can't oversell products |
| Product catalog | Eventual | Staleness OK, performance matters |
| Configuration | Strong | System must use correct config |

---

## Trade-offs in Traffic Manager

### Write Path: Strong Consistency

**Why?**
- Route configuration must be correct
- Can't have wrong URLs
- Changes are infrequent (minutes/hours)

**Trade-offs:**
- ✅ Correctness guaranteed
- ✅ Simple to reason about
- ❌ Slower (must wait for DB)
- ❌ Less scalable (DB is bottleneck)

**Implementation:**
```python
# ACID transaction ensures consistency
BEGIN;
  INSERT INTO endpoints ...;
COMMIT;
# All reads immediately see new route
```

### Read Path: Eventual Consistency

**Why?**
- Performance critical (thousands of requests/second)
- Staleness acceptable (routes change infrequently)
- Bounded staleness (max 60 seconds)

**Trade-offs:**
- ✅ Fast (cache hits in microseconds)
- ✅ Scalable (cache can handle high load)
- ✅ Available (works even if DB is slow)
- ❌ May serve stale data (up to 60s old)

**Implementation:**
```python
# Cache may be stale, but fast
cached = redis.get(key)  # May be 0-60 seconds old
if cached:
    return cached  # Fast path
```

### The Bridge: Kafka Events

Kafka bridges strong and eventual consistency:

```
Write (Strong) → Kafka Event → Consumers (Eventual)
     ↓                              ↓
  Database                    Cache Invalidation
  (Source of Truth)           (Eventually Consistent)
```

**Flow:**
1. Write to database (strong consistency)
2. Publish Kafka event (best effort)
3. Consumers eventually process event
4. Cache invalidated (eventually consistent)

**Why This Works:**
- Database is always correct (source of truth)
- Cache TTL ensures eventual correctness
- Kafka events speed up cache invalidation
- System degrades gracefully

---

## Consistency Patterns

### Pattern 1: Read-Your-Writes

**Problem**: After writing, immediate read might see old data.

**Solution**: 
- Write path: Strong consistency
- Read path: Check write timestamp, bypass cache if recent

### Pattern 2: Monotonic Reads

**Problem**: User sees data going backwards in time.

**Solution**: 
- Track user's last seen timestamp
- Never show data older than that

### Pattern 3: Causal Consistency

**Problem**: Related operations must be seen in order.

**Solution**: 
- Track causal dependencies
- Ensure dependent operations seen after dependencies

### Pattern 4: Session Consistency

**Problem**: User's session should be consistent.

**Solution**: 
- Sticky sessions (same server)
- Or track session's last write timestamp

---

## Key Takeaways

1. **Strong consistency** = correctness, but slower and less available
2. **Eventual consistency** = performance, but may serve stale data
3. **CAP Theorem** = can only guarantee 2 of 3 (C, A, P)
4. **Choose based on requirements**: Correctness vs Performance vs Availability
5. **Traffic Manager uses both**: Strong for writes, eventual for reads
6. **Bounded staleness** = acceptable trade-off for performance
7. **Source of truth** = always know what's correct (database)

Understanding consistency models helps you:
- Make informed design decisions
- Explain trade-offs to stakeholders
- Choose the right model for each use case
- Design systems that meet requirements
