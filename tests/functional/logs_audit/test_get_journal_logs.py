# Copyright Red Hat
import json
import os

import pytest

from utils.shell import shell


async def _assert_journal_logs_match(mcp_session, arguments, journalctl_cmd):
    """
    Helper to call get_journal_logs and verify that its output exists within a
    wider window of the actual system journal to account for race conditions.
    """
    response = await mcp_session.call_tool("get_journal_logs", arguments=arguments)
    assert response is not None

    # Fetch a wider window (100 lines) from the shell to ensure the tool's
    # output (usually 5 lines) is captured even if new logs arrive
    # during the millisecond gap between the tool call and the shell call.
    wide_cmd = journalctl_cmd.replace("-n 5", "-n 100")
    actual_journal_logs = shell(wide_cmd, silent=True).stdout.strip()

    data = json.loads(response.content[0].text)
    tool_entries = data.get("entries", [])

    # Verify the tool's output is a contiguous subset of the journal.
    # We join with newlines to ensure we match the exact sequence of log lines.
    # We don't strictly assert on the count of tool_entries because
    # journalctl metadata (like boot markers) can cause the output to exceed
    # the requested line count.
    assert "\n".join(tool_entries) in actual_journal_logs


async def test_get_journal_logs(mcp_session):
    """
    Verify that the get_journal_logs tool works as expected.
    Also with different types of arguments
    """

    # 1. Happy path to show last 5 lines of the systemd-journald journal log
    await _assert_journal_logs_match(
        mcp_session,
        arguments={"unit": "systemd-journald", "lines": 5},
        journalctl_cmd="journalctl -u systemd-journald -n 5 --no-pager",
    )

    # 2. Call the tool with the lines=-1 argument. The tool returns an integer error
    response = await mcp_session.call_tool("get_journal_logs", arguments={"unit": "systemd-journald", "lines": -1})
    assert response is not None
    response_text = response.content[0].text
    assert "1 validation error for call[get_journal_logs]" in response_text
    assert "Input should be greater than or equal to 1" in response_text

    # 3. Happy path to show last 5 lines of the systemd-journald journal log with priority=warning
    await _assert_journal_logs_match(
        mcp_session,
        arguments={"unit": "systemd-journald", "lines": 5, "priority": "warning"},
        journalctl_cmd="journalctl -u systemd-journald -n 5 -p warning --no-pager",
    )

    # 4. Happy path to show last 5 lines of the systemd-journald journal log with priority and since argument
    await _assert_journal_logs_match(
        mcp_session,
        arguments={
            "unit": "systemd-journald",
            "lines": 5,
            "priority": "warning",
            "since": "1h ago",
        },
        journalctl_cmd="journalctl -u systemd-journald -n 5 -p warning --since '1h ago' --no-pager",
    )

    # 5. Call the tool with the invalid since argument
    response = await mcp_session.call_tool(
        "get_journal_logs", arguments={"unit": "systemd-journald", "lines": 5, "since": "1h"}
    )
    assert response is not None
    assert "Error reading journal logs: Failed to parse timestamp: 1h" in response.content[0].text


async def test_get_journal_logs_non_existing_unit(mcp_session):
    """
    Verify that the get_journal_logs tool works as expected.
    Also with different types of arguments
    """

    await _assert_journal_logs_match(
        mcp_session,
        arguments={"unit": "superamazingunit", "lines": 5},
        journalctl_cmd="journalctl -n 5 --no-pager --unit superamazingunit",
    )


@pytest.mark.skipif(
    os.getenv("MCP_TESTS_CONTAINER_EXECUTION", "").lower() == "true",
    reason="Audit logs are not available inside container",
)
@pytest.mark.skipif(
    not os.path.exists("/var/log/audit/audit.log"),
    reason="Audit log file does not exist",
)
async def test_get_journal_logs_audit(mcp_session):
    """
    Verify that the get_journal_logs tool works as expected with the audit transport.
    """

    # Happy path to show last 5 lines of the auditd journal log
    await _assert_journal_logs_match(
        mcp_session,
        arguments={"lines": 5, "transport": "audit"},
        journalctl_cmd="journalctl -n 5 --no-pager _TRANSPORT=audit",
    )
