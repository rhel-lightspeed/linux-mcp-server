"""Centralized logging configuration for Linux MCP Server.

Simplified logging setup with standard Python logging infrastructure.
Supports structured logging with extra fields for audit and diagnostic purposes.
"""

import json
import logging
import logging.handlers
import os
from pathlib import Path


def get_log_directory() -> Path:
    """Get the log directory path, creating it if necessary."""
    env_log_dir = os.getenv("LINUX_MCP_LOG_DIR")
    log_dir = Path(env_log_dir) if env_log_dir else Path.home() / ".local" / "share" / "linux-mcp-server" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_log_level() -> int:
    """Get the log level from environment variable (defaults to INFO)."""
    level_name = os.getenv("LINUX_MCP_LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def get_retention_days() -> int:
    """Get the log retention days from environment variable (defaults to 10)."""
    try:
        return int(os.getenv("LINUX_MCP_LOG_RETENTION_DAYS", "10"))
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

    EXCLUDE_FIELDS = {
        "args",
        "exc_text",
        "exc_info",
        "stack_info",
        "filename",
        "funcName",
        "lineno",
        "module",
        "msecs",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "thread",
        "threadName",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if (
                key not in self.EXCLUDE_FIELDS
                and key not in log_data
                and key not in {"name", "msg", "levelname", "levelno", "created"}
            ):
                log_data[key] = value

        return json.dumps(log_data)


def setup_logging():
    """Set up logging with structured formatters and rotation."""
    log_dir = get_log_directory()
    log_level = get_log_level()
    retention_days = get_retention_days()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()  # Remove existing handlers

    # Human-readable text log
    text_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_dir / "server.log",
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
    )
    text_handler.setLevel(log_level)
    text_handler.setFormatter(
        StructuredFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    text_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(text_handler)

    # JSON log
    json_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_dir / "server.json",
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8",
    )
    json_handler.setLevel(log_level)
    json_handler.setFormatter(JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
    json_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(json_handler)

    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(
        StructuredFormatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    root_logger.addHandler(console_handler)

    logging.getLogger(__name__).info(f"Logging initialized: {log_dir}")
