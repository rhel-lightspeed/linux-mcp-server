"""Tests for process management tools."""

import os

import psutil

from linux_mcp_server.server import mcp
from linux_mcp_server.tools import processes


def _get_text_from_mcp_result(result):
    """Helper to extract text from mcp.call_tool() result."""
    content_list, _ = result
    return content_list[0].text


class TestProcesses:
    """Test process management tools."""

    async def test_list_processes_returns_string(self):
        """Test that list_processes returns a string."""
        result = await mcp.call_tool("list_processes", {})
        text = _get_text_from_mcp_result(result)
        assert isinstance(text, str)
        assert len(text) > 0

    async def test_list_processes_contains_process_info(self):
        """Test that list_processes contains process information."""
        result = await mcp.call_tool("list_processes", {})
        text = _get_text_from_mcp_result(result)

        # Should contain process-related keywords
        assert "pid" in text.lower() or "process" in text.lower()
        # Should contain resource usage info
        assert "cpu" in text.lower() or "memory" in text.lower() or "mem" in text.lower()

    async def test_list_processes_shows_top_100(self):
        """Test that list_processes limits output to top 100 processes."""
        result = await mcp.call_tool("list_processes", {})
        text = _get_text_from_mcp_result(result)
        assert "Top 100" in text
        assert "Total processes:" in text

    async def test_list_processes_handles_no_access_denied(self, mocker):
        """Test that list_processes handles AccessDenied exceptions."""
        mock_proc = mocker.Mock()
        mock_proc.info = {"pid": 1, "name": "test"}

        def process_iter_side_effect(*args, **kwargs):
            # Return one good process and one that raises AccessDenied
            yield mock_proc
            mock_bad = mocker.Mock()
            mock_bad.info
            type(mock_bad).info = mocker.PropertyMock(side_effect=psutil.AccessDenied())
            yield mock_bad

        mocker.patch("psutil.process_iter", side_effect=process_iter_side_effect)
        mocker.patch("psutil.process_iter", return_value=[mock_proc])

        result = await mcp.call_tool("list_processes", {})
        text = _get_text_from_mcp_result(result)
        assert isinstance(text, str)
        assert "Running Processes" in text

    async def test_list_processes_exception_handling(self, mocker):
        """Test that list_processes handles general exceptions."""
        mocker.patch("psutil.process_iter", side_effect=Exception("Test error"))

        result = await mcp.call_tool("list_processes", {})
        text = _get_text_from_mcp_result(result)
        assert "Error listing processes" in text
        assert "Test error" in text

    async def test_get_process_info_with_current_process(self):
        """Test getting info about the current process."""
        current_pid = os.getpid()
        result = await mcp.call_tool("get_process_info", {"pid": current_pid})
        text = _get_text_from_mcp_result(result)
        assert isinstance(text, str)
        assert len(text) > 0
        # Should contain the PID
        assert str(current_pid) in text

    async def test_get_process_info_with_init_process(self):
        """Test getting info about init process (PID 1)."""
        result = await mcp.call_tool("get_process_info", {"pid": 1})
        text = _get_text_from_mcp_result(result)
        assert isinstance(text, str)
        assert len(text) > 0
        # Should contain process information
        assert "1" in text or "systemd" in text.lower() or "init" in text.lower()

    async def test_get_process_info_with_nonexistent_process(self):
        """Test getting info about a non-existent process."""
        # Use a very high PID that likely doesn't exist
        result = await mcp.call_tool("get_process_info", {"pid": 999999})
        text = _get_text_from_mcp_result(result)
        assert isinstance(text, str)
        assert len(text) > 0
        # Should handle gracefully
        assert "not found" in text.lower() or "does not exist" in text.lower() or "error" in text.lower()

    async def test_get_process_info_invalid_pid(self):
        """Test get_process_info with invalid PID."""
        result = await mcp.call_tool("get_process_info", {"pid": -1})
        text = _get_text_from_mcp_result(result)
        assert "Error: PID must be at least 1" in text

    async def test_get_process_info_accepts_float_pid(self):
        """Test that get_process_info accepts float PIDs (from LLMs)."""
        current_pid = float(os.getpid())
        result = await mcp.call_tool("get_process_info", {"pid": current_pid})
        text = _get_text_from_mcp_result(result)
        assert isinstance(text, str)
        assert str(int(current_pid)) in text

    async def test_get_process_info_access_denied(self, mocker):
        """Test get_process_info when access is denied."""
        mock_proc = mocker.Mock(spec=psutil.Process)
        mock_proc.pid = 1234
        mock_proc.name.side_effect = psutil.AccessDenied()
        mock_proc.exe.side_effect = psutil.AccessDenied()
        mock_proc.cmdline.side_effect = psutil.AccessDenied()
        mock_proc.status.side_effect = psutil.AccessDenied()
        mock_proc.username.side_effect = psutil.AccessDenied()
        mock_proc.ppid.side_effect = psutil.AccessDenied()
        mock_proc.cpu_percent.side_effect = psutil.AccessDenied()
        mock_proc.memory_info.side_effect = psutil.AccessDenied()
        mock_proc.memory_percent.side_effect = psutil.AccessDenied()
        mock_proc.create_time.side_effect = psutil.AccessDenied()
        mock_proc.cpu_times.side_effect = psutil.AccessDenied()
        mock_proc.num_threads.side_effect = psutil.AccessDenied()
        mock_proc.num_fds.side_effect = psutil.AccessDenied()
        mock_proc.connections.side_effect = psutil.AccessDenied()

        mocker.patch("psutil.pid_exists", return_value=True)
        mocker.patch("psutil.Process", return_value=mock_proc)

        result = await mcp.call_tool("get_process_info", {"pid": 1234})
        text = _get_text_from_mcp_result(result)
        assert isinstance(text, str)
        assert "1234" in text

    async def test_get_process_info_no_such_process_exception(self, mocker):
        """Test get_process_info when process disappears during query."""
        mocker.patch("psutil.pid_exists", return_value=True)
        mocker.patch("psutil.Process", side_effect=psutil.NoSuchProcess(999))

        result = await mcp.call_tool("get_process_info", {"pid": 999})
        text = _get_text_from_mcp_result(result)
        assert "does not exist" in text

    async def test_get_process_info_general_exception(self, mocker):
        """Test get_process_info with general exception."""
        mocker.patch("psutil.pid_exists", return_value=True)
        mocker.patch("psutil.Process", side_effect=Exception("Test error"))

        result = await mcp.call_tool("get_process_info", {"pid": 1234})
        text = _get_text_from_mcp_result(result)
        assert "Error getting process information" in text

    async def test_get_process_info_with_connections(self, mocker):
        """Test get_process_info includes network connections."""
        current_pid = os.getpid()

        # Create mock connection
        mock_conn = mocker.Mock()
        mock_conn.type.name = "SOCK_STREAM"
        mock_conn.laddr = ("127.0.0.1", 8080)
        mock_conn.raddr = ("192.168.1.1", 443)
        mock_conn.status = "ESTABLISHED"

        mock_proc = mocker.Mock(spec=psutil.Process)
        mock_proc.pid = current_pid
        mock_proc.name.return_value = "test_process"
        mock_proc.exe.return_value = "/usr/bin/test"
        mock_proc.cmdline.return_value = ["test", "--arg"]
        mock_proc.status.return_value = "running"
        mock_proc.username.return_value = "testuser"
        mock_proc.ppid.return_value = 1
        mock_proc.cpu_percent.return_value = 5.0
        mock_proc.memory_info.return_value = mocker.Mock(rss=1024 * 1024, vms=2048 * 1024)
        mock_proc.memory_percent.return_value = 1.5
        mock_proc.create_time.return_value = 1609459200.0
        mock_proc.cpu_times.return_value = mocker.Mock(user=1.0, system=0.5)
        mock_proc.num_threads.return_value = 4
        mock_proc.num_fds.return_value = 10
        mock_proc.connections.return_value = [mock_conn]

        mocker.patch("psutil.pid_exists", return_value=True)
        mocker.patch("psutil.Process", return_value=mock_proc)

        result = await mcp.call_tool("get_process_info", {"pid": current_pid})
        text = _get_text_from_mcp_result(result)
        assert "Network Connections" in text
        assert "SOCK_STREAM" in text

    async def test_get_process_info_with_many_connections(self, mocker):
        """Test get_process_info limits network connection display."""
        current_pid = os.getpid()

        # Create 15 mock connections
        mock_conns = []
        for i in range(15):
            mock_conn = mocker.Mock()
            mock_conn.type.name = "SOCK_STREAM"
            mock_conn.laddr = ("127.0.0.1", 8080 + i)
            mock_conn.raddr = None
            mock_conn.status = "LISTEN"
            mock_conns.append(mock_conn)

        mock_proc = mocker.Mock(spec=psutil.Process)
        mock_proc.pid = current_pid
        mock_proc.name.return_value = "test_process"
        mock_proc.exe.return_value = "/usr/bin/test"
        mock_proc.cmdline.return_value = ["test"]
        mock_proc.status.return_value = "running"
        mock_proc.username.return_value = "testuser"
        mock_proc.ppid.return_value = 1
        mock_proc.cpu_percent.return_value = 5.0
        mock_proc.memory_info.return_value = mocker.Mock(rss=1024 * 1024, vms=2048 * 1024)
        mock_proc.memory_percent.return_value = 1.5
        mock_proc.create_time.return_value = 1609459200.0
        mock_proc.cpu_times.return_value = mocker.Mock(user=1.0, system=0.5)
        mock_proc.num_threads.return_value = 4
        mock_proc.num_fds.return_value = 10
        mock_proc.connections.return_value = mock_conns

        mocker.patch("psutil.pid_exists", return_value=True)
        mocker.patch("psutil.Process", return_value=mock_proc)

        result = await mcp.call_tool("get_process_info", {"pid": current_pid})
        text = _get_text_from_mcp_result(result)
        assert "Network Connections (15)" in text
        assert "... and 5 more" in text


