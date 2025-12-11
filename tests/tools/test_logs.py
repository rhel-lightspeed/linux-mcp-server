"""Tests for log tools."""

from contextlib import nullcontext as does_not_raise

import pytest

from linux_mcp_server.server import mcp


def assert_tool_result_structure(result):
    """Verify common result structure returned by all tools."""
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], list)
    return result[0][0].text


@pytest.fixture
def mock_allowed_log_paths(mocker):
    """Fixture factory to set CONFIG.allowed_log_paths for read_log_file tests."""

    def _set_paths(paths=""):
        mock_config = mocker.patch("linux_mcp_server.tools.logs.CONFIG")
        mock_config.allowed_log_paths = paths
        return mock_config

    return _set_paths


class TestGetJournalLogs:
    """Tests for get_journal_logs tool."""

    @pytest.mark.parametrize(
        "params,expected_args,expected_in_output",
        [
            # Default parameters
            (
                {},
                ["-n", "100", "--no-pager"],
                ["last 100 entries", "no filters"],
            ),
            # Unit filter
            (
                {"unit": "nginx.service"},
                ["-u", "nginx.service"],
                ["unit=nginx.service"],
            ),
            # Priority filter
            (
                {"priority": "err"},
                ["-p", "err"],
                ["priority=err"],
            ),
            # Since filter
            (
                {"since": "today"},
                ["--since", "today"],
                ["since=today"],
            ),
            # Custom line count
            (
                {"lines": 50},
                ["-n", "50"],
                ["last 50 entries"],
            ),
            # All filters combined
            (
                {"unit": "nginx.service", "priority": "err", "since": "today", "lines": 50},
                ["-u", "nginx.service", "-p", "err", "--since", "today", "-n", "50"],
                ["last 50 entries", "unit=nginx.service", "priority=err", "since=today"],
            ),
        ],
    )
    async def test_get_journal_logs_filters(self, mock_execute_command, params, expected_args, expected_in_output):
        """Test get_journal_logs with various filter combinations."""
        mock_execute_command.return_value = (
            0,
            "Jan 01 12:00:00 host systemd[1]: Test log entry.",
            "",
        )

        result = await mcp.call_tool("get_journal_logs", params)
        output = assert_tool_result_structure(result)

        # Verify output contains expected strings
        for expected_str in expected_in_output:
            assert expected_str in output

        assert "Test log entry" in output

        # Verify command arguments
        mock_execute_command.assert_called_once()
        cmd_args = mock_execute_command.call_args[0][0]
        assert cmd_args[0] == "journalctl"
        for expected_arg in expected_args:
            assert expected_arg in cmd_args

    @pytest.mark.parametrize(
        "returncode,stdout,stderr,expected_error,expectation",
        [
            # Empty output
            (0, "", "", "No journal entries found", does_not_raise()),
            # Command error
            (1, "", "journalctl: Failed to access journal", "Error reading journal logs", does_not_raise()),
        ],
    )
    async def test_get_journal_logs_edge_cases(
        self, mock_execute_command, returncode, stdout, stderr, expected_error, expectation
    ):
        """Test get_journal_logs error handling and edge cases."""
        mock_execute_command.return_value = (returncode, stdout, stderr)

        with expectation:
            result = await mcp.call_tool("get_journal_logs", {})
            output = assert_tool_result_structure(result)
            assert expected_error in output

    async def test_get_journal_logs_journalctl_not_found(self, mock_execute_command):
        """Test get_journal_logs when journalctl is not available."""
        mock_execute_command.side_effect = FileNotFoundError("journalctl not found")

        result = await mcp.call_tool("get_journal_logs", {})
        output = assert_tool_result_structure(result)

        assert "journalctl command not found" in output
        assert "requires systemd" in output

    async def test_get_journal_logs_remote_execution(self, mock_execute_command):
        """Test get_journal_logs with remote execution."""
        mock_execute_command.return_value = (
            0,
            "Jan 01 12:00:00 remote systemd[1]: Remote log entry.",
            "",
        )

        result = await mcp.call_tool("get_journal_logs", {"host": "remote.server.com"})
        output = assert_tool_result_structure(result)

        assert "Remote log entry" in output

        # Verify host parameter was passed
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"


