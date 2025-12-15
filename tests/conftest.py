"""Shared pytest fixtures for Linux MCP Server tests.

Testing Strategy
----------------
This test suite uses two complementary approaches for testing MCP tools:

1. **Protocol Testing** (via `mcp_client` fixture):
   Use `await mcp_client.call_tool("tool_name", params)` to test the full MCP
   protocol stack, including serialization, validation, and the FastMCP framework.
   This is integration-style testing that verifies tools work correctly when
   called by real MCP clients.

2. **Direct Function Testing** (via `.fn()` attribute):
   Use `await tool_function.fn(param=value)` to call the underlying function
   directly, bypassing the MCP protocol layer. This is unit-style testing that
   allows faster execution and more granular control over inputs.

When to use each:
- Use `mcp_client` for testing tool registration, parameter validation, and
  end-to-end behavior as MCP clients would experience it.
- Use `.fn()` for testing edge cases, error handling, and scenarios where
  you need to bypass MCP's parameter processing.
"""

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
