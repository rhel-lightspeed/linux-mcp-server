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
from linux_mcp_server.utils.validation import validate_dnf_package_name


def _is_package_not_found(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}".casefold()
    return "no matching packages to list" in combined or "no match for argument" in combined


async def _run_dnf_command(command_name: str, host: Host | None = None, **kwargs: object) -> str:
    cmd = get_command(command_name)
    returncode, stdout, stderr = await cmd.run(host=host, **kwargs)

    if returncode != 0:
        return f"Error running dnf: {stderr}"

    if is_empty_output(stdout):
        return "No output returned by dnf."

    return stdout


@mcp.tool(
    title="List installed packages (dnf)",
    description="List installed packages via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_dnf_installed_packages(
    host: Host = None,
) -> str:
    """List installed packages using dnf."""
    return await _run_dnf_command("dnf_list_installed", host=host)


@mcp.tool(
    title="List available packages (dnf)",
    description="List available packages via dnf.",
    tags={"packages", "dnf", "troubleshooting"},
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def list_dnf_available_packages(
    host: Host = None,
) -> str:
    """List available packages using dnf."""
    return await _run_dnf_command("dnf_list_available", host=host)


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
    host: Host = None,
) -> str:
    """List configured repositories using dnf."""
    return await _run_dnf_command("dnf_repolist", host=host)
