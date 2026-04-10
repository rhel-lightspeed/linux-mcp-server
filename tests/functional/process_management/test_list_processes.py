# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
async def test_list_processes(mcp_session):
    """
    Verify that the server lists correctly all the running processes.
    """
    response = await mcp_session.call_tool("list_processes")
    assert response is not None

    assert response.content[0].text is not None
    assert len(response.content[0].text) > 0
    assert "=== Running Processes ===" in response.content[0].text
    assert "PID" in response.content[0].text
    assert "User" in response.content[0].text
    assert "Command" in response.content[0].text
