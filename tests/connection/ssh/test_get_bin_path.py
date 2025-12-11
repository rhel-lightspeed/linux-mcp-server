import asyncssh
import pytest

from linux_mcp_server.connection.ssh import get_bin_path
from linux_mcp_server.connection.ssh import get_remote_bin_path


def test_get_bin_path_not_found(mocker):
    mocker.patch("linux_mcp_server.connection.ssh.shutil.which", return_value=None)
    with pytest.raises(FileNotFoundError, match="Unable to find"):
        get_bin_path("/bin/ls")


async def test_get_remote_bin_path_error(mocker):
    connection = mocker.Mock(asyncssh.SSHClientConnection, _username="testuser")
    connection.run = mocker.AsyncMock(side_effect=asyncssh.Error(1, "Raised intentionally"))

    with pytest.raises(ConnectionError, match="Raised intentionally"):
        await get_remote_bin_path("ls", "host", connection)


async def test_get_remote_bin_not_found(mocker):
    connection = mocker.Mock(asyncssh.SSHClientConnection, _username="testuser")
    connection.run = mocker.AsyncMock(return_value=mocker.Mock(exit_status=0, stdout="", stderr=""))

    with pytest.raises(FileNotFoundError, match="Unable to find command"):
        await get_remote_bin_path("ls", "host", connection)
