"""Tests for redaction rule validation."""

import pytest

from pydantic import ValidationError

from linux_mcp_server.redaction.models import RedactionRule


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("", "Rule name cannot be empty", id="empty"),
        pytest.param("has spaces", "must contain only alphanumeric", id="invalid-characters"),
        pytest.param("builtin:mine", "cannot start with 'builtin:' prefix", id="reserved-prefix"),
    ],
)
def test_invalid_name_rejected(name: str, expected: str) -> None:
    """Names are restricted so a custom rule cannot pose as a built-in one."""
    with pytest.raises(ValidationError, match=expected):
        RedactionRule(name=name, description="Test", match=r"test")


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        pytest.param(r"[invalid(regex", "Invalid regex pattern", id="syntax-error"),
        pytest.param(r".*", "must not match empty strings", id="matches-empty"),
        pytest.param(r"(\w+)=\1", "Backreferences and conditional", id="backreference"),
        pytest.param(r"(a)?b(?(1)c|d)", "Backreferences and conditional", id="conditional"),
        # '[\1]' is an octal escape, but telling it apart needs a parser, so it is rejected.
        pytest.param(r"x=[\1]", "Backreferences and conditional", id="octal-escape-in-class"),
    ],
)
def test_invalid_pattern_rejected(pattern: str, expected: str) -> None:
    """Patterns that break once rules share one pattern are refused at load time."""
    with pytest.raises(ValidationError, match=expected):
        RedactionRule(name="rule", description="Test", match=pattern)


def test_escaped_backslash_is_not_a_backreference() -> None:
    """A digit after an escaped backslash is literal text, not a group reference."""
    assert RedactionRule(name="ok", description="Test", match=r"value=\\\\1").match == r"value=\\\\1"
