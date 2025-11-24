"""Tests for SSH executor module."""

from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import asyncssh
import pytest

from linux_mcp_server.connection.ssh import discover_ssh_key
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.connection.ssh import SSHConnectionManager


class TestSSHKeyDiscovery:
    """Test SSH key discovery functionality."""

    @patch("linux_mcp_server.connection.ssh.CONFIG")
    def test_discover_ssh_key_with_env_var(self, mock_settings, tmp_path):
        """Test SSH key discovery with explicit environment variable."""
        key_path = tmp_path / "custom_key"
        key_path.touch()

        # Use mocker.patch with PropertyMock for proper attribute access
        mock_settings.ssh_key_path = str(key_path)
        mock_settings.search_for_ssh_key = False
        result = discover_ssh_key()
        assert result == str(key_path)

    @patch("linux_mcp_server.connection.ssh.CONFIG")
    def test_discover_ssh_key_env_var_not_exists(self, mock_settings, tmp_path):
        """Test SSH key discovery with non-existent env var path."""
        key_path = tmp_path / "nonexistent_key"

        mock_settings.ssh_key_path = str(key_path)
        result = discover_ssh_key()
        assert result is None

    @patch("linux_mcp_server.connection.ssh.CONFIG")
    def test_discover_ssh_key_default_locations(self, mock_settings, tmp_path, mocker):
        """Test SSH key discovery falls back to default locations."""
        # Mock home directory
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()

        # Create a default key
        id_ed25519 = fake_ssh_dir / "id_ed25519"
        id_ed25519.touch()

        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        # Use mocker.patch with proper attribute configuration
        # Configure mock to return None for ssh_key_path (not a MagicMock)
        mock_settings.ssh_key_path = None
        mock_settings.search_for_ssh_key = True

        result = discover_ssh_key()

        assert result == str(id_ed25519)

    @patch("linux_mcp_server.connection.ssh.CONFIG")
    def test_discover_ssh_key_prefers_ed25519(self, mock_settings, tmp_path, mocker):
        """Test SSH key discovery prefers ed25519 over rsa."""
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()

        # Create both keys
        id_rsa = fake_ssh_dir / "id_rsa"
        id_ed25519 = fake_ssh_dir / "id_ed25519"
        id_rsa.touch()
        id_ed25519.touch()

        mocker.patch("pathlib.Path.home", return_value=tmp_path)
        # Use mocker.patch with proper attribute configuration
        mock_settings.ssh_key_path = None
        mock_settings.search_for_ssh_key = True

        result = discover_ssh_key()

        # Should prefer ed25519
        assert result == str(id_ed25519)

    @patch("linux_mcp_server.connection.ssh.CONFIG")
    def test_discover_ssh_key_no_keys_found(self, mock_settings, tmp_path, mocker):
        """Test SSH key discovery when no keys exist."""
        fake_ssh_dir = tmp_path / ".ssh"
        fake_ssh_dir.mkdir()

        mock_settings.seach_for_ssh_key = "yes"
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

    async def test_execute_command_remote_routes_to_ssh(self):
        """Test that remote execution routes through SSH."""
        mock_manager = AsyncMock()
        mock_manager.execute_remote = AsyncMock(return_value=(0, "output", ""))

        with patch("linux_mcp_server.connection.ssh._connection_manager", mock_manager):
            returncode, stdout, stderr = await execute_command(
                ["ls", "-la"],
                host="remote.example.com",
                username="testuser",
            )

            assert returncode == 0
            assert stdout == "output"
            mock_manager.execute_remote.assert_called_once()

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

    async def test_get_connection_creates_new(self):
        """Test getting a new SSH connection."""
        manager = SSHConnectionManager()

        mock_conn = AsyncMock()
        mock_conn.is_closed = Mock(return_value=False)

        async def async_connect(*args, **kwargs):
            return mock_conn

        with patch("asyncssh.connect", side_effect=async_connect) as mock_connect:
            conn = await manager.get_connection("host1", "user1")

            assert conn is mock_conn
            mock_connect.assert_called_once()

    async def test_get_connection_reuses_existing(self):
        """Test that existing connections are reused."""
        manager = SSHConnectionManager()
        manager._connections.clear()  # Clear any existing connections

        mock_conn = AsyncMock()
        mock_conn.is_closed = Mock(return_value=False)

        async def async_connect(*args, **kwargs):
            return mock_conn

        with patch("asyncssh.connect", side_effect=async_connect) as mock_connect:
            conn1 = await manager.get_connection("host1", "user1")
            conn2 = await manager.get_connection("host1", "user1")

            assert conn1 is conn2
            assert mock_connect.call_count == 1  # Only connected once

    async def test_get_connection_different_hosts(self):
        """Test that different hosts get different connections."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        mock_conn1 = AsyncMock()
        mock_conn1.is_closed = Mock(return_value=False)
        mock_conn2 = AsyncMock()
        mock_conn2.is_closed = Mock(return_value=False)

        async def async_connect(*args, **kwargs):
            return mock_conn1 if kwargs.get("host") == "host1" else mock_conn2

        with patch("asyncssh.connect", side_effect=async_connect):
            conn1 = await manager.get_connection("host1", "user1")
            conn2 = await manager.get_connection("host2", "user1")

            assert conn1 is not conn2

    async def test_execute_remote_success(self):
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

        with patch("asyncssh.connect", side_effect=async_connect):
            returncode, stdout, stderr = await manager.execute_remote(["ls", "-la"], "testhost", "testuser")

            assert returncode == 0
            assert stdout == "remote output"
            assert stderr == ""
            mock_conn.run.assert_called_once()

    async def test_execute_remote_command_failure(self):
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

        with patch("asyncssh.connect", side_effect=async_connect):
            returncode, stdout, stderr = await manager.execute_remote(["invalid_command"], "testhost", "testuser")

            assert returncode == 1
            assert "command not found" in stderr

    async def test_execute_remote_connection_failure(self):
        """Test handling of SSH connection failures."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        async def async_connect_fail(*args, **kwargs):
            raise asyncssh.DisconnectError(1, "Connection refused")

        with patch("asyncssh.connect", side_effect=async_connect_fail):
            with pytest.raises(ConnectionError, match="Failed to connect"):
                await manager.execute_remote(["ls"], "unreachable", "testuser")

    async def test_execute_remote_authentication_failure(self):
        """Test handling of authentication failures."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        with patch("asyncssh.connect", side_effect=asyncssh.PermissionDenied("Auth failed")):
            with pytest.raises(ConnectionError, match="Authentication failed"):
                await manager.execute_remote(["ls"], "testhost", "baduser")

    async def test_execute_remote_uses_discovered_key(self):
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

        with patch("asyncssh.connect", side_effect=async_connect) as mock_connect:
            await manager.execute_remote(["ls"], "testhost", "testuser")

            # Verify connect was called with the key
            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs.get("client_keys") == ["/home/user/.ssh/id_ed25519"]

    async def test_close_connections(self):
        """Test closing all connections."""
        manager = SSHConnectionManager()
        manager._connections.clear()

        mock_conn1 = AsyncMock()
        mock_conn1.is_closed = Mock(return_value=False)
        mock_conn1.wait_closed = AsyncMock()

        mock_conn2 = AsyncMock()
        mock_conn2.is_closed = Mock(return_value=False)
        mock_conn2.wait_closed = AsyncMock()

        async def async_connect(*args, **kwargs):
            return mock_conn1 if kwargs.get("host") == "host1" else mock_conn2

        with patch("asyncssh.connect", side_effect=async_connect):
            await manager.get_connection("host1", "user1")
            await manager.get_connection("host2", "user1")

            await manager.close_all()

            mock_conn1.close.assert_called_once()
            mock_conn2.close.assert_called_once()
            assert len(manager._connections) == 0
