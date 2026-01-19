"""Verify tool schemas contain expected metadata for LLM guidance."""

import pytest

from linux_mcp_server.server import mcp


@pytest.fixture(scope="module")
async def mcp_tools() -> dict:
    """Fetch all MCP tools using the public API."""
    return await mcp.get_tools()


@pytest.fixture
def tool_properties(mcp_tools: dict):
    """Get the properties dict for a tool's parameters schema."""

    def _tool_properties(tool_name: str) -> dict:
        tool = mcp_tools.get(tool_name)
        if tool is None:
            raise ValueError(f"Tool '{tool_name}' not found")
        return tool.parameters.get("properties", {})

    return _tool_properties


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
    def test_parameter_has_examples(self, tool_name: str, param_name: str, tool_properties) -> None:
        props = tool_properties(tool_name)

        assert param_name in props, f"Parameter '{param_name}' not found in {tool_name}"
        assert "examples" in props[param_name], f"Parameter '{param_name}' in {tool_name} missing examples"
        assert len(props[param_name]["examples"]) > 0, f"Parameter '{param_name}' in {tool_name} has empty examples"
