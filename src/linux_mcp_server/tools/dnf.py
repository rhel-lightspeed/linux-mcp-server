"""DNF package manager tools."""

import typing as t

from mcp.types import ToolAnnotations
from pydantic import Field
from pydantic.functional_validators import BeforeValidator

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.commands import get_command
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.validation import is_empty_output
from linux_mcp_server.utils.validation import validate_dnf_group_name
from linux_mcp_server.utils.validation import validate_dnf_package_name
from linux_mcp_server.utils.validation import validate_dnf_provides_query
from linux_mcp_server.utils.validation import validate_dnf_repo_id
from linux_mcp_server.utils.validation import validate_optional_dnf_module_name


DEFAULT_DNF_LIMIT = 500


def _is_package_not_found(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}".casefold()
    return "no matching packages to list" in combined or "no match for argument" in combined


def _matches_any_message(stdout: str, stderr: str, patterns: t.Sequence[str]) -> bool:
    combined = f"{stdout}\n{stderr}".casefold()
    return any(pattern in combined for pattern in patterns)


def _apply_output_limits(stdout: str, limit: int | None, offset: int, no_limit: bool) -> str:
    lines = stdout.splitlines()
    total_lines = len(lines)

    if no_limit or limit is None:
        if offset <= 0:
            return stdout

        sliced = lines[offset:]
        if not sliced:
            return "No output after applying limit/offset."

        return "\n".join(sliced)

    start = offset
    end = offset + limit
    sliced = lines[start:end]

    if not sliced:
        return "No output after applying limit/offset."

    result = "\n".join(sliced)
    if total_lines > end:
        result = f"{result}\n... output truncated: showing {len(sliced)} of {total_lines} lines"

    return result


async def _run_dnf_command(
    command_name: str,
    host: Host | None = None,
    limit: int | None = DEFAULT_DNF_LIMIT,
    offset: int = 0,
    no_limit: bool = False,
    **kwargs: object,
) -> str:
    cmd = get_command(command_name)
    returncode, stdout, stderr = await cmd.run(host=host, **kwargs)

    if returncode != 0:
        return f"Error running dnf: {stderr}"

    if is_empty_output(stdout):
        return "No output returned by dnf."

    return _apply_output_limits(stdout, limit=limit, offset=offset, no_limit=no_limit)


@mcp.tool(
    title="List installed packages (dnf)",
    description="List installed packages via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_dnf_installed_packages(
    limit: t.Annotated[
        int,
        Field(
            description="Maximum number of output lines to return",
            gt=0,
            examples=[DEFAULT_DNF_LIMIT],
        ),
    ] = DEFAULT_DNF_LIMIT,
    offset: t.Annotated[
        int,
        Field(
            description="Number of output lines to skip",
            ge=0,
            examples=[0],
        ),
    ] = 0,
    no_limit: t.Annotated[
        bool,
        Field(
            description="Disable output truncation",
            examples=[False],
        ),
    ] = False,
    host: Host = None,
) -> str:
    """List installed packages using dnf."""
    return await _run_dnf_command("dnf_list_installed", host=host, limit=limit, offset=offset, no_limit=no_limit)


@mcp.tool(
    title="List available packages (dnf)",
    description="List available packages via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_dnf_available_packages(
    limit: t.Annotated[
        int,
        Field(
            description="Maximum number of output lines to return",
            gt=0,
            examples=[DEFAULT_DNF_LIMIT],
        ),
    ] = DEFAULT_DNF_LIMIT,
    offset: t.Annotated[
        int,
        Field(
            description="Number of output lines to skip",
            ge=0,
            examples=[0],
        ),
    ] = 0,
    no_limit: t.Annotated[
        bool,
        Field(
            description="Disable output truncation",
            examples=[False],
        ),
    ] = False,
    host: Host = None,
) -> str:
    """List available packages using dnf."""
    return await _run_dnf_command("dnf_list_available", host=host, limit=limit, offset=offset, no_limit=no_limit)


