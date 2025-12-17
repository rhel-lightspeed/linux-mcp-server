"""Storage and hardware tools."""

import os
import typing as t

from collections.abc import Mapping
from pathlib import Path

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from pydantic.functional_validators import BeforeValidator

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.formatters import format_block_devices
from linux_mcp_server.formatters import format_directory_listing
from linux_mcp_server.formatters import format_file_listing
from linux_mcp_server.parsers import parse_directory_listing
from linux_mcp_server.parsers import parse_file_listing
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import StrEnum
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.types import NodeEntry
from linux_mcp_server.utils.validation import is_successful_output
from linux_mcp_server.utils.validation import validate_path


class OrderBy(StrEnum):
    SIZE = "size"
    NAME = "name"
    MODIFIED = "modified"


class SortBy(StrEnum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


DIRECTORY_COMMANDS: dict[OrderBy, str] = {
    OrderBy.SIZE: "list_directories_size",
    OrderBy.NAME: "list_directories_name",
    OrderBy.MODIFIED: "list_directories_modified",
}

FILE_COMMANDS: dict[OrderBy, str] = {
    OrderBy.SIZE: "list_files_size",
    OrderBy.NAME: "list_files_name",
    OrderBy.MODIFIED: "list_files_modified",
}


async def _list_resources(
    path: Path,
    order_by: OrderBy,
    sort: SortBy,
    top_n: int | None,
    host: Host | None,
    command_map: Mapping[OrderBy, str],
    parser: t.Callable[[str, OrderBy], list[NodeEntry]],
    formatter: t.Callable[[list[NodeEntry], Path, OrderBy, bool], str],
    resource_name: str,
) -> str:
    """List filesystem resources (files or directories) with sorting and filtering.

    Args:
        path: Absolute path to list resources from.
        order_by: Sort criterion (size, name, or modified).
        sort: Sort direction (ascending or descending).
        top_n: Optional limit on number of results to return.
        host: Optional remote host to execute command on.
        command_map: Mapping from OrderBy enum to command names.
        parser: Function to parse command output into NodeEntry objects.
        formatter: Function to format NodeEntry list as output string.
        resource_name: Human-readable name for error messages (e.g., "files").

    Returns:
        Formatted string listing of resources.

    Raises:
        ToolError: If path validation fails or command execution fails.
    """
    cmd_name = command_map[order_by]
    cmd = get_command(cmd_name)

    try:
        returncode, stdout, stderr = await cmd.run(host=host, path=path)

        # The du command will exit with code 1 even if it gets some valid results.
        # Only error in the case where we got non-zero exit code and no data in stdout.
        if returncode != 0 and not stdout:
            raise ToolError(f"Error running command: command failed with return code {returncode}: {stderr}")

        entries = parser(stdout, order_by)

        # Sort entries based on order_by criterion and sort direction
        if order_by == OrderBy.SIZE:
            entries = sorted(entries, key=lambda e: e.size, reverse=sort == SortBy.DESCENDING)
        elif order_by == OrderBy.MODIFIED:
            entries = sorted(entries, key=lambda e: e.modified, reverse=sort == SortBy.DESCENDING)
        else:
            entries = sorted(entries, key=lambda e: e.name.lower(), reverse=sort == SortBy.DESCENDING)

        # Apply limit if specified
        if top_n:
            entries = entries[:top_n]

        return formatter(entries, path, order_by, sort == SortBy.DESCENDING)

    except Exception as e:
        raise ToolError(f"Error listing {resource_name}: {str(e)}") from e


@mcp.tool(
    title="List block devices",
    description="List block devices on the system",
    tags={"devices", "storage"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_block_devices(
    host: Host = None,
) -> str:
    """List block devices.

    Retrieves all block devices (disks, partitions, LVM volumes) with their
    name, size, type, mount point, and filesystem information.
    """
    cmd = get_command("list_block_devices")
    returncode, stdout, stderr = await cmd.run(host=host)

    if not is_successful_output(returncode, stdout):
        raise ToolError(f"Unable to list block devices. lsblk command may not be available. {returncode}: {stderr}")

    return format_block_devices(stdout)


@mcp.tool(
    title="List directories",
    description="List directories under a specified path with various sorting options.",
    tags={"directories", "filesystem", "storage"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_directories(
    path: t.Annotated[
        Path,
        BeforeValidator(validate_path),
        Field(
            description="Absolute path to the directory to analyze",
            examples=["/var/log", "/etc", "/home", "/opt", "/tmp"],
        ),
    ],
    order_by: t.Annotated[OrderBy, "Sort order - 'size', 'name', or 'modified' (default: 'name')"] = OrderBy.NAME,
    sort: t.Annotated[SortBy, "Sort direction - 'ascending' or 'descending' (default: 'ascending')"] = SortBy.ASCENDING,
    top_n: t.Annotated[
        int | None,
        Field(
            description="Optional limit on number of directories to return (1-1000)",
            gt=0,
            le=1_000,
        ),
    ] = None,
    host: Host = None,
) -> str:
    """List directories under a specified path.

    Retrieves subdirectories with their size (when ordered by size) or
    modification time, supporting flexible sorting and result limiting.
    """
    return await _list_resources(
        path=path,
        order_by=order_by,
        sort=sort,
        top_n=top_n,
        host=host,
        command_map=DIRECTORY_COMMANDS,
        parser=parse_directory_listing,
        formatter=format_directory_listing,
        resource_name="directories",
    )


@mcp.tool(
    title="List files",
    description="List files under a specified path with various sorting options.",
    tags={"files", "filesystem", "storage"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_files(
    path: t.Annotated[
        Path,
        BeforeValidator(validate_path),
        Field(
            description="Absolute path to the directory to analyze",
            examples=["/var/log", "/etc", "/home", "/opt", "/tmp"],
        ),
    ],
    order_by: t.Annotated[OrderBy, "Sort order - 'size', 'name', or 'modified' (default: 'name')"] = OrderBy.NAME,
    sort: t.Annotated[SortBy, "Sort direction - 'ascending' or 'descending' (default: 'ascending')"] = SortBy.ASCENDING,
    top_n: t.Annotated[
        int | None,
        Field(
            description="Optional limit on number of files to return (1-1000)",
            gt=0,
            le=1_000,
        ),
    ] = None,
    host: Host = None,
) -> str:
    """List files under a specified path.

    Retrieves files with their size or modification time, supporting flexible
    sorting and result limiting. Useful for finding large or recently modified files.
    """
    return await _list_resources(
        path=path,
        order_by=order_by,
        sort=sort,
        top_n=top_n,
        host=host,
        command_map=FILE_COMMANDS,
        parser=parse_file_listing,
        formatter=format_file_listing,
        resource_name="files",
    )


@mcp.tool(
    title="Read file",
    description="Read the contents of a file using cat",
    tags={"files", "filesystem", "storage"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def read_file(
    path: t.Annotated[
        Path,
        BeforeValidator(validate_path),
        Field(
            description="Absolute path to the file to read",
            examples=["/etc/hosts", "/etc/resolv.conf", "/etc/os-release", "/proc/cpuinfo"],
        ),
    ],
    host: Host = None,
) -> str:
    """Read the contents of a file.

    Retrieves the full contents of a text file. The path must be absolute
    and the file must exist. Binary files may not display correctly.
    """
    if not host:
        # For local execution, check early if file exists
        if not os.path.isfile(path):
            raise ToolError(f"Path is not a file: {path}")

    cmd = get_command("read_file")

    returncode, stdout, stderr = await cmd.run_bytes(host=host, path=path)

    if returncode != 0:
        raise ToolError(f"Error running command: command failed with return code {returncode}: {stderr}")

    return stdout.decode("utf-8")
