"""Tests for logging configuration."""

import json
import logging
import sys

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from socket import socket
from typing import Any
from typing import Literal

import pytest

from fastmcp import FastMCP
from pytest_mock import MockerFixture
from uvicorn import Server

from linux_mcp_server.audit import audit_context
from linux_mcp_server.audit import Event
from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import LogFormat
from linux_mcp_server.config import LogLevel
from linux_mcp_server.config import LogOutput
from linux_mcp_server.config import Transport
from linux_mcp_server.logging_config import JSONFormatter
from linux_mcp_server.logging_config import setup_logging
from linux_mcp_server.logging_config import StructuredFormatter
from linux_mcp_server.logging_config import text_value


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
        logger = logging.getLogger("linux_mcp_server")
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
        assert " | INFO | linux_mcp_server | Test message" in captured.err


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

    for name in ("linux_mcp_server", "linux_mcp_server.audit", "asyncssh", "fastmcp.server", "uvicorn.error"):
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
    """Text formatting must not leak cached fields into JSON attributes.

    File mode sends the same LogRecord to the text handler before the JSON
    handler. Python's logging.Formatter adds message and asctime to that record
    during text formatting; JSON output must exclude those cached fields so its
    contents do not depend on which other handlers ran first.
    """
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


@pytest.mark.parametrize("level", ["DEFAULT", "DEBUG", "INFO", "WARNING"])
@pytest.mark.parametrize("transport", [Transport.http, Transport.streamable_http])
async def test_http_startup_preserves_logging(
    transport: Literal[Transport.http, Transport.streamable_http],
    level: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
) -> None:

    monkeypatch.setattr(CONFIG, "transport", transport)
    monkeypatch.setattr(CONFIG, "log_level", level)
    monkeypatch.setattr(CONFIG, "log_output", LogOutput.stdout)
    monkeypatch.setattr(CONFIG, "log_format", LogFormat.json)
    setup_logging()
    capsys.readouterr()

    async def serve(server: Server, sockets: list[socket] | None = None) -> None:
        # Config has run Uvicorn's real logging initialization by this point.
        assert server.config.log_config is None
        logging.getLogger("uvicorn.access").info('127.0.0.1 - "GET /mcp HTTP/1.1" 200')
        logging.getLogger("fastmcp.server").warning("Framework warning")
        logging.getLogger("linux_mcp_server").info("Application message")

    mocker.patch.object(Server, "serve", autospec=True, side_effect=serve)
    await FastMCP("logging-test").run_http_async(
        transport=transport.value, show_banner=False, **CONFIG.transport_kwargs
    )
    captured = capsys.readouterr()
    assert captured.err == ""
    records = [json.loads(line) for line in captured.out.splitlines()]
    assert sum(record["message"] == "Framework warning" for record in records) == 1
    assert any(record["message"] == "Application message" for record in records) == (level != "WARNING")
    assert any(record["logger"] == "uvicorn.access" for record in records) == (level in {"DEBUG", "INFO"})
    assert any("Starting MCP server" in record["message"] for record in records) == (level in {"DEBUG", "INFO"})


@pytest.mark.parametrize("level", ["DEFAULT", "DEBUG", "INFO", "WARNING"])
async def test_stdio_startup_preserves_logging(
    level: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mocker: MockerFixture,
) -> None:

    monkeypatch.setattr(CONFIG, "transport", Transport.stdio)
    monkeypatch.setattr(CONFIG, "log_level", level)
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
        logging.getLogger("linux_mcp_server").info("Application message")

    mocker.patch("fastmcp.server.mixins.transport.stdio_server", autospec=True, side_effect=streams)
    mocker.patch.object(server._mcp_server, "run", autospec=True, side_effect=run)
    await server.run_stdio_async(show_banner=False, **CONFIG.transport_kwargs)
    captured = capsys.readouterr()
    assert captured.out == ""
    records = [json.loads(line) for line in captured.err.splitlines()]
    assert sum(record["message"] == "Framework warning" for record in records) == 1
    assert any(record["message"] == "Application message" for record in records) == (level != "WARNING")
    assert any("Starting MCP server" in record["message"] for record in records) == (level in {"DEBUG", "INFO"})


