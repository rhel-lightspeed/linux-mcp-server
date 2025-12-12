import pytest

from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.connection.ssh import SSHConnectionManager


@pytest.mark.parametrize(
    "command, kwargs, expected_rc, expected_out, expected_err",
    (
        (["echo", "hello"], {}, 0, "hello", ""),
        (["false"], {}, 1, "", ""),
        (["bash", "-c", "echo error >&2"], {}, 0, "", "error"),
        (["echo", "test"], {"username": "someuser"}, 0, "test", ""),
        (["/bin/echo", "test"], {}, 0, "test", ""),
    ),
)
async def test_execute_command_local(command, kwargs, expected_rc, expected_out, expected_err):
    """Test local command execution success."""
    returncode, stdout, stderr = await execute_command(command, **kwargs)

    assert returncode == expected_rc
    assert expected_out in stdout
    assert expected_err in stderr


async def test_execute_command_remote(mocker):
    """Test that remote execution routes through SSH."""
    mock_manager = mocker.Mock(SSHConnectionManager)
    mock_manager.execute_remote = mocker.AsyncMock(return_value=(0, "output", ""))
    mocker.patch("linux_mcp_server.connection.ssh._connection_manager", mock_manager)

    returncode, stdout, stderr = await execute_command(
        ["ls", "-la"],
        host="remote.example.com",
        username="testuser",
    )

    assert returncode == 0
    assert stdout == "output"
    assert mock_manager.execute_remote.call_count == 1
