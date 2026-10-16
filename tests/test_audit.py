"""Tests for structured audit records and request isolation."""

import asyncio
import json
import logging

import pytest

from linux_mcp_server.audit import audit_context
from linux_mcp_server.audit import CommandDescription
from linux_mcp_server.audit import Event
from linux_mcp_server.audit import log_command_execution
from linux_mcp_server.audit import log_event
from linux_mcp_server.audit import log_ssh_connect
from linux_mcp_server.audit import sanitize_parameters
from linux_mcp_server.audit import SENSITIVE_FIELDS
from linux_mcp_server.logging_config import JSONFormatter


class TestSanitizeParameters:
    """Test parameter sanitization."""

    def test_sanitize_empty_dict(self):
        """Test sanitizing empty parameters."""
        result = sanitize_parameters({})
        assert result == {}

    def test_sanitize_normal_parameters(self):
        """Test sanitizing normal parameters."""
        params = {"host": "server1.com", "lines": 50, "service_name": "nginx"}
        result = sanitize_parameters(params)
        assert result == params

    def test_sanitize_password_field(self):
        """Test that password fields are sanitized."""
        params = {"username": "admin", "password": "secret123", "host": "server1.com"}
        result = sanitize_parameters(params)
        assert result["username"] == "admin"
        assert result["password"] == "***REDACTED***"
        assert result["host"] == "server1.com"

    def test_sanitize_api_key_field(self):
        """Test that API key fields are sanitized."""
        params = {"api_key": "secret_key_123", "host": "api.example.com"}
        result = sanitize_parameters(params)
        assert result["api_key"] == "***REDACTED***"
        assert result["host"] == "api.example.com"

    def test_sanitize_token_field(self):
        """Test that token fields are sanitized."""
        params = {"token": "bearer_token_123", "username": "admin"}
        result = sanitize_parameters(params)
        assert result["token"] == "***REDACTED***"
        assert result["username"] == "admin"

    def test_sanitize_nested_dict(self):
        """Test sanitizing nested dictionaries."""
        params = {
            "config": {
                "password": "secret",
                "host": "server.com",
            },
            "username": "admin",
        }
        result = sanitize_parameters(params)
        assert result["config"]["password"] == "***REDACTED***"
        assert result["config"]["host"] == "server.com"
        assert result["username"] == "admin"


@pytest.mark.parametrize("field", SENSITIVE_FIELDS)
def test_nested_redaction(field):
    value = {"items": [{field: "secret", "nested": ({field: "secret"},)}], "ctx": {"ctx": {field: "secret"}}}

    safe = sanitize_parameters(value)

    assert ': "secret"' not in json.dumps(safe)
    assert safe["items"][0]["nested"][0][field] == "***REDACTED***"
    assert safe["ctx"]["ctx"][field] == "***REDACTED***"
    assert value["items"][0][field] == "secret"


async def test_context_isolation_and_restoration(caplog):
    ready = {"one": asyncio.Event(), "two": asyncio.Event()}

    async def emit(call_id):
        with audit_context(call_id=call_id, claims={"token": "secret"}):
            ready[call_id].set()
            await ready["two" if call_id == "one" else "one"].wait()

            with audit_context(host="remote"):
                log_event(Event.TOOL_CALL, "Nested")

            log_event(Event.TOOL_COMPLETE, "Restored")

    with caplog.at_level(logging.INFO):
        await asyncio.gather(emit("one"), emit("two"))

        log_event(Event.TOOL_COMPLETE, "Outside")

    for call_id in ("one", "two"):
        nested, restored = [r for r in caplog.records if getattr(r, "call_id", None) == call_id]
        assert nested.host == "remote"
        assert not hasattr(restored, "host")
        assert nested.claims == {"token": "***REDACTED***"}

    assert not hasattr(caplog.records[-1], "call_id")


@pytest.mark.parametrize("error", [None, ValueError("failed"), asyncio.CancelledError(), KeyboardInterrupt()])
def test_command_completion(caplog, error):
    with caplog.at_level(logging.INFO):
        try:
            with audit_context(call_id="call", command="python -c script"):
                with log_command_execution("wrapper", "localhost") as execution:
                    execution.set_exit_status(3)
                    if error:
                        raise error
        except (ValueError, asyncio.CancelledError, KeyboardInterrupt) as exc:
            assert exc is error

        log_event(Event.TOOL_COMPLETE, "Outside")

    record = caplog.records[0]
    assert record.audit_event == Event.COMMAND_COMPLETE
    assert record.command == "wrapper"
    assert record.call_id == "call"
    assert record.host == "localhost"
    assert record.duration_ms >= 0
    assert record.status == (
        "cancelled" if isinstance(error, asyncio.CancelledError) else "error" if error else "failed"
    )

    if error:
        assert record.error == str(error)
        assert not hasattr(record, "exit_status")
    else:
        assert record.exit_status == 3
        assert not hasattr(record, "error")

    assert not hasattr(caplog.records[-1], "call_id")


@pytest.mark.parametrize(
    "status,reused,level,event",
    [
        ("success", False, logging.INFO, Event.SSH_CONNECT),
        ("success", True, logging.DEBUG, Event.SSH_CONNECT),
        ("failed", False, logging.WARNING, Event.SSH_AUTH_FAILED),
    ],
)
def test_ssh_connection_levels(caplog, status, reused, level, event):
    with caplog.at_level(logging.DEBUG):
        log_ssh_connect("server1", status=status, reused=reused, key_path="/key", error="reason")

    record = caplog.records[0]
    assert record.audit_event == event
    assert record.levelno == level
    assert record.host == "server1"
    assert record.reused is reused
    assert record.key_path == "/key"
    assert record.error == "reason"


def test_event_envelope(caplog):
    with caplog.at_level(logging.INFO), audit_context(tool="list_services", call_id="c42"):
        log_event(Event.TOOL_CALL, "Tool called", parameters={"token": "secret"})

    data = json.loads(JSONFormatter().format(caplog.records[0]))
    assert data["event"] == "TOOL_CALL"
    assert data["message"] == "Tool called"
    assert data["attributes"] == {
        "call_id": "c42",
        "tool": "list_services",
        "parameters": {"token": "***REDACTED***"},
    }


@pytest.mark.parametrize("interpreter", [None, "bash"])
def test_command_description_is_specific_to_execution(caplog, interpreter):
    description = CommandDescription(command="echo intended", interpreter=interpreter)

    with caplog.at_level(logging.INFO), audit_context(call_id="call"):
        with log_command_execution("wrapper", "remote", description=description) as execution:
            log_ssh_connect("remote", status="success")
            with log_command_execution("unrelated", "remote") as nested:
                nested.set_exit_status(0)
            execution.set_exit_status(0)

    connection, unrelated, script = caplog.records
    assert not hasattr(connection, "command")
    assert not hasattr(connection, "interpreter")
    assert unrelated.command == "unrelated"
    assert not hasattr(unrelated, "interpreter")
    assert script.command == "echo intended"
    assert getattr(script, "interpreter", None) == interpreter
