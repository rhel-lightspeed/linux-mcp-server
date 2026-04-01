# Copyright Red Hat
from utils.shell import shell


async def test_listening_ports(mcp_session):
    """
    Verify that the server lists correctly all the available listening ports.
    """

    response = await mcp_session.call_tool("get_listening_ports")
    assert response is not None

    mcp_output = response.content[0].text
    shell_output = shell("ss -tulnp", silent=True).stdout.strip()

    assert "=== Listening Ports ===" in mcp_output
    assert "Proto" in mcp_output
    assert "Local Address" in mcp_output
    shell_lines = [line for line in shell_output.split("\n")[1:] if line.strip()]
    expected_count = len(shell_lines)
    assert f"Total listening ports: {expected_count}" in mcp_output

    for line in shell_lines:
        parts = line.split()
        if len(parts) >= 5:
            local_addr = parts[4]
            assert local_addr in mcp_output, (
                f"Listening port {local_addr} not found in MCP output"
            )
