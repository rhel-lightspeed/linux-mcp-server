# MCP Inspector on OpenShift

This guide shows how to deploy the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) to OpenShift alongside the Linux MCP Server for visual testing and debugging.

## What is MCP Inspector?

MCP Inspector is a visual testing tool for MCP servers that provides:
- 🔍 **Interactive UI** for testing MCP tools, resources, and prompts
- 📊 **Real-time visualization** of requests and responses
- 🐛 **Debugging tools** with request history and error details
- 🔗 **Multiple transports** supporting stdio, SSE, and streamable-HTTP

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ Browser                                             │
│ https://mcp-inspector-rhel-mcp.apps...             │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│ MCP Inspector Pod                                   │
│ - UI: Port 6274                                     │
│ - WebSocket: Port 6277                              │
└────────────────┬────────────────────────────────────┘
                 │ (connects to)
┌────────────────▼────────────────────────────────────┐
│ Linux MCP Server                                    │
│ https://linux-mcp-server-rhel-mcp.apps...          │
│ - Streamable-HTTP: /mcp                            │
└────────────────┬────────────────────────────────────┘
                 │ (SSH to)
┌────────────────▼────────────────────────────────────┐
│ RHEL Instances                                      │
│ - bastion.example.com                               │
│ - prod-rhel-01.example.com                          │
└─────────────────────────────────────────────────────┘
```

## Deployment

### Quick Deploy

Deploy both Inspector and Linux MCP Server:

```bash
# Deploy Linux MCP Server (if not already deployed)
oc apply -f openshift/serviceaccount.yaml
oc create secret generic linux-mcp-ssh-keys \
  --from-file=id_rsa=~/.ssh/id_rsa \
  --namespace=rhel-mcp
oc apply -f openshift/configmap.yaml
oc apply -f openshift/pvc.yaml
oc apply -f openshift/deployment.yaml
oc apply -f openshift/service.yaml
oc apply -f openshift/route.yaml

# Deploy MCP Inspector
oc apply -f openshift/inspector-deployment.yaml
oc apply -f openshift/inspector-service.yaml
oc apply -f openshift/inspector-route.yaml

# Wait for deployments
oc rollout status deployment/linux-mcp-server -n rhel-mcp
oc rollout status deployment/mcp-inspector -n rhel-mcp
```

### Get URLs

```bash
# Get Inspector URL
INSPECTOR_URL=$(oc get route mcp-inspector -n rhel-mcp -o jsonpath='{.spec.host}')
echo "🔍 Inspector: https://$INSPECTOR_URL"

# Get MCP Server URL
MCP_SERVER_URL=$(oc get route linux-mcp-server -n rhel-mcp -o jsonpath='{.spec.host}')
echo "🖥️  MCP Server: https://$MCP_SERVER_URL"
```

## Using MCP Inspector

### Method 1: Port-Forward (Recommended)

The Inspector's WebSocket proxy works best with local port-forwarding:

```bash
# Terminal 1: Forward MCP Server
oc port-forward -n rhel-mcp deployment/linux-mcp-server 8000:8000

# Terminal 2: Forward Inspector
oc port-forward -n rhel-mcp deployment/mcp-inspector 6274:6274 6277:6277
```

Then open `http://localhost:6274` in your browser and configure:
- **Transport**: Streamable HTTP
- **Connection Type**: Via Proxy
- **URL**: `http://localhost:8000/mcp`
- Click **"Connect"**

### Method 2: Direct OpenShift Route (Limited)

Navigate to: `https://mcp-inspector-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com`

**Note**: WebSocket proxy connections may have limitations through OpenShift routes. Use port-forward method for full functionality.

### Method 3: CLI Mode (Scriptable)

Use the Inspector CLI for programmatic testing:

```bash
# Install Inspector CLI
npm install -g @modelcontextprotocol/inspector

# Get route URL
MCP_URL=$(oc get route linux-mcp-server -n rhel-mcp -o jsonpath='{.spec.host}')

# List tools
npx @modelcontextprotocol/inspector --cli https://$MCP_URL \
  --transport http \
  --method tools/list

# Call a tool
npx @modelcontextprotocol/inspector --cli https://$MCP_URL \
  --transport http \
  --method tools/call \
  --tool-name get_system_info \
  --tool-arg host=your-rhel-host.example.com \
  --tool-arg username=admin
```

### Step 3: Test Tools

Once connected, you can test all 22 diagnostic tools:

**Example 1: Get System Info**

