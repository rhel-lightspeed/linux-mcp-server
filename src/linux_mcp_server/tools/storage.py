"""Storage and hardware tools."""

import os
import typing as t

from collections.abc import Sequence
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
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.types import Username


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
async def list_block_devices(
    host: Host | None = None,
    username: Username | None = None,
) -> str:
    """
    List block devices.
    """
    try:
        # Try using lsblk first (most readable)
        returncode, stdout, _ = await execute_command(
            ["lsblk", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL", "--no-pager"],
            host=host,
            username=username,
        )

        if returncode == 0:
            result = ["=== Block Devices ===\n"]
            result.append(stdout)

            # Add disk I/O per-disk stats if available (only for local execution)
            if not host:
                try:
                    disk_io_per_disk = psutil.disk_io_counters(perdisk=True)
                    if disk_io_per_disk:
                        result.append("\n=== Disk I/O Statistics (per disk) ===")
                        for disk, stats in sorted(disk_io_per_disk.items()):
                            result.append(f"\n{disk}:")
                            result.append(f"  Read: {format_bytes(stats.read_bytes)}")
                            result.append(f"  Write: {format_bytes(stats.write_bytes)}")
                            result.append(f"  Read Count: {stats.read_count}")
                            result.append(f"  Write Count: {stats.write_count}")
                except Exception:
                    pass

            return "\n".join(result)
        else:
            # Fallback to listing partitions with psutil
            result = ["=== Block Devices (fallback) ===\n"]
            partitions = psutil.disk_partitions(all=True)

            for partition in partitions:
                result.append(f"\nDevice: {partition.device}")
                result.append(f"  Mountpoint: {partition.mountpoint}")
                result.append(f"  Filesystem: {partition.fstype}")
                result.append(f"  Options: {partition.opts}")

            return "\n".join(result)
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
    except Exception as e:
        return f"Error listing block devices: {str(e)}"


@mcp.tool(
    title="List directories",
    description="List directories under a specified path with flexible sorting options.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
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
    username: Username | None = None,
) -> t.Annotated[
    Sequence[DirectoryEntry],
    Field(description="List of directories with size or modified timestamp"),
]:
    # Validate order_by parameter
    try:
        order_by = OrderBy(order_by)
    except ValueError as e:
        raise ValueError(f"Invalid order_by value '{order_by}'. Must be one of: {', '.join(OrderBy)}") from e

    # Validate sort parameter
    try:
        sort = SortBy(sort)
    except ValueError as e:
        raise ValueError(f"Invalid sort value '{sort}'. Must be one of: {', '.join(SortBy)}") from e

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
            returncode, stdout, _ = await execute_command(
                ["du", "-b", "--max-depth=1", path],
                host=host,
                username=username,
            )

            # Parse output - du may return non-zero on permission errors but still give valid data
            lines = stdout.strip().split("\n")
            directories_by_size: list[DirectoryEntry] = []

            for line in lines:
                if not line:
                    continue
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    try:
                        size = int(parts[0])
                        dir_path_str = parts[1]
                        # Skip the parent directory itself
                        dir_name = Path(dir_path_str).name
                        if dir_path_str != path:
                            directories_by_size.append(DirectoryEntry(size=size, modified=0.0, name=dir_name))
                    except (ValueError, IndexError):
                        continue

            if not directories_by_size:
                # Only error if we got no output AND a bad return code
                if returncode != 0:
                    raise ToolError("du command failed and returned no directory data")
                raise ToolError(f"No subdirectories found in: {path}")

            # Sort by size
            reverse = sort == SortBy.DESCENDING
            directories_by_size.sort(key=lambda x: x.size, reverse=reverse)

            if top_n:
                directories_by_size = directories_by_size[:top_n]

            return directories_by_size
        case OrderBy.NAME:
            # Use find to list only immediate subdirectories
            returncode, stdout, _ = await execute_command(
                ["find", path, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%f\\n"],
                host=host,
                username=username,
            )

            if returncode != 0:
                raise ToolError(f"Error running find command: command failed with return code {returncode}")

            # Parse and sort output
            directories_by_name: list[DirectoryEntry] = [
                DirectoryEntry(name=line) for line in stdout.strip().split("\n") if line
            ]

            if not directories_by_name:
                raise ToolError(f"No subdirectories found in: {path}")

            # Sort alphabetically
            reverse = sort == SortBy.DESCENDING
            directories_by_name.sort(key=lambda x: x.name, reverse=reverse)

            if top_n:
                directories_by_name = directories_by_name[:top_n]

            return directories_by_name
        case OrderBy.MODIFIED:
            # Use find with modification time
            returncode, stdout, _ = await execute_command(
                ["find", path, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%T@\\t%f\\n"],
                host=host,
                username=username,
            )

            if returncode != 0:
                raise ToolError(f"Error running find command: command failed with return code {returncode}")

            # Parse output
            directories_by_modified: list[DirectoryEntry] = []
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        try:
                            timestamp = float(parts[0])
                            dir_name = parts[1]
                            directories_by_modified.append(DirectoryEntry(modified=timestamp, name=dir_name))
                        except ValueError:
                            continue

            if not directories_by_modified:
                raise ToolError(f"No subdirectories found in: {path}")

            # Sort by timestamp
            reverse = sort == SortBy.DESCENDING
            directories_by_modified.sort(key=lambda x: x.modified, reverse=reverse)

            if top_n:
                directories_by_modified = directories_by_modified[:top_n]

            return directories_by_modified
