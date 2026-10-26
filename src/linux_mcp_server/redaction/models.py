"""Pydantic models for redaction rule configuration."""

import re

from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator


# Combining rules renumbers capturing groups, so a reference by number silently points at
# another rule's group. Leading backslash pairs are escapes, not the start of a backreference.
_GROUP_NUMBER_REFERENCE = re.compile(r"(?<!\\)(?:\\\\)*\\[1-9]|\(\?\(")


class RedactionRule(BaseModel):
    """A single redaction rule definition."""

    name: str = Field(
        ...,
        description="Unique name for this rule (will be namespaced as 'custom:<name>' for custom rules)",
    )
    description: str = Field(
        ...,
        description="Description of what this rule matches",
    )
    match: str = Field(
        ...,
        description=(
            "Regular expression pattern. Every capturing group, or the entire match if there are "
            "none, is replaced with a redaction placeholder. Write groups that should stay in the "
            "output as '(?:...)'. Backreferences and conditional patterns are rejected."
        ),
    )

    @field_validator("match")
    @classmethod
    def validate_regex(cls, v: str) -> str:
        """Reject patterns that are invalid, match nothing, or break once rules are combined."""
        try:
            compiled = re.compile(v)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}") from e

        # Test against empty string to catch patterns that could match nothing
        if compiled.search(""):
            raise ValueError("Regex pattern must not match empty strings")

        if _GROUP_NUMBER_REFERENCE.search(v):
            raise ValueError(
                "Backreferences and conditional patterns are not supported because rules are "
                "combined into a single pattern that renumbers capturing groups"
            )

        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that the name contains only valid characters."""
        if not v:
            raise ValueError("Rule name cannot be empty")
        # Allow alphanumeric, underscore, hyphen, colon (for namespacing)
        if not re.match(r"^[a-zA-Z0-9_:.-]+$", v):
            raise ValueError(
                "Rule name must contain only alphanumeric characters, underscores, hyphens, periods, or colons"
            )
        # Disallow 'builtin:' prefix in custom rules (this will be checked at load time)
        if v.startswith("builtin:"):
            raise ValueError("Custom rule names cannot start with 'builtin:' prefix")
        return v


class RedactionStats(BaseModel):
    """What redaction matched, accumulated over however many strings share these stats.

    Passed to ``RedactionEngine.redact`` by a caller that wants to know what was caught;
    the engine holds none of its own, being shared between calls.
    """

    match_counts: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "How many times each rule was applied, by rule name. A rule that matched nothing is "
            "absent rather than zero, and a match replacing several capture groups counts once."
        ),
    )

    def record(self, rule_name: str) -> None:
        """Count one match of the named rule."""
        self.match_counts[rule_name] = self.match_counts.get(rule_name, 0) + 1


class RedactionRulesConfig(BaseModel):
    """Configuration for redaction rules."""

    version: Literal[1] = Field(
        ...,
        description="Schema version",
    )
    disable_rules: list[str] = Field(
        default_factory=list,
        description=(
            "List of rule names or patterns to disable. "
            "Supports wildcards (e.g., 'builtin:credentials:*'). "
            "Most-specific pattern wins when resolving conflicts with enable_rules."
        ),
    )
    enable_rules: list[str] = Field(
        default_factory=list,
        description=(
            "List of rule names or patterns to enable (for rules that are off by default). "
            "Supports wildcards (e.g., 'custom:*'). "
            "Most-specific pattern wins when resolving conflicts with disable_rules."
        ),
    )
    rules: list[RedactionRule] = Field(
        default_factory=list,
        description="Custom redaction rules to add",
    )
