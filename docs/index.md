# Linux MCP Server

[![CI](https://github.com/rhel-lightspeed/linux-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/rhel-lightspeed/linux-mcp-server/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/rhel-lightspeed/linux-mcp-server/graph/badge.svg?token=TtUkG1y0rx)](https://codecov.io/gh/rhel-lightspeed/linux-mcp-server)
[![PyPI](https://img.shields.io/pypi/v/linux-mcp-server?label=PyPI)](https://pypi.org/project/linux-mcp-server)

A Model Context Protocol (MCP) server for read-only Linux system administration, diagnostics, and troubleshooting on Linux systems.

## Quick Start

Python 3.10 or later and `pip` are required.

1. Install using `pip`. This will install to `~/.local/` on Linux and macOS and `%APPDATA%\Python` on Windows.

    ```bash
    pip install --user linux-mcp-server
    ```

1. Make sure [SSH connectivity is properly configured](install.md#ssh-configuration) between the system running the Linux MCP Server and the remote hosts you want to inspect.

1. [Configure your favorite MCP client](clients.md)

    On macOS, the path will be `/Users/YOUR_USER/.local/bin/linux-mcp-server`.

    On Windows, the path will be `C:\Users\YOUR_USER\AppData\Local\Python\Python3X\Scripts\linux-mcp-server`.

    Here is an example configuration for Claude Desktop. Make sure to replace `YOU_USER` with your actual username.


    ```json
    # Example claude_desktop_config.json
    {
      "mcpServers": {
        "Linux Tools": {
          "command": "/home/YOU_USER/.local/bin/linux-mcp-server",
          "env": {
            "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/messages,/var/log/lastlog"
            # Other options go here
          }
        }
      }
    }

    ```

    Here is an example configuration for goose. Run `goose configure` and select **Add Extension**.

    ```yaml
    # Example ~/.configure/goose/config.yaml
    extensions:
      linux-mcp-server:
        enabled: true
        type: stdio
        name: linux-mcp-server
        description: Linux troubleshooting tools
        cmd: /home/YOUR_USER/.local/bin/linux-mcp-server
        args: []
        envs:
          LINUX_MCP_ALLOWED_LOG_PATHS: /var/log/messages,/var/log/lastlog
          # Other options go here
        env_keys: []
        timeout: 30
    ```

1. Start diagnosing Linux systems!

For other installation methods, see the [Installation Guide](install.md).


## 🚀 New to MCP?

**[Start Here](getting-started.md)**
Learn what MCP is, how to set it up, and run your first command in 5 minutes.

**[Cheatsheet](cheatsheet.md)**
A fast lookup guide for common tasks and tools.


## How It Works

```mermaid
flowchart TB
    subgraph clients["MCP Clients"]
        direction LR
        C1[Claude Code] ~~~ C2[Goose] ~~~ C3[Other Clients]
    end

    MCP[Linux MCP Server]

    subgraph targets["Target Systems"]
        direction LR
        L[Local System] ~~~ R1[Remote Host 1] ~~~ R2[Remote Host 2] ~~~ RN[Remote Host N]
    end

    clients <--> MCP
    MCP <--> targets
```

## Features

- 🔒 **Read-Only Operations**: All tools are strictly read-only—diagnose with confidence knowing nothing will be modified. Perfect for production systems where you need answers without risk.

- 🌐 **Remote SSH Execution**: Troubleshoot remote servers from your local machine using secure SSH key-based authentication. No need to hop between terminals or remember complex command syntax.

- 🖥️ **Multi-Host Management**: Connect to your home lab, cloud VMs, or an entire data center in a single session. Seamlessly switch between hosts without reconfiguring.

- 🔍 **Comprehensive Diagnostics**: Get the full picture—system info, services, processes, logs, network connections, and storage—all through natural language queries. Ask "why is my system slow?" instead of memorizing `ps`, `journalctl`, and `ss` flags.

- 📋 **Configurable Log Access**: Control exactly which log files can be accessed via environment variables. Enterprise teams can enforce security policies while still enabling effective troubleshooting.

- 🎯 **RHEL/systemd Focused**: Built for Red Hat Enterprise Linux, Fedora, CentOS Stream, and other systemd-based distributions. Whether you're managing a personal Fedora workstation or a fleet of RHEL servers, this tool speaks your system's language.

## Key Components

- **FastMCP Server**: Core MCP protocol server handling tool registration and invocation
- **Tool Categories**: Six categories of read-only diagnostic tools
- **SSH Executor**: Routes commands to local subprocess or remote SSH execution with connection pooling
- **Audit Logger**: Comprehensive logging in both human-readable and JSON formats with automatic rotation
- **Multi-Target Execution**: Single server instance can execute commands on local system or multiple remote hosts
