"""Tests for resolving the host that a tool call targets."""

import pytest

from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool

from linux_mcp_server.target_host import resolve_target_host
from linux_mcp_server.target_host import target_host_from
from linux_mcp_server.utils.types import Host
from linux_mcp_server.utils.types import LOCALHOST


def make_tool(func):
    """Register `func` as a tool, for its signature only - nothing ever calls it.

    Hence the `pragma: no cover` on the bodies below.
    """

    return Tool.from_function(func)


def test_host_argument_is_used():
    async def with_host(host: Host) -> str:
        return host  # pragma: no cover

    assert resolve_target_host(make_tool(with_host), {"host": "web1.example.com"}) == "web1.example.com"
    assert resolve_target_host(make_tool(with_host), {"host": LOCALHOST}) == LOCALHOST


@pytest.mark.parametrize("arguments", [{}, {"host": None}, {"host": ""}, {"host": 42}, {"host": ["a", "b"]}])
def test_host_argument_must_be_a_non_empty_string(arguments):
    """Middleware runs before validation, so the schema guarantees nothing here."""

    async def with_host(host: Host) -> str:
        return host  # pragma: no cover

    with pytest.raises(ToolError, match="'host' parameter is required"):
        resolve_target_host(make_tool(with_host), arguments)


def test_resolver_is_used_when_there_is_no_host_argument():
    @target_host_from(lambda arguments: f"{arguments['id']}.example.com")
    async def with_resolver(id: str) -> str:
        return id  # pragma: no cover

    assert resolve_target_host(make_tool(with_resolver), {"id": "web1"}) == "web1.example.com"


def test_tool_without_host_or_resolver_is_a_bug():
    async def without_host() -> str:
        return "no host here"  # pragma: no cover

    with pytest.raises(RuntimeError, match="no 'host' parameter and no @target_host_from"):
        resolve_target_host(make_tool(without_host), {})
