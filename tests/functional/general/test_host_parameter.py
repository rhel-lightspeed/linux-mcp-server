# Copyright Contributors to the linux-mcp-server project
# SPDX-License-Identifier: Apache-2.0
import pytest


# A tool with no other required arguments, so 'host' is the only thing missing.
TOOL = "get_system_information"


async def test_host_is_required(mcp_session):
    """
    Verify a tool call that omits 'host' is refused rather than defaulting to
    the system the server runs on.
    """
    response = await mcp_session.call_tool_exactly(TOOL, {})
    assert response is not None
    assert "'host' parameter is required" in response.content[0].text


@pytest.mark.parametrize("host", [None, "", 42], ids=["null", "empty", "not-a-string"])
async def test_host_must_be_a_host_name(mcp_session, host):
    """
    Verify 'host' values that cannot name a system are refused. The server checks
    this itself because authorization runs before argument validation.
    """
    response = await mcp_session.call_tool_exactly(TOOL, {"host": host})
    assert response is not None
    assert "'host' parameter is required" in response.content[0].text


async def test_localhost_runs_on_the_server(mcp_session):
    """
    Verify 'localhost' is accepted and runs the work locally rather than being
    treated as a host to reach over SSH.
    """
    response = await mcp_session.call_tool_exactly(TOOL, {"host": "localhost"})
    assert response is not None
    assert not response.isError, response.content[0].text
