"""Core MCP server for Linux diagnostics using FastMCP."""

import asyncio
import functools
import logging
import time
import uuid

from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any
from typing import get_type_hints

from fastmcp import Context
from fastmcp import FastMCP
from fastmcp.exceptions import NotFoundError
from fastmcp.exceptions import ToolError
from fastmcp.resources import ResourceContent
from fastmcp.resources import ResourceResult
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.dependencies import get_http_request
from fastmcp.server.middleware import Middleware
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.server.middleware.middleware import CallNext
from fastmcp.tools import Tool
from fastmcp.utilities.components import FastMCPComponent
from mcp.types import InitializeRequest
from mcp.types import InitializeResult

import linux_mcp_server

from linux_mcp_server.audit import audit_context
from linux_mcp_server.audit import Event
from linux_mcp_server.audit import log_event
from linux_mcp_server.auth import create_auth_provider
from linux_mcp_server.auth import normalize_claims
from linux_mcp_server.auth_policy import evaluate_policy
from linux_mcp_server.auth_policy import PolicyAction
from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import Toolset
from linux_mcp_server.config import Transport
from linux_mcp_server.execution_context import ExecutionContext
from linux_mcp_server.execution_context import use_execution_context
from linux_mcp_server.mcp_app import hide_app_tools_for_client
from linux_mcp_server.mcp_app import MCP_APP_MIME_TYPE
from linux_mcp_server.mcp_app import RUN_SCRIPT_APP_URI
from linux_mcp_server.mcp_app import use_mcp_app_for_client
from linux_mcp_server.redaction.apply import redact_tool_output
from linux_mcp_server.redaction.engine import RedactionEngine
from linux_mcp_server.target_host import adjust_tool
from linux_mcp_server.target_host import resolve_target_host
from linux_mcp_server.target_host import restrict
from linux_mcp_server.target_host import target_host_instructions
from linux_mcp_server.tool_result import ToolResult
from linux_mcp_server.toolset import get_toolset
from linux_mcp_server.toolset import Toolset as ToolsetInfo
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.types import LOCALHOST


def monkeypatch_fastmcp_for_app_visibility():
    # fastmcp 3.2.4 has a bug where tools defined with
    # visibility=["app"] aren't returned by tools/list
    # https://github.com/PrefectHQ/fastmcp/issues/4088
    # https://github.com/PrefectHQ/fastmcp/pull/4112
    import fastmcp.server.server as m

    if hasattr(m, "_is_model_visible"):
        setattr(m, "_is_model_visible", lambda _tool: True)


monkeypatch_fastmcp_for_app_visibility()


logger = logging.getLogger(__name__)

INSTRUCTIONS_FIXED = """You have access to predefined commands that inspect the system. They run standard Linux utilities and return formatted results.

## Predefined command tools

These tools map to seven areas:

- **System:** hostname, OS, kernel, uptime, CPU details, memory and swap, disk usage, hardware (PCI, USB, DMI).
- **Services:** list systemd units with state; status and journal output for a given unit. Unit names get a `.service` suffix when omitted.
- **Network:** interfaces and stats, active connections, listening ports and processes.
- **Processes:** full process list and detailed info for a given PID.
- **Storage and files:** block devices; list directories or files under a path (sort by size, name, or modification time); read a file. Paths must be absolute.
- **Logs:** systemd journal with filters (unit, priority, time, transport) and tail of a specific log file. Log file paths are restricted to an allowlist (LINUX_MCP_ALLOWED_LOG_PATHS).
- **Performance (PCP):** historical metric data from PCP archives; available metrics; performance summaries at a point in time.

## Behavior

{target_host}
- **Read-only vs destructive:** All tools are marked read-only. Do not expect to be able to modify the system.
- **Log file access:** requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
- **Service names:** automatically append '.service' suffix if not provided
- **File paths:** must be absolute
- **PCP metric names:** Before investigating performance with the PCP tools, call the `pcp_guide` tool. It lists the metrics recorded on a typical system and explains how to read the values returned. Do not guess metric names from memory.
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

{target_host}
- **Log file access:** requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
- **Service names:** automatically append '.service' suffix if not provided
- **File paths:** must be absolute
"""

