"""Storage and hardware tools."""

import os

from collections.abc import Sequence
from pathlib import Path

import psutil

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.server import mcp
from linux_mcp_server.tools.ssh_executor import execute_command
from linux_mcp_server.utils import format_bytes
from linux_mcp_server.utils import StrEnum


class OrderBy(StrEnum):
    SIZE = "size"
    NAME = "name"
    MODIFIED = "modified"


class SortBy(StrEnum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


def _format_directory_list(
    path: str,
    directories: Sequence[tuple[str, int] | tuple[str, float] | tuple[str]],
    order_by: OrderBy,
    sort_desc: str,
    top_n: int | None = None,
) -> str:
    """
    Format a list of directories with consistent output structure.

    Args:
        path: The parent directory path
        directories: List of tuples where first element is dir name, rest is metadata
        order_by: The ordering mode (size, name, or modified)
        sort_desc: Human-readable sort description
        top_n: Optional top N limit (only used for SIZE mode)

    Returns:
        Formatted string with directory listing
    """
    result = []

    # Header with mode-specific title
    match order_by:
        case OrderBy.SIZE:
            prefix = f"Top {top_n} " if top_n is not None else ""
            result.append(f"=== {prefix}Directories by Size ({sort_desc}) ===")
        case OrderBy.NAME:
            result.append(f"=== Directories by Name ({sort_desc}) ===")
        case OrderBy.MODIFIED:
            result.append(f"=== Directories by Modified Date ({sort_desc}) ===")

    # Path and count
    result.append(f"Path: {path}")
    result.append(f"\nTotal subdirectories: {len(directories)}\n")

    # Directory entries with metadata
    for i, dir_entry in enumerate(directories, 1):
        dir_name = dir_entry[0]
        result.append(f"{i}. {dir_name}")

        # Add metadata based on order_by mode
        if order_by == OrderBy.SIZE and len(dir_entry) > 1:
            size = dir_entry[1]  # type: ignore[misc]
            result.append(f"   Size: {format_bytes(size)}")
        elif order_by == OrderBy.MODIFIED and len(dir_entry) > 1:
            timestamp = dir_entry[1]  # type: ignore[misc]
            dt = datetime.fromtimestamp(timestamp)
            result.append(f"   Modified: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
        # NAME mode has no additional metadata

    return "\n".join(result)


@mcp.tool()
@log_tool_call
async def list_block_devices(
    host: str | None = None,
    username: str | None = None,
) -> str:
    """
    List block devices.

    Args:
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)

    Returns:
        Formatted string with block device information
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


@mcp.tool()
@log_tool_call
async def list_directories(  # noqa: C901
    path: str,
    order_by: str = "name",
    sort: str = "ascending",
    top_n: int | None = None,
    host: str | None = None,
    username: str | None = None,
) -> str:
    """
    List directories under a specified path with flexible sorting options.

    This function uses efficient Linux primitives (du, find) to list and sort directories.

    Args:
        path: The directory path to analyze
        order_by: Sort order - "size", "name", or "modified" (default: "name")
        sort: Sort direction - "ascending" or "descending" (default: "ascending")
        top_n: Optional limit on number of directories to return (1-1000, only used with size ordering)
        host: Optional remote host to connect to
        username: Optional SSH username (required if host is provided)

    Returns:
        Formatted string with directory information, or error message if validation fails

    Security Features:
        - Path validation and resolution using pathlib
        - Command parameters passed as list (not shell string)
        - Input sanitization for all parameters
        - Graceful error handling for permission issues
    """
    # Validate order_by parameter
    try:
        order_by = OrderBy(order_by)
    except ValueError:
        return f"Error: Invalid order_by value '{order_by}'. Must be one of: {', '.join(OrderBy)}"

    # Validate sort parameter
    try:
        sort = SortBy(sort)
    except ValueError:
        return f"Error: Invalid sort value '{sort}'. Must be one of: {', '.join(SortBy)}"

    # Validate top_n parameter
    try:
        top_n = clamped_int(top_n) if top_n is not None else None
    except ValueError:
        return f"Error: Invalid top_n value '{top_n}'. Must be between 1 and 1000."

    # For local execution, validate path
    if not host:
        try:
            path_obj = Path(path).resolve(strict=True)
        except (OSError, RuntimeError):
            return f"Error: Path does not exist or cannot be resolved: {path}"

        if not path_obj.is_dir():
            return f"Error: Path is not a directory: {path}"

        if not os.access(path_obj, os.R_OK):
            return f"Error: Permission denied to read directory: {path}"

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
            directories_by_size: list[tuple[str, int]] = []

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
                            directories_by_size.append((dir_name, size))
                    except (ValueError, IndexError):
                        continue

            if not directories_by_size:
                # Only error if we got no output AND a bad return code
                if returncode != 0:
                    return "Error: du command failed and returned no directory data"
                return f"No subdirectories found in: {path}"

            # Sort by size
            reverse = sort == SortBy.DESCENDING
            directories_by_size.sort(key=lambda x: x[1], reverse=reverse)

            return _format_directory_list(
                path=path,
                directories=directories_by_size[:top_n] if top_n is not None else directories_by_size,
                order_by=OrderBy.SIZE,
                sort_desc="Largest First" if reverse else "Smallest First",
                top_n=top_n,
            )
        case OrderBy.NAME:
            # Use find to list only immediate subdirectories
            returncode, stdout, _ = await execute_command(
                ["find", path, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%f\\n"],
                host=host,
                username=username,
            )

            if returncode != 0:
                return f"Error running find command: command failed with return code {returncode}"

            # Parse and sort output
            directories_by_name: list[str] = [line for line in stdout.strip().split("\n") if line]

            if not directories_by_name:
                return f"No subdirectories found in: {path}"

            # Sort alphabetically
            reverse = sort == SortBy.DESCENDING
            directories_by_name.sort(reverse=reverse)

            # Convert to tuples with single element for template compatibility
            directories_tuples = [(name,) for name in directories_by_name]
            return _format_directory_list(
                path=path,
                directories=directories_tuples,
                order_by=OrderBy.NAME,
                sort_desc="Z-A" if reverse else "A-Z",
            )
        case OrderBy.MODIFIED:
            # Use find with modification time
            returncode, stdout, _ = await execute_command(
                ["find", path, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%T@\\t%f\\n"],
                host=host,
                username=username,
            )

            if returncode != 0:
                return f"Error running find command: command failed with return code {returncode}"

            # Parse output
            directories_by_modified: list[tuple[float, str]] = []
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split("\t", 1)
                    if len(parts) == 2:
                        try:
                            timestamp = float(parts[0])
                            dir_name = parts[1]
                            directories_by_modified.append((timestamp, dir_name))
                        except ValueError:
                            continue

            if not directories_by_modified:
                return f"No subdirectories found in: {path}"

            # Sort by timestamp
            reverse = sort == SortBy.DESCENDING
            directories_by_modified.sort(key=lambda x: x[0], reverse=reverse)

            # Reorder tuples to (dir_name, timestamp) for template compatibility
            directories_tuples = [(dir_name, timestamp) for timestamp, dir_name in directories_by_modified]
            return _format_directory_list(
                path=path,
                directories=directories_tuples,
                order_by=OrderBy.MODIFIED,
                sort_desc="Newest First" if reverse else "Oldest First",
            )
