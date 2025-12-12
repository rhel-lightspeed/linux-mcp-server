"""Tests for audit logging utilities."""

import logging

import pytest

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
        params = {"host": "server1.com", "lines": 50, "service_name": "nginx"}
        result = sanitize_parameters(params)
        assert result == params

    def test_sanitize_password_field(self):
        """Test that password fields are sanitized."""
        params = {"username": "admin", "password": "secret123", "host": "server1.com"}
        result = sanitize_parameters(params)
        assert result["username"] == "admin"
        assert result["password"] == "***REDACTED***"
        assert result["host"] == "server1.com"

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
        with AuditContext(tool="test_tool", host="server1.com") as logger:
            # AuditContext returns a LoggerAdapter, not a Logger
            assert isinstance(logger, (logging.Logger, logging.LoggerAdapter))

    def test_context_fields_in_log(self):
        """Test that context fields appear in log records."""
        # Create a custom handler to capture records
        test_handler = logging.Handler()
        test_handler.setLevel(logging.INFO)
        records = []

        class RecordCapture(logging.Handler):
            def emit(self, record):
                records.append(record)

        capture = RecordCapture()
        capture.setLevel(logging.INFO)

        root_logger = logging.getLogger()
        root_logger.addHandler(capture)
        root_logger.setLevel(logging.INFO)

        try:
            with AuditContext(tool="test_tool", host="server1.com") as logger:
                logger.info("Test message")

            # Check that log record has the extra fields
            assert len(records) >= 1
            record = [r for r in records if "Test message" in r.getMessage()][0]
            assert hasattr(record, "tool")
            assert record.tool == "test_tool"
            assert hasattr(record, "host")
            assert record.host == "server1.com"
        finally:
            root_logger.removeHandler(capture)


class TestLogToolCall:
    """Test tool call logging."""

    @pytest.mark.parametrize(
        ("params", "mode"),
        (
            ({}, ExecutionMode.LOCAL),
            ({"host": "server1.com", "username": "admin"}, ExecutionMode.REMOTE),
        ),
    )
    def test_log_tool_call(self, caplog, decorated, params, mode):
        """Test logging a sync tool call."""
        with caplog.at_level(logging.INFO):
            decorated(**params)

        record = caplog.records[0]

        assert Event.TOOL_CALL in caplog.text
        assert "list_services" in caplog.text
        assert caplog.records
        assert getattr(record, "execution_mode") == mode

    @pytest.mark.parametrize(
        ("params", "mode"),
        (
            ({}, ExecutionMode.LOCAL),
            ({"host": "server1.com", "username": "admin"}, ExecutionMode.REMOTE),
        ),
    )
    async def test_log_tool_call_async(self, caplog, adecorated, params, mode):
        """Test logging an async call."""
        with caplog.at_level(logging.INFO):
            await adecorated(**params)

        record = caplog.records[0]

        assert Event.TOOL_CALL in caplog.text
        assert "list_services" in caplog.text
        assert caplog.records
        assert getattr(record, "execution_mode", None) == mode

    @pytest.mark.parametrize("sensitive_field", SENSITIVE_FIELDS)
    def test_log_tool_call_sanitizes_parameters(self, caplog, decorated, sensitive_field):
        """Test that tool call logging sanitizes sensitive parameters."""
        secret_value = "secret123"
        params = {sensitive_field: secret_value, "username": "admin"}
        with caplog.at_level(logging.INFO):
            decorated(**params)

        assert Event.TOOL_CALL in caplog.text
        assert secret_value not in caplog.text
        assert "REDACTED" in caplog.text

    @pytest.mark.parametrize("sensitive_field", SENSITIVE_FIELDS)
    async def test_log_tool_call_async_sanitizes_parameters(self, caplog, adecorated, sensitive_field):
        """Test that tool call logging sanitizes sensitive parameters."""
        secret_value = "secret123"
        params = {sensitive_field: secret_value, "username": "admin"}
        with caplog.at_level(logging.INFO):
            await adecorated(**params)

        assert Event.TOOL_CALL in caplog.text
        assert secret_value not in caplog.text
        assert "REDACTED" in caplog.text

    def test_log_tool_call_failure(self, caplog, decorated_fail):
        with caplog.at_level(logging.INFO), pytest.raises(ValueError, match="Raised intentionally"):
            decorated_fail()

        assert "error: Raised intentionally" in caplog.text

    async def test_log_tool_call_async_failure(self, caplog, adecorated_fail):
        with caplog.at_level(logging.INFO):
            with pytest.raises(ValueError, match="Raised intentionally"):
                await adecorated_fail()

        assert "error: Raised intentionally" in caplog.text


