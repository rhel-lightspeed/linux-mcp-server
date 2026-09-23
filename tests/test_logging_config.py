"""Tests for logging configuration."""

import json
import logging

from collections.abc import AsyncIterator
from pathlib import Path
from socket import socket
from typing import Any
from typing import Literal

import pytest

from pytest_mock import MockerFixture

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import LogFormat
from linux_mcp_server.config import LogOutput
from linux_mcp_server.config import Transport
from linux_mcp_server.logging_config import JSONFormatter
from linux_mcp_server.logging_config import setup_logging
from linux_mcp_server.logging_config import StructuredFormatter


pytestmark = pytest.mark.usefixtures("isolated_logging")


class TestSetupLogging:
    """Test logging setup."""

    @pytest.mark.parametrize("format", list(LogFormat))
    def test_setup_creates_log_files(self, tmp_path, mocker, monkeypatch, capsys, format):
        """Test that setup creates both text and JSON log files."""
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_dir", tmp_path)
        monkeypatch.setattr(CONFIG, "log_format", format)

        setup_logging()

        # Log something
        logger = logging.getLogger("test")
        logger.info("Test message")

        # Check both log files exist
        text_log = tmp_path / "server.log"
        json_log = tmp_path / "server.json"

        assert text_log.exists()
        assert json_log.exists()
        assert "Test message" in text_log.read_text()
        records = [json.loads(line) for line in json_log.read_text().splitlines()]
        assert records[-1]["message"] == "Test message"
        assert "attributes" not in records[-1]
        captured = capsys.readouterr()
        assert captured.out == ""
        assert " | INFO | test | Test message" in captured.err

    def test_log_level_from_environment(self, tmp_path, mocker):
        """Test that log level can be set from configuration."""
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_dir", tmp_path)
        mocker.patch("linux_mcp_server.logging_config.CONFIG.log_level", "DEBUG")

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

        assert data["attributes"] == {"host": "server1.example.com", "username": "admin", "exit_code": 0}

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


@pytest.mark.parametrize("output", [LogOutput.stdout, LogOutput.stderr])
@pytest.mark.parametrize("format", list(LogFormat))
def test_stream_output(
    output: LogOutput,
    format: LogFormat,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    log_dir = tmp_path / "must-not-exist"
    monkeypatch.setattr(CONFIG, "log_dir", log_dir)
    monkeypatch.setattr(CONFIG, "log_output", output)
    monkeypatch.setattr(CONFIG, "log_format", format)
    setup_logging()
    capsys.readouterr()

    for name in ("linux-mcp-server", "linux_mcp_server.audit", "asyncssh", "fastmcp.server", "uvicorn.error"):
        logging.getLogger(name).warning("Test message", extra={"host": "server1"})

    captured = capsys.readouterr()
    selected, other = (captured.out, captured.err) if output == LogOutput.stdout else (captured.err, captured.out)
    assert other == ""
    assert not log_dir.exists()
    lines = selected.splitlines()
    assert len(lines) == 5
    if format == LogFormat.json:
        records = [json.loads(line) for line in lines]
        assert all(record["attributes"] == {"host": "server1"} for record in records)
        assert all(record["message"] == "Test message" for record in records)
    else:
        assert all("Test message | host=server1" in line for line in lines)


def test_setup_replaces_and_closes_handlers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
) -> None:
    monkeypatch.setattr(CONFIG, "log_dir", tmp_path)
    setup_logging()
    old_handlers = logging.getLogger().handlers[:]
    # Simulate handlers installed by the frameworks before application setup.
    framework_handler = logging.StreamHandler()
    logging.getLogger("fastmcp").addHandler(framework_handler)
    close = mocker.spy(framework_handler, "close")
    monkeypatch.setattr(CONFIG, "log_output", LogOutput.stderr)
    setup_logging()
    close.assert_called_once_with()
    assert all(handler not in logging.getLogger().handlers for handler in old_handlers)
    assert all(handler.stream is None for handler in old_handlers if isinstance(handler, logging.FileHandler))
    capsys.readouterr()
    logging.getLogger("fastmcp.server").warning("Only once")
    assert capsys.readouterr().err.count("Only once") == 1


def test_json_is_independent_of_other_formatters() -> None:
    record = logging.makeLogRecord(
        {"msg": "First line\nSecond line", "created": 0, "path": Path("/tmp/example"), "timestamp": "custom"}
    )
    formatter = JSONFormatter()
    before = formatter.format(record)
    StructuredFormatter("%(asctime)s %(message)s").format(record)
    after = formatter.format(record)
    assert before == after
    assert len(after.splitlines()) == 1
    data = json.loads(after)
    assert data["timestamp"] == "1970-01-01T00:00:00Z"
    assert data["message"] == "First line\nSecond line"
    assert data["attributes"] == {"path": "/tmp/example", "timestamp": "custom"}


@pytest.mark.parametrize("transport", [Transport.http, Transport.streamable_http])
async def test_http_startup_preserves_logging(
    transport: Literal[Transport.http, Transport.streamable_http],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
) -> None:
    from fastmcp import FastMCP
    from uvicorn import Server

    monkeypatch.setattr(CONFIG, "transport", transport)
    monkeypatch.setattr(CONFIG, "log_output", LogOutput.stdout)
    monkeypatch.setattr(CONFIG, "log_format", LogFormat.json)
    setup_logging()
    capsys.readouterr()

    async def serve(server: Server, sockets: list[socket] | None = None) -> None:
        # Config has run Uvicorn's real logging initialization by this point.
        assert server.config.log_config is None
        logging.getLogger("uvicorn.access").info('127.0.0.1 - "GET /mcp HTTP/1.1" 200')
        logging.getLogger("fastmcp.server").warning("Framework warning")

    mocker.patch.object(Server, "serve", autospec=True, side_effect=serve)
    await FastMCP("logging-test").run_http_async(
        transport=transport.value, show_banner=False, **CONFIG.transport_kwargs
    )
    captured = capsys.readouterr()
    assert captured.err == ""
    records = [json.loads(line) for line in captured.out.splitlines()]
    assert sum(record["message"] == "Framework warning" for record in records) == 1
    assert any(record["logger"] == "uvicorn.access" for record in records)
    assert any("Starting MCP server" in record["message"] for record in records)


async def test_stdio_startup_preserves_logging(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
) -> None:
    from contextlib import asynccontextmanager

    from fastmcp import FastMCP

    monkeypatch.setattr(CONFIG, "transport", Transport.stdio)
    monkeypatch.setattr(CONFIG, "log_output", LogOutput.stderr)
    monkeypatch.setattr(CONFIG, "log_format", LogFormat.json)
    setup_logging()
    capsys.readouterr()
    server = FastMCP("logging-test")

    @asynccontextmanager
    async def streams() -> AsyncIterator[tuple[None, None]]:
        yield (None, None)

    async def run(*args: Any, **kwargs: Any) -> None:
        logging.getLogger("fastmcp.server").warning("Framework warning")

    mocker.patch("fastmcp.server.mixins.transport.stdio_server", autospec=True, side_effect=streams)
    mocker.patch.object(server._mcp_server, "run", autospec=True, side_effect=run)
    await server.run_stdio_async(show_banner=False, **CONFIG.transport_kwargs)
    captured = capsys.readouterr()
    assert captured.out == ""
    records = [json.loads(line) for line in captured.err.splitlines()]
    assert sum(record["message"] == "Framework warning" for record in records) == 1
    assert any("Starting MCP server" in record["message"] for record in records)
