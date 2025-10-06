"""Service management tools."""

import subprocess
import asyncio

from .validation import validate_line_count


async def list_services() -> str:
    """List all systemd services."""
    try:
        # Run systemctl to list all services
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "list-units", "--type=service", "--all", "--no-pager",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            return f"Error listing services: {stderr.decode()}"
        
        output = stdout.decode()
        
        # Format the output
        lines = output.strip().split('\n')
        result = ["=== System Services ===\n"]
        
        # Add the output from systemctl
        result.append(output)
        
        # Get summary
        proc_summary = await asyncio.create_subprocess_exec(
            "systemctl", "list-units", "--type=service", "--state=running", "--no-pager",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout_summary, _ = await proc_summary.communicate()
        running_count = len([l for l in stdout_summary.decode().split('\n') if '.service' in l])
        
        result.append(f"\n\nSummary: {running_count} services currently running")
        
        return "\n".join(result)
    except FileNotFoundError:
        return "Error: systemctl command not found. This tool requires systemd."
    except Exception as e:
        return f"Error listing services: {str(e)}"


async def get_service_status(service_name: str) -> str:
    """Get status of a specific service."""
    try:
        # Ensure service name has .service suffix if not present
        if not service_name.endswith('.service') and '.' not in service_name:
            service_name = f"{service_name}.service"
        
        # Run systemctl status
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "status", service_name, "--no-pager", "--full",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        # Note: systemctl status returns non-zero for inactive services, but that's expected
        output = stdout.decode()
        
        if not output and stderr:
            # Service not found
            error_msg = stderr.decode()
            if "not found" in error_msg.lower() or "could not be found" in error_msg.lower():
                return f"Service '{service_name}' not found on this system."
            return f"Error getting service status: {error_msg}"
        
        result = [f"=== Status of {service_name} ===\n"]
        result.append(output)
        
        return "\n".join(result)
    except FileNotFoundError:
        return "Error: systemctl command not found. This tool requires systemd."
    except Exception as e:
        return f"Error getting service status: {str(e)}"


async def get_service_logs(service_name: str, lines: int = 50) -> str:
    """Get logs for a specific service."""
    try:
        # Validate lines parameter (accepts floats from LLMs)
        lines, _ = validate_line_count(lines, default=50)
        
        # Ensure service name has .service suffix if not present
        if not service_name.endswith('.service') and '.' not in service_name:
            service_name = f"{service_name}.service"
        
        # Run journalctl for the service
        proc = await asyncio.create_subprocess_exec(
            "journalctl", "-u", service_name, "-n", str(lines), "--no-pager",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            error_msg = stderr.decode()
            if "not found" in error_msg.lower() or "no entries" in error_msg.lower():
                return f"No logs found for service '{service_name}'. The service may not exist or has no log entries."
            return f"Error getting service logs: {error_msg}"
        
        output = stdout.decode()
        
        if not output or output.strip() == "":
            return f"No log entries found for service '{service_name}'."
        
        result = [f"=== Last {lines} log entries for {service_name} ===\n"]
        result.append(output)
        
        return "\n".join(result)
    except FileNotFoundError:
        return "Error: journalctl command not found. This tool requires systemd."
    except Exception as e:
        return f"Error getting service logs: {str(e)}"

