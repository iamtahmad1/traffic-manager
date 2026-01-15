# Interview Questions by Topic - Senior/Staff/Principal Level

This document contains 5 interview questions for each topic, designed to help you prepare for senior/staff/principal platform/DevOps/SRE interviews.

---

## 1. Read Replicas (5 Questions)

### Q1: Explain how you would implement read replica routing in a Python application. What are the key considerations?

**Expected Answer Points**:
- Connection pool separation (read vs write pools)
- Routing logic based on operation type (SELECT → replica, INSERT/UPDATE → primary)
- Replication lag monitoring and handling
- Fallback to primary if replica fails
- Load balancing across multiple replicas
- Example: "I'd create separate connection pools for primary and replicas. Read operations use replica pool with round-robin selection. I monitor replication lag and route to primary if lag exceeds threshold (e.g., 1 second). If replica health check fails, all reads fallback to primary."

---

### Q2: How do you handle replication lag when using read replicas? What happens if a user reads immediately after a write?

**Expected Answer Points**:
- Replication lag is inevitable (typically 10-100ms)
- For read-after-write consistency, route to primary
- Use session-based routing (sticky sessions to primary after writes)
- Accept eventual consistency for most reads
- Monitor lag and alert if too high
- Example: "I use session-based routing - after a write, route that user's reads to primary for 30 seconds. For other reads, accept eventual consistency. I monitor replication lag and alert if it exceeds 500ms."

---

### Q3: What happens if a read replica fails? How do you ensure high availability?

**Expected Answer Points**:
- Health checks on replicas
- Automatic fallback to primary
- Remove failed replica from pool
- Retry logic with exponential backoff
- Monitoring and alerting
- Example: "I implement health checks every 5 seconds. If a replica fails, I immediately remove it from the pool and route all reads to primary. I also have retry logic to periodically check if the replica recovered. I alert on-call if primary is handling all traffic."

---

### Q4: How would you scale reads horizontally with read replicas? What's the maximum number of replicas you can have?

**Expected Answer Points**:
- Add more replicas as read load increases
- Load balance across replicas
- Consider replication overhead (each replica consumes resources)
- Network bandwidth limitations
- Typical limit: 5-10 replicas per primary
- Example: "I can add replicas up to the point where replication overhead becomes a bottleneck. Typically 5-10 replicas per primary. I use round-robin or least-connections load balancing. I monitor replica CPU and network to know when to add more."

---

### Q5: How do you monitor and alert on read replica health and performance?

**Expected Answer Points**:
- Replication lag metrics (seconds behind primary)
- Replica connection count
- Query latency on replicas
- Replica CPU/memory usage
- Alert on high lag (>1s) or replica failure
- Example: "I track replication lag via `pg_stat_replication`. I alert if lag exceeds 1 second or if replica is down. I also monitor query latency - if replica is slower than primary, investigate. I use Prometheus to scrape these metrics and Grafana for visualization."

---

## 2. Load Balancing & Multi-Instance (5 Questions)

### Q1: Explain the different load balancing algorithms. When would you use each one?

**Expected Answer Points**:
- Round-robin: Equal distribution, simple
- Least-connections: Best for long-lived connections
- IP-hash: Session affinity, sticky sessions
- Weighted: Different capacity servers
- Geographic: Route to nearest datacenter
- Example: "Round-robin for stateless APIs. Least-connections for database connections. IP-hash for session affinity. Weighted when servers have different capacities. I use least-connections for our API because it handles varying request durations better."

---

### Q2: How do you integrate health checks with load balancers? What happens during graceful draining?

**Expected Answer Points**:
- Load balancer checks `/health/ready` endpoint
- Unhealthy instances removed from rotation
- Graceful draining: stop accepting new requests, finish in-flight
- Readiness probe returns 503 during draining
- Load balancer stops sending traffic to draining instances
- Example: "My readiness probe checks dependencies and draining status. During graceful shutdown, it returns 503, so the load balancer stops sending new requests. In-flight requests complete, then the instance shuts down. This enables zero-downtime deployments."

---

### Q3: How do you handle session affinity (sticky sessions) in a load-balanced environment?

**Expected Answer Points**:
- IP-based affinity (same IP → same server)
- Cookie-based affinity (session cookie)
- Redis for shared session storage (stateless)
- Trade-offs: affinity vs. flexibility
- Example: "I prefer stateless design with Redis sessions. But if I need affinity, I use IP-hash algorithm or session cookies. The trade-off is less flexibility - if a server dies, those sessions are lost. Stateless is better for scalability."

---

### Q4: What's the difference between Layer 4 and Layer 7 load balancing? When would you use each?

**Expected Answer Points**:
- Layer 4 (L4): TCP/UDP level, faster, less intelligent
- Layer 7 (L7): HTTP level, can route by path/header, SSL termination
- L4: Simple, high throughput
- L7: More features, path-based routing, better for microservices
- Example: "L4 is faster and simpler - just forwards packets. L7 understands HTTP, can route by path (e.g., /api/v1 → service1, /api/v2 → service2), and handles SSL termination. I use L7 (Nginx/HAProxy) for our APIs because I need path-based routing and SSL termination."

---

### Q5: How do you ensure high availability with load balancing? What happens if the load balancer itself fails?

**Expected Answer Points**:
- Multiple load balancer instances (active-passive or active-active)
- Health checks on load balancers
- DNS failover (multiple A records)
- Keepalived for failover
- Cloud load balancers (AWS ALB, GCP LB) are managed
- Example: "I use cloud-managed load balancers (AWS ALB) which are highly available by default. For on-prem, I'd use Keepalived for active-passive failover. I also configure multiple load balancer instances behind DNS with health checks. If one fails, DNS routes to the healthy one."

