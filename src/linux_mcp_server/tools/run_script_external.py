"""Simplified run_script tool for use with external script checks (e.g. Claude Code hooks).

When external_script_checks is enabled, the gatekeeper model and token-based
approval workflow are bypassed. A single run_script tool is exposed that takes
full script parameters and executes directly. Safety evaluation and user
confirmation are handled externally by the calling client.
"""

import typing as t

from fastmcp import Context
from pydantic import Field

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.server import mcp
from linux_mcp_server.tools.run_script_common import RUN_SCRIPT_COMMON_DESCRIPTION
from linux_mcp_server.tools.run_script_common import ScriptType
from linux_mcp_server.tools.run_script_common import _wrap_script
from linux_mcp_server.utils.decorators import disallow_local_execution_in_containers
from linux_mcp_server.utils.types import Host


RUN_SCRIPT_EXTERNAL_DESCRIPTION = (
    """\
Run a script on the target system.

Set readonly to true if the script only reads the system state.
Set readonly to false if the script modifies files or settings.
Prefer readonly scripts when possible.
For modifications, choose the minimal change and avoid anything that could harm stability or security.
Describe what each script does in the description.
Do not fetch content from the internet; use only configured repositories if installing software.
"""
    + RUN_SCRIPT_COMMON_DESCRIPTION
)


@mcp.tool(
    tags={"run_script"},
    title="Run a script",
    description=RUN_SCRIPT_EXTERNAL_DESCRIPTION,
)
@log_tool_call
@disallow_local_execution_in_containers
async def run_script(
    ctx: Context,
    description: t.Annotated[
        str,
        Field(
            description="Description of what the script does - e.g. 'Check nginx configuration for syntax errors.'"
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
    host: Host = None,
) -> str:
    command = _wrap_script(script_type, script)
    returncode, stdout, stderr = await execute_command(command, host=host)

    if returncode == 0:
        return stdout if isinstance(stdout, str) else stdout.decode("utf-8", errors="replace")
    else:
        return f"Error executing script: return code {returncode}, stderr: {stderr}"
