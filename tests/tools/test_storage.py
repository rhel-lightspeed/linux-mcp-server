"""Tests for storage tools."""

import os
import sys

from collections.abc import Callable
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from fastmcp.exceptions import ToolError

from linux_mcp_server.tools import storage
from tests import verify_result_structure


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
def mock_storage_execute_command(mock_execute_command_for):
    """Storage-specific execute_command mock using the shared factory."""
    return mock_execute_command_for("linux_mcp_server.tools.storage")


class TestListBlockDevices:
    """Test suite for list_block_devices tool."""

    @pytest.mark.parametrize(
        ("lsblk_output", "expected_content"),
        [
            pytest.param(
                "NAME   SIZE TYPE MOUNTPOINT FSTYPE MODEL\nsda    1TB  disk            \nsda1   512G part /          ext4",
                ["=== Block Devices ===", "sda", "sda1"],
                id="lsblk_success",
            ),
            pytest.param(
                "",
                ["Error: Unable to list block devices"],
                id="lsblk_empty_output",
            ),
        ],
    )
    async def test_list_block_devices_lsblk_success(
        self,
        lsblk_output,
        expected_content,
        mock_storage_execute_command,
        mcp_client,
    ):
        """Test list_block_devices with successful lsblk command."""
        mock_storage_execute_command.return_value = (0, lsblk_output, "")

        result = await mcp_client.call_tool("list_block_devices", {})
        output = verify_result_structure(result)

        # Verify expected content
        for content in expected_content:
            assert content in output

        # Verify lsblk was called with correct arguments
        mock_storage_execute_command.assert_called_once()
        args = mock_storage_execute_command.call_args[0][0]
        assert args[0] == "lsblk"
        assert "-o" in args

    async def test_list_block_devices_command_failure(self, mocker, mcp_client):
        """Test list_block_devices returns error when lsblk fails."""
        mocker.patch(
            "linux_mcp_server.tools.storage.execute_command",
            AsyncMock(return_value=(1, "", "command failed")),
        )

        result = await mcp_client.call_tool("list_block_devices", {})
        output = verify_result_structure(result)

        assert "Error" in output or "Unable" in output

    async def test_list_block_devices_file_not_found(self, mocker, mcp_client):
        """Test list_block_devices when lsblk is not available."""
        mocker.patch("linux_mcp_server.tools.storage.execute_command", side_effect=FileNotFoundError("lsblk not found"))

        result = await mcp_client.call_tool("list_block_devices", {})
        output = verify_result_structure(result)

        assert "Error" in output or "not found" in output

    async def test_list_block_devices_remote_execution(self, mock_storage_execute_command, mcp_client):
        """Test list_block_devices with remote execution."""
        mock_storage_execute_command.return_value = (0, "NAME   SIZE TYPE\nsda    1TB  disk", "")

        result = await mcp_client.call_tool("list_block_devices", {"host": "remote.host.com"})
        output = verify_result_structure(result)

        assert "=== Block Devices ===" in output
        assert "sda" in output
        assert "=== Disk I/O Statistics" not in output

        # Verify execute_command was called with host parameter
        mock_storage_execute_command.assert_called_once()
        call_kwargs = mock_storage_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.host.com"

    async def test_list_block_devices_exception_handling(self, mock_storage_execute_command, mcp_client):
        """Test list_block_devices handles general exceptions."""
        mock_storage_execute_command.side_effect = ValueError("Raised intentionally")

        result = await mcp_client.call_tool("list_block_devices", {})
        output = verify_result_structure(result)
        assert "Error" in output


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListDirectories:
    async def test_list_directories_returns_string_output(self, setup_test_directory):
        """Test that list_directories returns string output."""
        dir_specs = [
            ("alpha", 100, 1000.0),
            ("beta", 200, 2000.0),
            ("gamma", 300, 3000.0),
        ]
        test_path, expected_names = setup_test_directory(dir_specs)

        result = await storage.list_directories.fn(str(test_path), order_by="name")

        assert isinstance(result, str)
        assert "=== Directories in" in result
        for name in expected_names:
            assert name in result

    async def test_list_directories_by_name(self, setup_test_directory):
        """Test that list_directories returns sorted output by name."""
        dir_specs = [
            ("gamma", 300, 3000.0),
            ("alpha", 100, 1000.0),
            ("beta", 200, 2000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        result = await storage.list_directories.fn(str(test_path), order_by="name")

        assert isinstance(result, str)
        # Verify all directories are present
        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result
        # Verify sorted order (alpha should appear before beta, beta before gamma)
        alpha_pos = result.find("alpha")
        beta_pos = result.find("beta")
        gamma_pos = result.find("gamma")
        assert alpha_pos < beta_pos < gamma_pos

    async def test_list_directories_by_size(self, setup_test_directory):
        """Test that list_directories sorts by size."""
        dir_specs = [
            ("small", 100, 1000.0),
            ("large", 300, 3000.0),
            ("medium", 200, 2000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        result = await storage.list_directories.fn(str(test_path), order_by="size")

        assert isinstance(result, str)
        # All directories should be present
        assert "small" in result
        assert "medium" in result
        assert "large" in result

    @pytest.mark.parametrize(
        ("dir_specs", "order_by", "expected_order"),
        [
            pytest.param(
                [("alpha", 100, 1000.0), ("beta", 200, 2000.0), ("gamma", 300, 3000.0)],
                "name",
                ["gamma", "beta", "alpha"],
                id="name_descending",
            ),
            pytest.param(
                [("small", 100, 1000.0), ("medium", 200, 2000.0), ("large", 300, 3000.0)],
                "size",
                ["large", "medium", "small"],
                id="size_descending",
            ),
            pytest.param(
                [("oldest", 100, 1000.0), ("middle", 200, 2000.0), ("newest", 300, 3000.0)],
                "modified",
                ["newest", "middle", "oldest"],
                id="modified_descending",
            ),
        ],
    )
    async def test_list_directories_descending(self, setup_test_directory, dir_specs, order_by, expected_order):
        """Test that list_directories can sort descending by name, size, or modified time."""
        test_path, _ = setup_test_directory(dir_specs)

        result = await storage.list_directories.fn(str(test_path), order_by=order_by, sort="descending")

        assert isinstance(result, str)
        # Verify descending order
        positions = [result.find(name) for name in expected_order]
        assert positions[0] < positions[1] < positions[2]

    async def test_list_directories_with_top_n(self, setup_test_directory):
        """Test that list_directories limits results with top_n."""
        dir_specs = [
            ("alpha", 100, 1000.0),
            ("beta", 200, 2000.0),
            ("gamma", 300, 3000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        result = await storage.list_directories.fn(str(test_path), order_by="name", top_n=2)

        assert isinstance(result, str)
        assert "Total directories: 2" in result

    async def test_list_directories_nonexistent_path(self, tmp_path):
        """Test list_directories with nonexistent path raises ToolError."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(ToolError) as exc_info:
            await storage.list_directories.fn(str(nonexistent))

        assert "Error running command: command failed with return code 1" in str(exc_info.value)

    async def test_list_directories_restricted_path(self, restricted_path):
        """Test list_directories with restricted path raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            await storage.list_directories.fn(str(restricted_path))

        assert "Error running command: command failed with return code 1" in str(exc_info.value)


class TestListDirectoriesRemote:
    """Test list_directories with mocked remote execution."""

    async def test_list_directories_remote(self, mocker):
        """Test list_directories with remote execution."""
        mock_execute = AsyncMock(return_value=(0, "alpha\nbeta\ngamma", ""))
        mocker.patch("linux_mcp_server.tools.storage.execute_command", mock_execute)

        result = await storage.list_directories.fn("/remote/path", host="remote.host")

        assert isinstance(result, str)
        assert "alpha" in result
        assert "beta" in result
        assert "gamma" in result

        # Verify execute_command was called with host
        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["host"] == "remote.host"


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListFiles:
    async def test_list_files_returns_string_output(self, setup_test_files):
        """Test that list_files returns string output."""
        file_specs = [
            ("file1.txt", 100, 1000.0),
            ("file2.txt", 200, 2000.0),
            ("file3.txt", 300, 3000.0),
        ]
        test_path, expected_names = setup_test_files(file_specs)

        result = await storage.list_files.fn(str(test_path), order_by="name")

        assert isinstance(result, str)
        assert "=== Files in" in result
        for name in expected_names:
            assert name in result

    async def test_list_files_by_name(self, setup_test_files):
        """Test that list_files returns sorted output by name."""
        file_specs = [
            ("gamma.txt", 300, 3000.0),
            ("alpha.txt", 100, 1000.0),
            ("beta.txt", 200, 2000.0),
        ]
        test_path, _ = setup_test_files(file_specs)

        result = await storage.list_files.fn(str(test_path), order_by="name")

        assert isinstance(result, str)
        # Verify sorted order
        alpha_pos = result.find("alpha.txt")
        beta_pos = result.find("beta.txt")
        gamma_pos = result.find("gamma.txt")
        assert alpha_pos < beta_pos < gamma_pos

    async def test_list_files_by_size(self, setup_test_files):
        """Test that list_files sorts by size."""
        file_specs = [
            ("small.txt", 100, 1000.0),
            ("large.txt", 300, 3000.0),
            ("medium.txt", 200, 2000.0),
        ]
        test_path, _ = setup_test_files(file_specs)

        result = await storage.list_files.fn(str(test_path), order_by="size")

        assert isinstance(result, str)
        # All files should be present
        assert "small.txt" in result
        assert "medium.txt" in result
        assert "large.txt" in result

    async def test_list_files_descending(self, setup_test_files):
        """Test that list_files can sort descending."""
        file_specs = [
            ("alpha.txt", 100, 1000.0),
            ("beta.txt", 200, 2000.0),
            ("gamma.txt", 300, 3000.0),
        ]
        test_path, _ = setup_test_files(file_specs)

        result = await storage.list_files.fn(str(test_path), order_by="name", sort="descending")

        assert isinstance(result, str)
        # Verify descending order
        gamma_pos = result.find("gamma.txt")
        beta_pos = result.find("beta.txt")
        alpha_pos = result.find("alpha.txt")
        assert gamma_pos < beta_pos < alpha_pos

    async def test_list_files_with_top_n(self, setup_test_files):
        """Test that list_files limits results with top_n."""
        file_specs = [
            ("file1.txt", 100, 1000.0),
            ("file2.txt", 200, 2000.0),
            ("file3.txt", 300, 3000.0),
        ]
        test_path, _ = setup_test_files(file_specs)

        result = await storage.list_files.fn(str(test_path), order_by="name", top_n=2)

        assert isinstance(result, str)
        assert "Total files: 2" in result

    async def test_list_files_nonexistent_path(self, tmp_path):
        """Test list_files with nonexistent path raises ToolError."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(ToolError) as exc_info:
            await storage.list_files.fn(str(nonexistent))

        assert "Error running command: command failed with return code 1" in str(exc_info.value)


class TestListFilesRemote:
    """Test list_files with mocked remote execution."""

    async def test_list_files_remote(self, mocker):
        """Test list_files with remote execution."""
        mock_execute = AsyncMock(return_value=(0, "file1.txt\nfile2.txt\nfile3.txt", ""))
        mocker.patch("linux_mcp_server.tools.storage.execute_command", mock_execute)

        result = await storage.list_files.fn("/remote/path", host="remote.host")

        assert isinstance(result, str)
        assert "file1.txt" in result
        assert "file2.txt" in result
        assert "file3.txt" in result

        # Verify execute_command was called with host
        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["host"] == "remote.host"


class TestReadFile:
    async def test_read_file_success(self, tmp_path):
        """Test reading a file successfully."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = await storage.read_file.fn(str(test_file))

        assert result == "Hello, World!"

    async def test_read_file_nonexistent(self, tmp_path):
        """Test reading a nonexistent file raises ToolError."""
        nonexistent = tmp_path / "nonexistent.txt"

        with pytest.raises(ToolError) as exc_info:
            await storage.read_file.fn(str(nonexistent))

        assert f"Path is not a file: {nonexistent}" == str(exc_info.value)

    async def test_read_file_is_directory(self, tmp_path):
        """Test reading a directory raises ToolError."""
        with pytest.raises(ToolError) as exc_info:
            await storage.read_file.fn(str(tmp_path))

        assert "not a file" in str(exc_info.value)

    async def test_read_file_remote(self, mocker):
        """Test reading a file remotely."""
        mock_execute = AsyncMock(return_value=(0, "Remote file content", ""))
        mocker.patch("linux_mcp_server.tools.storage.execute_command", mock_execute)

        result = await storage.read_file.fn("/remote/path/file.txt", host="remote.host")

        assert result == "Remote file content"

        # Verify execute_command was called with host
        mock_execute.assert_called_once()
        call_kwargs = mock_execute.call_args[1]
        assert call_kwargs["host"] == "remote.host"

    async def test_read_file_remote_failure(self, mocker):
        """Test reading a file remotely with failure."""
        mock_execute = AsyncMock(return_value=(1, "", "File not found"))
        mocker.patch("linux_mcp_server.tools.storage.execute_command", mock_execute)

        with pytest.raises(ToolError) as exc_info:
            await storage.read_file.fn("/remote/path/file.txt", host="remote.host")

        assert "Error running command: command failed with return code 1" in str(exc_info.value)
