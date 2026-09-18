"""Decorators for tool functions."""

import functools
import inspect
import os

from fastmcp.exceptions import ToolError

from linux_mcp_server.utils.types import LOCALHOST


CONTAINER_ENV_VARS = [
    "openvz",
    "lxc",
    "lxc-libvirt",
    "systemd-nspawn",
    "docker",
    "podman",
    "rkt",
    "wsl",
    "proot",
    "pouch",
]


def disallow_local_execution_in_containers(func):
    """
    Decorator that raises a ToolError if local execution is attempted in a container.

    This decorator checks if:
    1. The 'host' parameter is LOCALHOST (indicating local execution)
    2. The process is running in a container (via the 'container' environment variable)

    If both conditions are true, it raises a ToolError.

    Args:
        func: The function to decorate (must have a 'host' parameter)

    Returns:
        The wrapped function

    Raises:
        ToolError: If local execution is attempted in a container
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Get the function signature to find the 'host' parameter
        sig = inspect.signature(func)
        bound_args = sig.bind_partial(*args, **kwargs)
        bound_args.apply_defaults()

        # Check if 'host' parameter exists and is LOCALHOST
        host_value = bound_args.arguments.get("host")

        # Check if running in a container and the target is the local system
        if host_value == LOCALHOST and os.environ.get("container") in CONTAINER_ENV_VARS:
            raise ToolError(
                "Local execution is not allowed when running in a container. "
                "Please pass a remote host in the 'host' parameter to execute via SSH."
            )

        # Call the original function
        return await func(*args, **kwargs)

    return wrapper
