# src/tracking/__init__.py
# This module provides end-to-end request tracking using correlation IDs
# Correlation IDs allow us to trace a request through all components:
# - API layer
# - Service layer
# - Database queries
# - Cache operations
# - Kafka events
# - Consumer processing

from tracking.correlation import (
    get_correlation_id,
    set_correlation_id,
    clear_correlation_id,
    correlation_context,
    generate_correlation_id,
)

__all__ = [
    "get_correlation_id",
    "set_correlation_id",
    "clear_correlation_id",
    "correlation_context",
    "generate_correlation_id",
]
