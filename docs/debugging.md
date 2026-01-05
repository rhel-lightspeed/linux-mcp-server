# Debug Logging and Diagnostics

This document describes how to enable and use logging to debug and monitor the MCP server operations.

## Overview

The Linux MCP Server provides comprehensive logging for:
- Tool invocations with parameters
- SSH connection events
- Command execution (local and remote)
- Tool execution timing
- Errors and exceptions

Logging is centralized in the server layer with tiered verbosity based on log level.

## Enabling Debug Logging

Set the `LINUX_MCP_LOG_LEVEL` environment variable to `DEBUG`:

```bash
export LINUX_MCP_LOG_LEVEL=DEBUG
```

## Log Output Locations

Logs are written to two formats:

1. **Human-readable**: `~/.local/share/linux-mcp-server/logs/server.log`
2. **JSON format**: `~/.local/share/linux-mcp-server/logs/server.json`

You can customize the log directory with:

```bash
export LINUX_MCP_LOG_DIR=/path/to/your/logs
```

## Example Log Output

### Human-Readable Format (INFO level)

```
2025-10-10 15:30:45.123 | INFO | linux_mcp_server.audit | TOOL_CALL: list_directories | path=/home/user, order_by=size, sort=descending, top_n=10 | event=TOOL_CALL | tool=list_directories | execution_mode=local
2025-10-10 15:30:45.456 | INFO | linux_mcp_server.audit | TOOL_COMPLETE: list_directories | event=TOOL_COMPLETE | tool=list_directories | status=success | duration=0.333s
```

### Human-Readable Format (DEBUG level - shows command execution)

```
2025-10-10 15:30:45.123 | INFO | linux_mcp_server.audit | TOOL_CALL: list_directories | path=/home/user, order_by=size, sort=descending, top_n=10 | event=TOOL_CALL | tool=list_directories | execution_mode=local
2025-10-10 15:30:45.234 | DEBUG | linux_mcp_server.connection.ssh| LOCAL_EXEC completed: du -b --max-depth=1 /home/user | exit_code=0 | duration=0.200s
2025-10-10 15:30:45.456 | INFO | linux_mcp_server.audit | TOOL_COMPLETE: list_directories | event=TOOL_COMPLETE | tool=list_directories | status=success | duration=0.333s
```

### JSON Format

```json
{
  "timestamp": "2025-10-10T15:30:45",
  "level": "INFO",
  "logger": "linux_mcp_server.audit",
  "message": "TOOL_CALL: list_directories | path=/home/user, order_by=size, sort=descending, top_n=10",
  "event": "TOOL_CALL",
  "tool": "list_directories",
  "execution_mode": "local"
}
```

## Implementation

Logging is centralized in `src/linux_mcp_server/audit.py` using the `log_tool_call()` decorator.

```python
@mcp.tool()
@log_tool_call
async def list_directories(path: str, order_by: OrderBy, sort: SortBy, top_n: int | None) -> list[DirectoryEntry]:
    ...
```

The `audit.py` module provides structured logging functions:
- `log_tool_call()`: Logs tool invocation with parameters
- `log_ssh_connect()`: Logs SSH connection events
- `log_ssh_command()`: Logs remote command execution

## Log Levels

### INFO Level
- Tool invocations with parameters
- Tool completion with status and timing
- SSH connection success/failure
- Remote command execution

### DEBUG Level
- Detailed command execution timing
- SSH connection pool state
- Local command execution details
- All INFO level events plus detailed diagnostics

## Benefits

1. **Centralized Logging**: All logging happens in one place (server.py + audit.py)
2. **Structured Data**: Both human-readable and JSON formats available
3. **Audit Trail**: Complete record of all operations with timing
4. **SSH Monitoring**: Track remote connections and command execution
5. **Performance Insights**: Execution duration for every tool call

## Use Cases

- **Debugging**: Track tool invocations and identify issues
- **Auditing**: Complete record of all operations
- **Performance**: Monitor execution times
- **SSH Troubleshooting**: Debug connection and authentication issues
- **Development**: Understand tool behavior during testing

