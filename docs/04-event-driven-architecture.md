# Event-Driven Architecture

This document explains event-driven architecture, messaging patterns, and how Kafka enables decoupled, scalable systems.

## Table of Contents

1. [What is Event-Driven Architecture?](#what-is-event-driven-architecture)
2. [Event Sourcing vs Event Streaming](#event-sourcing-vs-event-streaming)
3. [Message Queue Patterns](#message-queue-patterns)
4. [Kafka Fundamentals](#kafka-fundamentals)
5. [Producer Patterns](#producer-patterns)
6. [Consumer Patterns](#consumer-patterns)
7. [Event Design](#event-design)
8. [Ordering and Partitioning](#ordering-and-partitioning)
9. [Delivery Semantics](#delivery-semantics)
10. [Traffic Manager's Event System](#traffic-managers-event-system)

---

## What is Event-Driven Architecture?

**Event-driven architecture (EDA)** is a design pattern where components communicate by producing and consuming events.

### Traditional Request-Response

```
Client → Service A → Service B → Service C
         (waits)      (waits)      (waits)
```

**Problems:**
- Tight coupling
- Synchronous (slow)
- Failure cascades
- Hard to scale

### Event-Driven

```
Client → Service A → Event Bus → Service B (async)
                      Event Bus → Service C (async)
                      Event Bus → Service D (async)
```

**Benefits:**
- Loose coupling
- Asynchronous (fast)
- Failure isolation
- Easy to scale

### Key Concepts

1. **Event**: Something that happened (e.g., "route created")
2. **Producer**: Publishes events
3. **Consumer**: Processes events
4. **Event Bus**: Transports events (Kafka, RabbitMQ, etc.)

---

## Event Sourcing vs Event Streaming

### Event Sourcing

**Event sourcing** stores all events as the source of truth.

```
State = Replay all events from beginning
```

**Example:**
```
Event 1: Account created (balance = 0)
Event 2: Deposit $100 (balance = 100)
Event 3: Withdraw $50 (balance = 50)

Current balance = Replay events = $50
```

**Pros:**
- Complete audit trail
- Can rebuild state
- Time travel (see state at any time)

**Cons:**
- Complex to implement
- Replay can be slow
- Storage grows forever

### Event Streaming

**Event streaming** uses events for communication, but state is stored separately.

```
State stored in database
Events used for communication
```

**Example:**
```
Database: route = {url: "https://..."}
Event: "route_changed" → Consumers update cache
```

**Pros:**
- Simpler than event sourcing
- Fast (no replay needed)
- Flexible (multiple consumers)

**Cons:**
- No complete history
- Can't time travel
- State and events can diverge

### Traffic Manager's Approach

**Event streaming** (not event sourcing):
- Database stores state (source of truth)
- Events used for cache invalidation and side effects
- Simpler and faster

---

## Message Queue Patterns

### 1. Point-to-Point (Queue)

**One producer, one consumer per message.**

```
Producer → Queue → Consumer
```

**Use case**: Task processing, job queues

### 2. Publish-Subscribe (Pub/Sub)

**One producer, multiple consumers.**

```
Producer → Topic → Consumer 1
                → Consumer 2
                → Consumer 3
```

**Use case**: Broadcasting, fan-out

### 3. Request-Reply

**Producer sends request, waits for reply.**

```
Producer → Request Queue → Consumer
Producer ← Reply Queue ← Consumer
```

**Use case**: RPC over messaging

### Kafka: Both Patterns

Kafka supports both:
- **Queue**: Consumer groups (one consumer per group processes message)
- **Pub/Sub**: Multiple consumer groups (each gets copy of message)

---

## Kafka Fundamentals

### Topics

**Topic** = category/stream of events (like a table in database).

```
route-events topic:
  - route_changed (created)
  - route_changed (activated)
  - route_changed (deactivated)
```

### Partitions

**Partition** = ordered sequence of events within a topic.

```
Topic: route-events
  Partition 0: [event1, event2, event3]
  Partition 1: [event4, event5, event6]
  Partition 2: [event7, event8, event9]
```

**Why partitions?**
- **Parallelism**: Multiple consumers can process different partitions
- **Scalability**: Can add more partitions
- **Ordering**: Events in same partition are ordered

### Offsets

**Offset** = position of event in partition.

```
Partition 0:
  Offset 0: event1
  Offset 1: event2
  Offset 2: event3
```

**Why offsets?**
- Track consumer position
- Resume from last position
- Replay events

### Consumer Groups

**Consumer group** = set of consumers working together.

```
Consumer Group A:
  Consumer 1 → Partition 0
  Consumer 2 → Partition 1
  Consumer 3 → Partition 2
```

**Benefits:**
- Load balancing (each partition processed by one consumer)
- Parallel processing
- Fault tolerance (if consumer dies, others take over)

---

## Producer Patterns

### 1. Fire-and-Forget

**Send and don't wait for confirmation.**

```python
producer.send(topic, value=event)
# Don't wait, continue immediately
```

**Use case**: Non-critical events, high throughput

### 2. Synchronous Send

**Wait for confirmation.**

```python
future = producer.send(topic, value=event)
result = future.get(timeout=10)  # Wait for ACK
```

**Use case**: Critical events, need confirmation

### 3. Idempotent Producer

**Prevent duplicates on retry.**

```python
producer = KafkaProducer(
    idempotent=True,  # Prevents duplicates
    acks='all'        # Wait for all replicas
)
```

**Use case**: Exactly-once semantics (best effort)

### 4. Batching

**Send multiple events together.**

```python
producer = KafkaProducer(
    batch_size=100,      # Batch 100 events
    linger_ms=10         # Wait 10ms for batch
)
```

**Use case**: High throughput, lower latency per event

### Traffic Manager's Approach

**Best-effort async**:
- Send event after DB commit
- Don't wait for confirmation
- Log failures (non-critical)
- Database is source of truth

---

## Consumer Patterns

### 1. At-Least-Once Delivery

**Message delivered at least once (may be duplicates).**

```python
consumer = KafkaConsumer(
    enable_auto_commit=False  # Manual commit
)

for message in consumer:
    process(message)
    consumer.commit()  # Commit after processing
```

**Trade-off**: May process same message twice (must be idempotent)

### 2. At-Most-Once Delivery

**Message delivered at most once (may be lost).**

```python
consumer = KafkaConsumer(
    enable_auto_commit=True,   # Auto commit
    auto_commit_interval_ms=1000
)
```

**Trade-off**: May lose messages (simpler, but risky)

### 3. Exactly-Once Delivery

**Message delivered exactly once (ideal, but complex).**

Requires:
- Idempotent producer
- Idempotent consumer
- Transactional processing

**Trade-off**: Complex, but guarantees no duplicates or losses

### Traffic Manager's Approach

**At-least-once with idempotency**:
- Consumer processes events
- Operations are idempotent (safe to retry)
- Effectively once (even if delivered multiple times)

---

## Event Design

### Event Structure

**Good event design:**
- Self-contained (all needed data)
- Immutable (never change after creation)
- Versioned (can evolve schema)
- Timestamped (when it happened)

### Example: Route Changed Event

```json
{
  "event_id": "uuid-123",
  "event_type": "route_changed",
  "event_version": "1.0",
  "action": "created",
  "tenant": "team-a",
  "service": "payments",
  "env": "prod",
  "version": "v2",
  "url": "https://...",
  "occurred_at": "2024-01-14T10:30:00Z",
  "metadata": {
    "user_id": "user-123",
    "request_id": "req-456"
  }
}
```

### Event Types

1. **Domain Events**: Business events (route_changed)
2. **Integration Events**: Cross-service events
3. **Technical Events**: System events (health checks)

### Schema Evolution

**Version events** to handle changes:

```json
// Version 1.0
{"event_type": "route_changed", "url": "https://..."}

// Version 1.1 (add field)
{"event_type": "route_changed", "url": "https://...", "region": "us-east"}
```

**Strategies:**
- Backward compatible (add optional fields)
- Version field in event
- Multiple topics for major versions

---

## Ordering and Partitioning

### Why Ordering Matters

**Ordering** ensures events processed in correct sequence.

**Example:**
```
Event 1: Create route
Event 2: Activate route
Event 3: Deactivate route
```

Must process in order!

### Partitioning Strategy

**Partition key** determines which partition event goes to.

```python
# Same key → same partition → ordered
partition_key = f"{tenant}:{service}:{env}:{version}"
producer.send(topic, key=partition_key, value=event)
```

**Benefits:**
- Events for same route are ordered
- Different routes can be processed in parallel
- Scalable (more partitions = more parallelism)

### Trade-offs

- **More partitions**: More parallelism, but more overhead
- **Fewer partitions**: Less overhead, but less parallelism
- **Key design**: Must balance ordering vs distribution

---

## Delivery Semantics

### At-Least-Once

**Guarantee**: Message delivered at least once.

**Implementation:**
- Producer retries on failure
- Consumer commits after processing

**Trade-off**: May process duplicates (must be idempotent)

### At-Most-Once

**Guarantee**: Message delivered at most once.

**Implementation:**
- Producer doesn't retry
- Consumer commits before processing

**Trade-off**: May lose messages (simpler)

### Exactly-Once

**Guarantee**: Message delivered exactly once.

**Implementation:**
- Idempotent producer
- Transactional consumer
- Idempotent processing

**Trade-off**: Complex, but perfect

### Traffic Manager's Approach

**At-least-once with idempotency**:
- Producer: Idempotent, retries enabled
- Consumer: Idempotent operations
- Effectively once (even if delivered multiple times)

---

## Traffic Manager's Event System

### Architecture

```
Write Path → Database (commit) → Kafka (event) → Consumers
                                              ↓
                                    Cache Invalidation
                                    Audit Logging
                                    Other Systems
```

### Event Flow

1. **Write operation** completes in database
2. **Kafka event** published (best effort)
3. **Consumers** process events asynchronously
4. **Side effects** executed (cache invalidation, etc.)

### Why This Design?

1. **Decoupling**: Write path doesn't wait for side effects
2. **Scalability**: Consumers scale independently
3. **Reliability**: Database is source of truth
4. **Flexibility**: Easy to add new consumers

### Event Schema

```json
{
  "event_id": "uuid",
  "event_type": "route_changed",
  "action": "created|activated|deactivated",
  "tenant": "team-a",
  "service": "payments",
  "env": "prod",
  "version": "v2",
  "url": "https://...",
  "occurred_at": "RFC3339 timestamp"
}
```

### Partitioning

```python
# Partition by route identifier
partition_key = f"{tenant}:{service}:{env}:{version}"
```

**Ensures:**
- Events for same route are ordered
- Different routes processed in parallel

### Consumer Example: Cache Invalidation

```python
def consume_events():
    for event in consumer:
        if event['action'] in ['created', 'activated', 'deactivated']:
            # Invalidate cache
            cache_key = f"route:{event['tenant']}:{event['service']}:{event['env']}:{event['version']}"
            redis.delete(cache_key)  # Idempotent operation
        
        consumer.commit()
```

---

## Key Takeaways

1. **Event-driven architecture** = loose coupling, async communication
2. **Event streaming** = events for communication, DB for state
3. **Kafka** = distributed event log (topics, partitions, offsets)
4. **Consumer groups** = parallel processing, load balancing
5. **Partitioning** = ordering within partition, parallelism across
6. **At-least-once** = may duplicate, must be idempotent
7. **Event design** = self-contained, immutable, versioned
8. **Best-effort publishing** = DB is source of truth, events are side effects

Understanding event-driven architecture helps you:
- Design decoupled systems
- Scale independently
- Handle failures gracefully
- Build flexible architectures
