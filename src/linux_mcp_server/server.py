"""Core MCP server for Linux diagnostics using FastMCP."""

import logging

from typing import Any

from fastmcp import FastMCP

from linux_mcp_server.utils.enum import TransportType


logger = logging.getLogger("linux-mcp-server")


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
)

from linux_mcp_server.tools import *  # noqa: E402, F403


def main(
    transport: TransportType = TransportType.STDIO,
    show_banner: bool = False,
    **transport_kwargs: Any,
) -> None:
    """Run the MCP server with the specified transport.

    Args:
        transport: Transport protocol to use ("stdio", "sse", "http", or "streamable-http")
        show_banner: Whether to show the FastMCP server banner
        **transport_kwargs: Additional transport-specific arguments (host, port, path, log_level, etc.)
    """
    mcp.run(transport=transport, show_banner=show_banner, **transport_kwargs)
