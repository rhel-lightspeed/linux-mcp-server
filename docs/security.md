# Security Best Practices

The Linux MCP Server is designed with security in mind. All default-enabled tools are strictly read-only, and several configuration options allow you to control what the server can access.

## Read-Only Operations

All default-enabled tools are read-only. No modifications to the system are possible through the fixed toolset. This makes it safe to use on production systems where you need answers without risk.

When [Guarded Command Execution](guarded-command-execution.md) is enabled, the server can run scripts that modify systems. See that page for details on the safety controls available.

## Log File Access Control

The `read_log_file` tool uses a whitelist approach. Only files explicitly listed in `LINUX_MCP_ALLOWED_LOG_PATHS` can be accessed.

```bash
# Only allow reading these specific log files
LINUX_MCP_ALLOWED_LOG_PATHS="/var/log/messages,/var/log/secure,/var/log/audit/audit.log"
```

If `LINUX_MCP_ALLOWED_LOG_PATHS` is not set, the `read_log_file` tool cannot read any files.

## Privileged Information

Some tools may require elevated privileges to show complete information:

- `get_journal_logs` (with `transport="audit"`) requires read access to the audit logs
- `get_network_connections` may require root to see all connections
- `get_hardware_information` requires root for some hardware details (dmidecode)

### Recommended Approach

Use an account on the target machine with the minimum required privileges. See [Per-Host Configuration](ssh.md#per-host-configuration) for how to control which account is used when connecting via SSH.

1. Add the target user to specific groups for log access:
   ```bash
   sudo usermod -a -G adm $USER
   sudo usermod -a -G systemd-journal $USER
   ```
2. Log out and log back in for group changes to take effect
3. Carefully curate the `LINUX_MCP_ALLOWED_LOG_PATHS` list to include only necessary files

## SSH Security

- **Use key-based authentication**: The MCP server requires passwordless SSH (key-based, not password). See [SSH Configuration](ssh.md) for setup.
- **Enable host key verification**: The server enables host key checking by default (`LINUX_MCP_VERIFY_HOST_KEYS=True`). Do not disable this on untrusted networks.
- **Limit SSH access**: Use `~/.ssh/config` to control which hosts are accessible and with what credentials.

## HTTP Transport

!!! warning
    The HTTP transport (`LINUX_MCP_TRANSPORT=http`) does not currently have authentication. It should not be used in production or on untrusted networks.

For most use cases, the default `stdio` transport is recommended, as the MCP client manages the server's lifecycle directly.
