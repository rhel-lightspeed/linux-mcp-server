"""Core MCP server for Linux diagnostics using FastMCP."""

import logging
import sys

from importlib import resources
from pathlib import Path
from types import CellType
from types import CodeType

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.server.middleware.middleware import CallNext
from mcp import ServerSession
from mcp.types import BlobResourceContents
from mcp.types import InitializeRequest
from mcp.types import InitializeRequestParams
from mcp.types import InitializeResult
from mcp.types import ReadResourceRequest
from mcp.types import ReadResourceResult
from mcp.types import ServerResult
from mcp.types import TextResourceContents

import linux_mcp_server

from linux_mcp_server.auth import create_auth_provider
from linux_mcp_server.auth_policy import evaluate_policy
from linux_mcp_server.auth_policy import PolicyAction
from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import Toolset
from linux_mcp_server.config import Transport
from linux_mcp_server.mcp_app import ALLOWED_UI_RESOURCE_URIS
from linux_mcp_server.mcp_app import MCP_APP_MIME_TYPE
from linux_mcp_server.mcp_app import MCP_UI_EXTENSION


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


kwargs = {}

match CONFIG.toolset:
    case Toolset.FIXED:
        instructions = INSTRUCTIONS_FIXED
        kwargs["exclude_tags"] = {"run_script"}
    case Toolset.RUN_SCRIPT:
        instructions = INSTRUCTIONS_RUN_SCRIPT
        kwargs["include_tags"] = {"run_script"}
    case Toolset.BOTH:
        instructions = INSTRUCTIONS_BOTH
    case _:
        assert False, f"Unknown toolset configuration: {CONFIG.toolset}"

if CONFIG.toolset != Toolset.FIXED and CONFIG.gatekeeper_model is None:
    logger.error("LINUX_MCP_GATEKEEPER_MODEL not set, this is needed for run_script tools")
    sys.exit(1)

# Create auth provider if configured
auth_provider = create_auth_provider()

mcp = FastMCP(
    "linux-mcp-server", instructions=instructions, version=linux_mcp_server.__version__, auth=auth_provider, **kwargs
)


_low_level_server = mcp._mcp_server
_original_resource_request_handler = _low_level_server.request_handlers[ReadResourceRequest]


async def _read_resource_with_meta(req: ReadResourceRequest):
    uri = str(req.params.uri)
    fallback_contents: list[TextResourceContents | BlobResourceContents] = [
        TextResourceContents(uri=req.params.uri, mimeType="text/plain", text="Resource not found")
    ]

    if uri.startswith("ui://"):
        if uri in ALLOWED_UI_RESOURCE_URIS:
            filename = uri.split("/")[-1]

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

            content = TextResourceContents.model_validate(
                {
                    "uri": uri,
                    "mimeType": MCP_APP_MIME_TYPE,
                    "text": html,
                }
            )

            return ServerResult(ReadResourceResult(contents=[content]))
    else:
        if _original_resource_request_handler:
            return await _original_resource_request_handler(req)

    return ServerResult(ReadResourceResult(contents=fallback_contents))


_low_level_server.request_handlers[ReadResourceRequest] = _read_resource_with_meta


from linux_mcp_server.tools import *  # noqa: E402, F403


def _use_mcp_app_for_client(client_params: InitializeRequestParams):
    # The configuration can overwrite the MCP app support detection, so we have the flexibility to
    # manually turn the Mcp app feature on/off for developing/testing purposes.
    if CONFIG.use_mcp_apps is not None:
        return CONFIG.use_mcp_apps

    # For python-sdk -1.x, count on extensibility of protocol types - while this is being
    # removed for v2, hopefully extensions will be there properly.
    capabilities = client_params.capabilities
    extensions = getattr(capabilities, "extensions", {})
    mcp_ui_extension = extensions.get(MCP_UI_EXTENSION) or {}
    mime_types = mcp_ui_extension.get("mimeTypes") or []

    # The configuration can overwrite the MCP app support detection, so we have the flexibility to
    # manually turn the Mcp app feature on/off for developing/testing purposes.
    return MCP_APP_MIME_TYPE in mime_types


