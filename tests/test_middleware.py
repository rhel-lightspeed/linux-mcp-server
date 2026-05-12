import importlib

import pytest

from mcp import ServerSession
from mcp.types import InitializeRequestParams
from mcp.types import Tool


# Workaround: with python-3.10, mocker.patch("linux_mcp_server.server.X")
# doesn't work because it finds the imported server function rather than the module.
server_module = importlib.import_module("linux_mcp_server.server")


class TestUseMcpAppForClient:
    @pytest.mark.parametrize("config_value,expected", [(True, True), (False, False)])
    def test_config_override(self, mocker, config_value, expected):
        # Test CONFIG.use_mcp_apps override
        mocker.patch.object(server_module, "CONFIG", use_mcp_apps=config_value)
        result = server_module._use_mcp_app_for_client(mocker.Mock(spec=InitializeRequestParams))
        assert result is expected

    @pytest.mark.parametrize(
        "extensions,expected",
        [
            ({server_module.MCP_UI_EXTENSION: {"mimeTypes": [server_module.MCP_APP_MIME_TYPE]}}, True),
            ({"other-extension": {}}, False),
        ],
    )
    def test_detection(self, mocker, extensions, expected):
        # Test mcp-app detection from client capabilities
        mocker.patch.object(server_module, "CONFIG", use_mcp_apps=None)
        capabilities = mocker.Mock()
        capabilities.extensions = extensions
        params = mocker.Mock(spec=InitializeRequestParams)
        params.capabilities = capabilities
        result = server_module._use_mcp_app_for_client(params)
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
        mocker.patch.object(server_module, "_use_mcp_app_for_client", return_value=False)

        mock_session = mocker.Mock(spec=ServerSession)
        mock_session._init_options = mocker.Mock()
        mock_session._init_options.instructions = "Use run_script_with_confirmation for changes"
        mock_context.fastmcp_context.session = mock_session

        await middleware.on_initialize(mock_context, mocker.AsyncMock(return_value=mocker.Mock()))

        assert mock_session._init_options.instructions == "Use run_script_with_confirmation for changes"

    async def test_modifies_instructions(self, middleware, mock_context, mocker):
        mocker.patch.object(server_module, "_use_mcp_app_for_client", return_value=True)

        mock_session = mocker.Mock(spec=ServerSession)
        mock_session._init_options = mocker.Mock()
        mock_session._init_options.instructions = "Use run_script_with_confirmation for changes"
        mock_context.fastmcp_context.session = mock_session

        await middleware.on_initialize(mock_context, mocker.AsyncMock(return_value=mocker.Mock()))

        assert mock_session._init_options.instructions == "Use run_script_interactive for changes"


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
        mocker.patch.object(server_module, "_use_mcp_app_for_client", return_value=True)

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
        mocker.patch.object(server_module, "_use_mcp_app_for_client", return_value=False)

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


