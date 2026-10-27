"""Tests for the --redact-list and --redact-test commands."""

import io

from pathlib import Path
from typing import Any

import pytest
import yaml

from linux_mcp_server.config import Config
from linux_mcp_server.config import RedactionConfig
from linux_mcp_server.redaction.cli import run


@pytest.fixture
def make_config(mock_getuser):
    def make_config(rules: dict[str, Any] | None = None, tmp_path: Path | None = None, **kwargs: Any) -> Config:
        redaction = RedactionConfig(enabled=True, rules_path=None)
        if rules is not None:
            assert tmp_path is not None
            rules_path = tmp_path / "redaction.yaml"
            rules_path.write_text(yaml.dump(rules))
            redaction = RedactionConfig(enabled=True, rules_path=rules_path)
        return Config(redaction=redaction, **kwargs)

    return make_config


class TestRedactList:
    def test_built_in_rules_are_listed(self, make_config, capsys):
        assert run(make_config(redact_list=True)) == 0

        out, err = capsys.readouterr()
        assert "builtin:credentials:jwt\n    JSON Web Tokens\n" in out
        assert not err

    def test_rules_file_is_used(self, make_config, tmp_path, capsys):
        rules = {
            "version": 1,
            "disable_rules": ["builtin:*"],
            "rules": [{"name": "hushhush", "description": "The secret word", "match": "hushhush"}],
        }

        assert run(make_config(rules, tmp_path, redact_list=True)) == 0

        out, _ = capsys.readouterr()
        assert out == "custom:hushhush\n    The secret word\n    hushhush\n"

    def test_no_active_rules(self, make_config, tmp_path, capsys):
        rules = {"version": 1, "disable_rules": ["builtin:*"]}

        assert run(make_config(rules, tmp_path, redact_list=True)) == 0

        out, err = capsys.readouterr()
        assert not out
        assert "No redaction rules are active" in err


class TestRedactTest:
    @pytest.fixture
    def stdin(self, monkeypatch):
        def stdin(text: str) -> None:
            monkeypatch.setattr("sys.stdin", io.StringIO(text))

        return stdin

    def test_standard_input_is_redacted(self, make_config, stdin, capsys):
        stdin("user=admin\npassword=hunter2")

        assert run(make_config(redact_test=True)) == 0

        out, err = capsys.readouterr()
        assert out == "user=admin\npassword=[REDACTED:builtin:credentials:generic_key_value]\n"
        assert "line 2: builtin:credentials:generic_key_value: 'password=hunter2'" in err

    def test_trailing_newline_is_not_doubled(self, make_config, stdin, capsys):
        stdin("password=hunter2\n")

        assert run(make_config(redact_test=True)) == 0

        out, _ = capsys.readouterr()
        assert out == "password=[REDACTED:builtin:credentials:generic_key_value]\n"

    def test_nothing_matched(self, make_config, stdin, capsys):
        stdin("nothing to see")

        assert run(make_config(redact_test=True)) == 0

        out, err = capsys.readouterr()
        assert out == "nothing to see\n"
        assert "No rules matched" in err

    def test_long_match_is_cut_short(self, make_config, stdin, capsys):
        stdin("-----BEGIN PRIVATE KEY-----\n" + "A" * 200 + "\n-----END PRIVATE KEY-----")

        assert run(make_config(redact_test=True)) == 0

        _, err = capsys.readouterr()
        assert "'-----BEGIN PRIVATE KEY-----\\nAAAA" in err
        assert "AAA...'" in err
        assert "A" * 100 not in err


class TestErrors:
    def test_both_commands(self, make_config, capsys):
        assert run(make_config(redact_list=True, redact_test=True)) == 1

        _, err = capsys.readouterr()
        assert "can't be used together" in err

    def test_redaction_disabled(self, mock_getuser, capsys):
        config = Config(redaction=RedactionConfig(enabled=False), redact_list=True)

        assert run(config) == 1

        _, err = capsys.readouterr()
        assert "redaction is disabled" in err

    @pytest.mark.parametrize(
        ("rules", "expected"),
        [
            ({"version": 1, "disable_rules": ["builtin:nope"]}, "Unknown rule pattern"),
            ({"version": 1, "rules": [{"name": "bad", "description": "Bad", "match": "("}]}, "Invalid regex"),
        ],
    )
    def test_bad_rules_file(self, make_config, tmp_path, capsys, rules, expected):
        assert run(make_config(rules, tmp_path, redact_list=True)) == 1

        _, err = capsys.readouterr()
        assert expected in err

    def test_missing_rules_file(self, mock_getuser, tmp_path, capsys):
        config = Config(redaction=RedactionConfig(rules_path=tmp_path / "missing.yaml"), redact_list=True)

        assert run(config) == 1

        _, err = capsys.readouterr()
        assert "not found" in err
