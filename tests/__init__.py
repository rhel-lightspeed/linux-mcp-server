"""Tests for Linux MCP Server."""


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
