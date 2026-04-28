import logging
import secrets
import shlex
import typing as t

from dataclasses import asdict
from dataclasses import dataclass

from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import ToolResult
from mcp.types import ContentBlock
from mcp.types import TextContent
from mcp.types import ToolAnnotations

# from pydantic import BaseModel
from pydantic import BaseModel
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.config import CONFIG
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.gatekeeper import check_run_script
from linux_mcp_server.gatekeeper import GatekeeperStatus
from linux_mcp_server.mcp_app import RUN_SCRIPT_APP_URI
from linux_mcp_server.mcp_app import use_mcp_app_for_client
from linux_mcp_server.server import mcp
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


logger = logging.getLogger("linux-mcp-server")

ExecutionState = t.Literal[
    "waiting-approval", "success", "failure", "executing", "rejected-user", "rejected-gatekeeper"
]

# This would make more sense as a StrEnum, but that generates a schema with
# the enum in $defs, which deeply confuses (at least) the combination of
# Claude Sonnet 4.5 and Claude Desktop - the model knows that it's supposed
# to use "python" or "bash" and passes it in the call, but the UI sees `null`
# instead.
#
# Future versions of FastMCP may automatically dereference references
# (https://github.com/jlowin/fastmcp/pulls/2814) but that doesn't currently
# happen as of v2.14.5 (https://github.com/jlowin/fastmcp/issues/3153).
#
ScriptType = t.Literal["python", "bash"]
SCRIPT_TYPE_PYTHON = "python"
SCRIPT_TYPE_BASH = "bash"


@dataclass()
class ScriptDetails:
    state: ExecutionState
    description: str
    script: str
    script_type: ScriptType
    host: Host
    readonly: bool

    @property
    def needs_confirmation(self) -> bool:
        return not self.readonly or CONFIG.always_confirm_scripts


# TODO: Might need a cleanup mechanism to limit the maximum number of scripts we can store
class ScriptStore:
    """
    Stores script execution state across the async approval lifecycle.

    When a script execution is requested, approval happens asynchronously via MCP app UI.
    This store maps request IDs to their execution details (script, host, state) so we can
    retrieve and execute the script after user approval, even though the original request
    context is no longer available. It also preserve execution state (waiting-approval, executing,
    success, failure, rejected) for the MCP app UI.
    """

    def __init__(self):
        self._scripts: dict[str, ScriptDetails] = {}

    def add_script(
        self,
        description: str,
        script: str,
        script_type: ScriptType,
        host: Host,
        readonly: bool,
    ) -> str:
        """
        Add a new script to the store and generate a unique ID for it.

        This method stores a script with its metadata and assigns it an initial state of
        "waiting-approval". The generated ID can be used to retrieve or update the script later.

        Args:
            description: Human-readable description of what the script does.
            script: The script content to execute (Python or Bash code).
            script_type: The type of script, either "python" or "bash".
            host: The target host where the script will be executed.
            readonly: Whether the script only reads and does not modify the system.

        Returns:
            A unique URL-safe token (16 bytes) identifying this script execution.
        """
        id = secrets.token_urlsafe(16)
        self._scripts[id] = ScriptDetails(
            state="waiting-approval",
            description=description,
            script=script,
            script_type=script_type,
            host=host,
            readonly=readonly,
        )
        return id

    def get_script_details(self, id: str) -> ScriptDetails:
        """
        Retrieve the full details of a stored script by its ID.

        Args:
            id: The unique identifier for the script, as returned by add_script().

        Returns:
            A ScriptDetails object containing the script's state, content, type, and target host.

        Raises:
            KeyError: If no script exists with the given ID.
        """
        return self._scripts[id]

    def set_script_state(self, id: str, new_state: ExecutionState):
        """
        Update the execution state of a stored script.

        This method is used to track script lifecycle transitions, such as moving from
        "waiting-approval" to "executing" to "success" or "failure".

        Args:
            id: The unique identifier for the script.
            new_state: The new execution state. Valid states are:
                - "waiting-approval": Script is pending user approval
                - "executing": Script is currently running
                - "success": Script completed successfully
                - "failure": Script execution failed
                - "rejected-user": User rejected the script
                - "rejected-gatekeeper": Script was rejected by policy checks

        Raises:
            KeyError: If no script exists with the given ID.
        """
        self._scripts[id].state = new_state


script_store = ScriptStore()


BASH_STRICT_PREAMBLE = "set -euo pipefail; "

