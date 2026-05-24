"""Core MCP server for Linux diagnostics using FastMCP."""

import logging
import sys

from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from fastmcp import Context
from fastmcp import FastMCP
from fastmcp.exceptions import NotFoundError
from fastmcp.resources import ResourceContent
from fastmcp.resources import ResourceResult
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.server.middleware.middleware import CallNext
from fastmcp.utilities.components import FastMCPComponent
from mcp.types import InitializeRequest
from mcp.types import InitializeResult

import linux_mcp_server

from linux_mcp_server.auth import create_auth_provider
from linux_mcp_server.auth_policy import evaluate_policy
from linux_mcp_server.auth_policy import PolicyAction
from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import Toolset
from linux_mcp_server.config import Transport
from linux_mcp_server.mcp_app import hide_app_tools_for_client
from linux_mcp_server.mcp_app import MCP_APP_MIME_TYPE
from linux_mcp_server.mcp_app import RUN_SCRIPT_APP_URI
from linux_mcp_server.mcp_app import use_mcp_app_for_client
from linux_mcp_server.toolset import get_toolset
from linux_mcp_server.toolset import Toolset as ToolsetInfo


def monkeypatch_fastmcp_for_app_visibility():
    # fastmcp 3.2.4 has a bug where tools defined with
    # visibility=["app"] aren't returned by tools/list
    # https://github.com/PrefectHQ/fastmcp/issues/4088
    # https://github.com/PrefectHQ/fastmcp/pull/4112
    import fastmcp.server.server as m

    if hasattr(m, "_is_model_visible"):
        m._is_model_visible = lambda _tool: True


monkeypatch_fastmcp_for_app_visibility()


logger = logging.getLogger("linux-mcp-server")

INSTRUCTIONS_FIXED = """You have access to predefined commands that inspect the system. They run standard Linux utilities and return formatted results.

## Predefined command tools

These tools map to six areas:

- **System:** hostname, OS, kernel, uptime, CPU details, memory and swap, disk usage, hardware (PCI, USB, DMI).
- **Services:** list systemd units with state; status and journal output for a given unit. Unit names get a `.service` suffix when omitted.
- **Network:** interfaces and stats, active connections, listening ports and processes.
- **Processes:** full process list and detailed info for a given PID.
- **Storage and files:** block devices; list directories or files under a path (sort by size, name, or modification time); read a file. Paths must be absolute.
- **Logs:** systemd journal with filters (unit, priority, time, transport) and tail of a specific log file. Log file paths are restricted to an allowlist (LINUX_MCP_ALLOWED_LOG_PATHS).

## Behavior

- **Remote execution:** Every tool accepts an optional `host` argument. When set, the work runs on that host over SSH instead of locally.
- **Containers:** If the `container` environment variable is set, tools refuse to run locally; a remote `host` must be used.
- **Read-only vs destructive:** All tools are marked read-only. Do not expect to be able to modify the system.
- **Log file access:** requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
- **Service names:** automatically append '.service' suffix if not provided
- **File paths:** must be absolute
"""

INSTRUCTIONS_RUN_SCRIPT = """You have access to tools that validate and execute Python or Bash scripts you supply on the target system, for inspection or for making changes.
You must validate a script before it will be allowed to run.

## Script tools

- **validate_script:** Validate a Python or Bash script via an external gatekeeper for security and policy compliance. Returns a token and needs_confirmation flag.
- **run_script:** Run a validated read-only script. Use when validate_script returned needs_confirmation: false.
- **run_script_with_confirmation:** Run a validated script that modifies the system. Use when validate_script returned needs_confirmation: true.

## Workflow

1. Call validate_script with your script and set readonly appropriately.
2. Check the needs_confirmation field in the response.
3. If needs_confirmation is false, call run_script with the token.
4. If needs_confirmation is true, call run_script_with_confirmation with the same parameters and the token.

## Usage

- Set readonly to true if the script only reads the system state.
- Set readonly to false if the script modifies files or settings.
- Prefer readonly scripts when possible.
- For modifications, choose the minimal change and avoid anything that could harm stability or security.
- Describe what each script does in the description.
- Do not fetch content from the internet; use only configured repositories if installing software.
- Bash scripts run with `set -euo pipefail`; handle expected non-zero exits explicitly.
- Prefer Bash for a few shell commands and Python when logic is more involved.

## Behavior

- **Remote execution:** Every tool accepts an optional `host` argument. When set, the work runs on that host over SSH instead of locally.
- **Containers:** If the `container` environment variable is set, tools refuse to run locally; a remote `host` must be used.
- **Log file access:** requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
- **Service names:** automatically append '.service' suffix if not provided
- **File paths:** must be absolute
"""

