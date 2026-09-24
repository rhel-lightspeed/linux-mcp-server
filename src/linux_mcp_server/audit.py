"""Audit logging utilities for Linux MCP Server.

This module provides helper functions for consistent audit logging across
the server. Events include structured context that can be rendered in both
human-readable and JSON formats.
"""

import asyncio
import logging
import time
import typing as t

from contextlib import contextmanager
from contextvars import ContextVar

from pydantic import BaseModel

from linux_mcp_server.utils import StrEnum
from linux_mcp_server.utils.types import Host


logger = logging.getLogger(__name__)
_context: ContextVar[dict[str, t.Any]] = ContextVar("audit_context", default={})

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
    TOOL_CALL = "TOOL_CALL"
    TOOL_COMPLETE = "TOOL_COMPLETE"
    COMMAND_COMPLETE = "COMMAND_COMPLETE"
    GATEKEEPER_RESULT = "GATEKEEPER_RESULT"
    SSH_CONNECT = "SSH_CONNECT"
    SSH_AUTH_FAILED = "SSH_AUTH_FAILED"


class Status(StrEnum):
    success = "success"
    error = "error"
    failed = "failed"


def sanitize_parameters(value: t.Any) -> t.Any:
    """Redact sensitive keys recursively, including dictionaries inside sequences."""
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("_", "").replace("-", "")
            sensitive = any(field.replace("_", "") in normalized for field in SENSITIVE_FIELDS)
            sanitized[key] = "***REDACTED***" if sensitive else sanitize_parameters(item)

        return sanitized

    if isinstance(value, (list, tuple)):
        return [sanitize_parameters(item) for item in value]

    return value


@contextmanager
def audit_context(**fields: t.Any) -> t.Iterator[dict[str, t.Any]]:
    """Add additional audit context fields for the duration of the body."""
    context = {**_context.get(), **sanitize_parameters(fields)}
    token = _context.set(context)

    try:
        yield context
    finally:
        _context.reset(token)


class AuditFilter(logging.Filter):
    """Attach request context to diagnostic and dependency records at output time."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in _context.get().items():
            record.__dict__.setdefault(key, value)

        return True


def log_event(event: Event, message: str, *, level: int = logging.INFO, **fields: t.Any) -> None:
    """Emit a primary event with a stable name and separate structured attributes."""
    logger.log(level, message, extra={"audit_event": event, **_context.get(), **sanitize_parameters(fields)})


class CommandDescription(BaseModel):
    """The intended command to report when execution uses a wrapper."""

    command: str
    interpreter: str | None = None


class CommandExecution(BaseModel):
    """The command being logged and its exit status, once the process exits."""

    command: str
    exit_status: int | None = None

    def set_exit_status(self, exit_status: int) -> None:
        self.exit_status = exit_status


@contextmanager
def log_command_execution(
    command: str, host: Host, *, description: CommandDescription | None = None
) -> t.Iterator[CommandExecution]:
    """Log one execution result and propagate execution errors to the caller.

    The caller must call set_exit_status() on the yielded object when the process
    exits. If execution raises instead, log the error without an exit status,
    even if one was previously set.
    Script callers can supply a description of the intended command. It applies
    only to this execution record, not other records emitted during execution.
    """
    execution = CommandExecution(command=description.command if description is not None else command)
    fields: dict[str, t.Any] = {"command": execution.command, "host": host}
    if description is not None and description.interpreter is not None:
        fields["interpreter"] = description.interpreter

    start = time.perf_counter()
    try:
        yield execution
    except BaseException as exc:
        fields.update(status="cancelled" if isinstance(exc, asyncio.CancelledError) else "error", error=str(exc))
        raise
    else:
        fields.update(exit_status=execution.exit_status, status="failed" if execution.exit_status else "success")
    finally:
        log_event(
            Event.COMMAND_COMPLETE,
            "Command completed",
            level=logging.ERROR if fields["status"] == "error" else logging.INFO,
            **fields,
            duration_ms=(time.perf_counter() - start) * 1000,
        )


def log_ssh_connect(
    host: Host,
    status: str,
    username: str = "",
    reused: bool = False,
    key_path: str | None = None,
    error: str | None = None,
) -> None:
    """Log new connections at INFO, reuse at DEBUG, and failures at WARNING."""
    level = logging.INFO if status == Status.success else logging.WARNING
    if status == Status.success and reused:
        level = logging.DEBUG

    log_event(
        Event.SSH_CONNECT if status == Status.success else Event.SSH_AUTH_FAILED,
        "SSH connected" if status == Status.success else "SSH connection failed",
        level=level,
        host=host,
        username=username,
        status=status,
        reused=reused,
        key_path=key_path,
        error=error,
    )
