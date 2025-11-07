"""Audit logging utilities for Linux MCP Server.

This module provides helper functions for consistent audit logging across
the entire MCP server. All functions add structured context to log records
that can be output in both human-readable and JSON formats.
"""

import functools
import inspect
import logging
import time
import typing as t

from contextlib import contextmanager
from datetime import timedelta

from linux_mcp_server.utils import StrEnum


Function: t.TypeAlias = t.Callable[..., t.Any]

# Sensitive field names that should be redacted in logs
SENSITIVE_FIELDS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "api_key",
    "apikey",
    "token",
    "auth",
    "authorization",
    "private_key",
    "privatekey",
}


class Event(StrEnum):
    LOCAL_EXEC_ERROR = "LOCAL_EXEC_ERROR"
    REMOTE_EXEC = "REMOTE_EXEC"
    REMOTE_EXEC_ERROR = "REMOTE_EXEC_ERROR"
    SSH_AUTH_FAILED = "SSH_AUTH_FAILED"
    SSH_CONNECT = "SSH_CONNECT"
    SSH_CONNECTING = "SSH_CONNECTING"
    TOOL_CALL = "TOOL_CALL"
    TOOL_COMPLETE = "TOOL_CALL"


class ExecutionMode(StrEnum):
    remote = "remote"
    local = "local"


def sanitize_parameters(params: dict[str, t.Any]) -> dict[str, t.Any]:
    """
    Sanitize parameters by redacting sensitive fields.

    Args:
        params: Dictionary of parameters to sanitize

    Returns:
        Dictionary with sensitive fields redacted
    """
    if not params:
        return params

    sanitized = {}
    for key, value in params.items():
        # Check if key is sensitive
        key_lower = key.lower().replace("_", "").replace("-", "")
        is_sensitive = any(sensitive in key_lower for sensitive in [s.replace("_", "") for s in SENSITIVE_FIELDS])

        if is_sensitive:
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = sanitize_parameters(value)
        else:
            sanitized[key] = value

    return sanitized


@contextmanager
def AuditContext(**extra_fields):
    """
    Context manager for adding extra fields to all log records.

    Usage:
        with AuditContext(tool="list_services", host="server1.com") as logger:
            logger.info("Starting operation")

    Args:
        **extra_fields: Additional fields to add to log records

    Yields:
        Logger with extra fields
    """
    logger = logging.getLogger()

    # Create adapter with extra fields
    class ContextAdapter(logging.LoggerAdapter):
        def process(self, msg, kwargs):
            # Add extra fields to the record
            if "extra" not in kwargs:
                kwargs["extra"] = {}

            if isinstance(self.extra, t.Iterable):
                kwargs["extra"].update(self.extra)

            return msg, kwargs

    adapter = ContextAdapter(logger, extra_fields)
    yield adapter


def _log_event_start(
    logger: logging.Logger,
    tool_name: str,
    params: dict[t.Any, t.Any],
) -> int:
    """
    Emit a log event and return a performance counter timestamp.

    The timestamp is in nanoseconds. It is meant to be used to calculate
    total execution time.
    """
    execution_mode = ExecutionMode.remote if params.get("host") else ExecutionMode.local
    safe_params = sanitize_parameters(params)

    extra = {
        "tool": tool_name,
        "execution_mode": execution_mode,
    }
    if "host" in params:
        extra["host"] = params["host"]

    if "username" in params:
        extra["username"] = params["username"]

    message = f"{Event.TOOL_CALL}: {tool_name}"

    params_str = ", ".join(f"{k}={v}" for k, v in safe_params.items() if k not in ["host", "username"])
    if params_str:
        message += f" | {params_str}"

    logger.info(message, extra=extra)

    return time.perf_counter_ns()


def _log_event_complete(
    logger: logging.Logger,
    tool_name: str,
    start_time: int,
    error: Exception | None = None,
) -> None:
    """
    Log the completion of a tool call and calculate the total execution time.
    """
    stop_time = time.perf_counter_ns()
    duration = timedelta(microseconds=(stop_time - start_time) / 1_000)
    status = "error" if error else "success"
    extra = {
        "tool": tool_name,
        "status": status,
        "duration": f"{duration}s",
    }

    message = f"{Event.TOOL_COMPLETE}: {tool_name}"

    if error:
        extra["error"] = str(error)
        message += f" | error: {error}"
        logger.error(message, extra=extra)
    else:
        logger.info(message, extra=extra)


def log_tool_call(func: t.Callable) -> Function:
    """Decorator to log tool calls

    Works with sync or async functions.
    """
    logger = logging.getLogger("linux-mcp-server")
    tool_name = func.__name__

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = _log_event_start(logger, tool_name, kwargs)
        error = None
        result = None

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            # FIXME: This could potentially swallow exceptions. Maybe narrow the exception type.
            error = exc

        _log_event_complete(logger, tool_name, start_time, error)

        return result

    @functools.wraps(func)
    async def awrapper(*args, **kwargs):
        start_time = _log_event_start(logger, tool_name, kwargs)
        error = None
        result = None

        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            error = exc

        _log_event_complete(logger, tool_name, start_time, error)

        return result

    if inspect.iscoroutinefunction(func):
        return awrapper

    return wrapper


def log_ssh_connect(
    host: str,
    username: str,
    status: str,
    reused: bool = False,
    key_path: str | None = None,
    error: str | None = None,
):
    """
    Log SSH connection event.

    Verbosity is tiered based on log level:
    - INFO: Basic connection success/failure
    - DEBUG: Detailed information including key path, reuse status

    Args:
        host: Remote host
        username: SSH username
        status: Connection status ("success" or "failed")
        reused: Whether connection was reused (shown at DEBUG level)
        key_path: Path to SSH key used (shown at DEBUG level)
        error: Optional error message
    """
    logger = logging.getLogger(__name__)

    user_host = f"{username}@{host}"

    if status == "success":
        extra = {
            "host": host,
            "username": username,
            "status": status,
        }

        # At INFO level, just log basic success
        message = f"{Event.SSH_CONNECT}: {user_host}"

        # At DEBUG level, add more details
        if logger.isEnabledFor(logging.DEBUG):
            if reused is not None:
                extra["reused"] = str(reused)
            if key_path:
                extra["key"] = key_path

        logger.info(message, extra=extra)

    else:
        # Connection failed
        extra = {
            "host": host,
            "username": username,
            "status": "failed",
        }

        if error:
            extra["reason"] = error

        message = f"{Event.SSH_AUTH_FAILED}: {user_host}"
        if error:
            message += f" | reason: {error}"

        logger.warning(message, extra=extra)


def log_ssh_command(
    command: str,
    host: str,
    exit_code: int,
    duration: float | None = None,
):
    """
    Log SSH command execution.

    Verbosity is tiered based on log level:
    - INFO: Command and exit code
    - DEBUG: Also includes execution duration

    Args:
        command: Command that was executed
        host: Remote host
        exit_code: Command exit code
        duration: Optional execution duration in seconds (shown at DEBUG level)
    """
    logger = logging.getLogger(__name__)

    extra = {
        "command": command,
        "host": host,
        "exit_code": exit_code,
    }

    message = f"{Event.REMOTE_EXEC}: {command} | host={host} | exit_code={exit_code}"

    # At DEBUG level, include duration
    if duration is not None and logger.isEnabledFor(logging.DEBUG):
        extra["duration"] = f"{duration:.3f}s"
        message += f" | duration={duration:.3f}s"

    logger.info(message, extra=extra)