INSTRUCTIONS_BOTH = """You have access to two kinds of tools: predefined commands that inspect the system, and script runners that execute Python or Bash you supply.

## Predefined command tools

These tools map to six areas:

- **System:** hostname, OS, kernel, uptime, CPU details, memory and swap, disk usage, hardware (PCI, USB, DMI).
- **Services:** list systemd units with state; status and journal output for a given unit. Unit names get a `.service` suffix when omitted.
- **Network:** interfaces and stats, active connections, listening ports and processes.
- **Processes:** full process list and detailed info for a given PID.
- **Storage and files:** block devices; list directories or files under a path (sort by size, name, or modification time); read a file. Paths must be absolute.
- **Logs:** systemd journal with filters (unit, priority, time, transport) and tail of a specific log file. Log file paths are restricted to an allowlist (LINUX_MCP_ALLOWED_LOG_PATHS).

## Script tools

- **validate_script:** Validate a Python or Bash script via an external gatekeeper for security and policy compliance. Returns a token and needs_confirmation flag.
- **run_script:** Run a validated read-only script. Use when validate_script returned needs_confirmation: false.
- **run_script_with_confirmation:** Run a validated script that modifies the system. Use when validate_script returned needs_confirmation: true.

## Workflow

1. Call validate_script with your script and set readonly appropriately.
2. Check the needs_confirmation field in the response.
3. If needs_confirmation is false, call run_script with the token.
4. If needs_confirmation is true, call run_script_with_confirmation with the same parameters and the token.

## Usage

- Prefer fixed commands over custom scripts when possible.
- Set readonly to true if the script only reads the system state.
- Set readonly to false if the script modifies files or settings.
- For modifications, choose the minimal change and avoid anything that could harm stability or security.
- Describe what each script does in the description.
- Do not fetch content from the internet; use only configured repositories if installing software.
- Bash scripts run with `set -euo pipefail`; handle expected non-zero exits explicitly.
- Prefer Bash for a few shell commands and Python when logic is more involved.

## Behavior

- **Remote execution:** Every tool accepts an optional `host` argument. When set, the work runs on that host over SSH instead of locally.
- **Containers:** If the `container` environment variable is set, tools refuse to run locally; a remote `host` must be used.
- **Log file access:** requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
- **Service names:** automatically append '.service' suffix if not provided
- **File paths:** must be absolute
"""


def _get_instructions() -> str:
    match CONFIG.toolset:
        case Toolset.FIXED:
            return INSTRUCTIONS_FIXED
        case Toolset.RUN_SCRIPT:
            return INSTRUCTIONS_RUN_SCRIPT
        case Toolset.BOTH:
            return INSTRUCTIONS_BOTH
        case _:  # pragma: no cover
            assert False, f"Unknown toolset configuration: {CONFIG.toolset}"


def _current_toolset():
    toolset = get_toolset(CONFIG.toolset.value)
    assert toolset is not None, f"Toolset not found in registry: {CONFIG.toolset}"

    return toolset


def _check_gatekeeper_model():
    if CONFIG.toolset != Toolset.FIXED and CONFIG.gatekeeper.model is None:
        logger.error("LINUX_MCP_GATEKEEPER__MODEL not set, this is needed for run_script tools")
        sys.exit(1)


