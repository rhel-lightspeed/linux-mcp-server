"""Tests for storage tools."""

import os
import re
import sys

from collections.abc import Callable
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from fastmcp.exceptions import ToolError

from linux_mcp_server.tools.storage import OrderBy


@pytest.fixture
def setup_test_directory(tmp_path) -> Callable[[list[tuple[str, int, float]]], tuple[Path, list[str]]]:
    """
    Factory fixture for creating test directories with subdirectories of specific sizes and modification times.

    Returns a function that accepts a list of (name, size, modified_time) tuples and:
    - Creates subdirectories with the specified sizes (by adding a file within each)
    - Sets their modification times
    - Returns the directory path and list of expected directory names
    """

    def _create_directory(dir_specs: list[tuple[str, int, float]]) -> tuple[Path, list[str]]:
        """
        Create a directory structure with specified subdirectories.

        Args:
            dir_specs: List of (name, size, modified_time) tuples

        Returns:
            Tuple of (directory_path, expected_names)
        """
        expected_names = []

        for name, size, modified_time in dir_specs:
            dir_path = tmp_path / name
            dir_path.mkdir()

            # Create a file inside the directory to give it size
            content_file = dir_path / "content.txt"
            content_file.write_text("x" * size)

            # Set modification time on the directory itself
            os.utime(dir_path, (modified_time, modified_time))

            expected_names.append(name)

        return tmp_path, expected_names

    return _create_directory


@pytest.fixture
def setup_test_files(tmp_path) -> Callable[[list[tuple[str, int, float]]], tuple[Path, list[str]]]:
    """
    Factory fixture for creating test files of specific sizes and modification times.

    Returns a function that accepts a list of (name, size, modified_time) tuples and:
    - Creates files with the specified sizes
    - Sets their modification times
    - Returns the directory path and list of expected file names
    """

    def _create_files(file_specs: list[tuple[str, int, float]]) -> tuple[Path, list[str]]:
        """
        Create files with specified attributes.

        Args:
            file_specs: List of (name, size, modified_time) tuples

        Returns:
            Tuple of (directory_path, expected_names)
        """
        expected_names = []

        for name, size, modified_time in file_specs:
            content_file = tmp_path / name
            content_file.write_text("x" * size)

            # Set modification time on the file itself
            os.utime(content_file, (modified_time, modified_time))

            expected_names.append(name)

        return tmp_path, expected_names

    return _create_files


@pytest.fixture
def restricted_path(tmp_path):
    restricted_path = tmp_path / "restricted"
    restricted_path.mkdir()
    restricted_path.chmod(0o000)

    yield restricted_path

    restricted_path.chmod(0o755)


@pytest.fixture
def mock_execute_with_fallback(mock_execute_with_fallback_for):
    """Storage-specific execute_with_fallback mock using the shared factory."""
    return mock_execute_with_fallback_for("linux_mcp_server.commands")


