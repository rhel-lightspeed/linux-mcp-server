"""Determining which host a tool call targets, and whether it may.

Most tools take an explicit ``host`` argument, but the script execution tools
identify a script that was validated earlier by a token, and take the host from
the stored details rather than having the model repeat it. The authorization
middleware still needs to know the target host before the tool runs, so those
tools declare where to find it with ``@target_host_from()``.

``LINUX_MCP_HOST_MODE`` narrows where tools may run. Its point is to give the
model an accurate picture of what it can do, so everything that shapes that
picture - the ``host`` parameter description, the server instructions, and the
error the model gets if it tries anyway - lives here next to the enforcement.
"""

import typing as t

from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import HostMode
from linux_mcp_server.execution_context import ExecutionContext
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.types import LOCALHOST


TargetHostResolver = t.Callable[[dict[str, t.Any]], Host]

RESOLVER_ATTRIBUTE = "__target_host_resolver__"

# What the 'host' parameter says under HostMode.REMOTE_ONLY. The other two modes need
# no entry: HostMode.ANY is what the Host annotation itself says and what the generated
# docs show, and HostMode.LOCAL_ONLY drops the parameter instead of describing it.
REMOTE_HOST_SCHEMA = {
    "description": "Remote system to connect to via SSH - this server cannot run anything on the system it runs on",
    "examples": ["web1.example.com"],
}

TARGET_HOST_INSTRUCTIONS = {
    HostMode.ANY: (
        "- **Target host:** Every tool requires a `host` argument: `localhost` runs the work on the "
        "system the MCP server runs on, any other value runs it on that host over SSH."
    ),
    HostMode.LOCAL_ONLY: (
        "- **Target host:** Tools run on the system the MCP server runs on, and take no `host` "
        "argument. This server cannot connect to other systems."
    ),
    HostMode.REMOTE_ONLY: (
        "- **Target host:** Every tool requires a `host` argument naming the system to run the work on "
        "over SSH. This server cannot run anything on the system it runs on, so `localhost` is not available."
    ),
}

# What to tell the model when 'host' is missing or isn't a host name. Middleware runs
# before argument validation, so this is our error to word, and the advice has to match
# what the mode will actually accept.
BAD_HOST_ERRORS = {
    HostMode.ANY: (
        f"The 'host' parameter is required and must be a host name - pass '{LOCALHOST}' "
        "to run on the system the MCP server runs on."
    ),
    HostMode.LOCAL_ONLY: (
        f"The 'host' parameter must be a host name. This server only runs tools on '{LOCALHOST}', "
        "so it can be left out entirely."
    ),
    HostMode.REMOTE_ONLY: (
        "The 'host' parameter is required and must name the remote system to run on, which this "
        "server connects to via SSH."
    ),
}


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


def _find_target_host(tool: Tool, arguments: dict[str, t.Any]) -> Host:
    if "host" in tool.parameters.get("properties", {}):
        if "host" not in arguments and CONFIG.host_mode == HostMode.LOCAL_ONLY:
            # adjust_tool() takes 'host' out of the schema in this mode, since there
            # is only one value it could have; fill in what the tool's own signature
            # still requires.
            arguments["host"] = LOCALHOST
            return LOCALHOST

        # The schema marks 'host' as a required string, but middleware runs before
        # argument validation, so anything the client sent gets here first.
        host = arguments.get("host")
        if not isinstance(host, str) or not host:
            raise ToolError(BAD_HOST_ERRORS[CONFIG.host_mode])
        return host

    resolver = get_target_host_resolver(tool)
    if resolver is None:
        raise RuntimeError(f"Tool '{tool.name}' has no 'host' parameter and no @target_host_from() resolver")

    return resolver(arguments)


def check_host_mode(host: Host) -> None:
    """Refuse a target host that LINUX_MCP_HOST_MODE doesn't allow.

    Never coerce: a tool call that runs somewhere other than where the model asked
    for would answer a question nobody posed.
    """
    match CONFIG.host_mode:
        case HostMode.LOCAL_ONLY if host != LOCALHOST:
            raise ToolError(
                f"This server can only run tools on '{LOCALHOST}', the system it runs on; "
                f"it cannot connect to '{host}'."
            )
        case HostMode.REMOTE_ONLY if host == LOCALHOST:
            raise ToolError(
                "This server can only run tools on remote systems reached over SSH; it cannot run "
                f"anything on '{LOCALHOST}', the system it runs on."
            )
        case _:
            pass


def resolve_target_host(tool: Tool, arguments: dict[str, t.Any]) -> Host:
    """Determine the host that a call to `tool` with `arguments` will run on.

    Raises if the configured host mode doesn't allow running there. Adds 'host' to
    `arguments` in the one case where the model isn't asked for it - see
    adjust_tool() - so the caller must pass the dict the tool will be called with.
    """

    host = _find_target_host(tool, arguments)
    check_host_mode(host)

    return host


def restrict(context: ExecutionContext) -> ExecutionContext:
    """Take out of `context` whatever LINUX_MCP_HOST_MODE doesn't allow.

    resolve_target_host() already refuses an out-of-mode host, so this changes
    nothing on its own; it means the mode still holds if anything ever reaches
    execution by another route.
    """

    match CONFIG.host_mode:
        case HostMode.LOCAL_ONLY:
            return context.model_copy(update={"allow_ssh_default": False, "ssh_key_path": None, "ssh_key_user": None})
        case HostMode.REMOTE_ONLY:
            return context.model_copy(update={"allow_local": False})
        case _:
            return context


def adjust_tool(tool: Tool) -> Tool:
    """Return `tool` with its 'host' parameter presented for the configured host mode."""

    properties = tool.parameters.get("properties", {})
    if CONFIG.host_mode == HostMode.ANY or "host" not in properties:
        return tool

    if CONFIG.host_mode == HostMode.LOCAL_ONLY:
        # There is only one host the tool could run on, so don't make the model recite
        # it on every call - that is only a chance to get it wrong. Drop the parameter
        # and let resolve_target_host() fill it in.
        parameters = {**tool.parameters, "properties": {k: v for k, v in properties.items() if k != "host"}}
        required = [name for name in parameters.get("required", []) if name != "host"]
        if required:
            parameters["required"] = required
        else:
            parameters.pop("required", None)
    else:
        host = {**properties["host"], **REMOTE_HOST_SCHEMA}
        parameters = {**tool.parameters, "properties": {**properties, "host": host}}

    return tool.model_copy(update={"parameters": parameters})


def target_host_instructions() -> str:
    """Describe where tools can run, for the server instructions."""

    return TARGET_HOST_INSTRUCTIONS[CONFIG.host_mode]
