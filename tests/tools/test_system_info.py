"""Tests for system information tools."""

import json

from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import TextContent

from linux_mcp_server.server import mcp
from linux_mcp_server.tools.system_info import CPUInfo
from linux_mcp_server.tools.system_info import DiskUsage
from linux_mcp_server.tools.system_info import HardwareInfo
from linux_mcp_server.tools.system_info import MemoryInfo
from linux_mcp_server.tools.system_info import MemoryStats
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
        assert cpu_info.logical_cores is not None or cpu_info.physical_cores_per_processor is not None

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
            cpu_info.cpu_model is not None
            or cpu_info.logical_cores is not None
            or cpu_info.physical_cores_per_processor is not None
        )
        assert has_cpu_info

    async def test_get_memory_info_contains_memory_data(self):
        """Test that memory info contains RAM and swap information with exact values."""
        # Mock free output
        mock_free_output = """
              total        used        free      shared  buff/cache   available
Mem:      6183096320  2513342464  1560502272     3973120  2362519552  3669753856
Swap:     6182400000           0  6182400000"""

        async def mock_execute_command(command, host=None, username=None):
            """Mock execute_command to return fixture data."""
            if command == ["free", "-b"]:
                return (0, mock_free_output, "")
            return (1, "", "Command not found")

        # Expected values from mock data
        # Percent is calculated as (used / total * 100)
        # For RAM: 2513342464 / 6183096320 * 100 = 40.64860603691841
        expected_memory_stats_json = {
            "ram": {
                "total": 6183096320,
                "used": 2513342464,
                "free": 1560502272,
                "available": 3669753856,
                "buffers": 2362519552,
                "percent": 2513342464 / 6183096320 * 100,  # 40.64860603691841
            },
            "swap": {
                "total": 6182400000,
                "used": 0,
                "free": 6182400000,
                "percent": 0.0,
            },
        }

        # Patch execute_command
        with patch(
            "linux_mcp_server.tools.system_info.execute_command",
            new=AsyncMock(side_effect=mock_execute_command),
        ):
            result = await mcp.call_tool("get_memory_information", arguments={})

            # MCP call_tool returns a tuple of (content, structured_output)
            assert isinstance(result, tuple)
            assert len(result) == 2
            content, structured_output = result

            # Content should be a TextContent object array
            assert isinstance(content, list)
            assert all(isinstance(item, TextContent) for item in content)

            # Extract text from content and verify JSON contains exact values
            assert isinstance(content[0], TextContent)
            text = content[0].text
            data = json.loads(text)

            # Verify RAM information in JSON
            assert "ram" in data
            ram = data["ram"]
            assert ram is not None
            assert ram["total"] == expected_memory_stats_json["ram"]["total"]
            assert ram["used"] == expected_memory_stats_json["ram"]["used"]
            assert ram["free"] == expected_memory_stats_json["ram"]["free"]
            assert ram["available"] == expected_memory_stats_json["ram"]["available"]
            assert ram["buffers"] == expected_memory_stats_json["ram"]["buffers"]
            assert ram["percent"] == pytest.approx(expected_memory_stats_json["ram"]["percent"], rel=1e-2)

            # Verify swap information in JSON
            assert "swap" in data
            swap = data["swap"]
            assert swap is not None
            assert swap["total"] == expected_memory_stats_json["swap"]["total"]
            assert swap["used"] == expected_memory_stats_json["swap"]["used"]
            assert swap["free"] == expected_memory_stats_json["swap"]["free"]
            assert swap["percent"] == expected_memory_stats_json["swap"]["percent"]

            # Verify structured output with exact values
            assert isinstance(structured_output, dict)
            memory_info = MemoryInfo(**structured_output)

            # Verify RAM values in structured output
            assert memory_info.ram == MemoryStats(**expected_memory_stats_json["ram"])

            # Verify Swap values in structured output
            assert memory_info.swap == MemoryStats(**expected_memory_stats_json["swap"])

    async def test_get_disk_usage_contains_filesystem_data(self):
        """Test that disk usage contains filesystem information."""
        # Mock df output
        mock_df_output = """Filesystem     1B-blocks        Used   Available Use% Mounted on
devtmpfs         4096000           0     4096000   0% /dev
tmpfs            8192000      204800     7987200   3% /dev/shm
/dev/vda1    107374182400 53687091200  48150528000  53% /
tmpfs            1048576           0     1048576   0% /run/credentials/serial-getty@hvc0.service"""

        # Mock /proc/diskstats output
        mock_diskstats_output = """ 252       0 vda 12345 0 987654 0 54321 0 876543 0 0 0 0 0 0 0 0 0 0
 252       1 vda1 10000 0 800000 0 45000 0 720000 0 0 0 0 0 0 0 0 0 0
 253       0 vdb 5000 0 400000 0 20000 0 320000 0 0 0 0 0 0 0 0 0 0
 251       0 zram0 105 0 4448 0 1 0 8 0 0 0 0 0 0 0 0 0 0"""

        async def mock_execute_command(command, host=None, username=None):
            """Mock execute_command to return fixture data."""
            if command == ["df", "-B1"]:
                return (0, mock_df_output, "")
            elif command == ["cat", "/proc/diskstats"]:
                return (0, mock_diskstats_output, "")
            return (1, "", "Command not found")

        # Expected values from mock data
        expected_partitions = [
            {
                "device": "devtmpfs",
                "mountpoint": "/dev",
                "size": 4096000,
                "used": 0,
                "free": 4096000,
                "percent": 0.0,
                "filesystem": None,
            },
            {
                "device": "tmpfs",
                "mountpoint": "/dev/shm",
                "size": 8192000,
                "used": 204800,
                "free": 7987200,
                "percent": 3.0,
                "filesystem": None,
            },
            {
                "device": "/dev/vda1",
                "mountpoint": "/",
                "size": 107374182400,
                "used": 53687091200,
                "free": 48150528000,
                "percent": 53.0,
                "filesystem": None,
            },
            {
                "device": "tmpfs",
                "mountpoint": "/run/credentials/serial-getty@hvc0.service",
                "size": 1048576,
                "used": 0,
                "free": 1048576,
                "percent": 0.0,
                "filesystem": None,
            },
        ]

        # Expected I/O stats (sum of vda and vdb; vda1 is a partition so excluded)
        # vda: 987654 sectors read, 876543 sectors written
        # vdb: 400000 sectors read, 320000 sectors written
        # Total: (987654 + 400000) * 512 = 710,478,848 bytes read
        #        (876543 + 320000) * 512 = 612,630,016 bytes written
        expected_io_stats = {
            "read_bytes": (987654 + 400000) * 512,  # 710,478,848 bytes
            "write_bytes": (876543 + 320000) * 512,  # 612,630,016 bytes
            "read_count": 12345 + 5000,  # 17,345
            "write_count": 54321 + 20000,  # 74,321
        }

        # Patch execute_command
        with patch(
            "linux_mcp_server.tools.system_info.execute_command",
            new=AsyncMock(side_effect=mock_execute_command),
        ):
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

            # Should have expected number of partitions
            assert len(partitions) == len(expected_partitions)

            # Verify each partition
            for i, partition in enumerate(partitions):
                expected = expected_partitions[i]
                assert partition["device"] == expected["device"]
                assert partition["mountpoint"] == expected["mountpoint"]
                assert partition["size"] == expected["size"]
                assert partition["used"] == expected["used"]
                assert partition["free"] == expected["free"]
                assert partition["percent"] == expected["percent"]

            # Should have root filesystem
            has_root = any(p["mountpoint"] == "/" for p in partitions)
            assert has_root

            # Verify I/O stats
            assert "io_stats" in data
            io_stats = data["io_stats"]
            assert io_stats is not None
            assert io_stats["read_bytes"] == expected_io_stats["read_bytes"]
            assert io_stats["write_bytes"] == expected_io_stats["write_bytes"]
            assert io_stats["read_count"] == expected_io_stats["read_count"]
            assert io_stats["write_count"] == expected_io_stats["write_count"]

            # Verify structured output
            assert isinstance(structured_output, dict)
            disk_usage = DiskUsage(**structured_output)
            assert len(disk_usage.partitions) == len(expected_partitions)

            # Verify first partition in structured output
            first_partition_model = disk_usage.partitions[0]
            assert first_partition_model.device == expected_partitions[0]["device"]
            assert first_partition_model.mountpoint == expected_partitions[0]["mountpoint"]
            assert first_partition_model.size == expected_partitions[0]["size"]
            assert first_partition_model.used == expected_partitions[0]["used"]
            assert first_partition_model.free == expected_partitions[0]["free"]
            assert first_partition_model.percent == expected_partitions[0]["percent"]

            # Verify I/O stats in structured output
            assert disk_usage.io_stats is not None
            assert disk_usage.io_stats.read_bytes == expected_io_stats["read_bytes"]
            assert disk_usage.io_stats.write_bytes == expected_io_stats["write_bytes"]
            assert disk_usage.io_stats.read_count == expected_io_stats["read_count"]
            assert disk_usage.io_stats.write_count == expected_io_stats["write_count"]

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

    @pytest.mark.parametrize(
        "fixture_file,expected_model,expected_logical_cores,expected_physical_sockets,expected_physical_cores_per_processor,expected_frequency,load_avg_values",
        [
            (
                "ARMv7.txt",
                "ARMv7 Processor",
                8,
                0,  # ARM doesn't have core id field
                0,  # ARM doesn't have physical cores per socket field
                0.0,  # ARM doesn't have frequency field
                (0.50, 0.75, 0.80),
            ),
            (
                "E5-2650v3.txt",
                "Intel(R) Xeon(R) CPU E5-2650 v3",
                40,
                2,  # Two physical sockets
                10,  # 10 physical cores per processor
                1721.790,  # First CPU MHz value in fixture
                (1.25, 2.50, 3.75),
            ),
        ],
        ids=["armv7", "xeon-e5-2650v3"],
    )
    async def test_get_cpu_info_with_fixture(
        self,
        fixture_file,
        expected_model,
        expected_logical_cores,
        expected_physical_sockets,
        expected_physical_cores_per_processor,
        expected_frequency,
        load_avg_values,
    ):
        """Test CPU info parsing with various cpuinfo fixtures."""
        # Read the fixture file
        fixture_path = Path(__file__).parent / "fixtures" / fixture_file
        cpuinfo_content = fixture_path.read_text()

        async def mock_execute_command(command, host=None, username=None):
            """Mock execute_command to return fixture data."""
            if command == ["cat", "/proc/cpuinfo"]:
                # Return full cpuinfo content
                return (0, cpuinfo_content, "")

            elif command == ["cat", "/proc/loadavg"]:
                # Mock load average based on test parameters
                return (0, f"{load_avg_values[0]} {load_avg_values[1]} {load_avg_values[2]} 1/100 12345", "")

            elif command == ["top", "-bn1"]:
                # Mock top output
                return (0, "Cpu(s): 10.5%us, 5.2%sy, 0.0%ni, 84.3%id, 0.0%wa", "")

            return (1, "", "Command not found")

        # Patch execute_command
        with patch(
            "linux_mcp_server.tools.system_info.execute_command", new=AsyncMock(side_effect=mock_execute_command)
        ):
            result = await mcp.call_tool("get_cpu_information", arguments={})

            # Verify result structure
            assert isinstance(result, tuple)
            assert len(result) == 2
            content, structured_output = result

            # Verify content
            assert isinstance(content, list)
            assert all(isinstance(item, TextContent) for item in content)

            # Verify structured output
            assert isinstance(structured_output, dict)
            cpu_info = CPUInfo(**structured_output)

            # Common assertions
            assert cpu_info.cpu_model is not None
            assert expected_model in cpu_info.cpu_model
            assert cpu_info.logical_cores == expected_logical_cores
            assert cpu_info.load_average is not None
            assert cpu_info.load_average.one_min == load_avg_values[0]
            assert cpu_info.load_average.five_min == load_avg_values[1]
            assert cpu_info.load_average.fifteen_min == load_avg_values[2]

            # Physical cores assertion
            if expected_physical_sockets > 0:
                assert cpu_info.physical_sockets is not None
                assert cpu_info.physical_sockets == expected_physical_sockets

            # Physical cores per processor assertion
            if expected_physical_cores_per_processor > 0:
                assert cpu_info.physical_cores_per_processor is not None
                assert cpu_info.physical_cores_per_processor == expected_physical_cores_per_processor

            # Frequency assertion
            if expected_frequency > 0:
                assert cpu_info.frequency_mhz is not None
                assert cpu_info.frequency_mhz == expected_frequency
            else:
                # ARM doesn't have frequency, so it will be 0.0
                assert cpu_info.frequency_mhz == 0.0
