"""Centralized logging configuration for Linux MCP Server.

Simplified logging setup with standard Python logging infrastructure.
Supports structured logging with extra fields for audit and diagnostic purposes.
"""

import json
import logging
import logging.handlers
import sys
import time

from typing import Any

from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import LogFormat
from linux_mcp_server.config import LogLevel
from linux_mcp_server.config import LogOutput


def get_log_level() -> int:
    """Get the root log level; default mode limits dependencies to WARNING."""
    level_name = CONFIG.log_level
    if level_name == LogLevel.DEFAULT:
        return logging.WARNING
    return getattr(logging, level_name)


def get_retention_days() -> int:
    """Get the log retention days from environment variable (defaults to 10)."""
    try:
        return int(CONFIG.log_retention_days)
    except ValueError:
        return 10


class StructuredFormatter(logging.Formatter):
    """
    Structured log formatter supporting extra fields.

    Format: TIMESTAMP | LEVEL | MODULE | MESSAGE | key=value ...
    Extra fields added to LogRecord are appended as key=value pairs.
    """

    STANDARD_FIELDS = {
        "name",
        "msg",
        "args",
        "created",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "exc_info",
        "exc_text",
        "stack_info",
        "asctime",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with extra fields."""
        # Base message
        base_msg = super().format(record)

        # Append extra fields as key=value pairs
        extra_fields = [f"{k}={v}" for k, v in record.__dict__.items() if k not in self.STANDARD_FIELDS]

        return f"{base_msg} | {' | '.join(extra_fields)}" if extra_fields else base_msg


class JSONFormatter(logging.Formatter):
    """JSON log formatter for machine-readable logs."""

    converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        attributes = {
            key: value for key, value in record.__dict__.items() if key not in StructuredFormatter.STANDARD_FIELDS
        }
        if attributes:
            log_data["attributes"] = attributes

        # Extra values from dependencies may not be JSON-native (e.g. Paths).
        return json.dumps(log_data, default=str)


def setup_logging() -> None:
    """Configure file or stream output for application and transport logs."""
    log_level = get_log_level()
    text_formatter = StructuredFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    json_formatter = JSONFormatter()
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    logging.getLogger("linux_mcp_server").setLevel(logging.INFO if CONFIG.log_level == LogLevel.DEFAULT else log_level)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    if CONFIG.log_output == LogOutput.files:
        log_dir = CONFIG.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        for filename, formatter in (("server.log", text_formatter), ("server.json", json_formatter)):
            file_handler = logging.handlers.TimedRotatingFileHandler(
                filename=log_dir / filename,
                when="midnight",
                interval=1,
                backupCount=get_retention_days(),
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.suffix = "%Y-%m-%d"
            root_logger.addHandler(file_handler)

    # File mode also emits text logs on stderr. Stream modes emit each record
    # once on the selected stream, with no log directory or rotating files.
    stream = sys.stdout if CONFIG.log_output == LogOutput.stdout else sys.stderr
    console_handler = logging.StreamHandler(stream)
    console_handler.setFormatter(
        json_formatter
        if CONFIG.log_output != LogOutput.files and CONFIG.log_format == LogFormat.json
        else text_formatter
    )
    root_logger.addHandler(console_handler)

    # FastMCP installs handlers at import time; Uvicorn may already have been
    # configured by an embedding application. Route both through our handlers.
    # transport_kwargs prevents either from replacing them during server startup.
    for name in ("fastmcp", "uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi"):
        logger = logging.getLogger(name)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
        logger.setLevel(logging.NOTSET)
        logger.propagate = True

    logging.getLogger(__name__).info("Logging initialized", extra={"output": CONFIG.log_output.value})
