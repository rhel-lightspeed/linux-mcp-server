import pytest

from linux_mcp_server.config import Config
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.connection.ssh import execute_with_fallback
from linux_mcp_server.connection.ssh import get_bin_path
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


async def test_execute_command_local_timeout(mocker):
    """Test local command timeout handling."""
    returncode, stdout, stderr = await execute_command(["sleep", "10"], timeout=1)

    assert returncode == 1
    assert isinstance(stderr, str)
    assert "timed out" in stderr


async def test_execute_command_local_exception(mocker):
    """Test local command exception handling."""
    mocker.patch(
        "asyncio.create_subprocess_exec",
        autospec=True,
        side_effect=Exception("Unexpected error"),
    )

    returncode, stdout, stderr = await execute_command(["/bin/echo", "test"])

    assert returncode == 1
    assert isinstance(stderr, str)
    assert "Unexpected error" in stderr


async def test_execute_with_fallback_primary_succeeds():
    """Test that fallback is not used when primary succeeds."""
    returncode, stdout, stderr = await execute_with_fallback(
        ["echo", "primary"],
        fallback=["echo", "fallback"],
    )

    assert returncode == 0
    assert isinstance(stdout, str)
    assert "primary" in stdout


async def test_execute_with_fallback_uses_fallback():
    """Test that fallback is used when primary fails."""
    returncode, stdout, stderr = await execute_with_fallback(
        ["false"],
        fallback=["echo", "fallback_used"],
    )

    assert returncode == 0
    assert isinstance(stdout, str)
    assert "fallback_used" in stdout


async def test_execute_with_fallback_no_fallback_provided():
    """Test behavior when primary fails and no fallback is provided."""
    returncode, stdout, stderr = await execute_with_fallback(["false"])

    assert returncode == 1


def test_get_bin_path_found():
    """Test get_bin_path finds existing command."""
    path = get_bin_path("echo")

    assert "echo" in path


def test_get_bin_path_not_found():
    """Test get_bin_path raises when command not found."""
    with pytest.raises(FileNotFoundError, match="Unable to find"):
        get_bin_path("nonexistent_command_xyz123")


async def test_get_manager_subprocess_backend(mocker):
    """Test _get_manager initializes subprocess backend when configured."""
    mock_config = mocker.MagicMock(spec=Config)
    mock_config.effective_ssh_backend = "subprocess"
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG", mock_config)

    from linux_mcp_server.connection.ssh import _get_manager

    manager = _get_manager()

    from linux_mcp_server.connection.subprocess_ssh import SSHSubprocessManager

    assert isinstance(manager, SSHSubprocessManager)


async def test_get_manager_asyncssh_backend(mocker):
    """Test _get_manager initializes asyncssh backend when configured."""
    mock_config = mocker.MagicMock(spec=Config)
    mock_config.effective_ssh_backend = "asyncssh"
    mocker.patch("linux_mcp_server.connection.ssh.CONFIG", mock_config)

    from linux_mcp_server.connection.ssh import _get_manager

    manager = _get_manager()

    from linux_mcp_server.connection.asyncssh_backend import SSHAsyncSSHManager

    assert isinstance(manager, SSHAsyncSSHManager)


def test_lazy_import_ssh_connection_manager():
    """Test lazy import of SSHConnectionManager for backwards compatibility."""
    from linux_mcp_server.connection import ssh

    manager_class = ssh.SSHConnectionManager

    assert manager_class is not None


def test_lazy_import_discover_ssh_key():
    """Test lazy import of discover_ssh_key for backwards compatibility."""
    from linux_mcp_server.connection import ssh

    func = ssh.discover_ssh_key

    assert callable(func)


def test_lazy_import_get_remote_bin_path():
    """Test lazy import of get_remote_bin_path for backwards compatibility."""
    from linux_mcp_server.connection import ssh

    func = ssh.get_remote_bin_path

    assert callable(func)


def test_lazy_import_unknown_attribute():
    """Test that accessing unknown attribute raises AttributeError."""
    from linux_mcp_server.connection import ssh

    with pytest.raises(AttributeError, match="has no attribute"):
        _ = ssh.nonexistent_attribute
