# src/service/write_path.py
# This file implements the write path for managing routes
# Write path = operations that change/create/update routes
# This follows the design in write_path.md

import time
from psycopg2.extras import RealDictCursor
from psycopg2 import IntegrityError
from logger import get_logger
from kafka_client import get_kafka_producer, publish_route_event
from metrics import (
    WRITE_REQUESTS_TOTAL,
    WRITE_SUCCESS_TOTAL,
    WRITE_FAILURE_TOTAL,
    WRITE_LATENCY_SECONDS,
)

logger = get_logger(__name__)

# SQL queries for write operations
# These queries insert or update data in the database

# Get or create tenant (idempotent - safe to run multiple times)
SQL_GET_OR_CREATE_TENANT = """
INSERT INTO tenants (name)
VALUES (%(name)s)
ON CONFLICT (name) DO NOTHING
RETURNING id;
"""

SQL_GET_TENANT = """
SELECT id FROM tenants WHERE name = %(name)s;
"""

# Get or create service (idempotent)
SQL_GET_OR_CREATE_SERVICE = """
INSERT INTO services (tenant_id, name)
VALUES (%(tenant_id)s, %(name)s)
ON CONFLICT (tenant_id, name) DO NOTHING
RETURNING id;
"""

SQL_GET_SERVICE = """
SELECT id FROM services WHERE tenant_id = %(tenant_id)s AND name = %(name)s;
"""

# Get or create environment (idempotent)
SQL_GET_OR_CREATE_ENVIRONMENT = """
INSERT INTO environments (service_id, name)
VALUES (%(service_id)s, %(name)s)
ON CONFLICT (service_id, name) DO NOTHING
RETURNING id;
"""

SQL_GET_ENVIRONMENT = """
SELECT id FROM environments WHERE service_id = %(service_id)s AND name = %(name)s;
"""

# Create or update endpoint
SQL_CREATE_OR_UPDATE_ENDPOINT = """
INSERT INTO endpoints (environment_id, version, url, is_active)
VALUES (%(environment_id)s, %(version)s, %(url)s, %(is_active)s)
ON CONFLICT (environment_id, version) 
DO UPDATE SET 
    url = EXCLUDED.url,
    is_active = EXCLUDED.is_active,
    updated_at = now()
RETURNING id, url, is_active;
"""

# Activate endpoint
SQL_ACTIVATE_ENDPOINT = """
UPDATE endpoints
SET is_active = true, updated_at = now()
WHERE environment_id = %(environment_id)s AND version = %(version)s
RETURNING id, url;
"""

# Deactivate endpoint
SQL_DEACTIVATE_ENDPOINT = """
UPDATE endpoints
SET is_active = false, updated_at = now()
WHERE environment_id = %(environment_id)s AND version = %(version)s
RETURNING id, url;
"""

# Get endpoint URL for Kafka event
SQL_GET_ENDPOINT_URL = """
SELECT e.url
FROM tenants t
JOIN services s ON s.tenant_id = t.id
JOIN environments env ON env.service_id = s.id
JOIN endpoints e ON e.environment_id = env.id
WHERE t.name = %(tenant)s
  AND s.name = %(service)s
  AND env.name = %(env)s
  AND e.version = %(version)s
LIMIT 1;
"""

def _get_or_create_tenant(cursor, tenant_name):
    """
    Helper function to get or create a tenant.
    
    This is idempotent - if tenant exists, we get it; if not, we create it.
    
    Returns:
        Tenant ID
    """
    # Try to insert (will fail silently if exists due to ON CONFLICT)
    cursor.execute(SQL_GET_OR_CREATE_TENANT, {"name": tenant_name})
    row = cursor.fetchone()
    
    if row:
        return row["id"]
    
    # If insert didn't return anything, tenant already exists - fetch it
    cursor.execute(SQL_GET_TENANT, {"name": tenant_name})
    row = cursor.fetchone()
    return row["id"]

def _get_or_create_service(cursor, tenant_id, service_name):
    """Helper to get or create a service. Returns service ID."""
    cursor.execute(SQL_GET_OR_CREATE_SERVICE, {
        "tenant_id": tenant_id,
        "name": service_name
    })
    row = cursor.fetchone()
    
    if row:
        return row["id"]
    
    cursor.execute(SQL_GET_SERVICE, {
        "tenant_id": tenant_id,
        "name": service_name
    })
    row = cursor.fetchone()
    return row["id"]

