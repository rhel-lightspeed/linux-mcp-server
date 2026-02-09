import logging
import secrets
import shlex
import typing as t

from dataclasses import asdict
from dataclasses import dataclass

from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import Tool
from fastmcp.tools.tool import ToolResult
from mcp.types import ContentBlock
from mcp.types import TextContent
from mcp.types import ToolAnnotations

# from pydantic import BaseModel
from pydantic import BaseModel
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.gatekeeper import check_run_script
from linux_mcp_server.gatekeeper import GatekeeperStatus
from linux_mcp_server.mcp_app import RUN_SCRIPT_APP_URI
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
    script: str
    script_type: ScriptType
    host: Host


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

    def add_script(self, script: str, script_type: ScriptType, host: Host) -> str:
        """
        Add a new script to the store and generate a unique ID for it.

        This method stores a script with its metadata and assigns it an initial state of
        "waiting-approval". The generated ID can be used to retrieve or update the script later.

        Args:
            script: The script content to execute (Python or Bash code).
            script_type: The type of script, either "python" or "bash".
            host: The target host where the script will be executed.

        Returns:
            A unique URL-safe token (16 bytes) identifying this script execution.
        """
        id = secrets.token_urlsafe(16)
        self._scripts[id] = ScriptDetails(state="waiting-approval", script=script, script_type=script_type, host=host)
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
    "--working-directory=/tmp",
    "--collect",
    "--wait",
    "--service-type=exec",
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


RUN_SCRIPT_READONLY_DESCRIPTION = (
    """
Run a script on a system in read-only mode.
"""
    + RUN_SCRIPT_COMMON_DESCRIPTION
)


RUN_SCRIPT_MODIFY_DESCRIPTION = (
    """
Run a script on a system to modify files or settings.
"""
    + RUN_SCRIPT_COMMON_DESCRIPTION
)

