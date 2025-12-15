"""Tests for process management tools."""

import os
import sys

import pytest

from linux_mcp_server.tools import processes


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux ps command")
class TestProcesses:
    """Test process management tools."""

    async def test_list_processes_returns_string(self):
        """Test that list_processes returns a string."""
        result = await processes.list_processes.fn()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_list_processes_contains_process_info(self):
        """Test that list_processes contains process information."""
        result = await processes.list_processes.fn()

        # Should contain process-related keywords
        assert "pid" in result.lower() or "process" in result.lower()
        # Should contain resource usage info
        assert "cpu" in result.lower() or "memory" in result.lower() or "mem" in result.lower()

    async def test_get_process_info_with_current_process(self):
        """Test getting info about the current process."""
        current_pid = os.getpid()
        result = await processes.get_process_info.fn(current_pid)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain the PID
        assert str(current_pid) in result

    async def test_get_process_info_with_init_process(self):
        """Test getting info about init process (PID 1)."""
        result = await processes.get_process_info.fn(1)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain process information
        assert "1" in result or "systemd" in result.lower() or "init" in result.lower()

    async def test_get_process_info_with_nonexistent_process(self):
        """Test getting info about a non-existent process."""
        # Use a very high PID that likely doesn't exist
        result = await processes.get_process_info.fn(999999)
        assert isinstance(result, str)
        assert len(result) > 0
        # Should handle gracefully
        assert "not found" in result.lower() or "does not exist" in result.lower() or "error" in result.lower()

    async def test_list_processes_with_host(self, mocker):
        mocker.patch.object(processes, "execute_command", return_value=(0, "some process", ""))

        result = await processes.list_processes.fn(host="starship.command")

        assert "Running Processes" in result

    async def test_get_process_info_with_host(self, mocker):
        """Test getting process info from a remote host."""
        ps_output = "  PID USER     STAT %CPU %MEM    VSZ   RSS TTY  TIME COMMAND ARGS\n    1 root     Ss   0.0  0.1 169436 11892 ?    0:01 init /sbin/init"
        proc_status = "Name:\tinit\nState:\tS (sleeping)\nPid:\t1\nPPid:\t0\nThreads:\t1"

        mocker.patch.object(
            processes,
            "execute_command",
            side_effect=[
                (0, ps_output, ""),  # ps_detail
                (0, proc_status, ""),  # proc_status
            ],
        )

        result = await processes.get_process_info.fn(1, host="starship.command")

        assert "Process Information for PID 1" in result
        assert "init" in result.lower()


class TestProcessesRemoteMocked:
    """Test process tools with mocked remote execution."""

    @pytest.fixture
    def mock_execute(self, mocker):
        """Fixture to mock execute_command."""
        return mocker.patch.object(processes, "execute_command")

    async def test_list_processes_parses_ps_output(self, mock_execute):
        """Test that list_processes correctly parses ps aux output."""
        ps_output = """USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 169436 11892 ?        Ss   Dec11   0:01 /sbin/init
nobody     100  1.5  2.0  50000 20000 ?        S    Dec11   5:00 /usr/bin/app"""

        mock_execute.return_value = (0, ps_output, "")

        result = await processes.list_processes.fn(host="remote.host")

        assert "Running Processes" in result
        assert "Total processes: 2" in result

    async def test_list_processes_handles_command_failure(self, mock_execute):
        """Test that list_processes handles command failure gracefully."""
        mock_execute.return_value = (1, "", "Command not found")

        result = await processes.list_processes.fn(host="remote.host")

        assert "Error" in result

    async def test_get_process_info_handles_nonexistent_process(self, mock_execute):
        """Test that get_process_info handles non-existent process."""
        mock_execute.return_value = (1, "", "")

        result = await processes.get_process_info.fn(99999, host="remote.host")

        assert "does not exist" in result.lower()

    async def test_get_process_info_includes_proc_status(self, mock_execute):
        """Test that get_process_info includes /proc status when available."""
        ps_output = "  PID USER     STAT\n    1 root     Ss"
        proc_status = """Name:	systemd
State:	S (sleeping)
Pid:	1
PPid:	0
Threads:	1
VmRSS:	    11892 kB"""

        mock_execute.side_effect = [
            (0, ps_output, ""),  # ps command
            (0, proc_status, ""),  # /proc/PID/status
        ]

        result = await processes.get_process_info.fn(1, host="remote.host")

        assert "Process Information for PID 1" in result
        assert "Detailed Status" in result
        assert "systemd" in result
        assert "VmRSS" in result

    async def test_get_process_info_handles_proc_status_failure(self, mock_execute):
        """Test that get_process_info works even if /proc status fails."""
        ps_output = "  PID USER     STAT\n    1 root     Ss"

        mock_execute.side_effect = [
            (0, ps_output, ""),  # ps command succeeds
            (1, "", "Permission denied"),  # /proc/PID/status fails
        ]

        result = await processes.get_process_info.fn(1, host="remote.host")

        # Should still return ps info
        assert "Process Information for PID 1" in result
        # Should not have detailed status section
        assert "Detailed Status" not in result
