# src/service/routing.py
from psycopg2.extras import RealDictCursor
from cache.redis_client import get_redis_client

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
CACHE_TTL_SECONDS = 60

def _cache_key(tenant, service, env, version):
    return f"route:{tenant}:{service}:{env}:{version}"

def resolve_endpoint(conn, tenant, service, env, version):
    cache_key = _cache_key(tenant, service, env, version)

    # 1️⃣ Try Redis first
    try:
        redis_client = get_redis_client()
        cached_url = redis_client.get(cache_key)

        if cached_url:
            return cached_url

    except Exception:
        # Redis failure must NOT break DB path
        pass

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
            raise RouteNotFoundError(
                f"No active route found for "
                f"{tenant}/{service}/{env}/{version}"
            )
        url = row["url"]
    
    try:
        redis_client.setex(cache_key, CACHE_TTL_SECONDS, url)
    except Exception:
        pass

    return url
