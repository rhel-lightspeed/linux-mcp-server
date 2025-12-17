"""Tests for command registry and utilities."""

import pytest

from linux_mcp_server.commands import get_command
from linux_mcp_server.commands import get_command_group
from linux_mcp_server.commands import substitute_command_args


class TestSubstituteCommandArgs:
    """Tests for substitute_command_args function."""

    @pytest.mark.parametrize(
        ("args", "kwargs", "expected"),
        [
            pytest.param(
                ["ps", "-p", "{pid}"],
                {"pid": 1234},
                ("ps", "-p", "1234"),
                id="basic_substitution",
            ),
            pytest.param(
                ("command", "--user={user}", "--host={host}"),
                {"user": "admin", "host": "localhost"},
                ("command", "--user=admin", "--host=localhost"),
                id="multiple_placeholders",
            ),
            pytest.param(
                ("ls", "-la", "/tmp"),
                {},
                ("ls", "-la", "/tmp"),
                id="no_placeholders",
            ),
            pytest.param(
                (),
                {},
                (),
                id="empty_args",
            ),
            pytest.param(
                ("tail", "-n", "{lines}"),
                {"lines": 100},
                ("tail", "-n", "100"),
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
                ("ps", "-p", "{pid}", "-u", "{user}"),
                {"pid": 1234},
                "Missing required placeholder.*user",
                id="partial_kwargs",
            ),
            pytest.param(
                ("tail", "-n", "{lines}", "{path}"),
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


class TestGetCommandGroup:
    """Tests for get_command_group function."""

    @pytest.mark.parametrize(
        ("name", "expected_subcommands"),
        [
            pytest.param("system_info", ["hostname", "kernel"], id="system_info"),
            pytest.param("network_interfaces", ["brief", "detail"], id="network_interfaces"),
        ],
    )
    def test_get_existing_group(self, name, expected_subcommands):
        """Test retrieving existing command groups."""
        group = get_command_group(name)()
        for subcommand in expected_subcommands:
            assert subcommand in group.commands

    def test_nonexistent_group_raises_with_available(self):
        """Test that nonexistent group raises KeyError listing available commands."""
        with pytest.raises(KeyError, match=r"Command 'nonexistent' not found.*Available:.*system_info"):
            get_command_group("nonexistent")()


class TestGetCommand:
    """Tests for get_command function."""

    @pytest.mark.parametrize(
        ("name", "subcommand", "expected_in_args"),
        [
            pytest.param("list_services", "default", "systemctl", id="default_subcommand"),
            pytest.param("network_interfaces", "brief", "ip", id="named_subcommand"),
        ],
    )
    def test_get_command_success(self, name, subcommand, expected_in_args):
        """Test retrieving commands with default and named subcommands."""
        cmd = get_command(name, subcommand)()
        assert expected_in_args in cmd.args

    def test_invalid_command_raises_with_available(self):
        """Test that invalid command raises KeyError listing available commands."""
        with pytest.raises(KeyError, match=r"Command 'invalid' not found.*Available:"):
            get_command("invalid")()

    def test_invalid_subcommand_raises_with_available(self):
        """Test that invalid subcommand raises KeyError listing available subcommands."""
        with pytest.raises(KeyError, match=r"Subcommand 'invalid' not found for 'system_info'.*Available:.*hostname"):
            get_command("system_info", "invalid")()
