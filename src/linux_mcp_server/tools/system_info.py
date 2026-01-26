"""System information tools."""

import json

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.commands import get_command_group
from linux_mcp_server.parsers import parse_cpu_info
from linux_mcp_server.parsers import parse_free_output
from linux_mcp_server.parsers import parse_system_info
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import CpuInfo
from linux_mcp_server.utils.types import DiskUsage
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.types import SystemInfo
from linux_mcp_server.utils.types import SystemMemory
from linux_mcp_server.utils.validation import is_successful_output


@mcp.tool(
    title="Get system information",
    description="Get basic system information such as operating system, distribution, kernel version, uptime, and last boot time.",
    tags={"hardware", "system"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_system_information(
    host: Host = None,
) -> SystemInfo:
    """Get basic system information.

    Retrieves hostname, OS name/version, kernel version, architecture,
    system uptime, and last boot time.
    """
    group = get_command_group("system_info")
    results = {}

    # Execute all commands in the group
    for name, cmd in group.commands.items():
        returncode, stdout, _ = await cmd.run(host=host)
        if is_successful_output(returncode, stdout):
            results[name] = stdout

    info = parse_system_info(results)
    return info


@mcp.tool(
    title="Get CPU information",
    description="Get CPU information.",
    tags={"cpu", "hardware", "performance", "system"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_cpu_information(
    host: Host = None,
) -> CpuInfo:
    """Get CPU information.

    Retrieves CPU model, core counts (logical and physical), frequency,
    and current load averages (1, 5, and 15 minute).
    """
    group = get_command_group("cpu_info")
    results = {}

    # Execute all commands in the group
    for name, cmd in group.commands.items():
        returncode, stdout, _ = await cmd.run(host=host)
        if is_successful_output(returncode, stdout):
            results[name] = stdout

    return parse_cpu_info(results)


@mcp.tool(
    title="Get memory information",
    description="Get detailed memory including physical and swap.",
    tags={"hardware", "memory", "performance", "system"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_memory_information(
    host: Host = None,
) -> SystemMemory:
    """Get memory information.

    Retrieves physical RAM and swap usage including total, used, free,
    shared, buffers, cached, and available memory.
    """
    # Execute free command
    free_cmd = get_command("memory_info", "free")

    try:
        returncode, stdout, stderr = await free_cmd.run(host=host)
    except Exception as e:
        raise ToolError(f"Error gathering memory information: {str(e)}") from e

    if not is_successful_output(returncode, stdout):
        raise ToolError(f"Unable to retrieve memory information: {stderr}")
    return parse_free_output(stdout)


@mcp.tool(
    title="Get disk usage",
    description="Get detailed disk space information including size, mount points, and utilization.",
    tags={"disk", "filesystem", "storage", "system"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_disk_usage(
    host: Host = None,
) -> DiskUsage:
    """Get disk usage information.

    Retrieves filesystem usage for all mounted volumes including size,
    used/available space, utilization percentage, and mount points.
    """
    cmd = get_command("disk_usage")

    try:
        returncode, stdout, stderr = await cmd.run(host=host)
    except Exception as e:
        raise ToolError(f"Error gathering disk usage information: {str(e)}") from e

    if not is_successful_output(returncode, stdout):
        raise ToolError(f"Unable to retrieve disk usage information: {stderr}")

    try:
        data = json.loads(stdout)
        return DiskUsage.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        raise ToolError(f"Error parsing disk usage information: {str(e)}") from e


@mcp.tool(
    title="Get hardware information",
    description="Get hardware information such as CPU details, PCI devices, USB devices, and hardware information from DMI.",
    tags={"hardware", "system"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_hardware_information(
    host: Host = None,
) -> dict[str, str | list[str]]:
    """Get hardware information.

    Retrieves detailed hardware inventory including CPU specifications,
    PCI devices, USB devices, and DMI/SMBIOS data (system manufacturer,
    model, BIOS version, etc.). Some information may require root privileges.
    """
    group = get_command_group("hardware_info")
    results: dict[str, str | list[str]] = {}

    # Execute all commands in the group
    for name, cmd in group.commands.items():
        try:
            returncode, stdout, stderr = await cmd.run(host=host)
            if is_successful_output(returncode, stdout):
                results[name] = stdout if name == "lscpu" else stdout.splitlines()
            else:
                results[name] = f"Error retrieving {name}: {stderr}"
        except FileNotFoundError:
            results[name] = f"{name} command not available"
        except Exception as e:
            raise ToolError(f"Error gathering hardware information: {str(e)}") from e

    return results
