"""Log and audit tools."""

import os
import typing as t

from pathlib import Path

from mcp.types import ToolAnnotations
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import validate_line_count


@mcp.tool(
    title="Get journal logs",
    description="Get systemd journal logs.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_journal_logs(
    unit: t.Annotated[
        str | None, Field(description="Filter by systemd unit name or pattern (e.g., 'nginx.service', 'ssh*')")
    ] = None,
    priority: t.Annotated[
        str | None,
        Field(
            description="Filter by priority. Possible values: priority level (0-7), syslog level name ('emerg' to 'debug'), or range (e.g., 'err..info')"
        ),
    ] = None,
    since: t.Annotated[
        str | None,
        Field(
            description="Filter entries since specified time. Date/time filter (format: 'YYYY-MM-DD HH:MM:SS', 'today', 'yesterday', 'now', or relative like '-1h')"
        ),
    ] = None,
    lines: t.Annotated[int, Field(description="Number of log lines to retrieve. Default: 100")] = 100,
    host: Host | None = None,
) -> str:
    """
    Get systemd journal logs.
    """
    try:
        # Validate lines parameter (accepts floats from LLMs)
        lines, _ = validate_line_count(lines, default=100)

        cmd = ["journalctl", "-n", str(lines), "--no-pager"]

        if unit:
            cmd.extend(["-u", unit])

        if priority:
            cmd.extend(["-p", priority])

        if since:
            cmd.extend(["--since", since])

        returncode, stdout, stderr = await execute_command(cmd, host=host)

        if returncode != 0:
            return f"Error reading journal logs: {stderr}"

        if not stdout or stdout.strip() == "":
            return "No journal entries found matching the criteria."

        # Build filter description
        filters = []
        if unit:
            filters.append(f"unit={unit}")
        if priority:
            filters.append(f"priority={priority}")
        if since:
            filters.append(f"since={since}")

        filter_desc = ", ".join(filters) if filters else "no filters"

        result = [f"=== Journal Logs (last {lines} entries, {filter_desc}) ===\n"]
        result.append(stdout)

        return "\n".join(result)
    except FileNotFoundError:
        return "Error: journalctl command not found. This tool requires systemd."
    except Exception as e:
        return f"Error reading journal logs: {str(e)}"


@mcp.tool(
    title="Get audit logs",
    description="Read the system audit logs. This requires root privileges.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_audit_logs(
    lines: t.Annotated[int, Field(description="Number of log lines to retrieve.")] = 100,
    host: Host | None = None,
) -> str:
    """
    Get audit logs.
    """
    # Validate lines parameter (accepts floats from LLMs)
    lines, _ = validate_line_count(lines, default=100)

    audit_log_path = "/var/log/audit/audit.log"

    try:
        # For local execution, check if file exists
        if not host and not os.path.exists(audit_log_path):
            return f"Audit log file not found at {audit_log_path}. Audit logging may not be enabled."

        # Use tail to read last N lines
        returncode, stdout, stderr = await execute_command(
            ["tail", "-n", str(lines), audit_log_path],
            host=host,
        )

        if returncode != 0:
            if "Permission denied" in stderr:
                return f"Permission denied reading audit logs. This tool requires elevated privileges (root) to read {audit_log_path}."
            return f"Error reading audit logs: {stderr}"

        if not stdout or stdout.strip() == "":
            return "No audit log entries found."

        result = [f"=== Audit Logs (last {lines} entries) ===\n"]
        result.append(stdout)

        return "\n".join(result)
    except FileNotFoundError:
        return "Error: tail command not found."
    except Exception as e:
        return f"Error reading audit logs: {str(e)}"


@mcp.tool(
    title="Read log file",
    description="Read a specific log file.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def read_log_file(  # noqa: C901
    log_path: t.Annotated[str, Field(description="Path to the log file")],
    lines: t.Annotated[int, Field(description="Number of lines to retrieve from the end.")] = 100,
    host: Host | None = None,
) -> str:
    """
    Read a specific log file.
    """
    try:
        # Validate lines parameter (accepts floats from LLMs)
        lines, _ = validate_line_count(lines, default=100)

        # Get allowed log paths from environment variable
        allowed_paths_env = os.getenv("LINUX_MCP_ALLOWED_LOG_PATHS", "")

        if not allowed_paths_env:
            return (
                "No log files are allowed. Set LINUX_MCP_ALLOWED_LOG_PATHS environment variable "
                "with comma-separated list of allowed log file paths."
            )

        allowed_paths = [p.strip() for p in allowed_paths_env.split(",") if p.strip()]

        # For local execution, validate path
        if not host:
            try:
                requested_path = Path(log_path).resolve()
            except Exception:
                return f"Invalid log file path: {log_path}"

            # Check if the requested path is in the allowed list
            is_allowed = False
            for allowed_path in allowed_paths:
                try:
                    allowed_resolved = Path(allowed_path).resolve()
                    if requested_path == allowed_resolved:
                        is_allowed = True
                        break
                except Exception:
                    continue

            if not is_allowed:
                return (
                    f"Access to log file '{log_path}' is not allowed.\n"
                    f"Allowed log files: {{', '.join(allowed_paths)}}"
                )  # nofmt

            # Check if file exists
            if not requested_path.exists():
                return f"Log file not found: {log_path}"

            if not requested_path.is_file():
                return f"Path is not a file: {log_path}"

            log_path_str = str(requested_path)
        else:
            # For remote execution, just check against whitelist without resolving
            if log_path not in allowed_paths:
                return (
                    f"Access to log file '{log_path}' is not allowed.\n"
                    f"Allowed log files: {', '.join(allowed_paths)}"
                )  # nofmt
            log_path_str = log_path

        # Read the file using tail
        returncode, stdout, stderr = await execute_command(
            ["tail", "-n", str(lines), log_path_str],
            host=host,
        )

        if returncode != 0:
            if "Permission denied" in stderr:
                return f"Permission denied reading log file: {log_path}"
            return f"Error reading log file: {stderr}"

        if not stdout or stdout.strip() == "":
            return f"Log file is empty: {log_path}"

        result = [f"=== Log File: {log_path} (last {lines} lines) ===\n"]
        result.append(stdout)

        return "\n".join(result)
    except FileNotFoundError:
        return "Error: tail command not found."
    except Exception as e:
        return f"Error reading log file: {str(e)}"
