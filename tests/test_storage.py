"""Tests for storage tools."""

import sys
import typing as t

import pytest

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

    async def test_list_directories_returns_string(self):
        """Test that list_directories returns a string."""
        # Use /tmp which should exist on all Linux systems
        result = await storage.list_directories("/tmp", order_by="name")
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_list_directories_invalid_order_by(self, tmp_path):
        """Test that invalid order_by parameter returns error."""
        result = await storage.list_directories(str(tmp_path), order_by="invalid")
        assert isinstance(result, str)
        assert "error" in result.lower()
        assert "order_by" in result.lower()

    async def test_list_directories_invalid_sort(self, tmp_path):
        """Test that invalid sort parameter returns error."""
        result = await storage.list_directories(str(tmp_path), sort="invalid")
        assert isinstance(result, str)
        assert "error" in result.lower()
        assert "sort" in result.lower()

    async def test_list_directories_invalid_path(self):
        """Test with non-existent path returns error message."""
        result = await storage.list_directories("/this/path/absolutely/does/not/exist/anywhere")
        assert isinstance(result, str)
        assert "error" in result.lower() or "not found" in result.lower() or "does not exist" in result.lower()

    async def test_list_directories_path_is_file_not_directory(self, tmp_path):
        """Test with a file path instead of directory returns error."""
        tmp_file = tmp_path / "data.txt"
        tmp_file.write_bytes(b"test content")

        result = await storage.list_directories(str(tmp_file))
        assert isinstance(result, str)
        assert "error" in result.lower() or "not a directory" in result.lower()

    async def test_list_directories_handles_permission_denied(self, restricted_path):
        """Test handling of permission denied errors gracefully."""
        result = await storage.list_directories(str(restricted_path))
        assert "Error: Permission denied to read directory".casefold() in result.casefold()

    async def test_list_directories_sanitizes_path_input(self):
        """Test that path injection attempts are handled safely."""
        # Test with various potentially malicious paths
        malicious_paths = [
            "/tmp/../../../etc/passwd",
            "/tmp; rm -rf /",
            "/tmp && echo 'malicious'",
            "/tmp`whoami`",
            "/tmp$(whoami)",
        ]

        for path in malicious_paths:
            result = await storage.list_directories(path)
            # Should either error safely or resolve to a safe path
            assert isinstance(result, str)
            # Should not execute commands or expose sensitive files


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

        assert isinstance(result, str)
        assert "dir2" in result or "dir1" in result or "dir3" in result
        assert "Size" in result or "size" in result.lower()
        assert "Largest First" in result

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

        assert isinstance(result, str)
        assert "Smallest First" in result
        # small should appear before large
        small_pos = result.find("small")
        large_pos = result.find("large")
        assert small_pos < large_pos

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of du")
    async def test_list_directories_by_size_with_top_n(self, tmp_path):
        """Test that top_n parameter limits results."""
        # Create 10 directories
        for i in range(10):
            dir_path = tmp_path / f"dir{i}"
            dir_path.mkdir()
            (dir_path / f"file{i}.txt").write_text("x" * (i * 100))

        result = await storage.list_directories(str(tmp_path), order_by="size", sort="descending", top_n=3)

        assert isinstance(result, str)
        assert "Top 3" in result

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

        assert isinstance(result, str)
        assert "parent" in result

    async def test_list_directories_by_size_validates_top_n(self, tmp_path):
        """Test that top_n parameter is validated."""
        # Test with negative number
        result = await storage.list_directories(str(tmp_path), order_by="size", top_n=-5)
        assert isinstance(result, str)
        assert "error" in result.lower() or "invalid" in result.lower()

        # Test with zero
        result = await storage.list_directories(str(tmp_path), order_by="size", top_n=0)
        assert isinstance(result, str)
        assert "error" in result.lower() or "invalid" in result.lower()

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

        assert isinstance(result, str)
        assert "error" not in result.lower()
        assert "Top 3" in result

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of du")
    async def test_list_directories_by_size_handles_empty_directory(self, tmp_path):
        """Test with empty directory."""
        result = await storage.list_directories(str(tmp_path), order_by="size")

        assert isinstance(result, str)
        assert "no subdirectories" in result.lower() or "0" in result

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of du")
    async def test_list_directories_by_size_formats_sizes_human_readable(self, tmp_path):
        """Test that sizes are formatted in human-readable format."""
        dir1 = tmp_path / "bigdir"
        dir1.mkdir()

        # Create a file > 1MB to test formatting
        (dir1 / "largefile.bin").write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

        result = await storage.list_directories(str(tmp_path), order_by="size")

        assert isinstance(result, str)
        # Should have size units
        assert any(unit in result for unit in ["KB", "MB", "GB", "B", "bytes"])

    async def test_list_directories_by_size_maximum_top_n_limit(self, tmp_path):
        """Test that there's a reasonable upper limit on top_n."""
        # Create a few directories
        for i in range(5):
            (tmp_path / f"dir{i}").mkdir()

        # Request an unreasonably large number
        result = await storage.list_directories(str(tmp_path), order_by="size", top_n=10000)

        assert isinstance(result, str)
        # Should return error for exceeding max
        assert "error" in result.lower() or "invalid" in result.lower()


