#!/usr/bin/env python3
"""
Load testing script for the read path (route resolution).

This script generates load by making concurrent HTTP requests to the
route resolution endpoint to test performance, throughput, and caching.

Usage:
    python scripts/load_test_read.py
    
    # Custom options:
    python scripts/load_test_read.py --requests 5000 --threads 10 --api-url http://localhost:5000
"""

import sys
import os
import time
import random
import argparse
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional
import requests

# Add src directory to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from db.pool import initialize_pool, get_connection, close_pool
from logger import get_logger
from config import settings

logger = get_logger(__name__)


def get_routes_from_db(limit: Optional[int] = None) -> List[Dict[str, str]]:
    """
    Fetch existing routes from the database to use for load testing.
    
    Args:
        limit: Maximum number of routes to fetch (None = all)
    
    Returns:
        List of route dictionaries with tenant, service, env, version
    """
    routes = []
    
    try:
        initialize_pool()
        with get_connection() as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT 
                        t.name as tenant,
                        s.name as service,
                        env.name as env,
                        e.version
                    FROM tenants t
                    JOIN services s ON s.tenant_id = t.id
                    JOIN environments env ON env.service_id = s.id
                    JOIN endpoints e ON e.environment_id = env.id
                    WHERE e.is_active = true
                """
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                for row in cursor.fetchall():
                    routes.append({
                        "tenant": row[0],
                        "service": row[1],
                        "env": row[2],
                        "version": row[3]
                    })
        
        close_pool()
        logger.info(f"Fetched {len(routes)} routes from database")
        return routes
    
    except Exception as e:
        logger.warning(f"Failed to fetch routes from DB: {e}")
        close_pool()
        return []


def generate_random_routes(count: int) -> List[Dict[str, str]]:
    """
    Generate random route combinations for load testing.
    
    Args:
        count: Number of random routes to generate
    
    Returns:
        List of route dictionaries
    """
    tenant_prefixes = ["team", "org", "company", "corp", "group", "squad"]
    tenant_suffixes = [chr(i) for i in range(ord('a'), ord('z')+1)] + [str(i) for i in range(1, 100)]
    
    services = [
        "payments", "orders", "users", "analytics", "notifications", "auth",
        "billing", "inventory", "shipping", "catalog", "search", "recommendations"
    ]
    
    environments = ["prod", "staging", "dev", "test", "qa"]
    
    routes = []
    for _ in range(count):
        tenant_prefix = random.choice(tenant_prefixes)
        tenant_suffix = random.choice(tenant_suffixes)
        tenant = f"{tenant_prefix}-{tenant_suffix}"
        
        routes.append({
            "tenant": tenant,
            "service": random.choice(services),
            "env": random.choice(environments),
            "version": f"v{random.randint(1, 20)}"
        })
    
    return routes


def make_request(api_url: str, route: Dict[str, str], request_id: int) -> Tuple[int, float, int, Optional[str]]:
    """
    Make a single HTTP request to the resolve endpoint.
    
    Args:
        api_url: Base URL of the API (e.g., http://localhost:5000)
        route: Route dictionary with tenant, service, env, version
        request_id: Unique identifier for this request (for logging)
    
    Returns:
        Tuple of (request_id, response_time_ms, status_code, error_message)
    """
    url = f"{api_url}/api/v1/routes/resolve"
    params = {
        "tenant": route["tenant"],
        "service": route["service"],
        "env": route["env"],
        "version": route["version"]
    }
    
    start_time = time.time()
    try:
        response = requests.get(url, params=params, timeout=10)
        elapsed_ms = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        return (request_id, elapsed_ms, response.status_code, None)
    
    except requests.exceptions.RequestException as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return (request_id, elapsed_ms, 0, str(e))


def run_load_test(
    api_url: str,
    routes: List[Dict[str, str]],
    total_requests: int,
    num_threads: int
) -> Dict:
    """
    Run the load test with concurrent requests.
    
    Args:
        api_url: Base URL of the API
        routes: List of routes to test
        total_requests: Total number of requests to make
        num_threads: Number of concurrent threads
    
    Returns:
        Dictionary with test results and statistics
    """
    logger.info(f"Starting load test:")
    logger.info(f"  API URL: {api_url}")
    logger.info(f"  Total requests: {total_requests}")
    logger.info(f"  Concurrent threads: {num_threads}")
    logger.info(f"  Routes pool: {len(routes)}")
    
    # Results tracking
    results = {
        "total_requests": total_requests,
        "completed": 0,
        "successful": 0,
        "failed": 0,
        "not_found": 0,
        "errors": 0,
        "response_times": [],
        "status_codes": {},
        "errors_list": []
    }
    
    start_time = time.time()
    
    # Use ThreadPoolExecutor for concurrent requests
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit all requests
        futures = []
        for i in range(total_requests):
            # Pick a random route from the pool
            route = random.choice(routes)
            future = executor.submit(make_request, api_url, route, i)
            futures.append(future)
        
        # Process completed requests
        completed = 0
        for future in as_completed(futures):
            request_id, response_time_ms, status_code, error = future.result()
            
            results["completed"] += 1
            results["response_times"].append(response_time_ms)
            
            if error:
                results["errors"] += 1
                results["failed"] += 1
                results["errors_list"].append(f"Request {request_id}: {error}")
            elif status_code == 200:
                results["successful"] += 1
            elif status_code == 404:
                results["not_found"] += 1
            else:
                results["failed"] += 1
            
            # Track status codes
            if status_code not in results["status_codes"]:
                results["status_codes"][status_code] = 0
            results["status_codes"][status_code] += 1
            
            completed += 1
            # Log progress every 100 requests
            if completed % 100 == 0 or completed == total_requests:
                logger.info(f"Progress: {completed}/{total_requests} requests completed")
    
    elapsed_time = time.time() - start_time
    
    # Calculate statistics
    if results["response_times"]:
        results["stats"] = {
            "total_time_seconds": elapsed_time,
            "requests_per_second": total_requests / elapsed_time if elapsed_time > 0 else 0,
            "avg_response_time_ms": statistics.mean(results["response_times"]),
            "median_response_time_ms": statistics.median(results["response_times"]),
            "min_response_time_ms": min(results["response_times"]),
            "max_response_time_ms": max(results["response_times"]),
            "p95_response_time_ms": statistics.quantiles(results["response_times"], n=20)[18] if len(results["response_times"]) > 20 else max(results["response_times"]),
            "p99_response_time_ms": statistics.quantiles(results["response_times"], n=100)[98] if len(results["response_times"]) > 100 else max(results["response_times"]),
        }
    else:
        results["stats"] = {}
    
    return results


def print_results(results: Dict):
    """
    Print load test results in a formatted way.
    
    Args:
        results: Dictionary with test results
    """
    print("\n" + "="*70)
    print("LOAD TEST RESULTS")
    print("="*70)
    
    print(f"\n📊 Request Summary:")
    print(f"  Total requests:     {results['total_requests']}")
    print(f"  Completed:          {results['completed']}")
    print(f"  Successful (200):   {results['successful']}")
    print(f"  Not Found (404):   {results['not_found']}")
    print(f"  Failed:             {results['failed']}")
    print(f"  Errors:             {results['errors']}")
    
    if results.get("status_codes"):
        print(f"\n📈 Status Code Distribution:")
        for status_code, count in sorted(results["status_codes"].items()):
            percentage = (count / results["completed"]) * 100 if results["completed"] > 0 else 0
            print(f"  {status_code}: {count:6d} ({percentage:5.2f}%)")
    
    if results.get("stats"):
        stats = results["stats"]
        print(f"\n⏱️  Performance Metrics:")
        print(f"  Total time:              {stats['total_time_seconds']:.2f} seconds")
        print(f"  Requests per second:     {stats['requests_per_second']:.2f} req/s")
        print(f"  Average response time:   {stats['avg_response_time_ms']:.2f} ms")
        print(f"  Median response time:    {stats['median_response_time_ms']:.2f} ms")
        print(f"  Min response time:       {stats['min_response_time_ms']:.2f} ms")
        print(f"  Max response time:       {stats['max_response_time_ms']:.2f} ms")
        print(f"  P95 response time:       {stats['p95_response_time_ms']:.2f} ms")
        print(f"  P99 response time:       {stats['p99_response_time_ms']:.2f} ms")
    
    if results.get("errors_list") and len(results["errors_list"]) > 0:
        print(f"\n❌ Errors (showing first 10):")
        for error in results["errors_list"][:10]:
            print(f"  {error}")
        if len(results["errors_list"]) > 10:
            print(f"  ... and {len(results['errors_list']) - 10} more errors")
    
    print("\n" + "="*70 + "\n")


def main():
    """Main function to run the load test."""
    parser = argparse.ArgumentParser(
        description="Load test the read path (route resolution endpoint)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic load test with defaults (1000 requests, 10 threads)
  python scripts/load_test_read.py
  
  # High load test (10000 requests, 50 threads)
  python scripts/load_test_read.py --requests 10000 --threads 50
  
  # Test against different API URL
  python scripts/load_test_read.py --api-url http://localhost:8080
  
  # Use random routes instead of DB routes
  python scripts/load_test_read.py --use-random --requests 5000
        """
    )
    
    parser.add_argument(
        "--requests",
        type=int,
        default=1000,
        help="Total number of requests to make (default: 1000)"
    )
    
    parser.add_argument(
        "--threads",
        type=int,
        default=10,
        help="Number of concurrent threads (default: 10)"
    )
    
    parser.add_argument(
        "--api-url",
        type=str,
        default=f"http://{settings.app.api_host}:{settings.app.api_port}",
        help=f"Base URL of the API (default: http://{settings.app.api_host}:{settings.app.api_port})"
    )
    
    parser.add_argument(
        "--use-random",
        action="store_true",
        help="Use randomly generated routes instead of fetching from database"
    )
    
    parser.add_argument(
        "--route-pool-size",
        type=int,
        default=1000,
        help="Number of routes to use in the pool (default: 1000)"
    )
    
    args = parser.parse_args()
    
    # Get routes for testing
    if args.use_random:
        logger.info(f"Generating {args.route_pool_size} random routes...")
        routes = generate_random_routes(args.route_pool_size)
    else:
        logger.info(f"Fetching routes from database (limit: {args.route_pool_size})...")
        routes = get_routes_from_db(limit=args.route_pool_size)
        
        if not routes:
            logger.warning("No routes found in database. Falling back to random routes.")
            routes = generate_random_routes(args.route_pool_size)
    
    if not routes:
        logger.error("No routes available for load testing. Exiting.")
        sys.exit(1)
    
    # Run the load test
    try:
        results = run_load_test(
            api_url=args.api_url,
            routes=routes,
            total_requests=args.requests,
            num_threads=args.threads
        )
        
        # Print results
        print_results(results)
        
        # Exit with error code if too many failures
        failure_rate = (results["failed"] / results["completed"]) * 100 if results["completed"] > 0 else 100
        if failure_rate > 10:  # More than 10% failures
            logger.warning(f"High failure rate: {failure_rate:.2f}%")
            sys.exit(1)
        
    except KeyboardInterrupt:
        logger.info("\nLoad test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
