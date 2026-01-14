"""Audit logging utilities for Linux MCP Server.

This module provides helper functions for consistent audit logging across
the entire MCP server. All functions add structured context to log records
that can be output in both human-readable and JSON formats.
"""

import functools
import inspect
import time
import typing as t

from contextlib import contextmanager
from datetime import timedelta
from typing import TYPE_CHECKING

from loguru import logger

from linux_mcp_server.utils import StrEnum


if TYPE_CHECKING:
    from loguru import Logger


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
    TOOL_COMPLETE = "TOOL_COMPLETE"


class ExecutionMode(StrEnum):
    REMOTE = "REMOTE"
    LOCAL = "LOCAL"


class Status(StrEnum):
    success = "success"
    error = "error"
    failed = "failed"


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
def AuditContext(**extra_fields: t.Any) -> t.Generator["Logger", None, None]:
    """
    Context manager for adding extra fields to all log records.

    Usage:
        with AuditContext(tool="list_services", host="testhost") as log:
            log.info("Starting operation")

    Args:
        **extra_fields: Additional fields to add to log records.

    Yields:
        Logger: The loguru logger with extra fields bound via contextualize().
    """
    with logger.contextualize(**extra_fields):
        yield logger


def _log_event_start(
    tool_name: str,
    params: dict[t.Any, t.Any],
) -> int:
    """
    Emit a log event and return a performance counter timestamp.

    The timestamp is in nanoseconds. It is meant to be used to calculate
    total execution time.
    """
    execution_mode = ExecutionMode.REMOTE if params.get("host") else ExecutionMode.LOCAL
    safe_params = sanitize_parameters(params)

    bound_logger = logger.bind(tool=tool_name, execution_mode=execution_mode)

    if "host" in params:
        bound_logger = bound_logger.bind(host=params["host"])

    if "username" in params:
        bound_logger = bound_logger.bind(username=params["username"])

    message = f"{Event.TOOL_CALL}: {tool_name}"

    params_str = ", ".join(f"{k}={v}" for k, v in safe_params.items() if k not in ["host", "username"])
    if params_str:
        message += f" | {params_str}"

    bound_logger.info(message)

    return time.perf_counter_ns()


def _log_event_complete(
    tool_name: str,
    start_time: int,
    error: Exception | None = None,
) -> None:
    """
    Log the completion of a tool call and calculate the total execution time.
    """
    stop_time = time.perf_counter_ns()
    duration = timedelta(microseconds=(stop_time - start_time) / 1_000)
    status = Status.error if error else Status.success

    bound_logger = logger.bind(tool=tool_name, status=status, duration=f"{duration}s")

    message = f"{Event.TOOL_COMPLETE}: {tool_name}"

    if error:
        bound_logger.bind(error=str(error)).error(f"{message} | error: {error}")
    else:
        bound_logger.info(message)


def log_tool_call(func: t.Callable) -> Function:
    """Decorator to log tool calls

    Works with sync or async functions.
    """
    tool_name = func.__name__

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = _log_event_start(tool_name, kwargs)
        error = None
        result = None

        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            error = exc
            _log_event_complete(tool_name, start_time, error)
            raise

        _log_event_complete(tool_name, start_time, error)

        return result

    @functools.wraps(func)
    async def awrapper(*args, **kwargs):
        start_time = _log_event_start(tool_name, kwargs)
        error = None
        result = None

        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            error = exc
            _log_event_complete(tool_name, start_time, error)
            raise

        _log_event_complete(tool_name, start_time, error)

        return result

    if inspect.iscoroutinefunction(func):
        return awrapper

    return wrapper


def log_ssh_connect(
    host: str,
    status: Status,
    username: str = "",
    reused: bool = False,
    key_path: str | None = None,
    error: str | None = None,
):
    """
    Log SSH connection event.

    Args:
        host: Remote host
        status: Connection status (Status.success or Status.failed)
        username: SSH username
        reused: Whether connection was reused (included in structured log extra at all levels)
        key_path: Path to SSH key used (included in structured log extra at all levels)
        error: Optional error message
    """
    if status == Status.success:
        bound_logger = logger.bind(host=host, username=username, status=status)

        message = f"{Event.SSH_CONNECT}: {username}@{host}"

        # Additional details are bound for structured logging
        if reused is not None:
            bound_logger = bound_logger.bind(reused=str(reused))
        if key_path:
            bound_logger = bound_logger.bind(key=key_path)

        bound_logger.info(message)

    else:
        # Connection failed
        bound_logger = logger.bind(host=host, username=username, status="failed")

        if error:
            bound_logger = bound_logger.bind(reason=error)

        message = f"{Event.SSH_AUTH_FAILED}: {username}@{host}"
        if error:
            message += f" | reason: {error}"

        bound_logger.warning(message)


def log_ssh_command(
    command: str,
    host: str,
    exit_code: int,
    duration: float | None = None,
):
    """
    Log SSH command execution.

    Args:
        command: Command that was executed
        host: Remote host
        exit_code: Command exit code
        duration: Optional execution duration in seconds (included in message and structured log extra at all levels)
    """
    bound_logger = logger.bind(command=command, host=host, exit_code=exit_code)

    message = f"{Event.REMOTE_EXEC}: {command} | host={host} | exit_code={exit_code}"

    # Duration is included in both message and structured log extra when provided
    if duration is not None:
        bound_logger = bound_logger.bind(duration=f"{duration:.3f}s")
        message += f" | duration={duration:.3f}s"

    bound_logger.info(message)