class TestAuthorizationMiddlewareOnCallTool:
    @pytest.fixture
    def middleware(self):
        return server_module.AuthorizationMiddleware()

    @pytest.fixture
    def mock_context(self, mocker):
        # Create a mock MiddlewareContext for tool calls
        context = mocker.Mock()
        context.message = mocker.Mock()
        context.message.name = "test_tool"
        context.message.arguments = {}

        # Mock FastMCP context with get_tool
        fastmcp_context = mocker.Mock()
        tool = mocker.Mock()
        tool.tags = set()
        fastmcp_context.fastmcp.get_tool = mocker.AsyncMock(return_value=tool)
        context.fastmcp_context = fastmcp_context

        # Mock user_info
        context.user_info = None

        return context

    async def test_no_auth_stdio_transport_allows(self, middleware, mock_context, mocker):
        # No auth configured, stdio transport with no policy, should allow
        mocker.patch.object(
            server_module, "CONFIG", auth=None, transport=server_module.Transport.stdio, policy_path=None
        )

        call_next = mocker.AsyncMock(return_value="result")
        result = await middleware.on_call_tool(mock_context, call_next)

        assert result == "result"
        call_next.assert_called_once()

    async def test_no_auth_http_with_all_users(self, middleware, mock_context, mocker):
        # No auth, HTTP, but policy allows all_users
        mocker.patch.object(server_module, "CONFIG", auth=None, transport=server_module.Transport.http)
        mocker.patch(
            "linux_mcp_server.server.evaluate_policy",
            return_value=(server_module.PolicyAction.LOCAL, None),
        )

        call_next = mocker.AsyncMock(return_value="result")
        result = await middleware.on_call_tool(mock_context, call_next)

        assert result == "result"

    async def test_with_auth_policy_deny(self, middleware, mock_context, mocker):
        # Auth configured, policy returns DENY
        mock_context.user_info = {"email": "user@example.com"}
        mocker.patch.object(server_module, "CONFIG", auth=mocker.Mock(), transport=server_module.Transport.http)

        # Mock get_access_token to return authenticated user
        mock_access_token = mocker.Mock()
        mock_access_token.claims = {"email": "user@example.com"}
        mocker.patch("linux_mcp_server.server.get_access_token", return_value=mock_access_token)

        mocker.patch(
            "linux_mcp_server.server.evaluate_policy",
            return_value=(server_module.PolicyAction.DENY, None),
        )

        call_next = mocker.AsyncMock()

        with pytest.raises(ValueError, match="Authorization denied"):
            await middleware.on_call_tool(mock_context, call_next)

    async def test_with_auth_policy_local(self, middleware, mock_context, mocker):
        # Auth configured, policy allows LOCAL action
        mock_context.user_info = {"email": "user@example.com"}
        mocker.patch.object(server_module, "CONFIG", auth=mocker.Mock(), transport=server_module.Transport.http)

        # Mock get_access_token to return authenticated user
        mock_access_token = mocker.Mock()
        mock_access_token.claims = {"email": "user@example.com"}
        mocker.patch("linux_mcp_server.server.get_access_token", return_value=mock_access_token)

        mocker.patch(
            "linux_mcp_server.server.evaluate_policy",
            return_value=(server_module.PolicyAction.LOCAL, None),
        )

        call_next = mocker.AsyncMock(return_value="result")
        result = await middleware.on_call_tool(mock_context, call_next)

        assert result == "result"

    async def test_ssh_default_with_no_host_raises(self, middleware, mock_context, mocker):
        # SSH_DEFAULT action but no host in arguments
        mock_context.user_info = {"email": "user@example.com"}
        mocker.patch.object(server_module, "CONFIG", auth=mocker.Mock(), transport=server_module.Transport.http)

        # Mock get_access_token to return authenticated user
        mock_access_token = mocker.Mock()
        mock_access_token.claims = {"email": "user@example.com"}
        mocker.patch("linux_mcp_server.server.get_access_token", return_value=mock_access_token)

        mocker.patch(
            "linux_mcp_server.server.evaluate_policy",
            return_value=(server_module.PolicyAction.SSH_DEFAULT, None),
        )

        call_next = mocker.AsyncMock()

        with pytest.raises(RuntimeError, match="Policy validation error: Cannot use SSH action"):
            await middleware.on_call_tool(mock_context, call_next)

    async def test_ssh_key_with_config_allows(self, middleware, mock_context, mocker):
        # SSH_KEY action with config, should allow and log
        mock_context.message.arguments = {"host": "db-server"}
        mock_context.user_info = {"email": "admin@example.com"}

        ssh_key_config = mocker.Mock()
        ssh_key_config.path = "/keys/db-key"
        ssh_key_config.user = "db-admin"

        mocker.patch.object(server_module, "CONFIG", auth=mocker.Mock(), transport=server_module.Transport.http)

        # Mock get_access_token to return authenticated user
        mock_access_token = mocker.Mock()
        mock_access_token.claims = {"email": "admin@example.com"}
        mocker.patch("linux_mcp_server.server.get_access_token", return_value=mock_access_token)

        mocker.patch(
            "linux_mcp_server.server.evaluate_policy",
            return_value=(server_module.PolicyAction.SSH_KEY, ssh_key_config),
        )
        mock_logger = mocker.patch.object(server_module, "logger")

        call_next = mocker.AsyncMock(return_value="result")
        result = await middleware.on_call_tool(mock_context, call_next)

        assert result == "result"
        # Verify SSH key override was logged
        mock_logger.debug.assert_called()

    async def test_local_action_with_host_raises(self, middleware, mock_context, mocker):
        # LOCAL action but host is specified
        mock_context.message.arguments = {"host": "remote-host"}
        mock_context.user_info = {"email": "user@example.com"}
        mocker.patch.object(server_module, "CONFIG", auth=mocker.Mock(), transport=server_module.Transport.http)

        # Mock get_access_token to return authenticated user
        mock_access_token = mocker.Mock()
        mock_access_token.claims = {"email": "user@example.com"}
        mocker.patch("linux_mcp_server.server.get_access_token", return_value=mock_access_token)

        mocker.patch(
            "linux_mcp_server.server.evaluate_policy",
            return_value=(server_module.PolicyAction.LOCAL, None),
        )

        call_next = mocker.AsyncMock()

        with pytest.raises(RuntimeError, match="Policy validation error: Cannot use local action for remote host"):
            await middleware.on_call_tool(mock_context, call_next)
