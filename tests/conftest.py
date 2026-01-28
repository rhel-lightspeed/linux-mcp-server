import pytest

from fastmcp.client import Client

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.server import mcp


@pytest.fixture
async def mcp_client():
    async with Client(transport=mcp) as mcp_client:
        yield mcp_client


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