class TestGetAuditLogs:
    """Tests for get_audit_logs tool."""

    @pytest.mark.parametrize(
        "lines,expected_line_count",
        [
            (100, "100"),  # Default
            (50, "50"),  # Custom
        ],
    )
    async def test_get_audit_logs_success(self, mocker, mock_execute_command, lines, expected_line_count):
        """Test get_audit_logs with various line counts."""
        mocker.patch("linux_mcp_server.tools.logs.os.path.exists", return_value=True)
        mock_execute_command.return_value = (
            0,
            "type=SYSCALL msg=audit(1234567890.123:456): arch=c000003e syscall=1\n" * int(expected_line_count),
            "",
        )

        params = {"lines": lines} if lines != 100 else {}
        result = await mcp.call_tool("get_audit_logs", params)
        output = assert_tool_result_structure(result)

        assert f"last {expected_line_count} entries" in output
        assert "type=SYSCALL" in output

        # Verify command arguments
        cmd_args = mock_execute_command.call_args[0][0]
        assert cmd_args == ["tail", "-n", expected_line_count, "/var/log/audit/audit.log"]

    async def test_get_audit_logs_file_not_found_local(self, mocker):
        """Test get_audit_logs when audit log file doesn't exist locally."""
        mocker.patch("linux_mcp_server.tools.logs.os.path.exists", return_value=False)

        result = await mcp.call_tool("get_audit_logs", {})
        output = assert_tool_result_structure(result)

        assert "Audit log file not found" in output
        assert "/var/log/audit/audit.log" in output
        assert "may not be enabled" in output

    @pytest.mark.parametrize(
        "returncode,stderr,expected_error",
        [
            # Permission denied
            (1, "tail: cannot open '/var/log/audit/audit.log': Permission denied", "Permission denied"),
            # General error
            (1, "tail: error reading file", "Error reading audit logs"),
        ],
    )
    async def test_get_audit_logs_errors(self, mocker, mock_execute_command, returncode, stderr, expected_error):
        """Test get_audit_logs error handling."""
        mocker.patch("linux_mcp_server.tools.logs.os.path.exists", return_value=True)
        mock_execute_command.return_value = (returncode, "", stderr)

        result = await mcp.call_tool("get_audit_logs", {})
        output = assert_tool_result_structure(result)

        assert expected_error in output

    async def test_get_audit_logs_no_entries(self, mocker, mock_execute_command):
        """Test get_audit_logs when no entries found."""
        mocker.patch("linux_mcp_server.tools.logs.os.path.exists", return_value=True)
        mock_execute_command.return_value = (0, "", "")

        result = await mcp.call_tool("get_audit_logs", {})
        output = assert_tool_result_structure(result)

        assert "No audit log entries found" in output

    async def test_get_audit_logs_tail_not_found(self, mocker, mock_execute_command):
        """Test get_audit_logs when tail command is not available."""
        mocker.patch("linux_mcp_server.tools.logs.os.path.exists", return_value=True)
        mock_execute_command.side_effect = FileNotFoundError("tail not found")

        result = await mcp.call_tool("get_audit_logs", {})
        output = assert_tool_result_structure(result)

        assert "tail command not found" in output

    async def test_get_audit_logs_remote_execution(self, mock_execute_command):
        """Test get_audit_logs with remote execution."""
        mock_execute_command.return_value = (
            0,
            "type=SYSCALL msg=audit(1234567890.123:456): remote audit entry",
            "",
        )

        result = await mcp.call_tool("get_audit_logs", {"host": "remote.server.com"})
        output = assert_tool_result_structure(result)

        assert "remote audit entry" in output

        # Verify host parameter was passed
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"


