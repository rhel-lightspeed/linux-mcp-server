"""Tests for audit logging utilities."""

import pytest

from loguru import logger

from linux_mcp_server.audit import AuditContext
from linux_mcp_server.audit import Event
from linux_mcp_server.audit import ExecutionMode
from linux_mcp_server.audit import log_ssh_command
from linux_mcp_server.audit import log_ssh_connect
from linux_mcp_server.audit import sanitize_parameters
from linux_mcp_server.audit import SENSITIVE_FIELDS
from linux_mcp_server.audit import Status


class TestSanitizeParameters:
    """Test parameter sanitization."""

    def test_sanitize_empty_dict(self):
        """Test sanitizing empty parameters."""
        result = sanitize_parameters({})
        assert result == {}

    def test_sanitize_normal_parameters(self):
        """Test sanitizing normal parameters."""
        params = {"host": "testhost", "lines": 50, "service_name": "nginx"}
        result = sanitize_parameters(params)
        assert result == params

    def test_sanitize_password_field(self):
        """Test that password fields are sanitized."""
        params = {"username": "admin", "password": "secret123", "host": "testhost"}
        result = sanitize_parameters(params)
        assert result["username"] == "admin"
        assert result["password"] == "***REDACTED***"
        assert result["host"] == "testhost"

    def test_sanitize_api_key_field(self):
        """Test that API key fields are sanitized."""
        params = {"api_key": "secret_key_123", "host": "api.example.com"}
        result = sanitize_parameters(params)
        assert result["api_key"] == "***REDACTED***"
        assert result["host"] == "api.example.com"

    def test_sanitize_token_field(self):
        """Test that token fields are sanitized."""
        params = {"token": "bearer_token_123", "username": "admin"}
        result = sanitize_parameters(params)
        assert result["token"] == "***REDACTED***"
        assert result["username"] == "admin"

    def test_sanitize_nested_dict(self):
        """Test sanitizing nested dictionaries."""
        params = {
            "config": {
                "password": "secret",
                "host": "server.com",
            },
            "username": "admin",
        }
        result = sanitize_parameters(params)
        assert result["config"]["password"] == "***REDACTED***"
        assert result["config"]["host"] == "server.com"
        assert result["username"] == "admin"


class TestAuditContext:
    """Test audit context manager."""

    def test_context_creates_logger(self):
        """Test that context creates a logger with extra fields."""
        with AuditContext(tool="test_tool", host="testhost") as log:
            # AuditContext yields the loguru logger
            assert log is logger

    def test_context_fields_in_log(self, loguru_caplog):
        """Test that context fields appear in log records."""
        with AuditContext(tool="test_tool", host="testhost") as log:
            log.info("Test message")

        # Check that log record has the extra fields
        filtered = [r for r in loguru_caplog.records if "Test message" in r["message"]]
        assert filtered, "expected log record with 'Test message'"
        record = filtered[0]
        assert record["extra"]["tool"] == "test_tool"
        assert record["extra"]["host"] == "testhost"


