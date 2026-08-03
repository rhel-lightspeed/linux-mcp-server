# Configuration Reference

The Linux MCP Server is configured through command line options or environment variables. Environment variables use a `LINUX_MCP_` prefix. For example, `--log-level` corresponds to `LINUX_MCP_LOG_LEVEL`.

!!! note "Precedence"
    Command line options take precedence over environment variables. For MCP client configurations (Claude Desktop, Cursor, etc.), you typically use environment variables in the config file rather than command line arguments, but either will work.

To see available options, run `linux-mcp-server --help`.

## Transport Settings

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--transport`<br>`LINUX_MCP_TRANSPORT` | `stdio` | Transport type: `stdio` or `http` |
| `--host`<br>`LINUX_MCP_HOST` | `127.0.0.1` | Host address for HTTP transport |
| `--port`<br>`LINUX_MCP_PORT` | `8000` | Port number for HTTP transport |
| `--path`<br>`LINUX_MCP_PATH` | `/mcp` | Path for HTTP transport |

!!! warning "HTTP Transport Security"
    The HTTP transport does not currently have authentication. It should not be used in production or on untrusted networks.

!!! note
    Some clients, like Claude Desktop, require `stdio` transport.

## SSH Connection Settings

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--user`<br>`LINUX_MCP_USER` | *(empty)* | Default username for SSH connections |
| `--ssh-key-path`<br>`LINUX_MCP_SSH_KEY_PATH` | *(none)* | Path to SSH private key file |
| `--key-passphrase`<br>`LINUX_MCP_KEY_PASSPHRASE` | *(empty)* | Passphrase for encrypted SSH key |
| `--search-for-ssh-key`<br>`LINUX_MCP_SEARCH_FOR_SSH_KEY` | `False` | Auto-discover SSH keys in `~/.ssh` |
| `--command-timeout`<br>`LINUX_MCP_COMMAND_TIMEOUT` | `30` | Local and remote command timeout in seconds |

## SSH Security Settings

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--verify-host-keys` / `--no-verify-host-keys`<br>`LINUX_MCP_VERIFY_HOST_KEYS` | `True` | Verify remote host identity via known_hosts |
| `--known-hosts-path`<br>`LINUX_MCP_KNOWN_HOSTS_PATH` | *(none)* | Custom path to known_hosts file |

See [SSH Configuration](ssh.md) for details on setting up SSH connections and managing host keys.

## Tool Settings

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--toolset`<br>`LINUX_MCP_TOOLSET` | `fixed` | Toolset: `fixed`, `run_script`, or `both` |
| `--allowed-log-paths`<br>`LINUX_MCP_ALLOWED_LOG_PATHS` | *(none)* | Comma-separated allowlist of log file paths for `read_log_file` |
| `--max-file-read-bytes`<br>`LINUX_MCP_MAX_FILE_READ_BYTES` | `1048576` | Maximum bytes `read_file` may return |

See [Guarded Command Execution](guarded-command-execution.md) for details on the `run_script` toolset.

## Guarded Command Execution Settings

These are used when `LINUX_MCP_TOOLSET` is set to `run_script` or `both`.

