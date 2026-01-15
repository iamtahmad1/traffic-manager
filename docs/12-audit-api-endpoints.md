# Audit API Endpoints

This document describes the REST API endpoints for querying audit logs from MongoDB.

## Base URL

All audit endpoints are under `/api/v1/audit/`

## Endpoints

### 1. Get Route History

Get audit history for a specific route.

**Endpoint:** `GET /api/v1/audit/route`

**Query Parameters:**
- `tenant` (required): Tenant name
- `service` (required): Service name
- `env` (required): Environment name
- `version` (required): Version name
- `limit` (optional): Maximum number of events to return (default: 100, max: 1000)

**Example Request:**
```bash
curl "http://localhost:8000/api/v1/audit/route?tenant=team-a&service=payments&env=prod&version=v2&limit=50"
```

**Example Response:**
```json
{
  "route": {
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v2"
  },
  "count": 3,
  "events": [
    {
      "event_id": "uuid-1",
      "action": "activated",
      "url": "https://payments.example.com/v2",
      "previous_url": null,
      "previous_state": null,
      "changed_by": "user@example.com",
      "occurred_at": "2024-01-14T17:30:00",
      "processed_at": "2024-01-14T17:30:01"
    },
    {
      "event_id": "uuid-2",
      "action": "created",
      "url": "https://payments.example.com/v2",
      "previous_url": null,
      "previous_state": null,
      "changed_by": "user@example.com",
      "occurred_at": "2024-01-14T17:25:00",
      "processed_at": "2024-01-14T17:25:01"
    }
  ]
}
```

**Use Cases:**
- "Who changed this route?"
- "When did it change?"
- "What was the previous value?"

---

### 2. Get Recent Events

Get audit events from the last N days.

**Endpoint:** `GET /api/v1/audit/recent`

**Query Parameters:**
- `days` (optional): Number of days to look back (default: 30, max: 365)
- `tenant` (optional): Filter by tenant
- `service` (optional): Filter by service
- `env` (optional): Filter by environment
- `limit` (optional): Maximum number of events to return (default: 100, max: 1000)

**Example Request:**
```bash
# Last 90 days
curl "http://localhost:8000/api/v1/audit/recent?days=90&limit=200"

# Last 30 days for specific tenant/service
curl "http://localhost:8000/api/v1/audit/recent?days=30&tenant=team-a&service=payments"
```

**Example Response:**
```json
{
  "days": 30,
  "count": 150,
  "events": [
    {
      "event_id": "uuid-1",
      "action": "deactivated",
      "route": {
        "tenant": "team-a",
        "service": "payments",
        "env": "prod",
        "version": "v1"
      },
      "url": "https://payments.example.com/v1",
      "previous_url": null,
      "previous_state": "active",
      "changed_by": "admin@example.com",
      "occurred_at": "2024-01-14T17:30:00",
      "processed_at": "2024-01-14T17:30:01"
    }
  ]
}
```

**Use Cases:**
- "Can we see history for last 30/90 days?"

---

### 3. Get Events by Action

Get audit events filtered by action type, optionally within a time window.

**Endpoint:** `GET /api/v1/audit/action`

**Query Parameters:**
- `action` (required): Action type - `created`, `activated`, or `deactivated`
- `hours` (optional): Number of hours to look back
- `tenant` (optional): Filter by tenant
- `service` (optional): Filter by service
- `env` (optional): Filter by environment
- `limit` (optional): Maximum number of events to return (default: 100, max: 1000)

**Example Request:**
```bash
# All deactivations in the last hour
curl "http://localhost:8000/api/v1/audit/action?action=deactivated&hours=1"

# All creations for a specific service
curl "http://localhost:8000/api/v1/audit/action?action=created&tenant=team-a&service=payments"
```

**Example Response:**
```json
{
  "action": "deactivated",
  "hours": 1,
  "count": 5,
  "events": [
    {
      "event_id": "uuid-1",
      "action": "deactivated",
      "route": {
        "tenant": "team-a",
        "service": "payments",
        "env": "prod",
        "version": "v1"
      },
      "url": "https://payments.example.com/v1",
      "previous_url": null,
      "previous_state": "active",
      "changed_by": "admin@example.com",
      "occurred_at": "2024-01-14T17:30:00",
      "processed_at": "2024-01-14T17:30:01"
    }
  ]
}
```

