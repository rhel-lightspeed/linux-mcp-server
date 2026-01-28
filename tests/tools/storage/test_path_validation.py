import pytest

from fastmcp.exceptions import ToolError


@pytest.mark.parametrize(
    ("path", "expected_error"),
    [
        pytest.param("/path/with\nnewline", "invalid characters", id="newline_injection"),
        pytest.param("/path/with\x00null", "invalid characters", id="null_byte_injection"),
    ],
)
async def test_path_validation_rejects_injection_characters(path, expected_error, mcp_client):
    with pytest.raises(ToolError, match=expected_error):
        await mcp_client.call_tool("read_file", arguments={"path": path})
