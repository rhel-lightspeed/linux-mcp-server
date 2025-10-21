# Deployment Configurations

This directory contains deployment configurations for various platforms.

## Directory Structure

```
deploy/
└── openshift/
    ├── linux-mcp-server/    # Linux MCP Server deployment
    │   ├── serviceaccount.yaml
    │   ├── secret.yaml
    │   ├── configmap.yaml
    │   ├── pvc.yaml
    │   ├── deployment.yaml
    │   ├── service.yaml
    │   └── route.yaml
    └── inspector/            # MCP Inspector deployment
        ├── deployment.yaml
        ├── service.yaml
        ├── route.yaml
        └── proxy-route.yaml
```

## OpenShift Deployment

### Linux MCP Server

Deploy the Linux MCP Server to OpenShift:

```bash
# Deploy all resources
oc apply -f deploy/openshift/linux-mcp-server/

# Or use the deployment script
./deploy/openshift/deploy.sh
```

For detailed instructions, see [docs/OPENSHIFT.md](../docs/OPENSHIFT.md).

### MCP Inspector

Deploy the MCP Inspector for visual testing and debugging:

```bash
# Deploy inspector
oc apply -f deploy/openshift/inspector/

# Get the Inspector URL
oc get route mcp-inspector -n rhel-mcp -o jsonpath='{.spec.host}'
```

For detailed instructions, see [docs/MCP_INSPECTOR.md](../docs/MCP_INSPECTOR.md).

## Quick Start

1. **Prerequisites**:
   - OpenShift cluster access
   - `oc` CLI installed and logged in
   - SSH keys for accessing RHEL instances

2. **Deploy both services**:
   ```bash
   # Create namespace
   oc create namespace rhel-mcp
   
   # Create SSH secret
   oc create secret generic linux-mcp-ssh-keys \
     --from-file=id_rsa=~/.ssh/id_rsa \
     --namespace=rhel-mcp
   
   # Deploy MCP Server
   oc apply -f deploy/openshift/linux-mcp-server/
   
   # Deploy Inspector
   oc apply -f deploy/openshift/inspector/
   
   # Get URLs
   echo "MCP Server: https://$(oc get route linux-mcp-server -n rhel-mcp -o jsonpath='{.spec.host}')"
   echo "Inspector: https://$(oc get route mcp-inspector -n rhel-mcp -o jsonpath='{.spec.host}')"
   ```

3. **Verify deployment**:
   ```bash
   oc get pods -n rhel-mcp
   oc logs -f deployment/linux-mcp-server -n rhel-mcp
   ```

## Configuration

- **Linux MCP Server**: Edit `deploy/openshift/linux-mcp-server/configmap.yaml` to configure RHEL hosts
- **Inspector**: Configuration is done through the UI after deployment

## Cleanup

```bash
# Remove all resources
oc delete -f deploy/openshift/linux-mcp-server/
oc delete -f deploy/openshift/inspector/

# Or delete the entire namespace
oc delete namespace rhel-mcp
```

