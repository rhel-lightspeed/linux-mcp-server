"""Tests for SSH executor module."""

from contextlib import nullcontext
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock

import asyncssh
import pytest

from asyncssh import SSHClientConnection

from linux_mcp_server.connection.ssh import discover_ssh_key
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.connection.ssh import SSHConnectionManager


class TestSSHKeyDiscovery:
    """Test SSH key discovery functionality."""

    def test_discover_ssh_key_env_var_not_exists(self, mocker, tmp_path):
        """Test SSH key discovery with non-existent env var path."""
        key_path = tmp_path / "nonexistent_key"

        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.ssh_key_path", key_path)

        result = discover_ssh_key()
        assert result is None

    def test_discover_ssh_key_default_locations(self, tmp_path, mocker):
        """Test SSH key discovery falls back to default locations."""
        # Mock home directory
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()

        # Create a default key
        id_ed25519 = fake_ssh_dir / "id_ed25519"
        id_ed25519.touch()

        # Use mocker.patch with proper attribute configuration
        # Configure mock to return None for ssh_key_path (not a MagicMock)
        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.ssh_key_path", None)
        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.search_for_ssh_key", True)

        result = discover_ssh_key()

        assert result == str(id_ed25519)

    def test_discover_ssh_key_prefers_ed25519(self, tmp_path, mocker):
        """Test SSH key discovery prefers ed25519 over rsa."""
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()

        # Create both keys
        id_rsa = fake_ssh_dir / "id_rsa"
        id_ed25519 = fake_ssh_dir / "id_ed25519"
        id_rsa.touch()
        id_ed25519.touch()

        # Use mocker.patch with proper attribute configuration
        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.ssh_key_path", None)
        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.search_for_ssh_key", True)

        result = discover_ssh_key()

        # Should prefer ed25519
        assert result == str(id_ed25519)

    def test_discover_ssh_key_no_keys_found(self, tmp_path, mocker):
        """Test SSH key discovery when no keys exist."""
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()

        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.search_for_ssh_key", "yes")
        mocker.patch("pathlib.Path.home", return_value=tmp_path)

        result = discover_ssh_key()

        assert result is None


class TestExecuteCommand:
    """Test the execute_command function."""

    async def test_execute_command_local_success(self):
        """Test local command execution success."""
        returncode, stdout, stderr = await execute_command(["echo", "hello"])

        assert returncode == 0
        assert "hello" in stdout
        assert stderr == ""

    async def test_execute_command_local_failure(self):
        """Test local command execution failure."""
        returncode, stdout, stderr = await execute_command(["false"])

        assert returncode != 0

    async def test_execute_command_local_with_stderr(self):
        """Test local command that produces stderr output."""
        returncode, stdout, stderr = await execute_command(["bash", "-c", "echo error >&2"])

        assert "error" in stderr

    async def test_execute_command_remote_routes_to_ssh(self, mocker):
        """Test that remote execution routes through SSH."""
        mock_manager = AsyncMock()
        mock_manager.execute_remote = AsyncMock(return_value=(0, "output", ""))

        mocker.patch("linux_mcp_server.connection.ssh._connection_manager", mock_manager)
        returncode, stdout, stderr = await execute_command(
            ["ls", "-la"],
            host="remote.example.com",
            username="testuser",
        )

        assert returncode == 0
        assert stdout == "output"
        assert mock_manager.execute_remote.call_count == 2

    async def test_execute_command_remote_requires_host(self):
        """Test that username without host uses local execution."""
        # Should execute locally, not fail
        returncode, stdout, stderr = await execute_command(["echo", "test"], username="someuser")
        assert returncode == 0


