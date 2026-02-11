"""Log and audit tools."""

import typing as t

from pathlib import Path

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from pydantic.functional_validators import BeforeValidator

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.config import CONFIG
from linux_mcp_server.models import JournalLogs
from linux_mcp_server.models import LogFile
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import StrEnum
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import is_empty_output
from linux_mcp_server.utils.validation import validate_path


class Transport(StrEnum):
    """Valid journalctl transport types for filtering journal entries.

    Transports identify the source/mechanism that submitted log messages to the journal.

    AUDIT - Linux audit subsystem messages (security events, syscall auditing)
    DRIVER - Kernel driver messages logged via dev_printk().
    JOURNAL - Messages logged directly to the journal via sd_journal_* APIs.
    KERNEL - Kernel ring buffer messages (dmesg/printk).
    STDOUT - stdout/stderr from services with StandardOutput/StandardError=journal.
    SYSLOG - Messages received via the syslog socket (/dev/log).
    """

    AUDIT = "audit"
    DRIVER = "driver"
    JOURNAL = "journal"
    KERNEL = "kernel"
    STDOUT = "stdout"
    SYSLOG = "syslog"


async def _get_journal_logs(
    lines: int,
    host: Host | None = None,
    unit: str | None = None,
    priority: str | None = None,
    since: str | None = None,
    transport: Transport | None = None,
) -> tuple[int, str, str]:
    """Execute journalctl command with optional filters.

    Args:
        lines: Number of log lines to retrieve.
        host: Optional remote host address.
        unit: Filter by systemd unit name.
        priority: Filter by priority level.
        since: Filter entries since specified time.
        transport: Filter by journal transport.

    Returns:
        Tuple of (returncode, stdout, stderr) from the command execution.

    Raises:
        FileNotFoundError: If journalctl command is not available.
    """

    cmd = get_command("journal_logs")
    return await cmd.run(
        host=host,
        lines=lines,
        unit=unit,
        priority=priority,
        since=since,
        transport=transport,
    )


@mcp.tool(
    title="Get journal logs",
    description="Get systemd journal logs.",
    tags={"journal", "logs", "systemd", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_journal_logs(
    unit: t.Annotated[
        str | None,
        Field(
            description="Filter by systemd unit name or pattern",
            examples=["sshd.service", "nginx", "httpd", "systemd-*", "audit*"],
        ),
    ] = None,
    priority: t.Annotated[
        str | None,
        Field(
            description="Filter by syslog priority level (0-7), name, or range",
            examples=["err", "warning", "info", "debug", "3", "err..warning"],
        ),
    ] = None,
    since: t.Annotated[
        str | None,
        Field(
            description="Filter entries since specified time (absolute or relative)",
            examples=["today", "yesterday", "-1h", "-30m", "-7d", "2025-01-15 10:00:00"],
        ),
    ] = None,
    transport: t.Annotated[
        Transport | None,
        "Filter by journal transport (e.g., 'audit' for audit logs, 'kernel' for kernel messages, 'syslog' for syslog messages)",
    ] = None,
    lines: t.Annotated[int, Field(description="Number of log lines to retrieve. Default: 100", ge=1, le=10_000)] = 100,
    host: Host = None,
) -> JournalLogs:
    """Get systemd journal logs.

    Retrieves entries from the systemd journal with optional filtering by unit,
    priority level, time range, and transport. Returns timestamped log messages.

    To get audit logs, use transport='audit'.
    """
    returncode, stdout, stderr = await _get_journal_logs(
        lines=lines, host=host, unit=unit, priority=priority, since=since, transport=transport
    )

    if returncode != 0:
        raise ToolError(f"Error reading journal logs: {stderr}")

    if is_empty_output(stdout):
        raise ToolError("No journal entries found matching the criteria.")

    entries = [line for line in stdout.strip().splitlines() if line]

    return JournalLogs(
        entries=entries,
        unit=unit,
        priority=priority,
        since=since,
        transport=transport,
    )


@mcp.tool(
    title="Read log file",
    description="Read a specific log file.",
    tags={"files", "logs", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def read_log_file(
    log_path: t.Annotated[
        Path,
        BeforeValidator(validate_path),
        Field(
            description="Absolute path to the log file (must be in allowed list)",
            examples=["/var/log/messages", "/var/log/secure", "/var/log/audit/audit.log", "/var/log/dnf.log"],
        ),
    ],
    lines: t.Annotated[int, Field(description="Number of lines to retrieve from the end.", ge=1, le=10_000)] = 100,
    host: Host = None,
) -> LogFile:
    """Read a specific log file.

    Retrieves the last N lines from a log file. The file path must be in the
    allowed list configured via LINUX_MCP_ALLOWED_LOG_PATHS environment variable.
    """
    # Get allowed log paths from environment variable
    allowed_paths_env = CONFIG.allowed_log_paths

    if not allowed_paths_env:
        raise ToolError(
            "No log files are allowed. Set LINUX_MCP_ALLOWED_LOG_PATHS environment variable "
            "with comma-separated list of allowed log file paths."
        )

    allowed_paths = [Path(p.strip()) for p in allowed_paths_env.split(",") if p.strip()]

    if not host:
        # For local execution, resolve and check against allowlist
        requested_path = log_path.resolve()

        is_allowed = False
        for allowed_path in allowed_paths:
            allowed_resolved = Path(allowed_path).resolve()
            if requested_path == allowed_resolved:
                is_allowed = True
                break

        if not is_allowed:
            raise ToolError(f"Access to log file '{log_path}' is not allowed.")

        if not requested_path.exists():
            raise ToolError(f"Log file not found: {log_path}")

        if not requested_path.is_file():
            raise ToolError(f"Path is not a file: {log_path}")

        log_path_str = str(requested_path)
    else:
        # For remote execution, check against allowlist without resolving
        if log_path not in allowed_paths:
            raise ToolError(f"Access to log file '{log_path}' is not allowed.")

        log_path_str = str(log_path)

    cmd = get_command("read_log_file")
    returncode, stdout, stderr = await cmd.run(host=host, lines=lines, log_path=log_path_str)

    if returncode != 0:
        if "Permission denied" in stderr:
            raise ToolError(f"Permission denied reading log file: {log_path}")

        raise ToolError(f"Error reading log file: {stderr}")

    if is_empty_output(stdout):
        raise ToolError(f"Log file is empty: {log_path}")

    entries = [line for line in stdout.strip().splitlines() if line]

    return LogFile(entries=entries, path=log_path)
