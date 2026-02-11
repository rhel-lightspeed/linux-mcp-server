"""Tests for log tools."""

import pytest

from fastmcp.exceptions import ToolError


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
        "params, expected_args, expected_fields",
        [
            # Default parameters
            (
                {},
                ["-n", "100", "--no-pager"],
                {"unit": None, "priority": None, "since": None, "transport": None},
            ),
            # Unit filter
            (
                {"unit": "nginx.service"},
                ["--unit", "nginx.service"],
                {"unit": "nginx.service"},
            ),
            # Priority filter
            (
                {"priority": "err"},
                ["--priority", "err"],
                {"priority": "err"},
            ),
            # Since filter
            (
                {"since": "today"},
                ["--since", "today"],
                {"since": "today"},
            ),
            # Custom line count
            (
                {"lines": 50},
                ["-n", "50"],
                {"unit": None},
            ),
            # All filters combined
            (
                {"unit": "nginx.service", "priority": "err", "since": "today", "lines": 50},
                ["--unit", "nginx.service", "--priority", "err", "--since", "today", "-n", "50"],
                {"unit": "nginx.service", "priority": "err", "since": "today"},
            ),
            # Transport filter (audit)
            (
                {"transport": "audit"},
                ["_TRANSPORT=audit"],
                {"transport": "audit"},
            ),
            (
                {"transport": "kernel"},
                ["_TRANSPORT=kernel"],
                {"transport": "kernel"},
            ),
            (
                {"transport": "audit", "priority": "err", "lines": 50},
                ["_TRANSPORT=audit", "--priority", "err", "-n", "50"],
                {"transport": "audit", "priority": "err"},
            ),
        ],
    )
    async def test_get_journal_logs_filters(
        self, mcp_client, mock_execute_with_fallback, params, expected_args, expected_fields
    ):
        """Test get_journal_logs with various filter combinations."""
        mock_execute_with_fallback.return_value = (
            0,
            "Jan 01 12:00:00 host systemd[1]: Test log entry.",
            "",
        )

        result = await mcp_client.call_tool("get_journal_logs", params)
        content = result.structured_content
        cmd_args = mock_execute_with_fallback.call_args.args[0]

        assert "Jan 01 12:00:00 host systemd[1]: Test log entry." in content["entries"]
        assert content["lines_count"] == 1
        assert cmd_args[0] == "journalctl"
        assert all(content[field] == value for field, value in expected_fields.items())
        assert all(arg in cmd_args for arg in expected_args)
        assert mock_execute_with_fallback.call_count == 1

    @pytest.mark.parametrize(
        "returncode, stdout, stderr, match",
        [
            # Empty output
            (0, "", "", "No journal entries found"),
            # Command error
            (1, "", "Journalctl: failed to access journal", "Error reading journal logs"),
        ],
    )
    async def test_get_journal_logs_failure(
        self, mcp_client, mock_execute_with_fallback, returncode, stdout, stderr, match
    ):
        """Test get_journal_logs error handling and edge cases."""
        mock_execute_with_fallback.return_value = (returncode, stdout, stderr)

        with pytest.raises(ToolError, match=match):
            await mcp_client.call_tool("get_journal_logs", {})

    @pytest.mark.parametrize(
        "side_effect",
        (
            FileNotFoundError("journalctl command not found"),
            ValueError("raised intentionally"),
        ),
    )
    async def test_get_journal_logs_journalctl_not_found(self, mcp_client, mocker, side_effect):
        """Test get_journal_logs failure."""
        mock_execute_with_fallback = mocker.patch("linux_mcp_server.commands.execute_with_fallback", autospec=True)
        mock_execute_with_fallback.side_effect = side_effect

        with pytest.raises(ToolError, match=side_effect.args[0]):
            await mcp_client.call_tool("get_journal_logs", {})

    async def test_get_journal_logs_invalid_transport(self, mcp_client, mock_execute_with_fallback):
        """Test get_journal_logs rejects invalid transport values via MCP validation."""
        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool("get_journal_logs", {"transport": "invalid"})

        assert "validation error" in str(exc_info.value).casefold() or "invalid" in str(exc_info.value).casefold()
        mock_execute_with_fallback.assert_not_called()

    async def test_get_journal_logs_remote_execution(self, mcp_client, mock_execute_with_fallback):
        """Test get_journal_logs with remote execution."""
        mock_execute_with_fallback.return_value = (
            0,
            "Jan 01 12:00:00 remote systemd[1]: remote log entry.",
            "",
        )

        result = await mcp_client.call_tool("get_journal_logs", {"host": "remote.server.com"})
        content = result.structured_content

        assert "Jan 01 12:00:00 remote systemd[1]: remote log entry." in content["entries"]

        call_kwargs = mock_execute_with_fallback.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_get_journal_logs_multiple_entries(self, mcp_client, mock_execute_with_fallback):
        """Test get_journal_logs returns multiple entries."""
        mock_execute_with_fallback.return_value = (
            0,
            "Jan 01 12:00:00 host sshd[1]: Entry one\nJan 01 12:00:01 host sshd[1]: Entry two\nJan 01 12:00:02 host sshd[1]: Entry three",
            "",
        )

        result = await mcp_client.call_tool("get_journal_logs", {})
        content = result.structured_content

        assert content["lines_count"] == 3
        assert len(content["entries"]) == 3


