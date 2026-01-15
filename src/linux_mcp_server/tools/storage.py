"""Storage and hardware tools."""

import os
import typing as t

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

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
from linux_mcp_server.utils.validation import is_successful_output
from linux_mcp_server.utils.validation import PathValidationError
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


def _validate_path(path: str) -> str:
    """Validate path, converting PathValidationError to ToolError for MCP compatibility."""
    try:
        return validate_path(path)
    except PathValidationError as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    title="List block devices",
    description="List block devices on the system",
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
    returncode, stdout, _ = await cmd.run(host=host)

    if is_successful_output(returncode, stdout):
        return format_block_devices(stdout)

    # Fallback message if lsblk fails
    return "Error: Unable to list block devices. lsblk command may not be available."


@mcp.tool(
    title="List directories",
    description="List directories under a specified path with various sorting options.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_directories(
    path: t.Annotated[str, "The directory path to analyze"],
    order_by: t.Annotated[OrderBy, "Sort order - 'size', 'name', or 'modified' (default: 'name')"] = OrderBy.NAME,
    sort: t.Annotated[SortBy, "Sort direction - 'ascending' or 'descending' (default: 'ascending')"] = SortBy.ASCENDING,
    top_n: t.Annotated[
        int | None,
        Field(
            description="Optional limit on number of directories to return (1-1000, only used with size ordering)",
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
    path = _validate_path(path)

    # Get the appropriate command for the order_by field
    cmd_name = DIRECTORY_COMMANDS[order_by]
    cmd = get_command(cmd_name)

    returncode, stdout, stderr = await cmd.run(host=host, path=path)

    if returncode != 0:
        raise ToolError(f"Error running command: command failed with return code {returncode}: {stderr}")

    # Parse the output
    entries = parse_directory_listing(stdout, order_by)

    # Apply top_n limit if specified
    if top_n:
        # Sort first if we need to limit
        if order_by == OrderBy.SIZE:
            entries = sorted(entries, key=lambda e: e.size, reverse=sort == SortBy.DESCENDING)
        elif order_by == OrderBy.MODIFIED:
            entries = sorted(entries, key=lambda e: e.modified, reverse=sort == SortBy.DESCENDING)
        else:
            entries = sorted(entries, key=lambda e: e.name.lower(), reverse=sort == SortBy.DESCENDING)
        entries = entries[:top_n]

    # Format the output
    return format_directory_listing(entries, path, order_by, reverse=sort == SortBy.DESCENDING)


@mcp.tool(
    title="List files",
    description="List files under a specified path with various sorting options.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_files(
    path: t.Annotated[str, "The path to analyze"],
    order_by: t.Annotated[OrderBy, "Sort order - 'size', 'name', or 'modified' (default: 'name')"] = OrderBy.NAME,
    sort: t.Annotated[SortBy, "Sort direction - 'ascending' or 'descending' (default: 'ascending')"] = SortBy.ASCENDING,
    top_n: t.Annotated[
        int | None,
        Field(
            description="Optional limit on number of files to return (1-1000, only used with size ordering)",
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
    # For local execution, validate path
    if not host:
        path = _validate_path(path)

    # Get the appropriate command for the order_by field
    cmd_name = FILE_COMMANDS[order_by]
    cmd = get_command(cmd_name)

    returncode, stdout, stderr = await cmd.run(host=host, path=path)

    if returncode != 0:
        raise ToolError(f"Error running command: command failed with return code {returncode}: {stderr}")

    # Parse the output
    entries = parse_file_listing(stdout, order_by)

    # Apply top_n limit if specified
    if top_n:
        # Sort first if we need to limit
        if order_by == OrderBy.SIZE:
            entries = sorted(entries, key=lambda e: e.size, reverse=sort == SortBy.DESCENDING)
        elif order_by == OrderBy.MODIFIED:
            entries = sorted(entries, key=lambda e: e.modified, reverse=sort == SortBy.DESCENDING)
        else:
            entries = sorted(entries, key=lambda e: e.name.lower(), reverse=sort == SortBy.DESCENDING)
        entries = entries[:top_n]

    # Format the output
    return format_file_listing(entries, path, order_by, reverse=sort == SortBy.DESCENDING)


@mcp.tool(
    title="Read file",
    description="Read the contents of a file using cat",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def read_file(
    path: t.Annotated[str, "The file path to read"],
    host: Host = None,
) -> str:
    """Read the contents of a file.

    Retrieves the full contents of a text file. The path must be absolute
    and the file must exist. Binary files may not display correctly.
    """

    # Validate path
    path = _validate_path(path)

    if not host:
        # For local execution, check early if file exists
        if not os.path.isfile(path):
            raise ToolError(f"Path is not a file: {path}")

    cmd = get_command("read_file")

    returncode, stdout, stderr = await cmd.run_bytes(host=host, path=path)

    if returncode != 0:
        raise ToolError(f"Error running command: command failed with return code {returncode}: {stderr}")

    return stdout.decode("utf-8")