**Use Cases:**
- "Can we debug an outage caused by a config change?"
- Find all deactivations around a specific time
- Track all route creations

---

### 4. Get Events in Time Range

Get audit events within a specific time range.

**Endpoint:** `GET /api/v1/audit/time-range`

**Query Parameters:**
- `start_time` (required): Start of time range in ISO 8601 format (e.g., `2024-01-14T17:00:00Z`)
- `end_time` (required): End of time range in ISO 8601 format (e.g., `2024-01-14T18:00:00Z`)
- `tenant` (optional): Filter by tenant
- `service` (optional): Filter by service
- `env` (optional): Filter by environment
- `action` (optional): Filter by action (`created`, `activated`, `deactivated`)
- `limit` (optional): Maximum number of events to return (default: 100, max: 1000)

**Example Request:**
```bash
# Events between two timestamps
curl "http://localhost:8000/api/v1/audit/time-range?start_time=2024-01-14T17:00:00Z&end_time=2024-01-14T18:00:00Z"

# Events in time range for specific service and action
curl "http://localhost:8000/api/v1/audit/time-range?start_time=2024-01-14T17:00:00Z&end_time=2024-01-14T18:00:00Z&tenant=team-a&service=payments&action=deactivated"
```

**Example Response:**
```json
{
  "start_time": "2024-01-14T17:00:00Z",
  "end_time": "2024-01-14T18:00:00Z",
  "count": 10,
  "events": [
    {
      "event_id": "uuid-1",
      "action": "deactivated",
      "route": {
        "tenant": "team-a",
        "service": "payments",
        "env": "prod",
        "version": "v1"
      },
      "url": "https://payments.example.com/v1",
      "previous_url": null,
      "previous_state": "active",
      "changed_by": "admin@example.com",
      "occurred_at": "2024-01-14T17:30:00",
      "processed_at": "2024-01-14T17:30:01"
    }
  ]
}
```

**Use Cases:**
- Debug outages by looking at changes in a specific time window
- Investigate incidents with precise time boundaries
- Audit compliance reporting for specific periods

---

## Error Responses

All endpoints return standard error responses:

**400 Bad Request:**
```json
{
  "error": "Missing required parameters",
  "required": ["tenant", "service", "env", "version"]
}
```

**500 Internal Server Error:**
```json
{
  "error": "Internal server error",
  "message": "An unexpected error occurred"
}
```

## Response Format

All successful responses include:
- `count`: Number of events returned
- `events`: Array of audit event objects

Each audit event contains:
- `event_id`: Unique event identifier
- `action`: Action type (created, activated, deactivated)
- `route`: Route identifiers (tenant, service, env, version)
- `url`: Current URL
- `previous_url`: Previous URL (if available)
- `previous_state`: Previous state (if available)
- `changed_by`: User who made the change (if available)
- `occurred_at`: Timestamp when the event occurred (ISO 8601)
- `processed_at`: Timestamp when the event was processed (ISO 8601)

## Performance Notes

- All queries use MongoDB indexes for efficient retrieval
- Results are sorted by `occurred_at` descending (most recent first)
- Default limit is 100 events, maximum is 1000
- Time-based queries are optimized with indexes on `occurred_at`
- Route-specific queries use compound indexes for fast lookups

## Examples

### Find who changed a route recently
```bash
curl "http://localhost:8000/api/v1/audit/route?tenant=team-a&service=payments&env=prod&version=v2&limit=10"
```

### Check for deactivations in the last hour (outage investigation)
```bash
curl "http://localhost:8000/api/v1/audit/action?action=deactivated&hours=1"
```

### Get all changes in the last 90 days
```bash
curl "http://localhost:8000/api/v1/audit/recent?days=90&limit=500"
```

### Investigate changes during a specific outage window
```bash
curl "http://localhost:8000/api/v1/audit/time-range?start_time=2024-01-14T17:00:00Z&end_time=2024-01-14T18:00:00Z&action=deactivated"
```