class TestSSHConnectionManager:
    """Test SSH connection manager."""

    async def test_connection_manager_singleton(self):
        """Test that connection manager is a singleton."""
        manager1 = SSHConnectionManager()
        manager2 = SSHConnectionManager()

        assert manager1 is manager2

    async def test_get_connection_creates_new(self, mocker):
        """Test getting a new SSH connection."""
        manager = SSHConnectionManager()

        mock_conn = AsyncMock()
        mock_conn.is_closed = Mock(return_value=False)

        async def async_connect(*args, **kwargs):
            return mock_conn

        mock_connect = MagicMock()
        mock_connect.side_effect = async_connect
        mocker.patch("asyncssh.connect", mock_connect)

        conn = await manager.get_connection("host1")
        assert conn is mock_conn
        mock_connect.assert_called_once()

    async def test_get_connection_reuses_existing(self, mocker):
        """Test that existing connections are reused."""
        manager = SSHConnectionManager()
        manager._connections.clear()  # Clear any existing connections

        mock_conn = AsyncMock(asyncssh.SSHClientConnection, _username="someuser")
        mock_conn.is_closed = Mock(return_value=False)

        async def async_connect(*args, **kwargs):
            return mock_conn

        mock_connect = MagicMock(asyncssh.SSHClientConnection, _username="someuser")
        mock_connect.side_effect = async_connect
        mocker.patch("asyncssh.connect", mock_connect)

        conn1 = await manager.get_connection("host1")
        conn2 = await manager.get_connection("host1")

        assert conn1 is conn2
        assert mock_connect.call_count == 1  # Only connected once

    async def test_get_connection_different_hosts(self, mocker):
        """Test that different hosts get different connections."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        mock_conn1 = AsyncMock()
        mock_conn1.is_closed = Mock(return_value=False)
        mock_conn2 = AsyncMock()
        mock_conn2.is_closed = Mock(return_value=False)

        async def async_connect(*args, **kwargs):
            return mock_conn1 if kwargs.get("host") == "host1" else mock_conn2

        mock_connect = MagicMock()
        mock_connect.side_effect = async_connect
        mocker.patch("asyncssh.connect", mock_connect)

        conn1 = await manager.get_connection("host1")
        conn2 = await manager.get_connection("host2")

        assert conn1 is not conn2

    async def test_execute_remote_success(self, mocker):
        """Test successful remote command execution."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        # Mock SSH connection and result
        mock_result = Mock()
        mock_result.exit_status = 0
        mock_result.stdout = "remote output"
        mock_result.stderr = ""

        mock_conn = AsyncMock()
        mock_conn.is_closed = Mock(return_value=False)
        mock_conn.run = AsyncMock(return_value=mock_result)

        async def async_connect(*args, **kwargs):
            return mock_conn

        mock_connect = MagicMock()
        mock_connect.side_effect = async_connect
        mocker.patch("asyncssh.connect", mock_connect)

        returncode, stdout, stderr = await manager.execute_remote(["ls", "-la"], "testhost")

        assert returncode == 0
        assert stdout == "remote output"
        assert stderr == ""
        mock_conn.run.assert_called_once()

    async def test_execute_remote_command_failure(self, mocker):
        """Test remote command that returns non-zero exit code."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        mock_result = Mock()
        mock_result.exit_status = 1
        mock_result.stdout = ""
        mock_result.stderr = "command not found"

        mock_conn = AsyncMock()
        mock_conn.is_closed = Mock(return_value=False)
        mock_conn.run = AsyncMock(return_value=mock_result)

        async def async_connect(*args, **kwargs):
            return mock_conn

        mock_connect = MagicMock()
        mock_connect.side_effect = async_connect
        mocker.patch("asyncssh.connect", mock_connect)
        returncode, stdout, stderr = await manager.execute_remote(["invalid_command"], "testhost")

        assert returncode == 1
        assert "command not found" in stderr

    async def test_execute_remote_connection_failure(self, mocker):
        """Test handling of SSH connection failures."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        async def async_connect_fail(*args, **kwargs):
            raise asyncssh.DisconnectError(1, "Connection refused")

        mock_connect = MagicMock()
        mock_connect.side_effect = async_connect_fail
        mocker.patch("asyncssh.connect", mock_connect)

        with pytest.raises(ConnectionError, match="Failed to connect"):
            await manager.execute_remote(["ls"], "unreachable")

    async def test_execute_remote_authentication_failure(self, mocker):
        """Test handling of authentication failures."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        mock_connect = MagicMock()
        mock_connect.side_effect = asyncssh.PermissionDenied("Auth failed")
        mocker.patch("asyncssh.connect", mock_connect)

        with pytest.raises(ConnectionError, match="Authentication failed"):
            await manager.execute_remote(["ls"], "testhost")

    async def test_execute_remote_uses_discovered_key(self, mocker):
        """Test that remote execution uses discovered SSH key."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        mock_conn = AsyncMock()
        mock_conn.is_closed = Mock(return_value=False)
        mock_result = Mock()
        mock_result.exit_status = 0
        mock_result.stdout = "ok"
        mock_result.stderr = ""
        mock_conn.run = AsyncMock(return_value=mock_result)

        # Set SSH key on the manager
        manager._ssh_key = "/home/user/.ssh/id_ed25519"

        async def async_connect(*args, **kwargs):
            return mock_conn

        mock_connect = MagicMock()
        mock_connect.side_effect = async_connect
        mocker.patch("asyncssh.connect", mock_connect)

        await manager.execute_remote(["ls"], "testhost")

        # Verify connect was called with the key
        call_kwargs = mock_connect.call_args[1]
        assert call_kwargs.get("client_keys") == ["/home/user/.ssh/id_ed25519"]

    async def test_close_connections(self, mocker):
        """Test closing all connections."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        mock_conn1 = AsyncMock(asyncssh.SSHClientConnection, _host="host1", _username="someuser")
        mock_conn1.is_closed = Mock(return_value=False)
        mock_conn1.wait_closed = AsyncMock()

        mock_conn2 = AsyncMock(asyncssh.SSHClientConnection, _host="host1", _username="someuser")
        mock_conn2.is_closed = Mock(return_value=False)
        mock_conn2.wait_closed = AsyncMock()

        async def async_connect(*args, **kwargs):
            return mock_conn1 if kwargs.get("host") == "host1" else mock_conn2

        mock_connect = MagicMock()
        mock_connect.side_effect = async_connect
        mocker.patch("asyncssh.connect", mock_connect)

        await manager.get_connection("host1")
        await manager.get_connection("host2")

        await manager.close_all()

        mock_conn1.close.assert_called_once()
        mock_conn2.close.assert_called_once()
        assert len(manager._connections) == 0


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


class TestSSHTimeouts:
    """Test SSH command timeout behavior (PR #1)."""

    @pytest.fixture
    def ssh_manager(self):
        """Provide a clean SSH manager for each test."""
        manager = SSHConnectionManager()
        manager._connections.clear()
        return manager

    @pytest.fixture
    def mock_ssh_connection(self, mocker):
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
        self,
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

    async def test_timeout_error_contains_context(self, mocker, ssh_manager, mock_ssh_connection):
        """Test that timeout error message includes command, host, and user context."""
        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.command_timeout", 30)
        mock_ssh_connection.run = _make_timeout_mock()

        with pytest.raises(ConnectionError) as exc_info:
            await ssh_manager.execute_remote(["mycommand", "arg1"], "myhost.example.com", timeout=5)

        error_msg = str(exc_info.value)

        assert "testuser@myhost.example.com" in error_msg
        assert "mycommand" in error_msg
        assert "5s" in error_msg


class TestSSHHostKeyVerification:
    """Test SSH host key verification behavior (PR #2)."""

    @pytest.fixture
    def ssh_manager(self):
        """Provide a clean SSH manager for each test."""
        manager = SSHConnectionManager()
        manager._connections.clear()
        return manager

    @pytest.fixture
    def mock_asyncssh_connect(self, mocker):
        """Provide a mock for asyncssh.connect that captures call arguments."""
        mock_conn = AsyncMock()
        mock_conn.is_closed = Mock(return_value=False)

        captured_kwargs = {}

        async def capture_connect(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return mock_conn

        mock_connect = MagicMock(side_effect=capture_connect)
        mocker.patch("asyncssh.connect", mock_connect)

        return captured_kwargs

    @pytest.mark.parametrize(
        ("verify_host_keys", "use_custom_path", "expect_none", "expect_warning"),
        [
            (True, False, False, False),  # Default: uses ~/.ssh/known_hosts
            (True, True, False, False),  # Custom path used when verification enabled
            (False, False, True, True),  # Disabled: None + warning
            (False, True, True, True),  # Disabled overrides custom path
        ],
        ids=[
            "enabled_default_path",
            "enabled_custom_path",
            "disabled_logs_warning",
            "disabled_overrides_custom",
        ],
    )
    async def test_known_hosts_configuration(
        self,
        mocker,
        ssh_manager,
        mock_asyncssh_connect,
        tmp_path,
        caplog,
        verify_host_keys,
        use_custom_path,
        expect_none,
        expect_warning,
    ):
        """Test known_hosts is configured correctly based on verify_host_keys and path settings."""
        custom_path = tmp_path / "custom_known_hosts" if use_custom_path else None

        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.verify_host_keys", verify_host_keys)
        mocker.patch("linux_mcp_server.connection.ssh.CONFIG.known_hosts_path", custom_path)
        mocker.patch("pathlib.Path.home", return_value=tmp_path)

        with caplog.at_level("WARNING"):
            await ssh_manager.get_connection("testhost")

        if expect_none:
            assert mock_asyncssh_connect["known_hosts"] is None
        elif use_custom_path:
            assert mock_asyncssh_connect["known_hosts"] == str(custom_path)
        else:
            assert mock_asyncssh_connect["known_hosts"] == str(tmp_path / ".ssh" / "known_hosts")

        if expect_warning:
            assert "host key verification disabled" in caplog.text.lower()
            assert "mitm" in caplog.text.lower()
        else:
            assert "mitm" not in caplog.text.lower()
