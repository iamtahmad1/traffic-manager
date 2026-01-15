# Datastore Setup

This directory contains Docker Compose configuration for all data stores used by Traffic Manager.

## Services

- **PostgreSQL 16**: Primary database (source of truth)
- **Redis 7**: Cache layer
- **MongoDB 7**: Audit store for route change history
- **Zookeeper**: Coordination service for Kafka
- **Kafka 7.5.0**: Event streaming platform

## Quick Start

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f

# Stop all services
docker compose down

# Stop and remove volumes (⚠️ deletes data)
docker compose down -v
```

## Kafka Replication Configuration

### Current Setup (Single Broker)

The current configuration uses **replication factor 1** because we have only **1 Kafka broker**.

**Important**: You cannot have replication factor 3 with only 1 broker. You need at least 3 brokers for replication factor 3.

### Current Configuration

- `KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1` - Required for single broker
- `KAFKA_DEFAULT_REPLICATION_FACTOR: 1` - Default for auto-created topics
- `KAFKA_NUM_PARTITIONS: 1` - Default partitions for auto-created topics

### For Production (Replication Factor 3)

If you need replication factor 3, you would need to:

1. **Add 2 more Kafka brokers** (total of 3)
2. **Update replication settings** to 3
3. **Create topics explicitly** with replication factor 3

Example for 3 brokers:
```yaml
kafka-1:
  KAFKA_BROKER_ID: 1
  KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3
  KAFKA_DEFAULT_REPLICATION_FACTOR: 3

kafka-2:
  KAFKA_BROKER_ID: 2
  KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3
  KAFKA_DEFAULT_REPLICATION_FACTOR: 3

kafka-3:
  KAFKA_BROKER_ID: 3
  KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3
  KAFKA_DEFAULT_REPLICATION_FACTOR: 3
```

### Creating Topics with Replication Factor 3

Even with replication factor 1 in the config, you can create topics explicitly:

```bash
# Connect to Kafka container
docker exec -it kafka bash

# Create topic with replication factor 3 (requires 3 brokers)
kafka-topics --create \
  --bootstrap-server localhost:9092 \
  --topic route-events \
  --partitions 3 \
  --replication-factor 3
```

**Note**: This will fail with a single broker. You need 3 brokers for replication factor 3.

## Environment Variables

### PostgreSQL

Set these in `.env` file:
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `POSTGRES_PORT` (default: 5432)

### MongoDB

Set these in `.env` file:
- `MONGODB_USER` (default: admin)
- `MONGODB_PASSWORD` (default: admin_password)
- `MONGODB_DB` (default: audit_db)
- `MONGODB_PORT` (default: 27017)

### Kafka

- `KAFKA_BOOTSTRAP_SERVERS`: `localhost:9092` (default)

## Ports

- **PostgreSQL**: 5432
- **Redis**: 6379
- **MongoDB**: 27017
- **Zookeeper**: 2181
- **Kafka**: 9092

## Volumes

All data is persisted in Docker volumes:
- `postgres_data`: PostgreSQL data
- `redis_data`: Redis data
- `mongodb_data`: MongoDB data
- `zookeeper_data`: Zookeeper data
- `zookeeper_logs`: Zookeeper logs
- `kafka_data`: Kafka logs and data

## Health Checks

```bash
# Check PostgreSQL
docker exec postgres pg_isready

# Check Redis
docker exec redis redis-cli ping

# Check MongoDB
docker exec mongodb mongosh --eval "db.adminCommand('ping')"

# Check Kafka
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# Check Zookeeper
docker exec zookeeper zkServer.sh status
```

## Troubleshooting

### Kafka won't start

1. Check Zookeeper is running: `docker compose ps zookeeper`
2. Check Kafka logs: `docker compose logs kafka`
3. Ensure ports 9092 and 2181 are not in use

### Connection refused errors

- Ensure all services are running: `docker compose ps`
- Check service logs: `docker compose logs <service-name>`
- Verify ports are not blocked by firewall

### Data persistence issues

- Volumes are created automatically
- To reset: `docker compose down -v` (⚠️ deletes all data)
- To backup: Copy volume data from Docker's volume directory

## Performance Tuning

### Kafka

Current memory settings: `-Xmx512M -Xms512M`

For higher throughput, you can increase:
```yaml
KAFKA_HEAP_OPTS: "-Xmx1G -Xms1G"
```

### PostgreSQL

Default settings are suitable for development. For production, tune:
- `shared_buffers`
- `effective_cache_size`
- `work_mem`

### Redis

Current setup uses append-only file (AOF) for durability. For higher performance:
- Consider disabling AOF if durability is less critical
- Increase `maxmemory` if needed

## Security Notes

⚠️ **This setup is for development only!**

For production:
- Use strong passwords
- Enable SSL/TLS for all connections
- Restrict network access
- Use secrets management
- Enable Kafka authentication (SASL/SSL)
- Enable PostgreSQL SSL connections
