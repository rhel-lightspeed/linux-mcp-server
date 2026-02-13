# API Reference

This section provides auto-generated documentation from the source code docstrings.

## Package Structure

### Core Modules

- **[Server](server.md)** - FastMCP server initialization
- **[Config](config.md)** - Configuration settings via Pydantic
- **[Commands](commands.md)** - Command registry and execution
- **[Audit](audit.md)** - Audit logging with rotation

### Tools

MCP tools organized by category:

- **[System Info](tools/system_info.md)** - OS, CPU, memory, disk, hardware information
- **[Services](tools/services.md)** - Systemd service management
- **[Processes](tools/processes.md)** - Process listing and details
- **[Logs](tools/logs.md)** - Journal, audit, and log file access
- **[Network](tools/network.md)** - Network interfaces, connections, ports, routes
- **[Storage](tools/storage.md)** - Block devices, directory and file listing

### Utilities

- **[Connection](connection.md)** - SSH connection pooling
- **[Formatters](formatters.md)** - Output formatting functions
- **[Parsers](parsers.md)** - Command output parsing
