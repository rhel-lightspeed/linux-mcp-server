"""Tests for storage tools."""

import os
import sys

from pathlib import Path
from typing import Literal
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from linux_mcp_server.server import mcp
from linux_mcp_server.tools.storage import NodeEntry


# =============================================================================
# Shared test data specs
# =============================================================================

ALPHA_BETA_GAMMA_SPECS = [
    ("alpha", 100, 1000.0),
    ("beta", 200, 2000.0),
    ("gamma", 300, 3000.0),
]

SIZE_ORDERED_SPECS = [
    ("small", 100, 1000.0),
    ("large", 300, 3000.0),
    ("medium", 200, 2000.0),
]

TIME_ORDERED_SPECS = [
    ("newest", 100, 3000.0),
    ("oldest", 100, 1000.0),
    ("middle", 100, 2000.0),
]

SIZE_WITH_TINY_SPECS = [
    ("small", 100, 1000.0),
    ("large", 300, 3000.0),
    ("medium", 200, 2000.0),
    ("tiny", 50, 500.0),
]


# =============================================================================
# Test fixtures
# =============================================================================


@pytest.fixture
def setup_test_nodes(tmp_path):
    """
    Factory fixture for creating test directories or files with specific sizes and modification times.

    Returns a function that accepts a list of (name, size, modified_time) tuples and a node_type
    parameter ("directory" or "file") and:
    - Creates directories or files with the specified sizes
    - Sets their modification times
    - Returns the parent directory path and list of expected NodeEntry objects
    """

    def _create_nodes(
        node_specs: list[tuple[str, int, float]],
        node_type: Literal["directory", "file"],
    ) -> tuple[Path, list[NodeEntry]]:
        expected_entries = []

        for name, size, modified_time in node_specs:
            if node_type == "directory":
                node_path = tmp_path / name
                node_path.mkdir()
                if size > 0:
                    (node_path / "content.txt").write_text("x" * size)
            else:
                node_path = tmp_path / name
                node_path.touch()
                if size > 0:
                    node_path.write_text("x" * size)

            os.utime(node_path, (modified_time, modified_time))
            expected_entries.append(NodeEntry(name=name, size=size, modified=modified_time))

        return tmp_path, expected_entries

    return _create_nodes


@pytest.fixture
def setup_test_directory(setup_test_nodes):
    """Legacy fixture - creates test directories. Delegates to setup_test_nodes."""

    def _create_directory(dir_specs: list[tuple[str, int, float]]) -> tuple[Path, list[NodeEntry]]:
        return setup_test_nodes(dir_specs, "directory")

    return _create_directory


@pytest.fixture
def setup_test_files(setup_test_nodes):
    """Legacy fixture - creates test files. Delegates to setup_test_nodes."""

    def _create_files(file_specs: list[tuple[str, int, float]]) -> tuple[Path, list[NodeEntry]]:
        return setup_test_nodes(file_specs, "file")

    return _create_files


@pytest.fixture
def restricted_path(tmp_path):
    restricted_path = tmp_path / "restricted"
    restricted_path.mkdir()
    restricted_path.chmod(0o000)

    yield restricted_path

    restricted_path.chmod(0o755)


@pytest.fixture
def assert_node_entries():
    """Fixture for asserting NodeEntry results from tool calls."""

    def _assert(result, expected_entries: list[NodeEntry]):
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [NodeEntry(**entry) for entry in result[1]["result"]]
        assert got == expected_entries

    return _assert


# =============================================================================
# TestListBlockDevices
# =============================================================================


