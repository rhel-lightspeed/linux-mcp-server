"""Tests for the core MCP server."""

import pytest
from linux_mcp_server.server import mcp


class TestLinuxMCPServer:
    """Test the core server functionality."""

    def test_server_initialization(self):
        """Test that the FastMCP server is initialized."""
        assert mcp is not None
        assert mcp.name == "linux-diagnostics"

    def test_server_has_list_tools_method(self):
        """Test that the server has list_tools method."""
        assert hasattr(mcp, "list_tools")
        assert callable(mcp.list_tools)

    @pytest.mark.asyncio
    async def test_list_tools_returns_tools(self):
        """Test that list_tools returns a list of tools."""
        tools = await mcp.list_tools()

        # Should return a list
        assert isinstance(tools, list)
        assert len(tools) > 0

    @pytest.mark.asyncio
    async def test_server_has_basic_tools(self):
        """Test that basic diagnostic tools are registered."""
        tools = await mcp.list_tools()
        tool_names = [tool.name for tool in tools]

        # Should have at least the basic tools
        assert "get_system_info" in tool_names
        assert "list_services" in tool_names
        assert "list_processes" in tool_names
        assert "get_network_interfaces" in tool_names
        assert "list_block_devices" in tool_names

    @pytest.mark.asyncio
    async def test_all_tools_have_correct_count(self):
        """Test that all 20 tools are registered."""
        tools = await mcp.list_tools()
        # We have 20 tools total (5 system info + 3 service + 2 process +
        # 3 log + 3 network + 4 storage)
        assert len(tools) == 20
