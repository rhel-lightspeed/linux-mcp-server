# OpenShift Deployment Guide

This guide provides instructions for deploying the Linux MCP Server on OpenShift with HTTP/SSE transport.

## Prerequisites

- OpenShift cluster access (4.x or later)
- `oc` CLI tool installed and configured
- Project/namespace: `rhel-mcp`
- SSH private key for accessing RHEL instances
- Container registry access (e.g., Quay.io)

## Architecture

### Connection Flow

```
┌──────────────┐      HTTPS       ┌─────────────────────────┐
│ MCP Client   ├─────────────────>│ OpenShift Route (TLS)   │
│ (Browser/CLI)│   (Streamable    └────────────┬────────────┘
└──────────────┘    HTTP/SSE)                  │
                                               │
                                               v
                          ┌────────────────────────────────────┐
                          │ Linux MCP Server Pod (OpenShift)   │
                          │                                    │
                          │ ┌──────────────────────────────┐  │
                          │ │ MCP Server Process           │  │
                          │ │ (Port 8000)                  │  │
                          │ └──────────────────────────────┘  │
                          │                                    │
                          │ ┌──────────────────────────────┐  │
                          │ │ Mounted Resources:           │  │
                          │ │ • ConfigMap -> hosts.yaml    │  │
                          │ │ • Secret -> SSH private keys │  │
                          │ │ • PVC -> /app/logs          │  │
                          │ └──────────────────────────────┘  │
                          └────────┬───────────────────────────┘
                                   │
                                   │ SSH Connection
                                   │ (Port 22)
                                   │
                    ┌──────────────┴─────────────────┐
                    │                                 │
                    v                                 v
         ┌──────────────────┐            ┌──────────────────┐
         │ RHEL Instance 1  │            │ RHEL Instance 2  │
         │ prod-web-01      │            │ prod-db-01       │
         │                  │            │                  │
         │ SSH Port 22      │            │ SSH Port 22      │
         └──────────────────┘            └──────────────────┘
```

### How SSH Connection Works in OpenShift

**1. SSH Keys Storage:**
- SSH private keys are stored as a Kubernetes **Secret** (`linux-mcp-ssh-keys`)
- Keys are mounted read-only into the pod at `/app/ssh-keys/`
- Multiple keys supported for different RHEL instances

**2. RHEL Hosts Configuration:**
- RHEL instance details stored in **ConfigMap** (`linux-mcp-config`)
- Mounted at `/app/config/hosts.yaml`
- Each host entry specifies:
  - Hostname/IP address
  - SSH username
  - Path to SSH key
  - Tags for organization

**3. Connection Process:**
```
MCP Client → OpenShift Route → MCP Server Pod
                                     ↓
                        Read hosts.yaml (ConfigMap)
                                     ↓
                        Load SSH key (Secret)
                                     ↓
                        Establish SSH connection
                                     ↓
                        Execute commands on RHEL
                                     ↓
                        Return results to client
```

### Deployment Components

The OpenShift deployment uses:
- **HTTP/SSE Transport**: Server-Sent Events for streaming MCP communication
- **ConfigMap**: Stores RHEL hosts configuration (hosts.yaml)
- **Secret**: Stores SSH private keys for authenticating to RHEL instances
- **PersistentVolume**: For log storage and persistence
- **Route**: HTTPS external access with TLS termination
- **ServiceAccount**: Limited permissions for pod security

## Quick Start

### 1. Build and Push Container Image

```bash
# Login to your container registry
podman login quay.io

# Build the container image
podman build -t quay.io/<your-org>/linux-mcp-server:latest .

# Push to registry
podman push quay.io/<your-org>/linux-mcp-server:latest
```

### 2. Create SSH Secret

Create a secret with your SSH private key(s):

```bash
# Single SSH key
oc create secret generic linux-mcp-ssh-keys \
  --from-file=id_ed25519=~/.ssh/id_ed25519 \
  --namespace=rhel-mcp

# Multiple SSH keys (for different hosts)
oc create secret generic linux-mcp-ssh-keys \
  --from-file=id_ed25519=~/.ssh/id_ed25519 \
  --from-file=prod-key=~/.ssh/prod_key \
  --from-file=dev-key=~/.ssh/dev_key \
  --namespace=rhel-mcp
```

**Important**: Ensure the key files have proper permissions (600) before creating the secret.

### 3. Configure RHEL Hosts

Edit the ConfigMap to add your RHEL instances:

```bash
oc edit configmap linux-mcp-config -n rhel-mcp
```

Update the `hosts.yaml` section with your RHEL instances:

```yaml
hosts:
  - name: "prod-rhel-01"
    host: "rhel-prod-01.example.com"
    username: "admin"
    description: "Production RHEL 9 server"
    ssh_key_path: "/app/ssh-keys/id_ed25519"
    tags:
      - production
      - rhel9
  
  - name: "dev-rhel-01"
    host: "192.168.1.100"
    username: "devuser"
    description: "Development RHEL 8 server"
    ssh_key_path: "/app/ssh-keys/dev-key"
    tags:
      - development
      - rhel8
```

