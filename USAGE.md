# Usage Guide - Linux MCP Server

This guide provides detailed instructions on how to use the Linux MCP Server for system diagnostics and troubleshooting.

## Quick Start

1. **Install and activate the environment:**
   ```bash
   cd linux-mcp-server
   uv venv
   source .venv/bin/activate
   uv pip install -e .
   ```

2. **Configure environment variables:**
   ```bash
   export LINUX_MCP_ALLOWED_LOG_PATHS="/var/log/messages,/var/log/secure,/var/log/audit/audit.log"
   ```

3. **Run the server:**
   ```bash
   python -m linux_mcp_server
   ```

## Available Tools

### System Information

#### `get_system_info`
Returns basic system information including OS version, kernel, hostname, and uptime.

**Parameters:** None

**Example use case:** "What version of RHEL is this system running?"

#### `get_cpu_info`
Returns detailed CPU information including cores, frequency, usage, and load averages.

**Parameters:** None

**Example use case:** "Show me the current CPU load and usage per core."

#### `get_memory_info`
Returns RAM and swap memory usage details.

**Parameters:** None

**Example use case:** "How much memory is being used on this system?"

#### `get_disk_usage`
Returns filesystem usage and mount points.

**Parameters:** None

**Example use case:** "Which filesystems are running out of space?"

### Service Management

#### `list_services`
Lists all systemd services with their current status.

**Parameters:** None

**Example use case:** "Show me all services and their status."

#### `get_service_status`
Returns detailed status information for a specific service.

**Parameters:**
- `service_name` (string, required): Name of the service (e.g., "sshd" or "sshd.service")

**Example use case:** "Is the httpd service running? What's its status?"

#### `get_service_logs`
Returns recent logs for a specific service.

**Parameters:**
- `service_name` (string, required): Name of the service
- `lines` (number, optional): Number of log lines to retrieve (default: 50)

**Example use case:** "Show me the last 100 log entries for the nginx service."

### Process Management

#### `list_processes`
Lists running processes sorted by CPU usage.

**Parameters:** None

**Example use case:** "What processes are consuming the most CPU?"

#### `get_process_info`
Returns detailed information about a specific process.

**Parameters:**
- `pid` (number, required): Process ID

**Example use case:** "Give me detailed information about process 1234."

### Logs & Audit

#### `get_journal_logs`
Query systemd journal logs with optional filters.

**Parameters:**
- `unit` (string, optional): Filter by systemd unit (e.g., "sshd.service")
- `priority` (string, optional): Filter by priority (emerg, alert, crit, err, warning, notice, info, debug)
- `since` (string, optional): Show entries since specified time (e.g., "1 hour ago", "2024-01-01")
- `lines` (number, optional): Number of log lines to retrieve (default: 100)

**Example use cases:**
- "Show me the last 200 error messages from the journal."
- "What has sshd logged in the last hour?"
- "Show me all critical and error logs since yesterday."

#### `get_audit_logs`
Returns audit logs (requires appropriate permissions).

**Parameters:**
- `lines` (number, optional): Number of log lines to retrieve (default: 100)

**Example use case:** "Show me the recent audit log entries."

#### `read_log_file`
Reads a specific log file (must be in the allowed list).

**Parameters:**
- `log_path` (string, required): Path to the log file
- `lines` (number, optional): Number of lines from end (default: 100)

**Example use case:** "Show me the last 50 lines of /var/log/messages."

**Security Note:** This tool respects the `LINUX_MCP_ALLOWED_LOG_PATHS` environment variable whitelist.

### Network Diagnostics

#### `get_network_interfaces`
Returns network interface information including IP addresses and statistics.

**Parameters:** None

**Example use case:** "What network interfaces are configured and what are their IP addresses?"

#### `get_network_connections`
Returns active network connections with process information.

**Parameters:** None

**Example use case:** "Show me all active network connections."

#### `get_listening_ports`
Returns ports that are listening on the system.

**Parameters:** None

**Example use case:** "What services are listening on network ports?"

### Storage & Hardware

#### `list_block_devices`
Lists block devices, partitions, and disk I/O statistics.

**Parameters:** None

**Example use case:** "Show me all disk devices and their usage statistics."