1. Navigate to the **"Tools"** tab
2. Select **"get_system_info"** from the list
3. Fill in parameters:
   - `host`: `bastion.example.com` (or your RHEL instance)
   - `username`: `student`
4. Click **"Call Tool"**
5. View the response with system information

**Example 2: List Services**

1. Select **"list_services"** 
2. Enter host and username
3. Click **"Call Tool"**
4. Browse the list of systemd services with their status

**Example 3: Get Process Info**

1. Select **"list_processes"**
2. Enter host and username
3. Optionally filter by process name
4. View running processes with CPU and memory usage

### Step 4: Explore Features

**Request History**
- View all past requests and responses
- Copy request JSON for debugging
- Retry failed requests

**Resource Browser**
- Navigate the server's resource hierarchy
- View resource metadata
- Read resource contents

**Prompt Testing**
- Test prompt templates
- View streaming responses
- Compare different prompts

## Testing Multiple RHEL Instances

Configure multiple hosts in the MCP Server's ConfigMap and test each one:

```bash
# Edit ConfigMap to add hosts
oc edit configmap linux-mcp-config -n rhel-mcp

# Add multiple hosts:
hosts:
  - name: "prod-web"
    host: "prod-web.example.com"
    username: "webadmin"
  - name: "prod-db"
    host: "prod-db.example.com"
    username: "dbadmin"
  - name: "dev-server"
    host: "dev.example.com"
    username: "developer"

# Restart MCP Server
oc rollout restart deployment/linux-mcp-server -n rhel-mcp

# In Inspector, test each host by changing the 'host' parameter
```

## Troubleshooting

### Inspector Can't Connect to MCP Server

**Check 1: Verify Routes**
```bash
oc get routes -n rhel-mcp
# Both mcp-inspector and linux-mcp-server should be listed
```

**Check 2: Test MCP Server Directly**
```bash
MCP_URL=$(oc get route linux-mcp-server -n rhel-mcp -o jsonpath='{.spec.host}')
curl -X POST "https://$MCP_URL/mcp" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}, "id": 1}'
```

**Check 3: View Logs**
```bash
# Inspector logs
oc logs -f deployment/mcp-inspector -n rhel-mcp

# MCP Server logs
oc logs -f deployment/linux-mcp-server -n rhel-mcp
```

### WebSocket Connection Issues

If you see WebSocket errors:
1. Check that port 6277 is accessible
2. Verify HAProxy sticky session annotations on the route
3. Check browser console for CORS errors

```bash
# Verify service ports
oc get svc mcp-inspector -n rhel-mcp -o yaml | grep -A 5 ports
```

### Tool Calls Failing

**Symptom**: Tools connect but calls fail

**Solution**: Check MCP Server logs for SSH authentication errors
```bash
oc logs deployment/linux-mcp-server -n rhel-mcp | grep -i "auth\|ssh"
```

Common issues:
- SSH key not mounted correctly
- Wrong username for RHEL host
- Network connectivity to RHEL instance

## Advanced: Using Inspector CLI

You can also use the Inspector in CLI mode to test programmatically:

```bash
# Install Inspector CLI
npm install -g @modelcontextprotocol/inspector

# Test from command line
MCP_URL=$(oc get route linux-mcp-server -n rhel-mcp -o jsonpath='{.spec.host}')

# List available tools
npx @modelcontextprotocol/inspector --cli https://$MCP_URL \
  --transport http \
  --method tools/list

# Call a tool
npx @modelcontextprotocol/inspector --cli https://$MCP_URL \
  --transport http \
  --method tools/call \
  --tool-name get_system_info \
  --tool-arg host=bastion.example.com \
  --tool-arg username=student
```

## Monitoring

**Check Deployment Status:**
```bash
oc get pods -n rhel-mcp -l app=mcp-inspector
oc get pods -n rhel-mcp -l app=linux-mcp-server
```

**Resource Usage:**
```bash
oc adm top pod -n rhel-mcp
```

## Cleanup

To remove the Inspector (keep MCP Server):
```bash
oc delete -f openshift/inspector-route.yaml
oc delete -f openshift/inspector-service.yaml
oc delete -f openshift/inspector-deployment.yaml
```

To remove everything:
```bash
oc delete project rhel-mcp
```

## References

- [MCP Inspector GitHub](https://github.com/modelcontextprotocol/inspector)
- [MCP Protocol Documentation](https://modelcontextprotocol.io)
- [Linux MCP Server Repository](https://github.com/rrbanda/linux-mcp-server)