### 4. Deploy to OpenShift

Deploy all resources:

```bash
# Apply all manifests
oc apply -f deploy/openshift/linux-mcp-server/serviceaccount.yaml
oc apply -f deploy/openshift/linux-mcp-server/secret.yaml  # Skip if created in step 2
oc apply -f deploy/openshift/linux-mcp-server/configmap.yaml
oc apply -f deploy/openshift/linux-mcp-server/pvc.yaml
oc apply -f deploy/openshift/linux-mcp-server/deployment.yaml
oc apply -f deploy/openshift/linux-mcp-server/service.yaml
oc apply -f deploy/openshift/linux-mcp-server/route.yaml
```

Or deploy all at once:

```bash
oc apply -f deploy/openshift/linux-mcp-server/
```

### 5. Verify Deployment

Check the deployment status:

```bash
# Check pod status
oc get pods -n rhel-mcp -l app=linux-mcp-server

# View logs
oc logs -f deployment/linux-mcp-server -n rhel-mcp

# Check route
oc get route linux-mcp-server -n rhel-mcp
```

### 6. Access the MCP Server

The server will be accessible at:
```
https://linux-mcp-server-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com
```

Test the health endpoint:
```bash
curl https://linux-mcp-server-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com/health
```

## Configuration

### Environment Variables

