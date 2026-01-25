# GitHub Actions Workflows

This directory contains CI/CD workflows for all microservices in the Traffic Manager project.

## Services

1. **Route Resolution Service** (`route-resolution-service.yml`)
   - Handles read path operations (route resolution, audit queries)
   - Port: 8001

2. **Route Management Service** (`route-management-service.yml`)
   - Handles write path operations (create, activate, deactivate routes)
   - Port: 8002

3. **Cache Invalidation Consumer** (`cache-invalidation-consumer.yml`)
   - Consumes Kafka events and invalidates Redis cache

4. **Cache Warming Consumer** (`cache-warming-consumer.yml`)
   - Consumes Kafka events and pre-warms Redis cache

5. **Audit Consumer** (`audit-consumer.yml`)
   - Consumes Kafka events and stores audit logs in MongoDB

## Workflow Triggers

Each workflow triggers on:
- Push to `main` branch (if relevant files changed)
- Creation of version tags (e.g., `v1.0.0`, `v2.1.3`)
- Manual trigger via GitHub Actions UI

### Path-Based Triggers

Each workflow only runs when relevant files change:
- `src/**` - Shared code changes trigger all services
- `services/{service-name}/**` - Service-specific changes
- `requirements.txt` - Dependency changes trigger all services

## Required Secrets

Configure these secrets in GitHub repository settings:

1. **DOCKERHUB_USERNAME**: Your Docker Hub username
2. **DOCKERHUB_TOKEN**: Your Docker Hub access token
3. **DOCKERHUB_REPO**: Base repository name (e.g., `myusername/traffic-manager`)

### Image Naming

Images will be pushed as:
- `{DOCKERHUB_REPO}-route-resolution-service:latest`
- `{DOCKERHUB_REPO}-route-management-service:latest`
- `{DOCKERHUB_REPO}-cache-invalidation-consumer:latest`
- `{DOCKERHUB_REPO}-cache-warming-consumer:latest`
- `{DOCKERHUB_REPO}-audit-consumer:latest`

## Image Tags

Each service gets multiple tags:
- `latest` - Latest from main branch
- `v1.0.0` - Exact version
- `v1.0` - Major.minor
- `v1` - Major version

## Example

After pushing tag `v1.0.0`, you'll have:

```bash
docker pull myusername/traffic-manager-route-resolution-service:v1.0.0
docker pull myusername/traffic-manager-route-management-service:v1.0.0
docker pull myusername/traffic-manager-cache-invalidation-consumer:v1.0.0
docker pull myusername/traffic-manager-cache-warming-consumer:v1.0.0
docker pull myusername/traffic-manager-audit-consumer:v1.0.0
```

## Multi-Architecture Support

All images are built for:
- `linux/amd64` (Intel/AMD 64-bit)
- `linux/arm64` (ARM 64-bit, Apple Silicon)

## Caching

Each workflow uses Docker layer caching:
- Cache stored per service in Docker Hub
- Faster builds when dependencies haven't changed

## Manual Trigger

You can manually trigger any workflow:
1. Go to **Actions** tab
2. Select the workflow
3. Click **Run workflow**
4. Choose branch and click **Run workflow**