class TestLogToolCall:
    """Test tool call logging."""

    @pytest.mark.parametrize(
        ("params", "mode"),
        (
            ({}, ExecutionMode.LOCAL),
            ({"host": "testhost", "username": "admin"}, ExecutionMode.REMOTE),
        ),
    )
    def test_log_tool_call(self, loguru_caplog, decorated, params, mode):
        """Test logging a sync tool call."""
        decorated(**params)

        assert Event.TOOL_CALL in loguru_caplog.text
        assert "list_services" in loguru_caplog.text

        # Check execution mode in extra
        filtered = [r for r in loguru_caplog.records if Event.TOOL_CALL in r["message"]]
        assert filtered, "expected TOOL_CALL log record"
        assert filtered[0]["extra"]["execution_mode"] == mode

    @pytest.mark.parametrize(
        ("params", "mode"),
        (
            ({}, ExecutionMode.LOCAL),
            ({"host": "testhost", "username": "admin"}, ExecutionMode.REMOTE),
        ),
    )
    async def test_log_tool_call_async(self, loguru_caplog, adecorated, params, mode):
        """Test logging an async call."""
        await adecorated(**params)

        assert Event.TOOL_CALL in loguru_caplog.text
        assert "list_services" in loguru_caplog.text

        # Check execution mode in extra
        filtered = [r for r in loguru_caplog.records if Event.TOOL_CALL in r["message"]]
        assert filtered, "expected TOOL_CALL log record"
        assert filtered[0]["extra"]["execution_mode"] == mode

    @pytest.mark.parametrize("sensitive_field", SENSITIVE_FIELDS)
    def test_log_tool_call_sanitizes_parameters(self, loguru_caplog, decorated, sensitive_field):
        """Test that tool call logging sanitizes sensitive parameters."""
        secret_value = "secret123"
        params = {sensitive_field: secret_value, "username": "admin"}
        decorated(**params)

        assert Event.TOOL_CALL in loguru_caplog.text
        assert secret_value not in loguru_caplog.text
        assert "REDACTED" in loguru_caplog.text

    @pytest.mark.parametrize("sensitive_field", SENSITIVE_FIELDS)
    async def test_log_tool_call_async_sanitizes_parameters(self, loguru_caplog, adecorated, sensitive_field):
        """Test that tool call logging sanitizes sensitive parameters."""
        secret_value = "secret123"
        params = {sensitive_field: secret_value, "username": "admin"}
        await adecorated(**params)

        assert Event.TOOL_CALL in loguru_caplog.text
        assert secret_value not in loguru_caplog.text
        assert "REDACTED" in loguru_caplog.text

    def test_log_tool_call_failure(self, loguru_caplog, decorated_fail):
        """Test logging a tool call that raises an exception."""
        with pytest.raises(ValueError, match="Raised intentionally"):
            decorated_fail()

        assert "error: Raised intentionally" in loguru_caplog.text

    async def test_log_tool_call_async_failure(self, loguru_caplog, adecorated_fail):
        """Test logging an async tool call that raises an exception."""
        with pytest.raises(ValueError, match="Raised intentionally"):
            await adecorated_fail()

        assert "error: Raised intentionally" in loguru_caplog.text


class TestLogSSHConnect:
    """Test SSH connection logging."""

    def test_log_ssh_connect_success_info(self, loguru_caplog):
        """Test logging successful SSH connection at INFO level."""
        log_ssh_connect("testhost", status=Status.success, reused=False)

        assert Event.SSH_CONNECT in loguru_caplog.text
        assert "testhost" in loguru_caplog.text

        record = loguru_caplog.records[-1]
        assert record["extra"]["status"] == "success"

    def test_log_ssh_connect_with_extra_details(self, loguru_caplog):
        """Test logging successful SSH connection includes reused and key_path in extra."""
        log_ssh_connect(
            "testhost",
            status=Status.success,
            reused=True,
            key_path="/home/user/.ssh/id_rsa",
        )

        assert Event.SSH_CONNECT in loguru_caplog.text
        assert "testhost" in loguru_caplog.text

        record = loguru_caplog.records[-1]
        assert record["extra"]["status"] == "success"
        assert record["extra"]["reused"] == "True"
        assert ".ssh/id_rsa" in record["extra"]["key"]

    def test_log_ssh_connect_failure(self, loguru_caplog):
        """Test logging failed SSH connection."""
        log_ssh_connect("testhost", status=Status.failed, error="Permission denied")

        assert Event.SSH_AUTH_FAILED in loguru_caplog.text
        assert "testhost" in loguru_caplog.text
        assert "Permission denied" in loguru_caplog.text


class TestLogSSHCommand:
    """Test SSH command execution logging."""

    def test_log_ssh_command_info(self, loguru_caplog):
        """Test logging SSH command at INFO level."""
        log_ssh_command("systemctl status nginx", "testhost", exit_code=0, duration=0.15)

        assert Event.REMOTE_EXEC in loguru_caplog.text
        assert "systemctl status nginx" in loguru_caplog.text
        assert "testhost" in loguru_caplog.text
        assert "exit_code=0" in loguru_caplog.text

    def test_log_ssh_command_includes_duration(self, loguru_caplog):
        """Test logging SSH command includes duration when provided."""
        log_ssh_command("ls -la", "testhost", exit_code=0, duration=0.05)

        assert Event.REMOTE_EXEC in loguru_caplog.text
        assert "ls -la" in loguru_caplog.text
        assert "duration" in loguru_caplog.text.lower()

    def test_log_ssh_command_error(self, loguru_caplog):
        """Test logging SSH command with non-zero exit code."""
        log_ssh_command("systemctl status missing", "testhost", exit_code=3, duration=0.1)

        assert Event.REMOTE_EXEC in loguru_caplog.text
        assert "exit_code=3" in loguru_caplog.text
