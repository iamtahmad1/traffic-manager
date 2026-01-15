#!/usr/bin/env python3
"""
Load testing script for the write path (route creation, activation, deactivation).

This script generates load by making concurrent HTTP requests to the
write path endpoints to test performance, throughput, and database handling.

Usage:
    python scripts/load_test_write.py
    
    # Custom options:
    python scripts/load_test_write.py --requests 500 --threads 5 --api-url http://localhost:5000
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

from logger import get_logger
from config import settings

logger = get_logger(__name__)


def generate_random_route() -> Dict[str, str]:
    """
    Generate a random route for write operations.
    
    Returns:
        Dictionary with tenant, service, env, version, url
    """
    tenant_prefixes = ["team", "org", "company", "corp", "group", "squad"]
    tenant_suffixes = [chr(i) for i in range(ord('a'), ord('z')+1)] + [str(i) for i in range(1, 100)]
    
    services = [
        "payments", "orders", "users", "analytics", "notifications", "auth",
        "billing", "inventory", "shipping", "catalog", "search", "recommendations"
    ]
    
    environments = ["prod", "staging", "dev", "test", "qa"]
    
    tenant_prefix = random.choice(tenant_prefixes)
    tenant_suffix = random.choice(tenant_suffixes)
    tenant = f"{tenant_prefix}-{tenant_suffix}"
    
    service = random.choice(services)
    env = random.choice(environments)
    version = f"v{random.randint(1, 20)}"
    
    # Generate random URL
    url_patterns = [
        f"https://{service}.{tenant}.example.com/{version}",
        f"https://{service}-{env}.{tenant}.example.com/{version}",
        f"https://{tenant}-{service}.example.com/{version}",
        f"https://api.{tenant}.example.com/{service}/{version}",
    ]
    url = random.choice(url_patterns)
    
    return {
        "tenant": tenant,
        "service": service,
        "env": env,
        "version": version,
        "url": url
    }


def make_create_request(api_url: str, route: Dict[str, str], request_id: int) -> Tuple[int, float, int, Optional[str]]:
    """
    Make a POST request to create a route.
    
    Args:
        api_url: Base URL of the API
        route: Route dictionary
        request_id: Unique identifier for this request
    
    Returns:
        Tuple of (request_id, response_time_ms, status_code, error_message)
    """
    url = f"{api_url}/api/v1/routes"
    
    start_time = time.time()
    try:
        response = requests.post(url, json=route, timeout=10)
        elapsed_ms = (time.time() - start_time) * 1000
        
        return (request_id, elapsed_ms, response.status_code, None)
    
    except requests.exceptions.RequestException as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return (request_id, elapsed_ms, 0, str(e))


def make_activate_request(api_url: str, route: Dict[str, str], request_id: int) -> Tuple[int, float, int, Optional[str]]:
    """
    Make a POST request to activate a route.
    
    Args:
        api_url: Base URL of the API
        route: Route dictionary (without url)
        request_id: Unique identifier for this request
    
    Returns:
        Tuple of (request_id, response_time_ms, status_code, error_message)
    """
    url = f"{api_url}/api/v1/routes/activate"
    payload = {
        "tenant": route["tenant"],
        "service": route["service"],
        "env": route["env"],
        "version": route["version"]
    }
    
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, timeout=10)
        elapsed_ms = (time.time() - start_time) * 1000
        
        return (request_id, elapsed_ms, response.status_code, None)
    
    except requests.exceptions.RequestException as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return (request_id, elapsed_ms, 0, str(e))


def make_deactivate_request(api_url: str, route: Dict[str, str], request_id: int) -> Tuple[int, float, int, Optional[str]]:
    """
    Make a POST request to deactivate a route.
    
    Args:
        api_url: Base URL of the API
        route: Route dictionary (without url)
        request_id: Unique identifier for this request
    
    Returns:
        Tuple of (request_id, response_time_ms, status_code, error_message)
    """
    url = f"{api_url}/api/v1/routes/deactivate"
    payload = {
        "tenant": route["tenant"],
        "service": route["service"],
        "env": route["env"],
        "version": route["version"]
    }
    
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, timeout=10)
        elapsed_ms = (time.time() - start_time) * 1000
        
        return (request_id, elapsed_ms, response.status_code, None)
    
    except requests.exceptions.RequestException as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return (request_id, elapsed_ms, 0, str(e))


def run_load_test(
    api_url: str,
    total_requests: int,
    num_threads: int,
    operation: str = "create"
) -> Dict:
    """
    Run the load test with concurrent write requests.
    
    Args:
        api_url: Base URL of the API
        total_requests: Total number of requests to make
        num_threads: Number of concurrent threads
        operation: Operation type (create, activate, deactivate, mixed)
    
    Returns:
        Dictionary with test results and statistics
    """
    logger.info(f"Starting write load test:")
    logger.info(f"  API URL: {api_url}")
    logger.info(f"  Total requests: {total_requests}")
    logger.info(f"  Concurrent threads: {num_threads}")
    logger.info(f"  Operation: {operation}")
    
    # Results tracking
    results = {
        "total_requests": total_requests,
        "completed": 0,
        "successful": 0,
        "failed": 0,
        "errors": 0,
        "response_times": [],
        "status_codes": {},
        "errors_list": [],
        "operations": {
            "create": 0,
            "activate": 0,
            "deactivate": 0
        }
    }
    
    start_time = time.time()
    
    # Choose request function based on operation
    if operation == "create":
        request_func = make_create_request
    elif operation == "activate":
        request_func = make_activate_request
    elif operation == "deactivate":
        request_func = make_deactivate_request
    elif operation == "mixed":
        # For mixed, we'll randomly choose operations
        def mixed_request(api_url, route, request_id):
            op = random.choice(["create", "activate", "deactivate"])
            results["operations"][op] += 1
            if op == "create":
                return make_create_request(api_url, route, request_id)
            elif op == "activate":
                return make_activate_request(api_url, route, request_id)
            else:
                return make_deactivate_request(api_url, route, request_id)
        request_func = mixed_request
    else:
        raise ValueError(f"Unknown operation: {operation}")
    
    # Use ThreadPoolExecutor for concurrent requests
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit all requests
        futures = []
        for i in range(total_requests):
            route = generate_random_route()
            future = executor.submit(request_func, api_url, route, i)
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
            elif status_code in [200, 201]:
                results["successful"] += 1
            else:
                results["failed"] += 1
            
            # Track status codes
            if status_code not in results["status_codes"]:
                results["status_codes"][status_code] = 0
            results["status_codes"][status_code] += 1
            
            completed += 1
            # Log progress every 50 requests (fewer for writes)
            if completed % 50 == 0 or completed == total_requests:
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
    print("WRITE LOAD TEST RESULTS")
    print("="*70)
    
    print(f"\n📊 Request Summary:")
    print(f"  Total requests:     {results['total_requests']}")
    print(f"  Completed:          {results['completed']}")
    print(f"  Successful:         {results['successful']}")
    print(f"  Failed:             {results['failed']}")
    print(f"  Errors:             {results['errors']}")
    
    if results.get("operations"):
        ops = results["operations"]
        if ops["create"] > 0 or ops["activate"] > 0 or ops["deactivate"] > 0:
            print(f"\n📝 Operations Breakdown:")
            if ops["create"] > 0:
                print(f"  Create:    {ops['create']}")
            if ops["activate"] > 0:
                print(f"  Activate:  {ops['activate']}")
            if ops["deactivate"] > 0:
                print(f"  Deactivate: {ops['deactivate']}")
    
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
        print(f"  Median response time:   {stats['median_response_time_ms']:.2f} ms")
        print(f"  Min response time:      {stats['min_response_time_ms']:.2f} ms")
        print(f"  Max response time:      {stats['max_response_time_ms']:.2f} ms")
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
        description="Load test the write path (route creation, activation, deactivation)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic load test with defaults (100 requests, 5 threads, create operation)
  python scripts/load_test_write.py
  
  # High load test (500 requests, 10 threads)
  python scripts/load_test_write.py --requests 500 --threads 10
  
  # Test activate operations
  python scripts/load_test_write.py --operation activate --requests 200
  
  # Test mixed operations (create, activate, deactivate)
  python scripts/load_test_write.py --operation mixed --requests 300
  
  # Test against different API URL
  python scripts/load_test_write.py --api-url http://localhost:8080
        """
    )
    
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        help="Total number of requests to make (default: 100)"
    )
    
    parser.add_argument(
        "--threads",
        type=int,
        default=5,
        help="Number of concurrent threads (default: 5)"
    )
    
    parser.add_argument(
        "--api-url",
        type=str,
        default=f"http://{settings.app.api_host}:{settings.app.api_port}",
        help=f"Base URL of the API (default: http://{settings.app.api_host}:{settings.app.api_port})"
    )
    
    parser.add_argument(
        "--operation",
        type=str,
        choices=["create", "activate", "deactivate", "mixed"],
        default="create",
        help="Operation type: create, activate, deactivate, or mixed (default: create)"
    )
    
    args = parser.parse_args()
    
    # Run the load test
    try:
        results = run_load_test(
            api_url=args.api_url,
            total_requests=args.requests,
            num_threads=args.threads,
            operation=args.operation
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