---

## 3. Rate Limiting (5 Questions)

### Q1: Explain the token bucket algorithm. How does it differ from sliding window?

**Expected Answer Points**:
- Token bucket: Tokens added at fixed rate, bucket has capacity
- Sliding window: Track requests in time window, more accurate
- Token bucket: Simpler, allows bursts
- Sliding window: More precise, no bursts
- Example: "Token bucket adds tokens at a fixed rate (e.g., 100/min). Bucket can hold up to capacity (e.g., 20). This allows bursts - if bucket is full, 20 requests can go through immediately. Sliding window tracks exact requests in the last minute, more accurate but more complex."

---

### Q2: How would you implement per-tenant rate limiting? What data structure would you use?

**Expected Answer Points**:
- Separate rate limiter per tenant
- In-memory map: `{tenant_id: TokenBucket}`
- Redis for distributed rate limiting
- Configurable limits per tenant
- Example: "I use a dictionary mapping tenant_id to TokenBucket. For distributed systems, I use Redis with Lua scripts for atomic operations. Each tenant has configurable limits stored in database. I check limits before processing requests and return 429 with retry-after header if exceeded."

---

### Q3: What HTTP status code and headers should you return when rate limit is exceeded?

**Expected Answer Points**:
- Status: 429 Too Many Requests
- Headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After
- Retry-After: Seconds until limit resets
- Example: "I return 429 with headers: X-RateLimit-Limit: 100, X-RateLimit-Remaining: 0, X-RateLimit-Reset: 1640000000, Retry-After: 60. This tells the client their limit, how many remain, when it resets, and how long to wait."

---

### Q4: How do you handle rate limiting in a distributed system with multiple API instances?

**Expected Answer Points**:
- Shared state (Redis) for distributed rate limiting
- Lua scripts for atomic operations
- Consistent hashing for tenant distribution
- Approximate counting algorithms (if high scale)
- Example: "I use Redis with Lua scripts for atomic check-and-increment. Each tenant's rate limit is stored in Redis with TTL. The script atomically checks if limit is exceeded and increments counter. For very high scale, I might use approximate algorithms like HyperLogLog."

---

### Q5: How would you implement different rate limits for different API endpoints?

**Expected Answer Points**:
- Per-endpoint rate limits
- Middleware that checks endpoint + tenant
- Configuration: `{endpoint: {limit, window}}`
- More restrictive limits for expensive operations
- Example: "I configure rate limits per endpoint in a config map. Expensive operations (e.g., /api/v1/routes/bulk-create) have lower limits (10/min) than simple reads (1000/min). My middleware checks both endpoint and tenant, applying the more restrictive limit."

---

## 4. Distributed Tracing (5 Questions)

### Q1: Explain what distributed tracing is and why it's important for microservices.

**Expected Answer Points**:
- Traces show request flow across services
- Each operation is a "span" with timing
- Spans are linked in a "trace"
- Helps debug performance issues
- Essential for microservices debugging
- Example: "Distributed tracing shows how a request flows through multiple services. Each service creates spans (database query, cache lookup, API call). Spans are linked in a trace with a trace ID. This helps me see where time is spent and debug issues across services."

---

### Q2: How does trace context propagation work? How do you pass trace IDs between services?

**Expected Answer Points**:
- Trace ID and Span ID in headers
- W3C Trace Context standard (traceparent header)
- Propagated via HTTP headers, gRPC metadata, Kafka headers
- Each service creates child spans
- Example: "I use W3C Trace Context with traceparent header: `00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01`. The format is version-trace_id-parent_span_id-flags. Each service extracts this, creates a child span, and propagates to downstream services."

---

### Q3: How would you instrument a Python Flask application with OpenTelemetry?

**Expected Answer Points**:
- Install OpenTelemetry SDK
- Auto-instrumentation for Flask, database, Redis
- Manual spans for business logic
- Export to Jaeger/Zipkin
- Example: "I install opentelemetry-instrumentation-flask, psycopg2, redis. I initialize the SDK with Jaeger exporter. Auto-instrumentation handles HTTP requests automatically. For business logic, I create manual spans with tracer.start_as_current_span(). I export traces to Jaeger on port 6831."

---

### Q4: What information should you include in a trace span? What should you avoid?

