# Copyright Red Hat
import json
import os
import pytest
from utils.shell import shell


@pytest.mark.parametrize(
    "mcp_session",
    [
        {
            "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/boot.log,/tmp/existing_file.txt,/tmp/nonexisting_file.txt"
        }
    ],
    indirect=True,
)
async def test_read_existing_log_file(mcp_session):
    """
    Verify the response contains the last 5 lines of the file.
    Happy path test case.
    """
    file_content = ["hello\n", "world\n", "this\n", "is\n", "a\n", "test\n"]
    with open("/tmp/existing_file.txt", "w", encoding="utf-8") as f:
        f.writelines(file_content)
    try:
        response = await mcp_session.call_tool(
            "read_log_file", arguments={"log_path": "/tmp/existing_file.txt", "lines": 5}
        )
        assert response is not None
        data = json.loads(response.content[0].text)

        # Check that the response contains the last 5 lines of the file
        entries = data.get("entries", [])
        for line in file_content[1:]:
            assert line.strip() in entries

        # Check that the response contains the file path
        assert data.get("path") == "/tmp/existing_file.txt"
    finally:
        try:
            os.remove("/tmp/existing_file.txt")
        except FileNotFoundError:
            pass


@pytest.mark.parametrize(
    "mcp_session",
    [
        {
            "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/boot.log,/tmp/existing_file.txt,/tmp/nonexisting_file.txt"
        }
    ],
    indirect=True,
)
async def test_read_non_existing_log_file(mcp_session):
    """
    Verify the response contains the error message when the file does not exist.
    The file is present inside the allowed list of paths, but does not exist.
    """
    response = await mcp_session.call_tool(
        "read_log_file", arguments={"log_path": "/tmp/nonexisting_file.txt", "lines": 5}
    )
    assert response is not None
    assert "Log file not found: /tmp/nonexisting_file.txt" in response.content[0].text


@pytest.mark.parametrize(
    "mcp_session",
    [
        {
            "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/boot.log,/tmp/existing_file.txt,/tmp/nonexisting_file.txt"
        }
    ],
    indirect=True,
)
async def test_read_not_allowed_log_file(mcp_session):
    """
    Verify the response contains the error message when the file is not allowed.
    The file is not present inside the allowed list of paths.
    """
    response = await mcp_session.call_tool(
        "read_log_file", arguments={"log_path": "/tmp/not_allowed_file.txt", "lines": 5}
    )
    assert response is not None
    assert (
        "Access to log file '/tmp/not_allowed_file.txt' is not allowed."
        in response.content[0].text
    )


@pytest.mark.parametrize(
    "mcp_session",
    [
        {
            "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/boot.log,/tmp/existing_file.txt,/tmp/nonexisting_file.txt"
        }
    ],
    indirect=True,
)
async def test_read_log_file_empty_argument(mcp_session):
    """
    Verify the response contains the error message when the tool is called with empty arguments.
    """
    response = await mcp_session.call_tool("read_log_file", arguments={})
    assert response is not None
    assert "1 validation error for call[read_log_file]" in response.content[0].text
    assert "Missing required argument" in response.content[0].text


@pytest.mark.parametrize(
    "mcp_session",
    [
        {
            "LINUX_MCP_ALLOWED_LOG_PATHS": "/var/log/boot.log,/tmp/existing_file.txt,/tmp/nonexisting_file.txt"
        }
    ],
    indirect=True,
)
@pytest.mark.skip(
    reason="""
    This test case require a restricted file a user cannot read. If this code is executed as a root, then it is hard to create a restricted file.
    If this code is executed as a non-root user, then we need to create a file as a different user. This is not ideal for local testing.
    Ideally we need to run this server tool on a remote server.
    """
)
async def test_read_unauthorized_log_file(mcp_session):
    """
    Verify the response contains the error message when the file is not authorized.
    The file is present inside the allowed list of paths, but the user does not have permission to read it.
    """
    response = await mcp_session.call_tool(
        "read_log_file", arguments={"log_path": "/var/log/boot.log", "lines": 5}
    )
    assert response is not None
    assert (
        "Permission denied reading log file: /var/log/boot.log"
        in response.content[0].text
    )
    # TODO Finish the test case, think about multihost testing for the MCP
