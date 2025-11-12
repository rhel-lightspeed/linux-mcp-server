"""Storage and hardware tools."""

import typing as t

from pathlib import Path

import psutil

from mcp.types import ToolAnnotations

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import format_bytes
from linux_mcp_server.utils.validation import validate_positive_int


@mcp.tool(
    title="List block devices",
    description="Get details about block devices attached to the system.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def list_block_devices(
    host: t.Annotated[str | None, "Remote host to connect to"] = None,
    username: t.Annotated[str | None, "SSH username (required if host is provided)"] = None,
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
    title="List directories by size",
    description="List directories under a specified path sorted by size (largest first).",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def list_directories_by_size(  # noqa: C901
    path: t.Annotated[str, "The directory path to analyze"],
    top_n: t.Annotated[
        int | float,
        "Number of top directories to return (1-1000). Accepts int or float (floats are truncated to integers)",
    ],
    host: t.Annotated[str | None, "Remote host to connect to"] = None,
    username: t.Annotated[str | None, "SSH username (required if host is provided)"] = None,
) -> str:
    """
    List directories under a specified path sorted by size (largest first).

    This function uses efficient Linux primitives (du command) to calculate directory
    sizes, making it much faster than Python-based directory traversal.

    Security Features:
        - Path validation and resolution using pathlib
        - Command parameters passed as list (not shell string)
        - Input sanitization for all parameters
        - Graceful error handling for permission issues
    """
    import os

    try:
        # Validate and normalize top_n parameter
        validated_top_n, error = validate_positive_int(
            top_n,
            param_name="top_n",
            min_value=1,
            max_value=1000,
        )
        if error:
            return error

        if validated_top_n is None:
            return "Invalid top_n value"

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

            path_str = str(path_obj)
        else:
            # For remote execution, use the path as-is
            path_str = path

        # Use du command to get directory sizes efficiently
        returncode, stdout, _ = await execute_command(
            ["du", "-b", "--max-depth=1", path_str],
            host=host,
            username=username,
        )

        # Parse output - du may return non-zero on permission errors but still give valid data
        lines = stdout.strip().split("\n")
        dir_sizes = []

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
                    if dir_path_str != path_str:
                        dir_sizes.append((dir_name, size))
                except (ValueError, IndexError):
                    continue

        if not dir_sizes:
            # Only error if we got no output AND a bad return code
            if returncode != 0:
                return "Error: du command failed and returned no directory data"
            return f"No subdirectories found in: {path}"

        # Sort by size (descending) and take top N
        dir_sizes.sort(key=lambda x: x[1], reverse=True)
        top_dirs = dir_sizes[:validated_top_n]

        # Format output
        result = []
        result.append(f"=== Top {len(top_dirs)} Largest Directories ===")
        result.append(f"Path: {path_str}")
        result.append(f"\nTotal subdirectories found: {len(dir_sizes)}\n")

        for i, (dir_name, size) in enumerate(top_dirs, 1):
            result.append(f"{i}. {dir_name}")
            result.append(f"   Size: {format_bytes(size)}")

        return "\n".join(result)

    except Exception as e:
        return f"Error analyzing directories: {str(e)}"


@mcp.tool(
    title="List directories by name",
    description="List directories under a specified path sorted by name.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def list_directories_by_name(
    path: t.Annotated[str, "The directory path to analyze"],
    reverse: t.Annotated[bool, "If True, sort in reverse alphabetical order (Z-A)"] = False,
    host: t.Annotated[str | None, "Remote host to connect to"] = None,
    username: t.Annotated[str | None, "SSH username (required if host is provided)"] = None,
) -> str:
    """
    List directories under a specified path sorted by name.

    This function uses efficient Linux primitives (find and sort) to list directories.
    """
    import os

    try:
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

            path_str = str(path_obj)
        else:
            # For remote execution, use the path as-is
            path_str = path

        # Use find to list only immediate subdirectories
        returncode, stdout, _ = await execute_command(
            ["find", path_str, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%f\\n"],
            host=host,
            username=username,
        )

        if returncode != 0:
            return f"Error running find command: command failed with return code {returncode}"

        # Parse and sort output
        directories = [line for line in stdout.strip().split("\n") if line]

        if not directories:
            return f"No subdirectories found in: {path}"

        # Sort alphabetically
        directories.sort(reverse=reverse)

        # Format output
        result = []
        sort_order = "Reverse Alphabetical" if reverse else "Alphabetical"
        result.append(f"=== Directories ({sort_order}) ===")
        result.append(f"Path: {path_str}")
        result.append(f"\nTotal subdirectories found: {len(directories)}\n")

        for i, dir_name in enumerate(directories, 1):
            result.append(f"{i}. {dir_name}")

        return "\n".join(result)

    except Exception as e:
        return f"Error listing directories: {str(e)}"


@mcp.tool(
    title="List directories by date",
    description="List directories under a specified path sorted by modification date.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
async def list_directories_by_modified_date(  # noqa: C901
    path: t.Annotated[str, "The directory path to analyze"],
    newest_first: t.Annotated[bool, "If True, show newest first; if False, show oldest first"] = True,
    host: t.Annotated[str | None, "Remote host to connect to"] = None,
    username: t.Annotated[str | None, "SSH username (required if host is provided)"] = None,
) -> str:
    """
    List directories under a specified path sorted by modification date.

    This function uses efficient Linux primitives (find) to list directories with timestamps.
    """
    import os

    from datetime import datetime

    try:
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

            path_str = str(path_obj)
        else:
            # For remote execution, use the path as-is
            path_str = path

        # Use find with modification time
        returncode, stdout, _ = await execute_command(
            ["find", path_str, "-mindepth", "1", "-maxdepth", "1", "-type", "d", "-printf", "%T@\\t%f\\n"],
            host=host,
            username=username,
        )

        if returncode != 0:
            return f"Error running find command: command failed with return code {returncode}"

        # Parse output
        directories = []
        for line in stdout.strip().split("\n"):
            if line:
                parts = line.split("\t", 1)
                if len(parts) == 2:
                    try:
                        timestamp = float(parts[0])
                        dir_name = parts[1]
                        directories.append((timestamp, dir_name))
                    except ValueError:
                        continue

        if not directories:
            return f"No subdirectories found in: {path}"

        # Sort by timestamp
        directories.sort(key=lambda x: x[0], reverse=newest_first)

        # Format output
        result = []
        sort_order = "Newest First" if newest_first else "Oldest First"
        result.append(f"=== Directories ({sort_order}) ===")
        result.append(f"Path: {path_str}")
        result.append(f"\nTotal subdirectories found: {len(directories)}\n")

        for i, (timestamp, dir_name) in enumerate(directories, 1):
            dt = datetime.fromtimestamp(timestamp)
            result.append(f"{i}. {dir_name}")
            result.append(f"   Modified: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(result)

    except Exception as e:
        return f"Error listing directories: {str(e)}"
