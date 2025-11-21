import pytest

from linux_mcp_server.tools import get_audit_logs
from linux_mcp_server.tools import get_journal_logs
from linux_mcp_server.tools import read_log_file


async def test_get_journal_logs(mocker):
    mocker.patch("linux_mcp_server.tools.logs.execute_command", return_value=(1, "", ""))

    result = await get_journal_logs()

    assert "Error reading journal logs" in result


async def test_get_audit_logs(mocker):
    mocker.patch("linux_mcp_server.tools.logs.validate_line_count", side_effect=ValueError("Raised intentionally"))

    with pytest.raises(ValueError, match="Raised intentionally"):
        await get_audit_logs()


async def test_read_log_file(mocker):
    mocker.patch("linux_mcp_server.tools.logs.validate_line_count", side_effect=ValueError("Raised intentionally"))

    result = await read_log_file("some_file")

    assert "Error reading log file" in result
    assert "Raised intentionally" in result
