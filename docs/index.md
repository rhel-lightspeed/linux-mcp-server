# Linux MCP Server

[![CI](https://github.com/rhel-lightspeed/linux-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/rhel-lightspeed/linux-mcp-server/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/rhel-lightspeed/linux-mcp-server/graph/badge.svg?token=TtUkG1y0rx)](https://codecov.io/gh/rhel-lightspeed/linux-mcp-server)
[![PyPI](https://img.shields.io/pypi/v/linux-mcp-server?label=PyPI)](https://pypi.org/project/linux-mcp-server)

A Model Context Protocol (MCP) server for read-only Linux system administration, diagnostics, and troubleshooting on RHEL-based systems.

## Features

- **Read-Only Operations**: All tools are strictly read-only for safe diagnostics
- **Remote SSH Execution**: Execute commands on remote systems via SSH with key-based authentication
- **Multi-Host Management**: Connect to different remote hosts in the same session
- **Comprehensive Diagnostics**: System info, services, processes, logs, network, and storage
- **Configurable Log Access**: Control which log files can be accessed via environment variables
- **RHEL/systemd Focused**: Optimized for Red Hat Enterprise Linux systems

## Quick Start

**1. Install**
```bash
pip install --user linux-mcp-server
```

**2. Configure your MCP client** ([details](clients.md))

**3. Start diagnosing Linux systems!**

See the [Installation Guide](install.md) for container installs, SSH setup, and more.

## Available Tools

| Category | Tools |
|----------|-------|
| **System Info** | `get_system_information`, `get_cpu_information`, `get_memory_information`, `get_disk_usage`, `get_hardware_information` |
| **Services** | `list_services`, `get_service_status`, `get_service_logs` |
| **Processes** | `list_processes`, `get_process_info` |
| **Logs** | `get_journal_logs`, `get_audit_logs`, `read_log_file` |
| **Network** | `get_network_interfaces`, `get_network_connections`, `get_listening_ports` |
| **Storage** | `list_block_devices`, `list_directories`, `list_files`, `read_file` |

## Key Components

- **FastMCP Server**: Core MCP protocol server handling tool registration and invocation
- **Tool Categories**: Six categories of read-only diagnostic tools
- **SSH Executor**: Routes commands to local subprocess or remote SSH execution with connection pooling
- **Audit Logger**: Comprehensive logging in both human-readable and JSON formats with automatic rotation
- **Multi-Target Execution**: Single server instance can execute commands on local system or multiple remote hosts

## Configuration

Key environment variables:

| Variable | Description |
|----------|-------------|
| `LINUX_MCP_ALLOWED_LOG_PATHS` | Comma-separated list of log files that can be accessed |
| `LINUX_MCP_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LINUX_MCP_SSH_KEY_PATH` | Path to SSH private key for remote execution |
| `LINUX_MCP_USER` | Username used for SSH connections (optional) |

See [Installation](install.md) for complete configuration details.