_check_gatekeeper_model()

# Create auth provider if configured
auth_provider = create_auth_provider()

mcp = FastMCP("linux-mcp-server", version=linux_mcp_server.__version__, auth=auth_provider)


@mcp.resource(
    RUN_SCRIPT_APP_URI,
    tags={"run_script", "mcp_apps_only"},
)
def run_script_app_html() -> ResourceResult:
    filename = "run-script-app.html"

    # Try ui_resources first (wheel install)
    ui_resources_path = resources.files(linux_mcp_server).joinpath("ui_resources")
    resource_file = ui_resources_path.joinpath(filename)
    logger.debug(f"Checking for UI resource at: {resource_file}")
    # Check if we need to fall back to mcp-app/dist (editable install)
    if not resource_file.is_file():
        package_path = Path(linux_mcp_server.__file__).parent
        repo_root = package_path.parent.parent
        mcp_app_dist = repo_root / "mcp-app" / "dist" / filename
        logger.debug(f"Checking for UI resource at: {mcp_app_dist}")
        if mcp_app_dist.exists():
            resource_file = mcp_app_dist
        else:
            logger.error(f"UI resource not found: {filename}")
            raise FileNotFoundError(f"Resource {filename} not found")
    # Read the file
    try:
        html = resource_file.read_text()
        logger.info(f"Serving UI resource from: {resource_file}")
    except Exception as e:
        logger.error(f"Failed to read UI resource from {resource_file}: {e}")
        raise

    return ResourceResult(contents=[ResourceContent(html, mime_type=MCP_APP_MIME_TYPE)])


from linux_mcp_server.tools import *  # noqa: E402, F403


@dataclass
class ComponentFilter:
    """
    Determines what components (tools/resources) should be visible for a client
    given the current config.
    """

    mcp_apps: bool
    toolset: ToolsetInfo
    hide_app_tools: bool

    def includes(self, component: FastMCPComponent):
        if not self.toolset.includes_tool(component.tags):
            return False

        if self.mcp_apps:
            if "mcp_apps_exclude" in component.tags:
                return False
        else:
            if "mcp_apps_only" in component.tags:
                return False

        if self.hide_app_tools and "hidden_from_model" in component.tags:
            return False

        return True

    @staticmethod
    def get(context: Context, *, is_list_tools=False):
        mcp_apps = use_mcp_app_for_client()
        hide_app_tools = mcp_apps and is_list_tools and hide_app_tools_for_client()

        return ComponentFilter(
            mcp_apps=mcp_apps,
            toolset=_current_toolset(),
            hide_app_tools=hide_app_tools,
        )


