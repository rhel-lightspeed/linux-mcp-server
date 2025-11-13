"""Tests for process management tools."""

import os

from linux_mcp_server.tools import processes


class TestProcesses:
    """Test process management tools."""

    async def test_list_processes_returns_string(self):
        """Test that list_processes returns a string."""
        result = await processes.list_processes()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_list_processes_contains_process_info(self):
        """Test that list_processes contains process information."""
        result = await processes.list_processes()

        # Should contain process-related keywords
        assert "pid" in result.lower() or "process" in result.lower()
        # Should contain resource usage info
        assert "cpu" in result.lower() or "memory" in result.lower() or "mem" in result.lower()

    async def test_get_process_info_with_current_process(self):
        """Test getting info about the current process."""
        current_pid = os.getpid()
        result = await processes.get_process_info(current_pid)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain the PID
        assert str(current_pid) in result

    async def test_get_process_info_with_init_process(self):
        """Test getting info about init process (PID 1)."""
        result = await processes.get_process_info(1)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain process information
        assert "1" in result or "systemd" in result.lower() or "init" in result.lower()

    async def test_get_process_info_with_nonexistent_process(self):
        """Test getting info about a non-existent process."""
        # Use a very high PID that likely doesn't exist
        result = await processes.get_process_info(999999)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should handle gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower() or "error" in result.lower()
