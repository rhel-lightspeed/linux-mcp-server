"""SSH backend using asyncssh library.

This module provides SSH connectivity via the asyncssh library. It is used
on Windows where native SSH subprocess is not well-supported, or when
explicitly configured via ssh_backend="asyncssh".
"""

import logging
import shlex
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
from linux_mcp_server.connection.base import parse_remote_bin_path
from linux_mcp_server.utils.types import Host


logger = logging.getLogger("linux-mcp-server")


def discover_ssh_key() -> str | None:
    """Discover SSH private key for authentication.

    Checks in order:
    1. LINUX_MCP_SSH_KEY_PATH environment variable
    2. Default locations: ~/.ssh/id_ed25519, ~/.ssh/id_rsa, ~/.ssh/id_ecdsa
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
    return None


async def get_remote_bin_path(
    command: str,
    hostname: Host,
    connection: asyncssh.SSHClientConnection,
    timeout: int = CONFIG.command_timeout,
) -> str:
    """Get the full path to an executable on a remote system."""
    logger.debug(f"Getting path for {command} on {hostname}")
    try:
        result = await connection.run(shlex.join(["command", "-v", command]), timeout=timeout)
    except asyncssh.Error as err:
        raise ConnectionError(
            f"Error when trying to locate command '{command}' on {connection.get_extra_info('username')}@{hostname}: {err}"
        )

    return parse_remote_bin_path(
        command,
        hostname or "",
        result.exit_status or 0,
        result.stdout or "",
        username=connection.get_extra_info("username"),
    )


class SSHAsyncSSHManager:
    """Manages SSH connections using asyncssh with connection pooling.

    This class implements a singleton pattern to maintain a pool of SSH connections
    across the lifetime of the application, improving performance by reusing
    connections to the same hosts.
    """

    _instance: Optional["SSHAsyncSSHManager"] = None
    _connections: dict[str, asyncssh.SSHClientConnection]
    _ssh_key: str | None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connections = {}
            cls._instance._ssh_key = discover_ssh_key()
        return cls._instance

    async def get_connection(self, host: str) -> asyncssh.SSHClientConnection:
        """Get or create an SSH connection to a host."""
        key = host

        if key in self._connections:
            conn = self._connections[key]
            if not conn.is_closed():
                logger.debug(f"SSH_REUSE: {key} | pool_size={len(self._connections)}")
                log_ssh_connect(
                    host,
                    username=conn.get_extra_info("username"),
                    status=Status.success,
                    reused=True,
                    key_path=self._ssh_key,
                )
                return conn
            else:
                logger.debug(f"SSH_POOL: remove_closed_connection | connection={key}")
                del self._connections[key]

        logger.debug(f"{Event.SSH_CONNECTING}: {key} | key={self._ssh_key or 'none'}")

        try:
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

            if CONFIG.ssh_connect_timeout:
                connect_kwargs["connect_timeout"] = CONFIG.ssh_connect_timeout

            conn = await asyncssh.connect(**connect_kwargs)
            self._connections[key] = conn

            log_ssh_connect(
                host,
                username=conn.get_extra_info("username"),
                status=Status.success,
                reused=False,
                key_path=self._ssh_key,
            )
            logger.debug(f"SSH_POOL: add_connection | connections={len(self._connections)}")

            return conn

        except asyncssh.PermissionDenied as e:
            error_msg = str(e)
            log_ssh_connect(host, status=Status.failed, error=f"Permission denied: {error_msg}")
            raise ConnectionError(f"Authentication failed for {host}") from e
        except asyncssh.Error as e:
            error_msg = str(e)
            log_ssh_connect(host, status=Status.failed, error=error_msg)
            raise ConnectionError(f"Failed to connect to {host}: {e}") from e

    async def execute_remote(
        self,
        command: Sequence[str],
        host: str,
        timeout: int = CONFIG.command_timeout,
        encoding: str | None = "utf-8",
    ) -> tuple[int, str | bytes, str | bytes]:
        """Execute a command on a remote host via SSH."""
        conn = await self.get_connection(host)
        binary = command[0]
        if not Path(binary).is_absolute():
            binary = await get_remote_bin_path(binary, host, conn)

        full_command = [binary, *command[1:]]
        cmd_str = shlex.join(full_command)
        start_time = time.time()

        try:
            try:
                result = await conn.run(cmd_str, check=False, timeout=timeout, encoding=encoding)
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
                    f"Command timed out after {timeout}s on {conn.get_extra_info('username')}@{host}: {cmd_str}"
                ) from None

            return_code = result.exit_status if result.exit_status is not None else 0

            stdout = result.stdout if result.stdout else b"" if encoding is None else ""
            stderr = result.stderr if result.stderr else b"" if encoding is None else ""
            duration = time.time() - start_time

            log_ssh_command(cmd_str, host, exit_code=return_code, duration=duration, backend="asyncssh")

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

    async def close_all(self) -> None:
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


# Backwards compatibility alias
SSHConnectionManager = SSHAsyncSSHManager
