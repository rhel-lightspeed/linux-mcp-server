"""Core MCP server for Linux diagnostics using FastMCP."""

import logging
import sys

from fastmcp import FastMCP

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import Toolset


logger = logging.getLogger("linux-mcp-server")


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
    instructions="""
        This server provides comprehensive Linux system diagnostics and monitoring
        capabilities across six main areas:
            - system information
            - services
            - network
            - processes
            - storage and files
            - logs

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
    """,
    **kwargs,
)

from linux_mcp_server.tools import *  # noqa: E402, F403


def main():
    mcp.run(show_banner=False)
