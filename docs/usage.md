# Usage Guide - Linux MCP Server

This guide provides detailed instructions on how to use the Linux MCP Server for system diagnostics and troubleshooting.

## Quick Start

### Prerequisites

Before using the MCP server, you need to either install it or have the necessary tools to run it on-demand (uvx).
See [Installation](install.md) for complete installation instructions.

**Quick install with pip:**
```bash
pip install linux-mcp-server
```

### Running the Server

```bash
linux-mcp-server
```

### Command Line Options

To see available options, run `linux-mcp-server --help`.

Options may be set using environment variables or command line options. Environment variables require a `LINUX_MCP_` prefix. For example `LINUX_MCP_LOG_LEVEL` is the same as `--log-level`.

!!! note "Command Line vs Environment Variables"
      Command line options take precedence over environment variables. For MCP client configurations (Claude Desktop, Cursor, etc.), you typically use environment variables in the config file rather than command line arguments but either will.


#### Available Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-h, --help` | - | - | Show help message and exit |
| `--version` | - | - | Display version and exit |
| `--user` | string | (empty) | Default username for SSH connections |
| `--transport` | string | stdio | Transport type: `stdio`, `http`, or `streamable_http` |
| `--host` | string | `127.0.0.1` | Host address for HTTP transport |
| `--port` | integer | 8000 | Port number for HTTP transport |
| `--path` | string | /mcp | Path for HTTP transport |
| `--log-dir` | path | `~/.local/share/linux-mcp-server/logs` | Directory for server logs |
| `--log-level` | string | `INFO` | Log verbosity level |
| `--log-retention-days` | integer | 10 | Days to retain log files |
| `--allowed-log-paths` | string | null | Comma-separated list of allowed log file paths |
| `--ssh-key-path` | path | null | Path to SSH private key file |
| `--key-passphrase` | string | (empty) | Passphrase for encrypted SSH key |
| `--search-for-ssh-key` | bool | False | Auto-discover SSH keys in `~/.ssh` |
| `--verify-host-keys` | bool | False | Verify remote host identity via known_hosts |
| `--known-hosts-path` | path | null | Path to known_hosts file |
| `--command-timeout` | integer | 30 | SSH command timeout in seconds |

#### Examples


**Specify SSH settings:**
```bash
linux-mcp-server --user admin --ssh-key-path ~/.ssh/id_rsa --verify-host-keys
```

**Configure log access:**
```bash
linux-mcp-server --allowed-log-paths "/var/log/messages,/var/log/secure,/var/log/audit/audit.log"
```

### Using with AI Agents

For the best experience, integrate the MCP server with an AI Agent of your preference.

