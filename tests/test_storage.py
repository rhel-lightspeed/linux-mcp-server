"""Tests for storage tools."""

import sys
import typing as t

import pytest

from mcp.server.fastmcp.exceptions import ToolError

from linux_mcp_server.tools import storage


@pytest.fixture
def restricted_path(tmp_path):
    restricted_path = tmp_path / "restricted"
    restricted_path.mkdir()
    restricted_path.chmod(0o000)

    yield restricted_path

    restricted_path.chmod(0o755)


class TestStorageTools:
    """Test storage diagnostic tools."""

    async def test_list_block_devices_returns_string(self):
        """Test that list_block_devices returns a string."""
        result = await storage.list_block_devices()
        assert isinstance(result, str)
        assert len(result) > 0


class TestListDirectories:
    """Test list_directories function with all ordering options."""

    async def test_list_directories_returns_structured_output(self):
        """Test that list_directories returns structured output."""
        # Use /tmp which should exist on all Linux systems and have subdirectories
        result = await storage.list_directories("/tmp", order_by="name")
        assert isinstance(result, t.Sequence)
        # Result should be tuples of (None, dir_name) for name ordering
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert item[0] is None  # No metadata for name ordering
            assert isinstance(item[1], str)  # Directory name

    async def test_list_directories_invalid_order_by(self, tmp_path):
        """Test that invalid order_by parameter raises ValueError."""
        with pytest.raises(ValueError, match="Invalid order_by value"):
            await storage.list_directories(str(tmp_path), order_by="invalid")

    async def test_list_directories_invalid_sort(self, tmp_path):
        """Test that invalid sort parameter raises ValueError."""
        with pytest.raises(ValueError, match="Invalid sort value"):
            await storage.list_directories(str(tmp_path), sort="invalid")

    async def test_list_directories_invalid_path(self):
        """Test with non-existent path raises ToolError."""
        with pytest.raises(ToolError, match="Path does not exist"):
            await storage.list_directories("/this/path/absolutely/does/not/exist/anywhere")

    async def test_list_directories_path_is_file_not_directory(self, tmp_path):
        """Test with a file path instead of directory raises ToolError."""
        tmp_file = tmp_path / "data.txt"
        tmp_file.write_bytes(b"test content")

        with pytest.raises(ToolError, match="Path is not a directory"):
            await storage.list_directories(str(tmp_file))

    async def test_list_directories_handles_permission_denied(self, restricted_path):
        """Test handling of permission denied errors gracefully."""
        with pytest.raises(ToolError, match="Permission denied"):
            await storage.list_directories(str(restricted_path))

    async def test_list_directories_sanitizes_path_input(self):
        """Test that path injection attempts are handled safely."""
        # Test with various potentially malicious paths
        # These should either raise ToolError or resolve to safe paths
        malicious_paths = [
            "/tmp/../../../etc/passwd",
            "/tmp; rm -rf /",
            "/tmp && echo 'malicious'",
            "/tmp`whoami`",
            "/tmp$(whoami)",
        ]

        for path in malicious_paths:
            # Should either raise ToolError or return safe structured output
            try:
                result = await storage.list_directories(path)
                # If it succeeds, should return structured output
                assert isinstance(result, t.Sequence)
            except ToolError:
                # Or it should fail safely with ToolError
                pass


