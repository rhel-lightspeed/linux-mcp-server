"""Process management tools."""

import typing as t

from mcp.types import ToolAnnotations
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.formatters import format_process_detail
from linux_mcp_server.formatters import format_process_list
from linux_mcp_server.parsers import parse_proc_status
from linux_mcp_server.parsers import parse_ps_output
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import validate_pid


@mcp.tool(
    title="List processes",
    description="List running processes",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_processes(
    host: Host | None = None,
) -> str:
    try:
        cmd = get_command("list_processes")
        returncode, stdout, _ = await cmd.run(host=host)

        if returncode == 0 and stdout:
            processes = parse_ps_output(stdout)
            return format_process_list(processes)
        else:
            return "Error executing ps command"
    except Exception as e:
        return f"Error listing processes: {str(e)}"


@mcp.tool(
    title="Process details",
    description="Get information about a specific process.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_process_info(
    pid: t.Annotated[int, Field(description="Process ID")],
    host: Host | None = None,
) -> str:
    # Validate PID (accepts floats from LLMs)
    validated_pid, error = validate_pid(pid)
    if error:
        return error

    if validated_pid is None:
        return "Invalid PID"

    try:
        # Get process details with ps
        ps_cmd = get_command("process_info", "ps_detail")
        returncode, stdout, _ = await ps_cmd.run(host=host, pid=validated_pid)

        if returncode != 0:
            return f"Process with PID {validated_pid} does not exist."

        if not stdout:
            return f"Process with PID {validated_pid} does not exist."

        # Try to get more details from /proc
        proc_status = None
        status_cmd = get_command("process_info", "proc_status")
        status_code, status_stdout, _ = await status_cmd.run(host=host, pid=validated_pid)

        if status_code == 0 and status_stdout:
            proc_status = parse_proc_status(status_stdout)

        return format_process_detail(stdout, proc_status, validated_pid)
    except Exception as e:
        return f"Error getting process information: {str(e)}"
