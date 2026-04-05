import pytest

from fastmcp.exceptions import ToolError


async def test_read_file_success(tmp_path, mcp_client):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!")

    result = await mcp_client.call_tool("read_file", arguments={"path": str(test_file)})

    assert result.content[0].text == "Hello, World!"


async def test_read_file_nonexistent(tmp_path, mcp_client):
    nonexistent = tmp_path / "nonexistent.txt"

    with pytest.raises(ToolError) as exc_info:
        await mcp_client.call_tool("read_file", arguments={"path": str(nonexistent)})

    assert f"Path is not a file: {nonexistent}" == str(exc_info.value)


async def test_read_file_is_directory(tmp_path, mcp_client):
    with pytest.raises(ToolError) as exc_info:
        await mcp_client.call_tool("read_file", arguments={"path": str(tmp_path)})

    assert "not a file" in str(exc_info.value)


async def test_read_file_remote(mock_execute_with_fallback, mcp_client):
    mock_execute_with_fallback.side_effect = [
        (0, "19", ""),
        (0, "Remote file content", ""),
    ]

    result = await mcp_client.call_tool("read_file", arguments={"path": "/remote/path/file.txt", "host": "remote.host"})

    assert result.content[0].text == "Remote file content"

    assert mock_execute_with_fallback.call_count == 2
    for call in mock_execute_with_fallback.call_args_list:
        assert call[1]["host"] == "remote.host"


async def test_read_file_rejects_large_local_file(tmp_path, mcp_client, mocker):
    mocker.patch("linux_mcp_server.tools.storage.CONFIG.max_file_read_bytes", 8)
    test_file = tmp_path / "big.txt"
    test_file.write_text("0123456789")

    with pytest.raises(ToolError, match="too large"):
        await mcp_client.call_tool("read_file", arguments={"path": str(test_file)})


async def test_read_file_remote_rejects_large_file(mock_execute_with_fallback, mcp_client, mocker):
    mocker.patch("linux_mcp_server.tools.storage.CONFIG.max_file_read_bytes", 8)
    mock_execute_with_fallback.return_value = (0, "10", "")

    with pytest.raises(ToolError, match="too large"):
        await mcp_client.call_tool("read_file", arguments={"path": "/remote/path/file.txt", "host": "remote.host"})


async def test_read_file_remote_command_failure(mock_execute_with_fallback, mcp_client):
    mock_execute_with_fallback.side_effect = [
        (0, "19", ""),
        (1, "", "File not found"),
    ]

    with pytest.raises(ToolError, match="command failed with return code 1"):
        await mcp_client.call_tool("read_file", arguments={"path": "/remote/path/file.txt", "host": "remote.host"})


async def test_read_file_sentinel_rejects_over_limit(tmp_path, mcp_client, mocker):
    mocker.patch("linux_mcp_server.tools.storage.CONFIG.max_file_read_bytes", 8)
    test_file = tmp_path / "sneaky.txt"
    test_file.write_text("012345678")

    mocker.patch("pathlib.Path.stat", return_value=type("stat", (), {"st_size": 7})())

    with pytest.raises(ToolError, match="too large"):
        await mcp_client.call_tool("read_file", arguments={"path": str(test_file)})


async def test_read_file_custom_limit(tmp_path, mcp_client, mocker):
    mocker.patch("linux_mcp_server.tools.storage.CONFIG.max_file_read_bytes", 4096)
    test_file = tmp_path / "small.txt"
    test_file.write_text("OK")

    result = await mcp_client.call_tool("read_file", arguments={"path": str(test_file)})

    assert result.content[0].text == "OK"
