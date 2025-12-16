"""SSH executor for remote command execution.

This module provides functionality to execute commands on remote systems via SSH,
with connection pooling and SSH key discovery. It seamlessly routes commands to
either local or remote execution based on the provided parameters.
"""

import asyncio
import logging
import os
import shlex
import shutil
import subprocess
import time

from collections.abc import Sequence
from pathlib import Path
from typing import Optional

import asyncssh

from linux_mcp_server.audit import Event
from linux_mcp_server.audit import log_ssh_command
from linux_mcp_server.audit import log_ssh_connect
from linux_mcp_server.audit import Status
from linux_mcp_server.config import CONFIG
from linux_mcp_server.utils.types import Host


logger = logging.getLogger("linux-mcp-server")


def discover_ssh_key() -> str | None:
    """
    Discover SSH private key for authentication.

    Checks in order:
    1. LINUX_MCP_SSH_KEY_PATH environment variable
    2. Default locations: ~/.ssh/id_ed25519, ~/.ssh/id_rsa, ~/.ssh/id_ecdsa

    Returns:
        Path to SSH private key if found, None otherwise.
    """
    logger.debug("Discovering SSH key for authentication")

    env_key = CONFIG.ssh_key_path
    if env_key:
        logger.debug(f"Checking SSH key from environment: {env_key}")
        key_path = Path(env_key)
        if key_path.exists() and key_path.is_file():
            logger.info(f"Using SSH key from environment: {env_key}")
            return str(key_path)
        else:
            logger.warning(f"SSH key specified in LINUX_MCP_SSH_KEY_PATH not found: {env_key}")
            return None

    # Check default locations (prefer modern algorithms)
    if CONFIG.search_for_ssh_key:
        home = Path.home()
        default_keys = [
            home / ".ssh" / "id_ed25519",
            home / ".ssh" / "id_ecdsa",
            home / ".ssh" / "id_rsa",
        ]

        logger.debug(f"Checking default SSH key locations: {[str(k) for k in default_keys]}")

        for key_path in default_keys:
            if key_path.exists() and key_path.is_file():
                logger.info(f"Using SSH key: {key_path}")
                return str(key_path)

        logger.warning("No SSH private key found in default locations")

    logger.debug("Not providing an SSH key")