The deployment supports these environment variables (set in `deployment.yaml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `LINUX_MCP_TRANSPORT` | `sse` | Transport mode (sse/stdio) |
| `LINUX_MCP_HOST` | `0.0.0.0` | Bind address |
| `LINUX_MCP_PORT` | `8000` | HTTP port |
| `LINUX_MCP_CONFIG_FILE` | `/app/config/hosts.yaml` | Configuration file path |
| `LINUX_MCP_LOG_DIR` | `/app/logs` | Log directory |
| `LINUX_MCP_LOG_LEVEL` | `INFO` | Log level |

### Hosts Configuration Schema

The `hosts.yaml` configuration file supports:

```yaml
hosts:
  - name: string              # Unique identifier
    host: string              # Hostname or IP
    username: string          # SSH username
    description: string       # Optional description
    ssh_key_path: string      # Path to SSH key in container
    tags: []                  # Optional tags for grouping

ssh_config:
  default_key_path: string    # Default SSH key
  connection_timeout: int     # Timeout in seconds
  keep_alive: bool            # Enable keep-alive
  keep_alive_interval: int    # Keep-alive interval

allowed_log_paths:
  - string                    # Whitelisted log file paths

logging:
  level: string               # Log level
  retention_days: int         # Log retention
  directory: string           # Log directory
```

## Resource Requirements

Default resource limits (adjust in `deployment.yaml`):

```yaml
resources:
  limits:
    cpu: "1"
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi
```

## Storage

### Log Persistence

The deployment uses a PersistentVolumeClaim for logs:
- **Size**: 5Gi (adjustable in `pvc.yaml`)
- **Access Mode**: ReadWriteOnce
- **Mount Path**: `/app/logs`

To use ephemeral storage instead, modify `deployment.yaml`:

```yaml
- name: logs
  emptyDir: {}
```

## Security

### Security Context

The container runs with restricted security context:
- **Non-root user**: UID 1001
- **Read-only root filesystem**: Yes (except /tmp and /app/logs)
- **No privilege escalation**: Enforced
- **Capabilities dropped**: ALL

### SSH Key Management

SSH keys are stored in a Kubernetes Secret:
- Mounted read-only at `/app/ssh-keys/`
- File permissions: 0400
- Not logged or exposed

### Network Security

To restrict egress to specific RHEL hosts, create a NetworkPolicy:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: linux-mcp-server-egress
  namespace: rhel-mcp
spec:
  podSelector:
    matchLabels:
      app: linux-mcp-server
  policyTypes:
  - Egress
  egress:
  - to:
    - ipBlock:
        cidr: 192.168.1.0/24  # Your RHEL subnet
    ports:
    - protocol: TCP
      port: 22
```

## Monitoring and Health Checks

### Health Endpoints

The server exposes a health endpoint:
- **URL**: `/health`
- **Port**: 8000
- **Response**: HTTP 200 OK

### Probes Configuration

The deployment includes three types of probes:

1. **Liveness Probe**: Restarts container if unhealthy
2. **Readiness Probe**: Removes from service if not ready
3. **Startup Probe**: Allows time for initial startup

### Viewing Logs

```bash
# Follow logs
oc logs -f deployment/linux-mcp-server -n rhel-mcp

# View logs from specific pod
oc logs <pod-name> -n rhel-mcp

# View logs in JSON format
oc exec deployment/linux-mcp-server -n rhel-mcp -- cat /app/logs/server.json
```

## Troubleshooting

### Pod Not Starting

```bash
# Check pod status
oc describe pod -l app=linux-mcp-server -n rhel-mcp

# Check events
oc get events -n rhel-mcp --sort-by='.lastTimestamp'

# View logs
oc logs -l app=linux-mcp-server -n rhel-mcp --previous
```

### SSH Connection Failures

1. Verify SSH key is correctly mounted:
```bash
oc exec deployment/linux-mcp-server -n rhel-mcp -- ls -la /app/ssh-keys/
```

2. Test SSH connectivity from pod:
```bash
oc exec deployment/linux-mcp-server -n rhel-mcp -- ssh -i /app/ssh-keys/id_ed25519 user@host -o StrictHostKeyChecking=no whoami
```

3. Check configuration:
```bash
oc exec deployment/linux-mcp-server -n rhel-mcp -- cat /app/config/hosts.yaml
```

### Configuration Issues

View effective configuration:
```bash
oc get configmap linux-mcp-config -n rhel-mcp -o yaml
```

Update configuration:
```bash
oc edit configmap linux-mcp-config -n rhel-mcp
```

**Note**: Pod must be restarted after ConfigMap changes:
```bash
oc rollout restart deployment/linux-mcp-server -n rhel-mcp
```

### Health Check Failures

1. Check if port 8000 is accessible:
```bash
oc port-forward deployment/linux-mcp-server 8000:8000 -n rhel-mcp
curl http://localhost:8000/health
```

2. Check server logs for startup errors:
```bash
oc logs deployment/linux-mcp-server -n rhel-mcp | grep -i error
```

## Scaling

The current deployment uses a single replica. For high availability:

```bash
# Scale to multiple replicas
oc scale deployment/linux-mcp-server --replicas=2 -n rhel-mcp
```

**Note**: Ensure session affinity is configured in the Service (already set).

## Updating

### Update Configuration

```bash
# Edit ConfigMap
oc edit configmap linux-mcp-config -n rhel-mcp

# Restart deployment
oc rollout restart deployment/linux-mcp-server -n rhel-mcp
```

### Update Image

```bash
# Update image
oc set image deployment/linux-mcp-server mcp-server=quay.io/<org>/linux-mcp-server:v2.0.0 -n rhel-mcp

# Check rollout status
oc rollout status deployment/linux-mcp-server -n rhel-mcp
```

### Rollback

```bash
# View rollout history
oc rollout history deployment/linux-mcp-server -n rhel-mcp

# Rollback to previous version
oc rollout undo deployment/linux-mcp-server -n rhel-mcp
```

## Cleanup

To remove all resources:

```bash
# Delete all resources
oc delete -f deploy/openshift/linux-mcp-server/

# Or delete individually
oc delete deployment linux-mcp-server -n rhel-mcp
oc delete service linux-mcp-server -n rhel-mcp
oc delete route linux-mcp-server -n rhel-mcp
oc delete configmap linux-mcp-config -n rhel-mcp
oc delete secret linux-mcp-ssh-keys -n rhel-mcp
oc delete pvc linux-mcp-logs -n rhel-mcp
oc delete serviceaccount linux-mcp-server -n rhel-mcp
```

## Integration with MCP Clients

### Connecting via HTTP/SSE

The MCP server uses Server-Sent Events (SSE) for streaming communication. To connect from a client:

```typescript
// Example: Connecting to the MCP server
const client = new Client({
  transport: 'sse',
  url: 'https://linux-mcp-server-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com'
});

await client.connect();
```

### Available Tools

All 22 MCP tools are available via HTTP/SSE transport:
- System Information (5 tools)
- Service Management (3 tools)
- Process Management (2 tools)
- Logs & Audit (3 tools)
- Network Diagnostics (3 tools)
- Storage & Disk Analysis (6 tools)

Refer to [USAGE.md](../USAGE.md) for detailed tool documentation.

## Best Practices

1. **SSH Key Security**
   - Use separate SSH keys for different environments
   - Rotate keys regularly
   - Use Ed25519 keys (preferred over RSA)

2. **Configuration Management**
   - Store production configs in a separate repository
   - Use GitOps workflows (ArgoCD, Flux) for deployment
   - Document all RHEL instances in hosts.yaml

3. **Logging**
   - Enable JSON logging for centralized log aggregation
   - Forward logs to OpenShift logging stack or external SIEM
   - Set appropriate retention policies

4. **Monitoring**
   - Monitor pod resource usage
   - Set up alerts for health check failures
   - Track SSH connection failures

5. **Network Policies**
   - Implement egress restrictions to RHEL hosts only
   - Use network policies to limit pod-to-pod communication
   - Document all required network access

## Support

For issues or questions:
- GitHub Issues: https://github.com/rhel-lightspeed/linux-mcp-server/issues
- Documentation: [README.md](../README.md), [USAGE.md](../USAGE.md)