SYSTEMD_RUN_ARGS = [
    "--quiet",
    "--pipe",
    "--collect",
    "--wait",
    "--property=WorkingDirectory=/tmp",
    "--property=PrivateTmp=true",
    "--property=NoNewPrivileges=true",
]
SYSTEMD_RUN_READONLY_ARGS = [
    "--property=ReadOnlyPaths=/",
    "--property=RestrictAddressFamilies=AF_UNIX",
]
SYSTEMD_RUN_COMMAND = "/usr/bin/sudo /usr/bin/systemd-run {args}"

# Wrapper for run_script_readonly: use sudo+systemd-run when available, else run script
# directly. Template uses {script_type} and {script}; script is escaped via shlex.quote().
WRAPPER_TEMPLATE = """\
set -euo pipefail
SCRIPT={script}
if command -v sudo >/dev/null 2>&1 && command -v systemd-run >/dev/null 2>&1 && sudo -l whoami >/dev/null 2>&1; then
  exec {systemd_run_command} {script_type} -c "$SCRIPT"
else
  exec {script_type} -c "$SCRIPT"
fi
"""

RUN_SCRIPT_COMMON_DESCRIPTION = """\
A bash script should be used for simple operations that can be expressed cleanly
as a few shell commands, but a Python script should be used if complex processing
is needed. Bash scripts are run with strict mode (set -euo pipefail) applied by
the invocation, so handle expected non-zero exit codes in the script (e.g. with
`|| true`) where needed.

Write short, simple scripts that are easy to review - do not include unnecessary
complexity such as elaborate logging or handling unlikely corner cases.
"""


RUN_SCRIPT_INTERACTIVE_DESCRIPTION = (
    """
Run a script that modifies the system. The user will be asked for approval interactively.
"""
    + RUN_SCRIPT_COMMON_DESCRIPTION
)


class RunScriptInteractiveResult(BaseModel):
    id: str
    status: GatekeeperStatus
    detail: str


# class UserInfo(BaseModel):
#    name: str
#    age: int
#


def _wrap_script(script_type: ScriptType, script: str) -> list[str]:
    """Wrap a script in a wrapper script that uses sudo+systemd-run when available, else run script directly."""
    wrapper_script = WRAPPER_TEMPLATE.format(
        systemd_run_command=SYSTEMD_RUN_COMMAND.format(args=" ".join(SYSTEMD_RUN_ARGS)),
        script_type=script_type,
        script=shlex.quote((BASH_STRICT_PREAMBLE + script) if script_type == SCRIPT_TYPE_BASH else script),
    )
    return ["bash", "-c", wrapper_script]


@dataclass
class ExecuteScriptResult:
    state: t.Literal["success", "failure"]
    output: str


@mcp.tool(
    tags={"run_script", "hidden_from_model"},
    description="Execute a script; this is only available to the our mcp-app",
    meta={"ui": {"visibility": ["app"]}},
)
@log_tool_call
@disallow_local_execution_in_containers
async def execute_script(
    id: t.Annotated[str, Field(description="The associated ID of the script to be executed")],
) -> ToolResult:
    script_details = script_store.get_script_details(id)
    command = _wrap_script(script_details.script_type, script_details.script)
    script_store.set_script_state(id, "executing")
    content: list[ContentBlock] = []

    try:
        returncode, stdout, stderr = await execute_command(command, host=script_details.host)
    except Exception:
        script_store.set_script_state(id, "failure")
        raise

    if returncode == 0:
        script_store.set_script_state(id, "success")

        output = stdout if isinstance(stdout, str) else stdout.decode("utf-8", errors="replace")
        content.append(TextContent(type="text", text=output))
        result = ExecuteScriptResult("success", output)
    else:
        script_store.set_script_state(id, "failure")

        output = f"Error executing script: return code {returncode}, stderr: {stderr}"
        content.append(TextContent(type="text", text=output))
        result = ExecuteScriptResult("failure", output)

    return ToolResult(content=content, structured_content=asdict(result))


@mcp.tool(
    tags={"run_script", "hidden_from_model"},
    description="Reject a script; this is only available to the our mcp-app",
    meta={"ui": {"visibility": ["app"]}},
)
@log_tool_call
@disallow_local_execution_in_containers
async def reject_script(
    id: t.Annotated[str, Field(description="The associated ID of the script to be rejected")],
):
    script_store.set_script_state(id, "rejected-user")