@mcp.tool(
    title="Package info (dnf)",
    description="Get details for a specific package via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_dnf_package_info(
    package: t.Annotated[
        str,
        BeforeValidator(validate_dnf_package_name),
        Field(description="Package name", examples=["bash", "openssl", "vim-enhanced", "python3"]),
    ],
    host: Host = None,
) -> str:
    """Get package details using dnf."""
    cmd = get_command("dnf_package_info")
    returncode, stdout, stderr = await cmd.run(host=host, package=package)

    if _is_package_not_found(stdout, stderr):
        return f"Package '{package}' not found."

    if returncode != 0:
        return f"Error running dnf: {stderr}"

    if is_empty_output(stdout):
        return "No output returned by dnf."

    return stdout


@mcp.tool(
    title="List repositories (dnf)",
    description="List configured repositories via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_dnf_repositories(
    limit: t.Annotated[
        int,
        Field(
            description="Maximum number of output lines to return",
            gt=0,
            examples=[DEFAULT_DNF_LIMIT],
        ),
    ] = DEFAULT_DNF_LIMIT,
    offset: t.Annotated[
        int,
        Field(
            description="Number of output lines to skip",
            ge=0,
            examples=[0],
        ),
    ] = 0,
    no_limit: t.Annotated[
        bool,
        Field(
            description="Disable output truncation",
            examples=[False],
        ),
    ] = False,
    host: Host = None,
) -> str:
    """List configured repositories using dnf."""
    return await _run_dnf_command("dnf_repolist", host=host, limit=limit, offset=offset, no_limit=no_limit)


@mcp.tool(
    title="Find packages providing a file (dnf)",
    description="Find packages that provide a specific file or binary via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def dnf_provides(
    query: t.Annotated[
        str,
        BeforeValidator(validate_dnf_provides_query),
        Field(description="File path or binary name", examples=["/usr/bin/python3", "libssl.so.3", "*/libssl.so.*"]),
    ],
    host: Host = None,
) -> str:
    """Find packages providing a file or binary using dnf."""
    cmd = get_command("dnf_provides")
    returncode, stdout, stderr = await cmd.run(host=host, query=query)

    if _matches_any_message(stdout, stderr, ("no matches found", "no match for argument")):
        return f"No packages provide '{query}'."

    if returncode != 0:
        return f"Error running dnf: {stderr}"

    if is_empty_output(stdout):
        return "No output returned by dnf."

    return stdout


@mcp.tool(
    title="Repository info (dnf)",
    description="Get detailed information for a specific repository via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_dnf_repo_info(
    repo_id: t.Annotated[
        str,
        BeforeValidator(validate_dnf_repo_id),
        Field(description="Repository id", examples=["baseos", "appstream"]),
    ],
    host: Host = None,
) -> str:
    """Get repository details using dnf."""
    cmd = get_command("dnf_repo_info")
    returncode, stdout, stderr = await cmd.run(host=host, repo_id=repo_id)

    if _matches_any_message(stdout, stderr, ("no matching repo", "no repository match", "no such repository")):
        return f"Repository '{repo_id}' not found."

    if returncode != 0:
        return f"Error running dnf: {stderr}"

    if is_empty_output(stdout):
        return "No output returned by dnf."

    return stdout


@mcp.tool(
    title="List groups (dnf)",
    description="List available and installed groups via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_dnf_groups(
    limit: t.Annotated[
        int,
        Field(
            description="Maximum number of output lines to return",
            gt=0,
            examples=[DEFAULT_DNF_LIMIT],
        ),
    ] = DEFAULT_DNF_LIMIT,
    offset: t.Annotated[
        int,
        Field(
            description="Number of output lines to skip",
            ge=0,
            examples=[0],
        ),
    ] = 0,
    no_limit: t.Annotated[
        bool,
        Field(
            description="Disable output truncation",
            examples=[False],
        ),
    ] = False,
    host: Host = None,
) -> str:
    """List group information using dnf."""
    return await _run_dnf_command("dnf_group_list", host=host, limit=limit, offset=offset, no_limit=no_limit)


