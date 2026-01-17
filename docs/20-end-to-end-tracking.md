# End-to-End Request Tracking

This document explains the end-to-end request tracking system implemented in Traffic Manager using correlation IDs.

## Overview

End-to-end request tracking allows you to trace a single request through all components of the system:
- API layer
- Service layer
- Database queries
- Cache operations
- Kafka events
- Consumer processing

This is essential for:
- **Debugging**: Finding all logs related to a specific request
- **Performance Analysis**: Understanding where time is spent in a request
- **Distributed Tracing**: Following requests across services and components
- **Troubleshooting**: Correlating errors with specific requests

## How It Works

### Correlation IDs

A **correlation ID** is a unique identifier assigned to each request. It flows through all components and appears in:
- All log messages
- Kafka events
- Response headers
- Metrics (when applicable)

### Request Flow

1. **Client sends request** with optional `X-Correlation-ID` header
2. **Tracking middleware** extracts the correlation ID or generates a new one
3. **Correlation ID is set** in request context (thread-local storage)
4. **All operations** automatically include the correlation ID in logs
5. **Kafka events** include the correlation ID
6. **Consumers** extract and use the correlation ID from events
7. **Response** includes the correlation ID in `X-Correlation-ID` header

## Usage

### Client-Side Tracking

Clients can provide their own correlation ID to trace requests across services:

```bash
curl -X GET "http://localhost:8000/api/v1/routes/resolve?tenant=team-a&service=payments&env=prod&version=v2" \
  -H "X-Correlation-ID: my-custom-id-12345"
```

The same correlation ID will appear in:
- All log messages for this request
- Kafka events published by this request
- Response headers

### Automatic Generation

If no `X-Correlation-ID` header is provided, the system automatically generates one:

```
req-abc123def4567890
```

The format is: `req-` followed by 16 hexadecimal characters (UUID-based).

### Response Headers

All responses include the correlation ID in the `X-Correlation-ID` header:

```bash
HTTP/1.1 200 OK
X-Correlation-ID: req-abc123def4567890
Content-Type: application/json

{
  "tenant": "team-a",
  "service": "payments",
  "env": "prod",
  "version": "v2",
  "url": "https://payments.example.com/v2"
}
```

## Log Format

All log messages include the correlation ID in a structured format:

```
2024-01-14 17:30:00,123 - [req-abc123def4567890] - src.service.routing - INFO - Resolving endpoint: team-a/payments/prod/v2
2024-01-14 17:30:00,125 - [req-abc123def4567890] - src.cache.redis_client - DEBUG - Cache miss for key: route:team-a:payments:prod:v2
2024-01-14 17:30:00,150 - [req-abc123def4567890] - src.service.routing - INFO - Route found in database
```

The format is: `[correlation_id]` appears after the timestamp and before the logger name.

## Kafka Events

All Kafka events include the correlation ID from the original request:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "event_type": "route_changed",
  "action": "created",
  "tenant": "team-a",
  "service": "payments",
  "env": "prod",
  "version": "v2",
  "url": "https://payments.example.com/v2",
  "occurred_at": "2024-01-14T17:30:00Z",
  "correlation_id": "req-abc123def4567890"
}
```

This allows tracing events back to the original request that triggered them.

## Consumer Processing

Kafka consumers automatically extract and use correlation IDs from events:

1. Consumer receives event with `correlation_id` field
2. Consumer sets correlation ID in its processing context
3. All consumer logs include the correlation ID
4. Audit logs in MongoDB include the correlation ID

Example consumer log:

```
2024-01-14 17:30:01,200 - [req-abc123def4567890] - src.kafka_client.consumer - INFO - Received audit event #42: action=created
2024-01-14 17:30:01,250 - [req-abc123def4567890] - src.mongodb_client.client - INFO - Audit log saved to MongoDB
```

## Querying by Correlation ID

### Logs

You can search logs by correlation ID to see all operations for a request:

```bash
# Using grep
grep "req-abc123def4567890" /var/log/traffic-manager.log

