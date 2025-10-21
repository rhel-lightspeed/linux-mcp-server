"""Audit logging utilities for Linux MCP Server.

This module provides helper functions for consistent audit logging across
the entire MCP server. All functions add structured context to log records
that can be output in both human-readable and JSON formats.
"""

import logging
import typing as t

from contextlib import contextmanager


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
            kwargs["extra"].update(self.extra)
            return msg, kwargs

    adapter = ContextAdapter(logger, extra_fields)
    yield adapter


def log_tool_call(tool_name: str, parameters: dict[str, t.Any]):
    """
    Log a tool invocation.

    Args:
        tool_name: Name of the tool being called
        parameters: Tool parameters (will be sanitized)
    """
    logger = logging.getLogger(__name__)

    # Determine if local or remote execution
    execution_mode = "remote" if parameters.get("host") else "local"

    # Sanitize parameters
    safe_params = sanitize_parameters(parameters)

    # Build log record with extra fields
    extra = {
        "event": "TOOL_CALL",
        "tool": tool_name,
        "execution_mode": execution_mode,
    }

    # Add host and username if present
    if "host" in parameters:
        extra["host"] = parameters["host"]
    if "username" in parameters:
        extra["username"] = parameters["username"]

    # Add sanitized parameters as string
    params_str = ", ".join(f"{k}={v}" for k, v in safe_params.items() if k not in ["host", "username"])

    message = f"TOOL_CALL: {tool_name}"
    if params_str:
        message += f" | {params_str}"

    logger.info(message, extra=extra)


def log_tool_complete(
    tool_name: str,
    status: str,
    duration: float,
    error: str | None = None,
):
    """
    Log tool completion.

    Args:
        tool_name: Name of the tool
        status: Completion status ("success" or "error")
        duration: Execution time in seconds
        error: Optional error message
    """
    logger = logging.getLogger(__name__)

    extra = {
        "event": "TOOL_COMPLETE",
        "tool": tool_name,
        "status": status,
        "duration": f"{duration:.3f}s",
    }

    message = f"TOOL_COMPLETE: {tool_name}"

    if status == "error":
        if error:
            extra["error"] = error
            message += f" | error: {error}"
        logger.error(message, extra=extra)
    else:
        logger.info(message, extra=extra)


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
            "event": "SSH_CONNECT",
            "host": host,
            "username": username,
            "status": status,
        }

        # At INFO level, just log basic success
        message = f"SSH_CONNECT: {user_host}"

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
            "event": "SSH_CONNECT_FAILED",
            "host": host,
            "username": username,
            "status": "failed",
        }

        if error:
            extra["reason"] = error

        message = f"SSH_AUTH_FAILED: {user_host}"
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
        "event": "REMOTE_EXEC",
        "command": command,
        "host": host,
        "exit_code": exit_code,
    }

    message = f"REMOTE_EXEC: {command} | host={host} | exit_code={exit_code}"

    # At DEBUG level, include duration
    if duration is not None and logger.isEnabledFor(logging.DEBUG):
        extra["duration"] = f"{duration:.3f}s"
        message += f" | duration={duration:.3f}s"

    logger.info(message, extra=extra)


def log_operation(operation: str, message: str, level: int = logging.INFO, **context):
    """
    Log a general operation with context.

    This is a generic logging function for operations that don't fit
    other specific logging functions.

    Args:
        operation: Name of the operation
        message: Log message
        level: Log level (default: INFO)
        **context: Additional context fields
    """
    logger = logging.getLogger(__name__)

    extra = {"operation": operation, **context}

    full_message = f"{operation}: {message}"

    logger.log(level, full_message, extra=extra)
