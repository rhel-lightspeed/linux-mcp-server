"""Storage and hardware tools."""

import os
import typing as t

from pathlib import Path

import psutil

from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import format_bytes
from linux_mcp_server.utils import StrEnum
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


class ToolExecutionAttributes(BaseModel):
    names: list[str]
    command: list[str]
    parser: t.Callable[[str], t.Any]

    async def execute(self, host: Host | None) -> str:
        returncode, stdout, _ = await execute_command(self.command, host=host)
        if returncode != 0 and stdout == "":
            # Throw error in case returncode/stdout is not what expected
            raise ToolError(
                f"Error running {self.command} command: command failed with return code {returncode} and no output was returned"
            )

        return stdout


class NodeEntry(BaseModel):
    """A node entry model that is used by both directories and files listing."""

    size: int = 0
    modified: float = 0.0
    name: str = ""


class OrderBy(StrEnum):
    SIZE = "size"
    NAME = "name"
    MODIFIED = "modified"


class SortBy(StrEnum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


@mcp.tool(
    title="List block devices",
    description="List block devices on the system",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_block_devices(
    host: Host | None = None,
) -> str:
    """
    List block devices.
    """
    try:
        # Try using lsblk first (most readable)
        returncode, stdout, _ = await execute_command(
            ["lsblk", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL", "--no-pager"],
            host=host,
        )
    except FileNotFoundError:
        # If lsblk is not available, use psutil
        result = ["=== Block Devices ===\n"]
        partitions = psutil.disk_partitions(all=True)

        for partition in partitions:
            result.append(f"\nDevice: {partition.device}")
            result.append(f"  Mountpoint: {partition.mountpoint}")
            result.append(f"  Filesystem: {partition.fstype}")
            result.append(f"  Options: {partition.opts}")

        return "\n".join(result)

    if returncode == 0:
        result = ["=== Block Devices ===\n"]
        result.append(stdout)

        # Add disk I/O per-disk stats if available (only for local execution)
        if not host:
            disk_io_per_disk = psutil.disk_io_counters(perdisk=True)
            if disk_io_per_disk:
                result.append("\n=== Disk I/O Statistics (per disk) ===")
                for disk, stats in sorted(disk_io_per_disk.items()):
                    result.append(f"\n{disk}:")
                    result.append(f"  Read: {format_bytes(stats.read_bytes)}")
                    result.append(f"  Write: {format_bytes(stats.write_bytes)}")
                    result.append(f"  Read Count: {stats.read_count}")
                    result.append(f"  Write Count: {stats.write_count}")

        return "\n".join(result)

    # Fallback to listing partitions with psutil
    result = ["=== Block Devices (fallback) ===\n"]
    partitions = psutil.disk_partitions(all=True)

    for partition in partitions:
        result.append(f"\nDevice: {partition.device}")
        result.append(f"  Mountpoint: {partition.mountpoint}")
        result.append(f"  Filesystem: {partition.fstype}")
        result.append(f"  Options: {partition.opts}")

    return "\n".join(result)


def _validate_path(path: str) -> str:
    """Validate a given user path"""
    try:
        path_obj = Path(path).resolve(strict=True)
    except (OSError, RuntimeError):
        raise ToolError(f"Path does not exist or cannot be resolved: {path}")

    if not os.access(path_obj, os.R_OK):
        raise ToolError(f"Permission denied to read: {path}")

    return str(path_obj)


def _sort_results(path: str, lines: str, order_by: OrderBy, top_n: int | None, sort: SortBy) -> list[NodeEntry]:
    """Sort results based on `py:OrderBy` enum."""
    nodes = []
    match order_by:
        case OrderBy.SIZE:
            nodes = [
                NodeEntry(size=int(size), name=Path(dir_path_str).name)
                for line in lines
                for size, dir_path_str in [line.split("\t", 1)]
                if dir_path_str != path
            ]
        case OrderBy.NAME:
            nodes = [NodeEntry(name=line) for line in lines]
        case OrderBy.MODIFIED:  # pragma: no branch
            nodes = [
                NodeEntry(modified=float(timestamp), name=dir_name)
                for line in lines
                for timestamp, dir_name in [line.split("\t", 1)]
            ]

    # Sort by the order_by field
    nodes.sort(key=lambda x: getattr(x, order_by), reverse=sort == SortBy.DESCENDING)

    if top_n:
        return nodes[:top_n]

    return nodes


def _splitlines(stdout: str) -> list[str]:
    """Helper function to splitlines from stdout."""
    return [line.strip() for line in stdout.strip().splitlines() if line]


async def _perform_tool_calling(
    path: str,
    host: Host | None,
    order_by: OrderBy,
    top_n: int | None,
    sort: SortBy,
    attributes: dict[OrderBy, ToolExecutionAttributes],
) -> list[NodeEntry]:
    """Perform the tool calling given by the list of `py:attributes`"""
    # For local execution, validate path
    if not host:
        path = _validate_path(path)

    try:
        result = await attributes[order_by].execute(host=host)
        result = attributes[order_by].parser(result)
    except KeyError as e:
        raise ToolError(str(e)) from e

    sorted_results = _sort_results(path, result, order_by, top_n, sort)

    return sorted_results


@mcp.tool(
    title="List directories",
    description="List directories under a specified path with various sorting options.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_directories(
    path: t.Annotated[str, Field(description="The directory path to analyze")],
    order_by: t.Annotated[
        OrderBy, Field(description="Sort order - 'size', 'name', or 'modified' (default: 'name')")
    ] = OrderBy.NAME,
    sort: t.Annotated[
        SortBy, Field(description="Sort direction - 'ascending' or 'descending' (default: 'ascending')")
    ] = SortBy.ASCENDING,
    top_n: t.Annotated[
        int | None,
        Field(
            description="Optional limit on number of directories to return (1-1000, only used with size ordering)",
            gt=0,
            le=1_000,
        ),
    ] = None,
    host: Host | None = None,
) -> t.Annotated[
    list[NodeEntry],
    "List of directories with size or modified timestamp",
]:
    attributes = {
        OrderBy.SIZE: ToolExecutionAttributes(
            names=[OrderBy.SIZE], command=["du", "-b", "--max-depth=1", path], parser=_splitlines
        ),
        OrderBy.NAME: ToolExecutionAttributes(
            names=[OrderBy.NAME],
            command=["find", path, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%f\\n"],
            parser=_splitlines,
        ),
        OrderBy.MODIFIED: ToolExecutionAttributes(
            names=[OrderBy.MODIFIED],
            command=["find", path, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%T@\\t%f\\n"],
            parser=_splitlines,
        ),
    }
    return await _perform_tool_calling(path, host, order_by, top_n, sort, attributes)


@mcp.tool(
    title="List files",
    description="List files under a specified path with various sorting options.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_files(
    path: t.Annotated[str, Field(description="The path to analyze")],
    order_by: t.Annotated[
        OrderBy, Field(description="Sort order - 'size', 'name', or 'modified' (default: 'name')")
    ] = OrderBy.NAME,
    sort: t.Annotated[
        SortBy, Field(description="Sort direction - 'ascending' or 'descending' (default: 'ascending')")
    ] = SortBy.ASCENDING,
    top_n: t.Annotated[
        int | None,
        Field(
            description="Optional limit on number of files to return (1-1000, only used with size ordering)",
            gt=0,
            le=1_000,
        ),
    ] = None,
    host: Host | None = None,
) -> t.Annotated[
    list[NodeEntry],
    "List of files with size or modified timestamp",
]:
    base_command = ["find", path, "-mindepth", "1", "-maxdepth", "1", "-type", "f", "-printf"]
    attributes = {
        OrderBy.SIZE: ToolExecutionAttributes(
            names=[OrderBy.SIZE], command=base_command + ["%s\\t%f\\n"], parser=_splitlines
        ),
        OrderBy.NAME: ToolExecutionAttributes(
            names=[OrderBy.NAME], command=base_command + ["%f\\n"], parser=_splitlines
        ),
        OrderBy.MODIFIED: ToolExecutionAttributes(
            names=[OrderBy.MODIFIED], command=base_command + ["%T@\\t%f\\n"], parser=_splitlines
        ),
    }
    return await _perform_tool_calling(path, host, order_by, top_n, sort, attributes)


@mcp.tool(
    title="Read file",
    description="Read the contents of a file using cat",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def read_file(
    path: t.Annotated[str, Field(description="The file path to read")],
    host: Host | None = None,
) -> str:
    """
    Read the contents of a file using cat.
    """
    # For local execution, validate path
    if not host:
        path = _validate_path(path)

        if not os.path.isfile(path):
            raise ToolError(f"Path is not a file: {path}")

    attributes = [
        # Use cat to read the file
        ToolExecutionAttributes(names=[""], command=["cat", path], parser=lambda x: x)
    ]

    return await attributes[0].execute(host)
