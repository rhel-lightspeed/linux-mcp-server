# Debug Logging for Tool Outputs

This document describes how to enable and use debug logging to see what content the MCP tools are returning to the LLM.

## Overview

All tool functions are decorated with `@log_tool_output`, which automatically logs:
- The function name
- All input parameters (excluding None values)
- The full content being returned to the LLM

This logging is **only active when DEBUG level is enabled** and provides complete visibility into tool outputs without code duplication.

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

### Human-Readable Format

```
2025-10-10 15:30:45.123 | DEBUG | linux_mcp_server.tools.storage | list_directories_by_size returning content | function=list_directories_by_size | path=/home/user | top_n=10 | content==== Top 10 Largest Directories ===
Path: /home/user

Total subdirectories found: 15

1. Documents
   Size: 2.3GB
2. Videos
   Size: 1.8GB
...
```

### JSON Format

```json
{
  "timestamp": "2025-10-10T15:30:45.123456Z",
  "level": "DEBUG",
  "logger": "linux_mcp_server.tools.storage",
  "message": "list_directories_by_size returning content",
  "function": "list_directories_by_size",
  "path": "/home/user",
  "top_n": 10,
  "content": "=== Top 10 Largest Directories ===\nPath: /home/user\n\nTotal subdirectories found: 15\n\n1. Documents\n   Size: 2.3GB\n2. Videos\n   Size: 1.8GB\n..."
}
```

## Implementation

The debug logging is implemented using a decorator pattern in `src/linux_mcp_server/tools/decorators.py`:

```python
@log_tool_output
async def list_directories_by_size(
    path: str,
    top_n: int,
    host: Optional[str] = None,
    username: Optional[str] = None
) -> str:
    # Function implementation...
    return result
```

The decorator:
- Automatically captures all function parameters
- Logs the full return value (no truncation)
- Only executes when DEBUG level is enabled (zero overhead otherwise)
- Works with both sync and async functions

## Benefits

1. **No Code Duplication**: Single decorator applied to all tools
2. **Full Visibility**: Complete output logging without truncation
3. **Easy Maintenance**: Changes to logging behavior happen in one place
4. **Performance**: Zero overhead when DEBUG is not enabled
5. **Structured Data**: Both human-readable and JSON formats available

## Use Cases

- **Debugging**: See exactly what data the LLM receives
- **Auditing**: Track all tool invocations and outputs
- **Development**: Understand tool behavior during testing
- **Troubleshooting**: Diagnose issues with tool responses

