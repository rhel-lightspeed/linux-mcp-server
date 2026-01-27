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
    """Test the main() function with different transport configurations."""

    def test_main_default_parameters(self, mocker):
        """Test main() with default parameters."""
        mock_run = mocker.patch.object(mcp, "run")

        main()

        mock_run.assert_called_once_with(
            transport="stdio",
            show_banner=False,
        )

    def test_main_stdio_transport(self, mocker):
        """Test main() with stdio transport."""
        mock_run = mocker.patch.object(mcp, "run")

        main(transport="stdio", show_banner=True)

        mock_run.assert_called_once_with(
            transport="stdio",
            show_banner=True,
        )

    def test_main_sse_transport(self, mocker):
        """Test main() with SSE transport."""
        mock_run = mocker.patch.object(mcp, "run")

        main(transport="sse", host="0.0.0.0", port=8080)

        mock_run.assert_called_once_with(
            transport="sse",
            show_banner=False,
            host="0.0.0.0",
            port=8080,
        )

    def test_main_http_transport(self, mocker):
        """Test main() with HTTP transport."""
        mock_run = mocker.patch.object(mcp, "run")

        main(
            transport="http",
            host="127.0.0.1",
            port=3000,
            path="/api/mcp",
            log_level="debug",
        )

        mock_run.assert_called_once_with(
            transport="http",
            show_banner=False,
            host="127.0.0.1",
            port=3000,
            path="/api/mcp",
            log_level="debug",
        )

    def test_main_streamable_http_transport(self, mocker):
        """Test main() with streamable-http transport."""
        mock_run = mocker.patch.object(mcp, "run")

        main(transport="streamable-http", show_banner=True, port=9000)

        mock_run.assert_called_once_with(
            transport="streamable-http",
            show_banner=True,
            port=9000,
        )

    def test_main_with_arbitrary_kwargs(self, mocker):
        """Test main() passes through arbitrary transport kwargs."""
        mock_run = mocker.patch.object(mcp, "run")

        main(
            transport="sse",
            custom_param="value",
            another_param=123,
        )

        mock_run.assert_called_once_with(
            transport="sse",
            show_banner=False,
            custom_param="value",
            another_param=123,
        )
