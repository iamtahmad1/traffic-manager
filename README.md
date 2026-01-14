# Traffic Manager

Traffic Manager is a production-ready service for managing, routing, and controlling application traffic through APIs. It provides a control plane for route configuration with fast reads, reliable writes, and comprehensive monitoring.

## Features

- 🚀 **REST API** - Full REST API for route management
- ⚡ **High Performance** - Sub-millisecond cache hits with Redis
- 🔒 **Reliable** - Database transactions with connection pooling
- 📊 **Observable** - Prometheus metrics and health checks
- 🏗️ **Production-Ready** - Centralized config, pooling, monitoring
- 📝 **Well-Documented** - Extensive comments and documentation

## Architecture

Traffic Manager follows a layered architecture:

- **API Layer**: REST endpoints for route management
- **Service Layer**: Business logic for read/write paths
- **Cache Layer**: Redis for fast reads (cache-aside pattern)
- **Database Layer**: PostgreSQL as source of truth
- **Event Layer**: Kafka for event streaming
- **Monitoring**: Prometheus metrics and health checks

## Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Redis 6+
- Kafka 2.8+ (optional, for event streaming)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd traffic-manager
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Database

```bash
# Start PostgreSQL (using Docker Compose)
cd datastore
docker-compose up -d postgresql

# Initialize database schema
cd db
./init_db.sh
# Or manually:
# psql -U app_user -d app_db -f schema.sql
```

### 4. Set Up Redis

```bash
# Start Redis (using Docker Compose)
cd datastore
docker-compose up -d redis
```

### 5. Set Up Kafka (Optional)

```bash
# Start Kafka (using Docker Compose)
cd datastore
docker-compose up -d zookeeper kafka
```

## Configuration

Configuration is managed through environment variables. All settings have sensible defaults for local development.

### Database Configuration

```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=app_db
export DB_USER=app_user
export DB_PASSWORD=your_password
export DB_POOL_MIN=2
export DB_POOL_MAX=10
```

### Redis Configuration

```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_MAX_CONNECTIONS=50
```

### Kafka Configuration

```bash
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export KAFKA_ROUTE_EVENTS_TOPIC=route-events
export KAFKA_ACKS=all
export KAFKA_IDEMPOTENT=true
```

### Application Configuration

```bash
export API_HOST=0.0.0.0
export API_PORT=8000
export APP_ENVIRONMENT=development
export APP_DEBUG=true
export APP_LOG_LEVEL=INFO
export APP_POSITIVE_CACHE_TTL=60
export APP_NEGATIVE_CACHE_TTL=10
```

See `src/config/settings.py` for all available configuration options.

## Running the Application

### Start the Server

```bash
python src/main.py
```

The server will start on `http://0.0.0.0:8000` (or your configured `API_HOST:API_PORT`).

### Verify It's Running

```bash
# Health check
curl http://localhost:8000/health

# Readiness check (checks all dependencies)
curl http://localhost:8000/health/ready

# Metrics endpoint
curl http://localhost:8000/metrics
```

## API Endpoints

### Read Path

#### Resolve Route

Get the endpoint URL for a route.

```bash
curl "http://localhost:8000/api/v1/routes/resolve?tenant=team-a&service=payments&env=prod&version=v2"
```

**Response:**
```json
{
  "url": "https://payments.example.com/v2"
}
```

**Query Parameters:**
- `tenant` (required): Tenant name
- `service` (required): Service name
- `env` (required): Environment (prod, staging, etc.)
- `version` (required): Version (v1, v2, etc.)

### Write Path

#### Create Route

Create a new route configuration.

```bash
curl -X POST http://localhost:8000/api/v1/routes \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v2",
    "url": "https://payments.example.com/v2"
  }'
```

**Response:**
```json
{
  "message": "Route created successfully",
  "route": {
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v2",
    "url": "https://payments.example.com/v2",
    "is_active": true
  }
}
```

#### Activate Route

Activate an existing route.

```bash
curl -X POST http://localhost:8000/api/v1/routes/activate \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v2"
  }'
```

#### Deactivate Route

Deactivate an existing route.

```bash
curl -X POST http://localhost:8000/api/v1/routes/deactivate \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v2"
  }'
```