class SSHConnectionManager:
    """
    Manages SSH connections with connection pooling.

    This class implements a singleton pattern to maintain a pool of SSH connections
    across the lifetime of the application, improving performance by reusing
    connections to the same hosts.
    """

    _instance: Optional["SSHConnectionManager"] = None
    _connections: dict[str, asyncssh.SSHClientConnection]
    _ssh_key: str | None

    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connections = {}
            cls._instance._ssh_key = discover_ssh_key()
        return cls._instance

    async def get_connection(self, host: str) -> asyncssh.SSHClientConnection:
        """
        Get or create an SSH connection to a host.

        Args:
            host: Remote host address
            username: SSH username

        Returns:
            SSH connection object

        Raises:
            ConnectionError: If connection fails
        """
        key = f"{host}"

        # Return existing connection if available
        if key in self._connections:
            conn = self._connections[key]
            if not conn.is_closed():
                # DEBUG level: Log connection reuse and pool state
                logger.debug(f"SSH_REUSE: {key} | pool_size={len(self._connections)}")
                # Use audit log with connection reuse info
                log_ssh_connect(
                    host, username=conn._username, status=Status.success, reused=True, key_path=self._ssh_key
                )
                return conn
            else:
                # Connection was closed, remove it
                logger.debug(f"SSH_POOL: remove_closed_connection | connection={key}")
                del self._connections[key]

        # Create new connection
        # DEBUG level: Log connection attempt before it completes
        logger.debug(f"{Event.SSH_CONNECTING}: {key} | key={self._ssh_key or 'none'}")

        try:
            # Determine host key verification settings
            if CONFIG.verify_host_keys:
                known_hosts = str(CONFIG.effective_known_hosts_path)
            else:
                logger.warning("SSH host key verification disabled - vulnerable to MITM attacks")
                known_hosts = None

            connect_kwargs = {
                "host": host,
                "known_hosts": known_hosts,
                "passphrase": CONFIG.key_passphrase,
            }

            if self._ssh_key:
                connect_kwargs["client_keys"] = [self._ssh_key]

            if CONFIG.user:
                connect_kwargs["username"] = CONFIG.user

            conn = await asyncssh.connect(**connect_kwargs)
            self._connections[key] = conn

            # Log successful connection using audit function
            log_ssh_connect(host, username=conn._username, status=Status.success, reused=False, key_path=self._ssh_key)

            # DEBUG level: Log pool state
            logger.debug(f"SSH_POOL: add_connection | connections={len(self._connections)}")

            return conn

        except asyncssh.PermissionDenied as e:
            # Use audit log for authentication failure
            error_msg = str(e)
            log_ssh_connect(host, status=Status.failed, error=f"Permission denied: {error_msg}")
            raise ConnectionError(f"Authentication failed for {host}") from e
        except asyncssh.Error as e:
            # Use audit log for connection failure
            error_msg = str(e)
            log_ssh_connect(host, status=Status.failed, error=error_msg)
            raise ConnectionError(f"Failed to connect to {host}: {e}") from e

    async def execute_remote(
        self,
        command: Sequence[str],
        host: str,
        timeout: int = CONFIG.command_timeout,
    ) -> tuple[int, str, str]:
        """
        Execute a command on a remote host via SSH.

        Commands are subject to a timeout to prevent indefinite hangs. The timeout
        can be specified per-call or defaults to CONFIG.command_timeout (30s).

        Args:
            command: Command and arguments to execute (tuple or list)
            host: Remote host address
            timeout: Command timeout in seconds. Defaults to CONFIG.command_timeout.
                Use for commands that need longer execution time.

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            ConnectionError: If SSH connection fails or command times out
        """
        conn = await self.get_connection(host)
        bin = command[0]
        # Convert to list for modification - CommandSpec.args is an immutable tuple
        cmd_list = list(command)
        if not Path(bin).is_absolute():
            cmd_list[0] = await get_remote_bin_path(bin, host, conn)

        # Build command string with proper shell escaping
        # Use shlex.quote() to ensure special characters (like \n in printf format) are preserved
        cmd_str = shlex.join(cmd_list)

        # Start timing for command execution
        start_time = time.time()

        try:
            try:
                result = await conn.run(cmd_str, check=False, timeout=timeout)
            except asyncssh.TimeoutError:
                duration = time.time() - start_time
                logger.error(
                    f"Command timed out after {timeout}s",
                    extra={
                        "event": Event.REMOTE_EXEC_ERROR,
                        "command": cmd_str,
                        "host": host,
                        "duration": f"{duration:.3f}s",
                        "error": "timeout",
                    },
                )
                raise ConnectionError(
                    f"Command timed out after {timeout}s on {conn._username}@{host}: {cmd_str}"
                ) from None

            return_code = result.exit_status if result.exit_status is not None else 0

            # Ensure stdout and stderr are strings (asyncssh can return bytes or str)
            stdout_raw = result.stdout if result.stdout else ""
            stderr_raw = result.stderr if result.stderr else ""
            stdout = stdout_raw if isinstance(stdout_raw, str) else stdout_raw.decode("utf-8", errors="replace")
            stderr = stderr_raw if isinstance(stderr_raw, str) else stderr_raw.decode("utf-8", errors="replace")

            # Calculate duration
            duration = time.time() - start_time

            # Use audit log for command execution
            log_ssh_command(cmd_str, host, exit_code=return_code, duration=duration)

            return return_code, stdout, stderr

        except asyncssh.Error as e:
            duration = time.time() - start_time
            logger.error(
                f"Error executing command on {host}: {e}",
                extra={
                    "event": Event.REMOTE_EXEC_ERROR,
                    "command": cmd_str,
                    "host": host,
                    "duration": f"{duration:.3f}s",
                    "error": str(e),
                },
            )
            raise ConnectionError(f"Failed to execute command on {host}: {e}") from e

    async def close_all(self):
        """Close all SSH connections."""
        connection_count = len(self._connections)
        logger.info(f"Closing {connection_count} SSH connections")

        for key, conn in list(self._connections.items()):
            try:
                logger.debug(f"SSH_CLOSE: {key}")
                conn.close()
                await conn.wait_closed()
            except Exception as e:
                logger.warning(f"Error closing connection to {key}: {e}")

        self._connections.clear()
        logger.debug(f"SSH_POOL: cleared | closed_connections={connection_count}")


# Global connection manager instance
_connection_manager = SSHConnectionManager()


def get_bin_path(command: str) -> str:
    """Get the full path to an executable.

    Raises FileNotFoundError if not found.
    """
    sbin_paths = ("/sbin", "/usr/sbin", "/usr/local/sbin")
    path = os.getenv("PATH", "").split(os.pathsep)
    path.extend(new_path for new_path in sbin_paths if new_path not in path)
    path = os.pathsep.join(path)
    bin_path = shutil.which(command, path=path)
    if bin_path is None:
        raise FileNotFoundError(f"Unable to find '{command}'")

    return bin_path