@pytest.mark.parametrize("output", list(LogOutput))
def test_log_level_policy_and_reconfiguration(
    output: LogOutput,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Check emitted records across destinations and repeated configuration."""

    monkeypatch.setattr(CONFIG, "log_output", output)
    monkeypatch.setattr(CONFIG, "log_format", LogFormat.json)
    monkeypatch.setattr(CONFIG, "log_dir", tmp_path)
    application_names = ("linux_mcp_server", "linux_mcp_server.connection.ssh", "linux_mcp_server.audit")
    dependency_names = ("mcp.server.lowlevel.server", "fastmcp.server", "asyncssh", "uvicorn.error", "uvicorn.access")
    levels = (logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL)

    # Switching both ways also checks that previous overrides do not persist.
    for configured in ("DEFAULT", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "DEFAULT"):
        monkeypatch.setattr(CONFIG, "log_level", configured)
        setup_logging()
        capsys.readouterr()
        offset = len((tmp_path / "server.json").read_text()) if output == LogOutput.files else 0
        for name in (*application_names, *dependency_names):
            for level in levels:
                logging.getLogger(name).log(level, "policy-%s", configured)
        with audit_context(tool="test_tool"):
            logging.getLogger("linux_mcp_server.audit").info("audit-%s", configured)

        captured = capsys.readouterr()
        if output == LogOutput.files:
            contents = (tmp_path / "server.json").read_text()[offset:]
        else:
            contents = captured.out if output == LogOutput.stdout else captured.err
        records = [json.loads(line) for line in contents.splitlines()]
        actual = [
            (record["logger"], record["level"]) for record in records if record["message"] == f"policy-{configured}"
        ]
        app_level = logging.INFO if configured == "DEFAULT" else getattr(logging, configured)
        dependency_level = logging.WARNING if configured == "DEFAULT" else app_level
        expected = [
            (name, logging.getLevelName(level))
            for names, threshold in ((application_names, app_level), (dependency_names, dependency_level))
            for name in names
            for level in levels
            if level >= threshold
        ]
        assert actual == expected
        assert any(record["message"] == f"audit-{configured}" for record in records) == (app_level <= logging.INFO)


@pytest.mark.parametrize("level", ["DEFAULT", "DEBUG", "INFO", "WARNING"])
def test_dependency_suppression_is_preserved(
    level: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FastMCP suppresses noisy griffe warnings; logging setup must preserve that."""
    logger = logging.getLogger("griffe")
    monkeypatch.setattr(logger, "level", logging.ERROR)
    monkeypatch.setattr(CONFIG, "log_level", level)
    monkeypatch.setattr(CONFIG, "log_output", LogOutput.stderr)
    monkeypatch.setattr(CONFIG, "log_format", LogFormat.json)
    setup_logging()
    capsys.readouterr()
    logger.warning("No type or annotation for parameter 'a'")
    logger.error("Parsing failed")
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [record["message"] for record in records] == ["Parsing failed"]
    assert logger.level == logging.ERROR


@pytest.mark.parametrize(
    "value,expected",
    [
        ("plain", "plain"),
        ("two words", '"two words"'),
        ("a|b=c", '"a|b=c"'),
        ("a\nb\r", '"a\\nb\\r"'),
        ('a"b\\c', '"a\\"b\\\\c"'),
        ("", '""'),
        ({"nested": [1, "a\nb"]}, '{"nested":[1,"a\\nb"]}'),
        (None, "null"),
        (True, "true"),
    ],
)
def test_text_values(value, expected):

    assert text_value(value) == expected


def test_primary_event_formatters_share_record():

    record = logging.makeLogRecord(
        {
            "name": "linux_mcp_server.audit",
            "levelname": "INFO",
            "msg": "Command completed",
            "audit_event": Event.COMMAND_COMPLETE,
            "command": "echo a\necho b",
            "exit_status": 0,
        }
    )

    formatter = StructuredFormatter("%(message)s")
    text = formatter.format(record)
    assert text == 'COMMAND_COMPLETE: Command completed | command="echo a\\necho b" | exit_status=0'

    data = json.loads(JSONFormatter().format(record))
    assert data["event"] == "COMMAND_COMPLETE"
    assert data["message"] == "Command completed"
    assert data["attributes"] == {"command": "echo a\necho b", "exit_status": 0}

    assert formatter.format(record) == text


def test_dependency_fields_cannot_replace_envelope():
    record = logging.makeLogRecord(
        {
            "name": "dependency",
            "msg": "message",
            "event": "custom",
            "audit_event": "custom",
            "timestamp": "fake",
            "attributes": {"nested": True},
        }
    )

    data = json.loads(JSONFormatter().format(record))
    assert "event" not in data
    assert data["timestamp"] != "fake"
    assert data["attributes"] == {
        "event": "custom",
        "audit_event": "custom",
        "timestamp": "fake",
        "attributes": {"nested": True},
    }


def test_text_exception_stays_on_one_line():

    try:
        raise ValueError("multiple\nlines")
    except ValueError:
        record = logging.makeLogRecord({"msg": "Failed\nrequest", "exc_info": sys.exc_info()})

    formatted = StructuredFormatter("%(message)s").format(record)
    assert "\n" not in formatted
    assert "Failed\\nrequest" in formatted
    assert "ValueError: multiple\\nlines" in formatted


@pytest.mark.usefixtures("isolated_logging")
@pytest.mark.parametrize("name", ["linux_mcp_server.test", "dependency"])
def test_diagnostic_context(name, monkeypatch, capsys):

    monkeypatch.setattr(CONFIG, "log_output", LogOutput.stderr)
    monkeypatch.setattr(CONFIG, "log_format", LogFormat.json)
    monkeypatch.setattr(CONFIG, "log_level", LogLevel.DEBUG)
    setup_logging()
    capsys.readouterr()

    with audit_context(call_id="c42", host="inherited"):
        logging.getLogger(name).debug("diagnostic", extra={"host": "explicit"})

    logging.getLogger(name).debug("outside")

    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert records[0]["attributes"] == {"call_id": "c42", "host": "explicit"}
    assert "attributes" not in records[1]
