"""Core redaction engine for pattern matching and replacement."""

import fnmatch
import logging
import re

from pathlib import Path
from typing import Any

import yaml

from pydantic import BaseModel
from pydantic import ValidationError

from linux_mcp_server.config import RedactionConfig
from linux_mcp_server.redaction.models import RedactionRule
from linux_mcp_server.redaction.models import RedactionRulesConfig


logger = logging.getLogger(__name__)


# Convert leading inline flags like (?i) to scoped form (?i:...) so patterns can be combined.
_LEADING_INLINE_FLAGS = re.compile(r"^\(\?([aiLmsux]+)\)")


# Built-in credential rules (enabled by default). This set is not stable yet; when restructuring
# it, leave an alias behind so a config naming an old rule still starts.
BUILTIN_CREDENTIAL_RULES = [
    RedactionRule.model_construct(
        name="builtin:credentials:generic_key_value",
        description="Generic key=value patterns where key contains sensitive keywords",
        # Quoted values are taken whole so a secret containing spaces is not cut at the first one.
        match=(
            r"(?i)(?:password|passwd|pwd|secret|token|key|credential)s?"
            r'["\']?\s*[=:]\s*'
            r'("(?:[^"\n\\]|\\.)*"|\'(?:[^\'\n\\]|\\.)*\'|["\'][^\n]*|[^\s"\',;}\]]+)'
        ),
    ),
    RedactionRule.model_construct(
        name="builtin:credentials:command_line_password",
        description="Password arguments in command lines (--password, -p)",
        # With mysql and similar commands '-p <arg>' prompts for a password, while '-p<arg>'
        # uses <arg> as the password - so we require whitespace before and no whitespace after -p
        match=r"(?:--password(?:=|\s+)|--pwd(?:=|\s+)|\s-p)([^\s]+)",
    ),
    RedactionRule.model_construct(
        name="builtin:credentials:url_credentials",
        description="Credentials embedded in URLs",
        match=r"(?i)(?:https?|ftp)://[^:/@\s]+:([^@\s]+)@",
    ),
    RedactionRule.model_construct(
        name="builtin:credentials:authorization_header",
        description="Authorization header values (Bearer, Basic)",
        match=r"(?i)authorization\s*:\s*(?:bearer|basic)\s+([^\s]+)",
    ),
    RedactionRule.model_construct(
        name="builtin:credentials:pem_private_key",
        description="PEM-encoded private keys",
        match=r"(-----BEGIN[A-Z\s]*PRIVATE KEY-----.*?-----END[A-Z\s]*PRIVATE KEY-----)",
    ),
    RedactionRule.model_construct(
        name="builtin:credentials:gcp_key",
        description="GCP service account keys and API keys",
        # Matches service account private key OR GCP API key pattern directly
        match=r'(?:"type":\s*"service_account".*?"private_key":\s*"([^"]+)"|AIza[0-9A-Za-z\\-_]{35})',
    ),
    RedactionRule.model_construct(
        name="builtin:credentials:azure:storage_connection_string",
        description="Credentials within Azure storage connection strings",
        # Excluding whitespace stops an unterminated key from swallowing the following lines.
        match=r"(?:AccountKey|SharedAccessSignature)=([^;\s]+)",
    ),
    RedactionRule.model_construct(
        name="builtin:credentials:jwt",
        description="JSON Web Tokens",
        match=r"(eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*)",
    ),
]


def _as_capturing_group(pattern: str) -> str:
    """Wrap a rule pattern in a capturing group, rescoping leading global inline flags."""
    flags = _LEADING_INLINE_FLAGS.match(pattern)
    if flags:
        return f"((?{flags.group(1)}:{pattern[flags.end() :]}))"
    return f"({pattern})"


class _ActiveRule(BaseModel):
    """A rule's placement within the combined pattern."""

    name: str
    description: str
    pattern: str
    group: int
    value_groups: list[int]


class RedactionMatch(BaseModel):
    """A piece of text that a rule matched."""

    rule: str
    start: int
    end: int
    text: str


