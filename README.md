[![CI](https://github.com/rhel-lightspeed/linux-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/rhel-lightspeed/linux-mcp-server/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/rhel-lightspeed/linux-mcp-server/graph/badge.svg?token=TtUkG1y0rx)](https://codecov.io/gh/rhel-lightspeed/linux-mcp-server)
[![PyPI](https://img.shields.io/pypi/v/linux-mcp-server?label=PyPI)](https://pypi.org/project/linux-mcp-server)
[![Docs](https://img.shields.io/badge/Docs-Linux%20MCP%20Server-red)](https://rhel-lightspeed.github.io/linux-mcp-server/)


# Linux MCP Server

A Model Context Protocol (MCP) server for read-only Linux system administration, diagnostics, and troubleshooting on RHEL-based systems.


## Features

- **Read-Only Operations**: All tools are strictly read-only for safe diagnostics
- **Remote SSH Execution**: Execute commands on remote systems via SSH with key-based authentication
- **Multi-Host Management**: Connect to different remote hosts in the same session
- **Comprehensive Diagnostics**: System info, services, processes, logs, network, and storage
- **Configurable Log Access**: Control which log files can be accessed via environment variables
- **RHEL/systemd Focused**: Optimized for Red Hat Enterprise Linux systems


## Installation and Usage

For detailed instructions on setting up and using the Linux MCP Server, please refer to our official documentation:

- **[Installation Guide](https://rhel-lightspeed.github.io/linux-mcp-server/install/)**: Detailed steps for `pip`, `uv`, and container-based deployments.
- **[Usage Guide](https://rhel-lightspeed.github.io/linux-mcp-server/usage/)**: Information on running the server, configuring AI agents (Claude, Goose), and troubleshooting.

## Available Tools

### System Information
- `get_system_information` - OS version, kernel, hostname, uptime
- `get_cpu_information` - CPU details and load averages
- `get_memory_information` - RAM usage and swap details
- `get_disk_usage` - Filesystem usage and mount points
- `get_hardware_information` - Hardware details (CPU architecture, PCI/USB devices, memory hardware)

### Service Management
- `list_services` - List all systemd services with status
- `get_service_status` - Detailed status of a specific service
- `get_service_logs` - Recent logs for a specific service

### Process Management
- `list_processes` - Running processes with CPU/memory usage
- `get_process_info` - Detailed information about a specific process

### Logs & Audit
- `get_journal_logs` - Query systemd journal with filters
- `get_audit_logs` - Read audit logs (if available)
- `read_log_file` - Read specific log file (whitelist-controlled)

### Network Diagnostics
- `get_network_interfaces` - Network interface information
- `get_network_connections` - Active network connections
- `get_listening_ports` - Ports listening on the system

### Storage & Disk Analysis
- `list_block_devices` - Block devices and partitions
- `list_directories` - List directories under a specified path with various sorting options

### Key Components

- **FastMCP Server**: Core MCP protocol server handling tool registration and invocation
- **Tool Categories**: Six categories of read-only diagnostic tools (system info, services, processes, logs, network, storage)
- **SSH Executor**: Routes commands to local subprocess or remote SSH execution with connection pooling
- **Audit Logger**: Comprehensive logging in both human-readable and JSON formats with automatic rotation
- **Multi-Target Execution**: Single server instance can execute commands on local system or multiple remote hosts

