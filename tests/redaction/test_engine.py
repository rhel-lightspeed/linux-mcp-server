"""Tests for the redaction engine."""

from pathlib import Path

import pytest
import yaml

from linux_mcp_server.redaction.engine import RedactionEngine
from linux_mcp_server.redaction.engine import RedactionMatch
from linux_mcp_server.redaction.models import RedactionRule
from linux_mcp_server.redaction.models import RedactionRulesConfig
from linux_mcp_server.redaction.models import RedactionStats


JWT_RULE = "builtin:credentials:jwt"


def custom_engine(*rules: RedactionRule) -> RedactionEngine:
    """Build an engine holding only the given rules, so built-ins cannot interfere."""
    config = RedactionRulesConfig(version=1, disable_rules=["builtin:*"], rules=list(rules))
    return RedactionEngine(config)


class TestRuleLoading:
    """Tests for which rules end up active."""

    def test_builtin_credential_rules_are_active_by_default(self) -> None:
        """An engine with no configuration still redacts credentials."""
        rule_names = [rule["name"] for rule in RedactionEngine().list_active_rules()]

        assert rule_names
        assert all(name.startswith("builtin:credentials:") for name in rule_names)

    def test_duplicate_custom_rule_rejected(self) -> None:
        """Two rules sharing a name would make the placeholder ambiguous."""
        config = RedactionRulesConfig(
            version=1,
            rules=[
                RedactionRule(name="duplicate", description="First", match=r"test1"),
                RedactionRule(name="duplicate", description="Second", match=r"test2"),
            ],
        )

        with pytest.raises(ValueError, match="Duplicate rule name"):
            RedactionEngine(config)

    @pytest.mark.parametrize(
        ("disable", "enable", "is_active"),
        [
            pytest.param([JWT_RULE], [], False, id="disabled-by-name"),
            pytest.param(["builtin:credentials:*"], [JWT_RULE], True, id="specific-enable-wins"),
            pytest.param([JWT_RULE], ["builtin:*"], False, id="specific-disable-wins"),
            pytest.param(["builtin:*"], ["builtin:*"], True, id="equal-specificity-enables"),
        ],
    )
    def test_enable_disable_precedence(self, disable: list[str], enable: list[str], is_active: bool) -> None:
        """The most specific pattern decides, and ties fall to enabling."""
        config = RedactionRulesConfig(version=1, disable_rules=disable, enable_rules=enable)
        rule_names = [rule["name"] for rule in RedactionEngine(config).list_active_rules()]

        assert (JWT_RULE in rule_names) is is_active

    @pytest.mark.parametrize(
        "disable",
        [
            pytest.param(["builtin:nonexistent"], id="unknown-name"),
            pytest.param(["nosuch:*"], id="wildcard-matching-nothing"),
        ],
    )
    def test_unknown_rule_pattern_rejected(self, disable: list[str]) -> None:
        """A name that matches nothing is a typo, and ignoring it would hide the mistake."""
        config = RedactionRulesConfig(version=1, disable_rules=disable)

        with pytest.raises(ValueError, match="Unknown rule pattern"):
            RedactionEngine(config)


class TestMatching:
    """Tests for how matches are found and replaced."""

    @pytest.mark.parametrize(
        ("text", "secret"),
        [
            pytest.param("password=secret123 tail", "secret123", id="key-value"),
            pytest.param("mysql -u bob --password=mypass123 -h host", "mypass123", id="command-line"),
            pytest.param("https://user:secretpass@example.com/api", "secretpass", id="url-credentials"),
            pytest.param("header eyJhbG.eyJzdWI.dozjgNry tail", "eyJhbG.eyJzdWI.dozjgNry", id="jwt"),
        ],
    )
    def test_credentials_are_redacted(self, text: str, secret: str) -> None:
        """Each built-in rule removes the secret it is meant to catch."""
        result = RedactionEngine().redact(text)

        assert secret not in result
        assert "[REDACTED:builtin:credentials:" in result

    def test_every_match_in_the_text_is_replaced(self) -> None:
        """Scanning continues past the first match."""
        result = RedactionEngine().redact("password=one key=two token=three")

        assert result.count("[REDACTED:") == 3
        assert not any(secret in result for secret in ("one", "two", "three"))

    @pytest.mark.parametrize(
        ("pattern", "text", "expected"),
        [
            pytest.param(r"CODE:\w+", "a CODE:AB1 b", "a [REDACTED:custom:r] b", id="no-group-redacts-match"),
            pytest.param(r'f="([^"]+)"', 'a f="x" b', 'a f="[REDACTED:custom:r]" b', id="group-keeps-context"),
            pytest.param(r"(?:TOKEN|C=(\w+))", "a TOKEN b", "a [REDACTED:custom:r] b", id="group-sat-out"),
            pytest.param(r"(?:TOKEN|C=(\w+))", "a C=xy b", "a C=[REDACTED:custom:r] b", id="group-took-part"),
        ],
    )
    def test_group_semantics(self, pattern: str, text: str, expected: str) -> None:
        """A participating group is redacted on its own; otherwise the whole match goes."""
        engine = custom_engine(RedactionRule(name="r", description="Test", match=pattern))

        assert engine.redact(text) == expected


