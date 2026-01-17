# Monitoring Guide

This document explains the monitoring capabilities in Traffic Manager and how to use them.

## Table of Contents

1. [Overview](#overview)
2. [Prometheus Metrics Endpoint](#prometheus-metrics-endpoint)
3. [Available Metrics](#available-metrics)
4. [Health Check Endpoints](#health-check-endpoints)
5. [Setting Up Prometheus](#setting-up-prometheus)
6. [Grafana Dashboards](#grafana-dashboards)
7. [Alerting Rules](#alerting-rules)

---

## Overview

Traffic Manager exposes comprehensive monitoring through:

1. **Prometheus Metrics** (`/metrics`) - All application metrics
2. **Health Checks** (`/health`, `/health/ready`, `/health/live`) - Service health
3. **System Metrics** - Infrastructure status (connection pools, cache, kafka)
4. **Request Metrics** - Automatic tracking of all API requests

---

## Prometheus Metrics Endpoint

### Endpoint
`GET /metrics`

### Purpose
Exposes all Prometheus metrics in standard format for scraping.

### Usage
```bash
# Get all metrics
curl http://localhost:8000/metrics
```

### Output Format
Prometheus text format:
```
# HELP resolve_requests_total Total number of resolve requests
# TYPE resolve_requests_total counter
resolve_requests_total 1234.0

# HELP resolve_latency_seconds Latency of resolve requests
# TYPE resolve_latency_seconds histogram
resolve_latency_seconds_bucket{le="0.005"} 1000.0
resolve_latency_seconds_bucket{le="0.01"} 1200.0
resolve_latency_seconds_bucket{le="0.025"} 1230.0
...
```

---

## Available Metrics

### Metric Types Explained

**Counter**: Monotonically increasing value (only goes up)
- Use for: Request counts, error counts, events
- Example: `resolve_requests_total` - total requests since startup
- PromQL: Use `rate()` or `increase()` to get per-second rates

**Histogram**: Distribution of values (buckets)
- Use for: Latency, sizes, durations
- Example: `resolve_latency_seconds` - request latency distribution
- PromQL: Use `histogram_quantile()` for percentiles (p50, p95, p99)

**Gauge**: Value that can go up or down
- Use for: Current state, resource usage, active connections
- Example: `db_pool_in_use` - current connections in use
- PromQL: Use directly or with `delta()` for changes

### Read Path Metrics

#### `resolve_requests_total`
- **Type**: Counter
- **Description**: Total number of route resolution requests
- **Labels**: None
- **Use**: Track request volume, calculate request rate
- **PromQL Examples**:
  ```promql
  # Request rate (requests per second)
  rate(resolve_requests_total[5m])
  
  # Total requests in last hour
  increase(resolve_requests_total[1h])
  ```

#### `resolve_cache_hit_total`
- **Type**: Counter
- **Description**: Number of cache hits (fast path)
- **Use**: Calculate cache hit rate

#### `resolve_cache_miss_total`
- **Type**: Counter
- **Description**: Number of cache misses (database queries)
- **Use**: Calculate cache hit rate

#### `resolve_negative_cache_hit_total`
- **Type**: Counter
- **Description**: Number of negative cache hits (404s from cache)
- **Use**: Track how often we cache "not found" results

#### `resolve_latency_seconds`
- **Type**: Histogram
- **Description**: Distribution of request latencies in seconds
- **Buckets**: Default Prometheus buckets (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10)
- **Use**: Monitor performance, calculate p50/p95/p99, detect latency spikes
- **PromQL Examples**:
  ```promql
  # P50 latency (median)
  histogram_quantile(0.50, rate(resolve_latency_seconds_bucket[5m]))
  
  # P95 latency (95th percentile)
  histogram_quantile(0.95, rate(resolve_latency_seconds_bucket[5m]))
  
  # P99 latency (99th percentile)
  histogram_quantile(0.99, rate(resolve_latency_seconds_bucket[5m]))
  
  # Average latency
  rate(resolve_latency_seconds_sum[5m]) / rate(resolve_latency_seconds_count[5m])
  
  # Requests slower than 100ms
  sum(rate(resolve_latency_seconds_bucket{le="0.1"}[5m]))
  ```
- **Technical Details**:
  - Histograms track counts in buckets (e.g., "how many requests took < 10ms?")
  - `_bucket` metrics: Count per bucket
  - `_sum` metric: Sum of all values
  - `_count` metric: Total count
  - Use `histogram_quantile()` to calculate percentiles from buckets

### Write Path Metrics

#### `write_requests_total`
- **Type**: Counter
- **Description**: Total write operations (create/activate/deactivate)
- **Use**: Track write volume

#### `write_success_total`
- **Type**: Counter
- **Description**: Successful write operations
- **Use**: Calculate success rate

#### `write_failure_total`
- **Type**: Counter
- **Description**: Failed write operations
- **Use**: Calculate error rate, alert on failures

#### `write_latency_seconds`
- **Type**: Histogram
- **Description**: Distribution of write operation latencies
- **Use**: Monitor write performance

### API Request Metrics

#### `api_requests_total`
- **Type**: Counter
- **Labels**: `method`, `endpoint`, `status_code`
- **Description**: Total HTTP requests to API
- **Use**: Track API usage by endpoint and status code

#### `api_request_duration_seconds`
- **Type**: Histogram
- **Labels**: `method`, `endpoint`
- **Description**: HTTP request duration
- **Use**: Monitor API performance per endpoint

### Kafka Metrics

#### `kafka_events_published_total`
- **Type**: Counter
- **Labels**: `action` (created/activated/deactivated)
- **Description**: Successfully published events
- **Use**: Track event publishing success

#### `kafka_events_failed_total`
- **Type**: Counter
- **Labels**: `action`
- **Description**: Failed event publications
- **Use**: Detect Kafka issues

### Database Metrics

#### `db_queries_total`
- **Type**: Counter
- **Description**: Total database queries executed
- **Use**: Monitor database load

#### `db_connection_errors_total`
- **Type**: Counter
- **Description**: Database connection errors
- **Use**: Alert on connection pool exhaustion

### System Metrics

#### `db_pool_size`
- **Type**: Gauge
- **Description**: Maximum connections in pool
- **Use**: Monitor pool configuration

#### `db_pool_available`
- **Type**: Gauge
- **Description**: Available connections in pool
- **Use**: Detect pool exhaustion

#### `db_pool_in_use`
- **Type**: Gauge
- **Description**: Connections currently in use
- **Use**: Monitor connection usage

#### `cache_connected`
- **Type**: Gauge (0 or 1)
- **Description**: Redis cache connectivity
- **Use**: Alert if cache is down

#### `kafka_producer_ready`
- **Type**: Gauge (0 or 1)
- **Description**: Kafka producer status
- **Use**: Alert if Kafka is down

#### `application_uptime_seconds`
- **Type**: Gauge
- **Description**: Application uptime
- **Use**: Track service availability

---

## Health Check Endpoints

### `/health` - Basic Health Check
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

**Use case**: Simple uptime monitoring

### `/health/ready` - Readiness Probe
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

**Use case**: 
- Kubernetes readiness probe
- Load balancer health checks
- Dependency monitoring

### `/health/live` - Liveness Probe
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

**Use case**: Kubernetes liveness probe (restart container if fails)

---

## Setting Up Prometheus

### 1. Install Prometheus

Download from [prometheus.io](https://prometheus.io/download/)

### 2. Configure Prometheus

Create `prometheus.yml`:
```yaml
global:
  scrape_interval: 15s  # How often to scrape metrics

scrape_configs:
  - job_name: 'traffic-manager'
    static_configs:
      - targets: ['localhost:8000']  # Your API server
    metrics_path: '/metrics'  # Prometheus metrics endpoint
```

### 3. Start Prometheus

```bash
prometheus --config.file=prometheus.yml
```

### 4. Access Prometheus UI

Open http://localhost:9090

### 5. Query Metrics

Example queries:
```promql
# Request rate
rate(resolve_requests_total[5m])

# Cache hit rate
rate(resolve_cache_hit_total[5m]) / rate(resolve_requests_total[5m])

# Error rate
rate(write_failure_total[5m])

# P95 latency
histogram_quantile(0.95, resolve_latency_seconds_bucket)
```

---

## Grafana Dashboards

### Creating a Dashboard

1. **Install Grafana**: Download from [grafana.com](https://grafana.com/grafana/download)
2. **Add Prometheus Data Source**: Point to your Prometheus instance
3. **Create Dashboard Panels**:

#### Request Rate Panel
```
Query: rate(resolve_requests_total[5m])
Visualization: Graph
Title: Request Rate
```

#### Cache Hit Rate Panel
```
Query: rate(resolve_cache_hit_total[5m]) / rate(resolve_requests_total[5m]) * 100
Visualization: Gauge
Title: Cache Hit Rate (%)
```

#### Latency Panel
```
Query: histogram_quantile(0.95, resolve_latency_seconds_bucket)
Visualization: Graph
Title: P95 Latency
```

#### Error Rate Panel
```
Query: rate(write_failure_total[5m])
Visualization: Graph
Title: Write Error Rate
```

#### Connection Pool Panel
```
Query: db_pool_in_use / db_pool_size * 100
Visualization: Gauge
Title: Connection Pool Usage (%)
```

---

## Advanced PromQL Queries

### Calculating Rates and Percentiles

```promql
# Request rate (requests per second over 5 minutes)
rate(resolve_requests_total[5m])

# Cache hit rate percentage
(rate(resolve_cache_hit_total[5m]) / rate(resolve_requests_total[5m])) * 100

# Error rate (errors per second)
rate(write_failure_total[5m])

# Error percentage
(rate(write_failure_total[5m]) / rate(write_requests_total[5m])) * 100

# Connection pool utilization
(db_pool_in_use / db_pool_size) * 100

# P95 latency
histogram_quantile(0.95, rate(resolve_latency_seconds_bucket[5m]))

# Requests per second by endpoint (if you add endpoint label)
sum(rate(api_requests_total[5m])) by (endpoint)
```

### Time-Based Queries

```promql
# Compare current vs 1 hour ago
resolve_requests_total - resolve_requests_total offset 1h

# Growth rate (requests per hour)
increase(resolve_requests_total[1h])

# Average over time window
avg_over_time(resolve_requests_total[1h])
```

### Aggregation Queries

```promql
# Sum across all instances
sum(resolve_requests_total)

# Average across instances
avg(resolve_requests_total)

# Maximum value
max(resolve_requests_total)

# Group by label
sum(rate(resolve_requests_total[5m])) by (tenant)
```

---

## Alerting Rules

### Prometheus Alert Rules

**Best Practices**:
- Alert on symptoms, not causes
- Use meaningful thresholds based on SLOs
- Include runbook links in annotations
- Avoid alert fatigue (don't alert on every small issue)
- Use alert grouping and inhibition

Create `alerts.yml`:
```yaml
groups:
  - name: traffic_manager
    rules:
      # High error rate
      - alert: HighWriteErrorRate
        expr: rate(write_failure_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High write error rate"
          description: "Write error rate is {{ $value }} errors/sec"

      # Low cache hit rate
      - alert: LowCacheHitRate
        expr: rate(resolve_cache_hit_total[5m]) / rate(resolve_requests_total[5m]) < 0.7
        for: 10m
        annotations:
          summary: "Low cache hit rate"
          description: "Cache hit rate is {{ $value | humanizePercentage }}"

      # High latency
      - alert: HighLatency
        expr: histogram_quantile(0.95, resolve_latency_seconds_bucket) > 1.0
        for: 5m
        annotations:
          summary: "High request latency"
          description: "P95 latency is {{ $value }}s"

      # Connection pool exhausted
      - alert: ConnectionPoolExhausted
        expr: db_pool_available == 0
        for: 2m
        annotations:
          summary: "Database connection pool exhausted"
          description: "No available connections in pool"

      # Cache down
      - alert: CacheDown
        expr: cache_connected == 0
        for: 1m
        annotations:
          summary: "Redis cache is down"
          description: "Cache connectivity lost"

      # Kafka down
      - alert: KafkaDown
        expr: kafka_producer_ready == 0
        for: 2m
        annotations:
          summary: "Kafka producer is down"
          description: "Kafka producer is not ready"
          
      # High request latency
      - alert: HighRequestLatency
        expr: histogram_quantile(0.95, rate(resolve_latency_seconds_bucket[5m])) > 0.5
        for: 5m
        annotations:
          summary: "High request latency"
          description: "P95 latency is {{ $value }}s (threshold: 0.5s)"
          
      # High error rate
      - alert: HighErrorRate
        expr: rate(write_failure_total[5m]) / rate(write_requests_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 5%)"
```

### AlertManager Configuration

```yaml
# alertmanager.yml
route:
  receiver: 'default'
  group_by: ['alertname', 'cluster']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  
receivers:
  - name: 'default'
    email_configs:
      - to: 'oncall@example.com'
        from: 'alerts@example.com'
        smarthost: 'smtp.example.com:587'
        
  - name: 'critical'
    pagerduty_configs:
      - service_key: 'your-pagerduty-key'
```

---

## SLO/SLI Definitions

### Service Level Indicators (SLIs)

**Availability SLI**:
```promql
# Uptime percentage (requests that succeed)
(sum(rate(api_requests_total{status_code!~"5.."}[5m])) / 
 sum(rate(api_requests_total[5m]))) * 100
```

**Latency SLI**:
```promql
# Percentage of requests under 200ms
(sum(rate(resolve_latency_seconds_bucket{le="0.2"}[5m])) / 
 sum(rate(resolve_latency_seconds_count[5m]))) * 100
```

### Service Level Objectives (SLOs)

Example SLOs for Traffic Manager:
- **Availability**: 99.9% (3 nines) - 8.76 hours downtime/year
- **Latency**: 95% of requests < 200ms
- **Error Rate**: < 0.1% of requests

### Error Budget

```promql
# Error budget remaining (for 99.9% SLO)
(1 - (sum(rate(api_requests_total{status_code=~"5.."}[5m])) / 
      sum(rate(api_requests_total[5m])))) - 0.999
```

---

## Performance Considerations

### Metric Cardinality

**High Cardinality Problem**:
- Too many unique label combinations
- Example: `requests_total{user_id="123"}` for every user = millions of time series
- Solution: Don't use high-cardinality labels (user_id, request_id)

**Best Practices**:
- Use low-cardinality labels: `service`, `env`, `status_code`
- Aggregate high-cardinality data separately
- Use recording rules to pre-aggregate

### Scraping Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'traffic-manager'
    scrape_interval: 15s      # How often to scrape
    scrape_timeout: 10s       # Timeout per scrape
    metrics_path: '/metrics'
    static_configs:
      - targets: ['api-1:8000', 'api-2:8000', 'api-3:8000']
```

### Storage Considerations

- Prometheus stores ~1-2 bytes per sample
- 1 million samples ≈ 1-2 MB
- Retention: Typically 15-30 days
- Long-term storage: Use Thanos or Cortex

---

## Grafana Dashboard Best Practices

### Dashboard Structure

1. **Top Row**: Key metrics (request rate, error rate, latency)
2. **Second Row**: Infrastructure (connection pool, cache, kafka)
3. **Third Row**: Business metrics (cache hit rate, write success rate)
4. **Bottom Row**: Detailed breakdowns

### Panel Types

- **Graph**: Time series data (request rate, latency over time)
- **Gauge**: Current value with thresholds (cache hit rate, pool usage)
- **Stat**: Single number (total requests, current connections)
- **Table**: Detailed breakdown (requests by endpoint, errors by type)

### Example Dashboard JSON

```json
{
  "dashboard": {
    "title": "Traffic Manager",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [{
          "expr": "rate(resolve_requests_total[5m])"
        }],
        "type": "graph"
      },
      {
        "title": "P95 Latency",
        "targets": [{
          "expr": "histogram_quantile(0.95, rate(resolve_latency_seconds_bucket[5m]))"
        }],
        "type": "graph"
      }
    ]
  }
}
```

---

## Troubleshooting

### Common Issues

**Metrics not appearing**:
- Check `/metrics` endpoint is accessible
- Verify Prometheus is scraping (check targets in Prometheus UI)
- Check scrape interval (default 15s)

**High cardinality warnings**:
- Review labels on metrics
- Remove high-cardinality labels
- Use recording rules to aggregate

**Missing metrics**:
- Verify metrics are being incremented in code
- Check metric names match (case-sensitive)
- Verify Prometheus client library is working

---

## Integration with Other Tools

### Datadog
- Use Datadog agent to scrape Prometheus metrics
- Or use Prometheus remote write to Datadog

### New Relic
- Use Prometheus remote write endpoint
- Or use New Relic's Prometheus integration

### CloudWatch
- Use CloudWatch Container Insights
- Or export metrics via CloudWatch agent

---

## Next Steps

1. **Set up Prometheus** in your environment
2. **Create Grafana dashboards** for key metrics
3. **Configure alerting** based on SLOs
4. **Monitor metric cardinality** to avoid performance issues
5. **Review and tune** alert thresholds based on actual behavior
      - alert: KafkaDown
        expr: kafka_producer_ready == 0
        for: 2m
        annotations:
          summary: "Kafka producer is down"
          description: "Kafka connectivity lost"
```

### Alert Severity Levels

- **Critical**: Service unavailable, data loss risk
- **Warning**: Degraded performance, non-critical issues
- **Info**: Informational alerts

---

## Key Metrics to Monitor

### Performance Metrics
- **Request rate**: `rate(resolve_requests_total[5m])`
- **Latency**: `histogram_quantile(0.95, resolve_latency_seconds_bucket)`
- **Cache hit rate**: `rate(resolve_cache_hit_total[5m]) / rate(resolve_requests_total[5m])`

### Reliability Metrics
- **Error rate**: `rate(write_failure_total[5m])`
- **Success rate**: `rate(write_success_total[5m]) / rate(write_requests_total[5m])`
- **Uptime**: `application_uptime_seconds`

### Infrastructure Metrics
- **Connection pool usage**: `db_pool_in_use / db_pool_size`
- **Cache connectivity**: `cache_connected`
- **Kafka connectivity**: `kafka_producer_ready`

### Business Metrics
- **Total requests**: `resolve_requests_total`
- **Total writes**: `write_requests_total`
- **Event publishing**: `kafka_events_published_total`

---

## Monitoring Best Practices

1. **Set up dashboards** for key metrics
2. **Configure alerts** for critical issues
3. **Monitor trends** (not just current values)
4. **Track SLAs** (latency, availability)
5. **Review regularly** (weekly/monthly)

---

## Troubleshooting

### Metrics not appearing
- Check `/metrics` endpoint is accessible
- Verify Prometheus is scraping correctly
- Check application logs for errors

### High latency
- Check cache hit rate (low = more DB queries)
- Check database connection pool usage
- Review slow query logs

### High error rate
- Check database connectivity
- Check Kafka connectivity
- Review application logs

---

This monitoring setup provides comprehensive visibility into the Traffic Manager system's health, performance, and reliability.
