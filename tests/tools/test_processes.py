"""Tests for process management tools."""

import os

import pytest

from linux_mcp_server.tools import processes


@pytest.fixture
def mock_execute_command(mock_execute_command_for):
    """Fixture to mock execute_command for the processes module."""
    return mock_execute_command_for("linux_mcp_server.tools.processes")


class TestProcesses:
    """Test process management tools using real system calls."""

    async def test_list_processes_returns_string_with_process_info(self):
        """Test that list_processes returns a string with process information."""
        result = await processes.list_processes()
        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain process-related keywords
        assert "pid" in result.lower() or "process" in result.lower()
        # Should contain resource usage info
        assert "cpu" in result.lower() or "memory" in result.lower() or "mem" in result.lower()

    async def test_list_processes_shows_total_processes(self):
        """Test that list_processes shows total process count."""
        result = await processes.list_processes()
        assert "Total processes:" in result
        assert "Running Processes" in result

    @pytest.mark.parametrize(
        "pid,expected_in_result",
        [
            pytest.param(1, ["1", "systemd", "init"], id="init_process"),
        ],
    )
    async def test_get_process_info_with_known_pids(self, pid, expected_in_result):
        """Test getting info about known processes."""
        result = await processes.get_process_info(pid)
        assert isinstance(result, str)
        assert len(result) > 0
        # At least one of the expected strings should be in result
        assert any(exp.lower() in result.lower() for exp in expected_in_result)

    async def test_get_process_info_with_current_process(self):
        """Test getting info about the current process."""
        current_pid = os.getpid()
        result = await processes.get_process_info(current_pid)
        assert isinstance(result, str)
        assert str(current_pid) in result

    async def test_get_process_info_with_nonexistent_process(self):
        """Test getting info about a non-existent process."""
        result = await processes.get_process_info(999999)
        assert isinstance(result, str)
        assert "not found" in result.lower() or "does not exist" in result.lower() or "error" in result.lower()

    @pytest.mark.parametrize(
        "pid,host",
        [
            pytest.param(-1, None, id="local_negative_one"),
            pytest.param(-5, "remote.example.com", id="remote_negative_five"),
            pytest.param(0, None, id="local_zero"),
        ],
    )
    async def test_get_process_info_invalid_pid(self, pid, host):
        """Test get_process_info with invalid PIDs."""
        result = await processes.get_process_info(pid, host=host)
        assert "Error: PID must be at least 1" in result

    async def test_get_process_info_accepts_float_pid(self):
        """Test that get_process_info accepts float PIDs (from LLMs)."""
        current_pid = float(os.getpid())
        result = await processes.get_process_info(current_pid)
        assert isinstance(result, str)
        assert str(int(current_pid)) in result


