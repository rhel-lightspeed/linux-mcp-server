"""Storage and hardware tools."""

import os

from datetime import datetime
from pathlib import Path

import psutil

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.server import mcp
from linux_mcp_server.tools.ssh_executor import execute_command
from linux_mcp_server.utils import format_bytes
from linux_mcp_server.utils.validation import validate_positive_int


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
    try:
        # Validate order_by parameter
        valid_order_by = ["size", "name", "modified"]
        if order_by not in valid_order_by:
            return f"Error: Invalid order_by value '{order_by}'. Must be one of: {', '.join(valid_order_by)}"

        # Validate sort parameter
        valid_sort = ["ascending", "descending"]
        if sort not in valid_sort:
            return f"Error: Invalid sort value '{sort}'. Must be one of: {', '.join(valid_sort)}"

        # Validate top_n if provided
        validated_top_n = None
        if top_n is not None:
            validated_top_n, error = validate_positive_int(
                top_n,
                param_name="top_n",
                min_value=1,
                max_value=1000,
            )
            if error:
                return error

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

        # Handle different ordering methods
        if order_by == "size":
            # Use du command to get directory sizes efficiently
            returncode, stdout, _ = await execute_command(
                ["du", "-b", "--max-depth=1", path_str],
                host=host,
                username=username,
            )

            # Parse output - du may return non-zero on permission errors but still give valid data
            lines = stdout.strip().split("\n")
            dir_data = []

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
                            dir_data.append((dir_name, size))
                    except (ValueError, IndexError):
                        continue

            if not dir_data:
                # Only error if we got no output AND a bad return code
                if returncode != 0:
                    return "Error: du command failed and returned no directory data"
                return f"No subdirectories found in: {path}"

            # Sort by size
            reverse = sort == "descending"
            dir_data.sort(key=lambda x: x[1], reverse=reverse)

            # Apply top_n limit if specified
            if validated_top_n is not None:
                dir_data = dir_data[:validated_top_n]

            # Format output
            result = []
            sort_desc = "Largest First" if sort == "descending" else "Smallest First"
            if validated_top_n:
                result.append(f"=== Top {len(dir_data)} Directories by Size ({sort_desc}) ===")
            else:
                result.append(f"=== Directories by Size ({sort_desc}) ===")
            result.append(f"Path: {path_str}")
            result.append(f"\nTotal subdirectories: {len(dir_data)}\n")

            for i, (dir_name, size) in enumerate(dir_data, 1):
                result.append(f"{i}. {dir_name}")
                result.append(f"   Size: {format_bytes(size)}")

            return "\n".join(result)

        elif order_by == "name":
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
            reverse = sort == "descending"
            directories.sort(reverse=reverse)

            # Format output
            result = []
            sort_desc = "Z-A" if sort == "descending" else "A-Z"
            result.append(f"=== Directories by Name ({sort_desc}) ===")
            result.append(f"Path: {path_str}")
            result.append(f"\nTotal subdirectories: {len(directories)}\n")

            for i, dir_name in enumerate(directories, 1):
                result.append(f"{i}. {dir_name}")

            return "\n".join(result)

        elif order_by == "modified":
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
            reverse = sort == "descending"
            directories.sort(key=lambda x: x[0], reverse=reverse)

            # Format output
            result = []
            sort_desc = "Newest First" if sort == "descending" else "Oldest First"
            result.append(f"=== Directories by Modified Date ({sort_desc}) ===")
            result.append(f"Path: {path_str}")
            result.append(f"\nTotal subdirectories: {len(directories)}\n")

            for i, (timestamp, dir_name) in enumerate(directories, 1):
                dt = datetime.fromtimestamp(timestamp)
                result.append(f"{i}. {dir_name}")
                result.append(f"   Modified: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

            return "\n".join(result)
        
        else:
            return f"Error: Invalid order_by value '{order_by}'. Must be one of: {', '.join(valid_order_by)}"

    except Exception as e:
        return f"Error listing directories: {str(e)}"
