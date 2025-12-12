"""Tests for storage tools."""

import os
import sys

from collections.abc import Callable
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import psutil
import pytest

from mcp.server.fastmcp.exceptions import ToolError

from linux_mcp_server.server import mcp
from linux_mcp_server.tools.storage import NodeEntry
from tests import verify_node_entries
from tests import verify_result_structure


@pytest.fixture
def setup_test_directory(tmp_path) -> Callable[[list[tuple[str, int, float]]], tuple[Path, list[NodeEntry]]]:
    """
    Factory fixture for creating test directories with subdirectories of specific sizes and modification times.

    Returns a function that accepts a list of (name, size, modified_time) tuples and:
    - Creates subdirectories with the specified sizes (by adding a file within each)
    - Sets their modification times
    - Returns the directory path and list of expected NodeEntry objects
    """

    def _create_directory(dir_specs: list[tuple[str, int, float]]) -> tuple[Path, list[NodeEntry]]:
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

            expected_entries.append(NodeEntry(name=name, size=size, modified=modified_time))

        return tmp_path, expected_entries

    return _create_directory


@pytest.fixture
def setup_test_files(tmp_path) -> Callable[[list[tuple[str, int, float]]], tuple[Path, list[NodeEntry]]]:
    """
    Factory fixture for creating test directories with subdirectories of specific sizes and modification times.

    Returns a function that accepts a list of (name, size, modified_time) tuples and:
    - Creates subdirectories with the specified sizes (by adding a file within each)
    - Sets their modification times
    - Returns the directory path and list of expected NodeEntry objects
    """

    def _create_files(dir_specs: list[tuple[str, int, float]]) -> tuple[Path, list[NodeEntry]]:
        """
        Create a directory structure with specified subdirectories.

        Args:
            dir_specs: List of (name, size, modified_time) tuples

        Returns:
            Tuple of (directory_path, expected_entries)
        """
        expected_entries = []

        for name, size, modified_time in dir_specs:
            content_file = tmp_path / name
            content_file.touch()

            # Create a file inside the directory to give it size
            if size > 0:
                content_file.write_text("x" * size)

            # Set modification time on the file itself
            os.utime(content_file, (modified_time, modified_time))

            expected_entries.append(NodeEntry(name=name, size=size, modified=modified_time))

        return tmp_path, expected_entries

    return _create_files


@pytest.fixture
def restricted_path(tmp_path):
    restricted_path = tmp_path / "restricted"
    restricted_path.mkdir()
    restricted_path.chmod(0o000)

    yield restricted_path

    restricted_path.chmod(0o755)


@pytest.fixture
def mock_disk_io_stats():
    """Fixture providing mock disk I/O statistics."""
    mock_stats = MagicMock(spec=psutil._pslinux.sdiskio)
    mock_stats.read_bytes = 1024 * 1024 * 1024  # 1 GB
    mock_stats.write_bytes = 512 * 1024 * 1024  # 512 MB
    mock_stats.read_count = 1000
    mock_stats.write_count = 500
    return {"sda": mock_stats}


@pytest.fixture
def mock_storage_execute_command(mock_execute_command_for):
    """Storage-specific execute_command mock using the shared factory."""
    return mock_execute_command_for("linux_mcp_server.tools.storage")


