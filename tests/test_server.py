"""Tests for the core MCP server."""

from linux_mcp_server.server import mcp


class TestLinuxMCPServer:
    """Test the core server functionality."""

    def test_server_initialization(self):
        """Test that the FastMCP server is initialized."""
        assert mcp is not None
        assert mcp.name == "linux-diagnostics"

    def test_server_has_get_tools_method(self):
        """Test that the server has get_tools method."""
        assert hasattr(mcp, "get_tools")
        assert callable(mcp.get_tools)

    async def test_get_tools_returns_tools(self):
        """Test that get_tools returns a list of tools."""
        tools = await mcp.get_tools()

        # Should return a list
        assert isinstance(tools, list)
        assert len(tools) > 0

    async def test_server_has_basic_tools(self):
        """Test that basic diagnostic tools are registered."""
        tools = await mcp.get_tools()
        tool_names = [tool.name for tool in tools]

        # Should have at least the basic tools
        assert "get_system_information" in tool_names
        assert "list_services" in tool_names
        assert "list_processes" in tool_names
        assert "get_network_interfaces" in tool_names
        assert "list_block_devices" in tool_names
        assert "list_directories" in tool_names
        assert "list_files" in tool_names

    async def test_all_tools_have_correct_count(self):
        """Test that all 20 tools are registered."""
        tools = await mcp.get_tools()
        assert len(tools) == 20
