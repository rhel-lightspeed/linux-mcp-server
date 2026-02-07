<!-- mcp-name: io.github.rhel-lightspeed/linux-mcp-server -->
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
- **Package Insights (DNF)**: Query installed packages, available packages, and repositories
- **Configurable Log Access**: Control which log files can be accessed via environment variables
- **RHEL/systemd Focused**: Optimized for Red Hat Enterprise Linux systems


## Installation and Usage

For detailed instructions on setting up and using the Linux MCP Server, please refer to our official documentation:

- **[Installation Guide]**: Detailed steps for `pip`, `uv`, and container-based deployments.
- **[Usage Guide]**: Information on running the server, configuring LLM clients, and troubleshooting.
- **[Cheatsheet]**: A reference for what prompts to use to invoke various tools.


[Installation Guide]: https://rhel-lightspeed.github.io/linux-mcp-server/install/
[Usage Guide]: https://rhel-lightspeed.github.io/linux-mcp-server/usage/
[Cheatsheet]: https://rhel-lightspeed.github.io/linux-mcp-server/cheatsheet/