class TestProcessesRemote:
    """Test remote process management."""

    async def test_list_processes_with_host(self, mocker):
        """Test list_processes on remote host."""
        mock_output = "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\nroot         1  0.0  0.1 169564 13808 ?        Ss   Nov01   0:01 /sbin/init\n"
        mocker.patch.object(processes, "execute_command", return_value=(0, mock_output, ""))

        result = await mcp.call_tool("list_processes", {"host": "remote.example.com"})
        text = _get_text_from_mcp_result(result)

        assert "Running Processes" in text
        assert "root" in text or "init" in text.lower()

    async def test_list_processes_with_host_many_processes(self, mocker):
        """Test list_processes on remote host with many processes."""
        # Create header + 102 processes
        lines = ["USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND"]
        for i in range(1, 103):
            lines.append(f"user     {i:5d}  0.0  0.1 169564 13808 ?        Ss   Nov01   0:01 process{i}")
        mock_output = "\n".join(lines)

        mocker.patch.object(processes, "execute_command", return_value=(0, mock_output, ""))

        result = await mcp.call_tool("list_processes", {"host": "remote.example.com"})
        text = _get_text_from_mcp_result(result)

        assert "Running Processes" in text
        assert "Top 100 by CPU usage" in text
        assert "Total processes: 102" in text

    async def test_list_processes_with_host_error(self, mocker):
        """Test list_processes on remote host with error."""
        mocker.patch.object(processes, "execute_command", return_value=(1, "", "Error"))

        result = await mcp.call_tool("list_processes", {"host": "remote.example.com"})
        text = _get_text_from_mcp_result(result)

        assert "Error executing ps command" in text

    async def test_list_processes_with_host_empty_output(self, mocker):
        """Test list_processes on remote host with empty output."""
        mocker.patch.object(processes, "execute_command", return_value=(0, "", ""))

        result = await mcp.call_tool("list_processes", {"host": "remote.example.com"})
        text = _get_text_from_mcp_result(result)

        assert "Error executing ps command" in text

    async def test_get_process_info_with_host(self, mocker):
        """Test get_process_info on remote host."""
        ps_output = "  PID USER     STAT  %CPU %MEM    VSZ   RSS     ELAPSED COMMAND         COMMAND\n    1 root     Ss     0.0  0.1 169564 13808    10:23:45 systemd         /sbin/init\n"
        status_output = "Name:\tsystemd\nState:\tS (sleeping)\nTgid:\t1\nPid:\t1\nPPid:\t0\nThreads:\t1\nVmPeak:\t  169564 kB\nVmSize:\t  169564 kB\nVmRSS:\t   13808 kB\n"

        execute_calls = [(0, ps_output, ""), (0, status_output, "")]

        mocker.patch.object(processes, "execute_command", side_effect=execute_calls)

        result = await mcp.call_tool("get_process_info", {"pid": 1, "host": "remote.example.com"})
        text = _get_text_from_mcp_result(result)

        assert "Process Information for PID 1" in text
        assert "systemd" in text.lower() or "init" in text.lower()
        assert "Detailed Status" in text

    async def test_get_process_info_with_host_no_proc_status(self, mocker):
        """Test get_process_info on remote host without /proc status."""
        ps_output = "  PID USER     STAT  %CPU %MEM    VSZ   RSS     ELAPSED COMMAND         COMMAND\n    1 root     Ss     0.0  0.1 169564 13808    10:23:45 systemd         /sbin/init\n"

        execute_calls = [(0, ps_output, ""), (1, "", "cat: /proc/1/status: Permission denied")]

        mocker.patch.object(processes, "execute_command", side_effect=execute_calls)

        result = await mcp.call_tool("get_process_info", {"pid": 1, "host": "remote.example.com"})
        text = _get_text_from_mcp_result(result)

        assert "Process Information for PID 1" in text
        assert "Detailed Status" not in text

    async def test_get_process_info_with_host_nonexistent(self, mocker):
        """Test get_process_info on remote host with nonexistent PID."""
        mocker.patch.object(processes, "execute_command", return_value=(1, "", "Error"))

        result = await mcp.call_tool("get_process_info", {"pid": 99999, "host": "remote.example.com"})
        text = _get_text_from_mcp_result(result)

        assert "does not exist on remote host" in text

    async def test_get_process_info_with_host_empty_output(self, mocker):
        """Test get_process_info on remote host with empty output."""
        mocker.patch.object(processes, "execute_command", return_value=(0, "", ""))

        result = await mcp.call_tool("get_process_info", {"pid": 1, "host": "remote.example.com"})
        text = _get_text_from_mcp_result(result)

        assert "does not exist on remote host" in text

    async def test_get_process_info_with_host_invalid_pid(self, mocker):
        """Test get_process_info on remote host with invalid PID."""
        result = await mcp.call_tool("get_process_info", {"pid": -5, "host": "remote.example.com"})
        text = _get_text_from_mcp_result(result)
        assert "Error: PID must be at least 1" in text

    async def test_list_processes(self):
        """Test calling list_processes through mcp.call_tool()."""
        result = await mcp.call_tool("list_processes", {})

        # mcp.call_tool returns a tuple of (list[TextContent], dict)
        assert isinstance(result, tuple)
        assert len(result) == 2
        content_list, metadata = result
        assert isinstance(content_list, list)
        assert len(content_list) == 1
        content = content_list[0]
        assert hasattr(content, "text")
        assert isinstance(content.text, str)
        assert "Running Processes" in content.text

    async def test_get_process_info(self):
        """Test calling get_process_info through mcp.call_tool()."""
        current_pid = os.getpid()
        result = await mcp.call_tool("get_process_info", {"pid": current_pid})

        # mcp.call_tool returns a tuple of (list[TextContent], dict)
        assert isinstance(result, tuple)
        assert len(result) == 2
        content_list, metadata = result
        assert isinstance(content_list, list)
        assert len(content_list) == 1
        content = content_list[0]
        assert hasattr(content, "text")
        assert isinstance(content.text, str)
        assert str(current_pid) in content.text

    async def test_get_process_info_invalid_pid(self):
        """Test calling get_process_info via MCP with invalid PID."""
        result = await mcp.call_tool("get_process_info", {"pid": -1})

        # mcp.call_tool returns a tuple of (list[TextContent], dict)
        assert isinstance(result, tuple)
        content_list, metadata = result
        assert isinstance(content_list, list)
        content = content_list[0]
        assert "Error: PID must be at least 1" in content.text

    async def test_get_process_info_nonexistent_pid(self):
        """Test calling get_process_info via MCP with nonexistent PID."""
        result = await mcp.call_tool("get_process_info", {"pid": 999999})

        # mcp.call_tool returns a tuple of (list[TextContent], dict)
        assert isinstance(result, tuple)
        content_list, metadata = result
        assert isinstance(content_list, list)
        content = content_list[0]
        assert "does not exist" in content.text.lower()