class TestListBlockDevices:
    async def test_list_block_devices_lsblk_success(self, mocker):
        """Test list_block_devices with successful lsblk command."""
        mock_execute_command = AsyncMock(
            return_value=(
                0,
                "NAME   SIZE TYPE MOUNTPOINT FSTYPE MODEL\nsda    1TB  disk            \nsda1   512G part /          ext4",
                "",
            )
        )
        mocker.patch("linux_mcp_server.tools.storage.execute_command", mock_execute_command)

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

    async def test_list_block_devices_with_disk_io_stats(self, mocker):
        """Test list_block_devices includes disk I/O statistics for local execution."""
        mocker.patch(
            "linux_mcp_server.tools.storage.execute_command",
            AsyncMock(
                return_value=(
                    0,
                    "NAME   SIZE TYPE MOUNTPOINT\nsda    1TB  disk",
                    "",
                )
            ),
        )

        # Create mock disk I/O stats
        mock_stats = MagicMock()
        mock_stats.read_bytes = 1024 * 1024 * 1024  # 1 GB
        mock_stats.write_bytes = 512 * 1024 * 1024  # 512 MB
        mock_stats.read_count = 1000
        mock_stats.write_count = 500

        mocker.patch("linux_mcp_server.tools.storage.psutil.disk_io_counters", return_value={"sda": mock_stats})

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

    async def test_list_block_devices_with_no_disk_io_stats(self, mocker):
        """Test list_block_devices includes disk I/O statistics for local execution."""
        mocker.patch("linux_mcp_server.tools.storage.execute_command", return_value=(0, "", ""))
        mocker.patch("linux_mcp_server.tools.storage.psutil.disk_io_counters", return_value={})

        result = await mcp.call_tool("list_block_devices", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "=== Disk I/O Statistics (per disk) ===" not in output

    async def test_list_block_devices_lsblk_fallback(self, mocker):
        """Test list_block_devices falls back to psutil when lsblk fails."""
        # lsblk returns non-zero
        mocker.patch(
            "linux_mcp_server.tools.storage.execute_command", AsyncMock(return_value=(1, "", "command failed"))
        )

        # Mock partition data
        mock_partition = MagicMock()
        mock_partition.device = "/dev/sda1"
        mock_partition.mountpoint = "/"
        mock_partition.fstype = "ext4"
        mock_partition.opts = "rw,relatime"

        mocker.patch("linux_mcp_server.tools.storage.psutil.disk_partitions", return_value=[mock_partition])

        result = await mcp.call_tool("list_block_devices", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "=== Block Devices (fallback) ===" in output
        assert "/dev/sda1" in output
        assert "Mountpoint: /" in output
        assert "Filesystem: ext4" in output

    async def test_list_block_devices_file_not_found(self, mocker):
        """Test list_block_devices when lsblk is not available."""
        # lsblk not found
        mocker.patch("linux_mcp_server.tools.storage.execute_command", side_effect=FileNotFoundError("lsblk not found"))

        # Mock partition data
        mock_partition = MagicMock()
        mock_partition.device = "/dev/nvme0n1p1"
        mock_partition.mountpoint = "/boot"
        mock_partition.fstype = "vfat"
        mock_partition.opts = "rw"

        mocker.patch("linux_mcp_server.tools.storage.psutil.disk_partitions", return_value=[mock_partition])

        result = await mcp.call_tool("list_block_devices", {})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "=== Block Devices ===" in output
        assert "/dev/nvme0n1p1" in output
        assert "Mountpoint: /boot" in output

    async def test_list_block_devices_remote_execution(self, mocker):
        """Test list_block_devices with remote execution (no disk I/O stats)."""
        mock_execute_command = AsyncMock(
            return_value=(
                0,
                "NAME   SIZE TYPE\nsda    1TB  disk",
                "",
            )
        )
        mocker.patch("linux_mcp_server.tools.storage.execute_command", mock_execute_command)

        # Mock disk I/O to ensure it's not called or used
        mock_stats = MagicMock()
        mock_stats.read_bytes = 1024
        mocker.patch("linux_mcp_server.tools.storage.psutil.disk_io_counters", return_value={"sda": mock_stats})

        result = await mcp.call_tool("list_block_devices", {"host": "remote.host.com"})
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        # Should NOT include disk I/O stats for remote execution
        assert "=== Disk I/O Statistics" not in output
        assert "=== Block Devices ===" in output

        # Verify execute_command was called with host
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.host.com"

    async def test_list_block_devices_exception_handling(self, mocker):
        """Test list_block_devices handles general exceptions."""
        mocker.patch("linux_mcp_server.tools.storage.execute_command", side_effect=ValueError("Raised intentionally"))

        with pytest.raises(ToolError, match="Raised intentionally"):
            await mcp.call_tool("list_block_devices", {})


# =============================================================================
# TestListDirectories
# =============================================================================


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListDirectories:
    async def test_list_directories_returns_structured_output(self, setup_test_directory):
        """Test that list_directories returns structured output."""
        test_path, _ = setup_test_directory(ALPHA_BETA_GAMMA_SPECS)

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": "name"})

        # Verify the entire result structure
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        directories = list[NodeEntry](result[1]["result"])
        assert directories is not None

    async def test_list_directories_by_name(self, setup_test_directory, assert_node_entries):
        """Test that list_directories returns structured output sorted by name."""
        test_path, _ = setup_test_directory(ALPHA_BETA_GAMMA_SPECS)

        # When ordering by name, only the name field is populated
        expected_entries = [
            NodeEntry(name="alpha", size=0, modified=0.0),
            NodeEntry(name="beta", size=0, modified=0.0),
            NodeEntry(name="gamma", size=0, modified=0.0),
        ]

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": "name"})
        assert_node_entries(result, expected_entries)

    async def test_list_directories_by_size(self, setup_test_directory, assert_node_entries):
        """Test that list_directories returns structured output sorted by size."""
        test_path, _ = setup_test_directory(SIZE_ORDERED_SPECS)

        expected_entries = [
            NodeEntry(name="small", size=100, modified=0.0),
            NodeEntry(name="medium", size=200, modified=0.0),
            NodeEntry(name="large", size=300, modified=0.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "size", "sort": "ascending"}
        )
        assert_node_entries(result, expected_entries)

    async def test_list_directories_by_modified(self, setup_test_directory, assert_node_entries):
        """Test that list_directories returns structured output sorted by modification time."""
        dir_specs = [
            ("newest", 0, 3000.0),
            ("oldest", 100, 1000.0),
            ("middle", 100, 2000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        # When ordering by modified, only name and modified fields are populated
        expected_entries = [
            NodeEntry(name="oldest", size=0, modified=1000.0),
            NodeEntry(name="middle", size=0, modified=2000.0),
            NodeEntry(name="newest", size=0, modified=3000.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "modified", "sort": "ascending"}
        )
        assert_node_entries(result, expected_entries)

    async def test_list_directories_by_name_with_top_n(self, setup_test_directory, assert_node_entries):
        """Test that list_directories returns structured output sorted by name with top_n limit."""
        test_path, _ = setup_test_directory(ALPHA_BETA_GAMMA_SPECS)

        # When ordering by name, only name field is populated
        expected_entries = [
            NodeEntry(name="alpha", size=0, modified=0.0),
            NodeEntry(name="beta", size=0, modified=0.0),
        ]

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": "name", "top_n": 2})
        assert_node_entries(result, expected_entries)

    async def test_list_directories_by_name_descending(self, setup_test_directory, assert_node_entries):
        """Test that list_directories returns structured output sorted by name in descending order."""
        test_path, _ = setup_test_directory(ALPHA_BETA_GAMMA_SPECS)

        expected_entries = [
            NodeEntry(name="gamma", size=0, modified=0.0),
            NodeEntry(name="beta", size=0, modified=0.0),
            NodeEntry(name="alpha", size=0, modified=0.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "name", "sort": "descending"}
        )
        assert_node_entries(result, expected_entries)

    async def test_list_directories_by_size_descending(self, setup_test_directory, assert_node_entries):
        """Test that list_directories returns structured output sorted by size in descending order."""
        test_path, _ = setup_test_directory(SIZE_ORDERED_SPECS)

        expected_entries = [
            NodeEntry(name="large", size=300, modified=0.0),
            NodeEntry(name="medium", size=200, modified=0.0),
            NodeEntry(name="small", size=100, modified=0.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "size", "sort": "descending"}
        )
        assert_node_entries(result, expected_entries)

    async def test_list_directories_by_modified_descending(self, setup_test_directory, assert_node_entries):
        """Test that list_directories returns structured output sorted by modified time in descending order."""
        test_path, _ = setup_test_directory(TIME_ORDERED_SPECS)

        expected_entries = [
            NodeEntry(name="newest", size=0, modified=3000.0),
            NodeEntry(name="middle", size=0, modified=2000.0),
            NodeEntry(name="oldest", size=0, modified=1000.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "modified", "sort": "descending"}
        )
        assert_node_entries(result, expected_entries)

    @pytest.mark.parametrize("invalid_param,invalid_value", [("order_by", "invalid"), ("sort", "invalid")])
    async def test_list_directories_invalid_parameter(self, tmp_path, invalid_param, invalid_value):
        """Test that invalid order_by/sort parameters raise validation errors."""
        with pytest.raises(ToolError, match="1 validation error"):
            await mcp.call_tool("list_directories", {"path": str(tmp_path), invalid_param: invalid_value})

    async def test_list_directories_invalid_path(self, tmp_path):
        """Test with non-existent path raises ToolError."""
        non_existent_path = tmp_path / "non_existent_directory"
        with pytest.raises(ToolError, match="Path does not exist or cannot be resolved"):
            await mcp.call_tool("list_directories", {"path": str(non_existent_path), "order_by": "name"})

    async def test_list_directories_handles_permission_denied(self, restricted_path):
        """Test handling of permission denied errors gracefully."""
        with pytest.raises(ToolError, match="Permission denied to read"):
            await mcp.call_tool("list_directories", {"path": str(restricted_path)})

    @pytest.mark.parametrize("order_by", ["name", "size", "modified"])
    async def test_list_directories_empty_directory(self, tmp_path, order_by, assert_node_entries):
        """Test list_directories with an empty directory for all order_by values."""
        result = await mcp.call_tool("list_directories", {"path": str(tmp_path), "order_by": order_by})
        assert_node_entries(result, [])

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
        got = [NodeEntry(**entry) for entry in result[1]["result"]]

        # Verify all directory names are correctly parsed
        names = [entry.name for entry in got]
        assert "dir with spaces" in names
        assert "dir-with-dashes" in names
        assert "dir_with_underscores" in names
        assert len(got) == 3

    async def test_list_directories_by_modified_with_top_n(self, setup_test_directory, assert_node_entries):
        """Test that list_directories returns structured output sorted by modified time with top_n limit."""
        test_path, _ = setup_test_directory(TIME_ORDERED_SPECS)

        expected_entries = [
            NodeEntry(name="oldest", size=0, modified=1000.0),
            NodeEntry(name="middle", size=0, modified=2000.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "modified", "sort": "ascending", "top_n": 2}
        )
        assert_node_entries(result, expected_entries)

    async def test_list_directories_by_size_with_top_n_descending(self, setup_test_directory, assert_node_entries):
        """Test that list_directories returns structured output sorted by size with top_n limit and descending order."""
        test_path, _ = setup_test_directory(SIZE_WITH_TINY_SPECS)

        expected_entries = [
            NodeEntry(name="large", size=300, modified=0.0),
            NodeEntry(name="medium", size=200, modified=0.0),
        ]

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": "size", "sort": "descending", "top_n": 2}
        )
        assert_node_entries(result, expected_entries)

    async def test_list_directories_remote_execution_by_size(self, mocker):
        """Test list_directories with remote execution for size ordering."""
        # Mock du command output
        mock_execute_command = AsyncMock(
            return_value=(
                0,
                "100\t/remote/path/small\n300\t/remote/path/large\n200\t/remote/path/medium\n500\t/remote/path",
                "",
            )
        )
        mocker.patch("linux_mcp_server.tools.storage.execute_command", mock_execute_command)

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": "size", "host": "remote.server.com"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [NodeEntry(**entry) for entry in result[1]["result"]]

        # Verify results are sorted by size
        assert len(got) == 3
        assert got[0].name == "small"
        assert got[0].size == 100
        assert got[1].name == "medium"
        assert got[1].size == 200
        assert got[2].name == "large"
        assert got[2].size == 300

        # Verify execute_command was called with host
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_list_directories_remote_execution_by_name(self, mocker):
        """Test list_directories with remote execution for name ordering."""
        # Mock find command output
        mock_execute_command = AsyncMock(
            return_value=(
                0,
                "gamma\nalpha\nbeta",
                "",
            )
        )
        mocker.patch("linux_mcp_server.tools.storage.execute_command", mock_execute_command)

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": "name", "host": "remote.server.com"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [NodeEntry(**entry) for entry in result[1]["result"]]

        # Verify results are sorted by name
        assert len(got) == 3
        assert got[0].name == "alpha"
        assert got[1].name == "beta"
        assert got[2].name == "gamma"

        # Verify execute_command was called with host
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_list_directories_remote_execution_by_modified(self, mocker):
        """Test list_directories with remote execution for modified ordering."""
        # Mock find command output with timestamps
        mock_execute_command = AsyncMock(
            return_value=(
                0,
                "3000.0\tnewest\n1000.0\toldest\n2000.0\tmiddle",
                "",
            )
        )
        mocker.patch("linux_mcp_server.tools.storage.execute_command", mock_execute_command)

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": "modified", "host": "remote.server.com"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [NodeEntry(**entry) for entry in result[1]["result"]]

        # Verify results are sorted by modified time
        assert len(got) == 3
        assert got[0].name == "oldest"
        assert got[0].modified == 1000.0
        assert got[1].name == "middle"
        assert got[1].modified == 2000.0
        assert got[2].name == "newest"
        assert got[2].modified == 3000.0

        # Verify execute_command was called with host
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_list_directories_remote_skips_path_validation(self, mocker):
        """Test that remote execution skips local path validation."""
        # Mock du command output
        mocker.patch(
            "linux_mcp_server.tools.storage.execute_command",
            AsyncMock(
                return_value=(
                    0,
                    "100\t/nonexistent/path",
                    "",
                )
            ),
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

    @pytest.mark.parametrize("order_by", ["size", "name", "modified"])
    async def test_list_directories_command_failure(self, mocker, order_by):
        """Test list_directories handles command failures for all order_by types."""
        mocker.patch(
            "linux_mcp_server.tools.storage.execute_command",
            AsyncMock(return_value=(1, "", "command: Permission denied")),
        )

        with pytest.raises(ToolError, match="Error executing tool list_directories"):
            await mcp.call_tool(
                "list_directories",
                {"path": "/some/path", "order_by": order_by, "host": "remote.server.com"},
            )


# =============================================================================
# TestListFiles
# =============================================================================


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListFiles:
    async def test_list_files_returns_structured_output(self, setup_test_files):
        """Test that list_files returns structured output."""
        test_path, _ = setup_test_files(ALPHA_BETA_GAMMA_SPECS)

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": "name"})

        # Verify the entire result structure
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        files = list[NodeEntry](result[1]["result"])
        assert files is not None

    async def test_list_files_by_name(self, setup_test_files, assert_node_entries):
        """Test that list_files returns structured output sorted by name."""
        test_path, _ = setup_test_files(ALPHA_BETA_GAMMA_SPECS)

        # When ordering by name, only the name field is populated
        expected_entries = [
            NodeEntry(name="alpha", size=0, modified=0.0),
            NodeEntry(name="beta", size=0, modified=0.0),
            NodeEntry(name="gamma", size=0, modified=0.0),
        ]

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": "name"})
        assert_node_entries(result, expected_entries)

    async def test_list_files_by_size(self, setup_test_files, assert_node_entries):
        """Test that list_files returns structured output sorted by size."""
        test_path, _ = setup_test_files(SIZE_ORDERED_SPECS)

        expected_entries = [
            NodeEntry(name="small", size=100, modified=0.0),
            NodeEntry(name="medium", size=200, modified=0.0),
            NodeEntry(name="large", size=300, modified=0.0),
        ]

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": "size", "sort": "ascending"})
        assert_node_entries(result, expected_entries)

    async def test_list_files_by_modified(self, setup_test_files, assert_node_entries):
        """Test that list_files returns structured output sorted by modification time."""
        dir_specs = [
            ("newest", 0, 3000.0),
            ("oldest", 100, 1000.0),
            ("middle", 100, 2000.0),
        ]
        test_path, _ = setup_test_files(dir_specs)

        # When ordering by modified, only name and modified fields are populated
        expected_entries = [
            NodeEntry(name="oldest", size=0, modified=1000.0),
            NodeEntry(name="middle", size=0, modified=2000.0),
            NodeEntry(name="newest", size=0, modified=3000.0),
        ]

        result = await mcp.call_tool(
            "list_files", {"path": str(test_path), "order_by": "modified", "sort": "ascending"}
        )
        assert_node_entries(result, expected_entries)

    async def test_list_files_by_name_with_top_n(self, setup_test_files, assert_node_entries):
        """Test that list_files returns structured output sorted by name with top_n limit."""
        test_path, _ = setup_test_files(ALPHA_BETA_GAMMA_SPECS)

        # When ordering by name, only name field is populated
        expected_entries = [
            NodeEntry(name="alpha", size=0, modified=0.0),
            NodeEntry(name="beta", size=0, modified=0.0),
        ]

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": "name", "top_n": 2})
        assert_node_entries(result, expected_entries)

    async def test_list_files_by_name_descending(self, setup_test_files, assert_node_entries):
        """Test that list_files returns structured output sorted by name in descending order."""
        test_path, _ = setup_test_files(ALPHA_BETA_GAMMA_SPECS)

        expected_entries = [
            NodeEntry(name="gamma", size=0, modified=0.0),
            NodeEntry(name="beta", size=0, modified=0.0),
            NodeEntry(name="alpha", size=0, modified=0.0),
        ]

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": "name", "sort": "descending"})
        assert_node_entries(result, expected_entries)

    async def test_list_files_by_size_descending(self, setup_test_files, assert_node_entries):
        """Test that list_files returns structured output sorted by size in descending order."""
        test_path, _ = setup_test_files(SIZE_ORDERED_SPECS)

        expected_entries = [
            NodeEntry(name="large", size=300, modified=0.0),
            NodeEntry(name="medium", size=200, modified=0.0),
            NodeEntry(name="small", size=100, modified=0.0),
        ]

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": "size", "sort": "descending"})
        assert_node_entries(result, expected_entries)

    async def test_list_files_by_modified_descending(self, setup_test_files, assert_node_entries):
        """Test that list_files returns structured output sorted by modified time in descending order."""
        test_path, _ = setup_test_files(TIME_ORDERED_SPECS)

        expected_entries = [
            NodeEntry(name="newest", size=0, modified=3000.0),
            NodeEntry(name="middle", size=0, modified=2000.0),
            NodeEntry(name="oldest", size=0, modified=1000.0),
        ]

        result = await mcp.call_tool(
            "list_files", {"path": str(test_path), "order_by": "modified", "sort": "descending"}
        )
        assert_node_entries(result, expected_entries)

    @pytest.mark.parametrize("invalid_param,invalid_value", [("order_by", "invalid"), ("sort", "invalid")])
    async def test_list_files_invalid_parameter(self, tmp_path, invalid_param, invalid_value):
        """Test that invalid order_by/sort parameters raise validation errors."""
        with pytest.raises(ToolError, match="1 validation error"):
            await mcp.call_tool("list_files", {"path": str(tmp_path), invalid_param: invalid_value})

    async def test_list_files_invalid_path(self, tmp_path):
        """Test with non-existent path raises ToolError."""
        non_existent_path = tmp_path / "non_existent_directory"
        with pytest.raises(ToolError, match="Path does not exist or cannot be resolved"):
            await mcp.call_tool("list_files", {"path": str(non_existent_path), "order_by": "name"})

    async def test_list_files_handles_permission_denied(self, restricted_path):
        """Test handling of permission denied errors gracefully."""
        with pytest.raises(ToolError, match="Permission denied to read"):
            await mcp.call_tool("list_files", {"path": str(restricted_path)})

    @pytest.mark.parametrize("order_by", ["name", "size", "modified"])
    async def test_list_files_empty_directory(self, tmp_path, order_by, assert_node_entries):
        """Test list_files with an empty directory for all order_by values."""
        result = await mcp.call_tool("list_files", {"path": str(tmp_path), "order_by": order_by})
        assert_node_entries(result, [])

    async def test_list_files_special_characters_in_names(self, tmp_path):
        """Test list_files handles directory names with special characters."""
        # Create files with special characters
        (tmp_path / "file with spaces").touch()
        (tmp_path / "file-with-dashes").touch()
        (tmp_path / "file_with_underscores").touch()
        (tmp_path / "file_with_@@$!($)@").touch()
        (tmp_path / "file_with_📁.txt").touch()
        (tmp_path / "file_with_✨.md").touch()
        (tmp_path / "file_with_question?.txt").touch()
        (tmp_path / "file_with_angle<test>.log").touch()
        (tmp_path / "file_with_pipe|symbol.txt").touch()
        (tmp_path / "file_with_colon:check.md").touch()

        result = await mcp.call_tool("list_files", {"path": str(tmp_path), "order_by": "name"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [NodeEntry(**entry) for entry in result[1]["result"]]

        # Verify all directory names are correctly parsed
        names = [entry.name for entry in got]
        assert "file with spaces" in names
        assert "file-with-dashes" in names
        assert "file_with_underscores" in names
        assert len(got) == 10

    async def test_list_files_by_modified_with_top_n(self, setup_test_files, assert_node_entries):
        """Test that list_files returns structured output sorted by modified time with top_n limit."""
        test_path, _ = setup_test_files(TIME_ORDERED_SPECS)

        expected_entries = [
            NodeEntry(name="oldest", size=0, modified=1000.0),
            NodeEntry(name="middle", size=0, modified=2000.0),
        ]

        result = await mcp.call_tool(
            "list_files", {"path": str(test_path), "order_by": "modified", "sort": "ascending", "top_n": 2}
        )
        assert_node_entries(result, expected_entries)

    async def test_list_files_by_size_with_top_n_descending(self, setup_test_files, assert_node_entries):
        """Test that list_files returns structured output sorted by size with top_n limit and descending order."""
        test_path, _ = setup_test_files(SIZE_WITH_TINY_SPECS)

        expected_entries = [
            NodeEntry(name="large", size=300, modified=0.0),
            NodeEntry(name="medium", size=200, modified=0.0),
        ]

        result = await mcp.call_tool(
            "list_files", {"path": str(test_path), "order_by": "size", "sort": "descending", "top_n": 2}
        )
        assert_node_entries(result, expected_entries)

    async def test_list_files_remote_execution_by_size(self, mocker):
        """Test list_files with remote execution for size ordering."""
        # Mock du command output
        mock_execute_command = mocker.patch(
            "linux_mcp_server.tools.storage.execute_command",
            AsyncMock(
                return_value=(
                    0,
                    "100\t/remote/path/small\n300\t/remote/path/large\n200\t/remote/path/medium\n500\t/remote/path",
                    "",
                )
            ),
        )

        result = await mcp.call_tool(
            "list_files",
            {"path": "/remote/path", "order_by": "size", "host": "remote.server.com"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [NodeEntry(**entry) for entry in result[1]["result"]]

        # Verify results are sorted by size
        assert len(got) == 3
        assert got[0].name == "small"
        assert got[0].size == 100
        assert got[1].name == "medium"
        assert got[1].size == 200
        assert got[2].name == "large"
        assert got[2].size == 300

        # Verify execute_command was called with host
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_list_files_remote_execution_by_name(self, mocker):
        """Test list_files with remote execution for name ordering."""
        mock_execute_command = mocker.patch(
            "linux_mcp_server.tools.storage.execute_command",
            AsyncMock(
                return_value=(
                    0,
                    "gamma\nalpha\nbeta",
                    "",
                )
            ),
        )

        result = await mcp.call_tool(
            "list_files",
            {"path": "/remote/path", "order_by": "name", "host": "remote.server.com"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [NodeEntry(**entry) for entry in result[1]["result"]]

        # Verify results are sorted by name
        assert len(got) == 3
        assert got[0].name == "alpha"
        assert got[1].name == "beta"
        assert got[2].name == "gamma"

        # Verify execute_command was called with host
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_list_files_remote_execution_by_modified(self, mocker):
        """Test list_files with remote execution for modified ordering."""
        mock_execute_command = mocker.patch(
            "linux_mcp_server.tools.storage.execute_command",
            AsyncMock(
                return_value=(
                    0,
                    "3000.0\tnewest\n1000.0\toldest\n2000.0\tmiddle",
                    "",
                )
            ),
        )

        result = await mcp.call_tool(
            "list_files",
            {"path": "/remote/path", "order_by": "modified", "host": "remote.server.com"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        got = [NodeEntry(**entry) for entry in result[1]["result"]]

        # Verify results are sorted by modified time
        assert len(got) == 3
        assert got[0].name == "oldest"
        assert got[0].modified == 1000.0
        assert got[1].name == "middle"
        assert got[1].modified == 2000.0
        assert got[2].name == "newest"
        assert got[2].modified == 3000.0

        # Verify execute_command was called with host
        mock_execute_command.assert_called_once()
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_list_files_remote_skips_path_validation(self, mocker):
        """Test that remote execution skips local path validation."""
        # Mock du command output
        mocker.patch(
            "linux_mcp_server.tools.storage.execute_command",
            AsyncMock(
                return_value=(
                    0,
                    "100\t/nonexistent/path",
                    "",
                )
            ),
        )

        # This path doesn't e'xist locally but should not raise an error for remote execution
        result = await mcp.call_tool(
            "list_files",
            {"path": "/nonexistent/remote/path", "order_by": "size", "host": "remote.server.com"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        # Should succeed even though path doesn't exist locally
        assert isinstance(result[1], dict)

    @pytest.mark.parametrize(("order_by"), (("size",), ("name",), ("modified",)))
    async def test_list_files_find_command_failure_order_by(self, mocker, order_by):
        """Test list_files handles find command failures for size ordering."""
        # Mock du command to return non-zero returncode
        mocker.patch(
            "linux_mcp_server.tools.storage.execute_command",
            return_value=(1, "", "find: '/some/path': Permission denied"),
        )

        with pytest.raises(ToolError, match="Error executing tool list_files"):
            await mcp.call_tool(
                "list_files",
                {"path": "/some/path", "order_by": order_by, "host": "remote.server.com"},
            )


# =============================================================================
# TestReadFile
# =============================================================================


class TestReadFile:
    async def test_read_file_success(self, tmp_path):
        """Test read_file with a valid file."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_content = "Hello, World!\nThis is a test file.\nLine 3."
        test_file.write_text(test_content)

        result = await mcp.call_tool("read_file", {"path": str(test_file)})

        # Verify result structure
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert output == test_content

    async def test_read_file_empty_file(self, tmp_path):
        """Test read_file with an empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")

        result = await mcp.call_tool("read_file", {"path": str(test_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert output == ""

    async def test_read_file_nonexistent(self, tmp_path):
        """Test read_file with a non-existent file."""
        non_existent_file = tmp_path / "nonexistent.txt"

        with pytest.raises(ToolError, match="Path does not exist"):
            await mcp.call_tool("read_file", {"path": str(non_existent_file)})

    async def test_read_file_directory_not_file(self, tmp_path):
        """Test read_file with a directory path instead of a file."""
        with pytest.raises(ToolError, match="Path is not a file"):
            await mcp.call_tool("read_file", {"path": str(tmp_path)})

    async def test_read_file_permission_denied(self, tmp_path):
        """Test read_file with a file that has no read permissions."""
        restricted_file = tmp_path / "restricted.txt"
        restricted_file.write_text("secret content")
        restricted_file.chmod(0o000)

        try:
            with pytest.raises(ToolError, match="Permission denied"):
                await mcp.call_tool("read_file", {"path": str(restricted_file)})
        finally:
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)

    async def test_read_file_with_special_characters(self, tmp_path):
        """Test read_file with content containing special characters."""
        test_file = tmp_path / "special.txt"
        special_content = "Line with\ttabs\nLine with 'quotes'\nLine with \"double quotes\"\n$pecial ch@rs: !@#$%"
        test_file.write_text(special_content)

        result = await mcp.call_tool("read_file", {"path": str(test_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert output == special_content

    async def test_read_file_with_unicode(self, tmp_path):
        """Test read_file with unicode content."""
        test_file = tmp_path / "unicode.txt"
        unicode_content = "Hello 世界\nBonjour 🌍\n한글"
        test_file.write_text(unicode_content)

        result = await mcp.call_tool("read_file", {"path": str(test_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert output == unicode_content

    async def test_read_file_large_file(self, tmp_path):
        """Test read_file with a relatively large file."""
        test_file = tmp_path / "large.txt"
        # Create a file with 1000 lines
        large_content = "\n".join([f"Line {i}" for i in range(1000)])
        test_file.write_text(large_content)

        result = await mcp.call_tool("read_file", {"path": str(test_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert output == large_content
        assert "Line 0" in output
        assert "Line 999" in output

    async def test_read_file_remote_execution(self, mocker):
        """Test read_file with remote execution."""
        mock_content = "Remote file content\nLine 2\nLine 3"
        mock_execute_command = mocker.patch(
            "linux_mcp_server.tools.storage.execute_command", AsyncMock(return_value=(0, mock_content, ""))
        )

        result = await mcp.call_tool("read_file", {"path": "/remote/path/file.txt", "host": "remote.host.com"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert output == mock_content

        # Verify execute_command was called with correct arguments
        mock_execute_command.assert_called_once()
        args = mock_execute_command.call_args[0][0]
        assert args[0] == "cat"
        assert args[1] == "/remote/path/file.txt"
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.host.com"

    async def test_read_file_remote_command_failure(self, mocker):
        """Test read_file handles command failures for remote execution."""
        mocker.patch(
            "linux_mcp_server.tools.storage.execute_command",
            AsyncMock((1, "", "cat: /remote/file.txt: No such file or directory")),
        )

        with pytest.raises(ToolError, match="Error executing tool read_file"):
            await mcp.call_tool("read_file", {"path": "/remote/file.txt", "host": "remote.host.com"})

    async def test_read_file_remote_skips_path_validation(self, mocker):
        """Test that remote execution skips local path validation."""
        mocker.patch(
            "linux_mcp_server.tools.storage.execute_command", AsyncMock(return_value=(0, "Remote content", ""))
        )

        # This path doesn't exist locally but should not raise an error for remote execution
        result = await mcp.call_tool("read_file", {"path": "/nonexistent/remote/file.txt", "host": "remote.server.com"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        # Should succeed even though path doesn't exist locally
        assert isinstance(result[0], list)

    async def test_read_file_remote_empty_output(self, mocker):
        """Test read_file with remote execution returning empty content."""
        mocker.patch("linux_mcp_server.tools.storage.execute_command", AsyncMock(return_value=(0, "", "")))

        result = await mcp.call_tool("read_file", {"path": "/remote/empty.txt", "host": "remote.host.com"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert output == ""

    async def test_read_file_with_relative_path(self, tmp_path):
        """Test read_file resolves relative paths correctly."""
        test_file = tmp_path / "test.txt"
        test_content = "Content"
        test_file.write_text(test_content)

        # Change to tmp_path directory and use relative path
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await mcp.call_tool("read_file", {"path": "test.txt"})

            assert isinstance(result, tuple)
            assert len(result) == 2
            assert isinstance(result[0], list)
            output = result[0][0].text

            assert output == test_content
        finally:
            os.chdir(original_cwd)

    async def test_read_file_with_symlink(self, tmp_path):
        """Test read_file follows symlinks correctly."""
        # Create a real file
        real_file = tmp_path / "real.txt"
        test_content = "Real content"
        real_file.write_text(test_content)

        # Create a symlink
        symlink_file = tmp_path / "link.txt"
        symlink_file.symlink_to(real_file)

        result = await mcp.call_tool("read_file", {"path": str(symlink_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert output == test_content
