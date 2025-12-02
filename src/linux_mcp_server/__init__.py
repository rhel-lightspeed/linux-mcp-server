import importlib.metadata

import linux_mcp_server._vendor  # noqa: F401

from linux_mcp_server.config import CONFIG as CONFIG


__version__ = importlib.metadata.version(__spec__.parent)
