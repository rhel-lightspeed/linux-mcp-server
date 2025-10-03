"""Tests for the core MCP server."""

import pytest
from linux_mcp_server.server import LinuxMCPServer


class TestLinuxMCPServer:
    """Test the core server functionality."""

    def test_server_initialization(self):
        """Test that the server can be initialized."""
        server = LinuxMCPServer()
        assert server is not None
        assert server.name == "linux-diagnostics"

    def test_server_has_list_tools_capability(self):
        """Test that the server provides list_tools capability."""
        server = LinuxMCPServer()
        assert hasattr(server, 'list_tools')

    @pytest.mark.asyncio
    async def test_list_tools_returns_available_tools(self):
        """Test that list_tools returns the available diagnostic tools."""
        server = LinuxMCPServer()
        tools = await server.list_tools()
        
        # Should return a list
        assert isinstance(tools, list)
        
        # Should have at least the basic tools
        tool_names = [tool.name for tool in tools]
        assert "get_system_info" in tool_names
        assert "list_services" in tool_names
        assert "list_processes" in tool_names

    @pytest.mark.asyncio
    async def test_call_tool_with_invalid_name_raises_error(self):
        """Test that calling an invalid tool raises appropriate error."""
        server = LinuxMCPServer()
        
        with pytest.raises(ValueError, match="Unknown tool"):
            await server.call_tool("nonexistent_tool", {})

