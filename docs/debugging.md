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

By default (`LINUX_MCP_LOG_OUTPUT=files`), logs are written to two files and also emitted as human-readable text on stderr:

1. **Human-readable**: `~/.local/share/linux-mcp-server/logs/server.log`
2. **JSON format**: `~/.local/share/linux-mcp-server/logs/server.json`

You can customize the log directory with:

```bash
export LINUX_MCP_LOG_DIR=/path/to/your/logs
```

### Stream output

For an HTTP server running in a container, emit JSON logs directly to stdout:

```bash
export LINUX_MCP_TRANSPORT=http
export LINUX_MCP_LOG_OUTPUT=stdout
export LINUX_MCP_LOG_FORMAT=json
```

The `streamable-http` transport also supports stdout logging.

For stdio transport, use `LINUX_MCP_LOG_OUTPUT=stderr` instead: stdout is reserved for MCP
protocol messages, and configuring stdout logging with stdio is rejected.

Stream output creates no log directory or files and emits each record once.
`LINUX_MCP_LOG_DIR` and `LINUX_MCP_LOG_RETENTION_DAYS` apply only to file output.
`LINUX_MCP_LOG_FORMAT=text` (the default) gives human-readable stream output; `json` emits
one JSON object per line. The format option has no effect in file mode, which
always writes both formats and uses text on stderr.

JSON records have a UTC `timestamp`, `level`, `logger`, and `message`. Custom
fields are nested under `attributes`, which is omitted when empty. Exceptions
are included in an optional `exception` field. Multiline messages and tracebacks
are escaped within the JSON string, preserving one physical line per record.

## Audit Events

Each tool invocation has a server-generated `call_id`. Use it to follow a call
from `TOOL_CALL` through gatekeeper decisions and command execution to
`TOOL_COMPLETE`, including authorization or validation failures. Events carry
the tool name, resolved host, verified identity claims, and HTTP client IP when
available. For HTTP, the client IP is the immediate requestor's address unless
an allowed proxy supplies `X-Forwarded-For`. `FORWARDED_ALLOW_IPS` controls which
proxies are allowed; the default is loopback addresses.

| Event | Fields and meaning |
| --- | --- |
| `TOOL_CALL` | Sanitized `parameters`, including nested values. Hosts for stored scripts come from their stored details. |
| `TOOL_COMPLETE` | `status`, `duration_ms`, and `error` on failure. Timing includes authorization and execution. |
| `GATEKEEPER_RESULT` | Parsed `status` and `explanation`, including early rejections and revalidation. Model failures have status `error` and an `error` message. |
| `SSH_CONNECT` | Successful new SSH connection, with `host`, `username`, and `key_path`. |
| `SSH_AUTH_FAILED` | Failed SSH connection, with `host` and `error`. |
| `COMMAND_COMPLETE` | `command`, `host`, `status`, `duration_ms`, and either `exit_status` or `error` on execution failure. Same fields for local and SSH commands. |

A command's nonzero exit status or error does not necessarily cause the tool to
fail. A tool may try a fallback command, skip a missing optional command, or
return an error message as its normal result. `TOOL_COMPLETE` describes whether
the tool call returned normally, raised an error, or was cancelled.

Sensitive parameter and claim keys (such as passwords and tokens) are redacted.
Bearer credentials and the injected tool context are not recorded. Script
bodies and ordinary argument values are logged as supplied.

### Text format

A stdio call to list services on a remote host:

```text
2026-09-24T15:00:00Z | INFO | linux_mcp_server.audit | TOOL_CALL: Tool called | call_id=bc769d24-5c4a-45cb-9c54-02abceef306a | tool=list_services | host=server1 | parameters={"host":"server1"}
2026-09-24T15:00:00Z | INFO | linux_mcp_server.audit | COMMAND_COMPLETE: Command completed | call_id=bc769d24-5c4a-45cb-9c54-02abceef306a | tool=list_services | host=server1 | command="systemctl list-units --type=service --all --no-pager" | exit_status=0 | status=success | duration_ms=84.2
2026-09-24T15:00:00Z | INFO | linux_mcp_server.audit | COMMAND_COMPLETE: Command completed | call_id=bc769d24-5c4a-45cb-9c54-02abceef306a | tool=list_services | host=server1 | command="systemctl list-units --type=service --state=running --no-pager" | exit_status=0 | status=success | duration_ms=72.1
2026-09-24T15:00:00Z | INFO | linux_mcp_server.audit | TOOL_COMPLETE: Tool completed | call_id=bc769d24-5c4a-45cb-9c54-02abceef306a | tool=list_services | host=server1 | status=success | duration_ms=158.4
```

Fields appear once as `key=value`. Strings containing whitespace, quotes, or
field delimiters are quoted; newlines are escaped. Nested objects use compact
JSON. Timestamps are UTC, and each record occupies one physical line.

### JSON format

```json
{
  "timestamp": "2026-09-24T15:00:00Z",
  "level": "INFO",
  "logger": "linux_mcp_server.audit",
  "message": "Command completed",
  "event": "COMMAND_COMPLETE",
  "attributes": {
    "call_id": "bc769d24-5c4a-45cb-9c54-02abceef306a",
    "tool": "list_services",
    "host": "server1",
    "command": "systemctl list-units --type=service --all --no-pager",
    "status": "success",
    "exit_status": 0,
    "duration_ms": 84.2
  }
}
```

The example is expanded for readability; emitted JSON is one object per line.
Primary audit records have a stable top-level `event`. Ordinary application and
library messages use the same envelope without an event. Their custom fields
stay under `attributes`, including any library field named `event`. Diagnostic
messages emitted during a tool call also receive its request context.

## Implementation

Tool lifecycle events are emitted by the authorization middleware. `audit.py`
provides `audit_context()` to add context fields and `log_event()` to log events.

## Log Levels

The default `LINUX_MCP_LOG_LEVEL=default` records INFO and above for
linux-mcp-server itself, but WARNING and above for libraries it depends upon.
Routine messages from those libraries, such as HTTP access logs and SSH
connection details, are suppressed.

An explicit level applies to both application and dependency logs. For example,
`LINUX_MCP_LOG_LEVEL=INFO` includes dependency INFO messages, and
`LINUX_MCP_LOG_LEVEL=DEBUG` enables debug output from both. `WARNING`, `ERROR`,
and `CRITICAL` can be used to restrict all logs to those levels and above.
Values are case-insensitive.

### INFO Level

- Tool invocation and completion, with parameters, status, and timing
- Gatekeeper decisions
- Successful SSH connections
- Local and remote command results, with timing