# Middleware to enforce authorization policy
class AuthorizationMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Extract tool metadata
        tool_args = context.message.arguments or {}
        target_host = tool_args.get("host")

        assert context.fastmcp_context

        tool = await context.fastmcp_context.fastmcp.get_tool(context.message.name)
        if tool is None or not ComponentFilter.get(context.fastmcp_context).includes(tool):
            logger.error(f"Tool not found: '{context.message.name}'")
            raise NotFoundError(f"Tool not found: '{context.message.name}'")

        # For stdio without policy configured, allow everything
        if CONFIG.transport == Transport.stdio and CONFIG.policy_path is None:
            return await call_next(context)

        # For http transports log auth at INFO for audit trail info
        # For stdio use DEBUG to avoid noise
        log_level = logger.info if CONFIG.transport != Transport.stdio else logger.debug

        # Get claims from access token if available else use empty claims
        access_token = get_access_token()
        claims = access_token.claims if access_token else {}
        email = claims.get("email", "unauthenticated")

        # Log authorization attempt
        log_level(f"Tool call: {tool.name}, Host: {target_host or 'local'}, User: {email}")

        # Evaluate policy by tool, host and claims matching
        action, ssh_key_config = evaluate_policy(tool, target_host, claims)

        # Validate that action matches execution mode (should be prevented by policy validation)
        is_local_execution = not target_host

        # Block local execution with SSH action (should be prevented by policy validation)
        if is_local_execution and action in [PolicyAction.SSH_KEY, PolicyAction.SSH_DEFAULT]:
            raise RuntimeError(
                f"Policy validation error: Cannot use SSH action ('{action.value}') for local execution."
            )

        # Block remote host with local action (should be prevented by policy validation)
        if not is_local_execution and action == PolicyAction.LOCAL:
            raise RuntimeError(f"Policy validation error: Cannot use local action for remote host '{target_host}'. ")

        if action == PolicyAction.DENY:
            logger.warning(f"Authorization denied: tool={tool.name}, host={target_host or 'local'}, user={email}")
            raise ValueError(f"Authorization denied: tool '{tool.name}' on host '{target_host or 'local'}'")

        # Log the authorized action
        log_level(f"Authorized: tool={tool.name}, host={target_host or 'local'}, action={action.value}, user={email}")

        # For SSH_KEY action, validate ssh_key_config (should be prevented by policy validation)
        if action == PolicyAction.SSH_KEY:
            if not ssh_key_config:
                raise RuntimeError("Policy validation error: SSH_KEY action requires ssh_key configuration.")
            logger.debug(f"SSH key override: path={ssh_key_config.path}, user={ssh_key_config.user}")

        return await call_next(context)


class DynamicDiscoveryMiddleware(Middleware):
    """
    Implement a dynamic server that presents the right instructions, tools, and resources
    depending on the client and the current configuration.

    Our configuration is logically static, but treating it dynamic makes it much
    easier to write the appropriate tests.

    The dynamic behavior is done *per call*, not per session, since that's more future-proof.
    (Future MCP protocol versions will remove sessions entirely:
    https://modelcontextprotocol.io/seps/2575-stateless-mcp). This means doing it ourselves
    rather than using FastMCP's system for session-level enabling and disabling components,
    but it doesn't come out much worse.
    """

    async def on_initialize(
        self,
        context: MiddlewareContext[InitializeRequest],
        call_next: CallNext[InitializeRequest, InitializeResult | None],
    ) -> InitializeResult | None:
        # The instructions that we give depend on whether we are using mcp-apps
        # or not. Making this work requires some dependencies on the internals
        # of mcp and FastMCP ... the instructions that are actually returned to
        # the client are fetched from the InitializationOptions object tucked
        # away in the ServerSession object, so we need to modify that based
        # on whether we'll use mcp-apps with the client making the InitializeRequest.
        #
        # For consistency and simplicity of testing, we always set the
        # instructions this way

        assert context.fastmcp_context
        session = context.fastmcp_context.session

        instructions = _get_instructions()

        toolset = _current_toolset()
        if "run_script" in toolset.tags and use_mcp_app_for_client(context.message.params):
            instructions = instructions.replace("run_script_with_confirmation", "run_script_interactive")

        session._init_options.instructions = instructions

        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        tools = await call_next(context)

        assert context.fastmcp_context
        filter = ComponentFilter.get(context.fastmcp_context, is_list_tools=True)
        return [t for t in tools if filter.includes(t)]

    async def on_list_resources(self, context: MiddlewareContext, call_next):
        resources = await call_next(context)

        assert context.fastmcp_context
        filter = ComponentFilter.get(context.fastmcp_context)
        return [r for r in resources if filter.includes(r)]

    # on_call_tool: the filtering for this is handled in AuthorizationMiddleware
    #    (the two middlewares could be combined)
    #
    # on_read_resource: we consider it harmless if any app reads the static and
    #    public mcp-app HTML, so we don't provide a on_read_resource() handler.


mcp.add_middleware(AuthorizationMiddleware())
mcp.add_middleware(DynamicDiscoveryMiddleware())


def main():
    mcp.run(show_banner=False, transport=CONFIG.transport.value, **CONFIG.transport_kwargs)