class TestReadLogFile:
    async def test_read_log_file_success(self, mocker, tmp_path):
        """Test read_log_file with successful read."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        # Create a test log file
        log_file = tmp_path / "test.log"
        log_content = "Log line 1\nLog line 2\nLog line 3"
        log_file.write_text(log_content)

        # Set allowed paths
        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", str(log_file))

        mock_execute_command.return_value = (0, log_content, "")

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert f"=== Log File: {log_file} (last 100 lines) ===" in output
        assert "Log line 1" in output

    async def test_read_log_file_custom_lines(self, mocker, tmp_path):
        """Test read_log_file with custom line count."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")

        log_file = tmp_path / "test.log"
        log_file.write_text("Log content")

        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", str(log_file))

        mock_execute_command.return_value = (0, "Log content", "")

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_file), "lines": 50})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "last 50 lines" in output

        args = mock_execute_command.call_args[0][0]
        assert "-n" in args
        assert "50" in args

    async def test_read_log_file_no_allowed_paths(self, mocker):
        """Test read_log_file when no allowed paths are configured."""
        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", "")

        result = await mcp.call_tool("read_log_file", {"log_path": "/var/log/test.log"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "No log files are allowed" in output
        assert "LINUX_MCP_ALLOWED_LOG_PATHS" in output

    async def test_read_log_file_path_not_allowed(self, tmp_path, mocker):
        """Test read_log_file when path is not in allowed list."""
        allowed_file = tmp_path / "allowed.log"
        allowed_file.write_text("allowed")

        restricted_file = tmp_path / "restricted.log"
        restricted_file.write_text("restricted")

        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", str(allowed_file))

        result = await mcp.call_tool("read_log_file", {"log_path": str(restricted_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "not allowed" in output
        assert "Allowed log files" in output

    async def test_read_log_file_invalid_path(self, mocker):
        """Test read_log_file with an invalid path."""
        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", "/valid/path/log.log")

        result = await mcp.call_tool("read_log_file", {"log_path": "\x00invalid"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Invalid log file path" in output

    async def test_read_log_file_does_not_exist(self, tmp_path, mocker):
        """Test read_log_file when file doesn't exist."""
        non_existent = tmp_path / "nonexistent.log"
        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", str(non_existent))

        result = await mcp.call_tool("read_log_file", {"log_path": str(non_existent)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Log file not found" in output

    async def test_read_log_file_path_is_not_file(self, tmp_path, mocker):
        """Test read_log_file when path is a directory, not a file."""
        log_dir = tmp_path / "logdir"
        log_dir.mkdir()
        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", str(log_dir))

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_dir)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Path is not a file" in output

    async def test_read_log_file_permission_denied(self, mocker, tmp_path):
        """Test read_log_file handles permission denied errors."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        log_file = tmp_path / "restricted.log"
        log_file.write_text("content")

        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", str(log_file))

        mock_execute_command.return_value = (1, "", "tail: cannot open: Permission denied")

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Permission denied reading log file" in output

    async def test_read_log_file_empty(self, mocker, tmp_path):
        """Test read_log_file with empty log file."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (0, "", "")

        log_file = tmp_path / "empty.log"
        log_file.write_text("")

        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", str(log_file))

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Log file is empty" in output

    async def test_read_log_file_remote_execution(self, mocker):
        """Test read_log_file with remote execution."""
        log_path = "/var/log/remote.log"
        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", log_path)

        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (
            0,
            "Remote log content\nLine 2",
            "",
        )

        result = await mcp.call_tool("read_log_file", {"log_path": log_path, "host": "remote.server.com"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Remote log content" in output

        # Verify execute_command was called with host
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_read_log_file_remote_skips_path_validation(self, mocker):
        """Test that remote execution skips local path validation."""
        log_path = "/nonexistent/remote.log"
        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", log_path)

        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (0, "Remote content", "")

        # This path doesn't exist locally but should not raise an error for remote execution
        result = await mcp.call_tool("read_log_file", {"log_path": log_path, "host": "remote.server.com"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        # Should succeed even though path doesn't exist locally

    async def test_read_log_file_remote_command_failure(self, mocker):
        """Test read_log_file handles command failures for remote execution."""
        log_path = "/var/log/remote.log"
        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", log_path)

        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (1, "", "tail: cannot open: No such file or directory")

        result = await mcp.call_tool("read_log_file", {"log_path": log_path, "host": "remote.server.com"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Error reading log file" in output

    async def test_read_log_file_tail_not_found(self, mocker, tmp_path):
        """Test read_log_file when tail command is not available."""
        log_file = tmp_path / "test.log"
        log_file.write_text("content")

        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", str(log_file))

        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.side_effect = FileNotFoundError("tail not found")

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_file)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "tail command not found" in output

    async def test_read_log_file_multiple_allowed_paths(self, mocker, tmp_path):
        """Test read_log_file with multiple allowed paths."""
        log_file1 = tmp_path / "log1.log"
        log_file2 = tmp_path / "log2.log"
        log_file1.write_text("content1")
        log_file2.write_text("content2")

        # Set multiple allowed paths
        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", f"{log_file1},{log_file2}")

        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (0, "content2", "")

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_file2)})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "content2" in output

    async def test_read_log_file_access_not_allowed_with_host(self, tmp_path, mocker):
        """Test that a given path is not allowed when using host."""
        log_path_allowed = tmp_path / "log1.log"
        log_path_not_allowed = tmp_path / "log2.log"
        log_path_allowed.write_text("allowed")
        log_path_not_allowed.write_text("not allowed")

        # Set multiple allowed paths
        mocker.patch("linux_mcp_server.tools.logs.CONFIG.allowed_log_paths", str(log_path_allowed))

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_path_not_allowed), "host": "test.test.test"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text
        assert f"Access to log file '{log_path_not_allowed}' is not allowed." in output
