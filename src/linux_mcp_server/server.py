"""Core MCP server for Linux diagnostics using FastMCP."""

import logging

from mcp.server.fastmcp import FastMCP


logger = logging.getLogger("linux-mcp-server")


# Initialize FastMCP server
mcp = FastMCP("linux-diagnostics")

from .tools import *


def main():
    """Run the MCP server using FastMCP."""
    logger.info("Initialized linux-diagnostics v0.1.0")
    logger.info("Starting FastMCP server")

    # Run the FastMCP server (it creates its own event loop)
    mcp.run()