**Expected Answer Points**:
- Include: Operation name, timing, tags (tenant, user_id, status codes)
- Avoid: Sensitive data (passwords, tokens, PII)
- Keep tags small (don't log entire request bodies)
- Use sampling for high-volume endpoints
- Example: "I include operation name, duration, tags like tenant_id, user_id, HTTP status. I avoid logging passwords, tokens, or full request bodies. I use sampling (e.g., 10% of requests) for high-volume endpoints to reduce overhead."

---

### Q5: How do you use distributed tracing to debug a slow API endpoint?

**Expected Answer Points**:
- Find trace for slow request
- Identify which span is slow
- Look at child spans to see what's taking time
- Compare with fast requests
- Example: "I search Jaeger for traces with high latency. I find the slow trace and see which span is taking time - maybe a database query span shows 2 seconds. I look at the query and see it's missing an index. I compare with a fast trace to see the difference."

---

## 5. Database Migrations (5 Questions)

### Q1: Explain why database migrations are important. What problems do they solve?

**Expected Answer Points**:
- Version control for database schema
- Reproducible deployments
- Rollback capabilities
- Team collaboration (multiple developers)
- Production safety
- Example: "Migrations version control the database schema, just like code. They ensure everyone has the same schema, enable rollbacks if something breaks, and make deployments reproducible. Without migrations, schema changes are manual and error-prone."

---

### Q2: How would you implement zero-downtime database migrations?

**Expected Answer Points**:
- Backward-compatible changes first
- Add columns as nullable, then populate, then make required
- Deploy code that works with old and new schema
- Remove old columns in separate migration
- Example: "For adding a required column: 1) Add column as nullable, 2) Deploy code that populates it, 3) Backfill data, 4) Make column NOT NULL, 5) Deploy code that requires it. Each step is backward-compatible, so no downtime."

---

### Q3: What's the difference between forward and backward migrations? How do you handle rollbacks?

**Expected Answer Points**:
- Forward (upgrade): Apply changes
- Backward (downgrade): Rollback changes
- Alembic/Flyway support both
- Test rollbacks in staging
- Example: "Forward migrations apply schema changes (upgrade). Backward migrations undo them (downgrade). I write both in Alembic. I test rollbacks in staging before production. If a migration fails, I can rollback to previous version."

---

### Q4: How do you run migrations in a Kubernetes environment?

**Expected Answer Points**:
- Init containers run migrations before app starts
- Jobs for one-time migrations
- Migrations run before new pods start
- Ensure migrations are idempotent
- Example: "I use init containers that run `alembic upgrade head` before the main container starts. This ensures migrations run before the app. For long-running migrations, I use Kubernetes Jobs. I make migrations idempotent so they're safe to run multiple times."

---

### Q5: What happens if a migration fails halfway through? How do you recover?

**Expected Answer Points**:
- Transactions ensure atomicity (all or nothing)
- Rollback to previous version
- Manual intervention may be needed
- Test migrations in staging first
- Have backup before migration
- Example: "If a migration fails, the transaction rolls back automatically. I can then run `alembic downgrade -1` to rollback. For complex migrations, I test in staging first and take a backup. If something goes wrong, I restore from backup and investigate."

---

## 6. Kubernetes Manifests (5 Questions)

### Q1: Explain the difference between Deployments and StatefulSets. When would you use each?

**Expected Answer Points**:
- Deployments: Stateless, pods are interchangeable
- StatefulSets: Stateful, stable network identity, ordered deployment
- Use Deployments for APIs, web servers
- Use StatefulSets for databases, Kafka, Zookeeper
- Example: "Deployments are for stateless apps - pods are identical and interchangeable. StatefulSets are for stateful apps - each pod has a stable identity (pod-0, pod-1), ordered startup/shutdown, and persistent storage. I use Deployments for APIs, StatefulSets for PostgreSQL."

---

### Q2: How do you configure resource requests and limits? What happens if you exceed limits?

**Expected Answer Points**:
- Requests: Guaranteed resources (scheduling)
- Limits: Maximum resources (throttling/killing)
- Exceeding limits: CPU throttled, memory OOMKilled
- Set requests = limits for guaranteed QoS
- Example: "Requests tell Kubernetes what resources the pod needs (for scheduling). Limits are the maximum (for protection). If CPU limit exceeded, pod is throttled. If memory limit exceeded, pod is OOMKilled. I set requests based on typical usage, limits based on worst case."

---

### Q3: Explain how Horizontal Pod Autoscaler (HPA) works. What metrics can you use?

**Expected Answer Points**:
- HPA scales pods based on metrics
- Default: CPU and memory utilization
- Custom metrics: requests per second, queue length
- Min/max replicas
- Example: "HPA monitors pod metrics (CPU, memory, or custom). If average CPU > target (e.g., 70%), it scales up. If below, it scales down. I configure min replicas (e.g., 3) and max (e.g., 10). I can use custom metrics like requests per second from Prometheus."

---

### Q4: What's the difference between liveness and readiness probes? How do you configure them?

**Expected Answer Points**:
- Liveness: Is the app running? (restart if fails)
- Readiness: Is the app ready? (remove from service if fails)
- Liveness: `/health/live` - simple check
- Readiness: `/health/ready` - checks dependencies
- Example: "Liveness checks if the process is alive - if it fails, Kubernetes restarts the pod. Readiness checks if the app is ready to serve traffic - if it fails, Kubernetes removes the pod from the service. I use `/health/live` for liveness (simple), `/health/ready` for readiness (checks DB, cache)."

---

### Q5: How do you manage secrets in Kubernetes? What are the best practices?

**Expected Answer Points**:
- Kubernetes Secrets (base64 encoded, not encrypted)
- External Secrets Operator (for Vault, AWS Secrets Manager)
- Don't commit secrets to Git
- Rotate secrets regularly
- Use RBAC to limit access
- Example: "I use Kubernetes Secrets for non-sensitive config, External Secrets Operator for sensitive data (connects to Vault). Secrets are base64 encoded but not encrypted at rest - I enable encryption at rest. I never commit secrets to Git. I rotate secrets regularly and use RBAC to limit who can access them."

---

## 7. Security (Auth/AuthZ) (5 Questions)

### Q1: Explain the difference between authentication and authorization. How do you implement both?

**Expected Answer Points**:
- Authentication: Who are you? (verify identity)
- Authorization: What can you do? (check permissions)
- Auth: JWT tokens, API keys
- AuthZ: RBAC, permissions, tenant isolation
- Example: "Authentication verifies identity (JWT token, API key). Authorization checks permissions (can this user access this tenant's data?). I use JWT for auth - token contains user_id, tenant_id, roles. I check roles/permissions before allowing operations. I enforce tenant isolation - users can only access their tenant's data."

---

### Q2: How do JWT tokens work? What information should you include in the payload?

**Expected Answer Points**:
- JWT: Header, payload, signature
- Payload: user_id, tenant_id, roles, exp (expiration)
- Signed with secret key
- Stateless (no server-side storage)
- Example: "JWT has three parts: header (algorithm), payload (claims like user_id, tenant_id, roles, exp), and signature (HMAC). The server signs it with a secret. Clients send it in Authorization header. I include user_id, tenant_id, roles, and expiration. I validate signature and expiration on each request."

---

### Q3: How do you implement role-based access control (RBAC)? Give an example.

**Expected Answer Points**:
- Roles: admin, user, viewer
- Permissions: create, read, update, delete
- Check roles before operations
- Tenant-level permissions
- Example: "I define roles: admin (all operations), user (create/read own), viewer (read only). Each role has permissions. Before operations, I check if the user's role has the required permission. I also check tenant - users can only access their tenant's data. I use decorators like @require_permission('create_route')."

---

### Q4: How do you handle tenant isolation in a multi-tenant system?

**Expected Answer Points**:
- Tenant ID in every request
- Filter queries by tenant_id
- Validate tenant access
- Prevent cross-tenant access
- Example: "I extract tenant_id from JWT token. Every database query includes tenant_id filter. I validate that the user's tenant matches the requested tenant. I never return data from other tenants. I use row-level security in the database if possible. I log all access attempts for auditing."

---

### Q5: How do you secure API keys? What's the difference between key ID and secret?

**Expected Answer Points**:
- Key ID: Public identifier (can be logged)
- Secret: Private, never exposed
- Hash secrets (don't store plaintext)
- Rotate keys regularly
- Store in secure vault
- Example: "Key ID is public (like username) - can be in logs. Secret is private (like password) - never log it, hash it before storing. I hash secrets with bcrypt. I store keys in Kubernetes Secrets or Vault. I rotate keys every 90 days. I validate key + secret together - both must match."

---

## 8. CI/CD Pipeline (5 Questions)

### Q1: Explain your CI/CD pipeline. What stages does it have?

**Expected Answer Points**:
- CI: Test, lint, build, security scan
- CD: Deploy to staging, test, deploy to prod
- Stages: build, test, security, deploy
- Quality gates (must pass tests to deploy)
- Example: "My pipeline has: 1) Build - compile code, 2) Test - unit and integration tests, 3) Lint - code quality, 4) Security scan - vulnerability scanning, 5) Build image - container image, 6) Deploy staging - deploy to K8s staging, 7) E2E tests, 8) Deploy prod - manual approval, then deploy. Each stage must pass to proceed."

---

### Q2: How do you implement blue-green or canary deployments?

**Expected Answer Points**:
- Blue-green: Two identical environments, switch traffic
- Canary: Gradual rollout (10% → 50% → 100%)
- Kubernetes: Use multiple Deployments or Argo Rollouts
- Monitor metrics during rollout
- Rollback if issues
- Example: "For canary: I deploy new version to 10% of pods. I monitor error rate, latency. If good, increase to 50%, then 100%. If bad, rollback. I use Argo Rollouts for this. For blue-green: I deploy new version alongside old, test it, then switch all traffic at once using Service selector."

---

### Q3: How do you handle secrets in CI/CD? How do you inject them into containers?

**Expected Answer Points**:
- Never commit secrets to Git
- Use secret management (Vault, AWS Secrets Manager)
- Inject via environment variables or mounted files
- Use External Secrets Operator in K8s
- Rotate secrets regularly
- Example: "I store secrets in Vault. CI/CD retrieves them and injects as environment variables or mounts as files. In Kubernetes, I use External Secrets Operator to sync from Vault to K8s Secrets. Secrets are never in code or Git. I rotate them every 90 days."

---

### Q4: How do you ensure code quality in your CI/CD pipeline?

**Expected Answer Points**:
- Automated tests (unit, integration, e2e)
- Linting (flake8, black, pylint)
- Code coverage requirements
- Security scanning (SAST, dependency scanning)
- Quality gates (must pass to merge)
- Example: "I run: 1) Unit tests (must pass), 2) Integration tests, 3) Linting (flake8, black), 4) Code coverage (must be >80%), 5) Security scan (Trivy for vulnerabilities), 6) Dependency scan (check for known vulnerabilities). All must pass before code can be merged or deployed."

---

### Q5: How do you handle rollbacks in your deployment pipeline?

**Expected Answer Points**:
- Keep previous image versions
- Quick rollback to previous deployment
- Database migration rollbacks
- Automated rollback on health check failure
- Manual rollback process
- Example: "I keep previous container images tagged with versions. If deployment fails health checks, I automatically rollback to previous version. For database, I have backward migrations. I can rollback in seconds using `kubectl rollout undo`. I also have a manual rollback process documented."

---

## 9. Containerization (Dockerfile) (5 Questions)

### Q1: Explain multi-stage Docker builds. Why are they important?

**Expected Answer Points**:
- Build stage: Install dependencies, compile
- Runtime stage: Copy only what's needed
- Smaller final image
- Better security (fewer packages)
- Faster deployments
- Example: "Multi-stage builds use one stage to build (with compilers, build tools) and another for runtime (minimal). I copy only the compiled artifacts to runtime stage. This reduces image size from 1GB to 200MB, improves security (fewer packages), and speeds up deployments."

---

### Q2: What are Docker best practices for production images?

**Expected Answer Points**:
- Use specific tags (not `latest`)
- Non-root user
- Minimal base images (Alpine)
- Layer caching optimization
- Health checks
- .dockerignore
- Example: "I use specific tags (python:3.11-slim), run as non-root user, use minimal base images (Alpine), optimize layer order for caching, add HEALTHCHECK, use .dockerignore to exclude unnecessary files. I also scan images for vulnerabilities."

---

### Q3: How do you handle secrets in Docker images?

**Expected Answer Points**:
- Never put secrets in images
- Use environment variables at runtime
- Use secrets management (Vault, K8s Secrets)
- Don't commit secrets to Git
- Example: "I never put secrets in Docker images or Dockerfiles. I inject them at runtime via environment variables or mounted files from Kubernetes Secrets or Vault. Secrets are never in the image layers, so they're not exposed if the image is inspected."

---

### Q4: How do you optimize Docker image size?

**Expected Answer Points**:
- Multi-stage builds
- Minimal base images
- Remove build dependencies
- Combine RUN commands
- Use .dockerignore
- Example: "I use multi-stage builds, Alpine base images, remove build tools in final stage, combine RUN commands to reduce layers, use .dockerignore to exclude files. I also use distroless images for even smaller size. This reduces image from 500MB to 50MB."

---

### Q5: How do you handle application signals (SIGTERM) in containers?

**Expected Answer Points**:
- Handle SIGTERM for graceful shutdown
- Finish in-flight requests
- Close connections properly
- Set appropriate timeout
- Example: "I handle SIGTERM signal in my app. When received, I stop accepting new requests, finish in-flight requests, close database connections, then exit. Kubernetes sends SIGTERM, waits 30 seconds (terminationGracePeriodSeconds), then sends SIGKILL. My app completes within this time."

---

## 10. Infrastructure as Code (5 Questions)

### Q1: Explain Infrastructure as Code (IaC). What tools would you use?

**Expected Answer Points**:
- Define infrastructure in code (version controlled)
- Tools: Terraform, CloudFormation, Pulumi, Ansible
- Benefits: Reproducible, testable, versioned
- Example: "IaC defines infrastructure (servers, networks, databases) in code files. I use Terraform for cloud resources (AWS, GCP, Azure) and Ansible for configuration. Infrastructure is version controlled, reproducible, and testable. Changes go through code review."

---

### Q2: How do you manage Terraform state? What are the best practices?

**Expected Answer Points**:
- Remote state (S3, GCS, Azure Storage)
- State locking (DynamoDB)
- Don't commit state to Git
- Use workspaces for environments
- Example: "I store Terraform state in S3 with versioning enabled. I use DynamoDB for state locking (prevents concurrent modifications). I never commit state to Git (contains secrets). I use workspaces for different environments (dev, staging, prod). I backup state regularly."

---

### Q3: How do you handle secrets in Terraform?

**Expected Answer Points**:
- Use variables (not hardcoded)
- Use secret management (Vault, AWS Secrets Manager)
- Use data sources to fetch secrets
- Never commit secrets to Git
- Example: "I use Terraform variables for secrets, passed via environment variables or .tfvars files (not committed). I use Vault provider to fetch secrets dynamically. I use data sources to read from AWS Secrets Manager. Secrets are never in code or state files."

---

### Q4: How do you test Infrastructure as Code?

**Expected Answer Points**:
- Terraform validate, plan, apply
- Test in dev/staging first
- Use terraform-compliance for policy testing
- Manual testing after apply
- Example: "I run `terraform validate` to check syntax, `terraform plan` to preview changes, apply to dev first, then staging, then prod. I use terraform-compliance to test policies (e.g., all resources must have tags). I manually verify resources after creation."

---

### Q5: How do you handle infrastructure changes and rollbacks?

**Expected Answer Points**:
- Version control all changes
- Review changes before apply
- Test in non-prod first
- Keep previous versions
- Rollback by reverting code
- Example: "All infrastructure changes are in Git. I review changes in PR, test in dev, then staging, then prod. If something breaks, I revert the commit and apply again. I keep previous Terraform versions. For critical changes, I have a rollback plan documented."

---

## 11. Monitoring Stack (5 Questions)

### Q1: Explain the Prometheus monitoring architecture. How does it work?

**Expected Answer Points**:
- Prometheus scrapes metrics from targets
- Pull model (Prometheus pulls, not push)
- Time-series database
- PromQL for querying
- AlertManager for alerts
- Example: "Prometheus scrapes metrics from targets (HTTP /metrics endpoint) at regular intervals. It stores time-series data. I query with PromQL. AlertManager evaluates alert rules and sends notifications. I use ServiceMonitor CRDs in Kubernetes to automatically discover targets."

---

### Q2: How do you create effective Grafana dashboards?

**Expected Answer Points**:
- Key metrics: request rate, latency, error rate, saturation
- Use appropriate visualizations (graphs, gauges, tables)
- Set meaningful thresholds
- Organize by service/team
- Example: "I create dashboards with: request rate (graph), latency (histogram), error rate (gauge with thresholds), resource usage (CPU, memory). I organize by service. I set thresholds (e.g., error rate > 1% = red). I use variables for filtering by environment/tenant."

---

### Q3: How do you write good Prometheus alert rules?

**Expected Answer Points**:
- Alert on symptoms, not causes
- Use meaningful thresholds
- Include runbook links
- Avoid alert fatigue
- Example: "I alert on: high error rate (>1%), high latency (p99 > 1s), service down, high resource usage. I use meaningful thresholds based on SLOs. I include runbook links in alerts. I avoid alerting on every small issue to prevent fatigue. I use alert grouping and inhibition."

---

### Q4: How do you monitor Kubernetes clusters?

**Expected Answer Points**:
- Node metrics (CPU, memory, disk)
- Pod metrics (CPU, memory, network)
- Cluster metrics (API server, etcd)
- Use node-exporter, kube-state-metrics
- Example: "I use node-exporter for node metrics, kube-state-metrics for pod/namespace metrics, and Prometheus Operator to scrape them. I monitor: node CPU/memory, pod resource usage, API server latency, etcd performance. I alert on node failures, resource exhaustion."

---

### Q5: How do you handle high-cardinality metrics in Prometheus?

**Expected Answer Points**:
- High cardinality = too many unique label combinations
- Limit labels (don't use user_id, request_id)
- Use recording rules to aggregate
- Consider other systems (InfluxDB, TimescaleDB) for high cardinality
- Example: "High cardinality (e.g., per-user metrics) causes performance issues. I limit labels - don't use user_id, request_id. I aggregate with recording rules (e.g., sum by service). For high-cardinality data, I use other systems or sample metrics. I monitor Prometheus cardinality."

---

## 12. Logging Stack (5 Questions)

### Q1: Explain the ELK (Elasticsearch, Logstash, Kibana) stack. How does it work?

**Expected Answer Points**:
- Logstash: Collects, parses, transforms logs
- Elasticsearch: Stores and indexes logs
- Kibana: Visualizes and searches logs
- Alternative: Loki (simpler, for Kubernetes)
- Example: "ELK stack: Logstash collects logs from files/containers, parses them (JSON, structured), and sends to Elasticsearch. Elasticsearch indexes and stores logs. Kibana provides UI for searching and visualizing. For Kubernetes, I prefer Loki (simpler, designed for K8s)."

---

### Q2: How do you ship logs from Kubernetes pods to a logging system?

**Expected Answer Points**:
- Sidecar containers (Fluentd/Fluent Bit)
- DaemonSet (one per node)
- Log aggregation at node level
- Use structured logging (JSON)
- Example: "I use Fluent Bit as DaemonSet (one per node). It reads logs from /var/log/containers, parses them, adds metadata (pod name, namespace), and sends to Loki/Elasticsearch. I use structured logging (JSON) in my app for easier parsing. I configure log retention policies."

---

### Q3: How do you handle log retention and storage costs?

**Expected Answer Points**:
- Set retention policies (e.g., 30 days)
- Archive old logs to cold storage (S3)
- Compress logs
- Sample high-volume logs
- Example: "I set retention: 7 days hot storage, 30 days warm, 1 year cold (S3). I compress logs. For very high volume, I sample (e.g., 10% of debug logs). I use log aggregation to reduce storage. I monitor storage costs and adjust retention based on needs."

---

### Q4: How do you search and analyze logs effectively?

**Expected Answer Points**:
- Use structured logging (JSON)
- Index important fields
- Use log aggregation tools (Kibana, Grafana)
- Create dashboards for common queries
- Example: "I use structured JSON logging with fields: timestamp, level, service, tenant, request_id. I index these fields in Elasticsearch. I create Kibana dashboards for common queries (errors by service, slow requests). I use request_id to trace requests across services."

---

### Q5: How do you handle sensitive data in logs?

**Expected Answer Points**:
- Don't log passwords, tokens, PII
- Mask sensitive fields
- Use log sanitization
- Comply with regulations (GDPR)
- Example: "I never log passwords, tokens, credit cards, or PII. I mask sensitive fields (e.g., show only last 4 digits of credit card). I use log sanitization libraries. I comply with GDPR - users can request log deletion. I audit what we log."

---

## 13. Service Mesh (5 Questions)

### Q1: What is a service mesh? Why would you use one?

**Expected Answer Points**:
- Infrastructure layer for service-to-service communication
- Handles: load balancing, retries, circuit breaking, mTLS
- Offloads cross-cutting concerns from apps
- Example: "Service mesh (Istio, Linkerd) is infrastructure that handles service communication. It provides: load balancing, retries, circuit breaking, mTLS, observability. Apps don't need to implement these - the mesh handles it. I use it for microservices with many services."

---

### Q2: Explain how Istio works. What are the main components?

**Expected Answer Points**:
- Control plane: Pilot (routing), Citadel (security), Galley (config)
- Data plane: Envoy proxies (sidecars)
- Traffic management, security, observability
- Example: "Istio has control plane (manages config) and data plane (Envoy sidecars in each pod). Pilot manages routing rules. Citadel handles mTLS. Envoy proxies intercept traffic and apply policies. I configure traffic splitting, retries, circuit breaking via Istio configs."

---

### Q3: How does mTLS (mutual TLS) work in a service mesh?

**Expected Answer Points**:
- Both client and server authenticate
- Service mesh automatically manages certificates
- Encrypts all service-to-service traffic
- No code changes needed
- Example: "mTLS means both sides authenticate with certificates. Istio automatically generates and rotates certificates. All service-to-service traffic is encrypted. Apps don't need to change - the sidecar handles it. I enable mTLS with a policy: `peerAuthentication: mode: STRICT`."

---

### Q4: How do you implement canary deployments with a service mesh?

**Expected Answer Points**:
- Use VirtualService to split traffic
- Route X% to new version, Y% to old
- Gradually increase percentage
- Monitor metrics
- Example: "I use Istio VirtualService to split traffic: 10% to new version (canary), 90% to old. I monitor error rate, latency. If good, increase to 50%, then 100%. I can rollback instantly by changing the split. No code changes needed - it's all config."

---

### Q5: What are the trade-offs of using a service mesh?

**Expected Answer Points**:
- Pros: Offloads concerns, consistent policies, observability
- Cons: Complexity, resource overhead (sidecars), learning curve
- Not needed for simple architectures
- Example: "Pros: consistent policies, automatic mTLS, great observability, no code changes. Cons: adds complexity, sidecars use resources (memory/CPU), learning curve. For simple apps with few services, it's overkill. For microservices with 10+ services, it's valuable."

---

## 14. Backup & Disaster Recovery (5 Questions)

### Q1: Explain your backup strategy for a Kubernetes application with databases.

**Expected Answer Points**:
- Database backups (automated, frequent)
- Application state backups
- Configuration backups (Git)
- Test restore procedures
- RTO/RPO definitions
- Example: "I backup PostgreSQL daily (full) and hourly (incremental). I use Velero for Kubernetes backups (PVCs, configs). I backup to S3 with versioning. RTO is 1 hour (time to restore), RPO is 1 hour (max data loss). I test restores monthly. I have runbooks for disaster recovery."

---

### Q2: How do you handle database backups in a production environment?

**Expected Answer Points**:
- Automated backups (cron jobs, K8s Jobs)
- Point-in-time recovery (WAL archiving)
- Backup to remote storage (S3, GCS)
- Encrypt backups
- Test restore regularly
- Example: "I use pg_dump for full backups (daily) and WAL archiving for point-in-time recovery. Backups go to S3 with encryption. I run backups as Kubernetes CronJobs. I test restore to a separate environment monthly. I monitor backup success/failure."

---

### Q3: What is RTO and RPO? How do you define them?

**Expected Answer Points**:
- RTO: Recovery Time Objective (how long to restore)
- RPO: Recovery Point Objective (max acceptable data loss)
- Define based on business requirements
- Example: "RTO is how long it takes to restore service (e.g., 1 hour). RPO is max data loss acceptable (e.g., 1 hour of data). I define these with business stakeholders. Critical systems: RTO 15min, RPO 5min. Less critical: RTO 4 hours, RPO 1 hour."

---

### Q4: How do you test disaster recovery procedures?

**Expected Answer Points**:
- Regular DR drills
- Test restore in isolated environment
- Document procedures
- Measure RTO/RPO
- Example: "I run DR drills quarterly. I restore from backup to a test environment, verify data integrity, measure restore time. I document procedures in runbooks. I measure actual RTO/RPO and compare to targets. I fix issues found during drills."

---

### Q5: How do you handle multi-region disaster recovery?

**Expected Answer Points**:
- Replicate data to multiple regions
- Active-passive or active-active
- DNS failover
- Regional backups
- Example: "I replicate databases to multiple regions. I use active-passive (one region active, others standby) or active-active (all regions serve traffic). I use DNS failover (Route53 health checks) to switch regions. I backup in each region. I test cross-region failover quarterly."

---

## 15. GitOps (5 Questions)

### Q1: What is GitOps? How does it differ from traditional CI/CD?

**Expected Answer Points**:
- Git as single source of truth
- Declarative infrastructure and apps
- Automated sync from Git to cluster
- ArgoCD, Flux are tools
- Example: "GitOps uses Git as source of truth. Infrastructure and app configs are in Git. Tools (ArgoCD, Flux) automatically sync Git to cluster. If cluster drifts from Git, it's automatically corrected. This is declarative and auditable - all changes are in Git commits."

---

### Q2: How does ArgoCD work? Explain the architecture.

**Expected Answer Points**:
- ArgoCD watches Git repositories
- Compares Git state with cluster state
- Automatically syncs if different
- Provides UI for visualization
- Example: "ArgoCD watches Git repos (monitors branches/tags). It compares desired state (Git) with actual state (cluster). If different, it syncs (applies changes). I configure apps in ArgoCD pointing to Git repos. ArgoCD shows sync status, health, and can rollback."

---

### Q3: How do you handle secrets in GitOps?

**Expected Answer Points**:
- Don't commit secrets to Git
- Use Sealed Secrets, External Secrets Operator
- Store secrets in Vault, sync to cluster
- Example: "I never commit secrets to Git. I use Sealed Secrets (encrypted secrets in Git, decrypted in cluster) or External Secrets Operator (syncs from Vault to K8s Secrets). Secrets are managed separately from app configs. I rotate secrets regularly."

---

### Q4: How do you implement blue-green deployments with GitOps?

**Expected Answer Points**:
- Use Argo Rollouts (not standard Deployments)
- Configure in Git (rollout manifest)
- ArgoCD syncs the rollout
- Example: "I use Argo Rollouts (CRD for advanced deployments). I define canary/blue-green strategy in Git. ArgoCD syncs it. Argo Rollouts handles traffic splitting, promotion, rollback. All config is in Git, so it's version controlled and auditable."

---

### Q5: What are the benefits and challenges of GitOps?

**Expected Answer Points**:
- Benefits: Auditable, reproducible, easy rollback, collaboration
- Challenges: Learning curve, Git as bottleneck, secret management
- Example: "Benefits: all changes auditable (Git history), reproducible, easy rollback (revert commit), team collaboration. Challenges: learning curve, Git can be bottleneck (many changes), secret management complexity. Overall, it's great for production environments."

---

## 16. Advanced Security (5 Questions)

### Q1: How do you implement network policies in Kubernetes?

**Expected Answer Points**:
- Network policies control pod-to-pod communication
- Define ingress/egress rules
- Default deny, allow specific traffic
- Example: "Network policies define which pods can talk to each other. I use default deny (no traffic allowed), then allow specific traffic. For example, only API pods can talk to database pods. I define ingress (who can talk to me) and egress (who I can talk to) rules."

---

### Q2: Explain Pod Security Standards. How do you enforce them?

**Expected Answer Points**:
- Pod Security Standards: privileged, baseline, restricted
- Enforce via admission controllers
- Prevent running as root, privileged containers
- Example: "Pod Security Standards define security levels. Restricted is most secure (no root, no privileged, read-only root filesystem). I enforce via Pod Security Admission (built-in) or OPA Gatekeeper. I set namespace labels to enforce standards. Violations are rejected."

---

### Q3: How do you implement secret rotation?

**Expected Answer Points**:
- Rotate secrets regularly (90 days)
- Use secret management (Vault)
- Update secrets in all places
- Zero-downtime rotation
- Example: "I rotate secrets every 90 days. I use Vault which supports automatic rotation. I update secrets in Vault, which syncs to Kubernetes Secrets via External Secrets Operator. I rotate database passwords, API keys, certificates. I do it during maintenance windows or use zero-downtime rotation."

---

### Q4: How do you scan container images for vulnerabilities?

**Expected Answer Points**:
- Scan in CI/CD pipeline
- Tools: Trivy, Snyk, Clair
- Block deployment if critical vulnerabilities
- Regularly update base images
- Example: "I scan images in CI/CD with Trivy. I block deployment if critical/high vulnerabilities found. I scan base images and application dependencies. I update base images regularly. I use distroless or minimal images to reduce attack surface. I monitor for new vulnerabilities."

---

### Q5: How do you implement image signing and verification?

**Expected Answer Points**:
- Sign images with Cosign
- Verify signatures before deployment
- Prevent tampering
- Use in admission controllers
- Example: "I sign container images with Cosign (part of Sigstore). Signatures are stored alongside images. I verify signatures in Kubernetes admission controller before allowing deployment. This prevents tampering - only signed images can be deployed. I integrate this into CI/CD pipeline."

---

## 17. Performance Testing (5 Questions)

### Q1: How do you perform load testing? What tools do you use?

**Expected Answer Points**:
- Tools: k6, Locust, JMeter, Gatling
- Test different scenarios (normal, peak, stress)
- Measure: throughput, latency, error rate
- Example: "I use k6 for load testing. I define scenarios: normal load (100 req/s), peak load (500 req/s), stress test (1000 req/s). I measure: requests per second, p50/p95/p99 latency, error rate. I run tests against staging environment. I identify bottlenecks and optimize."

---

### Q2: How do you identify performance bottlenecks?

**Expected Answer Points**:
- Use profiling tools
- Monitor metrics (CPU, memory, database queries)
- Use distributed tracing
- Load test and measure
- Example: "I use profiling (cProfile for Python), monitor metrics (Prometheus), use distributed tracing (Jaeger), and load test. I identify slow database queries, memory leaks, CPU bottlenecks. I optimize: add indexes, cache results, optimize algorithms. I measure before/after."

---

### Q3: How do you set performance targets (SLOs)?

**Expected Answer Points**:
- Define latency targets (p95 < 200ms)
- Define availability targets (99.9% uptime)
- Define error rate targets (<0.1%)
- Based on business requirements
- Example: "I set SLOs with stakeholders: p95 latency < 200ms, availability 99.9%, error rate < 0.1%. I monitor these with Prometheus and alert if violated. I track error budgets. I review SLOs quarterly and adjust based on business needs."

---

### Q4: How do you handle performance testing in CI/CD?

**Expected Answer Points**:
- Run performance tests in CI
- Compare against baselines
- Fail if performance degrades
- Use performance budgets
- Example: "I run performance tests in CI against staging. I compare metrics (latency, throughput) to baselines. If performance degrades >10%, CI fails. I use performance budgets (e.g., p95 latency must be < baseline + 10%). I track performance trends over time."

---

### Q5: How do you do capacity planning?

**Expected Answer Points**:
- Measure current usage
- Project growth
- Calculate resources needed
- Plan for peak load
- Example: "I measure current usage (requests/sec, CPU, memory). I project growth (e.g., 2x in 6 months). I calculate resources needed (e.g., if 100 req/s uses 2 CPUs, 500 req/s needs 10 CPUs). I plan for 2x peak load for safety margin. I review quarterly."

---

## 📝 How to Use This Document

1. **Study each topic** - Understand the concepts before memorizing answers
2. **Practice explaining** - Say answers out loud, not just read them
3. **Customize answers** - Use examples from your project
4. **Prepare follow-ups** - Interviewers may ask deeper questions
5. **Be honest** - If you don't know, say so and explain how you'd find out

## 💡 Interview Tips

- **Use STAR method**: Situation, Task, Action, Result
- **Give examples**: Reference your Traffic Manager project
- **Show depth**: Explain trade-offs, not just how
- **Be concise**: Answer in 2-3 minutes, then ask if they want more detail
- **Ask questions**: Show interest in their challenges

Good luck with your interviews! 🚀
