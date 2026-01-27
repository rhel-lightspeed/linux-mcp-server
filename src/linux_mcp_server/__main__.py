"""Main entry point for the Linux MCP Server."""

import logging
import sys

from typing import Literal
from typing import Optional

import typer

from linux_mcp_server import __version__
from linux_mcp_server.logging_config import setup_logging
from linux_mcp_server.server import main


app = typer.Typer(
    help="Linux MCP Server - Comprehensive Linux system diagnostics and monitoring",
    add_completion=False,
)


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        typer.echo(f"linux-mcp-server {__version__}")
        raise typer.Exit()


@app.command()
def cli(
    transport: Literal["stdio", "sse", "http", "streamable-http"] = typer.Option(
        "stdio",
        help="Transport protocol to use for MCP communication",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        help="Host address to bind to (only for http/sse transports)",
    ),
    port: int = typer.Option(
        8000,
        help="Port to bind to (only for http/sse transports)",
    ),
    path: Optional[str] = typer.Option(
        None,
        help="Endpoint path for the transport (only for http/sse transports)",
    ),
    log_level: Optional[Literal["debug", "info", "warning", "error", "critical"]] = typer.Option(
        None,
        "--log-level",
        help="Log level for the server (only for http/sse transports)",
    ),
    show_banner: bool = typer.Option(
        False,
        "--show-banner",
        help="Show the FastMCP server banner on startup",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """Console script entry point for the Linux MCP Server."""
    setup_logging()

    logger = logging.getLogger("linux-mcp-server")
    logger.info(f"Running Linux MCP Server {__version__}. Press Ctrl+C, Enter to stop the server.")

    # Prepare transport kwargs based on transport type
    transport_kwargs = {}
    if transport in {"http", "sse", "streamable-http"}:
        transport_kwargs["host"] = host
        transport_kwargs["port"] = port
        if path:
            transport_kwargs["path"] = path
        if log_level:
            transport_kwargs["log_level"] = log_level

    try:
        # FastMCP.run() creates its own event loop, don't use asyncio.run()
        main(
            transport=transport,
            show_banner=show_banner,
            **transport_kwargs,
        )
    except KeyboardInterrupt:
        logger.info("Linux MCP Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Fatal error in Linux MCP Server: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    app()
