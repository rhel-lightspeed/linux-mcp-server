"""Tests for redacting the value a tool returns."""

import json
import logging

from pathlib import Path

import pytest

from pydantic_core import PydanticSerializationError

from linux_mcp_server.audit import Event
from linux_mcp_server.models import LogEntries
from linux_mcp_server.models import NodeEntry
from linux_mcp_server.models import StorageNodes
from linux_mcp_server.redaction.apply import redact_tool_output
from linux_mcp_server.redaction.engine import RedactionEngine
from linux_mcp_server.redaction.models import RedactionRule
from linux_mcp_server.redaction.models import RedactionRulesConfig
from linux_mcp_server.tool_result import ToolResult


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


class TestPlainValues:
    """Whatever a tool returned is reduced to JSON, and the strings in it are scanned."""

    def test_a_bare_string_is_redacted(self, engine: RedactionEngine) -> None:
        assert redact_tool_output(f"token {SECRET} end", engine) == f"token {PLACEHOLDER} end"

    def test_dictionary_values_are_redacted_and_keys_kept(self, engine: RedactionEngine) -> None:
        assert redact_tool_output({SECRET: SECRET}, engine) == {SECRET: PLACEHOLDER}

    def test_nesting_is_followed_to_any_depth(self, engine: RedactionEngine) -> None:
        value = {"outer": {"inner": [{"deep": SECRET}]}}
        assert redact_tool_output(value, engine) == {"outer": {"inner": [{"deep": PLACEHOLDER}]}}

    def test_sequences_keep_their_order(self, engine: RedactionEngine) -> None:
        assert redact_tool_output([SECRET, "clean"], engine) == [PLACEHOLDER, "clean"]
        assert redact_tool_output((SECRET,), engine) == [PLACEHOLDER]

    def test_non_text_values_are_returned_unchanged(self, engine: RedactionEngine) -> None:
        assert redact_tool_output(42, engine) == 42
        assert redact_tool_output(None, engine) is None


class TestModels:
    """A model is scanned as the JSON that FastMCP would have rendered it to."""

    def test_model_fields_are_redacted(self, engine: RedactionEngine) -> None:
        entries = LogEntries(entries=[f"login {SECRET}", "clean"])

        assert redact_tool_output(entries, engine) == {
            "entries": [f"login {PLACEHOLDER}", "clean"],
            "unit": None,
            "path": None,
            "lines_count": 2,
        }

    def test_nested_models_inside_containers_are_redacted(self, engine: RedactionEngine) -> None:
        nodes = StorageNodes(nodes=[NodeEntry(name=f"{SECRET}.log"), NodeEntry(name="clean.log")])
        result = redact_tool_output(nodes, engine)

        assert [node["name"] for node in result["nodes"]] == [f"{PLACEHOLDER}.log", "clean.log"]

    def test_a_path_field_is_scanned(self, engine: RedactionEngine) -> None:
        """A path reaches the model as text, so a secret in one has to be caught."""
        entries = LogEntries(entries=["clean"], path=Path(f"/var/log/{SECRET}.log"))

        assert redact_tool_output(entries, engine)["path"] == f"/var/log/{PLACEHOLDER}.log"


class TestToolResult:
    """A tool that wrote its own text has each half of the pair scanned separately."""

    def test_both_halves_are_redacted(self, engine: RedactionEngine) -> None:
        result = redact_tool_output(
            ToolResult(content=f"output {SECRET}", structured_content={"output": f"output {SECRET}"}),
            engine,
        )

        assert result.structured_content == {"output": f"output {PLACEHOLDER}"}
        assert result.content[0].text == f"output {PLACEHOLDER}"  # type: ignore[union-attr]

    def test_text_the_tool_wrote_is_kept_rather_than_replaced(self, engine: RedactionEngine) -> None:
        """Authored text must survive, not be overwritten by the structure's JSON."""
        result = redact_tool_output(
            ToolResult(content="awaiting approval", structured_content={"id": "token123", "status": "OK"}),
            engine,
        )

        assert result.content[0].text == "awaiting approval"  # type: ignore[union-attr]

    def test_structured_content_is_optional(self, engine: RedactionEngine) -> None:
        result = redact_tool_output(ToolResult(content=SECRET), engine)

        assert result.structured_content is None
        assert result.content[0].text == PLACEHOLDER  # type: ignore[union-attr]

    def test_a_structured_model_is_scanned_as_json(self, engine: RedactionEngine) -> None:
        result = redact_tool_output(ToolResult(content="text", structured_content=LogEntries(entries=[SECRET])), engine)

        assert result.structured_content == {
            "entries": [PLACEHOLDER],
            "unit": None,
            "path": None,
            "lines_count": 1,
        }

    def test_the_pair_is_still_rendered_with_no_engine(self) -> None:
        """Turning redaction off must not leave FastMCP to render the pair as a value."""
        result = redact_tool_output(
            ToolResult(content="awaiting approval", structured_content={"id": "token123"}),
            None,
        )

        assert result.content[0].text == "awaiting approval"  # type: ignore[union-attr]
        assert result.structured_content == {"id": "token123"}