@mcp.tool(
    title="Group info (dnf)",
    description="Get details for a specific group via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_dnf_group_info(
    group: t.Annotated[
        str,
        BeforeValidator(validate_dnf_group_name),
        Field(description="Group name", examples=["Development Tools", "Server with GUI"]),
    ],
    host: Host = None,
) -> str:
    """Get group details using dnf."""
    cmd = get_command("dnf_group_info")
    returncode, stdout, stderr = await cmd.run(host=host, group=group)

    if _matches_any_message(stdout, stderr, ("no groups matched", "no match for argument")):
        return f"Group '{group}' not found."

    if returncode != 0:
        return f"Error running dnf: {stderr}"

    if is_empty_output(stdout):
        return "No output returned by dnf."

    return stdout


@mcp.tool(
    title="Group summary (dnf)",
    description="Show a summary of installed and available groups via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_dnf_group_summary(
    limit: t.Annotated[
        int,
        Field(
            description="Maximum number of output lines to return",
            gt=0,
            examples=[DEFAULT_DNF_LIMIT],
        ),
    ] = DEFAULT_DNF_LIMIT,
    offset: t.Annotated[
        int,
        Field(
            description="Number of output lines to skip",
            ge=0,
            examples=[0],
        ),
    ] = 0,
    no_limit: t.Annotated[
        bool,
        Field(
            description="Disable output truncation",
            examples=[False],
        ),
    ] = False,
    host: Host = None,
) -> str:
    """Get group summary using dnf."""
    return await _run_dnf_command("dnf_group_summary", host=host, limit=limit, offset=offset, no_limit=no_limit)


@mcp.tool(
    title="List modules (dnf)",
    description="List modules or filter by module name via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_dnf_modules(
    module: t.Annotated[
        str | None,
        BeforeValidator(validate_optional_dnf_module_name),
        Field(description="Optional module name filter", examples=["nodejs", "python39"]),
    ] = None,
    limit: t.Annotated[
        int,
        Field(
            description="Maximum number of output lines to return",
            gt=0,
            examples=[DEFAULT_DNF_LIMIT],
        ),
    ] = DEFAULT_DNF_LIMIT,
    offset: t.Annotated[
        int,
        Field(
            description="Number of output lines to skip",
            ge=0,
            examples=[0],
        ),
    ] = 0,
    no_limit: t.Annotated[
        bool,
        Field(
            description="Disable output truncation",
            examples=[False],
        ),
    ] = False,
    host: Host = None,
) -> str:
    """List modules using dnf."""
    cmd = get_command("dnf_module_list")
    returncode, stdout, stderr = await cmd.run(host=host, module=module)

    if module and _matches_any_message(stdout, stderr, ("no matching modules to list", "no match for argument")):
        return f"No modules matched '{module}'."

    if returncode != 0:
        return f"Error running dnf: {stderr}"

    if is_empty_output(stdout):
        return "No output returned by dnf."

    return _apply_output_limits(stdout, limit=limit, offset=offset, no_limit=no_limit)


@mcp.tool(
    title="Module provides (dnf)",
    description="Find modules that provide a specific package via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def dnf_module_provides(
    package: t.Annotated[
        str,
        BeforeValidator(validate_dnf_package_name),
        Field(description="Package name", examples=["python3", "nodejs"]),
    ],
    host: Host = None,
) -> str:
    """Find modules providing a package using dnf."""
    cmd = get_command("dnf_module_provides")
    returncode, stdout, stderr = await cmd.run(host=host, package=package)

    if _matches_any_message(stdout, stderr, ("no matching modules", "no match for argument")):
        return f"No modules provide '{package}'."

    if returncode != 0:
        return f"Error running dnf: {stderr}"

    if is_empty_output(stdout):
        return "No output returned by dnf."

    return stdout
