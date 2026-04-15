"""Service management tools."""

import json
import typing as t

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.models import LogEntries
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import is_empty_output


@mcp.tool(
    title="List services",
    description="List all systemd services.",
    tags={"services", "systemd"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_services(
    host: Host = None,
) -> list[dict[str, str]]:
    """List all systemd services.

    Retrieves all systemd service units with their load state, active state,
    sub-state, and description.

    Returns:
        list[dict[str, str]]: A list of dictionaries containing information about each service.

    Raises:
        ToolError: If an error occurs while listing services.
    """
    cmd = get_command("list_services")
    returncode, stdout, stderr = await cmd.run(host=host)

    if returncode != 0:
        raise ToolError(f"Error listing services: {stderr}")

    return t.cast(list[dict[str, str]], json.loads(stdout))


@mcp.tool(
    title="Get service status",
    description="Get detailed status of a specific systemd service.",
    tags={"services", "systemd"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_service_status(
    service_name: t.Annotated[
        str,
        Field(
            description="Name of the systemd service",
            examples=["sshd", "NetworkManager", "auditd", "rsyslog", "crond", "firewalld"],
        ),
    ],
    host: Host = None,
) -> str:
    """Get status of a specific systemd service.

    Retrieves detailed service information including active/enabled state,
    main PID, memory usage, etc.

    Returns:
        A string containing the output of the systemctl status command.

    Raises:
        ToolError: If there was an error getting the service status.
    """
    # Ensure service name has .service suffix if not present
    if not service_name.endswith(".service") and "." not in service_name:
        service_name = f"{service_name}.service"

    cmd = get_command("service_status")
    returncode, stdout, stderr = await cmd.run(host=host, service_name=service_name)

    # systemctl status uses exit status 4 when the unit does not exist (see systemctl(1)).
    # This is stable across locales; stderr text alone may be translated.
    if returncode == 4:
        raise ToolError(f"Service '{service_name}' not found on this system.")

    # Note: systemctl status returns non-zero for inactive services, but that's expected
    if not stdout and stderr:
        # Service not found
        if "not found" in stderr.lower() or "could not be found" in stderr.lower():
            raise ToolError(f"Service '{service_name}' not found on this system.")
        raise ToolError(f"Error getting service status: {stderr}")

    return stdout


@mcp.tool(
    title="Get service logs",
    description="Get recent logs for a specific systemd service.",
    tags={"logs", "services", "systemd", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_service_logs(
    service_name: t.Annotated[
        str,
        Field(
            description="Name of the systemd service",
            examples=["sshd", "NetworkManager", "auditd", "rsyslog", "crond", "firewalld"],
        ),
    ],
    lines: t.Annotated[int, Field(description="Number of log lines to retrieve.", ge=1, le=10_000)] = 50,
    host: Host = None,
) -> LogEntries:
    """Get recent logs for a specific systemd service.

    Retrieves journal lines for the specified service unit (default journalctl
    short format, same style as get_journal_logs).

    Raises:
        ToolError: If journal output is empty, or journalctl fails.

    Returns:
        LogEntries: Structured log lines, unit name, and line count.
    """
    # Ensure service name has .service suffix if not present
    if not service_name.endswith(".service") and "." not in service_name:
        service_name = f"{service_name}.service"

    cmd = get_command("service_logs")
    returncode, stdout, stderr = await cmd.run(host=host, service_name=service_name, lines=lines)

    if returncode != 0:
        raise ToolError(f"Error getting service logs: {stderr}")

    if is_empty_output(stdout):
        raise ToolError(f"No log entries found for service '{service_name}'.")

    entries = [line for line in stdout.strip().splitlines() if line]

    return LogEntries(entries=entries, unit=service_name)
