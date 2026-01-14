# How to Check Datastores

This guide provides steps to verify that all datastores (PostgreSQL, Redis, Kafka) are working correctly.

## Prerequisites

- Docker and Docker Compose installed
- PostgreSQL, Redis, and Kafka running (via `docker-compose up`)

---

## 1. Check PostgreSQL Database

### Start PostgreSQL

```bash
cd datastore
docker-compose up -d postgresql
```

### Connect to Database

```bash
# Using psql command line
psql -h localhost -p 5432 -U app_user -d app_db

# Or using Docker exec
docker exec -it traffic-manager-postgres psql -U app_user -d app_db
```

### Check Tables

```sql
-- List all tables
\dt

-- Check tenants table
SELECT * FROM tenants;

-- Check services table
SELECT * FROM services;

-- Check environments table
SELECT * FROM environments;

-- Check endpoints table
SELECT * FROM endpoints;

-- Check route_events table (if exists)
SELECT * FROM route_events;
```

### Check Table Structure

```sql
-- Describe tenants table
\d tenants

-- Describe services table
\d services

-- Describe environments table
\d environments

-- Describe endpoints table
\d endpoints
```

### Check Data Counts

```sql
-- Count records in each table
SELECT 'tenants' as table_name, COUNT(*) as count FROM tenants
UNION ALL
SELECT 'services', COUNT(*) FROM services
UNION ALL
SELECT 'environments', COUNT(*) FROM environments
UNION ALL
SELECT 'endpoints', COUNT(*) FROM endpoints;
```

### Check Active Routes

```sql
-- List all active routes
SELECT 
    t.name as tenant,
    s.name as service,
    env.name as environment,
    e.version,
    e.url,
    e.is_active,
    e.created_at
FROM tenants t
JOIN services s ON s.tenant_id = t.id
JOIN environments env ON env.service_id = s.id
JOIN endpoints e ON e.environment_id = env.id
WHERE e.is_active = true
ORDER BY t.name, s.name, env.name, e.version;
```

### Check Specific Route

```sql
-- Check if a specific route exists
SELECT 
    t.name as tenant,
    s.name as service,
    env.name as environment,
    e.version,
    e.url,
    e.is_active
FROM tenants t
JOIN services s ON s.tenant_id = t.id
JOIN environments env ON env.service_id = s.id
JOIN endpoints e ON e.environment_id = env.id
WHERE t.name = 'team-a'
  AND s.name = 'payments'
  AND env.name = 'prod'
  AND e.version = 'v2';
```

### Exit psql

```sql
\q
```

---

## 2. Check Redis Cache

### Start Redis

```bash
cd datastore
docker-compose up -d redis
```

### Connect to Redis

```bash
# Using redis-cli
redis-cli -h localhost -p 6379

# Or using Docker exec
docker exec -it traffic-manager-redis redis-cli
```

### Check Connection

```bash
# Ping Redis server
PING
# Should return: PONG
```

### Check Keys

```bash
# List all keys
KEYS *

# List keys matching a pattern
KEYS "route:*"

# Count total keys
DBSIZE
```

### Check Specific Cache Entry

```bash
# Get a cached route (if exists)
# Cache key format: route:{tenant}:{service}:{env}:{version}
GET route:team-a:payments:prod:v2

# Check TTL (Time To Live) of a key
TTL route:team-a:payments:prod:v2
```

### Check Cache Statistics

```bash
# Get Redis info
INFO stats

# Get memory usage
INFO memory

# Get connected clients
INFO clients
```

### Clear Cache (if needed)

```bash
# Clear all keys (use with caution!)
FLUSHALL

# Clear current database only
FLUSHDB
```

### Exit redis-cli

```bash
exit
```

---

## 3. Check Kafka

### Start Kafka

```bash
cd datastore
docker-compose up -d zookeeper kafka
```

### Wait for Kafka to Start

```bash
# Wait a few seconds for Kafka to fully start
sleep 10
```

### List Topics

```bash
# Using Docker exec
docker exec -it traffic-manager-kafka kafka-topics.sh \
  --list \
  --bootstrap-server localhost:9092

# Or if kafka-topics.sh is in your PATH
kafka-topics.sh --list --bootstrap-server localhost:9092
```

