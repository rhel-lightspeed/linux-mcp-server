"""PCP (Performance Co-Pilot) historical performance data tools."""

import typing as t

from mcp.types import ToolAnnotations
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import CommandSpec
from linux_mcp_server.commands import get_command
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


@mcp.tool(
    title="List available PCP metrics",
    description="Returns PCP metrics available on the system with descriptions. Accepts an optional keyword to filter results.",
    tags={"fixed", "performance", "pcp"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_pcp_metrics(
    search_keyword: t.Annotated[
        str | None,
        Field(
            description="Optional keyword to filter metrics",
            examples=["network", "cpu", "disk", "mem"],
        ),
    ] = None,
    host: Host = None,
) -> str:
    """List available PCP metrics with descriptions."""
    cmd = get_command("pcp_metrics_list")
    returncode, stdout, stderr = await cmd.run(host=host)

    if returncode != 0:
        if "command not found" in stderr:
            return "PCP is not installed on this system."
        return f"Error listing PCP metrics: {stderr}"

    if not stdout.strip():
        return "No PCP metrics found on this system."

    if search_keyword:
        keyword_lower = search_keyword.lower()
        filtered = [line for line in stdout.strip().split("\n") if keyword_lower in line.lower()]
        if not filtered:
            return f"No PCP metrics found matching '{search_keyword}'."
        return "\n".join(filtered)

    return stdout


@mcp.tool(
    title="List available PCP archive time periods",
    description="Returns available PCP archive time periods with start and end times for each archive.",
    tags={"fixed", "performance", "pcp"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_pcp_archives(
    host: Host = None,
) -> str:
    """List available PCP archive time periods.

    Finds archives under /var/log/pcp/pmlogger/ and uses pmdumplog -L
    to show the time range each archive covers.
    """
    cmd = get_command("pcp_archive_list")
    returncode, stdout, stderr = await cmd.run(host=host)

    if returncode != 0:
        if "command not found" in stderr or "No such file" in stderr:
            return "PCP is not installed on this system."
        return f"Error listing PCP archives: {stderr}"

    if not stdout.strip():
        return "No PCP archives found. Ensure pmlogger is running"

    index_files = [line.strip() for line in stdout.strip().split("\n") if line.strip()]

    results = []
    for index_file in index_files:
        base = index_file.replace(".index", "")
        dump_cmd = get_command("pcp_archive_info")
        returncode, dump_stdout, dump_stderr = await dump_cmd.run(host=host, archive=base)
        if returncode == 0:
            results.append(dump_stdout.strip())
        else:
            results.append(f"Archive: {base}\n  Error reading archive: {dump_stderr.strip()}")

    return "\n\n".join(results)


@mcp.tool(
    title="Query PCP historical metrics",
    description="Retrieves historical metric data from PCP archives for a specified time range.",
    tags={"fixed", "performance", "pcp"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def query_pcp_metrics(
    metrics: t.Annotated[
        list[str],
        Field(
            description="List of PCP metric names to query",
            examples=[["kernel.all.cpu.user", "kernel.all.cpu.sys", "mem.util.used"]],
        ),
    ],
    start_time: t.Annotated[
        str,
        Field(
            description="Start time for the query (e.g., '2026-08-14 14:00:00', '@14:00', '-2hours')",
        ),
    ],
    end_time: t.Annotated[
        str,
        Field(
            description="End time for the query (e.g., '2026-08-14 16:00:00', '@16:00', 'now')",
        ),
    ],
    interval: t.Annotated[
        str,
        Field(
            description="Sampling interval (e.g., '1minute', '10seconds', '5minutes')",
        ),
    ] = "1minute",
    host: Host = None,
) -> str:
    """Query historical PCP metric data from archives."""
    # Find the latest archive from pcp output
    cmd = get_command("pcp_archive_dir")
    returncode, stdout, stderr = await cmd.run(host=host)

    if returncode != 0:
        return "PCP is not installed on this system."

    archive = ""
    for line in stdout.split("\n"):
        if "pmlogger" in line:
            full_path = line.strip().split()[-1]
            archive = full_path.rsplit("/", 1)[0]
            break

    if not archive:
        return "No PCP archives found. Ensure pmlogger is running."

    base_cmd = get_command("pcp_query_metrics")
    full_cmd = CommandSpec(args=base_cmd.args + tuple(metrics))
    returncode, stdout, stderr = await full_cmd.run(
        host=host,
        archive=archive,
        start_time=start_time,
        end_time=end_time,
        interval=interval,
    )

    if returncode != 0:
        if "command not found" in stderr:
            return "pmrep is not installed."
        return f"Error querying metrics: {stderr}"

    if not stdout.strip():
        return "No data returned for the specified metrics and time range."

    return stdout


@mcp.tool(
    title="Get PCP performance summary",
    description="Produces a condensed snapshot of CPU, memory, disk, network, and process information using pcp xsos. Can summarize live system or a historical archive.",
    tags={"fixed", "performance", "pcp"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_performance_summary(
    archive_path: t.Annotated[
        str | None,
        Field(
            description="Optional PCP archive path for historical summary. If not provided, shows live system summary.",
        ),
    ] = None,
    host: Host = None,
) -> str:
    """Get a performance summary using pcp xsos."""
    if archive_path:
        cmd = get_command("pcp_xsos_archive")
        returncode, stdout, stderr = await cmd.run(host=host, archive=archive_path)
    else:
        cmd = get_command("pcp_xsos_live")
        returncode, stdout, stderr = await cmd.run(host=host)

    if returncode != 0:
        if "command not found" in stderr:
            return "pcp xsos is not available. Install with: dnf install pcp-system-tools"
        return f"Error getting performance summary: {stderr}"

    if not stdout.strip():
        return "No performance summary data returned."

    return stdout
