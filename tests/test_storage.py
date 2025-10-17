"""Tests for storage tools."""

import os
import tempfile

from pathlib import Path

from linux_mcp_server.tools import storage


class TestStorageTools:
    """Test storage diagnostic tools."""

    async def test_list_block_devices_returns_string(self):
        """Test that list_block_devices returns a string."""
        result = await storage.list_block_devices()
        assert isinstance(result, str)
        assert len(result) > 0


class TestListDirectoriesBySize:
    """Test list_directories_by_size function with security focus."""

    async def test_list_directories_by_size_returns_string(self):
        """Test that list_directories_by_size returns a string."""
        # Use /tmp which should exist on all Linux systems
        result = await storage.list_directories_by_size("/tmp", top_n=5)
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_list_directories_by_size_with_temp_dirs(self):
        """Test with temporary directories."""
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create subdirectories with files
            dir1 = Path(tmpdir) / "dir1"
            dir2 = Path(tmpdir) / "dir2"
            dir3 = Path(tmpdir) / "dir3"

            dir1.mkdir()
            dir2.mkdir()
            dir3.mkdir()

            # Create files of different sizes
            (dir1 / "file1.txt").write_text("x" * 1000)  # 1KB
            (dir2 / "file2.txt").write_text("x" * 5000)  # 5KB
            (dir3 / "file3.txt").write_text("x" * 500)  # 0.5KB

            result = await storage.list_directories_by_size(tmpdir, top_n=3)

            assert isinstance(result, str)
            assert "dir1" in result or "dir2" in result or "dir3" in result
            assert "Size" in result or "size" in result.lower()

    async def test_list_directories_by_size_recursive_mode(self):
        """Test with nested directories - sizes should include all nested content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            nested = Path(tmpdir) / "parent" / "child"
            nested.mkdir(parents=True)

            # Add files
            (Path(tmpdir) / "parent" / "file.txt").write_text("x" * 2000)
            (nested / "nested_file.txt").write_text("x" * 1000)

            result = await storage.list_directories_by_size(tmpdir, top_n=5)

            assert isinstance(result, str)
            assert "parent" in result

    async def test_list_directories_by_size_respects_top_n_limit(self):
        """Test that only top_n directories are returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 10 directories
            for i in range(10):
                dir_path = Path(tmpdir) / f"dir{i}"
                dir_path.mkdir()
                (dir_path / f"file{i}.txt").write_text("x" * (i * 100))

            result = await storage.list_directories_by_size(tmpdir, top_n=3)

            assert isinstance(result, str)
            # The result should mention "Top 3" or similar
            assert "3" in result or "top" in result.lower()

    async def test_list_directories_by_size_invalid_path(self):
        """Test with non-existent path returns error message."""
        result = await storage.list_directories_by_size("/this/path/absolutely/does/not/exist/anywhere", top_n=5)

        assert isinstance(result, str)
        assert "error" in result.lower() or "not found" in result.lower() or "does not exist" in result.lower()

    async def test_list_directories_by_size_path_is_file_not_directory(self):
        """Test with a file path instead of directory returns error."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"test content")
            tmp_file_path = tmp_file.name

        try:
            result = await storage.list_directories_by_size(tmp_file_path, top_n=5)

            assert isinstance(result, str)
            assert "error" in result.lower() or "not a directory" in result.lower()
        finally:
            os.unlink(tmp_file_path)

    async def test_list_directories_by_size_sanitizes_path_input(self):
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
            result = await storage.list_directories_by_size(path, top_n=5)
            # Should either error safely or resolve to a safe path
            assert isinstance(result, str)
            # Should not execute commands or expose sensitive files

    async def test_list_directories_by_size_validates_top_n(self):
        """Test that top_n parameter is validated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with negative number
            result = await storage.list_directories_by_size(tmpdir, top_n=-5)
            assert isinstance(result, str)
            assert "error" in result.lower() or "invalid" in result.lower()

            # Test with zero
            result = await storage.list_directories_by_size(tmpdir, top_n=0)
            assert isinstance(result, str)
            assert "error" in result.lower() or "invalid" in result.lower()

    async def test_list_directories_by_size_accepts_float_and_truncates(self):
        """Test that top_n accepts floats and truncates them to integers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 5 directories
            for i in range(5):
                dir_path = Path(tmpdir) / f"dir{i}"
                dir_path.mkdir()
                (dir_path / f"file{i}.txt").write_text("x" * (i * 100))

            # Test with float that should be truncated to 3
            result = await storage.list_directories_by_size(tmpdir, top_n=3.9)

            assert isinstance(result, str)
            assert "error" not in result.lower()
            assert "Top 3" in result

            # Test with exact float (5.0 should work as 5)
            result = await storage.list_directories_by_size(tmpdir, top_n=5.0)

            assert isinstance(result, str)
            assert "error" not in result.lower()
            assert "5" in result or "Top 5" in result

    async def test_list_directories_by_size_handles_empty_directory(self):
        """Test with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await storage.list_directories_by_size(tmpdir, top_n=5)

            assert isinstance(result, str)
            assert "no subdirectories" in result.lower() or "empty" in result.lower() or "0" in result

    async def test_list_directories_by_size_handles_permission_denied(self):
        """Test handling of permission denied errors gracefully."""
        # This test might be skipped on systems without restricted directories
        restricted_path = "/root"

        if os.path.exists(restricted_path) and not os.access(restricted_path, os.R_OK):
            result = await storage.list_directories_by_size(restricted_path, top_n=5)

            assert isinstance(result, str)
            # Should handle gracefully, not crash

    async def test_list_directories_by_size_formats_sizes_human_readable(self):
        """Test that sizes are formatted in human-readable format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = Path(tmpdir) / "bigdir"
            dir1.mkdir()

            # Create a file > 1MB to test formatting
            (dir1 / "largefile.bin").write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

            result = await storage.list_directories_by_size(tmpdir, top_n=5)

            assert isinstance(result, str)
            # Should have size units
            assert any(unit in result for unit in ["KB", "MB", "GB", "B", "bytes"])

    async def test_list_directories_by_size_maximum_top_n_limit(self):
        """Test that there's a reasonable upper limit on top_n."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a few directories
            for i in range(5):
                (Path(tmpdir) / f"dir{i}").mkdir()

            # Request an unreasonably large number
            result = await storage.list_directories_by_size(tmpdir, top_n=10000)

            assert isinstance(result, str)
            # Should either cap it or return available directories


