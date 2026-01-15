# MongoDB Audit Store Queries

The audit store uses MongoDB to provide rich querying capabilities for route change history. This document shows how to answer common audit questions.

## Overview

The audit store is designed to answer questions like:
- **Who changed this route?** (changed_by field)
- **When did it change?** (occurred_at timestamp)
- **What was the previous value?** (previous_url, previous_state)
- **Can we see history for last 30/90 days?** (time-based queries)
- **Can we debug an outage caused by a config change?** (full event context)

## Document Structure

Each audit event is stored as a MongoDB document with the following structure:

```json
{
  "_id": ObjectId("..."),
  "event_id": "uuid",
  "event_type": "route_changed",
  "action": "created|activated|deactivated",
  "route": {
    "tenant": "team-a",
    "service": "payments",
    "env": "prod",
    "version": "v2"
  },
  "url": "https://payments-v2.example.com",
  "previous_url": "https://payments-v1.example.com",
  "previous_state": "active",
  "changed_by": "user@example.com",
  "occurred_at": ISODate("2024-01-14T17:30:00Z"),
  "processed_at": ISODate("2024-01-14T17:30:01Z"),
  "metadata": {}
}
```

## Indexes

The following indexes are automatically created for efficient querying:

1. **Compound index on route fields + occurred_at**: `route.tenant`, `route.service`, `route.env`, `route.version`, `occurred_at`
   - Supports route-specific queries and history retrieval
   
2. **Index on occurred_at**: For time-based queries
   - Supports "last 30/90 days" queries
   
3. **Index on action + occurred_at**: For filtering by action type
   - Supports debugging outages by config changes
   
4. **Unique index on event_id**: For deduplication

## Example Queries

### 1. Who changed this route?

Find all changes to a specific route:

```javascript
db.route_events.find({
  "route.tenant": "team-a",
  "route.service": "payments",
  "route.env": "prod",
  "route.version": "v2"
}).sort({ "occurred_at": -1 })
```

With changed_by information:

```javascript
db.route_events.find({
  "route.tenant": "team-a",
  "route.service": "payments",
  "route.env": "prod",
  "route.version": "v2"
}).projection({
  "changed_by": 1,
  "action": 1,
  "occurred_at": 1,
  "url": 1
}).sort({ "occurred_at": -1 })
```

### 2. When did it change?

Get all changes with timestamps:

```javascript
db.route_events.find({
  "route.tenant": "team-a",
  "route.service": "payments",
  "route.env": "prod",
  "route.version": "v2"
}).projection({
  "action": 1,
  "occurred_at": 1,
  "processed_at": 1
}).sort({ "occurred_at": -1 })
```

### 3. What was the previous value?

Get change history showing previous and current values:

```javascript
db.route_events.find({
  "route.tenant": "team-a",
  "route.service": "payments",
  "route.env": "prod",
  "route.version": "v2"
}).projection({
  "action": 1,
  "url": 1,
  "previous_url": 1,
  "previous_state": 1,
  "occurred_at": 1
}).sort({ "occurred_at": -1 })
```

### 4. History for last 30/90 days

Last 30 days:

```javascript
const thirtyDaysAgo = new Date();
thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

db.route_events.find({
  "occurred_at": { "$gte": thirtyDaysAgo }
}).sort({ "occurred_at": -1 })
```

Last 90 days:

```javascript
const ninetyDaysAgo = new Date();
ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 90);

db.route_events.find({
  "occurred_at": { "$gte": ninetyDaysAgo }
}).sort({ "occurred_at": -1 })
```

For a specific route in the last 30 days:

```javascript
const thirtyDaysAgo = new Date();
thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

db.route_events.find({
  "route.tenant": "team-a",
  "route.service": "payments",
  "route.env": "prod",
  "route.version": "v2",
  "occurred_at": { "$gte": thirtyDaysAgo }
}).sort({ "occurred_at": -1 })
```

### 5. Debug an outage caused by a config change

Find all deactivations or URL changes around a specific time:

```javascript
// Find deactivations in the last hour (assuming outage just happened)
const oneHourAgo = new Date();
oneHourAgo.setHours(oneHourAgo.getHours() - 1);

db.route_events.find({
  "action": { "$in": ["deactivated", "created"] },
  "occurred_at": { "$gte": oneHourAgo }
}).sort({ "occurred_at": -1 })
```