class TestListBlockDevices:
    """Test suite for list_block_devices tool."""

    @pytest.mark.parametrize(
        ("lsblk_output", "disk_io_stats", "expected_content", "io_stats_expected"),
        [
            pytest.param(
                "NAME   SIZE TYPE MOUNTPOINT FSTYPE MODEL\nsda    1TB  disk            \nsda1   512G part /          ext4",
                {},
                ["=== Block Devices ===", "sda", "sda1"],
                False,
                id="lsblk_success_no_io_stats",
            ),
            pytest.param(
                "NAME   SIZE TYPE MOUNTPOINT\nsda    1TB  disk",
                None,  # Will be replaced with mock_disk_io_stats fixture in test
                [
                    "=== Block Devices ===",
                    "sda",
                    "=== Disk I/O Statistics (per disk) ===",
                    "Read Count: 1000",
                    "Write Count: 500",
                ],
                True,
                id="lsblk_success_with_io_stats",
            ),
            pytest.param(
                "",
                {},
                ["=== Block Devices ==="],
                False,
                id="lsblk_success_empty_output",
            ),
        ],
    )
    async def test_list_block_devices_lsblk_success(
        self,
        mocker,
        lsblk_output,
        disk_io_stats,
        expected_content,
        io_stats_expected,
        mock_disk_io_stats,
        mock_storage_execute_command,
    ):
        """Test list_block_devices with successful lsblk command and various disk I/O scenarios."""
        # None in parameterization signals "use the mock_disk_io_stats fixture"
        # This keeps parameterization clean while reusing shared fixture data
        if disk_io_stats is None:
            disk_io_stats = mock_disk_io_stats

        mock_storage_execute_command.return_value = (0, lsblk_output, "")
        mocker.patch("linux_mcp_server.tools.storage.psutil.disk_io_counters", return_value=disk_io_stats)

        result = await mcp.call_tool("list_block_devices", {})
        output = verify_result_structure(result)

        # Verify expected content
        for content in expected_content:
            assert content in output

        # Verify I/O stats presence/absence
        if io_stats_expected:
            assert "=== Disk I/O Statistics (per disk) ===" in output
        else:
            assert "=== Disk I/O Statistics (per disk) ===" not in output

        # Verify lsblk was called with correct arguments
        mock_storage_execute_command.assert_called_once()
        args = mock_storage_execute_command.call_args[0][0]
        assert args[0] == "lsblk"
        assert "-o" in args

    @pytest.mark.parametrize(
        ("execute_side_effect", "partition_device", "partition_mountpoint", "partition_fstype", "expected_header"),
        [
            pytest.param(
                AsyncMock(return_value=(1, "", "command failed")),
                "/dev/sda1",
                "/",
                "ext4",
                "=== Block Devices (fallback) ===",
                id="lsblk_non_zero_returncode",
            ),
            pytest.param(
                FileNotFoundError("lsblk not found"),
                "/dev/nvme0n1p1",
                "/boot",
                "vfat",
                "=== Block Devices ===",
                id="lsblk_file_not_found",
            ),
        ],
    )
    async def test_list_block_devices_psutil_fallback(
        self,
        mocker,
        execute_side_effect,
        partition_device,
        partition_mountpoint,
        partition_fstype,
        expected_header,
    ):
        """Test list_block_devices falls back to psutil when lsblk is unavailable or fails."""
        # Mock execute_command to fail in different ways
        mocker.patch("linux_mcp_server.tools.storage.execute_command", side_effect=execute_side_effect)

        # Create mock partition with test-specific values
        # Use spec from an actual partition instance to catch typos while satisfying type checker
        real_partitions = psutil.disk_partitions()
        spec_source = real_partitions[0] if real_partitions else None
        mock_partition = MagicMock(spec=spec_source)
        mock_partition.device = partition_device
        mock_partition.mountpoint = partition_mountpoint
        mock_partition.fstype = partition_fstype
        mock_partition.opts = "rw,relatime"

        mocker.patch("linux_mcp_server.tools.storage.psutil.disk_partitions", return_value=[mock_partition])

        result = await mcp.call_tool("list_block_devices", {})
        output = verify_result_structure(result)

        # Verify fallback behavior
        assert expected_header in output
        assert partition_device in output
        assert f"Mountpoint: {partition_mountpoint}" in output
        assert f"Filesystem: {partition_fstype}" in output
        assert "Options: rw,relatime" in output

    async def test_list_block_devices_remote_execution(self, mocker, mock_disk_io_stats, mock_storage_execute_command):
        """Test list_block_devices with remote execution (no disk I/O stats)."""
        mock_storage_execute_command.return_value = (0, "NAME   SIZE TYPE\nsda    1TB  disk", "")

        # Mock disk I/O counters to verify they're not used for remote execution
        mocker.patch("linux_mcp_server.tools.storage.psutil.disk_io_counters", return_value=mock_disk_io_stats)

        result = await mcp.call_tool("list_block_devices", {"host": "remote.host.com"})
        output = verify_result_structure(result)

        # Verify remote execution behavior
        assert "=== Block Devices ===" in output
        assert "sda" in output
        assert "=== Disk I/O Statistics" not in output

        # Verify execute_command was called with host parameter
        mock_storage_execute_command.assert_called_once()
        call_kwargs = mock_storage_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.host.com"

    async def test_list_block_devices_exception_handling(self, mock_storage_execute_command):
        """Test list_block_devices handles general exceptions."""
        mock_storage_execute_command.side_effect = ValueError("Raised intentionally")

        with pytest.raises(ToolError, match="Raised intentionally"):
            await mcp.call_tool("list_block_devices", {})


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListDirectories:
    """Test suite for list_directories tool."""

    # Test data for sorting tests - (order_by, sort, dir_specs, expected_entries)
    SORT_TEST_CASES = [
        pytest.param(
            "name",
            "ascending",
            [("alpha", 100, 1000.0), ("beta", 200, 2000.0), ("gamma", 300, 3000.0)],
            [
                NodeEntry(name="alpha", size=0, modified=0.0),
                NodeEntry(name="beta", size=0, modified=0.0),
                NodeEntry(name="gamma", size=0, modified=0.0),
            ],
            id="name_ascending",
        ),
        pytest.param(
            "name",
            "descending",
            [("alpha", 100, 1000.0), ("beta", 200, 2000.0), ("gamma", 300, 3000.0)],
            [
                NodeEntry(name="gamma", size=0, modified=0.0),
                NodeEntry(name="beta", size=0, modified=0.0),
                NodeEntry(name="alpha", size=0, modified=0.0),
            ],
            id="name_descending",
        ),
        pytest.param(
            "size",
            "ascending",
            [("small", 100, 1000.0), ("large", 300, 3000.0), ("medium", 200, 2000.0)],
            [
                NodeEntry(name="small", size=100, modified=0.0),
                NodeEntry(name="medium", size=200, modified=0.0),
                NodeEntry(name="large", size=300, modified=0.0),
            ],
            id="size_ascending",
        ),
        pytest.param(
            "size",
            "descending",
            [("small", 100, 1000.0), ("large", 300, 3000.0), ("medium", 200, 2000.0)],
            [
                NodeEntry(name="large", size=300, modified=0.0),
                NodeEntry(name="medium", size=200, modified=0.0),
                NodeEntry(name="small", size=100, modified=0.0),
            ],
            id="size_descending",
        ),
        pytest.param(
            "modified",
            "ascending",
            [("newest", 0, 3000.0), ("oldest", 100, 1000.0), ("middle", 100, 2000.0)],
            [
                NodeEntry(name="oldest", size=0, modified=1000.0),
                NodeEntry(name="middle", size=0, modified=2000.0),
                NodeEntry(name="newest", size=0, modified=3000.0),
            ],
            id="modified_ascending",
        ),
        pytest.param(
            "modified",
            "descending",
            [("newest", 100, 3000.0), ("oldest", 100, 1000.0), ("middle", 100, 2000.0)],
            [
                NodeEntry(name="newest", size=0, modified=3000.0),
                NodeEntry(name="middle", size=0, modified=2000.0),
                NodeEntry(name="oldest", size=0, modified=1000.0),
            ],
            id="modified_descending",
        ),
    ]

    # Test data for top_n tests - (order_by, sort, top_n, dir_specs, expected_entries)
    TOP_N_TEST_CASES = [
        pytest.param(
            "name",
            "ascending",
            2,
            [("alpha", 100, 1000.0), ("beta", 200, 2000.0), ("gamma", 300, 3000.0)],
            [
                NodeEntry(name="alpha", size=0, modified=0.0),
                NodeEntry(name="beta", size=0, modified=0.0),
            ],
            id="name_top_n",
        ),
        pytest.param(
            "modified",
            "ascending",
            2,
            [("newest", 100, 3000.0), ("oldest", 100, 1000.0), ("middle", 100, 2000.0)],
            [
                NodeEntry(name="oldest", size=0, modified=1000.0),
                NodeEntry(name="middle", size=0, modified=2000.0),
            ],
            id="modified_top_n",
        ),
        pytest.param(
            "size",
            "descending",
            2,
            [("small", 100, 1000.0), ("large", 300, 3000.0), ("medium", 200, 2000.0), ("tiny", 50, 500.0)],
            [
                NodeEntry(name="large", size=300, modified=0.0),
                NodeEntry(name="medium", size=200, modified=0.0),
            ],
            id="size_descending_top_n",
        ),
    ]

    # Test data for remote execution - (order_by, mock_output, expected_entries)
    REMOTE_EXECUTION_CASES = [
        pytest.param(
            "size",
            "100\t/remote/path/small\n300\t/remote/path/large\n200\t/remote/path/medium\n500\t/remote/path",
            [
                NodeEntry(name="small", size=100, modified=0.0),
                NodeEntry(name="medium", size=200, modified=0.0),
                NodeEntry(name="large", size=300, modified=0.0),
            ],
            id="remote_size",
        ),
        pytest.param(
            "name",
            "gamma\nalpha\nbeta",
            [
                NodeEntry(name="alpha", size=0, modified=0.0),
                NodeEntry(name="beta", size=0, modified=0.0),
                NodeEntry(name="gamma", size=0, modified=0.0),
            ],
            id="remote_name",
        ),
        pytest.param(
            "modified",
            "3000.0\tnewest\n1000.0\toldest\n2000.0\tmiddle",
            [
                NodeEntry(name="oldest", size=0, modified=1000.0),
                NodeEntry(name="middle", size=0, modified=2000.0),
                NodeEntry(name="newest", size=0, modified=3000.0),
            ],
            id="remote_modified",
        ),
    ]

    async def test_list_directories_returns_structured_output(self, setup_test_directory):
        """Test that list_directories returns structured output."""
        test_path, _ = setup_test_directory([("alpha", 100, 1000.0)])

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": "name"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        assert "result" in result[1]
        assert isinstance(result[1]["result"], list)

    @pytest.mark.parametrize(("order_by", "sort", "dir_specs", "expected_entries"), SORT_TEST_CASES)
    async def test_list_directories_sorting(self, setup_test_directory, order_by, sort, dir_specs, expected_entries):
        """Test list_directories with various sorting options."""
        test_path, _ = setup_test_directory(dir_specs)

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": order_by, "sort": sort})

        verify_node_entries(result, expected_entries)

    @pytest.mark.parametrize(("order_by", "sort", "top_n", "dir_specs", "expected_entries"), TOP_N_TEST_CASES)
    async def test_list_directories_with_top_n(
        self, setup_test_directory, order_by, sort, top_n, dir_specs, expected_entries
    ):
        """Test list_directories with top_n limit."""
        test_path, _ = setup_test_directory(dir_specs)

        result = await mcp.call_tool(
            "list_directories", {"path": str(test_path), "order_by": order_by, "sort": sort, "top_n": top_n}
        )

        verify_node_entries(result, expected_entries)

    @pytest.mark.parametrize("order_by", ["name", "size", "modified"])
    async def test_list_directories_empty_directory(self, tmp_path, order_by):
        """Test list_directories with empty directory."""
        result = await mcp.call_tool("list_directories", {"path": str(tmp_path), "order_by": order_by})

        verify_node_entries(result, [])

    @pytest.mark.parametrize(
        ("param", "value", "match"),
        [
            pytest.param("order_by", "invalid", "1 validation error", id="invalid_order_by"),
            pytest.param("sort", "invalid", "1 validation error", id="invalid_sort"),
        ],
    )
    async def test_list_directories_invalid_params(self, tmp_path, param, value, match):
        """Test list_directories with invalid parameters."""
        with pytest.raises(ToolError, match=match):
            await mcp.call_tool("list_directories", {"path": str(tmp_path), param: value})

    async def test_list_directories_invalid_path(self, tmp_path):
        """Test with non-existent path raises ToolError."""
        non_existent_path = tmp_path / "non_existent_directory"
        with pytest.raises(ToolError, match="Path does not exist or cannot be resolved"):
            await mcp.call_tool("list_directories", {"path": str(non_existent_path), "order_by": "name"})

    async def test_list_directories_handles_permission_denied(self, restricted_path):
        """Test handling of permission denied errors gracefully."""
        with pytest.raises(ToolError, match="Permission denied to read"):
            await mcp.call_tool("list_directories", {"path": str(restricted_path)})

    async def test_list_directories_special_characters_in_names(self, setup_test_directory):
        """Test list_directories handles directory names with special characters."""
        dir_specs = [
            ("dir with spaces", 100, 1000.0),
            ("dir-with-dashes", 200, 2000.0),
            ("dir_with_underscores", 300, 3000.0),
        ]
        test_path, _ = setup_test_directory(dir_specs)

        result = await mcp.call_tool("list_directories", {"path": str(test_path), "order_by": "name"})

        # Expected order is alphabetical (space < hyphen < underscore in ASCII)
        expected = [NodeEntry(name=n, size=0, modified=0.0) for n in sorted(n for n, _, _ in dir_specs)]
        verify_node_entries(result, expected)

    @pytest.mark.parametrize(("order_by", "mock_output", "expected_entries"), REMOTE_EXECUTION_CASES)
    async def test_list_directories_remote_execution(
        self, mock_storage_execute_command, order_by, mock_output, expected_entries
    ):
        """Test list_directories with remote execution."""
        mock_storage_execute_command.return_value = (0, mock_output, "")

        result = await mcp.call_tool(
            "list_directories",
            {"path": "/remote/path", "order_by": order_by, "host": "remote.server.com"},
        )

        verify_node_entries(result, expected_entries)

        # Verify execute_command was called with host
        mock_storage_execute_command.assert_called_once()
        assert mock_storage_execute_command.call_args[1]["host"] == "remote.server.com"

    async def test_list_directories_remote_skips_path_validation(self, mock_storage_execute_command):
        """Test that remote execution skips local path validation."""
        mock_storage_execute_command.return_value = (0, "100\t/nonexistent/path", "")

        # This path doesn't exist locally but should not raise an error for remote execution
        result = await mcp.call_tool(
            "list_directories",
            {"path": "/nonexistent/remote/path", "order_by": "size", "host": "remote.server.com"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        assert "result" in result[1]

    @pytest.mark.parametrize("order_by", ["size", "name", "modified"])
    async def test_list_directories_command_failure(self, mock_storage_execute_command, order_by):
        """Test list_directories handles command failures."""
        mock_storage_execute_command.return_value = (1, "", "command failed")

        with pytest.raises(ToolError, match="Error executing tool list_directories"):
            await mcp.call_tool(
                "list_directories",
                {"path": "/some/path", "order_by": order_by, "host": "remote.server.com"},
            )


@pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of coreutils/findutils")
class TestListFiles:
    """Test suite for list_files tool."""

    # Test data for sorting tests - (order_by, sort, file_specs, expected_entries)
    SORT_TEST_CASES = [
        pytest.param(
            "name",
            "ascending",
            [("alpha", 100, 1000.0), ("beta", 200, 2000.0), ("gamma", 300, 3000.0)],
            [
                NodeEntry(name="alpha", size=0, modified=0.0),
                NodeEntry(name="beta", size=0, modified=0.0),
                NodeEntry(name="gamma", size=0, modified=0.0),
            ],
            id="name_ascending",
        ),
        pytest.param(
            "name",
            "descending",
            [("alpha", 100, 1000.0), ("beta", 200, 2000.0), ("gamma", 300, 3000.0)],
            [
                NodeEntry(name="gamma", size=0, modified=0.0),
                NodeEntry(name="beta", size=0, modified=0.0),
                NodeEntry(name="alpha", size=0, modified=0.0),
            ],
            id="name_descending",
        ),
        pytest.param(
            "size",
            "ascending",
            [("small", 100, 1000.0), ("large", 300, 3000.0), ("medium", 200, 2000.0)],
            [
                NodeEntry(name="small", size=100, modified=0.0),
                NodeEntry(name="medium", size=200, modified=0.0),
                NodeEntry(name="large", size=300, modified=0.0),
            ],
            id="size_ascending",
        ),
        pytest.param(
            "size",
            "descending",
            [("small", 100, 1000.0), ("large", 300, 3000.0), ("medium", 200, 2000.0)],
            [
                NodeEntry(name="large", size=300, modified=0.0),
                NodeEntry(name="medium", size=200, modified=0.0),
                NodeEntry(name="small", size=100, modified=0.0),
            ],
            id="size_descending",
        ),
        pytest.param(
            "modified",
            "ascending",
            [("newest", 0, 3000.0), ("oldest", 100, 1000.0), ("middle", 100, 2000.0)],
            [
                NodeEntry(name="oldest", size=0, modified=1000.0),
                NodeEntry(name="middle", size=0, modified=2000.0),
                NodeEntry(name="newest", size=0, modified=3000.0),
            ],
            id="modified_ascending",
        ),
        pytest.param(
            "modified",
            "descending",
            [("newest", 100, 3000.0), ("oldest", 100, 1000.0), ("middle", 100, 2000.0)],
            [
                NodeEntry(name="newest", size=0, modified=3000.0),
                NodeEntry(name="middle", size=0, modified=2000.0),
                NodeEntry(name="oldest", size=0, modified=1000.0),
            ],
            id="modified_descending",
        ),
    ]

    # Test data for top_n tests - (order_by, sort, top_n, file_specs, expected_entries)
    TOP_N_TEST_CASES = [
        pytest.param(
            "name",
            "ascending",
            2,
            [("alpha", 100, 1000.0), ("beta", 200, 2000.0), ("gamma", 300, 3000.0)],
            [
                NodeEntry(name="alpha", size=0, modified=0.0),
                NodeEntry(name="beta", size=0, modified=0.0),
            ],
            id="name_top_n",
        ),
        pytest.param(
            "modified",
            "ascending",
            2,
            [("newest", 100, 3000.0), ("oldest", 100, 1000.0), ("middle", 100, 2000.0)],
            [
                NodeEntry(name="oldest", size=0, modified=1000.0),
                NodeEntry(name="middle", size=0, modified=2000.0),
            ],
            id="modified_top_n",
        ),
        pytest.param(
            "size",
            "descending",
            2,
            [("small", 100, 1000.0), ("large", 300, 3000.0), ("medium", 200, 2000.0), ("tiny", 50, 500.0)],
            [
                NodeEntry(name="large", size=300, modified=0.0),
                NodeEntry(name="medium", size=200, modified=0.0),
            ],
            id="size_descending_top_n",
        ),
    ]

    # Test data for remote execution - (order_by, mock_output, expected_entries)
    REMOTE_EXECUTION_CASES = [
        pytest.param(
            "size",
            "100\t/remote/path/small\n300\t/remote/path/large\n200\t/remote/path/medium\n500\t/remote/path",
            [
                NodeEntry(name="small", size=100, modified=0.0),
                NodeEntry(name="medium", size=200, modified=0.0),
                NodeEntry(name="large", size=300, modified=0.0),
            ],
            id="remote_size",
        ),
        pytest.param(
            "name",
            "gamma\nalpha\nbeta",
            [
                NodeEntry(name="alpha", size=0, modified=0.0),
                NodeEntry(name="beta", size=0, modified=0.0),
                NodeEntry(name="gamma", size=0, modified=0.0),
            ],
            id="remote_name",
        ),
        pytest.param(
            "modified",
            "3000.0\tnewest\n1000.0\toldest\n2000.0\tmiddle",
            [
                NodeEntry(name="oldest", size=0, modified=1000.0),
                NodeEntry(name="middle", size=0, modified=2000.0),
                NodeEntry(name="newest", size=0, modified=3000.0),
            ],
            id="remote_modified",
        ),
    ]

    async def test_list_files_returns_structured_output(self, setup_test_files):
        """Test that list_files returns structured output."""
        test_path, _ = setup_test_files([("alpha", 100, 1000.0)])

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": "name"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)
        assert "result" in result[1]
        assert isinstance(result[1]["result"], list)

    @pytest.mark.parametrize(("order_by", "sort", "file_specs", "expected_entries"), SORT_TEST_CASES)
    async def test_list_files_sorting(self, setup_test_files, order_by, sort, file_specs, expected_entries):
        """Test list_files with various sorting options."""
        test_path, _ = setup_test_files(file_specs)

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": order_by, "sort": sort})

        verify_node_entries(result, expected_entries)

    @pytest.mark.parametrize(("order_by", "sort", "top_n", "file_specs", "expected_entries"), TOP_N_TEST_CASES)
    async def test_list_files_with_top_n(self, setup_test_files, order_by, sort, top_n, file_specs, expected_entries):
        """Test list_files with top_n limit."""
        test_path, _ = setup_test_files(file_specs)

        result = await mcp.call_tool(
            "list_files", {"path": str(test_path), "order_by": order_by, "sort": sort, "top_n": top_n}
        )

        verify_node_entries(result, expected_entries)

    @pytest.mark.parametrize("order_by", ["name", "size", "modified"])
    async def test_list_files_empty_directory(self, tmp_path, order_by):
        """Test list_files with empty directory."""
        result = await mcp.call_tool("list_files", {"path": str(tmp_path), "order_by": order_by})

        verify_node_entries(result, [])

    @pytest.mark.parametrize(
        ("param", "value", "match"),
        [
            pytest.param("order_by", "invalid", "1 validation error", id="invalid_order_by"),
            pytest.param("sort", "invalid", "1 validation error", id="invalid_sort"),
        ],
    )
    async def test_list_files_invalid_params(self, tmp_path, param, value, match):
        """Test list_files with invalid parameters."""
        with pytest.raises(ToolError, match=match):
            await mcp.call_tool("list_files", {"path": str(tmp_path), param: value})

    async def test_list_files_invalid_path(self, tmp_path):
        """Test with non-existent path raises ToolError."""
        non_existent_path = tmp_path / "non_existent_directory"
        with pytest.raises(ToolError, match="Path does not exist or cannot be resolved"):
            await mcp.call_tool("list_files", {"path": str(non_existent_path), "order_by": "name"})

    async def test_list_files_handles_permission_denied(self, restricted_path):
        """Test handling of permission denied errors gracefully."""
        with pytest.raises(ToolError, match="Permission denied to read"):
            await mcp.call_tool("list_files", {"path": str(restricted_path)})

    async def test_list_files_special_characters_in_names(self, setup_test_files):
        """Test list_files handles file names with special characters."""
        file_specs = [
            ("file with spaces", 100, 1000.0),
            ("file-with-dashes", 200, 2000.0),
            ("file_with_underscores", 300, 3000.0),
        ]
        test_path, _ = setup_test_files(file_specs)

        result = await mcp.call_tool("list_files", {"path": str(test_path), "order_by": "name"})

        # Expected order is alphabetical (space < hyphen < underscore in ASCII)
        expected = [NodeEntry(name=n, size=0, modified=0.0) for n in sorted(n for n, _, _ in file_specs)]
        verify_node_entries(result, expected)

    @pytest.mark.parametrize(("order_by", "mock_output", "expected_entries"), REMOTE_EXECUTION_CASES)
    async def test_list_files_remote_execution(
        self, mock_storage_execute_command, order_by, mock_output, expected_entries
    ):
        """Test list_files with remote execution."""
        mock_storage_execute_command.return_value = (0, mock_output, "")

        result = await mcp.call_tool(
            "list_files",
            {"path": "/remote/path", "order_by": order_by, "host": "remote.server.com"},
        )

        verify_node_entries(result, expected_entries)

        # Verify execute_command was called with host
        mock_storage_execute_command.assert_called_once()
        assert mock_storage_execute_command.call_args[1]["host"] == "remote.server.com"

    async def test_list_files_remote_skips_path_validation(self, mock_storage_execute_command):
        """Test that remote execution skips local path validation."""
        mock_storage_execute_command.return_value = (0, "100\t/nonexistent/path", "")

        # This path doesn't exist locally but should not raise an error for remote execution
        result = await mcp.call_tool(
            "list_files",
            {"path": "/nonexistent/remote/path", "order_by": "size", "host": "remote.server.com"},
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[1], dict)

    @pytest.mark.parametrize("order_by", ["size", "name", "modified"])
    async def test_list_files_command_failure(self, mock_storage_execute_command, order_by):
        """Test list_files handles command failures."""
        mock_storage_execute_command.return_value = (1, "", "command failed")

        with pytest.raises(ToolError, match="Error executing tool list_files"):
            await mcp.call_tool(
                "list_files",
                {"path": "/some/path", "order_by": order_by, "host": "remote.server.com"},
            )


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
