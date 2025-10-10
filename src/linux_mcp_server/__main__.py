"""Main entry point for the Linux MCP Server."""

import asyncio
import sys
from .server import main


def cli():
    """Console script entry point for the Linux MCP Server."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    cli()

