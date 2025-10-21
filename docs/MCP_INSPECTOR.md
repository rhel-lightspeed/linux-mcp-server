# MCP Inspector on OpenShift

This guide shows how to deploy the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) to OpenShift alongside the Linux MCP Server for visual testing and debugging.

## What is MCP Inspector?

MCP Inspector is a visual testing tool for MCP servers that provides:
- 🔍 **Interactive UI** for testing MCP tools, resources, and prompts
- 📊 **Real-time visualization** of requests and responses
- 🐛 **Debugging tools** with request history and error details
- 🔗 **Multiple transports** supporting stdio, SSE, and streamable-HTTP

## Quick Start

### ⚡ Fastest Way to Get Started (OpenShift Route)

1. **Open**: https://mcp-inspector-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com
2. **Click Configuration** (⚙️ button)
3. **Set MCP_PROXY_FULL_ADDRESS** to: `https://mcp-inspector-proxy-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com`
4. **Save** and close configuration
5. **Configure Connection**:
   - Transport: `Streamable HTTP`
   - Connection Type: `Via Proxy`
   - URL: `http://linux-mcp-server:8000/mcp`
6. **Click Connect** ✅

That's it! You should now see 22 available tools.

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
oc apply -f deploy/openshift/linux-mcp-server/serviceaccount.yaml
oc create secret generic linux-mcp-ssh-keys \
  --from-file=id_rsa=~/.ssh/id_rsa \
  --namespace=rhel-mcp
oc apply -f deploy/openshift/linux-mcp-server/configmap.yaml
oc apply -f deploy/openshift/linux-mcp-server/pvc.yaml
oc apply -f deploy/openshift/linux-mcp-server/deployment.yaml
oc apply -f deploy/openshift/linux-mcp-server/service.yaml
oc apply -f deploy/openshift/linux-mcp-server/route.yaml

# Deploy MCP Inspector
oc apply -f deploy/openshift/inspector/

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

### Method 1: OpenShift Route (Recommended for Remote Access)

**Step 1:** Navigate to the Inspector UI:
```
https://mcp-inspector-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com
```

**Step 2:** Configure the Proxy Address (IMPORTANT!)

Click **"Configuration"** (⚙️ button in sidebar) and set:
- **MCP_PROXY_FULL_ADDRESS**: `https://mcp-inspector-proxy-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com`
- Click **"Save"**

**Step 3:** Connect to MCP Server

Configure connection settings:
- **Transport**: `Streamable HTTP`
- **Connection Type**: `Via Proxy`
- **URL**: `http://linux-mcp-server:8000/mcp`
- Click **"Connect"**

⚠️ **Important**: Use the **internal Kubernetes service name** (`linux-mcp-server`) not the external route. The proxy runs inside the cluster and connects to the MCP server using internal networking.

### Method 2: Port-Forward (For Local Development)

Use port-forwarding when you need direct pod access or for debugging:

```bash
# Terminal 1: Forward Inspector (UI + Proxy)
oc port-forward -n rhel-mcp deployment/mcp-inspector 6274:6274 6277:6277

# Terminal 2: Forward MCP Server (optional, proxy uses internal service)
oc port-forward -n rhel-mcp deployment/linux-mcp-server 8000:8000
```

Then open `http://localhost:6274` in your browser and configure:
- **Transport**: `Streamable HTTP`
- **Connection Type**: `Via Proxy`
- **URL**: `http://linux-mcp-server:8000/mcp` (uses internal service)
- Click **"Connect"**

**Note**: The proxy always connects to `linux-mcp-server:8000` using the Kubernetes service DNS, regardless of port-forwarding.

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

### Inspector UI Loads But Can't Connect to Proxy

**Symptom**: Inspector UI loads but shows "Couldn't connect to MCP Proxy Server" or `:6277/health` timeout errors

**Root Cause**: The Inspector UI is trying to connect to `localhost:6277` instead of the OpenShift proxy route.

**Solution**: Configure the proxy address in the UI

1. **Open Configuration**: Click the **"Configuration"** button (⚙️) in the Inspector sidebar

2. **Set Proxy Address**: Find **"MCP_PROXY_FULL_ADDRESS"** and enter:
   ```
   https://mcp-inspector-proxy-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com
   ```

3. **Save**: Click "Save" to apply the configuration

4. **Try connecting again** with:
   - Transport: `Streamable HTTP`
   - Connection Type: `Via Proxy`
   - URL: `http://linux-mcp-server:8000/mcp`

**Additional Checks**:

1. **Missing Proxy Route**: Ensure the proxy route is deployed
```bash
oc get route mcp-inspector-proxy -n rhel-mcp
# If not found, apply it:
oc apply -f deploy/openshift/inspector/proxy-route.yaml
```

2. **Verify Environment Variables**: Check the deployment has correct var names
```bash
oc get deployment mcp-inspector -n rhel-mcp -o yaml | grep -A 20 "env:"
# Should see CLIENT_PORT, SERVER_PORT, and MCP_PROXY_FULL_ADDRESS
```

3. **Check ALLOWED_ORIGINS**: Verify DNS rebinding protection is configured
```bash
oc get deployment mcp-inspector -n rhel-mcp -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="ALLOWED_ORIGINS")].value}'
# Should show OpenShift URLs and localhost URLs
```

### Inspector Can't Connect to MCP Server

**Check 1: Verify All Routes**
```bash
oc get routes -n rhel-mcp
# Should see: mcp-inspector, mcp-inspector-proxy, and linux-mcp-server
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

### Connection Shows "Missing session ID" Error

**Symptom**: Error message shows `Bad Request: Missing session ID`

**Root Cause**: Using "Direct" connection mode, which doesn't work properly with Streamable HTTP through OpenShift routes.

**Solution**: Use "Via Proxy" connection mode:
1. Change **Connection Type** to: `Via Proxy`
2. Ensure **MCP_PROXY_FULL_ADDRESS** is configured (see above)
3. Use internal service URL: `http://linux-mcp-server:8000/mcp`

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

## Architecture: How the Inspector Works

Understanding the architecture helps troubleshoot connection issues:

```
┌─────────────────────────────────────────────────────────┐
│ Your Browser                                            │
│ https://mcp-inspector-rhel-mcp.apps... OR localhost     │
└────────────────┬────────────────────────────────────────┘
                 │ HTTPS/HTTP
┌────────────────▼────────────────────────────────────────┐
│ Inspector UI (Port 6274)                                │
│ - Serves web interface                                  │
│ - Runs in OpenShift pod                                 │
└────────────────┬────────────────────────────────────────┘
                 │ Connects to proxy at 6277
┌────────────────▼────────────────────────────────────────┐
│ Inspector Proxy (Port 6277)                             │
│ - Also runs in same OpenShift pod                       │
│ - Bridges browser ↔ MCP Server                         │
└────────────────┬────────────────────────────────────────┘
                 │ Internal Kubernetes network
                 │ http://linux-mcp-server:8000/mcp
┌────────────────▼────────────────────────────────────────┐
│ Linux MCP Server (Port 8000)                            │
│ - Streamable HTTP transport                             │
│ - Connects to RHEL instances via SSH                    │
└─────────────────────────────────────────────────────────┘
```

**Key Points**:
- The **proxy runs inside the OpenShift pod**, not in your browser
- The proxy uses **internal Kubernetes service DNS** to reach the MCP server
- Always use `http://linux-mcp-server:8000/mcp` (not external routes) when configuring the connection
- For OpenShift route access, configure `MCP_PROXY_FULL_ADDRESS` to point to the proxy route

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

