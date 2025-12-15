"""Tests for system information tools."""

import sys

import pytest


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


@pytest.mark.skipif(sys.platform != "linux", reason="requires Linux commands")
async def test_get_hardware_info(mcp_client):
    """Test that get_hardware_information returns a non-empty string."""
    result = await mcp_client.call_tool("get_hardware_information")
    result_text = result.content[0].text

    assert isinstance(result_text, str)
    assert len(result_text) > 0
    # Should not start with "Error" if successful
    assert not result_text.startswith("Error"), f"Unexpected error: {result_text[:200]}"
