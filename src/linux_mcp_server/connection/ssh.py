"""SSH executor for remote command execution.

This module provides functionality to execute commands on remote systems via SSH,
with connection pooling and SSH key discovery. It seamlessly routes commands to
either local or remote execution based on the provided parameters.

The module acts as a facade, delegating to the appropriate SSH backend based on
platform and configuration:
- subprocess backend (default on Unix): Uses native ssh command for full
  ~/.ssh/config support including ProxyJump, Kerberos, smartcards, ControlMaster
- asyncssh backend (default on Windows): Uses asyncssh library
"""

import asyncio
import logging
import os
import shutil
import subprocess
import time

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from linux_mcp_server.audit import Event
from linux_mcp_server.config import CONFIG
from linux_mcp_server.connection.asyncssh_backend import discover_ssh_key
from linux_mcp_server.connection.asyncssh_backend import get_remote_bin_path
from linux_mcp_server.connection.asyncssh_backend import SSHConnectionManager


if TYPE_CHECKING:
    from linux_mcp_server.connection.base import SSHManagerProtocol  # pragma: no cover


logger = logging.getLogger("linux-mcp-server")

_connection_manager: "SSHManagerProtocol | None" = None


def _get_manager() -> "SSHManagerProtocol":
    """Get the appropriate SSH connection manager based on configuration."""
    global _connection_manager

    if _connection_manager is not None:
        return _connection_manager

    backend = CONFIG.effective_ssh_backend

    if backend == "subprocess":
        from linux_mcp_server.connection.subprocess_ssh import SSHSubprocessManager

        _connection_manager = SSHSubprocessManager()
    else:
        from linux_mcp_server.connection.asyncssh_backend import SSHAsyncSSHManager

        _connection_manager = SSHAsyncSSHManager()

    logger.debug(f"SSH backend initialized: {backend}")
    return _connection_manager


def get_bin_path(command: str) -> str:
    """Get the full path to an executable.

    Raises FileNotFoundError if not found.
    """
    sbin_paths = ["/sbin", "/usr/sbin", "/usr/local/sbin"]
    path_dirs = os.get_exec_path()
    path_dirs.extend(p for p in sbin_paths if p not in path_dirs)
    bin_path = shutil.which(command, path=os.pathsep.join(path_dirs))
    if bin_path is None:
        raise FileNotFoundError(f"Unable to find '{command}'")

    return bin_path


async def execute_command(
    command: Sequence[str],
    host: str | None = None,
    encoding: str | None = "utf-8",
    timeout: int = CONFIG.command_timeout,
    **kwargs,
) -> tuple[int, str | bytes, str | bytes]:
    """Execute a command locally or remotely.

    This is the main entry point for command execution. It routes the command
    to either local subprocess execution or remote SSH execution based on
    whether host/username parameters are provided.

    Args:
        command: Command and arguments to execute. If the command is not an absolute path
                 it will be resolved to the full path before execution.
        host: Optional remote host address
        encoding: Character encoding for stdout/stderr. Defaults to "utf-8".
            Set to None to receive raw bytes for commands that may output
            binary content.
        **kwargs: Additional arguments (reserved for future use)

    Returns:
        Tuple of (return_code, stdout, stderr) where stdout and stderr are strings
        if encoding is not None, otherwise bytes.

    Raises:
        ValueError: If host is provided without username
        ConnectionError: If remote connection fails
        ToolError: If the command is missing
    """
    cmd_str = " ".join(command)

    if host:
        logger.debug(f"Routing to remote execution: {host} | command={cmd_str}")
        manager = _get_manager()
        return await manager.execute_remote(command, host, timeout=timeout, encoding=encoding)

    logger.debug(f"LOCAL_EXEC: {cmd_str}")
    return await _execute_local(command, encoding=encoding, timeout=timeout)


async def execute_with_fallback(
    args: Sequence[str],
    fallback: Sequence[str] | None = None,
    host: str | None = None,
    encoding: str | None = "utf-8",
    **kwargs,
) -> tuple[int, str | bytes, str | bytes]:
    """Execute a command with optional fallback if primary command fails.

    This function attempts to execute the primary command. If it fails
    (non-zero return code) and a fallback command is provided, it will
    attempt the fallback command.

    Args:
        args: Primary command and arguments to execute
        fallback: Optional fallback command if primary fails
        host: Optional remote host address
        username: Optional SSH username (required if host is provided)
        encoding: Character encoding for stdout/stderr. Defaults to "utf-8".
            Set to None to receive raw bytes for commands that may output
            binary content.
        **kwargs: Additional arguments passed to execute_command

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    returncode, stdout, stderr = await execute_command(args, host=host, encoding=encoding, **kwargs)

    if returncode != 0 and fallback:
        logger.debug(f"Primary command failed (exit={returncode}), trying fallback: {' '.join(fallback)}")
        returncode, stdout, stderr = await execute_command(fallback, host=host, encoding=encoding, **kwargs)

    return returncode, stdout, stderr


async def _execute_local(
    command: Sequence[str],
    encoding: str | None = "utf-8",
    timeout: int | None = None,
) -> tuple[int, str | bytes, str | bytes]:
    """Execute a command locally using subprocess."""
    cmd_str = " ".join(command)
    start_time = time.time()
    binary = command[0]
    if not Path(binary).is_absolute():
        binary = get_bin_path(binary)

    full_command = [binary, *command[1:]]

    try:
        proc = await asyncio.create_subprocess_exec(*full_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(timeout) if timeout else None,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            duration = time.time() - start_time
            logger.error(f"Local command timed out after {timeout}s: {cmd_str}")
            timeout_msg = f"Command timed out after {timeout}s"
            if encoding is None:
                return 1, b"", timeout_msg.encode("utf-8")
            return 1, "", timeout_msg

        return_code = proc.returncode if proc.returncode is not None else 0
        stdout = stdout_bytes if encoding is None else stdout_bytes.decode(encoding, errors="replace")
        stderr = stderr_bytes if encoding is None else stderr_bytes.decode(encoding, errors="replace")

        duration = time.time() - start_time
        logger.debug(f"LOCAL_EXEC completed: {cmd_str} | exit_code={return_code} | duration={duration:.3f}s")

        return return_code, stdout, stderr

    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Error executing local command: {cmd_str}",
            extra={
                "event": Event.LOCAL_EXEC_ERROR,
                "command": cmd_str,
                "duration": f"{duration:.3f}s",
                "error": str(e),
            },
        )
        return 1, "", str(e)


__all__ = [
    "execute_command",
    "execute_with_fallback",
    "get_bin_path",
    "SSHConnectionManager",
    "discover_ssh_key",
    "get_remote_bin_path",
]
