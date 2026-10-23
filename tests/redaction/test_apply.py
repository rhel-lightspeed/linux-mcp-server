"""Tests for redacting the value a tool returns."""

import json
import re

from pathlib import Path

import pytest

from fastmcp.tools import ToolResult
from mcp.types import ImageContent
from mcp.types import TextContent

from linux_mcp_server.models import LogEntries
from linux_mcp_server.models import NodeEntry
from linux_mcp_server.models import StorageNodes
from linux_mcp_server.redaction.apply import redact_tool_output
from linux_mcp_server.redaction.engine import RedactionEngine
from linux_mcp_server.redaction.models import RedactionRule
from linux_mcp_server.redaction.models import RedactionRulesConfig


SECRET = "SECRET_ABC123"
PLACEHOLDER = "[REDACTED:custom:secret]"


@pytest.fixture
def engine() -> RedactionEngine:
    """An engine holding one predictable rule, so built-ins cannot interfere."""
    return RedactionEngine(
        RedactionRulesConfig(
            version=1,
            disable_rules=["builtin:*"],
            rules=[RedactionRule(name="secret", description="Test secret", match="SECRET_[A-Z0-9]+")],
        )
    )


class TestContainers:
    """Strings are found wherever they are nested, and containers keep their shape."""

    def test_a_bare_string_is_redacted(self, engine: RedactionEngine) -> None:
        assert redact_tool_output(f"token {SECRET} end", engine) == f"token {PLACEHOLDER} end"

    def test_dictionary_values_are_redacted_and_keys_kept(self, engine: RedactionEngine) -> None:
        assert redact_tool_output({SECRET: SECRET}, engine) == {SECRET: PLACEHOLDER}

    def test_nesting_is_followed_to_any_depth(self, engine: RedactionEngine) -> None:
        value = {"outer": {"inner": [{"deep": SECRET}]}}
        assert redact_tool_output(value, engine) == {"outer": {"inner": [{"deep": PLACEHOLDER}]}}

    def test_sequences_keep_their_type_and_order(self, engine: RedactionEngine) -> None:
        assert redact_tool_output([SECRET], engine) == [PLACEHOLDER]
        assert redact_tool_output((SECRET,), engine) == (PLACEHOLDER,)

    def test_non_text_values_are_returned_unchanged(self, engine: RedactionEngine) -> None:
        assert redact_tool_output(42, engine) == 42
        assert redact_tool_output(None, engine) is None


class TestModels:
    """Project models are edited in place, keeping their type and serialization."""

    def test_model_fields_are_redacted_and_the_type_is_kept(self, engine: RedactionEngine) -> None:
        entries = LogEntries(entries=[f"login {SECRET}", "clean"])
        result = redact_tool_output(entries, engine)

        assert result is entries
        assert result.entries == [f"login {PLACEHOLDER}", "clean"]

    def test_the_model_still_serializes(self, engine: RedactionEngine) -> None:
        """A dump/validate round trip would fail here, so the helper must not use one."""
        entries = LogEntries(entries=[SECRET])
        dumped = redact_tool_output(entries, engine).model_dump()

        assert dumped == {"entries": [PLACEHOLDER], "unit": None, "path": None, "lines_count": 1}

    def test_nested_models_inside_containers_are_redacted(self, engine: RedactionEngine) -> None:
        nodes = StorageNodes(nodes=[NodeEntry(name=f"{SECRET}.log"), NodeEntry(name="clean.log")])
        result = redact_tool_output(nodes, engine)

        assert [node.name for node in result.nodes] == [f"{PLACEHOLDER}.log", "clean.log"]

    def test_a_path_field_is_scanned_and_stays_a_path(self, engine: RedactionEngine) -> None:
        """A path reaches the model as text, so a secret in one has to be caught."""
        entries = LogEntries(entries=["clean"], path=Path(f"/var/log/{SECRET}.log"))
        result = redact_tool_output(entries, engine)

        assert result.path == Path(f"/var/log/{PLACEHOLDER}.log")
        assert isinstance(result.path, Path)


