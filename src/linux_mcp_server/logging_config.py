"""Centralized logging configuration for Linux MCP Server.

This module provides dual-format logging (human-readable text + JSON) with
daily rotation and configurable retention. All logs are written to a single
unified log stream with both formats available for different use cases.
"""

import json
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def get_log_directory() -> Path:
    """
    Get the log directory path, creating it if necessary.
    
    Uses LINUX_MCP_LOG_DIR environment variable if set, otherwise defaults
    to ~/.local/share/linux-mcp-server/logs/
    
    Returns:
        Path object for the log directory
    """
    env_log_dir = os.getenv("LINUX_MCP_LOG_DIR")
    
    if env_log_dir:
        log_dir = Path(env_log_dir)
    else:
        log_dir = Path.home() / ".local" / "share" / "linux-mcp-server" / "logs"
    
    # Create directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)
    
    return log_dir


def get_log_level() -> int:
    """
    Get the log level from environment variable.
    
    Returns:
        Logging level (defaults to INFO)
    """
    level_name = os.getenv("LINUX_MCP_LOG_LEVEL", "INFO").upper()
    return getattr(logging, level_name, logging.INFO)


def get_retention_days() -> int:
    """
    Get the log retention days from environment variable.
    
    Returns:
        Number of days to retain logs (defaults to 10)
    """
    retention = os.getenv("LINUX_MCP_LOG_RETENTION_DAYS", "10")
    try:
        return int(retention)
    except ValueError:
        return 10


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable log formatter.
    
    Format: TIMESTAMP | LEVEL | MODULE | MESSAGE | key=value key=value
    
    Extra fields added to LogRecord are appended as key=value pairs.
    """
    
    # Standard fields to exclude from extra context
    STANDARD_FIELDS = {
        'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
        'levelno', 'lineno', 'module', 'msecs', 'message', 'pathname', 'process',
        'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
        'exc_text', 'stack_info', 'asctime', 'taskName'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record."""
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        
        # Base format: TIMESTAMP | LEVEL | MODULE | MESSAGE
        parts = [
            timestamp,
            record.levelname,
            record.name,
            record.getMessage()
        ]
        
        base_message = " | ".join(parts)
        
        # Add extra context fields as key=value pairs
        extra_fields = []
        for key, value in record.__dict__.items():
            if key not in self.STANDARD_FIELDS:
                # Format the value appropriately
                if isinstance(value, str):
                    extra_fields.append(f"{key}={value}")
                else:
                    extra_fields.append(f"{key}={value}")
        
        if extra_fields:
            return f"{base_message} | {' | '.join(extra_fields)}"
        else:
            return base_message


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter.
    
    Outputs each log record as a single-line JSON object with all fields.
    """
    
    # Standard fields to exclude from JSON output
    EXCLUDE_FIELDS = {
        'args', 'exc_text', 'exc_info', 'stack_info', 'filename', 'funcName',
        'lineno', 'module', 'msecs', 'pathname', 'process', 'processName',
        'relativeCreated', 'thread', 'threadName', 'taskName'
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""
        # Build JSON object
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add all extra fields
        for key, value in record.__dict__.items():
            if key not in self.EXCLUDE_FIELDS and key not in log_data:
                # Skip standard message fields already included
                if key not in {'name', 'msg', 'levelname', 'levelno', 'created'}:
                    log_data[key] = value
        
        return json.dumps(log_data)


def cleanup_old_logs(log_dir: Path, retention_days: Optional[int] = None):
    """
    Clean up old rotated log files.
    
    Args:
        log_dir: Directory containing log files
        retention_days: Number of days to retain (default from env var or 10)
    """
    if retention_days is None:
        retention_days = get_retention_days()
    
    # Find all rotated log files (both .log.* and .json.*)
    patterns = ["server.log.*", "server.json.*"]
    
    for pattern in patterns:
        log_files = sorted(log_dir.glob(pattern))
        
        # Keep only the most recent retention_days files
        if len(log_files) > retention_days:
            files_to_delete = log_files[:-retention_days]
            for old_file in files_to_delete:
                try:
                    old_file.unlink()
                except Exception:
                    # Ignore errors during cleanup
                    pass


def setup_logging():
    """
    Set up dual-format logging with daily rotation.
    
    Creates both human-readable text logs and JSON structured logs.
    Logs are rotated daily at midnight with configurable retention.
    """
    log_dir = get_log_directory()
    log_level = get_log_level()
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create human-readable text log handler
    text_log_path = log_dir / "server.log"
    text_handler = logging.handlers.TimedRotatingFileHandler(
        filename=text_log_path,
        when='midnight',
        interval=1,
        backupCount=get_retention_days(),
        encoding='utf-8',
    )
    text_handler.setLevel(log_level)
    text_handler.setFormatter(HumanReadableFormatter())
    text_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(text_handler)
    
    # Create JSON log handler
    json_log_path = log_dir / "server.json"
    json_handler = logging.handlers.TimedRotatingFileHandler(
        filename=json_log_path,
        when='midnight',
        interval=1,
        backupCount=get_retention_days(),
        encoding='utf-8',
    )
    json_handler.setLevel(log_level)
    json_handler.setFormatter(JSONFormatter())
    json_handler.suffix = "%Y-%m-%d"
    root_logger.addHandler(json_handler)
    
    # Also add console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(HumanReadableFormatter())
    root_logger.addHandler(console_handler)
    
    # Clean up old logs
    cleanup_old_logs(log_dir)
    
    # Log initialization message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized: {log_dir}")

