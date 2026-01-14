#!/usr/bin/env python3
"""
Script to populate the database with sample route data.

This script creates sample tenants, services, environments, and routes
for testing and demonstration purposes.

Generates 1000+ random route records for load testing and demonstration.

Usage:
    python scripts/populate_db.py
"""

import sys
import os
import random

# Add src directory to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from db.pool import initialize_pool, get_connection, close_pool
from service.write_path import create_route
from logger import get_logger
from config import settings

logger = get_logger(__name__)


def generate_random_routes(count: int = 1000):
    """
    Generate random route data for database population.
    
    Args:
        count: Number of random routes to generate (default: 1000)
    
    Returns:
        List of route dictionaries with random data
    """
    # Random data pools
    tenant_prefixes = ["team", "org", "company", "corp", "group", "squad"]
    tenant_suffixes = [chr(i) for i in range(ord('a'), ord('z')+1)] + [str(i) for i in range(1, 100)]
    
    services = [
        "payments", "orders", "users", "analytics", "notifications", "auth",
        "billing", "inventory", "shipping", "catalog", "search", "recommendations",
        "reviews", "ratings", "messaging", "chat", "email", "sms", "push",
        "reports", "dashboard", "admin", "api", "gateway", "proxy", "cdn",
        "storage", "compute", "monitoring", "logging", "metrics", "tracing"
    ]
    
    environments = ["prod", "staging", "dev", "test", "qa", "preprod", "canary"]
    
    # Generate random routes
    routes = []
    seen_combinations = set()  # Avoid duplicates
    
    logger.info(f"Generating {count} random routes...")
    
    while len(routes) < count:
        # Generate random tenant name
        tenant_prefix = random.choice(tenant_prefixes)
        tenant_suffix = random.choice(tenant_suffixes)
        tenant = f"{tenant_prefix}-{tenant_suffix}"
        
        # Generate random service
        service = random.choice(services)
        
        # Generate random environment
        env = random.choice(environments)
        
        # Generate random version (v1 to v20)
        version = f"v{random.randint(1, 20)}"
        
        # Create unique key to avoid duplicates
        route_key = (tenant, service, env, version)
        if route_key in seen_combinations:
            continue  # Skip duplicates
        seen_combinations.add(route_key)
        
        # Generate random URL
        # Different URL patterns for variety
        url_patterns = [
            f"https://{service}.{tenant}.example.com/{version}",
            f"https://{service}-{env}.{tenant}.example.com/{version}",
            f"https://{tenant}-{service}.example.com/{version}",
            f"https://api.{tenant}.example.com/{service}/{version}",
            f"https://{service}.api.{tenant}.example.com/{version}",
            f"https://{env}.{service}.{tenant}.example.com/{version}",
        ]
        url = random.choice(url_patterns)
        
        routes.append({
            "tenant": tenant,
            "service": service,
            "env": env,
            "version": version,
            "url": url
        })
    
    logger.info(f"Generated {len(routes)} unique random routes")
    return routes


def populate_sample_data():
    """
    Populate database with random route data.
    
    Generates 1000+ random routes with:
    - Random tenant names (team-a, org-b, company-1, etc.)
    - Random services (payments, orders, users, analytics, etc.)
    - Random environments (prod, staging, dev, test, etc.)
    - Random versions (v1 to v20)
    - Random URL patterns
    """
    logger.info("Starting database population...")
    
    # Initialize connection pool
    initialize_pool()
    logger.info("Database connection pool initialized")
    
    # Generate 1000+ random routes
    target_count = 1000
    sample_routes = generate_random_routes(count=target_count)
    
    created_count = 0
    error_count = 0
    
    try:
        # Create each route with progress logging
        total_routes = len(sample_routes)
        logger.info(f"Creating {total_routes} routes...")
        
        for idx, route in enumerate(sample_routes, 1):
            try:
                with get_connection() as conn:
                    create_route(
                        conn=conn,
                        tenant=route["tenant"],
                        service=route["service"],
                        env=route["env"],
                        version=route["version"],
                        url=route["url"]
                    )
                    created_count += 1
                    
                    # Log progress every 100 routes
                    if idx % 100 == 0 or idx == total_routes:
                        logger.info(
                            f"Progress: {idx}/{total_routes} routes created "
                            f"({created_count} successful, {error_count} errors)"
                        )
            except Exception as e:
                error_count += 1
                # Only log errors for first few and last few to avoid spam
                if error_count <= 5 or idx > total_routes - 5:
                    logger.error(
                        f"✗ Failed to create route {route['tenant']}/{route['service']}/"
                        f"{route['env']}/{route['version']}: {e}"
                    )
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Database population complete!")
        logger.info(f"  Total routes: {total_routes}")
        logger.info(f"  Created: {created_count} routes")
        logger.info(f"  Errors: {error_count} routes")
        logger.info(f"{'='*60}")
        
    finally:
        # Close connection pool
        close_pool()
        logger.info("Database connection pool closed")


if __name__ == "__main__":
    try:
        populate_sample_data()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