INSTRUCTIONS_BOTH = """You have access to two kinds of tools: predefined commands that inspect the system, and script runners that execute Python or Bash you supply.

## Predefined command tools

These tools map to seven areas:

- **System:** hostname, OS, kernel, uptime, CPU details, memory and swap, disk usage, hardware (PCI, USB, DMI).
- **Services:** list systemd units with state; status and journal output for a given unit. Unit names get a `.service` suffix when omitted.
- **Network:** interfaces and stats, active connections, listening ports and processes.
- **Processes:** full process list and detailed info for a given PID.
- **Storage and files:** block devices; list directories or files under a path (sort by size, name, or modification time); read a file. Paths must be absolute.
- **Logs:** systemd journal with filters (unit, priority, time, transport) and tail of a specific log file. Log file paths are restricted to an allowlist (LINUX_MCP_ALLOWED_LOG_PATHS).
- **Performance (PCP):** historical metric data from PCP archives; available metrics; performance summaries at a point in time.

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

{target_host}
- **Log file access:** requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
- **Service names:** automatically append '.service' suffix if not provided
- **File paths:** must be absolute
- **PCP metric names:** Before investigating performance with the PCP tools, call the `pcp_guide` tool. It lists the metrics recorded on a typical system and explains how to read the values returned. Do not guess metric names from memory.
"""


def _get_instructions() -> str:
    match CONFIG.toolset:
        case Toolset.FIXED:
            instructions = INSTRUCTIONS_FIXED
        case Toolset.RUN_SCRIPT:
            instructions = INSTRUCTIONS_RUN_SCRIPT
        case Toolset.BOTH:
            instructions = INSTRUCTIONS_BOTH
        case _:  # pragma: no cover
            assert False, f"Unknown toolset configuration: {CONFIG.toolset}"

    return instructions.replace("{target_host}", target_host_instructions())


def _current_toolset():
    toolset = get_toolset(CONFIG.toolset.value)
    assert toolset is not None, f"Toolset not found in registry: {CONFIG.toolset}"

    return toolset


# Sent when redaction fails. Doesn't include the value or the error, since whichever
# one could not be scanned is the one that might be carrying a secret.
REDACTION_FAILURE_MESSAGE = "Tool output could not be safely returned."


def _create_redaction_engine() -> RedactionEngine | None:
    if not CONFIG.redaction.enabled:
        logger.info("Redaction disabled")
        return None

    if CONFIG.redaction.rules_path is None:
        logger.info("Redaction enabled with built-in credential rules")
        return RedactionEngine()

    logger.info(f"Redaction enabled with rules from {CONFIG.redaction.rules_path}")
    return RedactionEngine.from_yaml_file(CONFIG.redaction.rules_path)


redaction_engine = _create_redaction_engine()


