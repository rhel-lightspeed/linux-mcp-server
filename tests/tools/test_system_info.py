"""Tests for system information tools."""

import pytest

from linux_mcp_server.tools import system_info


# =============================================================================
# Constants for assertion keywords
# =============================================================================

# Keywords indicating error/failure in function output
ERROR_INDICATORS = ("error", "not available", "failed", "unable")

# Keywords indicating permission-related issues
PERMISSION_ERROR_INDICATORS = ("permission denied", "requires root", "sudo", "root")

# =============================================================================
# Test data structures
# =============================================================================

# Maps info function names to (callable, expected_keywords) pairs.
# Each keyword group is a tuple of alternatives - if ANY keyword in the group
# matches (case-insensitive), the assertion passes. This allows flexible
# validation when output format may vary (e.g., "cpu" vs "processor").
#
# Example: [("cpu", "processor"), ("load",)] means:
#   - Result must contain either "cpu" OR "processor"
#   - Result must also contain "load"
INFO_FUNCTIONS = {
    "system": (
        system_info.get_system_information,
        [("hostname",), ("kernel",), ("os", "operating system"), ("uptime",)],
    ),
    "cpu": (
        system_info.get_cpu_information,
        [("cpu", "processor"), ("load", "usage")],
    ),
    "memory": (
        system_info.get_memory_information,
        [("memory", "ram"), ("total",), ("used", "available")],
    ),
    "disk": (
        system_info.get_disk_usage,
        [("filesystem", "device", "mounted")],
    ),
    "hardware": (
        system_info.get_hardware_information,
        [],  # No specific keywords to check
    ),
}

# Remote execution test data for SSH-based command execution.
# Structure: {name: (function, mock_responses, expected_substrings)}
#
# mock_responses: List of (return_code, stdout, stderr) tuples that will be
#   returned sequentially by the mocked execute_command function.
# expected_substrings: Strings that must appear in the function's output.
REMOTE_EXEC_CASES = {
    "system": (
        system_info.get_system_information,
        [
            (0, "testhost\n", ""),
            (0, 'PRETTY_NAME="Fedora Linux 40"\nVERSION_ID="40"\n', ""),
            (0, "6.8.0-300.fc40.x86_64\n", ""),
            (0, "x86_64\n", ""),
            (0, "up 2 days, 3 hours\n", ""),
            (0, "2024-01-15 10:30:00\n", ""),
        ],
        ["testhost", "Fedora Linux 40", "6.8.0", "x86_64"],
    ),
    "cpu": (
        system_info.get_cpu_information,
        [
            (0, "model name\t: AMD Ryzen 9 5950X\n", ""),
            (0, "32\n", ""),
            (0, "core id\t: 0\ncore id\t: 1\ncore id\t: 2\n", ""),
            (0, "cpu MHz\t\t: 3400.000\n", ""),
            (0, "0.50 0.45 0.40 1/500 12345\n", ""),
            (0, "%Cpu(s):  5.0 us,  2.0 sy\n", ""),
        ],
        ["AMD Ryzen 9 5950X", "32", "3400"],
    ),
    "memory": (
        system_info.get_memory_information,
        [
            (
                0,
                "              total        used        free      shared  buff/cache   available\n"
                "Mem:    16000000000  8000000000  4000000000   500000000  4000000000  7000000000\n"
                "Swap:    8000000000  1000000000  7000000000",
                "",
            ),
        ],
        ["RAM", "Total", "Used", "Swap"],
    ),
    "disk": (
        system_info.get_disk_usage,
        [
            (
                0,
                "Filesystem      Size  Used Avail Use% Mounted on\n"
                "/dev/sda1       100G   50G   50G  50% /\n"
                "/dev/sdb1       500G  100G  400G  20% /data",
                "",
            ),
        ],
        ["/", "/data", "Filesystem"],
    ),
    "hardware": (
        system_info.get_hardware_information,
        [
            (0, "Architecture: x86_64\nCPU(s): 16\n", ""),
            (0, "00:00.0 Host bridge: Intel\n00:02.0 VGA: Intel\n", ""),
            (0, "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation\n", ""),
            (0, "Memory Device\n  Size: 16 GB\n", ""),
        ],
        ["x86_64", "USB"],
    ),
}

