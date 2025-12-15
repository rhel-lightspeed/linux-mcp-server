import pytest

from linux_mcp_server.audit import log_tool_call


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
def mock_execute_command_for(mocker):
    """Factory fixture for mocking execute_command in any module.

    Returns a callable that creates mocks for execute_command in the specified module.
    Uses autospec=True to verify arguments match the real function signature.

    Usage:
        @pytest.fixture
        def mock_execute_command(mock_execute_command_for):
            return mock_execute_command_for("linux_mcp_server.tools.mymodule")

        async def test_something(mock_execute_command):
            mock_execute_command.return_value = (0, "output", "")
            # ... test code ...
            mock_execute_command.assert_called_once()
    """

    def _mock(module: str):
        return mocker.patch(
            f"{module}.execute_command",
            autospec=True,
        )

    return _mock
