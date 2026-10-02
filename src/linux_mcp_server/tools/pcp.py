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
from linux_mcp_server.formatters import format_pcp_metric_listing
from linux_mcp_server.models import PCPSample
from linux_mcp_server.parsers import parse_pminfo_listing
from linux_mcp_server.parsers import parse_pmrep_csv
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.hostinfo import discover_timezone_name
from linux_mcp_server.utils.pcp import PCP_GUIDE_TOOL
from linux_mcp_server.utils.pcp import pmlogger_archive_dir
from linux_mcp_server.utils.pcp import read_pcp_guide
from linux_mcp_server.utils.pcp_namespace import collapse_metric_tree
from linux_mcp_server.utils.pcp_timespec import parse_time_spec
from linux_mcp_server.utils.pcp_timespec import resolve_pcp_window
from linux_mcp_server.utils.pcp_timespec import to_pcp_time
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import validate_pcp_metrics
from linux_mcp_server.utils.validation import validate_pcp_prefix


async def _target_timezone(host: str) -> tzinfo:
    """Return the target system's timezone as a ZoneInfo, failing if unavailable or invalid."""
    name = await discover_timezone_name(host)
    return zoneinfo.ZoneInfo(name)


@mcp.tool(
    title="Read the PCP metrics guide",
    description=(
        "Returns the PCP metrics guide: a catalog of the metric names recorded on a typical "
        "Linux system, and how to read the values the other PCP tools return. Read it before "
        "investigating performance with PCP, and take metric names from it rather than from "
        "memory."
    ),
    tags={"fixed", "performance", "pcp"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
# Fixed documentation with no arguments is logically a resource, and this did start
# out as one. As of 2026-09 that is not what clients do with it: of the client and
# model combinations we tried, several never surfaced the resource to the model at
# all, and when both the resource and this tool were offered, every one of them
# reached for the tool. So the resource is gone and only the tool remains.
async def pcp_guide(
    *,
    # The guide is shipped with the server and says nothing about any particular
    # system, but every tool is dispatched and authorized by target host, so it
    # is asked for here too rather than made an exception of.
    host: Host,
) -> str:
    """Return the shipped PCP metrics guide."""
    return read_pcp_guide()


@mcp.tool(
    title="List available PCP metrics",
    description=(
        "Browses the PCP metric namespace. Lists the metrics under 'prefix' with their "
        "descriptions, collapsing any large sub-namespace to one line giving its name and how "
        "many metrics it holds; call again with that name as the prefix to see inside it. "
        "Only metrics this system's pmlogger records are listed, so everything listed can be "
        "passed to pcp_query_metrics. "
        f"The {PCP_GUIDE_TOOL} tool already names the commonly needed metrics, so reach for "
        "this when you need a subsystem the guide does not cover. "
        "Use only if get_system_information() indicates PCP is available."
    ),
    tags={"fixed", "performance", "pcp"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def pcp_list_metrics(
    prefix: t.Annotated[
        str | None,
        Field(
            description=(
                "Namespace to list, such as 'mem' or 'disk.dev'. Omit it to see the top-level "
                "namespaces, which is where to start when you do not know the name."
            ),
            examples=["mem", "disk.dev", "network.interface"],
        ),
    ] = None,
    *,
    host: Host,
) -> str:
    """List the recorded PCP metrics under a namespace, collapsing what does not fit."""
    if prefix is not None:
        try:
            prefix = validate_pcp_prefix(prefix)
        except ValueError as e:
            raise ToolError(str(e)) from e

    # The archives rather than pmcd, so that this lists what pcp_query_metrics can
    # actually return. A stock pmlogger records well under half the live namespace,
    # whole subsystems of it, and nothing here can query the rest.
    cmd = get_command("pcp_metrics_list")
    returncode, stdout, stderr = await cmd.run(host=host, archive=await pmlogger_archive_dir(host), prefix=prefix)

    # pminfo reports an unresolvable name on stderr; checked ahead of the exit code
    # because otherwise a bad prefix looks like a system with no metrics at all.
    if prefix and "Unknown metric name" in stderr:
        raise ToolError(
            f"No recorded PCP metric or namespace is called {prefix!r}. Either it does not exist "
            "on this system or its pmlogger is not configured to record it, and either way there "
            "is no historical data to query. Call this tool without a prefix to see what is recorded."
        )

    if returncode != 0:
        raise ToolError(f"Error listing PCP metrics: {stderr}")

    metrics = parse_pminfo_listing(stdout)
    if not metrics:
        raise ToolError("No PCP metrics found in this system's archives.")

    return format_pcp_metric_listing(collapse_metric_tree(metrics, prefix), prefix)


@mcp.tool(
    title="Query PCP historical metrics",
    description=(
        "Retrieves historical metric data from PCP archives as JSON samples. "
        "When start_time, end_time, or interval is omitted, reasonable defaults "
        "are chosen, targeting one hour or about 20 samples. "
        f"Call {PCP_GUIDE_TOOL} first for the metric catalog and how to read the values; "
        "do not guess metric names. "
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
