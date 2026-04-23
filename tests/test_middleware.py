"""Tests for middleware in server.py"""

import importlib

import pytest

from mcp import ServerSession
from mcp.types import InitializeRequestParams
from mcp.types import Tool

from linux_mcp_server.mcp_app import MCP_APP_MIME_TYPE
from linux_mcp_server.mcp_app import MCP_UI_EXTENSION


# Workaround: with python-3.10, mocker.patch("linux_mcp_server.server.X")
# doesn't work because it finds the imported server function rather than the module.
server_module = importlib.import_module("linux_mcp_server.server")
mcp_app_module = importlib.import_module("linux_mcp_server.mcp_app")


class TestUseMcpAppForClient:
    @pytest.mark.parametrize("config_value,expected", [(True, True), (False, False)])
    def test_config_override(self, mocker, config_value, expected):
        # Test CONFIG.use_mcp_apps override
        mocker.patch.object(mcp_app_module, "CONFIG", use_mcp_apps=config_value)
        result = server_module.use_mcp_app_for_client(mocker.Mock(spec=InitializeRequestParams))
        assert result is expected

    @pytest.mark.parametrize(
        "extensions,expected",
        [
            ({MCP_UI_EXTENSION: {"mimeTypes": [MCP_APP_MIME_TYPE]}}, True),
            ({"other-extension": {}}, False),
        ],
    )
    def test_detection(self, mocker, extensions, expected):
        # Test mcp-app detection from client capabilities
        mocker.patch.object(mcp_app_module, "CONFIG", use_mcp_apps=None)
        capabilities = mocker.Mock()
        capabilities.extensions = extensions
        params = mocker.Mock(spec=InitializeRequestParams)
        params.capabilities = capabilities
        result = server_module.use_mcp_app_for_client(params)
        assert result is expected


class TestDynamicDiscoveryMiddlewareOnInitialize:
    @pytest.fixture
    def middleware(self):
        return server_module.DynamicDiscoveryMiddleware()

    @pytest.fixture
    def mock_context(self, mocker):
        # Create a mock MiddlewareContext with message.params
        context = mocker.Mock()
        context.message = mocker.Mock()
        context.message.params = mocker.Mock(spec=InitializeRequestParams)
        context.fastmcp_context = mocker.Mock()
        return context

    async def test_skips_modification_when_disabled(self, middleware, mock_context, mocker):
        # Test that instructions are not modified when mcp-apps is disabled
        mocker.patch.object(server_module, "use_mcp_app_for_client", return_value=False)

        mock_session = mocker.Mock(spec=ServerSession)
        mock_session._init_options = mocker.Mock()
        mock_session._init_options.instructions = "Use run_script_with_confirmation for changes"
        mock_context.fastmcp_context._session = mock_session

        await middleware.on_initialize(mock_context, mocker.AsyncMock(return_value=mocker.Mock()))

        assert mock_session._init_options.instructions == "Use run_script_with_confirmation for changes"

    async def test_modifies_instructions_fastmcp_3x(self, middleware, mock_context, mocker):
        # Test instruction modification with FastMCP 3.x
        mocker.patch.object(server_module, "use_mcp_app_for_client", return_value=True)

        mock_session = mocker.Mock(spec=ServerSession)
        mock_session._init_options = mocker.Mock()
        mock_session._init_options.instructions = "Use run_script_with_confirmation for changes"
        mock_context.fastmcp_context._session = mock_session

        await middleware.on_initialize(mock_context, mocker.AsyncMock(return_value=mocker.Mock()))

        assert mock_session._init_options.instructions == "Use run_script_interactive for changes"

    async def test_modifies_instructions_fastmcp_2x(self, middleware, mock_context, mocker):
        # Test instruction modification with FastMCP 2.x via closure extraction
        mocker.patch.object(server_module, "use_mcp_app_for_client", return_value=True)
        mock_context.fastmcp_context._session = None

        mock_session = mocker.Mock(spec=ServerSession)
        mock_session._init_options = mocker.Mock()
        mock_session._init_options.instructions = "Use run_script_with_confirmation for changes"

        def make_call_next(session_obj):
            self = session_obj

            async def call_next_func(_ctx):
                _ = self
                return mocker.Mock()

            return call_next_func

        await middleware.on_initialize(mock_context, make_call_next(mock_session))

        assert mock_session._init_options.instructions == "Use run_script_interactive for changes"

    async def test_handles_extraction_failure(self, middleware, mock_context, mocker):
        # Test graceful handling when session extraction fails
        mocker.patch.object(server_module, "use_mcp_app_for_client", return_value=True)
        mock_logger = mocker.patch.object(server_module, "logger")

        mock_context.fastmcp_context._session = None
        call_next = mocker.AsyncMock(return_value=mocker.Mock())
        call_next.__code__ = mocker.Mock()
        call_next.__code__.co_freevars = []
        call_next.__closure__ = None

        await middleware.on_initialize(mock_context, call_next)

        mock_logger.warning.assert_called_once()


class TestDynamicDiscoveryMiddlewareOnListTools:
    @pytest.fixture
    def middleware(self):
        return server_module.DynamicDiscoveryMiddleware()

    @pytest.fixture
    def mock_context(self, mocker):
        # Create a mock context with full request_context chain
        context = mocker.Mock()
        fastmcp_context = mocker.Mock()
        request_ctx = mocker.Mock()
        session = mocker.Mock()
        client_params = mocker.Mock(spec=InitializeRequestParams)

        session.client_params = client_params
        request_ctx.session = session
        fastmcp_context.request_context = request_ctx
        context.fastmcp_context = fastmcp_context

        return context

    def _make_tool(self, mocker, name: str, tags: set[str] | None = None) -> Tool:
        # Helper to create a Tool with tags
        tool = mocker.Mock(spec=Tool)
        tool.name = name
        tool.tags = tags or set()  # type: ignore
        return tool

    async def test_filters_when_mcp_apps_enabled(self, middleware, mock_context, mocker):
        # Test that hidden_from_model and mcp_apps_exclude are filtered when enabled
        mocker.patch.object(server_module, "use_mcp_app_for_client", return_value=True)

        tools = [
            self._make_tool(mocker, "regular", set()),
            self._make_tool(mocker, "hidden", {"hidden_from_model"}),
            self._make_tool(mocker, "excluded", {"mcp_apps_exclude"}),
            self._make_tool(mocker, "app_only", {"mcp_apps_only"}),
        ]

        result = await middleware.on_list_tools(mock_context, mocker.AsyncMock(return_value=tools))

        assert len(result) == 2
        result_names = {tool.name for tool in result}
        assert result_names == {"regular", "app_only"}

    async def test_filters_when_mcp_apps_disabled(self, middleware, mock_context, mocker):
        # Test that hidden_from_model and mcp_apps_only are filtered when disabled
        mocker.patch.object(server_module, "use_mcp_app_for_client", return_value=False)

        tools = [
            self._make_tool(mocker, "regular", set()),
            self._make_tool(mocker, "hidden", {"hidden_from_model"}),
            self._make_tool(mocker, "excluded", {"mcp_apps_exclude"}),
            self._make_tool(mocker, "app_only", {"mcp_apps_only"}),
        ]

        result = await middleware.on_list_tools(mock_context, mocker.AsyncMock(return_value=tools))

        assert len(result) == 2
        result_names = {tool.name for tool in result}
        assert result_names == {"regular", "excluded"}