class TestProcessesMocked:
    """Test process management with mocked execute_command."""

    @pytest.mark.parametrize(
        "return_code,ps_output,expected_in_result,process_count",
        [
            pytest.param(
                0,
                "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\nroot         1  0.0  0.1 169564 13808 ?        Ss   Nov01   0:01 /sbin/init\n",
                ["Running Processes"],
                1,
                id="single_process",
            ),
            pytest.param(
                0,
                "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\nroot         1  0.0  0.1 169436 11892 ?        Ss   Dec11   0:01 /sbin/init\nnobody     100  1.5  2.0  50000 20000 ?        S    Dec11   5:00 /usr/bin/app",
                ["Running Processes", "Total processes: 2"],
                2,
                id="multiple_processes",
            ),
            pytest.param(
                0,
                # Generate header + 102 processes programmatically or inline
                "\n".join(
                    ["USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND"]
                    + [
                        f"user     {i:5d}  0.0  0.1 169564 13808 ?        Ss   Nov01   0:01 process{i}"
                        for i in range(1, 103)
                    ]
                ),
                ["Running Processes", "Total processes: 102"],
                102,
                id="many_processes",
            ),
        ],
    )
    async def test_list_processes_remote_scenarios(
        self, mock_execute_command, return_code, ps_output, expected_in_result, process_count
    ):
        """Test list_processes on remote host with various outputs."""
        mock_execute_command.return_value = (return_code, ps_output, "")

        result = await processes.list_processes(host="remote.example.com")

        for expected in expected_in_result:
            assert expected in result

        async def test_list_processes_with_host(self, mock_execute_command):
            """Test list_processes on remote host."""
            mock_output = "USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\nroot         1  0.0  0.1 169564 13808 ?        Ss   Nov01   0:01 /sbin/init\n"
            mock_execute_command.return_value = (0, mock_output, "")

            result = await processes.list_processes(host="remote.example.com")

            assert "Running Processes" in result
            assert f"Total processes: {process_count}" in result

    @pytest.mark.parametrize(
        "return_code,stdout,stderr",
        [
            pytest.param(1, "", "Error", id="command_error"),
            pytest.param(0, "", "", id="empty_output"),
        ],
    )
    async def test_list_processes_error_conditions(self, mock_execute_command, return_code, stdout, stderr):
        """Test list_processes error handling for various failure conditions."""
        mock_execute_command.return_value = (return_code, stdout, stderr)

        result = await processes.list_processes(host="remote.example.com")

        assert "Error executing ps command" in result

    async def test_list_processes_exception_handling(self, mock_execute_command):
        """Test that list_processes handles general exceptions."""
        mock_execute_command.side_effect = Exception("Test error")

        result = await processes.list_processes()
        assert "Error listing processes" in result
        assert "Test error" in result

    async def test_get_process_info_with_host(self, mock_execute_command):
        """Test getting process info from a remote host."""
        ps_output = "  PID USER     STAT %CPU %MEM    VSZ   RSS TTY  TIME COMMAND ARGS\n    1 root     Ss   0.0  0.1 169436 11892 ?    0:01 init /sbin/init"
        proc_status = "Name:\tinit\nState:\tS (sleeping)\nPid:\t1\nPPid:\t0\nThreads:\t1"

        mock_execute_command.side_effect = [
            (0, ps_output, ""),  # ps_detail
            (0, proc_status, ""),  # proc_status
        ]

        result = await processes.get_process_info(1, host="starship.command")

        assert "Process Information for PID 1" in result
        assert "init" in result.lower()

    @pytest.mark.parametrize(
        "proc_status_result,expect_detailed_status",
        [
            pytest.param(
                (0, "Name:\tsystemd\nState:\tS (sleeping)\nPid:\t1\nPPid:\t0\nThreads:\t1\nVmRSS:\t    11892 kB", ""),
                True,
                id="with_proc_status",
            ),
            pytest.param(
                (1, "", "Permission denied"),
                False,
                id="proc_status_failure",
            ),
        ],
    )
    async def test_get_process_info_proc_status_handling(
        self, mock_execute_command, proc_status_result, expect_detailed_status
    ):
        """Test get_process_info handles /proc status availability."""
        ps_output = "  PID USER     STAT\n    1 root     Ss"

        mock_execute_command.side_effect = [
            (0, ps_output, ""),  # ps command
            proc_status_result,  # /proc/PID/status
        ]

        result = await processes.get_process_info(1, host="remote.host")

        assert "Process Information for PID 1" in result
        if expect_detailed_status:
            assert "Detailed Status" in result
            assert "systemd" in result
        else:
            assert "Detailed Status" not in result

    @pytest.mark.parametrize(
        "return_code,stdout,stderr,pid",
        [
            pytest.param(1, "", "Error", 99999, id="command_error"),
            pytest.param(0, "", "", 1, id="empty_output"),
            pytest.param(1, "", "", 99999, id="nonexistent_process"),
        ],
    )
    async def test_get_process_info_not_found_conditions(self, mock_execute_command, return_code, stdout, stderr, pid):
        """Test get_process_info returns 'does not exist' for various failure conditions."""
        mock_execute_command.return_value = (return_code, stdout, stderr)

        result = await processes.get_process_info(pid, host="remote.example.com")

        assert "does not exist" in result

    async def test_get_process_info_general_exception(self, mock_execute_command):
        """Test get_process_info with general exception."""
        mock_execute_command.side_effect = Exception("Test error")

        result = await processes.get_process_info(1234)
        assert "Error getting process information" in result
        assert "Test error" in result


class TestProcessesEdgeCases:
    """Test edge cases for process formatting."""

    @pytest.mark.parametrize(
        "ps_line,expected_truncated",
        [
            pytest.param(
                "verylongusername123  1234  0.0  0.1 169564 13808 ?  Ss   Nov01   0:01 short_cmd",
                "verylongu...",
                id="long_username",
            ),
            pytest.param(
                "user  1234  0.0  0.1 169564 13808 ?  Ss   Nov01   0:01 very_long_process_name_that_exceeds_the_limit_by_a_lot_more_characters",
                "very_long_process_name_that_exceeds_t...",
                id="long_command",
            ),
        ],
    )
    async def test_list_processes_truncates_long_fields(self, mock_execute_command, ps_line, expected_truncated):
        """Test that long field values are truncated properly."""
        ps_output = f"USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n{ps_line}"
        mock_execute_command.return_value = (0, ps_output, "")

        result = await processes.list_processes(host="remote.host")
        assert expected_truncated in result
