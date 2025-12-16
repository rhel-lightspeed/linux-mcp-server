"""Tests for the core MCP server."""

from linux_mcp_server.server import mcp


class TestLinuxMCPServer:
    """Test the core server functionality."""

    def test_server_initialization(self):
        """Test that the FastMCP server is initialized."""
        assert mcp is not None
        assert mcp.name == "linux-diagnostics"

    async def test_list_tools_returns_tools(self, mcp_client):
        """Test that list_tools returns a list of tools."""
        tools = await mcp_client.list_tools()

        assert tools

    async def test_server_has_basic_tools(self, mcp_client):
        """Test that basic diagnostic tools are registered."""
        tools = await mcp_client.list_tools()
        tool_names = {tool.name for tool in tools}
        expected_tools = {
            "get_system_information",
            "list_services",
            "list_processes",
            "get_network_interfaces",
            "list_block_devices",
            "list_directories",
            "list_files",
        }

        assert tool_names.issuperset(expected_tools), "Missing basic tools"
