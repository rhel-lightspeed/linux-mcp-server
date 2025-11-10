"""Main entry point for the Linux MCP Server."""

import logging
import sys

from linux_mcp_server.logging_config import setup_logging
from linux_mcp_server.server import main


def cli():
    """Console script entry point for the Linux MCP Server."""
    # Initialize logging first, before any other operations
    setup_logging()

    logger = logging.getLogger("linux-mcp-server")
    logger.info("Starting Linux MCP Server")

    try:
        # FastMCP.run() creates its own event loop, don't use asyncio.run()
        main()
    except KeyboardInterrupt:
        logger.info("Linux MCP Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error in Linux MCP Server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
