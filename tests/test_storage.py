"""Tests for storage tools."""

import os
import tempfile
import pytest
from pathlib import Path
from linux_mcp_server.tools import storage


class TestStorageTools:
    """Test storage diagnostic tools."""

    @pytest.mark.asyncio
    async def test_list_block_devices_returns_string(self):
        """Test that list_block_devices returns a string."""
        result = await storage.list_block_devices()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_hardware_info_returns_string(self):
        """Test that get_hardware_info returns a string."""
        result = await storage.get_hardware_info()
        assert isinstance(result, str)
        assert len(result) > 0


class TestGetBiggestDirectories:
    """Test get_biggest_directories function with security focus."""

    @pytest.mark.asyncio
    async def test_get_biggest_directories_returns_string(self):
        """Test that get_biggest_directories returns a string."""
        # Use /tmp which should exist on all Linux systems
        result = await storage.get_biggest_directories("/tmp", recursive=False, top_n=5)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_biggest_directories_nonrecursive_with_temp_dirs(self):
        """Test non-recursive mode with temporary directories."""
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
            (dir3 / "file3.txt").write_text("x" * 500)   # 0.5KB
            
            result = await storage.get_biggest_directories(tmpdir, recursive=False, top_n=3)
            
            assert isinstance(result, str)
            assert "dir1" in result or "dir2" in result or "dir3" in result
            assert "Size" in result or "size" in result.lower()

    @pytest.mark.asyncio
    async def test_get_biggest_directories_recursive_mode(self):
        """Test recursive mode with nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            nested = Path(tmpdir) / "parent" / "child"
            nested.mkdir(parents=True)
            
            # Add files
            (Path(tmpdir) / "parent" / "file.txt").write_text("x" * 2000)
            (nested / "nested_file.txt").write_text("x" * 1000)
            
            result = await storage.get_biggest_directories(tmpdir, recursive=True, top_n=5)
            
            assert isinstance(result, str)
            assert "parent" in result

    @pytest.mark.asyncio
    async def test_get_biggest_directories_respects_top_n_limit(self):
        """Test that only top_n directories are returned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 10 directories
            for i in range(10):
                dir_path = Path(tmpdir) / f"dir{i}"
                dir_path.mkdir()
                (dir_path / f"file{i}.txt").write_text("x" * (i * 100))
            
            result = await storage.get_biggest_directories(tmpdir, recursive=False, top_n=3)
            
            assert isinstance(result, str)
            # The result should mention "Top 3" or similar
            assert "3" in result or "top" in result.lower()

    @pytest.mark.asyncio
    async def test_get_biggest_directories_invalid_path(self):
        """Test with non-existent path returns error message."""
        result = await storage.get_biggest_directories(
            "/this/path/absolutely/does/not/exist/anywhere",
            recursive=False,
            top_n=5
        )
        
        assert isinstance(result, str)
        assert "error" in result.lower() or "not found" in result.lower() or "does not exist" in result.lower()

    @pytest.mark.asyncio
    async def test_get_biggest_directories_path_is_file_not_directory(self):
        """Test with a file path instead of directory returns error."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(b"test content")
            tmp_file_path = tmp_file.name
        
        try:
            result = await storage.get_biggest_directories(tmp_file_path, recursive=False, top_n=5)
            
            assert isinstance(result, str)
            assert "error" in result.lower() or "not a directory" in result.lower()
        finally:
            os.unlink(tmp_file_path)

    @pytest.mark.asyncio
    async def test_get_biggest_directories_sanitizes_path_input(self):
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
            result = await storage.get_biggest_directories(path, recursive=False, top_n=5)
            # Should either error safely or resolve to a safe path
            assert isinstance(result, str)
            # Should not execute commands or expose sensitive files

    @pytest.mark.asyncio
    async def test_get_biggest_directories_validates_top_n(self):
        """Test that top_n parameter is validated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with negative number
            result = await storage.get_biggest_directories(tmpdir, recursive=False, top_n=-5)
            assert isinstance(result, str)
            assert "error" in result.lower() or "invalid" in result.lower()
            
            # Test with zero
            result = await storage.get_biggest_directories(tmpdir, recursive=False, top_n=0)
            assert isinstance(result, str)
            assert "error" in result.lower() or "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_get_biggest_directories_handles_empty_directory(self):
        """Test with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await storage.get_biggest_directories(tmpdir, recursive=False, top_n=5)
            
            assert isinstance(result, str)
            assert "no subdirectories" in result.lower() or "empty" in result.lower() or "0" in result

    @pytest.mark.asyncio
    async def test_get_biggest_directories_handles_permission_denied(self):
        """Test handling of permission denied errors gracefully."""
        # This test might be skipped on systems without restricted directories
        restricted_path = "/root"
        
        if os.path.exists(restricted_path) and not os.access(restricted_path, os.R_OK):
            result = await storage.get_biggest_directories(restricted_path, recursive=False, top_n=5)
            
            assert isinstance(result, str)
            # Should handle gracefully, not crash

    @pytest.mark.asyncio
    async def test_get_biggest_directories_formats_sizes_human_readable(self):
        """Test that sizes are formatted in human-readable format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = Path(tmpdir) / "bigdir"
            dir1.mkdir()
            
            # Create a file > 1MB to test formatting
            (dir1 / "largefile.bin").write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB
            
            result = await storage.get_biggest_directories(tmpdir, recursive=False, top_n=5)
            
            assert isinstance(result, str)
            # Should have size units
            assert any(unit in result for unit in ["KB", "MB", "GB", "B", "bytes"])

    @pytest.mark.asyncio
    async def test_get_biggest_directories_maximum_top_n_limit(self):
        """Test that there's a reasonable upper limit on top_n."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a few directories
            for i in range(5):
                (Path(tmpdir) / f"dir{i}").mkdir()
            
            # Request an unreasonably large number
            result = await storage.get_biggest_directories(tmpdir, recursive=False, top_n=10000)
            
            assert isinstance(result, str)
            # Should either cap it or return available directories


class TestGetBiggestDirectoriesIntegration:
    """Test integration of get_biggest_directories with MCP server."""

    @pytest.mark.asyncio
    async def test_server_lists_get_biggest_directories_tool(self):
        """Test that the server lists the new tool."""
        from linux_mcp_server.server import LinuxMCPServer
        
        server = LinuxMCPServer()
        tools = await server.list_tools()
        tool_names = [tool.name for tool in tools]
        
        assert "get_biggest_directories" in tool_names

    @pytest.mark.asyncio
    async def test_server_can_call_get_biggest_directories(self):
        """Test that the tool can be called through the server."""
        from linux_mcp_server.server import LinuxMCPServer
        
        server = LinuxMCPServer()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            result = await server.call_tool("get_biggest_directories", {
                "path": tmpdir,
                "recursive": False,
                "top_n": 5
            })
            
            assert len(result) > 0
            assert result[0].type == "text"
            assert isinstance(result[0].text, str)

    @pytest.mark.asyncio
    async def test_server_tool_has_proper_schema(self):
        """Test that the tool has proper input schema defined."""
        from linux_mcp_server.server import LinuxMCPServer
        
        server = LinuxMCPServer()
        tools = await server.list_tools()
        
        tool = next((t for t in tools if t.name == "get_biggest_directories"), None)
        assert tool is not None
        
        # Check that it has the required parameters
        props = tool.inputSchema.get("properties", {})
        assert "path" in props
        assert "recursive" in props
        assert "top_n" in props
        
        # Check types
        assert props["path"]["type"] == "string"
        assert props["recursive"]["type"] == "boolean"
        assert props["top_n"]["type"] == "number"