# Exception handling test data for verifying graceful error handling.
# Structure: [(mock_target, function), ...]
#
# mock_target: The function/method to patch (relative to system_info module).
# function: The info function that should gracefully handle the exception.
#
# Each test patches the target to raise RuntimeError and verifies the info
# function returns an error message instead of propagating the exception.
EXCEPTION_CASES = [
    ("platform.node", system_info.get_system_information),
    ("psutil.cpu_count", system_info.get_cpu_information),
    ("psutil.virtual_memory", system_info.get_memory_information),
    ("psutil.disk_partitions", system_info.get_disk_usage),
    ("execute_command", system_info.get_hardware_information),
]


@pytest.fixture(params=INFO_FUNCTIONS.keys())
def info_func_with_keywords(request):
    """Fixture providing each info function with its expected keywords."""
    func, keywords = INFO_FUNCTIONS[request.param]
    return request.param, func, keywords


class TestSystemInfo:
    """Test system information tools."""

    async def test_returns_nonempty_string(self, info_func_with_keywords):
        """Test that info functions return non-empty strings."""
        name, func, _ = info_func_with_keywords
        result = await func()
        assert isinstance(result, str), f"{name} should return a string"
        assert len(result) > 0, f"{name} should return non-empty result"

    async def test_contains_expected_keywords(self, info_func_with_keywords):
        """Test that info functions contain expected keywords."""
        name, func, keywords = info_func_with_keywords
        if not keywords:
            pytest.skip(f"No keyword checks for {name}")

        result = await func()
        result_lower = result.lower()

        for keyword_group in keywords:
            assert any(kw in result_lower for kw in keyword_group), f"{name} should contain one of: {keyword_group}"

    async def test_disk_usage_shows_root(self):
        """Test that disk usage shows root filesystem."""
        result = await system_info.get_disk_usage()
        assert "/" in result, "Disk usage should show root filesystem"


class TestRemoteExecution:
    """Test remote execution paths via mocked SSH commands."""

    @pytest.fixture(params=REMOTE_EXEC_CASES.keys())
    def remote_case(self, request, mocker):
        """Fixture providing remote execution test cases with mocked execute_command."""
        func, responses, expected = REMOTE_EXEC_CASES[request.param]
        mock = mocker.patch("linux_mcp_server.tools.system_info.execute_command")
        mock.side_effect = responses
        return request.param, func, expected

    async def test_remote_execution(self, remote_case):
        """Test info gathering via remote SSH commands."""
        name, func, expected_strings = remote_case
        result = await func(host="remote.example.com")

        for expected in expected_strings:
            assert expected in result, f"{name}: expected '{expected}' in result"

    async def test_disk_usage_remote_fallback(self, mocker):
        """Test disk usage falls back to basic 'df' when --output fails."""
        mock = mocker.patch("linux_mcp_server.tools.system_info.execute_command")
        mock.side_effect = [
            (1, "", "df: unrecognized option '--output'"),
            (0, "Filesystem  Size  Used  Avail  Use%  Mounted\n/dev/sda1  100G  50G  50G  50%  /", ""),
        ]

        result = await system_info.get_disk_usage(host="remote.example.com")

        assert "/" in result
        assert "Filesystem" in result


