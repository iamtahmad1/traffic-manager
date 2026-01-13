from prometheus_client import Counter, Histogram

# Total requests
RESOLVE_REQUESTS_TOTAL = Counter(
    "resolve_requests_total",
    "Total number of resolve requests",
)

# Cache behavior
CACHE_HIT_TOTAL = Counter(
    "resolve_cache_hit_total",
    "Total cache hits",
)

CACHE_MISS_TOTAL = Counter(
    "resolve_cache_miss_total",
    "Total cache misses",
)

NEGATIVE_CACHE_HIT_TOTAL = Counter(
    "resolve_negative_cache_hit_total",
    "Total negative cache hits",
)

# Latency
RESOLVE_LATENCY_SECONDS = Histogram(
    "resolve_latency_seconds",
    "Latency of resolve requests",
)
