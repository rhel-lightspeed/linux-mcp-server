"""Tests for the core MCP server."""

from linux_mcp_server.server import main
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


class TestMainFunction:
    """Test the main() function."""

    def test_main_uses_config(self, mocker, monkeypatch):
        """Test that main() uses CONFIG for all settings."""
        mock_run = mocker.patch.object(mcp, "run")

        # Mock CONFIG to return specific values
        mock_config = mocker.patch("linux_mcp_server.server.CONFIG")
        mock_config.transport.value = "stdio"
        mock_config.transport_kwargs = {}

        main()

        mock_run.assert_called_once_with(
            transport="stdio",
            show_banner=False,
        )

    def test_main_with_http_transport(self, mocker):
        """Test main() with HTTP transport configuration."""
        mock_run = mocker.patch.object(mcp, "run")

        # Mock CONFIG for HTTP transport
        mock_config = mocker.patch("linux_mcp_server.server.CONFIG")
        mock_config.transport.value = "http"
        mock_config.transport_kwargs = {
            "host": "0.0.0.0",
            "port": 8080,
            "path": "/api/mcp",
            "log_level": "DEBUG",
        }

        main()

        mock_run.assert_called_once_with(
            transport="http",
            show_banner=False,
            host="0.0.0.0",
            port=8080,
            path="/api/mcp",
            log_level="DEBUG",
        )