### Check Topic Details

```bash
# Describe a specific topic
docker exec -it traffic-manager-kafka kafka-topics.sh \
  --describe \
  --topic route-events \
  --bootstrap-server localhost:9092
```

### Create Topic (if it doesn't exist)

```bash
docker exec -it traffic-manager-kafka kafka-topics.sh \
  --create \
  --topic route-events \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1
```

### Consume Messages (Read Events)

```bash
# Consume messages from the beginning
docker exec -it traffic-manager-kafka kafka-console-consumer.sh \
  --topic route-events \
  --from-beginning \
  --bootstrap-server localhost:9092

# Consume new messages only
docker exec -it traffic-manager-kafka kafka-console-consumer.sh \
  --topic route-events \
  --bootstrap-server localhost:9092
```

### Produce Test Message

```bash
# Produce a test message
docker exec -it traffic-manager-kafka kafka-console-producer.sh \
  --topic route-events \
  --bootstrap-server localhost:9092

# Then type a message and press Enter
# Example: {"test": "message"}
# Press Ctrl+C to exit
```

### Check Consumer Groups

```bash
# List consumer groups
docker exec -it traffic-manager-kafka kafka-consumer-groups.sh \
  --list \
  --bootstrap-server localhost:9092
```

### Check Broker Status

```bash
# Get broker information
docker exec -it traffic-manager-kafka kafka-broker-api-versions.sh \
  --bootstrap-server localhost:9092
```

---

## 4. Quick Health Check Script

Create a simple script to check all datastores:

```bash
#!/bin/bash
# check_all_datastores.sh

echo "Checking PostgreSQL..."
docker exec traffic-manager-postgres psql -U app_user -d app_db -c "SELECT COUNT(*) FROM endpoints;" || echo "✗ PostgreSQL not accessible"

echo ""
echo "Checking Redis..."
docker exec traffic-manager-redis redis-cli PING || echo "✗ Redis not accessible"

echo ""
echo "Checking Kafka..."
docker exec traffic-manager-kafka kafka-topics.sh --list --bootstrap-server localhost:9092 || echo "✗ Kafka not accessible"

echo ""
echo "Health check complete!"
```

Make it executable and run:

```bash
chmod +x check_all_datastores.sh
./check_all_datastores.sh
```

---

## 5. Using Python to Check Datastores

You can also use Python scripts to check datastores:

### Check PostgreSQL

```python
from src.db.pool import initialize_pool, get_connection, close_pool

initialize_pool()
with get_connection() as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM endpoints")
        count = cursor.fetchone()[0]
        print(f"Total endpoints: {count}")
close_pool()
```

### Check Redis

```python
from src.cache import get_redis_client

client = get_redis_client()
result = client.ping()
print(f"Redis connected: {result}")

keys = client.keys("route:*")
print(f"Cached routes: {len(keys)}")
```

### Check Kafka

```python
from src.kafka import get_kafka_producer

producer = get_kafka_producer()
topics = producer.list_topics(timeout=5)
print(f"Kafka topics: {list(topics)}")
```

---

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check PostgreSQL logs
docker logs traffic-manager-postgres

# Test connection
psql -h localhost -p 5432 -U app_user -d app_db -c "SELECT 1;"
```

### Redis Connection Issues

```bash
# Check if Redis is running
docker ps | grep redis

# Check Redis logs
docker logs traffic-manager-redis

# Test connection
redis-cli -h localhost -p 6379 PING
```

### Kafka Connection Issues

```bash
# Check if Kafka is running
docker ps | grep kafka

# Check Kafka logs
docker logs traffic-manager-kafka

# Check if Zookeeper is running (Kafka requires it)
docker ps | grep zookeeper
```

---

## Summary

- **PostgreSQL**: Use `psql` to connect and run SQL queries
- **Redis**: Use `redis-cli` to check keys and values
- **Kafka**: Use `kafka-topics.sh` and `kafka-console-consumer.sh` to check topics and messages

All datastores should be accessible and working before running the Traffic Manager application.
