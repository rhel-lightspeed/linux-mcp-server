from pathlib import Path

import pytest

from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.connection.ssh import SSHConnectionManager
from linux_mcp_server.execution_context import ExecutionContext
from linux_mcp_server.execution_context import use_execution_context


@pytest.fixture
def mock_connection_manager(mocker):
    """Fixture to mock the SSH connection manager."""
    mock_manager = mocker.Mock(spec=SSHConnectionManager)
    mock_manager.execute_remote = mocker.AsyncMock(return_value=(0, "output", ""))
    mocker.patch("linux_mcp_server.connection.ssh._connection_manager", mock_manager)
    return mock_manager


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
    context = ExecutionContext(allow_local=True)

    with use_execution_context(context):
        returncode, stdout, stderr = await execute_command(command, **kwargs)

    assert returncode == expected_rc
    assert expected_out in stdout
    assert expected_err in stderr


async def test_execute_command_remote(mock_connection_manager):
    """Test that remote execution routes through SSH."""
    context = ExecutionContext(allow_ssh_default=True)

    with use_execution_context(context):
        returncode, stdout, stderr = await execute_command(
            ["ls", "-la"],
            host="remote.example.com",
            username="testuser",
        )

    assert returncode == 0
    assert stdout == "output"
    assert mock_connection_manager.execute_remote.call_count == 1


async def test_execute_command_fails_without_context():
    """Test execute_command fails when no ExecutionContext is set."""
    with pytest.raises(RuntimeError, match="No execution context set"):
        await execute_command(["echo", "test"])


async def test_local_execution_allowed():
    """Test local execution succeeds when allow_local=True."""
    context = ExecutionContext(allow_local=True)

    with use_execution_context(context):
        returncode, stdout, stderr = await execute_command(["echo", "test"])

    assert returncode == 0
    assert isinstance(stdout, str)
    assert "test" in stdout


async def test_local_execution_denied():
    """Test local execution fails when allow_local=False."""
    context = ExecutionContext(allow_local=False)

    with use_execution_context(context):
        with pytest.raises(RuntimeError, match="Local execution not allowed"):
            await execute_command(["echo", "test"])


async def test_remote_execution_with_ssh_default_allowed(mock_connection_manager):
    """Test remote execution succeeds when allow_ssh_default=True."""
    context = ExecutionContext(allow_ssh_default=True)

    with use_execution_context(context):
        returncode, stdout, stderr = await execute_command(
            ["ls", "-la"],
            host="remote.example.com",
        )

    assert returncode == 0
    assert stdout == "output"
    assert mock_connection_manager.execute_remote.call_count == 1


async def test_remote_execution_denied_no_permissions(mock_connection_manager):
    """Test remote execution fails when no SSH permissions are set."""
    context = ExecutionContext(allow_ssh_default=False, ssh_key_path=None)

    with use_execution_context(context):
        with pytest.raises(RuntimeError, match="Remote execution not allowed"):
            await execute_command(["ls", "-la"], host="remote.example.com")

    assert mock_connection_manager.execute_remote.call_count == 0


async def test_remote_execution_with_ssh_key(mock_connection_manager):
    """Test remote execution succeeds with ssh_key_path set."""
    ssh_path = Path("/home/user/.ssh/id_rsa")
    context = ExecutionContext(
        allow_ssh_default=False,
        ssh_key_path=ssh_path,
        ssh_key_user="ubuntu",
    )

    with use_execution_context(context):
        returncode, stdout, stderr = await execute_command(
            ["ls", "-la"],
            host="remote.example.com",
        )

    assert returncode == 0
    assert mock_connection_manager.execute_remote.call_count == 1