class TestToolResult:
    """A tool's own ToolResult has each half scanned separately."""

    def test_text_blocks_are_redacted(self, engine: RedactionEngine) -> None:
        result = redact_tool_output(ToolResult(content=[TextContent(type="text", text=SECRET)]), engine)

        assert isinstance(result.content[0], TextContent)
        assert result.content[0].text == PLACEHOLDER

    def test_structured_content_is_redacted_recursively(self, engine: RedactionEngine) -> None:
        structured = {"state": "success", "nested": {"token": SECRET}, "count": 1}
        result = redact_tool_output(ToolResult(structured_content=structured), engine)

        assert result.structured_content == {"state": "success", "nested": {"token": PLACEHOLDER}, "count": 1}

    def test_both_halves_are_redacted(self, engine: RedactionEngine) -> None:
        result = redact_tool_output(
            ToolResult(
                content=[TextContent(type="text", text=f"output {SECRET}")],
                structured_content={"output": f"output {SECRET}"},
            ),
            engine,
        )

        assert result.structured_content == {"output": f"output {PLACEHOLDER}"}
        assert result.content[0].text == f"output {PLACEHOLDER}"

    def test_non_text_blocks_are_preserved(self, engine: RedactionEngine) -> None:
        image = ImageContent(type="image", data="aGVsbG8=", mimeType="image/png")
        result = redact_tool_output(
            ToolResult(content=[image, TextContent(type="text", text=SECRET)]),
            engine,
        )

        assert result.content[0] == image
        assert result.content[1].text == PLACEHOLDER

    def test_text_the_tool_wrote_is_kept_rather_than_replaced(self, engine: RedactionEngine) -> None:
        """Authored text must survive, not be overwritten by the structure's JSON."""
        result = redact_tool_output(
            ToolResult(
                content=[TextContent(type="text", text="awaiting approval")],
                structured_content={"id": "token123", "status": "OK"},
            ),
            engine,
        )

        assert result.content[0].text == "awaiting approval"


class TestTextDerivedFromStructure:
    """Text FastMCP rendered inside the tool is rebuilt, not scanned as written text."""

    ESCAPED_SECRET = r'pa"ss\word'

    @pytest.fixture
    def escaping_engine(self) -> RedactionEngine:
        """An engine whose rule matches the raw secret but not its JSON spelling."""
        return RedactionEngine(
            RedactionRulesConfig(
                version=1,
                disable_rules=["builtin:*"],
                rules=[RedactionRule(name="pw", description="Password", match=re.escape(self.ESCAPED_SECRET))],
            )
        )

    def test_a_secret_json_escapes_is_not_recoverable_from_the_text(self, escaping_engine: RedactionEngine) -> None:
        """Regression: building a ToolResult without content renders the JSON early."""
        result = redact_tool_output(
            ToolResult(structured_content={"password": self.ESCAPED_SECRET}),
            escaping_engine,
        )

        # Compare decoded values: a repr re-escapes the backslash and would hide the leak.
        assert result.structured_content["password"] == "[REDACTED:custom:pw]"
        assert json.loads(result.content[0].text) == result.structured_content

    def test_derived_text_is_regenerated_from_the_clean_structure(self, engine: RedactionEngine) -> None:
        result = redact_tool_output(ToolResult(structured_content={"token": SECRET, "count": 1}), engine)

        assert result.structured_content == {"token": PLACEHOLDER, "count": 1}
        assert json.loads(result.content[0].text) == {"token": PLACEHOLDER, "count": 1}


class TestEngineFailures:
    """A failed scan must not quietly yield unscanned data."""

    @pytest.fixture
    def failing_engine(self, mocker) -> RedactionEngine:
        engine = mocker.Mock(spec=RedactionEngine)
        engine.redact.side_effect = RuntimeError("regex blew up")
        return engine

    def test_a_scan_failure_propagates(self, failing_engine: RedactionEngine) -> None:
        with pytest.raises(RuntimeError, match="regex blew up"):
            redact_tool_output("string", failing_engine)

        with pytest.raises(RuntimeError, match="regex blew up"):
            redact_tool_output({"key": "value"}, failing_engine)

        with pytest.raises(RuntimeError, match="regex blew up"):
            redact_tool_output(LogEntries(entries=["test"]), failing_engine)
