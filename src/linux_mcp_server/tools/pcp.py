"""PCP (Performance Co-Pilot) historical performance data tools."""

import typing as t
import zoneinfo

from datetime import datetime
from datetime import tzinfo

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from pydantic.functional_validators import AfterValidator

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.models import PCPSample
from linux_mcp_server.parsers import parse_pmrep_csv
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.hostinfo import discover_timezone_name
from linux_mcp_server.utils.pcp import pmlogger_archive_dir
from linux_mcp_server.utils.pcp_timespec import parse_time_spec
from linux_mcp_server.utils.pcp_timespec import resolve_pcp_window
from linux_mcp_server.utils.pcp_timespec import to_pcp_time
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import validate_pcp_metrics


async def _target_timezone(host: str) -> tzinfo:
    """Return the target system's timezone as a ZoneInfo, failing if unavailable or invalid."""
    name = await discover_timezone_name(host)
    return zoneinfo.ZoneInfo(name)


@mcp.tool(
    title="List available PCP metrics",
    description=(
        "Returns every PCP metric available on the system with its description. "
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
        raise ToolError(f"Error listing PCP metrics: {stderr}")

    if not stdout.strip():
        raise ToolError("No PCP metrics found on this system.")

    return stdout


@mcp.tool(
    title="Query PCP historical metrics",
    description=(
        "Retrieves historical metric data from PCP archives as JSON samples. "
        "When start_time, end_time, or interval is omitted, reasonable defaults "
        "are chosen, targeting one hour or about 20 samples. "
        "Use only if get_system_information() indicates PCP is available."
    ),
    tags={"fixed", "performance", "pcp"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def pcp_query_metrics(
    metrics: t.Annotated[
        list[str],
        AfterValidator(validate_pcp_metrics),
        Field(
            description="List of PCP metric names to query",
            examples=[["kernel.all.cpu.user", "kernel.all.cpu.sys", "mem.util.used"]],
        ),
    ],
    start_time: t.Annotated[
        str | None,
        Field(
            description=(
                "Start time as a full date and time (e.g., '2026-08-14 14:00:00'), or 'now'. "
                "Timestamps without a UTC offset are read in the target system's timezone."
            ),
        ),
    ] = None,
    end_time: t.Annotated[
        str | None,
        Field(
            description=(
                "End time as a full date and time (e.g., '2026-08-14 16:00:00'), or 'now'. "
                "Timestamps without a UTC offset are read in the target system's timezone."
            ),
        ),
    ] = None,
    interval: t.Annotated[
        str | None,
        Field(
            description="Sampling interval (e.g., '1minute', '10seconds', '5minutes').",
        ),
    ] = None,
    *,
    host: Host,
) -> list[PCPSample]:
    """Query historical PCP metric data from archives."""
    tz = await _target_timezone(host)
    window = resolve_pcp_window(start_time, end_time, interval, now=datetime.now(tz))

    archive = await pmlogger_archive_dir(host)

    base_cmd = get_command("pcp_query_metrics")
    args = base_cmd.args + tuple(metrics)
    full_cmd = base_cmd.model_copy(update={"args": args})
    returncode, stdout, stderr = await full_cmd.run(
        host=host,
        archive=archive,
        start_time=window.start,
        end_time=window.end,
        interval=window.interval,
        samples=window.samples,
    )

    if returncode != 0:
        raise ToolError(f"Error querying metrics: {stderr}")

    samples = parse_pmrep_csv(stdout, tz)

    if not samples:
        raise ToolError("No data returned for the specified metrics and time range.")

    return samples


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
                "Optional summary timestamp: a full date and time (e.g., '2026-08-14 14:00:00'), or 'now'. "
                "Timestamps without a UTC offset are read in the target system's timezone. "
                "If not provided, shows live system summary."
            ),
        ),
    ] = None,
    *,
    host: Host,
) -> str:
    """Get a performance summary using pcp xsos."""
    if timestamp is not None:
        tz = await _target_timezone(host)
        moment = parse_time_spec(timestamp, datetime.now(tz))

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
        raise ToolError(f"Error getting performance summary: {stderr}")

    if not stdout.strip():
        raise ToolError("No performance summary data returned.")

    return stdout
