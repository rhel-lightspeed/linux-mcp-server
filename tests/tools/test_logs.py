"""Tests for log tools."""

from contextlib import nullcontext as does_not_raise

import pytest

from linux_mcp_server.server import mcp


@pytest.fixture
def mock_execute_command(mock_execute_command_for):
    """Logs-specific execute_command mock using the shared factory."""
    return mock_execute_command_for("linux_mcp_server.tools.logs")


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

    @pytest.mark.parametrize(
        "side_effect",
        (
            FileNotFoundError("journalctl command not found"),
            ValueError("Raised intentionally"),
        ),
    )
    async def test_get_journal_logs_journalctl_not_found(self, mocker, side_effect):
        """Test get_journal_logs failure."""
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_execute_command.side_effect = side_effect

        result = await mcp.call_tool("get_journal_logs", {})
        output = assert_tool_result_structure(result)

        assert str(side_effect).casefold() in output.casefold()

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

    @pytest.mark.parametrize(
        "side_effect",
        (
            FileNotFoundError("tail command not found"),
            ValueError("Raised intentionally"),
        ),
    )
    async def test_get_audit_logs_tail_not_found(self, mocker, side_effect):
        """Test get_audit_logs when tail command is not available."""
        mock_exists = mocker.patch("linux_mcp_server.tools.logs.os.path.exists")
        mock_execute_command = mocker.patch("linux_mcp_server.tools.logs.execute_command")
        mock_exists.return_value = True
        mock_execute_command.side_effect = side_effect

        result = await mcp.call_tool("get_audit_logs", {})
        output = assert_tool_result_structure(result)

        assert str(side_effect).casefold() in output.casefold()

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
    """Tests for read_log_file tool."""

    @pytest.fixture
    def setup_log_file(self, tmp_path, mock_allowed_log_paths):
        """Create a test log file and configure allowed paths."""

        def _setup(content="Test log content\nLine 2\nLine 3"):
            log_file = tmp_path / "test.log"
            log_file.write_text(content)
            mock_allowed_log_paths(str(log_file))
            return log_file

        return _setup

    @pytest.mark.parametrize(
        "lines,expected_line_count",
        [
            (100, "100"),  # Default
            (50, "50"),  # Custom
        ],
    )
    async def test_read_log_file_success(self, mock_execute_command, setup_log_file, lines, expected_line_count):
        """Test read_log_file with various line counts."""
        log_file = setup_log_file()
        mock_execute_command.return_value = (0, "Test log content\nLine 2", "")

        params = {"log_path": str(log_file)}
        if lines != 100:
            params["lines"] = lines

        result = await mcp.call_tool("read_log_file", params)
        output = assert_tool_result_structure(result)

        assert f"last {expected_line_count} lines" in output
        assert "Test log content" in output

        # Verify command arguments
        cmd_args = mock_execute_command.call_args[0][0]
        assert "-n" in cmd_args
        assert expected_line_count in cmd_args

    async def test_read_log_file_no_allowed_paths(self, mock_allowed_log_paths):
        """Test read_log_file when no allowed paths are configured."""
        mock_allowed_log_paths("")

        result = await mcp.call_tool("read_log_file", {"log_path": "/var/log/test.log"})
        output = assert_tool_result_structure(result)

        assert "No log files are allowed" in output
        assert "LINUX_MCP_ALLOWED_LOG_PATHS" in output

    @pytest.mark.parametrize(
        "test_scenario,path_resolver,expected_error",
        [
            # Invalid path
            ("invalid_path", lambda tp: "\x00invalid", "Invalid log file path"),
            # Path not in allowed list
            ("not_allowed", lambda tp: str(tp / "restricted.log"), "not allowed"),
        ],
    )
    async def test_read_log_file_path_validation(
        self, mock_allowed_log_paths, tmp_path, test_scenario, path_resolver, expected_error
    ):
        """Test read_log_file path validation scenarios."""
        # Setup allowed path
        allowed_file = tmp_path / "allowed.log"
        allowed_file.write_text("allowed")
        mock_allowed_log_paths(str(allowed_file))

        # Create restricted file for not_allowed scenario
        if test_scenario == "not_allowed":
            restricted_file = tmp_path / "restricted.log"
            restricted_file.write_text("restricted")

        test_path = path_resolver(tmp_path)
        result = await mcp.call_tool("read_log_file", {"log_path": test_path})
        output = assert_tool_result_structure(result)

        assert expected_error in output

    async def test_read_log_file_nonexistent_but_allowed(self, mock_allowed_log_paths, tmp_path):
        """Test read_log_file when path is allowed but file doesn't exist."""
        nonexistent_file = tmp_path / "nonexistent.log"
        mock_allowed_log_paths(str(nonexistent_file))

        result = await mcp.call_tool("read_log_file", {"log_path": str(nonexistent_file)})
        output = assert_tool_result_structure(result)

        assert "Log file not found" in output

    async def test_read_log_file_path_is_directory(self, mock_allowed_log_paths, tmp_path):
        """Test read_log_file when path is a directory, not a file."""
        log_dir = tmp_path / "logdir"
        log_dir.mkdir()
        mock_allowed_log_paths(str(log_dir))

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_dir)})
        output = assert_tool_result_structure(result)

        assert "Path is not a file" in output

    @pytest.mark.parametrize(
        "returncode,stderr,expected_error",
        [
            # Permission denied
            (1, "tail: cannot open: Permission denied", "Permission denied"),
            # General error
            (1, "tail: error reading file", "Error reading log file"),
        ],
    )
    async def test_read_log_file_command_errors(
        self, mock_execute_command, setup_log_file, returncode, stderr, expected_error
    ):
        """Test read_log_file command error handling."""
        log_file = setup_log_file()
        mock_execute_command.return_value = (returncode, "", stderr)

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_file)})
        output = assert_tool_result_structure(result)

        assert expected_error in output

    async def test_read_log_file_empty(self, mock_execute_command, setup_log_file):
        """Test read_log_file with empty log file."""
        log_file = setup_log_file(content="")
        mock_execute_command.return_value = (0, "", "")

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_file)})
        output = assert_tool_result_structure(result)

        assert "Log file is empty" in output

    async def test_read_log_file_tail_not_found(self, mock_execute_command, setup_log_file):
        """Test read_log_file when tail command is not available."""
        log_file = setup_log_file()
        mock_execute_command.side_effect = FileNotFoundError("tail not found")

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_file)})
        output = assert_tool_result_structure(result)

        assert "tail command not found" in output

    async def test_read_log_file_multiple_allowed_paths(self, mock_execute_command, mock_allowed_log_paths, tmp_path):
        """Test read_log_file with multiple allowed paths."""
        log_file1 = tmp_path / "log1.log"
        log_file2 = tmp_path / "log2.log"
        log_file1.write_text("content1")
        log_file2.write_text("content2")

        # Set multiple allowed paths
        mock_allowed_log_paths(f"{log_file1},{log_file2}")
        mock_execute_command.return_value = (0, "content2", "")

        result = await mcp.call_tool("read_log_file", {"log_path": str(log_file2)})
        output = assert_tool_result_structure(result)

        assert "content2" in output

    async def test_read_log_file_remote_execution(self, mock_execute_command, mock_allowed_log_paths):
        """Test read_log_file with remote execution."""
        log_path = "/var/log/remote.log"
        mock_allowed_log_paths(log_path)
        mock_execute_command.return_value = (0, "Remote log content\nLine 2", "")

        result = await mcp.call_tool("read_log_file", {"log_path": log_path, "host": "remote.server.com"})
        output = assert_tool_result_structure(result)

        assert "Remote log content" in output

        # Verify host parameter was passed
        call_kwargs = mock_execute_command.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_read_log_file_remote_skips_local_validation(self, mock_execute_command, mock_allowed_log_paths):
        """Test that remote execution skips local path validation."""
        log_path = "/nonexistent/remote.log"
        mock_allowed_log_paths(log_path)
        mock_execute_command.return_value = (0, "Remote content", "")

        # This path doesn't exist locally but should work for remote execution
        result = await mcp.call_tool("read_log_file", {"log_path": log_path, "host": "remote.server.com"})
        output = assert_tool_result_structure(result)

        assert "Remote content" in output

    async def test_read_log_file_remote_not_in_allowed_paths(self, mock_allowed_log_paths, tmp_path):
        """Test that remote execution still checks allowed paths."""
        allowed_path = tmp_path / "allowed.log"
        restricted_path = tmp_path / "restricted.log"
        allowed_path.write_text("allowed")
        restricted_path.write_text("restricted")

        mock_allowed_log_paths(str(allowed_path))

        result = await mcp.call_tool("read_log_file", {"log_path": str(restricted_path), "host": "remote.server.com"})
        output = assert_tool_result_structure(result)

        assert "not allowed" in output
