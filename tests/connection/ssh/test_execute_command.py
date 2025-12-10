from linux_mcp_server.connection.ssh import execute_command


async def test_execute_command_local_success():
    """Test local command execution success."""
    returncode, stdout, stderr = await execute_command(["echo", "hello"])

    assert returncode == 0
    assert "hello" in stdout
    assert stderr == ""


async def test_execute_command_local_failure():
    """Test local command execution failure."""
    returncode, stdout, stderr = await execute_command(["false"])

    assert returncode != 0


async def test_execute_command_local_with_stderr():
    """Test local command that produces stderr output."""
    returncode, stdout, stderr = await execute_command(["bash", "-c", "echo error >&2"])

    assert "error" in stderr


async def test_execute_command_remote_routes_to_ssh(mocker):
    """Test that remote execution routes through SSH."""
    mock_manager = mocker.AsyncMock()
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


async def test_execute_command_remote_requires_host():
    """Test that username without host uses local execution."""
    # Should execute locally, not fail
    returncode, stdout, stderr = await execute_command(["echo", "test"], username="someuser")
    assert returncode == 0