#### `get_hardware_info`
Returns hardware information including CPU architecture, PCI devices, USB devices.

**Parameters:** None

**Example use case:** "What hardware is installed in this system?"

## Configuration

### Environment Variables

#### `LINUX_MCP_ALLOWED_LOG_PATHS`
**Required for `read_log_file` tool**

Comma-separated list of log file paths that are allowed to be read.

**Example:**
```bash
export LINUX_MCP_ALLOWED_LOG_PATHS="/var/log/messages,/var/log/secure,/var/log/httpd/access_log,/var/log/httpd/error_log"
```

**Security:** This whitelist prevents access to arbitrary files on the system.

#### `LINUX_MCP_LOG_LEVEL`
**Optional**

Sets the logging level for the MCP server itself (not the system logs).

**Values:** DEBUG, INFO, WARNING, ERROR, CRITICAL

**Example:**
```bash
export LINUX_MCP_LOG_LEVEL="DEBUG"
```

## Integration with Claude Desktop

Add this configuration to your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "linux-diagnostics": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/yourusername/linux-mcp-server",
        "run",
        "python",
        "-m",
        "linux_mcp_server"
      ],
      "env": {
        "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/secure,/var/log/audit/audit.log"
      }
    }
  }
}
```

## Example Troubleshooting Sessions

### High CPU Usage Investigation
1. "Show me the system CPU information and load averages" → `get_cpu_info`
2. "List all processes sorted by CPU usage" → `list_processes`
3. "Give me detailed info about process 12345" → `get_process_info`
4. "Show me the service status for httpd" → `get_service_status`

### Service Not Starting
1. "What's the status of the postgresql service?" → `get_service_status`
2. "Show me the last 100 logs for postgresql" → `get_service_logs`
3. "Show me error logs from the journal in the last hour" → `get_journal_logs`

### Network Connectivity Issues
1. "Show me all network interfaces and their status" → `get_network_interfaces`
2. "What ports are listening on this system?" → `get_listening_ports`
3. "Show me active network connections" → `get_network_connections`

### Disk Space Problems
1. "Show me disk usage for all filesystems" → `get_disk_usage`
2. "List all block devices" → `list_block_devices`
3. "Show me system information including uptime" → `get_system_info`

## Security Considerations

### Read-Only Operations
All tools are strictly read-only. No modifications to the system are possible through this MCP server.

### Log File Access Control
The `read_log_file` tool uses a whitelist approach. Only files explicitly listed in `LINUX_MCP_ALLOWED_LOG_PATHS` can be accessed.

### Privileged Information
Some tools may require elevated privileges to show complete information:
- `get_audit_logs` - Requires read access to `/var/log/audit/audit.log`
- `get_network_connections` - May require root to see all connections
- `get_hardware_info` - Some hardware details (dmidecode) require root

### Recommended Approach
Run the MCP server with the minimum required privileges. Consider:
1. Adding the user to specific groups (e.g., `adm` for log access)
2. Using sudo only when necessary for specific diagnostics
3. Carefully curating the `LINUX_MCP_ALLOWED_LOG_PATHS` list

## Troubleshooting

### "systemctl command not found"
The system doesn't have systemd. This MCP server is designed for systemd-based Linux distributions like RHEL 7+, Fedora, Ubuntu 16.04+, etc.

### "Permission denied" errors
The user running the MCP server doesn't have permission to access certain resources. Consider:
- Adding the user to the `adm` group for log access
- Running with sudo for diagnostics requiring root
- Adjusting file permissions as needed

### No log files accessible with `read_log_file`
Set the `LINUX_MCP_ALLOWED_LOG_PATHS` environment variable before starting the server.

## Best Practices

1. **Start Broad, Then Narrow**: Use general tools like `get_system_info` before diving into specific diagnostics.

2. **Correlate Information**: Combine multiple tools for comprehensive diagnostics (e.g., process info + service status + logs).

3. **Time-Based Investigation**: Use `since` parameter in `get_journal_logs` to focus on recent events.

4. **Security First**: Only whitelist log files that are necessary for diagnostics.

5. **Regular Updates**: Keep the MCP server and its dependencies updated for security and compatibility.

