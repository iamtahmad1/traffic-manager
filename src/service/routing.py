# src/service/routing.py
import logging
import time
from psycopg2.extras import RealDictCursor
from cache.redis_client import get_redis_client
from metrics import (
    RESOLVE_REQUESTS_TOTAL,
    CACHE_HIT_TOTAL,
    CACHE_MISS_TOTAL,
    NEGATIVE_CACHE_HIT_TOTAL,
    RESOLVE_LATENCY_SECONDS,
)

logger = logging.getLogger(__name__)

class RouteNotFoundError(Exception):
    pass


SQL_RESOLVE_ENDPOINT = """
SELECT e.url
FROM tenants t
JOIN services s ON s.tenant_id = t.id
JOIN environments env ON env.service_id = s.id
JOIN endpoints e ON e.environment_id = env.id
WHERE t.name = %(tenant)s
  AND s.name = %(service)s
  AND env.name = %(env)s
  AND e.version = %(version)s
  AND e.is_active = true
LIMIT 1;
"""

NEGATIVE_CACHE_VALUE = "__NOT_FOUND__"
POSITIVE_CACHE_TTL = 60
NEGATIVE_CACHE_TTL = 10

def _cache_key(tenant, service, env, version):
    return f"route:{tenant}:{service}:{env}:{version}"

def resolve_endpoint(conn, tenant, service, env, version):
    start_time = time.time()
    cache_key = _cache_key(tenant, service, env, version)
    logger.info(f"Resolving endpoint: {tenant}/{service}/{env}/{version}")
    RESOLVE_REQUESTS_TOTAL.inc()

    # 1️⃣ Try Redis first
    try:
        redis_client = get_redis_client()
        cached_url = redis_client.get(cache_key)

        if cached_url:
            if cached_url == NEGATIVE_CACHE_VALUE:
                logger.info("Negative cache hit")
                NEGATIVE_CACHE_HIT_TOTAL.inc()
                duration = time.time() - start_time
                RESOLVE_LATENCY_SECONDS.observe(duration)
                raise RouteNotFoundError(
                    f"No active route found for "
                    f"{tenant}/{service}/{env}/{version}"
                )
            logger.info("Cache hit")
            CACHE_HIT_TOTAL.inc()
            duration = time.time() - start_time
            RESOLVE_LATENCY_SECONDS.observe(duration)
            return cached_url
        logger.debug("Cache miss")
        CACHE_MISS_TOTAL.inc()

    except RouteNotFoundError:
        raise
    except Exception as e:
        logger.warning(f"Redis error: {e}")
        # Redis failure must NOT break DB path
        pass

    logger.info("Querying database")
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            SQL_RESOLVE_ENDPOINT,
            {
                "tenant": tenant,
                "service": service,
                "env": env,
                "version": version,
            },
        )
        row = cursor.fetchone()

        if row is None:
            logger.warning("Route not found in database")
            # Cache negative result
            try:
                redis_client.setex(cache_key, NEGATIVE_CACHE_TTL, NEGATIVE_CACHE_VALUE)
                logger.debug("Cached negative result")
            except Exception as e:
                logger.warning(f"Failed to cache negative result: {e}")
            duration = time.time() - start_time
            RESOLVE_LATENCY_SECONDS.observe(duration)
            raise RouteNotFoundError(
                f"No active route found for "
                f"{tenant}/{service}/{env}/{version}"
            )
        url = row["url"]
    
    try:
        redis_client.setex(cache_key, POSITIVE_CACHE_TTL, url)
        logger.debug("Cached endpoint")
    except Exception as e:
        logger.warning(f"Failed to cache: {e}")

    duration = time.time() - start_time
    RESOLVE_LATENCY_SECONDS.observe(duration)
    return url