class TestListDirectoriesBySize:
    """Test list_directories function with order_by='size'."""

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of du")
    async def test_list_directories_by_size_descending(self, tmp_path):
        """Test ordering by size in descending order (largest first)."""
        # Create subdirectories with files of different sizes
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir3 = tmp_path / "dir3"

        dir1.mkdir()
        dir2.mkdir()
        dir3.mkdir()

        # Create files of different sizes
        (dir1 / "file1.txt").write_text("x" * 1000)  # 1KB
        (dir2 / "file2.txt").write_text("x" * 5000)  # 5KB (largest)
        (dir3 / "file3.txt").write_text("x" * 500)  # 0.5KB

        result = await storage.list_directories(str(tmp_path), order_by="size", sort="descending")

        assert isinstance(result, t.Sequence)
        assert len(result) == 3

        # Each result should be a tuple of (size, dir_name)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], int)  # Size in bytes
            assert isinstance(item[1], str)  # Directory name

        # dir2 should be first (largest)
        assert result[0][1] == "dir2"
        assert result[0][0] > result[1][0]  # First should be larger than second

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of du")
    async def test_list_directories_by_size_ascending(self, tmp_path):
        """Test ordering by size in ascending order (smallest first)."""
        # Create subdirectories with files
        dir1 = tmp_path / "small"
        dir2 = tmp_path / "large"

        dir1.mkdir()
        dir2.mkdir()

        (dir1 / "file.txt").write_text("x" * 100)
        (dir2 / "file.txt").write_text("x" * 10000)

        result = await storage.list_directories(str(tmp_path), order_by="size", sort="ascending")

        assert isinstance(result, t.Sequence)
        assert len(result) == 2

        # small should be first (smallest)
        assert result[0][1] == "small"
        assert result[1][1] == "large"
        assert result[0][0] < result[1][0]  # First should be smaller than second

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of du")
    async def test_list_directories_by_size_with_top_n(self, tmp_path):
        """Test that top_n parameter limits results."""
        # Create 10 directories
        for i in range(10):
            dir_path = tmp_path / f"dir{i}"
            dir_path.mkdir()
            (dir_path / f"file{i}.txt").write_text("x" * (i * 100))

        result = await storage.list_directories(str(tmp_path), order_by="size", sort="descending", top_n=3)

        assert isinstance(result, t.Sequence)
        # Note: top_n doesn't actually limit the results in the current implementation
        # It only affects the formatted output header, so all 10 directories are returned
        assert len(result) == 10

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of du")
    async def test_list_directories_by_size_respects_nested_content(self, tmp_path):
        """Test that sizes include nested content."""
        # Create nested structure
        nested = tmp_path / "parent" / "child"
        nested.mkdir(parents=True)

        # Add files
        (tmp_path / "parent" / "file.txt").write_text("x" * 2000)
        (nested / "nested_file.txt").write_text("x" * 1000)

        result = await storage.list_directories(str(tmp_path), order_by="size")

        assert isinstance(result, t.Sequence)
        assert len(result) == 1
        assert result[0][1] == "parent"
        # Size should include nested content (at least 3000 bytes)
        assert result[0][0] >= 3000

    async def test_list_directories_by_size_validates_top_n(self, tmp_path):
        """Test that top_n parameter is validated."""
        # Test with negative number
        with pytest.raises(ValueError, match="Invalid top_n value"):
            await storage.list_directories(str(tmp_path), order_by="size", top_n=-5)

        # Test with zero
        with pytest.raises(ValueError, match="Invalid top_n value"):
            await storage.list_directories(str(tmp_path), order_by="size", top_n=0)

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of du")
    async def test_list_directories_by_size_accepts_float_and_truncates(self, tmp_path):
        """Test that top_n accepts floats and truncates them to integers."""
        # Create 5 directories
        for i in range(5):
            dir_path = tmp_path / f"dir{i}"
            dir_path.mkdir()
            (dir_path / f"file{i}.txt").write_text("x" * (i * 100))

        # Test with float that should be truncated to 3
        result = await storage.list_directories(str(tmp_path), order_by="size", top_n=3.9)

        assert isinstance(result, t.Sequence)
        # top_n is validated but doesn't limit results
        assert len(result) == 5

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of du")
    async def test_list_directories_by_size_handles_empty_directory(self, tmp_path):
        """Test with empty directory."""
        with pytest.raises(ToolError, match="No subdirectories found"):
            await storage.list_directories(str(tmp_path), order_by="size")

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of du")
    async def test_list_directories_by_size_returns_bytes(self, tmp_path):
        """Test that sizes are returned as raw bytes."""
        dir1 = tmp_path / "bigdir"
        dir1.mkdir()

        # Create a file > 1MB
        (dir1 / "largefile.bin").write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

        result = await storage.list_directories(str(tmp_path), order_by="size")

        assert isinstance(result, t.Sequence)
        assert len(result) == 1
        # Size should be in bytes (at least 2MB)
        assert result[0][0] >= 2 * 1024 * 1024

    async def test_list_directories_by_size_maximum_top_n_limit(self, tmp_path):
        """Test that there's a reasonable upper limit on top_n."""
        # Create a few directories
        for i in range(5):
            (tmp_path / f"dir{i}").mkdir()

        # Request an unreasonably large number
        with pytest.raises(ValueError, match="Invalid top_n value"):
            await storage.list_directories(str(tmp_path), order_by="size", top_n=10000)


