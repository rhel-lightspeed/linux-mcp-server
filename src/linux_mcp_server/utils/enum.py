import sys

from enum import Enum


# StrEnum is available in Python 3.11+
if sys.version_info >= (3, 11):
    from enum import StrEnum as _StrEnumBase
else:
    _StrEnumBase = None  # type: ignore[assignment,misc]


class StringEnum(str, Enum):
    """String-based enum for Python < 3.11 compatibility."""

    def __str__(self) -> str:
        return self.value


# Use native StrEnum if available, otherwise use our StringEnum
StrEnum = _StrEnumBase if _StrEnumBase is not None else StringEnum  # type: ignore[assignment,misc]


class TransportType(StrEnum):  # type: ignore[misc,valid-type]
    """Transport protocol types for the MCP server."""

    STDIO = "stdio"
    HTTP = "http"
    STREAMABLE_HTTP = "streamable-http"
