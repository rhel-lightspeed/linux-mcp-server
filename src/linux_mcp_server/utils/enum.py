from enum import Enum


try:
    from enum import StrEnum  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    StrEnum = None


class StringEnum(str, Enum):
    def __str__(self):
        return self.value


if StrEnum is None:
    StrEnum = StringEnum


class TransportType(StrEnum):
    """Transport protocol types for the MCP server."""

    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"
    STREAMABLE_HTTP = "streamable-http"
