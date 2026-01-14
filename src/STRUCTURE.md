# Source Code Structure

This document explains the organization of the `src/` folder and the purpose of each module.

## Directory Structure

```
src/
├── api/              # REST API layer (Flask endpoints)
├── cache/            # Cache layer (Redis client)
├── config/           # Centralized configuration management
├── db/               # Database layer (PostgreSQL connection & pooling)
├── kafka_client/     # Event streaming (Kafka producer)
├── logger/           # Logging configuration
├── metrics/          # Metrics definitions (Prometheus)
├── monitoring/       # Monitoring and observability
├── service/          # Business logic (read/write paths)
└── main.py           # Application entry point
```

## Module Descriptions

### `api/` - API Layer
**Purpose**: REST API endpoints and health checks

**Files**:
- `__init__.py`: Package exports
- `app.py`: Flask application and route definitions

**Exports**:
- `create_app()`: Flask application factory

**Endpoints**:
- `GET /api/v1/routes/resolve` - Resolve endpoint URL (read path)
- `POST /api/v1/routes` - Create route (write path)
- `POST /api/v1/routes/activate` - Activate route (write path)
- `POST /api/v1/routes/deactivate` - Deactivate route (write path)
- `GET /health` - Basic health check
- `GET /health/ready` - Readiness probe (checks dependencies)
- `GET /health/live` - Liveness probe
- `GET /metrics` - Prometheus metrics endpoint

**Used by**: `main.py` (starts the API server)

---

### `cache/` - Cache Layer
**Purpose**: Redis cache client and operations

**Files**:
- `__init__.py`: Package exports
- `redis_client.py`: Redis client creation

**Exports**:
- `get_redis_client()`: Creates and returns Redis client

**Used by**: `service/routing.py` (read path)

---

### `db/` - Database Layer
**Purpose**: PostgreSQL database connection and connection pooling

**Files**:
- `__init__.py`: Package exports
- `connection.py`: Direct database connection (legacy, for reference)
- `pool.py`: Connection pooling (production pattern)

**Exports**:
- `get_db_connection()`: Creates direct database connection (legacy)
- `initialize_pool()`: Initializes connection pool
- `close_pool()`: Closes connection pool
- `get_connection()`: Context manager to get connection from pool
- `get_pool_status()`: Returns pool status information

**Used by**: All service modules (via connection pool)

**Note**: Connection pooling is the recommended production pattern for better performance and resource management.

---

### `kafka_client/` - Event Streaming
**Purpose**: Kafka event publishing

**Files**:
- `__init__.py`: Package exports
- `producer.py`: Kafka producer and event publishing
- `consumer.py`: Kafka consumers (cache invalidation, warming, audit)

**Exports**:
- `get_kafka_producer()`: Creates Kafka producer
- `publish_route_event()`: Publishes route change events
- `ROUTE_EVENTS_TOPIC`: Topic name constant

**Used by**: `service/write_path.py` (write path)

---

### `logger/` - Logging
**Purpose**: Centralized logging configuration

**Files**:
- `__init__.py`: Package exports
- `logging.py`: Logging setup and configuration

**Exports**:
- `setup_logging()`: Configures logging
- `get_logger()`: Gets logger instance

**Used by**: All modules

---

### `config/` - Configuration Management
**Purpose**: Centralized configuration with environment variable support

**Files**:
- `__init__.py`: Package exports
- `settings.py`: Configuration dataclasses and settings object

**Exports**:
- `settings`: Global settings object with all configuration

**Configuration sections**:
- `settings.db` - Database configuration
- `settings.redis` - Redis cache configuration
- `settings.kafka` - Kafka configuration
- `settings.app` - Application configuration

**Used by**: All modules that need configuration

---

### `metrics/` - Metrics Definitions
**Purpose**: Prometheus metric definitions

**Files**:
- `__init__.py`: Package exports
- `metrics.py`: Metric definitions (Counters, Histograms, Gauges)

**Exports**:
- Read path metrics: `RESOLVE_REQUESTS_TOTAL`, `CACHE_HIT_TOTAL`, etc.
- Write path metrics: `WRITE_REQUESTS_TOTAL`, `WRITE_SUCCESS_TOTAL`, etc.
- Latency histograms: `RESOLVE_LATENCY_SECONDS`, `WRITE_LATENCY_SECONDS`
- Kafka metrics: `KAFKA_EVENTS_PUBLISHED_TOTAL`, `KAFKA_EVENTS_FAILED_TOTAL`
- Database metrics: `DB_QUERIES_TOTAL`, `DB_CONNECTION_ERRORS_TOTAL`

**Used by**: `service/routing.py`, `service/write_path.py`, `kafka_client/producer.py`, `db/pool.py`

---

### `monitoring/` - Monitoring and Observability
**Purpose**: Monitoring infrastructure and metrics exposure

**Files**:
- `__init__.py`: Package exports
- `metrics_endpoint.py`: Prometheus `/metrics` endpoint setup
- `system_metrics.py`: System metrics collection (connection pool, cache, kafka)
- `middleware.py`: Request monitoring middleware

**Exports**:
- `setup_metrics_endpoint()`: Sets up `/metrics` endpoint
- `setup_request_monitoring()`: Sets up request tracking middleware
- `start_metrics_collector()`: Starts background system metrics collection
- `collect_system_metrics()`: Collects system metrics

