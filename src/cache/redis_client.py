import os
import logging
import redis

logger = logging.getLogger(__name__)

def get_redis_client():
    logger.debug("Creating Redis client")
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=int(os.getenv("REDIS_DB", 0)),
        decode_responses=True
    )