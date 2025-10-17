"""SSH executor for remote command execution.

This module provides functionality to execute commands on remote systems via SSH,
with connection pooling and SSH key discovery. It seamlessly routes commands to
either local or remote execution based on the provided parameters.
"""

import asyncio
import logging
import os
import shlex
import subprocess
import time

from pathlib import Path
from typing import Optional
from typing import Tuple

import asyncssh

from ..audit import log_ssh_command
from ..audit import log_ssh_connect


logger = logging.getLogger(__name__)


def discover_ssh_key() -> Optional[str]:
    """
    Discover SSH private key for authentication.

    Checks in order:
    1. LINUX_MCP_SSH_KEY_PATH environment variable
    2. Default locations: ~/.ssh/id_ed25519, ~/.ssh/id_rsa, ~/.ssh/id_ecdsa

    Returns:
        Path to SSH private key if found, None otherwise.
    """
    logger.debug("Discovering SSH key for authentication")

    # Check environment variable first
    env_key = os.getenv("LINUX_MCP_SSH_KEY_PATH")
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
    return None


class SSHConnectionManager:
    """
    Manages SSH connections with connection pooling.

    This class implements a singleton pattern to maintain a pool of SSH connections
    across the lifetime of the application, improving performance by reusing
    connections to the same hosts.
    """

    _instance = None

    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connections = {}
            cls._instance._ssh_key = discover_ssh_key()
        return cls._instance

    async def get_connection(self, host: str, username: str) -> asyncssh.SSHClientConnection:
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
        key = f"{username}@{host}"

        # Return existing connection if available
        if key in self._connections:
            conn = self._connections[key]
            if not conn.is_closed():
                # DEBUG level: Log connection reuse and pool state
                logger.debug(f"SSH_REUSE: {key} | pool_size={len(self._connections)}")
                # Use audit log with connection reuse info
                log_ssh_connect(host, username, status="success", reused=True, key_path=self._ssh_key)
                return conn
            else:
                # Connection was closed, remove it
                logger.debug(f"SSH_POOL: remove_closed_connection | connection={key}")
                del self._connections[key]

        # Create new connection
        # DEBUG level: Log connection attempt before it completes
        logger.debug(f"SSH_CONNECTING: {key} | key={self._ssh_key or 'none'}")

        try:
            connect_kwargs = {
                "host": host,
                "username": username,
                "known_hosts": None,  # Don't verify host keys for now
            }

            if self._ssh_key:
                connect_kwargs["client_keys"] = [self._ssh_key]

            conn = await asyncssh.connect(**connect_kwargs)
            self._connections[key] = conn

            # Log successful connection using audit function
            log_ssh_connect(host, username, status="success", reused=False, key_path=self._ssh_key)

            # DEBUG level: Log pool state
            logger.debug(f"SSH_POOL: add_connection | connections={len(self._connections)}")

            return conn

        except asyncssh.PermissionDenied as e:
            # Use audit log for authentication failure
            error_msg = str(e)
            log_ssh_connect(host, username, status="failed", error=f"Permission denied: {error_msg}")
            raise ConnectionError(f"Authentication failed for {username}@{host}") from e
        except asyncssh.Error as e:
            # Use audit log for connection failure
            error_msg = str(e)
            log_ssh_connect(host, username, status="failed", error=error_msg)
            raise ConnectionError(f"Failed to connect to {username}@{host}: {e}") from e

    async def execute_remote(
        self,
        command: list[str],
        host: str,
        username: str,
    ) -> Tuple[int, str, str]:
        """
        Execute a command on a remote host via SSH.

        Args:
            command: Command and arguments to execute
            host: Remote host address
            username: SSH username

        Returns:
            Tuple of (return_code, stdout, stderr)

        Raises:
            ConnectionError: If SSH connection fails
        """
        conn = await self.get_connection(host, username)

        # Build command string with proper shell escaping
        # Use shlex.quote() to ensure special characters (like \n in printf format) are preserved
        cmd_str = " ".join(shlex.quote(arg) for arg in command)

        # Start timing for command execution
        start_time = time.time()

        try:
            result = await conn.run(cmd_str, check=False)

            return_code = result.exit_status if result.exit_status is not None else 0
            stdout = result.stdout if result.stdout else ""
            stderr = result.stderr if result.stderr else ""

            # Calculate duration
            duration = time.time() - start_time

            # Use audit log for command execution
            log_ssh_command(cmd_str, host, exit_code=return_code, duration=duration)

            return return_code, stdout, stderr

        except asyncssh.Error as e:
            duration = time.time() - start_time
            logger.error(
                f"Error executing command on {username}@{host}: {e}",
                extra={
                    "event": "REMOTE_EXEC_ERROR",
                    "command": cmd_str,
                    "host": host,
                    "duration": f"{duration:.3f}s",
                    "error": str(e),
                },
            )
            raise ConnectionError(f"Failed to execute command on {username}@{host}: {e}") from e

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


async def execute_command(
    command: list[str],
    host: Optional[str] = None,
    username: Optional[str] = None,
    **kwargs,
) -> Tuple[int, str, str]:
    """
    Execute a command locally or remotely.

    This is the main entry point for command execution. It routes the command
    to either local subprocess execution or remote SSH execution based on
    whether host/username parameters are provided.

    Args:
        command: Command and arguments to execute
        host: Optional remote host address
        username: Optional SSH username (required if host is provided)
        **kwargs: Additional arguments (reserved for future use)

    Returns:
        Tuple of (return_code, stdout, stderr)

    Raises:
        ValueError: If host is provided without username
        ConnectionError: If remote connection fails

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

    # Route to remote execution if host is provided
    if host:
        if not username:
            logger.error(f"Host provided without username for command: {cmd_str}")
            raise ValueError("username is required when host is provided")

        logger.debug(f"Routing to remote execution: {username}@{host} | command={cmd_str}")
        return await _connection_manager.execute_remote(command, host, username)

    # Local execution
    logger.debug(f"LOCAL_EXEC: {cmd_str}")
    return await _execute_local(command)


async def _execute_local(command: list[str]) -> Tuple[int, str, str]:
    """
    Execute a command locally using subprocess.

    Args:
        command: Command and arguments to execute

    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    cmd_str = " ".join(command)
    start_time = time.time()

    try:
        proc = await asyncio.create_subprocess_exec(*command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
                "event": "LOCAL_EXEC_ERROR",
                "command": cmd_str,
                "duration": f"{duration:.3f}s",
                "error": str(e),
            },
        )
        return 1, "", str(e)