## Health Checks

### Basic Health Check

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "traffic-manager"
}
```

### Readiness Probe

Checks if the service is ready to accept traffic (verifies database, cache, kafka).

```bash
curl http://localhost:8000/health/ready
```

**Response:**
```json
{
  "status": "ready",
  "checks": {
    "database": {
      "status": "healthy",
      "message": "Database is accessible",
      "pool": {
        "initialized": true,
        "min_connections": 2,
        "max_connections": 10,
        "current_connections": 3,
        "available_connections": 7
      }
    },
    "cache": {
      "status": "healthy",
      "message": "Cache is accessible"
    },
    "kafka": {
      "status": "healthy",
      "message": "Kafka is accessible"
    }
  }
}
```

### Liveness Probe

Checks if the service process is alive.

```bash
curl http://localhost:8000/health/live
```

**Response:**
```json
{
  "status": "alive",
  "service": "traffic-manager"
}
```

## Monitoring

### Prometheus Metrics

The application exposes Prometheus metrics at `/metrics`:

```bash
curl http://localhost:8000/metrics
```

**Available Metrics:**

- **Business Metrics**: Request counts, cache hits/misses, latency
- **Infrastructure Metrics**: Connection pool status, cache connectivity, kafka status
- **API Metrics**: HTTP request counts and latencies per endpoint

### Setting Up Prometheus

1. **Install Prometheus**: Download from [prometheus.io](https://prometheus.io/download/)

2. **Configure Prometheus** (`prometheus.yml`):
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'traffic-manager'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

3. **Start Prometheus**:
```bash
prometheus --config.file=prometheus.yml
```

4. **Access Prometheus UI**: http://localhost:9090

### Example Queries

```promql
# Request rate
rate(resolve_requests_total[5m])

# Cache hit rate
rate(resolve_cache_hit_total[5m]) / rate(resolve_requests_total[5m])

# P95 latency
histogram_quantile(0.95, resolve_latency_seconds_bucket)

# Connection pool usage
db_pool_in_use / db_pool_size * 100
```

For detailed monitoring setup, see [docs/10-monitoring-guide.md](docs/10-monitoring-guide.md).

## Kafka Consumers

Three common consumer use cases are implemented in `src/kafka_client/consumer.py`:

1. **Cache Invalidation Consumer (MOST IMPORTANT)**
   - Deletes cached routes when a change event arrives
2. **Cache Warming Consumer (VERY COMMON)**
   - Pre-loads cache after a change so reads stay fast
3. **Audit / Change Log Consumer (EXTREMELY COMMON)**
   - Writes route change events to the `route_events` table

### Run a Consumer

```bash
# Most important: invalidate cache on every change
python scripts/run_consumer.py cache_invalidation

# Warm cache after changes
python scripts/run_consumer.py cache_warming

# Save events for audit/history
python scripts/run_consumer.py audit_log
```

## End-to-End Test (API → Kafka → Consumers)

This walks through the full flow: API write → Kafka event → consumers react.

### 1. Start dependencies

```bash
cd datastore
docker-compose up -d
```

### 2. Initialize the database schema

```bash
cd datastore/db
./init_db.sh
```

### 3. Start the API server

```bash
cd ../..
source venv/bin/activate
python src/main.py
```

### 4. Start consumers (3 terminals)

```bash
source venv/bin/activate
python scripts/run_consumer.py cache_invalidation
```

```bash
source venv/bin/activate
python scripts/run_consumer.py cache_warming
```

```bash
source venv/bin/activate
python scripts/run_consumer.py audit_log
```

### 5. Trigger a route change (write path)

```bash
curl -X POST http://localhost:8000/api/v1/routes \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v1",
    "url": "https://payments.example.com/v1"
  }'
```

### 6. Verify cache invalidation + warming

```bash
# Check Redis key (should exist after warming)
redis-cli GET route:team-a:payments:prod:v1

# Check TTL (should be positive)
redis-cli TTL route:team-a:payments:prod:v1
```

### 7. Verify audit log in PostgreSQL

```bash
psql -U app_user -d app_db -h localhost \
  -c "SELECT tenant, service, env, version, action, created_at FROM route_events ORDER BY created_at DESC LIMIT 5;"