class TestRemoteCommandFailures:
    """Test graceful handling of remote command failures."""

    @pytest.fixture
    def mock_execute(self, mocker):
        """Fixture to mock execute_command."""
        return mocker.patch("linux_mcp_server.tools.system_info.execute_command")

    async def test_system_info_handles_partial_failures(self, mock_execute):
        """Test that system info continues even if some commands fail."""
        mock_execute.side_effect = [
            (0, "testhost\n", ""),
            (1, "", "cat: /etc/os-release: No such file"),
            (0, "6.8.0\n", ""),
            (1, "", "command not found"),
            (0, "up 1 day\n", ""),
            (1, "", "error"),
        ]

        result = await system_info.get_system_information(host="remote.example.com")

        assert "testhost" in result
        assert "6.8.0" in result
        assert "up 1 day" in result

    async def test_memory_info_handles_empty_output(self, mock_execute):
        """Test memory info handles empty 'free' output gracefully."""
        mock_execute.return_value = (0, "", "")
        result = await system_info.get_memory_information(host="remote.example.com")
        assert isinstance(result, str)

    async def test_hardware_info_handles_missing_commands(self, mock_execute):
        """Test hardware info handles FileNotFoundError for missing commands."""
        mock_execute.side_effect = FileNotFoundError("lscpu not found")
        result = await system_info.get_hardware_information(host="remote.example.com")
        result_lower = result.lower()
        assert any(indicator in result_lower for indicator in ERROR_INDICATORS), (
            f"Expected error indicator in output, got: {result}"
        )

    async def test_hardware_info_permission_denied(self, mock_execute):
        """Test hardware info handles permission denied for dmidecode."""
        mock_execute.side_effect = [
            (0, "Architecture: x86_64\n", ""),
            (0, "00:00.0 Host bridge\n", ""),
            (0, "Bus 001 Device 001\n", ""),
            (1, "", "Permission denied"),
        ]

        result = await system_info.get_hardware_information(host="remote.example.com")
        result_lower = result.lower()

        # Successful commands should still appear in output
        assert "x86_64" in result
        # dmidecode failure should be gracefully handled with error context
        assert any(indicator in result_lower for indicator in PERMISSION_ERROR_INDICATORS), (
            f"Expected permission error indicator in output, got: {result}"
        )


class TestLocalExecutionEdgeCases:
    """Test edge cases in local execution paths."""

    async def test_system_info_without_os_release(self, mocker):
        """Test system info fallback when /etc/os-release doesn't exist."""
        mocker.patch("linux_mcp_server.tools.system_info.os.path.exists", return_value=False)
        mocker.patch("linux_mcp_server.tools.system_info.platform.system", return_value="Linux")
        mocker.patch("linux_mcp_server.tools.system_info.platform.release", return_value="6.8.0")

        result = await system_info.get_system_information()

        assert "Linux" in result
        assert "6.8.0" in result

    async def test_cpu_info_without_frequency(self, mocker):
        """Test CPU info when frequency info isn't available."""
        mocker.patch("linux_mcp_server.tools.system_info.psutil.cpu_freq", return_value=None)
        mocker.patch("linux_mcp_server.tools.system_info.psutil.cpu_count", side_effect=[8, 16])
        mocker.patch("linux_mcp_server.tools.system_info.psutil.cpu_percent", return_value=[10.0] * 16)
        mocker.patch("linux_mcp_server.tools.system_info.os.getloadavg", return_value=(1.0, 0.8, 0.6))
        mocker.patch("builtins.open", mocker.mock_open(read_data="model name\t: Test CPU\n"))

        result = await system_info.get_cpu_information()

        assert "Core" in result or "CPU" in result
        assert "Load Average" in result

    async def test_disk_usage_permission_error(self, mocker):
        """Test disk usage skips partitions with permission errors."""
        mock_partition = mocker.MagicMock()
        mock_partition.device = "/dev/restricted"
        mock_partition.mountpoint = "/restricted"

        mocker.patch("linux_mcp_server.tools.system_info.psutil.disk_partitions", return_value=[mock_partition])
        mocker.patch("linux_mcp_server.tools.system_info.psutil.disk_usage", side_effect=PermissionError)
        mocker.patch("linux_mcp_server.tools.system_info.psutil.disk_io_counters", return_value=None)

        result = await system_info.get_disk_usage()

        assert "Filesystem" in result
        assert "Error" not in result


class TestExceptionHandling:
    """Test that all functions handle exceptions gracefully."""

    @pytest.fixture(params=EXCEPTION_CASES, ids=[c[0] for c in EXCEPTION_CASES])
    def exception_case(self, request, mocker):
        """Fixture providing exception test cases."""
        mock_target, func = request.param
        mocker.patch(
            f"linux_mcp_server.tools.system_info.{mock_target}",
            side_effect=RuntimeError("Simulated failure"),
        )
        return func

    async def test_returns_error_message_on_exception(self, exception_case):
        """Test that functions return error strings on exceptions."""
        result = await exception_case()
        assert "Error" in result