def _get_or_create_environment(cursor, service_id, env_name):
    """Helper to get or create an environment. Returns environment ID."""
    cursor.execute(SQL_GET_OR_CREATE_ENVIRONMENT, {
        "service_id": service_id,
        "name": env_name
    })
    row = cursor.fetchone()
    
    if row:
        return row["id"]
    
    cursor.execute(SQL_GET_ENVIRONMENT, {
        "service_id": service_id,
        "name": env_name
    })
    row = cursor.fetchone()
    return row["id"]

def create_route(conn, tenant, service, env, version, url):
    """
    Create a new route (or update if it exists).
    
    This function:
    1. Validates inputs
    2. Creates/gets tenant, service, environment (if needed)
    3. Creates/updates the endpoint
    4. Commits the transaction
    5. Publishes Kafka event (best effort - doesn't fail if Kafka is down)
    
    Args:
        conn: Database connection
        tenant: Tenant name
        service: Service name
        env: Environment name
        version: Version name
        url: Endpoint URL
    
    Returns:
        Dictionary with route information
    
    Raises:
        ValueError: If inputs are invalid
        Exception: If database operation fails
    """
    start_time = time.time()
    WRITE_REQUESTS_TOTAL.inc()
    
    logger.info(f"Creating route: {tenant}/{service}/{env}/{version} -> {url}")
    
    # Validate inputs
    if not all([tenant, service, env, version, url]):
        WRITE_FAILURE_TOTAL.inc()
        raise ValueError("All parameters (tenant, service, env, version, url) are required")
    
    if not url.strip():
        WRITE_FAILURE_TOTAL.inc()
        raise ValueError("URL cannot be empty")
    
    # Start database transaction
    # Everything inside this transaction will succeed or fail together
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        try:
            # Get or create tenant, service, environment
            # These are idempotent operations
            tenant_id = _get_or_create_tenant(cursor, tenant)
            service_id = _get_or_create_service(cursor, tenant_id, service)
            environment_id = _get_or_create_environment(cursor, service_id, env)
            
            # Create or update endpoint
            # is_active defaults to True for new routes
            cursor.execute(SQL_CREATE_OR_UPDATE_ENDPOINT, {
                "environment_id": environment_id,
                "version": version,
                "url": url,
                "is_active": True
            })
            
            result = cursor.fetchone()
            
            # Commit the transaction
            # This makes all changes permanent
            conn.commit()
            
            logger.info(f"Route created successfully: {tenant}/{service}/{env}/{version}")
            WRITE_SUCCESS_TOTAL.inc()
            
            # Record latency
            duration = time.time() - start_time
            WRITE_LATENCY_SECONDS.observe(duration)
            
            # Publish Kafka event (best effort - doesn't fail if this fails)
            # This happens AFTER the database commit, so DB is always correct
            try:
                producer = get_kafka_producer()
                publish_route_event(
                    producer,
                    action="created",
                    tenant=tenant,
                    service=service,
                    env=env,
                    version=version,
                    url=url
                )
                producer.flush()  # Make sure message is sent
            except Exception as e:
                # Kafka failure doesn't fail the write
                logger.warning(f"Failed to publish Kafka event (non-critical): {e}")
            
            return {
                "tenant": tenant,
                "service": service,
                "env": env,
                "version": version,
                "url": url,
                "is_active": result["is_active"]
            }
            
        except IntegrityError as e:
            # Database constraint violation (shouldn't happen with our queries)
            conn.rollback()  # Undo all changes
            WRITE_FAILURE_TOTAL.inc()
            logger.error(f"Database constraint violation: {e}")
            raise
        except Exception as e:
            # Any other error - rollback and re-raise
            conn.rollback()
            WRITE_FAILURE_TOTAL.inc()
            logger.error(f"Failed to create route: {e}")
            raise

