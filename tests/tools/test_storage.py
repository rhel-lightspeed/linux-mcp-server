"""Tests for storage tools."""

import os
import sys

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from linux_mcp_server.server import mcp
from linux_mcp_server.tools.storage import DirectoryEntry


@pytest.fixture
def setup_test_directory(tmp_path) -> Callable[[list[tuple[str, int, float]]], tuple[Path, list[DirectoryEntry]]]:
    """
    Factory fixture for creating test directories with subdirectories of specific sizes and modification times.

    Returns a function that accepts a list of (name, size, modified_time) tuples and:
    - Creates subdirectories with the specified sizes (by adding a file within each)
    - Sets their modification times
    - Returns the directory path and list of expected DirectoryEntry objects
    """

    def _create_directory(dir_specs: list[tuple[str, int, float]]) -> tuple[Path, list[DirectoryEntry]]:
        """
        Create a directory structure with specified subdirectories.

        Args:
            dir_specs: List of (name, size, modified_time) tuples

        Returns:
            Tuple of (directory_path, expected_entries)
        """
        expected_entries = []

        for name, size, modified_time in dir_specs:
            dir_path = tmp_path / name
            dir_path.mkdir()

            # Create a file inside the directory to give it size
            if size > 0:
                content_file = dir_path / "content.txt"
                content_file.write_text("x" * size)

            # Set modification time on the directory itself
            os.utime(dir_path, (modified_time, modified_time))

            expected_entries.append(DirectoryEntry(name=name, size=size, modified=modified_time))

        return tmp_path, expected_entries

    return _create_directory


@pytest.fixture
def restricted_path(tmp_path):
    restricted_path = tmp_path / "restricted"
    restricted_path.mkdir()
    restricted_path.chmod(0o000)

    yield restricted_path

    restricted_path.chmod(0o755)


