"""Protocol definitions and shared utilities for SSH connection backends.

This module defines abstract interfaces that all SSH backends must implement,
enabling a clean separation between the asyncssh and subprocess implementations.
"""

from collections.abc import Sequence
from typing import Protocol
from typing import runtime_checkable


def parse_remote_bin_path(
    command: str,
    host: str,
    returncode: int,
    stdout: str | bytes,
    username: str | None = None,
) -> str:
    """Parse the result of a remote 'command -v' lookup.

    Args:
        command: The command name that was looked up.
        host: The remote host where the lookup was performed.
        returncode: Exit code from the remote command.
        stdout: Standard output from the remote command.
        username: Optional username for error messages.

    Returns:
        The full path to the executable.

    Raises:
        FileNotFoundError: If the command was not found on the remote system.
    """
    if returncode == 0 and stdout:
        stdout_str = stdout if isinstance(stdout, str) else stdout.decode("utf-8")
        return stdout_str.strip()

    user_prefix = f"{username}@" if username else ""
    raise FileNotFoundError(f"Unable to find command '{command}' on {user_prefix}{host}")


@runtime_checkable
class SSHConnectionProtocol(Protocol):
    """Protocol for SSH connection backends.

    Defines the interface for a single SSH connection to a remote host.
    Implementations handle command execution and connection lifecycle.
    """

    async def run(
        self,
        command: str | Sequence[str],
        timeout: int | None = None,
        encoding: str | None = "utf-8",
    ) -> tuple[int, str | bytes, str | bytes]:
        """Execute a command on the remote host.

        Args:
            command: Command string or sequence of command arguments.
            timeout: Command timeout in seconds. None means no timeout.
            encoding: Character encoding for stdout/stderr. None returns bytes.

        Returns:
            Tuple of (return_code, stdout, stderr).
        """
        ...

    async def close(self) -> None:
        """Close the SSH connection and release resources."""
        ...

    def is_connected(self) -> bool:
        """Check if the connection is still active.

        Returns:
            True if connection is active, False otherwise.
        """
        ...


@runtime_checkable
class SSHManagerProtocol(Protocol):
    """Protocol for SSH connection manager backends.

    Defines the interface for managing multiple SSH connections with
    connection pooling and lifecycle management.
    """

    async def execute_remote(
        self,
        command: Sequence[str],
        host: str,
        timeout: int = 30,
        encoding: str | None = "utf-8",
    ) -> tuple[int, str | bytes, str | bytes]:
        """Execute a command on a remote host.

        Args:
            command: Command and arguments to execute.
            host: Remote host address.
            timeout: Command timeout in seconds.
            encoding: Character encoding for stdout/stderr. None returns bytes.

        Returns:
            Tuple of (return_code, stdout, stderr).

        Raises:
            ConnectionError: If SSH connection fails or command times out.
        """
        ...

    async def close_all(self) -> None:
        """Close all managed SSH connections."""
        ...