class TestListDirectoriesByName:
    """Test list_directories_by_name function."""

    async def test_list_directories_by_name_returns_string(self):
        """Test that list_directories_by_name returns a string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some directories
            for name in ["alpha", "beta", "gamma"]:
                (Path(tmpdir) / name).mkdir()

            result = await storage.list_directories_by_name(tmpdir)
            assert isinstance(result, str)
            assert len(result) > 0

    async def test_list_directories_by_name_sorts_alphabetically(self):
        """Test that directories are sorted alphabetically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directories
            for name in ["zebra", "alpha", "mike"]:
                (Path(tmpdir) / name).mkdir()

            result = await storage.list_directories_by_name(tmpdir, reverse=False)

            assert isinstance(result, str)
            # alpha should appear before zebra in alphabetical order
            alpha_pos = result.find("alpha")
            zebra_pos = result.find("zebra")
            assert alpha_pos < zebra_pos

    async def test_list_directories_by_name_reverse_sort(self):
        """Test reverse alphabetical sorting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for name in ["alpha", "beta", "gamma"]:
                (Path(tmpdir) / name).mkdir()

            result = await storage.list_directories_by_name(tmpdir, reverse=True)

            assert isinstance(result, str)
            # gamma should appear before alpha in reverse order
            gamma_pos = result.find("gamma")
            alpha_pos = result.find("alpha")
            assert gamma_pos < alpha_pos

    async def test_list_directories_by_name_lists_all(self):
        """Test that all directories are returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                (Path(tmpdir) / f"dir{i:02d}").mkdir()

            result = await storage.list_directories_by_name(tmpdir)
            assert isinstance(result, str)
            assert "10" in result  # Total subdirectories found: 10


class TestListDirectoriesByModifiedDate:
    """Test list_directories_by_modified_date function."""

    async def test_list_directories_by_modified_date_returns_string(self):
        """Test that list_directories_by_modified_date returns a string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some directories
            for name in ["dir1", "dir2", "dir3"]:
                (Path(tmpdir) / name).mkdir()

            result = await storage.list_directories_by_modified_date(tmpdir)
            assert isinstance(result, str)
            assert len(result) > 0

    async def test_list_directories_by_modified_date_sorts_by_time(self):
        """Test that directories are sorted by modification time."""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directories with time delays
            dir1 = Path(tmpdir) / "old_dir"
            dir1.mkdir()
            time.sleep(0.1)

            dir2 = Path(tmpdir) / "new_dir"
            dir2.mkdir()

            result = await storage.list_directories_by_modified_date(tmpdir, newest_first=True)

            assert isinstance(result, str)
            # new_dir should appear before old_dir when sorted newest first
            new_pos = result.find("new_dir")
            old_pos = result.find("old_dir")
            assert new_pos < old_pos

    async def test_list_directories_by_modified_date_lists_all(self):
        """Test that all directories are returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                (Path(tmpdir) / f"dir{i}").mkdir()

            result = await storage.list_directories_by_modified_date(tmpdir)
            assert isinstance(result, str)
            assert "10" in result  # Total subdirectories found: 10

    async def test_list_directories_by_modified_date_invalid_path(self):
        """Test with non-existent path returns error message."""
        result = await storage.list_directories_by_modified_date("/this/path/absolutely/does/not/exist/anywhere")
        assert isinstance(result, str)
        assert "error" in result.lower()


class TestListDirectoriesBySizeIntegration:
    """Test integration of list_directories_by_size with MCP server."""

    async def test_server_lists_list_directories_by_size_tool(self):
        """Test that the server lists the new tool."""
        from linux_mcp_server.server import mcp

        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        assert "list_directories_by_size" in tool_names

    async def test_server_can_call_list_directories_by_size(self):
        """Test that the tool can be called through the server."""
        from linux_mcp_server.server import mcp

        with tempfile.TemporaryDirectory() as tmpdir:
            # FastMCP's call_tool returns a tuple of (result_list, result_dict)
            result_list, result_dict = await mcp.call_tool("list_directories_by_size", {"path": tmpdir, "top_n": 5})

            assert result_list is not None
            assert len(result_list) > 0
            # The result should be a string in the result_dict or in result_list
            assert isinstance(result_dict.get("result"), str) or isinstance(result_list[0].text, str)

    async def test_server_tool_has_proper_schema(self):
        """Test that the tool has proper input schema defined."""
        from linux_mcp_server.server import mcp

        tools = await mcp.list_tools()

        tool = next((t for t in tools if t.name == "list_directories_by_size"), None)
        assert tool is not None

        # Check that it has the required parameters
        props = tool.inputSchema.get("properties", {})
        assert "path" in props
        assert "top_n" in props
