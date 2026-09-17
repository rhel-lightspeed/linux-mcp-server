# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
from utils.shell import shell


async def test_network_connections(mcp_session):
    """
    Verify that the server lists correctly all the available network connections.
    """
    response = await mcp_session.call_tool("get_network_connections")
    assert response is not None

    content = response.structured_content["result"]
    assert content is not None

    mcp_locals = {f"{conn['local_address']}:{conn['local_port']}" for conn in content}
    shell_output = shell("ss -tunap", silent=True).stdout.strip()
    shell_lines = [line for line in shell_output.split("\n")[1:] if line.strip()]

    found_count = 0
    total_checked = 0
    for line in shell_lines:
        parts = line.split()
        if len(parts) >= 5:
            total_checked += 1
            local_addr = parts[4]
            if local_addr in mcp_locals:
                found_count += 1

    if total_checked > 0:
        assert found_count >= total_checked * 0.8, f"Only {found_count} out of {total_checked} connections matched"