class TestCombinedPatternEdgeCases:
    """Regression tests for behaviour that only shows up once rules share one pattern."""

    @pytest.mark.parametrize(
        ("text", "secret"),
        [
            pytest.param('password="my secret pass"', "secret pass", id="double-quoted-with-spaces"),
            pytest.param("password='it is secret'", "is secret", id="single-quoted-with-spaces"),
            pytest.param('{"password": "hunter2"}', "hunter2", id="json-quoted-key"),
            pytest.param('password="abc', "abc", id="unterminated-quote"),
        ],
    )
    def test_quoted_values_are_removed_whole(self, text: str, secret: str) -> None:
        """A quoted secret must not be cut at its first space, leaving the rest in the clear."""
        result = RedactionEngine().redact(text)

        assert secret not in result
        assert "[REDACTED:builtin:credentials:generic_key_value]" in result

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("mkdir -p /var/log/myapp", id="mkdir"),
            pytest.param("cp -p source dest", id="cp"),
            pytest.param("ps -p 1234", id="ps"),
            pytest.param("ssh -p 2222 host", id="ssh"),
        ],
    )
    def test_unrelated_p_flags_are_left_alone(self, text: str) -> None:
        """-p only carries a password when the value is attached, as in mysql's -psecret."""
        assert RedactionEngine().redact(text) == text

    def test_attached_p_value_is_redacted(self) -> None:
        """The mysql form still loses its password."""
        result = RedactionEngine().redact("mysql -u bob -phunter2")

        assert "hunter2" not in result
        assert result.startswith("mysql -u bob -p")

    def test_p_in_bracketed_text_is_not_redacted(self) -> None:
        """[per-pid] and similar patterns should not be treated as -p flags."""
        text = "Per-pid history [per-pid] and [per-process] metrics"
        assert RedactionEngine().redact(text) == text

    def test_azure_key_stops_at_end_of_line(self) -> None:
        """An unterminated key must not swallow the lines that follow it."""
        result = RedactionEngine().redact("AccountKey=abc123\nUnrelated line")

        assert "abc123" not in result
        assert result.endswith("\nUnrelated line")

    def test_every_capture_group_is_redacted(self) -> None:
        """A rule capturing two secrets must not redact one and leave the other in the clear."""
        engine = custom_engine(RedactionRule(name="pair", description="Test", match=r"user=(\S+) pass=(\S+)"))

        result = engine.redact("user=bob pass=TOPSECRET")

        assert result == "user=[REDACTED:custom:pair] pass=[REDACTED:custom:pair]"

    def test_nested_groups_redact_once(self) -> None:
        """A group nested in another must not produce a second placeholder."""
        engine = custom_engine(RedactionRule(name="nested", description="Test", match=r"id=((\w+)-\w+)"))

        assert engine.redact("id=ab-cd end") == "id=[REDACTED:custom:nested] end"

    def test_rule_keeps_its_own_inline_flags(self) -> None:
        """A rule's leading (?i) must not leak into or be lost by the neighbouring rules."""
        engine = custom_engine(
            RedactionRule(name="insensitive", description="Test", match=r"(?i)ALPHA=(\w+)"),
            RedactionRule(name="sensitive", description="Test", match=r"BETA=(\w+)"),
        )

        assert "one" not in engine.redact("alpha=one")
        assert engine.redact("beta=two") == "beta=two"
        assert "two" not in engine.redact("BETA=two")

    def test_reused_group_name_reports_a_clear_error(self) -> None:
        """Two rules can each be valid alone yet collide once merged."""
        with pytest.raises(ValueError, match="Failed to combine redaction rules into one pattern"):
            custom_engine(
                RedactionRule(name="first", description="Test", match=r"a=(?P<v>\w+)"),
                RedactionRule(name="second", description="Test", match=r"b=(?P<v>\w+)"),
            )