Find changes to a specific service/environment:

```javascript
const oneHourAgo = new Date();
oneHourAgo.setHours(oneHourAgo.getHours() - 1);

db.route_events.find({
  "route.tenant": "team-a",
  "route.service": "payments",
  "route.env": "prod",
  "occurred_at": { "$gte": oneHourAgo }
}).sort({ "occurred_at": -1 })
```

Find all changes between two timestamps:

```javascript
const startTime = new Date("2024-01-14T17:00:00Z");
const endTime = new Date("2024-01-14T18:00:00Z");

db.route_events.find({
  "occurred_at": {
    "$gte": startTime,
    "$lte": endTime
  }
}).sort({ "occurred_at": -1 })
```

## Using MongoDB Shell

Connect to MongoDB:

```bash
# Using docker exec
docker exec -it mongodb mongosh -u admin -p admin_password

# Or using mongosh directly (if installed locally)
mongosh mongodb://admin:admin_password@localhost:27017/audit_db
```

## Using Python (pymongo)

Example Python script for querying audit events:

```python
from pymongo import MongoClient
from datetime import datetime, timedelta

# Connect to MongoDB
client = MongoClient(
    "mongodb://admin:admin_password@localhost:27017/audit_db"
)
db = client["audit_db"]
collection = db["route_events"]

# Query: Who changed this route?
results = collection.find({
    "route.tenant": "team-a",
    "route.service": "payments",
    "route.env": "prod",
    "route.version": "v2"
}).sort("occurred_at", -1)

for event in results:
    print(f"{event['occurred_at']}: {event['action']} by {event.get('changed_by', 'unknown')}")

# Query: History for last 30 days
thirty_days_ago = datetime.utcnow() - timedelta(days=30)
results = collection.find({
    "occurred_at": {"$gte": thirty_days_ago}
}).sort("occurred_at", -1)

# Query: Debug outage (changes in last hour)
one_hour_ago = datetime.utcnow() - timedelta(hours=1)
results = collection.find({
    "action": {"$in": ["deactivated", "created"]},
    "occurred_at": {"$gte": one_hour_ago}
}).sort("occurred_at", -1)
```

## Aggregation Examples

### Count changes by action type

```javascript
db.route_events.aggregate([
  {
    "$group": {
      "_id": "$action",
      "count": { "$sum": 1 }
    }
  },
  {
    "$sort": { "count": -1 }
  }
])
```

### Changes per service

```javascript
db.route_events.aggregate([
  {
    "$group": {
      "_id": {
        "tenant": "$route.tenant",
        "service": "$route.service"
      },
      "count": { "$sum": 1 }
    }
  },
  {
    "$sort": { "count": -1 }
  }
])
```

### Timeline of changes

```javascript
db.route_events.aggregate([
  {
    "$group": {
      "_id": {
        "$dateToString": {
          "format": "%Y-%m-%d",
          "date": "$occurred_at"
        }
      },
      "count": { "$sum": 1 }
    }
  },
  {
    "$sort": { "_id": -1 }
  }
])
```

## Best Practices

1. **Use indexes**: All common query patterns are indexed. Use the indexed fields in your queries.

2. **Limit results**: For large result sets, use `.limit()`:
   ```javascript
   db.route_events.find({...}).limit(100)
   ```

3. **Projection**: Only retrieve fields you need:
   ```javascript
   db.route_events.find({...}).projection({ "action": 1, "occurred_at": 1 })
   ```

4. **Time-based queries**: Always use indexed `occurred_at` field for time-based queries.

5. **Compound queries**: Use compound indexes (route fields + occurred_at) for route-specific history queries.

## Performance Considerations

- Indexes are automatically created on startup
- Queries using indexed fields are fast (milliseconds)
- Time-based queries on `occurred_at` are efficient
- Compound queries on route fields + time are optimized
- For very large collections, consider TTL indexes for automatic cleanup of old data

## TTL Index (Optional)

To automatically delete old audit events (e.g., older than 1 year):

```javascript
// Create TTL index on occurred_at (expires after 365 days)
db.route_events.createIndex(
  { "occurred_at": 1 },
  { "expireAfterSeconds": 31536000 }  // 365 days in seconds
)
```

**Note**: Only create TTL index if you want automatic cleanup. The audit store is designed to retain history for compliance and debugging purposes.