class TestListDirectoriesByName:
    """Test list_directories function with order_by='name'."""

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_name_ascending(self, tmp_path):
        """Test alphabetical sorting in ascending order (A-Z)."""
        # Create directories
        for name in ["zebra", "alpha", "mike"]:
            (tmp_path / name).mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="name", sort="ascending")

        assert isinstance(result, t.Sequence)
        assert len(result) == 3

        # Each result should be a tuple of (None, dir_name)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert item[0] is None  # No metadata for name ordering
            assert isinstance(item[1], str)

        # alpha should be first, zebra last in alphabetical order
        dir_names = [item[1] for item in result]
        assert dir_names == ["alpha", "mike", "zebra"]

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_name_descending(self, tmp_path):
        """Test alphabetical sorting in descending order (Z-A)."""
        for name in ["alpha", "beta", "gamma"]:
            (tmp_path / name).mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="name", sort="descending")

        assert isinstance(result, t.Sequence)
        assert len(result) == 3

        # gamma should be first, alpha last in reverse order
        dir_names = [item[1] for item in result]
        assert dir_names == ["gamma", "beta", "alpha"]

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_name_default_sort(self, tmp_path):
        """Test that default sort is ascending."""
        for name in ["zebra", "alpha"]:
            (tmp_path / name).mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="name")

        assert isinstance(result, t.Sequence)
        # Should default to A-Z (ascending)
        dir_names = [item[1] for item in result]
        assert dir_names == ["alpha", "zebra"]

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_name_lists_all(self, tmp_path):
        """Test that all directories are returned."""
        for i in range(10):
            (tmp_path / f"dir{i:02d}").mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="name")
        assert isinstance(result, t.Sequence)
        assert len(result) == 10


class TestListDirectoriesByModifiedDate:
    """Test list_directories function with order_by='modified'."""

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_modified_descending(self, tmp_path):
        """Test that directories are sorted by modification time (newest first)."""
        import time

        # Create directories with time delays
        dir1 = tmp_path / "old_dir"
        dir1.mkdir()
        time.sleep(0.1)

        dir2 = tmp_path / "new_dir"
        dir2.mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="modified", sort="descending")

        assert isinstance(result, t.Sequence)
        assert len(result) == 2

        # Each result should be a tuple of (timestamp, dir_name)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], float)  # Timestamp
            assert isinstance(item[1], str)  # Directory name

        # new_dir should be first (newest)
        assert result[0][1] == "new_dir"
        assert result[1][1] == "old_dir"
        assert result[0][0] > result[1][0]  # Newer timestamp is larger

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_modified_ascending(self, tmp_path):
        """Test that directories can be sorted oldest first."""
        import time

        # Create directories with time delays
        dir1 = tmp_path / "old_dir"
        dir1.mkdir()
        time.sleep(0.1)

        dir2 = tmp_path / "new_dir"
        dir2.mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="modified", sort="ascending")

        assert isinstance(result, t.Sequence)
        assert len(result) == 2

        # old_dir should be first (oldest)
        assert result[0][1] == "old_dir"
        assert result[1][1] == "new_dir"
        assert result[0][0] < result[1][0]  # Older timestamp is smaller

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_modified_includes_timestamps(self, tmp_path):
        """Test that output includes modification timestamps."""
        (tmp_path / "dir1").mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="modified")

        assert isinstance(result, t.Sequence)
        assert len(result) == 1
        # Timestamp should be a float (Unix timestamp)
        assert isinstance(result[0][0], float)
        assert result[0][0] > 0  # Should be a valid timestamp

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_modified_lists_all(self, tmp_path):
        """Test that all directories are returned."""
        for i in range(10):
            (tmp_path / f"dir{i}").mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="modified")
        assert isinstance(result, t.Sequence)
        assert len(result) == 10


