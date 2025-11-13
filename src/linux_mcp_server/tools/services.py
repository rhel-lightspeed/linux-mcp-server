"""Service management tools."""

import typing as t

from mcp.types import ToolAnnotations

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.types import Username
from linux_mcp_server.utils.validation import validate_line_count


@mcp.tool(
    title="List services",
    description="List all systemd services.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def list_services(
    host: Host | None = None,
    username: Username | None = None,
) -> str:
    """
    List all systemd services.
    """
    try:
        # Run systemctl to list all services
        returncode, stdout, stderr = await execute_command(
            ["systemctl", "list-units", "--type=service", "--all", "--no-pager"],
            host=host,
            username=username,
        )

        if returncode != 0:
            return f"Error listing services: {stderr}"

        # Format the output
        result = ["=== System Services ===\n"]
        result.append(stdout)

        # Get summary
        returncode_summary, stdout_summary, _ = await execute_command(
            ["systemctl", "list-units", "--type=service", "--state=running", "--no-pager"],
            host=host,
            username=username,
        )

        if returncode_summary == 0:
            running_count = len([line for line in stdout_summary.split("\n") if ".service" in line])
            result.append(f"\n\nSummary: {running_count} services currently running")

        return "\n".join(result)
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
async def get_service_status(
    service_name: t.Annotated[str, "Name of the service"],
    host: Host | None = None,
    username: Username | None = None,
) -> str:
    """
    Get status of a specific service.
    """
    try:
        # Ensure service name has .service suffix if not present
        if not service_name.endswith(".service") and "." not in service_name:
            service_name = f"{service_name}.service"

        # Run systemctl status
        _, stdout, stderr = await execute_command(
            ["systemctl", "status", service_name, "--no-pager", "--full"],
            host=host,
            username=username,
        )

        # Note: systemctl status returns non-zero for inactive services, but that's expected
        if not stdout and stderr:
            # Service not found
            if "not found" in stderr.lower() or "could not be found" in stderr.lower():
                return f"Service '{service_name}' not found on this system."
            return f"Error getting service status: {stderr}"

        result = [f"=== Status of {service_name} ===\n"]
        result.append(stdout)

        return "\n".join(result)
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
async def get_service_logs(
    service_name: t.Annotated[str, "Name of the service"],
    lines: t.Annotated[int, "Number of log lines to retrieve."] = 50,
    host: Host | None = None,
    username: Username | None = None,
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

        # Run journalctl for the service
        returncode, stdout, stderr = await execute_command(
            ["journalctl", "-u", service_name, "-n", str(lines), "--no-pager"],
            host=host,
            username=username,
        )

        if returncode != 0:
            if "not found" in stderr.lower() or "no entries" in stderr.lower():
                return f"No logs found for service '{service_name}'. The service may not exist or has no log entries."
            return f"Error getting service logs: {stderr}"

        if not stdout or stdout.strip() == "":
            return f"No log entries found for service '{service_name}'."

        result = [f"=== Last {lines} log entries for {service_name} ===\n"]
        result.append(stdout)

        return "\n".join(result)
    except FileNotFoundError:
        return "Error: journalctl command not found. This tool requires systemd."
    except Exception as e:
        return f"Error getting service logs: {str(e)}"
