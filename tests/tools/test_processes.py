"""Tests for process management tools."""

import os

from unittest.mock import MagicMock

import pytest

from linux_mcp_server.tools import processes
from tests.conftest import GLOBAL_IPV6
from tests.conftest import IPV4_ADDR
from tests.conftest import LINK_LOCAL_FILTER_CASES_PROCESS
from tests.conftest import LINK_LOCAL_IPV6
from tests.conftest import make_mixed_connections_process
from tests.conftest import MockAddr
from tests.conftest import MockConnection


class TestTruncateHelpers:
    """Test string truncation helpers."""

    @pytest.mark.parametrize(
        "value,max_len,expected",
        [
            (None, 10, "N/A"),
            ("short", 10, "short"),
            ("exactly10!", 10, "exactly10!"),
            ("this is too long", 10, "this is..."),
            ("", 10, ""),
        ],
    )
    def test_truncate(self, value, max_len, expected):
        from linux_mcp_server.tools.processes import _truncate

        assert _truncate(value, max_len) == expected

    def test_truncate_custom_suffix(self):
        from linux_mcp_server.tools.processes import _truncate

        assert _truncate("toolong", 5, "~") == "tool~"

    @pytest.mark.parametrize(
        "cmdline,fallback,expected",
        [
            (None, "fallback", "fallback"),
            ([], "fallback", "fallback"),
            (["cmd"], "fallback", "cmd"),
            (["cmd", "arg1", "arg2"], "fallback", "cmd arg1 arg2"),
        ],
    )
    def test_format_cmdline(self, cmdline, fallback, expected):
        from linux_mcp_server.tools.processes import _format_cmdline

        assert _format_cmdline(cmdline, fallback) == expected

    def test_format_cmdline_truncates_long_commands(self):
        """Test that long command lines are truncated."""
        from linux_mcp_server.tools.processes import _format_cmdline

        long_cmdline = ["cmd", "arg1", "arg2", "arg3", "arg4", "arg5", "arg6"]
        result = _format_cmdline(long_cmdline, "fallback", max_len=20)
        assert len(result) == 20
        assert result.endswith("...")


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

    async def test_list_processes_with_host(self, mocker):
        mocker.patch.object(processes, "execute_command", return_value=(0, "some process", ""))

        result = await processes.list_processes(host="starship.command")

        assert "Running Processes" in result


@pytest.fixture
def create_mock_process():
    """Factory fixture to create a mock process with configurable network connections."""

    def _create(connections):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "test_process"
        mock_proc.exe.return_value = "/usr/bin/test"
        mock_proc.cmdline.return_value = ["test", "--arg"]
        mock_proc.status.return_value = "running"
        mock_proc.username.return_value = "testuser"
        mock_proc.pid = 12345
        mock_proc.ppid.return_value = 1
        mock_proc.cpu_percent.return_value = 1.5
        mock_proc.memory_percent.return_value = 2.0
        mock_proc.memory_info.return_value = MagicMock(rss=1024 * 1024, vms=2048 * 1024)
        mock_proc.create_time.return_value = 1700000000.0
        mock_proc.cpu_times.return_value = MagicMock(user=10.0, system=5.0)
        mock_proc.num_threads.return_value = 4
        mock_proc.num_fds.return_value = 10
        mock_proc.net_connections.return_value = connections
        return mock_proc

    return _create


class TestGetProcessInfoLinkLocalFiltering:
    """Test get_process_info filters link-local connections."""

    @pytest.mark.parametrize("laddr_ip,raddr_ip,expectation", LINK_LOCAL_FILTER_CASES_PROCESS)
    async def test_get_process_info_filters_link_local_connections(
        self, mocker, create_mock_process, laddr_ip, raddr_ip, expectation
    ):
        """Test that process connections with link-local addresses are filtered."""
        connections = [
            MockConnection(
                type_name="SOCK_STREAM",
                laddr=MockAddr(laddr_ip, 8080),
                raddr=MockAddr(raddr_ip, 54321),
                status="ESTABLISHED",
            ),
        ]

        mock_proc = create_mock_process(connections)
        mocker.patch.object(processes.psutil, "pid_exists", return_value=True)
        mocker.patch.object(processes.psutil, "Process", return_value=mock_proc)

        result = await processes.get_process_info(12345)  # noqa: F841 - used in eval

        assert eval(expectation)

    async def test_get_process_info_mixed_connections_filtering(self, mocker, create_mock_process):
        """Test filtering with mix of link-local and regular connections."""
        mock_proc = create_mock_process(make_mixed_connections_process())
        mocker.patch.object(processes.psutil, "pid_exists", return_value=True)
        mocker.patch.object(processes.psutil, "Process", return_value=mock_proc)

        result = await processes.get_process_info(12345)

        # Should only show 1 connection (the IPv4 -> global IPv6 one)
        assert "Network Connections (1)" in result
        assert f"{IPV4_ADDR}:80" in result
        assert f"{GLOBAL_IPV6}:12345" in result
        # Link-local addresses should not appear
        assert LINK_LOCAL_IPV6 not in result

    async def test_get_process_info_shows_more_than_10_connections_message(self, mocker, create_mock_process):
        """Test that 'and X more' message shows correct count after filtering."""
        # Create 15 regular connections (should show "and 5 more")
        connections = [
            MockConnection(
                type_name="SOCK_STREAM",
                laddr=MockAddr(IPV4_ADDR, 8000 + i),
                raddr=MockAddr(GLOBAL_IPV6, 50000 + i),
                status="ESTABLISHED",
            )
            for i in range(15)
        ]
        # Add 5 link-local connections that should be filtered out
        connections.extend(
            [
                MockConnection(
                    type_name="SOCK_STREAM",
                    laddr=MockAddr(LINK_LOCAL_IPV6, 9000 + i),
                    raddr=MockAddr(IPV4_ADDR, 60000 + i),
                    status="ESTABLISHED",
                )
                for i in range(5)
            ]
        )

        mock_proc = create_mock_process(connections)
        mocker.patch.object(processes.psutil, "pid_exists", return_value=True)
        mocker.patch.object(processes.psutil, "Process", return_value=mock_proc)

        result = await processes.get_process_info(12345)

        # Should show 15 filtered connections, first 10 displayed, "and 5 more"
        assert "Network Connections (15)" in result
        assert "... and 5 more" in result

    @pytest.mark.parametrize(
        "laddr,raddr,expected_local,expected_remote",
        [
            pytest.param(MockAddr(IPV4_ADDR, 80), None, f"{IPV4_ADDR}:80", "N/A", id="no-raddr"),
            pytest.param(None, MockAddr(IPV4_ADDR, 80), "N/A", f"{IPV4_ADDR}:80", id="no-laddr"),
        ],
    )
    async def test_get_process_info_connection_missing_address(
        self, mocker, create_mock_process, laddr, raddr, expected_local, expected_remote
    ):
        """Test connections with missing local or remote address."""
        connections = [
            MockConnection(type_name="SOCK_STREAM", laddr=laddr, raddr=raddr, status="ESTABLISHED"),
        ]

        mock_proc = create_mock_process(connections)
        mocker.patch.object(processes.psutil, "pid_exists", return_value=True)
        mocker.patch.object(processes.psutil, "Process", return_value=mock_proc)

        result = await processes.get_process_info(12345)

        assert "Network Connections (1)" in result
        assert expected_local in result
        assert expected_remote in result
