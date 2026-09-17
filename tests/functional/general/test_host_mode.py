# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
import pytest


# A tool with no other required arguments, so 'host' is the only thing that matters.
TOOL = "get_system_information"

REMOTE = "web1.example.com"

LOCAL_ONLY = [{"LINUX_MCP_HOST_MODE": "local-only"}]
REMOTE_ONLY = [{"LINUX_MCP_HOST_MODE": "remote-only"}]


@pytest.mark.parametrize("mcp_session", LOCAL_ONLY, indirect=True)
async def test_local_only_refuses_a_remote_host(mcp_session):
    """
    Verify local-only mode refuses a host it would have to reach over SSH.
    """
    response = await mcp_session.call_tool_exactly(TOOL, {"host": REMOTE})
    assert response is not None
    assert f"cannot connect to '{REMOTE}'" in response.content[0].text


@pytest.mark.parametrize("mcp_session", LOCAL_ONLY, indirect=True)
async def test_local_only_drops_the_host_parameter(mcp_session):
    """
    Verify the model isn't asked to recite the only host the server would accept.
    """
    response = await mcp_session.list_tools()
    tool = next(tool for tool in response.tools if tool.name == TOOL)

    assert "host" not in tool.inputSchema["properties"]


@pytest.mark.parametrize("mcp_session", LOCAL_ONLY, indirect=True)
async def test_local_only_runs_without_a_host(mcp_session):
    """
    Verify a call made from that schema - with no 'host' at all - actually runs.
    """
    response = await mcp_session.call_tool_exactly(TOOL, {})
    assert response is not None
    assert not response.isError


@pytest.mark.parametrize("mcp_session", REMOTE_ONLY, indirect=True)
async def test_remote_only_refuses_localhost(mcp_session):
    """
    Verify remote-only mode refuses to run anything on the system the server runs on.
    """
    response = await mcp_session.call_tool_exactly(TOOL, {"host": "localhost"})
    assert response is not None
    assert "only run tools on remote systems" in response.content[0].text


@pytest.mark.parametrize("mcp_session", REMOTE_ONLY, indirect=True)
async def test_remote_only_describes_itself(mcp_session):
    """
    Verify the model is told localhost is unavailable before it tries to use it.
    """
    response = await mcp_session.list_tools()
    tool = next(tool for tool in response.tools if tool.name == TOOL)

    assert "cannot run anything on the system it runs on" in tool.inputSchema["properties"]["host"]["description"]
