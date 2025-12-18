"""Tests for process management tools."""

import os
import sys

import pytest


@pytest.fixture
def mock_execute_with_fallback(mock_execute_with_fallback_for):
    """Processes-specific execute_with_fallback mock using the shared factory."""
    return mock_execute_with_fallback_for("linux_mcp_server.commands")


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux ps command")
class TestProcesses:
    async def test_list_processes(self, mcp_client):
        """Test that list_processes contains process information."""
        result = await mcp_client.call_tool("list_processes")
        result_text = result.content[0].text.casefold()
        expected = (
            ("pid", "process"),
            ("cpu", "memory", "mem"),
        )

        assert all(any(n in result_text for n in case) for case in expected), "Did not find all expected values"

    async def test_get_process_info_with_current_process(self, mcp_client):
        """Test getting info about the current process."""
        current_pid = os.getpid()
        result = await mcp_client.call_tool("get_process_info", arguments={"pid": current_pid})

        assert str(current_pid) in result.content[0].text

    async def test_get_process_info_with_init_process(self, mcp_client):
        """Test getting info about init process (PID 1)."""
        result = await mcp_client.call_tool("get_process_info", arguments={"pid": 1})
        result_text = result.content[0].text.casefold()
        expected = (
            "1",
            "systemd",
            "init",
        )
        assert any(n in result_text for n in expected), "Did not find any expected values"

    async def test_get_process_info_with_nonexistent_process(self, mcp_client):
        """Test getting info about a non-existent process."""
        # Use a very high PID that likely doesn't exist
        result = await mcp_client.call_tool("get_process_info", arguments={"pid": 999999})
        result_text = result.content[0].text.casefold()
        expected = ("not found", "does not exist", "error")

        assert any(n in result_text for n in expected), "Did not find any expected values"

    async def test_list_processes_with_host(self, mcp_client, mock_execute_with_fallback):
        mock_execute_with_fallback.return_value = (0, "some process", "")

        result = await mcp_client.call_tool("list_processes", arguments={"host": "starship.command"})

        assert "running processes" in result.content[0].text.casefold()

    async def test_get_process_info_with_host(self, mcp_client, mock_execute_with_fallback):
        """Test getting process info from a remote host."""
        ps_output = "  PID USER     STAT %CPU %MEM    VSZ   RSS TTY  TIME COMMAND ARGS\n    1 root     Ss   0.0  0.1 169436 11892 ?    0:01 init /sbin/init"
        proc_status = "Name:\tinit\nState:\tS (sleeping)\nPid:\t1\nPPid:\t0\nThreads:\t1"

        mock_execute_with_fallback.side_effect = [
            (0, ps_output, ""),  # ps_detail
            (0, proc_status, ""),  # proc_status
        ]

        result = await mcp_client.call_tool("get_process_info", arguments={"pid": 1, "host": "starship.command"})
        result_text = result.content[0].text.casefold()

        assert "process information for pid 1" in result_text
        assert "init" in result_text


class TestProcessesRemoteMocked:
    """Test process tools with mocked remote execution."""

    async def test_list_processes_parses_ps_output(self, mcp_client, mock_execute_with_fallback):
        """Test that list_processes correctly parses ps aux output."""
        ps_output = """USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1  0.0  0.1 169436 11892 ?        Ss   Dec11   0:01 /sbin/init
nobody     100  1.5  2.0  50000 20000 ?        S    Dec11   5:00 /usr/bin/app"""

        mock_execute_with_fallback.return_value = (0, ps_output, "")

        result = await mcp_client.call_tool("list_processes", arguments={"host": "remote.host"})
        result_text = result.content[0].text.casefold()

        assert "running processes" in result_text
        assert "total processes: 2" in result_text

    async def test_list_processes_handles_command_failure(self, mcp_client, mock_execute_with_fallback):
        """Test that list_processes handles command failure gracefully."""
        mock_execute_with_fallback.return_value = (1, "", "Command not found")

        result = await mcp_client.call_tool("list_processes", arguments={"host": "remote.host"})

        assert "error" in result.content[0].text.casefold()

    async def test_get_process_info_handles_nonexistent_process(self, mcp_client, mock_execute_with_fallback):
        """Test that get_process_info handles non-existent process."""
        mock_execute_with_fallback.return_value = (1, "", "")

        result = await mcp_client.call_tool("get_process_info", arguments={"pid": 99999, "host": "remote.host"})

        assert "does not exist" in result.content[0].text.casefold()

    async def test_get_process_info_includes_proc_status(self, mcp_client, mock_execute_with_fallback):
        """Test that get_process_info includes /proc status when available."""
        ps_output = "  PID USER     STAT\n    1 root     Ss"
        proc_status = """Name:	systemd
State:	S (sleeping)
Pid:	1
PPid:	0
Threads:	1
VmRSS:	    11892 kB"""

        mock_execute_with_fallback.side_effect = [
            (0, ps_output, ""),  # ps command
            (0, proc_status, ""),  # /proc/PID/status
        ]

        result = await mcp_client.call_tool("get_process_info", arguments={"pid": 1, "host": "remote.host"})
        result_text = result.content[0].text.casefold()

        assert "process information for pid 1" in result_text
        assert "detailed status" in result_text
        assert "systemd" in result_text
        assert "vmrss" in result_text

    async def test_get_process_info_handles_proc_status_failure(self, mcp_client, mock_execute_with_fallback):
        """Test that get_process_info works even if /proc status fails."""
        ps_output = "  PID USER     STAT\n    1 root     Ss"

        mock_execute_with_fallback.side_effect = [
            (0, ps_output, ""),  # ps command succeeds
            (1, "", "Permission denied"),  # /proc/PID/status fails
        ]

        result = await mcp_client.call_tool("get_process_info", arguments={"pid": 1, "host": "remote.host"})
        result_text = result.content[0].text.casefold()

        assert "process information for pid 1" in result_text
        assert "detailed status" not in result_text
