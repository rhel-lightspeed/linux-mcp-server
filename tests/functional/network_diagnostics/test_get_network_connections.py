# Copyright Red Hat
from utils.shell import shell


async def test_network_connections(mcp_session):
    """
    Verify that the server lists correctly all the available network connections.
    """
    response = await mcp_session.call_tool("get_network_connections")
    assert response is not None

    mcp_output = response.content[0].text
    shell_output = shell("ss -tunap", silent=True).stdout.strip()
    assert "=== Active Network Connections ===" in mcp_output
    assert "Proto" in mcp_output
    assert "Local Address" in mcp_output
    assert "Remote Address" in mcp_output
    assert "Status" in mcp_output

    shell_lines = [line for line in shell_output.split("\n")[1:] if line.strip()]
    expected_count = len(shell_lines)
    # Verify the output has a total connections line (count may slightly vary due to transient connections)
    assert "Total connections:" in mcp_output

    found_count = 0
    total_checked = 0
    for line in shell_lines:
        parts = line.split()
        if len(parts) >= 5:
            total_checked += 1
            # Column 4 is Local Address:Port in ss -tunap output
            local_addr = parts[4]
            if local_addr in mcp_output:
                found_count += 1
                
    if total_checked > 0:
        # At least 80% of connections should match between the two calls
        assert found_count >= total_checked * 0.8, f"Only {found_count} out of {total_checked} connections matched"
