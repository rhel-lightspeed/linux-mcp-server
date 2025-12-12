"""Storage and hardware tools."""

import base64
import json
import typing as t

from pathlib import Path

from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ansible import execute_ansible_module
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import StrEnum
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


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
async def list_block_devices(host: Host | None = None) -> str:
    """List block devices using Ansible setup module.

    Args:
        host: Optional remote host address

    Returns:
        JSON string with block device information
    """
    result = await execute_ansible_module(
        module="setup",
        module_args={"gather_subset": ["!all", "!min", "devices"]},
        host=host,
    )

    devices = result.get("ansible_facts", {}).get("ansible_devices", {})
    return json.dumps(devices, indent=2)


async def _execute_find_ansible(
    path: str,
    file_type: str,
    host: Host | None = None,
) -> list[dict[str, t.Any]]:
    """Execute Ansible find module for directories or files.

    Args:
        path: Path to search in
        file_type: Either "directory" or "file"
        host: Optional remote host address (None = localhost)

    Returns:
        List of file/directory dictionaries from Ansible find module
    """
    result = await execute_ansible_module(
        module="find",
        module_args={
            "paths": path,
            "file_type": file_type,
            "recurse": False,
        },
        host=host,
    )

    return result.get("files", [])


def _parse_ansible_find_results(
    files: list[dict[str, t.Any]],
    order_by: OrderBy,
) -> list[NodeEntry]:
    """Parse Ansible find module results into NodeEntry objects.

    Args:
        files: List of file dicts from Ansible find module
        order_by: Which field to populate based on ordering

    Returns:
        List of NodeEntry objects
    """
    nodes = []
    for file_info in files:
        # Extract basename from full path
        name = Path(file_info["path"]).name

        match order_by:
            case OrderBy.SIZE:
                nodes.append(NodeEntry(size=int(file_info.get("size", 0)), name=name))
            case OrderBy.NAME:
                nodes.append(NodeEntry(name=name))
            case OrderBy.MODIFIED:
                nodes.append(NodeEntry(modified=float(file_info.get("mtime", 0.0)), name=name))

    return nodes


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
    """List directories using Ansible find module."""
    files = await _execute_find_ansible(path, "directory", host)
    nodes = _parse_ansible_find_results(files, order_by)

    # Sort and apply limits
    nodes.sort(key=lambda x: getattr(x, order_by), reverse=sort == SortBy.DESCENDING)
    if top_n:
        return nodes[:top_n]
    return nodes


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
    """List files using Ansible find module."""
    files = await _execute_find_ansible(path, "file", host)
    nodes = _parse_ansible_find_results(files, order_by)

    # Sort and apply limits
    nodes.sort(key=lambda x: getattr(x, order_by), reverse=sort == SortBy.DESCENDING)
    if top_n:
        return nodes[:top_n]
    return nodes


@mcp.tool(
    title="Read file",
    description="Read the contents of a file",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def read_file(
    path: t.Annotated[str, Field(description="The file path to read")],
    host: Host | None = None,
) -> str:
    """Read the contents of a file using Ansible slurp module.

    Args:
        path: File path to read
        host: Optional remote host address (None = localhost)

    Returns:
        File contents as string

    Raises:
        ToolError: If file doesn't exist or can't be read
    """
    result = await execute_ansible_module(
        module="slurp",
        module_args={"src": path},
        host=host,
    )

    # Decode base64 content from Ansible slurp
    content_b64 = result.get("content", "")
    try:
        return base64.b64decode(content_b64).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as e:
        raise ToolError(f"Failed to decode file content from {path}: {e}") from e
