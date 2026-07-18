# Keycloak Configuration

This guide covers how to configure Keycloak for JWT  and Introspection based authentication.


## Prerequisites

- Keycloak server runnings
- Admin access to Keycloak Admin Console

### Running Keycloak Locally with Podman

```bash
# Pull the latest Keycloak image
podman pull quay.io/keycloak/keycloak:latest

# Run Keycloak in development mode
podman run -d \
  --name keycloak \
  -p 8080:8080 \
  -e KEYCLOAK_ADMIN=admin \
  -e KEYCLOAK_ADMIN_PASSWORD=admin \
  quay.io/keycloak/keycloak:latest start-dev

# Check logs
podman logs -f keycloak

# Access admin console at: http://localhost:8080/admin
# Login with: admin / admin
```

---

This approach uses **Dynamic Client Registration (DCR)** where MCP clients automatically register themselves with Keycloak. The MCP server validates JWT tokens or uses introspection.

### Step 1: Create Realm

1. Navigate to **Keycloak Admin Console**: `http://localhost:8080/admin/master/console/`
2. Log in with admin credentials
3. Click the realm dropdown (top left, shows "master") → **Create Realm**
4. Configure:
   - **Realm name**: Choose your realm name
   - **Enabled**: `ON`
5. Click **Create**

### Step 2: Add Audience Mapper to Client Scope

DCR clients need the `aud` (audience) claim in their tokens. Add an audience mapper to the `basic` client scope (which is already set as "Default"):

- Navigate to **Client scopes → basic → Mappers**
- Add an **Audience** mapper with `Included Client Audience: account`
- Enable "Add to access token"

This ensures all DCR-created clients automatically get tokens with `aud: account`.

### Step 3: Verify Dynamic Client Registration

DCR is enabled by default. Optionally verify that **Realm settings → Client Registration → Policies** has no policies blocking anonymous registration.

### Step 4: Create a Test User

Create a user with email and password for testing authentication:

- Navigate to **Users** and create a new user
- Set a non-temporary password in the **Credentials** tab


## MCP Server Configuration

###  JWT Validation

The MCP server validates JWT tokens using Keycloak's public keys (JWKS).

```bash
# Transport
export LINUX_MCP_TRANSPORT=streamable-http
export LINUX_MCP_HOST=localhost
export LINUX_MCP_PORT=3000

# JWT Authentication
export LINUX_MCP_AUTH__PROVIDER=jwt
export LINUX_MCP_AUTH__JWT__JWKS_URI="http://localhost:8080/realms/mcp_realm/protocol/openid-connect/certs"
export LINUX_MCP_AUTH__JWT__ISSUER="http://localhost:8080/realms/mcp_realm"
export LINUX_MCP_AUTH__JWT__AUDIENCE="account"  # Must match the audience mapper value

```

**Authentication Flow**: Clients discover Keycloak via `/.well-known/oauth-protected-resource/mcp`, auto-register using DCR, obtain JWT tokens through Keycloak's OAuth flow, and send tokens to the MCP server which validates them locally using JWKS.


### Token Introspection

The MCP server validates tokens by calling Keycloak's introspection endpoint. Requires a confidential client.

#### Create Introspection Client

Create a confidential OpenID Connect client with service account roles enabled for introspection:

- Create a new client
- Enable **Client authentication** and **Service account roles**
- Copy the client secret from the **Credentials** tab

```bash
# Transport
export LINUX_MCP_TRANSPORT=streamable-http
export LINUX_MCP_HOST=localhost
export LINUX_MCP_PORT=3000

# Introspection Authentication
export LINUX_MCP_AUTH__PROVIDER=introspection
export LINUX_MCP_AUTH__INTROSPECTION__INTROSPECTION_URL="http://localhost:8080/realms/mcp_realm/protocol/openid-connect/token/introspect"
export LINUX_MCP_AUTH__INTROSPECTION__ISSUER="http://localhost:8080/realms/mcp_realm"
export LINUX_MCP_AUTH__INTROSPECTION__CLIENT_ID="linux_mcp_server"
export LINUX_MCP_AUTH__INTROSPECTION__CLIENT_SECRET="<your-client-secret>"
```

**Authentication Flow**: Same discovery and DCR flow as JWT mode, but the server validates tokens by calling Keycloak's introspection endpoint rather than using local JWKS validation—enabling real-time revocation checks at the cost of higher latency.

---
