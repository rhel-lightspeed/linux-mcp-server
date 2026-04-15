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
|------------------|---------|-------------|
| `--gatekeeper-model`<br>`LINUX_MCP_GATEKEEPER_MODEL` | *(none)* | Required: [LiteLLM model name](https://docs.litellm.ai/docs/providers) to use |
| `--always-confirm-scripts` / `--no-always-confirm-scripts`<br>`LINUX_MCP_ALWAYS_CONFIRM_SCRIPTS` | `False` | All scripts must be confirmed by the user |
| Other environment variables | *(none)* | As required by the LiteLLM provider, e.g. `OPENAI_API_KEY` |

## Logging Configuration

| Option / Env Var | Default | Description |
|------------------|---------|-------------|
| `--log-dir`<br>`LINUX_MCP_LOG_DIR` | `~/.local/share/linux-mcp-server/logs` | Directory for server logs |
| `--log-level`<br>`LINUX_MCP_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING` |
| `--log-retention-days`<br>`LINUX_MCP_LOG_RETENTION_DAYS` | `10` | Days to retain log files |

See [Debug Logging](debugging.md) for details on log formats and locations.

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