class TestProcessesEdgeCases:
    """Test edge cases and special scenarios."""

    async def test_list_processes_truncates_long_usernames(self, mocker):
        """Test that long usernames are truncated."""
        mock_proc = mocker.Mock()
        mock_proc.info = {
            "pid": 1234,
            "name": "test",
            "username": "verylongusername123",
            "cpu_percent": 1.0,
            "memory_percent": 1.0,
            "status": "running",
            "cmdline": ["test"],
        }

        mocker.patch("psutil.process_iter", return_value=[mock_proc])

        result = await mcp.call_tool("list_processes", {})
        text = _get_text_from_mcp_result(result)
        assert "verylongu..." in text

    async def test_list_processes_truncates_long_names(self, mocker):
        """Test that long process names are truncated."""
        mock_proc = mocker.Mock()
        mock_proc.info = {
            "pid": 1234,
            "name": "very_long_process_name_that_exceeds_limit",
            "username": "user",
            "cpu_percent": 1.0,
            "memory_percent": 1.0,
            "status": "running",
            "cmdline": ["test"],
        }

        mocker.patch("psutil.process_iter", return_value=[mock_proc])

        result = await mcp.call_tool("list_processes", {})
        text = _get_text_from_mcp_result(result)
        # Name gets truncated to 27 chars + "..."
        assert "very_long_process_name_that..." in text

    async def test_list_processes_truncates_long_commands(self, mocker):
        """Test that long command lines are truncated."""
        mock_proc = mocker.Mock()
        mock_proc.info = {
            "pid": 1234,
            "name": "test",
            "username": "user",
            "cpu_percent": 1.0,
            "memory_percent": 1.0,
            "status": "running",
            "cmdline": ["test"] + ["arg"] * 50,
        }

        mocker.patch("psutil.process_iter", return_value=[mock_proc])

        result = await mcp.call_tool("list_processes", {})
        text = _get_text_from_mcp_result(result)
        assert "..." in text

    async def test_list_processes_handles_missing_values(self, mocker):
        """Test that list_processes handles missing values in process info."""
        mock_proc = mocker.Mock()
        # Use missing keys instead of None values to trigger defaults
        mock_proc.info = {
            "pid": 1234,
            "status": "running",
        }

        mocker.patch("psutil.process_iter", return_value=[mock_proc])

        result = await mcp.call_tool("list_processes", {})
        text = _get_text_from_mcp_result(result)
        assert "1234" in text
        assert "N/A" in text

    async def test_list_processes_handles_empty_cmdline(self, mocker):
        """Test that list_processes handles empty cmdline."""
        mock_proc = mocker.Mock()
        mock_proc.info = {
            "pid": 1234,
            "name": "test_proc",
            "username": "user",
            "cpu_percent": 1.0,
            "memory_percent": 1.0,
            "status": "running",
            "cmdline": [],
        }

        mocker.patch("psutil.process_iter", return_value=[mock_proc])

        result = await mcp.call_tool("list_processes", {})
        text = _get_text_from_mcp_result(result)
        # Should use name when cmdline is empty
        assert "test_proc" in text

    async def test_get_process_info_handles_no_fds_attribute(self, mocker):
        """Test get_process_info on systems without num_fds support."""
        current_pid = os.getpid()

        mock_proc = mocker.Mock(spec=psutil.Process)
        mock_proc.pid = current_pid
        mock_proc.name.return_value = "test_process"
        mock_proc.exe.return_value = "/usr/bin/test"
        mock_proc.cmdline.return_value = ["test"]
        mock_proc.status.return_value = "running"
        mock_proc.username.return_value = "testuser"
        mock_proc.ppid.return_value = 1
        mock_proc.cpu_percent.return_value = 5.0
        mock_proc.memory_info.return_value = mocker.Mock(rss=1024 * 1024, vms=2048 * 1024)
        mock_proc.memory_percent.return_value = 1.5
        mock_proc.create_time.return_value = 1609459200.0
        mock_proc.cpu_times.return_value = mocker.Mock(user=1.0, system=0.5)
        mock_proc.num_threads.return_value = 4
        mock_proc.num_fds.side_effect = AttributeError("Not available")
        mock_proc.connections.return_value = []

        mocker.patch("psutil.pid_exists", return_value=True)
        mocker.patch("psutil.Process", return_value=mock_proc)

        result = await mcp.call_tool("get_process_info", {"pid": current_pid})
        text = _get_text_from_mcp_result(result)
        assert isinstance(text, str)
        assert "test_process" in text
        # Should not crash when num_fds is not available

    async def test_get_process_info_exe_access_denied(self, mocker):
        """Test get_process_info shows access denied message for exe."""
        current_pid = os.getpid()

        mock_proc = mocker.Mock(spec=psutil.Process)
        mock_proc.pid = current_pid
        mock_proc.name.return_value = "test_process"
        mock_proc.exe.side_effect = psutil.AccessDenied()
        mock_proc.cmdline.return_value = ["test"]
        mock_proc.status.return_value = "running"
        mock_proc.username.return_value = "testuser"
        mock_proc.ppid.return_value = 1
        mock_proc.cpu_percent.return_value = 5.0
        mock_proc.memory_info.return_value = mocker.Mock(rss=1024 * 1024, vms=2048 * 1024)
        mock_proc.memory_percent.return_value = 1.5
        mock_proc.create_time.return_value = 1609459200.0
        mock_proc.cpu_times.return_value = mocker.Mock(user=1.0, system=0.5)
        mock_proc.num_threads.return_value = 4
        mock_proc.num_fds.return_value = 10
        mock_proc.connections.return_value = []

        mocker.patch("psutil.pid_exists", return_value=True)
        mocker.patch("psutil.Process", return_value=mock_proc)

        result = await mcp.call_tool("get_process_info", {"pid": current_pid})
        text = _get_text_from_mcp_result(result)
        assert "[Access Denied]" in text
