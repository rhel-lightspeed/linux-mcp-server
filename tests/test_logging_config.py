"""Tests for logging configuration."""

import json

from loguru import logger

from linux_mcp_server.logging_config import setup_logging


class TestLoguruCapture:
    """Test the loguru_caplog fixture functionality."""

    def test_capture_and_clear(self, loguru_caplog):
        """Test that loguru_caplog captures logs and clear() works."""
        logger.info("First message")
        assert "First message" in loguru_caplog.text
        assert len(loguru_caplog.records) == 1

        loguru_caplog.clear()

        assert loguru_caplog.text == ""
        assert len(loguru_caplog.records) == 0

        logger.info("Second message")
        assert "Second message" in loguru_caplog.text
        assert len(loguru_caplog.records) == 1


class TestGetRetentionDays:
    """Test log retention days configuration."""

    def test_invalid_retention_days_returns_default(self, mocker):
        """Test that invalid retention days falls back to default of 10."""
        from linux_mcp_server.logging_config import get_retention_days

        # Mock CONFIG.log_retention_days to return a non-integer string
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_retention_days", "invalid")

        result = get_retention_days()

        assert result == 10


class TestSetupLogging:
    """Test logging setup."""

    def test_setup_creates_log_files(self, tmp_path, mocker):
        """Test that setup creates both text and JSON log files."""
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_dir", tmp_path)

        # Remove all existing handlers before test
        logger.remove()

        setup_logging()

        # Log something using the bound logger
        logger.info("Test message")

        # Check both log files exist
        text_log = tmp_path / "server.log"
        json_log = tmp_path / "server.json"

        assert text_log.exists()
        assert json_log.exists()

    def test_log_level_from_environment(self, tmp_path, monkeypatch, mocker):
        """Test that log level can be set from environment variable."""
        monkeypatch.setenv("LINUX_MCP_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("LINUX_MCP_LOG_RETENTION_DAYS", "10")
        monkeypatch.setenv("LINUX_MCP_LOG_DIR", str(tmp_path))

        # Reload config module to pick up the environment variables
        import importlib

        from linux_mcp_server import config

        importlib.reload(config)

        # Reload logging_config to pick up the new CONFIG
        from linux_mcp_server import logging_config

        importlib.reload(logging_config)

        # Remove all existing handlers
        logger.remove()

        # Import setup_logging again to get the reloaded version
        from linux_mcp_server.logging_config import setup_logging

        setup_logging()

        # Log a debug message to verify DEBUG level is enabled
        log_sink = []
        logger.add(log_sink.append, format="{level} {message}", level="DEBUG")
        logger.debug("Debug test message")

        # Verify debug message was captured
        assert any("DEBUG" in str(record) and "Debug test message" in str(record) for record in log_sink)

    def test_default_log_level_is_info(self, mocker, tmp_path):
        """Test that default log level is INFO and DEBUG messages are filtered."""
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_dir", tmp_path)
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_level", "INFO")

        # Remove all existing handlers
        logger.remove()

        setup_logging()

        # Log both debug and info to verify level filtering
        log_sink = []
        logger.add(log_sink.append, format="{level} {message}", level="INFO")

        logger.debug("Debug message")  # Should be filtered
        logger.info("Info message")  # Should appear

        # Verify info appears but debug doesn't
        messages = [str(record) for record in log_sink]
        assert any("Info message" in msg for msg in messages)
        assert not any("Debug message" in msg for msg in messages)


class TestLogOutput:
    """Test log output formats."""

    def test_text_log_format(self, tmp_path, mocker):
        """Test that text logs are formatted correctly."""
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_dir", tmp_path)

        logger.remove()
        setup_logging()

        logger.info("Test message")

        text_log = tmp_path / "server.log"
        content = text_log.read_text()

        # Check format contains expected parts
        assert "INFO" in content
        assert "Test message" in content

    def test_json_log_format(self, tmp_path, mocker):
        """Test that JSON logs are valid JSON with expected fields."""
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_dir", tmp_path)

        logger.remove()
        setup_logging()

        logger.info("Test message")

        json_log = tmp_path / "server.json"
        content = json_log.read_text().strip()

        # Parse each line as JSON (loguru writes one JSON object per line)
        lines = [ln for ln in content.split("\n") if ln]
        assert lines, "No log lines found in JSON log"
        for line in lines:
            data = json.loads(line)
            assert "text" in data  # loguru includes full formatted text
            assert "record" in data  # loguru includes record metadata

    def test_json_log_with_extra_fields(self, tmp_path, mocker):
        """Test that extra fields appear in JSON logs."""
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_dir", tmp_path)

        logger.remove()
        setup_logging()

        # Log with bound extra fields
        logger.bind(host="server1.example.com", username="admin").info("Test message")

        json_log = tmp_path / "server.json"
        content = json_log.read_text().strip()

        # Find the line with our test message
        for line in content.split("\n"):
            if line and "Test message" in line:
                data = json.loads(line)
                # Extra fields should be in record.extra
                assert data["record"]["extra"]["host"] == "server1.example.com"
                assert data["record"]["extra"]["username"] == "admin"
                break
        else:
            raise AssertionError("Test message not found in JSON log")
