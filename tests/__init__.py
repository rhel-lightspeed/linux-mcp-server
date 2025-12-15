"""Tests for Linux MCP Server."""

from fastmcp.client.client import CallToolResult


def verify_result_structure(result: CallToolResult) -> str:
    """Verify standard MCP tool result structure and extract output text.

    FastMCP 2.x Client.call_tool returns a CallToolResult object with
    content as a list of TextContent objects.

    Args:
        result: The CallToolResult from a Client.call_tool() call

    Returns:
        The text content from the first item in the result list
    """
    assert isinstance(result, CallToolResult)
    assert result.content is not None
    assert len(result.content) > 0
    return result.content[0].text
