"""Tests for target host information discovery."""

import pytest

from pytest_mock import MockType

from linux_mcp_server.utils.hostinfo import discover_timezone_name
from linux_mcp_server.utils.hostinfo import TimezoneDiscoveryError


async def test_discover_timezone_name(mock_execute_with_fallback: MockType) -> None:
    mock_execute_with_fallback.return_value = (0, "America/New_York\n", "")

    assert await discover_timezone_name("example.test") == "America/New_York"
    mock_execute_with_fallback.assert_awaited_once_with(
        ("timedatectl", "show", "-p", "Timezone", "--value"),
        fallback=("cat", "/etc/timezone"),
        host="example.test",
    )


@pytest.mark.parametrize(
    ("result", "message"),
    [
        ((1, "", "timedatectl failed"), "command exited with status 1: timedatectl failed"),
        ((0, "  \n", ""), "command returned empty output"),
    ],
)
async def test_discover_timezone_name_reports_command_failure(
    mock_execute_with_fallback: MockType, result: tuple[int, str, str], message: str
) -> None:
    mock_execute_with_fallback.return_value = result

    with pytest.raises(TimezoneDiscoveryError, match=message) as exc:
        await discover_timezone_name("example.test")
    assert "example.test" in str(exc.value)


async def test_discover_timezone_name_propagates_execution_errors(mock_execute_with_fallback: MockType) -> None:
    error = OSError("ssh: connect failed")
    mock_execute_with_fallback.side_effect = error

    with pytest.raises(OSError) as exc:
        await discover_timezone_name("example.test")
    assert exc.value is error
