# Copyright Red Hat
import os
import json
import pytest
from utils.shell import shell


async def test_list_block_devices_happy_path(mcp_session):
    """
    Verify that the server lists block devices correctly.
    Happy path test - basic invocation should return block device information.
    """
    response = await mcp_session.call_tool("list_block_devices")
    assert response is not None
    assert response.content[0].text is not None

    data = json.loads(response.content[0].text)
    assert "blockdevices" in data
    assert isinstance(data["blockdevices"], list)
    assert data.get("total", 0) == len(data["blockdevices"])


@pytest.mark.skipif(
    os.getenv("MCP_TESTS_CONTAINER_EXECUTION", "").lower() == "true",
    reason="Skipping root device assertion inside container",
)
async def test_list_block_devices_contains_root_device(mcp_session):
    """
    Verify that the root filesystem block device appears in the list.
    """
    response = await mcp_session.call_tool("list_block_devices")
    assert response is not None

    root_device_name = shell(
        "basename $(df --output=source / | tail -1)", silent=True
    ).stdout.strip()
    
    # In some setups, df / gives a mapped device name like luks-...
    # which lsblk doesn't show at top level, but it will be somewhere in the response text.
    # We can just check the raw JSON text as a fallback, or recursively search.
    # Searching the raw JSON text is easiest since it covers all nested children.
    assert root_device_name in response.content[0].text
