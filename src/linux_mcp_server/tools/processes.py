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
from linux_mcp_server.utils.validation import is_successful_output


@mcp.tool(
    title="List processes",
    description="List running processes",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_processes(
    host: Host = None,
) -> str:
    """List all running processes.

    Retrieves a snapshot of all running processes with details including PID,
    user, CPU/memory usage, process state, start time, and command line.
    """
    try:
        cmd = get_command("list_processes")
        returncode, stdout, _ = await cmd.run(host=host)

        if is_successful_output(returncode, stdout):
            processes = parse_ps_output(stdout)
            return format_process_list(processes)
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
    pid: t.Annotated[int, Field(description="Process ID", ge=1)],
    host: Host = None,
) -> str:
    """Get detailed information about a specific process.

    Retrieves comprehensive process details including CPU/memory usage, process
    state, virtual/resident memory size, controlling terminal, and additional
    metadata from /proc/<pid>/status when available.
    """
    try:
        # Get process details with ps
        ps_cmd = get_command("process_info", "ps_detail")
        returncode, stdout, _ = await ps_cmd.run(host=host, pid=pid)

        if returncode != 0:
            return f"Process with PID {pid} does not exist."

        if not stdout:
            return f"Process with PID {pid} does not exist."

        # Try to get more details from /proc
        proc_status = None
        status_cmd = get_command("process_info", "proc_status")
        status_code, status_stdout, _ = await status_cmd.run(host=host, pid=pid)

        if is_successful_output(status_code, status_stdout):
            proc_status = parse_proc_status(status_stdout)

        return format_process_detail(stdout, proc_status, pid)
    except Exception as e:
        return f"Error getting process information: {str(e)}"