class TestListBlockDevices:
    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_block_devices_lsblk_success(self, mock_execute_command):
        """Test list_block_devices with successful lsblk command."""
        mock_execute_command.return_value = (
            0,
            "NAME   SIZE TYPE MOUNTPOINT FSTYPE MODEL\nsda    1TB  disk            \nsda1   512G part /          ext4",
            "",
        )

        result = await mcp.call_tool("list_block_devices", {})

        # Verify result structure
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "=== Block Devices ===" in output
        assert "sda" in output
        assert "sda1" in output

        # Verify lsblk was called with correct arguments
        mock_execute_command.assert_called_once()
        args = mock_execute_command.call_args[0][0]
        assert args[0] == "lsblk"
        assert "-o" in args

    @patch("linux_mcp_server.tools.storage.psutil.disk_io_counters")
    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_block_devices_with_disk_io_stats(self, mock_execute_command, mock_disk_io):
        """Test list_block_devices includes disk I/O statistics for local execution."""
        mock_execute_command.return_value = (
            0,
            "NAME   SIZE TYPE MOUNTPOINT\nsda    1TB  disk",
            "",
        )

        # Create mock disk I/O stats
        mock_stats = MagicMock()
        mock_stats.read_bytes = 1024 * 1024 * 1024  # 1 GB
        mock_stats.write_bytes = 512 * 1024 * 1024  # 512 MB
        mock_stats.read_count = 1000
        mock_stats.write_count = 500

        mock_disk_io.return_value = {"sda": mock_stats}

        result = await mcp.call_tool("list_block_devices", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "=== Disk I/O Statistics (per disk) ===" in output
        assert "sda:" in output
        assert "Read:" in output
        assert "Write:" in output
        assert "Read Count: 1000" in output
        assert "Write Count: 500" in output

    @patch("linux_mcp_server.tools.storage.psutil.disk_partitions")
    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_block_devices_lsblk_fallback(self, mock_execute_command, mock_partitions):
        """Test list_block_devices falls back to psutil when lsblk fails."""
        # lsblk returns non-zero
        mock_execute_command.return_value = (1, "", "command failed")

        # Mock partition data
        mock_partition = MagicMock()
        mock_partition.device = "/dev/sda1"
        mock_partition.mountpoint = "/"
        mock_partition.fstype = "ext4"
        mock_partition.opts = "rw,relatime"

        mock_partitions.return_value = [mock_partition]

        result = await mcp.call_tool("list_block_devices", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "=== Block Devices (fallback) ===" in output
        assert "/dev/sda1" in output
        assert "Mountpoint: /" in output
        assert "Filesystem: ext4" in output

    @patch("linux_mcp_server.tools.storage.psutil.disk_partitions")
    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_block_devices_file_not_found(self, mock_execute_command, mock_partitions):
        """Test list_block_devices when lsblk is not available."""
        # lsblk not found
        mock_execute_command.side_effect = FileNotFoundError("lsblk not found")

        # Mock partition data
        mock_partition = MagicMock()
        mock_partition.device = "/dev/nvme0n1p1"
        mock_partition.mountpoint = "/boot"
        mock_partition.fstype = "vfat"
        mock_partition.opts = "rw"

        mock_partitions.return_value = [mock_partition]

        result = await mcp.call_tool("list_block_devices", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "=== Block Devices ===" in output
        assert "/dev/nvme0n1p1" in output
        assert "Mountpoint: /boot" in output

    @patch("linux_mcp_server.tools.storage.psutil.disk_io_counters")
    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_block_devices_remote_execution(self, mock_execute_command, mock_disk_io):
        """Test list_block_devices with remote execution (no disk I/O stats)."""
        mock_execute_command.return_value = (
            0,
            "NAME   SIZE TYPE\nsda    1TB  disk",
            "",
        )

        # Mock disk I/O to ensure it's not called or used
        mock_stats = MagicMock()
        mock_stats.read_bytes = 1024
        mock_disk_io.return_value = {"sda": mock_stats}

        result = await mcp.call_tool("list_block_devices", {"host": "remote.host.com", "username": "testuser"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        # Should NOT include disk I/O stats for remote execution
        assert "=== Disk I/O Statistics" not in output
        assert "=== Block Devices ===" in output

        # Verify execute_command was called with host/username
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.host.com"
        assert call_kwargs["username"] == "testuser"

    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_block_devices_exception_handling(self, mock_execute_command):
        """Test list_block_devices handles general exceptions."""
        mock_execute_command.side_effect = Exception("Unexpected error")

        result = await mcp.call_tool("list_block_devices", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Error listing block devices:" in output
        assert "Unexpected error" in output


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListDirectories:
    async def test_list_directories_returns_structured_output(self, setup_test_directory):
        """Test that list_directories returns structured output."""
        file_specs = [
            ("alpha", 100, 1000.0),
            ("beta", 200, 2000.0),
            ("gamma", 300, 3000.0),
        ]
        test_path, _ = setup_test_directory(file_specs)

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": "name"})

        # Verify the entire result structure
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        directories = list[DirectoryEntry](result[1]["result"])
        assert directories is not None

    async def test_list_directories_by_name(self, setup_test_directory):
        """Test that list_directories returns structured output sorted by name."""
        dir_specs = [
            ("alpha", 100, 1000.0),
            ("beta", 200, 2000.0),
            ("gamma", 300, 3000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        # When ordering by name, only the name field is populated
        expected_entries = [
            DirectoryEntry(name="alpha", size=0, modified=0.0),
            DirectoryEntry(name="beta", size=0, modified=0.0),
            DirectoryEntry(name="gamma", size=0, modified=0.0),
        ]

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": "name"})

        # Verify the structured output
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == expected_entries

    async def test_list_directories_by_size(self, setup_test_directory):
        """Test that list_directories returns structured output sorted by size."""
        dir_specs = [
            ("small", 100, 1000.0),
            ("large", 300, 3000.0),
            ("medium", 200, 2000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        expected_entries = [
            DirectoryEntry(name="small", size=100, modified=0.0),
            DirectoryEntry(name="medium", size=200, modified=0.0),
            DirectoryEntry(name="large", size=300, modified=0.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "size", "sort": "ascending"}
        )

        # Verify the structured output - should be sorted by size (ascending)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == expected_entries

    async def test_list_directories_by_modified(self, setup_test_directory):
        """Test that list_directories returns structured output sorted by modification time."""
        dir_specs = [
            ("newest", 100, 3000.0),
            ("oldest", 100, 1000.0),
            ("middle", 100, 2000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        # When ordering by modified, only name and modified fields are populated
        expected_entries = [
            DirectoryEntry(name="oldest", size=0, modified=1000.0),
            DirectoryEntry(name="middle", size=0, modified=2000.0),
            DirectoryEntry(name="newest", size=0, modified=3000.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "modified", "sort": "ascending"}
        )

        # Verify the structured output - should be sorted by modification time (ascending)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == expected_entries

    async def test_list_directories_by_name_with_top_n(self, setup_test_directory):
        """Test that list_directories returns structured output sorted by name with top_n limit."""
        dir_specs = [
            ("alpha", 100, 1000.0),
            ("beta", 200, 2000.0),
            ("gamma", 300, 3000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        # When ordering by name, only name field is populated
        expected_entries = [
            DirectoryEntry(name="alpha", size=0, modified=0.0),
            DirectoryEntry(name="beta", size=0, modified=0.0),
        ]

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": "name", "top_n": 2})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == expected_entries

    async def test_list_directories_by_name_descending(self, setup_test_directory):
        """Test that list_directories returns structured output sorted by name in descending order."""
        dir_specs = [
            ("alpha", 100, 1000.0),
            ("beta", 200, 2000.0),
            ("gamma", 300, 3000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        expected_entries = [
            DirectoryEntry(name="gamma", size=0, modified=0.0),
            DirectoryEntry(name="beta", size=0, modified=0.0),
            DirectoryEntry(name="alpha", size=0, modified=0.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "name", "sort": "descending"}
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == expected_entries

    async def test_list_directories_by_size_descending(self, setup_test_directory):
        """Test that list_directories returns structured output sorted by size in descending order."""
        dir_specs = [
            ("small", 100, 1000.0),
            ("large", 300, 3000.0),
            ("medium", 200, 2000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        expected_entries = [
            DirectoryEntry(name="large", size=300, modified=0.0),
            DirectoryEntry(name="medium", size=200, modified=0.0),
            DirectoryEntry(name="small", size=100, modified=0.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "size", "sort": "descending"}
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == expected_entries

    async def test_list_directories_by_modified_descending(self, setup_test_directory):
        """Test that list_directories returns structured output sorted by modified time in descending order."""
        dir_specs = [
            ("newest", 100, 3000.0),
            ("oldest", 100, 1000.0),
            ("middle", 100, 2000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        expected_entries = [
            DirectoryEntry(name="newest", size=0, modified=3000.0),
            DirectoryEntry(name="middle", size=0, modified=2000.0),
            DirectoryEntry(name="oldest", size=0, modified=1000.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "modified", "sort": "descending"}
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == expected_entries

    async def test_list_directories_invalid_order_by(self, tmp_path):
        """Test that invalid order_by parameter raises ValueError."""
        with pytest.raises(ToolError, match="1 validation error"):
            await mcp.call_tool("list_directories", {"path": str(tmp_path), "order_by": "invalid"})

    async def test_list_directories_invalid_sort(self, tmp_path):
        """Test that invalid sort parameter raises ValueError."""
        with pytest.raises(ToolError, match="1 validation error"):
            await mcp.call_tool("list_directories", {"path": str(tmp_path), "sort": "invalid"})

    async def test_list_directories_invalid_path(self, tmp_path):
        """Test with non-existent path raises ToolError."""
        non_existent_path = tmp_path / "non_existent_directory"
        with pytest.raises(ToolError, match="Path does not exist"):
            await mcp.call_tool("list_directories", {"path": str(non_existent_path), "order_by": "name"})

    async def test_list_directories_path_is_file_not_directory(self, tmp_path):
        """Test with a file path instead of directory raises ToolError."""
        tmp_file = tmp_path / "data.txt"
        tmp_file.write_bytes(b"test content")

        with pytest.raises(ToolError, match="Path is not a directory"):
            await mcp.call_tool("list_directories", {"path": str(tmp_file), "order_by": "name"})

    async def test_list_directories_handles_permission_denied(self, restricted_path):
        """Test handling of permission denied errors gracefully."""
        with pytest.raises(ToolError, match="Permission denied"):
            await mcp.call_tool("list_directories", {"path": str(restricted_path)})

    async def test_list_directories_empty_directory_by_name(self, tmp_path):
        """Test list_directories with a directory containing no subdirectories (name ordering)."""
        result = await mcp.call_tool("list_directories", {"path": str(tmp_path), "order_by": "name"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == []

    async def test_list_directories_empty_directory_by_size(self, tmp_path):
        """Test list_directories with a directory containing no subdirectories (size ordering)."""
        result = await mcp.call_tool("list_directories", {"path": str(tmp_path), "order_by": "size"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == []

    async def test_list_directories_empty_directory_by_modified(self, tmp_path):
        """Test list_directories with a directory containing no subdirectories (modified ordering)."""
        result = await mcp.call_tool("list_directories", {"path": str(tmp_path), "order_by": "modified"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == []

    async def test_list_directories_special_characters_in_names(self, tmp_path):
        """Test list_directories handles directory names with special characters."""
        # Create directories with special characters
        (tmp_path / "dir with spaces").mkdir()
        (tmp_path / "dir-with-dashes").mkdir()
        (tmp_path / "dir_with_underscores").mkdir()

        result = await mcp.call_tool("list_directories", {"path": str(tmp_path), "order_by": "name"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]

        # Verify all directory names are correctly parsed
        names = [entry.name for entry in got]
        assert "dir with spaces" in names
        assert "dir-with-dashes" in names
        assert "dir_with_underscores" in names
        assert len(got) == 3

    async def test_list_directories_by_modified_with_top_n(self, setup_test_directory):
        """Test that list_directories returns structured output sorted by modified time with top_n limit."""
        dir_specs = [
            ("newest", 100, 3000.0),
            ("oldest", 100, 1000.0),
            ("middle", 100, 2000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        expected_entries = [
            DirectoryEntry(name="oldest", size=0, modified=1000.0),
            DirectoryEntry(name="middle", size=0, modified=2000.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "modified", "sort": "ascending", "top_n": 2}
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == expected_entries

    async def test_list_directories_by_size_with_top_n_descending(self, setup_test_directory):
        """Test that list_directories returns structured output sorted by size with top_n limit and descending order."""
        dir_specs = [
            ("small", 100, 1000.0),
            ("large", 300, 3000.0),
            ("medium", 200, 2000.0),
            ("tiny", 50, 500.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        expected_entries = [
            DirectoryEntry(name="large", size=300, modified=0.0),
            DirectoryEntry(name="medium", size=200, modified=0.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "size", "sort": "descending", "top_n": 2}
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]
        assert got == expected_entries

    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_directories_remote_execution_by_size(self, mock_execute_command):
        """Test list_directories with remote execution for size ordering."""
        # Mock du command output
        mock_execute_command.return_value = (
            0,
            "100\t/remote/path/small\n300\t/remote/path/large\n200\t/remote/path/medium\n500\t/remote/path",
            "",
        )

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": "size", "host": "remote.server.com", "username": "testuser"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]

        # Verify results are sorted by size
        assert len(got) == 3
        assert got[0].name == "small"
        assert got[0].size == 100
        assert got[1].name == "medium"
        assert got[1].size == 200
        assert got[2].name == "large"
        assert got[2].size == 300

        # Verify execute_command was called with host/username
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"
        assert call_kwargs["username"] == "testuser"

    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_directories_remote_execution_by_name(self, mock_execute_command):
        """Test list_directories with remote execution for name ordering."""
        # Mock find command output
        mock_execute_command.return_value = (
            0,
            "gamma\nalpha\nbeta",
            "",
        )

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": "name", "host": "remote.server.com", "username": "testuser"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]

        # Verify results are sorted by name
        assert len(got) == 3
        assert got[0].name == "alpha"
        assert got[1].name == "beta"
        assert got[2].name == "gamma"

        # Verify execute_command was called with host/username
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"
        assert call_kwargs["username"] == "testuser"

    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_directories_remote_execution_by_modified(self, mock_execute_command):
        """Test list_directories with remote execution for modified ordering."""
        # Mock find command output with timestamps
        mock_execute_command.return_value = (
            0,
            "3000.0\tnewest\n1000.0\toldest\n2000.0\tmiddle",
            "",
        )

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": "modified", "host": "remote.server.com", "username": "testuser"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [DirectoryEntry(**entry) for entry in result[1]["result"]]

        # Verify results are sorted by modified time
        assert len(got) == 3
        assert got[0].name == "oldest"
        assert got[0].modified == 1000.0
        assert got[1].name == "middle"
        assert got[1].modified == 2000.0
        assert got[2].name == "newest"
        assert got[2].modified == 3000.0

        # Verify execute_command was called with host/username
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"
        assert call_kwargs["username"] == "testuser"

    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_directories_remote_skips_path_validation(self, mock_execute_command):
        """Test that remote execution skips local path validation."""
        # Mock du command output
        mock_execute_command.return_value = (
            0,
            "100\t/nonexistent/path",
            "",
        )

        # This path doesn't exist locally but should not raise an error for remote execution
        result = await mcp.call_tool(
            "list_directories",
            {"path": "/nonexistent/remote/path", "order_by": "size", "host": "remote.server.com"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        # Should succeed even though path doesn't exist locally
        assert isinstance(result[1], dict)

    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_directories_du_command_failure(self, mock_execute_command):
        """Test list_directories handles du command failures for size ordering."""
        # Mock du command to return non-zero returncode
        mock_execute_command.return_value = (1, "", "du: cannot read directory")

        with pytest.raises(ToolError, match="Error running du command"):
            await mcp.call_tool(
                "list_directories",
                {"path": "/some/path", "order_by": "size", "host": "remote.server.com"},
            )

    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_directories_find_command_failure_name(self, mock_execute_command):
        """Test list_directories handles find command failures for name ordering."""
        # Mock find command to return non-zero returncode
        mock_execute_command.return_value = (1, "", "find: '/some/path': Permission denied")

        with pytest.raises(ToolError, match="Error running find command"):
            await mcp.call_tool(
                "list_directories",
                {"path": "/some/path", "order_by": "name", "host": "remote.server.com"},
            )

    @patch("linux_mcp_server.tools.storage.execute_command")
    async def test_list_directories_find_command_failure_modified(self, mock_execute_command):
        """Test list_directories handles find command failures for modified ordering."""
        # Mock find command to return non-zero returncode
        mock_execute_command.return_value = (1, "", "find: '/some/path': Permission denied")

        with pytest.raises(ToolError, match="Error running find command"):
            await mcp.call_tool(
                "list_directories",
                {"path": "/some/path", "order_by": "modified", "host": "remote.server.com"},
            )