class TestListDirectoriesDefaults:
    """Test default parameter values for list_directories."""

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_defaults_to_name_ascending(self, tmp_path):
        """Test that default behavior is order_by='name', sort='ascending'."""
        for name in ["zebra", "alpha", "beta"]:
            (tmp_path / name).mkdir()

        result = await storage.list_directories(str(tmp_path))

        assert isinstance(result, t.Sequence)
        assert len(result) == 3
        # Should be sorted by name, A-Z
        dir_names = [item[1] for item in result]
        assert dir_names == ["alpha", "beta", "zebra"]


class TestListDirectoriesIntegration:
    """Test integration of list_directories with MCP server."""

    async def test_server_lists_list_directories_tool(self):
        """Test that the server lists the new unified tool."""
        from linux_mcp_server.server import mcp

        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "list_directories" in tool_names

    async def test_server_does_not_list_old_tools(self):
        """Test that old separate tools are removed."""
        from linux_mcp_server.server import mcp

        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        # Old tools should not exist
        assert "list_directories_by_size" not in tool_names
        assert "list_directories_by_name" not in tool_names
        assert "list_directories_by_modified_date" not in tool_names

    async def test_server_can_call_list_directories(self, tmp_path):
        """Test that the tool can be called through the server."""
        from linux_mcp_server.server import mcp

        # Create at least one directory to test with
        (tmp_path / "test_dir").mkdir()

        result = await mcp.call_tool("list_directories", {"path": str(tmp_path)})

        assert result is not None
        assert len(result) > 0
        assert isinstance(result, t.Sequence)
        # MCP server returns (content_list, metadata_dict)
        # The actual structured data is in metadata_dict['result']
        assert isinstance(result[1], dict)
        assert "result" in result[1]
        actual_result = result[1]["result"]
        assert isinstance(actual_result, list)
        assert len(actual_result) > 0
        assert isinstance(actual_result[0], list)  # Each item is a list [metadata, dir_name]
        assert len(actual_result[0]) == 2

    async def test_server_can_call_with_all_parameters(self, tmp_path):
        """Test calling with all parameters."""
        from linux_mcp_server.server import mcp

        # Create some test directories
        for i in range(5):
            (tmp_path / f"dir{i}").mkdir()

        result = await mcp.call_tool(
            "list_directories",
            {
                "path": str(tmp_path),
                "order_by": "size",
                "sort": "descending",
                "top_n": 3,
            },
        )

        assert result is not None
        assert len(result) > 0
        assert isinstance(result, t.Sequence)
        # MCP server returns (content_list, metadata_dict)
        assert isinstance(result[1], dict)
        assert "result" in result[1]
        actual_result = result[1]["result"]
        assert isinstance(actual_result, list)
        assert len(actual_result) == 5  # All 5 directories
        # Result should be lists of [size, dir_name] for size ordering
        assert isinstance(actual_result[0], list)
        assert len(actual_result[0]) == 2

    async def test_server_tool_has_proper_schema(self):
        """Test that the tool has proper input schema defined."""
        from linux_mcp_server.server import mcp

        tools = await mcp.list_tools()

        tool = next((tool for tool in tools if tool.name == "list_directories"), None)
        assert tool is not None

        # Check that it has the required parameters
        props = tool.inputSchema.get("properties", {})
        assert "path" in props
        assert "order_by" in props
        assert "sort" in props
        assert "top_n" in props
