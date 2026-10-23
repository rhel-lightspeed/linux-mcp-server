"""Redact sensitive data in tool return values before FastMCP renders them."""

from pathlib import Path
from typing import Any

from fastmcp.tools import ToolResult
from mcp.types import TextContent
from pydantic import BaseModel

from linux_mcp_server.redaction.engine import RedactionEngine


def redact_tool_output(value: Any, engine: RedactionEngine) -> Any:
    """Redact strings in a tool's return value, preserving type and structure.

    Args:
        value: Tool return value (string, model, dict, list, or ToolResult)
        engine: Redaction engine with active rules

    Returns:
        Value with strings redacted. Models/ToolResults edited in place, containers rebuilt.
    """
    if isinstance(value, ToolResult):
        return _redact_tool_result(value, engine)
    return _redact(value, engine)


def _redact_tool_result(result: ToolResult, engine: RedactionEngine) -> ToolResult:
    """Redact a ToolResult, rebuilding derived text from redacted structure.

    Auto-generated JSON text is discarded and re-rendered from the redacted structure
    to avoid JSON escaping hiding secrets. Explicit text is scanned as-is.
    """
    if result.structured_content is None:
        _redact_text_blocks(result, engine)
        return result

    # Ask FastMCP what it would render from this structure. Matching content came from
    # that rendering, so it can be produced again once the structure is clean.
    derived = ToolResult(structured_content=result.structured_content).content == result.content

    result.structured_content = _redact(result.structured_content, engine)

    if derived:
        result.content = ToolResult(structured_content=result.structured_content).content
    else:
        _redact_text_blocks(result, engine)

    return result


def _redact_text_blocks(result: ToolResult, engine: RedactionEngine) -> None:
    """Scan each text block the tool supplied, leaving other block types alone."""
    for block in result.content:
        if isinstance(block, TextContent):
            block.text = engine.redact(block.text)


def _redact(value: Any, engine: RedactionEngine) -> Any:
    """Replace the string leaves of a value, descending into models and containers."""
    if isinstance(value, str):
        return engine.redact(value)

    # A path is free-form text that reaches the model as a string, so it is scanned as
    # one and handed back as a path: the field keeps the type it declared.
    if isinstance(value, Path):
        return type(value)(engine.redact(str(value)))

    if isinstance(value, BaseModel):
        for name in type(value).model_fields:
            setattr(value, name, _redact(getattr(value, name), engine))
        return value

    if isinstance(value, dict):
        return {key: _redact(item, engine) for key, item in value.items()}

    if isinstance(value, tuple):
        return tuple(_redact(item, engine) for item in value)

    if isinstance(value, list):
        return [_redact(item, engine) for item in value]

    # Numbers, booleans, None and datetimes carry no text to scan.
    return value
