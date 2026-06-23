from linux_mcp_server.models import LogEntries


def test_log_entries_null_value_serialization():
    """Assert that null values are properly serialized."""

    log_entry = LogEntries(entries=["log"])
    model = log_entry.model_dump()

    assert model["unit"] is None
    assert model["path"] is None
