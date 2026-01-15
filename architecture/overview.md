# Traffic Manager - Architecture Overview

## 1. System Overview

Traffic Manager is a multi-tenant routing control plane that manages and resolves endpoint URLs for services across different tenants, environments, and versions. The system provides both read and write paths with different consistency guarantees optimized for their respective use cases.

### Core Responsibilities

- **Route Resolution (Read Path)**: Fast, cache-optimized endpoint URL resolution
- **Route Management (Write Path)**: Strongly consistent route creation, activation, and deactivation
- **Event-Driven Architecture**: Decoupled side effects via Kafka for cache invalidation and downstream systems
- **Audit Trail**: Comprehensive audit logging with MongoDB for change history and compliance

### Design Principles

1. **Database as Source of Truth**: PostgreSQL is the authoritative data store
2. **Strong Consistency for Writes**: All write operations are transactional and synchronous
3. **Eventual Consistency for Reads**: Cache provides fast reads with bounded staleness
4. **Failure Isolation**: Component failures don't cascade to critical paths
5. **Idempotency**: All operations are safe to retry
6. **Resilience Patterns**: Circuit breakers, retry budgets, bulkheads, and graceful draining

## 2. System Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ├─────────────────┐
       │                 │
       ▼                 ▼
┌─────────────┐   ┌─────────────┐
│  Read Path  │   │ Write Path  │
│ (routing.py)│   │(write_path) │
└──────┬──────┘   └──────┬──────┘
       │                 │
       │                 │
       ▼                 ▼
┌─────────────┐   ┌─────────────┐
│    Redis    │   │ PostgreSQL  │
│   (Cache)   │   │  (Source of │
│             │   │    Truth)   │
└─────────────┘   └──────┬──────┘
                         │
                         │ (after commit)
                         ▼
                  ┌─────────────┐
                  │    Kafka    │
                  │  (Events)   │
                  └─────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │  Consumers  │
                  │ (Cache Inv, │
                  │   Audit,    │
                  │   etc.)     │
                  └──────┬───────┘
                         │
                         │ (audit consumer)
                         ▼
                  ┌─────────────┐
                  │  MongoDB    │
                  │ (Audit Store│
                  │   & History)│
                  └─────────────┘
