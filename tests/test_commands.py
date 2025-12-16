"""Tests for command registry and utilities."""

from contextlib import nullcontext

import pytest

from linux_mcp_server.commands import CommandSpec
from linux_mcp_server.commands import get_command
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


@pytest.mark.parametrize(
    ("should_raise", "name", "commands", "expected_instance"),
    (
        (pytest.raises(TypeError), "list_process", {"list_process": None}, None),
        (pytest.raises(TypeError), "list_process", {"bla": None}, None),
        (pytest.raises(TypeError), "list_process", {"list_process": {"args": ["ps"]}}, None),
        (nullcontext(), "list_process", {"list_process": CommandSpec(args=[])}, CommandSpec),
    ),
)
def test_get_command(should_raise, name, commands, expected_instance, mocker):
    """Test that get_command is raising when a given command is not in the expected format."""
    mocker.patch("linux_mcp_server.commands.COMMANDS", commands)

    with should_raise:
        result = get_command(name)
        assert isinstance(result, expected_instance)