class TestMatchCounts:
    """One audit event collects what matched across the whole response."""

    def test_every_string_in_the_response_adds_to_the_totals(self, engine: RedactionEngine, caplog) -> None:
        value = {"stdout": f"{SECRET} {SECRET}", "lines": [SECRET, "clean"], "code": 0}

        with caplog.at_level(logging.INFO):
            redacted = redact_tool_output(value, engine)

        assert redacted == {"stdout": f"{PLACEHOLDER} {PLACEHOLDER}", "lines": [PLACEHOLDER, "clean"], "code": 0}
        events = [r for r in caplog.records if getattr(r, "audit_event", None) == Event.REDACTION_APPLIED]
        assert len(events) == 1
        assert events[0].__dict__["rules"] == [{"name": "custom:secret", "matches": 3}]

    def test_both_halves_of_a_tool_result_count_together(self, engine: RedactionEngine, caplog) -> None:
        with caplog.at_level(logging.INFO):
            result = redact_tool_output(ToolResult(content=SECRET, structured_content={"output": SECRET}), engine)

        assert result.content[0].text == PLACEHOLDER  # type: ignore[union-attr]
        assert result.structured_content == {"output": PLACEHOLDER}
        events = [r for r in caplog.records if getattr(r, "audit_event", None) == Event.REDACTION_APPLIED]
        assert len(events) == 1
        assert events[0].__dict__["rules"] == [{"name": "custom:secret", "matches": 2}]

    def test_a_later_failure_does_not_log_partial_counts(self, engine: RedactionEngine, caplog) -> None:
        value = ToolResult(content=SECRET, structured_content={"unserializable": object()})

        with caplog.at_level(logging.INFO), pytest.raises(PydanticSerializationError):
            redact_tool_output(value, engine)

        assert not any(getattr(r, "audit_event", None) == Event.REDACTION_APPLIED for r in caplog.records)


class TestEscapedSecrets:
    """A secret that JSON respells must not survive in the text rendered from it."""

    ESCAPED_SECRET = r'pa"ss\word'

    @pytest.fixture
    def escaping_engine(self) -> RedactionEngine:
        """An engine whose rule matches the raw secret but not its JSON spelling."""
        return RedactionEngine(
            RedactionRulesConfig(
                version=1,
                disable_rules=["builtin:*"],
                rules=[RedactionRule(name="pw", description="Password", match=r'pa"ss\\word')],
            )
        )

    def test_the_secret_is_gone_before_any_text_is_rendered(self, escaping_engine: RedactionEngine) -> None:
        """The scanned document is what FastMCP renders, so the escaping cannot hide it."""
        redacted = redact_tool_output({"password": self.ESCAPED_SECRET}, escaping_engine)

        assert redacted == {"password": "[REDACTED:custom:pw]"}
        # Compare decoded values: a repr re-escapes the backslash and would hide a leak.
        assert json.loads(json.dumps(redacted)) == redacted


class TestEngineFailures:
    """A failed scan must not quietly yield unscanned data."""

    @pytest.fixture
    def failing_engine(self, mocker) -> RedactionEngine:
        engine = mocker.Mock(spec=RedactionEngine)
        engine.redact.side_effect = RuntimeError("regex blew up")
        return engine

    @pytest.mark.parametrize(
        "value",
        [
            "string",
            {"key": "value"},
            LogEntries(entries=["test"]),
            ToolResult(content="text"),
        ],
        ids=["string", "dict", "model", "tool-result"],
    )
    def test_a_scan_failure_propagates(self, value, failing_engine: RedactionEngine) -> None:
        with pytest.raises(RuntimeError, match="regex blew up"):
            redact_tool_output(value, failing_engine)
