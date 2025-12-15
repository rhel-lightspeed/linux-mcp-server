"""Tests for command registry and utilities."""

import pytest

from linux_mcp_server.commands import substitute_command_args


class TestSubstituteCommandArgs:
    """Tests for substitute_command_args function."""

    @pytest.mark.parametrize(
        ("args", "kwargs", "expected"),
        [
            pytest.param(
                ["ps", "-p", "{pid}"],
                {"pid": 1234},
                ["ps", "-p", "1234"],
                id="basic_substitution",
            ),
            pytest.param(
                ["command", "--user={user}", "--host={host}"],
                {"user": "admin", "host": "localhost"},
                ["command", "--user=admin", "--host=localhost"],
                id="multiple_placeholders",
            ),
            pytest.param(
                ["ls", "-la", "/tmp"],
                {},
                ["ls", "-la", "/tmp"],
                id="no_placeholders",
            ),
            pytest.param(
                [],
                {},
                [],
                id="empty_args",
            ),
            pytest.param(
                ["tail", "-n", "{lines}"],
                {"lines": 100},
                ["tail", "-n", "100"],
                id="int_conversion",
            ),
        ],
    )
    def test_substitution_success(self, args, kwargs, expected):
        """Test successful placeholder substitution."""
        assert substitute_command_args(args, **kwargs) == expected

    @pytest.mark.parametrize(
        ("args", "kwargs", "match"),
        [
            pytest.param(
                ["ps", "-p", "{pid}", "-u", "{user}"],
                {"pid": 1234},
                "Missing required placeholder.*user",
                id="partial_kwargs",
            ),
            pytest.param(
                ["tail", "-n", "{lines}", "{path}"],
                {},
                "Missing required placeholder.*lines",
                id="no_kwargs",
            ),
        ],
    )
    def test_missing_placeholder_raises(self, args, kwargs, match):
        """Test that missing placeholders raise ValueError."""
        with pytest.raises(ValueError, match=match):
            substitute_command_args(args, **kwargs)
