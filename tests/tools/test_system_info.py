"""Tests for system information tools."""

import sys

from contextlib import nullcontext

import pytest

from fastmcp.exceptions import ToolError


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
        (
            "get_hardware_information",
            [("hardware information", "cpu architecture")],
        ),
    ),
)
async def test_system_info_tools(tool, expected, mcp_client):
    result = await mcp_client.call_tool(tool)
    result_text = result.content[0].text.casefold()

    assert all(any(n in result_text for n in case) for case in expected), "Did not find all expected values"


@pytest.mark.parametrize(
    "tool, return_value, side_effect, expected, assertion",
    (
        (
            "get_memory_information",
            (0, "", ""),
            None,
            pytest.raises(ToolError, match="Unable to retrieve"),
            "result_text == ''",
        ),
        (
            "get_disk_usage",
            (0, "", ""),
            None,
            pytest.raises(ToolError, match="Unable to retrieve"),
            "result_text == ''",
        ),
        ("get_system_information", (0, "", ""), None, nullcontext(), "result_text == ''"),
        ("get_cpu_information", (0, "", ""), None, nullcontext(), "result_text == ''"),
        (
            "get_hardware_information",
            (1, "", ""),
            None,
            nullcontext(),
            "'no hardware information tools available' in result_text",
        ),
        (
            "get_hardware_information",
            (1, "", ""),
            FileNotFoundError,
            nullcontext(),
            "'command not available' in result_text",
        ),
    ),
)
async def test_system_info_tools_unsuccessful(
    tool, return_value, side_effect, expected, assertion, mcp_client, mock_execute
):
    mock_execute.return_value = return_value
    mock_execute.side_effect = side_effect

    result_text = None
    with expected:
        result = await mcp_client.call_tool(tool)
        result_text = result.content[0].text.casefold()

    if result_text:
        assert eval(assertion)
