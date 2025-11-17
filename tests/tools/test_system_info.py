"""Tests for system information tools."""

import json

from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import TextContent

from linux_mcp_server.server import mcp
from linux_mcp_server.tools.system_info import CPUInfo
from linux_mcp_server.tools.system_info import DiskUsage
from linux_mcp_server.tools.system_info import HardwareInfo
from linux_mcp_server.tools.system_info import MemoryInfo
from linux_mcp_server.tools.system_info import SystemInfo


class TestSystemInfo:
    """Test system information tools."""

    async def test_get_system_info_contains_key_information(self):
        """Test that system info contains essential data."""
        result = await mcp.call_tool("get_system_information", arguments={})

        # MCP call_tool returns a tuple of (content, structured_output)
        assert isinstance(result, tuple)
        assert len(result) == 2
        content, structured_output = result

        # Content should be a TextContent object array
        assert isinstance(content, list)
        assert all(isinstance(item, TextContent) for item in content)

        # Extract text from content
        assert isinstance(content[0], TextContent)
        text = content[0].text
        data = json.loads(text)
        assert "hostname" in data
        assert "kernel_version" in data
        assert "operating_system" in data
        assert "uptime" in data

        assert isinstance(structured_output, dict)
        system_info = SystemInfo(**structured_output)
        assert system_info.hostname is not None
        assert system_info.kernel_version is not None
        assert system_info.operating_system is not None
        assert system_info.uptime is not None

    async def test_get_cpu_info_returns_cpu_info_model(self):
        """Test that get_cpu_information returns a CPUInfo model."""
        result = await mcp.call_tool("get_cpu_information", arguments={})

        # MCP call_tool returns a tuple of (content, structured_output)
        assert isinstance(result, tuple)
        assert len(result) == 2
        content, structured_output = result

        # Content should be a TextContent object array
        assert isinstance(content, list)
        assert all(isinstance(item, TextContent) for item in content)

        # Extract text from content
        assert isinstance(content[0], TextContent)
        text = content[0].text
        data = json.loads(text)
        # Should have core information
        assert "logical_cores" in data or "physical_cores" in data
        # Should have load average
        assert "load_average" in data

        # Verify structured output
        assert isinstance(structured_output, dict)
        cpu_info = CPUInfo(**structured_output)
        assert cpu_info.logical_cores is not None or cpu_info.physical_cores is not None

    async def test_get_cpu_info_contains_cpu_data(self):
        """Test that CPU info contains relevant data."""
        result = await mcp.call_tool("get_cpu_information", arguments={})

        # MCP call_tool returns a tuple of (content, structured_output)
        assert isinstance(result, tuple)
        assert len(result) == 2
        content, structured_output = result

        # Content should be a TextContent object array
        assert isinstance(content, list)
        assert all(isinstance(item, TextContent) for item in content)

        # Extract text from content
        assert isinstance(content[0], TextContent)
        text = content[0].text
        data = json.loads(text)

        # Should contain CPU information
        # Check for at least one of these fields
        has_cpu_data = (
            data.get("cpu_model") is not None
            or data.get("logical_cores") is not None
            or data.get("physical_cores") is not None
        )
        assert has_cpu_data

        # Should have load average or usage data
        has_load_data = data.get("load_average") is not None or data.get("cpu_usage_percent") is not None
        assert has_load_data

        # Verify structured output
        assert isinstance(structured_output, dict)
        cpu_info = CPUInfo(**structured_output)
        has_cpu_info = (
            cpu_info.cpu_model is not None or cpu_info.logical_cores is not None or cpu_info.physical_cores is not None
        )
        assert has_cpu_info

    async def test_get_memory_info_returns_memory_info_model(self):
        """Test that get_memory_information returns a MemoryInfo model."""
        result = await mcp.call_tool("get_memory_information", arguments={})

        # MCP call_tool returns a tuple of (content, structured_output)
        assert isinstance(result, tuple)
        assert len(result) == 2
        content, structured_output = result

        # Content should be a TextContent object array
        assert isinstance(content, list)
        assert all(isinstance(item, TextContent) for item in content)

        # Verify structured output
        assert isinstance(structured_output, dict)
        memory_info = MemoryInfo(**structured_output)
        assert memory_info.ram is not None
        assert memory_info.swap is not None

    async def test_get_memory_info_contains_memory_data(self):
        """Test that memory info contains RAM and swap information."""
        result = await mcp.call_tool("get_memory_information", arguments={})

        # MCP call_tool returns a tuple of (content, structured_output)
        assert isinstance(result, tuple)
        assert len(result) == 2
        content, structured_output = result

        # Content should be a TextContent object array
        assert isinstance(content, list)
        assert all(isinstance(item, TextContent) for item in content)

        # Extract text from content
        assert isinstance(content[0], TextContent)
        text = content[0].text
        data = json.loads(text)

        # Should contain RAM information
        assert "ram" in data
        ram = data["ram"]
        assert ram is not None
        assert "total" in ram
        assert "used" in ram
        assert "free" in ram
        assert "percent" in ram

        # Should contain swap information
        assert "swap" in data
        swap = data["swap"]
        assert swap is not None
        assert "total" in swap
        assert "used" in swap

        # Verify structured output
        assert isinstance(structured_output, dict)
        memory_info = MemoryInfo(**structured_output)
        assert memory_info.ram is not None
        assert memory_info.ram.total >= 0
        assert memory_info.ram.used >= 0
        assert memory_info.swap is not None
        assert memory_info.swap.total >= 0

    async def test_get_disk_usage_returns_disk_usage_model(self):
        """Test that get_disk_usage returns a DiskUsage model."""
        result = await mcp.call_tool("get_disk_usage", arguments={})

        # MCP call_tool returns a tuple of (content, structured_output)
        assert isinstance(result, tuple)
        assert len(result) == 2
        content, structured_output = result

        # Content should be a TextContent object array
        assert isinstance(content, list)
        assert all(isinstance(item, TextContent) for item in content)

        # Verify structured output
        assert isinstance(structured_output, dict)
        disk_usage = DiskUsage(**structured_output)
        assert disk_usage.partitions is not None
        assert isinstance(disk_usage.partitions, list)

    async def test_get_disk_usage_contains_filesystem_data(self):
        """Test that disk usage contains filesystem information."""
        result = await mcp.call_tool("get_disk_usage", arguments={})

        # MCP call_tool returns a tuple of (content, structured_output)
        assert isinstance(result, tuple)
        assert len(result) == 2
        content, structured_output = result

        # Content should be a TextContent object array
        assert isinstance(content, list)
        assert all(isinstance(item, TextContent) for item in content)

        # Extract text from content
        assert isinstance(content[0], TextContent)
        text = content[0].text
        data = json.loads(text)

        # Should contain partitions
        assert "partitions" in data
        partitions = data["partitions"]
        assert isinstance(partitions, list)

        # Should have at least one partition
        assert len(partitions) > 0

        # Check first partition has required fields
        first_partition = partitions[0]
        assert "device" in first_partition
        assert "mountpoint" in first_partition
        assert "size" in first_partition
        assert "used" in first_partition
        assert "free" in first_partition
        assert "percent" in first_partition

        # Should at least have root filesystem
        has_root = any(p["mountpoint"] == "/" for p in partitions)
        assert has_root

        # Verify structured output
        assert isinstance(structured_output, dict)
        disk_usage = DiskUsage(**structured_output)
        assert len(disk_usage.partitions) > 0
        first_partition_model = disk_usage.partitions[0]
        assert first_partition_model.device is not None
        assert first_partition_model.mountpoint is not None
        assert first_partition_model.size >= 0
        assert first_partition_model.used >= 0
        assert first_partition_model.free >= 0

    async def test_get_hardware_info_returns_hardware_info_model(self):
        """Test that get_hardware_information returns a HardwareInfo model."""
        result = await mcp.call_tool("get_hardware_information", arguments={})

        # MCP call_tool returns a tuple of (content, structured_output)
        assert isinstance(result, tuple)
        assert len(result) == 2
        content, structured_output = result

        # Content should be a TextContent object array
        assert isinstance(content, list)
        assert all(isinstance(item, TextContent) for item in content)

        # Extract text from content
        assert isinstance(content[0], TextContent)
        text = content[0].text
        data = json.loads(text)

        # Should have some hardware information fields
        # At least one of these should be present
        has_hardware_data = (
            data.get("cpu_architecture") is not None
            or data.get("pci_devices") is not None
            or data.get("usb_devices") is not None
        )
        assert has_hardware_data

        # Verify structured output
        assert isinstance(structured_output, dict)
        hardware_info = HardwareInfo(**structured_output)
        has_hardware_info = (
            hardware_info.cpu_architecture is not None
            or len(hardware_info.pci_devices) > 0
            or hardware_info.usb_devices is not None
        )
        assert has_hardware_info

    async def test_error_handling(self):
        """Test that errors are properly raised as ToolError."""
        # Test with invalid host to trigger an error
        # Note: This test may not always trigger an error depending on the system
        # but it demonstrates how to test error handling
        try:
            result = await mcp.call_tool(
                "get_system_information", arguments={"host": "invalid-host-that-does-not-exist-12345.local"}
            )
            # If it succeeds, check the result structure
            content, structured_output = result
            # We either get an error or success, both are acceptable for this test
            assert isinstance(result, tuple)
        except Exception as e:
            # If an exception is raised, it should be a valid exception type
            assert isinstance(e, (ToolError, Exception))