#### For Claude Desktop
See [Client Configuration](clients.md#claude-desktop).

## Available Tools

### System Information

#### `get_system_information`
Returns basic system information including OS version, kernel, hostname, and uptime.

**Parameters:** None

**Example use case:** "What version of RHEL is this system running?"

#### `get_cpu_information`
Returns detailed CPU information including cores, frequency, usage, and load averages.

**Parameters:** None

**Example use case:** "Show me the current CPU load and usage per core."

#### `get_memory_information`
Returns RAM and swap memory usage details.

**Parameters:** None

**Example use case:** "How much memory is being used on this system?"

#### `get_disk_usage`
Returns filesystem usage and mount points.

**Parameters:** None

**Example use case:** "Which filesystems are running out of space?"

#### `get_hardware_information`
Returns hardware information including CPU architecture, PCI devices, USB devices, and memory hardware.

**Parameters:** None

**Example use case:** "What hardware is installed in this system?"

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

### Package Management (DNF)

#### `list_dnf_installed_packages`
Lists installed packages via `dnf`.

**Parameters:**
- `host` (string, optional): Remote host identifier
- `limit` (number, optional): Maximum number of output lines to return (default: 500)
- `offset` (number, optional): Number of output lines to skip (default: 0)
- `no_limit` (boolean, optional): Disable output truncation (default: false)

**Example use case:** "Show me all installed packages."

#### `list_dnf_available_packages`
Lists packages available in configured repositories.

**Parameters:**
- `host` (string, optional): Remote host identifier
- `limit` (number, optional): Maximum number of output lines to return (default: 500)
- `offset` (number, optional): Number of output lines to skip (default: 0)
- `no_limit` (boolean, optional): Disable output truncation (default: false)

**Example use case:** "Which packages are available from enabled repos?"

#### `get_dnf_package_info`
Returns detailed information for a specific package.

**Parameters:**
- `package` (string, required): Package name (e.g., "bash", "openssl")
- `host` (string, optional): Remote host identifier

**Example use case:** "Get details for the bash package."

#### `list_dnf_repositories`
Lists configured repositories and their status.

**Parameters:**
- `host` (string, optional): Remote host identifier
- `limit` (number, optional): Maximum number of output lines to return (default: 500)
- `offset` (number, optional): Number of output lines to skip (default: 0)
- `no_limit` (boolean, optional): Disable output truncation (default: false)

**Example use case:** "Show me all configured repositories and whether they are enabled."

#### `dnf_provides`
Finds packages that provide a file or binary.

**Parameters:**
- `query` (string, required): File path or binary name (e.g., "/usr/bin/python3", "libssl.so.3")
- `host` (string, optional): Remote host identifier

**Example use case:** "Which package provides /usr/bin/python3?"

#### `get_dnf_repo_info`
Shows detailed information for a specific repository.

**Parameters:**
- `repo_id` (string, required): Repository id (e.g., "baseos", "appstream")
- `host` (string, optional): Remote host identifier

**Example use case:** "Show details for the baseos repository."

#### `list_dnf_groups`
Lists available and installed package groups.

**Parameters:**
- `host` (string, optional): Remote host identifier
- `limit` (number, optional): Maximum number of output lines to return (default: 500)
- `offset` (number, optional): Number of output lines to skip (default: 0)
- `no_limit` (boolean, optional): Disable output truncation (default: false)

**Example use case:** "List all package groups."

#### `get_dnf_group_info`
Shows details for a specific package group.

**Parameters:**
- `group` (string, required): Group name (e.g., "Development Tools")
- `host` (string, optional): Remote host identifier

**Example use case:** "Show details for the Development Tools group."

#### `get_dnf_group_summary`
Shows a summary of installed and available groups.

**Parameters:**
- `host` (string, optional): Remote host identifier
- `limit` (number, optional): Maximum number of output lines to return (default: 500)
- `offset` (number, optional): Number of output lines to skip (default: 0)
- `no_limit` (boolean, optional): Disable output truncation (default: false)

**Example use case:** "Summarize installed and available groups."

#### `list_dnf_modules`
Lists modules (optionally filtered by module name).

**Parameters:**
- `module` (string, optional): Module name filter (e.g., "nodejs")
- `host` (string, optional): Remote host identifier
- `limit` (number, optional): Maximum number of output lines to return (default: 500)
- `offset` (number, optional): Number of output lines to skip (default: 0)
- `no_limit` (boolean, optional): Disable output truncation (default: false)

**Example use case:** "List available nodejs module streams."

#### `dnf_module_provides`
Shows modules that provide a specific package.

**Parameters:**
- `package` (string, required): Package name (e.g., "python3")
- `host` (string, optional): Remote host identifier

**Example use case:** "Which module provides python3?"

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

#### `get_ip_route_table`
Returns IPv4/IPv6 routing table entries using `ip route`.

**Parameters:**
- `family` (string, optional): `ipv4`, `ipv6`, or `all` (default: `ipv4`)
- `host` (string, optional): Remote host identifier

**Example use case:** "Show me the IPv4 routing table."

### Storage & Disk Analysis

#### `list_block_devices`
Lists block devices, partitions, and disk I/O statistics.

**Parameters:** None

**Example use case:** "Show me all disk devices and their usage statistics."

#### `list_directories`
Lists immediate subdirectories under a specified path with flexible sorting options. Uses efficient Linux commands (`du` for size, `find` for name and date) for fast analysis.

**Parameters:**
- `path` (string, required): Directory path to analyze (e.g., "/home", "/var", "/")
- `order_by` (string, optional): Sort order - 'size', 'name', or 'modified' (default: 'name')
- `sort` (string, optional): Sort direction - 'ascending' or 'descending' (default: 'ascending')
- `top_n` (number, optional): Limit number of directories to return (1-1000, primarily used with size ordering)

**Key Features:**
- Lists only immediate children (not nested paths)
- When ordering by size, sizes include all nested content recursively
- Fast performance using native Linux commands
- Path validation prevents traversal attacks
- Flexible sorting options for different use cases

**Example use cases:**
- "Find the top 5 largest directories in /var" → `list_directories(path="/var", order_by="size", sort="descending", top_n=5)`
- "What are the 10 biggest directories under /home?" → `list_directories(path="/home", order_by="size", sort="descending", top_n=10)`
- "List all directories in /home alphabetically" → `list_directories(path="/home", order_by="name")`
- "Show me directories in /var in reverse alphabetical order" → `list_directories(path="/var", order_by="name", sort="descending")`
- "Show me recently modified directories in /home" → `list_directories(path="/home", order_by="modified", sort="descending")`
- "What directories in /tmp were changed (oldest first)?" → `list_directories(path="/tmp", order_by="modified", sort="ascending")`

## Configuration

See [Client Configuration](clients.md) for environment variables and AI agent integration details.

## Example Troubleshooting Sessions

### High CPU Usage Investigation
1. "Show me the system CPU information and load averages" → `get_cpu_information`
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
4. "Show me the routing table" → `get_ip_route_table`

### Disk Space Problems
1. "Show me disk usage for all filesystems" → `get_disk_usage`
2. "List all block devices" → `list_block_devices`
3. "Find the top 10 largest directories in /var" → `list_directories`
4. "What are the biggest directories under /home?" → `list_directories`
5. "List recently modified directories in /tmp" → `list_directories`
6. "Show me system information including uptime" → `get_system_information`

### Detailed Disk Space Analysis
1. "Show me overall disk usage" → `get_disk_usage`
2. "Which directories under /var are using the most space?" → `list_directories(path="/var", order_by="size", sort="descending", top_n=10)`
3. "What are the biggest directories under /home?" → `list_directories(path="/home", order_by="size", sort="descending", top_n=20)`
4. "What's taking up space in the root filesystem?" → `list_directories(path="/", order_by="size", sort="descending", top_n=5)`
5. "Show me all directories in /opt alphabetically" → `list_directories(path="/opt", order_by="name")`
6. "Which directories in /var/log were modified recently?" → `list_directories(path="/var/log", order_by="modified", sort="descending")`

## Security Considerations

### Read-Only Operations
All tools are strictly read-only. No modifications to the system are possible through this MCP server.

### Log File Access Control
The `read_log_file` tool uses a whitelist approach. Only files explicitly listed in `LINUX_MCP_ALLOWED_LOG_PATHS` can be accessed.

### Privileged Information
Some tools may require elevated privileges to show complete information:
- `get_audit_logs` - Requires read access to `/var/log/audit/audit.log`
- `get_network_connections` - May require root to see all connections
- `get_hardware_information` - Some hardware details (dmidecode) require root

### Recommended Approach
Run the MCP server with the minimum required privileges. Consider:
1. Adding the user to specific groups (e.g., `adm` for log access)
2. Using sudo only when necessary for specific diagnostics
3. Carefully curating the `LINUX_MCP_ALLOWED_LOG_PATHS` list

## Troubleshooting

See the [Troubleshooting Guide](troubleshooting.md) for detailed solutions, debugging steps, and permission setup.

## Best Practices

1. **Start Broad, Then Narrow**: Use general tools like `get_system_information` before diving into specific diagnostics.

2. **Correlate Information**: Combine multiple tools for comprehensive diagnostics (e.g., process info + service status + logs).

3. **Time-Based Investigation**: Use `since` parameter in `get_journal_logs` to focus on recent events.

4. **Security First**: Only whitelist log files that are necessary for diagnostics.

5. **Regular Updates**: Keep the MCP server and its dependencies updated for security and compatibility.
