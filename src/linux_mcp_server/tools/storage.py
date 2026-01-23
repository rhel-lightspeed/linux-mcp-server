"""Storage and hardware tools."""

import os
import typing as t

from operator import attrgetter
from pathlib import Path

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field
from pydantic.functional_validators import BeforeValidator

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.models import BlockDevices
from linux_mcp_server.models import StorageNodes
from linux_mcp_server.parsers import parse_directory_listing
from linux_mcp_server.parsers import parse_file_listing
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import StrEnum
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import is_successful_output
from linux_mcp_server.utils.validation import validate_path


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
    tags={"devices", "storage"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_block_devices(
    host: Host = None,
) -> BlockDevices:
    """List block devices.

    Retrieves all block devices (disks, partitions, LVM volumes) with their
    name, size, type, mount point, and filesystem information.
    """
    cmd = get_command("list_block_devices")
    returncode, stdout, stderr = await cmd.run(host=host)

    if not is_successful_output(returncode, stdout):
        raise ToolError(f"Unable to list block devices. lsblk command may not be available. {returncode}: {stderr}")

    return BlockDevices.model_validate_json(stdout)


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
) -> StorageNodes:
    """List directories under a specified path.

    Retrieves subdirectories with their size (when ordered by size) or
    modification time, supporting flexible sorting and result limiting.
    """
    cmd = get_command(f"list_directories_{order_by}")

    returncode, stdout, stderr = await cmd.run(host=host, path=path)

    # The du command will exit with code 1 even if it gets some valid results.
    # Only error in the case where we got non-zero exit code and no data in stdout.
    if returncode != 0 and not stdout:
        raise ToolError(f"Error running command: command failed with return code {returncode}: {stderr}")

    # Parse the output
    entries = parse_directory_listing(stdout, order_by)

    reverse = sort == SortBy.DESCENDING
    entries = sorted(entries, key=attrgetter(order_by), reverse=reverse)
    entries = entries[:top_n]

    return StorageNodes(nodes=entries)


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
            description="Optional limit on number of files to return (1-1000, only used with size ordering)",
            gt=0,
            le=1_000,
        ),
    ] = None,
    host: Host = None,
) -> StorageNodes:
    """List files under a specified path.

    Retrieves files with their size or modification time, supporting flexible
    sorting and result limiting. Useful for finding large or recently modified files.
    """
    cmd = get_command(f"list_files_{order_by}")

    returncode, stdout, stderr = await cmd.run(host=host, path=path)

    if returncode != 0:
        raise ToolError(f"Error running command: command failed with return code {returncode}: {stderr}")

    entries = parse_file_listing(stdout, order_by)

    reverse = sort == SortBy.DESCENDING
    entries = sorted(entries, key=attrgetter(order_by), reverse=reverse)
    entries = entries[:top_n]

    return StorageNodes(nodes=entries)


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
