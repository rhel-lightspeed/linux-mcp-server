"""Tests for system information tools."""

import sys

import pytest


@pytest.fixture
def mock_execute(mock_execute_with_fallback_for):
    return mock_execute_with_fallback_for("linux_mcp_server.commands")


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux commands")
@pytest.mark.parametrize(
    "tool, expected",
    (
        (
            "get_system_information",
            (
                ("hostname",),
                ("kernel",),
                ("operating system", "os"),
                ("uptime",),
            ),
        ),
        (
            "get_cpu_information",
            (
                ("cpu", "processor"),
                ("load", "usage"),
            ),
        ),
        (
            "get_memory_information",
            (
                ("memory", "ram"),
                ("total",),
                ("used", "available"),
            ),
        ),
        (
            "get_disk_usage",
            (
                ("filesystem", "device", "mounted"),
                ("/",),
            ),
        ),
    ),
)
async def test_system_info_tools(tool, expected, mcp_client):
    result = await mcp_client.call_tool(tool)
    result_text = result.content[0].text.casefold()

    assert all(any(n in result_text for n in case) for case in expected), "Did not find all expected values"


@pytest.mark.parametrize(
    "tool",
    (
        "get_memory_information",
        "get_disk_usage",
    ),
)
async def test_system_info_tools_unsuccessful(tool, mcp_client, mock_execute):
    mock_execute.return_value = (0, "", "")

    result = await mcp_client.call_tool(tool)
    result_text = result.content[0].text.casefold()

    assert "error" in result_text


@pytest.mark.parametrize(
    "tool",
    (
        "get_system_information",
        "get_cpu_information",
    ),
)
async def test_system_info_tools_unsuccessful_empty(tool, mcp_client, mock_execute):
    mock_execute.return_value = (0, "", "")

    result = await mcp_client.call_tool(tool)
    result_text = result.content[0].text.casefold()

    assert result_text == ""