@mcp.tool(
    tags={"run_script", "mcp_apps_only"},
    title="Run a script with interactive user confirmation",
    description=RUN_SCRIPT_INTERACTIVE_DESCRIPTION,
    annotations=ToolAnnotations(destructiveHint=True),
    output_schema=RunScriptInteractiveResult.model_json_schema(),
    meta={"ui": {"resourceUri": RUN_SCRIPT_APP_URI}},
)
@log_tool_call
@disallow_local_execution_in_containers
async def run_script_interactive(
    ctx: Context,
    description: t.Annotated[
        str,
        Field(
            description="Description of what the script does - e.g. 'Modify file permissions on nginx.conf to fix startup errors.'"
        ),
    ],
    script_type: t.Annotated[
        ScriptType,
        Field(description="The type of script to run (python or bash)."),
    ],
    script: t.Annotated[
        str,
        Field(description="The script to run."),
    ],
    readonly: t.Annotated[bool, Field(description="Should be true if the script does not modify the system.")],
    token: t.Annotated[str, Field(description="The token returned by the validate_script tool.")],
    host: Host = None,
) -> ToolResult:
    script_details = script_store.get_script_details(token)

    # Verify that this script requires confirmation
    if not script_details.needs_confirmation:
        raise ToolError("This script does not require confirmation. Use run_script instead of run_script_interactive.")

    # Check if the passed parameters match the stored script details
    new_details = ScriptDetails(
        state="waiting-approval",
        description=description,
        script_type=script_type,
        script=script,
        host=host,
        readonly=readonly,
    )

    result_id = token
    if new_details != script_details:
        # Parameters don't match - revalidate and create a new script store entry
        gatekeeper_result = check_run_script(
            description,
            script_type,
            (BASH_STRICT_PREAMBLE + script) if script_type == SCRIPT_TYPE_BASH else script,
            readonly=readonly,
        )
        if gatekeeper_result.status != GatekeeperStatus.OK:
            script_store.set_script_state(token, "rejected-gatekeeper")
            raise ToolError(gatekeeper_result.description)

        # Create new script store entry with the updated parameters
        result_id = script_store.add_script(description, script, script_type, host, readonly)

    content: list[ContentBlock] = [
        TextContent(
            type="text",
            text="The user has been asked for approval; please respond nothing to the user yet; the final result will be provided as a separate message later.",
        )
    ]

    structured_content_obj = RunScriptInteractiveResult(id=result_id, status=GatekeeperStatus.OK, detail="")

    return ToolResult(content=content, structured_content=structured_content_obj.model_dump())


@mcp.tool(
    tags={"run_script", "hidden_from_model"},
    title="Get the execution state with request ID",
    description="Get the execution state with request ID",
    meta={"ui": {"visibility": ["app"]}},
)
@log_tool_call
@disallow_local_execution_in_containers
async def get_execution_state(id: str):
    script_detail = script_store.get_script_details(id)
    return {"state": script_detail.state}


def _pick_execution_tool(readonly: bool, needs_confirmation: bool, use_mcp_app: bool):
    if not needs_confirmation and readonly:
        return "run_script"

    if use_mcp_app:
        return "run_script_interactive"
    else:
        return "run_script_with_confirmation"


@mcp.tool(
    tags={"run_script"},
    title="Validate a script",
    description="Request validation of a script from the gatekeeper. The tool will return a unique token that must be included in the run_script tool call.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def validate_script(
    ctx: Context,
    description: t.Annotated[
        str,
        Field(
            description="Description of what the script does - e.g. 'Modify file permissions on nginx.conf to fix startup errors.'"
        ),
    ],
    script_type: t.Annotated[
        ScriptType,
        Field(description="The type of script to run (python or bash)."),
    ],
    script: t.Annotated[
        str,
        Field(description="The script to run."),
    ],
    host: Host = None,
    readonly: t.Annotated[bool, Field(description="Should be true if the script does not modify the system.")] = True,
) -> ToolResult:
    gatekeeper_result = check_run_script(
        description,
        script_type,
        (BASH_STRICT_PREAMBLE + script) if script_type == SCRIPT_TYPE_BASH else script,
        readonly=readonly,
    )

    id = script_store.add_script(description, script, script_type, host, readonly)
    script_details = script_store.get_script_details(id)

    if gatekeeper_result.status != GatekeeperStatus.OK:
        script_store.set_script_state(id, "rejected-gatekeeper")
        raise ToolError(gatekeeper_result.description)

    client_params = ctx.session.client_params
    assert client_params is not None, "FastMCP framework error: client_params should not be None inside tool"

    execution_tool = _pick_execution_tool(
        readonly, script_details.needs_confirmation, use_mcp_app_for_client(client_params)
    )

    result = ToolResult(
        content=[
            TextContent(
                type="text",
                text=f"Script passed gatekeeper validation and is stored with ID {id}. Please use {execution_tool} to execute the validated script.",
            )
        ],
        structured_content={
            "token": id,
            "needs_confirmation": script_details.needs_confirmation,
        },
    )
    return result


