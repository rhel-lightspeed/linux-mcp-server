"""Verify tool schemas contain expected metadata for LLM guidance."""

import pytest

from linux_mcp_server.server import mcp


class TestToolSchemaExamples:
    """Verify parameters have examples for LLM guidance."""

    @pytest.mark.parametrize(
        ("tool_name", "param_name"),
        [
            ("get_journal_logs", "unit"),
            ("get_journal_logs", "priority"),
            ("get_journal_logs", "since"),
            ("read_log_file", "log_path"),
            ("get_service_status", "service_name"),
            ("get_service_logs", "service_name"),
            ("get_process_info", "pid"),
            ("list_directories", "path"),
            ("list_files", "path"),
            ("read_file", "path"),
        ],
    )
    async def test_parameter_has_examples(self, tool_name: str, param_name: str) -> None:
        tool = await mcp.get_tool(tool_name)
        assert tool
        props = tool.parameters.get("properties", {})

        assert param_name in props, f"Parameter '{param_name}' not found in {tool_name}"
        assert "examples" in props[param_name], f"Parameter '{param_name}' in {tool_name} missing examples"
        assert len(props[param_name]["examples"]) > 0, f"Parameter '{param_name}' in {tool_name} has empty examples"


def test_log_entries_serialization_schema_no_path_format() -> None:
    """Verify that LogEntries serialization schema does not contain 'format': 'path' for unit or path."""
    from linux_mcp_server.models import LogEntries

    schema = LogEntries.model_json_schema(mode="serialization")
    for field_name in ("unit", "path"):
        field_schema = schema.get("properties", {}).get(field_name, {})
        # Verify it is not a direct 'format': 'path'
        assert field_schema.get("format") != "path", f"Field '{field_name}' has format: 'path'"
        # Verify it is not inside anyOf
        for subschema in field_schema.get("anyOf", []):
            assert subschema.get("format") != "path", f"Field '{field_name}' has subschema with format: 'path'"
