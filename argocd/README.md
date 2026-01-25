## Argo CD + Helm Deployment

This folder contains Helm charts for each microservice and Argo CD `Application`
manifests to deploy them.

### Prerequisites
- Argo CD installed in your cluster.
- Docker images pushed to your Docker Hub account.
- A namespace for workloads (default: `traffic-manager`).

### Required edits before applying
1. Update `repoURL` in each file under `argocd/applications/` to point to your
   Git repository URL.
2. Update each chart's `values.yaml`:
   - `image.repository` should match your Docker Hub image name.
   - `secretEnv` should contain real secrets (DB passwords, Mongo creds, etc).

### Apply all Applications
If you use app-of-apps (recommended), create an Argo CD application that points
to `argocd/applications/` in this repo. The included `kustomization.yaml` lets
Argo CD or `kubectl apply -k` apply all child apps.

### Images expected by default
- `docker.io/REPLACE_ME/traffic-manager-route-resolution-service`
- `docker.io/REPLACE_ME/traffic-manager-route-management-service`
- `docker.io/REPLACE_ME/traffic-manager-cache-invalidation-consumer`
- `docker.io/REPLACE_ME/traffic-manager-cache-warming-consumer`
- `docker.io/REPLACE_ME/traffic-manager-audit-consumer`

### Notes
- The API services expose HTTP on ports 8001 and 8002 and include liveness and
  readiness probes at `/health`.
- The consumer services do not expose an HTTP service by default and have probes
  disabled by default.
