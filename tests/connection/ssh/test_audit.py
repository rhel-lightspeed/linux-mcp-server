"""The local and remote executors expose the same audit results."""

import logging

import asyncssh
import pytest

from linux_mcp_server.audit import audit_context
from linux_mcp_server.audit import CommandDescription
from linux_mcp_server.audit import Event
from linux_mcp_server.connection.ssh import _execute_local
from linux_mcp_server.connection.ssh import execute_command
from linux_mcp_server.connection.ssh import SSHConnectionManager
from linux_mcp_server.execution_context import ExecutionContext
from linux_mcp_server.execution_context import use_execution_context


@pytest.mark.parametrize("remote", [False, True])
@pytest.mark.parametrize("exit_status", [0, 3])
async def test_command_result(remote, exit_status, mocker, caplog):
    command = ["/bin/sh", "-c", f"exit {exit_status}"]
    manager = SSHConnectionManager()
    conn = mocker.Mock(spec=asyncssh.SSHClientConnection)
    conn.run = mocker.AsyncMock(
        spec=asyncssh.SSHClientConnection.run,
        return_value=asyncssh.SSHCompletedProcess(
            exit_status=exit_status,
            stdout="",
            stderr="",
        ),
    )
    mocker.patch.object(manager, "get_connection", autospec=True, return_value=conn)
    host = "remote" if remote else "localhost"

    with caplog.at_level(logging.INFO), audit_context(call_id="c42", tool="example"):
        if remote:
            result = await manager.execute_remote(command, host)
        else:
            result = await _execute_local(command)

    assert result[0] == exit_status

    events = [r for r in caplog.records if getattr(r, "audit_event", None) == Event.COMMAND_COMPLETE]
    assert len(events) == 1

    record = events[0]
    assert record.command == f"/bin/sh -c 'exit {exit_status}'"
    assert record.host == host
    assert record.exit_status == exit_status
    assert not hasattr(record, "error")
    assert record.status == ("success" if exit_status == 0 else "failed")
    assert record.call_id == "c42"
    assert record.duration_ms >= 0


@pytest.mark.parametrize("remote", [False, True])
async def test_command_lookup_failure(remote, mocker, caplog):
    manager = SSHConnectionManager()
    conn = mocker.Mock(spec=asyncssh.SSHClientConnection)
    mocker.patch.object(manager, "get_connection", autospec=True, return_value=conn)
    mocker.patch(
        "linux_mcp_server.connection.ssh.get_remote_bin_path",
        autospec=True,
        side_effect=FileNotFoundError("Missing command"),
    )
    mocker.patch(
        "linux_mcp_server.connection.ssh.get_bin_path", autospec=True, side_effect=FileNotFoundError("Missing command")
    )

    with caplog.at_level(logging.INFO), pytest.raises(FileNotFoundError):
        if remote:
            await manager.execute_remote(["missing"], "remote")
        else:
            await _execute_local(["missing"])

    assert len(caplog.records) == 1

    record = caplog.records[0]
    assert record.audit_event == Event.COMMAND_COMPLETE
    assert record.status == "error"
    assert record.error == "Missing command"
    assert not hasattr(record, "exit_status")


async def test_local_spawn_failure_propagates(caplog):
    with caplog.at_level(logging.INFO), pytest.raises(FileNotFoundError) as error:
        await _execute_local(["/nonexistent-linux-mcp-test-command"])

    record = caplog.records[-1]
    assert record.audit_event == Event.COMMAND_COMPLETE
    assert record.status == "error"
    assert not hasattr(record, "exit_status")
    assert record.error == str(error.value)


async def test_local_command_description(caplog):
    description = CommandDescription(command="exit 0", interpreter="bash")

    with caplog.at_level(logging.INFO), use_execution_context(ExecutionContext(allow_local=True)):
        result = await execute_command(["/bin/sh", "-c", "exit 0"], "localhost", description=description)

    assert result[0] == 0
    record = caplog.records[-1]
    assert record.audit_event == Event.COMMAND_COMPLETE
    assert record.command == "exit 0"
    assert record.interpreter == "bash"