# Middleware to enforce authorization policy
class AuthorizationMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Extract tool metadata
        tool_name = context.message.name
        tool_args = context.message.arguments or {}
        target_host = tool_args.get("host")

        # Get tool tags from FastMCP (needed for policy evaluation)
        if context.fastmcp_context is None:
            logger.error("FastMCP context not available in middleware")
            raise ValueError("Internal error: FastMCP context not available")

        tool = await context.fastmcp_context.fastmcp.get_tool(tool_name)
        tool_tags = tool.tags if tool.tags else set()

        # Skip authorization for stdio transport when auth is not configured
        # For HTTP, auth is required or explicit allow_unauthorized in policy
        if CONFIG.auth is None:
            if CONFIG.transport == Transport.stdio:
                return await call_next(context)

            # For HTTP without auth, check if policy allows unauthorized access
            if CONFIG.policy_path is None:
                logger.error("HTTP transport requires either authentication or a policy with allow_unauthorized")
                raise ValueError("Authentication required for HTTP transport")

            # Check policy with empty claims to see if unauthorized access is allowed
            action, ssh_key_config, allow_unauthorized = evaluate_policy(tool_name, tool_tags, target_host, {})

            if not allow_unauthorized:
                logger.warning(f"Unauthorized HTTP request denied: tool={tool_name}, host={target_host or 'local'}")
                raise ValueError("Authentication required: no policy rule allows unauthorized access")

            logger.info(
                f"Allowing unauthorized HTTP request via policy: tool={tool_name}, host={target_host or 'local'}, action={action.value}"
            )

            # Validate that action matches execution mode
            is_local_execution = not target_host

            # Block local execution with SSH action
            if is_local_execution and action in [PolicyAction.SSH_KEY, PolicyAction.SSH_DEFAULT]:
                logger.error(f"Policy error: SSH action for local execution - tool={tool_name}, action={action.value}")
                raise ValueError(f"Authorization denied: Cannot use SSH action ('{action.value}') for local execution")

            # Block remote host with local action
            if not is_local_execution and action == PolicyAction.LOCAL:
                logger.error(f"Policy error: Local action for remote host: tool={tool_name}, host={target_host}")
                raise ValueError(f"Authorization denied: Cannot use local action for remote host '{target_host}'")

            if action == PolicyAction.DENY:
                logger.warning(f"Authorization denied: tool={tool_name}, host={target_host or 'local'}")
                raise ValueError(f"Authorization denied: tool '{tool_name}' on host '{target_host or 'local'}'")

            # For SSH_KEY action, validate ssh_key_config
            if action == PolicyAction.SSH_KEY:
                if not ssh_key_config:
                    logger.error(f"Policy error: SSH_KEY action requires ssh_key configuration - tool={tool_name}")
                    raise ValueError(
                        "Authorization denied: SSH_KEY action requires ssh_key configuration in policy rule"
                    )
                logger.debug(f"SSH key override: path={ssh_key_config.path}, user={ssh_key_config.user}")

            # Unauthorized request is allowed, proceed without further auth checks
            return await call_next(context)

        # For http transports log auth at INFO for audit trail info
        # For stdio use DEBUG to avoid noise
        log_level = logger.info if CONFIG.transport != Transport.stdio else logger.debug

        # Get authenticated user claims
        try:
            access_token = get_access_token()
            if not access_token:
                logger.warning("No authentication token, request denied")
                raise ValueError("Authentication required")

            claims = access_token.claims
            email = claims.get("email", "unknown")
        except Exception as e:
            logger.error(f"Failed to get access token: {e}")
            raise ValueError(f"Authentication error: {e}") from e

        # Log authorization attempt
        log_level(f"Tool call: {tool_name}, Host: {target_host}, User: {email}")

        # If auth policy is configured evaluate it
        if CONFIG.policy_path is not None:
            action, ssh_key_config, allow_unauthorized = evaluate_policy(tool_name, tool_tags, target_host, claims)

            # Validate that action matches execution mode
            is_local_execution = not target_host

            # Block local execution with SSH action
            if is_local_execution and action in [PolicyAction.SSH_KEY, PolicyAction.SSH_DEFAULT]:
                logger.error(
                    f"Policy error: SSH action for local execution - tool={tool_name}, action={action.value}, user={email}"
                )
                raise ValueError(f"Authorization denied: Cannot use SSH action ('{action.value}') for local execution")

            # Block remote host with local action
            if not is_local_execution and action == PolicyAction.LOCAL:
                logger.error(
                    f"Policy error: Local action for remote host: tool={tool_name}, host={target_host}, user={email}"
                )
                raise ValueError(f"Authorization denied: Cannot use local action for remote host '{target_host}'")

            if action == PolicyAction.DENY:
                logger.warning(f"Authorization denied: tool={tool_name}, host={target_host or 'local'}, user={email}")
                raise ValueError(f"Authorization denied: tool '{tool_name}' on host '{target_host or 'local'}'")

            # Log the authorized action
            log_level(
                f"Authorized: tool={tool_name}, host={target_host or 'local'}, action={action.value}, user={email}"
            )

            # LOCAL and SSH_DEFAULT already handled by execute_command()
            # TODO: Pass ssh_key_config (path and user) to connection manager for SSH_KEY action
            if action == PolicyAction.SSH_KEY:
                if not ssh_key_config:
                    logger.error(
                        f"Policy error: SSH_KEY action requires ssh_key configuration: tool={tool_name}, user={email}"
                    )
                    raise ValueError(
                        "Authorization denied: SSH_KEY action requires ssh_key configuration in policy rule"
                    )
                logger.debug(f"SSH key override: path={ssh_key_config.path}, user={ssh_key_config.user}")

        return await call_next(context)


