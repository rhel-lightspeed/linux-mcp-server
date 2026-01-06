import pytest

from fastmcp.client import Client
from loguru import logger

from linux_mcp_server.audit import log_tool_call
from linux_mcp_server.server import mcp


class LoguruCapture:
    """Capture loguru log records for testing."""

    def __init__(self):
        self.records: list = []

    def sink(self, message):
        """Sink function for loguru."""
        self.records.append(message.record)

    @property
    def text(self) -> str:
        """Get all captured log text as a single string."""
        return "\n".join(r["message"] for r in self.records)

    def clear(self):
        """Clear captured records."""
        self.records.clear()


@pytest.fixture
def loguru_caplog():
    """Fixture to capture loguru logs, similar to pytest's caplog.

    Usage:
        def test_something(loguru_caplog):
            logger.info("test message")
            assert "test message" in loguru_caplog.text
            assert loguru_caplog.records[0]["extra"]["key"] == "value"
    """
    capture = LoguruCapture()
    handler_id = logger.add(capture.sink, format="{message}", level="DEBUG")
    yield capture
    logger.remove(handler_id)


@pytest.fixture(autouse=True)
def reset_loguru_for_tests():
    """Reset loguru handlers before each test for isolation."""
    # Remove any existing handlers from previous tests
    logger.remove()

    yield

    # Cleanup after test
    logger.remove()


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