@mcp.tool(
    tags={"run_script"},
    title="Run a script",
    description="Call this tool to run a previously validated script. Use this when validate_script returned needs_confirmation: false.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def run_script(
    ctx: Context,
    token: t.Annotated[str, Field(description="The token returned by the validate_script tool.")],
) -> str:
    script_details = script_store.get_script_details(token)

    client_params = ctx.session.client_params
    assert client_params is not None, "FastMCP framework error: client_params should not be None inside tool"

    if use_mcp_app_for_client(client_params):
        confirmation_tool_name = "run_script_interactive"
    else:
        confirmation_tool_name = "run_script_with_confirmation"

    # Verify that this script doesn't require confirmation
    if script_details.needs_confirmation:
        raise ToolError(f"This script requires confirmation. Use {confirmation_tool_name} instead of run_script.")

    script_store.set_script_state(token, "executing")
    try:
        command = _wrap_script(script_details.script_type, script_details.script)
        returncode, stdout, stderr = await execute_command(command, host=script_details.host)
    except Exception:
        script_store.set_script_state(token, "failure")
        raise

    if returncode == 0:
        script_store.set_script_state(token, "success")
        return stdout if isinstance(stdout, str) else stdout.decode("utf-8", errors="replace")
    else:
        script_store.set_script_state(token, "failure")
        return f"Error executing script: return code {returncode}, stderr: {stderr}"


@mcp.tool(
    tags={"run_script", "mcp_apps_exclude"},
    title="Run a script with confirmation",
    description="Call this tool to run a previously validated script that modifies the system. Use this when validate_script returned needs_confirmation: true. The parameters must match those passed to validate_script.",
    annotations=ToolAnnotations(destructiveHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def run_script_with_confirmation(
    ctx: Context,
    description: t.Annotated[
        str,
        Field(
            description="Description of what the script does - e.g. 'Modify file permissions on nginx.conf to fix startup errors.'"
        ),
    ],
    script_type: t.Annotated[
        ScriptType,
        Field(description="The type of script to run (python or bash)."),
    ],
    script: t.Annotated[
        str,
        Field(description="The script to run."),
    ],
    readonly: t.Annotated[bool, Field(description="Should be true if the script does not modify the system.")],
    token: t.Annotated[str, Field(description="The token returned by the validate_script tool.")],
    host: Host = None,
) -> str:
    script_details = script_store.get_script_details(token)

    # Verify that this script requires confirmation
    if not script_details.needs_confirmation:
        raise ToolError(
            "This script does not require confirmation. Use run_script instead of run_script_with_confirmation."
        )

    # Verify the retrieved script details match the incoming parameters
    new_details = ScriptDetails(
        state="waiting-approval",
        description=description,
        script_type=script_type,
        script=script,
        host=host,
        readonly=readonly,
    )

    details_changed = new_details != script_details
    execute_details = new_details if details_changed else script_details

    if details_changed:
        # Revalidate the script again; this is a convenience for the user to avoid
        # potentially having to double-approve the same script.
        gatekeeper_result = check_run_script(
            description,
            script_type,
            (BASH_STRICT_PREAMBLE + script) if script_type == SCRIPT_TYPE_BASH else script,
            readonly=readonly,
        )
        if gatekeeper_result.status != GatekeeperStatus.OK:
            script_store.set_script_state(token, "rejected-gatekeeper")
            raise ToolError(gatekeeper_result.description)
    else:
        script_store.set_script_state(token, "executing")

    try:
        command = _wrap_script(execute_details.script_type, execute_details.script)
        returncode, stdout, stderr = await execute_command(command, host=execute_details.host)
    except Exception:
        if not details_changed:
            script_store.set_script_state(token, "failure")
        raise

    if returncode == 0:
        if not details_changed:
            script_store.set_script_state(token, "success")
        return stdout if isinstance(stdout, str) else stdout.decode("utf-8", errors="replace")
    else:
        if not details_changed:
            script_store.set_script_state(token, "failure")
        return f"Error executing script: return code {returncode}, stderr: {stderr}"