def activate_route(conn, tenant, service, env, version):
    """
    Activate a route (set is_active = true).
    
    Args:
        conn: Database connection
        tenant: Tenant name
        service: Service name
        env: Environment name
        version: Version name
    
    Returns:
        Dictionary with route information
    
    Raises:
        ValueError: If route not found
    """
    start_time = time.time()
    WRITE_REQUESTS_TOTAL.inc()
    
    logger.info(f"Activating route: {tenant}/{service}/{env}/{version}")
    
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        try:
            # Get environment_id first
            cursor.execute("""
                SELECT env.id as environment_id
                FROM tenants t
                JOIN services s ON s.tenant_id = t.id
                JOIN environments env ON env.service_id = s.id
                WHERE t.name = %(tenant)s
                  AND s.name = %(service)s
                  AND env.name = %(env)s
                LIMIT 1;
            """, {"tenant": tenant, "service": service, "env": env})
            
            env_row = cursor.fetchone()
            if not env_row:
                WRITE_FAILURE_TOTAL.inc()
                raise ValueError(f"Environment not found: {tenant}/{service}/{env}")
            
            environment_id = env_row["environment_id"]
            
            # Activate the endpoint
            cursor.execute(SQL_ACTIVATE_ENDPOINT, {
                "environment_id": environment_id,
                "version": version
            })
            
            result = cursor.fetchone()
            if not result:
                WRITE_FAILURE_TOTAL.inc()
                raise ValueError(f"Route not found: {tenant}/{service}/{env}/{version}")
            
            conn.commit()
            
            logger.info(f"Route activated: {tenant}/{service}/{env}/{version}")
            WRITE_SUCCESS_TOTAL.inc()
            
            duration = time.time() - start_time
            WRITE_LATENCY_SECONDS.observe(duration)
            
            # Publish Kafka event
            try:
                producer = get_kafka_producer()
                publish_route_event(
                    producer,
                    action="activated",
                    tenant=tenant,
                    service=service,
                    env=env,
                    version=version,
                    url=result["url"]
                )
                producer.flush()
            except Exception as e:
                logger.warning(f"Failed to publish Kafka event (non-critical): {e}")
            
            return {
                "tenant": tenant,
                "service": service,
                "env": env,
                "version": version,
                "url": result["url"],
                "is_active": True
            }
            
        except Exception as e:
            conn.rollback()
            WRITE_FAILURE_TOTAL.inc()
            raise

def deactivate_route(conn, tenant, service, env, version):
    """
    Deactivate a route (set is_active = false).
    
    Args:
        conn: Database connection
        tenant: Tenant name
        service: Service name
        env: Environment name
        version: Version name
    
    Returns:
        Dictionary with route information
    """
    start_time = time.time()
    WRITE_REQUESTS_TOTAL.inc()
    
    logger.info(f"Deactivating route: {tenant}/{service}/{env}/{version}")
    
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        try:
            # Get environment_id first
            cursor.execute("""
                SELECT env.id as environment_id
                FROM tenants t
                JOIN services s ON s.tenant_id = t.id
                JOIN environments env ON env.service_id = s.id
                WHERE t.name = %(tenant)s
                  AND s.name = %(service)s
                  AND env.name = %(env)s
                LIMIT 1;
            """, {"tenant": tenant, "service": service, "env": env})
            
            env_row = cursor.fetchone()
            if not env_row:
                WRITE_FAILURE_TOTAL.inc()
                raise ValueError(f"Environment not found: {tenant}/{service}/{env}")
            
            environment_id = env_row["environment_id"]
            
            # Deactivate the endpoint
            cursor.execute(SQL_DEACTIVATE_ENDPOINT, {
                "environment_id": environment_id,
                "version": version
            })
            
            result = cursor.fetchone()
            if not result:
                WRITE_FAILURE_TOTAL.inc()
                raise ValueError(f"Route not found: {tenant}/{service}/{env}/{version}")
            
            conn.commit()
            
            logger.info(f"Route deactivated: {tenant}/{service}/{env}/{version}")
            WRITE_SUCCESS_TOTAL.inc()
            
            duration = time.time() - start_time
            WRITE_LATENCY_SECONDS.observe(duration)
            
            # Publish Kafka event
            try:
                producer = get_kafka_producer()
                publish_route_event(
                    producer,
                    action="deactivated",
                    tenant=tenant,
                    service=service,
                    env=env,
                    version=version,
                    url=result["url"]
                )
                producer.flush()
            except Exception as e:
                logger.warning(f"Failed to publish Kafka event (non-critical): {e}")
            
            return {
                "tenant": tenant,
                "service": service,
                "env": env,
                "version": version,
                "url": result["url"],
                "is_active": False
            }
            
        except Exception as e:
            conn.rollback()
            WRITE_FAILURE_TOTAL.inc()
            raise