```

## 3. Component Details

### 3.1 Read Path (`service/routing.py`)

**Purpose**: Resolve endpoint URLs for incoming requests

**Flow**:
1. Check Redis cache first (fast path)
2. If cache miss, query PostgreSQL
3. Cache result (positive or negative)
4. Return URL

**Characteristics**:
- **Latency**: Sub-millisecond for cache hits, ~10-50ms for cache misses
- **Consistency**: Eventually consistent (bounded by cache TTL)
- **Caching Strategy**:
  - Positive cache: 60 seconds TTL
  - Negative cache: 10 seconds TTL (for non-existent routes)

**Cache Key Format**: `route:{tenant}:{service}:{env}:{version}`

### 3.2 Write Path (`service/write_path.py`)

**Purpose**: Create, activate, and deactivate routes

**Operations**:
- `create_route()`: Create new route (idempotent)
- `activate_route()`: Set `is_active = true`
- `deactivate_route()`: Set `is_active = false`

**Flow**:
1. Validate inputs
2. Begin database transaction
3. Get or create tenant/service/environment (idempotent)
4. Apply mutation (create/activate/deactivate)
5. Commit transaction
6. Publish Kafka event (best effort, non-blocking)

**Characteristics**:
- **Latency**: ~50-200ms (database transaction + Kafka publish)
- **Consistency**: Strong consistency (ACID transactions)
- **Idempotency**: All operations are safe to retry

### 3.3 Database Schema

**Tables**:
- `tenants`: Multi-tenancy support
- `services`: Services per tenant
- `environments`: Environments per service (prod, staging, etc.)
- `endpoints`: Route definitions with version and URL

**Constraints**:
- `(tenant_id, service_name)` unique
- `(service_id, env_name)` unique
- `(environment_id, version)` unique
- `is_active` flag for soft deactivation

### 3.4 Cache Layer (`cache/redis_client.py`)

**Purpose**: Reduce database load and improve read latency

**Strategy**: Cache-aside pattern
- Application manages cache
- Cache misses trigger database queries
- Cache writes happen after database reads

**TTL Strategy**:
- Positive entries: 60 seconds
- Negative entries: 10 seconds (shorter to allow quick recovery)

### 3.5 Audit Store (`mongodb_client/client.py`)

**Purpose**: Store route change history for audit, compliance, and debugging

**Storage**: MongoDB for flexible schema and efficient querying

**Document Structure**:
```json
{
  "event_id": "uuid",
  "event_type": "route_changed",
  "action": "created|activated|deactivated",
  "route": {
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v2"
  },
  "url": "https://...",
  "previous_url": "https://...",
  "previous_state": "active|inactive",
  "changed_by": "user@example.com",
  "occurred_at": ISODate,
  "processed_at": ISODate,
  "metadata": {}
}
```

**Indexes**:
- Compound index on route fields + occurred_at (for route-specific queries)
- Index on occurred_at (for time-based queries)
- Index on action + occurred_at (for filtering by action type)
- Unique index on event_id (for deduplication)

**Query Capabilities**:
- Who changed this route? (changed_by field)
- When did it change? (occurred_at timestamp)
- What was the previous value? (previous_url, previous_state)
- History for last 30/90 days? (time-based queries)
- Debug outages? (full event context with action, route, timestamps)

**API Endpoints**:
- `GET /api/v1/audit/route` - Get history for specific route
- `GET /api/v1/audit/recent` - Get events from last N days
- `GET /api/v1/audit/action` - Filter by action type
- `GET /api/v1/audit/time-range` - Query within time window

### 3.6 Event System (`kafka/producer.py`)

**Purpose**: Decouple write path from side effects

**Topic**: `route-events`

**Event Format**:
```json
{
  "event_id": "uuid",
  "event_type": "route_changed",
  "action": "created | activated | deactivated",
  "tenant": "team-a",
  "service": "payments",
  "env": "prod",
  "version": "v2",
  "url": "https://...",
  "occurred_at": "RFC3339 timestamp"
}
```

**Partitioning**: By `{tenant}:{service}:{env}:{version}` to ensure ordering per route

**Producer Configuration**:
- `acks='all'`: Wait for all replicas
- `idempotent=True`: Prevent duplicates
- `retries=3`: Automatic retry on failure

**Semantics**: At-least-once delivery with effectively-once behavior via idempotent consumers

### 3.7 Resilience Patterns (`resilience/`)

**Purpose**: Handle failures gracefully and maintain availability under stress

**Implemented Patterns**:

1. **Circuit Breaker** (`circuit_breaker.py`):
   - Detects service failures and fails fast
   - States: CLOSED (normal), OPEN (tripped), HALF_OPEN (testing)
   - Protects database, Redis, and MongoDB calls
   - Auto-recovers when services come back

2. **Retry Budget** (`retry_budget.py`):
   - Limits total retries in a time window
   - Prevents retry storms that amplify failures
   - Tracks retries and fails fast when budget exhausted

3. **Bulkhead** (`bulkhead.py`):
   - Isolates resources for different operation types
   - Separate pools for reads, writes, and audit operations
   - Prevents one operation type from blocking others

4. **Graceful Draining** (`graceful_drain.py`):
   - Enables zero-downtime deployments
   - Stops accepting new requests during shutdown
   - Waits for in-flight requests to complete

**Integration**:
- Read path: Circuit breaker + bulkhead + graceful draining
- Write path: Circuit breaker + bulkhead + graceful draining
- All patterns accessible via `get_resilience_manager()`

**Metrics**: Available at `/health/resilience` endpoint

### 3.8 Observability

**Logging** (`logger/logging.py`):
- Centralized logging configuration
- Structured logs with timestamps, levels, and context
- Log levels: DEBUG, INFO, WARNING, ERROR

**Metrics** (`metrics/metrics.py`):
- **Read Path Metrics**:
  - `resolve_requests_total`: Total read requests
  - `resolve_cache_hit_total`: Cache hits
  - `resolve_cache_miss_total`: Cache misses
  - `resolve_negative_cache_hit_total`: Negative cache hits
  - `resolve_latency_seconds`: Read latency histogram

- **Write Path Metrics**:
  - `write_requests_total`: Total write requests
  - `write_success_total`: Successful writes
  - `write_failure_total`: Failed writes
  - `write_latency_seconds`: Write latency histogram

**Metrics Format**: Prometheus-compatible

## 4. Data Flow

### 4.1 Read Path Flow

```
Client Request
    │
    ▼