class RedactionEngine:
    """Engine for applying redaction rules to text."""

    def __init__(self, config: RedactionRulesConfig | None = None) -> None:
        """Initialize the redaction engine.

        Args:
            config: Optional configuration with custom rules and enable/disable lists.
                   If None, only built-in credential rules are active.
        """
        self.config = config or RedactionRulesConfig(version=1)
        self._rules: list[_ActiveRule] = []
        self._pattern: re.Pattern[str] | None = None
        self._initialize_rules()

    def _initialize_rules(self) -> None:
        """Initialize and compile all active rules."""
        # Start with all built-in rules
        all_rules: dict[str, RedactionRule] = {}

        # Add built-in credential rules
        for rule in BUILTIN_CREDENTIAL_RULES:
            all_rules[rule.name] = rule

        # Add custom rules with 'custom:' namespace
        for rule in self.config.rules:
            namespaced_name = f"custom:{rule.name}"
            if namespaced_name in all_rules:
                raise ValueError(f"Duplicate rule name: {namespaced_name}")
            # Use model_construct to bypass validation since we're adding the namespace
            all_rules[namespaced_name] = RedactionRule.model_construct(
                name=namespaced_name,
                description=rule.description,
                match=rule.match,
            )

        # Filter rules based on enable/disable lists
        active_rules = self._filter_active_rules(all_rules)

        # Combine every active rule into one alternation so a single scan redacts the whole text.
        # Wrapping each rule shifts its group numbers by the groups contributed by rules ahead.
        alternatives: list[str] = []
        next_group = 1

        for name, rule in active_rules.items():
            wrapped = _as_capturing_group(rule.match)
            try:
                # Compiling the wrapped form means wrapping errors name the rule.
                group_count = re.compile(wrapped).groups - 1
            except re.error as e:
                raise ValueError(f"Failed to compile rule '{name}': {e}") from e

            alternatives.append(wrapped)
            self._rules.append(
                _ActiveRule(
                    name=name,
                    description=rule.description,
                    pattern=rule.match,
                    group=next_group,
                    value_groups=list(range(next_group + 1, next_group + 1 + group_count)),
                )
            )
            next_group += 1 + group_count

        if alternatives:
            try:
                self._pattern = re.compile("|".join(alternatives), re.DOTALL | re.MULTILINE)
            except re.error as e:
                # Reached when rules only conflict once merged, such as a reused group name.
                raise ValueError(f"Failed to combine redaction rules into one pattern: {e}") from e

    def _filter_active_rules(self, all_rules: dict[str, RedactionRule]) -> dict[str, RedactionRule]:
        """Filter rules based on enable/disable lists with most-specific-pattern precedence.

        Args:
            all_rules: Dictionary of all available rules (built-in + custom)

        Returns:
            Dictionary of active rules after applying enable/disable filters

        Raises:
            ValueError: If unknown rule names are found in enable_rules or disable_rules
        """
        # Validate that all patterns in enable/disable lists match at least one rule
        all_rule_names = set(all_rules.keys())

        # Check for unknown patterns in disable_rules
        for pattern in self.config.disable_rules:
            if not self._pattern_matches_any_rule(pattern, all_rule_names):
                raise ValueError(f"Unknown rule pattern in disable_rules: {pattern}")

        # Check for unknown patterns in enable_rules
        for pattern in self.config.enable_rules:
            if not self._pattern_matches_any_rule(pattern, all_rule_names):
                raise ValueError(f"Unknown rule pattern in enable_rules: {pattern}")

        # Determine which rules are active
        active_rules = {}
        for name, rule in all_rules.items():
            # Default state: all built-in credential rules and custom rules are enabled
            is_enabled = True

            # Apply enable/disable rules with most-specific-pattern wins
            disabled_by = self._get_most_specific_match(name, self.config.disable_rules)
            enabled_by = self._get_most_specific_match(name, self.config.enable_rules)

            if disabled_by and enabled_by:
                # Both lists mention this rule - most specific wins
                if self._pattern_specificity(disabled_by) > self._pattern_specificity(enabled_by):
                    is_enabled = False
                else:
                    is_enabled = True
            elif disabled_by:
                is_enabled = False
            elif enabled_by:
                is_enabled = True

            if is_enabled:
                active_rules[name] = rule

        return active_rules

    def _pattern_matches_any_rule(self, pattern: str, rule_names: set[str]) -> bool:
        """Check if a pattern matches at least one rule name."""
        # Exact match
        if pattern in rule_names:
            return True

        # Wildcard match
        if "*" in pattern:
            for rule_name in rule_names:
                if fnmatch.fnmatch(rule_name, pattern):
                    return True

        return False

    def _get_most_specific_match(self, rule_name: str, patterns: list[str]) -> str | None:
        """Get the most specific pattern that matches the rule name.

        Returns:
            The most specific matching pattern, or None if no match
        """
        matching_patterns = []
        for pattern in patterns:
            if pattern == rule_name:
                # Exact match, most specific possible
                return pattern
            elif "*" in pattern and fnmatch.fnmatch(rule_name, pattern):
                matching_patterns.append(pattern)

        if not matching_patterns:
            return None

        # Return the most specific (longest) pattern
        return max(matching_patterns, key=self._pattern_specificity)

    def _pattern_specificity(self, pattern: str) -> int:
        """Calculate pattern specificity (higher = more specific).

        Specificity is based on:
        1. Number of colon-separated segments
        2. Length of the pattern
        """
        segment_count = pattern.count(":") + 1
        return (segment_count * 1000) + len(pattern)

    def redact(self, text: str) -> str:
        """Apply all active redaction rules to the given text.

        Matches are found in a single left-to-right scan and never overlap. When more than one
        rule can match at the same position, which rule is applied is unspecified.

        Args:
            text: Text to redact

        Returns:
            Redacted text with sensitive data replaced by bracketed placeholders
        """
        if not text or self._pattern is None:
            return text

        return self._pattern.sub(self._replacement, text)

    def find_matches(self, text: str) -> list[RedactionMatch]:
        """Find what redact() would replace in the given text, and which rule replaces it."""
        if not text or self._pattern is None:
            return []

        # finditer() makes the same scan as the sub() in redact(), so it finds the same matches.
        return [
            RedactionMatch(rule=self._rule_for(match).name, start=match.start(), end=match.end(), text=match.group())
            for match in self._pattern.finditer(text)
        ]

    def _rule_for(self, match: re.Match[str]) -> _ActiveRule:
        """Find the rule whose alternative of the combined pattern produced a match."""
        return next(candidate for candidate in self._rules if match.group(candidate.group) is not None)

    def _replacement(self, match: re.Match[str]) -> str:
        """Build the replacement text for one match of the combined pattern."""
        rule = self._rule_for(match)
        placeholder = f"[REDACTED:{rule.name}]"

        pieces: list[str] = []
        cursor = match.start()
        for group in rule.value_groups:
            start, end = match.span(group)
            # A group that sat out spans (-1, -1), and one nested in an earlier group starts behind it.
            if start < cursor:
                continue
            pieces.append(match.string[cursor:start])
            pieces.append(placeholder)
            cursor = end

        # Rules without groups, and rules whose groups all sat out, redact the whole match.
        if not pieces:
            return placeholder

        pieces.append(match.string[cursor : match.end()])
        return "".join(pieces)

    @classmethod
    def from_yaml_file(cls, path: Path) -> "RedactionEngine":
        """Load redaction configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file

        Returns:
            Initialized RedactionEngine

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the YAML is malformed or fails validation
        """
        if not path.exists():
            raise FileNotFoundError(f"Redaction rules file not found: {path}")

        try:
            with path.open("r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML file {path}: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML structure in {path}: expected a dictionary")

        try:
            config = RedactionRulesConfig.model_validate(data)
        except ValidationError as e:
            raise ValueError(f"Invalid redaction rules configuration in {path}: {e}") from e

        return cls(config)

    def list_active_rules(self) -> list[dict[str, Any]]:
        """List all currently active rules.

        Returns:
            List of dictionaries with rule information (name, description, pattern)
        """
        return [
            {
                "name": rule.name,
                "description": rule.description,
                "pattern": rule.pattern,
                "has_capture_group": bool(rule.value_groups),
            }
            for rule in self._rules
        ]


def create_redaction_engine(config: RedactionConfig) -> RedactionEngine | None:
    """Build the engine that the configuration asks for, or None if redaction is turned off.

    Raises:
        FileNotFoundError: If the configured rules file doesn't exist
        ValueError: If the rules file is malformed or its rules are invalid
    """
    if not config.enabled:
        logger.info("Redaction disabled")
        return None

    if config.rules_path is None:
        logger.info("Redaction enabled with built-in credential rules")
        return RedactionEngine()

    logger.info(f"Redaction enabled with rules from {config.rules_path}")
    return RedactionEngine.from_yaml_file(config.rules_path)
