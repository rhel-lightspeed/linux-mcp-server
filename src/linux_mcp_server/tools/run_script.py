import logging
import typing as t

from fastmcp import Context
from fastmcp.exceptions import ToolError
from fastmcp.tools.tool import Tool
from fastmcp.tools.tool import ToolResult
from mcp.types import ContentBlock
from mcp.types import TextContent
from mcp.types import ToolAnnotations

# from pydantic import BaseModel
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.gatekeeper import check_run_script
from linux_mcp_server.gatekeeper import GatekeeperStatus
from linux_mcp_server.mcp_app import RUN_SCRIPT_APP_URI
from linux_mcp_server.server import mcp
from linux_mcp_server.utils import StrEnum
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


logger = logging.getLogger("linux-mcp-server")


class ScriptType(StrEnum):
    PYTHON = "python"
    BASH = "bash"


RUN_SCRIPT_COMMON_DESCRIPTION = """\
A bash script should be used for simple operations that can be expressed cleanly
as a few shell commands, but a Python script should be used if complex processing
is needed. `set -euo pipefail` will be prepended to bash scripts, so make sure to
handle expected non-zero exit codes properly.

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


# class UserInfo(BaseModel):
#    name: str
#    age: int
#


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
    command = []

    if script_type == ScriptType.BASH:
        script = "# added by linux-mcp-server\nset -euo pipefail\n\n" + script

    if script_type == ScriptType.PYTHON:
        command = ["python3", "-c", script]
    elif script_type == ScriptType.BASH:
        command = ["bash", "-c", script]

    gatekeeper_result = check_run_script(description, script_type, script, readonly=True)

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


async def _execute_script(
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
    command = []

    if script_type == ScriptType.BASH:
        script = "# added by linux-mcp-server\nset -euo pipefail\n\n" + script

    if script_type == ScriptType.PYTHON:
        command = ["python3", "-c", script]
    elif script_type == ScriptType.BASH:
        command = ["bash", "-c", script]

    returncode, stdout, stderr = await execute_command(command, host=host)
    if returncode == 0:
        stdout = stdout if isinstance(stdout, str) else stdout.decode("utf-8", errors="replace")
        return stdout
    else:
        return f"Error executing script: return code {returncode}, stderr: {stderr}"


execute_script = Tool.from_function(
    _execute_script,
    name="execute_script",
    tags={"run_script", "hidden_from_model"},
    description="Execute a script; this is only available to the our mcp-app",
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

    result = ToolResult(content=content, structured_content=gatekeeper_result.model_dump())

    return result


run_script_modify_interactive = Tool.from_function(
    _run_script_modify_interactive,
    name="run_script_modify_interactive",
    tags={"run_script"},
    title="Propose to run a script that modifies system",
    description=RUN_SCRIPT_MODIFY_INTERACTIVE,
    annotations=ToolAnnotations(destructiveHint=True),
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
    command = []

    if script_type == ScriptType.BASH:
        script = "# added by linux-mcp-server\nset -euo pipefail\n\n" + script

    if script_type == ScriptType.PYTHON:
        command = ["python3", "-c", script]
    elif script_type == ScriptType.BASH:
        command = ["bash", "-c", script]

    gatekeeper_result = check_run_script(description, script_type, script, readonly=False)

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