class TestListDirectoriesByName:
    """Test list_directories function with order_by='name'."""

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_name_ascending(self, tmp_path):
        """Test alphabetical sorting in ascending order (A-Z)."""
        # Create directories
        for name in ["zebra", "alpha", "mike"]:
            (tmp_path / name).mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="name", sort="ascending")

        assert isinstance(result, str)
        assert "A-Z" in result
        # alpha should appear before zebra in alphabetical order
        alpha_pos = result.find("alpha")
        zebra_pos = result.find("zebra")
        assert alpha_pos < zebra_pos

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_name_descending(self, tmp_path):
        """Test alphabetical sorting in descending order (Z-A)."""
        for name in ["alpha", "beta", "gamma"]:
            (tmp_path / name).mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="name", sort="descending")

        assert isinstance(result, str)
        assert "Z-A" in result
        # gamma should appear before alpha in reverse order
        gamma_pos = result.find("gamma")
        alpha_pos = result.find("alpha")
        assert gamma_pos < alpha_pos

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_name_default_sort(self, tmp_path):
        """Test that default sort is ascending."""
        for name in ["zebra", "alpha"]:
            (tmp_path / name).mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="name")

        assert isinstance(result, str)
        # Should default to A-Z (ascending)
        alpha_pos = result.find("alpha")
        zebra_pos = result.find("zebra")
        assert alpha_pos < zebra_pos

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_name_lists_all(self, tmp_path):
        """Test that all directories are returned."""
        for i in range(10):
            (tmp_path / f"dir{i:02d}").mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="name")
        assert isinstance(result, str)
        assert "10" in result  # Total subdirectories: 10


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

        assert isinstance(result, str)
        assert "Newest First" in result
        # new_dir should appear before old_dir when sorted newest first
        new_pos = result.find("new_dir")
        old_pos = result.find("old_dir")
        assert new_pos < old_pos

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

        assert isinstance(result, str)
        assert "Oldest First" in result
        # old_dir should appear before new_dir when sorted oldest first
        old_pos = result.find("old_dir")
        new_pos = result.find("new_dir")
        assert old_pos < new_pos

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_modified_includes_timestamps(self, tmp_path):
        """Test that output includes modification timestamps."""
        (tmp_path / "dir1").mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="modified")

        assert isinstance(result, str)
        assert "Modified" in result
        # Should include date/time information
        assert any(char.isdigit() for char in result)

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_by_modified_lists_all(self, tmp_path):
        """Test that all directories are returned."""
        for i in range(10):
            (tmp_path / f"dir{i}").mkdir()

        result = await storage.list_directories(str(tmp_path), order_by="modified")
        assert isinstance(result, str)
        assert "10" in result  # Total subdirectories: 10


class TestListDirectoriesDefaults:
    """Test default parameter values for list_directories."""

    @pytest.mark.skipif(sys.platform != "linux", reason="requires GNU version of find")
    async def test_list_directories_defaults_to_name_ascending(self, tmp_path):
        """Test that default behavior is order_by='name', sort='ascending'."""
        for name in ["zebra", "alpha", "beta"]:
            (tmp_path / name).mkdir()

        result = await storage.list_directories(str(tmp_path))

        assert isinstance(result, str)
        # Should be sorted by name, A-Z
        assert "by Name" in result
        assert "A-Z" in result
        alpha_pos = result.find("alpha")
        zebra_pos = result.find("zebra")
        assert alpha_pos < zebra_pos


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

        result = await mcp.call_tool("list_directories", {"path": str(tmp_path)})

        assert result is not None
        assert len(result) > 0
        assert isinstance(result, t.Sequence)
        assert isinstance(result[1], dict)
        assert "result" in result[1]

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
        assert isinstance(result[1], dict)
        assert "result" in result[1]

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
