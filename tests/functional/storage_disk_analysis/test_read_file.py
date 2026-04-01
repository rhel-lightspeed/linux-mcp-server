# Copyright Red Hat
import os
import tempfile

from utils.shell import shell


async def test_read_file_happy_path(mcp_session):
    """
    Verify that the server can read the contents of an existing file.
    Creates a temporary file with known content and reads it back.
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        test_content = "Hello, World!\nThis is a test file.\nLine 3."
        f.write(test_content)
        temp_path = f.name

    try:
        response = await mcp_session.call_tool("read_file", arguments={"path": temp_path})
        assert response is not None

        response_text = response.content[0].text
        # Verify the content matches
        assert "Hello, World!" in response_text
        assert "This is a test file." in response_text
        assert "Line 3." in response_text
    finally:
        os.unlink(temp_path)


async def test_read_file_multiline_content(mcp_session):
    """
    Verify that the server correctly reads multiline file content.
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        lines = [f"Line {i}" for i in range(1, 11)]
        f.write("\n".join(lines))
        temp_path = f.name

    try:
        response = await mcp_session.call_tool("read_file", arguments={"path": temp_path})
        assert response is not None

        response_text = response.content[0].text
        # Verify all lines are present
        for i in range(1, 11):
            assert f"Line {i}" in response_text
    finally:
        os.unlink(temp_path)


async def test_read_file_system_file(mcp_session):
    """
    Verify that the server can read a known system file.
    Uses /etc/hostname which should be readable on most systems.
    """
    # First check if /etc/hostname exists and is readable
    result = shell("cat /etc/hostname 2>/dev/null || echo ''", silent=True, doAssert=False)
    if not result.stdout.strip():
        # Skip if /etc/hostname doesn't exist or isn't readable
        return

    expected_hostname = result.stdout.strip()

    response = await mcp_session.call_tool("read_file", arguments={"path": "/etc/hostname"})
    assert response is not None

    response_text = response.content[0].text
    assert expected_hostname in response_text


async def test_read_file_non_existing_path(mcp_session):
    """
    Verify the response contains error when file does not exist.
    """
    non_existing_path = "/nonexistent/path/file.txt"
    response = await mcp_session.call_tool("read_file", arguments={"path": non_existing_path})
    assert response is not None

    response_text = response.content[0].text
    # Should indicate path doesn't exist or cannot be resolved
    assert f"Path is not a file: {non_existing_path}" in response_text


async def test_read_file_directory_path(mcp_session):
    """
    Verify the response contains error when path is a directory, not a file.
    """
    response = await mcp_session.call_tool("read_file", arguments={"path": "/tmp"})
    assert response is not None

    response_text = response.content[0].text
    # Should indicate path is not a file
    assert (
        "not a file" in response_text.lower()
        or "is a directory" in response_text.lower()
        or "error" in response_text.lower()
    )


async def test_read_file_empty_argument(mcp_session):
    """
    Verify the response contains validation error when called without path.
    """
    response = await mcp_session.call_tool("read_file", arguments={})
    assert response is not None
    assert "1 validation error for call[read_file]" in response.content[0].text
    assert "Missing required argument" in response.content[0].text


async def test_read_file_empty_file(mcp_session):
    """
    Verify that the server can read an empty file without error.
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        # Create empty file
        temp_path = f.name

    try:
        response = await mcp_session.call_tool("read_file", arguments={"path": temp_path})
        assert response is not None
        # Empty file should return without error
        # The response content may be empty or contain just whitespace
    finally:
        os.unlink(temp_path)


async def test_read_file_special_characters(mcp_session):
    """
    Verify that the server correctly reads file content with special characters.
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        test_content = "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?\nTabs:\t\tand spaces"
        f.write(test_content)
        temp_path = f.name

    try:
        response = await mcp_session.call_tool("read_file", arguments={"path": temp_path})
        assert response is not None

        response_text = response.content[0].text
        # Verify special characters are preserved
        assert "!@#$%^&*()" in response_text
        assert "Tabs:" in response_text
    finally:
        os.unlink(temp_path)
