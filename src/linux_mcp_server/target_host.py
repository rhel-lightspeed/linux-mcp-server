"""Determining which host a tool call targets.

Most tools take an explicit ``host`` argument, but the script execution tools
identify a script that was validated earlier by a token, and take the host from
the stored details rather than having the model repeat it. The authorization
middleware still needs to know the target host before the tool runs, so those
tools declare where to find it with ``@target_host_from()``.
"""

import typing as t

from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool

from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.types import LOCALHOST


TargetHostResolver = t.Callable[[dict[str, t.Any]], Host]

RESOLVER_ATTRIBUTE = "__target_host_resolver__"


def target_host_from(resolver: TargetHostResolver):
    """Declare how to find the target host of a tool that has no 'host' parameter.

    The attribute is set on the undecorated function; since the other tool
    decorators use functools.wraps(), which copies __dict__, it is still visible
    on the function that FastMCP ends up wrapping.
    """

    def decorate(func):
        setattr(func, RESOLVER_ATTRIBUTE, resolver)
        return func

    return decorate


def get_target_host_resolver(tool: Tool) -> TargetHostResolver | None:
    """Return the resolver `tool` was decorated with, if any."""

    # Only FunctionTool has 'fn'; tools from other sources can't carry a resolver.
    return getattr(getattr(tool, "fn", None), RESOLVER_ATTRIBUTE, None)


def resolve_target_host(tool: Tool, arguments: dict[str, t.Any]) -> Host:
    """Determine the host that a call to `tool` with `arguments` would run on."""

    if "host" in tool.parameters.get("properties", {}):
        # The schema marks 'host' as a required string, but middleware runs before
        # argument validation, so anything the client sent gets here first.
        host = arguments.get("host")
        if not isinstance(host, str) or not host:
            raise ToolError(
                f"The 'host' parameter is required and must be a host name - pass '{LOCALHOST}' "
                "to run on the system the MCP server runs on."
            )
        return host

    resolver = get_target_host_resolver(tool)
    if resolver is None:
        raise RuntimeError(f"Tool '{tool.name}' has no 'host' parameter and no @target_host_from() resolver")

    return resolver(arguments)
