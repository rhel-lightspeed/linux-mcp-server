import json

from datetime import datetime

import pytest

from pydantic import ValidationError

from linux_mcp_server.models import LogEntries
from linux_mcp_server.models import NodeEntry
from linux_mcp_server.models import StorageNodes


def test_log_entries_null_value_serialization():
    """Assert that null values are properly serialized."""

    log_entry = LogEntries(entries=["log"])
    model = log_entry.model_dump()

    assert model["unit"] is None
    assert model["path"] is None


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-01-01T00:00:00.499999+05:45", "2026-01-01T00:00:00+05:45"),
        ("2026-01-01T00:00:00.500000+05:45", "2026-01-01T00:00:00+05:45"),
        ("2025-12-31T23:59:59.999999-04:00", "2025-12-31T23:59:59-04:00"),
        ("1969-12-31T23:59:59.600000+00:00", "1969-12-31T23:59:59Z"),
    ],
)
def test_node_modified_truncation(timestamp: str, expected: str) -> None:
    """Drop fractional seconds in JSON while retaining them on the model."""
    modified = datetime.fromisoformat(timestamp)
    node = NodeEntry(name="alpha", modified=modified)
    assert json.loads(node.model_dump_json()) == {"name": "alpha", "modified": expected}
    assert node.modified == modified


def test_node_omits_missing_metadata() -> None:
    nodes = StorageNodes(nodes=[NodeEntry(name="alpha")])
    expected = {"nodes": [{"name": "alpha"}], "total": 1}
    assert nodes.model_dump() == expected
    assert json.loads(nodes.model_dump_json()) == expected


def test_node_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        NodeEntry(name="alpha", modified=datetime(2026, 1, 1))


def test_node_preserves_zero_metadata() -> None:
    """Real zero sizes and epoch timestamps must not be omitted."""
    node = NodeEntry(name="empty", size=0, modified=datetime.fromisoformat("1970-01-01T00:00:00+00:00"))
    assert json.loads(node.model_dump_json()) == {"name": "empty", "size": 0, "modified": "1970-01-01T00:00:00Z"}
