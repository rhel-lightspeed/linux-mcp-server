from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import Mock

import asyncssh
import pytest

from linux_mcp_server.connection.ssh import SSHConnectionManager


async def test_connection_manager_singleton():
    """Test that connection manager is a singleton."""
    manager1 = SSHConnectionManager()
    manager2 = SSHConnectionManager()

    assert manager1 is manager2


async def test_get_connection_creates_new(mocker):
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


async def test_get_connection_reuses_existing(mocker):
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


async def test_get_connection_different_hosts(mocker):
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


async def test_execute_remote_success(mocker):
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


async def test_execute_remote_command_failure(mocker):
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


async def test_execute_remote_connection_failure(mocker):
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


async def test_execute_remote_authentication_failure(mocker):
    """Test handling of authentication failures."""
    manager = SSHConnectionManager()
    manager._connections.clear()

    mock_connect = MagicMock()
    mock_connect.side_effect = asyncssh.PermissionDenied("Auth failed")
    mocker.patch("asyncssh.connect", mock_connect)

    with pytest.raises(ConnectionError, match="Authentication failed"):
        await manager.execute_remote(["ls"], "testhost")


async def test_execute_remote_uses_discovered_key(mocker):
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


async def test_close_connections(mocker):
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
