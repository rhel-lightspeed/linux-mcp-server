"""PCP (Performance Co-Pilot) historical performance data tools."""

import json
import typing as t
import zoneinfo

from datetime import datetime
from datetime import tzinfo

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.parsers import parse_pmrep_csv
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.pcp import discover_timezone_name
from linux_mcp_server.utils.pcp import pmlogger_archive_dir
from linux_mcp_server.utils.timespec import parse_time_spec
from linux_mcp_server.utils.timespec import resolve_pcp_window
from linux_mcp_server.utils.timespec import to_pcp_time
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import validate_pcp_metrics


async def _target_timezone(host: str) -> tzinfo:
    """Return the target system's timezone, or fail if it is unknown.

    Times the caller gives without an offset mean the target's zone, which is
    rarely this server's and rarely UTC, so substituting UTC here would
    silently shift every such timestamp and every timestamp reported back.
    """
    name = await discover_timezone_name(host)

    if name is None:
        raise ToolError(
            "Unable to determine the target system's timezone. Cannot safely interpret or return PCP timestamps."
        )

    try:
        return zoneinfo.ZoneInfo(name)
    except (ValueError, zoneinfo.ZoneInfoNotFoundError) as e:
        raise ToolError(
            f"Cannot load the target system's timezone: {name!r}. "
            "Check the target timezone and the MCP server's timezone data."
        ) from e


@mcp.tool(
    title="List available PCP metrics",
    description=(
        "Returns every PCP metric available on the system with its description. "
        "The result is very large, delegate this call to a subagent and have it return only "
        "the metric names you need. Call it directly only if delegation is unavailable. "
        "Use only if get_system_information() indicates PCP is available."
    ),
    tags={"fixed", "performance", "pcp"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def pcp_list_metrics(
    host: Host,
) -> str:
    """List available PCP metrics with descriptions."""
    cmd = get_command("pcp_metrics_list")
    returncode, stdout, stderr = await cmd.run(host=host)

    if returncode != 0:
        if "command not found" in stderr:
            raise ToolError("PCP is not installed on this system.")
        raise ToolError(f"Error listing PCP metrics: {stderr}")

    if not stdout.strip():
        raise ToolError("No PCP metrics found on this system.")

    return stdout


@mcp.tool(
    title="Query PCP historical metrics",
    description=(
        "Retrieves historical metric data from PCP archives as JSON samples. "
        "Supply start_time, end_time and interval together to get exactly the range requested. "
        "Use only if get_system_information() indicates PCP is available."
    ),
    tags={"fixed", "performance", "pcp"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def pcp_query_metrics(
    metrics: t.Annotated[
        list[str],
        Field(
            description="List of PCP metric names to query",
            examples=[["kernel.all.cpu.user", "kernel.all.cpu.sys", "mem.util.used"]],
        ),
    ],
    start_time: t.Annotated[
        str | None,
        Field(
            description=(
                "Start time for the query (e.g., '2026-08-14 14:00:00', '-2hours'). "
                "Timestamps without a UTC offset are read in the target system's timezone. "
                "Defaults to one hour before end_time, or to one interval-sized window before it."
            ),
        ),
    ] = None,
    end_time: t.Annotated[
        str | None,
        Field(
            description=(
                "End time for the query (e.g., '2026-08-14 16:00:00', 'now'). "
                "Timestamps without a UTC offset are read in the target system's timezone. "
                "Defaults to one hour after start_time, or to now when start_time is also omitted."
            ),
        ),
    ] = None,
    interval: t.Annotated[
        str | None,
        Field(
            description=(
                "Sampling interval (e.g., '1minute', '10seconds', '5minutes'). "
                "Defaults to a round value yielding about 20 samples over the time range."
            ),
        ),
    ] = None,
    *,
    host: Host,
) -> str:
    """Query historical PCP metric data from archives."""
    try:
        metric_names = validate_pcp_metrics(metrics)
    except ValueError as e:
        raise ToolError(str(e)) from e

    tz = await _target_timezone(host)

    try:
        window = resolve_pcp_window(start_time, end_time, interval, now=datetime.now(tz))
    except ValueError as e:
        raise ToolError(str(e)) from e

    archive = await pmlogger_archive_dir(host)

    base_cmd = get_command("pcp_query_metrics")
    args = base_cmd.args + metric_names
    if window.samples is not None:
        args += ("--samples", str(window.samples))
    full_cmd = base_cmd.model_copy(update={"args": args})
    returncode, stdout, stderr = await full_cmd.run(
        host=host,
        archive=archive,
        start_time=window.start,
        end_time=window.end,
        interval=window.interval,
    )

    if returncode != 0:
        if "command not found" in stderr:
            raise ToolError("pmrep is not installed.")
        raise ToolError(f"Error querying metrics: {stderr}")

    try:
        samples = parse_pmrep_csv(stdout, tz)
    except ValueError as e:
        raise ToolError(str(e)) from e

    if not samples:
        raise ToolError("No data returned for the specified metrics and time range.")

    return json.dumps([sample.model_dump() for sample in samples], indent=2)


@mcp.tool(
    title="Get PCP performance summary",
    description=(
        "Produces a condensed snapshot of CPU, memory, disk, network, and process information "
        "using pcp xsos. Can summarize the live system or a particular time in the past. "
        "Use only if get_system_information() indicates PCP is available."
    ),
    tags={"fixed", "performance", "pcp"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def pcp_performance_summary(
    timestamp: t.Annotated[
        str | None,
        Field(
            description=(
                "Optional timestamp for a summary at a particular time (e.g., '2026-08-14 14:00:00', '-2hours'). "
                "Timestamps without a UTC offset are read in the target system's timezone. "
                "If not provided, shows live system summary."
            ),
        ),
    ] = None,
    *,
    host: Host,
) -> str:
    """Get a performance summary using pcp xsos."""
    if timestamp:
        tz = await _target_timezone(host)
        try:
            moment = parse_time_spec(timestamp, datetime.now(tz))
        except ValueError as e:
            raise ToolError(str(e)) from e

        cmd = get_command("pcp_xsos_archive")
        returncode, stdout, stderr = await cmd.run(
            host=host,
            archive=await pmlogger_archive_dir(host),
            # pcp xsos has no --timezone option, so the origin carries its own.
            origin=to_pcp_time(moment),
        )
    else:
        cmd = get_command("pcp_xsos_live")
        returncode, stdout, stderr = await cmd.run(host=host)

    if returncode != 0:
        if "command not found" in stderr:
            raise ToolError("pcp xsos is not available. Install with: dnf install pcp-system-tools")
        raise ToolError(f"Error getting performance summary: {stderr}")

    if not stdout.strip():
        raise ToolError("No performance summary data returned.")

    return stdout
