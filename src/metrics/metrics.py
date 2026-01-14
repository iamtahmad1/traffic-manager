# src/metrics/metrics.py
# This file defines metrics - numbers we track to understand how our application is performing
# Metrics are like a dashboard in a car - they show us speed, fuel, etc.
# Prometheus is a tool that collects and stores these metrics

# Import Counter and Histogram from prometheus_client
# Counter: counts things (like "how many requests did we get?")
# Histogram: measures things over time (like "how long did requests take?")
from prometheus_client import Counter, Histogram

# Total requests counter
# This counts every time someone asks us to resolve an endpoint
# Counter() creates a new counter with a name and description
RESOLVE_REQUESTS_TOTAL = Counter(
    "resolve_requests_total",  # The name of the metric (used in Prometheus)
    "Total number of resolve requests",  # Description of what this metric measures
)

# Cache behavior counters
# These help us understand how well our cache is working

# Cache hit: we found the data in cache (fast!)
CACHE_HIT_TOTAL = Counter(
    "resolve_cache_hit_total",
    "Total cache hits",
)

# Cache miss: we had to go to the database (slower)
CACHE_MISS_TOTAL = Counter(
    "resolve_cache_miss_total",
    "Total cache misses",
)

# Negative cache hit: we found a "not found" result in cache
# This means we remembered that a route doesn't exist
NEGATIVE_CACHE_HIT_TOTAL = Counter(
    "resolve_negative_cache_hit_total",
    "Total negative cache hits",
)

# Latency histogram
# This measures how long requests take to complete
# Histogram tracks the distribution of values (min, max, average, percentiles)
# This helps us see if requests are getting slower
RESOLVE_LATENCY_SECONDS = Histogram(
    "resolve_latency_seconds",  # Name of the metric
    "Latency of resolve requests",  # Description
)

# Write path metrics
# These track write operations (create, activate, deactivate routes)

# Total write requests
WRITE_REQUESTS_TOTAL = Counter(
    "write_requests_total",
    "Total number of write requests",
)

# Successful writes
WRITE_SUCCESS_TOTAL = Counter(
    "write_success_total",
    "Total successful write operations",
)

# Failed writes
WRITE_FAILURE_TOTAL = Counter(
    "write_failure_total",
    "Total failed write operations",
)

# Write latency
WRITE_LATENCY_SECONDS = Histogram(
    "write_latency_seconds",
    "Latency of write operations",
)

# Kafka event metrics
# These track event publishing to Kafka
KAFKA_EVENTS_PUBLISHED_TOTAL = Counter(
    "kafka_events_published_total",
    "Total number of events published to Kafka",
    ["action"]  # Label: created, activated, deactivated
)

KAFKA_EVENTS_FAILED_TOTAL = Counter(
    "kafka_events_failed_total",
    "Total number of failed Kafka event publications",
    ["action"]  # Label: created, activated, deactivated
)

# Database connection metrics
# These track database connection pool usage
DB_CONNECTION_ERRORS_TOTAL = Counter(
    "db_connection_errors_total",
    "Total number of database connection errors",
)

DB_QUERIES_TOTAL = Counter(
    "db_queries_total",
    "Total number of database queries executed",
)
