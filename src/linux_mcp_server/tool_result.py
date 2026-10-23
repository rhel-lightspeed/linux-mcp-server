"""The result type for tools that need to control the text they return."""

from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Text and structured content for a tool to return, as the tool wrote them.

    Returning plain data from a tool is the normal case: the text the model sees is
    rendered from it. A tool returns this instead when the text has to say something
    different from the structured content - for instance when the structured half is
    addressed to an mcp-app rather than to the model.

    This deliberately isn't FastMCP's ``ToolResult``, which converts both halves as it
    is constructed. Redaction has to see what the tool actually produced, so the pair is
    carried as-is and converted once it has been scanned.
    """

    content: str
    structured_content: Any = None
