"""Service management tools."""

import typing as t

from .ssh_executor import execute_command
from .validation import validate_line_count


async def list_services(
    host: t.Optional[str] = None,
    username: t.Optional[str] = None,
) -> str:
    """
    List all systemd services.

    Args:
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)

    Returns:
        Formatted string with service list
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


async def get_service_status(
    service_name: str,
    host: t.Optional[str] = None,
    username: t.Optional[str] = None,
) -> str:
    """
    Get status of a specific service.

    Args:
        service_name: Name of the service
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)

    Returns:
        Formatted string with service status
    """
    try:
        # Ensure service name has .service suffix if not present
        if not service_name.endswith(".service") and "." not in service_name:
            service_name = f"{service_name}.service"

        # Run systemctl status
        returncode, stdout, stderr = await execute_command(
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


async def get_service_logs(
    service_name: str,
    lines: int = 50,
    host: t.Optional[str] = None,
    username: t.Optional[str] = None,
) -> str:
    """
    Get logs for a specific service.

    Args:
        service_name: Name of the service
        lines: Number of log lines to retrieve (default: 50)
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)

    Returns:
        Formatted string with service logs
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