**What it does**:
- Exposes Prometheus metrics endpoint (`/metrics`)
- Automatically tracks all HTTP requests (count, latency, status codes)
- Collects system metrics (connection pool, cache connectivity, kafka status)
- Runs background thread for periodic metric updates

**Used by**: `api/app.py` (integrated into Flask app)

---

### `service/` - Business Logic
**Purpose**: Core business logic for read and write paths

**Files**:
- `__init__.py`: Package exports
- `routing.py`: Read path (route resolution)
- `write_path.py`: Write path (route management)

**Exports**:
- `resolve_endpoint()`: Resolves endpoint URL (read path)
- `RouteNotFoundError`: Exception for missing routes
- `create_route()`: Creates new route (write path)
- `activate_route()`: Activates route (write path)
- `deactivate_route()`: Deactivates route (write path)

**Used by**: `main.py`

---

### `main.py` - Application Entry Point
**Purpose**: Main application file that orchestrates the system

**Responsibilities**:
- Initialize services (database pool, cache, kafka)
- Create and start Flask API server
- Handle errors and graceful shutdown
- Clean up resources on exit

**Usage**:
```bash
python src/main.py
```

**What it does**:
1. Initializes database connection pool
2. Initializes Redis cache client
3. Initializes Kafka producer
4. Creates Flask application with all routes and monitoring
5. Starts HTTP server on configured host/port
6. Handles graceful shutdown on exit

---

## Import Patterns

### Absolute Imports (Recommended)

```python
from db.connection import get_db_connection
from cache.redis_client import get_redis_client
from service.routing import resolve_endpoint
```

### Package-Level Imports

```python
from db import get_db_connection
from cache import get_redis_client
from service import resolve_endpoint
```

Both patterns work because each package has `__init__.py` that exports the functions.

---

## Design Principles

1. **Separation of Concerns**: Each module has a single responsibility
2. **Package Structure**: All modules are proper Python packages with `__init__.py`
3. **Clear Exports**: Each `__init__.py` clearly defines what's exported
4. **Layered Architecture**: Clear separation between infrastructure (db, cache, kafka) and business logic (service)
5. **Dependency Direction**: Business logic depends on infrastructure, not vice versa

---

## Adding New Modules

When adding a new module:

1. **Create folder** with descriptive name
2. **Add `__init__.py`** that exports public API
3. **Document purpose** in this file
4. **Follow naming conventions**: lowercase, underscores
5. **Keep it focused**: One responsibility per module

---

## File Naming Conventions

- **Modules**: `snake_case.py` (e.g., `redis_client.py`)
- **Packages**: `snake_case/` (e.g., `cache/`)
- **Classes**: `PascalCase` (e.g., `RouteNotFoundError`)
- **Functions**: `snake_case` (e.g., `get_redis_client()`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `ROUTE_EVENTS_TOPIC`)

---

## Dependencies Between Modules

```
main.py
  └─> api/
        ├─> service/
        │     ├─> db/
        │     ├─> cache/
        │     ├─> kafka_client/
        │     ├─> logger/
        │     └─> metrics/
        ├─> monitoring/
        │     ├─> metrics/
        │     ├─> db/
        │     ├─> cache/
        │     └─> kafka_client/
        └─> config/
```

**Key points**:
- `main.py` depends on `api/` and `config/`
- `api/` depends on `service/` and `monitoring/`
- `service/` depends on infrastructure modules (`db/`, `cache/`, `kafka_client/`)
- `monitoring/` depends on infrastructure modules for system metrics
- All modules depend on `config/` for configuration
- All modules depend on `logger/` for logging
- Infrastructure modules are independent
- No circular dependencies

---

This structure follows Python best practices and makes the codebase maintainable and easy to understand.

---

## Production Readiness

**Current Status**: Production-ready structure (~85% production-ready)

**What's Production-Ready**:
- ✅ Modular, well-organized structure
- ✅ Proper package organization
- ✅ Centralized logging and metrics
- ✅ **Centralized configuration management** (`config/`)
- ✅ **Connection pooling** (database connections via `db/pool.py`)
- ✅ **REST API layer** (`api/` with Flask)
- ✅ **Health check endpoints** (`/health`, `/health/ready`, `/health/live`)
- ✅ **Monitoring and observability** (`monitoring/` with Prometheus)
- ✅ **Request tracking middleware** (automatic API metrics)
- ✅ **System metrics collection** (connection pool, cache, kafka status)
- ✅ Environment variable usage
- ✅ Clear separation of concerns

**What's Still Missing for Full Production**:
- ⚠️ Input validation layer (Pydantic)
- ⚠️ Authentication/Authorization
- ⚠️ Rate limiting
- ⚠️ Comprehensive test suite
- ⚠️ Dockerfile for containerization
- ⚠️ CI/CD pipelines
- ⚠️ Grafana dashboards (monitoring setup)

**For detailed production readiness analysis**, see `../docs/08-production-readiness.md`

**For implemented production patterns**, see `../docs/09-production-patterns-implemented.md`

**Note**: This structure is now **production-ready** with all high-priority patterns implemented. The codebase demonstrates production best practices while maintaining educational value with extensive comments.