resolve_endpoint()
    │
    ├─► Check Redis Cache
    │   │
    │   ├─► Cache Hit (positive)
    │   │   └─► Return URL (fast path)
    │   │
    │   ├─► Cache Hit (negative)
    │   │   └─► Raise RouteNotFoundError
    │   │
    │   └─► Cache Miss
    │       │
    │       ▼
    │   Query PostgreSQL
    │       │
    │       ├─► Route Found
    │       │   ├─► Cache URL (60s TTL)
    │       │   └─► Return URL
    │       │
    │       └─► Route Not Found
    │           ├─► Cache negative result (10s TTL)
    │           └─► Raise RouteNotFoundError
    │
    └─► Return Response
```

### 4.2 Write Path Flow

```
Client Request
    │
    ▼
create_route() / activate_route() / deactivate_route()
    │
    ├─► Validate Inputs
    │
    ├─► Begin DB Transaction
    │   │
    │   ├─► Get/Create Tenant
    │   ├─► Get/Create Service
    │   ├─► Get/Create Environment
    │   └─► Apply Mutation (create/activate/deactivate)
    │
    ├─► Commit Transaction
    │   │
    │   └─► If commit fails → Rollback → Return Error
    │
    ├─► Publish Kafka Event (best effort)
    │   │
    │   ├─► Success → Log success
    │   └─► Failure → Log warning (non-critical)
    │
    └─► Return Success Response
```

### 4.3 Event Consumption Flow

```
Kafka Topic (route-events)
    │
    ├─► Cache Invalidation Consumer
    │   └─► Delete Redis keys for changed routes
    │
    ├─► Audit Consumer
    │   └─► Write audit logs to MongoDB
    │
    └─► Other Consumers
        └─► Custom business logic
