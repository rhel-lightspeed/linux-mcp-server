"""SSH backend using native subprocess for command execution.

This module provides SSH connectivity via the system's native `ssh` command,
enabling full support for user SSH configurations including ProxyJump,
Kerberos/GSSAPI authentication, smartcards, and ControlMaster multiplexing.
"""

import asyncio
import atexit
import getpass
import hashlib
import logging
import shlex
import shutil
import tempfile
import time

from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar
from typing import Optional

from linux_mcp_server.audit import log_ssh_command
from linux_mcp_server.audit import log_ssh_connect
from linux_mcp_server.audit import Status
from linux_mcp_server.config import CONFIG
from linux_mcp_server.connection.base import parse_remote_bin_path


logger = logging.getLogger("linux-mcp-server")

# SSH exit code indicating connection-level failure (vs command failure)
SSH_CONNECTION_ERROR_CODE = 255


def _create_control_dir() -> Path:
    """Create and return the ControlMaster socket directory.

    Uses a per-user directory under /tmp to avoid permission issues
    on multi-user systems while keeping paths short for the 108-char
    Unix socket path limit.
    """
    user_hash = hashlib.sha256(getpass.getuser().encode()).hexdigest()[:8]
    control_dir = Path(tempfile.gettempdir()) / f"linux_mcp_{user_hash}"
    control_dir.mkdir(mode=0o700, exist_ok=True)
    return control_dir


def _create_control_path(host: str) -> Path:
    """Generate ControlMaster socket path for a host.

    Uses hash-based naming to keep paths under the 108-char Unix socket limit
    while maintaining uniqueness per host.
    """
    host_hash = hashlib.sha256(host.encode()).hexdigest()[:12]
    return _create_control_dir() / f"{host_hash}.sock"


def _find_ssh_binary() -> str:
    """Locate the ssh binary, raising FileNotFoundError if not found."""
    ssh_path = shutil.which("ssh")
    if ssh_path is None:
        raise FileNotFoundError("ssh command not found in PATH")
    return ssh_path


