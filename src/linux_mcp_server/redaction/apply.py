"""Redact sensitive data in tool return values before FastMCP renders them."""

from typing import Any

import pydantic_core

from fastmcp.tools import ToolResult as RenderedToolResult

from linux_mcp_server.redaction.engine import RedactionEngine
from linux_mcp_server.tool_result import ToolResult


def redact_tool_output(value: Any, engine: RedactionEngine | None) -> Any:
    """Scan everything a tool returned, and hand back a value FastMCP can render.

    Whatever the tool produced is reduced to JSON before it is scanned, so that there
    is a single document to look at rather than a tree of models, paths and containers
    whose types would have to be put back together afterwards. It is also the shape a
    future hook script would be handed.

    A tool that returned a ``ToolResult`` wrote its own text, so both halves are
    scanned and the pair is rendered here, once clean. Anything else is handed back as
    JSON data for FastMCP to render as it normally would - text and structured content
    then both come from the scanned document.

    With no engine there is nothing to scan, and a value FastMCP would have rendered
    itself is handed straight back. A ``ToolResult`` is still rendered here: it is a
    pair of halves to hand FastMCP separately, not data describing itself, so passing
    one along as it stands would render the container instead of what is in it.
    """
    if isinstance(value, ToolResult):
        return RenderedToolResult(
            content=value.content if engine is None else engine.redact(value.content),
            structured_content=_as_json(value.structured_content, engine),
        )

    if engine is None:
        return value

    return _as_json(value, engine)


def _as_json(value: Any, engine: RedactionEngine | None) -> Any:
    """Reduce a value to JSON, scanning the strings in it if there is an engine."""
    jsonable = pydantic_core.to_jsonable_python(value)

    return jsonable if engine is None else _redact(jsonable, engine)


def _redact(value: Any, engine: RedactionEngine) -> Any:
    """Replace the string leaves of a JSON document, keeping its shape.

    Keys are left alone: they are field names the tools chose, and rewriting one would
    rename a property the output schema requires.
    """
    if isinstance(value, str):
        return engine.redact(value)

    if isinstance(value, dict):
        return {key: _redact(item, engine) for key, item in value.items()}

    if isinstance(value, list):
        return [_redact(item, engine) for item in value]

    # Numbers, booleans and None carry no text to scan.
    return value
