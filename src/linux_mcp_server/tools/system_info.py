"""System information tools."""

from mcp.types import ToolAnnotations

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.commands import get_command_group
from linux_mcp_server.formatters import format_cpu_info
from linux_mcp_server.formatters import format_disk_usage
from linux_mcp_server.formatters import format_hardware_info
from linux_mcp_server.formatters import format_memory_info
from linux_mcp_server.formatters import format_system_info
from linux_mcp_server.parsers import parse_cpu_info
from linux_mcp_server.parsers import parse_free_output
from linux_mcp_server.parsers import parse_system_info
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import is_successful_output


@mcp.tool(
    title="Get system information",
    description="Get basic system information such as operating system, distribution, kernel version, uptime, and last boot time.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_system_information(
    host: Host = None,
) -> str:
    """Get basic system information.

    Retrieves hostname, OS name/version, kernel version, architecture,
    system uptime, and last boot time.
    """
    try:
        group = get_command_group("system_info")
        results = {}

        # Execute all commands in the group
        for name, cmd in group.commands.items():
            returncode, stdout, _ = await cmd.run(host=host)
            if is_successful_output(returncode, stdout):
                results[name] = stdout

        info = parse_system_info(results)
        return format_system_info(info)
    except Exception as e:
        return f"Error gathering system information: {str(e)}"


@mcp.tool(
    title="Get CPU information",
    description="Get CPU information.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_cpu_information(
    host: Host = None,
) -> str:
    """Get CPU information.

    Retrieves CPU model, core counts (logical and physical), frequency,
    and current load averages (1, 5, and 15 minute).
    """
    try:
        group = get_command_group("cpu_info")
        results = {}

        # Execute all commands in the group
        for name, cmd in group.commands.items():
            returncode, stdout, _ = await cmd.run(host=host)
            if is_successful_output(returncode, stdout):
                results[name] = stdout

        info = parse_cpu_info(results)
        return format_cpu_info(info)
    except Exception as e:
        return f"Error gathering CPU information: {str(e)}"


@mcp.tool(
    title="Get memory information",
    description="Get detailed memory including physical and swap.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_memory_information(
    host: Host = None,
) -> str:
    """Get memory information.

    Retrieves physical RAM and swap usage including total, used, free,
    shared, buffers, cached, and available memory.
    """
    try:
        # Execute free command
        free_cmd = get_command("memory_info", "free")
        returncode, stdout, _ = await free_cmd.run(host=host)

        if is_successful_output(returncode, stdout):
            memory = parse_free_output(stdout)
            return format_memory_info(memory)

        return "Error: Unable to retrieve memory information"
    except Exception as e:
        return f"Error gathering memory information: {str(e)}"


@mcp.tool(
    title="Get disk usage",
    description="Get detailed disk space information including size, mount points, and utilization.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_disk_usage(
    host: Host = None,
) -> str:
    """Get disk usage information.

    Retrieves filesystem usage for all mounted volumes including size,
    used/available space, utilization percentage, and mount points.
    """
    try:
        cmd = get_command("disk_usage")

        returncode, stdout, _ = await cmd.run(host=host)

        if is_successful_output(returncode, stdout):
            return format_disk_usage(stdout)

        return "Error: Unable to retrieve disk usage information"
    except Exception as e:
        return f"Error gathering disk usage information: {str(e)}"


@mcp.tool(
    title="Get hardware information",
    description="Get hardware information such as CPU details, PCI devices, USB devices, and hardware information from DMI.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_hardware_information(
    host: Host = None,
) -> str:
    """Get hardware information.

    Retrieves detailed hardware inventory including CPU specifications,
    PCI devices, USB devices, and DMI/SMBIOS data (system manufacturer,
    model, BIOS version, etc.). Some information may require root privileges.
    """
    try:
        group = get_command_group("hardware_info")
        results = {}

        # Execute all commands in the group
        for name, cmd in group.commands.items():
            try:
                returncode, stdout, stderr = await cmd.run(host=host)
                if returncode == 0:
                    results[name] = stdout
            except FileNotFoundError:
                results[name] = f"{name} command not available"

        return format_hardware_info(results)
    except Exception as e:
        return f"Error getting hardware information: {str(e)}"
