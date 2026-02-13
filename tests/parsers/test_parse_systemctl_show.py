"""Tests for parse_systemctl_show"""

import pytest

from linux_mcp_server.parsers import parse_systemctl_show


@pytest.mark.parametrize(
    "stdout, expected",
    [
        (
            """
            ActiveState=active
            SubState=running
            LoadState=loaded
        """,
            {
                "ActiveState": "active",
                "SubState": "running",
                "LoadState": "loaded",
            },
        ),
        (
            """
            Field=value
            EmptyField=
        """,
            {"Field": "value", "EmptyField": ""},
        ),
    ],
)
def test_parse_systemctl_show(stdout, expected):
    assert parse_systemctl_show(stdout) == expected
