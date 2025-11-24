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


class DirectoryEntry(BaseModel):
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


@mcp.tool(
    title="List directories",
    description="List directories under a specified path with various sorting options.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_directories(  # noqa: C901
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
    list[DirectoryEntry],
    "List of directories with size or modified timestamp",
]:
    # For local execution, validate path
    if not host:
        try:
            path_obj = Path(path).resolve(strict=True)
        except (OSError, RuntimeError):
            raise ToolError(f"Path does not exist or cannot be resolved: {path}")

        if not path_obj.is_dir():
            raise ToolError(f"Path is not a directory: {path}")

        if not os.access(path_obj, os.R_OK):
            raise ToolError(f"Permission denied to read directory: {path}")

        path = str(path_obj)

    match order_by:
        case OrderBy.SIZE:
            # Use du command to get directory sizes efficiently
            command = ["du", "-b", "--max-depth=1", path]
        case OrderBy.NAME:
            # Use find to list only immediate subdirectories
            command = ["find", path, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%f\\n"]
        case OrderBy.MODIFIED:  # pragma: no branch
            # Use find with modification time
            command = ["find", path, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%T@\\t%f\\n"]

    returncode, stdout, _ = await execute_command(
        command,
        host=host,
    )

    if returncode != 0 and stdout == "":
        raise ToolError(
            f"Error running {command[0]} command: command failed with return code {returncode} and no output was returned"
        )

    lines = [line.strip() for line in stdout.strip().splitlines() if line]

    match order_by:
        case OrderBy.SIZE:
            directories = [
                DirectoryEntry(size=int(size), name=Path(dir_path_str).name)
                for line in lines
                for size, dir_path_str in [line.split("\t", 1)]
                if dir_path_str != path
            ]
        case OrderBy.NAME:
            directories = [DirectoryEntry(name=line) for line in lines]
        case OrderBy.MODIFIED:  # pragma: no branch
            directories = [
                DirectoryEntry(modified=float(timestamp), name=dir_name)
                for line in lines
                for timestamp, dir_name in [line.split("\t", 1)]
            ]

    # Sort by the order_by field
    directories.sort(key=lambda x: getattr(x, order_by), reverse=sort == SortBy.DESCENDING)

    if top_n:
        return directories[:top_n]

    return directories