class TestLogSSHConnect:
    """Test SSH connection logging."""

    def test_log_ssh_connect_success_info(self, caplog):
        """Test logging successful SSH connection at INFO level."""
        with caplog.at_level(logging.INFO):
            log_ssh_connect("server1.com", status=Status.success, reused=False)

        assert Event.SSH_CONNECT in caplog.text
        assert "server1.com" in caplog.text
        # Check the log record attributes
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "status")
        assert record.status == "success"
        # At INFO level, reused might not be in the record if logger is not at DEBUG
        # (depends on implementation)

    def test_log_ssh_connect_success_debug(self, caplog):
        """Test logging successful SSH connection at DEBUG level shows more details."""
        # Set the root logger to DEBUG level so our check in log_ssh_connect works
        logging.getLogger().setLevel(logging.DEBUG)

        with caplog.at_level(logging.DEBUG):
            log_ssh_connect("server1.com", status=Status.success, reused=True, key_path="/home/user/.ssh/id_rsa")

        assert Event.SSH_CONNECT in caplog.text
        assert "server1.com" in caplog.text
        # Check the log record attributes
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "status")
        assert record.status == "success"
        # At DEBUG level, SHOULD show reused status and key path
        assert hasattr(record, "reused")
        assert record.reused
        assert hasattr(record, "key")
        assert ".ssh/id_rsa" in record.key

    def test_log_ssh_connect_failure(self, caplog):
        """Test logging failed SSH connection."""
        with caplog.at_level(logging.WARNING):
            log_ssh_connect("server1.com", status="failed", error="Permission denied")

        assert Event.SSH_CONNECT in caplog.text or Event.SSH_AUTH_FAILED in caplog.text
        assert "server1.com" in caplog.text
        assert "Permission denied" in caplog.text


class TestLogSSHCommand:
    """Test SSH command execution logging."""

    def test_log_ssh_command_info(self, caplog):
        """Test logging SSH command at INFO level."""
        with caplog.at_level(logging.INFO):
            log_ssh_command("systemctl status nginx", "server1.com", exit_code=0, duration=0.15)

        assert Event.REMOTE_EXEC in caplog.text
        assert "systemctl status nginx" in caplog.text
        assert "server1.com" in caplog.text
        assert "exit_code=0" in caplog.text
        # At INFO level, duration may or may not be shown
        # depending on implementation

    def test_log_ssh_command_debug(self, caplog):
        """Test logging SSH command at DEBUG level shows duration."""
        with caplog.at_level(logging.DEBUG):
            log_ssh_command("ls -la", "server1.com", exit_code=0, duration=0.05)

        assert Event.REMOTE_EXEC in caplog.text
        assert "ls -la" in caplog.text
        assert "duration" in caplog.text.lower()

    def test_log_ssh_command_error(self, caplog):
        """Test logging SSH command with non-zero exit code."""
        with caplog.at_level(logging.INFO):
            log_ssh_command("systemctl status missing", "server1.com", exit_code=3, duration=0.1)

        assert Event.REMOTE_EXEC in caplog.text
        assert "exit_code=3" in caplog.text
