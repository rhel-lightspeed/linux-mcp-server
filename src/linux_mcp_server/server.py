"""Core MCP server for Linux diagnostics using FastMCP."""

import logging
import sys

from fastmcp import FastMCP

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import Toolset


logger = logging.getLogger("linux-mcp-server")

INSTRUCTIONS = """
{fixed_instructions}

{run_script_instructions}

All tools support optional 'host' parameter for SSH-based remote diagnostics.
When provided, commands execute on the remote system instead of locally.

If running inside a container, which is indicated by the the environment variable
"container", local execution is not allowed.

IMPORTANT NOTES:
    - Most tools are read-only operations (indicated by readOnlyHint)
    - Log file access requires explicit allowlist configuration via LINUX_MCP_ALLOWED_LOG_PATHS
    - Service names automatically append '.service' suffix if not provided
    - File paths must be absolute
    - Some hardware info may require elevated privileges
"""

FIXED_INSTRUCTIONS = """
This server provides comprehensive Linux system diagnostics and monitoring
capabilities across six main categories:
    - system information
    - services
    - network
    - processes
    - storage and files
    - logs

"""

RUN_SCRIPT_INSTRUCTIONS = """
This server provides the ability to run Python and Bash scripts for advanced
diagnostic and remediation tasks. When using this capability, please adhere to the
following guidelines:
    - Use read-only scripts whenever possible.
    - If a script modifies the system, ensure it is safe and necessary for the task.
    - Avoid any operations that could compromise system stability or security.
    - Clearly document the purpose and actions of any modifying scripts.
    - Do not download files from the internet; only use pre-configured repositories for installations.
"""

kwargs = {}

match CONFIG.toolset:
    case Toolset.FIXED:
        kwargs["exclude_tags"] = {"run_script"}
    case Toolset.RUN_SCRIPT:
        kwargs["include_tags"] = {"run_script"}
    case Toolset.BOTH:
        pass  # No kwargs
    case _:
        assert False, f"Unknown toolset configuration: {CONFIG.toolset}"


if CONFIG.toolset != Toolset.FIXED and CONFIG.gatekeeper_model is None:
    logger.error("LINUX_MCP_GATEKEEPER_MODEL not set, this is needed for run_script tools")
    sys.exit(1)

# Initialize FastMCP server
mcp = FastMCP(
    "linux-diagnostics",
    instructions=INSTRUCTIONS.format(
        fixed_instructions=FIXED_INSTRUCTIONS
        if CONFIG.toolset == Toolset.FIXED or CONFIG.toolset == Toolset.BOTH
        else "",
        run_script_instructions=RUN_SCRIPT_INSTRUCTIONS
        if CONFIG.toolset == Toolset.RUN_SCRIPT or CONFIG.toolset == Toolset.BOTH
        else "",
    ),
    **kwargs,
)

from linux_mcp_server.tools import *  # noqa: E402, F403


def main():
    mcp.run(show_banner=False)
