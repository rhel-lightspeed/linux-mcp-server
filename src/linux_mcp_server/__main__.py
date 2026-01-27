"""Main entry point for the Linux MCP Server."""

import argparse
import logging
import sys

from linux_mcp_server import __version__
from linux_mcp_server.logging_config import setup_logging
from linux_mcp_server.server import main


def cli():
    """Console script entry point for the Linux MCP Server."""
    parser = argparse.ArgumentParser(
        description="Linux MCP Server - Comprehensive Linux system diagnostics and monitoring",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "sse", "http", "streamable-http"],
        default="stdio",
        help="Transport protocol to use for MCP communication",
    )

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind to (only for http/sse transports)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (only for http/sse transports)",
    )

    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Endpoint path for the transport (only for http/sse transports)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["debug", "info", "warning", "error", "critical"],
        default=None,
        help="Log level for the server (only for http/sse transports)",
    )

    parser.add_argument(
        "--show-banner",
        action="store_true",
        default=False,
        help="Show the FastMCP server banner on startup",
    )

    args = parser.parse_args()

    setup_logging()

    logger = logging.getLogger("linux-mcp-server")
    logger.info(f"Running Linux MCP Server {__version__}. Press Ctrl+C, Enter to stop the server.")

    # Prepare transport kwargs based on transport type
    transport_kwargs = {}
    if args.transport in {"http", "sse", "streamable-http"}:
        transport_kwargs["host"] = args.host
        transport_kwargs["port"] = args.port
        if args.path:
            transport_kwargs["path"] = args.path
        if args.log_level:
            transport_kwargs["log_level"] = args.log_level

    try:
        # FastMCP.run() creates its own event loop, don't use asyncio.run()
        main(
            transport=args.transport,
            show_banner=args.show_banner,
            **transport_kwargs,
        )
    except KeyboardInterrupt:
        logger.info("Linux MCP Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error in Linux MCP Server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