class TestReadLogFile:
    """Tests for read_log_file tool."""

    @pytest.fixture
    def setup_log_file(self, mcp_client, tmp_path, mock_allowed_log_paths):
        """Create a test log file and configure allowed paths."""

        def _setup(content="Test log content\nLine 2\nLine 3"):
            log_file = tmp_path / "test.log"
            log_file.write_text(content)
            mock_allowed_log_paths(str(log_file))
            return log_file

        return _setup

    async def test_read_log_file_success(self, mcp_client, mock_execute_with_fallback, setup_log_file):
        """Test read_log_file returns structured data."""
        log_file = setup_log_file()
        mock_execute_with_fallback.return_value = (0, "Test log content\nLine 2", "")

        result = await mcp_client.call_tool("read_log_file", {"log_path": log_file})
        content = result.structured_content

        assert content["entries"] == ["Test log content", "Line 2"]
        assert content["lines_count"] == 2
        assert content["path"] == str(log_file)

        cmd_args = mock_execute_with_fallback.call_args[0][0]
        assert "-n" in cmd_args
        assert "100" in cmd_args

    async def test_read_log_file_custom_lines(self, mcp_client, mock_execute_with_fallback, setup_log_file):
        """Test read_log_file with custom line count."""
        log_file = setup_log_file()
        mock_execute_with_fallback.return_value = (0, "Test log content\nLine 2", "")

        result = await mcp_client.call_tool("read_log_file", {"log_path": log_file, "lines": 50})
        content = result.structured_content

        assert content["lines_count"] == 2

        cmd_args = mock_execute_with_fallback.call_args[0][0]
        assert "50" in cmd_args

    async def test_read_log_file_no_allowed_paths(self, mcp_client, mock_allowed_log_paths):
        """Test read_log_file when no allowed paths are configured."""
        mock_allowed_log_paths("")

        with pytest.raises(ToolError, match="No log files are allowed"):
            await mcp_client.call_tool("read_log_file", {"log_path": "/var/log/test.log"})

    @pytest.mark.parametrize(
        "test_scenario, log_path, match",
        [
            ("invalid_path", "\x00invalid", "Path contains invalid characters"),
            ("not_allowed", "restricted.log", "not allowed"),
        ],
        ids=["invalid-path", "path-not-in-list"],
    )
    async def test_read_log_file_path_validation(
        self, mcp_client, mock_allowed_log_paths, tmp_path, test_scenario, log_path, match
    ):
        """Test read_log_file path validation scenarios."""
        allowed_file = tmp_path / "allowed.log"
        allowed_file.write_text("allowed")
        mock_allowed_log_paths(str(allowed_file))

        restricted_file = tmp_path / "restricted.log"
        restricted_file.write_text("restricted")

        test_path = tmp_path / log_path
        with pytest.raises(ToolError, match=match):
            await mcp_client.call_tool("read_log_file", {"log_path": test_path})

    async def test_read_log_file_nonexistent_but_allowed(self, mcp_client, mock_allowed_log_paths, tmp_path):
        """Test read_log_file when path is allowed but file doesn't exist."""
        nonexistent_file = tmp_path / "nonexistent.log"
        mock_allowed_log_paths(str(nonexistent_file))

        with pytest.raises(ToolError, match="Log file not found"):
            await mcp_client.call_tool("read_log_file", {"log_path": nonexistent_file})

    async def test_read_log_file_path_is_directory(self, mcp_client, mock_allowed_log_paths, tmp_path):
        """Test read_log_file when path is a directory, not a file."""
        log_dir = tmp_path / "logdir"
        log_dir.mkdir()
        mock_allowed_log_paths(str(log_dir))

        with pytest.raises(ToolError, match="Path is not a file"):
            await mcp_client.call_tool("read_log_file", {"log_path": log_dir})

    @pytest.mark.parametrize(
        "returncode, stderr, match",
        [
            (1, "tail: cannot open: Permission denied", "Permission denied"),
            (1, "tail: error reading file", "Error reading log file"),
        ],
    )
    async def test_read_log_file_command_errors(
        self, mcp_client, mock_execute_with_fallback, setup_log_file, returncode, stderr, match
    ):
        """Test read_log_file command error handling."""
        log_file = setup_log_file()
        mock_execute_with_fallback.return_value = (returncode, "", stderr)

        with pytest.raises(ToolError, match=match):
            await mcp_client.call_tool("read_log_file", {"log_path": log_file})

    async def test_read_log_file_empty(self, mcp_client, mock_execute_with_fallback, setup_log_file):
        """Test read_log_file with empty log file."""
        log_file = setup_log_file(content="")
        mock_execute_with_fallback.return_value = (0, "", "")

        with pytest.raises(ToolError, match="Log file is empty"):
            await mcp_client.call_tool("read_log_file", {"log_path": log_file})

    async def test_read_log_file_tail_not_found(self, mcp_client, mock_execute_with_fallback, setup_log_file):
        """Test read_log_file when tail command is not available."""
        log_file = setup_log_file()
        mock_execute_with_fallback.side_effect = FileNotFoundError("tail not found")

        with pytest.raises(ToolError, match="tail not found"):
            await mcp_client.call_tool("read_log_file", {"log_path": log_file})

    async def test_read_log_file_multiple_allowed_paths(
        self, mcp_client, mock_execute_with_fallback, mock_allowed_log_paths, tmp_path
    ):
        """Test read_log_file with multiple allowed paths."""
        log_file1 = tmp_path / "log1.log"
        log_file2 = tmp_path / "log2.log"
        log_file1.write_text("content1")
        log_file2.write_text("content2")

        mock_allowed_log_paths(f"{log_file1},{log_file2}")
        mock_execute_with_fallback.return_value = (0, "content2", "")

        result = await mcp_client.call_tool("read_log_file", {"log_path": log_file2})
        content = result.structured_content

        assert "content2" in content["entries"]

    async def test_read_log_file_remote_execution(self, mcp_client, mock_execute_with_fallback, mock_allowed_log_paths):
        """Test read_log_file with remote execution."""
        log_path = "/var/log/remote.log"
        mock_allowed_log_paths(log_path)
        mock_execute_with_fallback.return_value = (0, "Remote log content\nLine 2", "")

        result = await mcp_client.call_tool("read_log_file", {"log_path": log_path, "host": "remote.server.com"})
        content = result.structured_content

        assert "Remote log content" in content["entries"]
        assert content["path"] == log_path

        call_kwargs = mock_execute_with_fallback.call_args[1]
        assert call_kwargs["host"] == "remote.server.com"

    async def test_read_log_file_remote_skips_local_validation(
        self, mcp_client, mock_execute_with_fallback, mock_allowed_log_paths
    ):
        """Test that remote execution skips local path validation."""
        log_path = "/nonexistent/remote.log"
        mock_allowed_log_paths(log_path)
        mock_execute_with_fallback.return_value = (0, "Remote content", "")

        result = await mcp_client.call_tool("read_log_file", {"log_path": log_path, "host": "remote.server.com"})
        content = result.structured_content

        assert "Remote content" in content["entries"]

    async def test_read_log_file_remote_not_in_allowed_paths(self, mcp_client, mock_allowed_log_paths, tmp_path):
        """Test that remote execution still checks allowed paths."""
        allowed_path = tmp_path / "allowed.log"
        restricted_path = tmp_path / "restricted.log"
        allowed_path.write_text("allowed")
        restricted_path.write_text("restricted")

        mock_allowed_log_paths(str(allowed_path))

        with pytest.raises(ToolError, match="not allowed"):
            await mcp_client.call_tool("read_log_file", {"log_path": restricted_path, "host": "remote.server.com"})
