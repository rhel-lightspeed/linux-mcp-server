import importlib.metadata

from linux_mcp_server.config import CONFIG as CONFIG


__version__ = importlib.metadata.version(__spec__.parent)
