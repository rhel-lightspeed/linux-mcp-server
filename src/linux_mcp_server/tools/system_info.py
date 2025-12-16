"""System information tools."""

import typing as t

from mcp.types import ToolAnnotations
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import CommandGroup
from linux_mcp_server.commands import CommandSpec
from linux_mcp_server.commands import get_command
from linux_mcp_server.commands import get_command_group
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.connection.ssh import execute_with_fallback
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


@mcp.tool(
    title="Get system information",
    description="Get basic system information such as operating system, distribution, kernel version, uptime, and last boot time.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_system_information(
    host: Host | None = None,
    cmd_group: t.Annotated[CommandGroup, Field(description="Ignore this parameter")] = get_command_group("system_info"),
) -> str:
    """
    Get basic system information.
    """
    try:
        results = {}

        # Execute all commands in the group
        for name, cmd in cmd_group.commands.items():
            returncode, stdout, _ = await execute_command(cmd.args, host=host)
            if returncode == 0 and stdout:
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
    host: Host | None = None,
    cmd_group: t.Annotated[CommandGroup, Field(description="Ignore this parameter")] = get_command_group("cpu_info"),
) -> str:
    """
    Get CPU information.
    """
    try:
        results = {}

        # Execute all commands in the group
        for name, cmd in cmd_group.commands.items():
            returncode, stdout, _ = await execute_command(cmd.args, host=host)
            if returncode == 0 and stdout:
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
    host: Host | None = None,
    cmd: t.Annotated[CommandSpec, Field(description="Ignore this parameter")] = get_command("memory_info", "free"),
) -> str:
    """
    Get memory information.
    """
    try:
        # Execute free command
        returncode, stdout, _ = await execute_command(cmd.args, host=host)

        if returncode == 0 and stdout:
            memory = parse_free_output(stdout)
            return format_memory_info(memory)

        return "Error: Unable to retrieve memory information"
    except Exception as e:
        return f"Error gathering memory information: {str(e)}"


@mcp.tool(
    title="Get disk usage",
    description="Get detailed disk space information including size, mount points, and utilization..",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_disk_usage(
    host: Host | None = None,
    cmd: t.Annotated[CommandSpec, Field(description="Ignore this parameter")] = get_command("disk_usage"),
) -> str:
    """
    Get disk usage information.
    """
    try:
        returncode, stdout, _ = await execute_with_fallback(
            cmd.args,
            fallback=cmd.fallback,
            host=host,
        )

        if returncode == 0 and stdout:
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
    host: Host | None = None,
    cmd_group: t.Annotated[CommandGroup, Field(description="Ignore this parameter")] = get_command_group(
        "hardware_info"
    ),
) -> str:
    """
    Get hardware information.
    """
    try:
        results = {}

        # Execute all commands in the group
        for name, cmd in cmd_group.commands.items():
            try:
                returncode, stdout, stderr = await execute_command(cmd.args, host=host)
                if returncode == 0:
                    results[name] = stdout
            except FileNotFoundError:
                results[name] = f"{name} command not available"

        return format_hardware_info(results)
    except Exception as e:
        return f"Error getting hardware information: {str(e)}"
