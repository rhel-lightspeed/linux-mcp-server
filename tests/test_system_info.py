"""Tests for system information tools."""

import pytest
from linux_mcp_server.tools import system_info


class TestSystemInfo:
    """Test system information tools."""

    @pytest.mark.asyncio
    async def test_get_system_info_returns_string(self):
        """Test that get_system_info returns a string."""
        result = await system_info.get_system_info()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_system_info_contains_key_information(self):
        """Test that system info contains essential data."""
        result = await system_info.get_system_info()
        
        # Should contain key system information
        assert "Hostname" in result or "hostname" in result.lower()
        assert "Kernel" in result or "kernel" in result.lower()
        assert "OS" in result or "operating system" in result.lower()
        assert "Uptime" in result or "uptime" in result.lower()

    @pytest.mark.asyncio
    async def test_get_cpu_info_returns_string(self):
        """Test that get_cpu_info returns a string."""
        result = await system_info.get_cpu_info()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_cpu_info_contains_cpu_data(self):
        """Test that CPU info contains relevant data."""
        result = await system_info.get_cpu_info()
        
        # Should contain CPU information
        assert "CPU" in result or "cpu" in result.lower() or "processor" in result.lower()
        assert "load" in result.lower() or "usage" in result.lower()

    @pytest.mark.asyncio
    async def test_get_memory_info_returns_string(self):
        """Test that get_memory_info returns a string."""
        result = await system_info.get_memory_info()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_memory_info_contains_memory_data(self):
        """Test that memory info contains RAM and swap information."""
        result = await system_info.get_memory_info()
        
        # Should contain memory information
        assert "memory" in result.lower() or "ram" in result.lower()
        assert "total" in result.lower()
        assert "used" in result.lower() or "available" in result.lower()

    @pytest.mark.asyncio
    async def test_get_disk_usage_returns_string(self):
        """Test that get_disk_usage returns a string."""
        result = await system_info.get_disk_usage()
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_disk_usage_contains_filesystem_data(self):
        """Test that disk usage contains filesystem information."""
        result = await system_info.get_disk_usage()
        
        # Should contain disk usage information
        assert "filesystem" in result.lower() or "device" in result.lower() or "mounted" in result.lower()
        assert "/" in result  # Should at least show root filesystem

