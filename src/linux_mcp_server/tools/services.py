"""Service management tools."""

import typing as t

from mcp.types import ToolAnnotations
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import CommandSpec
from linux_mcp_server.commands import get_command
from linux_mcp_server.commands import substitute_command_args
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.formatters import format_service_logs
from linux_mcp_server.formatters import format_service_status
from linux_mcp_server.formatters import format_services_list
from linux_mcp_server.parsers import parse_service_count
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import validate_line_count


@mcp.tool(
    title="List services",
    description="List all systemd services.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_services(
    host: Host | None = None,
    list_cmd: t.Annotated[CommandSpec, Field(description="Ignore this parameter")] = get_command("list_services"),
    running_cmd: t.Annotated[CommandSpec, Field(description="Ignore this parameter")] = get_command("running_services"),
) -> str:
    """
    List all systemd services.
    """
    try:
        returncode, stdout, stderr = await execute_command(list_cmd.args, host=host)

        if returncode != 0:
            return f"Error listing services: {stderr}"

        # Get running services count
        returncode_summary, stdout_summary, _ = await execute_command(
            running_cmd.args,
            host=host,
        )

        running_count = None
        if returncode_summary == 0:
            running_count = parse_service_count(stdout_summary)

        return format_services_list(stdout, running_count)
    except FileNotFoundError:
        return "Error: systemctl command not found. This tool requires systemd."
    except Exception as e:
        return f"Error listing services: {str(e)}"


@mcp.tool(
    title="Get service status",
    description="Get detailed status of a specific systemd service.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_service_status(
    service_name: t.Annotated[str, Field(description="Name of the service")],
    host: Host | None = None,
    cmd: t.Annotated[CommandSpec, Field(description="Ignore this parameter")] = get_command("service_status"),
) -> str:
    """
    Get status of a specific service.
    """
    try:
        # Ensure service name has .service suffix if not present
        if not service_name.endswith(".service") and "." not in service_name:
            service_name = f"{service_name}.service"

        args = substitute_command_args(cmd.args, service_name=service_name)

        _, stdout, stderr = await execute_command(args, host=host)

        # Note: systemctl status returns non-zero for inactive services, but that's expected
        if not stdout and stderr:
            # Service not found
            if "not found" in stderr.lower() or "could not be found" in stderr.lower():
                return f"Service '{service_name}' not found on this system."
            return f"Error getting service status: {stderr}"

        return format_service_status(stdout, service_name)
    except FileNotFoundError:
        return "Error: systemctl command not found. This tool requires systemd."
    except Exception as e:
        return f"Error getting service status: {str(e)}"


@mcp.tool(
    title="Get service logs",
    description="Get recent logs for a specific systemd service.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_service_logs(
    service_name: t.Annotated[str, Field(description="Name of the service")],
    lines: t.Annotated[int, Field(description="Number of log lines to retrieve.")] = 50,
    host: Host | None = None,
    cmd: t.Annotated[CommandSpec, Field(description="Ignore this parameter")] = get_command("service_logs"),
) -> str:
    """
    Get logs for a specific service.
    """
    try:
        # Validate lines parameter (accepts floats from LLMs)
        lines, _ = validate_line_count(lines, default=50)

        # Ensure service name has .service suffix if not present
        if not service_name.endswith(".service") and "." not in service_name:
            service_name = f"{service_name}.service"

        args = substitute_command_args(cmd.args, service_name=service_name, lines=lines)

        returncode, stdout, stderr = await execute_command(args, host=host)

        if returncode != 0:
            if "not found" in stderr.lower() or "no entries" in stderr.lower():
                return f"No logs found for service '{service_name}'. The service may not exist or has no log entries."
            return f"Error getting service logs: {stderr}"

        if not stdout or stdout.strip() == "":
            return f"No log entries found for service '{service_name}'."

        return format_service_logs(stdout, service_name, lines)
    except FileNotFoundError:
        return "Error: journalctl command not found. This tool requires systemd."
    except Exception as e:
        return f"Error getting service logs: {str(e)}"
