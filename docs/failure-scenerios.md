### Redis unavailable
Requests fall back to the database. Cache failure does not impact correctness.

### DB unavailable
Cached requests can still succeed. Cache misses fail because the DB is the source of truth.

### Cache stale
Users may receive stale routing data within the TTL window until the cache expires and refreshes.

### Route inactive
The API returns 404 Not Found. Inactive routes are intentionally invisible.

### Sudden traffic spike
The database becomes the first bottleneck on cache misses. Redis absorbs most read traffic for hot keys.