```

### 8. Check consumer logs

You should see logs like:
- `Cache invalidated: route:team-a:payments:prod:v1`
- `Cache warmed: team-a/payments/prod/v1`
- `Audit log saved: team-a/payments/prod/v1 action=created`

## Example Workflow

### 1. Create a Route

```bash
curl -X POST http://localhost:8000/api/v1/routes \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v2",
    "url": "https://payments.example.com/v2"
  }'
```

### 2. Resolve the Route

```bash
curl "http://localhost:8000/api/v1/routes/resolve?tenant=team-a&service=payments&env=prod&version=v2"
```

### 3. Deactivate the Route

```bash
curl -X POST http://localhost:8000/api/v1/routes/deactivate \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v2"
  }'
```

### 4. Activate the Route Again

```bash
curl -X POST http://localhost:8000/api/v1/routes/activate \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v2"
  }'
```

## Project Structure

```
traffic-manager/
├── src/                    # Source code
│   ├── api/               # REST API layer
│   ├── cache/             # Redis cache client
│   ├── config/            # Configuration management
│   ├── db/                # Database layer (connection pooling)
│   ├── kafka_client/      # Kafka event producer
│   ├── logger/            # Logging configuration
│   ├── metrics/           # Prometheus metrics definitions
│   ├── monitoring/        # Monitoring and observability
│   ├── service/           # Business logic
│   └── main.py            # Application entry point
├── datastore/             # Database setup and Docker Compose
├── docs/                   # Documentation
├── architecture/          # Architecture documentation
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

For detailed structure information, see [src/STRUCTURE.md](src/STRUCTURE.md).

## Documentation

- **[Core Concepts](docs/01-core-concepts.md)** - Fundamental concepts and terminology
- **[Consistency Models](docs/02-consistency-models.md)** - Consistency and CAP theorem
- **[Caching Strategies](docs/03-caching-strategies.md)** - Cache-aside pattern and TTL strategies
- **[Event-Driven Architecture](docs/04-event-driven-architecture.md)** - Kafka and event streaming
- **[Database Design](docs/05-database-design-principles.md)** - Schema design and transactions
- **[Scalability Patterns](docs/06-scalability-patterns.md)** - Horizontal scaling and load balancing
- **[Failure Handling](docs/07-failure-handling-resilience.md)** - Resilience patterns
- **[Production Readiness](docs/08-production-readiness.md)** - Production patterns assessment
- **[Implemented Patterns](docs/09-production-patterns-implemented.md)** - What's been implemented
- **[Monitoring Guide](docs/10-monitoring-guide.md)** - Monitoring setup and usage

## Development

### Running in Development Mode

```bash
export APP_DEBUG=true
export APP_LOG_LEVEL=DEBUG
python src/main.py
```

### Code Structure

The codebase follows production patterns with extensive comments for learning:

- **Centralized Configuration**: `src/config/settings.py`
- **Connection Pooling**: `src/db/pool.py`
- **REST API**: `src/api/app.py`
- **Health Checks**: Integrated in API
- **Monitoring**: `src/monitoring/`

## Production Deployment

### Environment Variables

Set all required environment variables for your production environment:

```bash
export DB_HOST=your-db-host
export DB_PASSWORD=secure-password
export REDIS_HOST=your-redis-host
export KAFKA_BOOTSTRAP_SERVERS=your-kafka-servers
export APP_ENVIRONMENT=production
export APP_DEBUG=false
```

### Health Checks for Kubernetes

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Prometheus Scraping

Configure Prometheus to scrape `/metrics` endpoint for monitoring.

## Troubleshooting

### Database Connection Issues

```bash
# Check database is running
docker ps | grep postgres

# Test connection
psql -U app_user -d app_db -h localhost

# Check logs
python src/main.py
```

### Redis Connection Issues

```bash
# Check Redis is running
docker ps | grep redis

# Test connection
redis-cli ping
```

### Kafka Connection Issues

```bash
# Check Kafka is running
docker ps | grep kafka

# List topics
kafka-topics.sh --list --bootstrap-server localhost:9092
```

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

---

**Note**: This is a learning project with extensive comments explaining production patterns. The codebase demonstrates real-world practices while maintaining educational value.