```

## 5. Consistency Model

### 5.1 Strong Consistency

**Scope**: Database writes
- All write operations are ACID transactions
- Immediate visibility after commit
- Serialized concurrent writes via database constraints

### 5.2 Eventual Consistency

**Scope**: 
- Redis cache
- Downstream systems consuming Kafka events
- Cache invalidation consumers

**Bounded Staleness**:
- Cache TTL: 60 seconds (positive), 10 seconds (negative)
- Kafka consumer lag: Typically < 1 second

**Trade-off**: Acceptable for routing data where eventual consistency is sufficient

## 6. Failure Handling

### 6.1 Read Path Failures

| Failure | Impact | Behavior |
|---------|--------|----------|
| Redis unavailable | Cache misses | Fall back to database |
| Database unavailable | Cache misses fail | Return error |
| Cache stale | Stale data served | Bounded by TTL (60s) |

### 6.2 Write Path Failures

| Failure | Impact | Behavior |
|---------|--------|----------|
| Database failure | Write fails | Transaction rollback, return error |
| Kafka failure | Event not published | Write succeeds, log warning |
| Consumer failure | Side effects delayed | Events replayed on recovery |

### 6.3 Failure Isolation

- **Redis failure**: Doesn't affect writes, reads fall back to DB
- **Kafka failure**: Doesn't affect writes, only side effects delayed
- **Consumer failure**: Doesn't affect reads/writes, events replayed

## 7. Scalability Characteristics

### 7.1 Read Scalability

- **Redis**: Handles 100K+ requests/second
- **Cache hit rate**: Typically 80-95% for hot routes
- **Database load**: Reduced by 80-95% due to caching

### 7.2 Write Scalability

- **Database**: Limited by PostgreSQL throughput (~1K-10K writes/sec)
- **Writes are rare**: Control plane operations, not data plane
- **Rate limiting**: Can be added if needed

### 7.3 Horizontal Scaling

- **Read path**: Stateless, can scale horizontally
- **Write path**: Stateless, can scale horizontally (DB is bottleneck)
- **Kafka consumers**: Scale independently and horizontally

## 8. Technology Stack

### 8.1 Core Technologies

- **Language**: Python 3.x
- **Database**: PostgreSQL 16 (source of truth)
- **Cache**: Redis 7 (read path optimization)
- **Audit Store**: MongoDB 7 (change history and audit logs)
- **Message Queue**: Apache Kafka 7.5.0
- **Coordination**: Zookeeper (for Kafka)

### 8.2 Python Libraries

- `psycopg2`: PostgreSQL driver
- `redis`: Redis client
- `pymongo`: MongoDB client for audit store
- `kafka-python`: Kafka producer/consumer
- `prometheus-client`: Metrics collection
- **Resilience patterns**: Custom implementation (no external dependencies)

### 8.3 Infrastructure

- **Containerization**: Docker & Docker Compose
- **Orchestration**: Docker Compose for local development

## 9. Design Decisions

### 9.1 Why Cache-Aside Pattern?

- **Flexibility**: Application controls cache behavior
- **Simplicity**: Easy to understand and debug
- **Cache invalidation**: Can be done via Kafka events

### 9.2 Why Negative Caching?

- **Performance**: Avoids repeated DB queries for non-existent routes
- **Shorter TTL**: 10 seconds allows quick recovery if route is created
- **Reduces load**: Protects database from thundering herd

### 9.3 Why Kafka for Events?

- **Decoupling**: Write path doesn't wait for side effects
- **Scalability**: Consumers scale independently
- **Replayability**: Events can be replayed for recovery
- **Fan-out**: Multiple consumers can process same events

### 9.4 Why Database Transactions?

- **Correctness**: Ensures atomicity and consistency
- **Idempotency**: Unique constraints prevent duplicates
- **Durability**: Committed writes survive failures

### 9.5 Why Best-Effort Kafka Publishing?

- **Write latency**: Doesn't block on Kafka
- **Reliability**: Database is source of truth
- **Recovery**: Cache TTL ensures eventual correctness

## 10. Operational Considerations

### 10.1 Monitoring

- **Metrics**: Prometheus metrics exposed
- **Logs**: Centralized logging with structured format
- **Alerts**: Can be configured for:
  - High write failure rate
  - High cache miss rate
  - Kafka consumer lag
  - Database connection errors

### 10.2 Deployment

- **Database migrations**: Schema changes via SQL scripts
- **Zero-downtime**: Stateless services allow rolling updates
- **Configuration**: Environment variables for all settings

### 10.3 Backup & Recovery

- **Database**: PostgreSQL backups (WAL archiving)
- **MongoDB**: Audit store backups for compliance
- **Kafka**: Event replay for recovery
- **Cache**: Rebuilds automatically via cache-aside pattern

## 11. Future Enhancements

### 11.1 Potential Improvements

- **Authentication/Authorization**: RBAC for multi-tenant access
- **Rate Limiting**: Per-tenant rate limits
- **Multi-region**: Cross-region replication
- **GraphQL API**: Flexible query interface
- **WebSocket**: Real-time route updates
- **Audit Analytics**: Advanced analytics and reporting on audit data

### 11.2 Performance Optimizations

- **Connection pooling**: For database connections
- **Batch operations**: Bulk route updates
- **Read replicas**: Scale read capacity
- **Cache warming**: Pre-populate hot routes

## 12. Summary

Traffic Manager is designed as a control plane for routing configuration with:

- **Fast reads**: Sub-millisecond cache hits, eventually consistent
- **Reliable writes**: Strong consistency, ACID transactions
- **Comprehensive audit trail**: MongoDB-based audit store with rich querying capabilities
- **Scalable architecture**: Horizontal scaling for reads, independent consumer scaling
- **Fault tolerance**: Component failures don't cascade
- **Observability**: Comprehensive logging and metrics

The system prioritizes correctness for writes and performance for reads, with clear consistency guarantees, failure isolation, full auditability for compliance and debugging, and comprehensive resilience patterns (circuit breakers, retry budgets, bulkheads, and graceful draining) for production-grade reliability.
