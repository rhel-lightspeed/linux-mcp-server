from contextlib import nullcontext
from unittest.mock import AsyncMock
from unittest.mock import Mock

import asyncssh
import pytest

from asyncssh import SSHClientConnection

from linux_mcp_server.connection.ssh import _execute_local
from linux_mcp_server.connection.ssh import SSHConnectionManager


def _make_success_mock():
    """Create a mock that returns successful command output."""
    return AsyncMock(return_value=Mock(exit_status=0, stdout="ok", stderr=""))


def _make_timeout_mock():
    """Create a mock that raises asyncssh.TimeoutError."""
    timeout_error = asyncssh.TimeoutError(
        env=None,
        command="cmd",
        subsystem=None,
        exit_status=None,
        exit_signal=None,
        returncode=None,
        stdout="",
        stderr="",
    )
    return AsyncMock(side_effect=timeout_error)


@pytest.fixture
def ssh_manager():
    """Provide a clean SSH manager for each test."""
    manager = SSHConnectionManager()
    manager._connections.clear()
    return manager


@pytest.fixture
def mock_ssh_connection(mocker):
    """Provide a mock SSH connection with asyncssh.connect patched."""
    mock_conn = Mock(spec=SSHClientConnection, _username="testuser")
    mock_conn.is_closed.return_value = False

    mock_connect = AsyncMock(spec=asyncssh.connect)
    mock_connect.return_value = mock_conn

    mocker.patch("asyncssh.connect", mock_connect)

    return mock_conn


@pytest.mark.parametrize(
    ("global_timeout", "per_cmd_timeout", "expected_timeout", "mock_run_factory", "expectation"),
    [
        # Success cases - verify timeout is passed correctly
        (30, None, 30, _make_success_mock, nullcontext()),
        (30, 60, 60, _make_success_mock, nullcontext()),
        # Timeout error cases - verify asyncssh.TimeoutError is handled
        (30, None, 30, _make_timeout_mock, pytest.raises(ConnectionError, match="Command timed out")),
        (60, 10, 10, _make_timeout_mock, pytest.raises(ConnectionError, match="Command timed out")),
    ],
    ids=[
        "uses_global_timeout",
        "per_cmd_overrides_global",
        "global_timeout_error",
        "per_cmd_timeout_error",
    ],
)
async def test_timeout_behavior(
    mocker,
    ssh_manager,
    mock_ssh_connection,
    global_timeout,
    per_cmd_timeout,
    expected_timeout,
    mock_run_factory,
    expectation,
):
    """Test timeout parameter passing and error handling."""
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.command_timeout", global_timeout)
    mocker.patch("linux_mcp_server.connection.ssh.get_remote_bin_path", return_value=("/usr/bin/cmd"))
    mock_ssh_connection.run = mock_run_factory()

    with expectation:
        # Only pass timeout if explicitly set (None means use default)
        kwargs = {}
        if per_cmd_timeout is not None:
            kwargs["timeout"] = per_cmd_timeout

        returncode, stdout, _ = await ssh_manager.execute_remote(["cmd"], "host", **kwargs)
        call_kwargs = mock_ssh_connection.run.call_args.kwargs

        assert returncode == 0
        assert stdout == "ok"
        assert call_kwargs["timeout"] == expected_timeout


async def test_timeout_error_contains_context(mocker, ssh_manager, mock_ssh_connection):
    """Test that timeout error message includes command, host, and user context."""
    mock_ssh_connection.run = _make_timeout_mock()
    mocker.patch("linux_mcp_server.connection.ssh.get_remote_bin_path", return_value=("/usr/bin/mycommand"))

    with pytest.raises(ConnectionError) as exc_info:
        await ssh_manager.execute_remote(["mycommand", "arg1"], "myhost.example.com", timeout=5)

    error_msg = str(exc_info.value)

    assert "testuser@myhost.example.com" in error_msg
    assert "mycommand" in error_msg
    assert "5s" in error_msg


class TestLocalTimeout:
    """Test timeout behavior for local command execution."""

    async def test_local_command_completes_within_timeout(self, mocker):
        """Local commands that finish before the timeout succeed normally."""
        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.command_timeout", 30)
        mocker.patch("linux_mcp_server.connection.ssh.get_bin_path", return_value="/bin/echo")

        returncode, stdout, stderr = await _execute_local(["/bin/echo", "hello"])

        assert returncode == 0
        assert isinstance(stdout, str)
        assert "hello" in stdout

    async def test_local_command_timeout_raises_connection_error(self, mocker):
        """Local commands exceeding the timeout raise ConnectionError."""
        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.command_timeout", 1)
        mocker.patch("linux_mcp_server.connection.ssh.get_bin_path", return_value="/bin/sleep")

        with pytest.raises(ConnectionError, match="Command timed out after 1s on localhost"):
            await _execute_local(["/bin/sleep", "60"])

    async def test_local_timeout_error_contains_command(self, mocker):
        """Timeout error message includes the command that timed out."""
        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.command_timeout", 1)
        mocker.patch("linux_mcp_server.connection.ssh.get_bin_path", return_value="/bin/sleep")

        with pytest.raises(ConnectionError) as exc_info:
            await _execute_local(["/bin/sleep", "60"])

        assert "sleep" in str(exc_info.value)
        assert "1s" in str(exc_info.value)
        assert "localhost" in str(exc_info.value)