class TestMatchCounts:
    """What the caller's stats collect from a scan, when they pass any."""

    def test_each_rule_is_counted_as_it_fires(self) -> None:
        """Stats accumulate over the strings the caller scans with them, and no others."""
        engine = custom_engine(
            RedactionRule(name="first", description="Test", match=r"A=(\w+)"),
            RedactionRule(name="second", description="Test", match=r"B=(\w+)"),
        )
        stats = RedactionStats()

        redacted = engine.redact("A=one B=two A=three", stats)
        engine.redact("A=four")

        assert redacted == "A=[REDACTED:custom:first] B=[REDACTED:custom:second] A=[REDACTED:custom:first]"
        assert stats.match_counts == {"custom:first": 2, "custom:second": 1}

    def test_a_match_replacing_two_groups_counts_once(self) -> None:
        """The count says how often a rule fired, not how many placeholders it left."""
        engine = custom_engine(RedactionRule(name="pair", description="Test", match=r"user=(\S+) pass=(\S+)"))
        stats = RedactionStats()

        assert engine.redact("user=bob pass=TOPSECRET", stats).count("[REDACTED:") == 2
        assert stats.match_counts == {"custom:pair": 1}


class TestYAMLLoading:
    """Tests for loading configuration from YAML files."""

    def test_load_from_yaml_file(self, tmp_path: Path) -> None:
        """A rules file supplies custom rules and switches built-ins off."""
        yaml_file = tmp_path / "rules.yaml"
        yaml_file.write_text(
            yaml.dump(
                {
                    "version": 1,
                    "disable_rules": [JWT_RULE],
                    "rules": [{"name": "custom_rule", "description": "Test", "match": r"DATACODE:(\w+)"}],
                }
            )
        )

        rule_names = [rule["name"] for rule in RedactionEngine.from_yaml_file(yaml_file).list_active_rules()]

        assert "custom:custom_rule" in rule_names
        assert JWT_RULE not in rule_names

    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            pytest.param("this is not: [valid yaml", "Failed to parse YAML", id="malformed"),
            pytest.param("version: 99", "Invalid redaction rules configuration", id="fails-validation"),
        ],
    )
    def test_invalid_file_rejected(self, tmp_path: Path, content: str, expected: str) -> None:
        """A rules file that cannot be trusted stops start-up rather than redacting nothing."""
        yaml_file = tmp_path / "rules.yaml"
        yaml_file.write_text(content)

        with pytest.raises(ValueError, match=expected):
            RedactionEngine.from_yaml_file(yaml_file)


class TestFindMatches:
    """Tests for reporting what redaction replaces."""

    def test_each_match_names_its_rule(self) -> None:
        engine = custom_engine(
            RedactionRule(name="alpha", description="Alpha", match=r"alpha=(\w+)"),
            RedactionRule(name="beta", description="Beta", match=r"beta"),
        )

        assert engine.find_matches("alpha=1 beta\nalpha=2") == [
            RedactionMatch(rule="custom:alpha", start=0, end=7, text="alpha=1"),
            RedactionMatch(rule="custom:beta", start=8, end=12, text="beta"),
            RedactionMatch(rule="custom:alpha", start=13, end=20, text="alpha=2"),
        ]

    @pytest.mark.parametrize("text", ["", "nothing to see here"])
    def test_no_matches(self, text: str) -> None:
        assert RedactionEngine().find_matches(text) == []

    def test_no_active_rules(self) -> None:
        assert custom_engine().find_matches("password=hunter2") == []

    def test_rules_are_listed_with_their_description(self) -> None:
        engine = custom_engine(RedactionRule(name="alpha", description="Alpha", match="alpha"))

        assert engine.list_active_rules() == [
            {"name": "custom:alpha", "description": "Alpha", "pattern": "alpha", "has_capture_group": False}
        ]
