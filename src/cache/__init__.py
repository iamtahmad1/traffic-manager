# src/cache/__init__.py
# This file makes the cache folder a Python package

from .redis_client import get_redis_client, close_redis_client

__all__ = [
    "get_redis_client",
    "close_redis_client",
]
