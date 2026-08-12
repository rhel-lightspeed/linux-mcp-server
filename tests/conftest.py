import os

from contextlib import AsyncExitStack
from contextlib import contextmanager
from unittest.mock import patch


# Register script tools on the in-process MCP instance used by ``mcp_client``.
# Default CLI/config is FIXED-only; tests need validate_script / run_script / etc.
os.environ.setdefault("LINUX_MCP_TOOLSET", "both")
os.environ.setdefault("LINUX_MCP_GATEKEEPER__MODEL", "gemini-2.5-flash")
os.environ.setdefault("LINUX_MCP_GATEKEEPER__PROVIDER", "gemini")

import pytest

from fastmcp.client import Client
from mcp.types import Implementation
from mcp.types import InitializeRequest

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.config import CONFIG
from linux_mcp_server.config import Toolset
from linux_mcp_server.server import mcp


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    unset = {"container"}
    for var in unset:
        monkeypatch.delenv(var, raising=False)


@contextmanager
def _with_mcp_app_client():
    """Context manager that runs the body so that the first created FastMCP client
    in the body will have extended capabilities marking it as a mcp-app client.

    This requires a complicated dance to patch the InitializeRequest() constructor
    but unpatch it before the in-process server side deserializes the request.
    """
    OriginalInitializeRequest = InitializeRequest
    patcher = patch("mcp.types.InitializeRequest")

    def intercept_init_request(*args, **kwargs):
        # 3. SELF-DESTRUCT: Stop the patch immediately upon first call.
        # This restores the real class globally before the Server ever sees the request.
        patcher.stop()

        params = kwargs.get("params")
        if params and hasattr(params, "capabilities"):
            if not hasattr(params.capabilities, "extensions"):
                params.capabilities.extensions = {}
            params.capabilities.extensions["io.modelcontextprotocol/ui"] = {"mimeTypes": ["text/html;profile=mcp-app"]}

        return OriginalInitializeRequest(*args, **kwargs)

    mocked_class = patcher.start()
    mocked_class.side_effect = intercept_init_request

    try:
        yield
    finally:
        patcher.stop()


@pytest.fixture
async def setup_client(mocker):
    # The AsyncExitStack allows us to flexibly clean things up when the
    # test exits, even when we can't represent them as a with: stack
    # (in particular, we want to add the cleanups when setup_fn is
    # called, not when the fixture is called.)
    async with AsyncExitStack() as stack:
        is_setup = False

        async def setup_fn(
            *,
            toolset: Toolset = Toolset.FIXED,
            mcp_apps: bool = False,
            auto_initialize: bool = True,
            client_info: Implementation | None = None,
        ):
            nonlocal is_setup
            if is_setup:
                raise RuntimeError("setup_client can only be called once per test.")
            is_setup = True

            if mcp_apps:
                # Patch things so the client advertises mcp-app support
                stack.enter_context(_with_mcp_app_client())

            # Patch the toolset
            stack.enter_context(patch.object(CONFIG, "toolset", toolset))

            client = Client(transport=mcp, auto_initialize=auto_initialize, client_info=client_info)
            # Automatically connect to the client so that the caller
            # doesn't need a with: block - the client will be disconnected
            # via the AsyncExitStack when the test exits.
            return await stack.enter_async_context(client)

        yield setup_fn


@pytest.fixture
async def mcp_client(setup_client):
    yield await setup_client(toolset=Toolset.FIXED, mcp_apps=False)


@pytest.fixture
def decorated():
    @log_tool_call
    def list_services(*args, **kwargs):
        return args, kwargs

    return list_services


@pytest.fixture
def adecorated():
    @log_tool_call
    async def list_services(*args, **kwargs):
        return args, kwargs

    return list_services


@pytest.fixture
async def decorated_fail():
    @log_tool_call
    def list_services(*args, **kwargs):
        raise ValueError("Raised intentionally")

    return list_services


@pytest.fixture
async def adecorated_fail():
    @log_tool_call
    async def list_services(*args, **kwargs):
        raise ValueError("Raised intentionally")

    return list_services


@pytest.fixture
def mock_execute_with_fallback_for(mocker):
    """Factory fixture for mocking execute_with_fallback in any module.

    Returns a callable that creates mocks for execute_with_fallback in the specified module.
    Uses autospec=True to verify arguments match the real function signature.

    Usage:
        @pytest.fixture
        def mock_execute_with_fallback(mock_execute_with_fallback_for):
            return mock_execute_with_fallback_for("linux_mcp_server.commands")

        async def test_something(mock_execute_with_fallback):
            mock_execute_with_fallback.return_value = (0, "output", "")
            # ... test code ...
            mock_execute_with_fallback.assert_called_once()
    """

    def _mock(module: str):
        return mocker.patch(
            f"{module}.execute_with_fallback",
            autospec=True,
        )

    return _mock


@pytest.fixture
def mock_getuser(mocker):
    """Mock getpass.getuser to return 'testuser'."""
    return mocker.patch("getpass.getuser", return_value="testuser")


@pytest.fixture
def mock_execute_with_fallback(mock_execute_with_fallback_for):
    """Shared execute_with_fallback mock for linux_mcp_server.commands."""
    return mock_execute_with_fallback_for("linux_mcp_server.commands")
