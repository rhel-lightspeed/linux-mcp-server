"""Tests for log tools."""

from contextlib import nullcontext as does_not_raise
from unittest.mock import AsyncMock

import pytest

from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.server import mcp


def assert_tool_result_structure(result):
    """Verify common result structure returned by all tools."""
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], list)
    return result[0][0].text


class TestGetJournalLogs:
    async def test_get_journal_logs_default(self, mocker):
        """Test get_journal_logs with default parameters."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (
            0,
            "Jan 01 12:00:00 host systemd[1]: Started some service.\nJan 01 12:01:00 host systemd[1]: Stopped some service.",
            "",
        )

        result = await mcp.call_tool("get_journal_logs", {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "=== Journal Logs (last 100 entries, no filters) ===" in output
        assert "Started some service" in output
        assert "Stopped some service" in output

        # Verify journalctl was called with correct arguments
        mock_execute_command.assert_called_once()
        args = mock_execute_command.call_args[0][0]
        assert args[0] == "journalctl"
        assert "-n" in args
        assert "100" in args
        assert "--no-pager" in args

    async def test_get_journal_logs_with_unit_filter(self, mocker):
        """Test get_journal_logs with unit filter."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (
            0,
            "Jan 01 12:00:00 host nginx[123]: Started nginx.",
            "",
        )

        result = await mcp.call_tool("get_journal_logs", {"unit": "nginx.service"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "unit=nginx.service" in output
        assert "Started nginx" in output

        # Verify unit filter was passed
        args = mock_execute_command.call_args[0][0]
        assert "-u" in args
        assert "nginx.service" in args

    async def test_get_journal_logs_with_priority_filter(self, mocker):
        """Test get_journal_logs with priority filter."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (
            0,
            "Jan 01 12:00:00 host systemd[1]: Error occurred.",
            "",
        )

        result = await mcp.call_tool("get_journal_logs", {"priority": "err"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "priority=err" in output
        assert "Error occurred" in output

        # Verify priority filter was passed
        args = mock_execute_command.call_args[0][0]
        assert "-p" in args
        assert "err" in args

    async def test_get_journal_logs_with_since_filter(self, mocker):
        """Test get_journal_logs with since filter."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (
            0,
            "Jan 01 13:00:00 host systemd[1]: Recent log entry.",
            "",
        )

        result = await mcp.call_tool("get_journal_logs", {"since": "today"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "since=today" in output
        assert "Recent log entry" in output

        # Verify since filter was passed
        args = mock_execute_command.call_args[0][0]
        assert "--since" in args
        assert "today" in args

    async def test_get_journal_logs_with_all_filters(self, mocker):
        """Test get_journal_logs with all filters combined."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (
            0,
            "Jan 01 13:00:00 host nginx[123]: Error in nginx.",
            "",
        )

        result = await mcp.call_tool(
            "get_journal_logs", {"unit": "nginx.service", "priority": "err", "since": "today", "lines": 50}
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "last 50 entries" in output
        assert "unit=nginx.service" in output
        assert "priority=err" in output
        assert "since=today" in output

        # Verify all filters were passed
        args = mock_execute_command.call_args[0][0]
        assert "-u" in args
        assert "nginx.service" in args
        assert "-p" in args
        assert "err" in args
        assert "--since" in args
        assert "today" in args
        assert "-n" in args
        assert "50" in args

    async def test_get_journal_logs_no_entries_found(self, mocker):
        """Test get_journal_logs when no entries match criteria."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (0, "", "")

        result = await mcp.call_tool("get_journal_logs", {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "No journal entries found matching the criteria" in output

    async def test_get_journal_logs_command_error(self, mocker):
        """Test get_journal_logs handles command errors."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (1, "", "journalctl: Failed to access journal")

        result = await mcp.call_tool("get_journal_logs", {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Error reading journal logs" in output
        assert "Failed to access journal" in output

    async def test_get_journal_logs_journalctl_not_found(self, mocker):
        """Test get_journal_logs when journalctl is not available."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.side_effect = FileNotFoundError("journalctl not found")

        result = await mcp.call_tool("get_journal_logs", {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "journalctl command not found" in output
        assert "requires systemd" in output

    async def test_get_journal_logs_remote_execution(self, mocker):
        """Test get_journal_logs with remote execution."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (
            0,
            "Jan 01 12:00:00 remote systemd[1]: Remote log entry.",
            "",
        )

        result = await mcp.call_tool("get_journal_logs", {"host": "remote.server.com"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Remote log entry" in output

        # Verify execute_command was called with host
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"


class TestGetAuditLogs:
    async def test_get_audit_logs_success(self, mocker):
        """Test get_audit_logs with successful read."""
        mock_exists = mocker.patch("linux_mcp_server.tools.logs.os.path.exists")
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_exists.return_value = True
        mock_execute_command.return_value = (
            0,
            "type=SYSCALL msg=audit(1234567890.123:456): arch=c000003e syscall=1\ntype=SYSCALL msg=audit(1234567890.124:457): arch=c000003e syscall=2",
            "",
        )

        result = await mcp.call_tool("get_audit_logs", {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "=== Audit Logs (last 100 entries) ===" in output
        assert "type=SYSCALL" in output
        assert "syscall=1" in output

        # Verify tail command was called correctly
        args = mock_execute_command.call_args[0][0]
        assert args[0] == "tail"
        assert "-n" in args
        assert "100" in args
        assert "/var/log/audit/audit.log" in args

    async def test_get_audit_logs_custom_lines(self, mocker):
        """Test get_audit_logs with custom line count."""
        mock_exists = mocker.patch("linux_mcp_server.tools.logs.os.path.exists")
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_exists.return_value = True
        mock_execute_command.return_value = (0, "audit log entry", "")

        result = await mcp.call_tool("get_audit_logs", {"lines": 50})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "last 50 entries" in output

        args = mock_execute_command.call_args[0][0]
        assert "-n" in args
        assert "50" in args

    async def test_get_audit_logs_file_not_found(self, mocker):
        """Test get_audit_logs when audit log file doesn't exist locally."""
        mock_exists = mocker.patch("linux_mcp_server.tools.logs.os.path.exists")
        mock_exists.return_value = False

        result = await mcp.call_tool("get_audit_logs", {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Audit log file not found" in output
        assert "/var/log/audit/audit.log" in output
        assert "may not be enabled" in output

    async def test_get_audit_logs_permission_denied(self, mocker):
        """Test get_audit_logs handles permission denied errors."""
        mock_exists = mocker.patch("linux_mcp_server.tools.logs.os.path.exists")
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_exists.return_value = True
        mock_execute_command.return_value = (1, "", "tail: cannot open '/var/log/audit/audit.log': Permission denied")

        result = await mcp.call_tool("get_audit_logs", {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Permission denied reading audit logs" in output
        assert "requires elevated privileges" in output
        assert "root" in output

    async def test_get_audit_logs_command_error(self, mocker):
        """Test get_audit_logs handles general command errors."""
        mock_exists = mocker.patch("linux_mcp_server.tools.logs.os.path.exists")
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_exists.return_value = True
        mock_execute_command.return_value = (1, "", "tail: error reading file")

        result = await mcp.call_tool("get_audit_logs", {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "Error reading audit logs" in output
        assert "error reading file" in output

    async def test_get_audit_logs_no_entries(self, mocker):
        """Test get_audit_logs when no entries found."""
        mock_exists = mocker.patch("linux_mcp_server.tools.logs.os.path.exists")
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_exists.return_value = True
        mock_execute_command.return_value = (0, "", "")

        result = await mcp.call_tool("get_audit_logs", {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "No audit log entries found" in output

    async def test_get_audit_logs_remote_execution(self, mocker):
        """Test get_audit_logs with remote execution."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.return_value = (
            0,
            "type=SYSCALL msg=audit(1234567890.123:456): remote audit entry",
            "",
        )

        result = await mcp.call_tool("get_audit_logs", {"host": "remote.server.com"})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "remote audit entry" in output

        # Verify execute_command was called with host
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_get_audit_logs_tail_not_found(self, mocker):
        """Test get_audit_logs when tail command is not available."""
        mock_exists = mocker.patch("linux_mcp_server.tools.logs.os.path.exists")
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_exists.return_value = True
        mock_execute_command.side_effect = FileNotFoundError("tail not found")

        result = await mcp.call_tool("get_audit_logs", {})

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        output = result[0][0].text

        assert "tail command not found" in output


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