RUN_SCRIPT_MODIFY_INTERACTIVE = (
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


@mcp.tool(
    tags={"run_script"},
    title="Run script on system, read-only",
    description=RUN_SCRIPT_READONLY_DESCRIPTION,
    annotations=ToolAnnotations(readOnlyHint=True),
)
@log_tool_call
@disallow_local_execution_in_containers
async def run_script_readonly(
    ctx: Context,
    description: t.Annotated[
        str,
        Field(
            description="Description of what the script does - e.g. 'Collect SELinux messages from the system logs.'"
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
) -> str:
    command = _wrap_script(script_type, script)

    gatekeeper_result = check_run_script(
        description,
        script_type,
        (BASH_STRICT_PREAMBLE + script) if script_type == SCRIPT_TYPE_BASH else script,
        readonly=True,
    )

    match gatekeeper_result.status:
        case GatekeeperStatus.OK:
            pass
        case GatekeeperStatus.BAD_DESCRIPTION:
            raise ToolError(f"Bad description: {gatekeeper_result.detail}")
        case GatekeeperStatus.POLICY:
            raise ToolError(f"Policy violation: {gatekeeper_result.detail}")
        case GatekeeperStatus.MODIFIES_SYSTEM:
            raise RuntimeError("Model returned MODIFIES_SYSTEM error for run_script_modify")
        case GatekeeperStatus.UNCLEAR:
            raise ToolError(f"Unclear script: {gatekeeper_result.detail}")
        case GatekeeperStatus.DANGEROUS:
            raise ToolError(f"Dangerous script: {gatekeeper_result.detail}")
        case GatekeeperStatus.MALICIOUS:
            # We don't provide detail here to make it harder for a malicious model
            # to figure out workarounds
            raise ToolError("Possibly malicious script: not allowed")

    returncode, stdout, stderr = await execute_command(command, host=host)
    if returncode == 0:
        stdout = stdout if isinstance(stdout, str) else stdout.decode("utf-8", errors="replace")
        return stdout
    else:
        return f"Error executing script: return code {returncode}, stderr: {stderr}"


@dataclass
class ExecuteScriptResult:
    state: t.Literal["success", "failure"]
    output: str


async def _execute_script(
    id: t.Annotated[str, Field(description="The associated ID of the script to be executed")],
) -> ToolResult:
    script_details = script_store.get_script_details(id)
    command = _wrap_script(script_details.script_type, script_details.script)
    script_store.set_script_state(id, "executing")
    content: list[ContentBlock] = []

    try:
        returncode, stdout, stderr = await execute_command(command, host=script_details.host)
    except Exception as e:
        raise ToolError(f"Execution failed: {e}")

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


execute_script = Tool.from_function(
    _execute_script,
    name="execute_script",
    tags={"run_script", "hidden_from_model"},
    description="Execute a script; this is only available to the our mcp-app",
    meta={"ui": {"visibility": ["app"]}},
)


async def _reject_script(
    id: t.Annotated[str, Field(description="The associated ID of the script to be rejected")],
):
    script_store.set_script_state(id, "rejected-user")


reject_script = Tool.from_function(
    _reject_script,
    name="reject_script",
    tags={"run_script", "hidden_from_model"},
    description="Reject a script; this is only available to the our mcp-app",
    meta={"ui": {"visibility": ["app"]}},
)


@log_tool_call
@disallow_local_execution_in_containers
async def _run_script_modify_interactive(
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
) -> ToolResult:
    gatekeeper_result = check_run_script(description, script_type, script, readonly=False)
    content: list[ContentBlock] = []

    if gatekeeper_result.status == GatekeeperStatus.OK:
        content.append(
            TextContent(
                type="text",
                text="The user has been asked for approval; please respond nothing to the user yet; the final result will be provided as a separate message later.",
            )
        )

    # Initialize execution detail to keep execution status persistent
    # Store script and script_type so set_script_approval can retrieve them by id
    id = script_store.add_script(script, script_type, host)

    if gatekeeper_result.status != GatekeeperStatus.OK:
        script_store.set_script_state(id, "rejected-gatekeeper")

    structured_content_obj = RunScriptInteractiveResult(
        id=id, status=gatekeeper_result.status, detail=gatekeeper_result.detail
    )

    result = ToolResult(content=content, structured_content=structured_content_obj.model_dump())

    return result


run_script_modify_interactive = Tool.from_function(
    _run_script_modify_interactive,
    name="run_script_modify_interactive",
    tags={"run_script"},
    title="Propose to run a script that modifies system",
    description=RUN_SCRIPT_MODIFY_INTERACTIVE,
    annotations=ToolAnnotations(destructiveHint=True),
    output_schema=RunScriptInteractiveResult.model_json_schema(),
    meta={"ui": {"resourceUri": RUN_SCRIPT_APP_URI}},
)


@log_tool_call
@disallow_local_execution_in_containers
async def _run_script_modify(
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
) -> str:
    command = _wrap_script(script_type, script)

    gatekeeper_result = check_run_script(
        description,
        script_type,
        (BASH_STRICT_PREAMBLE + script) if script_type == SCRIPT_TYPE_BASH else script,
        readonly=False,
    )

    match gatekeeper_result.status:
        case GatekeeperStatus.OK:
            pass
        case GatekeeperStatus.BAD_DESCRIPTION:
            raise ToolError(f"Bad description: {gatekeeper_result.detail}")
        case GatekeeperStatus.POLICY:
            raise ToolError(f"Policy violation: {gatekeeper_result.detail}")
        case GatekeeperStatus.MODIFIES_SYSTEM:
            raise ToolError(f"Script modifies the system - use run_script_modify: {gatekeeper_result.detail}")
        case GatekeeperStatus.UNCLEAR:
            raise ToolError(f"Unclear script: {gatekeeper_result.detail}")
        case GatekeeperStatus.DANGEROUS:
            raise ToolError(f"Dangerous script: {gatekeeper_result.detail}")
        case GatekeeperStatus.MALICIOUS:
            # We don't provide detail here to make it harder for a malicious model
            # to figure out workarounds
            raise ToolError("Malicious script: not allowed")

    returncode, stdout, stderr = await execute_command(command, host=host)
    if returncode == 0:
        stdout = stdout if isinstance(stdout, str) else stdout.decode("utf-8", errors="replace")
        return stdout
    else:
        return f"Error executing script: return code {returncode}, stderr: {stderr}"


run_script_modify = Tool.from_function(
    _run_script_modify,
    name="run_script_modify",
    tags={"run_script"},
    title="Run script to modify system",
    description=RUN_SCRIPT_MODIFY_DESCRIPTION,
    annotations=ToolAnnotations(destructiveHint=True),
)


def _get_execution_state(id: str):
    script_detail = script_store.get_script_details(id)
    return {"state": script_detail.state}


get_execution_state = Tool.from_function(
    _get_execution_state,
    name="get_execution_state",
    tags={"run_script", "hidden_from_model"},
    title="Get the execution state with request ID",
    description="Get the execution state with request ID",
    meta={"ui": {"visibility": ["app"]}},
)
