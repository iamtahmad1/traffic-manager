# src/kafka_client/__init__.py
# This file makes the kafka_client folder a Python package

from .producer import (
    get_kafka_producer,
    close_kafka_producer,
    publish_route_event,
    ROUTE_EVENTS_TOPIC,
)
from .consumer import run_consumer

__all__ = [
    "get_kafka_producer",
    "close_kafka_producer",
    "publish_route_event",
    "ROUTE_EVENTS_TOPIC",
    "run_consumer",
]
