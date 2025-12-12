"""Tests for Linux MCP Server."""

from typing import TYPE_CHECKING


# TYPE_CHECKING is False at runtime but True for type checkers (pyright, mypy).
# This allows type hints without runtime import overhead or circular import issues.
if TYPE_CHECKING:  # pragma: no cover
    from linux_mcp_server.tools.storage import NodeEntry


def verify_result_structure(result) -> str:
    """Verify standard MCP tool result structure and extract output text.

    Args:
        result: The result tuple from an MCP tool call

    Returns:
        The text content from the first item in the result list
    """
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], list)
    assert len(result[0]) >= 1
    return result[0][0].text


def verify_node_entries(result, expected: list["NodeEntry"]) -> list["NodeEntry"]:
    """Verify structured result and extract NodeEntry objects.

    Args:
        result: The result tuple from an MCP tool call
        expected: The expected list of NodeEntry objects

    Returns:
        The list of NodeEntry objects from the result
    """
    from linux_mcp_server.tools.storage import NodeEntry

    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[1], dict)
    assert "result" in result[1]
    assert isinstance(result[1]["result"], list)
    actual = [NodeEntry(**entry) for entry in result[1]["result"]]
    assert actual == expected
    return actual
