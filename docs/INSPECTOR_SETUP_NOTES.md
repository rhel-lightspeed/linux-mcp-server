# MCP Inspector Setup - Technical Notes

## Problem Summary

The MCP Inspector was not working when accessed through OpenShift routes. After extensive troubleshooting, we identified and fixed several configuration issues.

## Root Causes Identified

### 1. **Incorrect Environment Variable Names**
- **Problem**: Deployment used `PORT` and `PROXY_PORT`
- **Fix**: Changed to `CLIENT_PORT` and `SERVER_PORT` (correct MCP Inspector variable names)

### 2. **Missing ALLOWED_ORIGINS Configuration**
- **Problem**: DNS rebinding protection blocked connections from OpenShift routes and localhost
- **Fix**: Added both OpenShift URLs and localhost URLs to `ALLOWED_ORIGINS`:
  ```
  https://mcp-inspector-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com,
  https://mcp-inspector-proxy-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com,
  http://localhost:6274,
  http://127.0.0.1:6274
  ```

### 3. **Missing MCP_PROXY_FULL_ADDRESS Configuration**
- **Problem**: When accessing through OpenShift route, the Inspector UI tried to connect to `localhost:6277` instead of the proxy route
- **Fix**: Users must configure `MCP_PROXY_FULL_ADDRESS` in the Inspector UI Configuration settings
- **Value**: `https://mcp-inspector-proxy-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com`

### 4. **Incorrect Connection URL**
- **Problem**: Users tried using external OpenShift route URL or `localhost:8000`
- **Fix**: Must use **internal Kubernetes service name**: `http://linux-mcp-server:8000/mcp`
- **Why**: The proxy runs inside the OpenShift pod and uses internal cluster networking

### 5. **Wrong Connection Mode**
- **Problem**: "Direct" connection mode doesn't work with Streamable HTTP through routes (session ID errors)
- **Fix**: Always use "Via Proxy" connection mode

## Architecture Understanding

```
Browser
  ↓ (HTTPS through OpenShift route)
Inspector UI Pod (Port 6274)
  ↓ (connects to port 6277 on same pod)
Inspector Proxy (Port 6277)
  ↓ (uses Kubernetes internal DNS)
MCP Server Service (http://linux-mcp-server:8000)
  ↓
MCP Server Pod
```

**Key Insight**: The proxy runs **inside the cluster**, not in the user's browser. Therefore:
- It cannot reach `localhost:8000` on the user's machine
- It must use Kubernetes service DNS (`linux-mcp-server`)
- For OpenShift route access, the browser must know the proxy's external URL

## Working Configuration

### For OpenShift Route Access:

**Inspector UI Configuration** (⚙️ Configuration button):
```
MCP_PROXY_FULL_ADDRESS: https://mcp-inspector-proxy-rhel-mcp.apps.prod.rhoai.rh-aiservices-bu.com
```

**Connection Settings**:
```
Transport Type: Streamable HTTP
Connection Type: Via Proxy
URL: http://linux-mcp-server:8000/mcp
```

### For Port-Forward Access:

**Connection Settings**:
```
Transport Type: Streamable HTTP
Connection Type: Via Proxy
URL: http://linux-mcp-server:8000/mcp
```

Note: Even with port-forwarding, use the internal service name because the proxy uses internal networking.

## Files Modified

1. **deploy/openshift/inspector/deployment.yaml**
   - Fixed environment variable names (CLIENT_PORT, SERVER_PORT)
   - Added ALLOWED_ORIGINS with all required URLs
   - Added MCP_AUTO_OPEN_ENABLED=false

2. **deploy/openshift/inspector/proxy-route.yaml**
   - Added WebSocket-specific HAProxy annotations
   - Ensured proper session affinity

3. **docs/MCP_INSPECTOR.md**
   - Added Quick Start section
   - Added Architecture diagram
   - Updated all connection instructions
   - Added comprehensive troubleshooting section
   - Explained why internal service names must be used

## Verification Commands

```bash
# Check deployment configuration
oc get deployment mcp-inspector -n rhel-mcp -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="CLIENT_PORT")].value}'
oc get deployment mcp-inspector -n rhel-mcp -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="ALLOWED_ORIGINS")].value}'

# Check routes exist
oc get routes -n rhel-mcp | grep inspector

# Check proxy logs
oc logs -n rhel-mcp deployment/mcp-inspector --tail=20

# Check MCP server logs
oc logs -n rhel-mcp deployment/linux-mcp-server --tail=20
```

## Lessons Learned

1. **MCP Inspector proxy architecture is complex**: The proxy runs inside the container, not in the browser, which affects how URLs are configured.

2. **DNS rebinding protection is strict**: Both the OpenShift routes AND localhost must be explicitly allowed in ALLOWED_ORIGINS.

3. **Internal vs External URLs**: Always use internal Kubernetes service names when the proxy is making connections inside the cluster.

4. **Configuration persistence**: The `MCP_PROXY_FULL_ADDRESS` must be set in the UI's Configuration (it's not automatically detected from environment variables when accessed through routes).

5. **Transport limitations**: "Direct" mode doesn't work well with Streamable HTTP through OpenShift routes. "Via Proxy" mode is required.

## Future Improvements

1. Consider setting `MCP_PROXY_FULL_ADDRESS` as a default in the deployment environment variables that the UI can read
2. Add health check endpoints to the proxy route for better monitoring
3. Consider using a ConfigMap for the Inspector configuration to pre-populate settings
4. Document the session ID lifecycle for Streamable HTTP transport

## Testing Checklist

- [ ] Inspector UI loads at OpenShift route
- [ ] Configuration page accessible
- [ ] MCP_PROXY_FULL_ADDRESS configurable
- [ ] Connection establishes with "Via Proxy" mode
- [ ] Tools list loads (22 tools)
- [ ] Resources tab populated
- [ ] Prompts tab accessible
- [ ] Tool execution works
- [ ] Port-forward access also works
- [ ] Both OpenShift routes and localhost in ALLOWED_ORIGINS