async def get_remote_bin_path(
    command: str,
    hostname: Host,
    connection: asyncssh.SSHClientConnection,
    timeout: int = CONFIG.command_timeout,
) -> str:
    """Get the full path to an executable on a remote system.

    Raises FileNotFoundError if not found.
    """
    logger.debug(f"Getting path for {command} on {hostname}")
    try:
        result = await connection.run(shlex.join(["command", "-v", command]), timeout=timeout)
    except asyncssh.Error as err:
        raise ConnectionError(
            f"Error when trying to locate command '{command}' on {connection._username}@{hostname}: {err}"
        )

    if result.exit_status == 0 and result.stdout:
        stdout = result.stdout.decode() if isinstance(result.stdout, bytes) else result.stdout
        return stdout.strip()

    raise FileNotFoundError(f"Unable to find command '{command}' on {connection._username}@{hostname}")


async def execute_command(
    command: Sequence[str],
    host: str | None = None,
    **kwargs,
) -> tuple[int, str, str]:
    """
    Execute a command locally or remotely.

    This is the main entry point for command execution. It routes the command
    to either local subprocess execution or remote SSH execution based on
    whether host/username parameters are provided.

    Args:
        command: Command and arguments to execute (tuple or list). If the command
                 is not an absolute path it will be resolved to the full path
                 before execution.
        host: Optional remote host address
        **kwargs: Additional arguments (reserved for future use)

    Returns:
        Tuple of (return_code, stdout, stderr)

    Raises:
        ValueError: If host is provided without username
        ConnectionError: If remote connection fails
        ToolError: If the command is missing

    Examples:
        # Local execution
        >>> returncode, stdout, stderr = await execute_command(["ls", "-la"])

        # Remote execution
        >>> returncode, stdout, stderr = await execute_command(
        ...     ["ls", "-la"],
        ...     host="server.example.com",
        ...     username="admin"
        ... )
    """
    cmd_str = " ".join(command)

    if host:
        logger.debug(f"Routing to remote execution: {host} | command={cmd_str}")
        return await _connection_manager.execute_remote(command, host)

    logger.debug(f"LOCAL_EXEC: {cmd_str}")
    return await _execute_local(command)


async def execute_with_fallback(
    args: Sequence[str],
    fallback: Sequence[str] | None = None,
    host: str | None = None,
    **kwargs,
) -> tuple[int, str, str]:
    """
    Execute a command with optional fallback if primary command fails.

    This function attempts to execute the primary command. If it fails
    (non-zero return code) and a fallback command is provided, it will
    attempt the fallback command.

    Args:
        args: Primary command and arguments to execute (tuple or list)
        fallback: Optional fallback command if primary fails (tuple or list)
        host: Optional remote host address
        **kwargs: Additional arguments passed to execute_command

    Returns:
        Tuple of (return_code, stdout, stderr)

    Examples:
        # Try ss, fall back to netstat
        >>> returncode, stdout, stderr = await execute_with_fallback(
        ...     ["ss", "-tunap"],
        ...     fallback=["netstat", "-tunap"],
        ...     host="server.example.com"
        ... )
    """
    returncode, stdout, stderr = await execute_command(args, host=host, **kwargs)

    # If primary command failed and we have a fallback, try it
    if returncode != 0 and fallback:
        logger.debug(f"Primary command failed (exit={returncode}), trying fallback: {' '.join(fallback)}")
        returncode, stdout, stderr = await execute_command(fallback, host=host, **kwargs)

    return returncode, stdout, stderr


async def _execute_local(command: Sequence[str]) -> tuple[int, str, str]:
    """
    Execute a command locally using subprocess.

    Args:
        command: Command and arguments to execute (tuple or list)

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    # Convert to list for modification - CommandSpec.args is an immutable tuple
    cmd_list = list(command)
    cmd_str = " ".join(cmd_list)
    start_time = time.time()
    bin = cmd_list[0]
    if not Path(bin).is_absolute():
        cmd_list[0] = get_bin_path(bin)

    try:
        proc = await asyncio.create_subprocess_exec(*cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_bytes, stderr_bytes = await proc.communicate()

        return_code = proc.returncode if proc.returncode is not None else 0
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        duration = time.time() - start_time

        # DEBUG level: Log local command execution with timing
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
