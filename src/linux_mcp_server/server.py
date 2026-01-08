"""Core MCP server for Linux diagnostics using FastMCP."""

import logging

from fastmcp import FastMCP


logger = logging.getLogger("linux-mcp-server")


# Initialize FastMCP server
mcp = FastMCP("linux-diagnostics")

from linux_mcp_server.tools import *  # noqa: E402, F403


def main():
    mcp.run(show_banner=False)
