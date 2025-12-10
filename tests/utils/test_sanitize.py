"""Tests for command-line sanitization utilities."""

import pytest

from linux_mcp_server.utils.sanitize import REDACTED
from linux_mcp_server.utils.sanitize import sanitize_cmdline


def test_sanitize_cmdline_none():
    """None input should return None."""
    result = sanitize_cmdline(None)

    assert result is None


def test_sanitize_cmdline_empty():
    """Empty list should return empty list."""
    result = sanitize_cmdline([])

    assert result == []


def test_sanitize_cmdline_no_secrets():
    """Command with no secrets should remain unchanged."""
    cmdline = ["ls", "-la", "/home/user"]
    result = sanitize_cmdline(cmdline)

    assert result == ["ls", "-la", "/home/user"]


@pytest.mark.parametrize(
    ("cmdline", "expected"),
    (
        # Short flag with separate value
        (
            ["mysql", "-p", "secretpass", "-u", "admin"],
            ["mysql", "-p", REDACTED, "-u", "admin"],
        ),
        # Long flag with separate value
        (
            ["curl", "--password", "mypass", "http://example.com"],
            ["curl", "--password", REDACTED, "http://example.com"],
        ),
        # Long flag with equals
        (
            ["curl", "--password=mypass", "http://example.com"],
            ["curl", f"--password={REDACTED}", "http://example.com"],
        ),
        # Mixed case in key=value pattern
        (
            ["app", "PASSWORD=secret123"],
            ["app", f"PASSWORD={REDACTED}"],
        ),
        # Token pattern
        (
            ["gh", "auth", "login", "--token=ghp_1234567890abcdef"],
            ["gh", "auth", "login", f"--token={REDACTED}"],
        ),
        # API key pattern with underscore
        (
            ["script.py", "--api_key=sk-1234567890"],
            ["script.py", f"--api_key={REDACTED}"],
        ),
        # Multiple secrets
        (
            ["db", "-p", "dbpass", "--token=abc123", "connect"],
            ["db", "-p", REDACTED, f"--token={REDACTED}", "connect"],
        ),
        # Secret flag at end (no value to redact)
        (
            ["cmd", "arg1", "-p"],
            ["cmd", "arg1", "-p"],
        ),
        # Various secret flags
        (
            ["app", "--secret", "s3cr3t"],
            ["app", "--secret", REDACTED],
        ),
        (
            ["app", "-k", "mykey"],
            ["app", "-k", REDACTED],
        ),
        (
            ["app", "--apikey", "key123"],
            ["app", "--apikey", REDACTED],
        ),
        (
            ["app", "--auth", "bearer token"],
            ["app", "--auth", REDACTED],
        ),
        (
            ["app", "--credential", "cred123"],
            ["app", "--credential", REDACTED],
        ),
        (
            ["app", "--private-key", "/path/to/key"],
            ["app", "--private-key", REDACTED],
        ),
        # Key=value patterns
        (
            ["app", "pass=secret"],
            ["app", f"pass={REDACTED}"],
        ),
        (
            ["app", "passwd=secret"],
            ["app", f"passwd={REDACTED}"],
        ),
        (
            ["app", "secret=value"],
            ["app", f"secret={REDACTED}"],
        ),
        (
            ["app", "apikey=123"],
            ["app", f"apikey={REDACTED}"],
        ),
        (
            ["app", "credential=xyz"],
            ["app", f"credential={REDACTED}"],
        ),
        (
            ["app", "auth=bearer"],
            ["app", f"auth={REDACTED}"],
        ),
        (
            ["app", "key=value"],
            ["app", f"key={REDACTED}"],
        ),
        # Edge case: equals with empty value
        (
            ["app", "password="],
            ["app", f"password={REDACTED}"],
        ),
        # Non-secret flags that contain secret words but aren't exact matches
        (
            ["app", "--pass-through", "value"],
            ["app", "--pass-through", "value"],
        ),
        # Non-secret key=value patterns should remain unchanged
        (
            ["app", "--verbose=true", "mode=debug"],
            ["app", "--verbose=true", "mode=debug"],
        ),
        # Complex real-world example
        (
            [
                "ssh",
                "-i",
                "/path/to/key",
                "user@host",
                "mysql",
                "-u",
                "root",
                "-p",
                "dbpass",
            ],
            [
                "ssh",
                "-i",
                "/path/to/key",
                "user@host",
                "mysql",
                "-u",
                "root",
                "-p",
                REDACTED,
            ],
        ),
    ),
)
def test_sanitize_cmdline_secrets(cmdline, expected):
    """Various secret formats should be properly redacted."""
    result = sanitize_cmdline(cmdline)

    assert result == expected