class SSHSubprocessConnection:
    """SSH connection to a single host using native subprocess.

    Uses ControlMaster for connection multiplexing, inheriting all user
    SSH configuration from ~/.ssh/config.
    """

    def __init__(
        self,
        host: str,
        control_persist: int = 300,
    ):
        self._host = host
        self._control_path = _create_control_path(host)
        self._control_persist = control_persist
        self._ssh_bin = _find_ssh_binary()
        self._connected = False

    def _build_ssh_command(self, remote_command: str, timeout: int | None = None) -> list[str]:
        """Build the ssh command with all required options.

        SSH options set here take precedence over ~/.ssh/config settings.
        This is intentional to ensure consistent behavior regardless of
        user configuration.
        """
        cmd = [
            self._ssh_bin,
            # Disable interactive prompts (passwords, host key confirmation)
            "-o",
            "BatchMode=yes",
            # Send keepalive every 30s to detect dead connections
            "-o",
            "ServerAliveInterval=30",
            # Disconnect after 3 missed keepalives (90s unresponsive)
            "-o",
            "ServerAliveCountMax=3",
            # Reuse existing connection if available, create master if not
            "-o",
            "ControlMaster=auto",
            # Unix socket path for connection multiplexing
            "-o",
            f"ControlPath={self._control_path}",
            # Keep master connection alive for N seconds after last session
            "-o",
            f"ControlPersist={self._control_persist}",
            # Host key verification policy (security vs convenience tradeoff)
            "-o",
            f"StrictHostKeyChecking={'yes' if CONFIG.verify_host_keys else 'no'}",
            # Path to known_hosts file for host key verification
            "-o",
            f"UserKnownHostsFile={CONFIG.effective_known_hosts_path}",
        ]

        if CONFIG.ssh_connect_timeout:
            cmd.extend(["-o", f"ConnectTimeout={CONFIG.ssh_connect_timeout}"])

        if CONFIG.ssh_key_path:
            cmd.extend(["-i", str(CONFIG.ssh_key_path)])

        if CONFIG.user:
            cmd.extend(["-l", CONFIG.user])

        cmd.append(self._host)
        cmd.append(remote_command)

        return cmd

    async def run(
        self,
        command: str | Sequence[str],
        timeout: int | None = None,
        encoding: str | None = "utf-8",
    ) -> tuple[int, str | bytes, str | bytes]:
        """Execute a command on the remote host via SSH subprocess."""
        if isinstance(command, str):
            remote_cmd = command
        else:
            remote_cmd = shlex.join(command)

        ssh_cmd = self._build_ssh_command(remote_cmd, timeout)
        start_time = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                *ssh_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(timeout) if timeout else None,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                duration = time.time() - start_time
                logger.error(
                    f"SSH command timed out after {timeout}s on {self._host}",
                    extra={"duration": f"{duration:.3f}s"},
                )
                raise ConnectionError(f"Command timed out after {timeout}s on {self._host}: {remote_cmd}") from None

            return_code = proc.returncode if proc.returncode is not None else 0

            if return_code == SSH_CONNECTION_ERROR_CODE:
                stderr_text = stderr_bytes.decode("utf-8", errors="replace")
                raise ConnectionError(f"SSH connection failed to {self._host}: {stderr_text}")

            if not self._connected:
                self._connected = True
                log_ssh_connect(self._host, username=CONFIG.user, status=Status.success, reused=False)
            duration = time.time() - start_time
            log_ssh_command(remote_cmd, self._host, exit_code=return_code, duration=duration)

            if encoding is None:
                return return_code, stdout_bytes, stderr_bytes

            stdout = stdout_bytes.decode(encoding, errors="replace")
            stderr = stderr_bytes.decode(encoding, errors="replace")
            return return_code, stdout, stderr

        except FileNotFoundError as e:
            raise ConnectionError(f"SSH binary not found: {e}") from e
        except OSError as e:
            raise ConnectionError(f"Failed to execute SSH: {e}") from e

    async def close(self) -> None:
        """Close the ControlMaster connection and remove the socket."""
        if self._control_path.exists():
            try:
                proc = await asyncio.create_subprocess_exec(
                    self._ssh_bin,
                    "-O",
                    "exit",
                    "-o",
                    f"ControlPath={self._control_path}",
                    self._host,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except (asyncio.TimeoutError, OSError) as e:
                logger.debug(f"ControlMaster exit failed for {self._host}: {e}")
            finally:
                try:
                    self._control_path.unlink(missing_ok=True)
                except OSError:
                    pass

        self._connected = False

    def is_connected(self) -> bool:
        """Check if the connection is active (ControlMaster socket exists)."""
        return self._connected and self._control_path.exists()


class SSHSubprocessManager:
    """Manages SSH subprocess connections with connection pooling.

    Implements the singleton pattern to maintain a pool of SSH connections
    across the application lifetime. Uses ControlMaster for efficient
    connection multiplexing.
    """

    _instance: ClassVar[Optional["SSHSubprocessManager"]] = None
    _atexit_registered: ClassVar[bool] = False
    _connections: dict[str, SSHSubprocessConnection]
    _control_persist: int

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._connections = {}
            cls._instance._control_persist = CONFIG.ssh_control_persist
            if not cls._atexit_registered:
                atexit.register(cls._instance._cleanup_sync)
                cls._atexit_registered = True
        return cls._instance

    def _cleanup_sync(self) -> None:
        """Synchronous cleanup for atexit handler."""
        control_dir = _create_control_dir()
        if control_dir.exists():
            for socket_file in control_dir.glob("*.sock"):
                try:
                    socket_file.unlink()
                except OSError:
                    pass
            try:
                control_dir.rmdir()
            except OSError:
                pass

    async def _get_connection(self, host: str) -> SSHSubprocessConnection:
        """Get or create an SSH connection for a host."""
        if host in self._connections:
            conn = self._connections[host]
            if conn.is_connected():
                logger.debug(f"SSH_REUSE: {host} | pool_size={len(self._connections)}")
                log_ssh_connect(host, username=CONFIG.user, status=Status.success, reused=True)
                return conn
            del self._connections[host]

        logger.debug(f"SSH_CONNECTING: {host}")
        conn = SSHSubprocessConnection(host, control_persist=self._control_persist)
        self._connections[host] = conn
        return conn

    async def execute_remote(
        self,
        command: Sequence[str],
        host: str,
        timeout: int = CONFIG.command_timeout,
        encoding: str | None = "utf-8",
    ) -> tuple[int, str | bytes, str | bytes]:
        """Execute a command on a remote host via SSH subprocess."""
        conn = await self._get_connection(host)

        binary = command[0]
        if not Path(binary).is_absolute():
            binary = await self._get_remote_bin_path(binary, host, conn, timeout)

        full_command = [binary, *command[1:]]

        try:
            return await conn.run(full_command, timeout=timeout, encoding=encoding)
        except ConnectionError:
            if host in self._connections:
                await self._connections[host].close()
                del self._connections[host]
            raise

    async def _get_remote_bin_path(
        self,
        command: str,
        host: str,
        conn: SSHSubprocessConnection,
        timeout: int,
    ) -> str:
        """Get the full path to an executable on the remote system."""
        logger.debug(f"Getting path for {command} on {host}")
        returncode, stdout, _ = await conn.run(
            ["command", "-v", command],
            timeout=timeout,
            encoding="utf-8",
        )
        return parse_remote_bin_path(command, host, returncode, stdout, username=CONFIG.user)

    async def close_all(self) -> None:
        """Close all SSH connections."""
        connection_count = len(self._connections)
        logger.info(f"Closing {connection_count} SSH subprocess connections")

        for host, conn in list(self._connections.items()):
            try:
                logger.debug(f"SSH_CLOSE: {host}")
                await conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection to {host}: {e}")

        self._connections.clear()
        logger.debug(f"SSH_POOL: cleared | closed_connections={connection_count}")
