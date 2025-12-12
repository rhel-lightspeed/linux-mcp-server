"""Tests for Linux MCP Server."""

from typing import TYPE_CHECKING


# TYPE_CHECKING is False at runtime but True for type checkers (pyright, mypy).
# This allows type hints without runtime import overhead or circular import issues.
if TYPE_CHECKING:  # pragma: no cover
    from linux_mcp_server.utils.types import NodeEntry


def verify_result_structure(result) -> str:
    """Verify standard MCP tool result structure and extract output text.

    All MCP tools return a tuple of (list[TextContent], dict). This function
    validates that structure and extracts the text content for assertions.

    Args:
        result: The result tuple from an MCP tool call

    Returns:
        The text content from the first item in the result list
    """
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], list)
    return result[0][0].text


def assert_node_entries(result, expected: list["NodeEntry"]) -> None:  # pragma: no cover
    """Assert that result contains expected NodeEntry objects.

    Args:
        result: The result tuple from an MCP tool call
        expected: The expected list of NodeEntry objects
    """
    from linux_mcp_server.utils.types import NodeEntry

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[1], dict)
    assert "result" in result[1]
    assert isinstance(result[1]["result"], list)
    actual = [NodeEntry(**entry) for entry in result[1]["result"]]
    assert actual == expected