def _redacting(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a tool function so that what it returns is scanned before it is rendered.

    Scanning here rather than on the rendered result means both the text and the
    structured content FastMCP produces come from data already clean, instead of
    needing to be scanned separately once JSON escaping has respelled it.

    Errors are left alone: they are redacted in AuthorizationMiddleware, which is also
    where they are logged.
    """

    @functools.wraps(fn)
    async def redacting(*args: Any, **kwargs: Any) -> Any:
        result = await fn(*args, **kwargs)

        try:
            return redact_tool_output(result, redaction_engine)
        except Exception:
            # The one place we write unscanned text to the log: scanning is what just
            # failed, so the traceback - and the message of anything in its chain -
            # goes out as it is. Accepted to make a rule that blows up diagnosable at
            # all; the client is told nothing but the fixed message.
            logger.exception("Redaction failed; withholding tool output")
            raise ToolError(REDACTION_FAILURE_MESSAGE)

    return redacting


class RedactingFastMCP(FastMCP):
    """A FastMCP server that scans everything its tools return.

    Registering is the hook, rather than a decorator each tool module has to remember
    to use: ``@mcp.tool`` is the only way a tool reaches the server, so there is no
    second path by which unscanned output could reach a client.
    """

    def tool(self, name_or_fn: str | Callable[..., Any] | None = None, **kwargs: Any) -> Any:
        register = super().tool

        if callable(name_or_fn):
            return register(_redacting(name_or_fn), **_tool_kwargs(name_or_fn, kwargs))

        def decorator(fn: Callable[..., Any]) -> Any:
            return register(name_or_fn, **_tool_kwargs(fn, kwargs))(_redacting(fn))

        return decorator


def _tool_kwargs(fn: Callable[..., Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Suppress the output schema FastMCP would derive from our own ToolResult.

    A tool returning one says what its two halves are rather than describing the data
    in them, so there is nothing for FastMCP to generate a schema from. (It does this
    for its own ToolResult, but only knows to for that one type.)
    """
    if get_type_hints(fn).get("return") is ToolResult:
        kwargs.setdefault("output_schema", None)

    return kwargs


# Create auth provider if configured
auth_provider = create_auth_provider()

mcp = RedactingFastMCP("linux-mcp-server", version=linux_mcp_server.__version__, auth=auth_provider)


@mcp.resource(
    RUN_SCRIPT_APP_URI,
    tags={"run_script", "mcp_apps_only"},
)
def run_script_app_html() -> ResourceResult:
    ui_dir = resources.files(linux_mcp_server).joinpath("ui_resources")
    html = ui_dir.joinpath("run-script-app.html").read_text()
    css = ui_dir.joinpath("run-script-app.css").read_text()
    js = ui_dir.joinpath("run-script-app.js").read_text()
    html = html.replace("/* __CSS__ */", css).replace("/* __JS__ */", js)
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


def _redacted_error(error: BaseException) -> BaseException:
    """Return the exception to report for a failed tool call, with its message scanned.

    A tool quoting the output it was reading into an error message is an ordinary way
    for a secret to get out, so this sits next to the logging of that message: both
    the audit log and the client see the same, scanned, text.

    The message is all that is scanned, because the message is all that is reported:
    neither the client nor the audit log is shown a traceback or an exception chain.
    Were that to change - `logger.exception`, `exc_info=`, anything that formats a
    chain - the scanning would have to grow to match, because a cause can hold text
    the proximate message does not: `raise ToolError("could not read config") from
    OSError(secret)` comes through here looking clean.

    An error with nothing to redact is handed back untouched; there is nothing to be
    gained by rebuilding it. One that had something redacted is rebuilt with its own
    type, since that is what decides whether FastMCP reports the message or replaces
    it. An error that cannot be rebuilt, or scanned, becomes the fixed message.

    One chain is already logged, and not by us: for anything that isn't a FastMCPError
    - a plain OSError out of a tool, say - FastMCP logs the exception with its
    traceback before the middleware ever sees it. (A ToolError it logs without one.)
    Closing that means catching the error back in the tool wrapper, which runs inside
    the try that logs it, and redacting a chain in place rather than rebuilding a
    single exception.
    """
    engine = redaction_engine
    if engine is None:
        return error

    try:
        message = str(error)
        redacted = engine.redact(message)
        if redacted == message:
            return error

        return type(error)(redacted)
    except Exception:
        # Logged with its traceback, unscanned, for the reason given where the scan of
        # a tool's output fails.
        logger.exception("Redaction failed; withholding tool error")
        return ToolError(REDACTION_FAILURE_MESSAGE)


# Middleware to enforce authorization policy
class AuthorizationMiddleware(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        tool_args = context.message.arguments = context.message.arguments or {}
        parameters = {key: value for key, value in tool_args.items() if key != "ctx"}

        access_token = get_access_token()
        claims = normalize_claims(access_token.claims or {}) if access_token else {}

        request_fields: dict[str, Any] = {}
        if CONFIG.transport != Transport.stdio:
            request_fields["claims"] = claims
            try:
                request = get_http_request()
                if request.client:
                    request_fields["client_ip"] = request.client.host
            except RuntimeError:
                pass

        start = time.perf_counter()
        started = False
        outcome = {"status": "success"}

        with audit_context(
            call_id=str(uuid.uuid4()),
            tool=context.message.name,
            **request_fields,
        ) as fields:
            try:
                assert context.fastmcp_context
                tool = await context.fastmcp_context.fastmcp.get_tool(context.message.name)
                if tool is None or not ComponentFilter.get(context.fastmcp_context).includes(tool):
                    raise NotFoundError(f"Tool not found: '{context.message.name}'")

                target_host = resolve_target_host(tool, tool_args)
                fields["host"] = target_host
                parameters = {key: value for key, value in tool_args.items() if key != "ctx"}

                log_event(Event.TOOL_CALL, "Tool called", parameters=parameters)
                started = True

                return await self._authorize_and_call_tool(context, call_next, tool, target_host, claims)
            except BaseException as exc:
                failure = _redacted_error(exc)
                outcome = {
                    "status": "cancelled" if isinstance(exc, asyncio.CancelledError) else "error",
                    "error": str(failure),
                }
                raise failure
            finally:
                if not started:
                    log_event(Event.TOOL_CALL, "Tool called", parameters=parameters)

                log_event(
                    Event.TOOL_COMPLETE,
                    "Tool completed",
                    level=logging.ERROR if outcome["status"] == "error" else logging.INFO,
                    **outcome,
                    duration_ms=(time.perf_counter() - start) * 1000,
                )

    async def _authorize_and_call_tool(
        self,
        context: MiddlewareContext,
        call_next: CallNext,
        tool: Tool,
        target_host: Host,
        claims: dict[str, Any],
    ) -> Any:
        # For stdio without policy configured, allow everything
        if CONFIG.transport == Transport.stdio and CONFIG.policy_path is None:
            exec_context = ExecutionContext(allow_local=True, allow_ssh_default=True)
            with use_execution_context(restrict(exec_context)):
                return await call_next(context)

        # Evaluate policy by tool, host and claims matching
        action, ssh_key_config = evaluate_policy(tool, target_host, claims)

        # Validate that action matches execution mode (should be prevented by policy validation)
        is_local_execution = target_host == LOCALHOST

        # Block local execution with SSH action (should be prevented by policy validation)
        if is_local_execution and action in [PolicyAction.SSH_KEY, PolicyAction.SSH_DEFAULT]:
            raise RuntimeError(
                f"Policy validation error: Cannot use SSH action ('{action.value}') for local execution."
            )

        # Block remote host with local action (should be prevented by policy validation)
        if not is_local_execution and action == PolicyAction.LOCAL:
            raise RuntimeError(f"Policy validation error: Cannot use local action for remote host '{target_host}'. ")

        if action == PolicyAction.DENY:
            raise ValueError(f"Authorization denied: tool '{tool.name}' on host '{target_host}'")

        # Log the authorized action
        logger.debug("Authorized tool call", extra={"tool": tool.name, "host": target_host, "action": action.value})

        # Build ExecutionContext based on policy action
        match action:
            case PolicyAction.LOCAL:
                exec_context = ExecutionContext(allow_local=True)
            case PolicyAction.SSH_DEFAULT:
                exec_context = ExecutionContext(allow_ssh_default=True)
            case PolicyAction.SSH_KEY:
                if not ssh_key_config:
                    raise RuntimeError("Policy validation error: SSH_KEY action requires ssh_key configuration.")
                logger.debug(f"SSH key override: path={ssh_key_config.path}, user={ssh_key_config.user}")
                exec_context = ExecutionContext(
                    ssh_key_path=Path(ssh_key_config.path),
                    ssh_key_user=ssh_key_config.user,
                )
            case _:  # pragma: no cover
                raise RuntimeError(f"Unexpected policy action: {action}")

        # Execute with the appropriate ExecutionContext
        with use_execution_context(restrict(exec_context)):
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
        return [adjust_tool(t) for t in tools if filter.includes(t)]

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
