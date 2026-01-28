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
    mock_execute_with_fallback.return_value = (0, "Remote file content", "")

    result = await mcp_client.call_tool("read_file", arguments={"path": "/remote/path/file.txt", "host": "remote.host"})

    assert result.content[0].text == "Remote file content"

    mock_execute_with_fallback.assert_called_once()
    call_kwargs = mock_execute_with_fallback.call_args[1]
    assert call_kwargs["host"] == "remote.host"


async def test_read_file_remote_failure(mock_execute_with_fallback, mcp_client):
    mock_execute_with_fallback.return_value = (1, "", "File not found")

    with pytest.raises(ToolError) as exc_info:
        await mcp_client.call_tool("read_file", arguments={"path": "/remote/path/file.txt", "host": "remote.host"})

    assert "Error running command: command failed with return code 1" in str(exc_info.value)
