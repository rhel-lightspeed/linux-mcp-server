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
2025-10-10 15:30:45.123 | INFO | linux_mcp_server.audit | TOOL_CALL: list_directories_by_size | path=/home/user, top_n=10 | event=TOOL_CALL | tool=list_directories_by_size | execution_mode=local
2025-10-10 15:30:45.456 | INFO | linux_mcp_server.audit | TOOL_COMPLETE: list_directories_by_size | event=TOOL_COMPLETE | tool=list_directories_by_size | status=success | duration=0.333s
```

### Human-Readable Format (DEBUG level - shows command execution)

```
2025-10-10 15:30:45.123 | INFO | linux_mcp_server.audit | TOOL_CALL: list_directories_by_size | path=/home/user, top_n=10 | event=TOOL_CALL | tool=list_directories_by_size | execution_mode=local
2025-10-10 15:30:45.234 | DEBUG | linux_mcp_server.tools.ssh_executor | LOCAL_EXEC completed: du -b --max-depth=1 /home/user | exit_code=0 | duration=0.200s
2025-10-10 15:30:45.456 | INFO | linux_mcp_server.audit | TOOL_COMPLETE: list_directories_by_size | event=TOOL_COMPLETE | tool=list_directories_by_size | status=success | duration=0.333s
```

### JSON Format

```json
{
  "timestamp": "2025-10-10T15:30:45",
  "level": "INFO",
  "logger": "linux_mcp_server.audit",
  "message": "TOOL_CALL: list_directories_by_size | path=/home/user, top_n=10",
  "event": "TOOL_CALL",
  "tool": "list_directories_by_size",
  "execution_mode": "local"
}
```

## Implementation

Logging is centralized in `src/linux_mcp_server/server.py` using the `_execute_tool()` helper:

```python
async def _execute_tool(tool_name: str, handler, **kwargs):
    """Execute a tool with logging and error handling."""
    log_tool_call(tool_name, kwargs)  # Log invocation
    
    start_time = time.time()
    try:
        result = await handler(**kwargs)
        duration = time.time() - start_time
        log_tool_complete(tool_name, status=Status.success, duration=duration)
        return result
    except Exception as e:
        duration = time.time() - start_time
        log_tool_complete(tool_name, status="error", duration=duration, error=str(e))
        raise
```

All tools are registered using FastMCP decorators:
```python
@mcp.tool()
async def list_directories_by_size(path: str, top_n: int, ...) -> str:
    return await _execute_tool("list_directories_by_size", 
                               storage.list_directories_by_size,
                               path=path, top_n=top_n, ...)
```

The `audit.py` module provides structured logging functions:
- `log_tool_call()`: Logs tool invocation with parameters
- `log_tool_complete()`: Logs completion with timing and status
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

