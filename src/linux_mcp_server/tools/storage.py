"""Storage and hardware tools."""

import os
import typing as t

from pathlib import Path

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.commands import substitute_command_args
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.formatters import format_block_devices
from linux_mcp_server.formatters import format_directory_listing
from linux_mcp_server.formatters import format_file_listing
from linux_mcp_server.parsers import parse_directory_listing
from linux_mcp_server.parsers import parse_file_listing
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import StrEnum
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


class OrderBy(StrEnum):
    SIZE = "size"
    NAME = "name"
    MODIFIED = "modified"


class SortBy(StrEnum):
    ASCENDING = "ascending"
    DESCENDING = "descending"


# Map OrderBy enum to command names
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
    """Validate path for command and flag injection."""
    if not path or any(c in path for c in ["\n", "\r", "\x00"]):
        raise ToolError("Invalid path (cannot contain newlines, carriage returns, or null bytes).")
    if path.startswith("-"):
        raise ToolError("Invalid path (cannot start with '-').")
    if not Path(path).is_absolute():
        raise ToolError("Invalid path (must be absolute).")
    return Path(path).as_posix()


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
        cmd = get_command("list_block_devices")
        returncode, stdout, _ = await execute_command(cmd.args, host=host)

        if returncode == 0 and stdout:
            return format_block_devices(stdout)

        # Fallback message if lsblk fails
        return "Error: Unable to list block devices. lsblk command may not be available."
    except FileNotFoundError:
        return "Error: lsblk command not found."
    except Exception as e:
        return f"Error listing block devices: {str(e)}"


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
) -> str:
    """
    List directories under a specified path.
    """
    path = _validate_path(path)

    # Get the appropriate command for the order_by field
    cmd_name = DIRECTORY_COMMANDS[order_by]
    cmd = get_command(cmd_name)

    # Substitute path into command args
    args = substitute_command_args(cmd.args, path=path)

    try:
        returncode, stdout, stderr = await execute_command(args, host=host)

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

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error listing directories: {str(e)}") from e


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
) -> str:
    """
    List files under a specified path.
    """
    # For local execution, validate path
    if not host:
        path = _validate_path(path)

    # Get the appropriate command for the order_by field
    cmd_name = FILE_COMMANDS[order_by]
    cmd = get_command(cmd_name)

    # Substitute path into command args
    args = substitute_command_args(cmd.args, path=path)

    try:
        returncode, stdout, stderr = await execute_command(args, host=host)

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

    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error listing files: {str(e)}") from e


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

    cmd = get_command("read_file")
    args = substitute_command_args(cmd.args, path=path)

    try:
        returncode, stdout, stderr = await execute_command(args, host=host)

        if returncode != 0:
            raise ToolError(f"Error running command: command failed with return code {returncode}: {stderr}")

        return stdout
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(f"Error reading file: {str(e)}") from e
