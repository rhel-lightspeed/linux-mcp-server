"""Tests for audit logging utilities."""

import logging
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from linux_mcp_server.audit import (
    log_tool_call,
    log_tool_complete,
    log_ssh_connect,
    log_ssh_command,
    log_operation,
    sanitize_parameters,
    AuditContext,
)


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

    def test_log_tool_call_local(self, caplog):
        """Test logging a local tool call."""
        with caplog.at_level(logging.INFO):
            log_tool_call("list_services", {})

        assert "TOOL_CALL" in caplog.text
        assert "list_services" in caplog.text
        # Check the log record attributes
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "execution_mode")
        assert record.execution_mode == "local"

    def test_log_tool_call_remote(self, caplog):
        """Test logging a remote tool call."""
        params = {"host": "server1.com", "username": "admin"}
        with caplog.at_level(logging.INFO):
            log_tool_call("list_services", params)

        assert "TOOL_CALL" in caplog.text
        assert "list_services" in caplog.text
        # Check the log record attributes
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "execution_mode")
        assert record.execution_mode == "remote"
        assert hasattr(record, "host")
        assert record.host == "server1.com"

    def test_log_tool_call_sanitizes_parameters(self, caplog):
        """Test that tool call logging sanitizes sensitive parameters."""
        params = {"password": "secret123", "username": "admin"}
        with caplog.at_level(logging.INFO):
            log_tool_call("some_tool", params)

        assert "TOOL_CALL" in caplog.text
        assert "secret123" not in caplog.text
        assert "REDACTED" in caplog.text


class TestLogToolComplete:
    """Test tool completion logging."""

    def test_log_tool_complete_success(self, caplog):
        """Test logging successful tool completion."""
        with caplog.at_level(logging.INFO):
            log_tool_complete("list_services", status="success", duration=0.5)

        assert "TOOL_COMPLETE" in caplog.text
        assert "list_services" in caplog.text
        # Check the log record attributes
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "status")
        assert record.status == "success"
        assert hasattr(record, "duration")

    def test_log_tool_complete_failure(self, caplog):
        """Test logging failed tool completion."""
        with caplog.at_level(logging.ERROR):
            log_tool_complete("list_services", status="error", duration=0.1, error="Connection failed")

        assert "TOOL_COMPLETE" in caplog.text
        assert "list_services" in caplog.text
        assert "Connection failed" in caplog.text
        # Check the log record attributes
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "status")
        assert record.status == "error"


class TestLogSSHConnect:
    """Test SSH connection logging."""

    def test_log_ssh_connect_success_info(self, caplog):
        """Test logging successful SSH connection at INFO level."""
        with caplog.at_level(logging.INFO):
            log_ssh_connect("server1.com", "admin", status="success", reused=False)

        assert "SSH_CONNECT" in caplog.text
        assert "admin@server1.com" in caplog.text
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
            log_ssh_connect("server1.com", "admin", status="success", reused=True, key_path="/home/user/.ssh/id_rsa")

        assert "SSH_CONNECT" in caplog.text
        assert "admin@server1.com" in caplog.text
        # Check the log record attributes
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "status")
        assert record.status == "success"
        # At DEBUG level, SHOULD show reused status and key path
        assert hasattr(record, "reused")
        assert record.reused == True
        assert hasattr(record, "key")
        assert ".ssh/id_rsa" in record.key

    def test_log_ssh_connect_failure(self, caplog):
        """Test logging failed SSH connection."""
        with caplog.at_level(logging.WARNING):
            log_ssh_connect("server1.com", "admin", status="failed", error="Permission denied")

        assert "SSH_CONNECT" in caplog.text or "SSH_AUTH_FAILED" in caplog.text
        assert "admin@server1.com" in caplog.text
        assert "Permission denied" in caplog.text


class TestLogSSHCommand:
    """Test SSH command execution logging."""

    def test_log_ssh_command_info(self, caplog):
        """Test logging SSH command at INFO level."""
        with caplog.at_level(logging.INFO):
            log_ssh_command("systemctl status nginx", "server1.com", exit_code=0, duration=0.15)

        assert "REMOTE_EXEC" in caplog.text
        assert "systemctl status nginx" in caplog.text
        assert "server1.com" in caplog.text
        assert "exit_code=0" in caplog.text
        # At INFO level, duration may or may not be shown
        # depending on implementation

    def test_log_ssh_command_debug(self, caplog):
        """Test logging SSH command at DEBUG level shows duration."""
        with caplog.at_level(logging.DEBUG):
            log_ssh_command("ls -la", "server1.com", exit_code=0, duration=0.05)

        assert "REMOTE_EXEC" in caplog.text
        assert "ls -la" in caplog.text
        assert "duration" in caplog.text.lower()

    def test_log_ssh_command_error(self, caplog):
        """Test logging SSH command with non-zero exit code."""
        with caplog.at_level(logging.INFO):
            log_ssh_command("systemctl status missing", "server1.com", exit_code=3, duration=0.1)

        assert "REMOTE_EXEC" in caplog.text
        assert "exit_code=3" in caplog.text


class TestLogOperation:
    """Test general operation logging."""

    def test_log_operation_info(self, caplog):
        """Test logging an operation at INFO level."""
        with caplog.at_level(logging.INFO):
            log_operation("list_processes", "Listing processes", process_count=42)

        assert "list_processes" in caplog.text
        assert "Listing processes" in caplog.text
        # Check the log record attributes
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "process_count")
        assert record.process_count == 42

    def test_log_operation_debug(self, caplog):
        """Test logging an operation at DEBUG level."""
        with caplog.at_level(logging.DEBUG):
            log_operation("get_service_status", "Checking service status", service="nginx", level=logging.DEBUG)

        assert "get_service_status" in caplog.text
        assert "Checking service status" in caplog.text
        # Check the log record attributes
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "service")
        assert record.service == "nginx"

    def test_log_operation_with_context(self, caplog):
        """Test logging operation with extra context."""
        with caplog.at_level(logging.INFO):
            log_operation("read_log_file", "Reading log file", file_path="/var/log/messages", lines=100)

        assert "read_log_file" in caplog.text
        assert "Reading log file" in caplog.text
        # Check the log record attributes
        assert len(caplog.records) >= 1
        record = caplog.records[-1]
        assert hasattr(record, "file_path")
        assert record.file_path == "/var/log/messages"
        assert hasattr(record, "lines")
        assert record.lines == 100