# Middleware to log authenticated user
class AuthLoggingMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # For http transports log auth at INFO for audit trail info
        # For stdio use DEBUG to avoid noise
        log_level = logger.info if CONFIG.transport != Transport.stdio else logger.debug

        try:
            access_token = get_access_token()
            if access_token:
                log_level(f"Authentication email: {access_token.claims['email']}")
            else:
                log_level("No authentication token present")
        except Exception as e:
            log_level(f"Could not get access token: {e}")

        return await call_next(context)


class DynamicDiscoveryMiddleware(Middleware):
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

        if _use_mcp_app_for_client(context.message.params):
            # Getting the ServerSession object is easy for FastMCP 3.x - it's
            # just context.fastcmp_context.session, but the property getter
            # will raise RuntimeError for FastMCP 2.x, so we check _session instead.
            assert context.fastmcp_context is not None, "fastmcp_context should be set in on_initialize"
            session: ServerSession | None = getattr(context.fastmcp_context, "_session", None)
            if session is None:
                # FastMCP 2.x - let's pull out the hacks! call_next is a closure within a method
                # of fastmcp.server.low_level.MiddlewareServerSession. The "self" variable used
                # in the closure is what we need. Assuming CPython, we can dig and and get it!
                code: CodeType | None = getattr(call_next, "__code__", None)
                closure: tuple[CellType, ...] | None = getattr(call_next, "__closure__", None)
                if code and closure:
                    # co_freevars gives us the names of the variables captured in __closure__
                    closure_dict = dict(zip(code.co_freevars, [c.cell_contents for c in closure]))
                    session = closure_dict.get("self")

            if session and isinstance(session, ServerSession):
                instructions = session._init_options.instructions
                if instructions:
                    session._init_options.instructions = instructions.replace(
                        "run_script_with_confirmation", "run_script_interactive"
                    )
            else:
                logger.warning("Unable to get ServerSession to update instructions for mcp-apps")

        return await call_next(context)

    async def on_list_tools(self, context: MiddlewareContext, call_next):
        tools = await call_next(context)

        # Eventually, the tagging of the tools via _meta.ui.visiblity as "app" or "model" will
        # hide this tool but Goose doesn't support this yet. On the other hand, goose is happy
        # if the app calls tools we don't list at all, so we just filter out the "app" tools
        filtered_tools = [t for t in tools if "hidden_from_model" not in (t.tags)]

        fastmcp_context = context.fastmcp_context
        assert fastmcp_context is not None, (
            "FastMCP framework error: context.fastmcp_context should not be None inside on_list_tools"
        )

        request_ctx = fastmcp_context.request_context
        assert request_ctx is not None, (
            "FastMCP framework error: request context should not be None inside on_list_tools"
        )

        client_params = request_ctx.session.client_params
        assert client_params is not None, (
            "FastMCP framework error: client_params should not be None inside on_list_tools"
        )

        if _use_mcp_app_for_client(client_params):
            filtered_tools = [t for t in filtered_tools if "mcp_apps_exclude" not in t.tags]
        else:
            filtered_tools = [t for t in filtered_tools if "mcp_apps_only" not in t.tags]

        return filtered_tools


def main():
    mcp.add_middleware(AuthorizationMiddleware())
    mcp.add_middleware(AuthLoggingMiddleware())
    mcp.add_middleware(DynamicDiscoveryMiddleware())
    mcp.run(show_banner=False, transport=CONFIG.transport.value, **CONFIG.transport_kwargs)
