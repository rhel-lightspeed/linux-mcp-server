# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
from utils.shell import shell


async def test_listening_ports(mcp_session):
    """
    Verify that the server lists correctly all the available listening ports.
    """
    response = await mcp_session.call_tool("get_listening_ports")
    assert response is not None

    content = response.structured_content["result"]
    assert content is not None

    mcp_locals = {f"{port['local_address']}:{port['local_port']}" for port in content}
    shell_output = shell("ss -tulnp", silent=True).stdout.strip()
    shell_lines = [line for line in shell_output.split("\n")[1:] if line.strip()]

    for line in shell_lines:
        parts = line.split()
        if len(parts) >= 5:
            local_addr = parts[4]
            assert local_addr in mcp_locals, f"Listening port {local_addr} not found in structured output"
