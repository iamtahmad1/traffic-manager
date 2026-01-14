# src/metrics/__init__.py
# This file makes the metrics folder a Python package
# It also controls what gets imported when someone does "from metrics import ..."

# Import all our metrics from the metrics.py file
# The dot (.) means "from the current package"
# So .metrics means "from the metrics.py file in this same folder"
from .metrics import (
    RESOLVE_REQUESTS_TOTAL,
    CACHE_HIT_TOTAL,
    CACHE_MISS_TOTAL,
    NEGATIVE_CACHE_HIT_TOTAL,
    RESOLVE_LATENCY_SECONDS,
    WRITE_REQUESTS_TOTAL,
    WRITE_SUCCESS_TOTAL,
    WRITE_FAILURE_TOTAL,
    WRITE_LATENCY_SECONDS,
    KAFKA_EVENTS_PUBLISHED_TOTAL,
    KAFKA_EVENTS_FAILED_TOTAL,
    DB_CONNECTION_ERRORS_TOTAL,
    DB_QUERIES_TOTAL,
)

# __all__ is a special list that defines what gets exported
# When someone does "from metrics import *", only things in __all__ are imported
# This is a best practice - it makes it clear what the package provides
__all__ = [
    "RESOLVE_REQUESTS_TOTAL",
    "CACHE_HIT_TOTAL",
    "CACHE_MISS_TOTAL",
    "NEGATIVE_CACHE_HIT_TOTAL",
    "RESOLVE_LATENCY_SECONDS",
    "WRITE_REQUESTS_TOTAL",
    "WRITE_SUCCESS_TOTAL",
    "WRITE_FAILURE_TOTAL",
    "WRITE_LATENCY_SECONDS",
    "KAFKA_EVENTS_PUBLISHED_TOTAL",
    "KAFKA_EVENTS_FAILED_TOTAL",
    "DB_CONNECTION_ERRORS_TOTAL",
    "DB_QUERIES_TOTAL",
]