# Using structured logging tools (e.g., ELK, Splunk)
correlation_id:"req-abc123def4567890"
```

### MongoDB Audit Store

Audit documents in MongoDB include the correlation ID:

```javascript
db.route_events.find({ correlation_id: "req-abc123def4567890" })
```

This returns all audit events related to the original request.

## Metrics

Tracking metrics are available in Prometheus:

- `correlation_ids_generated_total`: Count of correlation IDs generated (when not provided by client)
- `correlation_ids_provided_total`: Count of correlation IDs provided by clients

These metrics help understand:
- How many clients are providing their own correlation IDs
- How many requests need automatic generation

## Implementation Details

### Tracking Module (`src/tracking/`)

- **`correlation.py`**: Core correlation ID management
  - `generate_correlation_id()`: Creates new correlation IDs
  - `get_correlation_id()`: Retrieves current correlation ID
  - `set_correlation_id()`: Sets correlation ID in context
  - `correlation_context()`: Context manager for scoped correlation IDs

- **`middleware.py`**: Flask middleware for correlation ID handling
  - Extracts correlation ID from `X-Correlation-ID` header
  - Generates new correlation ID if not provided
  - Adds correlation ID to response headers

### Logger Integration

The logger automatically includes correlation IDs via a custom filter:

```python
class CorrelationIDFilter(logging.Filter):
    def filter(self, record):
        correlation_id = get_correlation_id()
        record.correlation_id = correlation_id or "-"
        return True
```

### Context Variables

Correlation IDs are stored using Python's `contextvars`, which provides:
- Thread-safe storage
- Async/await compatibility
- Request-scoped isolation

## Best Practices

### 1. Always Include Correlation ID in Client Requests

When making requests from other services, include the correlation ID:

```python
import requests

correlation_id = "req-abc123def4567890"
response = requests.get(
    "http://traffic-manager:8000/api/v1/routes/resolve",
    headers={"X-Correlation-ID": correlation_id}
)
```

### 2. Log Correlation ID in External Service Calls

When calling external services, log the correlation ID:

```python
logger.info(f"Calling external service with correlation_id={correlation_id}")
```

### 3. Use Correlation ID for Error Reporting

Include correlation ID in error reports to trace issues:

```python
try:
    # operation
except Exception as e:
    correlation_id = get_correlation_id()
    error_report = {
        "error": str(e),
        "correlation_id": correlation_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    send_to_error_tracking(error_report)
```

### 4. Query by Correlation ID for Debugging

When debugging an issue:
1. Get the correlation ID from the error response
2. Search logs for that correlation ID
3. Review all operations for that request
4. Check MongoDB audit store for related events

## Troubleshooting

### Correlation ID Not Appearing in Logs

If correlation IDs are not appearing in logs:
1. Check that tracking middleware is enabled in `app.py`
2. Verify logger configuration includes `CorrelationIDFilter`
3. Ensure `tracking` module is properly imported

### Correlation ID Not in Kafka Events

If correlation IDs are missing from Kafka events:
1. Check that `publish_route_event()` calls `get_correlation_id()`
2. Verify correlation ID is set before publishing events
3. Check event payload includes `correlation_id` field

### Correlation ID Not in Consumer Logs

If consumer logs don't include correlation IDs:
1. Verify consumer extracts `correlation_id` from event
2. Check that `correlation_context()` is used in consumer processing
3. Ensure logger is configured with correlation ID filter

## Summary

End-to-end request tracking with correlation IDs provides:

- ✅ **Complete Request Visibility**: Trace requests through all components
- ✅ **Easy Debugging**: Find all logs for a specific request
- ✅ **Distributed Tracing**: Follow requests across services
- ✅ **Performance Analysis**: Understand request flow and timing
- ✅ **Error Correlation**: Link errors to specific requests

The system automatically handles correlation ID generation, propagation, and logging, making it easy to trace any request through the entire system.
