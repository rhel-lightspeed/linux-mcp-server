import re

from unittest.mock import AsyncMock

import pytest

from fastmcp.exceptions import ToolError


async def test_list_block_devices(mock_execute_with_fallback, mcp_client):
    lsblk_output = '{"blockdevices":[{"name":"sda","size":"1TB","type":"disk","mountpoint":null,"fstype":null,"model":null,"children":[{"name":"sda1","size":"512G","type":"part","mountpoint":"/","fstype":"ext4","model":null}]}]}'
    mock_execute_with_fallback.return_value = (0, lsblk_output, "")

    result = await mcp_client.call_tool("list_block_devices", {})
    result = result.structured_content
    first_device = result["blockdevices"][0]

    assert first_device["name"] == "sda"
    assert first_device["children"][0]["name"] == "sda1"

    mock_execute_with_fallback.assert_called_once()
    args = mock_execute_with_fallback.call_args[0][0]
    assert args[0] == "lsblk"
    assert "-o" in args


@pytest.mark.parametrize(
    "side_effect, expected_match",
    (
        (
            AsyncMock(return_value=(1, "", "command failed")),
            re.compile(r"Unable to list block devices", flags=re.I),
        ),
        (FileNotFoundError("lsblk not found"), re.compile("not found", flags=re.I)),
        (ValueError("Raised intentionally"), re.compile(r"error.*raised intentionally", flags=re.I)),
        (
            AsyncMock(return_value=(1, "", "Unable to list block devices")),
            re.compile("Unable to list block devices"),
        ),
    ),
)
async def test_list_block_devices_command_failure(side_effect, expected_match, mocker, mcp_client):
    mocker.patch(
        "linux_mcp_server.commands.execute_with_fallback",
        side_effect=side_effect,
        autospec=True,
    )

    with pytest.raises(ToolError, match=expected_match):
        await mcp_client.call_tool("list_block_devices", {})


async def test_list_block_devices_remote_execution(mock_execute_with_fallback, mcp_client):
    mock_execute_with_fallback.return_value = (0, "NAME   SIZE TYPE\nsda    1TB  disk", "")
    mock_execute_with_fallback.return_value = (
        0,
        '{"blockdevices":[{"name":"sda","size":"1TB","type":"disk","mountpoint":null,"fstype":null,"model":null,"children":[]}]}',
        "",
    )

    result = await mcp_client.call_tool("list_block_devices", {"host": "remote.host.com"})
    device_names = [item["name"] for item in result.structured_content["blockdevices"]]

    assert "sda" in device_names

    mock_execute_with_fallback.assert_called_once()
    call_kwargs = mock_execute_with_fallback.call_args[1]
    assert call_kwargs["host"] == "remote.host.com"
