"""Tests for logging configuration."""

import importlib
import json
import logging

from linux_mcp_server.logging_config import JSONFormatter
from linux_mcp_server.logging_config import setup_logging
from linux_mcp_server.logging_config import StructuredFormatter


class TestSetupLogging:
    """Test logging setup."""

    def test_setup_creates_log_files(self, tmp_path, mocker):
        """Test that setup creates both text and JSON log files."""
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_dir", tmp_path)

        setup_logging()

        # Log something
        logger = logging.getLogger("test")
        logger.info("Test message")

        # Check both log files exist
        text_log = tmp_path / "server.log"
        json_log = tmp_path / "server.json"

        assert text_log.exists()
        assert json_log.exists()

    def test_log_level_from_environment(self, tmp_path, monkeypatch):
        """Test that log level can be set from environment variable."""
        # Patch log_dir to avoid creating files in home directory during tests
        monkeypatch.setenv("LINUX_MCP_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("LINUX_MCP_LOG_RETENTION_DAYS", "10")
        monkeypatch.setenv("LINUX_MCP_LOG_DIR", str(tmp_path))

        # Reload config module to pick up the environment variables
        from linux_mcp_server import config

        importlib.reload(config)

        # Reload logging_config to pick up the new CONFIG
        from linux_mcp_server import logging_config

        importlib.reload(logging_config)

        # Import setup_logging again to get the reloaded version
        from linux_mcp_server.logging_config import setup_logging

        setup_logging()

        # Root logger should be at DEBUG level
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

    def test_default_log_level_is_info(self, mocker, tmp_path):
        """Test that default log level is INFO."""
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_dir", tmp_path)
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_level", "INFO")

        setup_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO


class TestStructuredFormatter:
    """Test structured log formatter."""

    def test_format_basic_message(self):
        """Test formatting a basic log message."""
        formatter = StructuredFormatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        record = logging.LogRecord(
            name="test_module",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        # Check format: TIMESTAMP | LEVEL | MODULE | MESSAGE
        parts = formatted.split(" | ")
        assert len(parts) == 4
        assert parts[1] == "INFO"
        assert parts[2] == "test_module"
        assert parts[3] == "Test message"

    def test_format_with_extra_fields(self):
        """Test formatting with extra context fields."""
        formatter = StructuredFormatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        record = logging.LogRecord(
            name="test_module",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.host = "server1.example.com"
        record.username = "admin"

        formatted = formatter.format(record)

        assert "host=server1.example.com" in formatted
        assert "username=admin" in formatted


class TestJSONFormatter:
    """Test JSON log formatter."""

    def test_format_basic_message(self):
        """Test formatting a basic log message as JSON."""
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
        record = logging.LogRecord(
            name="test_module",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["level"] == "INFO"
        assert data["logger"] == "test_module"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_format_with_extra_fields(self):
        """Test formatting with extra context fields as JSON."""
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
        record = logging.LogRecord(
            name="test_module",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.host = "server1.example.com"
        record.username = "admin"
        record.exit_code = 0

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert data["host"] == "server1.example.com"
        assert data["username"] == "admin"
        assert data["exit_code"] == 0

    def test_format_with_exception(self):
        """Test formatting with exception information."""
        import sys

        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test_module",
                level=logging.ERROR,
                pathname="",
                lineno=0,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )

            formatted = formatter.format(record)
            data = json.loads(formatted)

            assert "exception" in data
            assert "ValueError: Test error" in data["exception"]
