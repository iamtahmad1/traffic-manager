# Microservices Architecture

This directory contains the microservices implementation of Traffic Manager, split from the original monolithic service.

## Services Overview

### 1. Route Resolution Service
**Port**: 8001  
**Purpose**: Handles read path operations
- Route resolution (resolve endpoint URLs)
- Audit query endpoints (read-only)
- High-throughput, cache-optimized

**Endpoints**:
- `GET /api/v1/routes/resolve` - Resolve route
- `GET /api/v1/audit/route` - Get route audit history
- `GET /api/v1/audit/recent` - Get recent audit events
- `GET /api/v1/audit/action` - Get audit events by action
- `GET /api/v1/audit/time-range` - Get audit events in time range

### 2. Route Management Service
**Port**: 8002  
**Purpose**: Handles write path operations
- Route creation
- Route activation/deactivation
- Transactional operations

**Endpoints**:
- `POST /api/v1/routes` - Create route
- `POST /api/v1/routes/activate` - Activate route
- `POST /api/v1/routes/deactivate` - Deactivate route

### 3. Cache Invalidation Consumer
**Purpose**: Consumes Kafka events and invalidates Redis cache
- Listens to `route-events` topic
- Deletes cache keys when routes change
- Ensures cache consistency

### 4. Cache Warming Consumer
**Purpose**: Consumes Kafka events and pre-warms Redis cache
- Listens to `route-events` topic
- Pre-loads cache after route changes
- Improves read performance

### 5. Audit Consumer
**Purpose**: Consumes Kafka events and stores audit logs
- Listens to `route-events` topic
- Stores audit logs in MongoDB
- Provides compliance and debugging capabilities

## Architecture

```
┌─────────────────┐
│     Client      │
└────────┬────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌─────────────────┐  ┌─────────────────┐
│ Route Resolution │  │ Route Management│
│    Service       │  │    Service      │
│   (Port 8001)    │  │   (Port 8002)   │
└────────┬─────────┘  └────────┬────────┘
         │                     │
         │                     │
         ▼                     ▼
┌─────────────────┐  ┌─────────────────┐
│   PostgreSQL    │  │      Kafka      │
│  (Source of     │  │  (route-events) │
│     Truth)      │  └────────┬────────┘
└─────────────────┘           │
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Cache Invalidation│ │ Cache Warming   │  │  Audit Consumer │
│    Consumer      │  │    Consumer     │  │                 │
└────────┬─────────┘  └────────┬────────┘  └────────┬────────┘
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│     Redis       │  │   PostgreSQL    │  │    MongoDB      │
│     (Cache)     │  │  (for warming)  │  │  (Audit Store)  │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Shared Code

All services use shared code from the `src/` directory:
- Configuration (`src/config/`)
- Database layer (`src/db/`)
- Cache layer (`src/cache/`)
- Kafka clients (`src/kafka_client/`)
- Service logic (`src/service/`)
- Resilience patterns (`src/resilience/`)
- Logging (`src/logger/`)
- Metrics (`src/metrics/`)
- Tracking (`src/tracking/`)

Each service has a minimal entry point in `services/{service-name}/main.py` that imports from the shared code.

## Running Services

### Individual Services

```bash
# Route Resolution Service
cd services/route-resolution-service
python main.py

# Route Management Service
cd services/route-management-service
python main.py

# Consumers
cd services/cache-invalidation-consumer
python main.py
```

## Service Discovery

See `service-discovery.yml` for service discovery configuration compatible with:
- Kubernetes Services
- Consul
- Eureka
- Service Mesh (Istio, Linkerd)

## Docker Images

Each service has its own Docker image:
- `{repo}-route-resolution-service:latest`
- `{repo}-route-management-service:latest`
- `{repo}-cache-invalidation-consumer:latest`
- `{repo}-cache-warming-consumer:latest`
- `{repo}-audit-consumer:latest`

## CI/CD

Each service has its own GitHub Actions workflow:
- `.github/workflows/route-resolution-service.yml`
- `.github/workflows/route-management-service.yml`
- `.github/workflows/cache-invalidation-consumer.yml`
- `.github/workflows/cache-warming-consumer.yml`
- `.github/workflows/audit-consumer.yml`

## Benefits of Microservices

1. **Independent Scaling**: Scale read and write services independently
2. **Service Discovery**: Test service mesh patterns
3. **Fault Isolation**: Failures in one service don't affect others
4. **Technology Flexibility**: Can use different tech stacks per service
5. **Team Autonomy**: Different teams can own different services
6. **Deployment Independence**: Deploy services independently

## Migration from Monolith

The original monolithic service (`src/main.py`) still exists and works. The microservices are built on top of the same shared code, making migration straightforward.