| Option / Env Var | Default | Description |
| ---------------- | ------- | ----------- |
| `--always-confirm-scripts` / `--no-always-confirm-scripts`<br>`LINUX_MCP_ALWAYS_CONFIRM_SCRIPTS` | `False` | All scripts must be confirmed by the user |
| `--gatekeeper.provider`<br>`LINUX_MCP_GATEKEEPER__PROVIDER` | `openai` (inferred from model if unset) | LLM provider: `openai`, `anthropic`, `gemini`, or `openrouter` |
| `--gatekeeper.backend`<br>`LINUX_MCP_GATEKEEPER__BACKEND` | `direct` | API backend: `direct` or `vertex` (GCP/Vertex AI) |
| `--gatekeeper.model`<br>`LINUX_MCP_GATEKEEPER__MODEL` | _(none)_ | Required: provider-native model ID (e.g. `gpt-5.4`, `claude-sonnet-4-6`, `gemini-2.0-flash`, `openai/gpt-oss-120b` for OpenRouter) |
| `--gatekeeper.quantization`<br>`LINUX_MCP_GATEKEEPER__QUANTIZATION` | _(none)_ | OpenRouter only: filter providers by quantization level (e.g. `fp4`, `bf16`) |
| `--gatekeeper.base_url`<br>`LINUX_MCP_GATEKEEPER__BASE_URL` / `OPENAI_API_BASE` | `https://api.openai.com/v1` | OpenAI-compatible API base URL (OpenAI provider only) |
| `--gatekeeper.project`<br>`LINUX_MCP_GATEKEEPER__PROJECT` / `VERTEXAI_PROJECT` | _(none)_ | GCP project for Vertex backends |
| `--gatekeeper.location`<br>`LINUX_MCP_GATEKEEPER__LOCATION` / `VERTEXAI_LOCATION` | `global` | GCP region for Vertex backends |
| `--gatekeeper.reasoning_effort`<br>`LINUX_MCP_GATEKEEPER__REASONING_EFFORT` | _(model specific)_ | Reasoning effort (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`). Not all values are supported for all models. |
| `--gatekeeper.structured_output`<br>`LINUX_MCP_GATEKEEPER__STRUCTURED_OUTPUT` | `True` | Whether to use structured JSON output from the model |
| `--gatekeeper.temperature`<br>`LINUX_MCP_GATEKEEPER__TEMPERATURE` | 0.0 | Temperature to use for the model |
| `--gatekeeper.template_kwargs`<br>`LINUX_MCP_GATEKEEPER__TEMPLATE_KWARGS` | _(none)_ | _Not usually needed_ - Extra chat-template arguments for OpenAI-compatible servers (e.g. llama.cpp `enable_thinking`), sent as `chat_template_kwargs` on Chat Completions requests. JSON object, e.g. `{ "enable_thinking": false }` |
| Provider credentials | _(none)_ | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` / `GEMINI_API_KEY`, or `OPENROUTER_API_KEY` for direct backends; `GOOGLE_APPLICATION_CREDENTIALS` for Vertex backends |

## Logging Configuration

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--log-dir`<br>`LINUX_MCP_LOG_DIR` | `~/.local/share/linux-mcp-server/logs` | Directory for server logs |
| `--log-level`<br>`LINUX_MCP_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING` |
| `--log-retention-days`<br>`LINUX_MCP_LOG_RETENTION_DAYS` | `10` | Days to retain log files |

See [Debug Logging](debugging.md) for details on log formats and locations.

## Authorization Configuration

These settings enable OAuth2 authentication for the HTTP transport. See [Shared Server](shared.md) for an overview of authorization concepts and setup.

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--auth.provider`<br>`LINUX_MCP_AUTH__PROVIDER` | *(none)* | Authorization provider: `google`, `github`, `jwt`, or `introspection` |
| `--policy-path`<br>`LINUX_MCP_POLICY_PATH` | *(none)* | Path to [authorization policy](#authorization-policy) YAML file |

The behavior when `--policy-path` is not specified varies by transport:

 - `stdio`: all access is allowed - the default action is `local` for `localhost` and `ssh_default` otherwise.
 - `http`: all access is denied

*Note*: `--policy-path` can be specified for the `stdio` transport, but is not typically useful. All rules must have `all_users: true` since there are no token claims to match on.

## Authorization Providers

Each provider requires its own set of configuration options, described below. Only the settings for the selected `--auth.provider` need to be configured.

### Google

Uses Google OAuth for authentication. Suitable for testing or environments where users have Google accounts.

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--auth.google.client_id`<br>`LINUX_MCP_AUTH__GOOGLE__CLIENT_ID` | *(required)* | Google OAuth client ID |
| `--auth.google.client_secret`<br>`LINUX_MCP_AUTH__GOOGLE__CLIENT_SECRET` | *(required)* | Google OAuth client secret |

### GitHub

Uses GitHub OAuth for authentication. Suitable for testing or environments where users have GitHub accounts.

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--auth.github.client_id`<br>`LINUX_MCP_AUTH__GITHUB__CLIENT_ID` | *(required)* | GitHub OAuth client ID |
| `--auth.github.client_secret`<br>`LINUX_MCP_AUTH__GITHUB__CLIENT_SECRET` | *(required)* | GitHub OAuth client secret |

### JWT

Validates JWT tokens locally using a JWKS endpoint. Use this when your authorization server issues JWTs and publishes a JWKS endpoint for token verification.

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--auth.jwt.jwks_uri`<br>`LINUX_MCP_AUTH__JWT__JWKS_URI` | *(required)* | URL of the JWKS endpoint for token verification |
| `--auth.jwt.issuer`<br>`LINUX_MCP_AUTH__JWT__ISSUER` | *(required)* | Expected token issuer (`iss` claim) |
| `--auth.jwt.audience`<br>`LINUX_MCP_AUTH__JWT__AUDIENCE` | *(none)* | Expected token audience (`aud` claim) |

### Introspection

Validates tokens by sending them back to the authorization server's introspection endpoint. Use this when your authorization server supports [RFC 7662](https://datatracker.ietf.org/doc/html/rfc7662) token introspection.

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--auth.introspection.introspection_url`<br>`LINUX_MCP_AUTH__INTROSPECTION__INTROSPECTION_URL` | *(required)* | Token introspection endpoint URL |
| `--auth.introspection.issuer`<br>`LINUX_MCP_AUTH__INTROSPECTION__ISSUER` | *(required)* | Expected token issuer |
| `--auth.introspection.client_id`<br>`LINUX_MCP_AUTH__INTROSPECTION__CLIENT_ID` | *(required)* | Client ID for authenticating to the introspection endpoint |
| `--auth.introspection.client_secret`<br>`LINUX_MCP_AUTH__INTROSPECTION__CLIENT_SECRET` | *(required)* | Client secret for authenticating to the introspection endpoint |
| `--auth.introspection.timeout_seconds`<br>`LINUX_MCP_AUTH__INTROSPECTION__TIMEOUT_SECONDS` | `10` | Timeout in seconds for introspection requests |

## Authorization Policy

See [Configuring the Authorization policy](shared.md#configuring-the-authorization-policy) for an overview and examples.

An authorization policy is a YAML file with a single toplevel property, `rules`,
which is a list of rules.
The rules are checked in order,
and when a matching rule is found, the action from that rule is used, and processing stops.

Each rule has the following properties that are used for matching:

 - **`host`** (required, string): either `localhost` for local execution or a pattern (with * and ? wildcards) that matches a remote host. `localhost` must be specified literally - `host: *` will *not* match `localhost`.
 - **`tools`** (required, list of strings) - a list of tool names or toolsets to match. Use `*` to match all tools. A toolset (as for `LINUX_MCP_TOOLSET`) is represented by a `@` prefix. If a tool name or toolset name is preceded by `-`, that excludes the tool or toolset. (Exclusions take precedence, order doesn't matter.)
 - **`claims`** (object) - claims from the OAuth2 token to match on. Each item in here is of the form `<claim_name>`: `<value>` with the following match rules:
    - if `<value>` is a string, and the value from the token is a string, they must match exactly
    - if `<value>` is a string, and the value from the token is a list, `<value>` must be in the list (example: `groups: app-rhel-mcp-server-users`)
    - for all other types for `<value>` the values must match exactly (example: `email_verified: true`)
 - **`all_users`** (boolean) - `true` if this rule should match all users. Either `all_users: true` or a non-empty `claims` must be specified; a rule with `all_users: false` (the default) and no `claims` is invalid.

The rule also specifies an action and, if the action is `ssh_key`, additional properties for that action.

 - **`action`** (one of `deny`, `local`, `ssh_default`, `ssh_key`) - what to do for a matching rule
    - **`deny`** - deny execution of the tool
    - **`local`** - allow the tool to be executed on the local system
    - **`ssh_default`** - allow the tool to be executed on a remote system, using default SSH key lookup
    - **`ssh_key`** - allow the tool to be executed on a remote system using a specific SSH key identified by path
 - **`ssh_key`**: Required when `action` is `ssh_key`.
    - **`path`**: (string) - path to an SSH key to use to connect to a remote system
    - **`user`**: (string) - username to use on the remote system

## Examples

**Specify SSH settings:**
```bash
linux-mcp-server --user admin --ssh-key-path ~/.ssh/id_rsa --verify-host-keys
```

**Configure log access:**
```bash
linux-mcp-server --allowed-log-paths "/var/log/messages,/var/log/secure,/var/log/audit/audit.log"
```

**Using environment variables in a client config:**
```json
{
  "env": {
    "LINUX_MCP_USER": "admin",
    "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/secure",
    "LINUX_MCP_LOG_LEVEL": "DEBUG"
  }
}
```