class TestListBlockDevices:
    """Test suite for list_block_devices tool."""

    @pytest.mark.parametrize(
        ("lsblk_output", "expected_content"),
        [
            pytest.param(
                '{"blockdevices":[{"name":"sda","size":"1TB","type":"disk","mountpoint":null,"fstype":null,"model":null,"children":[{"name":"sda1","size":"512G","type":"part","mountpoint":"/","fstype":"ext4","module":null}]}]}',
                ["=== Block Devices ===", "sda", "sda1"],
                id="lsblk_success",
            ),
        ],
    )
    async def test_list_block_devices_lsblk_success(
        self,
        lsblk_output,
        expected_content,
        mock_execute_with_fallback,
        mcp_client,
    ):
        """Test list_block_devices with successful lsblk command."""
        mock_execute_with_fallback.return_value = (0, lsblk_output, "")

        result = await mcp_client.call_tool("list_block_devices", {})
        result = result.structured_content
        first_device = result["blockdevices"][0]

        assert first_device["name"] == "sda"
        assert first_device["children"][0]["name"] == "sda1"

        # Verify lsblk was called with correct arguments
        mock_execute_with_fallback.assert_called_once()
        args = mock_execute_with_fallback.call_args[0][0]
        assert args[0] == "lsblk"
        assert "-o" in args

    @pytest.mark.parametrize(
        "side_effect, expected_match",
        (
            (
                AsyncMock(return_value=(1, "", "command failed")),
                re.compile(r"Unable to list block devices", flags=re.I),
            ),
            (FileNotFoundError("lsblk not found"), re.compile("not found", flags=re.I)),
            (ValueError("Raised intentionally"), re.compile(r"error.*raised intentionally", flags=re.I)),
            (
                AsyncMock(return_value=(1, "", "Unable to list block devices")),
                re.compile("Unable to list block devices"),
            ),
        ),
    )
    async def test_list_block_devices_command_failure(self, side_effect, expected_match, mocker, mcp_client):
        """Test list_block_devices failure."""
        mocker.patch(
            "linux_mcp_server.commands.execute_with_fallback",
            side_effect=side_effect,
            autospec=True,
        )

        with pytest.raises(ToolError, match=expected_match):
            await mcp_client.call_tool("list_block_devices", {})

    async def test_list_block_devices_remote_execution(self, mock_execute_with_fallback, mcp_client):
        """Test list_block_devices with remote execution."""
        mock_execute_with_fallback.return_value = (0, "NAME   SIZE TYPE\nsda    1TB  disk", "")
        mock_execute_with_fallback.return_value = (
            0,
            '{"blockdevices":[{"name":"sda","size":"1TB","type":"disk","mountpoint":null,"fstype":null,"model":null,"children":[]}]}',
            "",
        )

        result = await mcp_client.call_tool("list_block_devices", {"host": "remote.host.com"})
        device_names = [item["name"] for item in result.structured_content["blockdevices"]]

        assert "sda" in device_names

        # Verify execute_with_fallback was called with host
        mock_execute_with_fallback.assert_called_once()
        call_kwargs = mock_execute_with_fallback.call_args[1]
        assert call_kwargs["host"] == "remote.host.com"


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListDirectories:
    async def test_list_directories(self, setup_test_directory, mcp_client):
        dir_specs = [
            ("alpha", 100, 1000.0),
            ("beta", 200, 2000.0),
            ("gamma", 300, 3000.0),
        ]
        test_path, expected_names = setup_test_directory(dir_specs)

        result = await mcp_client.call_tool("list_directories", arguments={"path": str(test_path), "order_by": "name"})
        content = result.structured_content
        names = [dir["name"] for dir in content["dirs"]]
        positions = {dir["name"]: id for id, dir in enumerate(content["dirs"])}

        assert names == expected_names, "Did not find all expected names"

        # Verify sorted order (alpha should appear before beta, beta before gamma)
        alpha_pos = positions["alpha"]
        beta_pos = positions["beta"]
        gamma_pos = positions["gamma"]
        assert alpha_pos < beta_pos < gamma_pos

    async def test_list_directories_by_size(self, setup_test_directory, mcp_client):
        """Test that list_directories sorts by size."""
        dir_specs = [
            ("small", 100, 1000.0),
            ("large", 300, 3000.0),
            ("medium", 200, 2000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        result = await mcp_client.call_tool("list_directories", arguments={"path": str(test_path), "order_by": "size"})
        content = result.structured_content
        names = [dir["name"] for dir in content["dirs"]]

        # All directories should be present
        assert content["total"] == len(dir_specs)
        assert names == ["small", "medium", "large"]

    @pytest.mark.parametrize(
        ("dir_specs", "order_by", "expected_order"),
        [
            pytest.param(
                [("alpha", 100, 1000.0), ("beta", 200, 2000.0), ("gamma", 300, 3000.0)],
                OrderBy.NAME,
                ["gamma", "beta", "alpha"],
                id="name_descending",
            ),
            pytest.param(
                [("small", 100, 1000.0), ("medium", 200, 2000.0), ("large", 300, 3000.0)],
                OrderBy.SIZE,
                ["large", "medium", "small"],
                id="size_descending",
            ),
            pytest.param(
                [("oldest", 100, 1000.0), ("middle", 200, 2000.0), ("newest", 300, 3000.0)],
                OrderBy.MODIFIED,
                ["newest", "middle", "oldest"],
                id="modified_descending",
            ),
        ],
    )
    async def test_list_directories_descending(
        self, setup_test_directory, dir_specs, order_by, expected_order, mcp_client
    ):
        """Test that list_directories can sort descending by name, size, or modified time."""
        test_path, _ = setup_test_directory(dir_specs)

        result = await mcp_client.call_tool(
            "list_directories", arguments={"path": str(test_path), "order_by": order_by, "sort": "descending"}
        )
        content = result.structured_content
        names = [dir["name"] for dir in content["dirs"]]
        positions = {dir["name"]: id for id, dir in enumerate(content["dirs"])}

        # Verify descending order
        assert names == expected_order
        assert positions[expected_order[0]] < positions[expected_order[1]] < positions[expected_order[2]]

    @pytest.mark.parametrize("order", ("size", "modified", "name"))
    async def test_list_directories_with_top_n(self, setup_test_directory, mcp_client, order):
        """Test that list_directories limits results with top_n."""
        dir_specs = [
            ("alpha", 100, 1000.0),
            ("beta", 200, 2000.0),
            ("gamma", 300, 3000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        result = await mcp_client.call_tool(
            "list_directories", arguments={"path": str(test_path), "order_by": order, "top_n": 2}
        )

        assert result.structured_content["total"] == 2

    async def test_list_directories_nonexistent_path(self, tmp_path, mcp_client):
        """Test list_directories with nonexistent path raises ToolError."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(ToolError, match="Error running command: command failed with return code 1"):
            await mcp_client.call_tool("list_directories", arguments={"path": str(nonexistent)})

    async def test_list_directories_restricted_path(self, restricted_path, mcp_client):
        """Test list_directories with restricted path raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            await mcp_client.call_tool("list_directories", arguments={"path": str(restricted_path)})

        assert "Error running command: command failed with return code 1" in str(exc_info.value)


class TestListDirectoriesRemote:
    """Test list_directories with mocked remote execution."""

    async def test_list_directories_remote(self, mock_execute_with_fallback, mcp_client):
        """Test list_directories with remote execution."""
        mock_execute_with_fallback.return_value = (0, "alpha\nbeta\ngamma", "")

        result = await mcp_client.call_tool(
            "list_directories", arguments={"path": "/remote/path", "host": "remote.host"}
        )
        result_text = result.content[0].text

        assert "alpha" in result_text
        assert "beta" in result_text
        assert "gamma" in result_text

        # Verify execute_with_fallback was called with host
        mock_execute_with_fallback.assert_called_once()
        call_kwargs = mock_execute_with_fallback.call_args[1]
        assert call_kwargs["host"] == "remote.host"


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListFiles:
    async def test_list_files_returns_string_output(self, setup_test_files, mcp_client):
        """Test that list_files returns string output."""
        file_specs = [
            ("file1.txt", 100, 1000.0),
            ("file2.txt", 200, 2000.0),
            ("file3.txt", 300, 3000.0),
        ]
        test_path, expected_names = setup_test_files(file_specs)

        result = await mcp_client.call_tool("list_files", arguments={"path": str(test_path), "order_by": "name"})
        result_text = result.content[0].text

        assert "=== Files in" in result_text
        assert all(name in result_text for name in expected_names)

    async def test_list_files_by_name(self, setup_test_files, mcp_client):
        """Test that list_files returns sorted output by name."""
        file_specs = [
            ("gamma.txt", 300, 3000.0),
            ("alpha.txt", 100, 1000.0),
            ("beta.txt", 200, 2000.0),
        ]
        test_path, _ = setup_test_files(file_specs)

        result = await mcp_client.call_tool("list_files", arguments={"path": str(test_path), "order_by": "name"})
        result_text = result.content[0].text

        # Verify sorted order
        alpha_pos = result_text.find("alpha.txt")
        beta_pos = result_text.find("beta.txt")
        gamma_pos = result_text.find("gamma.txt")
        assert alpha_pos < beta_pos < gamma_pos

    async def test_list_files_by_size(self, setup_test_files, mcp_client):
        """Test that list_files sorts by size."""
        file_specs = [
            ("small.txt", 100, 1000.0),
            ("large.txt", 300, 3000.0),
            ("medium.txt", 200, 2000.0),
        ]
        test_path, _ = setup_test_files(file_specs)
        result = await mcp_client.call_tool("list_files", arguments={"path": str(test_path), "order_by": "size"})
        result_text = result.content[0].text

        # All files should be present
        assert "small.txt" in result_text
        assert "medium.txt" in result_text
        assert "large.txt" in result_text

    async def test_list_files_descending(self, setup_test_files, mcp_client):
        """Test that list_files can sort descending."""
        file_specs = [
            ("alpha.txt", 100, 1000.0),
            ("beta.txt", 200, 2000.0),
            ("gamma.txt", 300, 3000.0),
        ]
        test_path, _ = setup_test_files(file_specs)
        result = await mcp_client.call_tool("list_files", arguments={"path": str(test_path), "sort": "descending"})
        result_text = result.content[0].text

        # Verify descending order
        gamma_pos = result_text.find("gamma.txt")
        beta_pos = result_text.find("beta.txt")
        alpha_pos = result_text.find("alpha.txt")
        assert gamma_pos < beta_pos < alpha_pos

    @pytest.mark.parametrize("order", ("size", "modified", "name"))
    async def test_list_files_with_top_n(self, setup_test_files, mcp_client, order):
        """Test that list_files limits results with top_n."""
        file_specs = [
            ("file1.txt", 100, 1000.0),
            ("file2.txt", 200, 2000.0),
            ("file3.txt", 300, 3000.0),
        ]
        test_path, _ = setup_test_files(file_specs)
        result = await mcp_client.call_tool(
            "list_files", arguments={"path": str(test_path), "order_by": order, "top_n": 2}
        )

        assert "Total files: 2" in result.content[0].text

    async def test_list_files_nonexistent_path(self, tmp_path, mcp_client):
        """Test list_files with nonexistent path raises ToolError."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(ToolError) as exc_info:
            await mcp_client.call_tool("list_files", arguments={"path": str(nonexistent)})

        assert "Error running command: command failed with return code 1" in str(exc_info.value)


class TestListFilesRemote:
    """Test list_files with mocked remote execution."""

    async def test_list_files_remote(self, mock_execute_with_fallback, mcp_client):
        """Test list_files with remote execution."""
        mock_execute_with_fallback.return_value = (0, "file1.txt\nfile2.txt\nfile3.txt", "")

        result = await mcp_client.call_tool("list_files", arguments={"path": "/remote/path", "host": "remote.host"})

        assert all(f"file{n}.txt" in result.content[0].text for n in range(1, 4))

        # Verify execute_with_fallback was called with host
        mock_execute_with_fallback.assert_called_once()
        call_kwargs = mock_execute_with_fallback.call_args[1]
        assert call_kwargs["host"] == "remote.host"


class TestPathValidation:
    """Test path validation for storage tools."""

    @pytest.mark.parametrize(
        ("path", "expected_error"),
        [
            pytest.param("/path/with\nnewline", "invalid characters", id="newline_injection"),
            pytest.param("/path/with\x00null", "invalid characters", id="null_byte_injection"),
        ],
    )
    async def test_path_validation_rejects_injection_characters(self, path, expected_error, mcp_client):
        """Test that storage tools reject paths with injection characters."""
        with pytest.raises(ToolError, match=expected_error):
            await mcp_client.call_tool("read_file", arguments={"path": path})


class TestReadFile:
    async def test_read_file_success(self, tmp_path, mcp_client):
        """Test reading a file successfully."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = await mcp_client.call_tool("read_file", arguments={"path": str(test_file)})

        assert result.content[0].text == "Hello, World!"

    async def test_read_file_nonexistent(self, tmp_path, mcp_client):
        """Test reading a nonexistent file raises ToolError."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(ToolError) as exc_info:
            await mcp_client.call_tool("read_file", arguments={"path": str(nonexistent)})

        assert f"Path is not a file: {nonexistent}" == str(exc_info.value)

    async def test_read_file_is_directory(self, tmp_path, mcp_client):
        """Test reading a directory raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            await mcp_client.call_tool("read_file", arguments={"path": str(tmp_path)})

        assert "not a file" in str(exc_info.value)

    async def test_read_file_remote(self, mock_execute_with_fallback, mcp_client):
        """Test reading a file remotely."""
        mock_execute_with_fallback.return_value = (0, "Remote file content", "")

        result = await mcp_client.call_tool(
            "read_file", arguments={"path": "/remote/path/file.txt", "host": "remote.host"}
        )

        assert result.content[0].text == "Remote file content"

        # Verify execute_with_fallback was called with host
        mock_execute_with_fallback.assert_called_once()
        call_kwargs = mock_execute_with_fallback.call_args[1]
        assert call_kwargs["host"] == "remote.host"

    async def test_read_file_remote_failure(self, mock_execute_with_fallback, mcp_client):
        """Test reading a file remotely with failure."""
        mock_execute_with_fallback.return_value = (1, "", "File not found")

        with pytest.raises(ToolError) as exc_info:
            await mcp_client.call_tool("read_file", arguments={"path": "/remote/path/file.txt", "host": "remote.host"})

        assert "Error running command: command failed with return code 1" in str(exc_info.value)
