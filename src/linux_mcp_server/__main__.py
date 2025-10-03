"""Main entry point for the Linux MCP Server."""

import asyncio
import sys
from .server import main


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)

