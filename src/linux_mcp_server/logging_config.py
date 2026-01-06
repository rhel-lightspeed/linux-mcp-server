"""Centralized logging configuration for Linux MCP Server.

Simplified logging setup using loguru for structured logging with
automatic JSON serialization and log rotation.
"""

import sys
import typing as t

from loguru import logger

from linux_mcp_server.config import CONFIG


def _format_extra_fields(extra: dict[str, t.Any]) -> str:
    """Format extra fields as pipe-separated key=value pairs for human-readable logs."""
    if not extra:
        return ""
    return " | ".join(f"{k}={v}" for k, v in extra.items())


def get_retention_days() -> int:
    """Get the log retention days from environment variable (defaults to 10)."""
    try:
        return int(CONFIG.log_retention_days)
    except ValueError:
        return 10


def setup_logging() -> None:
    """Configure loguru with text file, JSON file, and console sinks."""
    log_dir = CONFIG.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    retention_days = get_retention_days()

    # Remove default handler
    logger.remove()

    # Console sink (human-readable)
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
        level=CONFIG.log_level,
    )

    def format_with_extra(record: t.Any) -> str:
        """Custom format function that appends extra fields as key=value pairs."""
        base = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"
        extra_str = _format_extra_fields(record["extra"])
        if extra_str:
            return base + " | " + extra_str + "\n"
        return base + "\n"

    # Text file sink (human-readable with rotation)
    logger.add(
        log_dir / "server.log",
        format=format_with_extra,
        level=CONFIG.log_level,
        rotation="1 day",
        retention=f"{retention_days} days",
        encoding="utf-8",
    )

    # JSON file sink (machine-readable)
    logger.add(
        log_dir / "server.json",
        serialize=True,
        level=CONFIG.log_level,
        rotation="1 day",
        retention=f"{retention_days} days",
        encoding="utf-8",
    )

    logger.info(f"Logging initialized: {log_dir}")
