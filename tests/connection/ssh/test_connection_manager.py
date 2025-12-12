import asyncssh
import pytest

from linux_mcp_server.connection.ssh import SSHConnectionManager


@pytest.fixture
def mock_connection(mocker):
    mock_connection = mocker.AsyncMock(asyncssh.SSHClientConnection, name="connection", _username="testuser")
    mock_connection.run.return_value = mocker.Mock(exit_status=0, stdout="remote output", stderr="")
    mock_connection.is_closed.return_value = False

    return mock_connection


@pytest.fixture
def mock_asyncssh_connect(mocker, mock_connection):
    mock_connect = mocker.AsyncMock(name="async_connect", return_value=mock_connection)
    mocker.patch("asyncssh.connect", mock_connect)

    return mock_connect


async def test_connection_manager_singleton():
    """Test that connection manager is a singleton."""
    manager1 = SSHConnectionManager()
    manager2 = SSHConnectionManager()

    assert manager1 is manager2


async def test_get_connection(mock_connection, mock_asyncssh_connect):
    """Test getting a new SSH connection."""
    manager = SSHConnectionManager()
    manager._connections.clear()
    await manager.get_connection("host1")
    await manager.get_connection("host1")  # Called twice to verify asyncssh.connect is only be called once

    mock_asyncssh_connect.assert_called_once()


async def test_get_connection_user_from_config(mocker, mock_asyncssh_connect):
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG.user", "bobo")

    manager = SSHConnectionManager()
    manager._connections.clear()
    await manager.get_connection("host1")

    assert mock_asyncssh_connect.call_args.kwargs.get("username") == "bobo"


async def test_get_connection_different_hosts(mocker, mock_asyncssh_connect):
    """Test that different hosts get different connections."""

    manager = SSHConnectionManager()
    manager._connections.clear()

    mock_conn1 = mocker.AsyncMock(asyncssh.SSHClientConnection, return_value=False, _username="testuser")
    mock_conn2 = mocker.AsyncMock(asyncssh.SSHClientConnection, return_value=False, _username="testuser")

    async def async_connect(*args, **kwargs):
        return mock_conn1 if kwargs.get("host") == "host1" else mock_conn2

    mock_asyncssh_connect.side_effect = async_connect

    conn1 = await manager.get_connection("host1")
    conn2 = await manager.get_connection("host2")

    assert conn1 is not conn2


async def test_execute_remote_success(mocker, mock_asyncssh_connect, mock_connection):
    """Test successful remote command execution."""
    manager = SSHConnectionManager()
    manager._connections.clear()

    returncode, stdout, stderr = await manager.execute_remote(["/bin/ls", "-la"], "testhost")

    assert returncode == 0
    assert stdout == "remote output"
    assert stderr == ""
    assert mock_connection.run.call_count == 1


async def test_execute_remote_command_failure(mocker, mock_connection):
    """Test remote command that returns non-zero exit code."""
    manager = SSHConnectionManager()
    manager._connections.clear()

    mock_connection.run.side_effect = asyncssh.Error(1, "Raised intentionally")
    mock_get_connection = mocker.AsyncMock(asyncssh.SSHClientConnection, return_value=mock_connection)
    mocker.patch.object(manager, "get_connection", mock_get_connection)

    with pytest.raises(ConnectionError, match="Raised intentionally"):
        await manager.execute_remote(["/invalid_command"], "testhost")


async def test_execute_remote_connection_failure(mocker, mock_asyncssh_connect):
    """Test handling of SSH connection failures."""
    manager = SSHConnectionManager()
    manager._connections.clear()

    mock_asyncssh_connect.side_effect = asyncssh.DisconnectError(1, "Connection refused")

    with pytest.raises(ConnectionError, match="Failed to connect"):
        await manager.execute_remote(["ls"], "unreachable")


async def test_execute_remote_authentication_failure(mocker, mock_asyncssh_connect):
    """Test handling of authentication failures."""
    manager = SSHConnectionManager()
    manager._connections.clear()

    mock_asyncssh_connect.side_effect = asyncssh.PermissionDenied("Auth failed")

    with pytest.raises(ConnectionError, match="Authentication failed"):
        await manager.execute_remote(["ls"], "testhost")


async def test_execute_remote_uses_discovered_key(mocker, mock_asyncssh_connect):
    """Test that remote execution uses discovered SSH key."""
    manager = SSHConnectionManager()
    manager._connections.clear()
    manager._ssh_key = "/home/user/.ssh/id_ed25519"

    await manager.execute_remote(["ls"], "testhost")

    call_kwargs = mock_asyncssh_connect.call_args.kwargs

    assert call_kwargs.get("client_keys") == ["/home/user/.ssh/id_ed25519"]


async def test_close_connections(mocker, mock_asyncssh_connect):
    """Test closing all connections."""
    manager = SSHConnectionManager()
    manager._connections.clear()

    mock_conn1 = mocker.AsyncMock(
        asyncssh.SSHClientConnection, return_value=False, wait_closed=mocker.AsyncMock(), _username="testuser"
    )
    mock_conn2 = mocker.AsyncMock(
        asyncssh.SSHClientConnection, return_value=False, wait_closed=mocker.AsyncMock(), _username="testuser"
    )

    async def async_connect(*args, **kwargs):
        return mock_conn1 if kwargs.get("host") == "host1" else mock_conn2

    mock_asyncssh_connect.side_effect = async_connect

    await manager.get_connection("host1")
    await manager.get_connection("host2")
    await manager.close_all()

    assert mock_conn1.close.call_count == 1
    assert mock_conn2.close.call_count == 1
    assert len(manager._connections) == 0
