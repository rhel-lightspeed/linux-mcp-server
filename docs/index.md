# Linux MCP Server

[![CI](https://github.com/rhel-lightspeed/linux-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/rhel-lightspeed/linux-mcp-server/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/rhel-lightspeed/linux-mcp-server/graph/badge.svg?token=TtUkG1y0rx)](https://codecov.io/gh/rhel-lightspeed/linux-mcp-server)
[![PyPI](https://img.shields.io/pypi/v/linux-mcp-server?label=PyPI)](https://pypi.org/project/linux-mcp-server)

A Model Context Protocol (MCP) server for read-only Linux system administration, diagnostics, and troubleshooting on Linux systems.

## Features

- 🔒 **Read-Only Operations**: All tools are strictly read-only—diagnose with confidence knowing nothing will be modified. Perfect for production systems where you need answers without risk.

- 🌐 **Remote SSH Execution**: Troubleshoot remote servers from your local machine using secure SSH key-based authentication. No need to hop between terminals or remember complex command syntax.

- 🖥️ **Multi-Host Management**: Connect to your home lab, cloud VMs, or an entire data center in a single session. Seamlessly switch between hosts without reconfiguring.

- 🔍 **Comprehensive Diagnostics**: Get the full picture—system info, services, processes, logs, network connections, and storage—all through natural language queries. Ask "why is my system slow?" instead of memorizing `ps`, `journalctl`, and `ss` flags.

- 📋 **Configurable Log Access**: Control exactly which log files can be accessed via environment variables. Enterprise teams can enforce security policies while still enabling effective troubleshooting.

- 🎯 **RHEL/systemd Focused**: Built for Red Hat Enterprise Linux, Fedora, CentOS Stream, and other systemd-based distributions. Whether you're managing a personal Fedora workstation or a fleet of RHEL servers, this tool speaks your system's language.

## Quick Start

**1. Install**
```bash
pip install --user linux-mcp-server      # Install the MCP server
~/.local/bin/linux-mcp-server --help     # Verify installation
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
