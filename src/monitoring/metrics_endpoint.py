# src/monitoring/metrics_endpoint.py
# This file sets up the Prometheus metrics endpoint
# Prometheus is a monitoring system that collects metrics from applications
# It scrapes (pulls) metrics from a /metrics endpoint periodically

from flask import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from logger import get_logger

logger = get_logger(__name__)


def setup_metrics_endpoint(app):
    """
    Set up the /metrics endpoint for Prometheus to scrape.
    
    This endpoint exposes all Prometheus metrics in the standard format.
    Prometheus will periodically request this endpoint (every 15-60 seconds)
    and collect the metrics.
    
    How it works:
    1. Prometheus scrapes http://your-app:8000/metrics
    2. Application returns all metrics in Prometheus format
    3. Prometheus stores the metrics
    4. You can query and visualize metrics in Grafana
    
    Args:
        app: Flask application instance
    
    Example Prometheus output:
        # HELP resolve_requests_total Total number of resolve requests
        # TYPE resolve_requests_total counter
        resolve_requests_total 1234.0
        
        # HELP resolve_latency_seconds Latency of resolve requests
        # TYPE resolve_latency_seconds histogram
        resolve_latency_seconds_bucket{le="0.005"} 1000.0
        resolve_latency_seconds_bucket{le="0.01"} 1200.0
        ...
    """
    @app.route('/metrics', methods=['GET'])
    def metrics():
        """
        Prometheus metrics endpoint.
        
        This endpoint returns all metrics in Prometheus exposition format.
        Prometheus will scrape this endpoint to collect metrics.
        
        Returns:
            HTTP response with metrics in Prometheus format
        
        Example:
            curl http://localhost:8000/metrics
        """
        try:
            # generate_latest() collects all registered Prometheus metrics
            # and formats them in the standard Prometheus text format
            # This includes all counters, histograms, gauges, etc.
            metrics_data = generate_latest()
            
            # Return the metrics with proper content type
            # CONTENT_TYPE_LATEST is the standard MIME type for Prometheus metrics
            # It's: "text/plain; version=0.0.4; charset=utf-8"
            return Response(
                metrics_data,
                mimetype=CONTENT_TYPE_LATEST
            )
            
        except Exception as e:
            # If generating metrics fails, log it and return error
            # We don't want metrics endpoint failure to break the app
            logger.error(f"Error generating metrics: {e}", exc_info=True)
            return Response(
                f"Error generating metrics: {str(e)}",
                status=500,
                mimetype='text/plain'
            )
    
    logger.info("Prometheus metrics endpoint registered at /metrics")
