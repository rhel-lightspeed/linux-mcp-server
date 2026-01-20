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

1. **Configure environment variables (optional but recommended):**
   ```bash
   export LINUX_MCP_ALLOWED_LOG_PATHS="/var/log/messages,/var/log/secure,/var/log/audit/audit.log"
   export LINUX_MCP_LOG_LEVEL="INFO"
   ```

2. **Run the server:**
   ```bash
   linux-mcp-server
   ```

### Enabling running arbitrary commands ***EXPERIMENTAL***

The default tools exposed by the linux-mcp-server allow the AI agent a wide range of tools
to query information about specific aspects of the target machine, as described below.
However, the agent is not able to run arbitrary commands. It is also possible (as an experimental
feature), to enable additional tools to allow the AI agent to run arbitrary commands,
in read-only or read-write mode.

```
export LINUX_MCP_TOOLSET="run_script"
export LINUX_MCP_GATEKEEPER_MODEL="chatgpt/gpt-5.2"
export OPENAI_API_KEY="Your API key"
```

Three values are supported for LINUX_MCP_TOOLSET:

* **FIXED**: only read-only tools with fixed functionality
* **RUN_SCRIPT**: only `run_script_readonly` and `run_script_modify`
* **BOTH**: all the tools

Running in `both` mode will not necessarily produce better results then only using
the `run_script` toolset - the greater number of tools may confuse the AI agent.
Try it both ways.

To try to avoid actions that are dangerous or that do unintended things, the scripts
passed to the `run_script_*` tools are checked using a gatekeeper model that reviews
the commands before running them. You must configure this model. Configuration is
done by using the `LINUX_MCP_GATEKEEPER_MODEL` environment variable. Additional environment
variables will be needed to configure credentials. See the
[LiteLLM documentation](https://docs.litellm.ai/docs/providers).


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

#### `run_script_readonly` (experimental)
Runs a script on a system in read-only mode.

**Parameters**
- `description`: Description of what the script does - e.g. 'Collect SELinux messages from the system logs.'
- `script_type`: The type of script to run (`python` or `bash`)
- `script`: The script to run

#### `run_script_modify` (experimental)
Runs a script on a system to modify files or settings.

**Parameters**
- `description`: Description of what the script does - e.g. 'Modify file permissions on nginx.conf to fix startup errors.'
- `script_type`: The type of script to run (`python` or `bash`)
- `script`: The script to run


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

